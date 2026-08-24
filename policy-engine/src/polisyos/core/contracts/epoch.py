"""Import-safe contracts for semantic epochs and native boundary owners.

The models in this module carry owner evidence across package boundaries.  They
do not decide owner membership, currentness, acceptance, or custody.  Those
predicates remain with L5, Lex, Catalog Acquisition, and their appointed
consumers respectively.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Annotated, Any, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import ArtifactID, ArtifactRef
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes

Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$", strict=True)]

_CANON = CanonSpec(
    name="polisyos.canon.json",
    version="0.2.0",
    forbid_floats=True,
    forbid_nan_inf=True,
    exclude_none=False,
    max_depth=128,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
)
_COORDINATE_PREFIX = b"polisyos.native-coordinate.v1\0"
_QUERY_CONTEXT_PREFIX = b"polisyos.epoch.query-context.v1\0"
_ACQUISITION_CANDIDATE_PREFIX = b"polisyos.epoch.acquisition-semantic-boundary-candidate.v1\0"


class _EpochModel(BaseModel):
    """Strict immutable base for cross-owner epoch DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class _EpochArtifactStore(Protocol):
    """Minimal CAS surface used to re-establish an epoch statement from bytes."""

    def get_bytes(self, artifact_id: ArtifactID) -> bytes: ...

    def get_manifest(self, artifact_id: ArtifactID) -> object: ...

    def verify(self, artifact_id: ArtifactID) -> object: ...


def _frame(value: bytes) -> bytes:
    if len(value) >= 1 << 64:
        raise ValueError("epoch frame length exceeds uint64")
    return len(value).to_bytes(8, "big") + value


