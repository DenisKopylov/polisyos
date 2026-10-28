"""Import-safe contracts for semantic epochs and native boundary owners.

The models in this module carry owner evidence across package boundaries.  They
do not decide owner membership, currentness, acceptance, or custody.  Those
predicates remain with L5, Lex, Catalog Acquisition, and their appointed
consumers respectively.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import TYPE_CHECKING, Annotated, Any, Literal, NamedTuple, Protocol, Self

if TYPE_CHECKING:
    from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactManifest,
    ArtifactRef,
    CanonInfo,
    InputRef,
    RawManifestBytesReader,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.canon import CanonSpec, to_canonical_bytes

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
_EPOCH_OWNER_STATEMENT_MEDIA_TYPES: dict[str, str] = {
    "epoch.semantic_manifest": "application/vnd.polisyos.epoch+json",
    "epoch.production_receipt": "application/vnd.polisyos.epoch-production-receipt+json",
}
_EXTERNAL_STATEMENT_CANON = CanonSpec(forbid_floats=False, exclude_none=False)
_EXTERNAL_ACQUISITION_STATEMENT_KINDS = frozenset(
    {
        "epoch.acquisition_passport_snapshot",
        "epoch.pending_overlay_admission_receipt",
        "epoch.activated_overlay_admission_receipt",
    }
)
_EPOCH_ACQUISITION_ARTIFACT_KINDS = frozenset(
    {
        "epoch.prepared",
        "epoch.admitted_acquisition_boundary_evidence",
        "epoch.acquisition_semantic_boundary_candidate",
        "epoch.acquisition_native_member",
        "epoch.acquisition_owner_snapshot",
        "epoch.acquisition_native_membership",
        "epoch.acquisition_native_membership_receipt",
        "epoch.acquisition_semantic_denominator_receipt",
        "epoch.acquisition_semantic_projection_verification_receipt",
        "epoch.acquisition_projection_verifier_provenance",
        "epoch.semantic_manifest",
        "epoch.boundary_denominator_receipt",
        "epoch.facet_denominator_receipt",
        "epoch.scope_history",
        "epoch.l5_scoped_schema_regime_projection",
        "epoch.lex_amendment_window_denominator",
        "l5.schema_regime_denominator_receipt",
    }
)
_CANONICAL_OWNER_ROW_KINDS = frozenset(
    {
        "l5.schema_regime_owner_snapshot",
        "l5.schema_regime",
        "lex.amendment_owner_snapshot",
        "lex.amendment",
    }
)
_RAW_OWNER_SOURCE_KINDS = frozenset(
    {"l5.schema_regime_registry", "l5.schema_regime_scope_registry"}
)
_EPOCH_NATIVE_COORDINATE_ROLES: dict[
    str,
    Literal["valid_effect", "visibility_knowledge_cutoff", "purpose_admission_cutoff"],
] = {
    "epoch.coordinate.valid_effect.v1": "valid_effect",
    "epoch.coordinate.visibility_knowledge_cutoff.v1": "visibility_knowledge_cutoff",
    "epoch.coordinate.purpose_admission_cutoff.v1": "purpose_admission_cutoff",
    "epoch.coordinate.valid-date.v1": "valid_effect",
    "epoch.coordinate.knowledge-time.v1": "visibility_knowledge_cutoff",
    "epoch.coordinate.admission-time.v1": "purpose_admission_cutoff",
}
_CONNECTOR_CACHE_DATA_MEDIA_TYPES = frozenset(
    {
        "application/vnd.polisyos.cached-result+application/json",
        "application/vnd.polisyos.cached-result+application/parquet",
        "application/vnd.polisyos.cached-result+application/pickle",
    }
)


class AcquisitionArtifactCodec(NamedTuple):
    """Declared byte and manifest codec for one existing acquisition ref kind."""

    media_type: str
    payload_format: Literal[
        "epoch_frame",
        "canonical_json",
        "raw_json",
        "producer_json",
        "connector_cache_payload",
        "opaque_bytes",
        "native_coordinate",
        "full_prefix_bundle",
        "full_prefix_verification",
        "native_projection",
        "identity_token",
        "unresolved_reference",
    ]
    canon: CanonInfo | None
    schema_name: str | None = None
    schema_version: str | None = None
    require_schema_absent: bool = False


_COORDINATE_PREFIX = b"polisyos.native-coordinate.v1\0"
_QUERY_CONTEXT_PREFIX = b"polisyos.epoch.query-context.v1\0"
_ACQUISITION_CANDIDATE_PREFIX = b"polisyos.epoch.acquisition-semantic-boundary-candidate.v1\0"


class _EpochModel(BaseModel):
    """Strict immutable base for cross-owner epoch DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class _EpochArtifactStore(RawManifestBytesReader, Protocol):
    """Read-only CAS surface, including raw manifest bytes for Core profile checks."""

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef) -> bytes: ...

    def get_manifest(self, artifact_id: ArtifactID | ArtifactRef) -> object: ...

    def verify(self, artifact_id: ArtifactID | ArtifactRef) -> object: ...


