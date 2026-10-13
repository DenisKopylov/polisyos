"""Public doe stress report module API."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from math import isclose, isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef


class VulnerabilityType(str, Enum):
    """Vulnerability type public type."""

    CONSTRAINT_VIOLATION = "constraint_violation"
    NUMERICAL_INSTABILITY = "numerical_instability"
    OBJECTIVE_COLLAPSE = "objective_collapse"
    CONVERGENCE_FAILURE = "convergence_failure"
    EXTREME_SENSITIVITY = "extreme_sensitivity"
    DISTRIBUTIONAL = "distributional"
    COMBINATORIAL = "combinatorial"
    TEMPORAL = "temporal"


class Vulnerability(BaseModel):
    """Vulnerability public type."""

    model_config = ConfigDict(extra="forbid")

    vulnerability_id: str
    vulnerability_type: VulnerabilityType
    severity: str = "high"
    parameter_values: dict[str, float] = Field(default_factory=dict)
    objective_value: float | None = None
    description: str = ""
    affected_kpis: list[str] = Field(default_factory=list)
    constraint_violated: str | None = None
    mitigation: str = ""


class StressOutcomeRecord(BaseModel):
    """One emitted scenario occurrence; duplicate IDs remain separate rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    occurrence_index: int = Field(ge=0)
    scenario_id: str = Field(min_length=1)
    status: Literal["passed", "failed", "invalid", "skipped", "unknown"]
    parameter_values: dict[str, float] = Field(default_factory=dict)
    vulnerabilities: list[Vulnerability] = Field(default_factory=list)
    reason_code: str | None = None


class StressOutcomeBasis(BaseModel):
    """Persisted source rows used for a finite empirical scenario score."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    score_profile: Literal["finite_binary_scenario_v1"] = "finite_binary_scenario_v1"
    source_kind: Literal["adversarial_plan", "phase_d4_suite"]
    source_id: str = Field(min_length=1)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expected_count: int = Field(ge=0)
    expected_scenario_ids: list[str] = Field(default_factory=list)
    outcomes: list[StressOutcomeRecord] = Field(default_factory=list)
    complete: bool
    adaptive_continuation: bool = False
    plan_ref: ArtifactRef | None = None
    benchmark_evaluation_ref: ArtifactRef | None = None
    suite_id: str | None = None
    suite_version: str | None = None
    candidate_ref: ArtifactRef | None = None


class StressScoreComponent(BaseModel):
    """Reference to one immutable finite-scenario outcome basis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    component_id: str = Field(min_length=1)
    score_profile: Literal["finite_binary_scenario_v1"]
    outcome_basis_ref: ArtifactRef


