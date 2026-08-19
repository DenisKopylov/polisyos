"""Evidence authority envelope contracts for honest diagnostics."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core import canon

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
ConsumedInputMemberKind = Literal[
    "source",
    "artifact",
    "environment",
    "authority_history",
    "runtime_abi",
    "loader_binding",
    "filesystem",
    "session",
]
PredicateProvenanceClass = Literal[
    "recomputed",
    "independently_reconciled",
    "consumer_asserted",
    "institutionally_supplied",
    "not_established",
]
TimeSourceConsistencyDisposition = Literal[
    "consistent",
    "inconsistent",
    "insufficient_evidence",
    "blocked_for_owner_review",
]
TimeSourceConsistencyProducerRef = Literal[
    "polisyos.runtime.http.services.temporal."
    "build_time_source_consistency_audit_projection"
]
TimeSourceConsistencyProjectionKind = Literal["time_source_consistency_audit_projection"]
TimeSourceConsistencyProjectionScope = Literal[
    "catalog_source_runtime_time_role_consistency"
]
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
TIME_SOURCE_CONSISTENCY_PRODUCER_REF: Final[TimeSourceConsistencyProducerRef] = (
    "polisyos.runtime.http.services.temporal."
    "build_time_source_consistency_audit_projection"
)
TIME_SOURCE_CONSISTENCY_PROJECTION_KIND: Final[TimeSourceConsistencyProjectionKind] = (
    "time_source_consistency_audit_projection"
)
TIME_SOURCE_CONSISTENCY_PROJECTION_SCOPE: Final[TimeSourceConsistencyProjectionScope] = (
    "catalog_source_runtime_time_role_consistency"
)
TIME_SOURCE_CONSISTENT_DISPOSITION: Final[TimeSourceConsistencyDisposition] = "consistent"
TIME_SOURCE_INCONSISTENT_DISPOSITION: Final[TimeSourceConsistencyDisposition] = "inconsistent"
TIME_SOURCE_INSUFFICIENT_EVIDENCE_DISPOSITION: Final[TimeSourceConsistencyDisposition] = (
    "insufficient_evidence"
)
TIME_SOURCE_BLOCKED_FOR_OWNER_REVIEW_DISPOSITION: Final[
    TimeSourceConsistencyDisposition
] = "blocked_for_owner_review"
_TIME_SOURCE_PRODUCER_UNDECLARED = "invalid:time_source_consistency_producer_undeclared"
_TIME_SOURCE_SCOPE_UNDECLARED = "invalid:time_source_consistency_scope_undeclared"
_TIME_SOURCE_DISPOSITION_MISSING = "invalid:time_source_consistency_disposition_missing"

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


class AuthoritySurfaceDecision(BaseModel):
    """Consumer-side authority decision for one runtime/public surface."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    surface: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    status: Literal["allowed", "blocked", "candidate_only", "downgraded"]
    authority_result: str = Field(min_length=1)
    transition_disposition: str | None = None
    authority_boundary_ref: str | None = None
    consumed_authority_boundary: bool
    may_not_use_for: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    blocking: bool
    visible_downgrade: bool
    composed_gate_inputs: list[str] = Field(default_factory=list)
    secret_pii_finding_kinds: list[str] = Field(default_factory=list)
    integrity_status: Literal["not_applicable", "verified", "failed", "missing_input"] = (
        "not_applicable"
    )
    integrity_error: str | None = None
    time_source_dispositions: list[str] = Field(default_factory=list)
    s12_issue_codes: list[str] = Field(default_factory=list)
    candidate_firewall_issue_codes: list[str] = Field(default_factory=list)


class OutcomeReplayLevelProof(BaseModel):
    """Content-bound verification record for one F16 replay level."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: Literal["A", "B", "C"]
    replay_kind: Literal[
        "deterministic_operation",
        "decision_provenance_trace",
        "rewalkable_audit_trail",
    ]
    input_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    output_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    producer_roots: list[dict[str, Any]] = Field(default_factory=list)
    status: Literal["verified", "drift"]


class OutcomeReplayProof(BaseModel):
    """Typed three-level replay proof emitted by a production outcome run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "policyos.runtime.outcome_replay_proof.v1"
    case_id: str = Field(min_length=1)
    canonicalizer_ref: str = (
        "tools.quality.validation.gy_evidence_canon.canonical_evidence_hash"
    )
    replay_levels: list[Literal["A", "B", "C"]]
    input_hashes: dict[str, str]
    output_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    producer_roots: list[dict[str, Any]] = Field(default_factory=list)
    level_proofs: list[OutcomeReplayLevelProof]

    @model_validator(mode="after")
    def _require_three_replay_levels(self) -> OutcomeReplayProof:
        if self.replay_levels != ["A", "B", "C"]:
            raise ValueError("outcome replay proof requires levels A, B, and C")
        if [item.level for item in self.level_proofs] != self.replay_levels:
            raise ValueError("level proofs must match replay_levels in order")
        if not self.input_hashes:
            raise ValueError("outcome replay proof requires content-bound inputs")
        return self


