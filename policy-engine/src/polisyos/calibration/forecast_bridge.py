"""Produce neutral empirical evidence from a persisted backtest report.

This module is the producer half of the FRC-02 slice.  It reads the existing
IR ``BacktestReport`` artifact, derives interval hits from observed outcomes
and persisted bounds, and reconciles those observations with the report's
stored projections.  It deliberately does not know about S10, G2, W12D, or
runtime status lattices; a later runtime adapter owns that consumer boundary.

A nominal confidence level and a self-described lineage are not observations.
The producer therefore remains non-usable until a caller supplies the full
typed semantic binding and the stored interval evidence reconciles with the
underlying ``y_true`` values.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from typing import Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from polisyos.ir.analytics.backtest import BacktestReport, load_backtest_report
from polisyos.ir.artifacts import ArtifactStore
from polisyos.ir.registry.refs import BacktestReportRef

EmpiricalEvidenceKind = Literal["observed_interval_comparisons", "unavailable"]

_FORBIDDEN_PROVENANCE_MARKERS = (
    "synthetic",
    "fixture",
    "self-attest",
    "self_attest",
    "self attest",
    "self-certified",
    "self_certified",
)

_OBSERVATION_BLOCKERS = frozenset(
    {
        "interval_bounds_missing",
        "interval_bounds_partial",
        "within_ci_missing",
        "within_ci_mismatch",
        "persisted_interval_requested_mismatch",
        "persisted_interval_available_mismatch",
        "persisted_interval_availability_mismatch",
        "persisted_denominator_mismatch",
        "persisted_numerator_mismatch",
        "persisted_pass_rate_mismatch",
        "persisted_overall_coverage_mismatch",
        "persisted_metadata_numerator_mismatch",
        "persisted_metadata_denominator_mismatch",
        "persisted_metadata_counter_invalid",
        "zero_observation_denominator",
        "nominal_confidence_only",
    }
)

_IDENTITY_BINDING_ISSUES = frozenset(
    {
        "incomplete_model_policy_pair",
        "model_policy_binding_mismatch",
        "degraded_model_policy_provenance",
        "mixed_model_spec_refs",
        "mixed_policy_spec_refs",
        "model_spec_ref_mismatch",
        "policy_spec_ref_mismatch",
        "method_ref_mismatch",
        "method_version_mismatch",
        "rule_version_ref_mismatch",
        "estimand_mismatch",
    }
)


class EmpiricalCalibrationContext(BaseModel):
    """Caller-supplied semantic, provenance, and time binding for evidence.

    A generic backtest report cannot establish the estimand, method version, or
    temporal meaning of its rows.  Those fields are consequently required from
    the typed caller instead of being inferred from report metadata.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_spec_ref: str = Field(min_length=1, max_length=300)
    policy_spec_ref: str = Field(min_length=1, max_length=300)
    estimand: str = Field(min_length=1, max_length=240)
    method_ref: str = Field(min_length=1, max_length=300)
    method_version: str = Field(min_length=1, max_length=120)
    rule_version_ref: str = Field(min_length=1, max_length=300)
    calibration_threshold: float = Field(gt=0.0, le=1.0)
    calibration_threshold_ref: str = Field(min_length=1, max_length=300)

    observed_outcome_ref: str = Field(min_length=1, max_length=300)
    prediction_ref: str = Field(min_length=1, max_length=300)
    evaluation_design_ref: str = Field(min_length=1, max_length=300)
    credible_evaluation_evidence_ref: str = Field(min_length=1, max_length=300)
    source_lineage_refs: tuple[str, ...] = Field(min_length=1, max_length=80)
    method_lineage_refs: tuple[str, ...] = Field(min_length=1, max_length=80)
    evidence_origin: str = Field(default="persisted_backtest", min_length=1, max_length=120)

    prediction_time: AwareDatetime
    observation_time: AwareDatetime
    policy_effective_time: AwareDatetime
    data_valid_time: AwareDatetime
    calibration_window_start: AwareDatetime
    calibration_window_end: AwareDatetime

    @field_validator(
        "model_spec_ref",
        "policy_spec_ref",
        "estimand",
        "method_ref",
        "method_version",
        "rule_version_ref",
        "calibration_threshold_ref",
        "observed_outcome_ref",
        "prediction_ref",
        "evaluation_design_ref",
        "credible_evaluation_evidence_ref",
        "evidence_origin",
        mode="before",
    )
    @classmethod
    def _strip_required_text(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("empirical calibration context text fields must be non-empty strings")
        return value.strip()

    @field_validator("source_lineage_refs", "method_lineage_refs", mode="before")
    @classmethod
    def _normalize_refs(cls, value: object) -> tuple[str, ...]:
        if isinstance(value, str):
            values: Sequence[object] = (value,)
        elif isinstance(value, Sequence):
            values = value
        else:
            raise ValueError("empirical calibration lineage refs must be a sequence of strings")
        normalized = tuple(str(item).strip() for item in values)
        if any(not item for item in normalized):
            raise ValueError("empirical calibration lineage refs must not contain empty strings")
        return normalized

    @model_validator(mode="after")
    def _validate_binding(self) -> EmpiricalCalibrationContext:
        temporal_roles = (
            self.prediction_time,
            self.observation_time,
            self.policy_effective_time,
            self.data_valid_time,
            self.calibration_window_start,
            self.calibration_window_end,
        )
        if len(set(temporal_roles)) != len(temporal_roles):
            raise ValueError("all six empirical calibration temporal roles must be distinct")
        if self.calibration_window_end < self.calibration_window_start:
            raise ValueError("calibration window end cannot precede its start")
        if set(self.source_lineage_refs) & set(self.method_lineage_refs):
            raise ValueError("source and method lineage refs must be independently bound")

        provenance_values = (
            self.evidence_origin,
            self.observed_outcome_ref,
            self.prediction_ref,
            self.evaluation_design_ref,
            self.credible_evaluation_evidence_ref,
            *self.source_lineage_refs,
            *self.method_lineage_refs,
        )
        if any(_contains_forbidden_marker(value) for value in provenance_values):
            raise ValueError("synthetic or self-attested provenance is not admissible")
        return self


class EmpiricalCalibrationEvidence(BaseModel):
    """Persistable neutral evidence produced from observed interval rows.

    ``usable_for_calibration`` is an evidence property, not a runtime status.
    It is intentionally insufficient to route a recommendation or claim; the
    downstream runtime adapter must bind this artifact to its own consumer
    contract.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    evidence_ref: str = Field(min_length=1, max_length=300)
    report_id: str = Field(min_length=1)
    report_ref: BacktestReportRef

    model_spec_ref: str | None = None
    policy_spec_ref: str | None = None
    estimand: str | None = None
    method_ref: str | None = None
    method_version: str | None = None
    rule_version_ref: str | None = None
    calibration_threshold: float | None = Field(default=None, gt=0.0, le=1.0)
    calibration_threshold_ref: str | None = None
    observed_outcome_ref: str | None = None
    prediction_ref: str | None = None
    evaluation_design_ref: str | None = None
    credible_evaluation_evidence_ref: str | None = None
    source_lineage_refs: tuple[str, ...] = ()
    method_lineage_refs: tuple[str, ...] = ()

    prediction_time: AwareDatetime | None = None
    observation_time: AwareDatetime | None = None
    policy_effective_time: AwareDatetime | None = None
    data_valid_time: AwareDatetime | None = None
    calibration_window_start: AwareDatetime | None = None
    calibration_window_end: AwareDatetime | None = None

    evidence_kind: EmpiricalEvidenceKind
    empirical_observations_available: bool
    context_bound: bool
    usable_for_calibration: bool
    floor_passed: bool

    recomputed_numerator: int = Field(ge=0)
    recomputed_denominator: int = Field(ge=0)
    recomputed_pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    within_ci_numerator: int = Field(ge=0)
    within_ci_denominator: int = Field(ge=0)
    persisted_numerator: int = Field(ge=0)
    persisted_denominator: int = Field(ge=0)
    failure_codes: tuple[str, ...] = ()


def produce_empirical_calibration_evidence(
    store: ArtifactStore,
    report_ref: BacktestReportRef,
    *,
    context: EmpiricalCalibrationContext | None = None,
) -> EmpiricalCalibrationEvidence:
    """Read a persisted report and produce neutral, reconciled evidence.

    The report is loaded through the existing IR persistence boundary.  All
    interval hits are recomputed from ``y_true`` and complete lower/upper
    bounds.  ``within_ci`` and stored scenario/metadata counters are checked
    as projections, never used as a substitute for observations.
    """

    report = load_backtest_report(store, report_ref)
    (
        recomputed_numerator,
        recomputed_denominator,
        within_ci_numerator,
        within_ci_denominator,
        persisted_numerator,
        persisted_denominator,
        observation_issues,
    ) = _recompute_and_reconcile(report)

    issues = list(observation_issues)
    if context is None:
        issues.append("explicit_context_missing")
        binding_issues: tuple[str, ...] = ()
    else:
        binding_issues = _binding_issues(report, context)
        issues.extend(binding_issues)

    pass_rate = (
        recomputed_numerator / recomputed_denominator
        if recomputed_denominator
        else None
    )
    if context is not None and pass_rate is not None and pass_rate < context.calibration_threshold:
        issues.append("calibration_floor_not_met")

    failure_codes = _dedupe(issues)
    context_bound = context is not None and not any(
        issue in _IDENTITY_BINDING_ISSUES for issue in binding_issues
    )
    empirical_observations_available = (
        recomputed_denominator > 0
        and not any(issue in _OBSERVATION_BLOCKERS for issue in failure_codes)
    )
    floor_passed = bool(
        context_bound
        and empirical_observations_available
        and pass_rate is not None
        and context is not None
        and pass_rate >= context.calibration_threshold
    )
    usable_for_calibration = floor_passed and not failure_codes

    return EmpiricalCalibrationEvidence(
        evidence_ref=_evidence_ref(report_ref, report.report_id),
        report_id=report.report_id,
        report_ref=report_ref,
        model_spec_ref=report.model_spec_ref,
        policy_spec_ref=report.policy_spec_ref,
        estimand=context.estimand if context else None,
        method_ref=context.method_ref if context else None,
        method_version=context.method_version if context else None,
        rule_version_ref=context.rule_version_ref if context else None,
        calibration_threshold=context.calibration_threshold if context else None,
        calibration_threshold_ref=context.calibration_threshold_ref if context else None,
        observed_outcome_ref=context.observed_outcome_ref if context else None,
        prediction_ref=context.prediction_ref if context else None,
        evaluation_design_ref=context.evaluation_design_ref if context else None,
        credible_evaluation_evidence_ref=(
            context.credible_evaluation_evidence_ref if context else None
        ),
        source_lineage_refs=context.source_lineage_refs if context else (),
        method_lineage_refs=context.method_lineage_refs if context else (),
        prediction_time=context.prediction_time if context else None,
        observation_time=context.observation_time if context else None,
        policy_effective_time=context.policy_effective_time if context else None,
        data_valid_time=context.data_valid_time if context else None,
        calibration_window_start=context.calibration_window_start if context else None,
        calibration_window_end=context.calibration_window_end if context else None,
        evidence_kind=(
            "observed_interval_comparisons"
            if recomputed_denominator
            else "unavailable"
        ),
        empirical_observations_available=empirical_observations_available,
        context_bound=context_bound,
        usable_for_calibration=usable_for_calibration,
        floor_passed=floor_passed,
        recomputed_numerator=recomputed_numerator,
        recomputed_denominator=recomputed_denominator,
        recomputed_pass_rate=pass_rate,
        within_ci_numerator=within_ci_numerator,
        within_ci_denominator=within_ci_denominator,
        persisted_numerator=persisted_numerator,
        persisted_denominator=persisted_denominator,
        failure_codes=failure_codes,
    )


def _recompute_and_reconcile(
    report: BacktestReport,
) -> tuple[int, int, int, int, int, int, tuple[str, ...]]:
    """Recompute interval hits and reconcile all persisted projections."""

    recomputed_numerator = 0
    recomputed_denominator = 0
    within_ci_numerator = 0
    within_ci_denominator = 0
    persisted_numerator = 0
    persisted_denominator = 0
    issues: list[str] = []

    for scenario in report.scenarios:
        scenario_recomputed_numerator = 0
        scenario_recomputed_denominator = 0
        complete_bounds_count = 0

        for comparison in scenario.outcome_comparisons:
            if comparison.within_ci is True:
                within_ci_numerator += 1
            if comparison.within_ci is not None:
                within_ci_denominator += 1

            has_lower = comparison.ci_lower is not None
            has_upper = comparison.ci_upper is not None
            if has_lower and has_upper:
                complete_bounds_count += 1
                actual_hit = comparison.ci_lower <= comparison.y_true <= comparison.ci_upper
                scenario_recomputed_denominator += 1
                recomputed_denominator += 1
                if actual_hit:
                    scenario_recomputed_numerator += 1
                    recomputed_numerator += 1
                if comparison.within_ci is None:
                    issues.append("within_ci_missing")
                elif comparison.within_ci is not actual_hit:
                    issues.append("within_ci_mismatch")
            elif has_lower or has_upper:
                issues.append("interval_bounds_partial")
                if comparison.within_ci is not None:
                    issues.append("interval_bounds_missing")
            elif comparison.within_ci is not None:
                issues.append("interval_bounds_missing")

        persisted_numerator += scenario.interval_hit_count
        persisted_denominator += scenario.interval_evaluated_count
        if scenario.interval_requested_count != len(scenario.outcome_comparisons):
            issues.append("persisted_interval_requested_mismatch")
        if scenario.interval_available_count != complete_bounds_count:
            issues.append("persisted_interval_available_mismatch")
        if scenario.interval_availability is not None:
            expected_availability = (
                complete_bounds_count / scenario.interval_requested_count
                if scenario.interval_requested_count
                else 0.0
            )
            if not math.isclose(
                scenario.interval_availability,
                expected_availability,
                rel_tol=0.0,
                abs_tol=1e-9,
            ):
                issues.append("persisted_interval_availability_mismatch")
        if scenario.interval_evaluated_count != scenario_recomputed_denominator:
            issues.append("persisted_denominator_mismatch")
        if scenario.interval_hit_count != scenario_recomputed_numerator:
            issues.append("persisted_numerator_mismatch")
        if scenario.interval_hit_rate is not None:
            expected_rate = (
                scenario_recomputed_numerator / scenario_recomputed_denominator
                if scenario_recomputed_denominator
                else None
            )
            if expected_rate is None or not math.isclose(
                scenario.interval_hit_rate, expected_rate, rel_tol=0.0, abs_tol=1e-9
            ):
                issues.append("persisted_pass_rate_mismatch")

    if report.overall_coverage_probability is not None:
        expected_overall = (
            recomputed_numerator / recomputed_denominator
            if recomputed_denominator
            else None
        )
        if expected_overall is None or not math.isclose(
            report.overall_coverage_probability,
            expected_overall,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            issues.append("persisted_overall_coverage_mismatch")

    for numerator_key, denominator_key in (
        ("calibration_numerator", "calibration_denominator"),
        ("interval_hit_count", "interval_evaluated_count"),
    ):
        if numerator_key in report.metadata:
            raw_numerator = _coerce_int(report.metadata[numerator_key])
            if raw_numerator is None:
                issues.append("persisted_metadata_counter_invalid")
            elif raw_numerator != recomputed_numerator:
                issues.append("persisted_metadata_numerator_mismatch")
        if denominator_key in report.metadata:
            raw_denominator = _coerce_int(report.metadata[denominator_key])
            if raw_denominator is None:
                issues.append("persisted_metadata_counter_invalid")
            elif raw_denominator != recomputed_denominator:
                issues.append("persisted_metadata_denominator_mismatch")

    if recomputed_denominator == 0:
        issues.append("zero_observation_denominator")
        if any(scenario.nominal_confidence_level is not None for scenario in report.scenarios):
            issues.append("nominal_confidence_only")

    return (
        recomputed_numerator,
        recomputed_denominator,
        within_ci_numerator,
        within_ci_denominator,
        persisted_numerator,
        persisted_denominator,
        _dedupe(issues),
    )


def _binding_issues(
    report: BacktestReport,
    context: EmpiricalCalibrationContext,
) -> tuple[str, ...]:
    """Check report identity against the caller-supplied context."""

    issues: list[str] = []
    if not report.model_spec_ref or not report.policy_spec_ref:
        issues.append("incomplete_model_policy_pair")
    elif (
        report.model_spec_ref != context.model_spec_ref
        or report.policy_spec_ref != context.policy_spec_ref
    ):
        issues.append("model_policy_binding_mismatch")
    if report.degraded and any(
        "model_spec_ref" in reason or "policy_spec_ref" in reason
        for reason in report.degraded_reasons
    ):
        issues.append("degraded_model_policy_provenance")

    metadata = report.metadata
    for field_name, expected in (
        ("model_spec_ref", context.model_spec_ref),
        ("policy_spec_ref", context.policy_spec_ref),
        ("method_ref", context.method_ref),
        ("method_version", context.method_version),
        ("rule_version_ref", context.rule_version_ref),
        ("estimand", context.estimand),
    ):
        raw = metadata.get(field_name)
        if raw is not None and str(raw).strip() != expected:
            issues.append(f"{field_name}_mismatch")

    for field_name, expected in (
        ("model_spec_refs", context.model_spec_ref),
        ("policy_spec_refs", context.policy_spec_ref),
    ):
        raw = metadata.get(field_name)
        if raw is None:
            continue
        values = _as_text_sequence(raw)
        if len(values) != 1 or values[0] != expected:
            issues.append(f"mixed_{field_name}")
    return _dedupe(issues)


def _evidence_ref(report_ref: BacktestReportRef, report_id: str) -> str:
    token = hashlib.sha256(
        f"{report_ref.artifact_id}::{report_id}".encode("utf-8")
    ).hexdigest()[:24]
    return f"empirical-calibration://{token}"


def _as_text_sequence(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value.strip(),)
    if isinstance(value, Sequence):
        return tuple(str(item).strip() for item in value)
    return (str(value).strip(),)


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        coerced = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return coerced if coerced >= 0 else None


def _contains_forbidden_marker(value: object) -> bool:
    text = str(value).casefold()
    return any(marker in text for marker in _FORBIDDEN_PROVENANCE_MARKERS)


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values))


__all__ = [
    "EmpiricalCalibrationContext",
    "EmpiricalCalibrationEvidence",
    "EmpiricalEvidenceKind",
    "produce_empirical_calibration_evidence",
]