class StressScoreResolution(BaseModel):
    """Freshly recomputed finite outcome status and score."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal[
        "available",
        "not_evaluated",
        "partial",
        "invalid",
        "legacy_unknown",
        "profile_mismatch",
        "unbound",
    ]
    score_profile: Literal["finite_binary_scenario_v1"] | None = None
    robustness_score: float | None = None
    total_scenarios_evaluated: int = Field(default=0, ge=0)
    passed_count: int = Field(default=0, ge=0)
    critical_count: int = Field(default=0, ge=0)
    high_count: int = Field(default=0, ge=0)
    medium_count: int = Field(default=0, ge=0)
    component_ids: list[str] = Field(default_factory=list)
    reason_code: str = Field(min_length=1)
    predicate_status: Literal[
        "recomputed",
        "independently_reconciled",
        "consumer_asserted",
        "institutionally_supplied",
        "not_established",
    ] = "not_established"


def _same_artifact(left: ArtifactRef | None, right: ArtifactRef | None) -> bool:
    return (
        left is not None
        and right is not None
        and left.artifact_id == right.artifact_id
        and left.kind == right.kind
        and left.media_type == right.media_type
    )


def _expected_adversarial_count(plan) -> int | None:
    """Recompute a finite plan denominator without trusting report counters."""
    from polisyos.scientist.methods.doe.designs import AdversarialStrategy

    if plan.strategy is AdversarialStrategy.GRID_EXTREME:
        parameter_count = len(plan.parameter_specs)
        if parameter_count >= plan.max_iterations.bit_length():
            return plan.max_iterations
        return min(2**parameter_count, plan.max_iterations)
    if plan.strategy is AdversarialStrategy.RANDOM_TAIL:
        return plan.max_iterations
    if plan.strategy is AdversarialStrategy.SEARCH_LOOP:
        return min(plan.max_iterations, 32)
    return None


def _resolution(
    status, component_ids: list[str], reason_code: str, *, predicate_status="not_established"
) -> StressScoreResolution:
    return StressScoreResolution(
        status=status,
        component_ids=component_ids,
        reason_code=reason_code,
        predicate_status=predicate_status,
    )


def resolve_stress_score_components(
    store,
    components: list[StressScoreComponent],
    *,
    expected_candidate_ref: ArtifactRef | None,
) -> StressScoreResolution:
    """Resolve actual CAS outcome rows and recompute the finite binary score."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation, BenchmarkSplit
    from polisyos.scientist.methods.doe.designs import AdversarialPlan

    component_ids = [item.component_id for item in components]
    if not components:
        return _resolution("not_evaluated", [], "no_finite_score_components")
    if expected_candidate_ref is None:
        return _resolution("unbound", component_ids, "current_candidate_ref_missing")
    if expected_candidate_ref.kind != "scientist.policy_candidate_schema":
        return _resolution("unbound", component_ids, "current_candidate_ref_wrong_kind")
    if len(component_ids) != len(set(component_ids)):
        return _resolution("invalid", component_ids, "duplicate_component_id")

    total = passed = critical = high = medium = 0
    for component in components:
        try:
            basis = StressOutcomeBasis.model_validate(
                load_core_json_artifact(store, component.outcome_basis_ref)
            )
        except Exception:
            return _resolution("invalid", component_ids, "outcome_basis_unreadable")
        if (
            component.score_profile != basis.score_profile
            or component.component_id != basis.source_id
        ):
            return _resolution("invalid", component_ids, "basis_component_mismatch")
        if not _same_artifact(basis.candidate_ref, expected_candidate_ref):
            return _resolution("invalid", component_ids, "candidate_binding_missing_or_mismatched")

        if basis.source_kind == "adversarial_plan":
            if basis.plan_ref is None or basis.benchmark_evaluation_ref is not None:
                return _resolution("invalid", component_ids, "adversarial_source_refs_invalid")
            try:
                plan = AdversarialPlan.model_validate(
                    load_core_json_artifact(store, basis.plan_ref)
                )
            except Exception:
                return _resolution("invalid", component_ids, "adversarial_plan_unreadable")
            expected_count = _expected_adversarial_count(plan)
            if expected_count is None:
                return _resolution(
                    "profile_mismatch", component_ids, "unsupported_adversarial_strategy"
                )
            if basis.adaptive_continuation:
                return _resolution(
                    "profile_mismatch", component_ids, "adaptive_continuation_not_finite"
                )
            if basis.expected_count != expected_count:
                return _resolution("invalid", component_ids, "plan_denominator_mismatch")
            if basis.expected_scenario_ids != [f"initial:{i}" for i in range(expected_count)]:
                return _resolution("invalid", component_ids, "plan_occurrence_roster_mismatch")
            actual_scenario_ids = [item.scenario_id for item in basis.outcomes]
            if actual_scenario_ids != basis.expected_scenario_ids[: len(actual_scenario_ids)]:
                return _resolution("invalid", component_ids, "plan_outcome_roster_mismatch")
        else:
            if (
                basis.benchmark_evaluation_ref is None
                or basis.plan_ref is not None
                or basis.suite_id is None
                or basis.suite_version is None
            ):
                return _resolution("invalid", component_ids, "phase_d4_source_refs_invalid")
            try:
                evaluation = BenchmarkEvaluation.model_validate(
                    load_core_json_artifact(store, basis.benchmark_evaluation_ref)
                )
            except Exception:
                return _resolution("invalid", component_ids, "benchmark_evaluation_unreadable")
            executed = [item for item in basis.outcomes if item.status != "skipped"]
            sample_count = evaluation.sample_counts.get(BenchmarkSplit.ROTATING_CHALLENGE.value)
            if (
                evaluation.suite_id != basis.suite_id
                or evaluation.suite_version != basis.suite_version
                or evaluation.resolved_runtime_split_type() is not BenchmarkSplit.ROTATING_CHALLENGE
                or type(sample_count) is not int
                or sample_count != len(executed)
                or not _same_artifact(evaluation.candidate_ref, basis.candidate_ref)
                or evaluation.metadata.get("challenge_case_ids") != basis.expected_scenario_ids
                or [item.scenario_id for item in basis.outcomes] != basis.expected_scenario_ids
            ):
                return _resolution("invalid", component_ids, "phase_d4_evaluation_binding_mismatch")
            if executed:
                fraction = sum(item.status == "passed" for item in executed) / len(executed)
                for metrics in (evaluation.selection_metrics, evaluation.holdout_metrics):
                    reported = metrics.get("challenge_pass_rate")
                    if (
                        type(reported) not in {int, float}
                        or not isfinite(float(reported))
                        or not isclose(float(reported), fraction, rel_tol=0.0, abs_tol=1e-12)
                    ):
                        return _resolution("invalid", component_ids, "phase_d4_rate_mismatch")
            elif basis.expected_count:
                return _resolution("partial", component_ids, "phase_d4_has_no_executed_cases")

        indexes = [item.occurrence_index for item in basis.outcomes]
        if indexes != list(range(len(basis.outcomes))):
            return _resolution("invalid", component_ids, "occurrences_not_ordered")
        if basis.expected_count == 0:
            return _resolution("not_evaluated", component_ids, "zero_expected_denominator")
        if not basis.complete or len(basis.outcomes) != basis.expected_count:
            return _resolution("partial", component_ids, "expected_occurrence_rows_incomplete")
        if any(item.status == "skipped" for item in basis.outcomes):
            return _resolution("partial", component_ids, "skipped_occurrence_present")
        if any(item.status in {"invalid", "unknown"} for item in basis.outcomes):
            return _resolution("invalid", component_ids, "invalid_or_unknown_evaluation_present")
        for outcome in basis.outcomes:
            if outcome.status in {"passed", "failed"} and (
                (outcome.status == "passed") != (len(outcome.vulnerabilities) == 0)
            ):
                return _resolution("invalid", component_ids, "outcome_and_violations_disagree")
        total += len(basis.outcomes)
        passed += sum(item.status == "passed" for item in basis.outcomes)
        violations = [v for item in basis.outcomes for v in item.vulnerabilities]
        critical += sum(item.severity == "critical" for item in violations)
        high += sum(item.severity == "high" for item in violations)
        medium += sum(item.severity == "medium" for item in violations)

    if total == 0:
        return _resolution("not_evaluated", component_ids, "zero_observed_denominator")
    return StressScoreResolution(
        status="available",
        score_profile="finite_binary_scenario_v1",
        robustness_score=passed / total,
        total_scenarios_evaluated=total,
        passed_count=passed,
        critical_count=critical,
        high_count=high,
        medium_count=medium,
        component_ids=component_ids,
        reason_code="source_bound_occurrences_recomputed",
        # Both current source kinds are scored from their persisted outcome rows here.
        # No independent, non-producing source is currently consumed by this resolver.
        predicate_status="recomputed",
    )


