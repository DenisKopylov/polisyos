"""Authority-owned Claim Ledger roots, heads, and current-state resolution.

The production default is intentionally negative.  This module contains the
mechanism needed by an appointed owner, but repository composition does not
appoint an initialization-policy signer, root issuer, or verifier.  Candidate
Claim bytes therefore cannot become current merely because they are present in
the artifact store.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import UnionType
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    Protocol,
    Union,
    get_args,
    get_origin,
    runtime_checkable,
)

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, canon
from polisyos.core import contracts as core_contracts

if TYPE_CHECKING:
    from polisyos.scientist.evidence.claims.export import (
        ClaimExportAudience,
        ClaimLedgerExport,
    )
    from polisyos.scientist.evidence.claims.models import ClaimLedger

Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
ArtifactRef = artifacts.ArtifactRef
ArtifactStore = artifacts.ArtifactStore
ArtifactWriteOptions = artifacts.ArtifactWriteOptions
CHRONOLOGY_CANON_SPEC = core_contracts.chronology.CHRONOLOGY_CANON_SPEC
EpochValidityBatchTarget = core_contracts.EpochValidityBatchTarget
EpochValidityCompletedBatchEvidenceDenominator = (
    core_contracts.EpochValidityCompletedBatchEvidenceDenominator
)
PersistedEpochValidityBatchEvidence = core_contracts.PersistedEpochValidityBatchEvidence
c4_canonical_bytes = core_contracts.c4_canonical_bytes
c4_profile = core_contracts.c4_profile
c4_profile_manifest_is_exact = core_contracts.c4_profile_manifest_is_exact
c4_semantic_digest = core_contracts.c4_semantic_digest
from_canonical_bytes = canon.from_canonical_bytes
to_canonical_bytes = canon.to_canonical_bytes

CLAIM_LEDGER_AUTHORITY_PURPOSE = "claim_ledger_currentness"
_OWNER_SCOPE_PREFIX = b"polisyos.claim-ledger-owner-scope.v1\0"


def _raw_content_hash(raw: bytes) -> Digest:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _read_exact_artifact(
    *,
    store: ArtifactStore,
    ref: ArtifactRef,
    expected_kind: str | None = None,
    expected_media_type: str | None = None,
    expected_schema: artifacts.SchemaInfo | None = None,
) -> bytes:
    """Reload bytes only when the shaped ref and live manifest agree exactly."""

    raw = store.get_bytes(ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    report = store.verify(ref.artifact_id)
    if (
        not report.ok
        or str(manifest.artifact_id) != str(ref.artifact_id)
        or _raw_content_hash(raw) != str(ref.artifact_id)
        or ref.kind != manifest.kind
        or ref.media_type != manifest.media_type
        or (expected_kind is not None and ref.kind != expected_kind)
        or (expected_media_type is not None and ref.media_type != expected_media_type)
        or (expected_schema is not None and manifest.artifact_schema != expected_schema)
    ):
        raise ValueError("claim_artifact_profile_mismatch")
    return raw


def _persist_profiled_statement(
    *,
    store: ArtifactStore,
    record: str,
    value: BaseModel,
) -> tuple[ArtifactRef, Digest]:
    """Persist and immediately read back one exact frozen C4 statement."""

    profile = c4_profile(record)
    raw = c4_canonical_bytes(record, value)
    ref = store.put_bytes(
        raw,
        ArtifactWriteOptions(
            kind=profile.kind,
            media_type=profile.media_type,
            schema=artifacts.SchemaInfo(
                name=profile.schema_name,
                version=profile.schema_version,
            ),
            canon=artifacts.CanonInfo.from_spec(profile.canon_spec),
        ),
    )
    observed = store.get_bytes(ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    report = store.verify(ref.artifact_id)
    if (
        not report.ok
        or observed != raw
        or _raw_content_hash(observed) != str(ref.artifact_id)
        or not c4_profile_manifest_is_exact(
            record,
            ref=ref,
            manifest=manifest,
            raw=observed,
        )
    ):
        raise ValueError("claim_profiled_statement_readback_mismatch")
    return ref, c4_semantic_digest(record, value)


def _read_profiled_statement(
    *,
    store: ArtifactStore,
    record: str,
    ref: ArtifactRef,
    model: type[_StrictFrozenModel],
) -> _StrictFrozenModel:
    """Reload one exact frozen C4 statement without trusting its shaped ref."""

    profile = c4_profile(record)
    raw = store.get_bytes(ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    report = store.verify(ref.artifact_id)
    if (
        ref.kind != profile.kind
        or ref.media_type != profile.media_type
        or not report.ok
        or _raw_content_hash(raw) != str(ref.artifact_id)
        or not c4_profile_manifest_is_exact(
            record,
            ref=ref,
            manifest=manifest,
            raw=raw,
        )
    ):
        raise ValueError("claim_profiled_statement_profile_mismatch")
    parsed = model.model_validate(from_canonical_bytes(raw))
    if c4_canonical_bytes(record, parsed) != raw:
        raise ValueError("claim_profiled_statement_canonical_mismatch")
    return parsed


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _ClaimRootDenominatorMismatch(ValueError):
    """Internal discriminator for an independently observed root-set mismatch."""


class _ClaimBatchAlreadyApplied(Exception):
    """Internal control result for a fully verified idempotent bridge retry."""

    def __init__(self, result: PersistedClaimLifecycleBridgeResult) -> None:
        super().__init__(str(result.bridge_result_ref.artifact_id))
        self.result = result


class ClaimLedgerOwnerKeyDerivationInput(_StrictFrozenModel):
    """Content-bound inputs from which an owner scope is recomputed."""

    base_claims_ref: ArtifactRef
    base_claims_content_hash: Digest
    requested_authority_purpose: str = Field(min_length=1)


def derive_claim_ledger_owner_scope_ref(
    value: ClaimLedgerOwnerKeyDerivationInput,
) -> Digest:
    """Recompute the owner scope from candidate bytes and requested purpose."""

    mapping = value.model_dump(mode="json", exclude_none=False)
    encoded = to_canonical_bytes(mapping, CHRONOLOGY_CANON_SPEC)
    preimage = _OWNER_SCOPE_PREFIX + len(encoded).to_bytes(8, "big") + encoded
    return "sha256:" + hashlib.sha256(preimage).hexdigest()


class ClaimLedgerOwnerKey(_StrictFrozenModel):
    """Owner-qualified key for one immutable-root Claim Ledger lineage."""

    scope_ref: Digest
    claim_owner_ref: str = Field(min_length=1)
    authority_purpose: str = Field(min_length=1)
    derivation_input: ClaimLedgerOwnerKeyDerivationInput | None = None

    @model_validator(mode="after")
    def _scope_is_recomputed_when_derivation_is_present(self) -> ClaimLedgerOwnerKey:
        derivation = self.derivation_input
        if derivation is None:
            raise ValueError("claim_owner_derivation_missing")
        if self.scope_ref != derive_claim_ledger_owner_scope_ref(derivation):
            raise ValueError("claim_owner_scope_mismatch")
        if self.authority_purpose != derivation.requested_authority_purpose:
            raise ValueError("claim_owner_authority_purpose_mismatch")
        return self


class ClaimLedgerIssuanceNonReceipt(_StrictFrozenModel):
    """Typed refusal to issue or verify one immutable Claim Ledger root."""

    status: Literal["not_established", "rejected"]
    code: Literal[
        "claim_root_issuance_not_established",
        "claim_root_issuance_content_mismatch",
        "claim_root_denominator_mismatch",
        "claim_root_provenance_untrusted",
    ]


class ClaimLedgerHeadResolutionNonReceipt(_StrictFrozenModel):
    """Typed refusal to treat any Claim Ledger artifact as current."""

    result_kind: Literal["non_receipt"] = "non_receipt"
    status: Literal["not_established", "rejected"]
    code: Literal[
        "claim_head_absent",
        "claim_head_issuance_unverified",
        "claim_head_content_mismatch",
        "claim_head_conflict",
    ]


class ClaimLedgerCandidateProjection(_StrictFrozenModel):
    """Non-authoritative summary of candidate bytes before root issuance."""

    ledger_summary: dict[str, Any]
    blocked_summary: dict[str, Any]


class ClaimLedgerPreparationStatement(_StrictFrozenModel):
    """Non-self-referential preparation for one candidate initial ledger."""

    schema_version: Literal["polisyos.claim-ledger.preparation.v1"] = (
        "polisyos.claim-ledger.preparation.v1"
    )
    owner_key: ClaimLedgerOwnerKey
    base_claims_ref: ArtifactRef
    base_claims_content_hash: Digest
    source_artifact_refs: tuple[ArtifactRef, ...]
    source_artifact_content_hashes: tuple[Digest, ...]
    initialization_policy_ref: ArtifactRef
    initialization_policy_content_hash: Digest
    initialization_policy_verifier_provenance_ref: ArtifactRef
    initial_ledger_ref: ArtifactRef
    initial_ledger_content_hash: Digest

    @model_validator(mode="after")
    def _source_refs_and_hashes_biject(self) -> ClaimLedgerPreparationStatement:
        if len(self.source_artifact_refs) != len(self.source_artifact_content_hashes):
            raise ValueError("claim_preparation_source_ref_hash_count_mismatch")
        if len({str(ref.artifact_id) for ref in self.source_artifact_refs}) != len(
            self.source_artifact_refs
        ):
            raise ValueError("claim_preparation_source_ref_duplicate")
        derivation = self.owner_key.derivation_input
        if derivation is None:  # Defensive for pre-validation shaped objects.
            raise ValueError("claim_owner_derivation_missing")
        if (
            self.base_claims_ref != derivation.base_claims_ref
            or self.base_claims_content_hash != derivation.base_claims_content_hash
            or self.owner_key.authority_purpose != derivation.requested_authority_purpose
        ):
            raise ValueError("claim_preparation_owner_derivation_mismatch")
        return self


class PreparedClaimLedgerInitialization(_StrictFrozenModel):
    """Sealed handle returned before a decision packet is advertised."""

    preparation_ref: ArtifactRef
    preparation_content_hash: Digest
    owner_key: ClaimLedgerOwnerKey
    initial_ledger_ref: ArtifactRef
    initial_ledger_content_hash: Digest


class ClaimLedgerRootBasisStatement(_StrictFrozenModel):
    """Exact packet, ledger, preparation and denominator join for one root."""

    owner_key: ClaimLedgerOwnerKey
    preparation_ref: ArtifactRef
    preparation_content_hash: Digest
    decision_packet_ref: ArtifactRef
    decision_packet_content_hash: Digest
    initial_ledger_ref: ArtifactRef
    initial_ledger_content_hash: Digest
    denominator_receipt_ref: ArtifactRef
    denominator_receipt_content_hash: Digest


class ClaimLedgerRootStatement(_StrictFrozenModel):
    """Immutable Claim root issued over an exact root basis."""

    schema_version: Literal["polisyos.claim-ledger.root.v1"] = "polisyos.claim-ledger.root.v1"
    root_identity: Digest
    basis_ref: ArtifactRef
    basis_content_hash: Digest
    issuance_evidence_ref: ArtifactRef
    issuance_evidence_content_hash: Digest
    issuance_verifier_provenance_ref: ArtifactRef

    @model_validator(mode="after")
    def _root_identity_is_the_exact_basis(self) -> ClaimLedgerRootStatement:
        if self.root_identity != self.basis_content_hash:
            raise ValueError("claim_root_identity_basis_mismatch")
        return self


class PersistedClaimLedgerRoot(_StrictFrozenModel):
    """Readback-bound handle for an immutable Claim root."""

    root_receipt_ref: ArtifactRef
    root_receipt_content_hash: Digest
    statement: ClaimLedgerRootStatement


class ClaimLedgerRootVerificationReceipt(_StrictFrozenModel):
    """Independent exact-root verification statement."""

    root_ref: ArtifactRef
    root_content_hash: Digest
    verifier_provenance_ref: ArtifactRef
    disposition: Literal["verified"] = "verified"


class VerifiedClaimLedgerIssuance(_StrictFrozenModel):
    """Positive root issuance plus independently persisted verifier receipt."""

    root: PersistedClaimLedgerRoot
    verifier_receipt_ref: ArtifactRef
    verifier_receipt_content_hash: Digest
    predicate_class: Literal["independently_reconciled"] = "independently_reconciled"


class ClaimLedgerHeadStatement(_StrictFrozenModel):
    """Non-self-referential current-head statement for one immutable root."""

    schema_version: Literal["polisyos.claim-ledger.head.v1"] = "polisyos.claim-ledger.head.v1"
    root_identity: Digest
    root_receipt_ref: ArtifactRef
    root_receipt_content_hash: Digest
    owner_key: ClaimLedgerOwnerKey
    ledger_artifact_ref: ArtifactRef
    ledger_raw_cas_hash: Digest
    generation: int = Field(ge=0)
    predecessor_head_ref: ArtifactRef | None
    bridge_result_refs: tuple[ArtifactRef, ...]
    issuance_verifier_receipt_ref: ArtifactRef
    issuance_verifier_receipt_content_hash: Digest

    @model_validator(mode="after")
    def _predecessor_shape_matches_generation(self) -> ClaimLedgerHeadStatement:
        if self.generation == 0 and self.predecessor_head_ref is not None:
            raise ValueError("claim_head_genesis_has_predecessor")
        if self.generation > 0 and self.predecessor_head_ref is None:
            raise ValueError("claim_head_entry_predecessor_missing")
        bridge_ids = tuple(str(ref.artifact_id) for ref in self.bridge_result_refs)
        if len(bridge_ids) != len(set(bridge_ids)):
            raise ValueError("claim_head_bridge_result_duplicate")
        return self


class PersistedClaimLedgerHead(_StrictFrozenModel):
    """Persisted Claim head with its ref outside the statement preimage."""

    head_ref: ArtifactRef
    head_content_hash: Digest
    statement: ClaimLedgerHeadStatement

    @model_validator(mode="after")
    def _statement_hash_is_recomputed(self) -> PersistedClaimLedgerHead:
        if self.head_content_hash != c4_semantic_digest(
            "claim_ledger_head",
            self.statement,
        ):
            raise ValueError("claim_persisted_head_content_hash_mismatch")
        return self


class ClaimLedgerLifecycleLimitation(_StrictFrozenModel):
    """One owner-derived lifecycle limitation on the current Claim head."""

    claim_id: str = Field(min_length=1)
    action: Literal[
        "blocked",
        "invalidated",
        "marked_stale",
        "merged",
        "review_required",
        "split",
        "superseded",
        "withdrawn",
    ]


class ClaimLedgerCurrentHeadProjection(_StrictFrozenModel):
    """Exact consumer view derived from one verified head and owner export."""

    schema_version: Literal["polisyos.claim-ledger.current-head-projection.v1"] = (
        "polisyos.claim-ledger.current-head-projection.v1"
    )
    run_id: str = Field(min_length=1)
    owner_key: ClaimLedgerOwnerKey
    root_identity: Digest
    root_receipt_ref: ArtifactRef
    root_receipt_content_hash: Digest
    head_ref: ArtifactRef
    head_content_hash: Digest
    head_generation: int = Field(ge=0)
    ledger_artifact_ref: ArtifactRef
    ledger_raw_cas_hash: Digest
    issuance_verifier_receipt_ref: ArtifactRef
    issuance_verifier_receipt_content_hash: Digest
    claim_currentness: Literal["current", "not_established"]
    claim_bridge_pending: bool
    completed_batch_denominator_established: bool
    pending_receipt_refs: tuple[Digest, ...] = ()
    pending_batch_receipt_refs: tuple[Digest, ...] = ()
    pending_affected_claim_ids: tuple[str, ...] = ()
    pending_mapping_unresolved: bool = False
    lifecycle_limitations: tuple[ClaimLedgerLifecycleLimitation, ...] = ()
    predicate_class: Literal["independently_reconciled"] = "independently_reconciled"

    @model_validator(mode="after")
    def _owner_view_is_total_and_canonical(self) -> ClaimLedgerCurrentHeadProjection:
        if self.owner_key.authority_purpose != CLAIM_LEDGER_AUTHORITY_PURPOSE:
            raise ValueError("claim_current_head_authority_purpose_mismatch")
        for values, code in (
            (self.pending_receipt_refs, "claim_current_head_pending_refs_not_canonical"),
            (
                self.pending_batch_receipt_refs,
                "claim_current_head_pending_batches_not_canonical",
            ),
            (
                self.pending_affected_claim_ids,
                "claim_current_head_pending_claims_not_canonical",
            ),
        ):
            if values != tuple(sorted(set(values))):
                raise ValueError(code)
        limitations = tuple((row.claim_id, row.action) for row in self.lifecycle_limitations)
        if limitations != tuple(sorted(set(limitations))):
            raise ValueError("claim_current_head_lifecycle_not_canonical")
        expected_pending = bool(self.pending_receipt_refs or self.pending_batch_receipt_refs)
        if self.claim_bridge_pending != expected_pending:
            raise ValueError("claim_owner_pending_projection_invalid")
        expected_currentness = (
            "current"
            if not expected_pending and self.completed_batch_denominator_established
            else "not_established"
        )
        if self.claim_currentness != expected_currentness:
            raise ValueError("claim_owner_pending_projection_invalid")
        if (
            not expected_pending
            and self.completed_batch_denominator_established
            and (self.pending_affected_claim_ids or self.pending_mapping_unresolved)
        ):
            raise ValueError("claim_owner_pending_projection_invalid")
        return self


def project_claim_ledger_current_head(
    *,
    head: PersistedClaimLedgerHead,
    claim_export: ClaimLedgerExport,
) -> ClaimLedgerCurrentHeadProjection:
    """Bind one owner export to the exact verified head read by its consumer."""

    metadata = claim_export.metadata
    pending = metadata.get("claim_bridge_pending")
    currentness = metadata.get("claim_currentness")
    pending_refs = metadata.get("pending_receipt_refs")
    batch_refs = metadata.get("pending_batch_receipt_refs")
    affected = metadata.get("pending_affected_claim_ids")
    unresolved = metadata.get("pending_mapping_unresolved")
    denominator_established = metadata.get("completed_batch_denominator_established")
    lifecycle = metadata.get("lifecycle_limitation_by_claim")
    if (
        not isinstance(pending, bool)
        or currentness not in {"current", "not_established"}
        or not isinstance(pending_refs, list)
        or not isinstance(batch_refs, list)
        or not isinstance(affected, list)
        or not isinstance(unresolved, bool)
        or not isinstance(denominator_established, bool)
        or not isinstance(lifecycle, Mapping)
        or any(not isinstance(value, str) for value in (*pending_refs, *batch_refs, *affected))
        or any(
            not isinstance(claim_id, str) or not isinstance(action, str)
            for claim_id, action in lifecycle.items()
        )
    ):
        raise ValueError("claim_owner_pending_projection_invalid")
    projection = ClaimLedgerCurrentHeadProjection(
        run_id=claim_export.run_id,
        owner_key=head.statement.owner_key,
        root_identity=head.statement.root_identity,
        root_receipt_ref=head.statement.root_receipt_ref,
        root_receipt_content_hash=head.statement.root_receipt_content_hash,
        head_ref=head.head_ref,
        head_content_hash=head.head_content_hash,
        head_generation=head.statement.generation,
        ledger_artifact_ref=head.statement.ledger_artifact_ref,
        ledger_raw_cas_hash=head.statement.ledger_raw_cas_hash,
        issuance_verifier_receipt_ref=(head.statement.issuance_verifier_receipt_ref),
        issuance_verifier_receipt_content_hash=(
            head.statement.issuance_verifier_receipt_content_hash
        ),
        claim_currentness=currentness,
        claim_bridge_pending=pending,
        completed_batch_denominator_established=denominator_established,
        pending_receipt_refs=tuple(pending_refs),
        pending_batch_receipt_refs=tuple(batch_refs),
        pending_affected_claim_ids=tuple(affected),
        pending_mapping_unresolved=unresolved,
        lifecycle_limitations=tuple(
            ClaimLedgerLifecycleLimitation(claim_id=claim_id, action=action)
            for claim_id, action in sorted(lifecycle.items())
        ),
    )
    if claim_export.audience.value == "public":
        by_id = {claim.claim_id: claim for claim in claim_export.claims}
        frozen_ids = set(by_id) if projection.pending_mapping_unresolved else set(affected)
        if any(
            claim_id not in by_id
            or by_id[claim_id].visible
            or claim_id not in claim_export.omitted_claim_ids
            for claim_id in frozen_ids
        ):
            raise ValueError("claim_owner_pending_public_projection_bypass")
    return projection


class ClaimLedgerHeadReadbackStatement(_StrictFrozenModel):
    """Durability readback for one atomic Claim-head pointer change."""

    schema_version: Literal["polisyos.claim-ledger.head-readback.v1"] = (
        "polisyos.claim-ledger.head-readback.v1"
    )
    owner_key: ClaimLedgerOwnerKey
    root_identity: Digest
    expected_prior_head_ref: ArtifactRef | None
    observed_head_ref: ArtifactRef
    observed_head_content_hash: Digest
    observed_generation: int = Field(ge=0)
    durable_pointer_content_hash: Digest
    disposition: Literal["verified"] = "verified"


class ClaimLedgerHeadAdvanced(_StrictFrozenModel):
    """Successful durable head advance after readback under the same lock."""

    result_kind: Literal["advanced"] = "advanced"
    owner_key: ClaimLedgerOwnerKey
    root_identity: Digest
    prior_head_ref: ArtifactRef | None
    new_head: PersistedClaimLedgerHead
    durable_pointer_content_hash: Digest
    readback_receipt_ref: ArtifactRef

    @model_validator(mode="after")
    def _new_head_binds_result(self) -> ClaimLedgerHeadAdvanced:
        statement = self.new_head.statement
        if statement.owner_key != self.owner_key or statement.root_identity != self.root_identity:
            raise ValueError("claim_head_advance_owner_or_root_mismatch")
        if statement.predecessor_head_ref != self.prior_head_ref:
            raise ValueError("claim_head_advance_predecessor_mismatch")
        return self


class ClaimLedgerHeadAdvanceConflict(_StrictFrozenModel):
    """CAS conflict that preserves both the expected and observed heads."""

    result_kind: Literal["conflict"] = "conflict"
    owner_key: ClaimLedgerOwnerKey
    expected_head_ref: ArtifactRef | None
    observed_head_ref: ArtifactRef | None


ClaimLedgerHeadAdvanceReceipt = Annotated[
    ClaimLedgerHeadAdvanced | ClaimLedgerHeadAdvanceConflict | ClaimLedgerHeadResolutionNonReceipt,
    Field(discriminator="result_kind"),
]


class DecisionPacketRootRow(_StrictFrozenModel):
    """One canonical packet-to-ledger row in the owner root denominator."""

    decision_packet_ref: ArtifactRef | None
    decision_packet_content_hash: Digest | None
    ledger_artifact_ref: ArtifactRef
    ledger_raw_cas_hash: Digest

    @model_validator(mode="after")
    def _packet_ref_and_hash_pair(self) -> DecisionPacketRootRow:
        if (self.decision_packet_ref is None) != (self.decision_packet_content_hash is None):
            raise ValueError("claim_root_row_packet_ref_hash_mismatch")
        return self


class DecisionPacketRootSnapshotStatement(_StrictFrozenModel):
    """Canonical owner walk over every packet/root candidate row."""

    schema_version: Literal["polisyos.claim-ledger.decision-packet-root-snapshot.v1"] = (
        "polisyos.claim-ledger.decision-packet-root-snapshot.v1"
    )
    row_count: int = Field(ge=0)
    ordered_rows: tuple[DecisionPacketRootRow, ...]
    verifier_provenance_ref: ArtifactRef

    @model_validator(mode="after")
    def _rows_are_complete_and_canonical(self) -> DecisionPacketRootSnapshotStatement:
        if self.row_count != len(self.ordered_rows):
            raise ValueError("claim_root_snapshot_row_count_mismatch")
        keys = tuple(
            (
                "" if row.decision_packet_ref is None else str(row.decision_packet_ref.artifact_id),
                str(row.ledger_artifact_ref.artifact_id),
            )
            for row in self.ordered_rows
        )
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("claim_root_snapshot_rows_not_canonical_unique")
        return self


class DecisionPacketRootSnapshot(_StrictFrozenModel):
    """Persisted owner snapshot and exact statement."""

    snapshot_ref: ArtifactRef
    snapshot_content_hash: Digest
    statement: DecisionPacketRootSnapshotStatement


class ClaimLedgerRootAssessment(_StrictFrozenModel):
    """One ledger's exact root-registration disposition."""

    decision_packet_ref: ArtifactRef | None
    ledger_artifact_ref: ArtifactRef
    ledger_raw_cas_hash: Digest
    root_identity: Digest | None
    root_receipt_ref: ArtifactRef | None
    root_receipt_content_hash: Digest | None
    root_issuance_evidence_ref: ArtifactRef | None
    owner_key: ClaimLedgerOwnerKey | None
    disposition: Literal["registered", "migration_required", "not_established"]
    failure_code: str | None

    @model_validator(mode="after")
    def _registered_rows_have_complete_authority(self) -> ClaimLedgerRootAssessment:
        authority_values = (
            self.root_identity,
            self.root_receipt_ref,
            self.root_receipt_content_hash,
            self.root_issuance_evidence_ref,
            self.owner_key,
        )
        if self.disposition == "registered":
            if any(value is None for value in authority_values) or self.failure_code is not None:
                raise ValueError("claim_root_registered_authority_incomplete")
        elif self.failure_code is None:
            raise ValueError("claim_root_nonregistered_failure_code_missing")
        return self


