from __future__ import annotations

from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.autotune.models import BenchmarkEvaluation, BenchmarkSplit
from polisyos.scientist.doe.designs import AdversarialPlan, AdversarialStrategy, ParameterSpec
from polisyos.scientist.search.adversarial import (
    NegatedCompositeObjective,
    PlatformMetaEvaluationInput,
    PlatformMetaEvaluator,
    run_stress_test,
)
from polisyos.scientist.search.objective import (
    CompositeObjective,
    ObjectiveValue,
    OptimizationDirection,
)
from polisyos.scientist.search.sentinels import (
    SentinelCandidate,
    SentinelKind,
    SentinelObservation,
    SentinelSet,
)
from polisyos.scientist.search.stages import CorrelationTracker, StageResult


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


def test_platform_meta_evaluator_passes_healthy_sentinel_injection() -> None:
    tracker = CorrelationTracker(drift_window_size=5, sentinel_pass_floor=0.95)
    for idx in range(5):
        tracker.record(
            StageResult(policy_candidate={}, objective_value=0.8, is_promising=True, stage_name="L2"),
            StageResult(policy_candidate={}, objective_value=0.75, is_promising=True, stage_name="L4"),
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

    sentinel_result = next(item for item in report.attack_results if item.attack_type == "sentinel_injection")
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

    result = next(item for item in report.attack_results if item.attack_type == "hidden_holdout_rotation")
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

    result = next(item for item in report.attack_results if item.attack_type == "hidden_holdout_rotation")
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
            StageResult(policy_candidate={}, objective_value=float(idx), is_promising=True, stage_name="L2"),
            StageResult(policy_candidate={}, objective_value=float(5 - idx), is_promising=(idx % 2 == 0), stage_name="L4"),
            f"neg{idx}",
            is_sentinel=False,
        )
    report = PlatformMetaEvaluator().evaluate(
        PlatformMetaEvaluationInput(
            correlation_tracker=tracker,
            observed_scheduler_mode=tracker.routing_mode(),
        )
    )

    result = next(item for item in report.attack_results if item.attack_type == "calibration_drift_replay")
    assert result.status == "passed"
    assert "CALIBRATION_DRIFT" in result.triggered_guards or "PROMOTION_BAN" in result.triggered_guards
