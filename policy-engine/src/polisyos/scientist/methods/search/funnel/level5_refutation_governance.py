"""Level 5 refutation/governance funnel stage."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from math import isfinite
from typing import Any, Literal

from pydantic import BaseModel

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ArtifactRef, ArtifactStore, input_ref_from_artifact_ref
from polisyos.ir import FailureSeverity, TypedFailureCard, UncertaintyType
from polisyos.ir.analytics.causal import CausalEffectReport, EstimationStatus
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    EvidenceStatus,
    TransportStatus,
)
from polisyos.ir.analytics.distributional import DistributionalReport
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
)
from polisyos.scientist.methods.doe.stress_report import (
    StressScoreResolution,
    StressTestReport,
    resolve_stress_report_artifact,
)
from polisyos.scientist.methods.search.actionable_side_information import (
    ActionableSideInformation,
    persist_actionable_side_information,
    resolve_actionable_store,
)
from polisyos.scientist.methods.search.adversarial import PlatformMetaEvaluationReport
from polisyos.scientist.methods.search.funnel.types import (
    FunnelStage,
    FunnelStageResult,
)
from polisyos.scientist.methods.search.objective import ObjectiveScoreStatus
from polisyos.scientist.methods.search.uncertainty import (
    UncertaintyEnvelope,
    UncertaintyEstimate,
)

logger = get_logger(__name__)

_ReportResolver = Callable[[dict[str, Any], dict[str, Any]], Any | None]


class Level5RefutationGovernanceStage(FunnelStage):
    """Aggregates hidden holdout, stress, governance, and calibration guards."""

    def __init__(
        self,
        *,
        hidden_holdout_evaluator: _ReportResolver | None = None,
        stress_evaluator: _ReportResolver | None = None,
        governance_evaluator: _ReportResolver | None = None,
        platform_meta_evaluator: _ReportResolver | None = None,
        estimated_cost_usd: float = 0.25,
        cost_per_second_usd: float = 0.01,
        hidden_holdout_degradation_threshold: float = 0.10,
        require_hidden_holdout: bool = True,
        require_platform_meta: bool = False,
        store: ArtifactStore | None = None,
    ) -> None:
        self._hidden_holdout_evaluator = hidden_holdout_evaluator
        self._stress_evaluator = stress_evaluator
        self._governance_evaluator = governance_evaluator
        self._platform_meta_evaluator = platform_meta_evaluator
        self._estimated_cost_usd = float(estimated_cost_usd)
        self._cost_per_second_usd = float(cost_per_second_usd)
        self._hidden_holdout_degradation_threshold = float(hidden_holdout_degradation_threshold)
        self._require_hidden_holdout = bool(require_hidden_holdout)
        self._require_platform_meta = bool(require_platform_meta)
        self._store = store

    @property
    def stage_name(self) -> str:
        return "funnel_L5_refutation_governance"

    @property
    def fidelity_level(self) -> int:
        return 5

    @property
    def estimated_cost_usd(self) -> float:
        return self._estimated_cost_usd

    def evaluate(
        self,
        candidate: dict[str, Any],
        context: dict[str, Any],
    ) -> FunnelStageResult:
        start = datetime.now(UTC)
        prior_result = _prior_result(context)
        objective_value = prior_result.objective_value if prior_result is not None else None
        objective_score_status = (
            prior_result.score_status
            if prior_result is not None
            else ObjectiveScoreStatus.UNAVAILABLE
        )
        failure_cards: list[TypedFailureCard] = []
        terminal_action: (
            Literal[
                "advance",
                "defer",
                "reject",
                "retry_cheaper",
                "complete",
                "defer_to_human",
            ]
            | None
        ) = None

        selection = _coerce_model(
            BenchmarkEvaluation,
            context.get("selection_evaluation") or context.get("benchmark_evaluation"),
        )
        hidden_holdout = _coerce_model(
            BenchmarkEvaluation,
            context.get("hidden_holdout_evaluation"),
        )
        if hidden_holdout is None and self._hidden_holdout_evaluator is not None:
            hidden_holdout = _coerce_model(
                BenchmarkEvaluation,
                self._hidden_holdout_evaluator(candidate, context),
            )
        raw_stress_report_ref = context.get("stress_test_report_ref")
        stress_report_ref = _coerce_artifact_ref(raw_stress_report_ref)
        stress_report = _coerce_model(
            StressTestReport,
            context.get("stress_test_report") or context.get("level5_stress_report"),
        )
        score_status = "not_evaluated"
        score_profile = None
        score_reason = "stress_report_missing"
        score_predicate_status = "not_established"
        score_case_truth_status = "not_established"
        score_case_truth_required = False
        score_value: float | None = None
        source_score_status: str | None = None
        source_score_profile: str | None = None
        source_score_value: float | None = None
        score_source_reports: list[dict[str, Any]] = []
        stress_resolution: StressScoreResolution | None = None

        if raw_stress_report_ref is not None:
            store = context.get("store") or self._store
            raw_candidate_ref = context.get("policy_candidate_ref")
            current_candidate_ref = _coerce_artifact_ref(raw_candidate_ref)
            if stress_report_ref is None:
                stress_report = StressTestReport(
                    report_id="malformed-stress-report-reference"
                ).model_copy(
                    update={
                        "score_status": "invalid",
                        "score_reason": "malformed_stress_report_reference",
                        "score_predicate_status": "not_established",
                        "robustness_score": None,
                    }
                )
                score_status = "invalid"
                score_reason = "malformed_stress_report_reference"
            elif store is None:
                stress_report = stress_report or StressTestReport(
                    report_id="unbound-stress-report-reference"
                )
                source_score_status = stress_report.score_status
                source_score_profile = stress_report.score_profile
                source_score_value = stress_report.robustness_score
                score_source_reports = _stress_score_source_reports(stress_report)
                score_status = "unbound"
                score_profile = stress_report.score_profile
                score_reason = "fresh_report_store_unavailable"
                stress_report = stress_report.model_copy(
                    update={
                        "score_status": score_status,
                        "score_reason": score_reason,
                        "score_predicate_status": score_predicate_status,
                        "robustness_score": None,
                    }
                )
            else:
                raw_selected_phase_d4_refs = context.get("phase_d4_selected_evaluation_refs")
                phase_d4_roster = None
                selection_ref = _coerce_artifact_ref(context.get("selection_evaluation_ref"))
                selection = context.get("selection_evaluation")
                run_id = context.get("run_id")
                if (
                    "phase_d4_selected_evaluation_refs" in context
                    and isinstance(raw_selected_phase_d4_refs, (list, tuple))
                    and isinstance(selection, BenchmarkEvaluation)
                    and isinstance(run_id, str)
                    and current_candidate_ref is not None
                    and selection_ref is not None
                ):
                    try:
                        from polisyos.scientist.methods.backtesting.phase_d4_source import (
                            build_phase_d4_suite_roster,
                        )

                        phase_d4_roster = build_phase_d4_suite_roster(
                            store,
                            rotating_evaluation_refs=raw_selected_phase_d4_refs,
                            expected_candidate_ref=current_candidate_ref,
                            expected_selection_evaluation_ref=selection_ref,
                            expected_run_id=run_id,
                            expected_loop_id=selection.loop_id,
                        )
                    except Exception:
                        phase_d4_roster = None
                stress_report, resolution = resolve_stress_report_artifact(
                    store,
                    stress_report_ref,
                    expected_candidate_ref=current_candidate_ref,
                    expected_run_id=run_id if isinstance(run_id, str) else None,
                    expected_selection_evaluation_ref=selection_ref,
                    expected_phase_d4_roster=phase_d4_roster,
                )
                stress_resolution = resolution
                source_score_status = stress_report.score_status
                source_score_profile = stress_report.score_profile
                source_score_value = stress_report.robustness_score
                score_source_reports = _stress_score_source_reports(stress_report)
                if raw_candidate_ref is not None and current_candidate_ref is None:
                    resolution = resolution.model_copy(
                        update={
                            "status": "invalid",
                            "score_profile": None,
                            "robustness_score": None,
                            "reason_code": "malformed_current_candidate_reference",
                            "predicate_status": "not_established",
                        }
                    )
                score_status = resolution.status
                score_profile = resolution.score_profile or stress_report.score_profile
                score_reason = resolution.reason_code
                score_predicate_status = resolution.predicate_status
                score_case_truth_status = resolution.case_truth_status
                score_case_truth_required = resolution.case_truth_required is True
                score_value = resolution.robustness_score
                stress_report = stress_report.model_copy(
                    update={
                        "score_status": score_status,
                        "score_reason": score_reason,
                        "score_predicate_status": score_predicate_status,
                        "case_truth_status": score_case_truth_status,
                        "case_truth_reason": resolution.case_truth_reason,
                        "score_profile": score_profile,
                        "robustness_score": score_value,
                    }
                )
                stress_report._case_truth_required = resolution.case_truth_required
        else:
            if stress_report is None and self._stress_evaluator is not None:
                stress_report = _coerce_model(
                    StressTestReport,
                    self._stress_evaluator(candidate, context),
                )
            if stress_report is not None:
                source_score_status = stress_report.score_status
                source_score_profile = stress_report.score_profile
                source_score_value = stress_report.robustness_score
                score_source_reports = _stress_score_source_reports(stress_report)
                score_status = "unbound"
                score_profile = stress_report.score_profile
                score_reason = "persisted_report_reference_required"
                stress_report = stress_report.model_copy(
                    update={
                        "score_status": score_status,
                        "score_reason": score_reason,
                        "score_predicate_status": score_predicate_status,
                        "robustness_score": None,
                    }
                )

        governance_report = _coerce_model(
            GovernanceReport,
            context.get("governance_report"),
        )
        if governance_report is None and self._governance_evaluator is not None:
            governance_report = _coerce_model(
                GovernanceReport,
                self._governance_evaluator(candidate, context),
            )
        platform_meta = _coerce_model(
            PlatformMetaEvaluationReport,
            context.get("platform_meta_evaluation_report"),
        )
        if platform_meta is None and self._platform_meta_evaluator is not None:
            platform_meta = _coerce_model(
                PlatformMetaEvaluationReport,
                self._platform_meta_evaluator(candidate, context),
            )
        distributional_report = _coerce_model(
            DistributionalReport,
            context.get("distributional_report"),
        )
        causal_report = _coerce_model(
            CausalEffectReport,
            context.get("causal_effect_report"),
        )
        cross_graph_profile = _coerce_model(
            CrossGraphEvidenceProfile,
            context.get("cross_graph_profile"),
        )

        selection_split_card = _runtime_split_failure_card(
            evaluation=selection,
            expected=BenchmarkSplit.SELECTION,
            label="selection_evaluation",
        )
        if selection_split_card is not None:
            failure_cards.append(selection_split_card)
        hidden_holdout_split_card = _runtime_split_failure_card(
            evaluation=hidden_holdout,
            expected=BenchmarkSplit.HIDDEN_HOLDOUT,
            label="hidden_holdout_evaluation",
        )
        if hidden_holdout_split_card is not None:
            failure_cards.append(hidden_holdout_split_card)

        if self._require_hidden_holdout and hidden_holdout is None:
            failure_cards.append(
                TypedFailureCard(
                    judge_name="L5_refutation_governance",
                    failure_type="hidden_holdout_missing",
                    severity=FailureSeverity.BLOCKER,
                    description="Level 5 requires a hidden holdout evaluation before promotion.",
                    uncertainty_type=UncertaintyType.TRANSPORT,
                    remediation_hint="Attach hidden_holdout_evaluation to the funnel context.",
                )
            )

        holdout_delta = _holdout_degradation(selection, hidden_holdout)
        if (
            hidden_holdout is not None
            and holdout_delta is not None
            and holdout_delta > self._hidden_holdout_degradation_threshold
        ):
            failure_cards.append(
                TypedFailureCard(
                    judge_name="L5_refutation_governance",
                    failure_type="hidden_holdout_degradation",
                    severity=FailureSeverity.BLOCKER,
                    description=(
                        "Hidden holdout degraded beyond the configured threshold at Level 5."
                    ),
                    uncertainty_type=UncertaintyType.TRANSPORT,
                    remediation_hint="Re-evaluate on refreshed holdout slices before promotion.",
                    metadata={"degradation_delta": holdout_delta},
                )
            )
        if hidden_holdout is not None and not hidden_holdout.promotable:
            failure_cards.append(
                TypedFailureCard(
                    judge_name="L5_refutation_governance",
                    failure_type="hidden_holdout_not_promotable",
                    severity=FailureSeverity.BLOCKER,
                    description="Hidden holdout evaluation marked the candidate as non-promotable.",
                    uncertainty_type=UncertaintyType.TRANSPORT,
                )
            )

        if (
            score_status == "available"
            and score_case_truth_required
            and score_case_truth_status != "recomputed"
        ):
            score_status = "unbound"
            score_reason = "phase_d4_case_truth_not_established"
            score_value = None
            if stress_report is not None:
                stress_report = stress_report.model_copy(
                    update={
                        "score_status": score_status,
                        "score_reason": score_reason,
                        "robustness_score": None,
                    }
                )
        score_is_finite_binary = (
            score_status == "available"
            and score_profile == "finite_binary_scenario_v1"
            and score_value is not None
            and type(score_value) in {int, float}
            and isfinite(score_value)
            and score_predicate_status in {"recomputed", "independently_reconciled"}
            and (not score_case_truth_required or score_case_truth_status == "recomputed")
        )
        if score_status == "available" and not score_is_finite_binary:
            score_status = "invalid"
            score_reason = "available_score_not_finite_binary_or_recomputed"
            score_value = None
            if stress_report is not None:
                stress_report = stress_report.model_copy(
                    update={
                        "score_status": score_status,
                        "score_reason": score_reason,
                        "robustness_score": None,
                    }
                )
        if score_status == "invalid":
            failure_cards.append(
                TypedFailureCard(
                    judge_name="L5_refutation_governance",
                    failure_type="stress_score_invalid",
                    severity=FailureSeverity.BLOCKER,
                    description="Stress score evidence is malformed, stale, mismatched, or inconsistent.",
                    uncertainty_type=UncertaintyType.MODEL,
                    remediation_hint="Repair the current-candidate finite outcome basis before promotion.",
                    metadata={
                        "report_id": None if stress_report is None else stress_report.report_id,
                        "score_profile": score_profile,
                        "score_reason": score_reason,
                        "score_predicate_status": score_predicate_status,
                    },
                )
            )
        elif score_is_finite_binary and stress_report is not None and not stress_report.is_robust:
            failure_cards.append(
                TypedFailureCard(
                    judge_name="L5_refutation_governance",
                    failure_type="stress_test_failed",
                    severity=FailureSeverity.BLOCKER,
                    description="Fresh finite binary stress evidence uncovered high-severity vulnerabilities.",
                    uncertainty_type=UncertaintyType.MODEL,
                    remediation_hint="Address refutation and scenario vulnerabilities before promotion.",
                    metadata={
                        "critical_count": stress_report.critical_count,
                        "high_count": stress_report.high_count,
                        "report_id": stress_report.report_id,
                        "score_profile": score_profile,
                        "score_reason": score_reason,
                    },
                )
            )
        elif not score_is_finite_binary or stress_report is None:
            failure_cards.append(
                TypedFailureCard(
                    judge_name="L5_refutation_governance",
                    failure_type="stress_score_unavailable",
                    severity=FailureSeverity.WARNING,
                    description="A current finite binary stress score is unavailable; promotion is deferred.",
                    uncertainty_type=UncertaintyType.MODEL,
                    remediation_hint="Establish a current complete finite outcome basis or obtain human review.",
                    metadata={
                        "report_id": None if stress_report is None else stress_report.report_id,
                        "score_status": score_status,
                        "score_profile": score_profile,
                        "score_reason": score_reason,
                    },
                )
            )
            terminal_action = "defer_to_human"

        if governance_report is not None:
            if governance_report.verdict == "reject":
                failure_cards.append(
                    TypedFailureCard(
                        judge_name="L5_refutation_governance",
                        failure_type="governance_reject",
                        severity=FailureSeverity.BLOCKER,
                        description="Governance verdict rejected the candidate at Level 5.",
                        remediation_hint="Resolve governance issues before promotion.",
                    )
                )
            elif governance_report.verdict == "human_gate":
                terminal_action = "defer_to_human"

        if self._require_platform_meta and platform_meta is None:
            failure_cards.append(
                TypedFailureCard(
                    judge_name="L5_refutation_governance",
                    failure_type="platform_meta_missing",
                    severity=FailureSeverity.BLOCKER,
                    description="Platform meta evaluation is required for Level 5 promotion gating.",
                    uncertainty_type=UncertaintyType.OPTIMIZATION,
                )
            )
        if platform_meta is not None and not platform_meta.promotion_safe:
            failure_cards.append(
                TypedFailureCard(
                    judge_name="L5_refutation_governance",
                    failure_type="platform_meta_evaluation_failed",
                    severity=FailureSeverity.BLOCKER,
                    description="Platform adversarial meta-evaluation marked this candidate unsafe for promotion.",
                    uncertainty_type=UncertaintyType.OPTIMIZATION,
                    remediation_hint="Recalibrate the funnel or refresh hidden holdout assets before promotion.",
                )
            )

        correlation_metrics = dict(context.get("correlation_metrics") or {})
        if bool(correlation_metrics.get("promotion_ban_active")):
            failure_cards.append(
                TypedFailureCard(
                    judge_name="L5_refutation_governance",
                    failure_type="calibration_drift_promotion_ban",
                    severity=FailureSeverity.WARNING,
                    description="Calibration drift triggered a promotion cap pending recalibration.",
                    uncertainty_type=UncertaintyType.OPTIMIZATION,
                    remediation_hint="Run burn-in recalibration before promotion resumes.",
                    metadata={
                        "rolling_spearman_correlation": correlation_metrics.get(
                            "rolling_spearman_correlation"
                        )
                    },
                )
            )

        stress_observed_sample = _observed_stress_assessment(stress_report, stress_resolution)
        envelope = _level5_uncertainty_envelope(
            prior_result=prior_result,
            holdout_delta=holdout_delta,
            stress_report=stress_report,
            platform_meta=platform_meta,
        )
        duration = (datetime.now(UTC) - start).total_seconds()
        cost_usd = max(self._estimated_cost_usd, duration * self._cost_per_second_usd)
        side_information = _build_actionable_side_information(
            candidate=candidate,
            prior_result=prior_result,
            duration_seconds=duration,
            compute_cost_usd=cost_usd,
            selection=selection,
            hidden_holdout=hidden_holdout,
            stress_report=stress_report,
            stress_observed_sample_assessment=stress_observed_sample,
            governance_report=governance_report,
            platform_meta=platform_meta,
            distributional_report=distributional_report,
            causal_report=causal_report,
            cross_graph_profile=cross_graph_profile,
            holdout_delta=holdout_delta,
        )
        store = resolve_actionable_store(context=context, store=self._store)
        side_information_ref = None
        audit_refs = list(getattr(prior_result, "audit_refs", []))
        if store is not None:
            side_information_ref = persist_actionable_side_information(
                store,
                side_information,
                inputs=(
                    [input_ref_from_artifact_ref(stress_report_ref, role="stress_test_report")]
                    if stress_report_ref is not None
                    else []
                ),
            )
            audit_refs.append(side_information_ref)

        feedback = dict(getattr(prior_result, "feedback", {}) or {})
        feedback.update(
            {
                "fidelity_level": self.fidelity_level,
                "hidden_holdout_present": hidden_holdout is not None,
                "hidden_holdout_degradation": holdout_delta,
                "stress_robust": (
                    stress_report.is_robust
                    if score_is_finite_binary and stress_report is not None
                    else None
                ),
                "stress_score_status": score_status,
                "stress_score_profile": score_profile,
                "stress_score_reason": score_reason,
                "stress_score_predicate_status": score_predicate_status,
                "stress_score_case_truth_status": score_case_truth_status,
                "stress_score_case_truth_required": score_case_truth_required,
                "stress_score_value": score_value if score_is_finite_binary else None,
                "stress_score_source_status": source_score_status,
                "stress_score_source_profile": source_score_profile,
                "stress_score_source_value": source_score_value,
                "stress_score_source_reports": score_source_reports,
                "stress_observed_sample_assessment": stress_observed_sample,
                "governance_verdict": None
                if governance_report is None
                else governance_report.verdict,
                "platform_promotion_safe": None
                if platform_meta is None
                else platform_meta.promotion_safe,
                "actionable_side_information_ref": None
                if side_information_ref is None
                else side_information_ref.model_dump(mode="json"),
            }
        )
        if terminal_action is not None:
            feedback["funnel_action"] = terminal_action

        return FunnelStageResult(
            policy_candidate=candidate,
            objective_value=objective_value,
            is_promising=not any(card.is_blocker for card in failure_cards),
            score_status=objective_score_status,
            score_assessment=(prior_result.score_assessment if prior_result is not None else None),
            stage_name=self.stage_name,
            duration_seconds=duration,
            timestamp=datetime.now(UTC),
            simulation_results=getattr(prior_result, "simulation_results", {}),
            feedback=feedback,
            predicted_score=getattr(prior_result, "predicted_score", None),
            actual_score=(
                getattr(prior_result, "actual_score", objective_value)
                if objective_score_status is ObjectiveScoreStatus.AVAILABLE
                else None
            ),
            uncertainty_envelope=envelope,
            failure_cards=failure_cards,
            compute_cost_usd=cost_usd,
            compute_cost_origin="estimated",
            fidelity_level=self.fidelity_level,
            audit_refs=audit_refs,
            actionable_side_information_ref=side_information_ref,
            terminal_action=terminal_action,
        )


def _prior_result(context: dict[str, Any]) -> FunnelStageResult | None:
    for key in ("_funnel_L5_result", "_funnel_L4_result", "_funnel_L3_result"):
        result = context.get(key)
        if isinstance(result, FunnelStageResult):
            return result
    return None


def _stress_score_source_reports(report: StressTestReport) -> list[dict[str, Any]]:
    """Return non-authoritative source-profile records for Level 5 diagnostics."""
    source_reports = report.metadata.get("score_source_reports")
    if isinstance(source_reports, list):
        rows = [dict(item) for item in source_reports if isinstance(item, dict)]
        if rows:
            return rows
    reported_score = report.robustness_score
    if (
        reported_score is None
        or type(reported_score) not in {int, float}
        or not isfinite(reported_score)
    ):
        reported_score = None
    return [
        {
            "report_id": report.report_id,
            "schema_version": report.schema_version,
            "score_status": report.score_status,
            "score_profile": report.score_profile,
            "reported_score": reported_score,
            "reported_score_present": report.robustness_score is not None,
        }
    ]


def _observed_stress_assessment(
    report: StressTestReport | None,
    resolution: StressScoreResolution | None,
) -> dict[str, Any]:
    """Describe only the finite sample established by the fresh source resolver.

    A report's score, counters, or scope-shaped metadata alone do not establish
    this assessment. The canonical resolver owns both source verification and
    finite-sample arithmetic; its admission status remains a separate limit.
    """
    unavailable = {
        "status": "unassessed",
        "score_scope": "not_established",
        "population_probability": "not_established",
        "model_uncertainty": "not_established",
    }
    if report is None or resolution is None:
        return unavailable
    if report.score_status != resolution.status:
        return unavailable
    if report.score_profile != "finite_binary_scenario_v1":
        return unavailable
    observed = resolution.observed_sample_assessment
    if observed is not None:
        return observed
    if report.score_status == "partial" and resolution.status == "partial":
        return {**unavailable, "status": "partial", "completeness": False}
    return unavailable


def _coerce_artifact_ref(value: Any) -> ArtifactRef | None:
    if value is None:
        return None
    try:
        return value if isinstance(value, ArtifactRef) else ArtifactRef.model_validate(value)
    except (TypeError, ValueError):
        return None


def _coerce_model[ModelT: BaseModel](model_cls: type[ModelT], value: object) -> ModelT | None:
    if value is None or isinstance(value, model_cls):
        return value
    if isinstance(value, dict):
        return model_cls.model_validate(value)
    return None


def _holdout_degradation(
    selection: BenchmarkEvaluation | None,
    hidden_holdout: BenchmarkEvaluation | None,
) -> float | None:
    if selection is None or hidden_holdout is None:
        return None
    shared_metrics = sorted(set(selection.selection_metrics) & set(hidden_holdout.holdout_metrics))
    if not shared_metrics:
        return None
    metric = shared_metrics[0]
    selection_value = float(selection.selection_metrics.get(metric, 0.0))
    holdout_value = float(hidden_holdout.holdout_metrics.get(metric, selection_value))
    if selection_value <= 0.0:
        return 0.0
    return max(0.0, (selection_value - holdout_value) / selection_value)


def _runtime_split_failure_card(
    *,
    evaluation: BenchmarkEvaluation | None,
    expected: BenchmarkSplit,
    label: str,
) -> TypedFailureCard | None:
    if evaluation is None or evaluation.matches_runtime_split(expected):
        return None
    observed = evaluation.resolved_runtime_split_type()
    return TypedFailureCard(
        judge_name="L5_refutation_governance",
        failure_type="benchmark_split_type_mismatch",
        severity=FailureSeverity.BLOCKER,
        description=(
            f"{label} must use runtime benchmark split '{expected.value}', got '{observed.value}'."
        ),
        uncertainty_type=UncertaintyType.OPTIMIZATION,
        remediation_hint="Attach an evaluation artifact with the correct runtime split type.",
        metadata={
            "label": label,
            "expected_split": expected.value,
            "observed_split": observed.value,
            "suite_id": evaluation.suite_id,
        },
    )


def _level5_uncertainty_envelope(
    *,
    prior_result: FunnelStageResult | None,
    holdout_delta: float | None,
    stress_report: StressTestReport | None,
    platform_meta: PlatformMetaEvaluationReport | None,
) -> UncertaintyEnvelope:
    envelope = (
        prior_result.uncertainty_envelope
        if prior_result is not None
        else UncertaintyEnvelope.unknown()
    )
    transport_level = 1.0 if holdout_delta is None else min(1.0, max(0.0, holdout_delta))
    # Finite stress outcomes do not quantify model uncertainty. Keep the prior
    # estimate and its provenance, or the envelope's explicit unassessed state.
    optimization_level = (
        1.0 if platform_meta is not None and not platform_meta.promotion_safe else 0.25
    )
    return envelope.with_update(
        UncertaintyType.TRANSPORT,
        UncertaintyEstimate(
            level=transport_level,
            source="level5_hidden_holdout",
            quantification_method="holdout_delta",
            is_reducible=True,
            recommended_action="Refresh or expand holdout evaluation if degradation persists.",
        ),
    ).with_update(
        UncertaintyType.OPTIMIZATION,
        UncertaintyEstimate(
            level=optimization_level,
            source="level5_platform_meta",
            quantification_method="meta_guard_status",
            is_reducible=True,
            recommended_action="Recalibrate cheap-to-expensive routing if promotion guardrails fired.",
        ),
    )


def _build_actionable_side_information(
    *,
    candidate: dict[str, Any],
    prior_result: FunnelStageResult | None,
    duration_seconds: float,
    compute_cost_usd: float,
    selection: BenchmarkEvaluation | None,
    hidden_holdout: BenchmarkEvaluation | None,
    stress_report: StressTestReport | None,
    stress_observed_sample_assessment: dict[str, Any],
    governance_report: GovernanceReport | None,
    platform_meta: PlatformMetaEvaluationReport | None,
    distributional_report: DistributionalReport | None,
    causal_report: CausalEffectReport | None,
    cross_graph_profile: CrossGraphEvidenceProfile | None,
    holdout_delta: float | None,
) -> ActionableSideInformation:
    candidate_id = str(
        candidate.get("candidate_id")
        or candidate.get("id")
        or candidate.get("name")
        or "unknown_candidate"
    )
    sensitivity_failures: list[str] = []
    if stress_report is not None:
        sensitivity_failures.extend(
            vuln.description or vuln.vulnerability_id
            for vuln in stress_report.vulnerabilities
            if str(vuln.severity).lower() in {"critical", "high"}
        )
    if causal_report is not None:
        sensitivity_failures.extend(
            result.test_type.value
            for result in causal_report.refutation_results
            if not result.passed
        )
    subgroup_harms: list[str] = []
    if distributional_report is not None:
        subgroup_harms.extend(
            f"{entry.cohort_label}: {entry.net_impact}"
            for entry in distributional_report.winners_losers.losers
        )
    legality_failures: list[str] = []
    if governance_report is not None:
        legality_failures.extend(
            str(issue.get("message") or issue.get("code") or issue)
            for issue in governance_report.issues
        )
    transport_failures: list[str] = []
    if cross_graph_profile is not None:
        transport_failures.extend(
            need.need.need_id
            for need in cross_graph_profile.needs
            if need.transport_status
            in {
                TransportStatus.UNSUPPORTED,
                TransportStatus.BOUNDED_NON_IDENTIFIED,
            }
            or need.evidence_status
            in {
                EvidenceStatus.INSUFFICIENT,
                EvidenceStatus.UNSUPPORTED,
            }
        )
    identifiability_blockers = []
    if causal_report is not None and causal_report.status is not EstimationStatus.SUCCESS:
        identifiability_blockers.append(causal_report.status_reason or causal_report.status.value)
    compute_budget_explanation = {}
    prior_cost_evidence: dict[str, Any] | None = None
    if prior_result is not None:
        prior_cost_evidence = {
            "amount_usd": prior_result.compute_cost_usd,
            "origin": prior_result.compute_cost_origin,
        }
        if prior_result.compute_cost_usd is not None:
            compute_budget_explanation["level4_cost_usd"] = float(prior_result.compute_cost_usd)
    compute_budget_explanation["level5_wall_seconds"] = float(duration_seconds)
    if holdout_delta is not None:
        compute_budget_explanation["hidden_holdout_delta"] = float(holdout_delta)
    if selection is not None:
        compute_budget_explanation["selection_metric_count"] = float(
            len(selection.selection_metrics)
        )
    if hidden_holdout is not None:
        compute_budget_explanation["holdout_metric_count"] = float(
            len(hidden_holdout.holdout_metrics)
        )

    return ActionableSideInformation(
        candidate_id=candidate_id,
        profiler_output={
            "stage_name": "funnel_L5_refutation_governance",
            "duration_seconds": float(duration_seconds),
            "platform_meta_status": None if platform_meta is None else platform_meta.overall_status,
        },
        timeout_diagnostics={},
        identifiability_blockers=identifiability_blockers,
        sensitivity_failures=sensitivity_failures,
        subgroup_harm_notes=subgroup_harms,
        legality_failures=legality_failures,
        transport_failures=transport_failures,
        discovery_ambiguity_notes=[],
        policy_budget_explanation=_policy_budget_explanation(candidate),
        compute_budget_explanation=compute_budget_explanation,
        metadata={
            "hidden_holdout_present": hidden_holdout is not None,
            "stress_report_id": None if stress_report is None else stress_report.report_id,
            "stress_observed_sample_assessment": stress_observed_sample_assessment,
            "governance_verdict": None if governance_report is None else governance_report.verdict,
            "level4_cost_evidence": prior_cost_evidence,
            "level5_cost_evidence": {
                "amount_usd": compute_cost_usd,
                "origin": "estimated",
            },
        },
    )


def _policy_budget_explanation(candidate: dict[str, Any]) -> dict[str, float]:
    budget = candidate.get("budget") or candidate.get("budget_allocation") or {}
    if isinstance(budget, dict):
        output: dict[str, float] = {}
        for key, value in budget.items():
            try:
                output[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
        return output
    return {}


__all__ = ["Level5RefutationGovernanceStage"]