class _UnownedManifestSchemaExpectation(NamedTuple):
    """Bounded schema scope that this reader does not own or infer."""

    scope: str


class _ExactManifestInputClosure(NamedTuple):
    """Producer-declared direct inputs checked before payload access."""

    refs: tuple[InputRef, ...]


class _PayloadDerivedManifestInputClosure(NamedTuple):
    """Direct inputs recomputed from typed payload bytes before authority use."""

    owner: str
    comparison: Literal["ordered", "multiset"]


class _RequiredManifestInputViewSubset(NamedTuple):
    """Existing owner refs that must occur in a larger manifest input view."""

    refs: tuple[ArtifactRef, ...]


class _UnownedManifestInputClosure(NamedTuple):
    """Explicitly bound an input-lineage scope not declared by this owner."""

    scope: str


class _DataSnapshotManifestInputClosure(NamedTuple):
    """DataSnapshot edges recomputed from its Core Fabric DTO after byte decode."""

    owner: Literal["core.contracts.fabric.DataSnapshot"] = "core.contracts.fabric.DataSnapshot"


_ManifestSchemaExpectation = (
    SchemaInfo | tuple[SchemaInfo | None, ...] | None | _UnownedManifestSchemaExpectation
)

_ManifestInputExpectation = (
    _ExactManifestInputClosure
    | _PayloadDerivedManifestInputClosure
    | _RequiredManifestInputViewSubset
    | _UnownedManifestInputClosure
    | _DataSnapshotManifestInputClosure
)


def _manifest_schema_matches(manifest: object, expected_schema: _ManifestSchemaExpectation) -> bool:
    """Check an owner schema expectation without reading artifact bytes."""
    actual_schema = getattr(manifest, "artifact_schema", None)
    if isinstance(expected_schema, _UnownedManifestSchemaExpectation):
        if not expected_schema.scope.strip():
            raise TypeError("unowned manifest schema expectation requires a bounded scope")
        return True
    if isinstance(expected_schema, tuple):
        return actual_schema in expected_schema
    if expected_schema is None or isinstance(expected_schema, SchemaInfo):
        return actual_schema == expected_schema
    raise TypeError("manifest admission requires an exact or explicitly unowned schema")


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


