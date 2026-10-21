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
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactManifest,
    ArtifactRef,
    ArtifactWriteOptions,
    AtomicFileDurabilityError,
    ProducerInfo,
    SchemaInfo,
    ensure_directory_durable,
    fsync_directory,
    input_ref_from_artifact_ref,
)
from polisyos.data_forge.read_api.academic import (
    RetainedSKGSnapshot as RetainedSKGSnapshot,
)
from polisyos.data_forge.read_api.academic import (
    RetainedSKGSnapshotChunk,
    RetainedSKGSnapshotError,
    RetainedSKGSnapshotRecord,
    RetainedSKGSnapshotV11,
    SKGQuery,
)
from polisyos.data_forge.read_api.academic import (
    load_retained_skg_snapshot as _load_retained_skg_snapshot,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import PutOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.data_forge.read_api.academic import PreparedSKGRead
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState

SNAPSHOT_INPUT_KEY = "skg_source_snapshot"


class _RetainedSKGReadStore(Protocol):
    """Verified CAS member-read capabilities needed to reopen one selected source."""

    def get_manifest(self, artifact_id: ArtifactID | ArtifactRef | str) -> ArtifactManifest: ...

    def get_raw_manifest_bytes(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        *,
        manifest_profile_sha256: str | None = None,
    ) -> bytes: ...

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes: ...

    def open_member(
        self, artifact_id: ArtifactID | ArtifactRef | str, member: Literal["blob"]
    ) -> Any: ...

    def copy_member_to(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        member: Literal["blob"],
        destination: Any,
    ) -> Any: ...


class _RetainedSKGStore(_RetainedSKGReadStore, Protocol):
    """Selected-profile CAS capabilities used by capture and strict replay."""

    def put_bytes(
        self,
        data: bytes,
        opts: PutOptions,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef: ...

    def put_json(
        self,
        obj: object,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef: ...


_RETAINED_SKG_READ_METHODS = (
    "get_manifest",
    "get_raw_manifest_bytes",
    "get_bytes",
    "open_member",
    "copy_member_to",
)
_SNAPSHOT_KIND = "scientist.skg_source_snapshot"
_CHUNK_KIND = "scientist.skg_source_chunk"
_SNAPSHOT_VERSION: Literal["1.1"] = "1.1"
_CHUNK_VERSION: Literal["1.0"] = "1.0"
_CHUNK_BYTES = 1024 * 1024


def _file_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _write_options(kind: str, media_type: str) -> ArtifactWriteOptions:
    version = _CHUNK_VERSION if kind == _CHUNK_KIND else _SNAPSHOT_VERSION
    return ArtifactWriteOptions(
        kind=kind,
        media_type=media_type,
        schema=SchemaInfo(name=kind, version=version),
        producer=ProducerInfo(component=__name__, version=version),
    )


def _require_retained_skg_read_store(store: object) -> _RetainedSKGReadStore:
    """Require the profile and verified-member reads used by retained replay.

    Retry attempt facades delegate these read methods while keeping CAS writes
    behind their revocable authority. Do not unwrap their private target.
    """
    if not all(callable(getattr(store, name, None)) for name in _RETAINED_SKG_READ_METHODS):
        raise RetainedSKGSnapshotError("retained_skg_member_read_store_required")
    return cast("_RetainedSKGReadStore", store)


def _require_selected_written_ref(
    store: _RetainedSKGStore,
    ref: ArtifactRef,
    *,
    kind: str,
    media_type: str,
) -> ArtifactRef:
    """Accept only the exact selected reference returned by this producer write."""
    if not isinstance(ref, ArtifactRef) or ref.manifest_profile_sha256 is None:
        raise RetainedSKGSnapshotError("retained_skg_selected_written_ref_required")
    manifest = store.get_manifest(ref)
    if (
        ref.kind != kind
        or ref.media_type != media_type
        or manifest.kind != kind
        or manifest.media_type != media_type
    ):
        raise RetainedSKGSnapshotError("retained_skg_written_ref_type_mismatch")
    return ref


def load_retained_skg_snapshot(
    store: _RetainedSKGReadStore,
    ref: ArtifactRef,
) -> RetainedSKGSnapshotRecord:
    """Read the exact descriptor and verify its complete retained byte closure."""
    store = _require_retained_skg_read_store(store)
    return _load_retained_skg_snapshot(store, ref)


def retain_prepared_skg_read(
    store: _RetainedSKGStore,
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
    source_version_id = prepared.query.latest_skg_version_id()
    if source_version_id is None:
        raise RetainedSKGSnapshotError("retained_skg_source_version_missing")
    if (
        prepared.query.skg_snapshot_ref(version_id=source_version_id)
        != prepared.source_snapshot_ref
    ):
        raise RetainedSKGSnapshotError("retained_skg_source_version_binding_mismatch")
    if existing_ref is not None:
        snapshot = load_retained_skg_snapshot(store, existing_ref)
        if not isinstance(snapshot, RetainedSKGSnapshotV11):
            raise RetainedSKGSnapshotError("retained_skg_legacy_source_version_unbound")
        if (
            snapshot.source_sha256 != prepared.source_snapshot_sha256
            or snapshot.source_reference != prepared.source_snapshot_ref
            or snapshot.source_binding_schema_version != prepared.source_binding_schema_version
            or snapshot.query_version != prepared.query_version
            or snapshot.source_version_id != source_version_id
            or snapshot.version_identity_kind != "content_digest"
        ):
            raise RetainedSKGSnapshotError("retained_skg_existing_source_mismatch")
        if not prepared.source_generation_matches():
            raise RetainedSKGSnapshotError("retained_skg_source_changed")
        return existing_ref

    descriptor = os.open(
        prepared.db_path,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
    )
    chunks: list[RetainedSKGSnapshotChunk] = []
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
                return_selected_profile=True,
            )
            chunk_ref = _require_selected_written_ref(
                store,
                chunk_ref,
                kind=_CHUNK_KIND,
                media_type="application/octet-stream",
            )
            chunks.append(RetainedSKGSnapshotChunk(ref=chunk_ref, byte_size=len(payload)))
        if _file_identity(os.fstat(source.fileno())) != prepared.source_file_identity:
            raise RetainedSKGSnapshotError("retained_skg_source_changed")
    if (
        not prepared.source_generation_matches()
        or digest.hexdigest() != prepared.source_snapshot_sha256
        or total != prepared.source_file_identity[2]
    ):
        raise RetainedSKGSnapshotError("retained_skg_capture_digest_mismatch")
    snapshot = RetainedSKGSnapshotV11(
        schema_version=_SNAPSHOT_VERSION,
        source_reference=prepared.source_snapshot_ref,
        source_sha256=digest.hexdigest(),
        byte_size=total,
        source_binding_schema_version=prepared.source_binding_schema_version,
        query_version=prepared.query_version,
        source_version_id=source_version_id,
        version_identity_kind="content_digest",
        chunks=tuple(chunks),
    )
    options = replace(
        _write_options(_SNAPSHOT_KIND, "application/json"),
        inputs=[
            input_ref_from_artifact_ref(chunk.ref, role=f"source_chunk:{index}")
            for index, chunk in enumerate(chunks)
        ],
    )
    ref = store.put_json(
        snapshot.model_dump(mode="json"),
        options,
        return_selected_profile=True,
    )
    ref = _require_selected_written_ref(
        store,
        ref,
        kind=_SNAPSHOT_KIND,
        media_type="application/json",
    )
    if not prepared.source_generation_matches():
        raise RetainedSKGSnapshotError("retained_skg_source_changed_after_publication")
    return ref


def _require_local_file(path: Path, snapshot: RetainedSKGSnapshotRecord) -> None:
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


def retained_skg_snapshot_directory(trace_path: Path | None) -> Path:
    """Return the one run-local directory used for selected SKG snapshots."""
    if trace_path is None:
        raise RetainedSKGSnapshotError("retained_skg_run_path_required")
    return trace_path.parent / "skg-snapshots"


def _materialize_loaded_retained_skg_snapshot(
    store: _RetainedSKGReadStore,
    snapshot: RetainedSKGSnapshotRecord,
    *,
    directory: Path,
) -> Path:
    """Materialize a descriptor already verified from its selected CAS profile."""
    store = _require_retained_skg_read_store(store)
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


def materialize_retained_skg_snapshot(
    store: _RetainedSKGReadStore,
    ref: ArtifactRef,
    *,
    directory: Path,
) -> Path:
    """Restore retained bytes once, with no overwrite or fallback to the live DB."""
    snapshot = load_retained_skg_snapshot(store, ref)
    return _materialize_loaded_retained_skg_snapshot(store, snapshot, directory=directory)


def prepare_retained_skg_read(
    store: _RetainedSKGReadStore,
    ref: ArtifactRef,
    *,
    directory: Path,
    index_dir: Path,
) -> PreparedSKGRead:
    """Open the canonical reader and verify its selected retained byte binding."""
    return prepare_or_validate_retained_skg_read(
        store,
        ref,
        directory=directory,
        index_dir=index_dir,
    )


def prepare_or_validate_retained_skg_read(
    store: _RetainedSKGReadStore,
    ref: ArtifactRef,
    *,
    directory: Path,
    index_dir: Path,
    expected_path: Path | None = None,
    prepared_read: PreparedSKGRead | None = None,
) -> PreparedSKGRead:
    """Open or reconcile a reader against the descriptor actually selected from CAS.

    The expected digest/schema/query values are loaded from the profile-bound
    descriptor and its complete chunk closure. Caller-supplied paths or a live
    ``PreparedSKGRead`` never replace that selected basis.
    """
    from polisyos.data_forge.read_api.academic import PreparedSKGRead

    store = _require_retained_skg_read_store(store)
    if not isinstance(ref, ArtifactRef):
        raise RetainedSKGSnapshotError("retained_skg_descriptor_ref_required")
    if prepared_read is not None and type(prepared_read) is not PreparedSKGRead:
        raise RetainedSKGSnapshotError("retained_skg_prepared_read_type_required")

    snapshot = load_retained_skg_snapshot(store, ref)
    selected_path = directory.absolute() / f"{snapshot.source_sha256}.duckdb"
    if expected_path is not None and Path(expected_path).resolve() != selected_path.resolve():
        raise RetainedSKGSnapshotError("retained_skg_selected_path_mismatch")
    path = _materialize_loaded_retained_skg_snapshot(store, snapshot, directory=directory)

    owns_prepared_read = prepared_read is None
    active_read = (
        SKGQuery.prepare_read(db_path=path, index_dir=index_dir)
        if prepared_read is None
        else prepared_read
    )
    try:
        if (
            not active_read.matches_path(path)
            or active_read.source_snapshot_sha256 != snapshot.source_sha256
            or active_read.source_binding_schema_version != snapshot.source_binding_schema_version
            or active_read.query_version != snapshot.query_version
            or not active_read.source_generation_matches()
        ):
            raise RetainedSKGSnapshotError("retained_skg_prepared_source_mismatch")
    except BaseException:
        if owns_prepared_read:
            active_read.close()
        raise
    return active_read


def bind_retained_skg_source(
    store: _RetainedSKGReadStore,
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


def bind_retained_skg_workflow_input(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    record_run_input: bool = True,
) -> ExperimentState:
    """Bind an explicitly selected retained source at each workflow consumer intake.

    The complete typed descriptor remains in workflow state. Run owners record it
    once in the run manifest; per-node workers can bind with recording disabled
    when the workflow owner already admitted that input. A malformed supplied
    selector fails closed; only an absent selector preserves the live-source path.
    """
    if SNAPSHOT_INPUT_KEY not in state.inputs:
        return state
    ref = state.inputs[SNAPSHOT_INPUT_KEY]
    if not isinstance(ref, ArtifactRef):
        raise RetainedSKGSnapshotError("retained_skg_input_ref_required")
    store = _require_retained_skg_read_store(ctx.store)
    bound_state = bind_retained_skg_source(
        store,
        ref,
        state,
        directory=retained_skg_snapshot_directory(ctx.run.trace_path),
    )
    if record_run_input and ref not in ctx.run.run_manifest.inputs:
        ctx.run.add_input(ref)
    return bound_state
