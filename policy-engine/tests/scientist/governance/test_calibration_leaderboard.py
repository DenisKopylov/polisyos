from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.backtest import BacktestReportRef
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
from polisyos.ir.observation.contract_compilers import SpecificationCurveInput
from polisyos.scientist.discovery.utility_judge import (
    DownstreamUtilityReport,
    HypothesisUtilityScore,
)
from polisyos.scientist.governance.backtest_matrix import (
    BacktestKind,
    BacktestKindResult,
    BacktestMatrixResult,
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
from polisyos.ir.analytics.strategic import StrategicFallbackMode


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


def _backtest_matrix(score: float = 0.8) -> BacktestMatrixResult:
    return BacktestMatrixResult(
        report_id="BTM_test",
        backtest_report_ref=BacktestReportRef(artifact_id=f"sha256:{'b' * 64}"),
        kind_results=[
            BacktestKindResult(
                kind=kind,
                status="ok",
                score=score - (index * 0.02),
                n_plans=1,
                n_scenarios=1,
            )
            for index, kind in enumerate(BacktestKind)
        ],
        composite_score=score,
        worst_kind=BacktestKind.DISTRESS,
    )


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


def test_calibration_leaderboard_populates_all_metric_slots() -> None:
    leaderboard = CalibrationLeaderboard()
    entry = leaderboard.build_entry(
        run_id="R_lb_full",
        candidate_ref=_artifact_ref("a"),
        governance_report=_governance_report(),
        calibration_fit_score=0.92,
        backtest_matrix=_backtest_matrix(),
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

    metrics = entry.metrics
    assert metrics.calibration_fit_score is not None
    assert metrics.backtest_matrix_score is not None
    assert metrics.stress_robustness_score is not None
    assert metrics.specification_curve_robustness is not None
    assert metrics.transportability_score is not None
    assert metrics.interference_fit is not None
    assert metrics.strategic_response_plausibility is not None
    assert metrics.composite_score is not None
    assert metrics.eligible_for_promotion is True


def test_calibration_leaderboard_renormalizes_composite_on_optional_gaps() -> None:
    leaderboard = CalibrationLeaderboard()
    entry = leaderboard.build_entry(
        run_id="R_lb_gaps",
        candidate_ref=_artifact_ref("d"),
        governance_report=_governance_report(),
        calibration_fit_score=0.9,
        backtest_matrix=_backtest_matrix(0.75),
        stress_scenarios=_stress_result(0.8),
        specification_curve_input=SpecificationCurveInput(
            specification_ids=["s1", "s2"],
            estimates=[0.2, 0.22],
            standard_errors=[0.1, 0.1],
        ),
    )

    expected = (
        0.9 * 0.20
        + 0.75 * 0.30
        + 0.8 * 0.20
        + entry.metrics.specification_curve_robustness * 0.10
        + entry.metrics.strategic_response_plausibility * 0.05
    ) / 0.85
    assert entry.metrics.composite_score is not None
    assert abs(entry.metrics.composite_score - expected) < 1e-9
    assert "missing_metric:transportability_score" in entry.metrics.gap_flags


def test_calibration_leaderboard_blocks_promotion_on_governance_or_adversarial_failure() -> None:
    leaderboard = CalibrationLeaderboard()
    entry = leaderboard.build_entry(
        run_id="R_lb_blocked",
        candidate_ref=_artifact_ref("e"),
        governance_report=_governance_report(adversarial_status="failed"),
        calibration_fit_score=0.95,
        backtest_matrix=_backtest_matrix(0.95),
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


def test_calibration_leaderboard_ranking_is_deterministic_on_ties() -> None:
    leaderboard = CalibrationLeaderboard()
    first = leaderboard.build_entry(
        run_id="R_a",
        candidate_ref=_artifact_ref("f"),
        governance_report=_governance_report(),
        calibration_fit_score=0.8,
        backtest_matrix=_backtest_matrix(0.8),
        stress_scenarios=_stress_result(0.8),
    )
    second = leaderboard.build_entry(
        run_id="R_b",
        candidate_ref=_artifact_ref("b"),
        governance_report=_governance_report(),
        calibration_fit_score=0.8,
        backtest_matrix=_backtest_matrix(0.8),
        stress_scenarios=_stress_result(0.8),
    )

    ranked = leaderboard.rank([second, first])
    assert [entry.run_id for entry in ranked] == ["R_a", "R_b"]
    assert [entry.rank for entry in ranked] == [1, 2]
