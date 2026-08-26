"""Frozen persistence profiles shared by Cluster-4 owner implementations.

The registry is deliberately storage-agnostic.  Runtime and Scientist writers
consume the same kind/schema/canonicalization contract without importing one
another, while independent readers can reproduce the exact preimage directly
from these frozen rows.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel

from polisyos.core.artifacts import ArtifactID, ArtifactManifest, ArtifactRef, CanonInfo, SchemaInfo
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.chronology import CHRONOLOGY_CANON_SPEC


@dataclass(frozen=True, slots=True)
class C4PersistedProfileSpec:
    """One exact persisted-statement profile."""

    record: str
    kind: str
    schema_name: str
    schema_version: str
    media_type: str
    semantic_prefix: bytes
    raw_mapping_fields: tuple[str, ...]
    self_field_exclusions: tuple[str, ...]
    binary64_decimal_paths: tuple[tuple[str, ...], ...] = ()
    canon_spec: CanonSpec = CHRONOLOGY_CANON_SPEC


def _profile(
    record: str,
    kind: str,
    schema: str,
    semantic_prefix: bytes,
    raw_mapping_fields: tuple[str, ...],
    *,
    self_field_exclusions: tuple[str, ...] = (),
    binary64_decimal_paths: tuple[tuple[str, ...], ...] = (),
) -> C4PersistedProfileSpec:
    return C4PersistedProfileSpec(
        record=record,
        kind=kind,
        schema_name=schema,
        schema_version="1",
        media_type="application/octet-stream",
        semantic_prefix=semantic_prefix,
        raw_mapping_fields=raw_mapping_fields,
        self_field_exclusions=self_field_exclusions,
        binary64_decimal_paths=binary64_decimal_paths,
    )


# Task 4.3's seven frozen promotion rows plus the required OpenWorldRisk vector
# row.  The latter closes the plan's fixed-profile omission without appointing
# an owner or changing any capability/property result.
_PROMOTION_PROFILE_SPECS = {
    "generation_owner_snapshot": _profile(
        "generation_owner_snapshot",
        "runtime.promotion.generation_owner_snapshot",
        "polisyos.promotion.generation-owner-snapshot.v1",
        b"polisyos.promotion.generation-owner-snapshot.v1\0",
        (
            "design_problem_binding_ref",
            "design_problem_binding_content_hash",
            "declared_candidate_count",
            "ordered_candidate_ids",
            "ordered_candidate_content_hashes",
            "ordered_candidate_summary_content_hashes",
            "ordered_cycle_indices",
            "predicate_class",
        ),
    ),
    "candidate_occurrence": _profile(
        "candidate_occurrence",
        "runtime.promotion.candidate_occurrence",
        "polisyos.promotion.candidate-occurrence.v1",
        b"polisyos.promotion.candidate-occurrence.v1\0",
        (
            "ordinal",
            "design_problem_binding_ref",
            "design_problem_binding_content_hash",
            "candidate_id",
            "candidate_content_hash",
            "candidate_summary",
            "candidate_summary_content_hash",
            "cycle_index",
        ),
        binary64_decimal_paths=(
            ("candidate_summary", "proxy_score"),
            ("candidate_summary", "voi_estimate"),
            ("candidate_summary", "grounding_score"),
        ),
    ),
    "candidate_denominator": _profile(
        "candidate_denominator",
        "runtime.promotion.candidate_denominator",
        "polisyos.promotion.candidate-denominator.v1",
        b"polisyos.promotion.candidate-denominator.v1\0",
        (
            "owner_snapshot_ref",
            "owner_snapshot_content_hash",
            "design_problem_binding_ref",
            "declared_candidate_count",
            "ordered_occurrence_refs",
            "ordered_occurrence_content_hashes",
            "predicate_class",
        ),
    ),
    "epoch_query_evidence": _profile(
        "epoch_query_evidence",
        "runtime.promotion.semantic_epoch_query",
        "polisyos.promotion.semantic-epoch-query.v1",
        b"polisyos.promotion-query.semantic-epoch.v1\0",
        (
            "schema_version",
            "design_problem_binding_ref",
            "candidate",
            "qualification_result",
        ),
    ),
    "deployment_query_evidence": _profile(
        "deployment_query_evidence",
        "runtime.promotion.deployment_scope_query",
        "polisyos.promotion.deployment-scope-query.v1",
        b"polisyos.promotion-query.deployment-scope.v1\0",
        (
            "schema_version",
            "design_problem_binding_ref",
            "candidate",
            "authority_purpose",
        ),
    ),
    "member_context": _profile(
        "member_context",
        "runtime.promotion.candidate_context_member",
        "polisyos.promotion.candidate-context-member.v1",
        b"polisyos.promotion-candidate-context-member.v1\0",
        (
            "candidate_occurrence_ref",
            "candidate_occurrence_content_hash",
            "epoch_query_evidence_ref",
            "epoch_query_evidence_content_hash",
            "epoch_native_query_context_ref",
            "deployment_query_evidence_ref",
            "deployment_query_evidence_content_hash",
            "deployment_native_query_context_ref",
            "authority_purpose",
        ),
    ),
    "aggregate_context": _profile(
        "aggregate_context",
        "runtime.promotion.owner_query_context",
        "polisyos.promotion.owner-query-context.v2",
        b"polisyos.promotion-owner-query-context.v2\0",
        (
            "design_problem_binding_ref",
            "design_problem_binding_content_hash",
            "authority_purpose",
            "candidate_denominator_ref",
            "candidate_denominator_content_hash",
            "ordered_candidate_contexts",
            "requested_query_context_ref",
            "owner_resolution_provenance_ref",
            "predicate_class",
        ),
    ),
    "bound_member": _profile(
        "bound_member",
        "runtime.promotion.bound_candidate_context",
        "polisyos.promotion.bound-candidate-context.v1",
        b"polisyos.promotion-bound-candidate-context.v1\0",
        (
            "aggregate_context_ref",
            "aggregate_context_content_hash",
            "member_context_ref",
            "member_context_content_hash",
            "candidate_occurrence_ref",
            "ordinal",
        ),
    ),
    "open_world_risk_vector": _profile(
        "open_world_risk_vector",
        "runtime.promotion.open_world_risk_vector",
        "polisyos.promotion.open-world-risk-vector.v1",
        b"polisyos.open-world-risk.vector.v1\0",
        (
            "schema_version",
            "aggregate_context_ref",
            "aggregate_context_content_hash",
            "bound_member_ref",
            "bound_member_content_hash",
            "candidate_occurrence_ref",
            "candidate_occurrence_content_hash",
            "requested_query_context_ref",
            "declared_component_denominator_ref",
            "lifecycle_role_denominator_ref",
            "components",
            "status",
            "limitation_code",
            "vector_content_hash",
        ),
        self_field_exclusions=("vector_content_hash",),
    ),
    "pre_n9_epoch_subject": _profile(
        "pre_n9_epoch_subject",
        "runtime.promotion.pre_n9_epoch_validity_subject",
        "polisyos.promotion.pre-n9-epoch-validity-subject.v1",
        b"polisyos.promotion.pre-n9-epoch-validity-subject.v1\0",
        (
            "owner_query_context_ref",
            "owner_query_context_content_hash",
            "bound_member_ref",
            "bound_member_content_hash",
            "candidate_occurrence_ref",
            "candidate_occurrence_content_hash",
            "decision_packet_lineage_key_ref",
            "current_decision_packet_ref",
            "packet_epoch_refs",
        ),
    ),
    "epoch_validity_gate_receipt": _profile(
        "epoch_validity_gate_receipt",
        "runtime.promotion.epoch_validity_gate_receipt",
        "polisyos.promotion.epoch-validity-gate-receipt.v1",
        b"polisyos.promotion.epoch-validity-gate-receipt.v1\0",
        (
            "status",
            "subject_ref",
            "subject_content_hash",
            "current_decision_packet_ref",
            "packet_epoch_refs",
            "current_epoch_head_refs",
            "dependency_denominator_ref",
            "adjudication_denominator_ref",
            "prior_completed_binding_ref",
            "completed_batch_receipt_ref",
            "requested_query_context_ref",
            "failure_codes",
        ),
    ),
    "pre_n9_admitted_candidate_batch": _profile(
        "pre_n9_admitted_candidate_batch",
        "runtime.promotion.pre_n9_admitted_candidate_batch",
        "polisyos.promotion.pre-n9-admitted-candidate-batch.v1",
        b"polisyos.promotion.pre-n9-admitted-candidate-batch.v1\0",
        (
            "aggregate_context_ref",
            "aggregate_context_content_hash",
            "candidate_denominator_ref",
            "candidate_denominator_content_hash",
            "ordered_admissions",
            "batch_content_hash",
        ),
        self_field_exclusions=("batch_content_hash",),
    ),
}


# Task 4.5's Claim Ledger records are frozen before the first owner writer is
# implemented.  The final five rows complete the exhaustive persisted-record
# denominator named by the task prose even though its compact profile table
# listed only the six root/head records.
_CLAIM_PROFILE_SPECS = {
    "claim_ledger_preparation": _profile(
        "claim_ledger_preparation",
        "scientist.claims.ledger_preparation",
        "polisyos.claim-ledger.preparation.v1",
        b"polisyos.claim-ledger-preparation.v1\0",
        (
            "schema_version",
            "owner_key",
            "base_claims_ref",
            "base_claims_content_hash",
            "source_artifact_refs",
            "source_artifact_content_hashes",
            "initialization_policy_ref",
            "initialization_policy_content_hash",
            "initialization_policy_verifier_provenance_ref",
            "initial_ledger_ref",
            "initial_ledger_content_hash",
        ),
    ),
    "claim_ledger_root_basis": _profile(
        "claim_ledger_root_basis",
        "scientist.claims.ledger_root_basis",
        "polisyos.claim-ledger.root-basis.v1",
        b"polisyos.claim-ledger-root-basis.v1\0",
        (
            "owner_key",
            "preparation_ref",
            "preparation_content_hash",
            "decision_packet_ref",
            "decision_packet_content_hash",
            "initial_ledger_ref",
            "initial_ledger_content_hash",
            "denominator_receipt_ref",
            "denominator_receipt_content_hash",
        ),
    ),
    "claim_ledger_root": _profile(
        "claim_ledger_root",
        "scientist.claims.ledger_root",
        "polisyos.claim-ledger.root.v1",
        b"polisyos.claim-ledger-root-root.v1\0",
        (
            "schema_version",
            "root_identity",
            "basis_ref",
            "basis_content_hash",
            "issuance_evidence_ref",
            "issuance_evidence_content_hash",
            "issuance_verifier_provenance_ref",
        ),
    ),
    "claim_ledger_root_verification": _profile(
        "claim_ledger_root_verification",
        "scientist.claims.ledger_root_verification",
        "polisyos.claim-ledger.root-verification.v1",
        b"polisyos.claim-ledger-root-verification.v1\0",
        (
            "root_ref",
            "root_content_hash",
            "verifier_provenance_ref",
            "disposition",
        ),
    ),
    "claim_ledger_head": _profile(
        "claim_ledger_head",
        "scientist.claims.ledger_head",
        "polisyos.claim-ledger.head.v1",
        b"polisyos.claim-ledger-head-statement.v1\0",
        (
            "schema_version",
            "root_identity",
            "root_receipt_ref",
            "root_receipt_content_hash",
            "owner_key",
            "ledger_artifact_ref",
            "ledger_raw_cas_hash",
            "generation",
            "predecessor_head_ref",
            "bridge_result_refs",
            "issuance_verifier_receipt_ref",
            "issuance_verifier_receipt_content_hash",
        ),
    ),
    "claim_ledger_head_readback": _profile(
        "claim_ledger_head_readback",
        "scientist.claims.ledger_head_readback",
        "polisyos.claim-ledger.head-readback.v1",
        b"polisyos.claim-ledger-head-readback.v1\0",
        (
            "schema_version",
            "owner_key",
            "root_identity",
            "expected_prior_head_ref",
            "observed_head_ref",
            "observed_head_content_hash",
            "observed_generation",
            "durable_pointer_content_hash",
            "disposition",
        ),
    ),
    "decision_packet_root_snapshot": _profile(
        "decision_packet_root_snapshot",
        "scientist.claims.decision_packet_root_snapshot",
        "polisyos.claim-ledger.decision-packet-root-snapshot.v1",
        b"polisyos.claim-ledger-decision-packet-root-snapshot.v1\0",
        ("schema_version", "row_count", "ordered_rows", "verifier_provenance_ref"),
    ),
    "claim_ledger_root_denominator": _profile(
        "claim_ledger_root_denominator",
        "scientist.claims.ledger_root_denominator",
        "polisyos.claim-ledger.root-denominator.v1",
        b"polisyos.claim-ledger-root-denominator.v1\0",
        (
            "owner_snapshot_ref",
            "owner_snapshot_content_hash",
            "independent_walk_content_hash",
            "owner_snapshot_row_count",
            "independent_walk_row_count",
            "declared_root_count",
            "assessments",
            "denominator_hash",
            "predicate_class",
        ),
        self_field_exclusions=("denominator_hash",),
    ),
    "claim_dependency_denominator": _profile(
        "claim_dependency_denominator",
        "scientist.claims.dependency_denominator",
        "polisyos.claim-ledger.dependency-denominator.v1",
        b"polisyos.claim-ledger-dependency-denominator.v1\0",
        (
            "schema_version",
            "registry_ref",
            "registry_content_hash",
            "claim_schema_content_hash",
            "ledger_artifact_ref",
            "ledger_raw_cas_hash",
            "batch_dependency_denominator_ref",
            "requested_dependency_keys",
            "declared_path_count",
            "observed_path_count",
            "ordered_dependency_rows",
            "ordered_affected_claim_ids",
            "denominator_hash",
            "predicate_class",
        ),
        self_field_exclusions=("denominator_hash",),
    ),
    "claim_bridge_pending": _profile(
        "claim_bridge_pending",
        "scientist.claims.bridge_pending",
        "polisyos.claim-ledger.bridge-pending.v1",
        b"polisyos.claim-ledger-bridge-pending.v1\0",
        (
            "schema_version",
            "batch_receipt_ref",
            "batch_receipt_content_hash",
            "decision_packet_ref",
            "decision_packet_content_hash",
            "requested_query_context_ref",
            "target_mapping_ref",
            "target_mapping_content_hash",
            "ordered_affected_claim_ids",
            "expected_head_ref",
            "mapping_status",
            "limitation_code",
        ),
    ),
    "claim_bridge_result": _profile(
        "claim_bridge_result",
        "scientist.claims.bridge_result",
        "polisyos.claim-ledger.bridge-result.v1",
        b"polisyos.claim-ledger-bridge-result.v1\0",
        (
            "schema_version",
            "owner_key",
            "batch_receipt_ref",
            "batch_receipt_content_hash",
            "decision_packet_ref",
            "decision_packet_content_hash",
            "requested_query_context_ref",
            "pending_ref",
            "pending_content_hash",
            "dependency_denominator_ref",
            "dependency_denominator_content_hash",
            "lifecycle_result_ref",
            "lifecycle_result_content_hash",
            "prior_ledger_ref",
            "prior_ledger_content_hash",
            "next_ledger_ref",
            "next_ledger_content_hash",
            "ordered_affected_claim_ids",
            "predicate_class",
        ),
    ),
}


C4_PERSISTED_PROFILE_SPECS: Mapping[str, C4PersistedProfileSpec] = MappingProxyType(
    {**_PROMOTION_PROFILE_SPECS, **_CLAIM_PROFILE_SPECS}
)


def c4_profile(record: str) -> C4PersistedProfileSpec:
    """Return one exact profile or reject an unregistered persisted record."""

    try:
        return C4_PERSISTED_PROFILE_SPECS[record]
    except KeyError as exc:
        raise ValueError(f"c4_persisted_profile_unregistered:{record}") from exc


def _raw_value(value: Any) -> Any:
    if isinstance(value, ArtifactID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return _raw_value(value.model_dump(mode="python", exclude_none=False))
    if isinstance(value, Mapping):
        return {str(key): _raw_value(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_raw_value(item) for item in value]
    return value


def _normalize_binary64_path(payload: dict[str, Any], path: tuple[str, ...]) -> None:
    current: dict[str, Any] = payload
    for component in path[:-1]:
        nested = current.get(component)
        if not isinstance(nested, dict):
            raise ValueError("c4_persisted_binary64_path_mismatch:" + ".".join(path))
        current = nested
    value = current.get(path[-1])
    if not isinstance(value, float) or math.isnan(value) or math.isinf(value):
        raise ValueError("c4_persisted_binary64_value_invalid:" + ".".join(path))
    normalized = "0" if value == 0.0 else format(value, ".17g")
    current[path[-1]] = Decimal(normalized)


def c4_canonical_mapping(record: str, value: BaseModel | Mapping[str, object]) -> dict[str, Any]:
    """Build and validate the exact full raw mapping for one profile."""

    spec = c4_profile(record)
    payload = _raw_value(value)
    if not isinstance(payload, dict):
        raise TypeError("c4_persisted_value_must_be_mapping")
    if set(payload) != set(spec.raw_mapping_fields) or len(payload) != len(spec.raw_mapping_fields):
        raise ValueError(f"c4_persisted_profile_field_mismatch:{record}")
    for path in spec.binary64_decimal_paths:
        _normalize_binary64_path(payload, path)
    return {field: payload[field] for field in spec.raw_mapping_fields}


def c4_canonical_bytes(record: str, value: BaseModel | Mapping[str, object]) -> bytes:
    """Encode one full persisted mapping under the frozen common CanonSpec."""

    spec = c4_profile(record)
    return to_canonical_bytes(c4_canonical_mapping(record, value), spec.canon_spec)


def c4_semantic_digest(record: str, value: BaseModel | Mapping[str, object]) -> str:
    """Hash the exact self-excluded mapping with prefix and uint64 framing."""

    spec = c4_profile(record)
    mapping = c4_canonical_mapping(record, value)
    semantic_mapping = {
        field: mapping[field]
        for field in spec.raw_mapping_fields
        if field not in spec.self_field_exclusions
    }
    canonical = to_canonical_bytes(semantic_mapping, spec.canon_spec)
    preimage = spec.semantic_prefix + len(canonical).to_bytes(8, "big") + canonical
    return "sha256:" + hashlib.sha256(preimage).hexdigest()


def c4_profile_manifest_is_exact(
    record: str,
    *,
    ref: ArtifactRef,
    manifest: ArtifactManifest,
    raw: bytes,
) -> bool:
    """Return whether a first-writer manifest is exactly the frozen profile.

    Creation time and integrity are store-owned. Every optional authority,
    lineage, environment and warning field is deliberately absent for these
    statements; a prior writer cannot attach different provenance to the same
    content-addressed bytes.
    """

    spec = c4_profile(record)
    return (
        ref.kind == spec.kind
        and ref.media_type == spec.media_type
        and manifest.artifact_id == ref.artifact_id
        and manifest.kind == spec.kind
        and manifest.media_type == spec.media_type
        and manifest.byte_size == len(raw)
        and manifest.artifact_schema
        == SchemaInfo(name=spec.schema_name, version=spec.schema_version)
        and manifest.canon == CanonInfo.from_spec(spec.canon_spec)
        and manifest.inputs == []
        and manifest.producer is None
        and manifest.env is None
        and manifest.governance is None
        and manifest.tenant_context is None
        and manifest.same_input_closure is None
        and manifest.authority is None
        and manifest.warnings == []
        and manifest.integrity.sha256 == ref.artifact_id.hex
        and manifest.integrity.optional is None
    )


__all__ = [
    "C4_PERSISTED_PROFILE_SPECS",
    "C4PersistedProfileSpec",
    "c4_canonical_bytes",
    "c4_canonical_mapping",
    "c4_profile",
    "c4_profile_manifest_is_exact",
    "c4_semantic_digest",
]
