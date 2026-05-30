"""Evidence authority envelope contracts for honest diagnostics."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EvidenceClass = Literal[
    "authority_bearing",
    "diagnostic_supporting",
    "debug_only",
    "public_exported",
    "redacted_derived",
    "legacy_quarantined",
]
AuthorityRole = Literal[
    "producer_authority",
    "runtime_blocker",
    "scorecard_input",
    "readiness_input",
    "approval_input",
    "projection_only",
    "packaging_only",
    "diagnostic_only",
    "not_authoritative",
]
ProvenanceKind = Literal[
    "runtime_emitted",
    "runtime_blocker",
    "runtime_fallback",
    "runtime_projection",
    "bundle_packaged",
    "bundle_overlay",
    "fixture_input",
    "simulated_provider",
    "legacy_quarantined",
    "legacy_supported",
    "legacy_rejected",
]
SameInputClosureStatus = Literal["closed", "not_closed", "mismatched", "blocked"]
ValidationStatus = Literal["pass", "fail", "blocked", "not_applicable"]
BlockingStatus = Literal["non_blocking", "blocking", "non_overridable"]
AuthorityRootCauseClass = Literal[
    "missing_provenance",
    "unknown_provenance",
    "spoofed_provenance",
    "packaging_only_projection",
    "borrowed_authority_envelope",
    "runtime_domain_failure",
    "runtime_owned_domain_failure",
    "runtime_ref_identity_failure",
    "same_input_closure_failure",
    "legacy_authority_failure",
    "schema_contract_failure",
]

AUTHORITY_ENVELOPE_CONTRACT_NAME = "runtime_quality.evidence_authority_envelope"
AUTHORITY_ENVELOPE_CONTRACT_VERSION = "1.0.0"
EVIDENCE_AUTHORITY_ENVELOPE_SCHEMA_ID = (
    "https://schemas.policyos.local/runtime_quality/"
    "evidence_authority_envelope_v1.schema.json"
)
DEFAULT_AUTHORITY_ENVELOPE_SCHEMA_PATH = (
    Path(__file__).resolve().parents[4]
    / "schemas/runtime_quality/evidence_authority_envelope_v1.schema.json"
)

SERIOUS_EXECUTION_PROFILES = frozenset({"governed", "production", "research"})
_AUTHORITY_ROLES = frozenset({"producer_authority", "runtime_blocker"})
_SERIOUS_AUTHORITY_PROVENANCE = frozenset({"runtime_emitted", "runtime_blocker"})
_PROJECTION_ROLES = frozenset(
    {
        "approval_input",
        "diagnostic_only",
        "not_authoritative",
        "packaging_only",
        "projection_only",
        "readiness_input",
        "scorecard_input",
    }
)
_PROJECTION_PROVENANCE = frozenset(
    {
        "bundle_overlay",
        "bundle_packaged",
        "runtime_projection",
    }
)


class AuthorityEnvelopeError(ValueError):
    """Typed fail-closed authority-envelope invariant violation."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        evidence_id: str | None = None,
    ) -> None:
        self.code = code
        self.evidence_id = evidence_id
        detail = message or code
        if evidence_id:
            detail = f"{detail} (evidence_id={evidence_id})"
        super().__init__(f"{code}: {detail}")


AuthorityEnvelopeViolation = AuthorityEnvelopeError


class AuthorityFailureClassification(BaseModel):
    """Operator-facing root cause classification for authority-related failures."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    root_cause_class: AuthorityRootCauseClass
    owner: str = Field(min_length=1)
    first_failing_artifact_ref: str = Field(min_length=1)
    next_action: str = Field(min_length=1)
    authority_failure_code: str | None = None
    domain_failure_code: str | None = None
    producer_component: str | None = None
    producer_authority: dict[str, Any] = Field(default_factory=dict)


class ProducerIdentity(BaseModel):
    """Runtime producer identity copied onto every authority envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    component: str = Field(min_length=1)
    version: str = Field(min_length=1)
    owner: str = Field(min_length=1)

    @field_validator("component", "version", "owner")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)