def _preflight_core_manifest_profile(
    *,
    store: object,
    selector: object,
    expected_kind: str,
    expected_media_type: str,
    expected_canon: CanonInfo,
    expected_schema: _ManifestSchemaExpectation,
    require_selected_profile: bool,
    expected_inputs: _ManifestInputExpectation,
) -> ArtifactManifest:
    """Admit one existing Core manifest view before any payload or integrity read.

    ``selector`` is passed unchanged to the existing raw-manifest profile reader:
    an unselected reference therefore remains the actual default view.  The
    helper does not synthesize selectors or infer a profile from payload bytes.
    Every callsite must explicitly choose an input-closure contract. Exact
    producer contracts and required view subsets are checked at this manifest-only
    boundary. Payload-derived contracts are checked from typed bytes before the
    caller can use them. External ancestry is explicitly out of this owner's
    closure claim; it must not be described as a verified parent-edge relation.
    """
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.core.artifacts import artifact_manifest_profile_sha256, read_core_manifest_profile

    if isinstance(selector, ArtifactRef):
        if selector.kind != expected_kind or selector.media_type != expected_media_type:
            raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
        if require_selected_profile and selector.manifest_profile_sha256 is None:
            raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
    manifest, _declaration = read_core_manifest_profile(store, selector)
    selected_artifact_id = getattr(selector, "artifact_id", selector)
    schema_contract_matches = _manifest_schema_matches(manifest, expected_schema)
    manifest_inputs = getattr(manifest, "inputs", None)
    if isinstance(expected_inputs, _ExactManifestInputClosure):
        input_contract_matches = isinstance(manifest_inputs, list) and manifest_inputs == list(
            expected_inputs.refs
        )
    elif isinstance(expected_inputs, _RequiredManifestInputViewSubset):
        input_views = (
            {(str(row.artifact_id), row.manifest_profile_sha256) for row in manifest_inputs}
            if isinstance(manifest_inputs, list)
            else set()
        )
        required_views = {
            (str(ref.artifact_id), ref.manifest_profile_sha256) for ref in expected_inputs.refs
        }
        input_contract_matches = required_views.issubset(input_views)
    elif isinstance(
        expected_inputs,
        _PayloadDerivedManifestInputClosure
        | _UnownedManifestInputClosure
        | _DataSnapshotManifestInputClosure,
    ):
        input_contract_matches = True
    else:
        raise TypeError("Core manifest admission requires a typed input-closure contract")
    if (
        str(getattr(manifest, "artifact_id", None)) != str(selected_artifact_id)
        or getattr(manifest, "kind", None) != expected_kind
        or getattr(manifest, "media_type", None) != expected_media_type
        or not schema_contract_matches
        or getattr(manifest, "canon", None) != expected_canon
        or not input_contract_matches
        or (
            isinstance(selector, ArtifactRef)
            and selector.manifest_profile_sha256 is not None
            and artifact_manifest_profile_sha256(manifest) != selector.manifest_profile_sha256
        )
    ):
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_profile_mismatch")
    return ArtifactManifest.model_validate(manifest)


def epoch_canon_info() -> CanonInfo:
    """Return manifest metadata for the canonical epoch codec."""
    return CanonInfo.from_spec(_CANON)


def external_epoch_statement_canon_info() -> CanonInfo:
    """Return the declared codec for acquisition-owner JSON statements."""
    return CanonInfo.from_spec(_EXTERNAL_STATEMENT_CANON)


def canonical_external_epoch_statement_bytes(
    value: BaseModel | dict[str, Any],
) -> bytes:
    """Canonicalize one acquisition-owner statement with its declared codec."""
    mapping = _raw(value)
    if not isinstance(mapping, dict):
        raise TypeError("external epoch statement canonicalization requires a mapping")
    return to_canonical_bytes(mapping, _EXTERNAL_STATEMENT_CANON)


def _validate_chronology_query_context_payload(payload: bytes) -> None:
    """Validate the exact framed NativeChronologyQuery wire codec.

    This checks only typed content and canonical bytes. It does not qualify the
    query, its policy, or its authority.
    """
    from polisyos.core.contracts import chronology
    from polisyos.core.security import parse_canonical_statement

    parse_canonical_statement(payload, chronology.NativeChronologyQuery)


