"""Ordinary controller transfer configuration reaches original CAS rows and GP.

The measured history is the existing analytic input fixture. This checks the
configured receiver and raw training corpus, not population evidence, authority,
optimization quality, or an independently computed posterior.
"""

import pytest
import torch
from botorch.models import SingleTaskGP

from polisyos.core import artifacts, canon
from polisyos.scientist.methods.autotune.bayesian_generator import (
    BayesianCandidateGenerator,
    SearchSpace,
)
from polisyos.scientist.methods.autotune.models import BenchmarkSplit, MetricDirection
from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.objective import (
    BaseObjective,
    CompositeObjective,
    OptimizationDirection,
)
from polisyos.scientist.methods.search.stopping import MaxIterations
from polisyos.scientist.methods.search.strategies.transfer import NumericTransferBasis
from tests.unit.scientist.methods.search.strategies.test_transfer import (
    changed_history,
    measured_history,
)


class _MeasuredScore(BaseObjective):
    @property
    def name(self):
        return "score"

    @property
    def direction(self):
        return OptimizationDirection.MINIMIZE

    def _extract_value(self, results):
        return results["score"]


def _generator(basis):
    # No warm-start constructor injection or numerical workload overrides.
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=basis.bounds["parameters"]),
        primary_metric="score",
        direction=MetricDirection.MINIMIZE,
        compare_split=BenchmarkSplit.SELECTION,
        seed=19,
    )
    assert generator.botorch_available, "actual native backend must be ready"
    assert generator._warm_evals == []
    assert generator._optimizer._warm_evals == []
    assert generator._optimizer._model is None
    return generator


def _controller(generator, manager, target, calls):
    def stage_a(candidate, context):
        del candidate, context
        pytest.fail("disabled Stage A must not execute")

    def stage_b(candidate, context):
        del context
        x = candidate["x"]
        score = (x - 0.37) ** 2 + 0.01
        calls.append({"x": x, "score": score})
        return {
            "simulation_results": {"score": score},
            "feedback": {"verdict": "APPROVE"},
        }

    return SearchController(
        config=SearchConfig(
            stopping=MaxIterations(1),
            objective=CompositeObjective([_MeasuredScore()]),
            enable_stage_a=False,
            transfer_manager=manager,
            transfer_fingerprint=target,
        ),
        candidate_generator=generator,
        stage_a_evaluator=stage_a,
        stage_b_evaluator=stage_b,
    )


def _publish_discovery_pointer(index, source):
    metadata = source.model_dump(mode="json", exclude={"history_ref", "embedding"})
    metadata["history_ref"] = source.history_ref.model_dump(mode="json")
    index.add(source.run_id, source.embedding, metadata)


def test_ordinary_controller_configures_default_bridge_and_fits_eight_original_cas_rows(tmp_path):
    store, _, manager, _, target, originals, basis = measured_history(tmp_path, count=8)
    generator = _generator(basis)
    original_receiver = generator._optimizer
    calls = []
    controller = _controller(generator, manager, target, calls)
    optimizer = generator._optimizer
    assert optimizer is not original_receiver
    bridge = optimizer._warm_start_admission.__self__
    assert type(bridge) is WarmStartBridge and bridge._manager is manager
    assert bridge.last_load_report["loaded"] == 8
    assert bridge.last_load_report["rejected"] == 0
    assert len(generator._warm_evals) == len(optimizer._warm_evals) == 8
    assert optimizer._model is None and calls == []

    # Read the original producer bodies independently of the receiving bridge;
    # expected GP targets are the measured scores, not a fixture fit surrogate.
    ordered = sorted(originals, key=lambda row: row.scalar_score)
    raw_scores = []
    for row in ordered:
        ref = artifacts.ArtifactRef.model_validate(row.metadata["evaluation_ref"])
        raw = canon.from_canonical_bytes(store.get_verified_snapshot(ref).data)
        assert raw["metadata"]["params"] == row.params
        assert raw["runtime_split_type"] == "selection"
        assert raw["guardrails"] == {"finite": True}
        raw_scores.append(raw["selection_metrics"]["score"])
    expected_x = torch.tensor([row.params_normalized for row in ordered], dtype=torch.double)
    expected_y = torch.tensor([[-score] for score in raw_scores], dtype=torch.double)

    result = controller.run({})
    assert result.iterations_completed == result.stage_b_evaluations == 1
    assert result.stage_a_evaluations == 0 and len(calls) == 1
    assert result.best_objective == calls[0]["score"]
    assert result.history[0].candidate["_strategy_metadata"]["source"] == "bayesian_acquisition"
    assert isinstance(optimizer._model, SingleTaskGP)
    assert torch.equal(optimizer._fitted_train_X.cpu(), expected_x)
    assert torch.equal(optimizer._fitted_train_y_bo.cpu(), expected_y)
    assert {row.provenance_ref for row in optimizer._warm_evals} == {
        row.provenance_ref for row in originals
    }
    assert optimizer._fitted_train_X.shape[0] == 8
    # Numerical warm rows are not new controller evaluations or cost receipts.
    assert result.telemetry["new_evaluations"] == 1
    assert result.telemetry["budget_spent"] is None


