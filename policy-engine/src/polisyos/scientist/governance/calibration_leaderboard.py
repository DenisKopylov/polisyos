"""Score and rank calibration candidates after governance and validation replay.

The leaderboard combines C5a verdicts, C5b backtest/stress summaries,
specification-curve robustness, transportability, interference fit, and
strategic-response plausibility into a promotion-oriented score. Missing
evidence channels become explicit gap flags instead of silently inflating rank.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.foundry.methods.catalog.causal.strategic import StrategicSolveResult
from polisyos.foundry.methods.catalog.sensitivity.specification import SpecificationCurveEstimator
from polisyos.ir.analytics.interference import InterferenceCertificate, NetworkInterferenceReport
from polisyos.ir.analytics.transportability import TransportabilityResult, TransportabilityStatus
from polisyos.ir.observation.contract_compilers import SpecificationCurveInput
from polisyos.scientist.discovery.utility_judge import DownstreamUtilityReport
from polisyos.scientist.governance.backtest_matrix import BacktestKind, BacktestMatrixResult
from polisyos.scientist.governance.calibration import (
    CalibrationAdversarialResult,
    CalibrationGovernanceReport,
)
from polisyos.scientist.governance.stress_scenarios import StressScenarioKind, StressScenarioResult

_WEIGHTS: dict[str, float] = {
    "calibration_fit_score": 0.20,
    "backtest_matrix_score": 0.30,
    "stress_robustness_score": 0.20,
    "specification_curve_robustness": 0.10,
    "transportability_score": 0.10,
    "interference_fit": 0.05,
    "strategic_response_plausibility": 0.05,
}
_REQUIRED_NUMERIC_SLOTS = {
    "calibration_fit_score",
    "backtest_matrix_score",
    "stress_robustness_score",
}


class CalibrationLeaderboardMetrics(BaseModel):
    """Normalized promotion metrics used to rank calibration candidates.

    Required evidence channels are captured as nullable scores so missing inputs
    can be surfaced through `gap_flags`. `eligible_for_promotion` is true only
    when governance approves, required adversarial suites pass, and no required
    score is missing.
    """

    model_config = ConfigDict(extra="forbid")

    calibration_fit_score: float | None = Field(default=None, ge=0.0, le=1.0)
    backtest_matrix_score: float | None = Field(default=None, ge=0.0, le=1.0)
    stress_robustness_score: float | None = Field(default=None, ge=0.0, le=1.0)
    specification_curve_robustness: float | None = Field(default=None, ge=0.0, le=1.0)
    transportability_score: float | None = Field(default=None, ge=0.0, le=1.0)
    interference_fit: float | None = Field(default=None, ge=0.0, le=1.0)
    strategic_response_plausibility: float | None = Field(default=None, ge=0.0, le=1.0)
    governance_verdict: str | None = None
    adversarial_passed: bool | None = None
    eligible_for_promotion: bool = False
    composite_score: float | None = Field(default=None, ge=0.0, le=1.0)
    gap_flags: list[str] = Field(default_factory=list)


class CalibrationLeaderboardEntry(BaseModel):
    """One ranked candidate entry in the calibration leaderboard."""

    model_config = ConfigDict(extra="forbid")

    entry_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    candidate_ref: ArtifactRef | None = None
    metrics: CalibrationLeaderboardMetrics
    worst_backtest_kind: BacktestKind | None = None
    worst_stress_scenario: StressScenarioKind | None = None
    rank: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CalibrationLeaderboard:
    """Build and rank calibration-promotion leaderboard entries.

    Candidate generation and governance happen upstream; this class only
    synthesizes evaluator feedback into one comparable entry per run and orders
    entries by eligibility, composite score, and deterministic tie-breakers.
    """

    def __init__(self) -> None:
        self._specification_curve_estimator = SpecificationCurveEstimator()

    def build_entry(
        self,
        *,
        run_id: str,
        candidate_ref: ArtifactRef | None,
        governance_report: CalibrationGovernanceReport,
        calibration_fit_score: float | None,
        backtest_matrix: BacktestMatrixResult | None,
        stress_scenarios: StressScenarioResult | None,
        specification_curve_input: SpecificationCurveInput | None = None,
        downstream_utility_report: DownstreamUtilityReport | None = None,
        transportability_result: TransportabilityResult | None = None,
        network_interference_report: NetworkInterferenceReport | None = None,
        interference_certificate: InterferenceCertificate | None = None,
        strategic_summary: Mapping[str, Any] | StrategicSolveResult | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CalibrationLeaderboardEntry:
        """Assemble a leaderboard entry from governance and validation evidence."""

        metrics = CalibrationLeaderboardMetrics(
            calibration_fit_score=_clamp(calibration_fit_score),
            backtest_matrix_score=(
                None if backtest_matrix is None else _clamp(backtest_matrix.composite_score)
            ),
            stress_robustness_score=(
                None if stress_scenarios is None else _clamp(stress_scenarios.robustness_score)
            ),
            specification_curve_robustness=self._score_specification_curve(
                specification_curve_input
            ),
            transportability_score=_score_transportability(
                downstream_utility_report,
                transportability_result,
            ),
            interference_fit=_score_interference(
                network_interference_report,
                interference_certificate,
            ),
            strategic_response_plausibility=_score_strategic_response(
                governance_report.adversarial_results,
                strategic_summary,
            ),
            governance_verdict=governance_report.resolved_verdict(),
            adversarial_passed=_adversarial_passed(governance_report.adversarial_results),
        )
        gap_flags = _collect_gap_flags(metrics)
        metrics.gap_flags = gap_flags
        metrics.composite_score = _compute_composite_score(metrics)
        metrics.eligible_for_promotion = (
            metrics.governance_verdict == "approve"
            and metrics.adversarial_passed is True
            and not gap_flags
        )
        return CalibrationLeaderboardEntry(
            entry_id=f"leaderboard_{run_id}",
            run_id=run_id,
            candidate_ref=candidate_ref,
            metrics=metrics,
            worst_backtest_kind=None if backtest_matrix is None else backtest_matrix.worst_kind,
            worst_stress_scenario=(
                None if stress_scenarios is None else stress_scenarios.worst_scenario
            ),
            metadata=dict(metadata or {}),
        )

    def rank(
        self, entries: Sequence[CalibrationLeaderboardEntry]
    ) -> list[CalibrationLeaderboardEntry]:
        """Rank entries by promotion eligibility, composite score, and tie-breakers."""

        ranked = sorted(
            entries,
            key=lambda item: (
                -int(item.metrics.eligible_for_promotion),
                -(item.metrics.composite_score or -1.0),
                -(item.metrics.calibration_fit_score or -1.0),
                len(item.metrics.gap_flags),
                item.run_id,
                item.entry_id,
            ),
        )
        return [entry.model_copy(update={"rank": index + 1}) for index, entry in enumerate(ranked)]

    def _score_specification_curve(
        self,
        specification_curve_input: SpecificationCurveInput | None,
    ) -> float | None:
        if specification_curve_input is None:
            return None
        result = self._specification_curve_estimator.pure_step(
            specification_curve_input,
            {"significance_level": 0.05},
        )["result"]
        sign_consistency = float(result.get("sign_consistency", 0.0))
        share_significant = float(result.get("share_significant", 0.0))
        inverse_iqr = 1.0 / (1.0 + max(float(result.get("iqr", 0.0)), 0.0))
        return _clamp((sign_consistency + share_significant + inverse_iqr) / 3.0)


def _collect_gap_flags(metrics: CalibrationLeaderboardMetrics) -> list[str]:
    gap_flags: list[str] = []
    for slot in _WEIGHTS:
        if getattr(metrics, slot) is None:
            gap_flags.append(f"missing_metric:{slot}")
    if metrics.governance_verdict is None:
        gap_flags.append("missing_metric:governance_verdict")
    if metrics.adversarial_passed is None:
        gap_flags.append("missing_metric:adversarial_passed")
    return gap_flags


def _compute_composite_score(metrics: CalibrationLeaderboardMetrics) -> float | None:
    weighted_sum = 0.0
    total_weight = 0.0
    for slot, weight in _WEIGHTS.items():
        value = getattr(metrics, slot)
        if value is None:
            continue
        weighted_sum += float(value) * weight
        total_weight += weight
    if total_weight <= 0.0:
        return None
    return _clamp(weighted_sum / total_weight)


def _score_transportability(
    downstream_utility_report: DownstreamUtilityReport | None,
    transportability_result: TransportabilityResult | None,
) -> float | None:
    if downstream_utility_report is not None:
        for score in downstream_utility_report.scores:
            if score.transportability_score is not None:
                return _clamp(score.transportability_score)
    if transportability_result is None:
        return None
    if transportability_result.status is TransportabilityStatus.IDENTIFIED:
        return 1.0
    if transportability_result.status in {
        TransportabilityStatus.PARTIALLY_IDENTIFIED,
        TransportabilityStatus.BOUNDED_NON_IDENTIFIED,
    }:
        return 0.5
    return 0.0


def _score_interference(
    network_interference_report: NetworkInterferenceReport | None,
    interference_certificate: InterferenceCertificate | None,
) -> float | None:
    if network_interference_report is None or interference_certificate is None:
        return None
    effective_mode = interference_certificate.mode_used or interference_certificate.fallback_mode
    if network_interference_report.status != "success" or effective_mode == "unsupported":
        return 0.0
    mode_score = 1.0 if effective_mode == "pairwise" else 0.85
    error_bound = interference_certificate.reduction_error_bound
    error_score = 1.0 if error_bound is None else max(0.0, 1.0 - min(float(error_bound), 1.0))
    return _clamp(mode_score * error_score)


def _score_strategic_response(
    adversarial_results: Sequence[CalibrationAdversarialResult],
    strategic_summary: Mapping[str, Any] | StrategicSolveResult | None,
) -> float | None:
    if not adversarial_results and strategic_summary is None:
        return None

    strategic_result = _find_adversarial_result(adversarial_results, "strategic_gaming_adversarial")
    multiplicity_result = _find_adversarial_result(
        adversarial_results,
        "multiplicity_disclosure_adversarial",
    )
    fallback_mode = _strategic_fallback_mode(strategic_summary)
    if "static" in fallback_mode:
        return 0.0

    score = 1.0
    if strategic_result is not None and strategic_result.status != "passed":
        score = 0.0
    if multiplicity_result is not None and multiplicity_result.status != "passed":
        score = min(score, 0.25)

    mode_score = {
        "exact_equilibrium": 1.0,
        "strategic_bounds": 0.75,
        "macro_abstracted": 0.6,
        "blocked": 0.3,
        "": 0.5 if strategic_summary is not None else score,
    }.get(fallback_mode, 0.0)
    score = min(score, mode_score)
    if _undisclosed_multiplicity(strategic_summary):
        score = min(score, 0.25)
    return _clamp(score)


def _adversarial_passed(results: Sequence[CalibrationAdversarialResult]) -> bool | None:
    if not results:
        return None
    required = [result for result in results if result.required]
    evaluated = required or list(results)
    return all(result.status == "passed" for result in evaluated)


def _find_adversarial_result(
    results: Sequence[CalibrationAdversarialResult],
    alias: str,
) -> CalibrationAdversarialResult | None:
    return next((result for result in results if result.alias == alias), None)


def _strategic_fallback_mode(
    strategic_summary: Mapping[str, Any] | StrategicSolveResult | None,
) -> str:
    if strategic_summary is None:
        return ""
    if isinstance(strategic_summary, StrategicSolveResult):
        return strategic_summary.fallback_mode.value
    closure_summary = strategic_summary.get("closure_summary")
    if isinstance(closure_summary, Mapping) and closure_summary.get("mode"):
        return str(closure_summary["mode"])
    return str(strategic_summary.get("fallback_mode") or "")


def _undisclosed_multiplicity(
    strategic_summary: Mapping[str, Any] | StrategicSolveResult | None,
) -> bool:
    if strategic_summary is None:
        return False
    if isinstance(strategic_summary, StrategicSolveResult):
        return (
            len(strategic_summary.equilibrium_profiles) > 1
            and not strategic_summary.multiplicity_note
        )
    closure_summary = strategic_summary.get("closure_summary")
    equilibrium_count = 1
    if isinstance(closure_summary, Mapping):
        equilibrium_count = int(closure_summary.get("equilibrium_count", 1))
    multiplicity_note = strategic_summary.get("multiplicity_note")
    return equilibrium_count > 1 and not multiplicity_note


def _clamp(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))


__all__ = [
    "CalibrationLeaderboard",
    "CalibrationLeaderboardEntry",
    "CalibrationLeaderboardMetrics",
]
