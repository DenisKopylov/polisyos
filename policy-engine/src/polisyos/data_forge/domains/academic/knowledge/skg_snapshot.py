"""Typed local retention records for exact SKG source bytes.

These records bind a selected CAS descriptor to copied bytes and the source-local
version row observed through one read-only connection. They do not establish an
issuer, custody, authenticity, or currentness claim about the source.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, ClassVar, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    input_ref_from_artifact_ref,
    matches_runtime_protocol,
    validate_core_model_json_artifact,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.manifest import ArtifactManifest

_KIND = "scientist.skg_source_snapshot"
_MEDIA_TYPE = "application/json"
_CHUNK_KIND = "scientist.skg_source_chunk"
_CHUNK_MEDIA_TYPE = "application/octet-stream"
_CHUNK_SCHEMA_VERSION = "1.0"
_SNAPSHOT_SCHEMA_V1_0 = "1.0"
_SNAPSHOT_SCHEMA_V1_1 = "1.1"
_CHUNK_BYTES = 1024 * 1024


class RetainedSKGSnapshotError(ValueError):
    """Refuse a missing, inconsistent, or changing saved source."""


class _RetainedSKGReader(Protocol):
    """Exact read operations used to reconcile one retained descriptor."""

    def get_manifest(self, artifact_id: ArtifactID | ArtifactRef) -> ArtifactManifest: ...

    def get_raw_manifest_bytes(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        *,
        manifest_profile_sha256: str | None = None,
    ) -> bytes: ...

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef) -> bytes: ...


class _SnapshotChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    ref: ArtifactRef
    byte_size: int = Field(gt=0, le=_CHUNK_BYTES)


class RetainedSKGSnapshotChunk(_SnapshotChunk):
    """Current public chunk type; v1.0 keeps the original private schema name."""


class _RetainedSKGSnapshotFields[
    SnapshotVersionT: str,
    SnapshotChunkT: _SnapshotChunk,
](BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: SnapshotVersionT
    source_reference: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(gt=0)
    source_binding_schema_version: str = Field(min_length=1)
    query_version: str = Field(min_length=1)
    chunks: tuple[SnapshotChunkT, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_complete_length(self) -> Self:
        if sum(chunk.byte_size for chunk in self.chunks) != self.byte_size:
            raise ValueError("retained_skg_chunk_length_mismatch")
        if any(chunk.byte_size != _CHUNK_BYTES for chunk in self.chunks[:-1]):
            raise ValueError("retained_skg_chunk_boundary_mismatch")
        return self


class RetainedSKGSnapshot(
    _RetainedSKGSnapshotFields[Literal["1.0"], _SnapshotChunk],
):
    """Exact operational bytes and provenance; no scientific authenticity claim."""

    ARTIFACT_KIND: ClassVar[str] = _KIND
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = _MEDIA_TYPE
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = _KIND
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = _SNAPSHOT_SCHEMA_V1_0


class RetainedSKGSnapshotV11(
    _RetainedSKGSnapshotFields[Literal["1.1"], RetainedSKGSnapshotChunk],
):
    """Current descriptor with local content identity and observed source version."""

    ARTIFACT_KIND: ClassVar[str] = _KIND
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = _MEDIA_TYPE
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = _KIND
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = _SNAPSHOT_SCHEMA_V1_1

    source_version_id: int = Field(gt=0)
    version_identity_kind: Literal["content_digest"]


RetainedSKGSnapshotV10 = RetainedSKGSnapshot
RetainedSKGSnapshotRecord = RetainedSKGSnapshot | RetainedSKGSnapshotV11


class RetainedSKGSourceBinding(BaseModel):
    """Bundle projection of one exact descriptor and its local source identity."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    descriptor_ref: ArtifactRef
    source_reference: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_version_id: int = Field(gt=0)
    source_binding_schema_version: str = Field(min_length=1)
    query_version: str = Field(min_length=1)
    version_identity_kind: Literal["content_digest"]

    @model_validator(mode="after")
    def _require_selected_descriptor(self) -> RetainedSKGSourceBinding:
        if (
            self.descriptor_ref.kind != _KIND
            or self.descriptor_ref.media_type != _MEDIA_TYPE
            or self.descriptor_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("retained_skg_source_descriptor_profile_required")
        return self


def load_retained_skg_snapshot(
    store: _RetainedSKGReader,
    ref: ArtifactRef,
) -> RetainedSKGSnapshotRecord:
    """Resolve a selected descriptor and recompute its complete chunk digest."""
    if ref.manifest_profile_sha256 is None:
        raise RetainedSKGSnapshotError("retained_skg_descriptor_profile_required")
    manifest = store.get_manifest(ref)
    schema = manifest.artifact_schema
    if (
        ref.kind != _KIND
        or ref.media_type != _MEDIA_TYPE
        or manifest.kind != _KIND
        or manifest.media_type != _MEDIA_TYPE
        or schema is None
        or schema.name != _KIND
    ):
        raise RetainedSKGSnapshotError("retained_skg_descriptor_type_mismatch")
    if schema.version == _SNAPSHOT_SCHEMA_V1_0:
        snapshot: RetainedSKGSnapshotRecord = validate_core_model_json_artifact(
            RetainedSKGSnapshot, store, ref
        )
    elif schema.version == _SNAPSHOT_SCHEMA_V1_1:
        snapshot = validate_core_model_json_artifact(RetainedSKGSnapshotV11, store, ref)
    else:
        raise RetainedSKGSnapshotError("retained_skg_descriptor_type_mismatch")

    expected_inputs = [
        input_ref_from_artifact_ref(chunk.ref, role=f"source_chunk:{index}")
        for index, chunk in enumerate(snapshot.chunks)
    ]
    if manifest.inputs != expected_inputs:
        raise RetainedSKGSnapshotError("retained_skg_descriptor_lineage_mismatch")
    digest = hashlib.sha256()
    total = 0
    for chunk in snapshot.chunks:
        if chunk.ref.manifest_profile_sha256 is None:
            raise RetainedSKGSnapshotError("retained_skg_chunk_profile_required")
        chunk_manifest = store.get_manifest(chunk.ref)
        chunk_schema = chunk_manifest.artifact_schema
        if (
            chunk.ref.kind != _CHUNK_KIND
            or chunk.ref.media_type != _CHUNK_MEDIA_TYPE
            or chunk_manifest.kind != _CHUNK_KIND
            or chunk_manifest.media_type != _CHUNK_MEDIA_TYPE
            or chunk_manifest.byte_size != chunk.byte_size
            or chunk_schema is None
            or chunk_schema.name != _CHUNK_KIND
            or chunk_schema.version != _CHUNK_SCHEMA_VERSION
        ):
            raise RetainedSKGSnapshotError("retained_skg_chunk_type_mismatch")
        payload = store.get_bytes(chunk.ref)
        if len(payload) != chunk.byte_size:
            raise RetainedSKGSnapshotError("retained_skg_chunk_type_mismatch")
        digest.update(payload)
        total += len(payload)
    if total != snapshot.byte_size or digest.hexdigest() != snapshot.source_sha256:
        raise RetainedSKGSnapshotError("retained_skg_retained_digest_mismatch")
    return snapshot


def retained_skg_source_binding(
    store: ArtifactStore | _RetainedSKGReader,
    ref: ArtifactRef,
) -> RetainedSKGSourceBinding:
    """Build a typed binding only from a fully verified v1.1 descriptor."""
    if not matches_runtime_protocol(store, _RetainedSKGReader):
        raise RetainedSKGSnapshotError("retained_skg_descriptor_read_store_required")
    snapshot = load_retained_skg_snapshot(store, ref)
    if not isinstance(snapshot, RetainedSKGSnapshotV11):
        raise RetainedSKGSnapshotError("retained_skg_legacy_source_version_unbound")
    return RetainedSKGSourceBinding(
        descriptor_ref=ref,
        source_reference=snapshot.source_reference,
        source_sha256=snapshot.source_sha256,
        source_version_id=snapshot.source_version_id,
        source_binding_schema_version=snapshot.source_binding_schema_version,
        query_version=snapshot.query_version,
        version_identity_kind=snapshot.version_identity_kind,
    )


__all__ = [
    "RetainedSKGSnapshot",
    "RetainedSKGSnapshotChunk",
    "RetainedSKGSnapshotError",
    "RetainedSKGSnapshotRecord",
    "RetainedSKGSnapshotV10",
    "RetainedSKGSnapshotV11",
    "RetainedSKGSourceBinding",
    "load_retained_skg_snapshot",
    "retained_skg_source_binding",
]
