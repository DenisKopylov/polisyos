"""Current-head characterization for the SRV-03 autotune caller migration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    ChampionRegistry,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopRunner,
    SearchLoopSpec,
    persist_benchmark_suite,
)
from polisyos.scientist.methods.autotune.models import load_model_artifact
from polisyos.scientist.methods.autotune.runtime import (
    PydanticMutationCodec,
    SequenceCandidateGenerator,
)
from polisyos.scientist.methods.search.adapters import LegacySearchServiceAdapter
from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.objective import (
    CompositeObjective,
    ObjectiveValue,
    OptimizationDirection,
)
from polisyos.scientist.methods.search.stopping import MaxIterations

# The repository's test suite uses assert-based pytest witnesses by design.
# ruff: noqa: S101

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.artifacts.manifest import ArtifactRef


class _CostObjective:
    @property
    def name(self) -> str:
        return "cost"

    def evaluate(self, results: dict[str, Any]) -> ObjectiveValue:
        return ObjectiveValue(
            name=self.name,
            raw_value=float(results["cost"]),
            direction=OptimizationDirection.MINIMIZE,
        )


class _TraceBatchGenerator:
    """Generate the fixed current-head trace used before the native cutover."""

    def __init__(self) -> None:
        self._batches = [
            [],
            [
                {
                    "candidate_id": "sentinel",
                    "__sentinel__": {"sentinel_id": "srv03-sentinel"},
                    "cost": 100.0,
                },
                {"candidate_id": "evaluator-error", "cost": 9.0},
            ],
            [{"candidate_id": "resumed", "cost": 1.0}],
        ]
        self.context_history: list[dict[str, Any]] = []

    def generate_batch(
        self,
        history: list[Any],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
        batch_size: int,
    ) -> list[dict[str, Any]]:
        del history, current_best, batch_size
        self.context_history.append(dict(context["search_state"]))
        return list(self._batches.pop(0)) if self._batches else []

    def generate(
        self,
        history: list[Any],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del history, current_best, context
        raise AssertionError("the characterization must use the batch path")


def test_current_controller_trace_preserves_warm_sentinel_empty_error_resume() -> None:
    """Freeze lifecycle, counters, and detached request context before cutover."""
    generator = _TraceBatchGenerator()
    evaluated: list[str] = []

    def stage_b(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        del context
        candidate_id = str(candidate["candidate_id"])
        evaluated.append(candidate_id)
        if candidate_id == "evaluator-error":
            return {
                "simulation_results": {"cost": candidate["cost"]},
                "feedback": {"verdict": "REJECT", "reason": "evaluator_error"},
            }
        return {
            "simulation_results": {"cost": candidate["cost"]},
            "feedback": {"verdict": "APPROVE"},
        }

    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(2),
            objective=CompositeObjective([_CostObjective()]),
            batch_size=2,
            initial_evaluations=[
                {
                    "candidate": {"candidate_id": "warm", "cost": 10.0},
                    "objective_value": 10.0,
                    "is_promising": True,
                }
            ],
        ),
        candidate_generator=generator,
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=stage_b,
    )

    result = controller.run(initial_context={"run_id": "srv03-characterization"})

    assert evaluated == ["sentinel", "evaluator-error", "resumed"]
    assert [record.candidate["candidate_id"] for record in result.history] == [
        "warm",
        "evaluator-error",
        "resumed",
    ]
    assert result.best_candidate == {"candidate_id": "resumed", "cost": 1.0}
    assert result.best_objective == 1.0
    assert result.stage_a_evaluations == 3
    assert result.stage_b_evaluations == 3
    assert result.telemetry["sentinel_evaluations"] == 1
    assert result.telemetry["scientific_evaluations"] == 2
    assert result.telemetry["training_evaluations"] == 1
    assert result.telemetry["generation_transition"]["kind"] == "transient_empty"
    # Sentinel observations are counted separately and intentionally do not
    # enter the ordinary history visible to the next generator call.
    assert [state["history_length"] for state in generator.context_history] == [1, 1, 2]


class _RunnerMutation(MutationArtifact):
    value: int


class _IdentityGenerator:
    def __init__(self, candidate_id: object, *, include_id: bool = True) -> None:
        self._candidate_id = candidate_id
        self._include_id = include_id

    def generate(
        self,
        history: list[Any],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del history, current_best, context
        payload: dict[str, Any] = {"cost": 1.0}
        if self._include_id:
            payload["candidate_id"] = self._candidate_id
        return payload


def _identity_service(
    candidate_id: object,
    *,
    include_id: bool = True,
) -> LegacySearchServiceAdapter:
    return LegacySearchServiceAdapter(
        SearchController(
            config=SearchConfig(
                stopping=MaxIterations(1),
                objective=CompositeObjective([_CostObjective()]),
            ),
            candidate_generator=_IdentityGenerator(candidate_id, include_id=include_id),
            stage_a_evaluator=lambda candidate, context: (0.0, True),
            stage_b_evaluator=lambda candidate, context: {
                "simulation_results": {"cost": 1.0},
                "feedback": {"verdict": "APPROVE"},
            },
        )
    )


@pytest.mark.parametrize("candidate_id", [0, ""])
def test_native_service_rejects_explicit_falsy_candidate_id(candidate_id: object) -> None:
    """Only an absent ID may use generated identity; falsy IDs must not be rewritten."""
    service = _identity_service(candidate_id)

    with pytest.raises(ValueError, match="explicit non-empty string"):
        service.ask(goal=None, search_space=None, context={})


def test_native_service_preserves_negative_string_candidate_id() -> None:
    """A valid negative string remains the evaluator's identity."""
    service = _identity_service("-1")

    proposal = service.ask(goal=None, search_space=None, context={})[0]

    assert proposal.candidate_id == "-1"
    assert proposal.payload["candidate_id"] == "-1"


