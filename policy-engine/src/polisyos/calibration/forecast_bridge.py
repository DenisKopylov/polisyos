"""Produce neutral empirical evidence from a persisted backtest report.

This module is the producer half of the FRC-02 slice.  It admits a
content-bound IR ``BacktestReport``, derives interval hits from observed
outcomes and persisted bounds, reconciles every stored projection, and emits
neutral evidence.  It deliberately does not know about runtime status
lattices or S10/G2/W12D consumers; a later runtime adapter owns that boundary.

All evidence references are resolved through the same CAS and checked against
their role-specific manifest profile, bytes, report input edge, payload
identity, and declared identity.  A nominal confidence level or a
self-described lineage cannot substitute for those observations.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
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
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ArtifactRefModel, BacktestReportRef

EmpiricalEvidenceKind = Literal["observed_interval_comparisons", "unavailable"]
PredictiveAuthorityScope = Literal["predictive_only"]
AuthorityDenial = Literal[
    "causal_effect_authority",
    "treatment_assignment_authority",
    "s10_authority",
]

PREDICTIVE_ESTIMAND = "predictive_interval_coverage"
PREDICTIVE_AUTHORITY_SCOPE = "predictive_only"
PREDICTIVE_AUTHORITY_DENIALS: tuple[str, ...] = (
    "causal_effect_authority",
    "treatment_assignment_authority",
    "s10_authority",
)

REPORT_KIND = "ir.backtest_report"
REPORT_SCHEMA_NAME = "ir.backtest_report"
REPORT_SCHEMA_VERSION = "1.0"
EVIDENCE_KIND = "ir.empirical_calibration_evidence"
EVIDENCE_SCHEMA_NAME = "polisyos.calibration.empirical_calibration_evidence"
EVIDENCE_SCHEMA_VERSION = "1.0"

ReferenceRole = Literal[
    "scope_binding",
    "calibration_threshold",
    "observed_outcome",
    "prediction",
    "evaluation_design",
    "credible_evaluation",
    "source_lineage",
    "method_lineage",
]

# These profiles are the neutral producer contract.  A caller cannot select a
# kind/schema pair and make it authoritative; the role fixes the expected
# profile, and the report manifest must independently carry the same artifact
# under the same input role.
REFERENCE_PROFILES: dict[str, tuple[str, str, str]] = {
    "scope_binding": (
        "ir.calibration.scope_binding",
        "polisyos.calibration.scope_binding",
        "1.0",
    ),
    "calibration_threshold": (
        "ir.calibration.threshold",
        "polisyos.calibration.threshold",
        "1.0",
    ),
    "observed_outcome": (
        "ir.calibration.observed_outcome",
        "polisyos.calibration.observed_outcome",
        "1.0",
    ),
    "prediction": (
        "ir.calibration.prediction",
        "polisyos.calibration.prediction",
        "1.0",
    ),
    "evaluation_design": (
        "ir.calibration.evaluation_design",
        "polisyos.calibration.evaluation_design",
        "1.0",
    ),
    "credible_evaluation": (
        "ir.calibration.credible_evaluation",
        "polisyos.calibration.credible_evaluation",
        "1.0",
    ),
    "source_lineage": (
        "ir.calibration.source_lineage",
        "polisyos.calibration.source_lineage",
        "1.0",
    ),
    "method_lineage": (
        "ir.calibration.method_lineage",
        "polisyos.calibration.method_lineage",
        "1.0",
    ),
}

# Identity paths are part of the role contract.  They are not caller-selected
# JSON paths: the producer resolves the one field that gives each role its
# stable, semantic identity and rejects aliases or self-selected paths.
REFERENCE_IDENTITY_PATHS: dict[str, str] = {
    "scope_binding": "report_id",
    "calibration_threshold": "identity",
    "observed_outcome": "identity",
    "prediction": "identity",
    "evaluation_design": "identity",
    "credible_evaluation": "identity",
    "source_lineage": "identity",
    "method_lineage": "identity",
}
_REFERENCE_INPUT_ROLES = frozenset(REFERENCE_PROFILES)
_TRIVIAL_IDENTITY_VALUES = frozenset(
    {
        "",
        "identity",
        "report_id",
        "artifact_id",
        "role",
        "kind",
        "value",
        "true",
        "false",
        "none",
        "null",
    }
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
        "persisted_projection_incomplete",
        "persisted_metadata_counter_incomplete",
        "persisted_metadata_numerator_mismatch",
        "persisted_metadata_denominator_mismatch",
        "persisted_metadata_counter_invalid",
        "zero_observation_denominator",
        "nominal_confidence_only",
    }
)
_PERSISTENCE_ALLOWED_LIMITATIONS = frozenset(
    {
        "calibration_floor_not_met",
        "zero_observation_denominator",
        "nominal_confidence_only",
    }
)

class EvidenceArtifactRef(BaseModel):
    """Typed CAS reference with the contract needed to verify provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: ArtifactID
    role: ReferenceRole
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

    @model_validator(mode="after")
    def _validate_identity_binding(self) -> EvidenceArtifactRef:
        _validate_reference_identity_contract(self, self.role)
        return self