class ProductionLoopRunProof(BaseModel):
    """Typed proof of the durable HTTP control-to-WorkspaceLoop path."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_version: str = "policyos.policy_design_case.layer3_gy_loop.v1"
    run_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    http_request_id: str = Field(min_length=1)
    job_kind: str = Field(min_length=1)
    enqueued_at: str | None = None
    worker_lease_id: str | None = None
    worker_id: str | None = None
    execute_workflow_invocation_id: str = Field(
        alias="_execute_workflow_invocation_id",
        min_length=1,
    )
    workspace_loop_invocation_id: str = Field(min_length=1)
    control_store_state_transitions: list[str]
    input_artifacts: list[str]
    output_search_exit_contract_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    output_replay_proof_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    output_cas_refs: list[str]
    artifacts_index_refs: list[str]
    surface_reads_checked: list[str]
    surface_readbacks: list[dict[str, Any]] = Field(default_factory=list)
    legacy_path_disposition: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_durable_path_shape(self) -> ProductionLoopRunProof:
        if self.endpoint != "/api/v1/control/runs":
            raise ValueError("production loop proof must originate at the control runs route")
        if self.job_kind != "workflow_run":
            raise ValueError("production loop proof requires a workflow_run job")
        if self.worker_lease_id != self.worker_id or not self.worker_id:
            raise ValueError("production loop proof requires the observed worker lease")
        if (
            self.legacy_path_disposition != "routed_to_workspace_loop"
            and not self.legacy_path_disposition.startswith("blocked_")
            and "failed" not in self.control_store_state_transitions
        ):
            raise ValueError("production loop proof must use the WorkspaceLoop authority path")
        return self


def build_outcome_replay_proof(
    *,
    case_id: str,
    input_payloads: Mapping[str, Any],
    search_exit_contract: Mapping[str, Any],
    output_cas_refs: Iterable[str],
) -> OutcomeReplayProof:
    """Build the F16 A/B/C proof from run inputs and the emitted exit contract."""

    from polisyos.pdc import gy_content_hash

    contract = dict(search_exit_contract)
    ledger = contract.get("search_ledger")
    ledger = dict(ledger) if isinstance(ledger, Mapping) else {}
    incompleteness = contract.get("incompleteness_record")
    incompleteness = (
        dict(incompleteness) if isinstance(incompleteness, Mapping) else {}
    )
    input_hashes = {
        str(ref): gy_content_hash(payload)
        for ref, payload in sorted(input_payloads.items(), key=lambda item: str(item[0]))
    }
    producer_roots = _outcome_producer_roots(contract, input_payloads)
    deterministic_input = {
        "input_hashes": input_hashes,
        "invocations": ledger.get("invocations") or [],
    }
    deterministic_output = {
        "output_artifacts": contract.get("output_artifacts") or [],
        "terminal_state": contract.get("terminal_state") or {},
    }
    trace_input = {
        "events": ledger.get("events") or [],
        "applicability_results": ledger.get("applicability_results") or [],
    }
    trace_output = {
        "terminal_state": contract.get("terminal_state") or {},
        "incompleteness_record": incompleteness,
    }
    audit_input = {
        "producer_roots": producer_roots,
        "output_cas_refs": list(output_cas_refs),
    }
    output_hash = gy_content_hash(contract)
    return OutcomeReplayProof(
        case_id=case_id,
        replay_levels=["A", "B", "C"],
        input_hashes=input_hashes,
        output_hash=output_hash,
        producer_roots=producer_roots,
        level_proofs=[
            OutcomeReplayLevelProof(
                level="A",
                replay_kind="deterministic_operation",
                input_hash=gy_content_hash(deterministic_input),
                output_hash=gy_content_hash(deterministic_output),
                producer_roots=producer_roots,
                status="verified",
            ),
            OutcomeReplayLevelProof(
                level="B",
                replay_kind="decision_provenance_trace",
                input_hash=gy_content_hash(trace_input),
                output_hash=gy_content_hash(trace_output),
                producer_roots=producer_roots,
                status="verified",
            ),
            OutcomeReplayLevelProof(
                level="C",
                replay_kind="rewalkable_audit_trail",
                input_hash=gy_content_hash(audit_input),
                output_hash=output_hash,
                producer_roots=producer_roots,
                status="verified",
            ),
        ],
    )


def _outcome_producer_roots(
    contract: Mapping[str, Any],
    input_payloads: Mapping[str, Any],
) -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    envelopes = contract.get("artifact_envelopes")
    if isinstance(envelopes, list):
        for envelope in envelopes:
            if not isinstance(envelope, Mapping):
                continue
            for root in envelope.get("producer_roots") or []:
                if isinstance(root, Mapping):
                    roots.append(dict(root))
    for payload in input_payloads.values():
        if not isinstance(payload, Mapping):
            continue
        comparison = payload.get("provisional_comparison")
        if not isinstance(comparison, Mapping):
            continue
        for root in comparison.get("changed_producer_roots") or []:
            if isinstance(root, Mapping):
                roots.append(dict(root))
    deduped: dict[str, dict[str, Any]] = {}
    for root in roots:
        key = json.dumps(root, sort_keys=True, separators=(",", ":"), default=str)
        deduped.setdefault(key, root)
    return list(deduped.values())


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


class ConsumedInputMember(BaseModel):
    """One declared and resolved authority input consumed by a runtime owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    member_id: str = Field(min_length=1)
    member_kind: ConsumedInputMemberKind
    declared_identity: str = Field(min_length=1)
    resolved_identity: str | None = None
    predicate_class: PredicateProvenanceClass
    decisive: bool = True

    @field_validator("member_id", "declared_identity", "resolved_identity")
    @classmethod
    def _strip_member_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    def membership_key(self) -> tuple[str, str]:
        """Return the stable kind-qualified member identity."""

        return (self.member_kind, self.member_id)