def acquisition_artifact_codec(
    kind: str, *, media_type: str | None = None
) -> AcquisitionArtifactCodec | None:
    """Return the exact registered source codec for an existing ref kind.

    ``media_type`` is mandatory to resolve connector-cache payloads because the
    producer supports three distinct inner encodings. Unknown variants refuse.
    Identity tokens are not evidence bytes. Unresolved references have no owner
    byte resolver and cannot satisfy a selected-evidence read.
    """
    epoch_media = "application/vnd.polisyos.epoch+json"
    if kind == "epoch.chronology_query_context":
        query_media = "application/vnd.polisyos.chronology-query+json"
        if media_type not in (None, query_media):
            return None
        return AcquisitionArtifactCodec(
            query_media,
            "opaque_bytes",
            None,
            require_schema_absent=True,
        )
    if kind == "epoch.semantic_facet_source.v1":
        if media_type not in (None, epoch_media):
            return None
        return AcquisitionArtifactCodec(epoch_media, "canonical_json", epoch_canon_info())
    if kind in _EXTERNAL_ACQUISITION_STATEMENT_KINDS:
        return AcquisitionArtifactCodec(
            epoch_media, "epoch_frame", external_epoch_statement_canon_info()
        )
    if kind == "epoch.production_receipt":
        return AcquisitionArtifactCodec(
            "application/vnd.polisyos.epoch-production-receipt+json",
            "epoch_frame",
            epoch_canon_info(),
        )
    if kind == "epoch.history_append_receipt":
        return AcquisitionArtifactCodec(
            epoch_media,
            "epoch_frame",
            epoch_canon_info(),
            require_schema_absent=True,
        )
    if kind == "core.chronology.full_prefix.bundle":
        return AcquisitionArtifactCodec(
            "application/octet-stream",
            "full_prefix_bundle",
            epoch_canon_info(),
            "polisyos.chronology.FullPrefixBundle",
            "1",
        )
    if kind == "core.chronology.full_prefix.verification_result":
        return AcquisitionArtifactCodec(
            "application/octet-stream",
            "full_prefix_verification",
            epoch_canon_info(),
            "polisyos.chronology.FullPrefixVerificationResult",
            "1",
        )
    if kind == "core.chronology.native_projection":
        return AcquisitionArtifactCodec(
            "application/octet-stream",
            "native_projection",
            epoch_canon_info(),
            "polisyos.chronology.NativeProjection",
            "1",
        )
    if kind in _EPOCH_ACQUISITION_ARTIFACT_KINDS:
        return AcquisitionArtifactCodec(epoch_media, "epoch_frame", epoch_canon_info())
    if kind in _CANONICAL_OWNER_ROW_KINDS:
        return AcquisitionArtifactCodec("application/json", "canonical_json", epoch_canon_info())
    if kind in _RAW_OWNER_SOURCE_KINDS:
        return AcquisitionArtifactCodec("application/json", "raw_json", None)
    if kind == "fabric.acquisition.raw_evidence":
        return AcquisitionArtifactCodec("application/json", "opaque_bytes", None)
    if kind == "fabric.evidence_bundle":
        return AcquisitionArtifactCodec(
            "application/json",
            "producer_json",
            CanonInfo.from_spec(CanonSpec()),
            "fabric.evidence_bundle",
            "1.0",
        )
    if kind == "fabric.data_snapshot":
        return AcquisitionArtifactCodec(
            "application/json",
            "producer_json",
            CanonInfo.from_spec(CanonSpec(forbid_floats=False)),
            "polisyos.core.DataSnapshot",
            "0.2.0",
        )
    if kind == "fabric.quality_report":
        return AcquisitionArtifactCodec(
            "application/json",
            "producer_json",
            CanonInfo.from_spec(CanonSpec(forbid_floats=False)),
            "polisyos.fabric.DataQualityReport",
            "1.0",
        )
    if kind == "fabric.retrieval_summary":
        return AcquisitionArtifactCodec(
            "application/json",
            "producer_json",
            CanonInfo.from_spec(CanonSpec(forbid_floats=False)),
            "polisyos.fabric.RetrievalSummary",
            "1.0",
        )
    if kind == "connector_cache.payload":
        if media_type not in _CONNECTOR_CACHE_DATA_MEDIA_TYPES:
            return None
        return AcquisitionArtifactCodec(
            media_type,
            "connector_cache_payload",
            None,
            "fabric.connector_cache",
            "1.0",
        )
    if kind in _EPOCH_NATIVE_COORDINATE_ROLES:
        return AcquisitionArtifactCodec(epoch_media, "native_coordinate", None)
    if kind == "lex.document":
        return AcquisitionArtifactCodec("text/plain", "identity_token", None)
    if kind == "l5.schema_regime_scope_relation":
        return AcquisitionArtifactCodec("application/json", "unresolved_reference", None)
    return None


