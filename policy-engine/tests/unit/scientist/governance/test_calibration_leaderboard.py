from __future__ import annotations

import json

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.contracts.scientist import StressTestReportRef
from polisyos.foundry.methods.catalog.causal.strategic import StrategicSolveResult
from polisyos.ir.analytics.interference import (
    ExposureMappingType,
    InterferenceCertificate,
    InterferenceEffectDecomposition,
    InterferenceMethod,
    NetworkInterferenceReport,
)
from polisyos.ir.analytics.strategic import StrategicFallbackMode
from polisyos.ir.observation.bundles import BacktestPlanBundle, ContractCompatibilityTarget
from polisyos.ir.observation.contract_compilers import SpecificationCurveInput
from polisyos.scientist.governance.backtest_matrix import (
    BacktestKind,
    BacktestMatrixResult,
    BacktestMatrixRunner,
)
from polisyos.scientist.governance.calibration import (
    CalibrationAdversarialResult,
    CalibrationGovernanceReport,
)
from polisyos.scientist.governance.calibration_leaderboard import CalibrationLeaderboard
from polisyos.scientist.governance.stress_scenarios import (
    StressScenarioComparison,
    StressScenarioKind,
    StressScenarioResult,
)
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource
from polisyos.scientist.methods.discovery.utility_judge import (
    DownstreamUtilityReport,
    HypothesisUtilityScore,
)


def _artifact_ref(seed: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{seed * 64}",
        kind="scientist.test",
        media_type="application/json",
    )


def _governance_report(*, adversarial_status: str = "passed", with_blocker: bool = False):
    issues = []
    if with_blocker:
        issues.append(
            ComplianceIssue(
                pass_id="governance_gate",
                path=["governance"],
                message="blocked",
                severity=IssueSeverity.BLOCKER,
                code="BLOCKED",
            )
        )
    return CalibrationGovernanceReport(
        verdict="approve",
        adversarial_results=[
            CalibrationAdversarialResult(
                alias="strategic_gaming_adversarial",
                suite_id="strategic_gaming_v1",
                required=True,
                status=adversarial_status,
            ),
            CalibrationAdversarialResult(
                alias="multiplicity_disclosure_adversarial",
                suite_id="multiplicity_disclosure_v1",
                required=True,
                status=adversarial_status,
            ),
        ],
        issues=issues,
        metadata={},
    )


def _backtest_matrix(tmp_path, store, score: float = 1.0) -> BacktestMatrixResult:
    path = tmp_path / "historical.json"
    path.write_text(json.dumps({"metric": [1.0, 1.0]}), encoding="utf-8")
    plan = HistoricalValidationPlan(
        plan_id="historical",
        historical_data_path=str(path),
        intervention_step=1,
        ground_truth_outcomes={"metric": [1.0]},
        target_metrics=["metric"],
        prediction_source=PredictionSource.PROVIDED,
        predicted_outcomes={"metric": [1.0 / score]},
    )
    bundle = BacktestPlanBundle(
        contract_target=ContractCompatibilityTarget(
            contract_id="leaderboard_fixture", contract_fqn="polisyos.tests.BacktestPlanBundle"
        ),
        required_fields=["metric"],
        plans=[plan.model_dump(mode="json")],
    )
    return BacktestMatrixRunner(store).run(dict.fromkeys(BacktestKind, bundle))


def _stress_result(score: float = 0.78) -> StressScenarioResult:
    return StressScenarioResult(
        report_id="stress_test",
        stress_test_report_ref=StressTestReportRef(artifact_id=f"sha256:{'c' * 64}"),
        comparisons=[
            StressScenarioComparison(
                scenario=scenario,
                baseline_objective=100.0,
                stressed_objective=95.0,
                objective_delta=-5.0,
                relative_delta=-0.05,
                severity="medium",
            )
            for scenario in StressScenarioKind
        ],
        robustness_score=score,
        worst_scenario=StressScenarioKind.TRADE_DISRUPTION,
        medium_count=6,
    )


def _downstream_utility_report(score: float = 0.88) -> DownstreamUtilityReport:
    return DownstreamUtilityReport(
        scores=[
            HypothesisUtilityScore(
                hypothesis_id="h1",
                identification_status="identified",
                identifiability_score=1.0,
                stability_score=0.8,
                transportability_score=score,
                composite_score=0.9,
                rank=1,
            )
        ],
        recommended_shortlist=["h1"],
    )