class SealedConsumedInputSet(BaseModel):
    """Closed consumed-input membership bound to an existing input closure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    same_input_closure: SameInputClosure
    members: tuple[ConsumedInputMember, ...]
    membership_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_resolved_membership(self) -> SealedConsumedInputSet:
        """Prevent construction of a seal that did not resolve its members."""

        _assert_closed_consumed_input_closure(self.same_input_closure)
        resolved_members = _normalise_consumed_input_members(self.members)
        if resolved_members != self.members:
            raise ValueError("consumed_input_members_not_sorted")
        expected = _consumed_input_membership_sha256(
            self.same_input_closure,
            resolved_members,
        )
        if self.membership_sha256 != expected:
            raise ValueError("consumed_input_membership_mismatch")
        return self


_UNTRUSTED_DECISIVE_PREDICATE_CLASSES = frozenset(
    {"consumer_asserted", "institutionally_supplied", "not_established"}
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


def seal_consumed_input_set(
    *,
    closure: SameInputClosure,
    members: Iterable[ConsumedInputMember | Mapping[str, Any]],
) -> SealedConsumedInputSet:
    """Resolve, sort, and content-bind the complete authority input set."""

    _assert_closed_consumed_input_closure(closure)
    resolved_members = _normalise_consumed_input_members(members)
    membership_sha256 = _consumed_input_membership_sha256(closure, resolved_members)
    return SealedConsumedInputSet(
        same_input_closure=closure,
        members=resolved_members,
        membership_sha256=membership_sha256,
    )


def assert_consumed_input_reuse(
    sealed: SealedConsumedInputSet,
    *,
    closure: SameInputClosure,
    fresh_members: Iterable[ConsumedInputMember | Mapping[str, Any]],
) -> SealedConsumedInputSet:
    """Fail closed unless a fresh complete input set exactly matches its seal."""

    _assert_closed_consumed_input_closure(closure)
    if closure.identity_tuple() != sealed.same_input_closure.identity_tuple():
        raise AuthorityEnvelopeError(
            "consumed_input_closure_mismatch",
            f"closure_id={closure.closure_id}",
        )
    resolved_members = _normalise_consumed_input_members(fresh_members)
    expected_by_key = {member.membership_key(): member for member in sealed.members}
    actual_by_key = {member.membership_key(): member for member in resolved_members}
    for key in sorted(expected_by_key.keys() - actual_by_key.keys()):
        _raise_consumed_input_error("consumed_input_member_missing", key)
    for key in sorted(actual_by_key.keys() - expected_by_key.keys()):
        _raise_consumed_input_error("consumed_input_member_extra", key)
    for key in sorted(expected_by_key):
        if actual_by_key[key] != expected_by_key[key]:
            _raise_consumed_input_error("consumed_input_member_substituted", key)
    actual_sha256 = _consumed_input_membership_sha256(closure, resolved_members)
    if actual_sha256 != sealed.membership_sha256:
        raise AuthorityEnvelopeError(
            "consumed_input_membership_mismatch",
            f"expected={sealed.membership_sha256} actual={actual_sha256}",
        )
    return sealed


def _normalise_consumed_input_members(
    members: Iterable[ConsumedInputMember | Mapping[str, Any]],
) -> tuple[ConsumedInputMember, ...]:
    """Validate decisive predicates and return exact sorted member membership."""

    by_key: dict[tuple[str, str], ConsumedInputMember] = {}
    for raw_member in members:
        member = ConsumedInputMember.model_validate(raw_member)
        key = member.membership_key()
        if key in by_key:
            _raise_consumed_input_error("consumed_input_member_duplicate", key)
        if member.resolved_identity is None:
            _raise_consumed_input_error("consumed_input_member_unresolved", key)
        if member.declared_identity != member.resolved_identity:
            _raise_consumed_input_error("consumed_input_member_substituted", key)
        if member.decisive and member.predicate_class in _UNTRUSTED_DECISIVE_PREDICATE_CLASSES:
            _raise_consumed_input_error(
                "consumed_input_decisive_predicate_untrusted",
                key,
            )
        by_key[key] = member
    return tuple(by_key[key] for key in sorted(by_key))


def _consumed_input_membership_sha256(
    closure: SameInputClosure,
    members: tuple[ConsumedInputMember, ...],
) -> str:
    """Return the canonical identity hash for one resolved input closure."""

    return canon.fingerprint(
        {
            "same_input_closure": closure.identity_tuple(),
            "members": [member.model_dump(mode="json") for member in members],
        },
        prefix=True,
    )


def _assert_closed_consumed_input_closure(closure: SameInputClosure) -> None:
    """Require the existing closure owner to have a closed content identity."""

    if closure.status != "closed" or not closure.closure_sha256:
        raise AuthorityEnvelopeError(
            "same_input_closure_not_closed",
            f"closure_id={closure.closure_id}",
        )


def _raise_consumed_input_error(code: str, key: tuple[str, str]) -> None:
    """Raise one member-named fail-closed consumed-input error."""

    member_kind, member_id = key
    raise AuthorityEnvelopeError(code, f"member={member_kind}:{member_id}")


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


def authority_surface_decision(
    payload: Mapping[str, Any] | AuthorityEnvelopeInput | None,
    *,
    surface: str,
    purpose: str | None = None,
    artifact_ref_or_route: str | None = None,
    secret_pii_scope: str | None = None,
    block_on_secret_findings: bool = True,
    artifact_store: Any | None = None,
    artifact_id: Any | None = None,
    require_cas_integrity: bool = False,
    enforce_time_source: bool = True,
    enforce_s12: bool = True,
    enforce_candidate_firewall: bool = True,
    missing_authority_disposition: Literal["block", "downgrade"] = "block",
    missing_boundary_disposition: Literal["block", "downgrade"] = "block",
) -> AuthoritySurfaceDecision:
    """Return the composed fail-closed decision for a runtime/public surface.

    This is the single egress gate for Phase 3 surfaces. It preserves the GY-B2
    transition-disposition/AuthorityBoundary check and AND-composes the F2/F3
    admission inputs: secret/PII scan, CAS integrity, time/source envelope
    disposition, S12 dereference status, and candidate firewall.
    """

    authority_payload = _surface_authority_payload(
        payload,
        artifact_store=artifact_store,
        artifact_id=artifact_id,
    )
    base = _authority_boundary_surface_decision(
        authority_payload,
        surface=surface,
        purpose=purpose,
        missing_authority_disposition=missing_authority_disposition,
        missing_boundary_disposition=missing_boundary_disposition,
    )
    carrier = _authority_payload(authority_payload)
    gate_inputs: list[str] = ["authority_boundary"]
    blocking_reasons: list[str] = []
    downgrade_reasons: list[str] = []
    secret_findings: list[str] = []
    integrity_status: Literal["not_applicable", "verified", "failed", "missing_input"] = (
        "not_applicable"
    )
    integrity_error: str | None = None
    time_dispositions: list[str] = []
    s12_issue_codes: list[str] = []
    candidate_issue_codes: list[str] = []

    if base.blocking:
        blocking_reasons.append(base.reason)
    elif base.visible_downgrade:
        downgrade_reasons.append(base.reason)

    if secret_pii_scope is not None:
        gate_inputs.append("secret_pii_scan")
        try:
            from polisyos.core import scan_secret_and_pii

            scan = scan_secret_and_pii(
                payload,
                scope=secret_pii_scope,
                artifact_ref_or_route=artifact_ref_or_route or f"{surface}:unknown",
                redact=False,
                block_on_findings=block_on_secret_findings,
            )
        except Exception as exc:  # pragma: no cover - exercised through route fail-closed tests.
            secret_findings = ["scan_failed_closed"]
            blocking_reasons.append("secret_pii_scan_failed_closed")
            integrity_error = str(exc)
        else:
            secret_findings = list(scan.finding_kinds)
            if scan.has_findings:
                if block_on_secret_findings:
                    blocking_reasons.append("secret_pii_surface_blocked")
                else:
                    downgrade_reasons.append("secret_pii_redacted")

    if require_cas_integrity or artifact_store is not None or artifact_id is not None:
        gate_inputs.append("cas_integrity")
        if artifact_store is None or artifact_id is None:
            integrity_status = "missing_input"
            blocking_reasons.append("cas_integrity_input_missing")
        else:
            try:
                verification = artifact_store.verify(artifact_id)
            except Exception as exc:  # pragma: no cover - fail-closed guard.
                integrity_status = "failed"
                integrity_error = str(exc)
                blocking_reasons.append("cas_integrity_verify_failed_closed")
            else:
                if getattr(verification, "ok", False):
                    integrity_status = "verified"
                else:
                    integrity_status = "failed"
                    integrity_error = str(getattr(verification, "error", "") or "verify_failed")
                    blocking_reasons.append("cas_integrity_verify_failed")

    if enforce_time_source:
        gate_inputs.append("time_source_envelope")
        time_dispositions = _time_source_dispositions(payload)
        for disposition in time_dispositions:
            normalized = disposition.strip().casefold()
            if normalized in {
                TIME_SOURCE_INCONSISTENT_DISPOSITION,
                TIME_SOURCE_BLOCKED_FOR_OWNER_REVIEW_DISPOSITION,
            }:
                blocking_reasons.append("time_source_envelope_blocked")
            elif normalized and normalized != TIME_SOURCE_CONSISTENT_DISPOSITION:
                downgrade_reasons.append("time_source_envelope_obligation")

    if enforce_s12:
        gate_inputs.append("s12_dereference")
        s12_issue_codes = _s12_dereference_issue_codes(payload)
        if s12_issue_codes:
            downgrade_reasons.append("s12_reference_candidate_only")

    if enforce_candidate_firewall:
        gate_inputs.append("candidate_firewall")
        try:
            from polisyos.runtime.quality.candidate_firewall import (
                candidate_firewall_issues_for_payload,
            )

            issues = candidate_firewall_issues_for_payload(
                carrier,
                surface=surface,
            )
        except Exception as exc:  # pragma: no cover - fail-closed guard.
            candidate_issue_codes = ["candidate_firewall_failed_closed"]
            blocking_reasons.append("candidate_firewall_failed_closed")
            integrity_error = str(exc)
        else:
            candidate_issue_codes = [
                str(issue.get("code") or "candidate_firewall_blocked")
                for issue in issues
            ]
            if candidate_issue_codes:
                blocking_reasons.append("candidate_firewall_blocked")

    status = base.status
    reason = base.reason
    blocking = base.blocking
    visible_downgrade = base.visible_downgrade
    if blocking_reasons:
        status = "blocked"
        reason = blocking_reasons[0]
        blocking = True
        visible_downgrade = True
    elif downgrade_reasons:
        status = "downgraded" if base.status == "allowed" else base.status
        reason = downgrade_reasons[0]
        blocking = False
        visible_downgrade = True

    return AuthoritySurfaceDecision(
        surface=base.surface,
        purpose=base.purpose,
        status=status,
        authority_result=base.authority_result,
        transition_disposition=base.transition_disposition,
        authority_boundary_ref=base.authority_boundary_ref,
        consumed_authority_boundary=base.consumed_authority_boundary,
        may_not_use_for=list(base.may_not_use_for),
        reason=reason,
        blocking=blocking,
        visible_downgrade=visible_downgrade,
        composed_gate_inputs=list(dict.fromkeys(gate_inputs)),
        secret_pii_finding_kinds=sorted(set(secret_findings)),
        integrity_status=integrity_status,
        integrity_error=integrity_error,
        time_source_dispositions=sorted(set(time_dispositions)),
        s12_issue_codes=sorted(set(s12_issue_codes)),
        candidate_firewall_issue_codes=sorted(set(candidate_issue_codes)),
    )


def _authority_boundary_surface_decision(
    payload: Mapping[str, Any] | AuthorityEnvelopeInput | None,
    *,
    surface: str,
    purpose: str | None = None,
    missing_authority_disposition: Literal["block", "downgrade"] = "block",
    missing_boundary_disposition: Literal["block", "downgrade"] = "block",
) -> AuthoritySurfaceDecision:
    """Return the fail-closed authority decision for a runtime/public surface.

    The helper consumes GY-B2 transition disposition (`legacy_path_disposition` /
    `authority_path`) and the existing `AuthorityBoundary`; it does not introduce
    a second authority flag.
    """

    carrier = _authority_payload(payload)
    surface_name = _non_empty(surface)
    requested_purpose = _optional_text(purpose) or _default_surface_purpose(surface_name)
    surface_packet = _surface_packet_for(carrier, surface_name)
    boundary_payload = _extract_authority_boundary(carrier, surface_packet)
    transition_disposition = _transition_disposition(carrier, surface_packet)
    authority_result = (
        _authority_payload_text(surface_packet, "authority_result")
        or _authority_payload_text(surface_packet, "status")
        or _authority_payload_text(carrier, "authority_result")
        or "not_applicable"
    )
    has_authority_signal = _has_authority_surface_signal(
        carrier,
        surface_packet=surface_packet,
        transition_disposition=transition_disposition,
        authority_result=authority_result,
    )
    if not has_authority_signal:
        blocking = missing_authority_disposition == "block"
        return AuthoritySurfaceDecision(
            surface=surface_name,
            purpose=requested_purpose,
            status="blocked" if blocking else "downgraded",
            authority_result="not_applicable",
            transition_disposition=None,
            authority_boundary_ref=None,
            consumed_authority_boundary=False,
            may_not_use_for=[],
            reason="authority_surface_signal_missing",
            blocking=blocking,
            visible_downgrade=True,
        )

    if not boundary_payload:
        blocking = missing_boundary_disposition == "block"
        return AuthoritySurfaceDecision(
            surface=surface_name,
            purpose=requested_purpose,
            status="blocked" if blocking else "downgraded",
            authority_result=authority_result,
            transition_disposition=transition_disposition,
            authority_boundary_ref=None,
            consumed_authority_boundary=False,
            may_not_use_for=[],
            reason="authority_boundary_missing",
            blocking=blocking,
            visible_downgrade=True,
        )

    boundary_dump = _validated_authority_boundary_payload(boundary_payload)
    if boundary_dump is None:
        return AuthoritySurfaceDecision(
            surface=surface_name,
            purpose=requested_purpose,
            status="blocked",
            authority_result=authority_result,
            transition_disposition=transition_disposition,
            authority_boundary_ref=_authority_payload_text(boundary_payload, "boundary_id"),
            consumed_authority_boundary=False,
            may_not_use_for=list(_authority_payload_sequence(boundary_payload, "may_not_use_for")),
            reason="authority_boundary_invalid",
            blocking=True,
            visible_downgrade=True,
        )

    may_not_use_for = list(_authority_payload_sequence(boundary_dump, "may_not_use_for"))
    boundary_ref = _authority_payload_text(boundary_dump, "boundary_id")
    blockers = authority_purpose_blockers(boundary_dump, requested_purpose)
    if _is_blocked_surface_result(authority_result, transition_disposition):
        return AuthoritySurfaceDecision(
            surface=surface_name,
            purpose=requested_purpose,
            status="blocked",
            authority_result=authority_result,
            transition_disposition=transition_disposition,
            authority_boundary_ref=boundary_ref,
            consumed_authority_boundary=True,
            may_not_use_for=may_not_use_for,
            reason="workflow_failure_or_blocked_disposition",
            blocking=True,
            visible_downgrade=True,
        )
    if _is_candidate_surface_result(authority_result, transition_disposition):
        return AuthoritySurfaceDecision(
            surface=surface_name,
            purpose=requested_purpose,
            status="candidate_only",
            authority_result=authority_result,
            transition_disposition=transition_disposition,
            authority_boundary_ref=boundary_ref,
            consumed_authority_boundary=True,
            may_not_use_for=may_not_use_for,
            reason="candidate_or_legacy_shadow_disposition",
            blocking=False,
            visible_downgrade=True,
        )
    if blockers:
        return AuthoritySurfaceDecision(
            surface=surface_name,
            purpose=requested_purpose,
            status="downgraded",
            authority_result=authority_result,
            transition_disposition=transition_disposition,
            authority_boundary_ref=boundary_ref,
            consumed_authority_boundary=True,
            may_not_use_for=may_not_use_for,
            reason=blockers[0],
            blocking=False,
            visible_downgrade=True,
        )
    return AuthoritySurfaceDecision(
        surface=surface_name,
        purpose=requested_purpose,
        status="allowed",
        authority_result=authority_result,
        transition_disposition=transition_disposition,
        authority_boundary_ref=boundary_ref,
        consumed_authority_boundary=True,
        may_not_use_for=may_not_use_for,
        reason="authority_boundary_allows_surface_purpose",
        blocking=False,
        visible_downgrade=False,
    )


def _surface_authority_payload(
    payload: object,
    *,
    artifact_store: Any | None,
    artifact_id: Any | None,
) -> object:
    """Resolve the authority carrier for a surface without replacing scan bytes."""

    carrier = _authority_payload(payload)
    if _has_payload_authority_signal(carrier):
        return payload
    if artifact_store is None or artifact_id is None:
        return payload

    try:
        stored_payload = canon.from_canonical_bytes(artifact_store.get_bytes(artifact_id))
    except Exception:
        stored_payload = None
    if isinstance(stored_payload, Mapping) and _has_payload_authority_signal(stored_payload):
        return stored_payload

    try:
        manifest = artifact_store.get_manifest(artifact_id)
    except Exception:
        return payload
    authority = getattr(manifest, "authority", None)
    envelope_ref = getattr(authority, "authority_envelope_ref", None)
    if not envelope_ref:
        return payload
    try:
        envelope_bytes = artifact_store.get_bytes(envelope_ref)
        envelope_payload = canon.from_canonical_bytes(envelope_bytes)
    except Exception:
        return payload
    if isinstance(envelope_payload, Mapping):
        if _has_payload_authority_signal(envelope_payload):
            return envelope_payload
        if _validated_authority_boundary_payload(envelope_payload) is not None:
            return {"authority_boundary": dict(envelope_payload)}
    return payload


def _has_payload_authority_signal(payload: Mapping[str, Any]) -> bool:
    return any(
        key in payload
        for key in (
            "authority_surface_packet",
            "authority_boundary",
            "surface_authority",
            "public_packet",
            "failure",
            "runtime_state",
            "legacy_path_disposition",
            "authority_path",
            "authority_result",
        )
    )


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


def _default_surface_purpose(surface: str) -> str:
    purposes = {
        "run": "runtime_closeout_authority",
        "run_status": "runtime_closeout_authority",
        "artifact": "runtime_closeout_authority",
        "lineage": "runtime_closeout_authority",
        "export": "publication",
        "dashboard": "dashboard_display",
        "public_packet": "publication",
    }
    return purposes.get(surface, "runtime_closeout_authority")


def _surface_packet_for(
    carrier: Mapping[str, Any],
    surface: str,
) -> Mapping[str, Any]:
    packet = carrier.get("authority_surface_packet")
    if isinstance(packet, Mapping):
        surfaces = packet.get("surfaces")
        if isinstance(surfaces, Mapping):
            surface_packet = surfaces.get(surface)
            if isinstance(surface_packet, Mapping):
                return surface_packet
    surface_authority = carrier.get("surface_authority")
    if isinstance(surface_authority, Mapping):
        surface_packet = surface_authority.get(surface)
        if isinstance(surface_packet, Mapping):
            return surface_packet
    for projection_key in (
        f"{surface}_projection",
        "projection" if surface == "public_packet" else "",
    ):
        if not projection_key:
            continue
        surface_packet = carrier.get(projection_key)
        if isinstance(surface_packet, Mapping):
            return surface_packet
    return {}


def _extract_authority_boundary(
    carrier: Mapping[str, Any],
    surface_packet: Mapping[str, Any],
) -> Mapping[str, Any]:
    for candidate in (
        surface_packet.get("boundary"),
        carrier.get("authority_boundary"),
    ):
        if isinstance(candidate, Mapping):
            return candidate
    public_packet = carrier.get("public_packet")
    if isinstance(public_packet, Mapping):
        boundary = public_packet.get("authority_boundary")
        if isinstance(boundary, Mapping):
            return boundary
    search_exit_contract = carrier.get("search_exit_contract")
    if isinstance(search_exit_contract, Mapping):
        boundary = search_exit_contract.get("authority_boundary")
        if isinstance(boundary, Mapping):
            return boundary
        envelopes = search_exit_contract.get("artifact_envelopes")
        if isinstance(envelopes, Iterable) and not isinstance(envelopes, str | bytes):
            for envelope in envelopes:
                if not isinstance(envelope, Mapping):
                    continue
                envelope_boundary = envelope.get("authority_boundary")
                if isinstance(envelope_boundary, Mapping):
                    return envelope_boundary
    packet = carrier.get("authority_surface_packet")
    if isinstance(packet, Mapping):
        boundary = packet.get("boundary")
        if isinstance(boundary, Mapping):
            return boundary
    return {}


def _validated_authority_boundary_payload(
    payload: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    required_text = ("source_authority", "posture")
    if any(_authority_payload_text(payload, key) is None for key in required_text):
        return None
    for key in ("authoritative_for", "may_not_use_for", "rule_version_refs"):
        if not _authority_payload_sequence(payload, key):
            return None
    return dict(payload)


def _transition_disposition(
    carrier: Mapping[str, Any],
    surface_packet: Mapping[str, Any],
) -> str | None:
    return (
        _authority_payload_text(surface_packet, "transition_disposition")
        or _authority_payload_text(surface_packet, "legacy_path_disposition")
        or _authority_payload_text(carrier, "legacy_path_disposition")
        or _authority_payload_text(carrier, "authority_path")
    )


def _has_authority_surface_signal(
    carrier: Mapping[str, Any],
    *,
    surface_packet: Mapping[str, Any],
    transition_disposition: str | None,
    authority_result: str,
) -> bool:
    if surface_packet:
        return True
    if transition_disposition is not None:
        return True
    if authority_result != "not_applicable":
        return True
    return any(
        key in carrier
        for key in (
            "authority_surface_packet",
            "authority_boundary",
            "surface_authority",
            "public_packet",
            "failure",
            "runtime_state",
        )
    )


def _time_source_dispositions(value: object) -> list[str]:
    dispositions: list[str] = []
    _collect_time_source_dispositions(value, dispositions)
    return list(dict.fromkeys(dispositions))


def _collect_time_source_dispositions(value: object, dispositions: list[str]) -> None:
    if isinstance(value, bytes):
        try:
            loaded = json.loads(value)
        except (TypeError, json.JSONDecodeError, UnicodeDecodeError):
            return
        _collect_time_source_dispositions(loaded, dispositions)
        return
    if isinstance(value, str):
        return
    if isinstance(value, Mapping):
        if value.get("projection_kind") == TIME_SOURCE_CONSISTENCY_PROJECTION_KIND:
            if value.get("producer_ref") != TIME_SOURCE_CONSISTENCY_PRODUCER_REF:
                dispositions.append(_TIME_SOURCE_PRODUCER_UNDECLARED)
                return
            if value.get("projection_scope") != TIME_SOURCE_CONSISTENCY_PROJECTION_SCOPE:
                dispositions.append(_TIME_SOURCE_SCOPE_UNDECLARED)
                return
            disposition = value.get("mismatch_disposition")
            if isinstance(disposition, str) and disposition.strip():
                dispositions.append(disposition.strip())
            else:
                dispositions.append(_TIME_SOURCE_DISPOSITION_MISSING)
            return
        for item in value.values():
            _collect_time_source_dispositions(item, dispositions)
        return
    if isinstance(value, Iterable):
        for item in value:
            _collect_time_source_dispositions(item, dispositions)


def _s12_dereference_issue_codes(value: object) -> list[str]:
    issue_codes: list[str] = []
    raw_refs: list[str] = []
    explicit_resolution_seen = _collect_s12_dereference_issues(
        value,
        issue_codes=issue_codes,
        raw_refs=raw_refs,
    )
    if raw_refs and not explicit_resolution_seen:
        issue_codes.extend("s12_ref_non_dereferenceable" for _ in raw_refs)
    return list(dict.fromkeys(issue_codes))


def _collect_s12_dereference_issues(
    value: object,
    *,
    issue_codes: list[str],
    raw_refs: list[str],
) -> bool:
    explicit_resolution_seen = False
    if isinstance(value, bytes):
        try:
            loaded = json.loads(value)
        except (TypeError, json.JSONDecodeError, UnicodeDecodeError):
            return False
        return _collect_s12_dereference_issues(
            loaded,
            issue_codes=issue_codes,
            raw_refs=raw_refs,
        )
    if isinstance(value, str):
        if value.startswith("voi://") or value.startswith("s12://"):
            raw_refs.append(value)
        return False
    if isinstance(value, Mapping):
        candidate_refs = value.get("candidate_only_s12_refs")
        if isinstance(candidate_refs, Iterable) and not isinstance(candidate_refs, str | bytes):
            for ref in candidate_refs:
                text = str(ref).strip()
                if text:
                    issue_codes.append("s12_ref_non_dereferenceable")
                    raw_refs.append(text)
        disposition = value.get("disposition")
        if isinstance(disposition, str) and disposition == "candidate_only":
            explicit_resolution_seen = True
            issue_codes.append("s12_ref_non_dereferenceable")
        if value.get("resolved") is False:
            explicit_resolution_seen = True
            issue_codes.append("s12_ref_non_dereferenceable")
        raw_issue_codes = value.get("issue_codes")
        if isinstance(raw_issue_codes, Iterable) and not isinstance(
            raw_issue_codes,
            str | bytes,
        ):
            for code in raw_issue_codes:
                text = str(code).strip()
                if text:
                    issue_codes.append(text)
        for key, item in value.items():
            if key in {
                "s12_ref_dereference",
                "s12_ref_resolutions",
                "authorial_negative_fixture",
            }:
                explicit_resolution_seen = True
            if _collect_s12_dereference_issues(
                item,
                issue_codes=issue_codes,
                raw_refs=raw_refs,
            ):
                explicit_resolution_seen = True
        return explicit_resolution_seen
    if isinstance(value, Iterable):
        for item in value:
            if _collect_s12_dereference_issues(
                item,
                issue_codes=issue_codes,
                raw_refs=raw_refs,
            ):
                explicit_resolution_seen = True
    return explicit_resolution_seen


def _is_blocked_surface_result(
    authority_result: str,
    transition_disposition: str | None,
) -> bool:
    normalized_result = authority_result.strip().casefold()
    normalized_disposition = (transition_disposition or "").strip().casefold()
    return (
        normalized_result in {"blocked", "repair_required"}
        or normalized_disposition.startswith("blocked_")
        or normalized_disposition == "workflow_failure"
    )


def _is_candidate_surface_result(
    authority_result: str,
    transition_disposition: str | None,
) -> bool:
    normalized_result = authority_result.strip().casefold()
    normalized_disposition = (transition_disposition or "").strip().casefold()
    return (
        normalized_result in {"candidate_only", "legacy_shadow"}
        or normalized_disposition in {"legacy_shadow", "candidate_only_ring2_withheld"}
        or normalized_disposition.endswith("_candidate_only")
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
    "TIME_SOURCE_BLOCKED_FOR_OWNER_REVIEW_DISPOSITION",
    "TIME_SOURCE_CONSISTENCY_PRODUCER_REF",
    "TIME_SOURCE_CONSISTENCY_PROJECTION_KIND",
    "TIME_SOURCE_CONSISTENCY_PROJECTION_SCOPE",
    "TIME_SOURCE_CONSISTENT_DISPOSITION",
    "TIME_SOURCE_INCONSISTENT_DISPOSITION",
    "TIME_SOURCE_INSUFFICIENT_EVIDENCE_DISPOSITION",
    "AuthorityEnvelopeError",
    "AuthorityEnvelopeViolation",
    "AuthorityFailureClassification",
    "AuthorityRole",
    "AuthorityRootCauseClass",
    "AuthoritySurfaceDecision",
    "BlockingStatus",
    "ConsumedInputMember",
    "ConsumedInputMemberKind",
    "EvidenceAuthorityEnvelope",
    "EvidenceClass",
    "GovernanceMetadata",
    "OutcomeReplayLevelProof",
    "OutcomeReplayProof",
    "PredicateProvenanceClass",
    "ProducerIdentity",
    "ProductionLoopRunProof",
    "ProvenanceKind",
    "SameInputClosure",
    "SameInputClosureStatus",
    "SealedConsumedInputSet",
    "TimeSourceConsistencyDisposition",
    "TimeSourceConsistencyProducerRef",
    "TimeSourceConsistencyProjectionKind",
    "TimeSourceConsistencyProjectionScope",
    "ValidationStatus",
    "assert_authority_bearing",
    "assert_authority_purpose_allowed",
    "assert_capability_binding_purpose_allowed",
    "assert_consumed_input_reuse",
    "assert_runtime_emitted",
    "assert_same_input_closure",
    "authority_envelope_json_schema",
    "authority_envelope_ownership_issues",
    "authority_purpose_blockers",
    "authority_surface_decision",
    "build_outcome_replay_proof",
    "capability_binding_purpose_blockers",
    "classify_authority_failure",
    "classify_authority_role",
    "deserialize_authority_envelope",
    "seal_consumed_input_set",
    "serialize_authority_envelope",
    "write_authority_envelope_json_schema",
]