class EmpiricalCalibrationEvidenceRef(ArtifactRefModel):
    """Typed CAS reference for a persisted neutral empirical evidence artifact."""

    kind: Literal[EVIDENCE_KIND] = EVIDENCE_KIND
    media_type: Literal["application/json"] = "application/json"


class EmpiricalCalibrationContext(BaseModel):
    """Caller-supplied semantic, provenance, and time binding for evidence.

    A generic backtest report cannot establish the estimand, method version, or
    temporal meaning of its rows.  Those fields are required from the typed
    caller.  Every provenance field is also a typed CAS reference whose
    manifest and payload identity are checked against the same store, and the
    report manifest must carry each ref under its expected role.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_spec_ref: str = Field(min_length=1, max_length=300)
    policy_spec_ref: str = Field(min_length=1, max_length=300)
    estimand: Literal[PREDICTIVE_ESTIMAND] = PREDICTIVE_ESTIMAND
    method_ref: str = Field(min_length=1, max_length=300)
    method_version: str = Field(min_length=1, max_length=120)
    rule_version_ref: str = Field(min_length=1, max_length=300)
    authority_scope: PredictiveAuthorityScope = PREDICTIVE_AUTHORITY_SCOPE
    may_not_use_for: tuple[AuthorityDenial, ...] = PREDICTIVE_AUTHORITY_DENIALS
    calibration_threshold: float = Field(gt=0.0, le=1.0)
    scope_binding_ref: EvidenceArtifactRef
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
        if self.data_valid_time >= self.calibration_window_start:
            raise ValueError("data-valid time must precede the calibration window")
        if self.calibration_window_start >= self.calibration_window_end:
            raise ValueError("calibration window end must follow its start")
        if self.calibration_window_end > self.prediction_time:
            raise ValueError("calibration window must end no later than prediction time")
        if self.policy_effective_time > self.prediction_time:
            raise ValueError("policy effective time cannot follow prediction time")
        if self.prediction_time >= self.observation_time:
            raise ValueError("prediction time must precede observation time")

        if self.authority_scope != PREDICTIVE_AUTHORITY_SCOPE:
            raise ValueError("empirical calibration evidence is predictive-only")
        if tuple(self.may_not_use_for) != PREDICTIVE_AUTHORITY_DENIALS:
            raise ValueError("predictive evidence authority denials are immutable")

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
    estimand: Literal[PREDICTIVE_ESTIMAND] | None = None
    method_ref: str | None = None
    method_version: str | None = None
    rule_version_ref: str | None = None
    authority_scope: PredictiveAuthorityScope = PREDICTIVE_AUTHORITY_SCOPE
    may_not_use_for: tuple[AuthorityDenial, ...] = PREDICTIVE_AUTHORITY_DENIALS
    evidence_origin: str | None = None
    calibration_threshold: float | None = Field(default=None, gt=0.0, le=1.0)
    scope_binding_ref: EvidenceArtifactRef | None = None
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

    @model_validator(mode="after")
    def _validate_authority_boundary(self) -> EmpiricalCalibrationEvidence:
        if self.authority_scope != PREDICTIVE_AUTHORITY_SCOPE:
            raise ValueError("empirical calibration evidence is predictive-only")
        if tuple(self.may_not_use_for) != PREDICTIVE_AUTHORITY_DENIALS:
            raise ValueError("predictive evidence authority denials are immutable")
        return self


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
    provenance_payloads: dict[str, tuple[object, ...]] = {}
    if context is None:
        issues.append("explicit_context_missing")
    else:
        binding_issues = _binding_issues(report, context)
        provenance_issues, provenance_payloads = _context_reference_issues(
            store,
            validated_report_ref,
            report,
            context,
        )
        binding_issues = _dedupe(
            (
                *binding_issues,
                *_scope_binding_issues(
                    provenance_payloads.get("scope_binding", ()),
                    report,
                    context,
                ),
            )
        )
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
        authority_scope=(
            context.authority_scope if context else PREDICTIVE_AUTHORITY_SCOPE
        ),
        may_not_use_for=(
            context.may_not_use_for if context else PREDICTIVE_AUTHORITY_DENIALS
        ),
        evidence_origin=context.evidence_origin if context else None,
        calibration_threshold=context.calibration_threshold if context else None,
        scope_binding_ref=context.scope_binding_ref if context else None,
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

    expected = _reproduce_evidence(store, evidence)
    if not expected.context_bound or any(
        code not in _PERSISTENCE_ALLOWED_LIMITATIONS for code in expected.failure_codes
    ):
        raise ValueError("blocked empirical calibration evidence cannot be persisted")
    inputs: list[dict[str, object]] = [
        {"artifact_id": str(expected.report_ref.artifact_id), "role": "backtest_report"}
    ]
    for role, ref in _context_refs(expected):
        inputs.append({"artifact_id": str(ref.artifact_id), "role": role})

    payload = put_json_artifact(
        store,
        expected.model_dump(mode="json"),
        kind=EVIDENCE_KIND,
        schema_name=EVIDENCE_SCHEMA_NAME,
        schema_version=EVIDENCE_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
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
    _validate_evidence_input_edges(store, validated_ref, evidence)
    _validate_json_artifact(
        store,
        evidence.report_ref,
        expected_kind=REPORT_KIND,
        expected_media_type="application/json",
        expected_schema_name=REPORT_SCHEMA_NAME,
        expected_schema_version=REPORT_SCHEMA_VERSION,
    )
    _reproduce_evidence(store, evidence)
    return evidence


def _validate_evidence_input_edges(
    store: ArtifactStore,
    evidence_ref: EmpiricalCalibrationEvidenceRef,
    evidence: EmpiricalCalibrationEvidence,
) -> None:
    """Require the persisted evidence manifest's complete input edge set."""

    expected = [
        (str(evidence.report_ref.artifact_id), "backtest_report"),
        *(
            (str(ref.artifact_id), role)
            for role, ref in _context_refs(evidence)
        ),
    ]
    actual = _manifest_input_edges(store, evidence_ref.artifact_id)
    if sorted(actual) != sorted(expected):
        raise ValueError(
            "empirical evidence manifest input edge/role binding mismatch"
        )


