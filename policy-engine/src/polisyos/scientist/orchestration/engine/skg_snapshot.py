"""Retain exact DuckDB source bytes for Scientist saved-snapshot replay.

The canonical SKG query/selector remain owned by data_forge. This module stores
an operational source snapshot using the existing CAS, not a source issuer or
scientific evidence owner. Capture retains an accepted generation; cache-hit
reuse writes no new source chunks. Replay materializes verified CAS chunks at a
persistent run-local path. A descriptor
never authorizes a live-file fallback.
"""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    AtomicFileDurabilityError,
    FileSystemCAS,
    ProducerInfo,
    SchemaInfo,
    artifact_manifest_profile_sha256,
    ensure_directory_durable,
    fsync_directory,
    input_ref_from_artifact_ref,
)
from polisyos.data_forge.read_api.academic import SKGQuery

if TYPE_CHECKING:
    from polisyos.data_forge.read_api.academic import PreparedSKGRead
    from polisyos.scientist.orchestration.engine.state import ExperimentState

SNAPSHOT_INPUT_KEY = "skg_source_snapshot"
_SNAPSHOT_KIND = "scientist.skg_source_snapshot"
_CHUNK_KIND = "scientist.skg_source_chunk"
_VERSION: Literal["1.0"] = "1.0"
_CHUNK_BYTES = 1024 * 1024


class RetainedSKGSnapshotError(ValueError):
    """Refuse a missing, inconsistent, or changing saved source."""


class _SnapshotChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    ref: ArtifactRef
    byte_size: int = Field(gt=0, le=_CHUNK_BYTES)


class RetainedSKGSnapshot(BaseModel):
    """Exact operational bytes and provenance; no scientific authenticity claim."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["1.0"]
    source_reference: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(gt=0)
    source_binding_schema_version: str = Field(min_length=1)
    query_version: str = Field(min_length=1)
    chunks: tuple[_SnapshotChunk, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_complete_length(self) -> RetainedSKGSnapshot:
        if sum(chunk.byte_size for chunk in self.chunks) != self.byte_size:
            raise ValueError("retained_skg_chunk_length_mismatch")
        if any(chunk.byte_size != _CHUNK_BYTES for chunk in self.chunks[:-1]):
            raise ValueError("retained_skg_chunk_boundary_mismatch")
        return self


def _file_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _write_options(kind: str, media_type: str) -> ArtifactWriteOptions:
    return ArtifactWriteOptions(
        kind=kind,
        media_type=media_type,
        schema=SchemaInfo(name=kind, version=_VERSION),
        producer=ProducerInfo(component=__name__, version=_VERSION),
    )


def _select_written_ref(store: FileSystemCAS, ref: ArtifactRef) -> ArtifactRef:
    """Bind the producer's actual manifest view through the canonical CAS profile."""
    manifest = store.get_manifest(ref)
    if manifest.kind != ref.kind or manifest.media_type != ref.media_type:
        raise RetainedSKGSnapshotError("retained_skg_written_ref_type_mismatch")
    selected = ArtifactRef(
        artifact_id=ref.artifact_id,
        kind=ref.kind,
        media_type=ref.media_type,
        manifest_profile_sha256=artifact_manifest_profile_sha256(manifest),
    )
    # A default/unbound put can return no profile. Require its actual immutable
    # selected sidecar, rather than treating that legacy selector as a full view.
    store.get_manifest(selected)
    return selected