class GovernanceMetadata(BaseModel):
    """Governance metadata that controls downstream authority consumption."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    classification: str = Field(min_length=1)
    authority_boundary: str = Field(min_length=1)
    pii: str = Field(min_length=1)
    retention_policy: str = Field(min_length=1)
    review_status: str = Field(min_length=1)
    override_policy: str = Field(min_length=1)
    approval_policy: str = Field(min_length=1)

    @field_validator(
        "classification",
        "authority_boundary",
        "pii",
        "retention_policy",
        "review_status",
        "override_policy",
        "approval_policy",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)


class SameInputClosure(BaseModel):
    """Identity of the input context shared by authority-bearing evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    closure_id: str = Field(min_length=1)
    status: SameInputClosureStatus
    policy_intent_ref: str | None = None
    run_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str | None = None
    time_context_ref: str | None = None
    production_data_manifest_ref: str | None = None
    legal_snapshot_ref: str | None = None
    method_plan_ref: str | None = None
    provider_mode_ref: str | None = None
    effective_mode_ref: str | None = None
    degradation_ledger_ref: str | None = None
    evidence_input_refs: tuple[str, ...] = Field(default=())
    closure_sha256: str | None = None

    @field_validator("closure_id", "run_id", "job_id", "tenant_id")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator(
        "policy_intent_ref",
        "cell_id",
        "time_context_ref",
        "production_data_manifest_ref",
        "legal_snapshot_ref",
        "method_plan_ref",
        "provider_mode_ref",
        "effective_mode_ref",
        "degradation_ledger_ref",
        "closure_sha256",
    )
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("evidence_input_refs")
    @classmethod
    def _strip_ref_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_non_empty(value) for value in values)

    def identity_tuple(self) -> tuple[str | None, ...]:
        """Stable same-input identity used by closeout consumers."""

        return (
            self.closure_sha256,
            self.run_id,
            self.job_id,
            self.tenant_id,
            self.cell_id,
            self.policy_intent_ref,
            self.time_context_ref,
            self.production_data_manifest_ref,
            self.legal_snapshot_ref,
            self.method_plan_ref,
            self.provider_mode_ref,
            self.effective_mode_ref,
            self.degradation_ledger_ref,
        )


class EvidenceAuthorityEnvelope(BaseModel):
    """Authority-bearing evidence metadata emitted beside runtime evidence."""

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "$id": EVIDENCE_AUTHORITY_ENVELOPE_SCHEMA_ID,
            "$schema": "https://json-schema.org/draft/2020-12/schema",
        },
    )

    evidence_id: str = Field(min_length=1)
    artifact_ref: str = Field(min_length=1)
    artifact_kind: str = Field(min_length=1)
    evidence_class: EvidenceClass
    authority_role: AuthorityRole
    provenance_kind: ProvenanceKind
    producer_component: str = Field(min_length=1)
    producer_version: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    runtime_event_ref: str = Field(min_length=1)
    cas_ref: str | None = None
    payload_sha256: str = Field(min_length=1)
    schema_name: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    reader_contract: str = Field(min_length=1)
    reader_contract_version: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str | None = None
    run_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    span_id: str = Field(min_length=1)
    parent_span_id: str | None = None
    requested_execution_profile: str = Field(min_length=1)
    effective_execution_profile: str = Field(min_length=1)
    phase: str = Field(min_length=1)
    state_before: str | None = None
    state_after: str | None = None
    generated_at: str = Field(min_length=1)
    as_of_time: str = Field(min_length=1)
    same_input_closure: SameInputClosure
    input_refs: tuple[str, ...]
    output_refs: tuple[str, ...]
    effective_mode_ref: str = Field(min_length=1)
    degradation_ledger_ref: str | None = None
    schema_compatibility_ref: str | None = None
    semantic_binding_ref: str | None = None
    attestation_ref: str | None = None
    redaction_policy_ref: str | None = None
    duplicate_of: str | None = None
    validation_status: ValidationStatus
    blocking_status: BlockingStatus
    governance: GovernanceMetadata

    @field_validator(
        "evidence_id",
        "artifact_ref",
        "artifact_kind",
        "producer_component",
        "producer_version",
        "owner",
        "runtime_event_ref",
        "payload_sha256",
        "schema_name",
        "schema_version",
        "reader_contract",
        "reader_contract_version",
        "tenant_id",
        "run_id",
        "job_id",
        "trace_id",
        "span_id",
        "requested_execution_profile",
        "effective_execution_profile",
        "phase",
        "generated_at",
        "as_of_time",
        "effective_mode_ref",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator(
        "cas_ref",
        "cell_id",
        "parent_span_id",
        "state_before",
        "state_after",
        "degradation_ledger_ref",
        "schema_compatibility_ref",
        "semantic_binding_ref",
        "attestation_ref",
        "redaction_policy_ref",
        "duplicate_of",
    )
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("input_refs", "output_refs")
    @classmethod
    def _strip_ref_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_non_empty(value) for value in values)

    @model_validator(mode="after")
    def _validate_closure_identity(self) -> EvidenceAuthorityEnvelope:
        closure = self.same_input_closure
        mismatches = {
            "run_id": (closure.run_id, self.run_id),
            "job_id": (closure.job_id, self.job_id),
            "tenant_id": (closure.tenant_id, self.tenant_id),
            "cell_id": (closure.cell_id, self.cell_id),
        }
        mismatch_names = [
            name for name, (closure_value, envelope_value) in mismatches.items()
            if closure_value != envelope_value
        ]
        if mismatch_names:
            joined = ", ".join(sorted(mismatch_names))
            raise ValueError(f"same_input_closure identity mismatch: {joined}")
        return self

    @property
    def producer_identity(self) -> ProducerIdentity:
        """Structured producer identity derived from stable top-level fields."""

        return ProducerIdentity(
            component=self.producer_component,
            version=self.producer_version,
            owner=self.owner,
        )


