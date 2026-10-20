from __future__ import annotations

import math
from typing import Any

import pytest

from polisyos.core.artifacts import load_core_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation, BenchmarkSplit
from polisyos.scientist.methods.doe.designs import (
    AdversarialPlan,
    AdversarialStrategy,
    ParameterSpec,
)
from polisyos.scientist.methods.doe.stress_report import (
    StressOutcomeBasis,
    StressTestReport,
    VulnerabilityType,
    resolve_stress_report_artifact,
    resolve_stress_score_components,
)
from polisyos.scientist.methods.search.adversarial import (
    NegatedCompositeObjective,
    PlatformMetaEvaluationInput,
    PlatformMetaEvaluator,
    run_stress_test,
)
from polisyos.scientist.methods.search.funnel.level5_refutation_governance import (
    Level5RefutationGovernanceStage,
)
from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    CompositeObjective,
    GDPGrowthObjective,
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


def _selected_input(ref: ArtifactRef, *, role: str) -> InputRef:
    return InputRef(
        artifact_id=ref.artifact_id,
        role=role,
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )


from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)


def _artifact_ref(seed: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{seed * 64}",
        kind="scientist.test",
        media_type="application/json",
    )


def _persist_policy_candidate(store, candidate_id: str) -> ArtifactRef:
    token = candidate_id.replace("-", "_")
    candidate = PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(problem_id=f"problem_{token}", domain=ProblemDomain.FISCAL),
            policy_spec=PolicySpec(policy_id=f"policy_{token}"),
            model_spec=ModelSpec(model_id=f"model_{token}", data_snapshot_ref="sha256:" + "3" * 64),
        ),
        candidate_id=candidate_id,
    )
    return persist_policy_candidate_schema(store, candidate, return_selected_profile=True)


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
        base_objective=DirectionalScalarObjective(OptimizationDirection.MAXIMIZE),
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
    base = CompositeObjective([BudgetDeficitObjective(expected_unit=_FIXTURE_BUDGET_DEFICIT_UNIT)])
    negated = NegatedCompositeObjective(base)
    source = {
        "budget_deficit": 4.0,
        "metric_units": {"budget_deficit": _FIXTURE_BUDGET_DEFICIT_UNIT},
    }

    base_value = base.evaluate(source).raw_value
    negated_value = negated.evaluate(source).raw_value

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
        return _budget_deficit_simulation_result(candidate["x"] ** 2 + candidate["y"] ** 2)

    report = run_stress_test(
        adversarial_plan=plan,
        base_objective=CompositeObjective(
            [BudgetDeficitObjective(expected_unit=_FIXTURE_BUDGET_DEFICIT_UNIT)]
        ),
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
    assert top_one.robustness_score is None
    assert top_ten.robustness_score is None
    assert top_one.score_status == top_ten.score_status == "unbound"
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


_FIXTURE_BUDGET_DEFICIT_UNIT = "fixture-budget-deficit-unit"
_FIXTURE_GDP_GROWTH_UNIT = "fixture-gdp-growth-unit"


def _budget_deficit_simulation_result(value: object) -> dict[str, Any]:
    """Return a synthetic fiscal result with an explicit test-only unit."""
    return {
        "simulation_results": {
            "budget_deficit": value,
            "metric_units": {"budget_deficit": _FIXTURE_BUDGET_DEFICIT_UNIT},
        }
    }


def _gdp_growth_simulation_result(value: object) -> dict[str, Any]:
    """Return a synthetic growth result with an explicit test-only unit."""
    return {
        "simulation_results": {
            "gdp_change": value,
            "metric_units": {"gdp_change": _FIXTURE_GDP_GROWTH_UNIT},
        }
    }


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
        return _budget_deficit_simulation_result(next(costs))

    report = run_stress_test(
        adversarial_plan=plan,
        base_objective=CompositeObjective(
            [BudgetDeficitObjective(expected_unit=_FIXTURE_BUDGET_DEFICIT_UNIT)]
        ),
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
            _budget_deficit_simulation_result("not-a-number"),
            id="non_numeric",
        ),
        pytest.param(
            _budget_deficit_simulation_result(math.nan),
            id="nan",
        ),
        pytest.param(
            _budget_deficit_simulation_result(math.inf),
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
        return _budget_deficit_simulation_result(1.0)

    report = run_stress_test(
        adversarial_plan=plan,
        base_objective=CompositeObjective(
            [BudgetDeficitObjective(expected_unit=_FIXTURE_BUDGET_DEFICIT_UNIT)]
        ),
        stage_b_evaluator=stage_b,
        candidate_generator=adapter,
        context={},
    )

    assert calls == 33
    assert report.total_scenarios_evaluated == 33
    assert report.set_adequacy_status == "unverified"
    assert report.robustness_score is None
    assert report.score_status != "available"
    assert any(
        item.vulnerability_type == VulnerabilityType.NUMERICAL_INSTABILITY
        for item in report.vulnerabilities
    )


def test_finite_direct_objective_remains_candidate_only_at_level5(tmp_path) -> None:
    """Finite direct diagnostics remain visible but cannot become a scored finding."""
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = _persist_policy_candidate(store, "candidate-unbound-stress")
    plan = AdversarialPlan(
        parameter_specs=[ParameterSpec(name="shock", lower_bound=0.0, upper_bound=1.0)],
        strategy=AdversarialStrategy.GRID_EXTREME,
        max_iterations=2,
        vulnerability_threshold=None,
        stop_on_first_vulnerability=False,
        collect_top_k=2,
    )
    values = iter((0.5, 1.5))

    report = run_stress_test(
        adversarial_plan=plan,
        base_objective=DirectionalScalarObjective(OptimizationDirection.MINIMIZE),
        stage_b_evaluator=lambda _candidate, _context: {
            "simulation_results": {"utility": next(values)}
        },
        context={"policy_candidate_ref": candidate_ref},
        cas=store,
    )

    assert report.total_scenarios_evaluated == 2
    assert report.worst_case_objective == 1.5
    assert report.vulnerabilities == []
    assert report.score_components == []
    assert report.score_status == "unbound"
    assert report.robustness_score is None
    report_ref = report.cas_artifact_ref
    assert report_ref is not None

    _fresh_report, resolution = resolve_stress_report_artifact(
        store, report_ref, expected_candidate_ref=candidate_ref
    )
    assert resolution.status == "unbound"
    assert resolution.robustness_score is None

    level5 = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
        {"candidate_id": "candidate-unbound-stress"},
        {
            "store": store,
            "policy_candidate_ref": candidate_ref,
            "stress_test_report_ref": report_ref,
        },
    )
    assert level5.feedback["stress_score_status"] == "unbound"
    assert level5.feedback["stress_score_value"] is None
    assert not any(
        item.failure_type == "stress_test_failed" and item.is_blocker
        for item in level5.failure_cards
    )


@pytest.mark.parametrize(
    ("simulation_results", "expected_status"),
    [
        pytest.param(
            {"budget_deficit": 0.0},
            "unbound",
            id="missing-unit-stays-unavailable",
        ),
        pytest.param(
            {
                "budget_deficit": "malformed",
                "metric_units": {"budget_deficit": _FIXTURE_BUDGET_DEFICIT_UNIT},
            },
            "invalid",
            id="malformed-present-input-stays-invalid",
        ),
    ],
)
def test_adversarial_objective_unit_and_malformed_inputs_do_not_score(
    tmp_path,
    simulation_results: dict[str, Any],
    expected_status: str,
) -> None:
    """Unknown or malformed objective sources cannot be replaced with a score."""
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = _persist_policy_candidate(store, f"candidate-{expected_status}-stress")
    plan = AdversarialPlan(
        parameter_specs=[ParameterSpec(name="shock", lower_bound=0.0, upper_bound=1.0)],
        strategy=AdversarialStrategy.GRID_EXTREME,
        max_iterations=2,
        vulnerability_threshold=None,
        stop_on_first_vulnerability=False,
    )
    report = run_stress_test(
        adversarial_plan=plan,
        base_objective=CompositeObjective(
            [BudgetDeficitObjective(expected_unit=_FIXTURE_BUDGET_DEFICIT_UNIT)]
        ),
        stage_b_evaluator=lambda _candidate, _context: {"simulation_results": simulation_results},
        context={"policy_candidate_ref": candidate_ref},
        cas=store,
    )

    assert report.score_status == expected_status
    assert report.score_components == []
    assert report.robustness_score is None
    report_ref = report.cas_artifact_ref
    assert report_ref is not None
    _fresh_report, resolution = resolve_stress_report_artifact(
        store, report_ref, expected_candidate_ref=candidate_ref
    )
    assert resolution.status == expected_status
    assert resolution.robustness_score is None


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


def test_source_replayed_objective_names_remain_unbound_without_selected_intent(tmp_path) -> None:
    """Two real configured rules cannot authorize their own selected-intent claim."""
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = _persist_policy_candidate(store, "candidate-objective-intent-unbound")
    plan = AdversarialPlan(
        parameter_specs=[ParameterSpec(name="shock", lower_bound=0.0, upper_bound=1.0)],
        strategy=AdversarialStrategy.GRID_EXTREME,
        max_iterations=2,
        vulnerability_threshold=None,
        stop_on_first_vulnerability=False,
    )
    cases = (
        (
            CompositeObjective([GDPGrowthObjective(expected_unit=_FIXTURE_GDP_GROWTH_UNIT)]),
            lambda: _gdp_growth_simulation_result(0.0),
        ),
        (
            CompositeObjective(
                [BudgetDeficitObjective(expected_unit=_FIXTURE_BUDGET_DEFICIT_UNIT)]
            ),
            lambda: _budget_deficit_simulation_result(0.0),
        ),
    )
    for objective, result in cases:
        report = run_stress_test(
            adversarial_plan=plan,
            base_objective=objective,
            stage_b_evaluator=lambda _candidate, _context, make_result=result: make_result(),
            context={"policy_candidate_ref": candidate_ref},
            cas=store,
        )
        assert report.cas_artifact_ref is not None
        _, resolution = resolve_stress_report_artifact(
            store, report.cas_artifact_ref, expected_candidate_ref=candidate_ref
        )
        assert resolution.status == "unbound"
        assert resolution.reason_code == "selected_objective_intent_not_independently_established"
        assert resolution.robustness_score is None


def test_configured_gdp_report_stays_unbound_at_fresh_level5(tmp_path) -> None:
    """A configured GDP source replays, but no independent selected-intent ref reaches L5."""
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = _persist_policy_candidate(store, "candidate-gdp-intent-unbound")
    plan = AdversarialPlan(
        parameter_specs=[ParameterSpec(name="shock", lower_bound=0.0, upper_bound=1.0)],
        strategy=AdversarialStrategy.GRID_EXTREME,
        max_iterations=2,
        vulnerability_threshold=None,
        stop_on_first_vulnerability=False,
    )

    report = run_stress_test(
        adversarial_plan=plan,
        base_objective=CompositeObjective(
            [GDPGrowthObjective(expected_unit=_FIXTURE_GDP_GROWTH_UNIT)]
        ),
        stage_b_evaluator=lambda _candidate, _context: _gdp_growth_simulation_result(0.0),
        context={"policy_candidate_ref": candidate_ref},
        cas=store,
    )
    report_ref = report.cas_artifact_ref
    assert report_ref is not None
    assert report_ref.manifest_profile_sha256 is not None
    assert report.score_status == "unbound"
    assert report.score_reason == "selected_objective_intent_not_independently_established"

    fresh_report, resolution = resolve_stress_report_artifact(
        store, report_ref, expected_candidate_ref=candidate_ref
    )
    assert fresh_report.score_components
    assert resolution.status == "unbound"
    assert resolution.reason_code == "selected_objective_intent_not_independently_established"
    assert resolution.passed_count == 2
    assert resolution.robustness_score is None

    level5 = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
        {"candidate_id": "candidate-gdp-intent-unbound"},
        {
            "store": store,
            "policy_candidate_ref": candidate_ref,
            "stress_test_report_ref": report_ref,
        },
    )
    assert level5.feedback["stress_score_status"] == "unbound"
    assert level5.feedback["stress_score_value"] is None
    assert not any(
        card.failure_type == "stress_test_failed" and card.is_blocker
        for card in level5.failure_cards
    )