def _manifest_input_edges(
    store: ArtifactStore,
    artifact_id: ArtifactID,
) -> tuple[tuple[str, str], ...]:
    """Decode an artifact manifest's input edges without trusting its shape."""

    manifest = _as_mapping(store.get_manifest(artifact_id))
    raw_inputs = _field(manifest, "inputs")
    if not isinstance(raw_inputs, Sequence) or isinstance(
        raw_inputs, (str, bytes, bytearray)
    ):
        raise ValueError("artifact manifest inputs are missing or malformed")
    edges: list[tuple[str, str]] = []
    for raw_input in raw_inputs:
        input_payload = _as_mapping(raw_input)
        raw_artifact_id = _field(input_payload, "artifact_id")
        raw_role = _field(input_payload, "role")
        if raw_artifact_id is None or not isinstance(raw_role, str) or not raw_role.strip():
            raise ValueError("artifact manifest input edge is malformed")
        edges.append((str(raw_artifact_id), raw_role.strip()))
    return tuple(edges)


def _reproduce_evidence(
    store: ArtifactStore,
    evidence: EmpiricalCalibrationEvidence,
) -> EmpiricalCalibrationEvidence:
    """Recompute evidence from its report and preserved typed context.

    Persistence never treats the DTO's counters, status booleans, or failure
    codes as authority.  They must be exactly the deterministic projection of
    the current report plus the context that the DTO carries.
    """

    context = _context_from_evidence(store, evidence)
    expected = produce_empirical_calibration_evidence(
        store,
        evidence.report_ref,
        context=context,
    )
    if expected.model_dump(mode="json") != evidence.model_dump(mode="json"):
        raise ValueError(
            "empirical evidence payload is not reproducible from its report"
        )
    return expected