def _sha256(*chunks: bytes) -> Digest:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _raw(value: Any) -> Any:
    if isinstance(value, ArtifactID):
        return str(value)
    if isinstance(value, BaseModel):
        return {
            field.alias or name: _raw(getattr(value, name))
            for name, field in value.__class__.model_fields.items()
        }
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, tuple | list):
        return [_raw(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _raw(item) for key, item in value.items()}
    return value


def canonical_epoch_bytes(value: BaseModel | dict[str, Any]) -> bytes:
    """Return canonical JSON bytes for an explicitly typed epoch value."""

    mapping = _raw(value)
    if not isinstance(mapping, dict):
        raise TypeError("epoch canonicalization requires a mapping")
    return to_canonical_bytes(mapping, _CANON)


def epoch_semantic_content_hash(*, domain: str, value: BaseModel | dict[str, Any]) -> Digest:
    """Return one domain-separated semantic hash over canonical epoch bytes."""

    return _sha256(domain.encode(), b"\0", canonical_epoch_bytes(value))


def load_verified_epoch_statement(
    *,
    store: _EpochArtifactStore,
    ref: ArtifactRef,
    expected_kind: str,
    expected_media_type: str = "application/vnd.polisyos.epoch+json",
) -> dict[str, Any]:
    """Reload one exact framed epoch statement through its CAS manifest.

    The supplied reference is only a selector.  The returned mapping is admitted
    from independently re-read bytes after CAS, manifest-profile, frame-count and
    content-address checks all agree.
    """

    if ref.kind != expected_kind or ref.media_type != expected_media_type:
        raise ValueError("epoch statement reference profile differs")
    report = store.verify(ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    payload = store.get_bytes(ref.artifact_id)
    if (
        not bool(getattr(report, "ok", False))
        or getattr(manifest, "artifact_id", None) != ref.artifact_id
        or getattr(manifest, "kind", None) != expected_kind
        or getattr(manifest, "media_type", None) != expected_media_type
        or str(ref.artifact_id) != _sha256(payload)
        or len(payload) < 8
    ):
        raise ValueError("epoch statement CAS readback differs")
    size = int.from_bytes(payload[:8], "big")
    if size != len(payload) - 8:
        raise ValueError("epoch statement frame denominator differs from one")
    decoded = from_canonical_bytes(payload[8:])
    if not isinstance(decoded, dict):
        raise ValueError("epoch statement payload is not a mapping")
    return {str(key): value for key, value in decoded.items()}


def native_coordinate_ref(
    *, family: str, role: str, schema_profile: str, coordinate_bytes: bytes
) -> Digest:
    """Content-bind one sparse family-native temporal coordinate."""

    return _sha256(
        _COORDINATE_PREFIX,
        _frame(family.encode()),
        _frame(role.encode()),
        _frame(schema_profile.encode()),
        _frame(coordinate_bytes),
    )


def epoch_query_context_ref(
    *,
    family: str,
    scope_bytes: bytes,
    authority_purpose: str,
    coordinate_refs: tuple[Digest, ...],
) -> Digest:
    """Bind the ordered applicable role refs, native scope, and purpose."""

    chunks = [
        _QUERY_CONTEXT_PREFIX,
        _frame(family.encode()),
        _frame(scope_bytes),
        _frame(authority_purpose.encode()),
    ]
    chunks.extend(_frame(ref.encode()) for ref in coordinate_refs)
    return _sha256(*chunks)


class SemanticEpochStamp(_EpochModel):
    """Stable semantic selector carried by an admitted native record."""

    epoch_ref: Digest
    semantic_manifest_ref: ArtifactRef
    semantic_manifest_hash: Digest
    boundary_denominator_receipt_ref: ArtifactRef
    boundary_denominator_receipt_hash: Digest
    facet_denominator_receipt_ref: ArtifactRef
    facet_denominator_receipt_hash: Digest
    requested_query_context_ref: Digest
    authority_purpose: str = Field(min_length=1)
    valid_effect_coordinate_ref: Digest
    visibility_knowledge_cutoff_ref: Digest
    purpose_admission_cutoff_ref: Digest
    predicate_provenance_class: Literal["independently_reconciled"]


def semantic_epoch_stamp_content_hash(stamp: SemanticEpochStamp) -> Digest:
    """Return the one canonical content hash used by every stamp carrier."""

    return _sha256(canonical_epoch_bytes(stamp))


class AcquisitionSemanticBoundaryCandidateStatement(_EpochModel):
    """Canonical semantic projection of one acquisition source record."""

    source_record_ref: ArtifactRef
    source_record_content_hash: Digest
    scope_identity_ref: Digest
    authority_purpose: str = Field(min_length=1)
    valid_effect_coordinate_ref: Digest
    visibility_knowledge_cutoff_ref: Digest
    purpose_admission_cutoff_ref: Digest
    requested_query_context_ref: Digest


def acquisition_semantic_candidate_bytes(
    statement: AcquisitionSemanticBoundaryCandidateStatement,
) -> bytes:
    """Return the one framed canonical preimage for a candidate statement."""

    return _frame(canonical_epoch_bytes(statement))


def acquisition_semantic_candidate_content_hash(
    statement: AcquisitionSemanticBoundaryCandidateStatement,
) -> Digest:
    """Return the semantic digest for a candidate statement."""

    return _sha256(_ACQUISITION_CANDIDATE_PREFIX, acquisition_semantic_candidate_bytes(statement))


class AcquisitionSemanticBoundaryCandidate(_EpochModel):
    """Persisted candidate whose identity excludes the wrapper and future stamp."""

    candidate_ref: ArtifactRef
    candidate_content_hash: Digest
    statement: AcquisitionSemanticBoundaryCandidateStatement

    @model_validator(mode="after")
    def _bind_statement_bytes(self) -> Self:
        raw = acquisition_semantic_candidate_bytes(self.statement)
        if str(self.candidate_ref.artifact_id) != _sha256(raw):
            raise ValueError("semantic candidate CAS ref differs from canonical statement bytes")
        if self.candidate_content_hash != acquisition_semantic_candidate_content_hash(
            self.statement
        ):
            raise ValueError("semantic candidate content hash differs from statement")
        return self


class L5SchemaRegimeResolutionQuery(_EpochModel):
    scope_identity_ref: Digest
    authority_purpose: str = Field(min_length=1)
    valid_effect_value: date
    valid_effect_coordinate_schema_profile: str = Field(min_length=1)
    valid_effect_coordinate_ref: Digest
    visibility_knowledge_cutoff_schema_profile: str = Field(min_length=1)
    visibility_knowledge_cutoff_bytes: bytes
    visibility_knowledge_cutoff_ref: Digest
    purpose_admission_cutoff_schema_profile: str = Field(min_length=1)
    purpose_admission_cutoff_bytes: bytes
    purpose_admission_cutoff_ref: Digest
    requested_query_context_ref: Digest

    @model_validator(mode="after")
    def _coordinates_are_content_bound(self) -> Self:
        expected = (
            native_coordinate_ref(
                family="l5_schema_regime",
                role="valid_effect",
                schema_profile=self.valid_effect_coordinate_schema_profile,
                coordinate_bytes=self.valid_effect_value.isoformat().encode(),
            ),
            native_coordinate_ref(
                family="l5_schema_regime",
                role="visibility_knowledge_cutoff",
                schema_profile=self.visibility_knowledge_cutoff_schema_profile,
                coordinate_bytes=self.visibility_knowledge_cutoff_bytes,
            ),
            native_coordinate_ref(
                family="l5_schema_regime",
                role="purpose_admission_cutoff",
                schema_profile=self.purpose_admission_cutoff_schema_profile,
                coordinate_bytes=self.purpose_admission_cutoff_bytes,
            ),
        )
        if expected != (
            self.valid_effect_coordinate_ref,
            self.visibility_knowledge_cutoff_ref,
            self.purpose_admission_cutoff_ref,
        ):
            raise ValueError("l5 native coordinate bytes/ref mismatch")
        return self


class L5SchemaRegimeScopeRelation(_EpochModel):
    schema_regime_id: str = Field(min_length=1)
    scope_identity_refs: tuple[Digest, ...]
    relation_provenance_ref: ArtifactRef
    visibility_knowledge_from: datetime
    purpose_admission_from: datetime

    @model_validator(mode="after")
    def _history_is_usable(self) -> Self:
        if (
            self.visibility_knowledge_from.tzinfo is None
            or self.purpose_admission_from.tzinfo is None
        ):
            raise ValueError("schema-regime relation history must be timezone-aware")
        return self


class L5SchemaRegimeAssessment(_EpochModel):
    schema_regime_id: str = Field(min_length=1)
    regime_source_ref: ArtifactRef
    regime_content_hash: Digest
    scope_relation: L5SchemaRegimeScopeRelation | None
    disposition: Literal["applicable", "not_applicable", "unresolved"]
    failure_code: Literal["schema_regime_scope_missing", "schema_regime_scope_ambiguous"] | None

    @model_validator(mode="after")
    def _failure_matches_disposition(self) -> Self:
        if (self.disposition == "unresolved") != (self.failure_code is not None):
            raise ValueError("schema-regime failure must match unresolved disposition")
        if self.disposition != "unresolved" and self.scope_relation is None:
            raise ValueError("resolved schema regime lacks an owner scope relation")
        return self


class L5SchemaRegimeDenominatorReceipt(_EpochModel):
    query: L5SchemaRegimeResolutionQuery
    owner_source_snapshot_ref: ArtifactRef
    owner_source_snapshot_content_hash: Digest
    regime_registry_ref: ArtifactRef
    regime_registry_content_hash: Digest
    scope_registry_ref: ArtifactRef
    scope_registry_content_hash: Digest
    declared_regime_count: int = Field(ge=0)
    assessments: tuple[L5SchemaRegimeAssessment, ...]
    denominator_hash: Digest
    status: Literal["resolved", "unresolved"]
    failure_codes: tuple[str, ...]
    predicate_class: Literal["independently_reconciled"]

    @model_validator(mode="after")
    def _complete_denominator(self) -> Self:
        if self.declared_regime_count != len(self.assessments):
            raise ValueError("l5 declared regime count differs from assessments")
        failures = tuple(sorted({row.failure_code for row in self.assessments if row.failure_code}))
        if self.failure_codes != failures or self.status != (
            "unresolved" if failures else "resolved"
        ):
            raise ValueError("l5 denominator status/failures are not recomputed")
        return self


class ScopedSchemaRegimeProjection(_EpochModel):
    scope_identity_ref: Digest
    valid_effect_coordinate_ref: Digest
    requested_query_context_ref: Digest
    owner_source_snapshot_ref: ArtifactRef
    denominator_receipt_ref: ArtifactRef
    applicable_regime_ids: tuple[str, ...]
    applicable_regime_content_hashes: tuple[Digest, ...]
    changepoint_refs: tuple[Digest, ...]
    status: Literal["resolved", "unresolved", "contested"]
    projection_content_hash: Digest

    @model_validator(mode="after")
    def _parallel_regime_vectors(self) -> Self:
        if len(self.applicable_regime_ids) != len(self.applicable_regime_content_hashes):
            raise ValueError("regime projection IDs and hashes differ in length")
        mapping = {
            name: getattr(self, name)
            for name in self.__class__.model_fields
            if name != "projection_content_hash"
        }
        expected = _sha256(canonical_epoch_bytes(mapping))
        if self.projection_content_hash != expected:
            raise ValueError("scoped regime projection hash differs from its content")
        return self


class LegalAmendmentWindowResolutionQuery(_EpochModel):
    jurisdiction: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    authority_purpose: str = Field(min_length=1)
    valid_effect_value: date
    valid_effect_coordinate_schema_profile: str = Field(min_length=1)
    valid_effect_coordinate_ref: Digest
    visibility_knowledge_cutoff_schema_profile: str = Field(min_length=1)
    visibility_knowledge_cutoff_bytes: bytes
    visibility_knowledge_cutoff_ref: Digest
    purpose_admission_cutoff_schema_profile: str = Field(min_length=1)
    purpose_admission_cutoff_bytes: bytes
    purpose_admission_cutoff_ref: Digest
    requested_query_context_ref: Digest

    @model_validator(mode="after")
    def _coordinates_are_content_bound(self) -> Self:
        values = (
            (
                "valid_effect",
                self.valid_effect_coordinate_schema_profile,
                self.valid_effect_value.isoformat().encode(),
                self.valid_effect_coordinate_ref,
            ),
            (
                "visibility_knowledge_cutoff",
                self.visibility_knowledge_cutoff_schema_profile,
                self.visibility_knowledge_cutoff_bytes,
                self.visibility_knowledge_cutoff_ref,
            ),
            (
                "purpose_admission_cutoff",
                self.purpose_admission_cutoff_schema_profile,
                self.purpose_admission_cutoff_bytes,
                self.purpose_admission_cutoff_ref,
            ),
        )
        for role, profile, raw, observed in values:
            if (
                native_coordinate_ref(
                    family="lex_amendment_window",
                    role=role,
                    schema_profile=profile,
                    coordinate_bytes=raw,
                )
                != observed
            ):
                raise ValueError("lex native coordinate bytes/ref mismatch")
        return self


class LegalAmendmentWindowAssessment(_EpochModel):
    amendment_ref: ArtifactRef
    amendment_content_hash: Digest
    amended_doc_ref: ArtifactRef
    resolved_scope_ref: Digest | None
    effective_from: date | None
    effective_to: date | None
    disposition: Literal["applicable", "not_applicable", "unresolved"]
    failure_code: (
        Literal[
            "amendment_scope_unresolved",
            "amendment_scope_ambiguous",
            "amendment_knowledge_cutoff_unresolved",
            "amendment_valid_effect_window_unresolved",
        ]
        | None
    )

    @model_validator(mode="after")
    def _valid_window(self) -> Self:
        if self.effective_from is None and (
            self.failure_code != "amendment_valid_effect_window_unresolved"
        ):
            raise ValueError("missing legal amendment window must fail closed")
        if self.effective_to is not None and (
            self.effective_from is None or self.effective_to < self.effective_from
        ):
            raise ValueError("legal amendment window is inverted")
        if (self.disposition == "unresolved") != (self.failure_code is not None):
            raise ValueError("legal amendment failure must match unresolved disposition")
        if self.disposition != "unresolved" and self.resolved_scope_ref is None:
            raise ValueError("resolved amendment lacks an owner scope identity")
        return self


class LegalAmendmentWindowDenominatorReceipt(_EpochModel):
    query: LegalAmendmentWindowResolutionQuery
    owner_source_snapshot_ref: ArtifactRef
    owner_source_snapshot_content_hash: Digest
    declared_amendment_count: int = Field(ge=0)
    assessments: tuple[LegalAmendmentWindowAssessment, ...]
    denominator_hash: Digest
    status: Literal["resolved", "unresolved"]
    failure_codes: tuple[str, ...]
    owner_failure_code: Literal["amendment_owner_table_not_established"] | None = None
    predicate_class: Literal["independently_reconciled"]

    @model_validator(mode="after")
    def _complete_denominator(self) -> Self:
        if self.declared_amendment_count != len(self.assessments):
            raise ValueError("legal declared amendment count differs from assessments")
        failures = tuple(
            sorted(
                {
                    *(row.failure_code for row in self.assessments if row.failure_code),
                    *((self.owner_failure_code,) if self.owner_failure_code else ()),
                }
            )
        )
        if self.owner_failure_code is not None and self.assessments:
            raise ValueError("missing legal owner table cannot carry invented assessments")
        if self.failure_codes != failures or self.status != (
            "unresolved" if failures else "resolved"
        ):
            raise ValueError("legal denominator status/failures are not recomputed")
        return self


class AcquisitionBoundaryResolutionQuery(_EpochModel):
    scope_identity_ref: Digest
    authority_purpose: str = Field(min_length=1)
    valid_effect_coordinate_schema_profile: str = Field(min_length=1)
    valid_effect_coordinate_bytes: bytes
    valid_effect_coordinate_ref: Digest
    visibility_knowledge_cutoff_schema_profile: str = Field(min_length=1)
    visibility_knowledge_cutoff_bytes: bytes
    visibility_knowledge_cutoff_ref: Digest
    purpose_admission_cutoff_schema_profile: str = Field(min_length=1)
    purpose_admission_cutoff_bytes: bytes
    purpose_admission_cutoff_ref: Digest
    requested_query_context_ref: Digest

    @model_validator(mode="after")
    def _coordinates_are_content_bound(self) -> Self:
        values = (
            (
                "valid_effect",
                self.valid_effect_coordinate_schema_profile,
                self.valid_effect_coordinate_bytes,
                self.valid_effect_coordinate_ref,
            ),
            (
                "visibility_knowledge_cutoff",
                self.visibility_knowledge_cutoff_schema_profile,
                self.visibility_knowledge_cutoff_bytes,
                self.visibility_knowledge_cutoff_ref,
            ),
            (
                "purpose_admission_cutoff",
                self.purpose_admission_cutoff_schema_profile,
                self.purpose_admission_cutoff_bytes,
                self.purpose_admission_cutoff_ref,
            ),
        )
        for role, profile, raw, observed in values:
            if (
                native_coordinate_ref(
                    family="catalog_acquisition",
                    role=role,
                    schema_profile=profile,
                    coordinate_bytes=raw,
                )
                != observed
            ):
                raise ValueError("acquisition native coordinate bytes/ref mismatch")
        return self


class AcquisitionNativeMemberAssessment(_EpochModel):
    native_member_ref: ArtifactRef
    native_member_content_hash: Digest
    operational_epoch_id: int = Field(gt=0)
    passport_ref: ArtifactRef | None
    passport_content_hash: Digest | None
    semantic_candidate_ref: ArtifactRef | None
    semantic_candidate_content_hash: Digest | None
    binding_status: Literal["bound", "legacy_unresolved", "invalid"]
    query_disposition: Literal["applicable", "not_applicable", "unresolved"]
    failure_code: (
        Literal[
            "legacy_acquisition_candidate_identity_not_established",
            "acquisition_candidate_binding_mismatch",
            "acquisition_query_context_mismatch",
        ]
        | None
    )

    @model_validator(mode="after")
    def _binding_tuple_is_complete(self) -> Self:
        fields = (
            self.passport_ref,
            self.passport_content_hash,
            self.semantic_candidate_ref,
            self.semantic_candidate_content_hash,
        )
        if self.binding_status == "bound" and any(value is None for value in fields):
            raise ValueError("bound acquisition member lacks candidate/passport identity")
        if self.binding_status == "legacy_unresolved" and any(
            value is not None for value in fields[2:]
        ):
            raise ValueError("legacy acquisition member cannot synthesize candidate identity")
        if (self.query_disposition == "unresolved") != (self.failure_code is not None):
            raise ValueError("acquisition member failure must match unresolved disposition")
        if self.binding_status != "bound" and self.query_disposition != "unresolved":
            raise ValueError("unbound acquisition member cannot be query-applicable")
        if self.binding_status == "legacy_unresolved" and self.failure_code != (
            "legacy_acquisition_candidate_identity_not_established"
        ):
            raise ValueError("legacy acquisition member requires its exact failure code")
        if self.binding_status == "invalid" and self.failure_code != (
            "acquisition_candidate_binding_mismatch"
        ):
            raise ValueError("invalid acquisition binding requires its exact failure code")
        return self


class AcquisitionNativeMembershipReceipt(_EpochModel):
    query: AcquisitionBoundaryResolutionQuery
    owner_source_snapshot_ref: ArtifactRef
    owner_source_snapshot_content_hash: Digest
    declared_native_member_count: int = Field(ge=0)
    assessments: tuple[AcquisitionNativeMemberAssessment, ...]
    native_membership_hash: Digest
    status: Literal["resolved", "unresolved"]
    failure_codes: tuple[str, ...]
    predicate_class: Literal["independently_reconciled"]

    @model_validator(mode="after")
    def _complete_denominator(self) -> Self:
        if self.declared_native_member_count != len(self.assessments):
            raise ValueError("native acquisition member count differs from assessments")
        failures = tuple(sorted({row.failure_code for row in self.assessments if row.failure_code}))
        if self.failure_codes != failures or self.status != (
            "unresolved" if failures else "resolved"
        ):
            raise ValueError("native acquisition denominator is not recomputed")
        expected_hash = epoch_semantic_content_hash(
            domain="polisyos.epoch.acquisition-native-membership.v1",
            value={
                "query": self.query.model_dump(mode="json"),
                "owner_source_snapshot_content_hash": (self.owner_source_snapshot_content_hash),
                "assessments": [row.model_dump(mode="json") for row in self.assessments],
            },
        )
        if self.native_membership_hash != expected_hash:
            raise ValueError("native acquisition membership hash is not recomputed")
        return self


class AcquisitionSemanticCandidateAssessment(_EpochModel):
    semantic_candidate_ref: ArtifactRef
    semantic_candidate_content_hash: Digest
    disposition: Literal["applicable", "not_applicable", "unresolved"]
    failure_code: (
        Literal[
            "acquisition_member_unresolved",
            "acquisition_visibility_unresolved",
            "acquisition_query_context_mismatch",
        ]
        | None
    )

    @model_validator(mode="after")
    def _failure_matches_disposition(self) -> Self:
        if (self.disposition == "unresolved") != (self.failure_code is not None):
            raise ValueError("semantic candidate failure must match unresolved disposition")
        return self


class AcquisitionSemanticCandidateDenominatorReceipt(_EpochModel):
    query: AcquisitionBoundaryResolutionQuery
    semantic_candidate_set_hash: Digest
    declared_unique_candidate_count: int = Field(ge=0)
    assessments: tuple[AcquisitionSemanticCandidateAssessment, ...]
    denominator_hash: Digest
    status: Literal["resolved", "unresolved"]
    failure_codes: tuple[str, ...]
    predicate_class: Literal["independently_reconciled"]

    @model_validator(mode="after")
    def _unique_complete_denominator(self) -> Self:
        identities = tuple(
            (str(row.semantic_candidate_ref.artifact_id), row.semantic_candidate_content_hash)
            for row in self.assessments
        )
        if len(set(identities)) != len(identities):
            raise ValueError("semantic acquisition denominator contains duplicates")
        if self.declared_unique_candidate_count != len(self.assessments):
            raise ValueError("semantic candidate count differs from assessments")
        row_failures = {row.failure_code for row in self.assessments if row.failure_code}
        failures = set(self.failure_codes)
        if not row_failures.issubset(failures) or failures - row_failures - {
            "acquisition_member_unresolved"
        }:
            raise ValueError("semantic denominator carries an unowned failure code")
        if self.failure_codes != tuple(sorted(failures)) or self.status != (
            "unresolved" if failures else "resolved"
        ):
            raise ValueError("semantic acquisition denominator is not recomputed")
        expected_set_hash = epoch_semantic_content_hash(
            domain="polisyos.epoch.acquisition-semantic-candidate-set.v1",
            value={
                "candidates": [
                    {
                        "semantic_candidate_ref": row.semantic_candidate_ref.model_dump(
                            mode="json"
                        ),
                        "semantic_candidate_content_hash": (row.semantic_candidate_content_hash),
                    }
                    for row in self.assessments
                ]
            },
        )
        if self.semantic_candidate_set_hash != expected_set_hash:
            raise ValueError("semantic candidate-set hash is not recomputed")
        expected_denominator_hash = epoch_semantic_content_hash(
            domain="polisyos.epoch.acquisition-semantic-denominator.v1",
            value={
                "query": self.query.model_dump(mode="json"),
                "semantic_candidate_set_hash": self.semantic_candidate_set_hash,
                "assessments": [row.model_dump(mode="json") for row in self.assessments],
            },
        )
        if self.denominator_hash != expected_denominator_hash:
            raise ValueError("semantic candidate denominator hash is not recomputed")
        return self


class AcquisitionProjectionVerifierProvenance(_EpochModel):
    """Owner-held identity of the complete native-to-semantic projection verifier."""

    schema_version: Literal["polisyos.data_forge.acquisition_projection_verifier.v1"] = (
        "polisyos.data_forge.acquisition_projection_verifier.v1"
    )
    owner_kind: Literal["catalog_acquisition"] = "catalog_acquisition"
    algorithm_profile: Literal["complete_native_membership_to_unique_semantic_candidates_v1"] = (
        "complete_native_membership_to_unique_semantic_candidates_v1"
    )


class AcquisitionSemanticProjectionVerificationReceipt(_EpochModel):
    native_membership_receipt_ref: ArtifactRef
    native_membership_receipt_content_hash: Digest
    semantic_denominator_receipt_ref: ArtifactRef
    semantic_denominator_receipt_content_hash: Digest
    prospective_candidate_ref: ArtifactRef | None
    prospective_candidate_content_hash: Digest | None
    verifier_provenance_ref: ArtifactRef
    verifier_provenance_content_hash: Digest
    status: Literal["verified", "not_established"]

    @model_validator(mode="after")
    def _prospective_identity_is_atomic(self) -> Self:
        if (self.prospective_candidate_ref is None) != (
            self.prospective_candidate_content_hash is None
        ):
            raise ValueError("prospective candidate ref/hash must be both present or absent")
        if (
            self.verifier_provenance_ref.kind != "epoch.acquisition_projection_verifier_provenance"
            or self.verifier_provenance_ref.media_type != "application/vnd.polisyos.epoch+json"
        ):
            raise ValueError("acquisition projection verifier provenance profile differs")
        return self


class AdmittedAcquisitionBoundaryEvidence(_EpochModel):
    semantic_candidate_ref: ArtifactRef
    semantic_candidate_content_hash: Digest
    epoch_id: int = Field(gt=0)
    native_member_ref: ArtifactRef
    native_member_content_hash: Digest
    prepared_epoch_ref: ArtifactRef
    prepared_epoch_content_hash: Digest
    passport_ref: ArtifactRef
    passport_content_hash: Digest
    pending_overlay_receipt_ref: ArtifactRef
    pending_overlay_receipt_content_hash: Digest
    native_membership_receipt_ref: ArtifactRef
    native_membership_receipt_content_hash: Digest
    semantic_denominator_receipt_ref: ArtifactRef
    semantic_denominator_receipt_content_hash: Digest
    semantic_projection_verification_receipt_ref: ArtifactRef
    semantic_projection_verification_receipt_content_hash: Digest
    semantic_epoch_stamp: SemanticEpochStamp
    verifier_provenance_ref: ArtifactRef
    predicate_class: Literal["independently_reconciled"]

    @model_validator(mode="after")
    def _known_artifact_profiles_are_exact(self) -> Self:
        expected = {
            "semantic_candidate_ref": (
                "epoch.acquisition_semantic_boundary_candidate",
                "application/vnd.polisyos.epoch+json",
            ),
            "native_member_ref": (
                "epoch.acquisition_native_member",
                "application/vnd.polisyos.epoch+json",
            ),
            "prepared_epoch_ref": (
                "epoch.prepared",
                "application/vnd.polisyos.epoch+json",
            ),
            "passport_ref": (
                "epoch.acquisition_passport_snapshot",
                "application/vnd.polisyos.epoch+json",
            ),
            "pending_overlay_receipt_ref": (
                "epoch.pending_overlay_admission_receipt",
                "application/vnd.polisyos.epoch+json",
            ),
            "native_membership_receipt_ref": (
                "epoch.acquisition_native_membership",
                "application/vnd.polisyos.epoch+json",
            ),
            "semantic_denominator_receipt_ref": (
                "epoch.acquisition_semantic_denominator_receipt",
                "application/vnd.polisyos.epoch+json",
            ),
            "semantic_projection_verification_receipt_ref": (
                "epoch.acquisition_semantic_projection_verification_receipt",
                "application/vnd.polisyos.epoch+json",
            ),
        }
        for field, profile in expected.items():
            ref = getattr(self, field)
            if (ref.kind, ref.media_type) != profile:
                raise ValueError(f"{field} has an unexpected artifact profile")
        return self


class OverlayNativeMemberKey(_EpochModel):
    """One owner-derived native key included in a hidden acquisition admission."""

    table_name: str = Field(min_length=1)
    canonical_primary_key_hash: Digest


class PendingOverlayAdmissionStatement(_EpochModel):
    """Immutable hidden-admission statement; retry metadata is intentionally absent."""

    schema_version: Literal["polisyos.data_forge.acquisition_overlay.v2"] = (
        "polisyos.data_forge.acquisition_overlay.v2"
    )
    epoch_id: int = Field(gt=0)
    passport_id: str = Field(min_length=1)
    admission_content_sha256: Digest
    admitted_observation_count: int = Field(gt=0)
    observation_class: Literal["observed", "proxy"]
    effective_authority_score: float = Field(ge=0.0, le=1.0)
    baseline_before_sha256: Digest
    baseline_after_sha256: Digest
    semantic_epoch_stamp: SemanticEpochStamp
    prepared_semantic_epoch_ref: ArtifactRef
    boundary_candidate_ref: ArtifactRef
    native_member_keys: tuple[OverlayNativeMemberKey, ...]
    native_member_denominator_hash: Digest
    native_member_count: int = Field(gt=0)
    activation_state: Literal["pending_epoch_activation"]

    @model_validator(mode="after")
    def _member_denominator_is_recomputed(self) -> Self:
        ordered = tuple(
            sorted(
                self.native_member_keys,
                key=lambda row: (row.table_name, row.canonical_primary_key_hash),
            )
        )
        if self.native_member_keys != ordered or len(set(ordered)) != len(ordered):
            raise ValueError("overlay native-member keys must be unique and ordered")
        expected_hash = _sha256(
            canonical_epoch_bytes(
                {
                    "epoch_id": self.epoch_id,
                    "passport_id": self.passport_id,
                    "members": [
                        (row.table_name, row.canonical_primary_key_hash) for row in ordered
                    ],
                }
            )
        )
        if self.native_member_count != len(ordered):
            raise ValueError("overlay native-member count is not recomputed")
        if self.native_member_denominator_hash != expected_hash:
            raise ValueError("overlay native-member denominator hash is not recomputed")
        return self


class ActivatedOverlayAdmissionStatement(_EpochModel):
    """Immutable owner statement proving one pending row became read-visible."""

    schema_version: Literal["polisyos.data_forge.acquisition_overlay.v2"] = (
        "polisyos.data_forge.acquisition_overlay.v2"
    )
    epoch_id: int = Field(gt=0)
    passport_id: str = Field(min_length=1)
    admission_content_sha256: Digest
    admitted_observation_count: int = Field(gt=0)
    observation_class: Literal["observed", "proxy"]
    effective_authority_score: float = Field(ge=0.0, le=1.0)
    baseline_before_sha256: Digest
    baseline_after_sha256: Digest
    semantic_epoch_stamp: SemanticEpochStamp
    prepared_semantic_epoch_ref: ArtifactRef
    pending_overlay_receipt_ref: ArtifactRef
    admitted_boundary_evidence_ref: ArtifactRef
    semantic_epoch_production_receipt_ref: ArtifactRef
    activation_state: Literal["active"]


class SemanticEpochProductionReceiptStatement(_EpochModel):
    """Exact import-safe statement returned by the semantic-epoch producer.

    The persistence identity is deliberately carried by an outer wrapper so
    these bytes never contain a reference to themselves.  Data Forge may
    validate this statement without importing the runtime producer.
    """

    production_mode: Literal["ordinary", "acquisition_finalization"]
    status: Literal["appended", "no_change", "not_established", "contested"]
    prepared_epoch_ref: ArtifactRef | None
    admitted_boundary_evidence_ref: ArtifactRef | None
    epoch_ref: Digest | None
    semantic_manifest_ref: ArtifactRef | None
    owner_denominator_receipt_refs: tuple[ArtifactRef, ...]
    history_append_receipt_ref: ArtifactRef | None
    chronology_bundle_ref: ArtifactRef | None
    chronology_verification_ref: ArtifactRef | None
    requested_query_context_ref: Digest
    failure_codes: tuple[str, ...]

    @model_validator(mode="after")
    def _receipt_shape(self) -> Self:
        positive = self.status in {"appended", "no_change"}
        positive_fields = (
            self.epoch_ref,
            self.semantic_manifest_ref,
            self.history_append_receipt_ref,
            self.chronology_bundle_ref,
            self.chronology_verification_ref,
        )
        if positive and any(value is None for value in positive_fields):
            raise ValueError("positive epoch receipt lacks persisted proof fields")
        if not positive and any(value is not None for value in positive_fields):
            raise ValueError("negative epoch receipt carries positive proof fields")
        if positive == bool(self.failure_codes):
            raise ValueError("epoch production failures are required exactly when negative")
        if self.production_mode == "ordinary" and (
            self.prepared_epoch_ref is not None or self.admitted_boundary_evidence_ref is not None
        ):
            raise ValueError("ordinary epoch production cannot carry acquisition handshake refs")
        if self.production_mode == "acquisition_finalization" and (
            self.prepared_epoch_ref is None or self.admitted_boundary_evidence_ref is None
        ):
            raise ValueError("acquisition finalization requires both handshake refs")
        return self


__all__ = [
    "AcquisitionBoundaryResolutionQuery",
    "AcquisitionNativeMemberAssessment",
    "AcquisitionNativeMembershipReceipt",
    "AcquisitionProjectionVerifierProvenance",
    "AcquisitionSemanticBoundaryCandidate",
    "AcquisitionSemanticBoundaryCandidateStatement",
    "AcquisitionSemanticCandidateAssessment",
    "AcquisitionSemanticCandidateDenominatorReceipt",
    "AcquisitionSemanticProjectionVerificationReceipt",
    "ActivatedOverlayAdmissionStatement",
    "AdmittedAcquisitionBoundaryEvidence",
    "Digest",
    "L5SchemaRegimeAssessment",
    "L5SchemaRegimeDenominatorReceipt",
    "L5SchemaRegimeResolutionQuery",
    "L5SchemaRegimeScopeRelation",
    "LegalAmendmentWindowAssessment",
    "LegalAmendmentWindowDenominatorReceipt",
    "LegalAmendmentWindowResolutionQuery",
    "OverlayNativeMemberKey",
    "PendingOverlayAdmissionStatement",
    "ScopedSchemaRegimeProjection",
    "SemanticEpochProductionReceiptStatement",
    "SemanticEpochStamp",
    "acquisition_semantic_candidate_bytes",
    "acquisition_semantic_candidate_content_hash",
    "canonical_epoch_bytes",
    "epoch_query_context_ref",
    "epoch_semantic_content_hash",
    "load_verified_epoch_statement",
    "native_coordinate_ref",
]
