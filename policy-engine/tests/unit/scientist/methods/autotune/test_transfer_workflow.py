"""Real CAS -> configured bridge -> loop -> receiving GP, with analytic inputs.

These measurements characterize numerical plumbing only. They are not a
production historical benchmark or evidence of search acceleration.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest

from polisyos.scientist.agent.vector_memory import VectorMemoryStore
from polisyos.scientist.methods.autotune.bayesian_generator import BayesianCandidateGenerator
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopSpec,
    load_model_artifact,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.registry import ChampionRegistry
from polisyos.scientist.methods.autotune.runtime import SearchLoopRunner
from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies._deps import require_botorch, require_torch
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.transfer import (
    RunFingerprint,
    TransferLearningManager,
)
from polisyos.scientist.methods.search.strategies.types import Evaluation, ParameterBounds

_LOG = logging.getLogger(__name__)
_COORDINATES = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.75, 0.9)


class _QuadraticMutation(MutationArtifact):
    x: float


class _QuadraticCodec:
    def encode(self, payload):
        return _QuadraticMutation.model_validate(payload)

    def decode(self, payload):
        return _QuadraticMutation(loop_id="target", x=payload["x"])


class _AnalyticEvaluator:
    """Read the actual candidate CAS input, then measure this bounded function."""

    def evaluate(self, candidate_ref, suite_ref, context):
        store = context["store"]
        candidate = load_model_artifact(store, candidate_ref, _QuadraticMutation)
        suite = load_model_artifact(store, suite_ref, BenchmarkSuite)
        raw_score = 100.0 * candidate.x * candidate.x
        metadata = {
            "params": {"x": candidate.x},
            "directions": {"score": "minimize"},
            "evaluated_at": "2026-10-05T00:00:00+00:00",
        }
        if "warm_start_compatibility" in context:
            metadata["warm_start_compatibility"] = context["warm_start_compatibility"]
        return BenchmarkEvaluation(
            loop_id=context["loop_id"],
            suite_id=suite.suite_id,
            suite_version=suite.suite_version,
            candidate_ref=candidate_ref,
            selection_metrics={"score": raw_score},
            runtime_split_type=BenchmarkSplit.SELECTION,
            metadata=metadata,
            promotable=False,
        )


def _configured_scene(tmp_path, *, changed_origin=False, malformed_outcome=False):
    from polisyos.core.artifacts.store import FileSystemCAS

    require_botorch()
    pytest.importorskip("hnswlib")
    store = FileSystemCAS(tmp_path / "cas")
    space = SearchSpace([ParameterBounds(name="x", lower=0.0, upper=1.0)])
    source = RunFingerprint(
        run_id="source",
        space_hash=space.sobol_space_fingerprint(),
        bounds={"x": [0.0, 1.0]},
        objective_names=["score"],
        split="selection",
        units={"score": "analytic_units"},
        origin="bounded-analytic-quadratic-v1",
        tenant_id="isolated-test-tenant",
        objective_directions={"score": "minimize"},
        embedding=[1.0, 0.0],
    )
    compatibility = {
        "search_space_fingerprint": source.space_hash,
        "input_transform_fingerprint": "Normalize[0,1]",
        "outcome_transform_fingerprint": "Standardize[m=1]",
        "noise_model_fingerprint": "GaussianLikelihood[inferred]",
        "objective_fingerprint": "scalar_score[minimize]",
        "context_fingerprint": source.numeric_context_fingerprint(),
    }
    suite_ref = persist_benchmark_suite(
        store, BenchmarkSuite(suite_id="bounded-analytic", kind="analytic-test")
    )
    evaluator = _AnalyticEvaluator()
    evaluations = []
    original_bytes = {}
    for x in _COORDINATES:
        candidate_ref = persist_mutation_artifact(store, _QuadraticMutation(loop_id="source", x=x))
        original = evaluator.evaluate(
            candidate_ref,
            suite_ref,
            {"store": store, "loop_id": "source", "warm_start_compatibility": compatibility},
        )
        origin_ref = persist_benchmark_evaluation(store, original)
        original_bytes[str(origin_ref.artifact_id)] = store.get_bytes(origin_ref.artifact_id)
        raw_score = original.selection_metrics["score"]
        evaluations.append(
            Evaluation(
                candidate_id=str(candidate_ref.artifact_id),
                params={"x": x},
                params_normalized=space.normalize({"x": x}),
                objectives=[
                    ObjectiveValue(
                        name="score", raw_value=raw_score, direction=OptimizationDirection.MINIMIZE
                    )
                ],
                scalar_score=raw_score,
                stage_a_passed=True,
                provenance_ref=str(origin_ref.artifact_id),
                timestamp=datetime(2026, 10, 5, tzinfo=UTC),
                metadata={"source_run_id": "source", "warm_start_compatibility": compatibility},
            )
        )
    index = VectorMemoryStore(dim=2)
    if malformed_outcome:
        evaluations[0].stage_a_passed = "false"
    source.history_ref = TransferLearningManager(store, index).register_run(source, evaluations)
    target = source.model_copy(update={"run_id": "target", "history_ref": None})
    if changed_origin:
        target.origin = "changed-source-snapshot"
    reader = TransferLearningManager(store, index)
    generator = BayesianCandidateGenerator(
        space,
        primary_metric="score",
        direction=MetricDirection.MINIMIZE,
        compare_split=BenchmarkSplit.SELECTION,
        n_initial=6,
        seed=47,
        warm_start_bridge=WarmStartBridge(reader, max_evals=8),
        warm_start_fingerprint=target,
    )
    assert generator.botorch_available, "This witness requires the real receiving GP backend"
    optimizer = generator._optimizer
    optimizer._config.num_restarts = 3
    optimizer._config.raw_samples = 32
    optimizer._config.fallback_on_failure = False
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    spec = SearchLoopSpec(
        loop_id="target",
        mutation_codec=_QuadraticCodec(),
        candidate_generator=generator,
        benchmark_evaluator=evaluator,
        promotion_policy=PromotionPolicy(
            loop_id="target",
            primary_metric="score",
            direction=MetricDirection.MINIMIZE,
            compare_split=BenchmarkSplit.SELECTION,
            unit="analytic_units",
        ),
    )
    result = SearchLoopRunner(store=store, registry=registry).run(
        spec, suite_ref=suite_ref, max_iterations=1
    )
    assert len(result.history) == 1
    for ref, raw in original_bytes.items():
        assert store.get_bytes(ref) == raw
    entry = result.history[0]
    output = entry.stage_b_result["simulation_results"]
    measured = load_model_artifact(store, output["evaluation_ref"], BenchmarkEvaluation)
    executed = load_model_artifact(store, output["candidate_ref"], _QuadraticMutation)
    assert str(measured.candidate_ref.artifact_id) == output["candidate_ref"]
    assert measured.selection_metrics["score"] == 100.0 * executed.x * executed.x
    assert measured.loop_id == "target"
    assert measured.holdout_metrics == {} and measured.promotable is False
    assert registry.get("target") is None
    return generator, reader, entry, evaluations


def _assert_gp_corpus(generator, originals):
    from botorch.models import SingleTaskGP

    torch = require_torch()
    optimizer = generator._optimizer
    model = optimizer._model
    assert isinstance(model, SingleTaskGP), "Configured historical observations must reach a real GP"
    expected_x = torch.tensor([[evaluation.params["x"]] for evaluation in originals], dtype=torch.float64)
    expected_y = torch.tensor([[-evaluation.scalar_score] for evaluation in originals], dtype=torch.float64)
    actual_x = model._original_train_inputs
    if actual_x is None:
        actual_x = model.train_inputs[0]
    torch.testing.assert_close(actual_x.reshape(-1, 1), expected_x)
    actual_y, _ = model.outcome_transform.untransform(model.train_targets.unsqueeze(-1))
    torch.testing.assert_close(actual_y.reshape(-1, 1), expected_y, rtol=1e-9, atol=1e-10)
    return model


def test_configured_cas_transfer_reaches_the_receiving_gp_on_the_live_loop(tmp_path):
    generator, reader, entry, originals = _configured_scene(tmp_path)
    model = _assert_gp_corpus(generator, originals)
    assert reader.last_restore_report.accepted_rows == len(originals)
    metadata = entry.candidate["_strategy_metadata"]
    assert metadata["source"] == "bayesian_acquisition"
    assert metadata["acquisition_value"] is not None
    _LOG.warning(
        "TRANSFER_WORKFLOW source=%s train_rows=%d candidate=%s score=%s",
        metadata["source"], model.train_targets.shape[-1], entry.candidate["x"],
        entry.stage_b_result["simulation_results"]["score"],
    )


def test_changed_origin_never_reaches_the_receiving_gp_on_the_live_loop(tmp_path):
    generator, reader, entry, _ = _configured_scene(tmp_path, changed_origin=True)
    assert generator._optimizer._model is None
    assert generator._optimizer._warm_evals == []
    assert reader.last_restore_report.accepted_rows == 0
    assert reader.last_discovery_issues
    assert entry.candidate["_strategy_metadata"]["source"] == "sobol_init"


def test_malformed_source_outcome_is_excluded_from_the_real_receiving_gp(tmp_path):
    generator, reader, entry, originals = _configured_scene(tmp_path, malformed_outcome=True)
    model = _assert_gp_corpus(generator, originals[1:])
    assert model.train_targets.shape[-1] == 7
    assert reader.last_restore_report.accepted_rows == 7
    assert reader.last_restore_report.rejected_rows == 1
    (issue,) = reader.last_restore_rejections
    assert issue.candidate_id == originals[0].candidate_id
    assert issue.reason == "stage_a_passed must be a boolean"
    assert entry.candidate["_strategy_metadata"]["source"] == "bayesian_acquisition"