AuthorityEnvelopeInput = EvidenceAuthorityEnvelope | Mapping[str, Any] | str | bytes


def deserialize_authority_envelope(
    envelope: AuthorityEnvelopeInput,
) -> EvidenceAuthorityEnvelope:
    """Deserialize and validate one evidence authority envelope."""

    if isinstance(envelope, EvidenceAuthorityEnvelope):
        return envelope
    if isinstance(envelope, str | bytes):
        return EvidenceAuthorityEnvelope.model_validate_json(envelope)
    if isinstance(envelope, Mapping):
        return EvidenceAuthorityEnvelope.model_validate(dict(envelope))
    raise TypeError("authority envelope must be a mapping, JSON string, or model")


def serialize_authority_envelope(
    envelope: AuthorityEnvelopeInput,
    *,
    indent: int | None = None,
) -> str:
    """Validate and serialize one evidence authority envelope as stable JSON."""

    validated = deserialize_authority_envelope(envelope)
    return json.dumps(
        validated.model_dump(mode="json"),
        indent=indent,
        sort_keys=True,
    )


def assert_authority_bearing(
    envelope: AuthorityEnvelopeInput,
) -> EvidenceAuthorityEnvelope:
    """Assert that an envelope may be consumed as serious authority evidence."""

    validated = deserialize_authority_envelope(envelope)
    if validated.evidence_class != "authority_bearing":
        _raise(
            "evidence_not_authority_bearing",
            validated,
            f"evidence_class={validated.evidence_class!r}",
        )
    if validated.authority_role in _PROJECTION_ROLES:
        _raise(
            _role_failure_code(validated),
            validated,
            f"authority_role={validated.authority_role!r}",
        )
    if validated.authority_role not in _AUTHORITY_ROLES:
        _raise(
            "authority_role_cannot_satisfy_authority",
            validated,
            f"authority_role={validated.authority_role!r}",
        )
    if _is_serious_profile(validated) and (
        validated.provenance_kind not in _SERIOUS_AUTHORITY_PROVENANCE
    ):
        _raise(
            f"{validated.provenance_kind}_disallowed_for_serious_profile",
            validated,
            f"provenance_kind={validated.provenance_kind!r}",
        )
    return validated


def assert_runtime_emitted(
    envelope: AuthorityEnvelopeInput,
) -> EvidenceAuthorityEnvelope:
    """Assert that an envelope is runtime-emitted CAS-backed authority."""

    validated = assert_authority_bearing(envelope)
    if validated.provenance_kind != "runtime_emitted":
        _raise(
            "authority_not_runtime_emitted",
            validated,
            f"provenance_kind={validated.provenance_kind!r}",
        )
    if validated.authority_role != "producer_authority":
        _raise(
            "authority_role_not_runtime_producer",
            validated,
            f"authority_role={validated.authority_role!r}",
        )
    if not validated.cas_ref:
        _raise("authority_cas_missing", validated)
    if not _is_cas_ref(validated.cas_ref):
        _raise("authority_ref_not_cas", validated, f"cas_ref={validated.cas_ref!r}")
    if validated.artifact_ref != validated.cas_ref:
        _raise(
            "authority_runtime_ref_mismatch",
            validated,
            f"artifact_ref={validated.artifact_ref!r} cas_ref={validated.cas_ref!r}",
        )
    if validated.cas_ref not in validated.output_refs:
        _raise(
            "authority_output_ref_missing",
            validated,
            f"cas_ref={validated.cas_ref!r}",
        )
    return validated


