"""Produce neutral empirical evidence from a persisted backtest report.

This module is the producer half of the FRC-02 slice.  It admits a
content-bound IR ``BacktestReport``, derives interval hits from observed
outcomes and persisted bounds, reconciles every stored projection, and emits
neutral evidence.  It deliberately does not know about runtime status
lattices or S10/G2/W12D consumers; a later runtime adapter owns that boundary.

All evidence references are resolved through the same CAS and checked against
their manifest, bytes, schema, and declared identity.  A nominal confidence
level or a self-described lineage cannot substitute for those observations.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
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
from polisyos.ir.artifacts import (
    ArtifactID,
    ArtifactStore,
    get_json_artifact,
    put_json_artifact,
)
from polisyos.ir.registry.refs import ArtifactRefModel, BacktestReportRef

EmpiricalEvidenceKind = Literal["observed_interval_comparisons", "unavailable"]

REPORT_KIND = "ir.backtest_report"
REPORT_SCHEMA_NAME = "ir.backtest_report"
REPORT_SCHEMA_VERSION = "1.0"
EVIDENCE_KIND = "ir.empirical_calibration_evidence"
EVIDENCE_SCHEMA_NAME = "polisyos.calibration.empirical_calibration_evidence"
EVIDENCE_SCHEMA_VERSION = "1.0"

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
        "persisted_projection_incomplete",
        "persisted_metadata_counter_incomplete",
        "persisted_metadata_numerator_mismatch",
        "persisted_metadata_denominator_mismatch",
        "persisted_metadata_counter_invalid",
        "zero_observation_denominator",
        "nominal_confidence_only",
    }
)

class EvidenceArtifactRef(BaseModel):
    """Typed CAS reference with the contract needed to verify provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: ArtifactID
    kind: str = Field(min_length=1, max_length=300)
    media_type: Literal["application/json"] = "application/json"
    schema_name: str = Field(min_length=1, max_length=300)
    schema_version: str = Field(min_length=1, max_length=120)
    identity_path: str = Field(min_length=1, max_length=300)
    identity_value: str = Field(min_length=1, max_length=500)

    @field_validator(
        "kind",
        "schema_name",
        "schema_version",
        "identity_path",
        "identity_value",
        mode="before",
    )
    @classmethod
    def _strip_text(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("evidence artifact reference text must be non-empty")
        return value.strip()


class EmpiricalCalibrationEvidenceRef(ArtifactRefModel):
    """Typed CAS reference for a persisted neutral empirical evidence artifact."""

    kind: Literal[EVIDENCE_KIND] = EVIDENCE_KIND
    media_type: Literal["application/json"] = "application/json"


class EmpiricalCalibrationContext(BaseModel):
    """Caller-supplied semantic, provenance, and time binding for evidence.

    A generic backtest report cannot establish the estimand, method version, or
    temporal meaning of its rows.  Those fields are required from the typed
    caller.  Every provenance field is also a typed CAS reference whose
    manifest and payload identity are checked against the same store.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_spec_ref: str = Field(min_length=1, max_length=300)
    policy_spec_ref: str = Field(min_length=1, max_length=300)
    estimand: str = Field(min_length=1, max_length=240)
    method_ref: str = Field(min_length=1, max_length=300)
    method_version: str = Field(min_length=1, max_length=120)
    rule_version_ref: str = Field(min_length=1, max_length=300)
    calibration_threshold: float = Field(gt=0.0, le=1.0)
    calibration_threshold_ref: EvidenceArtifactRef

    observed_outcome_ref: EvidenceArtifactRef
    prediction_ref: EvidenceArtifactRef
    evaluation_design_ref: EvidenceArtifactRef
    credible_evaluation_evidence_ref: EvidenceArtifactRef
    source_lineage_refs: tuple[EvidenceArtifactRef, ...] = Field(min_length=1, max_length=80)
    method_lineage_refs: tuple[EvidenceArtifactRef, ...] = Field(min_length=1, max_length=80)
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
        "evidence_origin",
        mode="before",
    )
    @classmethod
    def _strip_required_text(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("empirical calibration context text fields must be non-empty strings")
        return value.strip()

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

        source_ids = {str(ref.artifact_id) for ref in self.source_lineage_refs}
        method_ids = {str(ref.artifact_id) for ref in self.method_lineage_refs}
        if source_ids & method_ids:
            raise ValueError("source and method lineage refs must be independently bound")
        return self


class EmpiricalCalibrationEvidence(BaseModel):
    """Neutral, typed evidence produced from observed interval rows.

    The artifact has no runtime status or recommendation authority.  Its
    separate ``EmpiricalCalibrationEvidenceRef`` is the durable identity after
    persistence; no derived URI pretends to be an artifact reference.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    report_id: str = Field(min_length=1)
    report_ref: BacktestReportRef

    model_spec_ref: str | None = None
    policy_spec_ref: str | None = None
    estimand: str | None = None
    method_ref: str | None = None
    method_version: str | None = None
    rule_version_ref: str | None = None
    calibration_threshold: float | None = Field(default=None, gt=0.0, le=1.0)
    calibration_threshold_ref: EvidenceArtifactRef | None = None
    observed_outcome_ref: EvidenceArtifactRef | None = None
    prediction_ref: EvidenceArtifactRef | None = None
    evaluation_design_ref: EvidenceArtifactRef | None = None
    credible_evaluation_evidence_ref: EvidenceArtifactRef | None = None
    source_lineage_refs: tuple[EvidenceArtifactRef, ...] = ()
    method_lineage_refs: tuple[EvidenceArtifactRef, ...] = ()

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
    """Read a verified report and produce neutral, reconciled evidence."""

    validated_report_ref, report = _load_verified_report(store, report_ref)
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
    binding_issues: tuple[str, ...] = ()
    provenance_issues: tuple[str, ...] = ()
    if context is None:
        issues.append("explicit_context_missing")
    else:
        binding_issues = _binding_issues(report, context)
        provenance_issues = _context_reference_issues(store, context)
        issues.extend(binding_issues)
        issues.extend(provenance_issues)

    pass_rate = (
        recomputed_numerator / recomputed_denominator
        if recomputed_denominator
        else None
    )
    if context is not None and pass_rate is not None and pass_rate < context.calibration_threshold:
        issues.append("calibration_floor_not_met")

    failure_codes = _dedupe(issues)
    context_bound = context is not None and not binding_issues and not provenance_issues
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
        report_id=report.report_id,
        report_ref=validated_report_ref,
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


def persist_empirical_calibration_evidence(
    store: ArtifactStore,
    evidence: EmpiricalCalibrationEvidence,
) -> EmpiricalCalibrationEvidenceRef:
    """Persist neutral evidence and return its typed CAS reference."""

    _validate_json_artifact(
        store,
        evidence.report_ref,
        expected_kind=REPORT_KIND,
        expected_media_type="application/json",
        expected_schema_name=REPORT_SCHEMA_NAME,
        expected_schema_version=REPORT_SCHEMA_VERSION,
    )
    inputs: list[dict[str, object]] = [
        {"artifact_id": str(evidence.report_ref.artifact_id), "role": "backtest_report"}
    ]
    for role, ref in _context_refs(evidence):
        _validate_json_artifact(
            store,
            ref,
            expected_kind=ref.kind,
            expected_media_type=ref.media_type,
            expected_schema_name=ref.schema_name,
            expected_schema_version=ref.schema_version,
        )
        inputs.append({"artifact_id": str(ref.artifact_id), "role": role})

    payload = put_json_artifact(
        store,
        evidence.model_dump(mode="json"),
        kind=EVIDENCE_KIND,
        schema_name=EVIDENCE_SCHEMA_NAME,
        schema_version=EVIDENCE_SCHEMA_VERSION,
        inputs=inputs,
    )
    return EmpiricalCalibrationEvidenceRef.model_validate(payload)


def load_empirical_calibration_evidence(
    store: ArtifactStore,
    evidence_ref: EmpiricalCalibrationEvidenceRef,
) -> EmpiricalCalibrationEvidence:
    """Validate a typed evidence artifact's manifest and read its payload."""

    validated_ref = EmpiricalCalibrationEvidenceRef.model_validate(evidence_ref)
    _validate_json_artifact(
        store,
        validated_ref,
        expected_kind=EVIDENCE_KIND,
        expected_media_type="application/json",
        expected_schema_name=EVIDENCE_SCHEMA_NAME,
        expected_schema_version=EVIDENCE_SCHEMA_VERSION,
    )
    evidence = EmpiricalCalibrationEvidence.model_validate(
        get_json_artifact(store, validated_ref.artifact_id)
    )
    _validate_json_artifact(
        store,
        evidence.report_ref,
        expected_kind=REPORT_KIND,
        expected_media_type="application/json",
        expected_schema_name=REPORT_SCHEMA_NAME,
        expected_schema_version=REPORT_SCHEMA_VERSION,
    )
    return evidence


def _load_verified_report(
    store: ArtifactStore,
    report_ref: BacktestReportRef,
) -> tuple[BacktestReportRef, BacktestReport]:
    """Validate report ref and CAS profile before invoking the report loader."""

    validated_ref = BacktestReportRef.model_validate(report_ref)
    _validate_json_artifact(
        store,
        validated_ref,
        expected_kind=REPORT_KIND,
        expected_media_type="application/json",
        expected_schema_name=REPORT_SCHEMA_NAME,
        expected_schema_version=REPORT_SCHEMA_VERSION,
    )
    return validated_ref, load_backtest_report(store, validated_ref)


def _validate_json_artifact(
    store: ArtifactStore,
    ref: ArtifactRefModel | EvidenceArtifactRef,
    *,
    expected_kind: str,
    expected_media_type: str,
    expected_schema_name: str,
    expected_schema_version: str,
) -> bytes:
    """Validate manifest profile, byte digest, and artifact identity."""

    if ref.kind != expected_kind or ref.media_type != expected_media_type:
        raise ValueError("artifact reference kind/media type binding mismatch")
    manifest = store.get_manifest(ref.artifact_id)
    manifest_payload = _as_mapping(manifest)
    if str(_field(manifest_payload, "artifact_id")) != str(ref.artifact_id):
        raise ValueError("artifact manifest identity does not match reference")
    if _field(manifest_payload, "kind") != expected_kind:
        raise ValueError("artifact manifest kind mismatch")
    if _field(manifest_payload, "media_type") != expected_media_type:
        raise ValueError("artifact manifest media type mismatch")

    schema = _field(manifest_payload, "schema")
    if schema is None:
        schema = _field(manifest_payload, "artifact_schema")
    schema_payload = _as_mapping(schema)
    if (
        _field(schema_payload, "name") != expected_schema_name
        or _field(schema_payload, "version") != expected_schema_version
    ):
        raise ValueError("artifact manifest schema binding mismatch")

    data = store.get_bytes(ref.artifact_id)
    actual_sha = hashlib.sha256(data).hexdigest()
    expected_sha = str(ref.artifact_id).split(":", 1)[1]
    integrity = _as_mapping(_field(manifest_payload, "integrity"))
    if actual_sha != expected_sha or _field(integrity, "sha256") != actual_sha:
        raise ValueError("artifact content binding mismatch")
    byte_size = _field(manifest_payload, "byte_size")
    if byte_size is not None and int(byte_size) != len(data):
        raise ValueError("artifact manifest byte size mismatch")
    return data


def _context_reference_issues(
    store: ArtifactStore,
    context: EmpiricalCalibrationContext,
) -> tuple[str, ...]:
    """Resolve every required context reference through the CAS."""

    issues: list[str] = []
    for field_name, ref in _context_refs(context):
        try:
            payload = _validate_and_load_reference(store, ref)
        except (FileNotFoundError, OSError, TypeError, ValueError):
            issues.extend(
                ("provenance_ref_unresolved", f"provenance_ref_invalid:{field_name}")
            )
            continue
        actual = _lookup_identity(payload, ref.identity_path)
        if actual is _MISSING or str(actual) != ref.identity_value:
            issues.extend(
                (
                    "provenance_ref_identity_mismatch",
                    f"provenance_ref_invalid:{field_name}",
                )
            )
        if _payload_contains_forbidden_marker(payload):
            issues.append("forbidden_provenance_marker")
    return _dedupe(issues)


def _validate_and_load_reference(
    store: ArtifactStore,
    ref: EvidenceArtifactRef,
) -> object:
    """Verify one typed context reference and decode its canonical JSON."""

    _validate_json_artifact(
        store,
        ref,
        expected_kind=ref.kind,
        expected_media_type=ref.media_type,
        expected_schema_name=ref.schema_name,
        expected_schema_version=ref.schema_version,
    )
    return get_json_artifact(store, ref.artifact_id)


def _recompute_and_reconcile(
    report: BacktestReport,
) -> tuple[int, int, int, int, int, int, tuple[str, ...]]:
    """Recompute interval hits and reconcile every persisted projection."""

    recomputed_numerator = 0
    recomputed_denominator = 0
    within_ci_numerator = 0
    within_ci_denominator = 0
    persisted_numerator = 0
    persisted_denominator = 0
    issues: list[str] = []

    required_scenario_fields = (
        "interval_requested_count",
        "interval_available_count",
        "interval_evaluated_count",
        "interval_hit_count",
        "interval_availability",
        "interval_hit_rate",
    )

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

        if scenario_recomputed_denominator > 0:
            if any(field not in scenario.model_fields_set for field in required_scenario_fields):
                issues.append("persisted_projection_incomplete")
            if scenario.interval_availability is None or scenario.interval_hit_rate is None:
                issues.append("persisted_projection_incomplete")

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
            if scenario.interval_availability != expected_availability:
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
            if expected_rate is None or scenario.interval_hit_rate != expected_rate:
                issues.append("persisted_pass_rate_mismatch")

    if recomputed_denominator > 0:
        if "overall_coverage_probability" not in report.model_fields_set:
            issues.append("persisted_projection_incomplete")
        if report.overall_coverage_probability is None:
            issues.append("persisted_projection_incomplete")
    if report.overall_coverage_probability is not None:
        expected_overall = (
            recomputed_numerator / recomputed_denominator
            if recomputed_denominator
            else None
        )
        if expected_overall is None or report.overall_coverage_probability != expected_overall:
            issues.append("persisted_overall_coverage_mismatch")

    for numerator_key, denominator_key in (
        ("calibration_numerator", "calibration_denominator"),
        ("interval_hit_count", "interval_evaluated_count"),
    ):
        numerator_present = numerator_key in report.metadata
        denominator_present = denominator_key in report.metadata
        if numerator_present != denominator_present:
            issues.append("persisted_metadata_counter_incomplete")
        if numerator_present:
            raw_numerator = _coerce_int(report.metadata[numerator_key])
            raw_denominator = _coerce_int(report.metadata[denominator_key])
            if raw_numerator is None or raw_denominator is None:
                issues.append("persisted_metadata_counter_invalid")
            else:
                if raw_numerator != recomputed_numerator:
                    issues.append("persisted_metadata_numerator_mismatch")
                if raw_denominator != recomputed_denominator:
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
    """Check report identity and complete scope against the caller context."""

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
    required_report_fields = (
        ("method_ref", context.method_ref, "report_method_ref_missing"),
        ("method_version", context.method_version, "report_method_version_missing"),
        ("rule_version_ref", context.rule_version_ref, "report_rule_version_ref_missing"),
        ("estimand", context.estimand, "report_estimand_missing"),
    )
    for field_name, expected, missing_code in required_report_fields:
        raw = metadata.get(field_name)
        if not isinstance(raw, str) or not raw.strip():
            issues.append(missing_code)
        elif raw.strip() != expected:
            issues.append(f"{field_name}_mismatch")

    direct_expected = (
        ("model_spec_ref", context.model_spec_ref),
        ("policy_spec_ref", context.policy_spec_ref),
    )
    for field_name, expected in direct_expected:
        raw = metadata.get(field_name)
        if raw is not None and (not isinstance(raw, str) or raw.strip() != expected):
            issues.append(f"{field_name}_mismatch")

    scope_values = _collect_scope_values(metadata)
    for scenario in report.scenarios:
        nested_values = _collect_scope_values(scenario.metadata)
        for field_name, values in nested_values.items():
            scope_values[field_name].extend(values)
    scope_values["model_spec_ref"].append(report.model_spec_ref or "")
    scope_values["policy_spec_ref"].append(report.policy_spec_ref or "")
    expected_values = {
        "model_spec_ref": context.model_spec_ref,
        "policy_spec_ref": context.policy_spec_ref,
        "method_ref": context.method_ref,
        "method_version": context.method_version,
        "rule_version_ref": context.rule_version_ref,
        "estimand": context.estimand,
    }
    for field_name, expected in expected_values.items():
        values = tuple(value for value in scope_values[field_name] if value)
        if not values or any(value != expected for value in values) or len(set(values)) != 1:
            issues.append(f"mixed_{field_name}_scope")

    # Preserve the more specific historical names for top-level plural refs.
    for field_name in ("model_spec_refs", "policy_spec_refs"):
        raw = metadata.get(field_name)
        if raw is not None:
            values = _as_text_sequence(raw)
            expected = expected_values[field_name.removesuffix("s")]
            if len(values) != 1 or values[0] != expected:
                issues.append(f"mixed_{field_name}")
    return _dedupe(issues)


def _context_refs(
    value: EmpiricalCalibrationContext | EmpiricalCalibrationEvidence,
) -> tuple[tuple[str, EvidenceArtifactRef], ...]:
    """Return every required context reference with its stable input role."""

    refs: list[tuple[str, EvidenceArtifactRef]] = []
    for field_name in (
        "calibration_threshold_ref",
        "observed_outcome_ref",
        "prediction_ref",
        "evaluation_design_ref",
        "credible_evaluation_evidence_ref",
    ):
        ref = getattr(value, field_name, None)
        if ref is not None:
            refs.append((field_name, ref))
    refs.extend(("source_lineage", ref) for ref in value.source_lineage_refs)
    refs.extend(("method_lineage", ref) for ref in value.method_lineage_refs)
    return tuple(refs)


def _collect_scope_values(value: object) -> dict[str, list[str]]:
    """Collect all scoped identity values from nested report metadata."""

    keys = (
        "model_spec_ref",
        "policy_spec_ref",
        "method_ref",
        "method_version",
        "rule_version_ref",
        "estimand",
    )
    collected = {key: [] for key in keys}
    plural = {f"{key}s": key for key in keys}

    def visit(node: object) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                target = str(key)
                if target in collected or target in plural:
                    canonical = (
                        collected[target]
                        if target in collected
                        else collected[plural[target]]
                    )
                    canonical.extend(_as_text_sequence(child))
                else:
                    visit(child)
        elif isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            for child in node:
                visit(child)

    visit(value)
    return collected


def _as_mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json", by_alias=True)
        if isinstance(dumped, Mapping):
            return dumped
    if value is None:
        return {}
    return {
        key: getattr(value, key)
        for key in (
            "artifact_id",
            "kind",
            "media_type",
            "schema",
            "artifact_schema",
            "integrity",
            "byte_size",
        )
        if hasattr(value, key)
    }


def _field(value: Mapping[str, object], name: str) -> object | None:
    return value.get(name)


_MISSING = object()


def _lookup_identity(payload: object, path: str) -> object:
    current = payload
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return _MISSING
    return current


def _payload_contains_forbidden_marker(payload: object) -> bool:
    markers = ("synthetic", "fixture", "self-attest", "self_attest", "self attest")
    if isinstance(payload, Mapping):
        return any(
            _payload_contains_forbidden_marker(key)
            or _payload_contains_forbidden_marker(value)
            for key, value in payload.items()
        )
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return any(_payload_contains_forbidden_marker(value) for value in payload)
    return any(marker in str(payload).casefold() for marker in markers)


def _as_text_sequence(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value.strip(),)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        values: list[str] = []
        for item in value:
            values.extend(_as_text_sequence(item))
        return tuple(values)
    return (str(value).strip(),)


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        coerced = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return coerced if coerced >= 0 else None


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values))


__all__ = [
    "EmpiricalCalibrationContext",
    "EmpiricalCalibrationEvidence",
    "EmpiricalCalibrationEvidenceRef",
    "EmpiricalEvidenceKind",
    "EvidenceArtifactRef",
    "load_empirical_calibration_evidence",
    "persist_empirical_calibration_evidence",
    "produce_empirical_calibration_evidence",
]
