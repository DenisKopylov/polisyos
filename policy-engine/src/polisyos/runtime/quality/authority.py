"""Evidence authority envelope contracts for honest diagnostics."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol, cast, overload

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StrictStr,
    ValidationError,
    field_validator,
    model_serializer,
    model_validator,
)

from polisyos.common.canonical_profile import require_declared_profile
from polisyos.core import artifacts as core_artifacts
from polisyos.core import canon
from polisyos.core.artifacts import read_core_json_artifact, read_core_manifest_profile
from polisyos.core.security import (
    SECURITY_ASSURANCE_ARTIFACT_KIND,
    SECURITY_ASSURANCE_ARTIFACT_SCHEMA_NAME,
)
from polisyos.runtime.quality.evaluation_safety import (
    EvalSafetyMetricsProjection,
    evaluation_safety_metrics_projection_identity,
)
from polisyos.runtime.quality.report_registry import (
    _RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY,
    _parse_runtime_quality_report_publication_basis,
    _runtime_quality_report_publication_view,
    _runtime_quality_report_writer_payload,
    runtime_quality_report_owner_contract,
    runtime_quality_report_owner_marker,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.runtime.http.services.control.artifacts import (
        AuthorityArtifactIdentityContext,
    )


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
ClosureIdentityDomain = Literal["cas", "owner_value", "null"]
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
    "polisyos.runtime.http.services.temporal.build_time_source_consistency_audit_projection"
]
TimeSourceConsistencyProjectionKind = Literal["time_source_consistency_audit_projection"]
TimeSourceConsistencyProjectionScope = Literal["catalog_source_runtime_time_role_consistency"]
ValidationStatus = Literal["pass", "fail", "blocked", "not_applicable"]
BlockingStatus = Literal["non_blocking", "blocking", "non_overridable"]
_EvalSafetyManifestIdentityState = Literal["exact", "other", "unresolved"]
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

AUTHORITY_ENVELOPE_CONTRACT_NAME = core_artifacts.AUTHORITY_ENVELOPE_SCHEMA_NAME
AUTHORITY_ENVELOPE_CONTRACT_VERSION = core_artifacts.AUTHORITY_ENVELOPE_SCHEMA_VERSION
EVIDENCE_AUTHORITY_ENVELOPE_SCHEMA_ID = (
    "https://schemas.policyos.local/runtime_quality/evidence_authority_envelope_v2.schema.json"
)
DEFAULT_AUTHORITY_ENVELOPE_SCHEMA_PATH = (
    Path(__file__).resolve().parents[4]
    / "schemas/runtime_quality/evidence_authority_envelope_v2.schema.json"
)
TIME_SOURCE_CONSISTENCY_PRODUCER_REF: Final[TimeSourceConsistencyProducerRef] = (
    "polisyos.runtime.http.services.temporal.build_time_source_consistency_audit_projection"
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
TIME_SOURCE_BLOCKED_FOR_OWNER_REVIEW_DISPOSITION: Final[TimeSourceConsistencyDisposition] = (
    "blocked_for_owner_review"
)
TIME_SOURCE_CONSISTENCY_ROLE_FIELDS: Final[tuple[str, ...]] = (
    "catalog_watermark",
    "source_observed_at",
    "source_published_at",
    "source_updated_at",
    "ingested_at",
    "effective_time",
    "legal_valid_time",
    "transaction_time",
    "as_of_time",
    "replay_time",
    "run_started_at",
    "run_finished_at",
    "node_started_at",
    "node_finished_at",
    "retention_or_expiry",
)
_TIME_SOURCE_PRODUCER_UNDECLARED = "invalid:time_source_consistency_producer_undeclared"
_TIME_SOURCE_SCOPE_UNDECLARED = "invalid:time_source_consistency_scope_undeclared"
_TIME_SOURCE_DISPOSITION_MISSING = "invalid:time_source_consistency_disposition_missing"
_TIME_SOURCE_CONTRACT_INVALID = "invalid:time_source_consistency_contract_invalid"

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


class _ArtifactSurfaceStore(Protocol):
    def get_bytes(self, artifact_id: object) -> bytes: ...

    def get_manifest(self, artifact_id: object) -> object: ...

    def verify(self, artifact_id: object) -> object: ...


class TimeSourceConsistencyAuditProjection(BaseModel):
    """Authority-owned contract for one projection-only time-role consistency audit."""

    model_config = ConfigDict(extra="forbid")

    projection_kind: TimeSourceConsistencyProjectionKind = TIME_SOURCE_CONSISTENCY_PROJECTION_KIND
    producer_ref: TimeSourceConsistencyProducerRef = TIME_SOURCE_CONSISTENCY_PRODUCER_REF
    projection_scope: TimeSourceConsistencyProjectionScope = (
        TIME_SOURCE_CONSISTENCY_PROJECTION_SCOPE
    )
    catalog_watermark: str | None = None
    source_observed_at: str | None = None
    source_published_at: str | None = None
    source_updated_at: str | None = None
    ingested_at: str | None = None
    effective_time: str | None = None
    legal_valid_time: str | None = None
    transaction_time: str | None = None
    as_of_time: str | None = None
    replay_time: str | None = None
    run_started_at: str | None = None
    run_finished_at: str | None = None
    node_started_at: str | None = None
    node_finished_at: str | None = None
    retention_or_expiry: str | None = None
    mismatch_disposition: TimeSourceConsistencyDisposition

    @model_validator(mode="after")
    def _require_recomputed_disposition(self) -> TimeSourceConsistencyAuditProjection:
        role_values = {field: getattr(self, field) for field in TIME_SOURCE_CONSISTENCY_ROLE_FIELDS}
        recomputed = resolve_time_source_consistency_disposition(role_values)
        if self.mismatch_disposition != recomputed:
            raise ValueError("time-source disposition does not match authority-owned recomputation")
        return self


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


class AuthoritySurfaceContributor(BaseModel):
    """One source-specific authority decision used by a composed surface gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    basis: Literal["base_surface", "selected_manifest"]
    status: Literal["allowed", "blocked", "candidate_only", "downgraded"]
    authority_result: str = Field(min_length=1)
    transition_disposition: str | None = None
    authority_boundary_ref: str | None = None
    consumed_authority_boundary: bool
    may_not_use_for: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    blocking: bool
    visible_downgrade: bool
    resolution_error: str | None = None


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
    authority_contributors: list[AuthoritySurfaceContributor] = Field(default_factory=list)


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


class OutputCASManifestProfile(BaseModel):
    """Bind one emitted PDC envelope to its exact selected CAS manifest view."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    envelope_artifact_id: StrictStr = Field(min_length=1)
    envelope_artifact_type: StrictStr = Field(min_length=1, max_length=80)
    payload_artifact_id: core_artifacts.ArtifactID
    payload_schema_ref: StrictStr = Field(min_length=1, max_length=200)
    manifest_profile_sha256: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")


_OUTCOME_REPLAY_V1 = "policyos.runtime.outcome_replay_proof.v1"
_OUTCOME_REPLAY_V2 = "policyos.runtime.outcome_replay_proof.v2"
_PRODUCTION_LOOP_PROOF_V1 = "policyos.policy_design_case.layer3_gy_loop.v1"
_PRODUCTION_LOOP_PROOF_V2 = "policyos.policy_design_case.layer3_gy_loop.v2"


class OutcomeReplayProof(BaseModel):
    """Typed three-level replay proof emitted by a production outcome run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[_OUTCOME_REPLAY_V1, _OUTCOME_REPLAY_V2] = _OUTCOME_REPLAY_V2
    case_id: str = Field(min_length=1)
    canonicalizer_ref: str = "tools.quality.validation.gy_evidence_canon.canonical_evidence_hash"
    replay_levels: list[Literal["A", "B", "C"]]
    input_hashes: dict[str, str]
    output_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    producer_roots: list[dict[str, Any]] = Field(default_factory=list)
    output_cas_manifest_profiles: list[OutputCASManifestProfile] = Field(default_factory=list)
    level_proofs: list[OutcomeReplayLevelProof]

    @model_validator(mode="after")
    def _require_three_replay_levels(self) -> OutcomeReplayProof:
        if self.replay_levels != ["A", "B", "C"]:
            raise ValueError("outcome replay proof requires levels A, B, and C")
        if [item.level for item in self.level_proofs] != self.replay_levels:
            raise ValueError("level proofs must match replay_levels in order")
        if not self.input_hashes:
            raise ValueError("outcome replay proof requires content-bound inputs")
        if self.schema_version == _OUTCOME_REPLAY_V1 and self.output_cas_manifest_profiles:
            raise ValueError("legacy replay proof cannot claim selected CAS profiles")
        identities = [
            (item.envelope_artifact_id, item.envelope_artifact_type)
            for item in self.output_cas_manifest_profiles
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("replay proof selected CAS profile entries must be unique")
        return self


class ProductionLoopRunProof(BaseModel):
    """Typed proof of the durable HTTP control-to-WorkspaceLoop path."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_version: Literal[_PRODUCTION_LOOP_PROOF_V1, _PRODUCTION_LOOP_PROOF_V2] = (
        _PRODUCTION_LOOP_PROOF_V2
    )
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
    output_cas_manifest_profiles: list[OutputCASManifestProfile] = Field(default_factory=list)
    artifacts_index_refs: list[str]
    surface_reads_checked: list[str]
    surface_readbacks: list[dict[str, Any]] = Field(default_factory=list)
    legacy_path_disposition: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_durable_path_shape(self) -> ProductionLoopRunProof:
        if self.schema_version == _PRODUCTION_LOOP_PROOF_V1 and self.output_cas_manifest_profiles:
            raise ValueError("legacy run proof cannot claim selected CAS profiles")
        profile_identities = [
            (item.envelope_artifact_id, item.envelope_artifact_type)
            for item in self.output_cas_manifest_profiles
        ]
        if len(profile_identities) != len(set(profile_identities)):
            raise ValueError("run proof selected CAS profile entries must be unique")
        output_refs = set(self.output_cas_refs)
        if any(
            str(item.payload_artifact_id) not in output_refs
            for item in self.output_cas_manifest_profiles
        ):
            raise ValueError("run proof selected CAS profile must bind a declared output ref")
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


_MEASUREMENT_ROOT_PRODUCER = "polisyos.runtime.quality.data_forge_binding.MeasurementRootProducer"
_MEASUREMENT_ROOT_PAYLOAD_KIND = "policyos.gy.measurement_root_payload"


class OutputCASManifestProfileRefusalError(ValueError):
    """Refuse a selected output profile that is absent or not Core-bound."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _resolve_output_cas_manifest_profile(
    *,
    artifact_store: object,
    payload_ref: str,
    payload_schema_ref: str,
    manifest_profile_sha256: str,
    envelope_content_hash: object,
    require_measurement_root_owner: bool,
) -> tuple[core_artifacts.ArtifactManifest, Mapping[str, Any]]:
    """Resolve one exact selected output view and bind it to its envelope."""

    from polisyos.core.artifacts import read_core_manifest_profile
    from polisyos.pdc import gy_content_hash

    try:
        artifact_id = core_artifacts.ArtifactID(payload_ref)
        manifest, _declaration = read_core_manifest_profile(
            artifact_store,
            artifact_id,
            manifest_profile_sha256=manifest_profile_sha256,
        )
        selected_ref = core_artifacts.ArtifactRef(
            artifact_id=artifact_id,
            kind=manifest.kind,
            media_type=manifest.media_type,
            manifest_profile_sha256=manifest_profile_sha256,
        )
        verification = artifact_store.verify(selected_ref)
        payload_read = read_core_json_artifact(
            artifact_store,
            selected_ref,
            manifest_profile_sha256=manifest_profile_sha256,
        )
    except (AttributeError, OSError, TypeError, ValueError, RuntimeError) as exc:
        raise OutputCASManifestProfileRefusalError(
            "selected_output_profile_core_resolution_failed"
        ) from exc

    if (
        not getattr(verification, "ok", False)
        or manifest.artifact_id != artifact_id
        or core_artifacts.artifact_manifest_profile_sha256(manifest) != manifest_profile_sha256
        or manifest.media_type != "application/json"
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != payload_schema_ref
    ):
        raise OutputCASManifestProfileRefusalError("selected_output_profile_manifest_mismatch")

    producer = manifest.producer
    if require_measurement_root_owner and (
        manifest.kind != _MEASUREMENT_ROOT_PAYLOAD_KIND
        or producer is None
        or producer.component != _MEASUREMENT_ROOT_PRODUCER
    ):
        raise OutputCASManifestProfileRefusalError(
            "measurement_root_producer_manifest_binding_mismatch"
        )
    payload = payload_read.value
    if (
        not isinstance(payload, Mapping)
        or not isinstance(envelope_content_hash, str)
        or gy_content_hash(payload) != envelope_content_hash
    ):
        raise OutputCASManifestProfileRefusalError(
            "selected_output_profile_content_binding_mismatch"
        )
    return manifest, payload