def acquisition_native_coordinate_role(
    kind: str,
) -> Literal["valid_effect", "visibility_knowledge_cutoff", "purpose_admission_cutoff"] | None:
    """Return the registered temporal role for one native coordinate kind."""
    codec = acquisition_artifact_codec(kind)
    if codec is None or codec.payload_format != "native_coordinate":
        return None
    return _EPOCH_NATIVE_COORDINATE_ROLES.get(kind)


def _acquisition_native_coordinate_role(
    kind: str,
) -> Literal["valid_effect", "visibility_knowledge_cutoff", "purpose_admission_cutoff"] | None:
    """Retain the pre-facade helper as an internal compatibility alias."""
    return acquisition_native_coordinate_role(kind)


def acquisition_artifact_canon_info(kind: str) -> CanonInfo | None:
    """Return a registered canon, or ``None`` for raw, identity, or unresolved refs."""
    codec = acquisition_artifact_codec(kind)
    return None if codec is None else codec.canon


def canonical_epoch_bytes(value: BaseModel | dict[str, Any]) -> bytes:
    """Return canonical JSON bytes for an explicitly typed epoch value."""

    if isinstance(value, ScopedSchemaRegimeProjection):
        mapping = _scoped_schema_regime_projection_payload(value, include_hash=True)
    else:
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

    The supplied reference selects a CAS manifest view: a profile digest selects
    that exact view, while an absent digest selects the store's actual default view.
    The reader never adds a selector. For semantic manifests and production receipts,
    an absent selector is accepted only when the actual manifest declares the exact
    Core epoch profile; a manifest missing that profile remains a typed refusal.
    The returned mapping is admitted from independently re-read bytes after CAS,
    frame-count, content-address, and owner input-closure checks agree.
    """
    from polisyos.core.artifacts import load_core_json_frame_records

    owner_media_type = _EPOCH_OWNER_STATEMENT_MEDIA_TYPES.get(expected_kind)
    if owner_media_type is not None and expected_media_type != owner_media_type:
        raise ValueError("epoch statement owner media type differs")
    if ref.kind != expected_kind or ref.media_type != expected_media_type:
        raise ValueError("epoch statement reference profile differs")
    codec = acquisition_artifact_codec(expected_kind, media_type=expected_media_type)
    if codec is None or codec.canon is None:
        raise ValueError("epoch statement has no registered Core profile")
    expected_schema = _known_epoch_statement_manifest_schema(expected_kind, codec)
    input_expectation = _known_epoch_statement_manifest_inputs(expected_kind)
    manifest = _preflight_core_manifest_profile(
        store=store,
        selector=ref,
        expected_kind=expected_kind,
        expected_media_type=expected_media_type,
        expected_canon=codec.canon,
        expected_schema=expected_schema,
        require_selected_profile=False,
        expected_inputs=input_expectation,
    )
    report = store.verify(ref)
    payload = store.get_bytes(ref)
    observed_manifest = store.get_manifest(ref)
    if observed_manifest != manifest:
        raise ValueError("epoch statement manifest changed after profile preflight")
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
    decoded = load_core_json_frame_records(store, ref, raw_payload_bytes=payload)[0]
    if not isinstance(decoded, dict):
        raise ValueError("epoch statement payload is not a mapping")
    # Read the Core profile first so an absent historical declaration remains
    # a typed CanonicalProfileRefusalError instead of being repaired here.
    if expected_kind in _EPOCH_OWNER_STATEMENT_MEDIA_TYPES and (
        getattr(manifest, "artifact_schema", None) is not None
        or getattr(manifest, "canon", None) != epoch_canon_info()
    ):
        raise ValueError("epoch statement Core profile differs")
    if isinstance(input_expectation, _PayloadDerivedManifestInputClosure):
        expected_inputs = _epoch_statement_manifest_inputs_after_decode(expected_kind, decoded)
        if expected_inputs is None:
            raise TypeError("payload-derived epoch statement input contract is incomplete")
        _verify_decoded_manifest_input_closure(
            manifest=manifest,
            expectation=input_expectation,
            decoded_inputs=expected_inputs,
            failure_message="epoch statement manifest input closure differs",
        )
    elif isinstance(input_expectation, _DataSnapshotManifestInputClosure):
        _verify_decoded_data_snapshot_manifest_inputs(manifest=manifest, decoded=decoded)
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
        expected = scoped_schema_regime_projection_content_hash(mapping)
        if self.projection_content_hash != expected:
            raise ValueError("scoped regime projection hash differs from its content")
        return self


def _scoped_schema_regime_projection_payload(
    value: ScopedSchemaRegimeProjection | dict[str, Any], *, include_hash: bool
) -> dict[str, Any]:
    """Normalize the two artifact refs with the projection's frozen v1 serializer."""

    if isinstance(value, ScopedSchemaRegimeProjection):
        payload = {name: getattr(value, name) for name in value.__class__.model_fields}
    else:
        payload = dict(value)
    if not include_hash:
        payload.pop("projection_content_hash", None)
    for name in ("owner_source_snapshot_ref", "denominator_receipt_ref"):
        ref = ArtifactRef.model_validate(payload[name])
        payload[name] = ref.model_dump(mode="json")
    return payload