def assert_same_input_closure(
    envelopes: Iterable[AuthorityEnvelopeInput],
) -> SameInputClosure:
    """Assert all envelopes carry the same closed input-context identity."""

    validated = tuple(deserialize_authority_envelope(envelope) for envelope in envelopes)
    if not validated:
        raise AuthorityEnvelopeError(
            "same_input_closure_missing",
            "at least one envelope is required",
        )

    first = validated[0].same_input_closure
    if first.status != "closed" or not first.closure_sha256:
        raise AuthorityEnvelopeError(
            "same_input_closure_not_closed",
            f"closure_id={first.closure_id}",
            evidence_id=validated[0].evidence_id,
        )
    expected = first.identity_tuple()
    for envelope in validated[1:]:
        closure = envelope.same_input_closure
        if closure.status != "closed" or not closure.closure_sha256:
            raise AuthorityEnvelopeError(
                "same_input_closure_not_closed",
                f"closure_id={closure.closure_id}",
                evidence_id=envelope.evidence_id,
            )
        if closure.identity_tuple() != expected:
            raise AuthorityEnvelopeError(
                "same_input_closure_mismatch",
                f"closure_id={closure.closure_id}",
                evidence_id=envelope.evidence_id,
            )
    return first


def classify_authority_role(envelope: AuthorityEnvelopeInput) -> AuthorityRole:
    """Return the validated authority role for an envelope."""

    return deserialize_authority_envelope(envelope).authority_role


def authority_purpose_blockers(
    envelope: Mapping[str, Any] | AuthorityEnvelopeInput | None,
    purpose: str,
) -> tuple[str, ...]:
    """Return purpose-boundary blockers from authoritative_for/may_not_use_for fields."""

    payload = _authority_payload(envelope)
    requested = _optional_text(str(purpose))
    if requested is None:
        return ("authority_purpose_missing",)
    may_not = set(_authority_payload_sequence(payload, "may_not_use_for"))
    may_not.update(_authority_payload_sequence(payload, "may_not_be_used_for"))
    if requested in may_not:
        return ("authority_purpose_forbidden",)
    authoritative_for = set(_authority_payload_sequence(payload, "authoritative_for"))
    if authoritative_for and requested not in authoritative_for:
        return ("authority_purpose_not_authorized",)
    return ()


def assert_authority_purpose_allowed(
    envelope: Mapping[str, Any] | AuthorityEnvelopeInput | None,
    purpose: str,
) -> Mapping[str, Any]:
    """Fail closed when an authority envelope forbids the requested purpose."""

    blockers = authority_purpose_blockers(envelope, purpose)
    if blockers:
        raise AuthorityEnvelopeError(blockers[0], f"purpose={purpose!r}")
    return _authority_payload(envelope)


def capability_binding_purpose_blockers(
    binding_result: Mapping[str, Any] | None,
    purpose: str,
) -> tuple[str, ...]:
    """Return purpose blockers for a capability binding result."""

    payload = _authority_payload(binding_result)
    blockers = list(authority_purpose_blockers(payload, purpose))
    requested = _optional_text(str(purpose))
    status = _authority_payload_text(payload, "status") or ""
    if requested in {"claim_evidence", "claim_evidence_closeout"} and not bool(
        payload.get("satisfies_claim_evidence")
    ):
        blockers.append(
            status
            if status.startswith("blocked_")
            else "capability_binding_cannot_satisfy_claim_evidence"
        )
    return tuple(dict.fromkeys(blockers))


def assert_capability_binding_purpose_allowed(
    binding_result: Mapping[str, Any] | None,
    purpose: str,
) -> Mapping[str, Any]:
    """Fail closed when a capability binding cannot be consumed for a purpose."""

    blockers = capability_binding_purpose_blockers(binding_result, purpose)
    if blockers:
        raise AuthorityEnvelopeError(blockers[0], f"purpose={purpose!r}")
    return _authority_payload(binding_result)