def _measurement_root_ref_matches_payload(
    root_value: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    payload_ref: str,
    payload_schema_ref: str,
) -> bool:
    """Recompute the selected MeasurementRoot projection from its CAS payload."""

    from polisyos.pdc import ArtifactRef as PDCArtifactRef

    try:
        if payload_schema_ref == "policyos.policy_design_case.layer3_gy_loop.v1":
            fixture_id = payload.get("fixture_id")
            catalog_binding_refs = payload.get("catalog_binding_refs")
            catalog_result = payload.get("catalog_result")
            distributions = payload.get("distributions")
            rows = payload.get("measurement_rows")
            producer_root_kind = payload.get("producer_root_kind")
            if (
                not isinstance(fixture_id, str)
                or not isinstance(catalog_binding_refs, list)
                or not catalog_binding_refs
                or not isinstance(catalog_binding_refs[0], str)
                or not isinstance(catalog_result, Mapping)
                or not isinstance(distributions, list)
                or not isinstance(rows, list)
                or any(
                    not isinstance(row, Mapping) or not isinstance(row.get("row_id"), str)
                    for row in rows
                )
                or not isinstance(producer_root_kind, str)
            ):
                return False
            connector_type = catalog_result.get("connector_type") or (
                str(distributions[0].get("connector_type")) if distributions else ""
            )
            normalized = "".join(char.lower() if char.isalnum() else "-" for char in fixture_id)
            slug = "-".join(part for part in normalized.split("-") if part) or "item"
            root_payload = {
                "dataset_id": catalog_binding_refs[0],
                "connector_type": connector_type,
                "producer_root_kind": producer_root_kind,
                "measurement_row_count": len(rows),
                "measurement_row_refs": [row["row_id"] for row in rows],
            }
            expected = PDCArtifactRef.from_payload(
                artifact_id=f"measurement-root-{slug}",
                artifact_type="MeasurementRoot",
                payload=root_payload,
                schema_ref=payload_schema_ref,
                uri=f"gy://slice0/{fixture_id}/measurement-root",
                version="v1",
            )
        elif payload_schema_ref == "policyos.gy.fabric_measurement_root.v2":
            if not payload_ref.startswith("sha256:"):
                return False
            expected = PDCArtifactRef.from_payload(
                artifact_id=f"measurement-root-{payload_ref.removeprefix('sha256:')}",
                artifact_type="MeasurementRoot",
                payload=dict(payload),
                schema_ref=payload_schema_ref,
                uri=f"cas://{payload_ref}",
                version="v2",
            )
        else:
            return False
        actual = PDCArtifactRef.model_validate(root_value)
    except (TypeError, ValueError, KeyError):
        return False
    return actual == expected