class StressTestReport(BaseModel):
    """Summary of vulnerabilities, worst cases, and scenario evidence from adversarial stress testing."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.1"
    report_id: str

    total_scenarios_evaluated: int = 0
    score_profile: (
        Literal["finite_binary_scenario_v1", "continuous_severity_v1", "mixed_unscored"] | None
    ) = None
    score_status: Literal[
        "available",
        "not_evaluated",
        "partial",
        "invalid",
        "legacy_unknown",
        "profile_mismatch",
        "unbound",
    ] = "legacy_unknown"
    score_reason: str | None = None
    score_predicate_status: Literal[
        "recomputed",
        "independently_reconciled",
        "consumer_asserted",
        "institutionally_supplied",
        "not_established",
    ] = "not_established"
    score_components: list[StressScoreComponent] = Field(default_factory=list)
    adversarial_plan_ref: str | None = None
    fidelity_mode: str = "stress_preset"

    worst_case_parameters: dict[str, float] = Field(default_factory=dict)
    worst_case_objective: float | None = None

    vulnerabilities: list[Vulnerability] = Field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0

    robustness_score: float | None = None
    set_adequacy_status: str | None = None
    coverage_empirical: float | None = Field(default=None, ge=0.0, le=1.0)
    coverage_target: float | None = Field(default=None, ge=0.0, le=1.0)
    inflation_mean: float | None = None
    inflation_budget: float | None = Field(default=None, ge=0.0)
    frontier_knee_rho: float | None = Field(default=None, ge=0.0)
    undercoverage_vulnerability: Vulnerability | None = None
    overconservatism_vulnerability: Vulnerability | None = None
    decision_packet_ref: str | None = None
    cas_artifact_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @property
    def is_robust(self) -> bool:
        """Return true only for an available finite-profile score."""
        return (
            self.score_status == "available"
            and self.score_profile == "finite_binary_scenario_v1"
            and self.robustness_score is not None
            and self.critical_count == 0
            and self.high_count == 0
        )


def resolve_stress_report_artifact(
    store,
    report_ref: ArtifactRef,
    *,
    expected_candidate_ref: ArtifactRef | None,
) -> tuple[StressTestReport, StressScoreResolution]:
    """Freshly resolve a report and reject summaries that disagree with CAS rows."""
    from polisyos.core.artifacts import load_core_json_artifact

    try:
        report = StressTestReport.model_validate(load_core_json_artifact(store, report_ref))
    except Exception:
        report = StressTestReport(report_id="unreadable-stress-report", schema_version="1.0")
        return report, _resolution("invalid", [], "stress_report_unreadable")
    if report.schema_version != "1.1":
        return report, _resolution("legacy_unknown", [], "legacy_report_without_occurrence_basis")
    if report.score_profile in {"continuous_severity_v1", "mixed_unscored"}:
        if report.score_components:
            component_resolution = resolve_stress_score_components(
                store,
                report.score_components,
                expected_candidate_ref=expected_candidate_ref,
            )
            if component_resolution.status != "available":
                return report, component_resolution
            reason_code = (
                "mixed_profile_is_not_binary"
                if report.score_profile == "mixed_unscored"
                else "continuous_profile_is_not_binary"
            )
            return report, component_resolution.model_copy(
                update={
                    "status": "profile_mismatch",
                    "score_profile": None,
                    "robustness_score": None,
                    "reason_code": reason_code,
                }
            )
        reason_code = (
            "mixed_profile_is_not_binary"
            if report.score_profile == "mixed_unscored"
            else "continuous_profile_is_not_binary"
        )
        return report, _resolution("profile_mismatch", [], reason_code)
    if not report.score_components:
        if report.score_status == "not_evaluated" and report.robustness_score is None:
            return report, _resolution("not_evaluated", [], "no_finite_occurrence_basis")
        if report.score_status == "available" or report.robustness_score is not None:
            return report, _resolution("invalid", [], "score_claim_without_finite_basis")
        return report, _resolution("legacy_unknown", [], "finite_basis_not_established")
    resolution = resolve_stress_score_components(
        store, report.score_components, expected_candidate_ref=expected_candidate_ref
    )
    if resolution.status != "available":
        if report.score_status == "available" or report.robustness_score is not None:
            resolution = resolution.model_copy(
                update={
                    "status": "invalid",
                    "robustness_score": None,
                    "reason_code": "score_claim_without_resolved_basis",
                }
            )
        return report, resolution
    matches = (
        report.score_profile == resolution.score_profile
        and report.total_scenarios_evaluated == resolution.total_scenarios_evaluated
        and report.critical_count == resolution.critical_count
        and report.high_count == resolution.high_count
        and report.medium_count == resolution.medium_count
        and report.score_predicate_status == resolution.predicate_status
        and report.score_status == "available"
        and report.robustness_score is not None
        and isclose(
            float(report.robustness_score),
            float(resolution.robustness_score),
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    )
    if not matches:
        resolution = resolution.model_copy(
            update={
                "status": "invalid",
                "robustness_score": None,
                "reason_code": "report_summary_reconciliation_failed",
            }
        )
    return report, resolution