def scoped_schema_regime_projection_content_hash(
    value: ScopedSchemaRegimeProjection | dict[str, Any],
) -> Digest:
    """Hash a typed scoped projection using its byte-stable artifact-ref payload."""

    payload = _scoped_schema_regime_projection_payload(value, include_hash=False)
    return _sha256(canonical_epoch_bytes(payload))


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
    chronology_projection_ref: ArtifactRef | None = None
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
        if not positive and self.chronology_projection_ref is not None:
            raise ValueError("negative epoch receipt carries native projection custody")
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


def _semantic_epoch_production_receipt_input_refs(
    receipt: SemanticEpochProductionReceiptStatement,
) -> tuple[InputRef, ...]:
    """Derive the producer-declared direct CAS edges for one epoch receipt.

    The direct lineage is the seven typed statement fields named below. The
    ``owner_denominator_receipt_refs`` field remains verification evidence in
    the receipt payload; its evidence validation belongs to the owning consumer,
    and it is not promoted into this CAS input-edge contract.
    """
    return tuple(
        input_ref_from_artifact_ref(source, role="epoch_production_input")
        for source in (
            receipt.prepared_epoch_ref,
            receipt.admitted_boundary_evidence_ref,
            receipt.semantic_manifest_ref,
            receipt.history_append_receipt_ref,
            receipt.chronology_bundle_ref,
            receipt.chronology_verification_ref,
            receipt.chronology_projection_ref,
        )
        if source is not None
    )


def _known_epoch_statement_manifest_schema(
    expected_kind: str, codec: AcquisitionArtifactCodec
) -> _ManifestSchemaExpectation:
    """Use the actual writer schema contract, or state the limited unowned scope.

    A missing codec schema name is not evidence that the manifest must omit its
    schema. Exact absence is used only for existing writers whose actual
    ``ArtifactWriteOptions`` omit the schema, including the selected raw L5
    registry source writers. Other registered source codecs with no schema
    declaration retain an explicitly bounded unowned expectation.
    """
    if expected_kind == "fabric.data_snapshot":
        return (
            SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            SchemaInfo(name="polisyos.core.DataSnapshot", version="0.3.0"),
        )
    if expected_kind == "fabric.quality_report":
        return (
            SchemaInfo(name="polisyos.fabric.DataQualityReport", version="1.0"),
            SchemaInfo(name="polisyos.fabric.DataQualityReport", version="1.1"),
        )
    if codec.schema_name is not None:
        return SchemaInfo(name=codec.schema_name, version=codec.schema_version or "")
    if (
        codec.require_schema_absent
        or expected_kind == "epoch.semantic_facet_source.v1"
        or expected_kind in _EPOCH_OWNER_STATEMENT_MEDIA_TYPES
        or expected_kind in _EPOCH_ACQUISITION_ARTIFACT_KINDS
        or expected_kind in _RAW_OWNER_SOURCE_KINDS
        or expected_kind in _EXTERNAL_ACQUISITION_STATEMENT_KINDS
        or expected_kind in _CANONICAL_OWNER_ROW_KINDS
        or expected_kind == "epoch.history_append_receipt"
    ):
        return None
    return _UnownedManifestSchemaExpectation(
        f"{expected_kind} schema is not declared by its registered acquisition codec"
    )