def _network_interference_report() -> NetworkInterferenceReport:
    return NetworkInterferenceReport(
        method=InterferenceMethod.PARTIAL_IPW,
        status="success",
        effects=InterferenceEffectDecomposition(
            direct_effect=0.2,
            spillover_effect=0.05,
            total_effect=0.25,
            n_units=10,
            n_treated=4,
        ),
        exposure_mapping=ExposureMappingType.FRACTIONAL,
        n_units=10,
        n_treated=4,
    )


def test_calibration_leaderboard_populates_all_metric_slots(tmp_path, cas_store) -> None:
    leaderboard = CalibrationLeaderboard(store=cas_store)
    inputs = dict(
        candidate_ref=_artifact_ref("a"),
        governance_report=_governance_report(),
        calibration_fit_score=0.92,
        stress_scenarios=_stress_result(),
        specification_curve_input=SpecificationCurveInput(
            specification_ids=["s1", "s2", "s3"],
            estimates=[0.4, 0.35, 0.3],
            standard_errors=[0.1, 0.1, 0.1],
        ),
        downstream_utility_report=_downstream_utility_report(),
        network_interference_report=_network_interference_report(),
        interference_certificate=InterferenceCertificate(
            supported_query_family="spillover",
            fallback_mode="pairwise",
            reduction_error_bound=0.05,
        ),
        strategic_summary={
            "fallback_mode": "exact_equilibrium",
            "closure_summary": {"mode": "exact_equilibrium", "equilibrium_count": 1},
            "multiplicity_note": "disclosed",
        },
    )
    matrix = _backtest_matrix(tmp_path, cas_store)
    assert matrix.metadata["report_trust_eligible"] is False
    entry = leaderboard.build_entry(run_id="R_lb_full", backtest_matrix=matrix, **inputs)

    metrics = entry.metrics
    assert metrics.calibration_fit_score is not None
    assert metrics.backtest_matrix_score is not None
    assert metrics.stress_robustness_score is not None
    assert metrics.specification_curve_robustness is not None
    assert metrics.transportability_score is not None
    assert metrics.interference_fit is not None
    assert metrics.strategic_response_plausibility is not None
    assert metrics.composite_score is not None
    assert not metrics.eligible_for_promotion
    assert "backtest_matrix_source_not_established" in metrics.gap_flags
    assert entry.metadata["composite_score_purpose"] == "candidate_diagnostic"

    degraded = _backtest_matrix(tmp_path, cas_store, 0.8)
    assert degraded.metadata["report_trust_eligible"] is False
    denied = leaderboard.build_entry(run_id="R_lb_degraded", backtest_matrix=degraded, **inputs)
    assert denied.metrics.backtest_matrix_score == degraded.composite_score
    assert denied.metrics.composite_score is not None
    assert not denied.metrics.eligible_for_promotion
    assert "backtest_matrix_source_not_established" in denied.metrics.gap_flags
    assert "backtest_matrix_report_not_trust_eligible" in denied.metrics.gap_flags


def test_unresolved_or_forged_matrix_cannot_supply_promotion_score(tmp_path, cas_store) -> None:
    matrix = _backtest_matrix(tmp_path, cas_store)
    entry = CalibrationLeaderboard().build_entry(
        run_id="R_unresolved",
        candidate_ref=_artifact_ref("a"),
        governance_report=_governance_report(),
        calibration_fit_score=0.92,
        backtest_matrix=matrix,
        stress_scenarios=_stress_result(),
    )
    assert entry.metrics.backtest_matrix_score is None
    assert entry.metrics.composite_score is None
    assert not entry.metrics.eligible_for_promotion
    assert "backtest_matrix_report_not_established" in entry.metrics.gap_flags

    # A score changed after a selected legacy report was persisted is also refused.
    matrix.composite_score = 0.9
    entry = CalibrationLeaderboard(store=cas_store).build_entry(
        run_id="R_forged_score",
        candidate_ref=_artifact_ref("a"),
        governance_report=_governance_report(),
        calibration_fit_score=0.92,
        backtest_matrix=matrix,
        stress_scenarios=_stress_result(),
    )
    assert entry.metrics.composite_score is None
    assert not entry.metrics.eligible_for_promotion
    assert "backtest_matrix_report_mismatch" in entry.metrics.gap_flags