def _context_from_evidence(
    store: ArtifactStore,
    evidence: EmpiricalCalibrationEvidence,
) -> EmpiricalCalibrationContext | None:
    """Recover a complete caller context, rejecting partial persisted context."""

    context_values = (
        evidence.evidence_origin,
        evidence.estimand,
        evidence.method_ref,
        evidence.method_version,
        evidence.rule_version_ref,
        evidence.calibration_threshold,
        evidence.scope_binding_ref,
        evidence.calibration_threshold_ref,
        evidence.observed_outcome_ref,
        evidence.prediction_ref,
        evidence.evaluation_design_ref,
        evidence.credible_evaluation_evidence_ref,
        *evidence.source_lineage_refs,
        *evidence.method_lineage_refs,
        evidence.prediction_time,
        evidence.observation_time,
        evidence.policy_effective_time,
        evidence.data_valid_time,
        evidence.calibration_window_start,
        evidence.calibration_window_end,
    )
    if not any(value is not None for value in context_values):
        return None

    required = {
        "evidence_origin": evidence.evidence_origin,
        "estimand": evidence.estimand,
        "method_ref": evidence.method_ref,
        "method_version": evidence.method_version,
        "rule_version_ref": evidence.rule_version_ref,
        "authority_scope": evidence.authority_scope,
        "may_not_use_for": evidence.may_not_use_for,
        "calibration_threshold": evidence.calibration_threshold,
        "scope_binding_ref": evidence.scope_binding_ref,
        "calibration_threshold_ref": evidence.calibration_threshold_ref,
        "observed_outcome_ref": evidence.observed_outcome_ref,
        "prediction_ref": evidence.prediction_ref,
        "evaluation_design_ref": evidence.evaluation_design_ref,
        "credible_evaluation_evidence_ref": evidence.credible_evaluation_evidence_ref,
        "source_lineage_refs": evidence.source_lineage_refs,
        "method_lineage_refs": evidence.method_lineage_refs,
        "prediction_time": evidence.prediction_time,
        "observation_time": evidence.observation_time,
        "policy_effective_time": evidence.policy_effective_time,
        "data_valid_time": evidence.data_valid_time,
        "calibration_window_start": evidence.calibration_window_start,
        "calibration_window_end": evidence.calibration_window_end,
    }
    if any(value is None or value == () for value in required.values()):
        raise ValueError("persisted empirical evidence context is incomplete")

    _report_ref, report = _load_verified_report(store, evidence.report_ref)
    if not report.model_spec_ref or not report.policy_spec_ref:
        raise ValueError(
            "persisted evidence context lacks a complete report model/policy pair"
        )
    return EmpiricalCalibrationContext.model_validate(
        {
            "model_spec_ref": report.model_spec_ref,
            "policy_spec_ref": report.policy_spec_ref,
            "estimand": evidence.estimand,
            "method_ref": evidence.method_ref,
            "method_version": evidence.method_version,
            "rule_version_ref": evidence.rule_version_ref,
            "authority_scope": evidence.authority_scope,
            "may_not_use_for": evidence.may_not_use_for,
            "evidence_origin": evidence.evidence_origin,
            "calibration_threshold": evidence.calibration_threshold,
            "scope_binding_ref": evidence.scope_binding_ref,
            "calibration_threshold_ref": evidence.calibration_threshold_ref,
            "observed_outcome_ref": evidence.observed_outcome_ref,
            "prediction_ref": evidence.prediction_ref,
            "evaluation_design_ref": evidence.evaluation_design_ref,
            "credible_evaluation_evidence_ref": evidence.credible_evaluation_evidence_ref,
            "source_lineage_refs": evidence.source_lineage_refs,
            "method_lineage_refs": evidence.method_lineage_refs,
            "prediction_time": evidence.prediction_time,
            "observation_time": evidence.observation_time,
            "policy_effective_time": evidence.policy_effective_time,
            "data_valid_time": evidence.data_valid_time,
            "calibration_window_start": evidence.calibration_window_start,
            "calibration_window_end": evidence.calibration_window_end,
        }
    )


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
    report = load_backtest_report(store, validated_ref)
    if report.schema_version != REPORT_SCHEMA_VERSION:
        raise ValueError("backtest report payload schema version mismatch")
    return validated_ref, report


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
    report_ref: BacktestReportRef,
    report: BacktestReport,
    context: EmpiricalCalibrationContext,
) -> tuple[tuple[str, ...], dict[str, tuple[object, ...]]]:
    """Resolve context refs against a role-bound report manifest.

    The report input edge and the payload's report identity are deliberately
    separate checks.  A caller-provided reference that is internally
    self-consistent, but is not an input to this report under the expected
    role, is therefore not admitted as evidence.
    """

    issues: list[str] = []
    payloads: dict[str, list[object]] = {}
    input_edges = _report_input_edges(store, report_ref)
    relations = set(input_edges)
    relation_roles: dict[str, set[str]] = {}
    for artifact_id, role in relations:
        relation_roles.setdefault(artifact_id, set()).add(role)

    expected_context_edges = tuple(
        (str(ref.artifact_id), role) for role, ref in _context_refs(context)
    )
    actual_context_edges = tuple(
        (artifact_id, role)
        for artifact_id, role in input_edges
        if role in _REFERENCE_INPUT_ROLES
    )
    if sorted(actual_context_edges) != sorted(expected_context_edges):
        issues.append("report_context_input_edges_mismatch")

    for role, ref in _context_refs(context):
        artifact_id = str(ref.artifact_id)
        if (artifact_id, role) not in relations:
            if artifact_id in relation_roles:
                issues.append("reference_report_role_mismatch")
            else:
                issues.append("reference_report_relation_not_established")
        try:
            payload = _validate_and_load_reference(store, ref, role=role)
        except (FileNotFoundError, OSError, TypeError, ValueError):
            issues.extend(
                ("provenance_ref_unresolved", f"provenance_ref_invalid:{role}")
            )
            continue
        payloads.setdefault(role, []).append(payload)

        if ref.role != role:
            issues.append(f"provenance_ref_role_mismatch:{role}")
        payload_role = _lookup_identity(payload, "role")
        if payload_role is _MISSING or str(payload_role) != role:
            issues.append("reference_payload_role_mismatch")
        payload_report_id = _lookup_identity(payload, "report_id")
        if payload_report_id is _MISSING or str(payload_report_id) != report.report_id:
            issues.append("reference_report_relation_not_established")
        actual = _lookup_identity(payload, ref.identity_path)
        if actual is _MISSING or str(actual) != ref.identity_value:
            issues.extend(
                (
                    "provenance_ref_identity_mismatch",
                    f"provenance_ref_invalid:{role}",
                )
            )
        if _payload_contains_forbidden_marker(payload):
            issues.append("forbidden_provenance_marker")
        issues.extend(_authority_payload_issues(payload))
    issues.extend(
        _threshold_binding_issues(
            payloads.get("calibration_threshold", ()),
            context,
        )
    )
    return _dedupe(issues), {
        role: tuple(values) for role, values in payloads.items()
    }