def declared_output_envelopes_from_contract(
    search_exit_contract: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    """Join each declared output to exactly one envelope by its complete PDC ref."""
    from polisyos.pdc import ArtifactRef as PDCArtifactRef

    outputs = search_exit_contract.get("output_artifacts")
    envelopes = search_exit_contract.get("artifact_envelopes")
    if outputs is None and envelopes == []:
        return []
    if not isinstance(outputs, list) or not isinstance(envelopes, list):
        raise OutputCASManifestProfileRefusalError("selected_output_profile_output_set_missing")

    normalized_outputs: list[dict[str, Any]] = []
    output_ids: set[str] = set()
    for output in outputs:
        try:
            normalized = PDCArtifactRef.model_validate(output).model_dump(mode="json")
        except (TypeError, ValueError) as exc:
            raise OutputCASManifestProfileRefusalError(
                "selected_output_profile_output_ref_invalid"
            ) from exc
        artifact_id = normalized["artifact_id"]
        if artifact_id in output_ids:
            raise OutputCASManifestProfileRefusalError("selected_output_profile_output_duplicate")
        output_ids.add(artifact_id)
        normalized_outputs.append(normalized)

    envelope_by_id: dict[str, list[tuple[dict[str, Any], Mapping[str, Any]]]] = {}
    for envelope in envelopes:
        if not isinstance(envelope, Mapping):
            raise OutputCASManifestProfileRefusalError("selected_output_profile_envelope_invalid")
        try:
            ref = PDCArtifactRef.model_validate(envelope.get("ref"))
        except (TypeError, ValueError) as exc:
            raise OutputCASManifestProfileRefusalError(
                "selected_output_profile_envelope_ref_invalid"
            ) from exc
        envelope_by_id.setdefault(ref.artifact_id, []).append(
            (ref.model_dump(mode="json"), envelope)
        )

    selected: list[Mapping[str, Any]] = []
    for output_ref in normalized_outputs:
        matches = envelope_by_id.get(output_ref["artifact_id"], [])
        if len(matches) != 1:
            raise OutputCASManifestProfileRefusalError(
                "selected_output_profile_output_envelope_cardinality_mismatch"
            )
        envelope_ref, envelope = matches[0]
        if envelope_ref != output_ref:
            raise OutputCASManifestProfileRefusalError(
                "selected_output_profile_output_envelope_identity_mismatch"
            )
        selected.append(envelope)
    return selected


def output_cas_payload_refs_from_contract(
    search_exit_contract: Mapping[str, Any],
) -> list[str]:
    """Return only CAS payloads belonging to the declared output envelope set."""
    refs: list[str] = []
    for envelope in declared_output_envelopes_from_contract(search_exit_contract):
        payload_ref = envelope.get("payload_ref")
        if (
            isinstance(payload_ref, str)
            and payload_ref.startswith("sha256:")
            and payload_ref not in refs
        ):
            refs.append(payload_ref)
    return refs


def _producer_profile_witness_matches(
    witness: object,
    *,
    ref: Mapping[str, Any],
    payload_ref: str,
    payload_schema_ref: str,
    profile: str,
    expected_run_id: str | None,
    expected_job_id: str | None,
) -> bool:
    from polisyos.runtime.quality.data_forge_binding import MeasurementRootProfileWitness

    return (
        type(witness) is MeasurementRootProfileWitness
        and witness.envelope_artifact_id == ref.get("artifact_id")
        and witness.envelope_artifact_type == ref.get("artifact_type")
        and witness.envelope_content_hash == ref.get("content_hash")
        and witness.payload_artifact_id == payload_ref
        and witness.payload_manifest_profile_sha256 == profile
        and witness.payload_schema_ref == payload_schema_ref
        and witness.payload_kind == _MEASUREMENT_ROOT_PAYLOAD_KIND
        and witness.payload_media_type == "application/json"
        and witness.producer_component == _MEASUREMENT_ROOT_PRODUCER
        and witness.producer_version
        == ("2.0.0" if payload_schema_ref == "policyos.gy.fabric_measurement_root.v2" else "1.0.0")
        and witness.run_id == expected_run_id
        and witness.job_id == expected_job_id
    )


def output_cas_manifest_profiles_from_contract(
    search_exit_contract: Mapping[str, Any],
    *,
    artifact_store: object | None = None,
    require_resolution: bool = False,
    producer_profile_witnesses: Iterable[object] = (),
    expected_run_id: str | None = None,
    expected_job_id: str | None = None,
    require_producer_witness: bool = False,
) -> list[OutputCASManifestProfile]:
    """Resolve producer-selected CAS profiles for declared outputs only."""
    from polisyos.core.artifacts import read_core_manifest_profile
    from polisyos.pdc import gy_content_hash

    if require_producer_witness and (
        artifact_store is None or not expected_run_id or not expected_job_id
    ):
        raise OutputCASManifestProfileRefusalError(
            "measurement_root_actual_producer_subject_not_established"
        )
    contract_snapshot_hash = gy_content_hash(search_exit_contract)
    selected: list[OutputCASManifestProfile] = []
    seen_payloads: set[str] = set()
    witnesses = tuple(producer_profile_witnesses)
    declared_envelopes = declared_output_envelopes_from_contract(search_exit_contract)
    for envelope in declared_envelopes:
        ref = envelope["ref"]
        envelope_type = ref["artifact_type"]
        payload_ref = envelope.get("payload_ref")
        profile = envelope.get("payload_manifest_profile_sha256")
        payload_schema_ref = envelope.get("payload_schema_ref")
        creator = envelope.get("created_by")
        creator_component = creator.get("component") if isinstance(creator, Mapping) else None
        roots = envelope.get("producer_roots")
        root_rows = (
            [
                root
                for root in roots
                if isinstance(root, Mapping) and root.get("artifact_type") == "MeasurementRoot"
            ]
            if isinstance(roots, list)
            else []
        )
        marker_claims_measurement_root = envelope_type == "BaseDataset" and (
            creator_component == _MEASUREMENT_ROOT_PRODUCER or bool(root_rows)
        )
        schema_claims_measurement_root = envelope_type == "BaseDataset" and payload_schema_ref in {
            "policyos.policy_design_case.layer3_gy_loop.v1",
            "policyos.gy.fabric_measurement_root.v2",
        }
        measurement_root = False
        if (
            envelope_type == "BaseDataset"
            and isinstance(payload_ref, str)
            and payload_ref.startswith("sha256:")
            and artifact_store is not None
        ):
            try:
                selected_manifest, _declaration = read_core_manifest_profile(
                    artifact_store,
                    core_artifacts.ArtifactID(payload_ref),
                    manifest_profile_sha256=profile if isinstance(profile, str) else None,
                )
            except (AttributeError, OSError, TypeError, ValueError, RuntimeError) as exc:
                if (
                    marker_claims_measurement_root
                    or schema_claims_measurement_root
                    or profile is not None
                    or require_resolution
                ):
                    raise OutputCASManifestProfileRefusalError(
                        "selected_output_profile_owner_manifest_unavailable"
                    ) from exc
            else:
                persisted_producer = selected_manifest.producer
                measurement_root = selected_manifest.kind == _MEASUREMENT_ROOT_PAYLOAD_KIND or (
                    persisted_producer is not None
                    and persisted_producer.component == _MEASUREMENT_ROOT_PRODUCER
                )
        elif require_resolution and (
            marker_claims_measurement_root or schema_claims_measurement_root or profile is not None
        ):
            raise OutputCASManifestProfileRefusalError(
                "selected_output_profile_owner_manifest_unavailable"
            )
        if marker_claims_measurement_root and artifact_store is not None and not measurement_root:
            raise OutputCASManifestProfileRefusalError(
                "measurement_root_producer_manifest_binding_mismatch"
            )
        if measurement_root:
            if profile is None:
                raise OutputCASManifestProfileRefusalError(
                    "measurement_root_selected_profile_missing"
                )
            if (
                envelope_type != "BaseDataset"
                or not isinstance(creator, Mapping)
                or creator.get("kind") != "producer"
                or creator_component != _MEASUREMENT_ROOT_PRODUCER
                or not isinstance(roots, list)
                or len(roots) != 1
                or len(root_rows) != 1
            ):
                raise OutputCASManifestProfileRefusalError(
                    "measurement_root_producer_root_binding_mismatch"
                )
        if profile is None:
            continue
        if (
            not isinstance(payload_ref, str)
            or not payload_ref.startswith("sha256:")
            or not isinstance(payload_schema_ref, str)
            or not payload_schema_ref
            or not isinstance(ref.get("content_hash"), str)
            or (measurement_root and ref.get("schema_ref") != payload_schema_ref)
        ):
            raise OutputCASManifestProfileRefusalError("selected_output_profile_envelope_invalid")
        try:
            item = OutputCASManifestProfile(
                envelope_artifact_id=str(ref.get("artifact_id") or ""),
                envelope_artifact_type=str(envelope_type),
                payload_artifact_id=payload_ref,
                payload_schema_ref=payload_schema_ref,
                manifest_profile_sha256=profile,
            )
        except (TypeError, ValueError) as exc:
            raise OutputCASManifestProfileRefusalError(
                "selected_output_profile_selector_invalid"
            ) from exc
        if str(item.payload_artifact_id) in seen_payloads:
            raise OutputCASManifestProfileRefusalError("selected_output_profile_payload_duplicate")
        seen_payloads.add(str(item.payload_artifact_id))
        if require_resolution and artifact_store is None:
            raise OutputCASManifestProfileRefusalError(
                "selected_output_profile_store_not_established"
            )
        if artifact_store is not None:
            if measurement_root:
                try:
                    from polisyos.runtime.quality.data_forge_binding import (
                        MeasurementRootBindingError,
                        resolve_measurement_root_selected_profile,
                    )

                    resolved_manifest, resolved_payload = resolve_measurement_root_selected_profile(
                        store=artifact_store,
                        payload_ref=str(item.payload_artifact_id),
                        payload_schema_ref=item.payload_schema_ref,
                        manifest_profile_sha256=item.manifest_profile_sha256,
                        envelope_content_hash=str(ref["content_hash"]),
                        expected_run_id=expected_run_id,
                        expected_job_id=expected_job_id,
                    )
                except (AttributeError, OSError, TypeError, ValueError, RuntimeError) as exc:
                    if isinstance(exc, MeasurementRootBindingError):
                        reason = str(exc)
                    else:
                        reason = "measurement_root_producer_profile_unresolved"
                    raise OutputCASManifestProfileRefusalError(reason) from exc
                persisted_producer = resolved_manifest.producer
                if (
                    resolved_manifest.kind != _MEASUREMENT_ROOT_PAYLOAD_KIND
                    or persisted_producer is None
                    or persisted_producer.component != _MEASUREMENT_ROOT_PRODUCER
                ):
                    raise OutputCASManifestProfileRefusalError(
                        "measurement_root_producer_manifest_binding_mismatch"
                    )
                if not _measurement_root_ref_matches_payload(
                    root_rows[0],
                    resolved_payload,
                    payload_ref=str(item.payload_artifact_id),
                    payload_schema_ref=item.payload_schema_ref,
                ):
                    raise OutputCASManifestProfileRefusalError(
                        "measurement_root_producer_root_binding_mismatch"
                    )
                if require_producer_witness and not any(
                    _producer_profile_witness_matches(
                        witness,
                        ref=ref,
                        payload_ref=str(item.payload_artifact_id),
                        payload_schema_ref=item.payload_schema_ref,
                        profile=item.manifest_profile_sha256,
                        expected_run_id=expected_run_id,
                        expected_job_id=expected_job_id,
                    )
                    for witness in witnesses
                ):
                    raise OutputCASManifestProfileRefusalError(
                        "measurement_root_actual_producer_witness_missing_or_mismatched"
                    )
            else:
                _resolve_output_cas_manifest_profile(
                    artifact_store=artifact_store,
                    payload_ref=str(item.payload_artifact_id),
                    payload_schema_ref=item.payload_schema_ref,
                    manifest_profile_sha256=item.manifest_profile_sha256,
                    envelope_content_hash=ref.get("content_hash"),
                    require_measurement_root_owner=False,
                )
        selected.append(item)
    if gy_content_hash(search_exit_contract) != contract_snapshot_hash:
        raise OutputCASManifestProfileRefusalError(
            "selected_output_profile_contract_changed_after_resolution"
        )
    return selected


def build_outcome_replay_proof(
    *,
    case_id: str,
    input_payloads: Mapping[str, Any],
    search_exit_contract: Mapping[str, Any],
    output_cas_refs: Iterable[str],
    schema_version: Literal[_OUTCOME_REPLAY_V1, _OUTCOME_REPLAY_V2] = _OUTCOME_REPLAY_V2,
    artifact_store: object | None = None,
    profile_resolution_required: bool = True,
    producer_profile_witnesses: Iterable[object] = (),
    expected_run_id: str | None = None,
    expected_job_id: str | None = None,
    require_producer_witness: bool = False,
) -> OutcomeReplayProof:
    """Build the F16 A/B/C proof from run inputs and the emitted exit contract."""

    from polisyos.pdc import gy_content_hash

    contract = dict(search_exit_contract)
    ledger = contract.get("search_ledger")
    ledger = dict(ledger) if isinstance(ledger, Mapping) else {}
    incompleteness = contract.get("incompleteness_record")
    incompleteness = dict(incompleteness) if isinstance(incompleteness, Mapping) else {}
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
    output_profiles = (
        output_cas_manifest_profiles_from_contract(
            contract,
            artifact_store=artifact_store,
            require_resolution=profile_resolution_required,
            producer_profile_witnesses=producer_profile_witnesses,
            expected_run_id=expected_run_id,
            expected_job_id=expected_job_id,
            require_producer_witness=require_producer_witness,
        )
        if schema_version == _OUTCOME_REPLAY_V2
        else []
    )
    audit_input = {
        "producer_roots": producer_roots,
        "output_cas_refs": list(output_cas_refs),
    }
    if schema_version == _OUTCOME_REPLAY_V2:
        audit_input["output_cas_manifest_profiles"] = [
            item.model_dump(mode="json") for item in output_profiles
        ]
    output_hash = gy_content_hash(contract)
    return OutcomeReplayProof(
        schema_version=schema_version,
        case_id=case_id,
        replay_levels=["A", "B", "C"],
        input_hashes=input_hashes,
        output_hash=output_hash,
        producer_roots=producer_roots,
        output_cas_manifest_profiles=output_profiles,
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


class ClosureCasIdentity(BaseModel):
    """Exact selected CAS view named by a v2 closure member."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    identity_domain: Literal["cas"] = "cas"
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    artifact_ref: core_artifacts.ArtifactRef
    schema_name: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    producer_component: str = Field(min_length=1)
    producer_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _require_selected_profile(self) -> ClosureCasIdentity:
        if self.artifact_ref.manifest_profile_sha256 is None:
            raise ValueError("closure_cas_manifest_profile_missing")
        return self


class ClosureOwnerValueIdentity(BaseModel):
    """Registered non-CAS value selected by an existing runtime owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    identity_domain: Literal["owner_value"] = "owner_value"
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    value: dict[str, Any]


class ClosureNullIdentity(BaseModel):
    """Explicit absence of one optional member."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    identity_domain: Literal["null"] = "null"
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)


ClosureMemberIdentity = ClosureCasIdentity | ClosureOwnerValueIdentity | ClosureNullIdentity


class SameInputClosure(BaseModel):
    """Identity of the input context shared by authority-bearing evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0", "2.0"] = "1.0"
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
    members: tuple[ClosureMemberIdentity, ...] = Field(default=())
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

    @model_serializer(mode="wrap")
    def _serialize_versioned_closure(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        """Keep the original strict v1 wire shape when reading legacy records."""
        payload = handler(self)
        if self.schema_version == "1.0":
            payload.pop("schema_version", None)
            payload.pop("members", None)
        return payload

    def identity_tuple(self) -> tuple[str | None, ...]:
        """Stable same-input identity used by closeout consumers."""

        identity = (
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

        # V1 is a historical read law. Extending its tuple would invalidate
        # already-persisted seal checksums; protected admission refuses v1.
        if self.schema_version == "1.0":
            return identity
        return (*identity, *self.evidence_input_refs)

    @model_validator(mode="after")
    def _validate_versioned_shape(self) -> SameInputClosure:
        if self.schema_version == "2.0" and not self.members:
            raise ValueError("closure_v2_members_missing")
        names = [member.name for member in self.members]
        if len(names) != len(set(names)):
            raise ValueError("closure_member_duplicate")
        if self.schema_version == "1.0" and self.members:
            raise ValueError("closure_legacy_members_forbidden")
        if self.schema_version == "2.0":
            # V2 uses typed members as its single identity. Legacy aliases may be
            # read only when they name the same CAS member or explicit absence.
            by_name = {member.name: member for member in self.members}
            for field in (
                "policy_intent_ref",
                "time_context_ref",
                "production_data_manifest_ref",
                "legal_snapshot_ref",
                "method_plan_ref",
                "provider_mode_ref",
                "effective_mode_ref",
                "degradation_ledger_ref",
            ):
                alias = getattr(self, field)
                if alias is None:
                    continue
                member = by_name.get(field)
                if not isinstance(member, ClosureCasIdentity) or alias != str(
                    member.artifact_ref.artifact_id
                ):
                    raise ValueError("closure_v2_legacy_alias_not_bound")
        return self


class ClosureMemberContract(BaseModel):
    """Trusted owner rule for one complete closure member."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    identity_domain: ClosureIdentityDomain
    required: bool = True


class SameInputClosureContract(BaseModel):
    """Candidate inventory; caller construction does not establish owner authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    owner: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    members: tuple[ClosureMemberContract, ...]


class SameInputClosureResolver(Protocol):
    """Candidate comparison adapter; implementing this protocol confers no authority."""

    def resolve_member(
        self, member: ClosureMemberIdentity, *, tenant_id: str, purpose: str
    ) -> ClosureMemberIdentity:
        """Return the independently resolved exact identity after current access checks."""

    def consumed_input_refs(self, *, run_id: str, job_id: str) -> tuple[str, ...]:
        """Return ordered role-qualified input edges observed at the producer boundary."""


_VERIFIED_CLOSURE_KEY = object()


class VerifiedSameInputClosure:
    """Process-local result of resolving and recomputing a v2 closure."""

    __slots__ = ("_closure", "_contract", "_identity", "_resolver", "_sealed")

    def __init__(
        self,
        key: object,
        closure: SameInputClosure,
        identity: tuple[str | None, ...],
        contract: SameInputClosureContract,
        resolver: SameInputClosureResolver,
    ) -> None:
        if key is not _VERIFIED_CLOSURE_KEY:
            raise TypeError("verified closure results can only be created by the verifier")
        object.__setattr__(self, "_closure", closure)
        object.__setattr__(self, "_identity", identity)
        object.__setattr__(self, "_contract", contract)
        object.__setattr__(self, "_resolver", resolver)
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: object) -> None:
        """Keep an issued admission result non-rebindable."""

        if getattr(self, "_sealed", False):
            raise AttributeError("verified closure results are immutable")
        object.__setattr__(self, name, value)

    @property
    def closure(self) -> SameInputClosure:
        """Return the immutable admitted closure."""

        return self._closure

    @property
    def identity(self) -> tuple[str | None, ...]:
        """Return the identity admitted by the issuing owner."""

        return self._identity

    def _revalidate(self, closure: SameInputClosure) -> bool:
        """Re-enter the issuing owner and current-access resolver."""

        if type(self) is not VerifiedSameInputClosure or closure != self._closure:
            return False
        try:
            refreshed = verify_same_input_closure(
                closure,
                contract=self._contract,
                resolver=self._resolver,
                expected_run_id=closure.run_id,
                expected_job_id=closure.job_id,
                expected_tenant_id=closure.tenant_id,
                expected_cell_id=closure.cell_id,
            )
        except (AuthorityEnvelopeError, PermissionError, TypeError, ValueError):
            return False
        return refreshed.identity == self._identity


def verify_same_input_closure(
    closure: SameInputClosure,
    *,
    contract: SameInputClosureContract,
    resolver: SameInputClosureResolver,
    expected_run_id: str,
    expected_job_id: str,
    expected_tenant_id: str,
    expected_cell_id: str | None,
) -> VerifiedSameInputClosure:
    """Refuse protected admission from caller-supplied contracts and callbacks.

    The current registered report owners define output identities, but no owner
    establishes a complete, purpose-specific consumed-input law. Successful
    candidate comparison is therefore not an authority admission. The retained
    v2 reader is available before any v2 authority writer is enabled.
    """
    compare_same_input_closure_candidate(
        closure,
        contract=contract,
        resolver=resolver,
        expected_run_id=expected_run_id,
        expected_job_id=expected_job_id,
        expected_tenant_id=expected_tenant_id,
        expected_cell_id=expected_cell_id,
    )
    raise AuthorityEnvelopeError("same_input_closure_owner_not_established")


def compare_same_input_closure_candidate(
    closure: SameInputClosure,
    *,
    contract: SameInputClosureContract,
    resolver: SameInputClosureResolver,
    expected_run_id: str,
    expected_job_id: str,
    expected_tenant_id: str,
    expected_cell_id: str | None,
) -> SameInputClosure:
    """Check caller-basis coherence for diagnostics without issuing authority.

    A matching callback result does not prove owner provenance or completeness.
    This function intentionally returns an ordinary candidate closure.
    """

    if closure.schema_version != "2.0":
        raise AuthorityEnvelopeError("same_input_closure_legacy_not_authoritative")
    expected_scope = (expected_run_id, expected_job_id, expected_tenant_id, expected_cell_id)
    if (closure.run_id, closure.job_id, closure.tenant_id, closure.cell_id) != expected_scope:
        raise AuthorityEnvelopeError("same_input_closure_scope_mismatch")
    declared = {member.name: member for member in closure.members}
    specifications = {member.name: member for member in contract.members}
    if len(specifications) != len(contract.members) or set(declared) != set(specifications):
        raise AuthorityEnvelopeError("same_input_closure_inventory_mismatch")
    resolved: list[ClosureMemberIdentity] = []
    for name, specification in specifications.items():
        member = declared[name]
        if member.role != specification.role or (
            member.identity_domain != specification.identity_domain
            and not (not specification.required and isinstance(member, ClosureNullIdentity))
        ):
            raise AuthorityEnvelopeError("same_input_closure_member_contract_mismatch", name)
        if specification.required and isinstance(member, ClosureNullIdentity):
            raise AuthorityEnvelopeError("same_input_closure_required_member_absent", name)
        actual = resolver.resolve_member(
            member, tenant_id=closure.tenant_id, purpose=contract.purpose
        )
        if actual != member:
            raise AuthorityEnvelopeError("same_input_closure_member_resolution_mismatch", name)
        resolved.append(actual)
    observed_refs = resolver.consumed_input_refs(run_id=closure.run_id, job_id=closure.job_id)
    if observed_refs != closure.evidence_input_refs:
        raise AuthorityEnvelopeError("same_input_closure_consumption_mismatch")
    projection = {
        "domain": "polisyos.runtime.same_input_closure",
        "schema_version": "2.0",
        "identity_law_version": contract.rule_version,
        "canonical_spec": core_artifacts.CanonInfo.from_spec(
            canon.CanonSpec(exclude_none=False)
        ).model_dump(mode="json"),
        "owner": contract.owner,
        "purpose": contract.purpose,
        "scope": {
            "run_id": closure.run_id,
            "job_id": closure.job_id,
            "tenant_id": closure.tenant_id,
            "cell_id": closure.cell_id,
        },
        "members": [member.model_dump(mode="json") for member in resolved],
        "evidence_input_refs": list(observed_refs),
    }
    actual_digest = (
        "sha256:"
        + hashlib.sha256(
            canon.to_canonical_bytes(projection, canon.CanonSpec(exclude_none=False))
        ).hexdigest()
    )
    if closure.status != "closed" or closure.closure_sha256 != actual_digest:
        raise AuthorityEnvelopeError("same_input_closure_digest_mismatch")
    return closure


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


ConsumedInputSealPurpose = Literal["authority", "declared_basis_cache_equality"]


class DeclaredBasisCacheSeal(BaseModel):
    """Content-bound equality of declared cache members, never authority admission.

    This type makes no claim that the member denominator is complete for any
    producer or purpose. It cannot satisfy protected sealing/reuse, envelope
    roles, purpose checks or public authority surfaces.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.runtime.declared_basis_cache_seal.v1"] = (
        "policyos.runtime.declared_basis_cache_seal.v1"
    )
    purpose: Literal["declared_basis_cache_equality"] = "declared_basis_cache_equality"
    authority_role: Literal["diagnostic_only"] = "diagnostic_only"
    basis_scope: Literal["declared_members_only"] = "declared_members_only"
    purpose_completeness_basis: Literal["not_established"] = "not_established"
    same_input_closure: SameInputClosure
    members: tuple[ConsumedInputMember, ...]
    membership_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_declared_equality(self) -> DeclaredBasisCacheSeal:
        """Recompute only the declared membership snapshot's mechanical identity."""
        members = _normalise_consumed_input_members(self.members)
        if members != self.members:
            raise ValueError("declared_basis_cache_members_not_sorted")
        if self.membership_sha256 != _declared_basis_cache_membership_sha256(
            self.same_input_closure, members
        ):
            raise ValueError("declared_basis_cache_membership_mismatch")
        return self


class SealedConsumedInputSet(BaseModel):
    """Closed consumed-input membership bound to an existing input closure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    same_input_closure: SameInputClosure
    members: tuple[ConsumedInputMember, ...]
    membership_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_resolved_membership(self) -> SealedConsumedInputSet:
        """Prevent construction of a seal that did not resolve its members."""

        if self.same_input_closure.status != "closed" or not self.same_input_closure.closure_sha256:
            raise ValueError("same_input_closure_not_closed")
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
    runtime_event_manifest_profile_sha256: str | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
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
    requested_execution_profile: StrictStr | None = Field(..., min_length=1)
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
        "effective_execution_profile",
        "phase",
        "generated_at",
        "as_of_time",
        "effective_mode_ref",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("requested_execution_profile")
    @classmethod
    def _preserve_requested_profile_absence(cls, value: StrictStr | None) -> StrictStr | None:
        """Preserve an admitted omitted request profile without inventing a value."""
        return None if value is None else _non_empty(value)

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
            name
            for name, (closure_value, envelope_value) in mismatches.items()
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
    *,
    verified_closure: VerifiedSameInputClosure | None = None,
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
    if validated.authority_role == "producer_authority":
        _assert_closed_consumed_input_closure(
            validated.same_input_closure, verified_closure=verified_closure
        )
    return validated


def assert_runtime_emitted(
    envelope: AuthorityEnvelopeInput,
    *,
    verified_closure: VerifiedSameInputClosure | None = None,
) -> EvidenceAuthorityEnvelope:
    """Assert that an envelope is runtime-emitted CAS-backed authority."""

    validated = assert_authority_bearing(envelope, verified_closure=verified_closure)
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
    *,
    verified: Iterable[VerifiedSameInputClosure] = (),
    historical_advisory: bool = False,
) -> SameInputClosure:
    """Assert all envelopes carry the same closed input-context identity."""

    validated = tuple(deserialize_authority_envelope(envelope) for envelope in envelopes)
    if not validated:
        raise AuthorityEnvelopeError(
            "same_input_closure_missing",
            "at least one envelope is required",
        )

    first = validated[0].same_input_closure
    if not historical_advisory and any(
        envelope.same_input_closure.schema_version != "2.0" for envelope in validated
    ):
        raise AuthorityEnvelopeError("same_input_closure_legacy_not_authoritative")
    verified_items = tuple(verified)
    if any(envelope.same_input_closure.schema_version == "2.0" for envelope in validated):
        if len(verified_items) != len(validated):
            raise AuthorityEnvelopeError("same_input_closure_verification_missing")
        for envelope, result in zip(validated, verified_items, strict=True):
            if type(result) is not VerifiedSameInputClosure or not result._revalidate(
                envelope.same_input_closure
            ):
                raise AuthorityEnvelopeError("same_input_closure_verification_mismatch")
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


@overload
def seal_consumed_input_set(
    *,
    closure: SameInputClosure,
    members: Iterable[ConsumedInputMember | Mapping[str, Any]],
    verified_closure: VerifiedSameInputClosure | None = None,
    purpose: Literal["authority"] = "authority",
) -> SealedConsumedInputSet: ...


@overload
def seal_consumed_input_set(
    *,
    closure: SameInputClosure,
    members: Iterable[ConsumedInputMember | Mapping[str, Any]],
    verified_closure: VerifiedSameInputClosure | None = None,
    purpose: Literal["declared_basis_cache_equality"],
) -> DeclaredBasisCacheSeal: ...


def seal_consumed_input_set(
    *,
    closure: SameInputClosure,
    members: Iterable[ConsumedInputMember | Mapping[str, Any]],
    verified_closure: VerifiedSameInputClosure | None = None,
    purpose: ConsumedInputSealPurpose = "authority",
) -> SealedConsumedInputSet | DeclaredBasisCacheSeal:
    """Seal admitted authority, or explicitly compare a non-authorizing cache basis.

    The default remains protected and refuses unverified closure input. The
    explicit cache purpose returns a distinct diagnostic type and proves only
    equality of the declared members, not complete producer/purpose admission.
    """
    if purpose == "declared_basis_cache_equality":
        resolved_members = _normalise_consumed_input_members(members)
        return DeclaredBasisCacheSeal(
            same_input_closure=closure,
            members=resolved_members,
            membership_sha256=_declared_basis_cache_membership_sha256(closure, resolved_members),
        )
    if purpose != "authority":
        raise AuthorityEnvelopeError("consumed_input_seal_purpose_unknown")
    _assert_closed_consumed_input_closure(closure, verified_closure=verified_closure)
    resolved_members = _normalise_consumed_input_members(members)
    membership_sha256 = _consumed_input_membership_sha256(closure, resolved_members)
    return SealedConsumedInputSet(
        same_input_closure=closure,
        members=resolved_members,
        membership_sha256=membership_sha256,
    )


@overload
def assert_consumed_input_reuse(
    sealed: SealedConsumedInputSet,
    *,
    closure: SameInputClosure,
    fresh_members: Iterable[ConsumedInputMember | Mapping[str, Any]],
    verified_closure: VerifiedSameInputClosure | None = None,
    purpose: Literal["authority"] = "authority",
) -> SealedConsumedInputSet: ...


@overload
def assert_consumed_input_reuse(
    sealed: DeclaredBasisCacheSeal,
    *,
    closure: SameInputClosure,
    fresh_members: Iterable[ConsumedInputMember | Mapping[str, Any]],
    verified_closure: VerifiedSameInputClosure | None = None,
    purpose: Literal["declared_basis_cache_equality"],
) -> DeclaredBasisCacheSeal: ...


def assert_consumed_input_reuse(
    sealed: SealedConsumedInputSet | DeclaredBasisCacheSeal,
    *,
    closure: SameInputClosure,
    fresh_members: Iterable[ConsumedInputMember | Mapping[str, Any]],
    verified_closure: VerifiedSameInputClosure | None = None,
    purpose: ConsumedInputSealPurpose = "authority",
) -> SealedConsumedInputSet | DeclaredBasisCacheSeal:
    """Recheck protected admission, or explicit declared-basis cache equality only."""
    if purpose == "declared_basis_cache_equality":
        if type(sealed) is not DeclaredBasisCacheSeal:
            raise AuthorityEnvelopeError("declared_basis_cache_seal_required")
        try:
            sealed = DeclaredBasisCacheSeal.model_validate_json(sealed.model_dump_json())
        except (TypeError, ValueError) as exc:
            raise AuthorityEnvelopeError("declared_basis_cache_seal_invalid") from exc
        # Bind the entire declared closure record here, including any v2 members.
        if closure.model_dump(mode="json") != sealed.same_input_closure.model_dump(mode="json"):
            raise AuthorityEnvelopeError("consumed_input_closure_mismatch")
    elif purpose == "authority":
        if type(sealed) is not SealedConsumedInputSet:
            raise AuthorityEnvelopeError("declared_basis_cache_seal_not_authoritative")
        _assert_closed_consumed_input_closure(closure, verified_closure=verified_closure)
        if closure.identity_tuple() != sealed.same_input_closure.identity_tuple():
            raise AuthorityEnvelopeError(
                "consumed_input_closure_mismatch", f"closure_id={closure.closure_id}"
            )
    else:
        raise AuthorityEnvelopeError("consumed_input_seal_purpose_unknown")
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
    actual_sha256 = (
        _declared_basis_cache_membership_sha256(closure, resolved_members)
        if purpose == "declared_basis_cache_equality"
        else _consumed_input_membership_sha256(closure, resolved_members)
    )
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


def _declared_basis_cache_membership_sha256(
    closure: SameInputClosure,
    members: tuple[ConsumedInputMember, ...],
) -> str:
    """Hash a fully declared cache record without inferring producer completeness."""
    spec = canon.CanonSpec(exclude_none=False)
    return (
        "sha256:"
        + hashlib.sha256(
            canon.to_canonical_bytes(
                {
                    "domain": "polisyos.runtime.declared_basis_cache_equality",
                    "schema_version": "1.0",
                    "canonical_spec": core_artifacts.CanonInfo.from_spec(spec).model_dump(
                        mode="json"
                    ),
                    "same_input_closure": closure.model_dump(mode="json"),
                    "members": [member.model_dump(mode="json") for member in members],
                },
                spec,
            )
        ).hexdigest()
    )


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


def _assert_closed_consumed_input_closure(
    closure: SameInputClosure,
    *,
    verified_closure: VerifiedSameInputClosure | None = None,
) -> None:
    """Require the existing closure owner to have a closed content identity."""

    if closure.status != "closed" or not closure.closure_sha256:
        raise AuthorityEnvelopeError(
            "same_input_closure_not_closed",
            f"closure_id={closure.closure_id}",
        )
    if closure.schema_version != "2.0":
        raise AuthorityEnvelopeError("same_input_closure_legacy_not_authoritative")
    if type(verified_closure) is not VerifiedSameInputClosure or not verified_closure._revalidate(
        closure
    ):
        raise AuthorityEnvelopeError("same_input_closure_verification_missing")


def _raise_consumed_input_error(code: str, key: tuple[str, str]) -> None:
    """Raise one member-named fail-closed consumed-input error."""

    member_kind, member_id = key
    raise AuthorityEnvelopeError(code, f"member={member_kind}:{member_id}")


def classify_authority_role(
    envelope: AuthorityEnvelopeInput,
    *,
    verified_closure: VerifiedSameInputClosure | None = None,
) -> AuthorityRole:
    """Return the validated authority role for an envelope."""

    validated = deserialize_authority_envelope(envelope)
    if validated.authority_role == "producer_authority":
        try:
            _assert_closed_consumed_input_closure(
                validated.same_input_closure, verified_closure=verified_closure
            )
        except AuthorityEnvelopeError:
            return "not_authoritative"
    return validated.authority_role


def _envelope_authority_admission_blockers(payload: Mapping[str, Any]) -> tuple[str, ...]:
    """Compose an envelope's role with any requested positive authority use.

    A purpose list or positive boundary cannot turn a diagnostic, blocker,
    malformed or unadmitted producer envelope into positive authority. Plain
    AuthorityBoundary records keep their existing independent contract.
    """
    if not any(
        field in payload for field in ("authority_role", "evidence_class", "same_input_closure")
    ):
        return ()
    role = (_authority_payload_text(payload, "authority_role") or "").casefold()
    if role != "producer_authority":
        return ("authority_envelope_cannot_authorize_purpose",)
    try:
        assert_authority_bearing(payload)
    except (AuthorityEnvelopeError, TypeError, ValueError):
        return ("same_input_closure_owner_not_established",)
    return ()


def authority_purpose_blockers(
    envelope: Mapping[str, Any] | AuthorityEnvelopeInput | None,
    purpose: str,
) -> tuple[str, ...]:
    """Return purpose-boundary blockers from authoritative_for/may_not_use_for fields."""

    payload = _authority_payload(envelope)
    envelope_blockers = _envelope_authority_admission_blockers(payload)
    if envelope_blockers:
        return envelope_blockers
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
    artifact_store: _ArtifactSurfaceStore | None = None,
    artifact_id: object | None = None,
    artifact_ref: core_artifacts.ArtifactRef | None = None,
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

    artifact_target = artifact_ref if artifact_ref is not None else artifact_id
    artifact_ref_mismatch = (
        artifact_ref is not None
        and artifact_id is not None
        and str(artifact_ref.artifact_id) != str(artifact_id)
    )
    eval_safety_applies, eval_safety_payload, eval_safety_blocker = (
        _strict_eval_safety_surface_payload(
            surface=surface,
            purpose=purpose,
            artifact_store=artifact_store,
            artifact_id=artifact_target,
        )
    )
    authority_payload = eval_safety_payload or _surface_authority_payload(
        payload,
        artifact_store=artifact_store,
        artifact_id=artifact_target,
    )
    (
        selected_manifest_has_authority,
        selected_manifest_authority_payload,
        selected_manifest_authority_error,
    ) = _selected_manifest_authority_payload(
        artifact_store=artifact_store,
        artifact_id=artifact_target,
    )
    base = _authority_boundary_surface_decision(
        authority_payload,
        surface=surface,
        purpose=purpose,
        missing_authority_disposition=missing_authority_disposition,
        missing_boundary_disposition=missing_boundary_disposition,
    )
    selected_manifest_decision = (
        _authority_boundary_surface_decision(
            selected_manifest_authority_payload,
            surface=surface,
            purpose=purpose,
            missing_authority_disposition=missing_authority_disposition,
            missing_boundary_disposition=missing_boundary_disposition,
        )
        if selected_manifest_authority_payload is not None
        else None
    )
    carrier = _authority_payload(authority_payload)
    gate_inputs: list[str] = ["authority_boundary"]
    blocking_reasons: list[str] = []
    downgrade_reasons: list[str] = []
    if artifact_ref_mismatch:
        blocking_reasons.append("artifact_ref_identity_mismatch")
    if selected_manifest_has_authority or selected_manifest_authority_error is not None:
        gate_inputs.append("selected_manifest_authority")
        if selected_manifest_authority_error is not None:
            blocking_reasons.append(selected_manifest_authority_error)
        elif selected_manifest_decision is not None:
            if selected_manifest_decision.blocking:
                blocking_reasons.append(selected_manifest_decision.reason)
            elif selected_manifest_decision.visible_downgrade:
                downgrade_reasons.append(selected_manifest_decision.reason)
    secret_findings: list[str] = []
    integrity_status: Literal["not_applicable", "verified", "failed", "missing_input"] = (
        "not_applicable"
    )
    integrity_error: str | None = None
    time_dispositions: list[str] = []
    s12_issue_codes: list[str] = []
    candidate_issue_codes: list[str] = []

    if eval_safety_applies:
        gate_inputs.append("eval_safety_projection")
        if eval_safety_blocker is not None:
            blocking_reasons.append(eval_safety_blocker)

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

    if (
        require_cas_integrity
        or artifact_store is not None
        or artifact_id is not None
        or artifact_ref is not None
    ):
        gate_inputs.append("cas_integrity")
        if artifact_store is None or artifact_target is None:
            integrity_status = "missing_input"
            blocking_reasons.append("cas_integrity_input_missing")
        else:
            try:
                verification = artifact_store.verify(artifact_target)
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
            if disposition in {
                TIME_SOURCE_INCONSISTENT_DISPOSITION,
                TIME_SOURCE_BLOCKED_FOR_OWNER_REVIEW_DISPOSITION,
            }:
                blocking_reasons.append("time_source_envelope_blocked")
            elif disposition != TIME_SOURCE_CONSISTENT_DISPOSITION:
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
                str(issue.get("code") or "candidate_firewall_blocked") for issue in issues
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

    contributors = [
        AuthoritySurfaceContributor(
            basis="base_surface",
            status=base.status,
            authority_result=base.authority_result,
            transition_disposition=base.transition_disposition,
            authority_boundary_ref=base.authority_boundary_ref,
            consumed_authority_boundary=base.consumed_authority_boundary,
            may_not_use_for=list(base.may_not_use_for),
            reason=base.reason,
            blocking=base.blocking,
            visible_downgrade=base.visible_downgrade,
        )
    ]
    selected_contributor: AuthoritySurfaceContributor | None = None
    if selected_manifest_authority_error is not None:
        selected_contributor = AuthoritySurfaceContributor(
            basis="selected_manifest",
            status="blocked",
            authority_result="not_applicable",
            transition_disposition=None,
            authority_boundary_ref=None,
            consumed_authority_boundary=False,
            may_not_use_for=[],
            reason=selected_manifest_authority_error,
            blocking=True,
            visible_downgrade=True,
            resolution_error=selected_manifest_authority_error,
        )
    elif selected_manifest_decision is not None:
        selected_contributor = AuthoritySurfaceContributor(
            basis="selected_manifest",
            status=selected_manifest_decision.status,
            authority_result=selected_manifest_decision.authority_result,
            transition_disposition=selected_manifest_decision.transition_disposition,
            authority_boundary_ref=selected_manifest_decision.authority_boundary_ref,
            consumed_authority_boundary=(selected_manifest_decision.consumed_authority_boundary),
            may_not_use_for=list(selected_manifest_decision.may_not_use_for),
            reason=selected_manifest_decision.reason,
            blocking=selected_manifest_decision.blocking,
            visible_downgrade=selected_manifest_decision.visible_downgrade,
        )
    if selected_contributor is not None:
        contributors.append(selected_contributor)

    primary_authority_result = base.authority_result
    primary_transition_disposition = base.transition_disposition
    primary_authority_boundary_ref = base.authority_boundary_ref
    primary_consumed_authority_boundary = base.consumed_authority_boundary
    if selected_contributor is not None and (
        (
            bool(blocking_reasons)
            and blocking_reasons[0] == selected_contributor.reason
            and selected_contributor.blocking
        )
        or (
            not blocking_reasons
            and bool(downgrade_reasons)
            and downgrade_reasons[0] == selected_contributor.reason
            and selected_contributor.visible_downgrade
        )
    ):
        primary_authority_result = selected_contributor.authority_result
        primary_transition_disposition = selected_contributor.transition_disposition
        primary_authority_boundary_ref = selected_contributor.authority_boundary_ref
        primary_consumed_authority_boundary = selected_contributor.consumed_authority_boundary

    all_may_not_use = list(
        dict.fromkeys(
            purpose_name
            for contributor in contributors
            for purpose_name in contributor.may_not_use_for
        )
    )
    return AuthoritySurfaceDecision(
        surface=base.surface,
        purpose=base.purpose,
        status=status,
        authority_result=primary_authority_result,
        transition_disposition=primary_transition_disposition,
        authority_boundary_ref=primary_authority_boundary_ref,
        consumed_authority_boundary=primary_consumed_authority_boundary,
        may_not_use_for=all_may_not_use,
        reason=reason,
        blocking=blocking,
        visible_downgrade=visible_downgrade,
        composed_gate_inputs=list(dict.fromkeys(gate_inputs)),
        authority_contributors=contributors,
        secret_pii_finding_kinds=sorted(set(secret_findings)),
        integrity_status=integrity_status,
        integrity_error=integrity_error,
        time_source_dispositions=sorted(set(time_dispositions)),
        s12_issue_codes=sorted(set(s12_issue_codes)),
        candidate_firewall_issue_codes=sorted(set(candidate_issue_codes)),
    )


def _strict_eval_safety_surface_payload(
    *,
    surface: str,
    purpose: str | None,
    artifact_store: _ArtifactSurfaceStore | None,
    artifact_id: object | None,
) -> tuple[bool, Mapping[str, Any] | None, str | None]:
    """Strict-load one exact EvalSafety projection for the generic egress gate."""

    if artifact_store is None or artifact_id is None:
        return False, None, None

    artifact_identity = evaluation_safety_metrics_projection_identity("artifact")
    manifest_identity, manifest = _eval_safety_manifest_identity(
        artifact_store=artifact_store,
        artifact_id=artifact_id,
        expected_kind=artifact_identity.kind,
    )
    if manifest_identity == "unresolved":
        return True, None, "eval_safety_projection_identity_unresolved"
    if manifest_identity == "other":
        return False, None, None
    if manifest is None:  # pragma: no cover - exact identity always carries a manifest.
        return True, None, "eval_safety_projection_identity_unresolved"

    try:
        verification = artifact_store.verify(artifact_id)
    except (OSError, ValueError):
        return True, None, "eval_safety_projection_cas_verify_failed"
    if not getattr(verification, "ok", False):
        return True, None, "eval_safety_projection_cas_unverified"

    schema = getattr(manifest, "artifact_schema", None)
    if (
        schema is None
        or getattr(schema, "name", None) != artifact_identity.schema_name
        or getattr(schema, "version", None) != artifact_identity.schema_version
    ):
        return True, None, "eval_safety_projection_schema_mismatch"

    try:
        stored_payload = require_declared_profile(
            read_core_json_artifact(artifact_store, artifact_id)
        )
        projection = EvalSafetyMetricsProjection.model_validate(stored_payload)
    except (OSError, UnicodeError, ValueError):
        return True, None, "eval_safety_projection_payload_invalid"

    projection_payload = projection.model_dump(mode="json")
    surfaces = projection.authority_surface_packet.surfaces
    packet_purposes = {row.purpose for row in surfaces.values()}
    packet_denials = {denied_use for row in surfaces.values() for denied_use in row.may_not_use_for}
    boundary = projection.authority_boundary
    if (
        set(boundary.authoritative_for) != packet_purposes
        or len(boundary.authoritative_for) != len(packet_purposes)
        or set(boundary.may_not_use_for) != packet_denials
        or len(boundary.may_not_use_for) != len(packet_denials)
    ):
        return (
            True,
            projection_payload,
            "eval_safety_projection_boundary_binding_invalid",
        )
    surface_key = next((key for key in surfaces if key == surface), None)
    if surface_key is None:
        return (
            True,
            projection_payload,
            "eval_safety_projection_surface_binding_invalid",
        )
    surface_identity = evaluation_safety_metrics_projection_identity(surface_key)
    surface_packet = surfaces[surface_key]
    effective_purpose = purpose if purpose is not None else _default_surface_purpose(surface)
    if (
        effective_purpose != surface_identity.purpose
        or surface_packet.purpose != surface_identity.purpose
    ):
        return (
            True,
            projection_payload,
            "eval_safety_projection_surface_binding_invalid",
        )
    return True, projection_payload, None


def _eval_safety_manifest_identity(
    *,
    artifact_store: _ArtifactSurfaceStore,
    artifact_id: object,
    expected_kind: str,
) -> tuple[_EvalSafetyManifestIdentityState, object | None]:
    """Resolve whether one manifest is the exact governed family, another, or unknown."""

    try:
        manifest = artifact_store.get_manifest(artifact_id)
    except (OSError, ValueError):
        return "unresolved", None
    manifest_kind = getattr(manifest, "kind", None)
    if (
        not isinstance(manifest_kind, str)
        or not manifest_kind
        or manifest_kind != manifest_kind.strip()
    ):
        return "unresolved", manifest
    if manifest_kind == expected_kind:
        return "exact", manifest
    return "other", manifest


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
    # Candidate and blocked dispositions above remain honest negative/limited
    # diagnostics. A positive boundary additionally needs the role's admission.
    envelope_blockers = tuple(
        blocker
        for candidate in (carrier, surface_packet)
        for blocker in _envelope_authority_admission_blockers(candidate)
    )
    if envelope_blockers:
        return AuthoritySurfaceDecision(
            surface=surface_name,
            purpose=requested_purpose,
            status="blocked",
            authority_result=authority_result,
            transition_disposition=transition_disposition,
            authority_boundary_ref=boundary_ref,
            consumed_authority_boundary=True,
            may_not_use_for=may_not_use_for,
            reason=envelope_blockers[0],
            blocking=True,
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


def _selected_manifest_authority_payload(
    *,
    artifact_store: _ArtifactSurfaceStore | None,
    artifact_id: object | None,
) -> tuple[bool, Mapping[str, Any] | None, str | None]:
    """Resolve and verify the authority envelope linked by the exact selected manifest."""

    if artifact_store is None or artifact_id is None:
        return False, None, None
    try:
        manifest = artifact_store.get_manifest(artifact_id)
    except Exception:
        if isinstance(artifact_id, core_artifacts.ArtifactRef):
            return False, None, "selected_manifest_resolution_failed"
        return False, None, None

    authority = getattr(manifest, "authority", None)
    if authority is None:
        return False, None, None
    try:
        envelope_ref = core_artifacts.resolve_authority_envelope_ref(
            cast("core_artifacts.ArtifactStore", artifact_store),
            authority,
        )
        verification = artifact_store.verify(envelope_ref)
        if not getattr(verification, "ok", False):
            return True, None, "selected_manifest_authority_integrity_failed"
        artifact_store.get_manifest(envelope_ref)
        envelope_payload = require_declared_profile(
            read_core_json_artifact(artifact_store, envelope_ref)
        )
    except Exception:
        return True, None, "selected_manifest_authority_resolution_failed"

    if not isinstance(envelope_payload, Mapping):
        return True, None, "selected_manifest_authority_payload_invalid"
    if _has_payload_authority_signal(envelope_payload):
        return True, envelope_payload, None
    boundary = _validated_authority_boundary_payload(envelope_payload)
    if boundary is not None:
        return True, {"authority_boundary": dict(boundary)}, None
    return True, None, "selected_manifest_authority_payload_invalid"


def _normalize_report_payload_hash(value: str | None) -> str | None:
    if value is None:
        return None
    digest = value.removeprefix("sha256:") if value.startswith("sha256:") else value
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        return None
    return f"sha256:{digest}"


def runtime_quality_report_cas_admission_issues(
    *,
    artifact_store: core_artifacts.ArtifactStore | None,
    selected_ref: core_artifacts.ArtifactRef | None,
    runtime_ref: str | None,
    report_key: str,
    ref_key: str,
    report: Mapping[str, Any],
    envelope: Mapping[str, Any] | None,
    expected_write_options: ArtifactWriteOptions | None = None,
    expected_identity_context: AuthorityArtifactIdentityContext | None = None,
) -> list[dict[str, Any]]:
    """Resolve, content-bind, and verify one selected runtime quality report.

    When the current publisher invocation is known, verify its complete typed
    write options and freshly rebuilt authority identity through the shared
    writer owner. A valid historical publication cannot stand in for a
    different current invocation.
    """
    if (
        envelope is not None
        and (_authority_payload_text(envelope, "authority_role") or "").casefold()
        == "producer_authority"
    ):
        try:
            assert_authority_bearing(envelope)
        except (AuthorityEnvelopeError, TypeError, ValueError):
            return [
                _ownership_issue(
                    "same_input_closure_owner_not_established",
                    "A parsed producer claim has no complete owner-established input admission.",
                    expected="owner-established purpose-specific consumed-input admission",
                    observed="not_established",
                    field="same_input_closure",
                )
            ]
    contract = runtime_quality_report_owner_contract(report_key, ref_key)
    if contract is None:
        return [
            _ownership_issue(
                "runtime_quality_owner_contract_not_established",
                "No producer-owned runtime quality report contract is registered for this role.",
                expected=report_key,
                observed=ref_key,
                field="owner_contract",
            )
        ]
    if artifact_store is None:
        return [
            _ownership_issue(
                "runtime_quality_cas_store_not_available",
                "A selected Core CAS store is required to admit runtime report authority.",
                expected="selected Core CAS reader",
                observed=None,
                field="artifact_store",
            )
        ]
    if type(selected_ref) is not core_artifacts.ArtifactRef:
        return [
            _ownership_issue(
                "runtime_quality_selected_ref_not_established",
                "A typed selected artifact ref is required for runtime report authority.",
                expected="Core ArtifactRef",
                observed=type(selected_ref).__name__ if selected_ref is not None else None,
                field="selected_ref",
            )
        ]
    profile = selected_ref.manifest_profile_sha256
    if profile is None:
        return [
            _ownership_issue(
                "runtime_quality_selected_profile_not_established",
                "The report ref has no selected manifest profile.",
                expected="sha256:<64 lowercase hex>",
                observed=None,
                field="manifest_profile_sha256",
            )
        ]
    selected_id = str(selected_ref.artifact_id)
    if runtime_ref != selected_id:
        return [
            _ownership_issue(
                "runtime_quality_selected_ref_mismatch",
                "Selected report ref does not match the runtime-owned report ref.",
                expected=runtime_ref,
                observed=selected_id,
                field="artifact_id",
            )
        ]
    if selected_ref.kind != contract.artifact_kind:
        return [
            _ownership_issue(
                "runtime_quality_selected_kind_mismatch",
                "Selected report ref kind does not match its registered producer owner.",
                expected=contract.artifact_kind,
                observed=selected_ref.kind,
                field="kind",
            )
        ]
    if selected_ref.media_type != contract.media_type:
        return [
            _ownership_issue(
                "runtime_quality_selected_media_type_mismatch",
                "Selected report ref media type does not match its registered producer owner.",
                expected=contract.media_type,
                observed=selected_ref.media_type,
                field="media_type",
            )
        ]

    try:
        store = artifact_store
        verification = store.verify(selected_ref)
        if not verification.ok:
            raise ValueError("selected_runtime_report_integrity_failed")
        manifest, declaration = read_core_manifest_profile(
            store,
            selected_ref,
            manifest_profile_sha256=profile,
        )
    except Exception:
        return [
            _ownership_issue(
                "runtime_quality_selected_cas_resolution_failed",
                "Selected report manifest could not be verified through the Core reader.",
                expected="verified selected manifest",
                observed=None,
                field="manifest",
            )
        ]

    manifest_schema = manifest.artifact_schema
    manifest_producer = manifest.producer
    manifest_profile = core_artifacts.artifact_manifest_profile_sha256(manifest)
    manifest_identity = (
        manifest.artifact_id == selected_ref.artifact_id
        and manifest.kind == contract.artifact_kind
        and manifest.media_type == contract.media_type
        and manifest_schema is not None
        and manifest_schema.name == contract.schema_name
        and manifest_schema.version == contract.schema_version
        and manifest_producer is not None
        and manifest_producer.component == contract.producer_component
        and manifest_producer.version == contract.producer_version
        and manifest_profile == profile
        and declaration.status == "declared"
    )
    if not manifest_identity:
        return [
            _ownership_issue(
                "runtime_quality_manifest_owner_mismatch",
                "Selected report manifest does not match its exact registered producer owner.",
                expected={
                    "kind": contract.artifact_kind,
                    "media_type": contract.media_type,
                    "schema_name": contract.schema_name,
                    "schema_version": contract.schema_version,
                    "producer_component": contract.producer_component,
                    "producer_version": contract.producer_version,
                    "manifest_profile_sha256": profile,
                },
                observed=None,
                field="manifest_identity",
            )
        ]

    try:
        payload_read = read_core_json_artifact(
            store,
            selected_ref,
            manifest_profile_sha256=profile,
        )
        payload = require_declared_profile(payload_read)
    except Exception:
        return [
            _ownership_issue(
                "runtime_quality_selected_payload_resolution_failed",
                "Selected report payload could not be read under its declared Core profile.",
                expected="declared profile-bound JSON",
                observed=None,
                field="payload",
            )
        ]
    if not isinstance(payload, Mapping):
        return [
            _ownership_issue(
                "runtime_quality_selected_payload_invalid",
                "Selected report payload is not a JSON object.",
                expected="mapping",
                observed=type(payload).__name__,
                field="payload",
            )
        ]

    marker = runtime_quality_report_owner_marker(report_key, ref_key)
    if marker is None or payload.get("runtime_authority_payload") != marker:
        return [
            _ownership_issue(
                "runtime_quality_payload_owner_marker_mismatch",
                "Selected report payload lacks the exact publisher owner marker.",
                expected=marker,
                observed=payload.get("runtime_authority_payload"),
                field="runtime_authority_payload",
            )
        ]
    if "runtime_authority_payload" in report and report.get("runtime_authority_payload") != marker:
        return [
            _ownership_issue(
                "runtime_quality_report_basis_mismatch",
                "Scored report carries a different owner marker from its selected payload.",
                expected=marker,
                observed=report.get("runtime_authority_payload"),
                field="runtime_authority_payload",
            )
        ]
    publication_basis = _parse_runtime_quality_report_publication_basis(
        report.get(_RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY),
        expected_report_key=report_key,
        expected_ref_key=ref_key,
    )
    if publication_basis is None:
        return [
            _ownership_issue(
                "runtime_quality_report_publication_basis_not_established",
                "The scored report lacks the exact publisher-owned source and selected-ref basis.",
                expected="typed publisher publication basis",
                observed=None,
                field=_RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY,
            )
        ]
    if publication_basis.artifact_ref != selected_ref.model_dump(mode="json"):
        return [
            _ownership_issue(
                "runtime_quality_report_basis_mismatch",
                "Publisher basis selected ref/profile differs from the verified Core ref.",
                expected=selected_ref.model_dump(mode="json"),
                observed=publication_basis.artifact_ref,
                field="runtime_quality_artifact_refs",
            )
        ]
    try:
        expected_cas_payload = _runtime_quality_report_writer_payload(
            publication_basis.report_payload,
            report_key=report_key,
            ref_key=ref_key,
        )
        expected_view = _runtime_quality_report_publication_view(publication_basis)
        expected_cas_bytes = canon.to_canonical_bytes(
            expected_cas_payload,
            canon.CanonSpec(forbid_floats=False),
        )
        payload_bytes = canon.to_canonical_bytes(
            dict(payload),
            canon.CanonSpec(forbid_floats=False),
        )
        expected_view_bytes = canon.to_canonical_bytes(
            expected_view,
            canon.CanonSpec(forbid_floats=False),
        )
        report_bytes = canon.to_canonical_bytes(
            dict(report),
            canon.CanonSpec(forbid_floats=False),
        )
    except Exception:
        expected_cas_bytes = b""
        payload_bytes = b""
        expected_view_bytes = b""
        report_bytes = b""
    if (
        not expected_cas_bytes
        or expected_cas_bytes != payload_bytes
        or not expected_view_bytes
        or expected_view_bytes != report_bytes
    ):
        return [
            _ownership_issue(
                "runtime_quality_report_basis_mismatch",
                "The complete publisher input or its selected compatibility view differs from CAS.",
                expected="complete source payload plus exact selected publication projection",
                observed="different, missing, or noncanonical report basis",
                field="report_payload",
            )
        ]

    manifest_authority = manifest.authority
    if manifest_authority is None:
        return [
            _ownership_issue(
                "runtime_quality_manifest_authority_missing",
                "Selected report manifest has no linked runtime authority envelope.",
                expected="manifest authority link",
                observed=None,
                field="manifest.authority",
            )
        ]
    expected_manifest_ref = f"cas-manifest://{selected_id}"
    if (
        manifest_authority.payload_sha256 != selected_ref.artifact_id.hex
        or manifest_authority.manifest_ref != expected_manifest_ref
        or manifest_authority.authority_envelope_manifest_profile_sha256 is None
        or manifest_authority.diagnostic_event_manifest_profile_sha256 is None
        or _normalize_report_payload_hash(_authority_payload_text(report, "payload_sha256"))
        != selected_id
        or _authority_payload_text(report, "manifest_ref") != expected_manifest_ref
        or _authority_payload_text(report, "authority_envelope_ref")
        != manifest_authority.authority_envelope_ref
        or _authority_payload_text(report, "runtime_event_ref")
        != manifest_authority.diagnostic_event_ref
        or report.get("runtime_event_manifest_profile_sha256")
        != manifest_authority.diagnostic_event_manifest_profile_sha256
    ):
        return [
            _ownership_issue(
                "runtime_quality_manifest_authority_link_mismatch",
                "Runtime report authority links do not match the selected CAS manifest.",
                expected="selected manifest authority links",
                observed=None,
                field="manifest.authority",
            )
        ]

    try:
        envelope_ref = core_artifacts.resolve_authority_envelope_ref(
            store,
            manifest_authority,
        )
        envelope_profile = manifest_authority.authority_envelope_manifest_profile_sha256
        if envelope_profile is None or envelope_ref.manifest_profile_sha256 != envelope_profile:
            raise ValueError("runtime_quality_envelope_profile_not_selected")
        envelope_verification = store.verify(envelope_ref)
        if not envelope_verification.ok:
            raise ValueError("runtime_quality_envelope_integrity_failed")
        envelope_manifest, envelope_declaration = read_core_manifest_profile(
            store,
            envelope_ref,
            manifest_profile_sha256=envelope_profile,
        )
        envelope_bytes = store.get_bytes(envelope_ref)
        envelope_payload = require_declared_profile(
            read_core_json_artifact(
                store,
                envelope_ref,
                raw_payload_bytes=envelope_bytes,
                manifest_profile_sha256=envelope_profile,
            )
        )
        if not isinstance(envelope_payload, Mapping):
            raise ValueError("runtime_quality_envelope_payload_invalid")
        selected_envelope = EvidenceAuthorityEnvelope.model_validate_json(
            envelope_bytes,
            strict=True,
        )
    except Exception:
        return [
            _ownership_issue(
                "runtime_quality_manifest_envelope_not_verified",
                "Selected manifest-linked authority envelope could not be verified.",
                expected="verified selected envelope",
                observed=None,
                field="manifest.authority_envelope_ref",
            )
        ]

    envelope_manifest_producer = envelope_manifest.producer
    report_tenant = manifest.tenant_context
    report_closure = manifest.same_input_closure
    selected_closure = selected_envelope.same_input_closure
    envelope_context_matches = (
        report_tenant is not None
        and report_closure is not None
        and envelope_manifest.producer == manifest.producer
        and envelope_manifest.inputs == manifest.inputs
        and envelope_manifest.tenant_context == report_tenant
        and envelope_manifest.same_input_closure == report_closure
        and envelope_manifest.governance == manifest.governance
        and envelope_manifest.canon == manifest.canon
        and envelope_manifest.authority is None
        and selected_envelope.tenant_id == report_tenant.tenant_id
        and selected_envelope.cell_id == report_tenant.cell_id
        and selected_envelope.run_id == report_closure.run_id
        and selected_envelope.job_id == report_closure.job_id
        and selected_envelope.same_input_closure.closure_id == report_closure.closure_id
        and selected_closure.status == report_closure.status
        and selected_closure.closure_sha256 == report_closure.closure_sha256
        and selected_closure.run_id == report_closure.run_id
        and selected_closure.job_id == report_closure.job_id
        and selected_closure.tenant_id == report_closure.tenant_id
        and selected_closure.cell_id == report_closure.cell_id
        and selected_closure.evidence_input_refs == report_closure.evidence_input_refs
    )
    envelope_manifest_profile = core_artifacts.artifact_manifest_profile_sha256(envelope_manifest)
    envelope_schema = envelope_manifest.artifact_schema
    envelope_manifest_identity = (
        envelope_declaration.status == "declared"
        and envelope_manifest.artifact_id == envelope_ref.artifact_id
        and envelope_manifest.kind == envelope_ref.kind
        and envelope_manifest.media_type == envelope_ref.media_type
        and envelope_manifest_profile == envelope_profile
        and envelope_schema is not None
        and envelope_manifest_producer is not None
        and envelope_manifest_producer.component == contract.producer_component
        and envelope_manifest_producer.version == contract.producer_version
        and envelope_context_matches
    )
    selected_envelope_identity = (
        selected_envelope.artifact_ref == selected_id
        and selected_envelope.cas_ref == selected_id
        and selected_envelope.payload_sha256 == selected_ref.artifact_id.hex
        and selected_envelope.artifact_kind == contract.artifact_kind
        and selected_envelope.schema_name == contract.schema_name
        and selected_envelope.schema_version == contract.schema_version
        and selected_envelope.producer_component == contract.producer_component
        and selected_envelope.producer_version == contract.producer_version
        and selected_envelope.phase == contract.phase
        and selected_envelope.runtime_event_ref == manifest_authority.diagnostic_event_ref
        and selected_envelope.runtime_event_manifest_profile_sha256
        == manifest_authority.diagnostic_event_manifest_profile_sha256
    )
    if not envelope_manifest_identity or not selected_envelope_identity:
        return [
            _ownership_issue(
                "runtime_quality_manifest_envelope_owner_mismatch",
                "Selected manifest-linked envelope does not match the report owner and context.",
                expected={
                    "artifact_id": selected_id,
                    "artifact_kind": contract.artifact_kind,
                    "schema_name": contract.schema_name,
                    "schema_version": contract.schema_version,
                    "producer_component": contract.producer_component,
                    "producer_version": contract.producer_version,
                    "phase": contract.phase,
                },
                observed=None,
                field="manifest.authority_envelope_ref",
            )
        ]
    if not isinstance(envelope, Mapping) or dict(envelope) != dict(envelope_payload):
        return [
            _ownership_issue(
                "runtime_quality_inline_envelope_mismatch",
                "Inline authority envelope differs from the selected manifest-linked envelope.",
                expected="selected manifest-linked envelope",
                observed="missing or different inline envelope",
                field="authority_envelope",
            )
        ]
    if (expected_write_options is None) != (expected_identity_context is None):
        return [
            _ownership_issue(
                "runtime_quality_current_identity_not_established",
                (
                    "Current invocation admission requires typed write options and a rebuilt "
                    "identity context."
                ),
                expected="write options plus current authority identity context",
                observed="one current identity component is missing",
                field="current_identity",
            )
        ]
    if expected_write_options is not None and expected_identity_context is not None:
        expected_inputs = tuple(expected_write_options.inputs or ())
        expected_input_refs = tuple(str(item.artifact_id) for item in expected_inputs)
        if (
            expected_inputs != expected_identity_context.manifest_inputs
            or expected_input_refs != expected_identity_context.input_refs
            or expected_input_refs
            != expected_identity_context.same_input_closure.evidence_input_refs
        ):
            return [
                _ownership_issue(
                    "runtime_quality_current_identity_mismatch",
                    (
                        "Current typed write inputs, rebuilt manifest inputs, input refs, and "
                        "closure inputs must agree exactly."
                    ),
                    expected="one complete typed input basis across the current identity",
                    observed="current write options or identity input edges differ",
                    field="current_identity.inputs",
                )
            ]
        try:
            from polisyos.runtime.http.services.control.artifacts import (
                verify_runtime_authority_artifact_identity,
            )

            verify_runtime_authority_artifact_identity(
                store,
                artifact_id=selected_ref,
                opts=expected_write_options,
                expected_context=expected_identity_context,
            )
        except Exception:
            return [
                _ownership_issue(
                    "runtime_quality_current_identity_mismatch",
                    (
                        "Selected report does not match the independently rebuilt current "
                        "publisher identity."
                    ),
                    expected="strict authority artifact identity for the current invocation",
                    observed="selected CAS identity differs or could not be verified",
                    field="current_identity",
                )
            ]
    return []


def _surface_authority_payload(
    payload: Mapping[str, Any] | AuthorityEnvelopeInput | None,
    *,
    artifact_store: _ArtifactSurfaceStore | None,
    artifact_id: object | None,
) -> Mapping[str, Any] | AuthorityEnvelopeInput | None:
    """Resolve the authority carrier for a surface without replacing scan bytes."""

    carrier = _authority_payload(payload)
    if _has_payload_authority_signal(carrier):
        return payload
    if artifact_store is None or artifact_id is None:
        return payload

    try:
        stored_payload = require_declared_profile(
            read_core_json_artifact(artifact_store, artifact_id)
        )
    except Exception:
        stored_payload = None
    if isinstance(stored_payload, Mapping) and _has_payload_authority_signal(stored_payload):
        return stored_payload

    try:
        manifest = artifact_store.get_manifest(artifact_id)
    except Exception:
        return payload
    authority = getattr(manifest, "authority", None)
    if authority is None:
        return payload
    try:
        envelope_ref = core_artifacts.resolve_authority_envelope_ref(
            cast("core_artifacts.ArtifactStore", artifact_store),
            authority,
        )
        if not artifact_store.verify(envelope_ref).ok:
            return payload
        artifact_store.get_manifest(envelope_ref)
        envelope_bytes = artifact_store.get_bytes(envelope_ref)
        envelope_payload = require_declared_profile(
            read_core_json_artifact(
                artifact_store,
                envelope_ref,
                raw_payload_bytes=envelope_bytes,
            )
        )
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
    owner_contract = runtime_quality_report_owner_contract(normalized_report_key, ref_key)
    expected_artifact_kinds = (
        {owner_contract.artifact_kind}
        if owner_contract is not None
        else _expected_artifact_kinds(
            report_key=normalized_report_key,
            ref_key=ref_key,
        )
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
    schema_matches = (
        schema_name == owner_contract.schema_name
        and _authority_payload_text(envelope, "schema_version") == owner_contract.schema_version
        if owner_contract is not None
        else _schema_matches_report(
            schema_name=schema_name,
            report_schema=report_schema,
            report_key=normalized_report_key,
            expected_artifact_kinds=expected_artifact_kinds,
        )
    )
    if not schema_matches:
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
    phase_matches = (
        phase == owner_contract.phase
        if owner_contract is not None
        else phase is None
        or _phase_matches_report(
            phase=phase,
            report_key=normalized_report_key,
            expected_artifact_kinds=expected_artifact_kinds,
        )
    )
    if not phase_matches:
        issues.append(
            _ownership_issue(
                "authority_envelope_phase_mismatch",
                "Authority envelope phase belongs to a different report family.",
                expected=normalized_report_key,
                observed=phase,
                field="phase",
            )
        )

    if owner_contract is not None:
        for field_name, expected_value in (
            ("producer_component", owner_contract.producer_component),
            ("producer_version", owner_contract.producer_version),
        ):
            observed = _authority_payload_text(envelope, field_name)
            if observed != expected_value:
                issues.append(
                    _ownership_issue(
                        "authority_envelope_producer_mismatch",
                        "Authority envelope producer identity does not match the registered owner.",
                        expected=expected_value,
                        observed=observed,
                        field=field_name,
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

    expected_event_profile_present, expected_event_profile = _runtime_event_profile_from_report(
        report
    )
    observed_event_profile = envelope.get("runtime_event_manifest_profile_sha256")
    if observed_event_profile is not None and (
        not isinstance(observed_event_profile, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", observed_event_profile) is None
    ):
        issues.append(
            _ownership_issue(
                "authority_envelope_runtime_event_profile_invalid",
                "Authority envelope runtime event profile is malformed.",
                expected="sha256:<64 lowercase hex>",
                observed=observed_event_profile,
                field="runtime_event_manifest_profile_sha256",
            )
        )
    if expected_event_profile_present and (
        not isinstance(expected_event_profile, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", expected_event_profile) is None
    ):
        issues.append(
            _ownership_issue(
                "authority_report_runtime_event_profile_invalid",
                "Report runtime event profile is supplied but malformed.",
                expected="sha256:<64 lowercase hex>",
                observed=expected_event_profile,
                field="runtime_event_manifest_profile_sha256",
            )
        )
    if expected_event_profile_present and observed_event_profile != expected_event_profile:
        issues.append(
            _ownership_issue(
                "authority_envelope_runtime_event_profile_mismatch",
                "Authority envelope runtime event profile does not match the report event profile.",
                expected=expected_event_profile,
                observed=observed_event_profile,
                field="runtime_event_manifest_profile_sha256",
            )
        )

    return issues


def authority_envelope_json_schema() -> dict[str, Any]:
    """Return the JSON Schema snapshot for the versioned authority envelope."""

    return EvidenceAuthorityEnvelope.model_json_schema(mode="validation")


def write_authority_envelope_json_schema(
    path: Path | str = DEFAULT_AUTHORITY_ENVELOPE_SCHEMA_PATH,
) -> Path:
    """Write the versioned authority envelope JSON Schema snapshot."""

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
    requested = envelope.requested_execution_profile
    return (
        requested is not None and requested.casefold() in SERIOUS_EXECUTION_PROFILES
    ) or envelope.effective_execution_profile.casefold() in SERIOUS_EXECUTION_PROFILES


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
        text for item in raw_values for text in (_optional_text(str(item)),) if text is not None
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
            if not isinstance(disposition, str) or not disposition:
                dispositions.append(_TIME_SOURCE_DISPOSITION_MISSING)
                return
            try:
                projection = TimeSourceConsistencyAuditProjection.model_validate(dict(value))
            except ValidationError:
                dispositions.append(_TIME_SOURCE_CONTRACT_INVALID)
            else:
                dispositions.append(projection.mismatch_disposition)
            return
        for item in value.values():
            _collect_time_source_dispositions(item, dispositions)
        return
    if isinstance(value, Iterable):
        for item in value:
            _collect_time_source_dispositions(item, dispositions)


def resolve_time_source_consistency_disposition(
    times: Mapping[str, datetime | str | None],
) -> TimeSourceConsistencyDisposition:
    """Recompute the diagnostic disposition from sparse family-native time roles."""

    resolved: dict[str, datetime | None] = {
        field: _parse_time_source_datetime(times.get(field))
        for field in TIME_SOURCE_CONSISTENCY_ROLE_FIELDS
    }
    catalog_watermark = resolved["catalog_watermark"]
    source_times = (
        resolved["source_observed_at"],
        resolved["source_published_at"],
        resolved["source_updated_at"],
    )
    if catalog_watermark is None or any(source_time is None for source_time in source_times):
        return TIME_SOURCE_INSUFFICIENT_EVIDENCE_DISPOSITION
    if any(source_time > catalog_watermark for source_time in source_times if source_time):
        return TIME_SOURCE_INCONSISTENT_DISPOSITION

    legal_valid_time = resolved["legal_valid_time"]
    as_of_time = resolved["as_of_time"]
    replay_time = resolved["replay_time"]
    if legal_valid_time is None or as_of_time is None or replay_time is None:
        return TIME_SOURCE_INSUFFICIENT_EVIDENCE_DISPOSITION
    if legal_valid_time > as_of_time or legal_valid_time > replay_time:
        return TIME_SOURCE_BLOCKED_FOR_OWNER_REVIEW_DISPOSITION

    run_started_at = resolved["run_started_at"]
    run_finished_at = resolved["run_finished_at"]
    if run_started_at is None or run_finished_at is None:
        return TIME_SOURCE_INSUFFICIENT_EVIDENCE_DISPOSITION
    if run_finished_at < run_started_at:
        return TIME_SOURCE_INCONSISTENT_DISPOSITION

    node_started_at = resolved["node_started_at"]
    node_finished_at = resolved["node_finished_at"]
    if node_started_at is None or node_finished_at is None:
        return TIME_SOURCE_INSUFFICIENT_EVIDENCE_DISPOSITION
    if node_finished_at < node_started_at:
        return TIME_SOURCE_INCONSISTENT_DISPOSITION

    retention_or_expiry = resolved["retention_or_expiry"]
    if retention_or_expiry is None:
        return TIME_SOURCE_INSUFFICIENT_EVIDENCE_DISPOSITION
    visibility_cutoff = max(as_of_time, replay_time, run_finished_at, node_finished_at)
    if retention_or_expiry < visibility_cutoff:
        return TIME_SOURCE_INCONSISTENT_DISPOSITION
    return TIME_SOURCE_CONSISTENT_DISPOSITION


def _parse_time_source_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        if not value or value != value.strip():
            raise ValueError("time-source role must be a non-empty canonical timestamp")
        candidate = f"{value[:-1]}+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError("time-source role must be an ISO-8601 timestamp") from exc
    else:
        raise ValueError("time-source role must be a datetime, string, or null")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("time-source role must include an explicit UTC offset")
    return parsed.astimezone(UTC)


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
    validation_status = (_authority_payload_text(envelope, "validation_status") or "").casefold()
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
        "runtime_event_manifest_profile_sha256",
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
    if report_key == "security_assurance_report":
        expected.add(SECURITY_ASSURANCE_ARTIFACT_KIND)
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
    if (
        report_key == "security_assurance_report"
        and schema_name == SECURITY_ASSURANCE_ARTIFACT_SCHEMA_NAME
    ):
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


def _runtime_event_profile_from_report(
    report: Mapping[str, Any] | None,
) -> tuple[bool, object | None]:
    """Return suppliedness separately so malformed explicit values cannot mean legacy absence."""
    if not isinstance(report, Mapping):
        return False, None
    if "runtime_event_manifest_profile_sha256" in report:
        return True, report.get("runtime_event_manifest_profile_sha256")
    event = report.get("diagnostic_event")
    if isinstance(event, Mapping) and "runtime_event_manifest_profile_sha256" in event:
        return True, event.get("runtime_event_manifest_profile_sha256")
    return False, None


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
    "TIME_SOURCE_CONSISTENCY_ROLE_FIELDS",
    "TIME_SOURCE_CONSISTENT_DISPOSITION",
    "TIME_SOURCE_INCONSISTENT_DISPOSITION",
    "TIME_SOURCE_INSUFFICIENT_EVIDENCE_DISPOSITION",
    "AuthorityEnvelopeError",
    "AuthorityEnvelopeViolation",
    "AuthorityFailureClassification",
    "AuthorityRole",
    "AuthorityRootCauseClass",
    "AuthoritySurfaceContributor",
    "AuthoritySurfaceDecision",
    "BlockingStatus",
    "ClosureCasIdentity",
    "ClosureMemberContract",
    "ClosureNullIdentity",
    "ClosureOwnerValueIdentity",
    "ConsumedInputMember",
    "ConsumedInputMemberKind",
    "ConsumedInputSealPurpose",
    "DeclaredBasisCacheSeal",
    "EvidenceAuthorityEnvelope",
    "EvidenceClass",
    "GovernanceMetadata",
    "OutcomeReplayLevelProof",
    "OutcomeReplayProof",
    "OutputCASManifestProfile",
    "OutputCASManifestProfileRefusalError",
    "PredicateProvenanceClass",
    "ProducerIdentity",
    "ProductionLoopRunProof",
    "ProvenanceKind",
    "SameInputClosure",
    "SameInputClosureContract",
    "SameInputClosureStatus",
    "SealedConsumedInputSet",
    "TimeSourceConsistencyAuditProjection",
    "TimeSourceConsistencyDisposition",
    "TimeSourceConsistencyProducerRef",
    "TimeSourceConsistencyProjectionKind",
    "TimeSourceConsistencyProjectionScope",
    "ValidationStatus",
    "VerifiedSameInputClosure",
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
    "compare_same_input_closure_candidate",
    "declared_output_envelopes_from_contract",
    "deserialize_authority_envelope",
    "output_cas_manifest_profiles_from_contract",
    "output_cas_payload_refs_from_contract",
    "resolve_time_source_consistency_disposition",
    "seal_consumed_input_set",
    "serialize_authority_envelope",
    "verify_same_input_closure",
    "write_authority_envelope_json_schema",
]
