"""Actual configured CAS→ANN→bridge→SearchLoopRunner→GP transfer workflow.

The analytic producer is an explicit conditional test input. No default
production composition or scientific/ownership authority is inferred from it.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
import torch
from botorch.models import SingleTaskGP

from polisyos.core import artifacts, canon
from polisyos.scientist.methods.autotune.bayesian_generator import (
    BayesianCandidateGenerator,
    SearchSpace,
)
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopSpec,
    persist_benchmark_suite,
)
from polisyos.scientist.methods.autotune.registry import ChampionRegistry
from polisyos.scientist.methods.autotune.runtime import SearchLoopRunner
from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
from polisyos.scientist.methods.search.strategies.types import StrategyState
from tests.unit.scientist.methods.search.strategies.test_transfer import (
    changed_history,
    measured_history,
)


class AnalyticMutation(MutationArtifact):
    x: float


class AnalyticCodec:
    def encode(self, payload):
        return AnalyticMutation.model_validate(payload)

    def decode(self, payload):
        return AnalyticMutation(loop_id="receiving", x=payload["x"])


class AnalyticEvaluator:
    """Compute an actual fixture measurement from the persisted receiving candidate."""

    def evaluate(self, candidate_ref, suite_ref, context):
        del suite_ref
        payload = canon.from_canonical_bytes(context["store"].get_bytes(candidate_ref))
        raw = (payload["x"] - 0.37) ** 2 + 0.01
        return BenchmarkEvaluation(
            loop_id="receiving",
            suite_id="analytic-receiving",
            candidate_ref=candidate_ref,
            selection_metrics={"score": raw},
            guardrails={"finite": True},
            promotable=False,
            status="ok",
            runtime_split_type=BenchmarkSplit.SELECTION,
            metadata={"params": {"x": payload["x"]}},
        )


def configured_generator(manager, target, basis):
    bridge = WarmStartBridge(manager)
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=basis.bounds["parameters"]),
        primary_metric="score",
        direction=MetricDirection.MINIMIZE,
        compare_split=BenchmarkSplit.SELECTION,
        n_initial=3,
        seed=19,
        warm_start_bridge=bridge,
        warm_start_fingerprint=target,
    )
    assert generator.botorch_available, "actual native backend must be ready"
    # Tune work without replacing a model, training call, acquisition or proposal.
    generator._optimizer._config = replace(
        generator._optimizer._config,
        num_restarts=2,
        raw_samples=32,
        refit_interval=20,
        fallback_on_failure=False,
    )
    return generator, bridge


@pytest.mark.parametrize("malformed", [False, True])
def test_actual_public_workflow_fits_only_admitted_original_cas_observations(tmp_path, malformed):
    store, index, manager, source, target, _, basis = measured_history(tmp_path, count=8)
    if malformed:
        source = changed_history(
            store, source, lambda payload: payload["evaluations"][0].update(stage_a_passed="false")
        )
        metadata = source.model_dump(mode="json", exclude={"history_ref", "embedding"})
        metadata["history_ref"] = source.history_ref.model_dump(mode="json")
        index.add(source.run_id, source.embedding, metadata)
    generator, bridge = configured_generator(manager, target, basis)
    optimizer = generator._optimizer
    expected = bridge.load_warm_start(target)
    assert len(expected) == (7 if malformed else 8)
    assert bridge.last_load_report["loaded"] == 8
    assert bridge.last_load_report["rejected"] == (1 if malformed else 0)
    assert len(optimizer._warm_evals) == len(expected)
    suite = persist_benchmark_suite(
        store, BenchmarkSuite(suite_id="analytic-receiving", kind="analytic")
    )
    registry = ChampionRegistry(tmp_path / "champions", store=store)
    spec = SearchLoopSpec(
        loop_id="receiving",
        mutation_codec=AnalyticCodec(),
        candidate_generator=generator,
        benchmark_evaluator=AnalyticEvaluator(),
        promotion_policy=PromotionPolicy(
            loop_id="receiving",
            primary_metric="score",
            unit="analytic-loss",
            direction=MetricDirection.MINIMIZE,
            compare_split=BenchmarkSplit.SELECTION,
        ),
    )
    result = SearchLoopRunner(store=store, registry=registry).run(
        spec, suite_ref=suite, max_iterations=1
    )
    assert result.iterations_completed == 1 and result.stage_b_evaluations == 1
    assert result.history[0].candidate["_strategy_metadata"]["source"] == "bayesian_acquisition"
    assert isinstance(optimizer._model, SingleTaskGP)
    expected_x = torch.tensor([row.params_normalized for row in expected], dtype=torch.double)
    expected_y = torch.tensor([[-row.scalar_score] for row in expected], dtype=torch.double)
    assert torch.equal(optimizer._fitted_train_X.cpu(), expected_x)
    assert torch.equal(optimizer._fitted_train_y_bo.cpu(), expected_y)
    assert {row.provenance_ref for row in optimizer._warm_evals} == {
        row.provenance_ref for row in expected
    }
    assert registry.get("receiving") is None
    checkpoint = optimizer.get_state()
    checkpoint_ref = store.put_bytes(
        checkpoint.to_artifact(),
        artifacts.PutOptions(kind="search.strategy_state", media_type="application/json"),
    )
    replay = StrategyState.from_artifact(store.get_bytes(checkpoint_ref))
    resumed, _ = configured_generator(manager, target, basis)
    resumed._optimizer.set_state(replay)
    assert isinstance(resumed._optimizer._model, SingleTaskGP)
    assert torch.equal(resumed._optimizer._fitted_train_X.cpu(), expected_x)
    assert torch.equal(resumed._optimizer._fitted_train_y_bo.cpu(), expected_y)
    with torch.no_grad():
        before = optimizer._model.posterior(expected_x[:2]).mean
        after = resumed._optimizer._model.posterior(expected_x[:2]).mean
    assert torch.allclose(before, after, rtol=1e-10, atol=1e-10)
    original_ref = artifacts.ArtifactRef.model_validate(expected[0].metadata["evaluation_ref"])
    blob, _ = store._paths(original_ref.artifact_id)
    blob.write_bytes(b"changed original measurement under the same full reference")
    with pytest.raises(ValueError):
        resumed._optimizer.set_state(replay)
    with pytest.raises(ValueError):
        optimizer.suggest([])


def test_configured_origin_mismatch_remains_discovery_only_and_cannot_fit_gp(tmp_path):
    _, _, manager, source, target, _, basis = measured_history(tmp_path, count=8)
    different = basis.model_copy(update={"origin": "different-producer"})
    target = target.model_copy(
        deep=True, update={"origin": different.origin, "numeric_basis": different}
    )
    assert manager.find_similar_runs(target)[0].history_ref == source.history_ref
    generator, bridge = configured_generator(manager, target, different)
    assert bridge.load_warm_start(target) == []
    assert bridge.last_admission_report["rejected"] == 8
    candidate = generator.generate([], None, {})
    assert candidate["_strategy_metadata"]["source"] == "sobol_init"
    assert generator._optimizer._warm_evals == [] and generator._optimizer._model is None