def classify_authority_failure(
    *,
    authority_error_code: str | None = None,
    domain_failure_code: str | None = None,
    envelope: AuthorityEnvelopeInput | Mapping[str, Any] | None = None,
    artifact_ref: str | None = None,
    owner: str | None = None,
    next_action: str | None = None,
) -> AuthorityFailureClassification:
    """Classify an authority failure without erasing runtime-owned domain failures."""

    envelope_payload = _authority_payload(envelope)
    normalized_authority_code = _normalize_code(authority_error_code)
    normalized_domain_code = _normalize_code(domain_failure_code)
    root_cause_class = _authority_root_cause_class(
        authority_code=normalized_authority_code,
        domain_code=normalized_domain_code,
        envelope=envelope_payload,
    )
    resolved_artifact_ref = (
        _optional_text(artifact_ref)
        or _authority_payload_text(envelope_payload, "cas_ref")
        or _authority_payload_text(envelope_payload, "artifact_ref")
        or _authority_payload_text(envelope_payload, "runtime_event_ref")
        or "runtime.authority"
    )
    resolved_owner = (
        _optional_text(owner)
        or _authority_payload_text(envelope_payload, "owner")
        or "team-runtime-quality"
    )
    resolved_next_action = _optional_text(next_action) or _next_action_for_root_cause(
        root_cause_class
    )
    producer_component = _authority_payload_text(envelope_payload, "producer_component")
    return AuthorityFailureClassification(
        root_cause_class=root_cause_class,
        owner=resolved_owner,
        first_failing_artifact_ref=resolved_artifact_ref,
        next_action=resolved_next_action,
        authority_failure_code=normalized_authority_code,
        domain_failure_code=(
            normalized_domain_code
            if normalized_domain_code and not _is_authority_infra_code(normalized_domain_code)
            else None
        ),
        producer_component=producer_component,
        producer_authority=_producer_authority_summary(envelope_payload),
    )


def authority_envelope_ownership_issues(
    *,
    envelope: Mapping[str, Any] | None,
    report_key: str,
    report: Mapping[str, Any] | None = None,
    ref_key: str | None = None,
    runtime_ref: str | None = None,
) -> list[dict[str, Any]]:
    """Validate that a report carries its own authority envelope, not a borrowed one."""

    if not isinstance(envelope, Mapping):
        return [
            _ownership_issue(
                "authority_envelope_missing",
                "Report is missing an authority envelope.",
                expected=report_key,
                observed=None,
                field="authority_envelope",
            )
        ]
    if not any(
        _authority_payload_text(envelope, key)
        for key in ("artifact_kind", "schema_name", "phase", "validation_status")
    ):
        return []

    normalized_report_key = _normalize_report_key(report_key)
    expected_artifact_kinds = _expected_artifact_kinds(
        report_key=normalized_report_key,
        ref_key=ref_key,
    )
    issues: list[dict[str, Any]] = []

    observed_artifact_kind = _authority_payload_text(envelope, "artifact_kind")
    if observed_artifact_kind not in expected_artifact_kinds:
        issues.append(
            _ownership_issue(
                "authority_envelope_artifact_kind_mismatch",
                "Authority envelope artifact_kind belongs to a different report family.",
                expected=sorted(expected_artifact_kinds),
                observed=observed_artifact_kind,
                field="artifact_kind",
            )
        )

    schema_name = _authority_payload_text(envelope, "schema_name")
    report_schema = _authority_payload_text(report or {}, "schema_version")
    if not _schema_matches_report(
        schema_name=schema_name,
        report_schema=report_schema,
        report_key=normalized_report_key,
        expected_artifact_kinds=expected_artifact_kinds,
    ):
        issues.append(
            _ownership_issue(
                "authority_envelope_schema_mismatch",
                "Authority envelope schema identity belongs to a different report family.",
                expected=report_schema or normalized_report_key,
                observed=schema_name,
                field="schema_name",
            )
        )

    phase = _authority_payload_text(envelope, "phase")
    if phase is not None and not _phase_matches_report(
        phase=phase,
        report_key=normalized_report_key,
        expected_artifact_kinds=expected_artifact_kinds,
    ):
        issues.append(
            _ownership_issue(
                "authority_envelope_phase_mismatch",
                "Authority envelope phase belongs to a different report family.",
                expected=normalized_report_key,
                observed=phase,
                field="phase",
            )
        )

    expected_validation_status = _validation_status_from_report(report)
    observed_validation_status = _authority_payload_text(envelope, "validation_status")
    if (
        expected_validation_status is not None
        and observed_validation_status is not None
        and observed_validation_status != expected_validation_status
    ):
        issues.append(
            _ownership_issue(
                "authority_envelope_validation_status_mismatch",
                "Authority envelope validation_status does not match the report status.",
                expected=expected_validation_status,
                observed=observed_validation_status,
                field="validation_status",
            )
        )

    expected_runtime_event_ref = _runtime_event_ref_from_report(report)
    observed_runtime_event_ref = _authority_payload_text(envelope, "runtime_event_ref")
    if (
        expected_runtime_event_ref is not None
        and observed_runtime_event_ref is not None
        and observed_runtime_event_ref != expected_runtime_event_ref
    ):
        issues.append(
            _ownership_issue(
                "authority_envelope_runtime_event_mismatch",
                "Authority envelope runtime_event_ref does not match the report runtime event.",
                expected=expected_runtime_event_ref,
                observed=observed_runtime_event_ref,
                field="runtime_event_ref",
            )
        )

    return issues