def _report_input_edges(
    store: ArtifactStore,
    report_ref: BacktestReportRef,
) -> tuple[tuple[str, str], ...]:
    """Return the report's declared artifact input edges.

    Missing or malformed input edges intentionally produce an empty set.  The
    caller then receives ``reference_report_relation_not_established`` rather
    than trusting an untyped or self-declared relationship.
    """

    try:
        manifest = _as_mapping(store.get_manifest(report_ref.artifact_id))
    except (FileNotFoundError, OSError, TypeError, ValueError):
        return ()
    raw_inputs = _field(manifest, "inputs")
    if not isinstance(raw_inputs, Sequence) or isinstance(
        raw_inputs, (str, bytes, bytearray)
    ):
        return ()
    relations: list[tuple[str, str]] = []
    for raw_input in raw_inputs:
        input_payload = _as_mapping(raw_input)
        artifact_id = _field(input_payload, "artifact_id")
        role = _field(input_payload, "role")
        if artifact_id is not None and isinstance(role, str) and role.strip():
            relations.append((str(artifact_id), role.strip()))
    return tuple(relations)


def _report_input_relations(
    store: ArtifactStore,
    report_ref: BacktestReportRef,
) -> set[tuple[str, str]]:
    """Return report input edges as a set for relation membership checks."""

    return set(_report_input_edges(store, report_ref))


