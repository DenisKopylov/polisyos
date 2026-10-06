from __future__ import annotations

import math
from typing import Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation, BenchmarkSplit
from polisyos.scientist.methods.doe.designs import (
    AdversarialPlan,
    AdversarialStrategy,
    ParameterSpec,
)
from polisyos.scientist.methods.doe.stress_report import VulnerabilityType
from polisyos.scientist.methods.search.adversarial import (
    NegatedCompositeObjective,
    PlatformMetaEvaluationInput,
    PlatformMetaEvaluator,
    run_stress_test,
)
from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    CompositeObjective,
    ObjectiveValue,
    OptimizationDirection,
)
from polisyos.scientist.methods.search.sentinels import (
    SentinelCandidate,
    SentinelKind,
    SentinelObservation,
    SentinelSet,
)
from polisyos.scientist.methods.search.stages import CorrelationTracker, StageResult
from polisyos.scientist.methods.search.strategies.adapter import StrategyAdapter
from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import ParameterBounds, PolicyCandidate


def _artifact_ref(seed: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{seed * 64}",
        kind="scientist.test",
        media_type="application/json",
    )


def _benchmark(
    selection: float,
    holdout: float,
    *,
    runtime_split_type: BenchmarkSplit,
) -> BenchmarkEvaluation:
    return BenchmarkEvaluation(
        loop_id="loop",
        suite_id="suite",
        candidate_ref=_artifact_ref("a"),
        selection_metrics={"score": selection},
        holdout_metrics={"score": holdout},
        sample_counts={"selection": 100, "holdout": 100},
        promotable=True,
        runtime_split_type=runtime_split_type,
    )


class QuadraticObjective:
    @property
    def name(self) -> str:
        return "quadratic"

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MINIMIZE

    def evaluate(self, results: dict[str, Any]) -> ObjectiveValue:
        x = float(results.get("x", 0.0))
        y = float(results.get("y", 0.0))
        return ObjectiveValue(
            name=self.name,
            raw_value=x * x + y * y,
            direction=self.direction,
        )


class ScalarObjective:
    """Minimal lower-tail objective used by the stress-report witnesses."""

    @property
    def name(self) -> str:
        return "utility"

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MINIMIZE

    def evaluate(self, results: dict[str, Any]) -> ObjectiveValue:
        return ObjectiveValue(
            name=self.name,
            raw_value=float(results["utility"]),
            direction=self.direction,
        )


class DirectionalScalarObjective:
    """Scalar objective that exposes the direction used by adaptive search."""

    def __init__(self, direction: OptimizationDirection) -> None:
        self._direction = direction

    @property
    def name(self) -> str:
        return "scalar"

    @property
    def direction(self) -> OptimizationDirection:
        return self._direction

    def evaluate(self, results: dict[str, Any]) -> ObjectiveValue:
        return ObjectiveValue(
            name=self.name,
            raw_value=float(results["utility"]),
            direction=self.direction,
        )

    def evaluate_detailed(self, results: dict[str, Any]) -> list[ObjectiveValue]:
        return [self.evaluate(results)]


class RecordingStrategy(RandomSearchStrategy):
    """Deterministic strategy that retains adapter-visible updates and suggestions."""

    def __init__(self, space: SearchSpace) -> None:
        super().__init__(space=space, seed=23)
        self.seen_updates: list[Any] = []
        self.seen_suggestions: list[list[Any]] = []

    def suggest(
        self,
        evaluations: list[Any],
        pending: list[PolicyCandidate] | None = None,
    ) -> PolicyCandidate:
        del pending
        self.seen_suggestions.append(list(evaluations))
        return PolicyCandidate(
            params={"p0": float(len(evaluations) + 1)},
            source_strategy="recording",
        )

    def update(self, evaluation: Any) -> None:
        self.seen_updates.append(evaluation)