def test_native_service_generates_id_only_when_candidate_id_is_absent() -> None:
    """Generated IDs remain the fallback for payloads with no identity field."""
    service = _identity_service(None, include_id=False)

    proposal = service.ask(goal=None, search_space=None, context={})[0]

    assert proposal.candidate_id == "candidate_0_0"
    assert "candidate_id" not in proposal.payload


class _RunnerEvaluator:
    def evaluate(
        self,
        candidate_ref: ArtifactRef,
        suite_ref: ArtifactRef,
        context: dict[str, Any],
    ) -> BenchmarkEvaluation:
        del suite_ref
        candidate = load_model_artifact(context["store"], candidate_ref, _RunnerMutation)
        score = float(candidate.value)
        return BenchmarkEvaluation(
            loop_id="srv03-loop",
            suite_id="srv03-suite",
            suite_version="1.0",
            candidate_ref=candidate_ref,
            selection_metrics={"score": score},
            holdout_metrics={"score": score},
            sample_counts={
                BenchmarkSplit.SELECTION.value: 1,
                BenchmarkSplit.HOLDOUT.value: 1,
            },
            guardrails={"score_present": True},
            promotable=True,
            runtime_split_type=BenchmarkSplit.HOLDOUT,
        )


def test_current_autotune_runner_characterizes_real_cas_consumer_path(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """The autotune caller persists evaluated candidates and promotes the best one."""

    def fail_legacy_controller_run(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise AssertionError("autotune must use the native service driver")

    monkeypatch.setattr(SearchController, "run", fail_legacy_controller_run)

    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="srv03-suite", suite_version="1.0"),
    )
    spec = SearchLoopSpec(
        loop_id="srv03-loop",
        mutation_codec=PydanticMutationCodec(_RunnerMutation),
        candidate_generator=SequenceCandidateGenerator(
            [
                _RunnerMutation(loop_id="srv03-loop", value=2),
                _RunnerMutation(loop_id="srv03-loop", value=7),
            ]
        ),
        benchmark_evaluator=_RunnerEvaluator(),
        promotion_policy=PromotionPolicy(
            loop_id="srv03-loop",
            primary_metric="score",
            direction=MetricDirection.MAXIMIZE,
            compare_split=BenchmarkSplit.HOLDOUT,
            min_sample_count=1,
            required_guardrails=["score_present"],
        ),
    )

    result = SearchLoopRunner(store=store, registry=registry).run(
        spec,
        suite_ref=suite_ref,
        initial_candidate=_RunnerMutation(loop_id="srv03-loop", value=1),
        context={"request_id": "srv03-user-path"},
        max_iterations=3,
    )

    assert result.best_candidate == {
        "loop_id": "srv03-loop",
        "artifact_version": "1.0",
        "search_space_version": "1.0",
        "notes": [],
        "value": 7,
    }
    assert result.iterations_completed == 3
    assert result.stage_a_evaluations == 0
    assert result.stage_b_evaluations == 3
    champion = registry.get("srv03-loop")
    assert champion is not None
    promoted = load_model_artifact(store, champion.candidate_ref, _RunnerMutation)
    assert promoted.value == 7