def _scope_binding_issues(
    payloads: Sequence[object],
    report: BacktestReport,
    context: EmpiricalCalibrationContext,
) -> tuple[str, ...]:
    """Check the independently persisted scope binding against both parties."""

    if len(payloads) != 1:
        return ("scope_binding_relation_not_established",)
    binding = _as_mapping(_lookup_identity(payloads[0], "binding"))
    expected = {
        "report_id": report.report_id,
        "model_spec_ref": report.model_spec_ref,
        "policy_spec_ref": report.policy_spec_ref,
        "estimand": context.estimand,
        "method_ref": context.method_ref,
        "method_version": context.method_version,
        "rule_version_ref": context.rule_version_ref,
    }
    if any(value is None for value in expected.values()):
        return ("scope_binding_relation_not_established",)
    issues: list[str] = []
    for field_name, expected_value in expected.items():
        actual = _field(binding, field_name)
        if actual is None or str(actual) != str(expected_value):
            issues.append("scope_binding_relation_not_established")
    authority_scope = _field(binding, "authority_scope")
    if authority_scope is not None and str(authority_scope) != PREDICTIVE_AUTHORITY_SCOPE:
        issues.append("authority_scope_mismatch")
    raw_threshold = _field(binding, "calibration_threshold")
    if raw_threshold is not None:
        declared_threshold = _coerce_decimal(raw_threshold, allow_text=True)
        if declared_threshold != _coerce_decimal(context.calibration_threshold):
            issues.append("calibration_threshold_binding_mismatch")
    return _dedupe(issues)


def _validate_and_load_reference(
    store: ArtifactStore,
    ref: EvidenceArtifactRef,
    *,
    role: str,
) -> object:
    """Verify one typed context reference and decode its canonical JSON."""

    if ref.role != role:
        raise ValueError("evidence reference role mismatch")
    _validate_reference_identity_contract(ref, role)
    try:
        expected_kind, expected_schema_name, expected_schema_version = (
            REFERENCE_PROFILES[role]
        )
    except KeyError as exc:
        raise ValueError("unsupported evidence reference role") from exc
    if ref.media_type != "application/json":
        raise ValueError("evidence reference media type mismatch")
    _validate_json_artifact(
        store,
        ref,
        expected_kind=expected_kind,
        expected_media_type="application/json",
        expected_schema_name=expected_schema_name,
        expected_schema_version=expected_schema_version,
    )
    if (
        ref.kind != expected_kind
        or ref.schema_name != expected_schema_name
        or ref.schema_version != expected_schema_version
    ):
        raise ValueError("evidence reference profile mismatch")
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
        if numerator_present and denominator_present:
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
    if context.estimand != PREDICTIVE_ESTIMAND:
        issues.append("unsupported_estimand")
    if context.authority_scope != PREDICTIVE_AUTHORITY_SCOPE:
        issues.append("authority_scope_mismatch")
    if tuple(context.may_not_use_for) != PREDICTIVE_AUTHORITY_DENIALS:
        issues.append("authority_denials_mismatch")
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
        ("authority_scope", PREDICTIVE_AUTHORITY_SCOPE, "report_authority_scope_missing"),
    )
    for field_name, expected, missing_code in required_report_fields:
        raw = metadata.get(field_name)
        if not isinstance(raw, str) or not raw.strip():
            issues.append(missing_code)
        elif raw.strip() != expected:
            issues.append(f"{field_name}_mismatch")

    raw_denials = metadata.get("may_not_use_for")
    if raw_denials is not None:
        declared_denials = tuple(_as_text_sequence(raw_denials))
        if declared_denials != PREDICTIVE_AUTHORITY_DENIALS:
            issues.append("authority_denials_mismatch")
    issues.extend(_authority_payload_issues(metadata))
    for scenario in report.scenarios:
        issues.extend(_authority_payload_issues(scenario.metadata))

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
    for role, field_name in (
        ("scope_binding", "scope_binding_ref"),
        ("calibration_threshold", "calibration_threshold_ref"),
        ("observed_outcome", "observed_outcome_ref"),
        ("prediction", "prediction_ref"),
        ("evaluation_design", "evaluation_design_ref"),
        ("credible_evaluation", "credible_evaluation_evidence_ref"),
    ):
        ref = getattr(value, field_name, None)
        if ref is not None:
            refs.append((role, ref))
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