def _known_epoch_statement_manifest_inputs(expected_kind: str) -> _ManifestInputExpectation:
    """Return the input-closure contract declared by a registered source writer.

    The prepared and production-receipt writers persist typed references as
    manifest inputs. The semantic-facet and chronology-query-context writers
    declare no input edges, which is an exact empty-list contract. Newly accepted
    codecs must add an evidenced writer contract here before protected loading.
    """
    if expected_kind == "epoch.prepared":
        return _PayloadDerivedManifestInputClosure("epoch.prepared", "multiset")
    if expected_kind == "epoch.production_receipt":
        return _PayloadDerivedManifestInputClosure("epoch.production_receipt", "multiset")
    if expected_kind == "fabric.data_snapshot":
        return _DataSnapshotManifestInputClosure()
    if expected_kind in {
        "fabric.evidence_bundle",
        "fabric.quality_report",
        "fabric.retrieval_summary",
    }:
        return _ExactManifestInputClosure(())
    if expected_kind in {"epoch.semantic_facet_source.v1", "epoch.chronology_query_context"}:
        return _ExactManifestInputClosure(())
    if expected_kind == "core.chronology.full_prefix.verification_result":
        return _PayloadDerivedManifestInputClosure(expected_kind, "ordered")
    if expected_kind == "core.chronology.native_projection":
        return _PayloadDerivedManifestInputClosure(expected_kind, "ordered")
    if expected_kind == "core.chronology.full_prefix.bundle":
        return _UnownedManifestInputClosure(
            "opaque bundle inputs require the linked native projection reconciliation"
        )
    if (
        expected_kind in _EPOCH_ACQUISITION_ARTIFACT_KINDS
        or expected_kind in _EXTERNAL_ACQUISITION_STATEMENT_KINDS
        or expected_kind in _CANONICAL_OWNER_ROW_KINDS
        or expected_kind == "epoch.history_append_receipt"
    ):
        return _ExactManifestInputClosure(())
    raise ValueError("epoch statement writer input contract is not registered")


def _epoch_statement_manifest_inputs_after_decode(
    expected_kind: str, decoded: dict[str, Any]
) -> tuple[InputRef, ...]:
    """Recompute registered typed-writer input edges from exact statement bytes."""
    if expected_kind in {
        "core.chronology.full_prefix.verification_result",
        "core.chronology.native_projection",
    }:
        from polisyos.core.contracts import chronology as chronology_contract

        if expected_kind == "core.chronology.full_prefix.verification_result":
            statement = chronology_contract.FullPrefixVerificationStatement.model_validate(decoded)
            return chronology_contract._full_prefix_verification_manifest_input_refs(statement)
        statement = chronology_contract.NativeChronologyProjectionStatement.model_validate(decoded)
        return chronology_contract._native_chronology_projection_manifest_input_refs(statement)
    if expected_kind == "epoch.prepared":
        stamp = SemanticEpochStamp.model_validate(decoded.get("stamp"))
        return (
            input_ref_from_artifact_ref(
                stamp.semantic_manifest_ref,
                role="semantic_manifest",
            ),
        )
    if expected_kind == "epoch.production_receipt":
        receipt = SemanticEpochProductionReceiptStatement.model_validate(decoded)
        return _semantic_epoch_production_receipt_input_refs(receipt)
    raise ValueError("epoch statement has no payload-derived input contract")


def _epoch_owner_manifest_inputs_match(
    actual: tuple[InputRef, ...] | list[InputRef],
    expected: tuple[InputRef, ...],
) -> bool:
    """Compare the complete input multiset while preserving each selected view."""
    return _epoch_owner_input_keys(actual) == _epoch_owner_input_keys(expected)


def _epoch_owner_input_keys(
    values: tuple[InputRef, ...] | list[InputRef],
) -> tuple[tuple[str, str, str], ...]:
    """Sort the exact edge multiset without discarding selected profile identity."""
    return tuple(
        sorted(
            (
                value.role,
                str(value.artifact_id),
                value.manifest_profile_sha256 or "",
            )
            for value in values
        )
    )