def load_retained_skg_snapshot(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> RetainedSKGSnapshot:
    """Read the exact descriptor and verify its complete retained byte closure."""
    if ref.manifest_profile_sha256 is None:
        raise RetainedSKGSnapshotError("retained_skg_descriptor_profile_required")
    manifest = store.get_manifest(ref)
    if (
        ref.kind != _SNAPSHOT_KIND
        or ref.media_type != "application/json"
        or manifest.kind != _SNAPSHOT_KIND
        or manifest.artifact_schema is None
        or (manifest.artifact_schema.name, manifest.artifact_schema.version)
        != (_SNAPSHOT_KIND, _VERSION)
    ):
        raise RetainedSKGSnapshotError("retained_skg_descriptor_type_mismatch")
    snapshot = RetainedSKGSnapshot.model_validate_json(store.get_bytes(ref))
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
        if (
            chunk.ref.kind != _CHUNK_KIND
            or chunk.ref.media_type != "application/octet-stream"
            or chunk_manifest.kind != _CHUNK_KIND
            or chunk_manifest.byte_size != chunk.byte_size
            or chunk_manifest.artifact_schema is None
            or (chunk_manifest.artifact_schema.name, chunk_manifest.artifact_schema.version)
            != (_CHUNK_KIND, _VERSION)
        ):
            raise RetainedSKGSnapshotError("retained_skg_chunk_type_mismatch")
        with store.open_member(chunk.ref, "blob") as source:
            while payload := source.read(_CHUNK_BYTES):
                digest.update(payload)
                total += len(payload)
    if total != snapshot.byte_size or digest.hexdigest() != snapshot.source_sha256:
        raise RetainedSKGSnapshotError("retained_skg_retained_digest_mismatch")
    return snapshot


def retain_prepared_skg_read(
    store: FileSystemCAS,
    prepared: PreparedSKGRead,
    *,
    existing_ref: ArtifactRef | None = None,
) -> ArtifactRef:
    """Capture a stable prepared generation, or reuse its already-issued descriptor.

    The executor passes a cached origin's descriptor on a hit. A missing/corrupt
    descriptor does not trigger a new live snapshot under its old identity.
    Capture streams bounded chunks and publishes the descriptor only after the
    complete copied digest and both source-generation checks agree.
    """
    if not prepared.source_generation_matches():
        raise RetainedSKGSnapshotError("retained_skg_source_changed")
    if existing_ref is not None:
        snapshot = load_retained_skg_snapshot(store, existing_ref)
        if (
            snapshot.source_sha256 != prepared.source_snapshot_sha256
            or snapshot.source_reference != prepared.source_snapshot_ref
            or snapshot.source_binding_schema_version != prepared.source_binding_schema_version
            or snapshot.query_version != prepared.query_version
        ):
            raise RetainedSKGSnapshotError("retained_skg_existing_source_mismatch")
        if not prepared.source_generation_matches():
            raise RetainedSKGSnapshotError("retained_skg_source_changed")
        return existing_ref

    descriptor = os.open(
        prepared.db_path,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
    )
    chunks: list[_SnapshotChunk] = []
    digest = hashlib.sha256()
    total = 0
    with os.fdopen(descriptor, "rb") as source:
        initial = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(initial.st_mode)
            or _file_identity(initial) != prepared.source_file_identity
        ):
            raise RetainedSKGSnapshotError("retained_skg_source_generation_mismatch")
        while payload := source.read(_CHUNK_BYTES):
            digest.update(payload)
            total += len(payload)
            chunk_ref = store.put_bytes(
                payload,
                _write_options(_CHUNK_KIND, "application/octet-stream"),
            )
            chunk_ref = _select_written_ref(store, chunk_ref)
            chunks.append(_SnapshotChunk(ref=chunk_ref, byte_size=len(payload)))
        if _file_identity(os.fstat(source.fileno())) != prepared.source_file_identity:
            raise RetainedSKGSnapshotError("retained_skg_source_changed")
    if (
        not prepared.source_generation_matches()
        or digest.hexdigest() != prepared.source_snapshot_sha256
        or total != prepared.source_file_identity[2]
    ):
        raise RetainedSKGSnapshotError("retained_skg_capture_digest_mismatch")
    snapshot = RetainedSKGSnapshot(
        schema_version=_VERSION,
        source_reference=prepared.source_snapshot_ref,
        source_sha256=digest.hexdigest(),
        byte_size=total,
        source_binding_schema_version=prepared.source_binding_schema_version,
        query_version=prepared.query_version,
        chunks=tuple(chunks),
    )
    options = replace(
        _write_options(_SNAPSHOT_KIND, "application/json"),
        inputs=[
            input_ref_from_artifact_ref(chunk.ref, role=f"source_chunk:{index}")
            for index, chunk in enumerate(chunks)
        ],
    )
    ref = store.put_bytes(snapshot.model_dump_json().encode("utf-8"), options)
    ref = _select_written_ref(store, ref)
    if not prepared.source_generation_matches():
        raise RetainedSKGSnapshotError("retained_skg_source_changed_after_publication")
    return ref