def authority_envelope_json_schema() -> dict[str, Any]:
    """Return the JSON Schema snapshot for the v1 authority envelope."""

    return EvidenceAuthorityEnvelope.model_json_schema(mode="validation")


def write_authority_envelope_json_schema(
    path: Path | str = DEFAULT_AUTHORITY_ENVELOPE_SCHEMA_PATH,
) -> Path:
    """Write the v1 authority envelope JSON Schema snapshot."""

    schema_path = Path(path)
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(
        json.dumps(authority_envelope_json_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return schema_path


def _non_empty(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("field is required")
    return text


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _is_serious_profile(envelope: EvidenceAuthorityEnvelope) -> bool:
    return (
        envelope.requested_execution_profile.casefold() in SERIOUS_EXECUTION_PROFILES
        or envelope.effective_execution_profile.casefold() in SERIOUS_EXECUTION_PROFILES
    )


def _is_cas_ref(value: str) -> bool:
    return value.startswith("cas://") or value.startswith("sha256:")


def _role_failure_code(envelope: EvidenceAuthorityEnvelope) -> str:
    if envelope.authority_role == "projection_only":
        return "projection_used_as_authority"
    if envelope.authority_role == "packaging_only":
        return "packaging_used_as_authority"
    if envelope.provenance_kind in _PROJECTION_PROVENANCE:
        return f"{envelope.provenance_kind}_used_as_authority"
    return f"{envelope.authority_role}_used_as_authority"


def _authority_payload(
    envelope: AuthorityEnvelopeInput | Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    if envelope is None:
        return {}
    if isinstance(envelope, EvidenceAuthorityEnvelope):
        return envelope.model_dump(mode="json")
    if isinstance(envelope, str | bytes):
        try:
            loaded = json.loads(envelope)
        except (TypeError, json.JSONDecodeError):
            return {}
        return loaded if isinstance(loaded, Mapping) else {}
    if isinstance(envelope, Mapping):
        return envelope
    return {}


def _authority_payload_text(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return _optional_text(value) if isinstance(value, str) else None


def _authority_payload_sequence(payload: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if isinstance(value, str):
        raw_values: Iterable[Any] = (value,)
    elif isinstance(value, Iterable):
        raw_values = value
    else:
        return ()
    return tuple(
        text
        for item in raw_values
        for text in (_optional_text(str(item)),)
        if text is not None
    )


def _normalize_code(value: str | None) -> str | None:
    return _optional_text(value)


def _authority_root_cause_class(
    *,
    authority_code: str | None,
    domain_code: str | None,
    envelope: Mapping[str, Any],
) -> AuthorityRootCauseClass:
    haystack = " ".join(
        value
        for value in (
            authority_code,
            domain_code,
            _authority_payload_text(envelope, "evidence_class"),
            _authority_payload_text(envelope, "authority_role"),
            _authority_payload_text(envelope, "provenance_kind"),
            _authority_payload_text(envelope, "validation_status"),
        )
        if value
    ).casefold()
    if "borrowed" in haystack or "wrong_report" in haystack:
        return "borrowed_authority_envelope"
    if "same_input_closure" in haystack:
        return "same_input_closure_failure"
    if "legacy" in haystack or "diagnostic_only" in haystack:
        return "legacy_authority_failure"
    if "schema" in haystack and "hds_schema" in haystack:
        return "schema_contract_failure"
    if any(
        marker in haystack
        for marker in (
            "ref_identity",
            "runtime_ref_mismatch",
            "payload_mismatch",
            "ref_not_cas",
            "cas_missing",
            "output_ref_missing",
            "authority_cas_missing",
            "authority_ref_not_cas",
        )
    ):
        return "runtime_ref_identity_failure"
    if "packaging" in haystack or "bundle_packaged" in haystack:
        return "packaging_only_projection"
    if any(
        marker in haystack
        for marker in (
            "projection",
            "public_exported",
            "redacted_derived",
            "scorecard_input",
            "readiness_input",
            "approval_input",
            "not_authoritative",
        )
    ):
        return "spoofed_provenance"
    if _runtime_owned_domain_failure(envelope=envelope, domain_code=domain_code):
        return "runtime_owned_domain_failure"
    if authority_code == "hds_unknown_provenance" or "unknown_provenance" in haystack:
        return "missing_provenance"
    if domain_code and not _is_authority_infra_code(domain_code):
        return "runtime_owned_domain_failure"
    if not envelope or not _authority_payload_text(envelope, "authority_role"):
        return "missing_provenance"
    return "unknown_provenance"


def _runtime_owned_domain_failure(
    *,
    envelope: Mapping[str, Any],
    domain_code: str | None,
) -> bool:
    if not domain_code or _is_authority_infra_code(domain_code):
        return False
    role = (_authority_payload_text(envelope, "authority_role") or "").casefold()
    provenance = (_authority_payload_text(envelope, "provenance_kind") or "").casefold()
    validation_status = (
        _authority_payload_text(envelope, "validation_status") or ""
    ).casefold()
    return (
        role == "producer_authority"
        and provenance in {"runtime_emitted", "runtime_blocker"}
        and validation_status in {"fail", "blocked"}
    )


def _is_authority_infra_code(code: str) -> bool:
    normalized = code.casefold()
    return (
        normalized.startswith("hds_")
        or normalized.startswith("legacy_migration_")
        or "authority" in normalized
        or "provenance" in normalized
        or "projection" in normalized
        or "packaging" in normalized
        or "same_input_closure" in normalized
        or "ref_identity" in normalized
        or "ref_not_cas" in normalized
        or "cas_missing" in normalized
    )


def _producer_authority_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in (
        "evidence_id",
        "artifact_ref",
        "artifact_kind",
        "authority_role",
        "provenance_kind",
        "producer_component",
        "owner",
        "runtime_event_ref",
        "cas_ref",
        "validation_status",
        "blocking_status",
    ):
        value = payload.get(key)
        if value not in (None, "", [], {}):
            summary[key] = value
    return summary


def _normalize_report_key(report_key: str) -> str:
    return report_key.strip().casefold().replace("-", "_").replace(".", "_")


def _expected_artifact_kinds(
    *,
    report_key: str,
    ref_key: str | None,
) -> set[str]:
    expected = {report_key}
    if ref_key:
        expected.add(ref_key.removesuffix("_ref"))
        expected.add(ref_key.removesuffix("_report_ref"))
    if report_key == "production_data_quality":
        expected.add("production_data_quality_report")
    if report_key.startswith("continuous_governance_"):
        expected.add("governance_lifecycle_report")
        expected.add(f"{report_key}_report")
    return {item for item in expected if item}


def _schema_matches_report(
    *,
    schema_name: str | None,
    report_schema: str | None,
    report_key: str,
    expected_artifact_kinds: set[str],
) -> bool:
    if schema_name is None:
        return False
    normalized_schema = _normalize_report_key(schema_name)
    if report_schema and normalized_schema == _normalize_report_key(report_schema):
        return True
    if report_key in normalized_schema:
        return True
    return any(kind and kind in normalized_schema for kind in expected_artifact_kinds)


def _phase_matches_report(
    *,
    phase: str,
    report_key: str,
    expected_artifact_kinds: set[str],
) -> bool:
    normalized_phase = _normalize_report_key(phase)
    if normalized_phase in {"quality_evidence", "authority_contract"}:
        return True
    if report_key in normalized_phase:
        return True
    return any(kind and kind in normalized_phase for kind in expected_artifact_kinds)


def _validation_status_from_report(report: Mapping[str, Any] | None) -> str | None:
    if not isinstance(report, Mapping):
        return None
    raw = _authority_payload_text(report, "status") or _authority_payload_text(
        report,
        "quality_status",
    )
    if raw is None:
        return None
    status = raw.casefold().replace("-", "_")
    if status in {"pass", "passed", "ok", "success", "completed", "match"}:
        return "pass"
    if status in {"blocked", "not_applicable"}:
        return status
    if status in {"fail", "failed", "error"}:
        return "fail"
    return None


def _runtime_event_ref_from_report(report: Mapping[str, Any] | None) -> str | None:
    if not isinstance(report, Mapping):
        return None
    for key in ("runtime_event_ref", "diagnostic_event_ref"):
        value = _authority_payload_text(report, key)
        if value:
            return value
    event = report.get("diagnostic_event")
    if isinstance(event, Mapping):
        for key in ("runtime_event_ref", "event_id"):
            value = _authority_payload_text(event, key)
            if value:
                return value
    return None


def _ownership_issue(
    code: str,
    message: str,
    *,
    expected: object,
    observed: object,
    field: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "fail",
        "status": "fail",
        "field": field,
        "message": message,
        "expected": expected,
        "observed": observed,
        "next_action": (
            "Mint a report-specific authority envelope whose artifact kind, schema, "
            "phase, validation status, and runtime event match the report it signs."
        ),
    }


def _next_action_for_root_cause(root_cause_class: AuthorityRootCauseClass) -> str:
    if root_cause_class in {"runtime_domain_failure", "runtime_owned_domain_failure"}:
        return "Repair the producer-owned domain evidence and rerun scorecard aggregation."
    if root_cause_class == "borrowed_authority_envelope":
        return (
            "Mint report-specific authority envelopes instead of borrowing authority "
            "from another artifact family."
        )
    if root_cause_class == "missing_provenance":
        return "Emit a runtime authority envelope before serious readiness closeout."
    if root_cause_class == "packaging_only_projection":
        return "Replace bundle packaging evidence with producer-owned runtime authority."
    if root_cause_class == "spoofed_provenance":
        return "Route projections through diagnostic-only surfaces, not authority gates."
    if root_cause_class == "runtime_ref_identity_failure":
        return "Reconcile runtime refs, CAS refs, output refs, and payload hashes."
    if root_cause_class == "same_input_closure_failure":
        return "Rebuild evidence from one closed same-input runtime context."
    if root_cause_class == "legacy_authority_failure":
        return "Quarantine legacy evidence or re-emit it through runtime authority."
    if root_cause_class == "schema_contract_failure":
        return "Emit a scorecard-readable schema-compatible runtime artifact."
    return "Investigate authority provenance and producer ownership before closeout."


def _raise(
    code: str,
    envelope: EvidenceAuthorityEnvelope,
    message: str | None = None,
) -> None:
    raise AuthorityEnvelopeError(code, message, evidence_id=envelope.evidence_id)


__all__ = [
    "AUTHORITY_ENVELOPE_CONTRACT_NAME",
    "AUTHORITY_ENVELOPE_CONTRACT_VERSION",
    "DEFAULT_AUTHORITY_ENVELOPE_SCHEMA_PATH",
    "EVIDENCE_AUTHORITY_ENVELOPE_SCHEMA_ID",
    "SERIOUS_EXECUTION_PROFILES",
    "AuthorityEnvelopeError",
    "AuthorityEnvelopeViolation",
    "AuthorityFailureClassification",
    "AuthorityRole",
    "AuthorityRootCauseClass",
    "BlockingStatus",
    "EvidenceAuthorityEnvelope",
    "EvidenceClass",
    "GovernanceMetadata",
    "ProducerIdentity",
    "ProvenanceKind",
    "SameInputClosure",
    "SameInputClosureStatus",
    "ValidationStatus",
    "assert_authority_bearing",
    "assert_authority_purpose_allowed",
    "assert_capability_binding_purpose_allowed",
    "assert_runtime_emitted",
    "assert_same_input_closure",
    "authority_envelope_json_schema",
    "authority_envelope_ownership_issues",
    "authority_purpose_blockers",
    "capability_binding_purpose_blockers",
    "classify_authority_failure",
    "classify_authority_role",
    "deserialize_authority_envelope",
    "serialize_authority_envelope",
    "write_authority_envelope_json_schema",
]