def _verify_decoded_data_snapshot_manifest_inputs(
    *,
    manifest: ArtifactManifest,
    decoded: dict[str, Any],
) -> None:
    """Check DataSnapshot parent edges against the typed Core Fabric contract."""
    from polisyos.core.contracts.fabric import (
        DataSnapshot,
        data_snapshot_manifest_inputs_match,
    )

    schema = manifest.artifact_schema
    if (
        manifest.kind != DataSnapshot.ARTIFACT_KIND
        or manifest.media_type != DataSnapshot.ARTIFACT_MEDIA_TYPE
        or schema is None
        or schema.name != DataSnapshot.ARTIFACT_SCHEMA_NAME
    ):
        raise ValueError("DataSnapshot selected manifest schema differs")
    snapshot = DataSnapshot.model_validate(decoded)
    if not data_snapshot_manifest_inputs_match(
        snapshot,
        manifest.inputs,
        schema_version=schema.version,
    ):
        raise ValueError("DataSnapshot manifest input closure differs")


def _verify_decoded_manifest_input_closure(
    *,
    manifest: ArtifactManifest,
    expectation: _ExactManifestInputClosure | _PayloadDerivedManifestInputClosure,
    decoded_inputs: Sequence[InputRef],
    failure_message: str,
) -> None:
    """Reconcile decoded owner refs with both the preflight view and manifest."""
    actual = manifest.inputs
    expected = list(decoded_inputs)
    if isinstance(expectation, _ExactManifestInputClosure):
        matches = actual == list(expectation.refs) == expected
    elif expectation.comparison == "ordered":
        matches = actual == expected
    else:
        matches = _epoch_owner_manifest_inputs_match(actual, expected)
    if not matches:
        raise ValueError(failure_message)


class SemanticEpochHistoryAppendReceiptStatement(_EpochModel):
    """Exact profileless history-owner receipt wire statement.

    This DTO validates only the bytes emitted by the native append owner. It
    does not assert that the recorded heads remain current or that the append
    was institutionally authorized.
    """

    schema_version: Literal["polisyos.epoch.history-append-receipt.v1"]
    status: Literal["appended", "idempotent"]
    manifest_ref: ArtifactRef
    epoch_ref: Digest
    expected_head_refs: tuple[Digest, ...]
    resulting_head_refs: tuple[Digest, ...]
    resulting_history_snapshot_ref: ArtifactRef
    resulting_history_snapshot_content_hash: Digest

    @model_validator(mode="after")
    def _bind_append_projection(self) -> Self:
        if (
            self.manifest_ref.kind != "epoch.semantic_manifest"
            or self.manifest_ref.media_type != "application/vnd.polisyos.epoch+json"
        ):
            raise ValueError("history append receipt manifest profile differs")
        if (
            self.resulting_history_snapshot_ref.kind != "epoch.scope_history"
            or self.resulting_history_snapshot_ref.media_type
            != "application/vnd.polisyos.epoch+json"
        ):
            raise ValueError("history append receipt snapshot profile differs")
        if str(self.resulting_history_snapshot_ref.artifact_id) != (
            self.resulting_history_snapshot_content_hash
        ):
            raise ValueError("history append snapshot hash differs from its CAS identity")
        if self.epoch_ref not in self.resulting_head_refs:
            raise ValueError("successful history append does not contain its resulting epoch head")
        return self


__all__ = [
    "AcquisitionArtifactCodec",
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
    "SemanticEpochHistoryAppendReceiptStatement",
    "SemanticEpochProductionReceiptStatement",
    "SemanticEpochStamp",
    "acquisition_artifact_canon_info",
    "acquisition_artifact_codec",
    "acquisition_native_coordinate_role",
    "acquisition_semantic_candidate_bytes",
    "acquisition_semantic_candidate_content_hash",
    "canonical_epoch_bytes",
    "canonical_external_epoch_statement_bytes",
    "epoch_canon_info",
    "epoch_query_context_ref",
    "epoch_semantic_content_hash",
    "external_epoch_statement_canon_info",
    "load_verified_epoch_statement",
    "native_coordinate_ref",
    "scoped_schema_regime_projection_content_hash",
]