def _require_local_file(path: Path, snapshot: RetainedSKGSnapshot) -> None:
    if path.with_name(path.name + ".wal").exists():
        raise RetainedSKGSnapshotError("retained_skg_materialization_wal")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size != snapshot.byte_size:
            raise RetainedSKGSnapshotError("retained_skg_materialization_size")
        digest = hashlib.file_digest(source, "sha256").hexdigest()
        after = os.fstat(source.fileno())
    if (
        digest != snapshot.source_sha256
        or _file_identity(before) != _file_identity(after)
        or _file_identity(path.stat()) != _file_identity(after)
    ):
        raise RetainedSKGSnapshotError("retained_skg_materialization_digest")


def materialize_retained_skg_snapshot(
    store: FileSystemCAS,
    ref: ArtifactRef,
    *,
    directory: Path,
) -> Path:
    """Restore retained bytes once, with no overwrite or fallback to the live DB."""
    snapshot = load_retained_skg_snapshot(store, ref)
    directory = directory.absolute()
    if any(component.is_symlink() for component in (directory, *directory.parents)):
        raise RetainedSKGSnapshotError("retained_skg_materialization_symlink")
    ensure_directory_durable(directory)
    target = directory / f"{snapshot.source_sha256}.duckdb"
    if target.exists() or target.is_symlink():
        _require_local_file(target, snapshot)
        fsync_directory(directory)
        return target

    descriptor, staging_name = tempfile.mkstemp(prefix=".skg-snapshot-", dir=directory)
    staging = Path(staging_name)
    try:
        with os.fdopen(descriptor, "wb") as destination:
            for chunk in snapshot.chunks:
                store.copy_member_to(chunk.ref, "blob", destination)
            destination.flush()
            os.fsync(destination.fileno())
        _require_local_file(staging, snapshot)
        try:
            os.link(staging, target)
        except FileExistsError:
            _require_local_file(target, snapshot)
        try:
            fsync_directory(directory)
        except OSError as exc:
            raise AtomicFileDurabilityError(
                "retained SKG name published but directory sync failed",
                replaced=True,
            ) from exc
    finally:
        staging.unlink(missing_ok=True)
    _require_local_file(target, snapshot)
    return target


def prepare_retained_skg_read(
    store: FileSystemCAS,
    ref: ArtifactRef,
    *,
    directory: Path,
    index_dir: Path,
) -> PreparedSKGRead:
    """Open the real canonical reader and verify its actual bound retained digest."""
    snapshot = load_retained_skg_snapshot(store, ref)
    path = materialize_retained_skg_snapshot(store, ref, directory=directory)
    prepared = SKGQuery.prepare_read(db_path=path, index_dir=index_dir)
    if (
        prepared.source_snapshot_sha256 != snapshot.source_sha256
        or prepared.source_binding_schema_version != snapshot.source_binding_schema_version
        or prepared.query_version != snapshot.query_version
    ):
        prepared.close()
        raise RetainedSKGSnapshotError("retained_skg_prepared_source_mismatch")
    return prepared


def bind_retained_skg_source(
    store: FileSystemCAS,
    ref: ArtifactRef,
    state: ExperimentState,
    *,
    directory: Path,
) -> ExperimentState:
    """Create an explicit replay input before node branching and key construction.

    Source selection is an executor input operation, not a node write. The live
    path is replaced only for this explicit saved-snapshot request. Per-node
    preparation must use prepare_retained_skg_read to recheck the selected digest.
    """
    path = materialize_retained_skg_snapshot(store, ref, directory=directory)
    return state.model_copy(
        update={
            "params": {**state.params, "skg_db_path": str(path)},
            "inputs": {**state.inputs, SNAPSHOT_INPUT_KEY: ref},
        }
    )