def _validate_reference_identity_contract(
    ref: EvidenceArtifactRef,
    role: str,
) -> None:
    """Enforce the canonical identity field assigned to a reference role."""

    expected_path = REFERENCE_IDENTITY_PATHS.get(role)
    if expected_path is None:
        raise ValueError("unsupported evidence reference role")
    if ref.identity_path != expected_path:
        raise ValueError(
            f"evidence reference identity path must be {expected_path!r} for {role}"
        )
    normalized = ref.identity_value.strip().casefold()
    if (
        normalized in _TRIVIAL_IDENTITY_VALUES
        or normalized == role.casefold()
        or normalized == f"{role}_ref".casefold()
        or normalized == str(ref.artifact_id).casefold()
    ):
        raise ValueError("evidence reference identity must be semantic and non-trivial")


def _coerce_decimal(value: object, *, allow_text: bool = False) -> Decimal | None:
    """Coerce a finite numeric value without accepting booleans as numbers."""

    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        candidate = value
    elif isinstance(value, (int, float)):
        candidate = Decimal(str(value))
    elif allow_text and isinstance(value, str):
        try:
            candidate = Decimal(value.strip())
        except (InvalidOperation, ValueError):
            return None
    else:
        return None
    return candidate if candidate.is_finite() else None


def _threshold_binding_issues(
    payloads: Sequence[object],
    context: EmpiricalCalibrationContext,
) -> tuple[str, ...]:
    """Bind the typed threshold to the canonical threshold artifact value."""

    if len(payloads) != 1:
        return ("calibration_threshold_relation_not_established",)
    raw_threshold = _lookup_identity(payloads[0], "threshold")
    if raw_threshold is _MISSING:
        return ("calibration_threshold_value_missing",)
    persisted_threshold = _coerce_decimal(raw_threshold)
    expected_threshold = _coerce_decimal(context.calibration_threshold)
    if persisted_threshold is None:
        return ("calibration_threshold_value_invalid",)
    if expected_threshold is None or persisted_threshold != expected_threshold:
        return ("calibration_threshold_binding_mismatch",)
    return ()


def _authority_payload_issues(payload: object) -> tuple[str, ...]:
    """Reject causal, treatment, or S10 purpose declarations in context data."""

    issues: list[str] = []

    def visit(node: object) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                key_name = str(key).casefold().replace("-", "_").replace(" ", "_")
                if key_name == "authority_scope":
                    if str(child) != PREDICTIVE_AUTHORITY_SCOPE:
                        issues.append("authority_scope_mismatch")
                elif key_name == "estimand":
                    if str(child) != PREDICTIVE_ESTIMAND:
                        issues.append("unsupported_estimand")
                elif key_name in {
                    "purpose",
                    "authority_purpose",
                    "claim_purpose",
                    "intended_use",
                    "use_for",
                }:
                    if any(_forbidden_authority_text(text) for text in _as_text_sequence(child)):
                        issues.append("forbidden_authority_purpose")
                elif key_name in {"may_not_use_for", "authority_denials", "denials"}:
                    declared = tuple(_as_text_sequence(child))
                    if declared != PREDICTIVE_AUTHORITY_DENIALS:
                        issues.append("authority_denials_mismatch")
                visit(child)
        elif isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            for child in node:
                visit(child)

    visit(payload)
    return _dedupe(issues)


def _forbidden_authority_text(value: str) -> bool:
    """Recognize purpose text that would grant a non-predictive authority."""

    normalized = value.casefold().replace("-", "_").replace(" ", "_")
    return any(token in normalized for token in ("causal", "treatment", "s10"))


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
    "AuthorityDenial",
    "EmpiricalCalibrationContext",
    "EmpiricalCalibrationEvidence",
    "EmpiricalCalibrationEvidenceRef",
    "EmpiricalEvidenceKind",
    "EvidenceArtifactRef",
    "PREDICTIVE_AUTHORITY_DENIALS",
    "PREDICTIVE_AUTHORITY_SCOPE",
    "PREDICTIVE_ESTIMAND",
    "REFERENCE_PROFILES",
    "REFERENCE_IDENTITY_PATHS",
    "ReferenceRole",
    "load_empirical_calibration_evidence",
    "persist_empirical_calibration_evidence",
    "produce_empirical_calibration_evidence",
]