@pytest.mark.parametrize("change", ["changed_ref", "basis", "direction", "false_outcome"])
def test_ordinary_controller_transfer_refuses_changed_source_or_basis_before_fit(tmp_path, change):
    store, index, manager, source, target, originals, basis = measured_history(tmp_path, count=8)
    generator = _generator(basis)
    original_receiver = generator._optimizer
    calls = []

    if change == "changed_ref":
        for row in originals:
            ref = artifacts.ArtifactRef.model_validate(row.metadata["evaluation_ref"])
            blob, _ = store._paths(ref.artifact_id)
            blob.write_bytes(b"changed original measurement under the same reference")
    elif change in {"basis", "direction"}:
        payload = basis.model_dump(mode="json")
        if change == "basis":
            payload["origin"] = "different-physical-measurement-origin"
        else:
            payload["direction"] = OptimizationDirection.MAXIMIZE.value
        different = NumericTransferBasis.model_validate(payload)
        target = target.model_copy(
            deep=True,
            update={
                "numeric_basis": different,
                "origin": different.origin,
                "objective_directions": {different.metric: different.direction.value},
            },
        )
    else:

        def false_outcomes(history):
            for row in history["evaluations"]:
                ref = artifacts.ArtifactRef.model_validate(row["metadata"]["evaluation_ref"])
                snapshot = store.get_verified_snapshot(ref)
                raw = canon.from_canonical_bytes(snapshot.data)
                raw["guardrails"] = {"finite": False}
                changed = store.put_json(
                    raw,
                    artifacts.PutOptions(
                        kind=snapshot.manifest.kind,
                        media_type=snapshot.manifest.media_type,
                        schema=snapshot.manifest.artifact_schema,
                    ),
                    canon_spec=canon.CanonSpec(forbid_floats=False),
                )
                row["metadata"]["evaluation_ref"] = changed.model_dump(mode="json")
                row["provenance_ref"] = str(changed.artifact_id)

        source = changed_history(store, source, false_outcomes)
        _publish_discovery_pointer(index, source)

    if change == "direction":
        with pytest.raises(ValueError, match="metric/direction/split"):
            _controller(generator, manager, target, calls)
        assert generator._optimizer is original_receiver
    else:
        _controller(generator, manager, target, calls)
        bridge = generator._optimizer._warm_start_admission.__self__
        assert type(bridge) is WarmStartBridge and bridge._manager is manager
        assert bridge.last_load_report["loaded"] == 8
        assert bridge.last_load_report["rejected"] == 8

    assert calls == []
    assert generator._warm_evals == generator._optimizer._warm_evals == []
    assert generator._optimizer._model is None
    assert generator._optimizer._fitted_train_X is None
    assert generator._optimizer._fitted_train_y_bo is None
    assert not generator._activity_started
