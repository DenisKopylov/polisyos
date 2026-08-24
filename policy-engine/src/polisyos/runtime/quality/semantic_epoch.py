"""Owner-native semantic epoch derivation and chronology composition.

This module composes complete receipts supplied by L5, Lex, and Catalog
Acquisition.  It never enumerates those owners' storage directly and it never
turns a common commitment head into a native authority head.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, canon, contracts
from polisyos.runtime.quality.chronology_qualification import (
    NativeChronologyAuthorityAdapter,
    QualificationConsumer,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

ArtifactID = artifacts.ArtifactID
ArtifactRef = artifacts.ArtifactRef
ArtifactStore = artifacts.ArtifactStore
ArtifactWriteOptions = artifacts.ArtifactWriteOptions
InputRef = artifacts.InputRef
from_canonical_bytes = canon.from_canonical_bytes
chronology_contract = contracts.chronology
epoch_contract = contracts.epoch
Digest = epoch_contract.Digest
BoundaryOwnerKind = Literal["l5_schema_regime", "lex_amendment_window", "catalog_acquisition"]

_SCOPE_PREFIX = b"polisyos.epoch.scope.v1\0"
_BOUNDARY_REGISTRY_PREFIX = b"polisyos.epoch.boundary-registry.v1\0"
_BOUNDARY_DENOMINATOR_PREFIX = b"polisyos.epoch.boundary-denominator.v1\0"
_FACET_REGISTRY_PREFIX = b"polisyos.epoch.facet-registry.v1\0"
_FACET_DENOMINATOR_PREFIX = b"polisyos.epoch.facet-denominator.v1\0"
_MANIFEST_PREFIX = b"polisyos.epoch.semantic-manifest.v1\0"
_EPOCH_PREFIX = b"polisyos.epoch.semantic-version.v1\0"


class _EpochModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _sha256(*chunks: bytes) -> Digest:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _model_hash(prefix: bytes, value: BaseModel | dict[str, object]) -> Digest:
    return _sha256(prefix, epoch_contract.canonical_epoch_bytes(value))


def _raw_cas_hash(payload: bytes) -> Digest:
    return _sha256(payload)


def _artifact_ref_for_bytes(*, payload: bytes, kind: str, media_type: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(_raw_cas_hash(payload)),
        kind=kind,
        media_type=media_type,
    )


class EpochScopeIdentity(_EpochModel):
    """Opaque family scope whose bytes, profile, and digest agree."""

    schema_profile: str = Field(min_length=1)
    identity_bytes: bytes
    scope_identity_ref: Digest

    @model_validator(mode="after")
    def _bind_identity(self) -> Self:
        expected = _sha256(
            _SCOPE_PREFIX,
            len(self.schema_profile.encode()).to_bytes(8, "big"),
            self.schema_profile.encode(),
            len(self.identity_bytes).to_bytes(8, "big"),
            self.identity_bytes,
        )
        if self.scope_identity_ref != expected:
            raise ValueError("epoch scope identity ref differs from its bytes")
        return self


def build_epoch_scope_identity(*, schema_profile: str, identity_bytes: bytes) -> EpochScopeIdentity:
    """Construct one content-bound epoch scope identity."""

    return EpochScopeIdentity(
        schema_profile=schema_profile,
        identity_bytes=identity_bytes,
        scope_identity_ref=_sha256(
            _SCOPE_PREFIX,
            len(schema_profile.encode()).to_bytes(8, "big"),
            schema_profile.encode(),
            len(identity_bytes).to_bytes(8, "big"),
            identity_bytes,
        ),
    )


class EpochResolutionQuery(_EpochModel):
    """Sparse query over the three temporal roles needed by semantic epochs."""

    scope_identity: EpochScopeIdentity
    authority_purpose: str = Field(min_length=1)
    valid_effect_coordinate_evidence_ref: ArtifactRef
    valid_effect_coordinate_ref: Digest
    visibility_knowledge_cutoff_evidence_ref: ArtifactRef
    visibility_knowledge_cutoff_ref: Digest
    purpose_admission_cutoff_evidence_ref: ArtifactRef
    purpose_admission_cutoff_ref: Digest
    requested_query_context_ref: Digest


def build_epoch_resolution_query_from_evidence(
    *,
    artifact_store: ArtifactStore,
    scope_identity: EpochScopeIdentity,
    authority_purpose: str,
    valid_effect_coordinate_evidence_ref: ArtifactRef,
    visibility_knowledge_cutoff_evidence_ref: ArtifactRef,
    purpose_admission_cutoff_evidence_ref: ArtifactRef,
) -> EpochResolutionQuery:
    """Build one query only from independently re-read coordinate evidence.

    Callers select the three evidence artifacts but never supply any of the
    semantic coordinate or query-context digests derived from their bytes.
    """

    evidence = (
        ("valid_effect", valid_effect_coordinate_evidence_ref),
        ("visibility_knowledge_cutoff", visibility_knowledge_cutoff_evidence_ref),
        ("purpose_admission_cutoff", purpose_admission_cutoff_evidence_ref),
    )
    coordinate_refs: list[Digest] = []
    for role, ref in evidence:
        report = artifact_store.verify(ref.artifact_id)
        manifest = artifact_store.get_manifest(ref.artifact_id)
        payload = artifact_store.get_bytes(ref.artifact_id)
        if (
            not bool(getattr(report, "ok", False))
            or getattr(manifest, "artifact_id", None) != ref.artifact_id
            or getattr(manifest, "kind", None) != ref.kind
            or getattr(manifest, "media_type", None) != ref.media_type
            or _raw_cas_hash(payload) != str(ref.artifact_id)
        ):
            raise ValueError("epoch_coordinate_evidence_basis_mismatch")
        coordinate_refs.append(
            epoch_contract.native_coordinate_ref(
                family="epoch",
                role=role,
                schema_profile=ref.kind,
                coordinate_bytes=payload,
            )
        )
    context_ref = epoch_contract.epoch_query_context_ref(
        family="epoch",
        scope_bytes=scope_identity.identity_bytes,
        authority_purpose=authority_purpose,
        coordinate_refs=tuple(coordinate_refs),
    )
    return EpochResolutionQuery(
        scope_identity=scope_identity,
        authority_purpose=authority_purpose,
        valid_effect_coordinate_evidence_ref=valid_effect_coordinate_evidence_ref,
        valid_effect_coordinate_ref=coordinate_refs[0],
        visibility_knowledge_cutoff_evidence_ref=(visibility_knowledge_cutoff_evidence_ref),
        visibility_knowledge_cutoff_ref=coordinate_refs[1],
        purpose_admission_cutoff_evidence_ref=purpose_admission_cutoff_evidence_ref,
        purpose_admission_cutoff_ref=coordinate_refs[2],
        requested_query_context_ref=context_ref,
    )


class EpochBoundarySourceRegistration(_EpochModel):
    """Data registration for one owner-native boundary source."""

    registration_id: str = Field(min_length=1)
    owner_kind: BoundaryOwnerKind
    owner_source_ref: Digest
    opaque_scope_binding_ref: Digest


class EpochBoundarySourceRegistry(_EpochModel):
    """Complete data-owned set of owner source registrations."""

    schema_version: Literal["polisyos.epoch.boundary-source-registry.v1"]
    registrations: tuple[EpochBoundarySourceRegistration, ...] = Field(min_length=1)
    registry_content_hash: Digest

    @model_validator(mode="after")
    def _bind_registry(self) -> Self:
        ids = tuple(row.registration_id for row in self.registrations)
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate epoch boundary registration")
        expected = _model_hash(
            _BOUNDARY_REGISTRY_PREFIX,
            {
                "schema_version": self.schema_version,
                "registrations": [row.model_dump(mode="json") for row in self.registrations],
            },
        )
        if self.registry_content_hash != expected:
            raise ValueError("boundary registry hash differs from registrations")
        return self


def build_boundary_registry(
    registrations: Sequence[EpochBoundarySourceRegistration],
) -> EpochBoundarySourceRegistry:
    """Build a registry without mapping registration IDs in engine code."""

    rows = tuple(registrations)
    mapping: dict[str, object] = {
        "schema_version": "polisyos.epoch.boundary-source-registry.v1",
        "registrations": [row.model_dump(mode="json") for row in rows],
    }
    return EpochBoundarySourceRegistry(
        **mapping,
        registry_content_hash=_model_hash(_BOUNDARY_REGISTRY_PREFIX, mapping),
    )


def load_boundary_registry(path: Path) -> EpochBoundarySourceRegistry:
    """Load the complete tracked boundary registry without ID-specific code."""

    value = json.loads(Path(path).read_bytes())
    if not isinstance(value, dict) or set(value) != {"schema_version", "registrations"}:
        raise ValueError("epoch boundary registry has an unexpected top-level shape")
    rows = value.get("registrations")
    if not isinstance(rows, list):
        raise ValueError("epoch boundary registrations are not a list")
    return build_boundary_registry(
        tuple(EpochBoundarySourceRegistration.model_validate(row) for row in rows)
    )


class EpochBoundaryAssessment(_EpochModel):
    """One complete owner-native member assessment."""

    native_member_ref: ArtifactRef
    native_member_content_hash: Digest
    semantic_value_hash: Digest | None
    disposition: Literal["applicable", "not_applicable", "unresolved"]
    failure_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _failure_matches_disposition(self) -> Self:
        if (self.disposition == "unresolved") != (self.failure_code is not None):
            raise ValueError("boundary failure must match unresolved disposition")
        if self.disposition == "applicable" and self.semantic_value_hash is None:
            raise ValueError("applicable boundary lacks a semantic value")
        return self


class EpochOwnerEvidenceBinding(_EpochModel):
    """One owner receipt/projection kept outside semantic epoch identity."""

    role: str = Field(min_length=1)
    artifact_ref: ArtifactRef
    content_hash: Digest


class EpochBoundaryOwnerBatch(_EpochModel):
    """Reloaded complete receipt from one registered native owner."""

    registration_id: str = Field(min_length=1)
    owner_kind: BoundaryOwnerKind
    owner_source_ref: Digest
    opaque_scope_binding_ref: Digest
    requested_query_context_ref: Digest
    owner_source_snapshot_ref: ArtifactRef
    owner_source_snapshot_content_hash: Digest
    denominator_receipt_ref: ArtifactRef
    denominator_receipt_content_hash: Digest
    supporting_evidence: tuple[EpochOwnerEvidenceBinding, ...] = ()
    projection_status: Literal["resolved", "unresolved", "contested"] = "resolved"
    aggregate_failure_codes: tuple[str, ...] = ()
    declared_member_count: int = Field(ge=0)
    assessments: tuple[EpochBoundaryAssessment, ...]
    denominator_hash: Digest
    status: Literal["resolved", "unresolved"]
    failure_codes: tuple[str, ...]
    predicate_class: Literal["independently_reconciled"]

    @model_validator(mode="after")
    def _complete_owner_batch(self) -> Self:
        if self.declared_member_count != len(self.assessments):
            raise ValueError("owner batch count differs from assessments")
        refs = tuple(str(row.native_member_ref.artifact_id) for row in self.assessments)
        if len(refs) != len(set(refs)):
            raise ValueError("owner batch repeats a native member")
        if self.aggregate_failure_codes != tuple(sorted(set(self.aggregate_failure_codes))):
            raise ValueError("owner aggregate failure codes must be unique and sorted")
        failure_set = {row.failure_code for row in self.assessments if row.failure_code} | set(
            self.aggregate_failure_codes
        )
        if self.projection_status != "resolved":
            failure_set.add(f"{self.owner_kind}_projection_{self.projection_status}")
        failures = tuple(sorted(failure_set))
        if self.failure_codes != failures or self.status != (
            "unresolved" if failures else "resolved"
        ):
            raise ValueError("owner batch status/failures are not recomputed")
        evidence_refs = (
            self.denominator_receipt_ref,
            *(row.artifact_ref for row in self.supporting_evidence),
        )
        evidence_roles = tuple(row.role for row in self.supporting_evidence)
        required_roles = {
            "l5_schema_regime": ("scoped_projection",),
            "lex_amendment_window": (),
            "catalog_acquisition": (
                "native_membership",
                "semantic_projection_verification",
            ),
        }[self.owner_kind]
        if evidence_roles != required_roles:
            raise ValueError("owner batch supporting-evidence role denominator differs")
        if len({str(ref.artifact_id) for ref in evidence_refs}) != len(evidence_refs):
            raise ValueError("owner batch repeats an evidence artifact")
        expected_hash = _model_hash(
            _BOUNDARY_DENOMINATOR_PREFIX,
            {
                "registration_id": self.registration_id,
                "owner_kind": self.owner_kind,
                "owner_source_ref": self.owner_source_ref,
                "opaque_scope_binding_ref": self.opaque_scope_binding_ref,
                "requested_query_context_ref": self.requested_query_context_ref,
                "semantic_projection": [
                    {
                        "semantic_value_hash": row.semantic_value_hash,
                        "disposition": row.disposition,
                        "failure_code": row.failure_code,
                    }
                    for row in self.assessments
                ],
            },
        )
        if self.denominator_hash != expected_hash:
            raise ValueError("owner batch denominator hash is not recomputed")
        return self

    @property
    def all_owner_evidence_refs(self) -> tuple[ArtifactRef, ...]:
        """Return the complete evidence set without changing semantic identity."""

        return (
            self.denominator_receipt_ref,
            *(row.artifact_ref for row in self.supporting_evidence),
        )


class EpochBoundaryDenominatorReceipt(_EpochModel):
    """Complete aggregate over every registered owner batch."""

    query: EpochResolutionQuery
    boundary_registry_content_hash: Digest
    batches: tuple[EpochBoundaryOwnerBatch, ...]
    denominator_hash: Digest
    status: Literal["resolved", "unresolved"]
    failure_codes: tuple[str, ...]
    predicate_class: Literal["independently_reconciled"]

    @model_validator(mode="after")
    def _bind_complete_denominator(self) -> Self:
        if any(
            batch.requested_query_context_ref != self.query.requested_query_context_ref
            for batch in self.batches
        ):
            raise ValueError("boundary receipt batch belongs to another query")
        failures = tuple(sorted({code for batch in self.batches for code in batch.failure_codes}))
        expected = _model_hash(
            _BOUNDARY_DENOMINATOR_PREFIX,
            {
                "query_semantics": {
                    "scope_identity_ref": self.query.scope_identity.scope_identity_ref,
                    "authority_purpose": self.query.authority_purpose,
                    "valid_effect_coordinate_ref": self.query.valid_effect_coordinate_ref,
                    "visibility_knowledge_cutoff_ref": (self.query.visibility_knowledge_cutoff_ref),
                    "purpose_admission_cutoff_ref": (self.query.purpose_admission_cutoff_ref),
                    "requested_query_context_ref": self.query.requested_query_context_ref,
                },
                "registry_content_hash": self.boundary_registry_content_hash,
                "batches": [
                    {
                        "registration_id": row.registration_id,
                        "owner_kind": row.owner_kind,
                        "denominator_hash": row.denominator_hash,
                        "status": row.status,
                        "failure_codes": row.failure_codes,
                    }
                    for row in self.batches
                ],
            },
        )
        if self.denominator_hash != expected:
            raise ValueError("boundary receipt denominator hash is not recomputed")
        if self.failure_codes != failures or self.status != (
            "unresolved" if failures else "resolved"
        ):
            raise ValueError("boundary receipt status/failures are not recomputed")
        return self


class SemanticFacetRegistration(_EpochModel):
    """One opaque semantic facet registration."""

    facet_id: str = Field(min_length=1)
    source_binding_ref: Digest


class SemanticFacetRegistry(_EpochModel):
    """Complete data-owned semantic-facet set."""

    schema_version: Literal["polisyos.epoch.semantic-facet-registry.v1"]
    registrations: tuple[SemanticFacetRegistration, ...] = Field(min_length=1)
    registry_content_hash: Digest

    @model_validator(mode="after")
    def _bind_registry(self) -> Self:
        ids = tuple(row.facet_id for row in self.registrations)
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate semantic facet registration")
        expected = _model_hash(
            _FACET_REGISTRY_PREFIX,
            {
                "schema_version": self.schema_version,
                "registrations": [row.model_dump(mode="json") for row in self.registrations],
            },
        )
        if self.registry_content_hash != expected:
            raise ValueError("facet registry hash differs from registrations")
        return self


def build_facet_registry(
    registrations: Sequence[SemanticFacetRegistration],
) -> SemanticFacetRegistry:
    """Build the complete data-owned semantic-facet registry."""

    rows = tuple(registrations)
    mapping: dict[str, object] = {
        "schema_version": "polisyos.epoch.semantic-facet-registry.v1",
        "registrations": [row.model_dump(mode="json") for row in rows],
    }
    return SemanticFacetRegistry(
        **mapping,
        registry_content_hash=_model_hash(_FACET_REGISTRY_PREFIX, mapping),
    )


def load_facet_registry(path: Path) -> SemanticFacetRegistry:
    """Load the complete tracked facet registry without facet-specific code."""

    value = json.loads(Path(path).read_bytes())
    if not isinstance(value, dict) or set(value) != {"schema_version", "registrations"}:
        raise ValueError("semantic facet registry has an unexpected top-level shape")
    rows = value.get("registrations")
    if not isinstance(rows, list):
        raise ValueError("semantic facet registrations are not a list")
    return build_facet_registry(
        tuple(SemanticFacetRegistration.model_validate(row) for row in rows)
    )


class SemanticFacetValue(_EpochModel):
    """One source-bound semantic facet value."""

    facet_id: str = Field(min_length=1)
    source_record_ref: ArtifactRef
    source_record_content_hash: Digest
    semantic_value_hash: Digest
    annotation_hash: Digest
    status: Literal["resolved", "unresolved"]
    failure_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _failure_matches_status(self) -> Self:
        if (self.status == "unresolved") != (self.failure_code is not None):
            raise ValueError("facet failure must match unresolved status")
        return self


class SemanticFacetDenominatorReceipt(_EpochModel):
    """Complete ordered facet denominator under one query."""

    query: EpochResolutionQuery
    facet_registry_content_hash: Digest
    values: tuple[SemanticFacetValue, ...]
    denominator_hash: Digest
    status: Literal["resolved", "unresolved"]
    failure_codes: tuple[str, ...]
    predicate_class: Literal["independently_reconciled"]

    @model_validator(mode="after")
    def _bind_complete_denominator(self) -> Self:
        failures = tuple(sorted({row.failure_code for row in self.values if row.failure_code}))
        expected = _model_hash(
            _FACET_DENOMINATOR_PREFIX,
            {
                "query_semantics": {
                    "scope_identity_ref": self.query.scope_identity.scope_identity_ref,
                    "authority_purpose": self.query.authority_purpose,
                    "valid_effect_coordinate_ref": self.query.valid_effect_coordinate_ref,
                    "visibility_knowledge_cutoff_ref": (self.query.visibility_knowledge_cutoff_ref),
                    "purpose_admission_cutoff_ref": (self.query.purpose_admission_cutoff_ref),
                    "requested_query_context_ref": self.query.requested_query_context_ref,
                },
                "registry_content_hash": self.facet_registry_content_hash,
                "values": [
                    {
                        "facet_id": row.facet_id,
                        "semantic_value_hash": row.semantic_value_hash,
                        "status": row.status,
                        "failure_code": row.failure_code,
                    }
                    for row in self.values
                ],
            },
        )
        if self.denominator_hash != expected:
            raise ValueError("facet receipt denominator hash is not recomputed")
        if self.failure_codes != failures or self.status != (
            "unresolved" if failures else "resolved"
        ):
            raise ValueError("facet receipt status/failures are not recomputed")
        return self


class EpochInputReconciliation(_EpochModel):
    """Pure reconciliation of complete registered owner and facet inputs."""

    query: EpochResolutionQuery
    boundary_registry_content_hash: Digest
    facet_registry_content_hash: Digest
    owner_batches: tuple[EpochBoundaryOwnerBatch, ...]
    facet_values: tuple[SemanticFacetValue, ...]
    boundary_denominator_hash: Digest
    facet_denominator_hash: Digest
    status: Literal["resolved", "unresolved"]
    failure_codes: tuple[str, ...]


class SemanticEpochManifest(_EpochModel):
    """Content-bound semantic version; no operational ordinal enters its identity."""

    schema_version: Literal["polisyos.epoch.semantic-manifest.v1"]
    scope_identity: EpochScopeIdentity
    authority_purpose: str = Field(min_length=1)
    valid_effect_coordinate_ref: Digest
    visibility_knowledge_cutoff_ref: Digest
    purpose_admission_cutoff_ref: Digest
    requested_query_context_ref: Digest
    boundary_registry_content_hash: Digest
    facet_registry_content_hash: Digest
    boundary_denominator_hash: Digest
    facet_denominator_hash: Digest
    boundary_semantic_hashes: tuple[Digest, ...]
    facet_semantic_hashes: tuple[Digest, ...]
    predecessor_refs: tuple[Digest, ...]
    manifest_content_hash: Digest
    epoch_ref: Digest

    @model_validator(mode="after")
    def _bind_manifest_and_epoch(self) -> Self:
        payload = self.identity_payload()
        manifest_hash = _model_hash(_MANIFEST_PREFIX, payload)
        if self.manifest_content_hash != manifest_hash:
            raise ValueError("semantic manifest hash differs from its content")
        if self.epoch_ref != _sha256(_EPOCH_PREFIX, manifest_hash.encode()):
            raise ValueError("epoch ref differs from semantic manifest")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the semantic manifest projection excluding its own identities."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key not in {"manifest_content_hash", "epoch_ref"}
        }


def _build_manifest(
    *, reconciliation: EpochInputReconciliation, predecessor_refs: tuple[Digest, ...]
) -> SemanticEpochManifest:
    query = reconciliation.query
    values: dict[str, object] = {
        "schema_version": "polisyos.epoch.semantic-manifest.v1",
        "scope_identity": query.scope_identity.model_dump(mode="json"),
        "authority_purpose": query.authority_purpose,
        "valid_effect_coordinate_ref": query.valid_effect_coordinate_ref,
        "visibility_knowledge_cutoff_ref": query.visibility_knowledge_cutoff_ref,
        "purpose_admission_cutoff_ref": query.purpose_admission_cutoff_ref,
        "requested_query_context_ref": query.requested_query_context_ref,
        "boundary_registry_content_hash": reconciliation.boundary_registry_content_hash,
        "facet_registry_content_hash": reconciliation.facet_registry_content_hash,
        "boundary_denominator_hash": reconciliation.boundary_denominator_hash,
        "facet_denominator_hash": reconciliation.facet_denominator_hash,
        "boundary_semantic_hashes": sorted(
            row.semantic_value_hash
            for batch in reconciliation.owner_batches
            for row in batch.assessments
            if row.disposition == "applicable" and row.semantic_value_hash is not None
        ),
        "facet_semantic_hashes": sorted(
            row.semantic_value_hash for row in reconciliation.facet_values
        ),
        "predecessor_refs": list(predecessor_refs),
    }
    manifest_hash = _model_hash(_MANIFEST_PREFIX, values)
    return SemanticEpochManifest(
        **values,
        manifest_content_hash=manifest_hash,
        epoch_ref=_sha256(_EPOCH_PREFIX, manifest_hash.encode()),
    )


class EpochBranchAdjudication(_EpochModel):
    """Owner evidence selecting one branch without transaction-time ordering."""

    competing_head_refs: tuple[Digest, ...] = Field(min_length=2)
    selected_head_ref: Digest
    adjudication_ref: ArtifactRef
    adjudication_content_hash: Digest
    verifier_provenance_ref: ArtifactRef
    predicate_class: Literal["independently_reconciled", "institutionally_supplied"]

    @model_validator(mode="after")
    def _selected_head_is_competing(self) -> Self:
        if self.selected_head_ref not in self.competing_head_refs:
            raise ValueError("branch adjudication selects a non-competing head")
        return self


class EpochResolutionResult(_EpochModel):
    """Pure semantic epoch resolution result."""

    status: Literal["resolved", "no_change", "not_established", "contested"]
    reconciliation: EpochInputReconciliation
    manifest: SemanticEpochManifest | None
    failure_codes: tuple[str, ...]

    @model_validator(mode="after")
    def _result_shape(self) -> Self:
        positive = self.status in {"resolved", "no_change"}
        if positive != (self.manifest is not None):
            raise ValueError("epoch result manifest presence differs from status")
        if positive == bool(self.failure_codes):
            raise ValueError("epoch failures are required exactly for negative results")
        return self


def reconcile_epoch_inputs(
    *,
    query: EpochResolutionQuery,
    boundary_registry: EpochBoundarySourceRegistry,
    owner_batches: Sequence[EpochBoundaryOwnerBatch],
    facet_registry: SemanticFacetRegistry,
    facet_values: Sequence[SemanticFacetValue],
) -> EpochInputReconciliation:
    """Reconcile complete owner/facet denominators without reading their stores."""

    batches = tuple(owner_batches)
    facets = tuple(facet_values)
    expected_registrations = tuple(row.registration_id for row in boundary_registry.registrations)
    observed_registrations = tuple(row.registration_id for row in batches)
    expected_facets = tuple(row.facet_id for row in facet_registry.registrations)
    observed_facets = tuple(row.facet_id for row in facets)
    failures: set[str] = set()
    if observed_registrations != expected_registrations:
        failures.add("epoch_boundary_registration_denominator_mismatch")
    else:
        expected_bindings = {
            row.registration_id: (
                row.owner_kind,
                row.owner_source_ref,
                row.opaque_scope_binding_ref,
            )
            for row in boundary_registry.registrations
        }
        if any(
            expected_bindings[row.registration_id]
            != (row.owner_kind, row.owner_source_ref, row.opaque_scope_binding_ref)
            for row in batches
        ):
            failures.add("epoch_boundary_owner_binding_mismatch")
    if observed_facets != expected_facets:
        failures.add("epoch_facet_denominator_mismatch")
    if any(row.requested_query_context_ref != query.requested_query_context_ref for row in batches):
        failures.add("epoch_query_context_mismatch")
    failures.update(code for batch in batches for code in batch.failure_codes)
    failures.update(
        code for row in facets if row.failure_code is not None for code in (row.failure_code,)
    )
    boundary_hash = _model_hash(
        _BOUNDARY_DENOMINATOR_PREFIX,
        {
            "query_semantics": {
                "scope_identity_ref": query.scope_identity.scope_identity_ref,
                "authority_purpose": query.authority_purpose,
                "valid_effect_coordinate_ref": query.valid_effect_coordinate_ref,
                "visibility_knowledge_cutoff_ref": query.visibility_knowledge_cutoff_ref,
                "purpose_admission_cutoff_ref": query.purpose_admission_cutoff_ref,
                "requested_query_context_ref": query.requested_query_context_ref,
            },
            "registry_content_hash": boundary_registry.registry_content_hash,
            "batches": [
                {
                    "registration_id": row.registration_id,
                    "owner_kind": row.owner_kind,
                    "denominator_hash": row.denominator_hash,
                    "status": row.status,
                    "failure_codes": row.failure_codes,
                }
                for row in batches
            ],
        },
    )
    facet_hash = _model_hash(
        _FACET_DENOMINATOR_PREFIX,
        {
            "query_semantics": {
                "scope_identity_ref": query.scope_identity.scope_identity_ref,
                "authority_purpose": query.authority_purpose,
                "valid_effect_coordinate_ref": query.valid_effect_coordinate_ref,
                "visibility_knowledge_cutoff_ref": query.visibility_knowledge_cutoff_ref,
                "purpose_admission_cutoff_ref": query.purpose_admission_cutoff_ref,
                "requested_query_context_ref": query.requested_query_context_ref,
            },
            "registry_content_hash": facet_registry.registry_content_hash,
            "values": [
                {
                    "facet_id": row.facet_id,
                    "semantic_value_hash": row.semantic_value_hash,
                    "status": row.status,
                    "failure_code": row.failure_code,
                }
                for row in facets
            ],
        },
    )
    codes = tuple(sorted(failures))
    return EpochInputReconciliation(
        query=query,
        boundary_registry_content_hash=boundary_registry.registry_content_hash,
        facet_registry_content_hash=facet_registry.registry_content_hash,
        owner_batches=batches,
        facet_values=facets,
        boundary_denominator_hash=boundary_hash,
        facet_denominator_hash=facet_hash,
        status="unresolved" if codes else "resolved",
        failure_codes=codes,
    )


def resolve_semantic_epoch(
    *,
    query: EpochResolutionQuery,
    boundary_registry: EpochBoundarySourceRegistry,
    owner_batches: Sequence[EpochBoundaryOwnerBatch],
    facet_registry: SemanticFacetRegistry,
    facet_values: Sequence[SemanticFacetValue],
    prior_manifests: Sequence[SemanticEpochManifest],
    owner_branch_adjudications: Sequence[EpochBranchAdjudication] = (),
) -> EpochResolutionResult:
    """Resolve a semantic version; incomparable current branches fail closed."""

    reconciliation = reconcile_epoch_inputs(
        query=query,
        boundary_registry=boundary_registry,
        owner_batches=owner_batches,
        facet_registry=facet_registry,
        facet_values=facet_values,
    )
    if reconciliation.status != "resolved":
        contested = any(
            code.endswith("_projection_contested") for code in reconciliation.failure_codes
        )
        return EpochResolutionResult(
            status="contested" if contested else "not_established",
            reconciliation=reconciliation,
            manifest=None,
            failure_codes=reconciliation.failure_codes or ("epoch_scope_unresolved",),
        )
    prior = tuple(prior_manifests)
    referenced_predecessors = {ref for row in prior for ref in row.predecessor_refs}
    heads = tuple(row.epoch_ref for row in prior if row.epoch_ref not in referenced_predecessors)
    if len(heads) > 1:
        selected = [
            row.selected_head_ref
            for row in owner_branch_adjudications
            if set(row.competing_head_refs) == set(heads)
        ]
        if len(set(selected)) != 1:
            return EpochResolutionResult(
                status="contested",
                reconciliation=reconciliation,
                manifest=None,
                failure_codes=("epoch_branches_incomparable",),
            )
        heads = (selected[0],)
    manifest = _build_manifest(reconciliation=reconciliation, predecessor_refs=heads)
    current = next((row for row in prior if row.epoch_ref in heads), None)
    if current is not None:
        semantic_fields = {
            key
            for key in SemanticEpochManifest.model_fields
            if key not in {"predecessor_refs", "manifest_content_hash", "epoch_ref"}
        }
        if all(getattr(current, key) == getattr(manifest, key) for key in semantic_fields):
            manifest = current
    if current is not None and manifest.epoch_ref == current.epoch_ref:
        return EpochResolutionResult(
            status="no_change",
            reconciliation=reconciliation,
            manifest=manifest,
            failure_codes=(),
        )
    return EpochResolutionResult(
        status="resolved",
        reconciliation=reconciliation,
        manifest=manifest,
        failure_codes=(),
    )


class EpochHistoryEntry(_EpochModel):
    """Content-bound native history row sufficient for later validity replay."""

    epoch_ref: Digest
    manifest_ref: ArtifactRef
    manifest_content_hash: Digest
    native_member_ref: ArtifactRef
    native_member_content_hash: Digest
    predecessor_refs: tuple[Digest, ...]


class EpochHistoryAppendReceipt(_EpochModel):
    """Native compare-and-append receipt."""

    status: Literal["appended", "idempotent", "conflict"]
    manifest_ref: ArtifactRef
    epoch_ref: Digest
    expected_head_refs: tuple[Digest, ...]
    resulting_head_refs: tuple[Digest, ...]
    resulting_history_snapshot_ref: ArtifactRef | None
    resulting_history_snapshot_content_hash: Digest | None
    history_receipt_ref: ArtifactRef | None
    history_receipt_content_hash: Digest | None

    @model_validator(mode="after")
    def _receipt_shape(self) -> Self:
        persisted = (
            self.resulting_history_snapshot_ref,
            self.resulting_history_snapshot_content_hash,
            self.history_receipt_ref,
            self.history_receipt_content_hash,
        )
        if self.status == "conflict" and any(value is not None for value in persisted):
            raise ValueError("conflict append receipt cannot carry persisted success artifacts")
        if self.status != "conflict" and any(value is None for value in persisted):
            raise ValueError("successful append receipt lacks its qualified history snapshot")
        return self


class EpochScopeHistory(_EpochModel):
    """Exact native history snapshot returned by the epoch owner."""

    scope: EpochScopeIdentity
    authority_purpose: str = Field(min_length=1)
    entries: tuple[EpochHistoryEntry, ...]
    head_refs: tuple[Digest, ...]
    history_snapshot_ref: ArtifactRef
    history_snapshot_content_hash: Digest
    predicate_class: Literal["recomputed"]


class SemanticEpochHistoryRepository(Protocol):
    def append_if_current(
        self,
        *,
        expected_head_refs: tuple[Digest, ...],
        manifest_ref: ArtifactRef,
        native_member_ref: ArtifactRef,
        predecessor_refs: tuple[Digest, ...],
        expected_resulting_history_snapshot_hash: Digest,
    ) -> EpochHistoryAppendReceipt: ...

    def resolve_scope_history(
        self, *, scope: EpochScopeIdentity, authority_purpose: str
    ) -> EpochScopeHistory: ...

    def resolve_scope_history_by_ref(
        self, *, scope_identity_ref: Digest, authority_purpose: str
    ) -> EpochScopeHistory: ...


class EpochBoundaryOwnerAdapter(Protocol):
    owner_kind: BoundaryOwnerKind

    def resolve_complete_batch(
        self,
        *,
        registration: EpochBoundarySourceRegistration,
        owner_query: (
            epoch_contract.L5SchemaRegimeResolutionQuery
            | epoch_contract.LegalAmendmentWindowResolutionQuery
            | epoch_contract.AcquisitionBoundaryResolutionQuery
        ),
        candidate_refs: tuple[ArtifactRef, ...] = (),
    ) -> EpochBoundaryOwnerBatch: ...


class SemanticFacetProvider(Protocol):
    def resolve_all(
        self,
        *,
        registry: SemanticFacetRegistry,
        owner_batches: tuple[EpochBoundaryOwnerBatch, ...],
        query: EpochResolutionQuery,
    ) -> tuple[SemanticFacetValue, ...]: ...


class EpochChronologyPolicyOwner(Protocol):
    """Epoch-family carrier for native predicate and projection provenance."""

    native_schema_profile: str
    projection_verifier_provenance_ref: ArtifactRef
    projection_verifier_provenance_content_hash: Digest

    def member_predicates(
        self,
        *,
        query: chronology_contract.NativeChronologyQuery,
        entries: tuple[EpochHistoryEntry, ...],
    ) -> tuple[chronology_contract.MemberPredicateDisposition, ...]: ...

    def query_predicates(
        self, *, query: chronology_contract.NativeChronologyQuery
    ) -> tuple[chronology_contract.QueryPredicateDisposition, ...]: ...


def _persist_history_view(
    *,
    artifacts: ArtifactStore,
    scope: EpochScopeIdentity,
    authority_purpose: str,
    entries: tuple[EpochHistoryEntry, ...],
    head_refs: tuple[Digest, ...],
) -> EpochScopeHistory:
    statement = {
        "schema_version": "polisyos.epoch.scope-history.v1",
        "scope": scope.model_dump(mode="json"),
        "authority_purpose": authority_purpose,
        "entries": [entry.model_dump(mode="json") for entry in entries],
        "head_refs": list(head_refs),
    }
    raw = chronology_contract._frame_record(epoch_contract.canonical_epoch_bytes(statement))
    ref = artifacts.put_bytes(
        raw,
        ArtifactWriteOptions(
            kind="epoch.scope_history",
            media_type="application/vnd.polisyos.epoch+json",
        ),
    )
    if _raw_cas_hash(artifacts.get_bytes(ref.artifact_id)) != str(ref.artifact_id):
        raise ValueError("epoch scope-history view failed CAS readback")
    return EpochScopeHistory(
        scope=scope,
        authority_purpose=authority_purpose,
        entries=entries,
        head_refs=head_refs,
        history_snapshot_ref=ref,
        history_snapshot_content_hash=_raw_cas_hash(raw),
        predicate_class="recomputed",
    )


class SemanticEpochQualificationAdapter(NativeChronologyAuthorityAdapter):
    """Epoch-native adapter over exact owner history and projection bytes."""

    _policy_owner: EpochChronologyPolicyOwner | None

    def __init__(
        self,
        *,
        history: SemanticEpochHistoryRepository,
        artifacts: ArtifactStore,
        policy_owner: EpochChronologyPolicyOwner,
        _fixed_history: EpochScopeHistory | None = None,
    ) -> None:
        self._history = history
        self._artifacts = artifacts
        self._policy_owner = policy_owner
        self._fixed_history = _fixed_history

    @classmethod
    def from_unallocated_policy_authority(
        cls,
        *,
        history: SemanticEpochHistoryRepository,
        artifacts: ArtifactStore,
    ) -> SemanticEpochQualificationAdapter:
        """Build the epoch adapter without inventing a predicate-policy owner.

        The adapter may be routed into the qualification consumer, but any
        attempt to reconcile a candidate or issue a projection fails closed.
        The production unallocated-policy consumer returns before either call.
        """

        adapter = object.__new__(cls)
        adapter._history = history
        adapter._artifacts = artifacts
        adapter._policy_owner = None
        adapter._fixed_history = None
        return adapter

    def for_history(self, history: EpochScopeHistory) -> SemanticEpochQualificationAdapter:
        """Return a query-local adapter over an immutable prospective history."""

        if self._policy_owner is None:
            adapter = SemanticEpochQualificationAdapter.from_unallocated_policy_authority(
                history=self._history,
                artifacts=self._artifacts,
            )
            adapter._fixed_history = history
            return adapter
        return SemanticEpochQualificationAdapter(
            history=self._history,
            artifacts=self._artifacts,
            policy_owner=self._policy_owner,
            _fixed_history=history,
        )

    def _appointed_policy_owner(self) -> EpochChronologyPolicyOwner:
        owner = self._policy_owner
        if owner is None:
            raise ValueError("epoch_predicate_policy_authority_unallocated")
        return owner

    def _history_for_query(
        self, request: chronology_contract.NativeChronologyQuery
    ) -> EpochScopeHistory:
        if self._fixed_history is not None:
            if (
                self._fixed_history.scope.scope_identity_ref != request.domain.scope_ref
                or self._fixed_history.authority_purpose != request.domain.authority_purpose
            ):
                raise ValueError("fixed epoch history belongs to another query")
            return self._fixed_history
        return self._history.resolve_scope_history_by_ref(
            scope_identity_ref=request.domain.scope_ref,
            authority_purpose=request.domain.authority_purpose,
        )

    def _cutoff_history(
        self, request: chronology_contract.NativeChronologyQuery
    ) -> EpochScopeHistory:
        history = self._history_for_query(request)
        by_ref = {row.epoch_ref: row for row in history.entries}
        if request.requested_cutoff_ref not in by_ref:
            raise ValueError("requested epoch cutoff is absent from native history")
        selected: set[Digest] = set()
        visiting: set[Digest] = set()

        def visit(ref: Digest) -> None:
            if ref in selected:
                return
            if ref in visiting or ref not in by_ref:
                raise ValueError("epoch cutoff ancestry is cyclic or dangling")
            visiting.add(ref)
            for predecessor in by_ref[ref].predecessor_refs:
                visit(predecessor)
            visiting.remove(ref)
            selected.add(ref)

        visit(request.requested_cutoff_ref)
        return _persist_history_view(
            artifacts=self._artifacts,
            scope=history.scope,
            authority_purpose=history.authority_purpose,
            entries=tuple(row for row in history.entries if row.epoch_ref in selected),
            head_refs=(request.requested_cutoff_ref,),
        )

    def reconcile_candidate(
        self, request: chronology_contract.NativeChronologyQuery
    ) -> chronology_contract.NativeChronologyCandidate:
        policy_owner = self._appointed_policy_owner()
        history = self._cutoff_history(request)
        entries = history.entries
        members: list[chronology_contract.ChronologyMemberInput] = []
        for row in entries:
            payload = self._artifacts.get_bytes(row.native_member_ref.artifact_id)
            members.append(
                chronology_contract.ChronologyMemberInput(
                    member_ref=row.epoch_ref,
                    native_artifact_ref=row.native_member_ref,
                    native_content_hash=chronology_contract._native_content_hash(payload),
                    native_schema_profile=policy_owner.native_schema_profile,
                    native_bytes=payload,
                    member_admission_basis_ref=history.history_snapshot_content_hash,
                    member_admission_context_ref=request.requested_query_context_ref,
                )
            )
        context_payload = chronology_contract._frame_record(
            chronology_contract._canonical_raw_bytes(
                chronology_contract._raw_model_mapping(request)
            )
        )
        context_ref = self._artifacts.put_bytes(
            context_payload,
            ArtifactWriteOptions(
                kind="epoch.chronology_query_context",
                media_type="application/vnd.polisyos.chronology-query+json",
            ),
        )
        return chronology_contract.NativeChronologyCandidate(
            query=request,
            declared_denominator_ref=history.history_snapshot_content_hash,
            native_denominator_artifact_ref=history.history_snapshot_ref,
            native_denominator_content_hash=history.history_snapshot_content_hash,
            query_context_artifact_ref=context_ref,
            query_context_content_hash=_sha256(
                b"polisyos.epoch.chronology-query-context.v1\0", context_payload
            ),
            ordered_members=tuple(members),
            member_predicates=policy_owner.member_predicates(query=request, entries=entries),
            query_predicates=policy_owner.query_predicates(query=request),
            exterior_limitation_code=None,
            native_authority_head_refs=history.head_refs,
        )


class PreparedBoundaryCandidateBinding(_EpochModel):
    """Preserve the registry row that owns each opaque preparation candidate."""

    registration_id: str = Field(min_length=1)
    candidate_refs: tuple[ArtifactRef, ...]


class PreparedSemanticEpoch(_EpochModel):
    prepared_epoch_ref: ArtifactRef
    prepared_content_hash: Digest
    query: EpochResolutionQuery
    stamp: epoch_contract.SemanticEpochStamp
    boundary_candidate_refs: tuple[ArtifactRef, ...]
    boundary_candidates_by_registration: tuple[PreparedBoundaryCandidateBinding, ...]
    owner_denominator_receipt_refs: tuple[ArtifactRef, ...]
    status: Literal["prepared"]

    @model_validator(mode="after")
    def _candidate_mapping_is_complete(self) -> Self:
        statement = {
            name: getattr(self, name)
            for name in self.__class__.model_fields
            if name not in {"prepared_epoch_ref", "prepared_content_hash"}
        }
        raw = chronology_contract._frame_record(epoch_contract.canonical_epoch_bytes(statement))
        if (
            str(self.prepared_epoch_ref.artifact_id) != _raw_cas_hash(raw)
            or self.prepared_epoch_ref.kind != "epoch.prepared"
            or self.prepared_epoch_ref.media_type != "application/vnd.polisyos.epoch+json"
        ):
            raise ValueError("prepared epoch ref/profile differs from canonical statement")
        if self.prepared_content_hash != _model_hash(b"polisyos.epoch.prepared.v1\0", statement):
            raise ValueError("prepared epoch semantic hash differs from canonical statement")
        ids = tuple(row.registration_id for row in self.boundary_candidates_by_registration)
        if len(ids) != len(set(ids)):
            raise ValueError("prepared epoch repeats a boundary registration")
        flattened = tuple(
            ref for row in self.boundary_candidates_by_registration for ref in row.candidate_refs
        )
        if flattened != self.boundary_candidate_refs:
            raise ValueError("prepared epoch candidate mapping differs from flat identity set")
        if (
            self.stamp.requested_query_context_ref != self.query.requested_query_context_ref
            or self.stamp.authority_purpose != self.query.authority_purpose
            or self.stamp.valid_effect_coordinate_ref != self.query.valid_effect_coordinate_ref
            or self.stamp.visibility_knowledge_cutoff_ref
            != self.query.visibility_knowledge_cutoff_ref
            or self.stamp.purpose_admission_cutoff_ref != self.query.purpose_admission_cutoff_ref
        ):
            raise ValueError("prepared epoch stamp differs from its query")
        return self


class SemanticEpochProductionReceipt(epoch_contract.SemanticEpochProductionReceiptStatement):
    """Runtime name for the import-safe exact production statement."""


class PersistedSemanticEpochProductionReceipt(SemanticEpochProductionReceipt):
    """CAS identity for exact production-receipt bytes.

    The two persistence fields are deliberately excluded from the persisted
    payload.  ``SemanticEpochProductionReceipt`` remains the exact plan-owned
    statement and therefore cannot contain a reference to itself.
    """

    receipt_ref: ArtifactRef
    receipt_content_hash: Digest

    @model_validator(mode="after")
    def _bind_exact_statement(self) -> Self:
        statement = {
            name: getattr(self, name) for name in SemanticEpochProductionReceipt.model_fields
        }
        raw = chronology_contract._frame_record(epoch_contract.canonical_epoch_bytes(statement))
        if (
            str(self.receipt_ref.artifact_id) != _raw_cas_hash(raw)
            or self.receipt_ref.kind != "epoch.production_receipt"
            or self.receipt_ref.media_type
            != "application/vnd.polisyos.epoch-production-receipt+json"
        ):
            raise ValueError("persisted epoch production receipt ref/profile differs")
        if self.receipt_content_hash != _model_hash(
            b"polisyos.epoch.production-receipt.v1\0", statement
        ):
            raise ValueError("persisted epoch production receipt content hash differs")
        return self


def _persist_model(
    *, store: ArtifactStore, value: BaseModel, kind: str, inputs: list[InputRef] | None = None
) -> tuple[ArtifactRef, Digest]:
    raw = chronology_contract._frame_record(epoch_contract.canonical_epoch_bytes(value))
    ref = store.put_bytes(
        raw,
        ArtifactWriteOptions(
            kind=kind,
            media_type="application/vnd.polisyos.epoch+json",
            inputs=inputs,
        ),
    )
    report = store.verify(ref.artifact_id)
    readback = store.get_bytes(ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    records = chronology_contract._split_framed_records(readback)
    if (
        not report.ok
        or _raw_cas_hash(readback) != str(ref.artifact_id)
        or manifest.artifact_id != ref.artifact_id
        or manifest.kind != kind
        or manifest.media_type != "application/vnd.polisyos.epoch+json"
        or len(records) != 1
    ):
        raise RuntimeError("semantic epoch artifact CAS readback failed")
    reparsed = value.__class__.model_validate(from_canonical_bytes(records[0]))
    if reparsed != value:
        raise RuntimeError("semantic epoch artifact changed after CAS readback")
    return ref, _model_hash(kind.encode() + b"\0", value)


def persist_semantic_epoch_production_receipt(
    *, store: ArtifactStore, receipt: SemanticEpochProductionReceipt
) -> PersistedSemanticEpochProductionReceipt:
    """Persist and reread one exact production receipt without self-reference."""

    statement = receipt.model_dump(mode="json")
    raw = chronology_contract._frame_record(epoch_contract.canonical_epoch_bytes(statement))
    receipt_ref = store.put_bytes(
        raw,
        ArtifactWriteOptions(
            kind="epoch.production_receipt",
            media_type="application/vnd.polisyos.epoch-production-receipt+json",
            inputs=[
                InputRef(artifact_id=ref.artifact_id, role="epoch_production_input")
                for ref in (
                    receipt.prepared_epoch_ref,
                    receipt.admitted_boundary_evidence_ref,
                    receipt.semantic_manifest_ref,
                    receipt.history_append_receipt_ref,
                    receipt.chronology_bundle_ref,
                    receipt.chronology_verification_ref,
                )
                if ref is not None
            ],
        ),
    )
    report = store.verify(receipt_ref.artifact_id)
    readback = store.get_bytes(receipt_ref.artifact_id)
    manifest = store.get_manifest(receipt_ref.artifact_id)
    records = chronology_contract._split_framed_records(readback)
    if (
        not report.ok
        or _raw_cas_hash(readback) != str(receipt_ref.artifact_id)
        or manifest.artifact_id != receipt_ref.artifact_id
        or manifest.kind != "epoch.production_receipt"
        or manifest.media_type != "application/vnd.polisyos.epoch-production-receipt+json"
        or len(records) != 1
    ):
        raise RuntimeError("epoch production receipt frame denominator differs from one")
    if SemanticEpochProductionReceipt.model_validate(from_canonical_bytes(records[0])) != receipt:
        raise RuntimeError("epoch production receipt changed after CAS readback")
    return PersistedSemanticEpochProductionReceipt(
        **statement,
        receipt_ref=receipt_ref,
        receipt_content_hash=_model_hash(b"polisyos.epoch.production-receipt.v1\0", statement),
    )


def _owner_batch_hash(
    *,
    registration_id: str,
    owner_kind: BoundaryOwnerKind,
    owner_source_ref: Digest,
    opaque_scope_binding_ref: Digest,
    requested_query_context_ref: Digest,
    assessments: tuple[EpochBoundaryAssessment, ...],
) -> Digest:
    return _model_hash(
        _BOUNDARY_DENOMINATOR_PREFIX,
        {
            "registration_id": registration_id,
            "owner_kind": owner_kind,
            "owner_source_ref": owner_source_ref,
            "opaque_scope_binding_ref": opaque_scope_binding_ref,
            "requested_query_context_ref": requested_query_context_ref,
            "semantic_projection": [
                {
                    "semantic_value_hash": row.semantic_value_hash,
                    "disposition": row.disposition,
                    "failure_code": row.failure_code,
                }
                for row in assessments
            ],
        },
    )


class L5SchemaRegimeOwner(Protocol):
    def resolve_schema_regime_denominator(
        self, *, query: epoch_contract.L5SchemaRegimeResolutionQuery
    ) -> epoch_contract.L5SchemaRegimeDenominatorReceipt: ...

    def project_scoped_schema_regimes(
        self, *, receipt: epoch_contract.L5SchemaRegimeDenominatorReceipt
    ) -> epoch_contract.ScopedSchemaRegimeProjection: ...

    def load_schema_regime_owner_snapshot(self, *, ref: ArtifactRef) -> bytes: ...


class LegalAmendmentWindowOwner(Protocol):
    def resolve_amendment_window_denominator(
        self, *, query: epoch_contract.LegalAmendmentWindowResolutionQuery
    ) -> epoch_contract.LegalAmendmentWindowDenominatorReceipt: ...

    def load_amendment_owner_snapshot(self, *, ref: ArtifactRef) -> bytes: ...


class CatalogAcquisitionBoundaryOwner(Protocol):
    def resolve_native_membership(
        self,
        *,
        query: epoch_contract.AcquisitionBoundaryResolutionQuery,
        candidate: epoch_contract.AcquisitionSemanticBoundaryCandidate | None = None,
    ) -> epoch_contract.AcquisitionNativeMembershipReceipt: ...

    def resolve_semantic_candidate_denominator(
        self,
        *,
        query: epoch_contract.AcquisitionBoundaryResolutionQuery,
        native_membership: epoch_contract.AcquisitionNativeMembershipReceipt,
        candidate: epoch_contract.AcquisitionSemanticBoundaryCandidate | None = None,
    ) -> epoch_contract.AcquisitionSemanticCandidateDenominatorReceipt: ...

    def verify_semantic_projection(
        self,
        *,
        native_membership_ref: ArtifactRef,
        semantic_denominator_ref: ArtifactRef,
        prospective_candidate: epoch_contract.AcquisitionSemanticBoundaryCandidate | None,
    ) -> epoch_contract.AcquisitionSemanticProjectionVerificationReceipt: ...

    def load_acquisition_owner_snapshot(self, *, ref: ArtifactRef) -> bytes: ...


def _admit_owner_snapshot(*, artifacts: ArtifactStore, ref: ArtifactRef, payload: bytes) -> None:
    """Copy exact owner bytes into the task CAS and prove the appointed profile."""

    if _raw_cas_hash(payload) != str(ref.artifact_id):
        raise ValueError("owner snapshot bytes differ from their content address")
    admitted = artifacts.put_bytes(
        payload,
        ArtifactWriteOptions(kind=ref.kind, media_type=ref.media_type),
    )
    report = artifacts.verify(admitted.artifact_id)
    manifest = artifacts.get_manifest(admitted.artifact_id)
    if (
        admitted != ref
        or not report.ok
        or artifacts.get_bytes(admitted.artifact_id) != payload
        or manifest.artifact_id != ref.artifact_id
        or manifest.kind != ref.kind
        or manifest.media_type != ref.media_type
    ):
        raise ValueError("owner snapshot CAS admission/profile mismatch")


def _verify_l5_snapshot(
    *, payload: bytes, receipt: epoch_contract.L5SchemaRegimeDenominatorReceipt
) -> None:
    value = json.loads(payload)
    if not isinstance(value, dict) or set(value) != {
        "regimes",
        "scope_relations",
        "changepoints",
    }:
        raise ValueError("L5 owner snapshot has an unexpected shape")
    regimes = value["regimes"]
    if not isinstance(regimes, dict):
        raise ValueError("L5 owner snapshot regimes are not a mapping")
    if tuple(sorted(regimes)) != tuple(row.schema_regime_id for row in receipt.assessments):
        raise ValueError("L5 owner receipt is not complete over its snapshot")
    for row in receipt.assessments:
        native = epoch_contract.canonical_epoch_bytes(regimes[row.schema_regime_id])
        native_hash = _raw_cas_hash(native)
        if (
            row.regime_content_hash != native_hash
            or str(row.regime_source_ref.artifact_id) != native_hash
        ):
            raise ValueError("L5 assessment differs from frozen owner bytes")
    denominator = epoch_contract.canonical_epoch_bytes(
        {
            "query": receipt.query.model_dump(mode="json"),
            "owner_source_snapshot_content_hash": receipt.owner_source_snapshot_content_hash,
            "assessments": [row.model_dump(mode="json") for row in receipt.assessments],
        }
    )
    if receipt.denominator_hash != _raw_cas_hash(denominator):
        raise ValueError("L5 denominator hash is not recomputed")


def _verify_lex_snapshot(
    *, payload: bytes, receipt: epoch_contract.LegalAmendmentWindowDenominatorReceipt
) -> None:
    value = json.loads(payload)
    rows = value.get("rows") if isinstance(value, dict) else None
    owner_failure_code = value.get("owner_failure_code") if isinstance(value, dict) else None
    if (
        not isinstance(rows, list)
        or len(rows) != receipt.declared_amendment_count
        or owner_failure_code != receipt.owner_failure_code
    ):
        raise ValueError("Lex owner receipt is not complete over its snapshot")
    by_ref = {_raw_cas_hash(epoch_contract.canonical_epoch_bytes(row)): row for row in rows}
    if set(by_ref) != {
        str(assessment.amendment_ref.artifact_id) for assessment in receipt.assessments
    }:
        raise ValueError("Lex assessment set differs from frozen owner bytes")
    for assessment in receipt.assessments:
        if assessment.amendment_content_hash != str(assessment.amendment_ref.artifact_id):
            raise ValueError("Lex assessment content hash differs from its native ref")
    denominator = epoch_contract.canonical_epoch_bytes(
        {
            "query": receipt.query.model_dump(mode="json"),
            "snapshot_hash": receipt.owner_source_snapshot_content_hash,
            "assessments": [row.model_dump(mode="json") for row in receipt.assessments],
        }
    )
    if receipt.denominator_hash != _raw_cas_hash(denominator):
        raise ValueError("Lex denominator hash is not recomputed")


def _verify_acquisition_snapshot(
    *, payload: bytes, receipt: epoch_contract.AcquisitionNativeMembershipReceipt
) -> None:
    records = chronology_contract._split_framed_records(payload)
    if len(records) != 1:
        raise ValueError("acquisition owner snapshot frame denominator differs from one")
    value = json.loads(records[0])
    rows = value.get("rows") if isinstance(value, dict) else None
    if not isinstance(rows, list) or len(rows) != receipt.declared_native_member_count:
        raise ValueError("acquisition receipt is not complete over its owner snapshot")
    expected: dict[str, Digest] = {}
    for row in rows:
        canonical = epoch_contract.canonical_epoch_bytes(row)
        framed = chronology_contract._frame_record(canonical)
        expected[_raw_cas_hash(framed)] = _model_hash(
            b"polisyos.epoch.acquisition-native-member.v1\0", row
        )
    observed = {
        str(row.native_member_ref.artifact_id): row.native_member_content_hash
        for row in receipt.assessments
    }
    if expected != observed:
        raise ValueError("acquisition native assessments differ from frozen owner bytes")
    membership_hash = _model_hash(
        b"polisyos.epoch.acquisition-native-membership.v1\0",
        {
            "query": receipt.query.model_dump(mode="json"),
            "owner_source_snapshot_content_hash": receipt.owner_source_snapshot_content_hash,
            "assessments": [row.model_dump(mode="json") for row in receipt.assessments],
        },
    )
    if receipt.native_membership_hash != membership_hash:
        raise ValueError("acquisition native membership hash is not recomputed")


class L5EpochBoundaryOwnerAdapter:
    """Convert one complete L5 owner receipt without re-deciding scope."""

    owner_kind: BoundaryOwnerKind = "l5_schema_regime"

    def __init__(self, *, owner: L5SchemaRegimeOwner, artifacts: ArtifactStore) -> None:
        self._owner = owner
        self._artifacts = artifacts

    def resolve_complete_batch(
        self,
        *,
        registration: EpochBoundarySourceRegistration,
        owner_query: (
            epoch_contract.L5SchemaRegimeResolutionQuery
            | epoch_contract.LegalAmendmentWindowResolutionQuery
            | epoch_contract.AcquisitionBoundaryResolutionQuery
        ),
        candidate_refs: tuple[ArtifactRef, ...] = (),
    ) -> EpochBoundaryOwnerBatch:
        if not isinstance(owner_query, epoch_contract.L5SchemaRegimeResolutionQuery):
            raise TypeError("L5 adapter received a different owner query")
        if candidate_refs:
            raise ValueError("L5 boundary does not accept acquisition candidates")
        receipt = self._owner.resolve_schema_regime_denominator(query=owner_query)
        snapshot = self._owner.load_schema_regime_owner_snapshot(
            ref=receipt.owner_source_snapshot_ref
        )
        _admit_owner_snapshot(
            artifacts=self._artifacts,
            ref=receipt.owner_source_snapshot_ref,
            payload=snapshot,
        )
        if receipt.owner_source_snapshot_content_hash != _raw_cas_hash(snapshot):
            raise ValueError("L5 owner snapshot semantic hash differs from its bytes")
        _verify_l5_snapshot(payload=snapshot, receipt=receipt)
        receipt_ref, receipt_hash = _persist_model(
            store=self._artifacts,
            value=receipt,
            kind="l5.schema_regime_denominator_receipt",
        )
        projection = self._owner.project_scoped_schema_regimes(receipt=receipt)
        if (
            projection.denominator_receipt_ref != receipt_ref
            or projection.owner_source_snapshot_ref != receipt.owner_source_snapshot_ref
            or projection.scope_identity_ref != owner_query.scope_identity_ref
            or projection.valid_effect_coordinate_ref != owner_query.valid_effect_coordinate_ref
            or projection.requested_query_context_ref != owner_query.requested_query_context_ref
        ):
            raise ValueError("L5 scoped projection differs from its owner receipt")
        projection_ref, projection_hash = _persist_model(
            store=self._artifacts,
            value=projection,
            kind="epoch.l5_scoped_schema_regime_projection",
        )
        projection_failures = set(receipt.failure_codes)
        if projection.status != "resolved":
            projection_failures.add(f"{self.owner_kind}_projection_{projection.status}")
        assessments = tuple(
            EpochBoundaryAssessment(
                native_member_ref=row.regime_source_ref,
                native_member_content_hash=row.regime_content_hash,
                semantic_value_hash=(
                    _sha256(
                        b"polisyos.epoch.l5-scoped-regime.v1\0",
                        row.regime_content_hash.encode(),
                        projection.projection_content_hash.encode(),
                    )
                    if row.disposition == "applicable"
                    else None
                ),
                disposition=row.disposition,
                failure_code=row.failure_code,
            )
            for row in receipt.assessments
        )
        return EpochBoundaryOwnerBatch(
            registration_id=registration.registration_id,
            owner_kind=self.owner_kind,
            owner_source_ref=registration.owner_source_ref,
            opaque_scope_binding_ref=registration.opaque_scope_binding_ref,
            requested_query_context_ref=owner_query.requested_query_context_ref,
            owner_source_snapshot_ref=receipt.owner_source_snapshot_ref,
            owner_source_snapshot_content_hash=receipt.owner_source_snapshot_content_hash,
            denominator_receipt_ref=receipt_ref,
            denominator_receipt_content_hash=receipt_hash,
            supporting_evidence=(
                EpochOwnerEvidenceBinding(
                    role="scoped_projection",
                    artifact_ref=projection_ref,
                    content_hash=projection_hash,
                ),
            ),
            projection_status=projection.status,
            declared_member_count=len(assessments),
            assessments=assessments,
            denominator_hash=_owner_batch_hash(
                registration_id=registration.registration_id,
                owner_kind=self.owner_kind,
                owner_source_ref=registration.owner_source_ref,
                opaque_scope_binding_ref=registration.opaque_scope_binding_ref,
                requested_query_context_ref=owner_query.requested_query_context_ref,
                assessments=assessments,
            ),
            status="unresolved" if projection_failures else "resolved",
            failure_codes=tuple(sorted(projection_failures)),
            predicate_class="independently_reconciled",
        )


class LexEpochBoundaryOwnerAdapter:
    """Convert one complete legal amendment-window owner receipt."""

    owner_kind: BoundaryOwnerKind = "lex_amendment_window"

    def __init__(self, *, owner: LegalAmendmentWindowOwner, artifacts: ArtifactStore) -> None:
        self._owner = owner
        self._artifacts = artifacts

    def resolve_complete_batch(
        self,
        *,
        registration: EpochBoundarySourceRegistration,
        owner_query: (
            epoch_contract.L5SchemaRegimeResolutionQuery
            | epoch_contract.LegalAmendmentWindowResolutionQuery
            | epoch_contract.AcquisitionBoundaryResolutionQuery
        ),
        candidate_refs: tuple[ArtifactRef, ...] = (),
    ) -> EpochBoundaryOwnerBatch:
        if not isinstance(owner_query, epoch_contract.LegalAmendmentWindowResolutionQuery):
            raise TypeError("Lex adapter received a different owner query")
        if candidate_refs:
            raise ValueError("Lex boundary does not accept acquisition candidates")
        receipt = self._owner.resolve_amendment_window_denominator(query=owner_query)
        snapshot = self._owner.load_amendment_owner_snapshot(ref=receipt.owner_source_snapshot_ref)
        _admit_owner_snapshot(
            artifacts=self._artifacts,
            ref=receipt.owner_source_snapshot_ref,
            payload=snapshot,
        )
        if receipt.owner_source_snapshot_content_hash != _raw_cas_hash(snapshot):
            raise ValueError("Lex owner snapshot semantic hash differs from its bytes")
        _verify_lex_snapshot(payload=snapshot, receipt=receipt)
        receipt_ref, receipt_hash = _persist_model(
            store=self._artifacts,
            value=receipt,
            kind="epoch.lex_amendment_window_denominator",
        )
        assessments = tuple(
            EpochBoundaryAssessment(
                native_member_ref=row.amendment_ref,
                native_member_content_hash=row.amendment_content_hash,
                semantic_value_hash=(
                    row.amendment_content_hash if row.disposition == "applicable" else None
                ),
                disposition=row.disposition,
                failure_code=row.failure_code,
            )
            for row in receipt.assessments
        )
        return EpochBoundaryOwnerBatch(
            registration_id=registration.registration_id,
            owner_kind=self.owner_kind,
            owner_source_ref=registration.owner_source_ref,
            opaque_scope_binding_ref=registration.opaque_scope_binding_ref,
            requested_query_context_ref=owner_query.requested_query_context_ref,
            owner_source_snapshot_ref=receipt.owner_source_snapshot_ref,
            owner_source_snapshot_content_hash=receipt.owner_source_snapshot_content_hash,
            denominator_receipt_ref=receipt_ref,
            denominator_receipt_content_hash=receipt_hash,
            aggregate_failure_codes=tuple(
                sorted(
                    set(receipt.failure_codes)
                    - {row.failure_code for row in receipt.assessments if row.failure_code}
                )
            ),
            declared_member_count=len(assessments),
            assessments=assessments,
            denominator_hash=_owner_batch_hash(
                registration_id=registration.registration_id,
                owner_kind=self.owner_kind,
                owner_source_ref=registration.owner_source_ref,
                opaque_scope_binding_ref=registration.opaque_scope_binding_ref,
                requested_query_context_ref=owner_query.requested_query_context_ref,
                assessments=assessments,
            ),
            status=receipt.status,
            failure_codes=receipt.failure_codes,
            predicate_class="independently_reconciled",
        )


class CatalogAcquisitionEpochBoundaryOwnerAdapter:
    """Convert complete N13b native membership into the semantic boundary."""

    owner_kind: BoundaryOwnerKind = "catalog_acquisition"

    def __init__(self, *, owner: CatalogAcquisitionBoundaryOwner, artifacts: ArtifactStore) -> None:
        self._owner = owner
        self._artifacts = artifacts

    def resolve_complete_batch(
        self,
        *,
        registration: EpochBoundarySourceRegistration,
        owner_query: (
            epoch_contract.L5SchemaRegimeResolutionQuery
            | epoch_contract.LegalAmendmentWindowResolutionQuery
            | epoch_contract.AcquisitionBoundaryResolutionQuery
        ),
        candidate_refs: tuple[ArtifactRef, ...] = (),
    ) -> EpochBoundaryOwnerBatch:
        if not isinstance(owner_query, epoch_contract.AcquisitionBoundaryResolutionQuery):
            raise TypeError("N13b adapter received a different owner query")
        if len(candidate_refs) > 1:
            raise ValueError("one N13b preparation cannot introduce two candidates")
        candidate = None
        if candidate_refs:
            candidate_mapping = epoch_contract.load_verified_epoch_statement(
                store=self._artifacts,
                ref=candidate_refs[0],
                expected_kind="epoch.acquisition_semantic_boundary_candidate",
            )
            statement = epoch_contract.AcquisitionSemanticBoundaryCandidateStatement.model_validate(
                candidate_mapping
            )
            candidate = epoch_contract.AcquisitionSemanticBoundaryCandidate(
                candidate_ref=candidate_refs[0],
                candidate_content_hash=(
                    epoch_contract.acquisition_semantic_candidate_content_hash(statement)
                ),
                statement=statement,
            )
        receipt = self._owner.resolve_native_membership(
            query=owner_query,
            candidate=candidate,
        )
        snapshot = self._owner.load_acquisition_owner_snapshot(
            ref=receipt.owner_source_snapshot_ref
        )
        _admit_owner_snapshot(
            artifacts=self._artifacts,
            ref=receipt.owner_source_snapshot_ref,
            payload=snapshot,
        )
        snapshot_mapping = json.loads(chronology_contract._split_framed_records(snapshot)[0])
        if receipt.owner_source_snapshot_content_hash != _model_hash(
            b"polisyos.epoch.acquisition-owner-snapshot.v1\0", snapshot_mapping
        ):
            raise ValueError("acquisition owner snapshot semantic hash differs")
        _verify_acquisition_snapshot(payload=snapshot, receipt=receipt)
        native_ref, native_hash = _persist_model(
            store=self._artifacts,
            value=receipt,
            kind="epoch.acquisition_native_membership",
        )
        semantic = self._owner.resolve_semantic_candidate_denominator(
            query=owner_query,
            native_membership=receipt,
            candidate=candidate,
        )
        semantic_ref, semantic_hash = _persist_model(
            store=self._artifacts,
            value=semantic,
            kind="epoch.acquisition_semantic_denominator_receipt",
        )
        projection = self._owner.verify_semantic_projection(
            native_membership_ref=native_ref,
            semantic_denominator_ref=semantic_ref,
            prospective_candidate=candidate,
        )
        projection_ref, projection_hash = _persist_model(
            store=self._artifacts,
            value=projection,
            kind="epoch.acquisition_semantic_projection_verification_receipt",
        )
        if projection.status != "verified":
            raise ValueError("acquisition semantic projection is not verified")
        assessments = tuple(
            EpochBoundaryAssessment(
                native_member_ref=row.semantic_candidate_ref,
                native_member_content_hash=row.semantic_candidate_content_hash,
                semantic_value_hash=(
                    row.semantic_candidate_content_hash if row.disposition == "applicable" else None
                ),
                disposition=row.disposition,
                failure_code=row.failure_code,
            )
            for row in semantic.assessments
        )
        return EpochBoundaryOwnerBatch(
            registration_id=registration.registration_id,
            owner_kind=self.owner_kind,
            owner_source_ref=registration.owner_source_ref,
            opaque_scope_binding_ref=registration.opaque_scope_binding_ref,
            requested_query_context_ref=owner_query.requested_query_context_ref,
            owner_source_snapshot_ref=receipt.owner_source_snapshot_ref,
            owner_source_snapshot_content_hash=receipt.owner_source_snapshot_content_hash,
            denominator_receipt_ref=semantic_ref,
            denominator_receipt_content_hash=semantic_hash,
            supporting_evidence=(
                EpochOwnerEvidenceBinding(
                    role="native_membership",
                    artifact_ref=native_ref,
                    content_hash=native_hash,
                ),
                EpochOwnerEvidenceBinding(
                    role="semantic_projection_verification",
                    artifact_ref=projection_ref,
                    content_hash=projection_hash,
                ),
            ),
            aggregate_failure_codes=tuple(
                sorted(
                    set(semantic.failure_codes)
                    - {row.failure_code for row in semantic.assessments if row.failure_code}
                )
            ),
            declared_member_count=len(assessments),
            assessments=assessments,
            denominator_hash=_owner_batch_hash(
                registration_id=registration.registration_id,
                owner_kind=self.owner_kind,
                owner_source_ref=registration.owner_source_ref,
                opaque_scope_binding_ref=registration.opaque_scope_binding_ref,
                requested_query_context_ref=owner_query.requested_query_context_ref,
                assessments=assessments,
            ),
            status=semantic.status,
            failure_codes=semantic.failure_codes,
            predicate_class="independently_reconciled",
        )


class ArtifactSemanticFacetProvider:
    """One generic provider over the complete data-owned facet registry."""

    def __init__(
        self, *, artifacts: ArtifactStore, source_refs: Mapping[Digest, ArtifactRef]
    ) -> None:
        self._artifacts = artifacts
        self._source_refs = dict(source_refs)

    def resolve_all(
        self,
        *,
        registry: SemanticFacetRegistry,
        owner_batches: tuple[EpochBoundaryOwnerBatch, ...],
        query: EpochResolutionQuery,
    ) -> tuple[SemanticFacetValue, ...]:
        del owner_batches, query
        expected = tuple(row.source_binding_ref for row in registry.registrations)
        if set(expected) != set(self._source_refs):
            raise ValueError("semantic facet source denominator mismatch")
        values: list[SemanticFacetValue] = []
        for registration in registry.registrations:
            ref = self._source_refs[registration.source_binding_ref]
            if registration.source_binding_ref != str(ref.artifact_id):
                raise ValueError("semantic facet source binding is not content-addressed")
            report = self._artifacts.verify(ref.artifact_id)
            raw = self._artifacts.get_bytes(ref.artifact_id)
            if not report.ok or _raw_cas_hash(raw) != str(ref.artifact_id):
                raise ValueError("semantic facet source failed CAS verification")
            try:
                decoded = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError):
                decoded = None
            if isinstance(decoded, dict) and "semantic_value" in decoded:
                semantic_bytes = epoch_contract.canonical_epoch_bytes(
                    {"semantic_value": decoded["semantic_value"]}
                )
                annotation_bytes = epoch_contract.canonical_epoch_bytes(
                    {"annotation": decoded.get("annotation")}
                )
            else:
                semantic_bytes = raw
                annotation_bytes = registration.facet_id.encode()
            semantic_hash = _sha256(b"polisyos.epoch.facet-value.v1\0", semantic_bytes)
            values.append(
                SemanticFacetValue(
                    facet_id=registration.facet_id,
                    source_record_ref=ref,
                    source_record_content_hash=_raw_cas_hash(raw),
                    semantic_value_hash=semantic_hash,
                    annotation_hash=_sha256(
                        b"polisyos.epoch.facet-annotation.v1\0",
                        annotation_bytes,
                    ),
                    status="resolved",
                    failure_code=None,
                )
            )
        return tuple(values)


class SemanticEpochService:
    """Production composition root for complete native receipts and C2 proof."""

    def __init__(
        self,
        *,
        boundary_registry: EpochBoundarySourceRegistry,
        boundary_adapters: Mapping[BoundaryOwnerKind, EpochBoundaryOwnerAdapter],
        facet_registry: SemanticFacetRegistry,
        facet_provider: SemanticFacetProvider,
        history: SemanticEpochHistoryRepository,
        artifact_store: ArtifactStore,
        qualification_consumer: QualificationConsumer,
        chronology_adapter: SemanticEpochQualificationAdapter,
    ) -> None:
        expected = {row.owner_kind for row in boundary_registry.registrations}
        observed = set(boundary_adapters)
        if expected != observed:
            raise ValueError("epoch owner-kind adapter denominator mismatch")
        if any(adapter.owner_kind != kind for kind, adapter in boundary_adapters.items()):
            raise ValueError("epoch owner-kind adapter key mismatch")
        self._boundary_registry = boundary_registry
        self._boundary_adapters = dict(boundary_adapters)
        self._facet_registry = facet_registry
        self._facet_provider = facet_provider
        self._history = history
        self._artifact_store = artifact_store
        self._qualification_consumer = qualification_consumer
        self._chronology_adapter = chronology_adapter

    def _owner_query(
        self, *, kind: BoundaryOwnerKind, query: EpochResolutionQuery
    ) -> (
        epoch_contract.L5SchemaRegimeResolutionQuery
        | epoch_contract.LegalAmendmentWindowResolutionQuery
        | epoch_contract.AcquisitionBoundaryResolutionQuery
    ):
        def raw(ref: ArtifactRef) -> bytes:
            report = self._artifact_store.verify(ref.artifact_id)
            payload = self._artifact_store.get_bytes(ref.artifact_id)
            manifest = self._artifact_store.get_manifest(ref.artifact_id)
            if (
                not report.ok
                or _raw_cas_hash(payload) != str(ref.artifact_id)
                or manifest.artifact_id != ref.artifact_id
                or manifest.kind != ref.kind
                or manifest.media_type != ref.media_type
            ):
                raise ValueError("epoch coordinate evidence is not CAS-verified")
            return payload

        valid = raw(query.valid_effect_coordinate_evidence_ref)
        visibility = raw(query.visibility_knowledge_cutoff_evidence_ref)
        admission = raw(query.purpose_admission_cutoff_evidence_ref)
        evidence = (
            (
                "valid_effect",
                query.valid_effect_coordinate_evidence_ref,
                valid,
                query.valid_effect_coordinate_ref,
            ),
            (
                "visibility_knowledge_cutoff",
                query.visibility_knowledge_cutoff_evidence_ref,
                visibility,
                query.visibility_knowledge_cutoff_ref,
            ),
            (
                "purpose_admission_cutoff",
                query.purpose_admission_cutoff_evidence_ref,
                admission,
                query.purpose_admission_cutoff_ref,
            ),
        )
        for role, ref, payload, observed in evidence:
            expected = epoch_contract.native_coordinate_ref(
                family="epoch",
                role=role,
                schema_profile=ref.kind,
                coordinate_bytes=payload,
            )
            if expected != observed:
                raise ValueError("epoch coordinate evidence bytes/ref mismatch")
        expected_context = epoch_contract.epoch_query_context_ref(
            family="epoch",
            scope_bytes=query.scope_identity.identity_bytes,
            authority_purpose=query.authority_purpose,
            coordinate_refs=(
                query.valid_effect_coordinate_ref,
                query.visibility_knowledge_cutoff_ref,
                query.purpose_admission_cutoff_ref,
            ),
        )
        if expected_context != query.requested_query_context_ref:
            raise ValueError("epoch query context differs from its bound coordinates")
        common: dict[str, object] = {
            "authority_purpose": query.authority_purpose,
            "visibility_knowledge_cutoff_schema_profile": (
                query.visibility_knowledge_cutoff_evidence_ref.kind
            ),
            "visibility_knowledge_cutoff_bytes": visibility,
            "visibility_knowledge_cutoff_ref": epoch_contract.native_coordinate_ref(
                family=kind,
                role="visibility_knowledge_cutoff",
                schema_profile=query.visibility_knowledge_cutoff_evidence_ref.kind,
                coordinate_bytes=visibility,
            ),
            "purpose_admission_cutoff_schema_profile": (
                query.purpose_admission_cutoff_evidence_ref.kind
            ),
            "purpose_admission_cutoff_bytes": admission,
            "purpose_admission_cutoff_ref": epoch_contract.native_coordinate_ref(
                family=kind,
                role="purpose_admission_cutoff",
                schema_profile=query.purpose_admission_cutoff_evidence_ref.kind,
                coordinate_bytes=admission,
            ),
            "requested_query_context_ref": query.requested_query_context_ref,
        }
        if kind == "l5_schema_regime":
            return epoch_contract.L5SchemaRegimeResolutionQuery(
                scope_identity_ref=query.scope_identity.scope_identity_ref,
                valid_effect_value=__import__("datetime").date.fromisoformat(valid.decode()),
                valid_effect_coordinate_schema_profile=(
                    query.valid_effect_coordinate_evidence_ref.kind
                ),
                valid_effect_coordinate_ref=epoch_contract.native_coordinate_ref(
                    family=kind,
                    role="valid_effect",
                    schema_profile=query.valid_effect_coordinate_evidence_ref.kind,
                    coordinate_bytes=valid,
                ),
                **common,
            )
        if kind == "lex_amendment_window":
            scope = json.loads(query.scope_identity.identity_bytes)
            if not isinstance(scope, dict):
                raise ValueError("lex epoch scope is not a mapping")
            return epoch_contract.LegalAmendmentWindowResolutionQuery(
                jurisdiction=str(scope["jurisdiction"]),
                domain=str(scope["domain"]),
                valid_effect_value=__import__("datetime").date.fromisoformat(valid.decode()),
                valid_effect_coordinate_schema_profile=(
                    query.valid_effect_coordinate_evidence_ref.kind
                ),
                valid_effect_coordinate_ref=epoch_contract.native_coordinate_ref(
                    family=kind,
                    role="valid_effect",
                    schema_profile=query.valid_effect_coordinate_evidence_ref.kind,
                    coordinate_bytes=valid,
                ),
                **common,
            )
        return epoch_contract.AcquisitionBoundaryResolutionQuery(
            scope_identity_ref=query.scope_identity.scope_identity_ref,
            valid_effect_coordinate_schema_profile=(
                query.valid_effect_coordinate_evidence_ref.kind
            ),
            valid_effect_coordinate_bytes=valid,
            valid_effect_coordinate_ref=epoch_contract.native_coordinate_ref(
                family=kind,
                role="valid_effect",
                schema_profile=query.valid_effect_coordinate_evidence_ref.kind,
                coordinate_bytes=valid,
            ),
            **common,
        )

    def _collect(
        self,
        *,
        query: EpochResolutionQuery,
        boundary_candidate_refs: Mapping[str, tuple[ArtifactRef, ...]] | None = None,
    ) -> tuple[tuple[EpochBoundaryOwnerBatch, ...], tuple[SemanticFacetValue, ...]]:
        if boundary_candidate_refs is not None:
            registered = {row.registration_id for row in self._boundary_registry.registrations}
            unknown = set(boundary_candidate_refs) - registered
            if unknown:
                raise ValueError(
                    "unregistered epoch boundary candidate keys: " + ",".join(sorted(unknown))
                )
        batches = tuple(
            self._boundary_adapters[registration.owner_kind].resolve_complete_batch(
                registration=registration,
                owner_query=self._owner_query(kind=registration.owner_kind, query=query),
                candidate_refs=(
                    ()
                    if boundary_candidate_refs is None
                    else boundary_candidate_refs.get(registration.registration_id, ())
                ),
            )
            for registration in self._boundary_registry.registrations
        )
        facets = self._facet_provider.resolve_all(
            registry=self._facet_registry,
            owner_batches=batches,
            query=query,
        )
        return batches, facets

    def _negative(
        self,
        *,
        mode: Literal["ordinary", "acquisition_finalization"],
        query: EpochResolutionQuery,
        status: Literal["not_established", "contested"],
        codes: tuple[str, ...],
        prepared_ref: ArtifactRef | None = None,
        admitted_ref: ArtifactRef | None = None,
        owner_receipt_refs: tuple[ArtifactRef, ...] = (),
    ) -> PersistedSemanticEpochProductionReceipt:
        receipt = SemanticEpochProductionReceipt(
            production_mode=mode,
            status=status,
            prepared_epoch_ref=prepared_ref,
            admitted_boundary_evidence_ref=admitted_ref,
            epoch_ref=None,
            semantic_manifest_ref=None,
            owner_denominator_receipt_refs=owner_receipt_refs,
            history_append_receipt_ref=None,
            chronology_bundle_ref=None,
            chronology_verification_ref=None,
            requested_query_context_ref=query.requested_query_context_ref,
            failure_codes=codes,
        )
        return persist_semantic_epoch_production_receipt(
            store=self._artifact_store,
            receipt=receipt,
        )

    def _append_and_qualify(
        self,
        *,
        query: EpochResolutionQuery,
        result: EpochResolutionResult,
        mode: Literal["ordinary", "acquisition_finalization"],
        prepared_ref: ArtifactRef | None = None,
        admitted_ref: ArtifactRef | None = None,
    ) -> PersistedSemanticEpochProductionReceipt:
        manifest = result.manifest
        if manifest is None:
            return self._negative(
                mode=mode,
                query=query,
                status="contested" if result.status == "contested" else "not_established",
                codes=result.failure_codes,
                prepared_ref=prepared_ref,
                admitted_ref=admitted_ref,
                owner_receipt_refs=tuple(
                    ref
                    for batch in result.reconciliation.owner_batches
                    for ref in batch.all_owner_evidence_refs
                ),
            )
        manifest_ref, _ = _persist_model(
            store=self._artifact_store,
            value=manifest,
            kind="epoch.semantic_manifest",
        )
        native_member_ref = manifest_ref
        current_history = self._history.resolve_scope_history(
            scope=query.scope_identity,
            authority_purpose=query.authority_purpose,
        )
        staged_entries = current_history.entries
        if manifest.epoch_ref not in {row.epoch_ref for row in staged_entries}:
            manifest_raw = self._artifact_store.get_bytes(manifest_ref.artifact_id)
            staged_entries = (
                *staged_entries,
                EpochHistoryEntry(
                    epoch_ref=manifest.epoch_ref,
                    manifest_ref=manifest_ref,
                    manifest_content_hash=manifest.manifest_content_hash,
                    native_member_ref=native_member_ref,
                    native_member_content_hash=_raw_cas_hash(manifest_raw),
                    predecessor_refs=manifest.predecessor_refs,
                ),
            )
        staged = _persist_history_view(
            artifacts=self._artifact_store,
            scope=query.scope_identity,
            authority_purpose=query.authority_purpose,
            entries=staged_entries,
            head_refs=(manifest.epoch_ref,),
        )
        chronology_query = chronology_contract.NativeChronologyQuery(
            domain=chronology_contract.ChronologyProofDomain(
                format="polisyos.chronology.full-prefix.v1",
                profile="full_prefix_canon_json_0_2_0_sha256_256_v1",
                proof_domain="semantic_epoch",
                family="epoch",
                scope_ref=query.scope_identity.scope_identity_ref,
                authority_purpose=query.authority_purpose,
            ),
            requested_cutoff_ref=manifest.epoch_ref,
            requested_query_context_ref=query.requested_query_context_ref,
        )
        qualified = self._qualification_consumer.qualify(
            adapter=self._chronology_adapter.for_history(staged),
            request=chronology_query,
        )
        if not isinstance(qualified, chronology_contract.NativeChronologyQualified):
            failure_code = (
                qualified.failure.code
                if isinstance(
                    qualified,
                    chronology_contract.NativeChronologyPolicyResolutionFailed,
                )
                else str(getattr(qualified, "code", qualified.result_kind))
            )
            return self._negative(
                mode=mode,
                query=query,
                status="not_established",
                codes=(failure_code,),
                prepared_ref=prepared_ref,
                admitted_ref=admitted_ref,
                owner_receipt_refs=tuple(
                    ref
                    for batch in result.reconciliation.owner_batches
                    for ref in batch.all_owner_evidence_refs
                ),
            )
        append = self._history.append_if_current(
            expected_head_refs=manifest.predecessor_refs,
            manifest_ref=manifest_ref,
            native_member_ref=native_member_ref,
            predecessor_refs=manifest.predecessor_refs,
            expected_resulting_history_snapshot_hash=(staged.history_snapshot_content_hash),
        )
        if (
            append.status == "conflict"
            or append.history_receipt_ref is None
            or manifest.epoch_ref not in append.resulting_head_refs
        ):
            return self._negative(
                mode=mode,
                query=query,
                status="contested",
                codes=("epoch_history_head_conflict",),
                prepared_ref=prepared_ref,
                admitted_ref=admitted_ref,
                owner_receipt_refs=tuple(
                    ref
                    for batch in result.reconciliation.owner_batches
                    for ref in batch.all_owner_evidence_refs
                ),
            )
        receipt = SemanticEpochProductionReceipt(
            production_mode=mode,
            status="no_change" if result.status == "no_change" else "appended",
            prepared_epoch_ref=prepared_ref,
            admitted_boundary_evidence_ref=admitted_ref,
            epoch_ref=manifest.epoch_ref,
            semantic_manifest_ref=manifest_ref,
            owner_denominator_receipt_refs=tuple(
                ref
                for batch in result.reconciliation.owner_batches
                for ref in batch.all_owner_evidence_refs
            ),
            history_append_receipt_ref=append.history_receipt_ref,
            chronology_bundle_ref=qualified.persisted_proof.artifact_ref,
            chronology_verification_ref=qualified.persisted_proof.verifier_result_ref,
            requested_query_context_ref=query.requested_query_context_ref,
            failure_codes=(),
        )
        return persist_semantic_epoch_production_receipt(
            store=self._artifact_store,
            receipt=receipt,
        )

    def resolve_and_persist_epoch(
        self, *, query: EpochResolutionQuery
    ) -> PersistedSemanticEpochProductionReceipt:
        """Resolve complete owner inputs, append native history, and persist C2 proof."""

        try:
            batches, facets = self._collect(query=query)
            history = self._history.resolve_scope_history(
                scope=query.scope_identity,
                authority_purpose=query.authority_purpose,
            )
            result = resolve_semantic_epoch(
                query=query,
                boundary_registry=self._boundary_registry,
                owner_batches=batches,
                facet_registry=self._facet_registry,
                facet_values=facets,
                prior_manifests=tuple(
                    SemanticEpochManifest.model_validate(
                        from_canonical_bytes(
                            chronology_contract._split_framed_records(
                                self._artifact_store.get_bytes(row.manifest_ref.artifact_id)
                            )[0]
                        )
                    )
                    for row in history.entries
                ),
            )
            return self._append_and_qualify(query=query, result=result, mode="ordinary")
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return self._negative(
                mode="ordinary",
                query=query,
                status="not_established",
                codes=("epoch_scope_unresolved",),
            )

    def prepare_epoch_candidate(
        self,
        *,
        query: EpochResolutionQuery,
        boundary_candidate_refs: Mapping[str, tuple[ArtifactRef, ...]],
    ) -> PreparedSemanticEpoch:
        """Persist a stable candidate/stamp without moving a native head."""

        batches, facets = self._collect(
            query=query,
            boundary_candidate_refs=boundary_candidate_refs,
        )
        history = self._history.resolve_scope_history(
            scope=query.scope_identity,
            authority_purpose=query.authority_purpose,
        )
        result = resolve_semantic_epoch(
            query=query,
            boundary_registry=self._boundary_registry,
            owner_batches=batches,
            facet_registry=self._facet_registry,
            facet_values=facets,
            prior_manifests=tuple(
                SemanticEpochManifest.model_validate(
                    from_canonical_bytes(
                        chronology_contract._split_framed_records(
                            self._artifact_store.get_bytes(row.manifest_ref.artifact_id)
                        )[0]
                    )
                )
                for row in history.entries
            ),
        )
        if result.manifest is None:
            raise ValueError("semantic epoch candidate is not resolvable")
        manifest_ref, _ = _persist_model(
            store=self._artifact_store,
            value=result.manifest,
            kind="epoch.semantic_manifest",
        )
        boundary_receipt = EpochBoundaryDenominatorReceipt(
            query=query,
            boundary_registry_content_hash=self._boundary_registry.registry_content_hash,
            batches=batches,
            denominator_hash=result.reconciliation.boundary_denominator_hash,
            status="resolved",
            failure_codes=(),
            predicate_class="independently_reconciled",
        )
        boundary_ref, boundary_hash = _persist_model(
            store=self._artifact_store,
            value=boundary_receipt,
            kind="epoch.boundary_denominator_receipt",
        )
        facet_receipt = SemanticFacetDenominatorReceipt(
            query=query,
            facet_registry_content_hash=self._facet_registry.registry_content_hash,
            values=facets,
            denominator_hash=result.reconciliation.facet_denominator_hash,
            status="resolved",
            failure_codes=(),
            predicate_class="independently_reconciled",
        )
        facet_ref, facet_hash = _persist_model(
            store=self._artifact_store,
            value=facet_receipt,
            kind="epoch.facet_denominator_receipt",
        )
        stamp = epoch_contract.SemanticEpochStamp(
            epoch_ref=result.manifest.epoch_ref,
            semantic_manifest_ref=manifest_ref,
            semantic_manifest_hash=result.manifest.manifest_content_hash,
            boundary_denominator_receipt_ref=boundary_ref,
            boundary_denominator_receipt_hash=boundary_hash,
            facet_denominator_receipt_ref=facet_ref,
            facet_denominator_receipt_hash=facet_hash,
            requested_query_context_ref=query.requested_query_context_ref,
            authority_purpose=query.authority_purpose,
            valid_effect_coordinate_ref=query.valid_effect_coordinate_ref,
            visibility_knowledge_cutoff_ref=query.visibility_knowledge_cutoff_ref,
            purpose_admission_cutoff_ref=query.purpose_admission_cutoff_ref,
            predicate_provenance_class="independently_reconciled",
        )
        candidate_refs = tuple(
            ref
            for registration in self._boundary_registry.registrations
            for ref in boundary_candidate_refs.get(registration.registration_id, ())
        )
        candidate_bindings = tuple(
            PreparedBoundaryCandidateBinding(
                registration_id=registration.registration_id,
                candidate_refs=boundary_candidate_refs.get(registration.registration_id, ()),
            )
            for registration in self._boundary_registry.registrations
        )
        statement: dict[str, object] = {
            "query": query,
            "stamp": stamp,
            "boundary_candidate_refs": candidate_refs,
            "boundary_candidates_by_registration": candidate_bindings,
            "owner_denominator_receipt_refs": tuple(
                ref for batch in batches for ref in batch.all_owner_evidence_refs
            ),
            "status": "prepared",
        }
        framed = chronology_contract._frame_record(epoch_contract.canonical_epoch_bytes(statement))
        prepared_ref = self._artifact_store.put_bytes(
            framed,
            ArtifactWriteOptions(
                kind="epoch.prepared",
                media_type="application/vnd.polisyos.epoch+json",
                inputs=[InputRef(artifact_id=manifest_ref.artifact_id, role="semantic_manifest")],
            ),
        )
        prepared_readback = epoch_contract.load_verified_epoch_statement(
            store=self._artifact_store,
            ref=prepared_ref,
            expected_kind="epoch.prepared",
        )
        expected_prepared = from_canonical_bytes(epoch_contract.canonical_epoch_bytes(statement))
        if prepared_readback != expected_prepared:
            raise RuntimeError("prepared semantic epoch changed after CAS readback")
        return PreparedSemanticEpoch(
            prepared_epoch_ref=prepared_ref,
            prepared_content_hash=_model_hash(b"polisyos.epoch.prepared.v1\0", statement),
            **statement,
        )

    def acquisition_owner_query(
        self, *, query: EpochResolutionQuery
    ) -> epoch_contract.AcquisitionBoundaryResolutionQuery:
        """Derive the sole registered acquisition owner's native query."""

        registrations = tuple(
            row
            for row in self._boundary_registry.registrations
            if row.owner_kind == "catalog_acquisition"
        )
        if len(registrations) != 1:
            raise ValueError("acquisition epoch registration denominator differs from one")
        native = self._owner_query(kind="catalog_acquisition", query=query)
        if not isinstance(native, epoch_contract.AcquisitionBoundaryResolutionQuery):
            raise TypeError("acquisition epoch query resolved to another owner kind")
        return native

    def prepare_acquisition_candidate(
        self,
        *,
        query: EpochResolutionQuery,
        candidate_ref: ArtifactRef,
    ) -> PreparedSemanticEpoch:
        """Prepare one acquisition candidate through its registry-owned route."""

        registrations = tuple(
            row
            for row in self._boundary_registry.registrations
            if row.owner_kind == "catalog_acquisition"
        )
        if len(registrations) != 1:
            raise ValueError("acquisition epoch registration denominator differs from one")
        return self.prepare_epoch_candidate(
            query=query,
            boundary_candidate_refs={registrations[0].registration_id: (candidate_ref,)},
        )

    def finalize_admitted_epoch(
        self,
        *,
        prepared_epoch_ref: ArtifactRef,
        admitted_boundary_evidence_ref: ArtifactRef,
    ) -> PersistedSemanticEpochProductionReceipt:
        """Re-enumerate owner state and append only the admitted stable candidate."""

        prepared_for_failure: PreparedSemanticEpoch | None = None
        try:

            def load_mapping(ref: ArtifactRef, *, kind: str) -> dict[str, object]:
                report = self._artifact_store.verify(ref.artifact_id)
                payload = self._artifact_store.get_bytes(ref.artifact_id)
                manifest = self._artifact_store.get_manifest(ref.artifact_id)
                records = chronology_contract._split_framed_records(payload)
                if (
                    not report.ok
                    or _raw_cas_hash(payload) != str(ref.artifact_id)
                    or manifest.artifact_id != ref.artifact_id
                    or manifest.kind != kind
                    or manifest.media_type != "application/vnd.polisyos.epoch+json"
                    or ref.kind != kind
                    or ref.media_type != "application/vnd.polisyos.epoch+json"
                    or len(records) != 1
                ):
                    raise ValueError("admitted acquisition artifact readback differs")
                mapping = from_canonical_bytes(records[0])
                if not isinstance(mapping, dict):
                    raise ValueError("admitted acquisition artifact is not a mapping")
                return mapping

            prepared_mapping = load_mapping(prepared_epoch_ref, kind="epoch.prepared")
            prepared = PreparedSemanticEpoch.model_validate(
                {
                    **prepared_mapping,
                    "prepared_epoch_ref": prepared_epoch_ref.model_dump(mode="json"),
                    "prepared_content_hash": _model_hash(
                        b"polisyos.epoch.prepared.v1\0", prepared_mapping
                    ),
                }
            )
            prepared_for_failure = prepared
            admitted = epoch_contract.AdmittedAcquisitionBoundaryEvidence.model_validate(
                load_mapping(
                    admitted_boundary_evidence_ref,
                    kind="epoch.admitted_acquisition_boundary_evidence",
                )
            )
            if (
                admitted.prepared_epoch_ref != prepared_epoch_ref
                or admitted.semantic_epoch_stamp != prepared.stamp
            ):
                raise ValueError("admitted acquisition evidence differs from prepared epoch")

            candidate_mapping = load_mapping(
                admitted.semantic_candidate_ref,
                kind="epoch.acquisition_semantic_boundary_candidate",
            )
            candidate_statement = (
                epoch_contract.AcquisitionSemanticBoundaryCandidateStatement.model_validate(
                    candidate_mapping
                )
            )
            candidate = epoch_contract.AcquisitionSemanticBoundaryCandidate(
                candidate_ref=admitted.semantic_candidate_ref,
                candidate_content_hash=admitted.semantic_candidate_content_hash,
                statement=candidate_statement,
            )
            native_mapping = load_mapping(
                admitted.native_member_ref,
                kind="epoch.acquisition_native_member",
            )
            passport_mapping = load_mapping(
                admitted.passport_ref,
                kind="epoch.acquisition_passport_snapshot",
            )
            pending_mapping = load_mapping(
                admitted.pending_overlay_receipt_ref,
                kind="epoch.pending_overlay_admission_receipt",
            )
            pending = epoch_contract.PendingOverlayAdmissionStatement.model_validate(
                pending_mapping
            )
            native_receipt = epoch_contract.AcquisitionNativeMembershipReceipt.model_validate(
                load_mapping(
                    admitted.native_membership_receipt_ref,
                    kind="epoch.acquisition_native_membership",
                )
            )
            semantic_receipt = (
                epoch_contract.AcquisitionSemanticCandidateDenominatorReceipt.model_validate(
                    load_mapping(
                        admitted.semantic_denominator_receipt_ref,
                        kind="epoch.acquisition_semantic_denominator_receipt",
                    )
                )
            )
            projection_receipt = (
                epoch_contract.AcquisitionSemanticProjectionVerificationReceipt.model_validate(
                    load_mapping(
                        admitted.semantic_projection_verification_receipt_ref,
                        kind=("epoch.acquisition_semantic_projection_verification_receipt"),
                    )
                )
            )
            provenance = epoch_contract.AcquisitionProjectionVerifierProvenance.model_validate(
                load_mapping(
                    admitted.verifier_provenance_ref,
                    kind="epoch.acquisition_projection_verifier_provenance",
                )
            )
            if (
                admitted.semantic_candidate_ref not in prepared.boundary_candidate_refs
                or candidate.statement.requested_query_context_ref
                != native_receipt.query.requested_query_context_ref
                or candidate.statement.scope_identity_ref != native_receipt.query.scope_identity_ref
                or candidate.statement.authority_purpose != native_receipt.query.authority_purpose
                or candidate.statement.valid_effect_coordinate_ref
                != native_receipt.query.valid_effect_coordinate_ref
                or candidate.statement.visibility_knowledge_cutoff_ref
                != native_receipt.query.visibility_knowledge_cutoff_ref
                or candidate.statement.purpose_admission_cutoff_ref
                != native_receipt.query.purpose_admission_cutoff_ref
                or str(passport_mapping.get("passport_id")) != pending.passport_id
                or int(passport_mapping.get("epoch_id", 0)) != admitted.epoch_id
                or passport_mapping.get("semantic_boundary_candidate_ref")
                != admitted.semantic_candidate_ref.model_dump(mode="json")
                or passport_mapping.get("semantic_boundary_candidate_content_hash")
                != admitted.semantic_candidate_content_hash
                or passport_mapping.get("semantic_epoch_stamp")
                != admitted.semantic_epoch_stamp.model_dump(mode="json")
                or passport_mapping.get("prepared_semantic_epoch_ref")
                != prepared_epoch_ref.model_dump(mode="json")
                or int(native_mapping.get("epoch_id", 0)) != admitted.epoch_id
                or native_mapping.get("passport_id") != pending.passport_id
                or native_mapping.get("passport_ref")
                != admitted.passport_ref.model_dump(mode="json")
                or native_mapping.get("passport_content_hash") != admitted.passport_content_hash
                or pending.prepared_semantic_epoch_ref != prepared_epoch_ref
                or pending.boundary_candidate_ref != admitted.semantic_candidate_ref
                or pending.semantic_epoch_stamp != prepared.stamp
                or projection_receipt.status != "verified"
                or projection_receipt.native_membership_receipt_ref
                != admitted.native_membership_receipt_ref
                or projection_receipt.semantic_denominator_receipt_ref
                != admitted.semantic_denominator_receipt_ref
                or projection_receipt.verifier_provenance_ref != admitted.verifier_provenance_ref
                or provenance.owner_kind != "catalog_acquisition"
            ):
                raise ValueError("admitted acquisition recursive binding differs")
            expected_hashes = (
                (
                    _model_hash(
                        b"polisyos.epoch.acquisition-native-member.v1\0",
                        native_mapping,
                    ),
                    admitted.native_member_content_hash,
                ),
                (
                    f"sha256:{hashlib.sha256(chronology_contract._split_framed_records(self._artifact_store.get_bytes(admitted.passport_ref.artifact_id))[0]).hexdigest()}",
                    admitted.passport_content_hash,
                ),
                (
                    f"sha256:{hashlib.sha256(chronology_contract._split_framed_records(self._artifact_store.get_bytes(admitted.pending_overlay_receipt_ref.artifact_id))[0]).hexdigest()}",
                    admitted.pending_overlay_receipt_content_hash,
                ),
                (
                    _model_hash(
                        b"polisyos.epoch.acquisition-native-membership-receipt.v1\0",
                        native_receipt,
                    ),
                    admitted.native_membership_receipt_content_hash,
                ),
                (
                    _model_hash(
                        b"polisyos.epoch.acquisition-semantic-denominator-receipt.v1\0",
                        semantic_receipt,
                    ),
                    admitted.semantic_denominator_receipt_content_hash,
                ),
                (
                    _model_hash(
                        b"polisyos.epoch.acquisition-semantic-projection-verification-receipt.v1\0",
                        projection_receipt,
                    ),
                    admitted.semantic_projection_verification_receipt_content_hash,
                ),
            )
            if any(expected != observed for expected, observed in expected_hashes):
                raise ValueError("admitted acquisition semantic content hash differs")
            batches, facets = self._collect(query=prepared.query)
            catalog_batches = tuple(
                batch for batch in batches if batch.owner_kind == "catalog_acquisition"
            )
            if len(catalog_batches) != 1:
                raise ValueError("catalog acquisition owner batch denominator differs")
            catalog_batch = catalog_batches[0]
            evidence_by_role = {
                row.role: row.artifact_ref for row in catalog_batch.supporting_evidence
            }
            if (
                catalog_batch.denominator_receipt_ref != admitted.semantic_denominator_receipt_ref
                or evidence_by_role.get("native_membership")
                != admitted.native_membership_receipt_ref
                or evidence_by_role.get("semantic_projection_verification")
                != admitted.semantic_projection_verification_receipt_ref
                or semantic_receipt.query != native_receipt.query
                or not any(
                    row.operational_epoch_id == admitted.epoch_id
                    and row.native_member_ref == admitted.native_member_ref
                    and row.passport_ref == admitted.passport_ref
                    and row.semantic_candidate_ref == admitted.semantic_candidate_ref
                    and row.binding_status == "bound"
                    for row in native_receipt.assessments
                )
            ):
                raise ValueError("post-admission owner denominator differs from evidence")
            history = self._history.resolve_scope_history(
                scope=prepared.query.scope_identity,
                authority_purpose=prepared.query.authority_purpose,
            )
            result = resolve_semantic_epoch(
                query=prepared.query,
                boundary_registry=self._boundary_registry,
                owner_batches=batches,
                facet_registry=self._facet_registry,
                facet_values=facets,
                prior_manifests=tuple(
                    SemanticEpochManifest.model_validate(
                        from_canonical_bytes(
                            chronology_contract._split_framed_records(
                                self._artifact_store.get_bytes(row.manifest_ref.artifact_id)
                            )[0]
                        )
                    )
                    for row in history.entries
                ),
            )
            if result.manifest is None or result.manifest.epoch_ref != prepared.stamp.epoch_ref:
                raise ValueError("post-admission semantic denominator changed")
            return self._append_and_qualify(
                query=prepared.query,
                result=result,
                mode="acquisition_finalization",
                prepared_ref=prepared_epoch_ref,
                admitted_ref=admitted_boundary_evidence_ref,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            if prepared_for_failure is not None:
                return self._negative(
                    mode="acquisition_finalization",
                    query=prepared_for_failure.query,
                    status="not_established",
                    codes=("epoch_scope_unresolved",),
                    prepared_ref=prepared_epoch_ref,
                    admitted_ref=admitted_boundary_evidence_ref,
                )
            # The query is deliberately not guessed from ambient state.  A malformed
            # prepared artifact cannot mint a query-bound production receipt.
            raise ValueError("epoch_finalization_evidence_not_established") from None


__all__ = [
    "BoundaryOwnerKind",
    "EpochBoundaryAssessment",
    "EpochBoundaryDenominatorReceipt",
    "EpochBoundaryOwnerAdapter",
    "EpochBoundaryOwnerBatch",
    "EpochBoundarySourceRegistration",
    "EpochBoundarySourceRegistry",
    "EpochBranchAdjudication",
    "EpochChronologyPolicyOwner",
    "EpochHistoryAppendReceipt",
    "EpochHistoryEntry",
    "EpochInputReconciliation",
    "EpochOwnerEvidenceBinding",
    "EpochResolutionQuery",
    "EpochResolutionResult",
    "EpochScopeHistory",
    "EpochScopeIdentity",
    "PersistedSemanticEpochProductionReceipt",
    "PreparedSemanticEpoch",
    "SemanticEpochHistoryRepository",
    "SemanticEpochManifest",
    "SemanticEpochProductionReceipt",
    "SemanticEpochQualificationAdapter",
    "SemanticEpochService",
    "SemanticFacetDenominatorReceipt",
    "SemanticFacetProvider",
    "SemanticFacetRegistration",
    "SemanticFacetRegistry",
    "SemanticFacetValue",
    "build_boundary_registry",
    "build_epoch_resolution_query_from_evidence",
    "build_epoch_scope_identity",
    "build_facet_registry",
    "persist_semantic_epoch_production_receipt",
    "reconcile_epoch_inputs",
    "resolve_semantic_epoch",
]