def test_calibration_leaderboard_renormalizes_composite_on_optional_gaps(
    tmp_path, cas_store
) -> None:
    leaderboard = CalibrationLeaderboard(store=cas_store)
    entry = leaderboard.build_entry(
        run_id="R_lb_gaps",
        candidate_ref=_artifact_ref("d"),
        governance_report=_governance_report(),
        calibration_fit_score=0.9,
        backtest_matrix=_backtest_matrix(tmp_path, cas_store),
        stress_scenarios=_stress_result(0.8),
        specification_curve_input=SpecificationCurveInput(
            specification_ids=["s1", "s2"],
            estimates=[0.2, 0.22],
            standard_errors=[0.1, 0.1],
        ),
    )

    expected = (
        0.9 * 0.20
        + 1.0 * 0.30
        + 0.8 * 0.20
        + entry.metrics.specification_curve_robustness * 0.10
        + entry.metrics.strategic_response_plausibility * 0.05
    ) / 0.85
    assert entry.metrics.composite_score is not None
    assert abs(entry.metrics.composite_score - expected) < 1e-9
    assert "missing_metric:transportability_score" in entry.metrics.gap_flags


def test_calibration_leaderboard_blocks_promotion_on_governance_or_adversarial_failure(
    tmp_path, cas_store
) -> None:
    leaderboard = CalibrationLeaderboard(store=cas_store)
    entry = leaderboard.build_entry(
        run_id="R_lb_blocked",
        candidate_ref=_artifact_ref("e"),
        governance_report=_governance_report(adversarial_status="failed"),
        calibration_fit_score=0.95,
        backtest_matrix=_backtest_matrix(tmp_path, cas_store),
        stress_scenarios=_stress_result(0.95),
        strategic_summary=StrategicSolveResult(
            fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
            equilibrium_profiles=({"agency": "comply"},),
            selected_equilibrium={"agency": "comply"},
            equilibrium_selection_dependence="deterministic",
            multiplicity_note=None,
            blocked_reason=None,
            performative_shift=0.0,
            post_adaptation_policy_value=1.0,
            bounds=None,
            closure_summary={"mode": "exact_equilibrium", "equilibrium_count": 1},
        ),
    )

    assert entry.metrics.composite_score is not None
    assert entry.metrics.eligible_for_promotion is False
    assert entry.metrics.adversarial_passed is False


def test_calibration_leaderboard_ranking_is_deterministic_on_ties(tmp_path, cas_store) -> None:
    leaderboard = CalibrationLeaderboard(store=cas_store)
    matrix = _backtest_matrix(tmp_path, cas_store)
    first = leaderboard.build_entry(
        run_id="R_a",
        candidate_ref=_artifact_ref("f"),
        governance_report=_governance_report(),
        calibration_fit_score=0.8,
        backtest_matrix=matrix,
        stress_scenarios=_stress_result(0.8),
    )
    second = leaderboard.build_entry(
        run_id="R_b",
        candidate_ref=_artifact_ref("b"),
        governance_report=_governance_report(),
        calibration_fit_score=0.8,
        backtest_matrix=matrix,
        stress_scenarios=_stress_result(0.8),
    )

    first.metrics.eligible_for_promotion = True
    first.metrics.composite_score = 1.0
    ranked = leaderboard.rank([second, first])
    assert [entry.run_id for entry in ranked] == ["R_a", "R_b"]
    assert [entry.rank for entry in ranked] == [1, 2]
    assert all(not entry.metrics.eligible_for_promotion for entry in ranked)
    assert all(entry.metrics.composite_score is None for entry in ranked)

    bound = leaderboard.rank(
        [second, first],
        backtest_matrices={first.entry_id: matrix, second.entry_id: matrix},
    )
    assert [entry.run_id for entry in bound] == ["R_a", "R_b"]
    assert all(entry.metrics.composite_score is not None for entry in bound)
    assert all(not entry.metrics.eligible_for_promotion for entry in bound)
    assert all(
        entry.metadata["composite_score_purpose"] == "candidate_diagnostic" for entry in bound
    )