def test_finite_occurrence_basis_is_freshly_recomputed_and_top_k_independent(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = _persist_policy_candidate(store, "candidate-finite-stress")
    plan = AdversarialPlan(
        parameter_specs=[
            ParameterSpec(name=f"p{i}", lower_bound=-1.0, upper_bound=1.0) for i in range(4)
        ],
        strategy=AdversarialStrategy.GRID_EXTREME,
        max_iterations=10,
        vulnerability_threshold=0.0,
        stop_on_first_vulnerability=False,
        collect_top_k=1,
    )

    def run(
        collect_top_k: int,
        values_to_evaluate: tuple[float, ...] = tuple(float(value) for value in range(-10, 0)),
    ) -> tuple[StressTestReport, ArtifactRef]:
        values = iter(values_to_evaluate)
        plan_for_run = plan.model_copy(
            update={
                "collect_top_k": collect_top_k,
                "max_iterations": len(values_to_evaluate),
            }
        )
        report = run_stress_test(
            adversarial_plan=plan_for_run,
            base_objective=CompositeObjective(
                [GDPGrowthObjective(expected_unit=_FIXTURE_GDP_GROWTH_UNIT)]
            ),
            stage_b_evaluator=lambda _candidate, _context: _gdp_growth_simulation_result(
                next(values)
            ),
            context={"policy_candidate_ref": candidate_ref},
            cas=store,
        )
        report_ref = report.cas_artifact_ref
        assert report_ref is not None
        return report, report_ref

    top_one, top_one_ref = run(1)
    assert top_one.cas_artifact_ref == top_one_ref
    assert top_one_ref.manifest_profile_sha256 is not None
    assert "cas_artifact_ref" not in top_one.model_dump(mode="json")
    report_manifest = store.get_manifest(top_one_ref)
    basis_ref = top_one.score_components[0].outcome_basis_ref
    assert basis_ref.manifest_profile_sha256 is not None
    basis = StressOutcomeBasis.model_validate(load_core_json_artifact(store, basis_ref))
    assert basis.plan_ref is not None and basis.plan_ref.manifest_profile_sha256 is not None
    assert basis.candidate_ref == candidate_ref
    basis_manifest = store.get_manifest(basis_ref)
    assert any(
        item.role == "adversarial_plan"
        and item.artifact_id == basis.plan_ref.artifact_id
        and item.manifest_profile_sha256 == basis.plan_ref.manifest_profile_sha256
        for item in basis_manifest.inputs
    )
    assert any(
        item.role == "candidate"
        and item.artifact_id == candidate_ref.artifact_id
        and item.manifest_profile_sha256 == candidate_ref.manifest_profile_sha256
        for item in basis_manifest.inputs
    )
    assert any(
        item.role == "stress_outcome_basis"
        and item.artifact_id == basis_ref.artifact_id
        and item.manifest_profile_sha256 == basis_ref.manifest_profile_sha256
        for item in report_manifest.inputs
    )
    assert any(
        item.role == "candidate"
        and item.artifact_id == candidate_ref.artifact_id
        and item.manifest_profile_sha256 == candidate_ref.manifest_profile_sha256
        for item in report_manifest.inputs
    )
    candidate_body = load_core_json_artifact(
        store, candidate_ref, manifest_profile_sha256=candidate_ref.manifest_profile_sha256
    )
    alternate_candidate_ref = store.put_json(
        candidate_body,
        PutOptions(
            kind="scientist.policy_candidate_schema",
            media_type="application/json",
            schema=SchemaInfo(name="candidate", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert alternate_candidate_ref.artifact_id == candidate_ref.artifact_id
    assert alternate_candidate_ref.manifest_profile_sha256 != candidate_ref.manifest_profile_sha256
    _, report_lineage_resolution = resolve_stress_report_artifact(
        store, top_one_ref, expected_candidate_ref=alternate_candidate_ref
    )
    assert report_lineage_resolution.status == "invalid"
    assert report_lineage_resolution.reason_code == "stress_report_lineage_mismatch"
    assert report_lineage_resolution.robustness_score is None
    top_ten, top_ten_ref = run(10)
    assert top_one.critical_count + top_one.high_count > 0
    finite_failure = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
        {"candidate_id": "candidate-finite-stress"},
        {
            "store": store,
            "policy_candidate_ref": candidate_ref,
            "stress_test_report_ref": top_one_ref,
        },
    )
    assert finite_failure.feedback["stress_score_status"] == "unbound"
    assert finite_failure.feedback["stress_score_value"] is None
    assert finite_failure.feedback["stress_score_profile"] == "finite_binary_scenario_v1"
    assert not any(
        card.failure_type == "stress_test_failed" and card.is_blocker
        for card in finite_failure.failure_cards
    )
    _, one_resolution = resolve_stress_report_artifact(
        store, top_one_ref, expected_candidate_ref=candidate_ref
    )
    # Even a legacy producer-side AVAILABLE claim does not independently bind selection.
    self_claimed_report = top_one.model_copy(
        update={
            "score_status": "available",
            "score_reason": "source_bound_occurrences_recomputed",
            "score_predicate_status": "recomputed",
            "robustness_score": 0.0,
        }
    )
    self_claimed_ref = store.put_json(
        self_claimed_report.model_dump(mode="json"),
        PutOptions(
            kind="scientist.stress_test_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.StressTestReport", version="1.1"),
            inputs=[
                *[
                    _selected_input(item.outcome_basis_ref, role="stress_outcome_basis")
                    for item in self_claimed_report.score_components
                ],
                _selected_input(candidate_ref, role="candidate"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    _, self_claimed_resolution = resolve_stress_report_artifact(
        store, self_claimed_ref, expected_candidate_ref=candidate_ref
    )
    assert self_claimed_resolution.status == "unbound"
    assert (
        self_claimed_resolution.reason_code
        == "selected_objective_intent_not_independently_established"
    )
    assert self_claimed_resolution.robustness_score is None

    _, ten_resolution = resolve_stress_report_artifact(
        store, top_ten_ref, expected_candidate_ref=candidate_ref
    )

    assert len(top_one.vulnerabilities) == 1
    assert len(top_ten.vulnerabilities) == 10
    assert one_resolution.status == ten_resolution.status == "unbound"
    assert (
        one_resolution.reason_code
        == ten_resolution.reason_code
        == "selected_objective_intent_not_independently_established"
    )

    wrong_schema_candidate = store.put_json(
        candidate_body,
        PutOptions(
            kind=PolicyCandidateSchema.ARTIFACT_KIND,
            media_type=PolicyCandidateSchema.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name="wrong.PolicyCandidateSchema", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert wrong_schema_candidate.artifact_id == candidate_ref.artifact_id
    assert wrong_schema_candidate.manifest_profile_sha256 != candidate_ref.manifest_profile_sha256
    wrong_schema_resolution = resolve_stress_score_components(
        store, top_one.score_components, expected_candidate_ref=wrong_schema_candidate
    )
    assert wrong_schema_resolution.status == "invalid"
    assert wrong_schema_resolution.reason_code == "current_candidate_manifest_invalid"
    assert wrong_schema_resolution.robustness_score is None

    counterfeit_legacy_kind = store.put_json(
        candidate_body,
        PutOptions(
            kind="scientist.policy_candidate_schema",
            media_type="application/json",
            schema=SchemaInfo(name=PolicyCandidateSchema.ARTIFACT_SCHEMA_NAME, version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    legacy_resolution = resolve_stress_score_components(
        store, top_one.score_components, expected_candidate_ref=counterfeit_legacy_kind
    )
    assert legacy_resolution.status == "unbound"
    assert legacy_resolution.reason_code == "current_candidate_ref_not_canonical"
    assert legacy_resolution.robustness_score is None

    profileless_candidate = candidate_ref.model_copy(update={"manifest_profile_sha256": None})
    profileless_resolution = resolve_stress_score_components(
        store, top_one.score_components, expected_candidate_ref=profileless_candidate
    )
    assert profileless_resolution.status == "unbound"
    assert profileless_resolution.robustness_score is None
    assert one_resolution.predicate_status == ten_resolution.predicate_status == "not_established"
    assert (
        one_resolution.total_scenarios_evaluated == ten_resolution.total_scenarios_evaluated == 10
    )
    assert one_resolution.passed_count == ten_resolution.passed_count == 0
    assert one_resolution.robustness_score is ten_resolution.robustness_score is None
    assert top_one.robustness_score is top_ten.robustness_score is None

    mixed_values = (1.0, -1.0, 1.0, -1.0)
    mixed_top_one, mixed_top_one_ref = run(1, mixed_values)
    mixed_top_two, mixed_top_two_ref = run(2, mixed_values)
    _, mixed_one_resolution = resolve_stress_report_artifact(
        store, mixed_top_one_ref, expected_candidate_ref=candidate_ref
    )
    _, mixed_two_resolution = resolve_stress_report_artifact(
        store, mixed_top_two_ref, expected_candidate_ref=candidate_ref
    )

    # Two of four explicit outcomes pass; one top-k presentation retains only one failure.
    assert len(mixed_top_one.vulnerabilities) == 1
    assert len(mixed_top_two.vulnerabilities) == 2
    assert mixed_one_resolution.status == mixed_two_resolution.status == "unbound"
    assert (
        mixed_one_resolution.predicate_status
        == mixed_two_resolution.predicate_status
        == "not_established"
    )
    assert (
        mixed_one_resolution.total_scenarios_evaluated
        == mixed_two_resolution.total_scenarios_evaluated
        == 4
    )
    assert mixed_one_resolution.passed_count == mixed_two_resolution.passed_count == 2
    assert mixed_one_resolution.robustness_score is mixed_two_resolution.robustness_score is None
    assert mixed_top_one.robustness_score is mixed_top_two.robustness_score is None

    zero_report, zero_report_ref = run(2, (0.0, 0.0))
    _, zero_resolution = resolve_stress_report_artifact(
        store, zero_report_ref, expected_candidate_ref=candidate_ref
    )
    assert zero_report.score_status == "unbound"
    assert zero_resolution.status == "unbound"
    assert zero_resolution.reason_code == "selected_objective_intent_not_independently_established"
    assert zero_resolution.passed_count == 0
    assert zero_resolution.robustness_score is None

    corrupted = top_one.model_copy(update={"critical_count": top_one.critical_count + 1})
    corrupted_ref = store.put_json(
        corrupted.model_dump(mode="json"),
        PutOptions(
            kind="scientist.stress_test_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.StressTestReport", version="1.1"),
            inputs=[
                *[
                    _selected_input(item.outcome_basis_ref, role="stress_outcome_basis")
                    for item in top_one.score_components
                ],
                _selected_input(candidate_ref, role="candidate"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    _, corrupted_resolution = resolve_stress_report_artifact(
        store, corrupted_ref, expected_candidate_ref=candidate_ref
    )
    assert corrupted_resolution.status == "invalid"
    assert corrupted_resolution.reason_code == "report_summary_reconciliation_failed"
    assert corrupted_resolution.robustness_score is None

    missing_candidate_component_resolution = resolve_stress_score_components(
        store, top_one.score_components, expected_candidate_ref=None
    )
    assert missing_candidate_component_resolution.status == "unbound"
    assert missing_candidate_component_resolution.reason_code == "current_candidate_ref_missing"
    assert missing_candidate_component_resolution.robustness_score is None
    _, missing_candidate_resolution = resolve_stress_report_artifact(
        store, top_one_ref, expected_candidate_ref=None
    )
    assert missing_candidate_resolution.status == "unbound"
    assert missing_candidate_resolution.reason_code == "current_candidate_ref_missing"
    assert missing_candidate_resolution.robustness_score is None

    component = top_one.score_components[0]
    basis_payload = load_core_json_artifact(store, component.outcome_basis_ref)
    basis = StressOutcomeBasis.model_validate(basis_payload)
    plan_ref = basis.plan_ref
    assert plan_ref is not None

    def basis_inputs(selected_basis: StressOutcomeBasis) -> list[InputRef]:
        refs: list[InputRef] = []
        if selected_basis.plan_ref is not None:
            refs.append(_selected_input(selected_basis.plan_ref, role="adversarial_plan"))
        if selected_basis.candidate_ref is not None:
            refs.append(_selected_input(selected_basis.candidate_ref, role="candidate"))
        if selected_basis.benchmark_evaluation_ref is not None:
            refs.append(
                _selected_input(
                    selected_basis.benchmark_evaluation_ref,
                    role="benchmark_evaluation",
                )
            )
        refs.extend(
            _selected_input(
                outcome.objective_evidence.source_ref,
                role=f"objective_source:{outcome.occurrence_index}",
            )
            for outcome in selected_basis.outcomes
            if outcome.objective_evidence is not None
        )
        return refs

    def persist_basis(
        selected_basis: StressOutcomeBasis,
        *,
        schema_name: str = "polisyos.scientist.StressOutcomeBasis",
    ) -> ArtifactRef:
        return store.put_json(
            selected_basis.model_dump(mode="json"),
            PutOptions(
                kind="scientist.stress_outcome_basis",
                media_type="application/json",
                schema=SchemaInfo(name=schema_name, version=selected_basis.schema_version),
                inputs=basis_inputs(selected_basis),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )

    source_evidence = basis.outcomes[0].objective_evidence
    assert source_evidence is not None
    source_ref = source_evidence.source_ref
    source_body = load_core_json_artifact(
        store,
        source_ref,
        manifest_profile_sha256=source_ref.manifest_profile_sha256,
    )
    assert isinstance(source_body, dict)
    altered_source = dict(source_body)
    altered_source["gdp_change"] = float(altered_source["gdp_change"]) + 0.25
    altered_source_ref = store.put_json(
        altered_source,
        PutOptions(
            kind="scientist.stress_objective_source",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.StressObjectiveSource", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    altered_outcome = basis.outcomes[0].model_copy(
        update={
            "objective_evidence": source_evidence.model_copy(
                update={"source_ref": altered_source_ref}
            )
        }
    )
    altered_basis = basis.model_copy(update={"outcomes": [altered_outcome, *basis.outcomes[1:]]})
    altered_basis_ref = persist_basis(altered_basis)
    altered_component = component.model_copy(update={"outcome_basis_ref": altered_basis_ref})
    altered_resolution = resolve_stress_score_components(
        store, [altered_component], expected_candidate_ref=candidate_ref
    )
    assert altered_resolution.status == "invalid"
    assert altered_resolution.reason_code == "objective_source_replay_mismatch"
    assert altered_resolution.robustness_score is None

    # Keep all source and lineage markers intact while falsifying the stored
    # outcome classification. Fresh resolution must derive status/severity
    # from the selected objective source and plan threshold.
    status_forgery = basis.outcomes[0].model_copy(
        update={"status": "passed", "vulnerabilities": []}
    )
    status_forgery_basis = basis.model_copy(
        update={"outcomes": [status_forgery, *basis.outcomes[1:]]}
    )
    status_forgery_ref = persist_basis(status_forgery_basis)
    status_forgery_resolution = resolve_stress_score_components(
        store,
        [component.model_copy(update={"outcome_basis_ref": status_forgery_ref})],
        expected_candidate_ref=candidate_ref,
    )
    assert status_forgery_resolution.status == "invalid"
    assert status_forgery_resolution.reason_code == "objective_outcome_classification_mismatch"
    assert status_forgery_resolution.robustness_score is None

    original_vulnerability = basis.outcomes[0].vulnerabilities[0]
    severity_forgery = basis.outcomes[0].model_copy(
        update={
            "vulnerabilities": [original_vulnerability.model_copy(update={"severity": "critical"})]
        }
    )
    severity_forgery_basis = basis.model_copy(
        update={"outcomes": [severity_forgery, *basis.outcomes[1:]]}
    )
    severity_forgery_ref = persist_basis(severity_forgery_basis)
    severity_forgery_resolution = resolve_stress_score_components(
        store,
        [component.model_copy(update={"outcome_basis_ref": severity_forgery_ref})],
        expected_candidate_ref=candidate_ref,
    )
    assert severity_forgery_resolution.status == "invalid"
    assert (
        severity_forgery_resolution.reason_code == "objective_vulnerability_classification_mismatch"
    )
    assert severity_forgery_resolution.robustness_score is None

    description_forgery = basis.outcomes[0].model_copy(
        update={
            "vulnerabilities": [
                original_vulnerability.model_copy(update={"description": "different report text"})
            ]
        }
    )
    description_forgery_basis = basis.model_copy(
        update={"outcomes": [description_forgery, *basis.outcomes[1:]]}
    )
    description_forgery_ref = persist_basis(description_forgery_basis)
    description_forgery_resolution = resolve_stress_score_components(
        store,
        [component.model_copy(update={"outcome_basis_ref": description_forgery_ref})],
        expected_candidate_ref=candidate_ref,
    )
    assert description_forgery_resolution.status == "invalid"
    assert (
        description_forgery_resolution.reason_code
        == "objective_vulnerability_classification_mismatch"
    )
    assert description_forgery_resolution.robustness_score is None

    sample_forgery = basis.outcomes[0].model_copy(
        update={"parameter_values": {**basis.outcomes[0].parameter_values, "p0": 0.5}}
    )
    sample_forgery_basis = basis.model_copy(
        update={"outcomes": [sample_forgery, *basis.outcomes[1:]]}
    )
    sample_forgery_ref = persist_basis(sample_forgery_basis)
    sample_forgery_resolution = resolve_stress_score_components(
        store,
        [component.model_copy(update={"outcome_basis_ref": sample_forgery_ref})],
        expected_candidate_ref=candidate_ref,
    )
    assert sample_forgery_resolution.status == "invalid"
    assert sample_forgery_resolution.reason_code == "plan_parameter_values_mismatch"
    assert sample_forgery_resolution.robustness_score is None

    malformed_evidence = source_evidence.model_copy(
        update={
            "score_assessment": {
                **source_evidence.score_assessment,
                "unrecognized_status_marker": "available",
            }
        }
    )
    malformed_basis = basis.model_copy(
        update={
            "outcomes": [
                basis.outcomes[0].model_copy(update={"objective_evidence": malformed_evidence}),
                *basis.outcomes[1:],
            ]
        }
    )
    malformed_basis_ref = persist_basis(malformed_basis)
    malformed_component = component.model_copy(update={"outcome_basis_ref": malformed_basis_ref})
    malformed_resolution = resolve_stress_score_components(
        store, [malformed_component], expected_candidate_ref=candidate_ref
    )
    assert malformed_resolution.status == "invalid"
    assert malformed_resolution.reason_code == "objective_assessment_contract_mismatch"
    assert malformed_resolution.robustness_score is None

    legacy_basis = basis.model_copy(
        update={
            "schema_version": "1.0",
            "outcomes": [
                outcome.model_copy(update={"objective_evidence": None})
                for outcome in basis.outcomes
            ],
        }
    )
    legacy_basis_ref = persist_basis(legacy_basis)
    legacy_component = component.model_copy(update={"outcome_basis_ref": legacy_basis_ref})
    legacy_resolution = resolve_stress_score_components(
        store, [legacy_component], expected_candidate_ref=candidate_ref
    )
    assert legacy_resolution.status == "unbound"
    assert legacy_resolution.reason_code == "legacy_adversarial_objective_source_evidence_missing"
    assert legacy_resolution.robustness_score is None

    plan_body = load_core_json_artifact(store, plan_ref)
    wrong_plan_schema_ref = store.put_json(
        plan_body,
        PutOptions(
            kind="scientist.adversarial_plan",
            media_type="application/json",
            schema=SchemaInfo(name="wrong.AdversarialPlan", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert wrong_plan_schema_ref.artifact_id == plan_ref.artifact_id
    assert wrong_plan_schema_ref.manifest_profile_sha256 != plan_ref.manifest_profile_sha256
    wrong_plan_basis = basis.model_copy(update={"plan_ref": wrong_plan_schema_ref})
    wrong_plan_basis_ref = persist_basis(wrong_plan_basis)

    def persist_report_for_basis(ref: ArtifactRef) -> ArtifactRef:
        selected_component = component.model_copy(update={"outcome_basis_ref": ref})
        selected_report = top_one.model_copy(update={"score_components": [selected_component]})
        return store.put_json(
            selected_report.model_dump(mode="json"),
            PutOptions(
                kind="scientist.stress_test_report",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.scientist.StressTestReport", version="1.1"),
                inputs=[
                    _selected_input(ref, role="stress_outcome_basis"),
                    _selected_input(candidate_ref, role="candidate"),
                ],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )

    def assert_basis_refusal(
        ref: ArtifactRef,
        *,
        component_status: str,
        component_reason: str,
        report_ref: ArtifactRef | None = None,
    ) -> None:
        selected_component = component.model_copy(update={"outcome_basis_ref": ref})
        component_resolution = resolve_stress_score_components(
            store, [selected_component], expected_candidate_ref=candidate_ref
        )
        assert component_resolution.status == component_status
        assert component_resolution.reason_code == component_reason
        assert component_resolution.robustness_score is None

        selected_report_ref = (
            report_ref if report_ref is not None else persist_report_for_basis(ref)
        )
        _, report_resolution = resolve_stress_report_artifact(
            store, selected_report_ref, expected_candidate_ref=candidate_ref
        )
        assert report_resolution.status == "invalid"
        assert report_resolution.reason_code == "score_claim_without_resolved_basis"
        assert report_resolution.robustness_score is None

    assert_basis_refusal(
        wrong_plan_basis_ref,
        component_status="invalid",
        component_reason="adversarial_plan_unreadable",
    )

    # The complete report projection is derived from source rows, not trusted by list shape.
    report_projection_forgery = top_one.model_copy(
        update={
            "vulnerabilities": [
                top_one.vulnerabilities[0].model_copy(update={"mitigation": "forged mitigation"})
            ]
        }
    )
    report_projection_forgery_ref = store.put_json(
        report_projection_forgery.model_dump(mode="json"),
        PutOptions(
            kind="scientist.stress_test_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.StressTestReport", version="1.1"),
            inputs=[
                _selected_input(component.outcome_basis_ref, role="stress_outcome_basis"),
                _selected_input(candidate_ref, role="candidate"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    _, report_projection_resolution = resolve_stress_report_artifact(
        store, report_projection_forgery_ref, expected_candidate_ref=candidate_ref
    )
    assert report_projection_resolution.status == "invalid"
    assert (
        report_projection_resolution.reason_code
        == "report_vulnerability_projection_reconciliation_failed"
    )
    assert report_projection_resolution.robustness_score is None
    wrong_basis_schema_ref = store.put_json(
        basis_payload,
        PutOptions(
            kind="scientist.stress_outcome_basis",
            media_type="application/json",
            schema=SchemaInfo(name="wrong.StressOutcomeBasis", version=basis.schema_version),
            inputs=basis_inputs(basis),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert wrong_basis_schema_ref.artifact_id == component.outcome_basis_ref.artifact_id
    assert store.get_bytes(wrong_basis_schema_ref.artifact_id) == store.get_bytes(
        component.outcome_basis_ref.artifact_id
    )
    assert (
        wrong_basis_schema_ref.manifest_profile_sha256
        != component.outcome_basis_ref.manifest_profile_sha256
    )
    assert_basis_refusal(
        wrong_basis_schema_ref,
        component_status="invalid",
        component_reason="outcome_basis_unreadable",
    )
    stale_profile_basis = basis.model_copy(
        update={"plan_ref": plan_ref.model_copy(update={"manifest_profile_sha256": None})}
    )
    stale_profile_basis_ref = persist_basis(stale_profile_basis)
    assert_basis_refusal(
        stale_profile_basis_ref,
        component_status="unbound",
        component_reason="adversarial_plan_profile_missing",
    )
    forged_basis = basis.model_copy(
        update={
            "outcomes": [
                basis.outcomes[0].model_copy(update={"scenario_id": "initial:forged"}),
                *basis.outcomes[1:],
            ]
        }
    )
    forged_basis_ref = persist_basis(forged_basis)
    forged_component = component.model_copy(update={"outcome_basis_ref": forged_basis_ref})
    forged_report_ref = store.put_json(
        top_one.model_copy(update={"score_components": [forged_component]}).model_dump(mode="json"),
        PutOptions(
            kind="scientist.stress_test_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.StressTestReport", version="1.1"),
            inputs=[
                _selected_input(candidate_ref, role="candidate"),
                _selected_input(forged_basis_ref, role="stress_outcome_basis"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert_basis_refusal(
        forged_basis_ref,
        component_status="invalid",
        component_reason="plan_outcome_roster_mismatch",
        report_ref=forged_report_ref,
    )

    partial_basis = basis.model_copy(update={"outcomes": basis.outcomes[:1], "complete": False})
    partial_basis_ref = persist_basis(partial_basis)
    partial_component = component.model_copy(update={"outcome_basis_ref": partial_basis_ref})
    partial_report_ref = store.put_json(
        top_one.model_copy(
            update={
                "score_components": [partial_component],
                "score_status": "partial",
                "score_reason": "expected_occurrence_rows_incomplete",
                "robustness_score": None,
            }
        ).model_dump(mode="json"),
        PutOptions(
            kind="scientist.stress_test_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.StressTestReport", version="1.1"),
            inputs=[
                _selected_input(candidate_ref, role="candidate"),
                _selected_input(partial_basis_ref, role="stress_outcome_basis"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    partial_component_resolution = resolve_stress_score_components(
        store, [partial_component], expected_candidate_ref=candidate_ref
    )
    assert partial_component_resolution.status == "partial"
    assert partial_component_resolution.reason_code == "expected_occurrence_rows_incomplete"
    assert partial_component_resolution.robustness_score is None
    _, partial_resolution = resolve_stress_report_artifact(
        store, partial_report_ref, expected_candidate_ref=candidate_ref
    )
    assert partial_resolution.status == "partial"
    assert partial_resolution.reason_code == "expected_occurrence_rows_incomplete"
    assert partial_resolution.robustness_score is None


def test_platform_meta_report_persistence_returns_selected_manifest_view(tmp_path) -> None:
    from polisyos.core.artifacts.canonical_profile import read_core_manifest_profile
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.scientist.methods.search.adversarial import (
        PlatformMetaEvaluationReport,
        persist_platform_meta_evaluation_report,
    )

    store = FileSystemCAS(tmp_path / "cas")
    report = PlatformMetaEvaluationReport(
        metadata={"run_id": "run-selected-meta"},
    )

    ref = persist_platform_meta_evaluation_report(store, report)

    assert ref.manifest_profile_sha256 is not None
    manifest, _declaration = read_core_manifest_profile(
        store,
        ref,
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )
    assert manifest.kind == "scientist.platform_meta_evaluation_report"