class ClaimLedgerRootDenominatorReceipt(_StrictFrozenModel):
    """Owner snapshot independently reconciled to a complete ArtifactStore walk."""

    owner_snapshot_ref: ArtifactRef
    owner_snapshot_content_hash: Digest
    independent_walk_content_hash: Digest
    owner_snapshot_row_count: int = Field(ge=0)
    independent_walk_row_count: int = Field(ge=0)
    declared_root_count: int = Field(ge=0)
    assessments: tuple[ClaimLedgerRootAssessment, ...]
    denominator_hash: Digest
    predicate_class: Literal["independently_reconciled"] = "independently_reconciled"

    @model_validator(mode="after")
    def _walk_counts_and_assessments_biject(self) -> ClaimLedgerRootDenominatorReceipt:
        if (
            self.owner_snapshot_row_count != self.independent_walk_row_count
            or self.declared_root_count != len(self.assessments)
            or self.owner_snapshot_row_count != self.declared_root_count
        ):
            raise ValueError("claim_root_denominator_count_mismatch")
        if self.denominator_hash != c4_semantic_digest(
            "claim_ledger_root_denominator",
            self,
        ):
            raise ValueError("claim_root_denominator_hash_mismatch")
        return self


def _annotation_model(annotation: object) -> type[BaseModel] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    origin = get_origin(annotation)
    if origin in {UnionType, Union}:
        for member in get_args(annotation):
            model = _annotation_model(member)
            if model is not None:
                return model
    return None


def _sequence_item(annotation: object) -> object | None:
    origin = get_origin(annotation)
    if origin in {list, tuple}:
        args = get_args(annotation)
        return args[0] if args else None
    if origin in {UnionType, Union}:
        for member in get_args(annotation):
            item = _sequence_item(member)
            if item is not None:
                return item
    return None


def _derive_dependency_paths(
    model: type[BaseModel],
    *,
    prefix: str = "",
) -> set[str]:
    """Derive reference-bearing paths without enumerating Claim field names."""

    paths: set[str] = set()
    for name, model_field in model.model_fields.items():
        annotation = model_field.annotation
        item = _sequence_item(annotation)
        item_model = _annotation_model(item) if item is not None else None
        direct_model = _annotation_model(annotation)
        if name == "source_attribution":
            paths.add(f"{prefix}{name}[]")
            continue
        if name.endswith("_refs"):
            suffix = "[].artifact_id" if item_model is ArtifactRef else "[]"
            paths.add(f"{prefix}{name}{suffix}")
            continue
        if name.endswith("_ref"):
            suffix = ".artifact_id" if direct_model is ArtifactRef else ""
            paths.add(f"{prefix}{name}{suffix}")
            continue
        if item_model is not None and item_model is not ArtifactRef:
            paths.update(
                _derive_dependency_paths(
                    item_model,
                    prefix=f"{prefix}{name}[].",
                )
            )
    return paths


class ClaimDependencyClaimAssociation(_StrictFrozenModel):
    """One dependency value bound to exactly the claims that carry it."""

    dependency_ref: str = Field(min_length=1)
    ordered_claim_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _claim_ids_are_canonical_unique(self) -> ClaimDependencyClaimAssociation:
        if self.ordered_claim_ids != tuple(sorted(set(self.ordered_claim_ids))):
            raise ValueError("claim_dependency_association_ids_not_canonical_unique")
        return self


class ClaimDependencyDenominatorRow(_StrictFrozenModel):
    """One registered ClaimRecord dependency path and its extracted targets."""

    field_path: str = Field(min_length=1)
    dependency_kind: str = Field(min_length=1)
    ordered_dependency_refs: tuple[str, ...]
    ordered_claim_ids: tuple[str, ...]
    ordered_dependency_claim_associations: tuple[ClaimDependencyClaimAssociation, ...]

    @model_validator(mode="after")
    def _values_are_canonical_unique(self) -> ClaimDependencyDenominatorRow:
        if self.ordered_dependency_refs != tuple(sorted(set(self.ordered_dependency_refs))):
            raise ValueError("claim_dependency_refs_not_canonical_unique")
        if self.ordered_claim_ids != tuple(sorted(set(self.ordered_claim_ids))):
            raise ValueError("claim_dependency_claim_ids_not_canonical_unique")
        association_refs = tuple(
            row.dependency_ref for row in self.ordered_dependency_claim_associations
        )
        if association_refs != tuple(sorted(set(association_refs))):
            raise ValueError("claim_dependency_associations_not_canonical_unique")
        if association_refs != self.ordered_dependency_refs:
            raise ValueError("claim_dependency_association_denominator_mismatch")
        associated_claim_ids = tuple(
            sorted(
                {
                    claim_id
                    for row in self.ordered_dependency_claim_associations
                    for claim_id in row.ordered_claim_ids
                }
            )
        )
        if associated_claim_ids != self.ordered_claim_ids:
            raise ValueError("claim_dependency_association_claim_denominator_mismatch")
        return self


class ClaimDependencyFieldRule(_StrictFrozenModel):
    """One data-owned path used to derive Claim dependency membership."""

    field_path: str = Field(min_length=1)
    dependency_kind: str = Field(min_length=1)
    value_kind: Literal["string", "artifact_id"]