class RecordingStrategyAdapter(StrategyAdapter):
    """Capture the bridge inputs while retaining the real StrategyAdapter path."""

    def __init__(self, strategy: RecordingStrategy, space: SearchSpace) -> None:
        super().__init__(strategy=strategy, space=space)
        self.seen_histories: list[list[Any]] = []
        self.seen_current_bests: list[dict[str, Any] | None] = []

    def generate(
        self,
        history: list[Any],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        self.seen_histories.append(list(history))
        self.seen_current_bests.append(current_best)
        return super().generate(history, current_best, context)


def _run_scalar_stress(*, values: tuple[float, ...], collect_top_k: int):
    """Run a bounded public stress sweep with deterministic scalar outcomes."""
    parameter_count = 4 if len(values) == 10 else 1
    plan = AdversarialPlan(
        parameter_specs=[
            ParameterSpec(name=f"p{index}", lower_bound=-1.0, upper_bound=1.0)
            for index in range(parameter_count)
        ],
        strategy=AdversarialStrategy.GRID_EXTREME,
        max_iterations=len(values),
        vulnerability_threshold=0.0,
        stop_on_first_vulnerability=False,
        collect_top_k=collect_top_k,
    )
    outcomes = iter(values)

    def stage_b(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        del candidate, context
        return {"simulation_results": {"utility": next(outcomes)}}

    return run_stress_test(
        adversarial_plan=plan,
        base_objective=CompositeObjective([ScalarObjective()]),
        stage_b_evaluator=stage_b,
        context={},
    )


def _run_adaptive_scalar_stress(
    *,
    values: tuple[float, ...],
    direction: OptimizationDirection,
    stop_on_first_vulnerability: bool,
):
    """Run a bounded SEARCH_LOOP sweep with a deterministic adaptive continuation."""
    plan = AdversarialPlan(
        parameter_specs=[ParameterSpec(name="p0", lower_bound=-1.0, upper_bound=1.0)],
        strategy=AdversarialStrategy.SEARCH_LOOP,
        max_iterations=len(values),
        vulnerability_threshold=0.0,
        stop_on_first_vulnerability=stop_on_first_vulnerability,
        collect_top_k=10,
    )
    outcomes = iter(values)
    space = SearchSpace([ParameterBounds(name="p0", lower=-1.0, upper=1.0)])
    strategy = RecordingStrategy(space)
    adapter = RecordingStrategyAdapter(strategy, space)

    def stage_b(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        del candidate, context
        return {"simulation_results": {"utility": next(outcomes)}}

    report = run_stress_test(
        adversarial_plan=plan,
        base_objective=DirectionalScalarObjective(direction),
        stage_b_evaluator=stage_b,
        candidate_generator=adapter,
        context={},
    )
    return report, adapter, strategy


def test_negated_objective_inverts_sign() -> None:
    base = CompositeObjective([QuadraticObjective()])
    negated = NegatedCompositeObjective(base)

    base_value = base.evaluate({"x": 2.0, "y": 0.0}).raw_value
    negated_value = negated.evaluate({"x": 2.0, "y": 0.0}).raw_value

    assert base_value == 4.0
    assert negated_value == -4.0


def test_run_stress_test_grid_extreme_reports_worst_case() -> None:
    plan = AdversarialPlan(
        parameter_specs=[
            ParameterSpec(name="x", lower_bound=-1.0, upper_bound=1.0),
            ParameterSpec(name="y", lower_bound=-1.0, upper_bound=1.0),
        ],
        strategy=AdversarialStrategy.GRID_EXTREME,
        max_iterations=10,
        vulnerability_threshold=2.0,
        stop_on_first_vulnerability=False,
    )

    def stage_b(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        del context
        return {"simulation_results": {"x": candidate["x"], "y": candidate["y"]}}

    report = run_stress_test(
        adversarial_plan=plan,
        base_objective=CompositeObjective([QuadraticObjective()]),
        stage_b_evaluator=stage_b,
        candidate_generator=None,
        context={},
    )

    assert report.total_scenarios_evaluated >= 4
    assert report.worst_case_objective is not None
    assert report.worst_case_objective >= 2.0
    assert report.vulnerabilities


def test_run_stress_test_top_k_does_not_change_ten_violation_score() -> None:
    values = tuple(float(value) for value in range(-10, 0))

    top_one = _run_scalar_stress(values=values, collect_top_k=1)
    top_ten = _run_scalar_stress(values=values, collect_top_k=10)

    assert top_one.total_scenarios_evaluated == 10
    assert top_ten.total_scenarios_evaluated == 10
    assert len(top_one.vulnerabilities) == 1
    assert len(top_ten.vulnerabilities) == 10
    assert top_one.robustness_score == top_ten.robustness_score == 0.0
    assert top_one.worst_case_objective == top_ten.worst_case_objective == -10.0


def test_run_stress_test_lower_tail_selects_negative_worst_case() -> None:
    report = _run_scalar_stress(values=(10.0, -5.0), collect_top_k=10)

    assert report.total_scenarios_evaluated == 2
    assert len(report.vulnerabilities) == 1
    assert report.worst_case_objective == -5.0


def test_run_stress_test_search_loop_tracks_lower_tail_through_adaptive_step() -> None:
    values = (*([10.0] * 32), 8.0, -5.0)

    report, adapter, strategy = _run_adaptive_scalar_stress(
        values=values,
        direction=OptimizationDirection.MAXIMIZE,
        stop_on_first_vulnerability=False,
    )

    assert report.total_scenarios_evaluated == 34
    assert len(adapter.seen_histories) == 2
    assert [len(history) for history in adapter.seen_histories] == [0, 1]
    assert adapter.seen_current_bests[0] is None
    assert adapter.seen_current_bests[1] is not None
    assert adapter.seen_current_bests[1]["p0"] == 1.0
    assert len(strategy.seen_updates) == 1
    assert strategy.seen_updates[0].scalar_score == 8.0
    assert adapter.seen_histories[1][0].objective_value == 8.0
    assert adapter.seen_histories[1][0].objective_details[0].raw_value == 8.0
    assert report.worst_case_objective == -5.0
    assert [item.objective_value for item in report.vulnerabilities] == [-5.0]


def test_run_stress_test_search_loop_stops_on_first_lower_tail_vulnerability() -> None:
    report, adapter, _strategy = _run_adaptive_scalar_stress(
        values=(*([10.0] * 32), -5.0),
        direction=OptimizationDirection.MAXIMIZE,
        stop_on_first_vulnerability=True,
    )

    assert report.total_scenarios_evaluated == 33
    assert len(adapter.seen_histories) == 1
    assert len(adapter.seen_histories[0]) == 0
    assert adapter.seen_current_bests == [None]
    assert report.worst_case_objective == -5.0
    assert [item.objective_value for item in report.vulnerabilities] == [-5.0]


def test_run_stress_test_search_loop_reverses_order_for_minimize_cost() -> None:
    values = (*([-5.0] * 32), -4.0, 10.0)

    report, adapter, _strategy = _run_adaptive_scalar_stress(
        values=values,
        direction=OptimizationDirection.MINIMIZE,
        stop_on_first_vulnerability=True,
    )

    assert report.total_scenarios_evaluated == 34
    assert len(adapter.seen_histories) == 2
    assert [len(history) for history in adapter.seen_histories] == [0, 1]
    assert report.worst_case_objective == 10.0
    assert [item.objective_value for item in report.vulnerabilities] == [10.0]


def test_run_stress_test_composite_budget_cost_selects_high_cost_as_worst_case() -> None:
    """Use the real composite cost objective rather than a direction surrogate."""
    plan = AdversarialPlan(
        parameter_specs=[ParameterSpec(name="p0", lower_bound=-1.0, upper_bound=1.0)],
        strategy=AdversarialStrategy.GRID_EXTREME,
        max_iterations=2,
        stop_on_first_vulnerability=False,
    )
    costs = iter((1.0, 10.0))

    def stage_b(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        del candidate, context
        return {"simulation_results": {"budget_deficit": next(costs)}}

    report = run_stress_test(
        adversarial_plan=plan,
        base_objective=CompositeObjective([BudgetDeficitObjective()]),
        stage_b_evaluator=stage_b,
        context={},
    )

    assert report.total_scenarios_evaluated == 2
    assert report.worst_case_objective == 10.0


@pytest.mark.parametrize(
    "invalid_result",
    [
        pytest.param(None, id="missing"),
        pytest.param(
            {"simulation_results": {"budget_deficit": "not-a-number"}},
            id="non_numeric",
        ),
        pytest.param(
            {"simulation_results": {"budget_deficit": math.nan}},
            id="nan",
        ),
        pytest.param(
            {"simulation_results": {"budget_deficit": math.inf}},
            id="inf",
        ),
    ],
)
def test_run_stress_test_search_loop_fails_closed_on_invalid_adaptive_result(
    invalid_result: object,
) -> None:
    """Invalid adaptive feedback cannot become a positive robustness claim."""
    plan = AdversarialPlan(
        parameter_specs=[ParameterSpec(name="p0", lower_bound=-1.0, upper_bound=1.0)],
        strategy=AdversarialStrategy.SEARCH_LOOP,
        max_iterations=33,
        stop_on_first_vulnerability=False,
    )
    space = SearchSpace([ParameterBounds(name="p0", lower=-1.0, upper=1.0)])
    strategy = RecordingStrategy(space)
    adapter = RecordingStrategyAdapter(strategy, space)
    calls = 0

    def stage_b(candidate: dict[str, Any], context: dict[str, Any]) -> Any:
        nonlocal calls
        del candidate, context
        calls += 1
        if calls == 33:
            return invalid_result
        return {"simulation_results": {"budget_deficit": 1.0}}

    report = run_stress_test(
        adversarial_plan=plan,
        base_objective=CompositeObjective([BudgetDeficitObjective()]),
        stage_b_evaluator=stage_b,
        candidate_generator=adapter,
        context={},
    )

    assert calls == 33
    assert report.total_scenarios_evaluated == 32
    assert report.metadata["attempted"] == 33
    assert report.metadata["unknown_or_nonfinite"] == 1
    assert report.set_adequacy_status == "partial"
    assert report.robustness_score == 1.0
    assert report.metadata["score_scope"] == "observed_finite_scenarios"
    assert any(
        item.vulnerability_type == VulnerabilityType.NUMERICAL_INSTABILITY
        for item in report.vulnerabilities
    )


def test_platform_meta_evaluator_passes_healthy_sentinel_injection() -> None:
    tracker = CorrelationTracker(drift_window_size=5, sentinel_pass_floor=0.95)
    for idx in range(5):
        tracker.record(
            StageResult(
                policy_candidate={}, objective_value=0.8, is_promising=True, stage_name="L2"
            ),
            StageResult(
                policy_candidate={}, objective_value=0.75, is_promising=True, stage_name="L4"
            ),
            f"c{idx}",
            is_sentinel=True,
        )
    report = PlatformMetaEvaluator().evaluate(
        PlatformMetaEvaluationInput(
            sentinel_set=SentinelSet(
                set_id="set",
                suite_id="suite",
                sentinels=[
                    SentinelCandidate(
                        sentinel_id="s1",
                        kind=SentinelKind.CALIBRATION,
                        candidate={},
                    )
                ],
                pass_rate_floor=0.95,
            ),
            sentinel_observations=[
                SentinelObservation(
                    sentinel_id="s1",
                    kind=SentinelKind.CALIBRATION,
                    candidate_hash="hash",
                    final_action="complete",
                    level_reached=4,
                    stage_a_passed=True,
                    stage_b_approved=True,
                )
            ],
            correlation_tracker=tracker,
        )
    )

    sentinel_result = next(
        item for item in report.attack_results if item.attack_type == "sentinel_injection"
    )
    assert sentinel_result.status == "passed"
    assert report.promotion_safe is True


def test_platform_meta_evaluator_detects_holdout_rotation_failure() -> None:
    report = PlatformMetaEvaluator().evaluate(
        PlatformMetaEvaluationInput(
            selection_evaluation=_benchmark(
                1.0,
                1.0,
                runtime_split_type=BenchmarkSplit.SELECTION,
            ),
            rotated_hidden_holdout_evaluations=[
                _benchmark(
                    1.0,
                    0.7,
                    runtime_split_type=BenchmarkSplit.ROTATING_CHALLENGE,
                ),
                _benchmark(
                    1.0,
                    0.65,
                    runtime_split_type=BenchmarkSplit.ROTATING_CHALLENGE,
                ),
            ],
            base_promotion_decision=True,
            rotated_promotion_decisions=[False, False],
        )
    )

    result = next(
        item for item in report.attack_results if item.attack_type == "hidden_holdout_rotation"
    )
    assert result.status == "failed"
    assert report.promotion_safe is False


def test_platform_meta_evaluator_rejects_mistyped_rotations() -> None:
    report = PlatformMetaEvaluator().evaluate(
        PlatformMetaEvaluationInput(
            selection_evaluation=_benchmark(
                1.0,
                1.0,
                runtime_split_type=BenchmarkSplit.SELECTION,
            ),
            rotated_hidden_holdout_evaluations=[
                _benchmark(
                    1.0,
                    0.9,
                    runtime_split_type=BenchmarkSplit.HIDDEN_HOLDOUT,
                )
            ],
        )
    )

    result = next(
        item for item in report.attack_results if item.attack_type == "hidden_holdout_rotation"
    )
    assert result.status == "failed"
    assert result.metrics["invalid_rotation_splits"] == [BenchmarkSplit.HIDDEN_HOLDOUT.value]


def test_platform_meta_evaluator_passes_drift_attack_when_tracker_degrades() -> None:
    tracker = CorrelationTracker(
        drift_window_size=5,
        spearman_warning_threshold=0.8,
        promotion_ban_threshold=0.6,
    )
    for idx in range(5):
        tracker.record(
            StageResult(
                policy_candidate={}, objective_value=float(idx), is_promising=True, stage_name="L2"
            ),
            StageResult(
                policy_candidate={},
                objective_value=float(5 - idx),
                is_promising=(idx % 2 == 0),
                stage_name="L4",
            ),
            f"neg{idx}",
            is_sentinel=False,
        )
    report = PlatformMetaEvaluator().evaluate(
        PlatformMetaEvaluationInput(
            correlation_tracker=tracker,
            observed_scheduler_mode=tracker.routing_mode(),
        )
    )

    result = next(
        item for item in report.attack_results if item.attack_type == "calibration_drift_replay"
    )
    assert result.status == "passed"
    assert (
        "CALIBRATION_DRIFT" in result.triggered_guards or "PROMOTION_BAN" in result.triggered_guards
    )