class ClaimDependencyFieldRegistry(_StrictFrozenModel):
    """Complete content-bound dependency-path registry for ``ClaimRecord``."""

    schema_version: Literal["polisyos.gy.claim-dependency-field-registry.v1"]
    model: Literal["polisyos.scientist.evidence.claims.models.ClaimRecord"]
    fields: tuple[ClaimDependencyFieldRule, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _paths_are_canonical_and_unique(self) -> ClaimDependencyFieldRegistry:
        paths = self.declared_paths
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("claim_dependency_registry_paths_not_canonical_unique")
        return self

    @property
    def declared_paths(self) -> tuple[str, ...]:
        """Return the exact ordered field-path denominator."""

        return tuple(row.field_path for row in self.fields)

    @classmethod
    def from_path(cls, source: Path) -> ClaimDependencyFieldRegistry:
        """Load a strict registry from exact tracked bytes."""

        return cls.model_validate_json(source.read_bytes())

    @staticmethod
    def derive_model_paths() -> tuple[str, ...]:
        """Derive the complete dependency-bearing path set from Claim models."""

        from polisyos.scientist.evidence.claims.models import ClaimRecord

        return tuple(sorted(_derive_dependency_paths(ClaimRecord)))


class ClaimDependencyDenominatorReceipt(_StrictFrozenModel):
    """Content-bound mapping from an epoch batch denominator to Claim ids."""

    schema_version: Literal["polisyos.claim-ledger.dependency-denominator.v1"] = (
        "polisyos.claim-ledger.dependency-denominator.v1"
    )
    registry_ref: ArtifactRef
    registry_content_hash: Digest
    claim_schema_content_hash: Digest
    ledger_artifact_ref: ArtifactRef
    ledger_raw_cas_hash: Digest
    batch_dependency_denominator_ref: Digest
    requested_dependency_keys: tuple[str, ...]
    declared_path_count: int = Field(ge=0)
    observed_path_count: int = Field(ge=0)
    ordered_dependency_rows: tuple[ClaimDependencyDenominatorRow, ...]
    ordered_affected_claim_ids: tuple[str, ...]
    denominator_hash: Digest
    predicate_class: Literal["independently_reconciled"] = "independently_reconciled"

    @model_validator(mode="after")
    def _dependency_rows_are_complete_and_unique(self) -> ClaimDependencyDenominatorReceipt:
        if self.declared_path_count != self.observed_path_count:
            raise ValueError("claim_target_denominator_unresolved")
        if self.declared_path_count != len(self.ordered_dependency_rows):
            raise ValueError("claim_dependency_path_count_mismatch")
        paths = tuple(row.field_path for row in self.ordered_dependency_rows)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("claim_dependency_paths_not_canonical_unique")
        if len(self.requested_dependency_keys) != len(set(self.requested_dependency_keys)):
            raise ValueError("claim_dependency_request_not_canonical_unique")
        if self.ordered_affected_claim_ids != tuple(sorted(set(self.ordered_affected_claim_ids))):
            raise ValueError("claim_dependency_affected_ids_not_canonical_unique")
        if self.denominator_hash != c4_semantic_digest(
            "claim_dependency_denominator",
            self,
        ):
            raise ValueError("claim_dependency_denominator_hash_mismatch")
        return self

    def unresolved_requested_dependency_keys(self) -> tuple[str, ...]:
        """Return requested keys absent from the complete observed mapping."""

        observed = {
            dependency
            for row in self.ordered_dependency_rows
            for dependency in row.ordered_dependency_refs
        }
        return tuple(key for key in self.requested_dependency_keys if key not in observed)


class ClaimBridgePendingStatement(_StrictFrozenModel):
    """Durable freeze between Decision Validity completion and Claim head advance."""

    schema_version: Literal["polisyos.claim-ledger.bridge-pending.v1"] = (
        "polisyos.claim-ledger.bridge-pending.v1"
    )
    batch_receipt_ref: ArtifactRef
    batch_receipt_content_hash: Digest
    decision_packet_ref: ArtifactRef
    decision_packet_content_hash: Digest
    requested_query_context_ref: Digest
    target_mapping_ref: ArtifactRef
    target_mapping_content_hash: Digest
    ordered_affected_claim_ids: tuple[str, ...]
    expected_head_ref: ArtifactRef | None
    mapping_status: Literal["resolved", "unresolved"]
    limitation_code: Literal["claim_target_denominator_unresolved"] | None

    @model_validator(mode="after")
    def _mapping_status_is_total(self) -> ClaimBridgePendingStatement:
        if self.ordered_affected_claim_ids != tuple(sorted(set(self.ordered_affected_claim_ids))):
            raise ValueError("claim_pending_affected_ids_not_canonical_unique")
        if self.mapping_status == "resolved" and self.limitation_code is not None:
            raise ValueError("claim_pending_resolved_limitation_present")
        if self.mapping_status == "unresolved" and self.limitation_code is None:
            raise ValueError("claim_pending_unresolved_limitation_missing")
        if self.mapping_status == "unresolved" and self.ordered_affected_claim_ids:
            raise ValueError("claim_pending_unresolved_has_targets")
        return self


class PersistedClaimBridgePending(_StrictFrozenModel):
    """Persisted pending-freeze handle."""

    pending_ref: ArtifactRef
    pending_content_hash: Digest
    statement: ClaimBridgePendingStatement


class ClaimBridgePendingProjection(_StrictFrozenModel):
    """Owner-derived pending view; immutable receipts, not a mutable flag, are truth."""

    active_pendings: tuple[PersistedClaimBridgePending, ...] = ()
    unmaterialized_batch_receipt_refs: tuple[ArtifactRef, ...] = ()
    ordered_affected_claim_ids: tuple[str, ...] = ()
    unresolved_mapping: bool = False
    completed_batch_denominator_established: bool

    @model_validator(mode="after")
    def _projection_is_canonical(self) -> ClaimBridgePendingProjection:
        pending_ids = tuple(str(row.pending_ref.artifact_id) for row in self.active_pendings)
        batch_ids = tuple(str(row.artifact_id) for row in self.unmaterialized_batch_receipt_refs)
        if pending_ids != tuple(sorted(set(pending_ids))):
            raise ValueError("claim_pending_projection_refs_not_canonical_unique")
        if batch_ids != tuple(sorted(set(batch_ids))):
            raise ValueError("claim_pending_projection_batches_not_canonical_unique")
        if self.ordered_affected_claim_ids != tuple(sorted(set(self.ordered_affected_claim_ids))):
            raise ValueError("claim_pending_projection_claim_ids_not_canonical_unique")
        if not self.completed_batch_denominator_established and not self.unresolved_mapping:
            raise ValueError("claim_pending_projection_unknown_denominator_not_limited")
        return self


@dataclass(frozen=True, slots=True)
class _VerifiedCompletedEpochValidityBatch:
    """Sealed completed-batch evidence passed only to the Claim owner."""

    evidence: PersistedEpochValidityBatchEvidence
    targets: tuple[EpochValidityBatchTarget, ...]
    dependency_denominator: ClaimDependencyDenominatorReceipt | None
    target_mapping_ref: ArtifactRef
    target_mapping_content_hash: Digest
    mapping_status: Literal["resolved", "unresolved"]


def _persist_claim_bridge_pending(
    *,
    store: ArtifactStore,
    statement: ClaimBridgePendingStatement,
) -> PersistedClaimBridgePending:
    """Persist and read back the exact pre-Claim-advance freeze."""

    pending_ref, pending_content_hash = _persist_profiled_statement(
        store=store,
        record="claim_bridge_pending",
        value=statement,
    )
    reloaded = _read_profiled_statement(
        store=store,
        record="claim_bridge_pending",
        ref=pending_ref,
        model=ClaimBridgePendingStatement,
    )
    if reloaded != statement:
        raise ValueError("claim_bridge_pending_readback_mismatch")
    return PersistedClaimBridgePending(
        pending_ref=pending_ref,
        pending_content_hash=pending_content_hash,
        statement=statement,
    )


class ClaimLifecycleBridgeResultStatement(_StrictFrozenModel):
    """Pre-head persisted result; it deliberately carries no new-head ref."""

    schema_version: Literal["polisyos.claim-ledger.bridge-result.v1"] = (
        "polisyos.claim-ledger.bridge-result.v1"
    )
    owner_key: ClaimLedgerOwnerKey
    batch_receipt_ref: ArtifactRef
    batch_receipt_content_hash: Digest
    decision_packet_ref: ArtifactRef
    decision_packet_content_hash: Digest
    requested_query_context_ref: Digest
    pending_ref: ArtifactRef
    pending_content_hash: Digest
    dependency_denominator_ref: ArtifactRef
    dependency_denominator_content_hash: Digest
    lifecycle_result_ref: ArtifactRef
    lifecycle_result_content_hash: Digest
    prior_ledger_ref: ArtifactRef
    prior_ledger_content_hash: Digest
    next_ledger_ref: ArtifactRef
    next_ledger_content_hash: Digest
    ordered_affected_claim_ids: tuple[str, ...]
    predicate_class: Literal["independently_reconciled"] = "independently_reconciled"


class PersistedClaimLifecycleBridgeResult(_StrictFrozenModel):
    """Persisted pre-head bridge result."""

    bridge_result_ref: ArtifactRef
    bridge_result_content_hash: Digest
    statement: ClaimLifecycleBridgeResultStatement


class ClaimLifecycleBridgeAdvanced(_StrictFrozenModel):
    """Positive bridge composition of a pre-head result and durable head advance."""

    result_kind: Literal["advanced"] = "advanced"
    bridge_result: PersistedClaimLifecycleBridgeResult
    head_advance: ClaimLedgerHeadAdvanced


class ClaimLifecycleBridgeNonReceipt(_StrictFrozenModel):
    """Typed negative that retains the exact pending freeze."""

    result_kind: Literal["non_receipt"] = "non_receipt"
    code: Literal[
        "claim_ledger_owner_not_established",
        "claim_target_denominator_unresolved",
        "claim_head_absent",
        "claim_head_conflict",
        "claim_batch_evidence_rejected",
    ]
    pending: PersistedClaimBridgePending | None = None
    decisive_evidence_refs: tuple[ArtifactRef, ...] = ()


ClaimLifecycleBridgeAuthorityResult = Annotated[
    ClaimLifecycleBridgeAdvanced | ClaimLifecycleBridgeNonReceipt,
    Field(discriminator="result_kind"),
]


def _extract_dependency_values(
    value: object,
    field_path: str,
    *,
    value_kind: Literal["string", "artifact_id"],
) -> tuple[str, ...]:
    current: list[object] = [value]
    for raw_segment in field_path.split("."):
        is_many = raw_segment.endswith("[]")
        segment = raw_segment[:-2] if is_many else raw_segment
        following: list[object] = []
        for item in current:
            if isinstance(item, BaseModel):
                resolved = getattr(item, segment)
            elif isinstance(item, dict):
                resolved = item.get(segment)
            else:
                raise ValueError("claim_dependency_registry_path_unreadable")
            if resolved is None:
                continue
            if is_many:
                if not isinstance(resolved, (list, tuple)):
                    raise ValueError("claim_dependency_registry_path_not_repeated")
                following.extend(resolved)
            else:
                following.append(resolved)
        current = following
    if value_kind == "artifact_id":
        if any(not isinstance(item, artifacts.ArtifactID) for item in current):
            raise ValueError("claim_dependency_artifact_id_type_mismatch")
    elif any(not isinstance(item, str) for item in current):
        raise ValueError("claim_dependency_string_type_mismatch")
    return tuple(sorted({str(item) for item in current}))


@dataclass(frozen=True, slots=True)
class ClaimDependencyDenominatorResolver:
    """Reconcile the tracked dependency registry to exact Claim bytes."""

    store: ArtifactStore
    registry_path: Path

    def persist_registry(self) -> tuple[ArtifactRef, Digest]:
        """Persist the exact tracked registry after schema reconciliation."""

        registry_raw = self.registry_path.read_bytes()
        registry = ClaimDependencyFieldRegistry.model_validate_json(registry_raw)
        if registry.declared_paths != registry.derive_model_paths():
            raise ValueError("claim_dependency_registry_schema_mismatch")
        registry_ref = self.store.put_bytes(
            registry_raw,
            ArtifactWriteOptions(
                kind="architecture.gy.claim_dependency_field_registry",
                media_type="application/json",
                schema=artifacts.SchemaInfo(
                    name=registry.schema_version,
                    version="1",
                ),
            ),
        )
        return registry_ref, _raw_content_hash(registry_raw)

    def resolve(
        self,
        *,
        ledger_artifact_ref: ArtifactRef,
        batch_dependency_denominator_ref: Digest,
        requested_dependency_keys: tuple[str, ...],
    ) -> (
        tuple[ClaimDependencyDenominatorReceipt, ArtifactRef, Digest]
        | ClaimLifecycleBridgeNonReceipt
    ):
        """Persist the complete mapping or return the one fail-closed terminal."""

        from polisyos.scientist.evidence.claims.audit import (
            CLAIM_LEDGER_V2_KIND,
            CLAIM_LEDGER_V2_SCHEMA_NAME,
            CLAIM_LEDGER_V2_SCHEMA_VERSION,
        )
        from polisyos.scientist.evidence.claims.ledger import (
            CLAIM_LEDGER_KIND,
            CLAIM_LEDGER_SCHEMA_NAME,
            CLAIM_LEDGER_SCHEMA_VERSION,
        )
        from polisyos.scientist.evidence.claims.lifecycle import AppendOnlyClaimLedger
        from polisyos.scientist.evidence.claims.models import ClaimLedger, ClaimRecord

        try:
            registry_raw = self.registry_path.read_bytes()
            registry = ClaimDependencyFieldRegistry.model_validate_json(registry_raw)
            registry_ref, registry_content_hash = self.persist_registry()
            if not requested_dependency_keys or requested_dependency_keys != tuple(
                dict.fromkeys(requested_dependency_keys)
            ):
                raise ValueError("claim_dependency_request_not_canonical_unique")
            ledger_raw = self.store.get_bytes(ledger_artifact_ref.artifact_id)
            ledger_report = self.store.verify(ledger_artifact_ref.artifact_id)
            ledger_manifest = self.store.get_manifest(ledger_artifact_ref.artifact_id)
            if (
                not ledger_report.ok
                or _raw_content_hash(ledger_raw) != str(ledger_artifact_ref.artifact_id)
                or ledger_artifact_ref.kind != ledger_manifest.kind
                or ledger_artifact_ref.media_type != ledger_manifest.media_type
            ):
                raise ValueError("claim_dependency_ledger_content_mismatch")
            payload = from_canonical_bytes(ledger_raw)
            if ledger_manifest.kind == CLAIM_LEDGER_V2_KIND:
                if ledger_manifest.artifact_schema != artifacts.SchemaInfo(
                    name=CLAIM_LEDGER_V2_SCHEMA_NAME,
                    version=CLAIM_LEDGER_V2_SCHEMA_VERSION,
                ):
                    raise ValueError("claim_dependency_ledger_profile_mismatch")
                ledger = AppendOnlyClaimLedger.model_validate(payload)
                claims = tuple(ledger.current_claims)
            elif ledger_manifest.kind == CLAIM_LEDGER_KIND:
                if ledger_manifest.artifact_schema != artifacts.SchemaInfo(
                    name=CLAIM_LEDGER_SCHEMA_NAME,
                    version=CLAIM_LEDGER_SCHEMA_VERSION,
                ):
                    raise ValueError("claim_dependency_ledger_profile_mismatch")
                ledger = ClaimLedger.model_validate(payload)
                claims = tuple(ledger.claims)
            else:
                raise ValueError("claim_dependency_ledger_profile_mismatch")
            if any(not isinstance(claim, ClaimRecord) for claim in claims):
                raise ValueError("claim_dependency_claim_type_mismatch")

            requested = set(requested_dependency_keys)
            affected: set[str] = set()
            rows: list[ClaimDependencyDenominatorRow] = []
            for rule in registry.fields:
                dependencies: set[str] = set()
                row_claims: set[str] = set()
                claims_by_dependency: dict[str, set[str]] = {}
                for claim in claims:
                    values = set(
                        _extract_dependency_values(
                            claim,
                            rule.field_path,
                            value_kind=rule.value_kind,
                        )
                    )
                    dependencies.update(values)
                    for dependency in values:
                        claims_by_dependency.setdefault(dependency, set()).add(claim.claim_id)
                    if values:
                        row_claims.add(claim.claim_id)
                    if values.intersection(requested):
                        affected.add(claim.claim_id)
                rows.append(
                    ClaimDependencyDenominatorRow(
                        field_path=rule.field_path,
                        dependency_kind=rule.dependency_kind,
                        ordered_dependency_refs=tuple(sorted(dependencies)),
                        ordered_claim_ids=tuple(sorted(row_claims)),
                        ordered_dependency_claim_associations=tuple(
                            ClaimDependencyClaimAssociation(
                                dependency_ref=dependency,
                                ordered_claim_ids=tuple(sorted(claims_by_dependency[dependency])),
                            )
                            for dependency in sorted(claims_by_dependency)
                        ),
                    )
                )
            schema_raw = to_canonical_bytes(
                ClaimRecord.model_json_schema(mode="validation"),
                CHRONOLOGY_CANON_SPEC,
            )
            draft: dict[str, object] = {
                "schema_version": "polisyos.claim-ledger.dependency-denominator.v1",
                "registry_ref": registry_ref.model_dump(mode="json"),
                "registry_content_hash": registry_content_hash,
                "claim_schema_content_hash": _raw_content_hash(schema_raw),
                "ledger_artifact_ref": ledger_artifact_ref.model_dump(mode="json"),
                "ledger_raw_cas_hash": _raw_content_hash(ledger_raw),
                "batch_dependency_denominator_ref": batch_dependency_denominator_ref,
                "requested_dependency_keys": requested_dependency_keys,
                "declared_path_count": len(registry.fields),
                "observed_path_count": len(rows),
                "ordered_dependency_rows": [row.model_dump(mode="json") for row in rows],
                "ordered_affected_claim_ids": tuple(sorted(affected)),
                "denominator_hash": "sha256:" + "0" * 64,
                "predicate_class": "independently_reconciled",
            }
            draft["denominator_hash"] = c4_semantic_digest(
                "claim_dependency_denominator",
                draft,
            )
            receipt = ClaimDependencyDenominatorReceipt.model_validate(draft)
            receipt_ref, receipt_content_hash = _persist_profiled_statement(
                store=self.store,
                record="claim_dependency_denominator",
                value=receipt,
            )
            return receipt, receipt_ref, receipt_content_hash
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ClaimLifecycleBridgeNonReceipt(code="claim_target_denominator_unresolved")


class _VerifiedClaimLedgerInitializationPolicy(_StrictFrozenModel):
    """Owner-verifier result; callers cannot construct policy authority from a ref."""

    policy_ref: ArtifactRef
    policy_content_hash: Digest
    claim_owner_ref: str = Field(min_length=1)
    authority_purpose: str = Field(min_length=1)
    verifier_provenance_ref: ArtifactRef
    predicate_class: Literal["independently_reconciled"] = "independently_reconciled"


class ClaimLedgerRootIssuanceEvidence(_StrictFrozenModel):
    """Opaque owner-native issuance evidence bound to basis and admitted policy."""

    evidence_ref: ArtifactRef
    evidence_content_hash: Digest
    basis_ref: ArtifactRef
    basis_content_hash: Digest
    initialization_policy_ref: ArtifactRef
    initialization_policy_content_hash: Digest
    verifier_provenance_ref: ArtifactRef


@runtime_checkable
class ClaimLedgerInitializationPolicyResolver(Protocol):
    """Resolve an independently verified owner policy for exact candidate bytes."""

    def resolve_for(
        self,
        *,
        derivation_input: ClaimLedgerOwnerKeyDerivationInput,
    ) -> _VerifiedClaimLedgerInitializationPolicy | ClaimLedgerIssuanceNonReceipt:
        """Return an admitted policy or the typed institutional negative."""
        ...


@runtime_checkable
class ClaimLedgerRootIssuer(Protocol):
    """Issue opaque owner evidence over one exact root basis and policy."""

    def issue_exact(
        self,
        *,
        basis_ref: ArtifactRef,
        basis_content_hash: Digest,
        policy: _VerifiedClaimLedgerInitializationPolicy,
    ) -> ClaimLedgerRootIssuanceEvidence | ClaimLedgerIssuanceNonReceipt:
        """Return basis-bound issuance evidence without referring to the future root."""
        ...


@runtime_checkable
class ClaimLedgerIssuanceVerifier(Protocol):
    """Independently reload and verify one exact persisted root."""

    def verify_exact(
        self,
        *,
        root_receipt_ref: ArtifactRef,
        expected_owner_key: ClaimLedgerOwnerKey | None = None,
    ) -> VerifiedClaimLedgerIssuance | ClaimLedgerIssuanceNonReceipt:
        """Return only an independently reconciled positive receipt."""
        ...


@runtime_checkable
class ClaimLedgerIssuanceEvidenceIndex(Protocol):
    """Owner-appointed lookup for issuance evidence over one legacy ledger."""

    def resolve_for_ledger(
        self,
        *,
        ledger_artifact_ref: ArtifactRef,
    ) -> ArtifactRef | ClaimLedgerHeadResolutionNonReceipt:
        """Return appointed evidence, never store-discovered authority."""
        ...


@dataclass(frozen=True, slots=True)
class NoClaimLedgerInitializationPolicyResolver:
    """Production resolver with no appointed Claim policy authority."""

    def resolve_for(
        self,
        *,
        derivation_input: ClaimLedgerOwnerKeyDerivationInput,
    ) -> ClaimLedgerIssuanceNonReceipt:
        del derivation_input
        return ClaimLedgerIssuanceNonReceipt(
            status="not_established",
            code="claim_root_issuance_not_established",
        )


@dataclass(frozen=True, slots=True)
class NoClaimLedgerIssuanceEvidenceIndex:
    """Negative production index: repository presence does not appoint issuance."""

    def resolve_for_ledger(
        self,
        *,
        ledger_artifact_ref: ArtifactRef,
    ) -> ClaimLedgerHeadResolutionNonReceipt:
        del ledger_artifact_ref
        return ClaimLedgerHeadResolutionNonReceipt(
            status="not_established",
            code="claim_head_issuance_unverified",
        )


def _owner_storage_key(owner_key: ClaimLedgerOwnerKey) -> str:
    raw = to_canonical_bytes(
        owner_key.model_dump(mode="json", exclude_none=False),
        CHRONOLOGY_CANON_SPEC,
    )
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class _ClaimLedgerMutationPermit:
    """Fieldless capability held only by the concrete Claim owner."""


_CLAIM_LEDGER_MUTATION_PERMIT = _ClaimLedgerMutationPermit()


class _LockedClaimLedgerHeadCAS:
    """Private interprocess CAS for durable current-head pointers."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        root: Path,
        closure_verifier: Callable[
            [PersistedClaimLedgerHead],
            ClaimLedgerHeadResolutionNonReceipt | None,
        ],
    ) -> None:
        self._store = store
        self._root = root
        self._closure_verifier = closure_verifier

    def resolve(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
    ) -> PersistedClaimLedgerHead | ClaimLedgerHeadResolutionNonReceipt:
        lock = self._lock_path(owner_key)
        self._root.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            current = self._read_pointer(owner_key=owner_key)
            if isinstance(current, PersistedClaimLedgerHead):
                closure_failure = self._closure_failure(current)
                if closure_failure is not None:
                    return closure_failure
            return current
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ClaimLedgerHeadResolutionNonReceipt(
                status="rejected",
                code="claim_head_content_mismatch",
            )
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    def export_locked(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
        formatter: Callable[[PersistedClaimLedgerHead], ClaimLedgerExport],
    ) -> ClaimLedgerExport | ClaimLedgerHeadResolutionNonReceipt:
        """Format one head/pending snapshot under the same lock as pending writes."""

        self._root.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(
            self._lock_path(owner_key),
            os.O_CREAT | os.O_RDWR | os.O_CLOEXEC,
            0o600,
        )
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            current = self._read_pointer(owner_key=owner_key)
            if not isinstance(current, PersistedClaimLedgerHead):
                return current
            closure_failure = self._closure_failure(current)
            if closure_failure is not None:
                return closure_failure
            return formatter(current)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ClaimLedgerHeadResolutionNonReceipt(
                status="rejected",
                code="claim_head_content_mismatch",
            )
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    def advance(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
        expected_prior_head_ref: ArtifactRef | None,
        new_head: PersistedClaimLedgerHead,
        permit: _ClaimLedgerMutationPermit,
    ) -> ClaimLedgerHeadAdvanceReceipt:
        if permit is not _CLAIM_LEDGER_MUTATION_PERMIT:
            return ClaimLedgerHeadResolutionNonReceipt(
                status="rejected",
                code="claim_head_content_mismatch",
            )
        self._root.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(
            self._lock_path(owner_key),
            os.O_CREAT | os.O_RDWR | os.O_CLOEXEC,
            0o600,
        )
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            candidate = self._reload_candidate_head(new_head)
            if isinstance(candidate, ClaimLedgerHeadResolutionNonReceipt):
                return candidate
            closure_failure = self._closure_failure(candidate)
            if closure_failure is not None:
                return closure_failure
            observed = self._read_pointer(owner_key=owner_key, absent_ok=True)
            if (
                isinstance(observed, ClaimLedgerHeadResolutionNonReceipt)
                and observed.code != "claim_head_absent"
            ):
                return observed
            if isinstance(observed, PersistedClaimLedgerHead):
                closure_failure = self._closure_failure(observed)
                if closure_failure is not None:
                    return closure_failure
            observed_ref = (
                observed.head_ref if isinstance(observed, PersistedClaimLedgerHead) else None
            )
            if observed_ref != expected_prior_head_ref:
                if (
                    isinstance(observed, PersistedClaimLedgerHead)
                    and observed.head_ref == new_head.head_ref
                    and observed.head_content_hash == new_head.head_content_hash
                    and new_head.statement.predecessor_head_ref == expected_prior_head_ref
                ):
                    try:
                        return self._readback_advanced(
                            owner_key=owner_key,
                            expected_prior_head_ref=expected_prior_head_ref,
                            new_head=observed,
                        )
                    except (KeyError, OSError, RuntimeError, TypeError, ValueError):
                        return ClaimLedgerHeadResolutionNonReceipt(
                            status="rejected",
                            code="claim_head_content_mismatch",
                        )
                return ClaimLedgerHeadAdvanceConflict(
                    owner_key=owner_key,
                    expected_head_ref=expected_prior_head_ref,
                    observed_head_ref=observed_ref,
                )
            try:
                self._validate_transition(
                    owner_key=owner_key,
                    prior=observed,
                    new_head=new_head,
                )
            except ValueError:
                return ClaimLedgerHeadResolutionNonReceipt(
                    status="rejected",
                    code="claim_head_content_mismatch",
                )
            pointer_raw = self._pointer_bytes(new_head)
            pointer_path = self._pointer_path(owner_key)
            temporary: Path | None = None
            try:
                fd, temporary_name = tempfile.mkstemp(
                    prefix=f".{pointer_path.name}.",
                    suffix=".tmp",
                    dir=self._root,
                )
                temporary = Path(temporary_name)
                try:
                    view = memoryview(pointer_raw)
                    while view:
                        written = os.write(fd, view)
                        if written < 1:
                            raise OSError("claim_head_pointer_short_write")
                        view = view[written:]
                    os.fsync(fd)
                finally:
                    os.close(fd)
                os.replace(temporary, pointer_path)
                temporary = None
                directory_fd = os.open(self._root, os.O_RDONLY | os.O_CLOEXEC)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except (KeyError, OSError, RuntimeError, TypeError, ValueError):
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
                return ClaimLedgerHeadResolutionNonReceipt(
                    status="rejected",
                    code="claim_head_content_mismatch",
                )
            reloaded = self._read_pointer(owner_key=owner_key)
            if not isinstance(reloaded, PersistedClaimLedgerHead) or reloaded != new_head:
                return ClaimLedgerHeadResolutionNonReceipt(
                    status="rejected",
                    code="claim_head_content_mismatch",
                )
            closure_failure = self._closure_failure(reloaded)
            if closure_failure is not None:
                return closure_failure
            try:
                return self._readback_advanced(
                    owner_key=owner_key,
                    expected_prior_head_ref=expected_prior_head_ref,
                    new_head=reloaded,
                )
            except (KeyError, OSError, RuntimeError, TypeError, ValueError):
                return ClaimLedgerHeadResolutionNonReceipt(
                    status="rejected",
                    code="claim_head_content_mismatch",
                )
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    def freeze_pending(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
        permit: _ClaimLedgerMutationPermit,
        persist_pending: Callable[
            [PersistedClaimLedgerHead],
            PersistedClaimBridgePending,
        ],
    ) -> (
        tuple[PersistedClaimLedgerHead, PersistedClaimBridgePending]
        | ClaimLedgerHeadResolutionNonReceipt
    ):
        """Bind pending evidence to the exact closed predecessor under its lock."""

        if permit is not _CLAIM_LEDGER_MUTATION_PERMIT:
            return ClaimLedgerHeadResolutionNonReceipt(
                status="rejected",
                code="claim_head_content_mismatch",
            )
        self._root.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(
            self._lock_path(owner_key),
            os.O_CREAT | os.O_RDWR | os.O_CLOEXEC,
            0o600,
        )
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            current = self._read_pointer(owner_key=owner_key)
            if not isinstance(current, PersistedClaimLedgerHead):
                return current
            closure_failure = self._closure_failure(current)
            if closure_failure is not None:
                return closure_failure
            pending = persist_pending(current)
            reloaded = _read_profiled_statement(
                store=self._store,
                record="claim_bridge_pending",
                ref=pending.pending_ref,
                model=ClaimBridgePendingStatement,
            )
            if (
                not isinstance(reloaded, ClaimBridgePendingStatement)
                or reloaded != pending.statement
                or reloaded.expected_head_ref != current.head_ref
                or c4_semantic_digest("claim_bridge_pending", reloaded)
                != pending.pending_content_hash
            ):
                raise ValueError("claim_bridge_pending_freeze_mismatch")
            return current, pending
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ClaimLedgerHeadResolutionNonReceipt(
                status="rejected",
                code="claim_head_content_mismatch",
            )
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    def readback_existing_current(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
        expected_bridge_result_ref: ArtifactRef,
    ) -> ClaimLedgerHeadAdvanceReceipt:
        """Emit a fresh readback for an idempotent retry already in current history."""

        self._root.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(
            self._lock_path(owner_key),
            os.O_CREAT | os.O_RDWR | os.O_CLOEXEC,
            0o600,
        )
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            current = self._read_pointer(owner_key=owner_key)
            if not isinstance(current, PersistedClaimLedgerHead):
                return current
            closure_failure = self._closure_failure(current)
            if closure_failure is not None:
                return closure_failure
            if expected_bridge_result_ref not in current.statement.bridge_result_refs:
                return ClaimLedgerHeadAdvanceConflict(
                    owner_key=owner_key,
                    expected_head_ref=current.statement.predecessor_head_ref,
                    observed_head_ref=current.head_ref,
                )
            return self._readback_advanced(
                owner_key=owner_key,
                expected_prior_head_ref=current.statement.predecessor_head_ref,
                new_head=current,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ClaimLedgerHeadResolutionNonReceipt(
                status="rejected",
                code="claim_head_content_mismatch",
            )
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    def _reload_candidate_head(
        self,
        candidate: PersistedClaimLedgerHead,
    ) -> PersistedClaimLedgerHead | ClaimLedgerHeadResolutionNonReceipt:
        try:
            parsed = _read_profiled_statement(
                store=self._store,
                record="claim_ledger_head",
                ref=candidate.head_ref,
                model=ClaimLedgerHeadStatement,
            )
            if not isinstance(parsed, ClaimLedgerHeadStatement):
                raise ValueError("claim_head_statement_type_mismatch")
            if (
                parsed != candidate.statement
                or c4_semantic_digest("claim_ledger_head", parsed) != candidate.head_content_hash
            ):
                raise ValueError("claim_head_candidate_binding_mismatch")
            return candidate
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ClaimLedgerHeadResolutionNonReceipt(
                status="rejected",
                code="claim_head_content_mismatch",
            )

    def _closure_failure(
        self,
        head: PersistedClaimLedgerHead,
    ) -> ClaimLedgerHeadResolutionNonReceipt | None:
        try:
            return self._closure_verifier(head)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ClaimLedgerHeadResolutionNonReceipt(
                status="rejected",
                code="claim_head_content_mismatch",
            )

    def _readback_advanced(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
        expected_prior_head_ref: ArtifactRef | None,
        new_head: PersistedClaimLedgerHead,
    ) -> ClaimLedgerHeadAdvanced:
        pointer_raw = self._pointer_path(owner_key).read_bytes()
        pointer_hash = _raw_content_hash(pointer_raw)
        statement = ClaimLedgerHeadReadbackStatement(
            owner_key=owner_key,
            root_identity=new_head.statement.root_identity,
            expected_prior_head_ref=expected_prior_head_ref,
            observed_head_ref=new_head.head_ref,
            observed_head_content_hash=new_head.head_content_hash,
            observed_generation=new_head.statement.generation,
            durable_pointer_content_hash=pointer_hash,
        )
        readback_ref, _ = _persist_profiled_statement(
            store=self._store,
            record="claim_ledger_head_readback",
            value=statement,
        )
        return ClaimLedgerHeadAdvanced(
            owner_key=owner_key,
            root_identity=new_head.statement.root_identity,
            prior_head_ref=expected_prior_head_ref,
            new_head=new_head,
            durable_pointer_content_hash=pointer_hash,
            readback_receipt_ref=readback_ref,
        )

    def _validate_transition(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
        prior: PersistedClaimLedgerHead | ClaimLedgerHeadResolutionNonReceipt,
        new_head: PersistedClaimLedgerHead,
    ) -> None:
        statement = new_head.statement
        if statement.owner_key != owner_key:
            raise ValueError("claim_head_owner_key_mismatch")
        if isinstance(prior, ClaimLedgerHeadResolutionNonReceipt):
            if statement.generation != 0 or statement.predecessor_head_ref is not None:
                raise ValueError("claim_head_initial_generation_invalid")
            return
        prior_statement = prior.statement
        if (
            statement.generation != prior_statement.generation + 1
            or statement.predecessor_head_ref != prior.head_ref
        ):
            raise ValueError("claim_head_generation_or_predecessor_mismatch")
        if (
            statement.owner_key != prior_statement.owner_key
            or statement.root_identity != prior_statement.root_identity
            or statement.root_receipt_ref != prior_statement.root_receipt_ref
            or statement.root_receipt_content_hash != prior_statement.root_receipt_content_hash
            or statement.issuance_verifier_receipt_ref
            != prior_statement.issuance_verifier_receipt_ref
            or statement.issuance_verifier_receipt_content_hash
            != prior_statement.issuance_verifier_receipt_content_hash
        ):
            raise ValueError("claim_head_root_or_issuance_changed")

    def _read_pointer(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
        absent_ok: bool = False,
    ) -> PersistedClaimLedgerHead | ClaimLedgerHeadResolutionNonReceipt:
        pointer = self._pointer_path(owner_key)
        if not pointer.exists():
            if absent_ok:
                return ClaimLedgerHeadResolutionNonReceipt(
                    status="not_established",
                    code="claim_head_absent",
                )
            return ClaimLedgerHeadResolutionNonReceipt(
                status="not_established",
                code="claim_head_absent",
            )
        try:
            payload = json.loads(pointer.read_text(encoding="utf-8"))
            head_ref = ArtifactRef.model_validate(payload["head_ref"])
            head_hash = str(payload["head_content_hash"])
            parsed = _read_profiled_statement(
                store=self._store,
                record="claim_ledger_head",
                ref=head_ref,
                model=ClaimLedgerHeadStatement,
            )
            if not isinstance(parsed, ClaimLedgerHeadStatement):
                raise ValueError("claim_head_statement_type_mismatch")
            if (
                parsed.owner_key != owner_key
                or c4_semantic_digest("claim_ledger_head", parsed) != head_hash
                or int(payload["generation"]) != parsed.generation
                or str(payload["root_identity"]) != parsed.root_identity
            ):
                raise ValueError("claim_head_pointer_binding_mismatch")
            return PersistedClaimLedgerHead(
                head_ref=head_ref,
                head_content_hash=head_hash,
                statement=parsed,
            )
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return ClaimLedgerHeadResolutionNonReceipt(
                status="rejected",
                code="claim_head_content_mismatch",
            )

    def _pointer_bytes(self, head: PersistedClaimLedgerHead) -> bytes:
        return to_canonical_bytes(
            {
                "head_ref": head.head_ref.model_dump(mode="json"),
                "head_content_hash": head.head_content_hash,
                "generation": head.statement.generation,
                "root_identity": head.statement.root_identity,
            },
            CHRONOLOGY_CANON_SPEC,
        )

    def _pointer_path(self, owner_key: ClaimLedgerOwnerKey) -> Path:
        return self._root / f"{_owner_storage_key(owner_key)}.json"

    def _lock_path(self, owner_key: ClaimLedgerOwnerKey) -> Path:
        return self._root / f"{_owner_storage_key(owner_key)}.lock"


@runtime_checkable
class DecisionPacketRootRepository(Protocol):
    """Canonical packet owner walk for the Claim root denominator."""

    def resolve_owner_snapshot(self) -> DecisionPacketRootSnapshot:
        """Persist and return the complete owner snapshot."""
        ...


@runtime_checkable
class ArtifactStoreClaimRootWalk(Protocol):
    """Independent artifact-store walk over packet-to-ledger rows."""

    def enumerate_independently(self) -> tuple[DecisionPacketRootRow, ...]:
        """Return canonical rows without consuming the owner snapshot."""
        ...


def _claim_ledger_ref_from_packet_payload(payload: object) -> ArtifactRef | None:
    if not isinstance(payload, dict):
        return None
    raw = payload.get("claim_ledger_v2_ref")
    ledger_kind = "scientist.claim_ledger_v2"
    if raw is None:
        artifacts_payload = payload.get("artifacts")
        if isinstance(artifacts_payload, dict):
            raw = artifacts_payload.get("claim_ledger_v2_ref")
    if raw is None:
        raw = payload.get("claims_ref")
        ledger_kind = "scientist.claim_ledger"
    if raw is None:
        artifacts_payload = payload.get("artifacts")
        if isinstance(artifacts_payload, dict):
            raw = artifacts_payload.get("claims_ref")
            ledger_kind = "scientist.claim_ledger"
    if isinstance(raw, dict):
        try:
            return ArtifactRef.model_validate(raw)
        except (TypeError, ValueError):
            return None
    if isinstance(raw, str) and raw.startswith("sha256:"):
        return ArtifactRef(
            artifact_id=raw,
            kind=ledger_kind,
            media_type="application/json",
        )
    return None


def _packet_root_row(
    *, store: ArtifactStore, packet_ref: ArtifactRef
) -> DecisionPacketRootRow | None:
    raw = _read_exact_artifact(
        store=store,
        ref=packet_ref,
        expected_kind="scientist.decision_packet",
        expected_media_type="application/json",
    )
    ledger_ref = _claim_ledger_ref_from_packet_payload(from_canonical_bytes(raw))
    if ledger_ref is None:
        return None
    ledger_raw = _load_exact_claim_ledger_bytes(store=store, ref=ledger_ref)
    return DecisionPacketRootRow(
        decision_packet_ref=packet_ref,
        decision_packet_content_hash=_raw_content_hash(raw),
        ledger_artifact_ref=ledger_ref,
        ledger_raw_cas_hash=_raw_content_hash(ledger_raw),
    )


def _independent_packet_root_row(
    *,
    store: ArtifactStore,
    packet_ref: ArtifactRef,
) -> DecisionPacketRootRow | None:
    """Reparse one packet without consuming the owner repository's projection."""

    raw = _read_exact_artifact(
        store=store,
        ref=packet_ref,
        expected_kind="scientist.decision_packet",
        expected_media_type="application/json",
    )
    payload = from_canonical_bytes(raw)
    if not isinstance(payload, dict):
        return None
    packet_artifacts = payload.get("artifacts")
    nested = packet_artifacts if isinstance(packet_artifacts, dict) else {}
    selected: tuple[object | None, str] = (
        payload.get("claim_ledger_v2_ref"),
        "scientist.claim_ledger_v2",
    )
    if selected[0] is None:
        selected = (nested.get("claim_ledger_v2_ref"), "scientist.claim_ledger_v2")
    if selected[0] is None:
        selected = (payload.get("claims_ref"), "scientist.claim_ledger")
    if selected[0] is None:
        selected = (nested.get("claims_ref"), "scientist.claim_ledger")
    raw_ledger_ref, expected_kind = selected
    if raw_ledger_ref is None:
        return None
    if isinstance(raw_ledger_ref, dict):
        ledger_ref = ArtifactRef.model_validate(raw_ledger_ref)
    elif isinstance(raw_ledger_ref, str) and raw_ledger_ref.startswith("sha256:"):
        ledger_ref = ArtifactRef(
            artifact_id=raw_ledger_ref,
            kind=expected_kind,
            media_type="application/json",
        )
    else:
        raise ValueError("claim_root_independent_ledger_ref_invalid")
    ledger_raw = _load_exact_claim_ledger_bytes(store=store, ref=ledger_ref)
    return DecisionPacketRootRow(
        decision_packet_ref=packet_ref,
        decision_packet_content_hash=_raw_content_hash(raw),
        ledger_artifact_ref=ledger_ref,
        ledger_raw_cas_hash=_raw_content_hash(ledger_raw),
    )


def _load_exact_claim_ledger_bytes(
    *,
    store: ArtifactStore,
    ref: ArtifactRef,
) -> bytes:
    """Verify one v1/v2 Claim artifact through its native exact-profile loader."""

    from polisyos.scientist.evidence.claims.audit import (
        CLAIM_LEDGER_V2_KIND,
        _load_append_only_claim_ledger,
    )
    from polisyos.scientist.evidence.claims.ledger import (
        CLAIM_LEDGER_KIND,
        _load_claim_ledger,
    )

    if ref.kind == CLAIM_LEDGER_V2_KIND:
        _load_append_only_claim_ledger(store, ref)
    elif ref.kind == CLAIM_LEDGER_KIND:
        _load_claim_ledger(store, ref)
    else:
        raise ValueError("claim_root_ledger_profile_mismatch")
    return store.get_bytes(ref.artifact_id)


def _resolve_decision_packet_claim_ledger(
    *,
    store: ArtifactStore,
    packet_ref: ArtifactRef,
) -> DecisionPacketRootRow:
    """Reload one packet and return its exact Claim-ledger binding."""

    row = _packet_root_row(store=store, packet_ref=packet_ref)
    if row is None:
        raise ValueError("claim_root_packet_ledger_binding_missing")
    return row


@dataclass(frozen=True, slots=True)
class ArtifactStoreDecisionPacketRootRepository:
    """Owner-side complete packet snapshot derived from artifact manifests."""

    store: ArtifactStore
    verifier_provenance_ref: ArtifactRef

    def resolve_owner_snapshot(self) -> DecisionPacketRootSnapshot:
        rows: list[DecisionPacketRootRow] = []
        for artifact_id in sorted(self.store.iter_artifact_ids(), key=str):
            manifest = self.store.get_manifest(artifact_id)
            if manifest.kind != "scientist.decision_packet":
                continue
            row = _packet_root_row(
                store=self.store,
                packet_ref=ArtifactRef(
                    artifact_id=artifact_id,
                    kind=manifest.kind,
                    media_type=manifest.media_type,
                ),
            )
            if row is not None:
                rows.append(row)
        ordered = tuple(
            sorted(
                rows,
                key=lambda row: (
                    ""
                    if row.decision_packet_ref is None
                    else str(row.decision_packet_ref.artifact_id),
                    str(row.ledger_artifact_ref.artifact_id),
                ),
            )
        )
        statement = DecisionPacketRootSnapshotStatement(
            row_count=len(ordered),
            ordered_rows=ordered,
            verifier_provenance_ref=self.verifier_provenance_ref,
        )
        ref, content_hash = _persist_profiled_statement(
            store=self.store,
            record="decision_packet_root_snapshot",
            value=statement,
        )
        return DecisionPacketRootSnapshot(
            snapshot_ref=ref,
            snapshot_content_hash=content_hash,
            statement=statement,
        )


@dataclass(frozen=True, slots=True)
class FilesystemArtifactStoreClaimRootWalk:
    """Filesystem-side walk independent of `ArtifactStore.iter_artifact_ids`."""

    store: ArtifactStore
    artifact_root: Path

    def enumerate_independently(self) -> tuple[DecisionPacketRootRow, ...]:
        rows: list[DecisionPacketRootRow] = []
        for manifest_path in sorted(
            (self.artifact_root / "artifacts" / "sha256").glob("*/*/*.manifest.json")
        ):
            try:
                manifest = artifacts.ArtifactManifest.model_validate_json(
                    manifest_path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError):
                raise ValueError("claim_root_independent_manifest_unreadable") from None
            if manifest.kind != "scientist.decision_packet":
                continue
            row = _independent_packet_root_row(
                store=self.store,
                packet_ref=ArtifactRef(
                    artifact_id=manifest.artifact_id,
                    kind=manifest.kind,
                    media_type=manifest.media_type,
                ),
            )
            if row is not None:
                rows.append(row)
        return tuple(
            sorted(
                rows,
                key=lambda row: (
                    ""
                    if row.decision_packet_ref is None
                    else str(row.decision_packet_ref.artifact_id),
                    str(row.ledger_artifact_ref.artifact_id),
                ),
            )
        )


@dataclass(frozen=True, slots=True)
class RepositoryClaimLedgerRootInventory:
    """Reconcile the owner packet snapshot against an independent store walk."""

    store: ArtifactStore
    decision_packets: DecisionPacketRootRepository
    independent_walk: ArtifactStoreClaimRootWalk
    issuance_evidence: ClaimLedgerIssuanceEvidenceIndex = field(
        default_factory=NoClaimLedgerIssuanceEvidenceIndex
    )

    def _assessment_for(self, row: DecisionPacketRootRow) -> ClaimLedgerRootAssessment:
        evidence_ref = self.issuance_evidence.resolve_for_ledger(
            ledger_artifact_ref=row.ledger_artifact_ref,
        )
        if isinstance(evidence_ref, ClaimLedgerHeadResolutionNonReceipt):
            return ClaimLedgerRootAssessment(
                decision_packet_ref=row.decision_packet_ref,
                ledger_artifact_ref=row.ledger_artifact_ref,
                ledger_raw_cas_hash=row.ledger_raw_cas_hash,
                root_identity=None,
                root_receipt_ref=None,
                root_receipt_content_hash=None,
                root_issuance_evidence_ref=None,
                owner_key=None,
                disposition="not_established",
                failure_code="claim_root_issuance_evidence_not_established",
            )

        matches: list[
            tuple[ArtifactRef, ClaimLedgerRootStatement, ClaimLedgerRootBasisStatement]
        ] = []
        profile = c4_profile("claim_ledger_root")
        for artifact_id in sorted(self.store.iter_artifact_ids(), key=str):
            manifest = self.store.get_manifest(artifact_id)
            if manifest.kind != profile.kind or manifest.media_type != profile.media_type:
                continue
            root_ref = ArtifactRef(
                artifact_id=artifact_id,
                kind=manifest.kind,
                media_type=manifest.media_type,
            )
            root = _read_profiled_statement(
                store=self.store,
                record="claim_ledger_root",
                ref=root_ref,
                model=ClaimLedgerRootStatement,
            )
            if not isinstance(root, ClaimLedgerRootStatement):
                continue
            basis = _read_profiled_statement(
                store=self.store,
                record="claim_ledger_root_basis",
                ref=root.basis_ref,
                model=ClaimLedgerRootBasisStatement,
            )
            if (
                isinstance(basis, ClaimLedgerRootBasisStatement)
                and root.issuance_evidence_ref == evidence_ref
                and basis.initial_ledger_ref == row.ledger_artifact_ref
                and basis.initial_ledger_content_hash == row.ledger_raw_cas_hash
                and basis.decision_packet_ref == row.decision_packet_ref
                and root.root_identity == root.basis_content_hash
                and root.basis_content_hash == c4_semantic_digest("claim_ledger_root_basis", basis)
            ):
                matches.append((root_ref, root, basis))
        if len(matches) != 1:
            return ClaimLedgerRootAssessment(
                decision_packet_ref=row.decision_packet_ref,
                ledger_artifact_ref=row.ledger_artifact_ref,
                ledger_raw_cas_hash=row.ledger_raw_cas_hash,
                root_identity=None,
                root_receipt_ref=None,
                root_receipt_content_hash=None,
                root_issuance_evidence_ref=evidence_ref,
                owner_key=None,
                disposition="not_established",
                failure_code=(
                    "claim_root_issuance_evidence_ambiguous"
                    if matches
                    else "claim_root_issuance_evidence_mismatch"
                ),
            )
        root_ref, root, basis = matches[0]
        return ClaimLedgerRootAssessment(
            decision_packet_ref=row.decision_packet_ref,
            ledger_artifact_ref=row.ledger_artifact_ref,
            ledger_raw_cas_hash=row.ledger_raw_cas_hash,
            root_identity=root.root_identity,
            root_receipt_ref=root_ref,
            root_receipt_content_hash=c4_semantic_digest("claim_ledger_root", root),
            root_issuance_evidence_ref=evidence_ref,
            owner_key=basis.owner_key,
            disposition="migration_required",
            failure_code="claim_root_migration_required",
        )

    def resolve_complete_roots(
        self,
    ) -> tuple[ClaimLedgerRootDenominatorReceipt, ArtifactRef, Digest]:
        snapshot = self.decision_packets.resolve_owner_snapshot()
        persisted_snapshot = _read_profiled_statement(
            store=self.store,
            record="decision_packet_root_snapshot",
            ref=snapshot.snapshot_ref,
            model=DecisionPacketRootSnapshotStatement,
        )
        if (
            not isinstance(persisted_snapshot, DecisionPacketRootSnapshotStatement)
            or persisted_snapshot != snapshot.statement
            or c4_semantic_digest(
                "decision_packet_root_snapshot",
                persisted_snapshot,
            )
            != snapshot.snapshot_content_hash
        ):
            raise _ClaimRootDenominatorMismatch("claim_root_owner_snapshot_content_mismatch")
        independent_rows = self.independent_walk.enumerate_independently()
        owner_rows = persisted_snapshot.ordered_rows
        if owner_rows != independent_rows:
            raise _ClaimRootDenominatorMismatch("claim_root_denominator_mismatch")
        independent_raw = to_canonical_bytes(
            [row.model_dump(mode="json", exclude_none=False) for row in independent_rows],
            CHRONOLOGY_CANON_SPEC,
        )
        assessments = tuple(self._assessment_for(row) for row in owner_rows)
        draft: dict[str, object] = {
            "owner_snapshot_ref": snapshot.snapshot_ref.model_dump(mode="json"),
            "owner_snapshot_content_hash": snapshot.snapshot_content_hash,
            "independent_walk_content_hash": _raw_content_hash(independent_raw),
            "owner_snapshot_row_count": len(owner_rows),
            "independent_walk_row_count": len(independent_rows),
            "declared_root_count": len(assessments),
            "assessments": [row.model_dump(mode="json") for row in assessments],
            "denominator_hash": "sha256:" + "0" * 64,
            "predicate_class": "independently_reconciled",
        }
        draft["denominator_hash"] = c4_semantic_digest(
            "claim_ledger_root_denominator",
            draft,
        )
        receipt = ClaimLedgerRootDenominatorReceipt.model_validate(draft)
        ref, content_hash = _persist_profiled_statement(
            store=self.store,
            record="claim_ledger_root_denominator",
            value=receipt,
        )
        return receipt, ref, content_hash


@runtime_checkable
class ClaimLedgerOwnerPort(Protocol):
    """Only authority-bearing Claim persistence and export boundary."""

    def persist_candidate_ledger(
        self,
        *,
        ledger: ClaimLedger,
        inputs: tuple[artifacts.InputRef, ...] = (),
    ) -> ArtifactRef:
        """Persist candidate bytes without issuing a root or current head."""
        ...

    def project_candidate_ledger(
        self,
        *,
        ledger: ClaimLedger,
    ) -> ClaimLedgerCandidateProjection:
        """Project candidate bytes without asserting currentness."""
        ...

    def prepare_initial_ledger(
        self,
        *,
        base_claims_ref: ArtifactRef,
        source_artifact_refs: tuple[ArtifactRef, ...],
    ) -> PreparedClaimLedgerInitialization | ClaimLedgerIssuanceNonReceipt:
        """Prepare an unadvertised initial ledger under an admitted policy."""
        ...

    def finalize_initial_root(
        self,
        *,
        preparation_ref: ArtifactRef,
        decision_packet_ref: ArtifactRef,
    ) -> ClaimLedgerHeadAdvanceReceipt | ClaimLedgerIssuanceNonReceipt:
        """Issue and register generation zero only after the packet is durable."""
        ...

    def resolve_current(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
    ) -> PersistedClaimLedgerHead | ClaimLedgerHeadResolutionNonReceipt:
        """Resolve one current root-verified head."""
        ...

    def advance_verified_batch(
        self,
        *,
        verified_batch: _VerifiedCompletedEpochValidityBatch,
        decision_packet_ref: ArtifactRef,
    ) -> ClaimLifecycleBridgeAuthorityResult:
        """Apply one independently resolved completed Decision Validity batch."""
        ...

    def append_verified_owner_event(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
        owner_event_ref: ArtifactRef,
    ) -> ClaimLedgerHeadAdvanceReceipt:
        """Append one independently verified owner event."""
        ...

    def export_current(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
        audience: ClaimExportAudience,
    ) -> ClaimLedgerExport | ClaimLedgerHeadResolutionNonReceipt:
        """Export only a root-verified current head."""
        ...

    def migrate_legacy_roots(
        self,
    ) -> tuple[ClaimLedgerHeadAdvanceReceipt | ClaimLedgerHeadResolutionNonReceipt, ...]:
        """Reconcile every legacy ledger from the complete owner inventory."""
        ...


@dataclass(frozen=True, slots=True)
class ClaimLedgerExportService:
    """Narrow export intake: callers provide only an owner key and audience."""

    claim_owner: ClaimLedgerOwnerPort

    def export(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
        audience: ClaimExportAudience,
    ) -> ClaimLedgerExport | ClaimLedgerHeadResolutionNonReceipt:
        """Resolve and format the owner's verified current head."""

        from polisyos.scientist.evidence.claims.export import ClaimLedgerExport

        result = self.claim_owner.export_current(owner_key=owner_key, audience=audience)
        if isinstance(result, ClaimLedgerExport):
            try:
                validated = ClaimLedgerExport.model_validate(result.model_dump(mode="python"))
                if validated.audience != audience:
                    raise ValueError("claim_export_audience_mismatch")
            except (TypeError, ValueError):
                return ClaimLedgerHeadResolutionNonReceipt(
                    status="rejected",
                    code="claim_head_content_mismatch",
                )
            return validated
        return result


def _resolve_claim_pending_projection(
    *,
    store: ArtifactStore,
    current: PersistedClaimLedgerHead,
    completed_batches: EpochValidityCompletedBatchEvidenceDenominator | None,
) -> ClaimBridgePendingProjection:
    """Reconcile pending receipts against the exact verified current head."""

    root = _read_profiled_statement(
        store=store,
        record="claim_ledger_root",
        ref=current.statement.root_receipt_ref,
        model=ClaimLedgerRootStatement,
    )
    if not isinstance(root, ClaimLedgerRootStatement):
        raise ValueError("claim_pending_root_type_mismatch")
    basis = _read_profiled_statement(
        store=store,
        record="claim_ledger_root_basis",
        ref=root.basis_ref,
        model=ClaimLedgerRootBasisStatement,
    )
    if not isinstance(basis, ClaimLedgerRootBasisStatement):
        raise ValueError("claim_pending_basis_type_mismatch")
    current_packet_ref = basis.decision_packet_ref
    current_packet_id = str(current_packet_ref.artifact_id)
    resolved_pending_ids: set[str] = set()
    materialized_batch_packets: set[tuple[str, str]] = set()
    for bridge_ref in current.statement.bridge_result_refs:
        bridge = _read_profiled_statement(
            store=store,
            record="claim_bridge_result",
            ref=bridge_ref,
            model=ClaimLifecycleBridgeResultStatement,
        )
        if not isinstance(bridge, ClaimLifecycleBridgeResultStatement):
            raise ValueError("claim_bridge_result_type_mismatch")
        if (
            bridge.decision_packet_ref != current_packet_ref
            or bridge.decision_packet_content_hash != basis.decision_packet_content_hash
        ):
            raise ValueError("claim_bridge_result_packet_mismatch")
        resolved_pending_ids.add(str(bridge.pending_ref.artifact_id))
        materialized_batch_packets.add(
            (
                str(bridge.batch_receipt_ref.artifact_id),
                current_packet_id,
            )
        )

    eligible_expected_heads: set[str] = {str(current.head_ref.artifact_id)}
    cursor = current
    while cursor.statement.predecessor_head_ref is not None:
        predecessor_ref = cursor.statement.predecessor_head_ref
        predecessor_statement = _read_profiled_statement(
            store=store,
            record="claim_ledger_head",
            ref=predecessor_ref,
            model=ClaimLedgerHeadStatement,
        )
        if not isinstance(predecessor_statement, ClaimLedgerHeadStatement):
            raise ValueError("claim_pending_predecessor_type_mismatch")
        if (
            predecessor_statement.owner_key != current.statement.owner_key
            or predecessor_statement.root_identity != current.statement.root_identity
            or predecessor_statement.generation + 1 != cursor.statement.generation
        ):
            raise ValueError("claim_pending_predecessor_chain_mismatch")
        eligible_expected_heads.add(str(predecessor_ref.artifact_id))
        cursor = PersistedClaimLedgerHead(
            head_ref=predecessor_ref,
            head_content_hash=c4_semantic_digest(
                "claim_ledger_head",
                predecessor_statement,
            ),
            statement=predecessor_statement,
        )

    pending_profile = c4_profile("claim_bridge_pending")
    active: list[PersistedClaimBridgePending] = []
    for artifact_id in sorted(store.iter_artifact_ids(), key=str):
        manifest = store.get_manifest(artifact_id)
        if (
            manifest.kind != pending_profile.kind
            or manifest.media_type != pending_profile.media_type
            or str(artifact_id) in resolved_pending_ids
        ):
            continue
        pending_ref = ArtifactRef(
            artifact_id=artifact_id,
            kind=manifest.kind,
            media_type=manifest.media_type,
        )
        statement = _read_profiled_statement(
            store=store,
            record="claim_bridge_pending",
            ref=pending_ref,
            model=ClaimBridgePendingStatement,
        )
        if (
            isinstance(statement, ClaimBridgePendingStatement)
            and statement.decision_packet_ref == current_packet_ref
            and statement.decision_packet_content_hash == basis.decision_packet_content_hash
            and statement.expected_head_ref is not None
            and str(statement.expected_head_ref.artifact_id) in eligible_expected_heads
        ):
            materialized_batch_packets.add(
                (
                    str(statement.batch_receipt_ref.artifact_id),
                    current_packet_id,
                )
            )
            active.append(
                PersistedClaimBridgePending(
                    pending_ref=pending_ref,
                    pending_content_hash=c4_semantic_digest(
                        "claim_bridge_pending",
                        statement,
                    ),
                    statement=statement,
                )
            )

    active.sort(key=lambda row: str(row.pending_ref.artifact_id))
    unmaterialized: tuple[ArtifactRef, ...] = ()
    denominator_established = completed_batches is not None
    if completed_batches is not None:
        first = completed_batches.enumerate_completed_epoch_batch_evidence()
        second = completed_batches.enumerate_completed_epoch_batch_evidence()
        if first != second:
            denominator_established = False
        else:
            unmaterialized = tuple(
                sorted(
                    (
                        row.batch_receipt_ref
                        for row in first
                        if current_packet_id in row.receipt.affected_packet_refs
                        and (
                            str(row.batch_receipt_ref.artifact_id),
                            current_packet_id,
                        )
                        not in materialized_batch_packets
                    ),
                    key=lambda ref: str(ref.artifact_id),
                )
            )
    affected = tuple(
        sorted(
            {claim_id for row in active for claim_id in row.statement.ordered_affected_claim_ids}
        )
    )
    return ClaimBridgePendingProjection(
        active_pendings=tuple(active),
        unmaterialized_batch_receipt_refs=unmaterialized,
        ordered_affected_claim_ids=affected,
        unresolved_mapping=(
            not denominator_established
            or bool(unmaterialized)
            or any(row.statement.mapping_status == "unresolved" for row in active)
        ),
        completed_batch_denominator_established=denominator_established,
    )


@dataclass(frozen=True, slots=True)
class UnappointedClaimLedgerOwner:
    """Production default when no institutional Claim root authority exists."""

    store: ArtifactStore

    def persist_candidate_ledger(
        self,
        *,
        ledger: ClaimLedger,
        inputs: tuple[artifacts.InputRef, ...] = (),
    ) -> ArtifactRef:
        """Persist candidate bytes while leaving currentness unestablished."""

        from polisyos.scientist.evidence.claims.ledger import _persist_claim_ledger

        return _persist_claim_ledger(
            self.store,
            ledger,
            inputs=list(inputs) if inputs else None,
        )

    def project_candidate_ledger(
        self,
        *,
        ledger: ClaimLedger,
    ) -> ClaimLedgerCandidateProjection:
        """Project candidate data while retaining absent authority."""

        from polisyos.scientist.evidence.claims.export import (
            _blocked_claim_summary,
            _claim_ledger_summary,
        )

        return ClaimLedgerCandidateProjection(
            ledger_summary=_claim_ledger_summary(ledger),
            blocked_summary=_blocked_claim_summary(ledger),
        )

    def prepare_initial_ledger(
        self,
        *,
        base_claims_ref: ArtifactRef,
        source_artifact_refs: tuple[ArtifactRef, ...],
    ) -> ClaimLedgerIssuanceNonReceipt:
        del base_claims_ref, source_artifact_refs
        return ClaimLedgerIssuanceNonReceipt(
            status="not_established",
            code="claim_root_issuance_not_established",
        )

    def finalize_initial_root(
        self,
        *,
        preparation_ref: ArtifactRef,
        decision_packet_ref: ArtifactRef,
    ) -> ClaimLedgerIssuanceNonReceipt:
        del preparation_ref, decision_packet_ref
        return ClaimLedgerIssuanceNonReceipt(
            status="not_established",
            code="claim_root_issuance_not_established",
        )

    def resolve_current(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
    ) -> ClaimLedgerHeadResolutionNonReceipt:
        del owner_key
        return ClaimLedgerHeadResolutionNonReceipt(
            status="not_established",
            code="claim_head_absent",
        )

    def advance_verified_batch(
        self,
        *,
        verified_batch: _VerifiedCompletedEpochValidityBatch,
        decision_packet_ref: ArtifactRef,
    ) -> ClaimLifecycleBridgeNonReceipt:
        try:
            packet_row = _resolve_decision_packet_claim_ledger(
                store=self.store,
                packet_ref=decision_packet_ref,
            )
            denominator = verified_batch.dependency_denominator
            affected_claim_ids = (
                denominator.ordered_affected_claim_ids
                if verified_batch.mapping_status == "resolved" and denominator is not None
                else ()
            )
            pending = _persist_claim_bridge_pending(
                store=self.store,
                statement=ClaimBridgePendingStatement(
                    batch_receipt_ref=verified_batch.evidence.batch_receipt_ref,
                    batch_receipt_content_hash=(verified_batch.evidence.batch_receipt_content_hash),
                    decision_packet_ref=decision_packet_ref,
                    decision_packet_content_hash=packet_row.decision_packet_content_hash,
                    requested_query_context_ref=(
                        verified_batch.evidence.receipt.requested_query_context_ref
                    ),
                    target_mapping_ref=verified_batch.target_mapping_ref,
                    target_mapping_content_hash=(verified_batch.target_mapping_content_hash),
                    ordered_affected_claim_ids=affected_claim_ids,
                    expected_head_ref=None,
                    mapping_status=verified_batch.mapping_status,
                    limitation_code=(
                        "claim_target_denominator_unresolved"
                        if verified_batch.mapping_status == "unresolved"
                        else None
                    ),
                ),
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ClaimLifecycleBridgeNonReceipt(
                code="claim_batch_evidence_rejected",
                decisive_evidence_refs=(verified_batch.evidence.batch_receipt_ref,),
            )
        return ClaimLifecycleBridgeNonReceipt(
            code=(
                "claim_target_denominator_unresolved"
                if verified_batch.mapping_status == "unresolved"
                else "claim_ledger_owner_not_established"
            ),
            pending=pending,
            decisive_evidence_refs=(
                verified_batch.evidence.batch_receipt_ref,
                decision_packet_ref,
                verified_batch.target_mapping_ref,
            ),
        )

    def append_verified_owner_event(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
        owner_event_ref: ArtifactRef,
    ) -> ClaimLedgerHeadResolutionNonReceipt:
        del owner_key, owner_event_ref
        return ClaimLedgerHeadResolutionNonReceipt(
            status="not_established",
            code="claim_head_absent",
        )

    def export_current(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
        audience: ClaimExportAudience,
    ) -> ClaimLedgerHeadResolutionNonReceipt:
        del owner_key, audience
        return ClaimLedgerHeadResolutionNonReceipt(
            status="not_established",
            code="claim_head_absent",
        )

    def migrate_legacy_roots(
        self,
    ) -> tuple[ClaimLedgerHeadResolutionNonReceipt, ...]:
        return (
            ClaimLedgerHeadResolutionNonReceipt(
                status="not_established",
                code="claim_head_absent",
            ),
        )


@dataclass(frozen=True, slots=True)
class _RepositoryClaimLedgerOwner:
    """Real owner mechanism, constructible only with explicit authority dependencies."""

    store: ArtifactStore
    policy_resolver: ClaimLedgerInitializationPolicyResolver
    root_issuer: ClaimLedgerRootIssuer | None = None
    issuance_verifier: ClaimLedgerIssuanceVerifier | None = None
    head_index_root: Path | None = None
    decision_packets: DecisionPacketRootRepository | None = None
    independent_walk: ArtifactStoreClaimRootWalk | None = None
    completed_batches: EpochValidityCompletedBatchEvidenceDenominator | None = None
    issuance_evidence: ClaimLedgerIssuanceEvidenceIndex = field(
        default_factory=NoClaimLedgerIssuanceEvidenceIndex
    )

    def _head_cas(self) -> _LockedClaimLedgerHeadCAS:
        """Build the sole pointer mutator with the owner's closure verifier."""

        if self.head_index_root is None:
            raise RuntimeError("claim_head_index_root_not_established")
        return _LockedClaimLedgerHeadCAS(
            store=self.store,
            root=self.head_index_root,
            closure_verifier=self._verify_closed_head,
        )

    def _verify_closed_head(
        self,
        head: PersistedClaimLedgerHead,
    ) -> ClaimLedgerHeadResolutionNonReceipt | None:
        """Verify the complete immutable-root and current-ledger closure."""

        if self.issuance_verifier is None:
            return ClaimLedgerHeadResolutionNonReceipt(
                status="rejected",
                code="claim_head_issuance_unverified",
            )
        try:
            root = _read_profiled_statement(
                store=self.store,
                record="claim_ledger_root",
                ref=head.statement.root_receipt_ref,
                model=ClaimLedgerRootStatement,
            )
            if not isinstance(root, ClaimLedgerRootStatement):
                raise ValueError("claim_head_root_type_mismatch")
            basis = _read_profiled_statement(
                store=self.store,
                record="claim_ledger_root_basis",
                ref=root.basis_ref,
                model=ClaimLedgerRootBasisStatement,
            )
            if not isinstance(basis, ClaimLedgerRootBasisStatement):
                raise ValueError("claim_head_basis_type_mismatch")
            preparation = _read_profiled_statement(
                store=self.store,
                record="claim_ledger_preparation",
                ref=basis.preparation_ref,
                model=ClaimLedgerPreparationStatement,
            )
            denominator = _read_profiled_statement(
                store=self.store,
                record="claim_ledger_root_denominator",
                ref=basis.denominator_receipt_ref,
                model=ClaimLedgerRootDenominatorReceipt,
            )
            if (
                not isinstance(preparation, ClaimLedgerPreparationStatement)
                or not isinstance(denominator, ClaimLedgerRootDenominatorReceipt)
                or head.statement.root_identity != root.root_identity
                or head.statement.root_receipt_content_hash
                != c4_semantic_digest("claim_ledger_root", root)
                or root.basis_content_hash != c4_semantic_digest("claim_ledger_root_basis", basis)
                or basis.owner_key != head.statement.owner_key
                or basis.preparation_content_hash
                != c4_semantic_digest("claim_ledger_preparation", preparation)
                or basis.denominator_receipt_content_hash
                != c4_semantic_digest("claim_ledger_root_denominator", denominator)
                or preparation.owner_key != head.statement.owner_key
                or preparation.initial_ledger_ref != basis.initial_ledger_ref
                or preparation.initial_ledger_content_hash != basis.initial_ledger_content_hash
            ):
                raise ValueError("claim_head_root_closure_mismatch")

            packet_raw = _read_exact_artifact(
                store=self.store,
                ref=basis.decision_packet_ref,
                expected_kind="scientist.decision_packet",
                expected_media_type="application/json",
            )
            packet_row = _packet_root_row(
                store=self.store,
                packet_ref=basis.decision_packet_ref,
            )
            if (
                packet_row is None
                or _raw_content_hash(packet_raw) != basis.decision_packet_content_hash
                or packet_row.ledger_artifact_ref != basis.initial_ledger_ref
                or packet_row.ledger_raw_cas_hash != basis.initial_ledger_content_hash
            ):
                raise ValueError("claim_head_packet_or_ledger_content_mismatch")

            from polisyos.scientist.evidence.claims.audit import (
                CLAIM_LEDGER_V2_KIND,
                CLAIM_LEDGER_V2_SCHEMA_NAME,
                CLAIM_LEDGER_V2_SCHEMA_VERSION,
                _load_append_only_claim_ledger,
            )

            current_ledger = _load_append_only_claim_ledger(
                self.store,
                head.statement.ledger_artifact_ref,
            )
            current_ledger_raw = _read_exact_artifact(
                store=self.store,
                ref=head.statement.ledger_artifact_ref,
                expected_kind=CLAIM_LEDGER_V2_KIND,
                expected_media_type="application/json",
                expected_schema=artifacts.SchemaInfo(
                    name=CLAIM_LEDGER_V2_SCHEMA_NAME,
                    version=CLAIM_LEDGER_V2_SCHEMA_VERSION,
                ),
            )
            if _raw_content_hash(current_ledger_raw) != head.statement.ledger_raw_cas_hash:
                raise ValueError("claim_head_ledger_content_mismatch")
            prior_ledger_ref = basis.initial_ledger_ref
            prior_ledger_hash = basis.initial_ledger_content_hash
            last_ledger = _load_append_only_claim_ledger(
                self.store,
                basis.initial_ledger_ref,
            )
            if head.statement.generation != len(head.statement.bridge_result_refs):
                raise ValueError("claim_head_generation_bridge_count_mismatch")
            for bridge_result_ref in head.statement.bridge_result_refs:
                bridge_result = _read_profiled_statement(
                    store=self.store,
                    record="claim_bridge_result",
                    ref=bridge_result_ref,
                    model=ClaimLifecycleBridgeResultStatement,
                )
                if not isinstance(bridge_result, ClaimLifecycleBridgeResultStatement):
                    raise ValueError("claim_head_bridge_result_type_mismatch")
                pending = _read_profiled_statement(
                    store=self.store,
                    record="claim_bridge_pending",
                    ref=bridge_result.pending_ref,
                    model=ClaimBridgePendingStatement,
                )
                dependency = _read_profiled_statement(
                    store=self.store,
                    record="claim_dependency_denominator",
                    ref=bridge_result.dependency_denominator_ref,
                    model=ClaimDependencyDenominatorReceipt,
                )
                next_ledger = _load_append_only_claim_ledger(
                    self.store,
                    bridge_result.next_ledger_ref,
                )
                next_ledger_raw = _read_exact_artifact(
                    store=self.store,
                    ref=bridge_result.next_ledger_ref,
                    expected_kind=CLAIM_LEDGER_V2_KIND,
                    expected_media_type="application/json",
                    expected_schema=artifacts.SchemaInfo(
                        name=CLAIM_LEDGER_V2_SCHEMA_NAME,
                        version=CLAIM_LEDGER_V2_SCHEMA_VERSION,
                    ),
                )
                from polisyos.scientist.governance.continuous.lifecycle_bridge import (
                    LIFECYCLE_BRIDGE_RESULT_KIND,
                    LIFECYCLE_BRIDGE_RESULT_SCHEMA_NAME,
                    LIFECYCLE_BRIDGE_RESULT_SCHEMA_VERSION,
                    LifecycleBridgeResult,
                )

                lifecycle_raw = _read_exact_artifact(
                    store=self.store,
                    ref=bridge_result.lifecycle_result_ref,
                    expected_kind=LIFECYCLE_BRIDGE_RESULT_KIND,
                    expected_media_type="application/json",
                    expected_schema=artifacts.SchemaInfo(
                        name=LIFECYCLE_BRIDGE_RESULT_SCHEMA_NAME,
                        version=LIFECYCLE_BRIDGE_RESULT_SCHEMA_VERSION,
                    ),
                )
                lifecycle_result = LifecycleBridgeResult.model_validate(
                    from_canonical_bytes(lifecycle_raw)
                )
                if (
                    not isinstance(pending, ClaimBridgePendingStatement)
                    or not isinstance(dependency, ClaimDependencyDenominatorReceipt)
                    or bridge_result.owner_key != head.statement.owner_key
                    or bridge_result.pending_content_hash
                    != c4_semantic_digest("claim_bridge_pending", pending)
                    or pending.target_mapping_ref != bridge_result.dependency_denominator_ref
                    or pending.target_mapping_content_hash
                    != bridge_result.dependency_denominator_content_hash
                    or bridge_result.dependency_denominator_content_hash
                    != c4_semantic_digest("claim_dependency_denominator", dependency)
                    or dependency.ledger_artifact_ref != bridge_result.prior_ledger_ref
                    or dependency.ledger_raw_cas_hash != bridge_result.prior_ledger_content_hash
                    or dependency.ordered_affected_claim_ids
                    != bridge_result.ordered_affected_claim_ids
                    or bridge_result.batch_receipt_ref != pending.batch_receipt_ref
                    or bridge_result.batch_receipt_content_hash
                    != pending.batch_receipt_content_hash
                    or bridge_result.decision_packet_ref != pending.decision_packet_ref
                    or bridge_result.decision_packet_ref != basis.decision_packet_ref
                    or bridge_result.decision_packet_content_hash
                    != pending.decision_packet_content_hash
                    or bridge_result.decision_packet_content_hash
                    != basis.decision_packet_content_hash
                    or bridge_result.requested_query_context_ref
                    != pending.requested_query_context_ref
                    or bridge_result.ordered_affected_claim_ids
                    != pending.ordered_affected_claim_ids
                    or bridge_result.prior_ledger_ref != prior_ledger_ref
                    or bridge_result.prior_ledger_content_hash != prior_ledger_hash
                    or _raw_content_hash(lifecycle_raw)
                    != bridge_result.lifecycle_result_content_hash
                    or _raw_content_hash(next_ledger_raw) != bridge_result.next_ledger_content_hash
                    or lifecycle_result.decision_packet_ref != bridge_result.decision_packet_ref
                    or lifecycle_result.original_claim_ledger_ref != bridge_result.prior_ledger_ref
                    or lifecycle_result.updated_ledger != next_ledger
                ):
                    raise ValueError("claim_head_bridge_closure_mismatch")
                prior_ledger_ref = bridge_result.next_ledger_ref
                prior_ledger_hash = bridge_result.next_ledger_content_hash
                last_ledger = next_ledger
            if (
                prior_ledger_ref != head.statement.ledger_artifact_ref
                or prior_ledger_hash != head.statement.ledger_raw_cas_hash
                or last_ledger != current_ledger
            ):
                raise ValueError("claim_head_ledger_chain_mismatch")
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ClaimLedgerHeadResolutionNonReceipt(
                status="rejected",
                code="claim_head_content_mismatch",
            )

        verified = self.issuance_verifier.verify_exact(
            root_receipt_ref=head.statement.root_receipt_ref,
            expected_owner_key=head.statement.owner_key,
        )
        if isinstance(verified, ClaimLedgerIssuanceNonReceipt):
            return ClaimLedgerHeadResolutionNonReceipt(
                status="rejected",
                code="claim_head_issuance_unverified",
            )
        if (
            verified.root.root_receipt_ref != head.statement.root_receipt_ref
            or verified.root.root_receipt_content_hash != head.statement.root_receipt_content_hash
            or verified.root.statement != root
            or verified.verifier_receipt_ref != head.statement.issuance_verifier_receipt_ref
            or verified.verifier_receipt_content_hash
            != head.statement.issuance_verifier_receipt_content_hash
            or verified.predicate_class != "independently_reconciled"
        ):
            return ClaimLedgerHeadResolutionNonReceipt(
                status="rejected",
                code="claim_head_issuance_unverified",
            )
        return None

    def _resolve_owner_key_for_packet(
        self,
        *,
        decision_packet_ref: ArtifactRef,
    ) -> ClaimLedgerOwnerKey | ClaimLedgerHeadResolutionNonReceipt:
        """Resolve exactly one profiled root basis for the durable packet."""

        matches: list[ClaimLedgerOwnerKey] = []
        profile = c4_profile("claim_ledger_root_basis")
        try:
            for artifact_id in sorted(
                self.store.iter_artifact_ids(),
                key=str,
            ):
                manifest = self.store.get_manifest(artifact_id)
                if manifest.kind != profile.kind or manifest.media_type != profile.media_type:
                    continue
                basis = _read_profiled_statement(
                    store=self.store,
                    record="claim_ledger_root_basis",
                    ref=ArtifactRef(
                        artifact_id=artifact_id,
                        kind=manifest.kind,
                        media_type=manifest.media_type,
                    ),
                    model=ClaimLedgerRootBasisStatement,
                )
                if (
                    isinstance(basis, ClaimLedgerRootBasisStatement)
                    and basis.decision_packet_ref == decision_packet_ref
                ):
                    matches.append(basis.owner_key)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ClaimLedgerHeadResolutionNonReceipt(
                status="rejected",
                code="claim_head_content_mismatch",
            )
        if len(matches) != 1:
            return ClaimLedgerHeadResolutionNonReceipt(
                status="not_established",
                code="claim_head_absent",
            )
        return matches[0]

    def persist_candidate_ledger(
        self,
        *,
        ledger: ClaimLedger,
        inputs: tuple[artifacts.InputRef, ...] = (),
    ) -> ArtifactRef:
        """Persist candidate Claim bytes without establishing currentness."""

        from polisyos.scientist.evidence.claims.ledger import _persist_claim_ledger

        return _persist_claim_ledger(
            self.store,
            ledger,
            inputs=list(inputs) if inputs else None,
        )

    def project_candidate_ledger(
        self,
        *,
        ledger: ClaimLedger,
    ) -> ClaimLedgerCandidateProjection:
        """Project candidate data without confusing it with a current head."""

        from polisyos.scientist.evidence.claims.export import (
            _blocked_claim_summary,
            _claim_ledger_summary,
        )

        return ClaimLedgerCandidateProjection(
            ledger_summary=_claim_ledger_summary(ledger),
            blocked_summary=_blocked_claim_summary(ledger),
        )

    def prepare_initial_ledger(
        self,
        *,
        base_claims_ref: ArtifactRef,
        source_artifact_refs: tuple[ArtifactRef, ...],
    ) -> PreparedClaimLedgerInitialization | ClaimLedgerIssuanceNonReceipt:
        """Persist an unadvertised v2 ledger only after exact policy verification."""

        from polisyos.scientist.evidence.claims.audit import (
            _claim_ledger_v2_inputs,
            _persist_append_only_claim_ledger,
        )
        from polisyos.scientist.evidence.claims.ledger import _load_claim_ledger
        from polisyos.scientist.evidence.claims.lifecycle import build_initial_append_only_ledger

        try:
            base_raw = self.store.get_bytes(base_claims_ref.artifact_id)
            base_report = self.store.verify(base_claims_ref.artifact_id)
            base_manifest = self.store.get_manifest(base_claims_ref.artifact_id)
            base_claims = _load_claim_ledger(self.store, base_claims_ref)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ClaimLedgerIssuanceNonReceipt(
                status="rejected",
                code="claim_root_issuance_content_mismatch",
            )
        base_content_hash = _raw_content_hash(base_raw)
        from polisyos.scientist.evidence.claims.ledger import (
            CLAIM_LEDGER_KIND,
            CLAIM_LEDGER_SCHEMA_NAME,
            CLAIM_LEDGER_SCHEMA_VERSION,
        )

        if (
            not base_report.ok
            or base_content_hash != str(base_claims_ref.artifact_id)
            or base_claims_ref.kind != CLAIM_LEDGER_KIND
            or base_claims_ref.kind != base_manifest.kind
            or base_claims_ref.media_type != "application/json"
            or base_claims_ref.media_type != base_manifest.media_type
            or base_manifest.artifact_schema
            != artifacts.SchemaInfo(
                name=CLAIM_LEDGER_SCHEMA_NAME,
                version=CLAIM_LEDGER_SCHEMA_VERSION,
            )
        ):
            return ClaimLedgerIssuanceNonReceipt(
                status="rejected",
                code="claim_root_issuance_content_mismatch",
            )
        derivation = ClaimLedgerOwnerKeyDerivationInput(
            base_claims_ref=base_claims_ref,
            base_claims_content_hash=base_content_hash,
            requested_authority_purpose=CLAIM_LEDGER_AUTHORITY_PURPOSE,
        )
        policy = self.policy_resolver.resolve_for(derivation_input=derivation)
        if isinstance(policy, ClaimLedgerIssuanceNonReceipt):
            return policy
        if not self._policy_is_exact(policy=policy, derivation=derivation):
            return ClaimLedgerIssuanceNonReceipt(
                status="rejected",
                code="claim_root_provenance_untrusted",
            )
        owner_key = ClaimLedgerOwnerKey(
            scope_ref=derive_claim_ledger_owner_scope_ref(derivation),
            claim_owner_ref=policy.claim_owner_ref,
            authority_purpose=policy.authority_purpose,
            derivation_input=derivation,
        )
        source_hashes: list[Digest] = []
        try:
            for source_ref in source_artifact_refs:
                raw = self.store.get_bytes(source_ref.artifact_id)
                report = self.store.verify(source_ref.artifact_id)
                manifest = self.store.get_manifest(source_ref.artifact_id)
                if (
                    not report.ok
                    or _raw_content_hash(raw) != str(source_ref.artifact_id)
                    or source_ref.kind != manifest.kind
                    or source_ref.media_type != manifest.media_type
                ):
                    raise ValueError("source_content_mismatch")
                source_hashes.append(_raw_content_hash(raw))
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ClaimLedgerIssuanceNonReceipt(
                status="rejected",
                code="claim_root_issuance_content_mismatch",
            )

        append_only = build_initial_append_only_ledger(
            base_claims,
            actor_id="scientist.claims.owner",
            reason="Prepared candidate Claim Ledger under an independently verified policy.",
            base_ledger_ref=base_claims_ref,
            retention_policy={"max_events": 500},
        )
        initial_ledger_ref = _persist_append_only_claim_ledger(
            self.store,
            append_only,
            inputs=_claim_ledger_v2_inputs(
                base_ledger_ref=base_claims_ref,
                source_artifact_refs=source_artifact_refs,
            ),
        )
        initial_ledger_raw_hash: Digest = str(initial_ledger_ref.artifact_id)
        statement = ClaimLedgerPreparationStatement(
            owner_key=owner_key,
            base_claims_ref=base_claims_ref,
            base_claims_content_hash=base_content_hash,
            source_artifact_refs=source_artifact_refs,
            source_artifact_content_hashes=tuple(source_hashes),
            initialization_policy_ref=policy.policy_ref,
            initialization_policy_content_hash=policy.policy_content_hash,
            initialization_policy_verifier_provenance_ref=policy.verifier_provenance_ref,
            initial_ledger_ref=initial_ledger_ref,
            initial_ledger_content_hash=initial_ledger_raw_hash,
        )
        preparation_ref, preparation_hash = _persist_profiled_statement(
            store=self.store,
            record="claim_ledger_preparation",
            value=statement,
        )
        return PreparedClaimLedgerInitialization(
            preparation_ref=preparation_ref,
            preparation_content_hash=preparation_hash,
            owner_key=owner_key,
            initial_ledger_ref=initial_ledger_ref,
            initial_ledger_content_hash=initial_ledger_raw_hash,
        )

    def _policy_is_exact(
        self,
        *,
        policy: _VerifiedClaimLedgerInitializationPolicy,
        derivation: ClaimLedgerOwnerKeyDerivationInput,
    ) -> bool:
        if (
            policy.authority_purpose != derivation.requested_authority_purpose
            or policy.predicate_class != "independently_reconciled"
        ):
            return False
        try:
            policy_raw = _read_exact_artifact(
                store=self.store,
                ref=policy.policy_ref,
            )
            provenance_raw = _read_exact_artifact(
                store=self.store,
                ref=policy.verifier_provenance_ref,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return False
        return (
            _raw_content_hash(policy_raw) == policy.policy_content_hash
            and policy.policy_content_hash == str(policy.policy_ref.artifact_id)
            and _raw_content_hash(provenance_raw) == str(policy.verifier_provenance_ref.artifact_id)
        )

    def finalize_initial_root(
        self,
        *,
        preparation_ref: ArtifactRef,
        decision_packet_ref: ArtifactRef,
    ) -> ClaimLedgerHeadAdvanceReceipt | ClaimLedgerIssuanceNonReceipt:
        if (
            self.root_issuer is None
            or self.issuance_verifier is None
            or self.head_index_root is None
            or self.decision_packets is None
            or self.independent_walk is None
        ):
            return ClaimLedgerIssuanceNonReceipt(
                status="not_established",
                code="claim_root_issuance_not_established",
            )
        try:
            preparation = _read_profiled_statement(
                store=self.store,
                record="claim_ledger_preparation",
                ref=preparation_ref,
                model=ClaimLedgerPreparationStatement,
            )
            if not isinstance(preparation, ClaimLedgerPreparationStatement):
                raise ValueError("claim_preparation_type_mismatch")
            derivation = preparation.owner_key.derivation_input
            if derivation is None:
                raise ValueError("claim_preparation_owner_derivation_missing")
            preparation_hash = c4_semantic_digest("claim_ledger_preparation", preparation)
            packet_row = _packet_root_row(store=self.store, packet_ref=decision_packet_ref)
            if (
                packet_row is None
                or packet_row.ledger_artifact_ref != preparation.initial_ledger_ref
            ):
                raise ValueError("claim_root_packet_ledger_binding_mismatch")
            if packet_row.ledger_raw_cas_hash != preparation.initial_ledger_content_hash:
                raise ValueError("claim_root_packet_ledger_hash_mismatch")
            policy = self.policy_resolver.resolve_for(derivation_input=derivation)
            if not isinstance(policy, _VerifiedClaimLedgerInitializationPolicy):
                return policy
            if (
                not self._policy_is_exact(
                    policy=policy,
                    derivation=derivation,
                )
                or policy.policy_ref != preparation.initialization_policy_ref
                or policy.policy_content_hash != preparation.initialization_policy_content_hash
                or policy.verifier_provenance_ref
                != preparation.initialization_policy_verifier_provenance_ref
                or policy.claim_owner_ref != preparation.owner_key.claim_owner_ref
            ):
                raise ValueError("claim_root_policy_binding_mismatch")
            inventory = RepositoryClaimLedgerRootInventory(
                store=self.store,
                decision_packets=self.decision_packets,
                independent_walk=self.independent_walk,
                issuance_evidence=self.issuance_evidence,
            )
            denominator, denominator_ref, denominator_content_hash = (
                inventory.resolve_complete_roots()
            )
            exact_rows = tuple(
                assessment
                for assessment in denominator.assessments
                if assessment.decision_packet_ref == decision_packet_ref
                and assessment.ledger_artifact_ref == preparation.initial_ledger_ref
            )
            if len(exact_rows) != 1:
                raise _ClaimRootDenominatorMismatch("claim_root_denominator_target_missing")
            packet_raw = self.store.get_bytes(decision_packet_ref.artifact_id)
            basis = ClaimLedgerRootBasisStatement(
                owner_key=preparation.owner_key,
                preparation_ref=preparation_ref,
                preparation_content_hash=preparation_hash,
                decision_packet_ref=decision_packet_ref,
                decision_packet_content_hash=_raw_content_hash(packet_raw),
                initial_ledger_ref=preparation.initial_ledger_ref,
                initial_ledger_content_hash=preparation.initial_ledger_content_hash,
                denominator_receipt_ref=denominator_ref,
                denominator_receipt_content_hash=denominator_content_hash,
            )
            basis_ref, basis_content_hash = _persist_profiled_statement(
                store=self.store,
                record="claim_ledger_root_basis",
                value=basis,
            )
            issuance = self.root_issuer.issue_exact(
                basis_ref=basis_ref,
                basis_content_hash=basis_content_hash,
                policy=policy,
            )
            if isinstance(issuance, ClaimLedgerIssuanceNonReceipt):
                return issuance
            if not self._issuance_evidence_is_exact(
                issuance=issuance,
                basis_ref=basis_ref,
                basis_content_hash=basis_content_hash,
                policy=policy,
            ):
                raise ValueError("claim_root_issuance_evidence_mismatch")
            root = ClaimLedgerRootStatement(
                root_identity=basis_content_hash,
                basis_ref=basis_ref,
                basis_content_hash=basis_content_hash,
                issuance_evidence_ref=issuance.evidence_ref,
                issuance_evidence_content_hash=issuance.evidence_content_hash,
                issuance_verifier_provenance_ref=issuance.verifier_provenance_ref,
            )
            root_ref, root_content_hash = _persist_profiled_statement(
                store=self.store,
                record="claim_ledger_root",
                value=root,
            )
            verified = self.issuance_verifier.verify_exact(
                root_receipt_ref=root_ref,
                expected_owner_key=preparation.owner_key,
            )
            if isinstance(verified, ClaimLedgerIssuanceNonReceipt):
                return verified
            if (
                verified.root.root_receipt_ref != root_ref
                or verified.root.root_receipt_content_hash != root_content_hash
                or verified.root.statement != root
                or verified.predicate_class != "independently_reconciled"
            ):
                raise ValueError("claim_root_verifier_result_mismatch")
            head_statement = ClaimLedgerHeadStatement(
                root_identity=root.root_identity,
                root_receipt_ref=root_ref,
                root_receipt_content_hash=root_content_hash,
                owner_key=preparation.owner_key,
                ledger_artifact_ref=preparation.initial_ledger_ref,
                ledger_raw_cas_hash=preparation.initial_ledger_content_hash,
                generation=0,
                predecessor_head_ref=None,
                bridge_result_refs=(),
                issuance_verifier_receipt_ref=verified.verifier_receipt_ref,
                issuance_verifier_receipt_content_hash=verified.verifier_receipt_content_hash,
            )
            head_ref, head_content_hash = _persist_profiled_statement(
                store=self.store,
                record="claim_ledger_head",
                value=head_statement,
            )
            return self._head_cas().advance(
                owner_key=preparation.owner_key,
                expected_prior_head_ref=None,
                new_head=PersistedClaimLedgerHead(
                    head_ref=head_ref,
                    head_content_hash=head_content_hash,
                    statement=head_statement,
                ),
                permit=_CLAIM_LEDGER_MUTATION_PERMIT,
            )
        except _ClaimRootDenominatorMismatch:
            return ClaimLedgerIssuanceNonReceipt(
                status="rejected",
                code="claim_root_denominator_mismatch",
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ClaimLedgerIssuanceNonReceipt(
                status="rejected",
                code="claim_root_issuance_content_mismatch",
            )

    def _issuance_evidence_is_exact(
        self,
        *,
        issuance: ClaimLedgerRootIssuanceEvidence,
        basis_ref: ArtifactRef,
        basis_content_hash: Digest,
        policy: _VerifiedClaimLedgerInitializationPolicy,
    ) -> bool:
        if (
            issuance.basis_ref != basis_ref
            or issuance.basis_content_hash != basis_content_hash
            or issuance.initialization_policy_ref != policy.policy_ref
            or issuance.initialization_policy_content_hash != policy.policy_content_hash
            or issuance.verifier_provenance_ref != policy.verifier_provenance_ref
        ):
            return False
        try:
            raw = self.store.get_bytes(issuance.evidence_ref.artifact_id)
            report = self.store.verify(issuance.evidence_ref.artifact_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return False
        return (
            report.ok
            and _raw_content_hash(raw) == issuance.evidence_content_hash
            and issuance.evidence_content_hash == str(issuance.evidence_ref.artifact_id)
        )

    def resolve_current(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
    ) -> PersistedClaimLedgerHead | ClaimLedgerHeadResolutionNonReceipt:
        if self.head_index_root is None or self.issuance_verifier is None:
            return ClaimLedgerHeadResolutionNonReceipt(
                status="not_established",
                code="claim_head_absent",
            )
        current = self._head_cas().resolve(owner_key=owner_key)
        if isinstance(current, ClaimLedgerHeadResolutionNonReceipt):
            return current
        return current

    def advance_verified_batch(
        self,
        *,
        verified_batch: _VerifiedCompletedEpochValidityBatch,
        decision_packet_ref: ArtifactRef,
    ) -> ClaimLifecycleBridgeAuthorityResult:
        owner_key = self._resolve_owner_key_for_packet(
            decision_packet_ref=decision_packet_ref,
        )
        if isinstance(owner_key, ClaimLedgerHeadResolutionNonReceipt):
            return ClaimLifecycleBridgeNonReceipt(
                code="claim_head_absent",
                decisive_evidence_refs=(
                    verified_batch.evidence.batch_receipt_ref,
                    decision_packet_ref,
                ),
            )
        try:
            packet_row = _resolve_decision_packet_claim_ledger(
                store=self.store,
                packet_ref=decision_packet_ref,
            )
            receipt = verified_batch.evidence.receipt
            packet_id = str(decision_packet_ref.artifact_id)
            expected_targets = tuple(
                target for target in receipt.targets if target.packet_ref == packet_id
            )
            if (
                packet_id not in receipt.affected_packet_refs
                or not expected_targets
                or verified_batch.targets != expected_targets
            ):
                raise ValueError("claim_batch_packet_target_binding_mismatch")

            def persist_pending(
                current: PersistedClaimLedgerHead,
            ) -> PersistedClaimBridgePending:
                existing = self._find_applied_batch(
                    current=current,
                    verified_batch=verified_batch,
                    decision_packet_ref=decision_packet_ref,
                )
                if existing is not None:
                    raise _ClaimBatchAlreadyApplied(existing)
                denominator = verified_batch.dependency_denominator
                affected_claim_ids = (
                    denominator.ordered_affected_claim_ids
                    if verified_batch.mapping_status == "resolved" and denominator is not None
                    else ()
                )
                return _persist_claim_bridge_pending(
                    store=self.store,
                    statement=ClaimBridgePendingStatement(
                        batch_receipt_ref=(verified_batch.evidence.batch_receipt_ref),
                        batch_receipt_content_hash=(
                            verified_batch.evidence.batch_receipt_content_hash
                        ),
                        decision_packet_ref=decision_packet_ref,
                        decision_packet_content_hash=(packet_row.decision_packet_content_hash),
                        requested_query_context_ref=(
                            verified_batch.evidence.receipt.requested_query_context_ref
                        ),
                        target_mapping_ref=verified_batch.target_mapping_ref,
                        target_mapping_content_hash=(verified_batch.target_mapping_content_hash),
                        ordered_affected_claim_ids=affected_claim_ids,
                        expected_head_ref=current.head_ref,
                        mapping_status=verified_batch.mapping_status,
                        limitation_code=(
                            "claim_target_denominator_unresolved"
                            if verified_batch.mapping_status == "unresolved"
                            else None
                        ),
                    ),
                )

            try:
                frozen = self._head_cas().freeze_pending(
                    owner_key=owner_key,
                    permit=_CLAIM_LEDGER_MUTATION_PERMIT,
                    persist_pending=persist_pending,
                )
            except _ClaimBatchAlreadyApplied as already:
                readback = self._head_cas().readback_existing_current(
                    owner_key=owner_key,
                    expected_bridge_result_ref=already.result.bridge_result_ref,
                )
                if isinstance(readback, ClaimLedgerHeadAdvanced):
                    return ClaimLifecycleBridgeAdvanced(
                        bridge_result=already.result,
                        head_advance=readback,
                    )
                return ClaimLifecycleBridgeNonReceipt(
                    code="claim_head_conflict",
                    decisive_evidence_refs=(
                        verified_batch.evidence.batch_receipt_ref,
                        decision_packet_ref,
                        already.result.bridge_result_ref,
                    ),
                )
            if isinstance(frozen, ClaimLedgerHeadResolutionNonReceipt):
                return ClaimLifecycleBridgeNonReceipt(
                    code=(
                        "claim_head_absent"
                        if frozen.code == "claim_head_absent"
                        else "claim_batch_evidence_rejected"
                    ),
                    decisive_evidence_refs=(
                        verified_batch.evidence.batch_receipt_ref,
                        decision_packet_ref,
                    ),
                )
            current, pending = frozen
            if verified_batch.mapping_status == "unresolved":
                return ClaimLifecycleBridgeNonReceipt(
                    code="claim_target_denominator_unresolved",
                    pending=pending,
                    decisive_evidence_refs=(
                        verified_batch.evidence.batch_receipt_ref,
                        decision_packet_ref,
                        verified_batch.target_mapping_ref,
                    ),
                )

            from polisyos.scientist.evidence.claims.audit import (
                _claim_ledger_v2_inputs,
                _load_append_only_claim_ledger,
                _persist_append_only_claim_ledger,
            )
            from polisyos.scientist.governance.continuous.lifecycle_bridge import (
                _apply_verified_epoch_batch_to_claim_lifecycle,
                persist_lifecycle_bridge_result,
            )

            prior_ledger = _load_append_only_claim_ledger(
                self.store,
                current.statement.ledger_artifact_ref,
            )
            lifecycle_result = _apply_verified_epoch_batch_to_claim_lifecycle(
                ledger=prior_ledger,
                verified_batch=verified_batch,
                decision_packet_ref=decision_packet_ref,
                original_claim_ledger_ref=current.statement.ledger_artifact_ref,
                actor_id="decision_validity_epoch_bridge",
            )
            next_ledger_ref = _persist_append_only_claim_ledger(
                self.store,
                lifecycle_result.updated_ledger,
                inputs=_claim_ledger_v2_inputs(
                    base_ledger_ref=current.statement.ledger_artifact_ref,
                    source_artifact_refs=(
                        verified_batch.evidence.batch_receipt_ref,
                        verified_batch.target_mapping_ref,
                    ),
                ),
            )
            lifecycle_result_ref = persist_lifecycle_bridge_result(
                self.store,
                lifecycle_result,
            )
            bridge_statement = ClaimLifecycleBridgeResultStatement(
                owner_key=owner_key,
                batch_receipt_ref=verified_batch.evidence.batch_receipt_ref,
                batch_receipt_content_hash=(verified_batch.evidence.batch_receipt_content_hash),
                decision_packet_ref=decision_packet_ref,
                decision_packet_content_hash=packet_row.decision_packet_content_hash,
                requested_query_context_ref=(
                    verified_batch.evidence.receipt.requested_query_context_ref
                ),
                pending_ref=pending.pending_ref,
                pending_content_hash=pending.pending_content_hash,
                dependency_denominator_ref=verified_batch.target_mapping_ref,
                dependency_denominator_content_hash=(verified_batch.target_mapping_content_hash),
                lifecycle_result_ref=lifecycle_result_ref,
                lifecycle_result_content_hash=str(lifecycle_result_ref.artifact_id),
                prior_ledger_ref=current.statement.ledger_artifact_ref,
                prior_ledger_content_hash=current.statement.ledger_raw_cas_hash,
                next_ledger_ref=next_ledger_ref,
                next_ledger_content_hash=str(next_ledger_ref.artifact_id),
                ordered_affected_claim_ids=pending.statement.ordered_affected_claim_ids,
            )
            bridge_result_ref, bridge_result_content_hash = _persist_profiled_statement(
                store=self.store,
                record="claim_bridge_result",
                value=bridge_statement,
            )
            bridge_result = PersistedClaimLifecycleBridgeResult(
                bridge_result_ref=bridge_result_ref,
                bridge_result_content_hash=bridge_result_content_hash,
                statement=bridge_statement,
            )
            next_head_statement = ClaimLedgerHeadStatement(
                root_identity=current.statement.root_identity,
                root_receipt_ref=current.statement.root_receipt_ref,
                root_receipt_content_hash=current.statement.root_receipt_content_hash,
                owner_key=owner_key,
                ledger_artifact_ref=next_ledger_ref,
                ledger_raw_cas_hash=str(next_ledger_ref.artifact_id),
                generation=current.statement.generation + 1,
                predecessor_head_ref=current.head_ref,
                bridge_result_refs=(
                    *current.statement.bridge_result_refs,
                    bridge_result_ref,
                ),
                issuance_verifier_receipt_ref=(current.statement.issuance_verifier_receipt_ref),
                issuance_verifier_receipt_content_hash=(
                    current.statement.issuance_verifier_receipt_content_hash
                ),
            )
            next_head_ref, next_head_content_hash = _persist_profiled_statement(
                store=self.store,
                record="claim_ledger_head",
                value=next_head_statement,
            )
            head_advance = self._head_cas().advance(
                owner_key=owner_key,
                expected_prior_head_ref=current.head_ref,
                new_head=PersistedClaimLedgerHead(
                    head_ref=next_head_ref,
                    head_content_hash=next_head_content_hash,
                    statement=next_head_statement,
                ),
                permit=_CLAIM_LEDGER_MUTATION_PERMIT,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ClaimLifecycleBridgeNonReceipt(
                code="claim_batch_evidence_rejected",
                pending=locals().get("pending"),
                decisive_evidence_refs=(
                    verified_batch.evidence.batch_receipt_ref,
                    decision_packet_ref,
                    verified_batch.target_mapping_ref,
                ),
            )
        if isinstance(head_advance, ClaimLedgerHeadAdvanced):
            return ClaimLifecycleBridgeAdvanced(
                bridge_result=bridge_result,
                head_advance=head_advance,
            )
        return ClaimLifecycleBridgeNonReceipt(
            code=(
                "claim_head_conflict"
                if isinstance(head_advance, ClaimLedgerHeadAdvanceConflict)
                else "claim_batch_evidence_rejected"
            ),
            pending=pending,
            decisive_evidence_refs=(
                verified_batch.evidence.batch_receipt_ref,
                decision_packet_ref,
                bridge_result_ref,
            ),
        )

    def _find_applied_batch(
        self,
        *,
        current: PersistedClaimLedgerHead,
        verified_batch: _VerifiedCompletedEpochValidityBatch,
        decision_packet_ref: ArtifactRef,
    ) -> PersistedClaimLifecycleBridgeResult | None:
        matches: list[PersistedClaimLifecycleBridgeResult] = []
        for bridge_ref in current.statement.bridge_result_refs:
            statement = _read_profiled_statement(
                store=self.store,
                record="claim_bridge_result",
                ref=bridge_ref,
                model=ClaimLifecycleBridgeResultStatement,
            )
            if not isinstance(statement, ClaimLifecycleBridgeResultStatement):
                raise ValueError("claim_bridge_result_type_mismatch")
            if (
                statement.batch_receipt_ref == verified_batch.evidence.batch_receipt_ref
                and statement.batch_receipt_content_hash
                == verified_batch.evidence.batch_receipt_content_hash
                and statement.decision_packet_ref == decision_packet_ref
                and statement.requested_query_context_ref
                == verified_batch.evidence.receipt.requested_query_context_ref
            ):
                matches.append(
                    PersistedClaimLifecycleBridgeResult(
                        bridge_result_ref=bridge_ref,
                        bridge_result_content_hash=c4_semantic_digest(
                            "claim_bridge_result",
                            statement,
                        ),
                        statement=statement,
                    )
                )
        if len(matches) > 1:
            raise ValueError("claim_batch_applied_more_than_once")
        return matches[0] if matches else None

    def append_verified_owner_event(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
        owner_event_ref: ArtifactRef,
    ) -> ClaimLedgerHeadAdvanceReceipt:
        del owner_key, owner_event_ref
        return ClaimLedgerHeadResolutionNonReceipt(
            status="not_established",
            code="claim_head_absent",
        )

    def export_current(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
        audience: ClaimExportAudience,
    ) -> ClaimLedgerExport | ClaimLedgerHeadResolutionNonReceipt:
        from polisyos.scientist.evidence.claims.audit import _load_append_only_claim_ledger
        from polisyos.scientist.evidence.claims.export import _format_resolved_claim_ledger

        def format_locked(current: PersistedClaimLedgerHead) -> ClaimLedgerExport:
            ledger = _load_append_only_claim_ledger(
                self.store,
                current.statement.ledger_artifact_ref,
            )
            pending_projection = _resolve_claim_pending_projection(
                store=self.store,
                current=current,
                completed_batches=self.completed_batches,
            )
            return _format_resolved_claim_ledger(
                ledger,
                audience=audience,
                pending_projection=pending_projection,
            )

        return self._head_cas().export_locked(
            owner_key=owner_key,
            formatter=format_locked,
        )

    def migrate_legacy_roots(
        self,
    ) -> tuple[ClaimLedgerHeadAdvanceReceipt | ClaimLedgerHeadResolutionNonReceipt, ...]:
        if (
            self.issuance_verifier is None
            or self.head_index_root is None
            or self.decision_packets is None
            or self.independent_walk is None
        ):
            return (
                ClaimLedgerHeadResolutionNonReceipt(
                    status="not_established",
                    code="claim_head_issuance_unverified",
                ),
            )
        try:
            inventory = RepositoryClaimLedgerRootInventory(
                store=self.store,
                decision_packets=self.decision_packets,
                independent_walk=self.independent_walk,
                issuance_evidence=self.issuance_evidence,
            )
            denominator, _, _ = inventory.resolve_complete_roots()
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return (
                ClaimLedgerHeadResolutionNonReceipt(
                    status="rejected",
                    code="claim_head_content_mismatch",
                ),
            )

        outcomes: list[ClaimLedgerHeadAdvanceReceipt] = []
        for assessment in denominator.assessments:
            if (
                assessment.disposition != "migration_required"
                or assessment.root_identity is None
                or assessment.root_receipt_ref is None
                or assessment.root_receipt_content_hash is None
                or assessment.root_issuance_evidence_ref is None
                or assessment.owner_key is None
            ):
                outcomes.append(
                    ClaimLedgerHeadResolutionNonReceipt(
                        status="not_established",
                        code="claim_head_issuance_unverified",
                    )
                )
                continue
            verified = self.issuance_verifier.verify_exact(
                root_receipt_ref=assessment.root_receipt_ref,
                expected_owner_key=assessment.owner_key,
            )
            if (
                isinstance(verified, ClaimLedgerIssuanceNonReceipt)
                or verified.root.root_receipt_ref != assessment.root_receipt_ref
                or verified.root.root_receipt_content_hash != assessment.root_receipt_content_hash
                or verified.root.statement.root_identity != assessment.root_identity
                or verified.root.statement.issuance_evidence_ref
                != assessment.root_issuance_evidence_ref
                or verified.predicate_class != "independently_reconciled"
            ):
                outcomes.append(
                    ClaimLedgerHeadResolutionNonReceipt(
                        status="rejected",
                        code="claim_head_issuance_unverified",
                    )
                )
                continue
            statement = ClaimLedgerHeadStatement(
                root_identity=assessment.root_identity,
                root_receipt_ref=assessment.root_receipt_ref,
                root_receipt_content_hash=assessment.root_receipt_content_hash,
                owner_key=assessment.owner_key,
                ledger_artifact_ref=assessment.ledger_artifact_ref,
                ledger_raw_cas_hash=assessment.ledger_raw_cas_hash,
                generation=0,
                predecessor_head_ref=None,
                bridge_result_refs=(),
                issuance_verifier_receipt_ref=verified.verifier_receipt_ref,
                issuance_verifier_receipt_content_hash=(verified.verifier_receipt_content_hash),
            )
            head_ref, head_hash = _persist_profiled_statement(
                store=self.store,
                record="claim_ledger_head",
                value=statement,
            )
            outcomes.append(
                self._head_cas().advance(
                    owner_key=assessment.owner_key,
                    expected_prior_head_ref=None,
                    new_head=PersistedClaimLedgerHead(
                        head_ref=head_ref,
                        head_content_hash=head_hash,
                        statement=statement,
                    ),
                    permit=_CLAIM_LEDGER_MUTATION_PERMIT,
                )
            )
        return tuple(outcomes)


def build_default_claim_ledger_owner(*, store: ArtifactStore) -> ClaimLedgerOwnerPort:
    """Build the one production Claim owner composition: explicitly unappointed."""

    return UnappointedClaimLedgerOwner(store=store)


__all__ = [
    "CLAIM_LEDGER_AUTHORITY_PURPOSE",
    "ClaimBridgePendingStatement",
    "ClaimDependencyDenominatorReceipt",
    "ClaimDependencyDenominatorRow",
    "ClaimLedgerHeadAdvanceConflict",
    "ClaimLedgerHeadAdvanceReceipt",
    "ClaimLedgerHeadAdvanced",
    "ClaimLedgerCurrentHeadProjection",
    "ClaimLedgerExportService",
    "ClaimLedgerCandidateProjection",
    "ClaimLedgerHeadReadbackStatement",
    "ClaimLedgerHeadResolutionNonReceipt",
    "ClaimLedgerHeadStatement",
    "ClaimLedgerIssuanceNonReceipt",
    "ClaimLedgerLifecycleLimitation",
    "ClaimLedgerOwnerKey",
    "ClaimLedgerOwnerKeyDerivationInput",
    "ClaimLedgerOwnerPort",
    "ClaimLedgerPreparationStatement",
    "ClaimLedgerRootAssessment",
    "ClaimLedgerRootBasisStatement",
    "ClaimLedgerRootDenominatorReceipt",
    "ClaimLedgerRootStatement",
    "ClaimLedgerRootVerificationReceipt",
    "ClaimLifecycleBridgeAdvanced",
    "ClaimLifecycleBridgeAuthorityResult",
    "ClaimLifecycleBridgeNonReceipt",
    "ClaimLifecycleBridgeResultStatement",
    "DecisionPacketRootRow",
    "DecisionPacketRootSnapshot",
    "DecisionPacketRootSnapshotStatement",
    "PersistedClaimBridgePending",
    "PersistedClaimLedgerHead",
    "PersistedClaimLedgerRoot",
    "PersistedClaimLifecycleBridgeResult",
    "PreparedClaimLedgerInitialization",
    "UnappointedClaimLedgerOwner",
    "VerifiedClaimLedgerIssuance",
    "derive_claim_ledger_owner_scope_ref",
    "project_claim_ledger_current_head",
]
