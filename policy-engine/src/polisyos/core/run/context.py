"""Public run context module API."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import secrets
import stat
import threading
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from polisyos.common.logger import get_logger
from polisyos.common.serialization import fast_json_dumps

from ..artifacts import ManifestLifecycle, artifact_ref_identity_key
from ..artifacts._atomic_write import AtomicFileWriter
from ..artifacts.manifest import (
    ArtifactManifest,
    ArtifactRef,
    ArtifactTenantContextInfo,
    CanonInfo,
    EnvInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    WarningRecord,
)
from ..artifacts.protocol import _require_return_selected_profile_writer
from ..artifacts.write_contract import ArtifactWriteOptions
from ..canon import CanonSpec, content_hash, from_canonical_bytes, to_canonical_bytes
from ..trace import RunTerminality
from ..trace.record import TraceRecord, TraceRefs
from ..trace.sink import BatchTraceSink, JsonlTraceSink, TraceSink
from .manifest import (
    RunInvocationCompleted,
    RunInvocationImplementationIdentity,
    RunInvocationStarted,
    RunManifest,
    RunOwnerSnapshot,
    RunOwnerSnapshotV101,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from polisyos.core.run.worker_lifecycle import WorkerLifecycleCapability
    from polisyos.core.security.access_scope import AccessScope

    from ..artifacts.protocol import ArtifactStore

logger = get_logger(__name__)
_FINALIZE_JOURNAL_SCHEMA_VERSION = "1.0"
_FINALIZE_JOURNAL_NAME = ".finalize-journal.json"
_FINALIZE_LOCK_NAME = ".finalize.lock"
_RUN_FINALIZE_THREAD_LOCKS = tuple(threading.RLock() for _ in range(64))
_RUN_ACTIVE_LOCK_NAME = ".run-active.lock"
_RUN_OWNER_SNAPSHOT_KIND = "core.run_owner_snapshot"
_RUN_OWNER_SNAPSHOT_SCHEMA = "polisyos.core.RunOwnerSnapshot"
_RUN_OWNER_SNAPSHOT_SCHEMA_VERSION = "1.0.2"
_RUN_OWNER_SNAPSHOT_LEGACY_SCHEMA_VERSION = "1.0.1"
_RUN_OWNER_SNAPSHOT_CANON = CanonSpec(exclude_none=False)
_RUN_INVOCATION_RECORD_KIND = "core.run_invocation_attempt"
_RUN_INVOCATION_RECORD_SCHEMA = "polisyos.core.RunInvocationAttempt"
_RUN_INVOCATION_RECORD_CANON = CanonSpec(exclude_none=False)
_RUN_OWNER_SCOPE_CANON = CanonSpec(
    name="polisyos.core.run.owner-scope",
    version="1.0",
    forbid_floats=False,
    sort_keys=True,
)
_ACTIVE_RUN_THREAD_LOCKS: dict[Path, threading.Lock] = {}
_ACTIVE_RUN_THREAD_LOCKS_GUARD = threading.Lock()


class ChildRunStartUnknown(RuntimeError):  # noqa: N818 - stable unknown outcome
    """Private child start was attempted and may have persisted partial owner state."""

    def __init__(self, *, run_id: str, run_dir: Path) -> None:
        self.run_id = run_id
        self.run_dir = run_dir
        super().__init__("child_run_start_outcome_unknown")


class _FinalizeRecoveryError(ValueError):
    """A pending finalize journal cannot be reconciled from its durable facts."""


@contextmanager
def _run_finalize_lease(run_dir: Path) -> Iterator[None]:
    """Serialize durable finalization and recovery for one run directory.

    The lock file is permanent: unlinking it could let waiters lock different inodes.
    """
    try:
        lock_dir = run_dir.resolve(strict=True)
        import fcntl
    except (ImportError, OSError) as exc:
        raise _FinalizeRecoveryError("run_finalize_lock_unavailable") from exc
    if not lock_dir.is_dir():
        raise _FinalizeRecoveryError("run_finalize_lock_directory_invalid")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise _FinalizeRecoveryError("run_finalize_lock_no_follow_unavailable")

    # flock coordinates independent processes; local stripes also coordinate
    # threads on platforms where flock ownership is process-scoped.
    thread_gate = _RUN_FINALIZE_THREAD_LOCKS[hash(lock_dir) % len(_RUN_FINALIZE_THREAD_LOCKS)]
    with thread_gate:
        lock_path = lock_dir / _FINALIZE_LOCK_NAME
        try:
            AtomicFileWriter.write_once(lock_path, b"", durable_parent=True)
            flags = os.O_CREAT | os.O_RDWR | nofollow | getattr(os, "O_CLOEXEC", 0)
            descriptor = os.open(lock_path, flags, 0o600)
        except OSError as exc:
            raise _FinalizeRecoveryError("run_finalize_lock_unavailable") from exc
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise _FinalizeRecoveryError("run_finalize_lock_file_invalid")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
            except OSError as exc:
                raise _FinalizeRecoveryError("run_finalize_lock_unavailable") from exc
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


class _FcntlModule(Protocol):
    """The fcntl operations retained until a run execution lease is released."""

    LOCK_UN: int

    def flock(self, descriptor: int, operation: int) -> None: ...


class _RunExecutionLease:
    """Hold one run's writer lease until finalization, suspension, or process exit."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self._run_key: Path | None = None
        self._thread_lock: threading.Lock | None = None
        self._descriptor: int | None = None
        self._fcntl: _FcntlModule | None = None
        self._owner_pid: int | None = None

    def acquire(self) -> None:
        try:
            run_key = self.run_dir.resolve(strict=True)
            if not run_key.is_dir():
                raise _FinalizeRecoveryError("run_execution_lease_directory_invalid")
        except OSError as exc:
            raise _FinalizeRecoveryError("run_execution_lease_directory_invalid") from exc

        with _ACTIVE_RUN_THREAD_LOCKS_GUARD:
            local_lock = _ACTIVE_RUN_THREAD_LOCKS.get(run_key)
            if local_lock is None:
                local_lock = threading.Lock()
                _ACTIVE_RUN_THREAD_LOCKS[run_key] = local_lock
            if not local_lock.acquire(blocking=False):
                raise _FinalizeRecoveryError("run_execution_lease_busy")
        self._run_key = run_key
        self._thread_lock = local_lock

        try:
            import fcntl

            nofollow = getattr(os, "O_NOFOLLOW", 0)
            if not nofollow:
                raise _FinalizeRecoveryError("run_execution_lease_no_follow_unavailable")
            lock_path = run_key / _RUN_ACTIVE_LOCK_NAME
            AtomicFileWriter.write_once(lock_path, b"", durable_parent=True)
            flags = os.O_CREAT | os.O_RDWR | nofollow | getattr(os, "O_CLOEXEC", 0)
            descriptor = os.open(lock_path, flags, 0o600)
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                os.close(descriptor)
                raise _FinalizeRecoveryError("run_execution_lease_file_invalid")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                os.close(descriptor)
                if exc.errno in {errno.EACCES, errno.EAGAIN}:
                    raise _FinalizeRecoveryError("run_execution_lease_busy") from exc
                raise _FinalizeRecoveryError("run_execution_lease_unavailable") from exc
            self._owner_pid = os.getpid()
            self._fcntl = fcntl
            self._descriptor = descriptor
        except (ImportError, OSError) as exc:
            self._release_thread_lock()
            if isinstance(exc, _FinalizeRecoveryError):
                raise
            raise _FinalizeRecoveryError("run_execution_lease_unavailable") from exc
        except Exception:
            self._release_thread_lock()
            raise

    def require_owner_process(self) -> None:
        """Refuse terminal lifecycle changes from a process that inherited this lease."""
        if self._owner_pid != os.getpid():
            raise _FinalizeRecoveryError("run_execution_lease_inherited_process")

    def _release_thread_lock(self) -> None:
        run_key = self._run_key
        local_lock = self._thread_lock
        if run_key is None or local_lock is None:
            return
        with _ACTIVE_RUN_THREAD_LOCKS_GUARD:
            local_lock.release()
            if _ACTIVE_RUN_THREAD_LOCKS.get(run_key) is local_lock:
                del _ACTIVE_RUN_THREAD_LOCKS[run_key]
        self._run_key = None
        self._thread_lock = None

    def release(self) -> None:
        descriptor = self._descriptor
        fcntl = self._fcntl
        owner_pid = self._owner_pid
        self._descriptor = None
        self._fcntl = None
        self._owner_pid = None
        try:
            if descriptor is not None and fcntl is not None:
                try:
                    if owner_pid == os.getpid():
                        fcntl.flock(descriptor, fcntl.LOCK_UN)
                finally:
                    os.close(descriptor)
        finally:
            self._release_thread_lock()


@dataclass(frozen=True)
class _RunOwnerIdentity:
    """Lifecycle identity established by the canonical RUN_STARTED event."""

    run_id: str
    tenant_id: str | None
    cell_id: str | None


@dataclass(frozen=True)
class _RunInvocationAttempt:
    """One validated start basis and its optional engine-observed completion."""

    basis: RunInvocationStarted
    basis_ref: ArtifactRef
    outcome: RunInvocationCompleted | None
    outcome_ref: ArtifactRef | None


def _run_invocation_attempt_chain(
    store: ArtifactStore,
    *,
    tail_ref: ArtifactRef | None,
    run_manifest: RunManifest,
) -> list[_RunInvocationAttempt]:
    """Validate the complete owner-linked attempt sequence, rejecting forks/conflicts."""
    if tail_ref is None:
        return []

    def _ref_key(ref: ArtifactRef) -> tuple[str, str | None]:
        return str(ref.artifact_id), ref.manifest_profile_sha256

    reverse_records: list[tuple[ArtifactRef, RunInvocationStarted | RunInvocationCompleted]] = []
    seen_refs: set[tuple[str, str | None]] = set()
    current_ref: ArtifactRef | None = tail_ref
    while current_ref is not None:
        current_key = _ref_key(current_ref)
        if current_key in seen_refs:
            raise _FinalizeRecoveryError("run_invocation_record_cycle")
        seen_refs.add(current_key)
        current_record = _load_run_invocation_record(
            store,
            current_ref,
            run_manifest=run_manifest,
        )
        reverse_records.append((current_ref, current_record))
        current_ref = current_record.previous_record_ref
    records = list(reversed(reverse_records))
    starts: dict[tuple[str, str | None], tuple[ArtifactRef, RunInvocationStarted]] = {}
    completed_by_basis: dict[
        tuple[str, str | None], tuple[ArtifactRef, RunInvocationCompleted]
    ] = {}
    attempts: set[str] = set()
    prior_record_keys: set[tuple[str, str | None]] = set()
    for index, (record_ref, record) in enumerate(records):
        expected_previous = records[index - 1][0] if index else None
        if record.previous_record_ref != expected_previous:
            raise _FinalizeRecoveryError("run_invocation_record_chain_mismatch")
        if isinstance(record, RunInvocationStarted):
            record_key = _ref_key(record_ref)
            if record.attempt_id in attempts or record.run_id != run_manifest.run_id:
                raise _FinalizeRecoveryError("run_invocation_attempt_identity_conflict")
            attempts.add(record.attempt_id)
            starts[record_key] = (record_ref, record)
        else:
            basis_key = _ref_key(record.basis_ref)
            basis_pair = starts.get(basis_key)
            if (
                basis_pair is None
                or basis_key not in prior_record_keys
                or record.attempt_id != basis_pair[1].attempt_id
                or record.attempt_number != basis_pair[1].attempt_number
                or record.run_id != basis_pair[1].run_id
                or basis_key in completed_by_basis
            ):
                raise _FinalizeRecoveryError("run_invocation_attempt_completion_conflict")
            completed_by_basis[basis_key] = (record_ref, record)
        prior_record_keys.add(_ref_key(record_ref))
    return [
        _RunInvocationAttempt(
            basis=basis,
            basis_ref=basis_ref,
            outcome=completed_by_basis.get(_ref_key(basis_ref), (None, None))[1],
            outcome_ref=completed_by_basis.get(_ref_key(basis_ref), (None, None))[0],
        )
        for basis_ref, basis in starts.values()
    ]


class _AuditTraceSink(Protocol):
    """Trace sink protocol that also supports explicit shutdown."""

    def emit(self, rec: TraceRecord) -> None: ...

    def close(self) -> None: ...


def _run_manifest_write_options(
    run_manifest: RunManifest, *, selected_registry: bool = False
) -> ArtifactWriteOptions:
    tenant_context = _run_manifest_tenant_context(run_manifest)
    return ArtifactWriteOptions(
        kind="core.run_manifest",
        media_type="application/json",
        schema=SchemaInfo(name="polisyos.core.RunManifest", version="0.1.0"),
        producer=run_manifest.producer,
        env=run_manifest.env,
        inputs=[
            InputRef(
                artifact_id=run_manifest.registry_bundle.artifact_id,
                role="registry_bundle",
                manifest_profile_sha256=(
                    run_manifest.registry_bundle.manifest_profile_sha256
                    if selected_registry
                    else None
                ),
            )
        ],
        tenant_context=tenant_context,
    )


def _run_owner_snapshot_write_options(
    snapshot: RunOwnerSnapshot | RunOwnerSnapshotV101,
) -> ArtifactWriteOptions:
    tenant_context = _run_manifest_tenant_context(snapshot.run_manifest)
    inputs = [
        InputRef(
            artifact_id=snapshot.run_manifest.registry_bundle.artifact_id,
            role="registry_bundle",
            manifest_profile_sha256=(snapshot.run_manifest.registry_bundle.manifest_profile_sha256),
        )
    ]
    if snapshot.previous_snapshot_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=snapshot.previous_snapshot_ref.artifact_id,
                role="previous_owner_snapshot",
                manifest_profile_sha256=(snapshot.previous_snapshot_ref.manifest_profile_sha256),
            )
        )
    invocation_tail_ref = getattr(snapshot, "runtime_invocation_tail_ref", None)
    if invocation_tail_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=invocation_tail_ref.artifact_id,
                role="runtime_invocation_tail",
                manifest_profile_sha256=invocation_tail_ref.manifest_profile_sha256,
            )
        )
    canon = _RUN_OWNER_SNAPSHOT_CANON
    return ArtifactWriteOptions(
        kind=_RUN_OWNER_SNAPSHOT_KIND,
        media_type="application/json",
        schema=SchemaInfo(
            name=_RUN_OWNER_SNAPSHOT_SCHEMA,
            version=snapshot.schema_version,
        ),
        producer=snapshot.run_manifest.producer,
        env=snapshot.run_manifest.env,
        inputs=inputs,
        canon=CanonInfo.from_spec(canon),
        tenant_context=tenant_context,
    )


def _run_manifest_tenant_context(
    run_manifest: RunManifest,
) -> ArtifactTenantContextInfo | None:
    """Derive the artifact tenant profile only from durable run-owner fields."""
    if run_manifest.tenant_id is None:
        if run_manifest.cell_id is not None:
            raise _FinalizeRecoveryError("run_owner_tenant_context_owner_invalid")
        return None
    return ArtifactTenantContextInfo(
        tenant_id=run_manifest.tenant_id,
        cell_id=run_manifest.cell_id,
    )


def _owner_profile_options_for_persisted_manifest(
    store: ArtifactStore,
    *,
    ref: ArtifactRef,
    manifest: ArtifactManifest,
    options: ArtifactWriteOptions,
    mismatch_code: str,
) -> ArtifactWriteOptions:
    """Match a selected artifact profile to its payload-bound run owner.

    A selected pre-tenant profile can be replayed only when the exact raw,
    canonical manifest sidecar is available and binds the selected profile.
    Current profiles must carry the tenant context derived from the payload.
    """
    if manifest.child_release is not None:
        # The selected child marker is accepted only through the actual storage
        # owner. A manifest's own declaration cannot appoint a private scope.
        from ..artifacts.store import FileSystemCAS
        from .child_custody import _ManagedStore, _ParentProofReads

        if type(store) is _ManagedStore:
            store._require_owned_release_profile(ref, manifest)
            options = store._options(options)
        elif type(store) is _ParentProofReads:
            options = store._owned_release_options(ref, manifest, options)
        elif type(store) is FileSystemCAS:
            if store.get_manifest(ref) != manifest:
                raise _FinalizeRecoveryError("run_owner_child_release_profile_mismatch")
            store._require_child_manifest_release(manifest)
            options = replace(options, child_release=manifest.child_release)
        else:
            raise _FinalizeRecoveryError("run_owner_child_release_owner_not_established")
    expected_context = options.tenant_context
    if manifest.tenant_context == expected_context:
        return options
    if expected_context is None or manifest.tenant_context is not None:
        raise _FinalizeRecoveryError(mismatch_code)
    profile_sha256 = ref.manifest_profile_sha256
    raw_reader = getattr(store, "get_raw_manifest_bytes", None)
    if profile_sha256 is None or not callable(raw_reader):
        raise _FinalizeRecoveryError(f"{mismatch_code}_legacy_profile_not_proven")
    try:
        raw_manifest = raw_reader(ref, manifest_profile_sha256=profile_sha256)
    except (OSError, TypeError, ValueError, KeyError) as exc:
        raise _FinalizeRecoveryError(f"{mismatch_code}_legacy_profile_unavailable") from exc
    if (
        type(raw_manifest) is not bytes
        or raw_manifest != ManifestLifecycle.to_bytes(manifest)
        or ManifestLifecycle.profile_sha256(manifest) != profile_sha256
    ):
        raise _FinalizeRecoveryError(f"{mismatch_code}_legacy_profile_mismatch")
    return replace(options, tenant_context=None)


def _access_scope_sha256(access_scope: AccessScope | None) -> str | None:
    if access_scope is None:
        return None
    to_dict = getattr(access_scope, "to_dict", None)
    if not callable(to_dict):
        raise _FinalizeRecoveryError("run_owner_access_scope_not_established")
    return content_hash(
        to_canonical_bytes(to_dict(), _RUN_OWNER_SCOPE_CANON),
        prefix=True,
    )


def _run_invocation_record_write_options(
    record: RunInvocationStarted | RunInvocationCompleted,
    *,
    run_manifest: RunManifest,
) -> ArtifactWriteOptions:
    """Bind one invocation record to the exact full-profile owner edges."""
    refs: list[tuple[ArtifactRef, str]] = []
    if record.previous_record_ref is not None:
        refs.append((record.previous_record_ref, "previous_invocation_record"))
    if isinstance(record, RunInvocationStarted):
        refs.extend(
            [
                (record.workflow_spec_ref, "workflow_spec"),
                (record.input_state_ref, "input_state"),
            ]
        )
    else:
        refs.append((record.basis_ref, "attempt_basis"))
        if record.outcome_state_ref is not None:
            refs.append((record.outcome_state_ref, "outcome_state"))
        refs.extend(
            (ref, f"outcome_output_{index}") for index, ref in enumerate(record.output_refs)
        )
    return ArtifactWriteOptions(
        kind=_RUN_INVOCATION_RECORD_KIND,
        media_type="application/json",
        schema=SchemaInfo(
            name=_RUN_INVOCATION_RECORD_SCHEMA,
            version=record.schema_version,
        ),
        producer=run_manifest.producer,
        env=run_manifest.env,
        inputs=[
            InputRef(
                artifact_id=ref.artifact_id,
                role=role,
                manifest_profile_sha256=ref.manifest_profile_sha256,
            )
            for ref, role in refs
        ],
        canon=CanonInfo.from_spec(_RUN_INVOCATION_RECORD_CANON),
        tenant_context=_run_manifest_tenant_context(run_manifest),
    )


def _persist_run_invocation_record(
    store: ArtifactStore,
    record: RunInvocationStarted | RunInvocationCompleted,
    *,
    run_manifest: RunManifest,
) -> ArtifactRef:
    """Persist one immutable attempt record with its selected manifest profile."""
    _require_return_selected_profile_writer(store, "put_json")
    ref = store.put_json(
        record,
        _run_invocation_record_write_options(record, run_manifest=run_manifest),
        canon_spec=_RUN_INVOCATION_RECORD_CANON,
        return_selected_profile=True,
    )
    if ref.manifest_profile_sha256 is None:
        raise _FinalizeRecoveryError("run_invocation_record_profile_not_established")
    return ref


def _load_run_invocation_record(
    store: ArtifactStore,
    ref: ArtifactRef,
    *,
    run_manifest: RunManifest,
) -> RunInvocationStarted | RunInvocationCompleted:
    """Read back and content-bind one engine attempt record."""
    if (
        ref.kind != _RUN_INVOCATION_RECORD_KIND
        or ref.media_type != "application/json"
        or ref.manifest_profile_sha256 is None
    ):
        raise _FinalizeRecoveryError("run_invocation_record_ref_invalid")
    try:
        verification = store.verify(ref)
        if not verification.ok:
            raise _FinalizeRecoveryError("run_invocation_record_cas_invalid")
        payload = store.get_bytes(ref)
        artifact_manifest = store.get_manifest(ref)
        decoded = from_canonical_bytes(payload)
        if not isinstance(decoded, dict):
            raise _FinalizeRecoveryError("run_invocation_record_payload_invalid")
        record_type = decoded.get("record_type")
        record: RunInvocationStarted | RunInvocationCompleted
        if record_type == "started":
            record = RunInvocationStarted.model_validate(decoded)
        elif record_type == "completed":
            record = RunInvocationCompleted.model_validate(decoded)
        else:
            raise _FinalizeRecoveryError("run_invocation_record_type_invalid")
        expected_bytes = to_canonical_bytes(record, _RUN_INVOCATION_RECORD_CANON)
        if (
            payload != expected_bytes
            or content_hash(payload, prefix=True) != str(ref.artifact_id)
            or content_hash(expected_bytes, prefix=True) != str(ref.artifact_id)
            or record.run_id != run_manifest.run_id
        ):
            raise _FinalizeRecoveryError("run_invocation_record_content_mismatch")
        options = _run_invocation_record_write_options(record, run_manifest=run_manifest)
        profile_options = _owner_profile_options_for_persisted_manifest(
            store,
            ref=ref,
            manifest=artifact_manifest,
            options=options,
            mismatch_code="run_invocation_record_tenant_context_mismatch",
        )
        ManifestLifecycle.validate_profile(
            artifact_manifest,
            data_size=len(payload),
            opts=profile_options,
        )
        if artifact_manifest.inputs != profile_options.inputs:
            raise _FinalizeRecoveryError("run_invocation_record_lineage_mismatch")
        refs: list[ArtifactRef] = []
        if record.previous_record_ref is not None:
            refs.append(record.previous_record_ref)
        if isinstance(record, RunInvocationStarted):
            refs.extend([record.workflow_spec_ref, record.input_state_ref])
        else:
            refs.append(record.basis_ref)
            if record.outcome_state_ref is not None:
                refs.append(record.outcome_state_ref)
            refs.extend(record.output_refs)
        for linked_ref in refs:
            linked_verification = store.verify(linked_ref)
            if not linked_verification.ok:
                raise _FinalizeRecoveryError("run_invocation_record_linked_cas_invalid")
            linked_manifest = store.get_manifest(linked_ref)
            if linked_ref.manifest_profile_sha256 is not None and (
                ManifestLifecycle.profile_sha256(linked_manifest)
                != linked_ref.manifest_profile_sha256
            ):
                raise _FinalizeRecoveryError("run_invocation_record_linked_profile_mismatch")
    except _FinalizeRecoveryError:
        raise
    except (OSError, TypeError, ValueError, KeyError) as exc:
        raise _FinalizeRecoveryError("run_invocation_record_unreadable") from exc
    return record


def _persist_run_owner_snapshot(
    store: ArtifactStore,
    *,
    run_manifest: RunManifest,
    access_scope_sha256: str | None,
    previous_snapshot_ref: ArtifactRef | None,
    runtime_invocation_tail_ref: ArtifactRef | None = None,
) -> ArtifactRef:
    snapshot = RunOwnerSnapshot(
        schema_version=_RUN_OWNER_SNAPSHOT_SCHEMA_VERSION,
        run_manifest=run_manifest.model_copy(deep=True),
        access_scope_sha256=access_scope_sha256,
        previous_snapshot_ref=previous_snapshot_ref,
        runtime_invocation_tail_ref=runtime_invocation_tail_ref,
    )
    options = _run_owner_snapshot_write_options(snapshot)
    snapshot_ref = store.put_json(
        snapshot,
        options,
        canon_spec=_RUN_OWNER_SNAPSHOT_CANON,
        return_selected_profile=True,
    )
    _validate_run_owner_snapshot_ref(
        store,
        snapshot_ref,
        require_registry_profile=False,
    )
    return snapshot_ref


def _validate_run_owner_snapshot_ref(
    store: ArtifactStore,
    ref: ArtifactRef,
    *,
    require_registry_profile: bool = True,
) -> RunOwnerSnapshot | RunOwnerSnapshotV101:
    if (
        ref.kind != _RUN_OWNER_SNAPSHOT_KIND
        or ref.media_type != "application/json"
        or ref.manifest_profile_sha256 is None
    ):
        raise _FinalizeRecoveryError("run_resume_owner_snapshot_ref_invalid")
    try:
        verification = store.verify(ref)
        if not verification.ok:
            raise _FinalizeRecoveryError("run_resume_owner_snapshot_cas_invalid")
        payload = store.get_bytes(ref)
        artifact_manifest = store.get_manifest(ref)
        decoded = from_canonical_bytes(payload)
        if not isinstance(decoded, dict):
            raise _FinalizeRecoveryError("run_resume_owner_snapshot_payload_invalid")
        snapshot: RunOwnerSnapshot | RunOwnerSnapshotV101
        try:
            snapshot_version = decoded.get("schema_version")
            if snapshot_version == _RUN_OWNER_SNAPSHOT_LEGACY_SCHEMA_VERSION:
                snapshot = RunOwnerSnapshotV101.model_validate(decoded)
            elif snapshot_version == _RUN_OWNER_SNAPSHOT_SCHEMA_VERSION:
                snapshot = RunOwnerSnapshot.model_validate(decoded)
            else:
                raise ValueError("run_owner_snapshot_schema_version_unsupported")
        except (TypeError, ValueError) as exc:
            raise _FinalizeRecoveryError("run_resume_owner_snapshot_schema_invalid") from exc
        expected_bytes = to_canonical_bytes(snapshot, _RUN_OWNER_SNAPSHOT_CANON)
        if (
            payload != expected_bytes
            or content_hash(payload, prefix=True) != str(ref.artifact_id)
            or content_hash(expected_bytes, prefix=True) != str(ref.artifact_id)
        ):
            raise _FinalizeRecoveryError("run_resume_owner_snapshot_content_mismatch")
        options = _run_owner_snapshot_write_options(snapshot)
        profile_options = _owner_profile_options_for_persisted_manifest(
            store,
            ref=ref,
            manifest=artifact_manifest,
            options=options,
            mismatch_code="run_resume_owner_snapshot_tenant_context_mismatch",
        )
        ManifestLifecycle.validate_profile(
            artifact_manifest,
            data_size=len(payload),
            opts=profile_options,
        )
        if artifact_manifest.inputs != profile_options.inputs:
            raise _FinalizeRecoveryError("run_resume_owner_snapshot_lineage_mismatch")
        invocation_tail_ref = getattr(snapshot, "runtime_invocation_tail_ref", None)
        if invocation_tail_ref is not None:
            _load_run_invocation_record(
                store,
                invocation_tail_ref,
                run_manifest=snapshot.run_manifest,
            )
        registry_ref = snapshot.run_manifest.registry_bundle
        if require_registry_profile and registry_ref.manifest_profile_sha256 is None:
            raise _FinalizeRecoveryError("run_resume_registry_profile_not_established")
        if not store.verify(registry_ref).ok:
            raise _FinalizeRecoveryError("run_resume_registry_cas_invalid")
        store.get_manifest(registry_ref)
    except _FinalizeRecoveryError:
        raise
    except (OSError, TypeError, ValueError, KeyError) as exc:
        raise _FinalizeRecoveryError("run_resume_owner_snapshot_proof_unavailable") from exc
    manifest = snapshot.run_manifest
    if (
        snapshot.schema_version
        not in {
            _RUN_OWNER_SNAPSHOT_SCHEMA_VERSION,
            _RUN_OWNER_SNAPSHOT_LEGACY_SCHEMA_VERSION,
        }
        or manifest.status != "running"
        or manifest.finished_at is not None
        or manifest.trace_ref is not None
        or manifest.started_at.tzinfo is None
        or manifest.started_at.utcoffset() is None
        or manifest.started_at > datetime.now(UTC)
    ):
        raise _FinalizeRecoveryError("run_resume_owner_snapshot_state_invalid")
    return snapshot


def _read_incomplete_run_trace(
    run_dir: Path,
    *,
    run_id: str,
    allow_incomplete_worker_invocation_id: str | None = None,
) -> tuple[list[TraceRecord], TraceRecord]:
    if os.path.lexists(_finalize_journal_path(run_dir)):
        raise _FinalizeRecoveryError("run_resume_finalize_journal_conflict")
    trace_path = run_dir / "trace.jsonl"
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        if not getattr(os, "O_NOFOLLOW", 0):
            raise _FinalizeRecoveryError("run_resume_trace_no_follow_unavailable")
        descriptor = os.open(trace_path, flags)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise _FinalizeRecoveryError("run_resume_trace_file_invalid")
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except _FinalizeRecoveryError:
        raise
    except (OSError, UnicodeError) as exc:
        raise _FinalizeRecoveryError("run_resume_trace_unreadable") from exc
    records: list[TraceRecord] = []
    try:
        records = [TraceRecord.model_validate_json(line) for line in lines if line.strip()]
    except (TypeError, ValueError) as exc:
        raise _FinalizeRecoveryError("run_resume_trace_record_invalid") from exc
    starts = [
        record for record in records if record.phase == "core" and record.event == "RUN_STARTED"
    ]
    if (
        len(starts) != 1
        or not records
        or records[0] is not starts[0]
        or starts[0].run_id != run_id
        or starts[0].run_terminality is not RunTerminality.NON_TERMINAL
    ):
        raise _FinalizeRecoveryError("run_resume_trace_owner_fact_invalid")
    owner = starts[0]
    for record in records:
        if (
            record.run_id != owner.run_id
            or record.tenant_id != owner.tenant_id
            or record.cell_id != owner.cell_id
            or record.run_terminality is RunTerminality.TERMINAL
            or record.run_terminality is RunTerminality.NOT_ESTABLISHED
            or (record.phase == "core" and record.event == "RUN_FINALIZED")
        ):
            raise _FinalizeRecoveryError("run_resume_trace_not_incomplete")
    _validate_worker_receipt_history(
        records,
        allow_incomplete_invocation_id=allow_incomplete_worker_invocation_id,
    )
    return records, owner


def _worker_trace_digest(records: Sequence[TraceRecord]) -> str:
    """Hash the exact JSONL bytes used for one parent-admitted worker event set."""
    digest = hashlib.sha256()
    for record in records:
        digest.update(record.model_dump_json(exclude_none=True).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _validate_worker_receipt_history(
    records: Sequence[TraceRecord],
    *,
    allow_incomplete_invocation_id: str | None = None,
) -> None:
    """Verify durable worker receipt markers against their exact event bodies.

    A JSONL append can leave a complete-record prefix. Only the live parent
    admission path may reconcile that prefix, and it must present the exact
    still-pending dispatch. Resume and finalization reject it because they do
    not possess the worker's original receipt.
    """
    grouped: dict[str, list[TraceRecord]] = {}
    for record in records:
        invocation_id = record.worker_invocation_id
        dispatch_digest = record.worker_dispatch_sha256
        has_receipt_fields = (
            invocation_id is not None
            or dispatch_digest is not None
            or record.worker_receipt_phase is not None
            or record.worker_receipt_count is not None
            or record.worker_receipt_sha256 is not None
        )
        if not has_receipt_fields:
            continue
        if invocation_id is None or dispatch_digest is None:
            raise _FinalizeRecoveryError("worker_receipt_dispatch_binding_invalid")
        grouped.setdefault(invocation_id, []).append(record)

    for invocation_id, receipt_records in grouped.items():
        started = [record for record in receipt_records if record.worker_receipt_phase == "started"]
        completed = [
            record for record in receipt_records if record.worker_receipt_phase == "completed"
        ]
        if len(started) != 1 or len(completed) > 1:
            raise _FinalizeRecoveryError("worker_receipt_marker_conflict")
        start_marker = started[0]
        if (
            receipt_records[0] is not start_marker
            or start_marker.phase != "core"
            or start_marker.event != "WORKER_INVOCATION_STARTED"
            or start_marker.run_terminality is not None
            or start_marker.worker_receipt_count is None
            or start_marker.worker_receipt_sha256 is None
            or len(start_marker.refs.inputs) != 1
            or start_marker.refs.outputs
        ):
            raise _FinalizeRecoveryError("worker_receipt_start_marker_invalid")

        events = [record for record in receipt_records if record.worker_receipt_phase is None]
        for record in receipt_records:
            if (
                record.worker_invocation_id != invocation_id
                or record.worker_dispatch_sha256 != start_marker.worker_dispatch_sha256
                or record.worker_receipt_count not in {None, start_marker.worker_receipt_count}
                or record.worker_receipt_sha256 not in {None, start_marker.worker_receipt_sha256}
            ):
                raise _FinalizeRecoveryError("worker_receipt_marker_binding_mismatch")
        if any(record.worker_receipt_phase == "started" for record in events):
            raise _FinalizeRecoveryError("worker_receipt_marker_conflict")
        for record in events:
            if record.run_terminality is not None:
                raise _FinalizeRecoveryError("worker_receipt_event_authority_invalid")

        if completed:
            completed_marker = completed[0]
            if (
                receipt_records[-1] is not completed_marker
                or completed_marker.phase != "core"
                or completed_marker.event != "WORKER_INVOCATION_COMPLETED"
                or completed_marker.run_terminality is not None
                or completed_marker.refs.inputs != start_marker.refs.inputs
                or completed_marker.refs.outputs
                or completed_marker.worker_receipt_count != start_marker.worker_receipt_count
                or completed_marker.worker_receipt_sha256 != start_marker.worker_receipt_sha256
                or len(events) != start_marker.worker_receipt_count
                or _worker_trace_digest(events) != start_marker.worker_receipt_sha256
            ):
                raise _FinalizeRecoveryError("worker_receipt_completed_body_mismatch")
        elif invocation_id != allow_incomplete_invocation_id:
            raise _FinalizeRecoveryError("worker_receipt_incomplete")
        elif len(events) > start_marker.worker_receipt_count:
            raise _FinalizeRecoveryError("worker_receipt_prefix_count_mismatch")


_WORKER_MANIFEST_UPDATE_FIELDS = frozenset(
    {
        "execution_profile",
        "control_job_id",
        "capability_manifest_ref",
        "environment_manifest_ref",
        "sbom_ref",
        "tee_attestation_ref",
    }
)
_WORKER_RUN_OPERATION_EVENTS = frozenset(
    {"RUN_INPUT_ADDED", "RUN_OUTPUT_ADDED", "RUN_CONTEXT_SNAPSHOT"}
)


def _apply_worker_run_operation(
    store: ArtifactStore,
    *,
    manifest: RunManifest,
    owner_snapshot_ref: ArtifactRef,
    access_scope_sha256: str | None,
    record: TraceRecord,
) -> tuple[RunManifest, ArtifactRef]:
    """Apply one typed worker-emitted RunContext operation to a candidate state."""
    if record.event == "RUN_INPUT_ADDED":
        if record.phase != "core" or len(record.refs.inputs) != 1 or record.refs.outputs:
            raise _FinalizeRecoveryError("worker_merge_input_operation_invalid")
        manifest.inputs.append(record.refs.inputs[0])
        return manifest, owner_snapshot_ref
    if record.event == "RUN_OUTPUT_ADDED":
        if record.phase != "core" or record.refs.inputs or len(record.refs.outputs) != 1:
            raise _FinalizeRecoveryError("worker_merge_output_operation_invalid")
        manifest.outputs.append(record.refs.outputs[0])
        return manifest, owner_snapshot_ref
    if record.event != "RUN_CONTEXT_SNAPSHOT":
        return manifest, owner_snapshot_ref
    if record.phase != "core" or record.refs.inputs or len(record.refs.outputs) != 1:
        raise _FinalizeRecoveryError("worker_merge_snapshot_operation_invalid")
    next_owner_ref = record.refs.outputs[0]
    try:
        snapshot = _validate_run_owner_snapshot_ref(
            store,
            next_owner_ref,
            require_registry_profile=False,
        )
    except _FinalizeRecoveryError as exc:
        raise _FinalizeRecoveryError("worker_merge_snapshot_operation_unverified") from exc
    if (
        snapshot.previous_snapshot_ref != owner_snapshot_ref
        or snapshot.access_scope_sha256 != access_scope_sha256
    ):
        raise _FinalizeRecoveryError("worker_merge_snapshot_operation_chain_mismatch")
    current_snapshot = _validate_run_owner_snapshot_ref(
        store,
        owner_snapshot_ref,
        require_registry_profile=False,
    )
    if getattr(snapshot, "runtime_invocation_tail_ref", None) != getattr(
        current_snapshot,
        "runtime_invocation_tail_ref",
        None,
    ):
        raise _FinalizeRecoveryError("worker_merge_invocation_tail_update_forbidden")
    current = manifest.model_dump(mode="python", by_alias=True, exclude_none=False)
    updated = snapshot.run_manifest.model_dump(mode="python", by_alias=True, exclude_none=False)
    changed_fields = {name for name in current if current[name] != updated[name]}
    if not changed_fields or changed_fields - _WORKER_MANIFEST_UPDATE_FIELDS:
        raise _FinalizeRecoveryError("worker_merge_snapshot_operation_fields_invalid")
    return snapshot.run_manifest.model_copy(deep=True), next_owner_ref


def _run_owner_snapshot_chain(
    store: ArtifactStore,
    *,
    records: list[TraceRecord],
    started: TraceRecord,
    allow_incomplete_worker_invocation_id: str | None = None,
) -> tuple[RunOwnerSnapshot | RunOwnerSnapshotV101, ArtifactRef, int]:
    if started.refs.inputs or len(started.refs.outputs) != 1:
        raise _FinalizeRecoveryError("run_resume_owner_snapshot_ref_invalid")
    owner_ref = started.refs.outputs[0]
    snapshot = _validate_run_owner_snapshot_ref(store, owner_ref)
    if snapshot.previous_snapshot_ref is not None:
        raise _FinalizeRecoveryError("run_resume_owner_snapshot_chain_invalid")
    if (
        started.ts.tzinfo is None
        or started.ts.utcoffset() is None
        or started.ts > datetime.now(UTC)
        or snapshot.run_manifest.started_at != started.ts
    ):
        raise _FinalizeRecoveryError("run_resume_owner_snapshot_time_mismatch")
    if (
        snapshot.run_manifest.run_id != started.run_id
        or snapshot.run_manifest.tenant_id != started.tenant_id
        or snapshot.run_manifest.cell_id != started.cell_id
    ):
        raise _FinalizeRecoveryError("run_resume_owner_snapshot_scope_mismatch")
    if snapshot.run_manifest.inputs or snapshot.run_manifest.outputs:
        raise _FinalizeRecoveryError("run_resume_initial_manifest_refs_invalid")
    inputs: list[ArtifactRef] = []
    outputs: list[ArtifactRef] = []
    last_snapshot_index = 0
    for index, record in enumerate(records[1:], start=1):
        if (
            allow_incomplete_worker_invocation_id is not None
            and record.worker_invocation_id == allow_incomplete_worker_invocation_id
        ):
            if record.worker_receipt_phase == "started" and record.refs.inputs != [owner_ref]:
                raise _FinalizeRecoveryError("run_resume_worker_receipt_owner_mismatch")
            continue
        if record.event == "RUN_INPUT_ADDED":
            if record.phase != "core" or len(record.refs.inputs) != 1 or record.refs.outputs:
                raise _FinalizeRecoveryError("run_resume_input_event_invalid")
            inputs.extend(record.refs.inputs)
        elif record.event == "RUN_OUTPUT_ADDED":
            if record.phase != "core" or len(record.refs.outputs) != 1 or record.refs.inputs:
                raise _FinalizeRecoveryError("run_resume_output_event_invalid")
            outputs.extend(record.refs.outputs)
        elif record.event == "RUN_CONTEXT_SNAPSHOT":
            if record.phase != "core" or record.refs.inputs or len(record.refs.outputs) != 1:
                raise _FinalizeRecoveryError("run_resume_owner_snapshot_event_invalid")
            next_ref = record.refs.outputs[0]
            next_snapshot = _validate_run_owner_snapshot_ref(store, next_ref)
            previous = next_snapshot.previous_snapshot_ref
            if previous != owner_ref:
                raise _FinalizeRecoveryError("run_resume_owner_snapshot_chain_invalid")
            previous_invocation_tail = getattr(snapshot, "runtime_invocation_tail_ref", None)
            next_invocation_tail = getattr(next_snapshot, "runtime_invocation_tail_ref", None)
            if next_invocation_tail != previous_invocation_tail:
                if next_invocation_tail is None:
                    raise _FinalizeRecoveryError("run_resume_invocation_tail_rewound")
                next_invocation_record = _load_run_invocation_record(
                    store,
                    next_invocation_tail,
                    run_manifest=next_snapshot.run_manifest,
                )
                if next_invocation_record.previous_record_ref != previous_invocation_tail:
                    raise _FinalizeRecoveryError("run_resume_invocation_tail_chain_invalid")
            before = snapshot.run_manifest
            after = next_snapshot.run_manifest
            immutable_fields = (
                "run_id",
                "started_at",
                "producer",
                "env",
                "registry_bundle",
                "tenant_id",
                "cell_id",
                "seed",
                "parent_run_id",
                "replay_source_ref",
            )
            if (
                any(getattr(before, name) != getattr(after, name) for name in immutable_fields)
                or next_snapshot.access_scope_sha256 != snapshot.access_scope_sha256
                or after.inputs != inputs
                or after.outputs != outputs
            ):
                raise _FinalizeRecoveryError("run_resume_owner_snapshot_binding_mismatch")
            snapshot = next_snapshot
            owner_ref = next_ref
            last_snapshot_index = index
        elif record.phase == "core" and record.event in {"RUN_INPUT_ADDED", "RUN_OUTPUT_ADDED"}:
            raise _FinalizeRecoveryError("run_resume_manifest_event_phase_invalid")
    return snapshot, owner_ref, last_snapshot_index


def _finalize_journal_path(run_dir: Path) -> Path:
    return run_dir / _FINALIZE_JOURNAL_NAME


def _write_finalize_journal(run_dir: Path, run_manifest: RunManifest) -> None:
    payload = {
        "schema_version": _FINALIZE_JOURNAL_SCHEMA_VERSION,
        "run_manifest": run_manifest.model_dump(mode="json"),
    }
    AtomicFileWriter.write_atomic(
        _finalize_journal_path(run_dir),
        (fast_json_dumps(payload, sort_keys=True) + "\n").encode("utf-8"),
    )


def _clear_finalize_journal(run_dir: Path) -> None:
    _finalize_journal_path(run_dir).unlink(missing_ok=True)


def _load_finalize_journal(run_dir: Path) -> RunManifest | None:
    journal_path = _finalize_journal_path(run_dir)
    if not journal_path.exists():
        return None
    try:
        payload = json.loads(journal_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        logger.warning("Ignoring unreadable finalize journal for %s: %s", run_dir, exc)
        return None
    if not isinstance(payload, dict):
        logger.warning("Ignoring non-object finalize journal for %s", run_dir)
        return None
    if payload.get("schema_version") != _FINALIZE_JOURNAL_SCHEMA_VERSION:
        logger.warning("Ignoring unsupported finalize journal version for %s", run_dir)
        return None
    run_manifest_payload = payload.get("run_manifest")
    if not isinstance(run_manifest_payload, dict):
        logger.warning("Ignoring malformed finalize journal for %s", run_dir)
        return None
    try:
        return RunManifest.model_validate(run_manifest_payload)
    except (TypeError, ValueError) as exc:
        logger.warning("Ignoring invalid finalize journal for %s: %s", run_dir, exc)
        return None


def _trace_terminal_run_finalized_ref(
    trace_path: Path,
    *,
    owner: _RunOwnerIdentity,
    expected_workflow_finalization_ref: ArtifactRef | None = None,
) -> ArtifactRef | None:
    """Read one terminal fact and, when supplied, its exact workflow transition input."""
    try:
        lines = trace_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise _FinalizeRecoveryError("run_finalize_trace_unreadable") from exc

    records: list[TraceRecord] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            records.append(TraceRecord.model_validate_json(line))
        except (TypeError, ValueError) as exc:
            raise _FinalizeRecoveryError("run_finalize_trace_record_invalid") from exc
    if not records:
        raise _FinalizeRecoveryError("run_finalize_trace_empty")

    starts = [
        record for record in records if record.phase == "core" and record.event == "RUN_STARTED"
    ]
    if (
        len(starts) != 1
        or records[0] is not starts[0]
        or starts[0].run_terminality is not RunTerminality.NON_TERMINAL
    ):
        raise _FinalizeRecoveryError("run_finalize_trace_owner_fact_invalid")
    for record in records:
        if (
            record.run_id != owner.run_id
            or record.tenant_id != owner.tenant_id
            or record.cell_id != owner.cell_id
        ):
            raise _FinalizeRecoveryError("run_finalize_trace_owner_scope_mismatch")
    _validate_worker_receipt_history(records)

    finalized = [
        record for record in records if record.phase == "core" and record.event == "RUN_FINALIZED"
    ]
    if not finalized:
        if any(record.run_terminality is RunTerminality.TERMINAL for record in records):
            raise _FinalizeRecoveryError("run_finalize_trace_terminal_fact_ambiguous")
        return None
    if len(finalized) != 1 or records[-1] is not finalized[0]:
        raise _FinalizeRecoveryError("run_finalize_trace_duplicate_terminal_fact")
    if any(record.run_terminality is RunTerminality.TERMINAL for record in records[:-1]):
        raise _FinalizeRecoveryError("run_finalize_trace_intermediate_terminal_fact")

    terminal = finalized[0]
    if terminal.run_terminality is not RunTerminality.TERMINAL:
        raise _FinalizeRecoveryError("run_finalize_trace_terminality_not_established")
    if expected_workflow_finalization_ref is not None and terminal.refs.inputs != [
        expected_workflow_finalization_ref
    ]:
        raise _FinalizeRecoveryError("run_finalize_workflow_finalization_not_established")
    manifest_outputs = [
        output for output in terminal.refs.outputs if output.kind == "core.run_manifest"
    ]
    if len(manifest_outputs) != 1 or manifest_outputs[0].media_type != "application/json":
        raise _FinalizeRecoveryError("run_finalize_trace_manifest_ref_invalid")
    return manifest_outputs[0]


def _validate_terminal_run_manifest_ref(
    store: ArtifactStore,
    *,
    run_manifest: RunManifest,
    run_ref: ArtifactRef,
    require_selected_profile: bool,
) -> None:
    """Bind an existing terminal ref to the exact journal payload and write contract."""
    options = _run_manifest_write_options(run_manifest)
    profile_options = replace(options, canon=CanonInfo.from_spec(CanonSpec()))
    if (
        run_ref.kind != options.kind
        or run_ref.media_type != options.media_type
        or (
            (require_selected_profile or options.tenant_context is not None)
            and run_ref.manifest_profile_sha256 is None
        )
    ):
        raise _FinalizeRecoveryError("run_finalize_manifest_ref_contract_mismatch")

    try:
        verification = store.verify(run_ref)
        if not verification.ok:
            raise _FinalizeRecoveryError("run_finalize_manifest_cas_verification_failed")
        artifact_manifest = store.get_manifest(run_ref)
        if artifact_manifest.child_release is not None:
            options = _run_manifest_write_options(run_manifest, selected_registry=True)
            profile_options = replace(options, canon=CanonInfo.from_spec(CanonSpec()))
        expected_bytes = to_canonical_bytes(run_manifest, CanonSpec())
        manifest_bytes = store.get_bytes(run_ref)
    except _FinalizeRecoveryError:
        raise
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise _FinalizeRecoveryError("run_finalize_manifest_proof_unavailable") from exc

    if (
        manifest_bytes != expected_bytes
        or content_hash(manifest_bytes, prefix=True) != str(run_ref.artifact_id)
        or content_hash(expected_bytes, prefix=True) != str(run_ref.artifact_id)
    ):
        raise _FinalizeRecoveryError("run_finalize_manifest_journal_binding_mismatch")
    try:
        profile_options = _owner_profile_options_for_persisted_manifest(
            store,
            ref=run_ref,
            manifest=artifact_manifest,
            options=profile_options,
            mismatch_code="run_finalize_manifest_tenant_context_mismatch",
        )
        ManifestLifecycle.validate_profile(
            artifact_manifest,
            data_size=len(manifest_bytes),
            opts=profile_options,
        )
    except ValueError as exc:
        raise _FinalizeRecoveryError("run_finalize_manifest_write_profile_mismatch") from exc


def _trace_run_started_identity(trace_path: Path) -> _RunOwnerIdentity | None:
    if not trace_path.exists():
        return None
    owners: set[_RunOwnerIdentity] = set()
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = TraceRecord.model_validate_json(line)
        except TypeError, ValueError:
            return None
        if record.phase == "core" and record.event == "RUN_STARTED":
            if record.run_terminality not in {None, RunTerminality.NON_TERMINAL}:
                return None
            owners.add(
                _RunOwnerIdentity(
                    run_id=record.run_id,
                    tenant_id=record.tenant_id,
                    cell_id=record.cell_id,
                )
            )
    if len(owners) != 1:
        return None
    return next(iter(owners))


def _record_recovered_run_manifest_owner(
    store: ArtifactStore,
    *,
    run_manifest: RunManifest,
    run_ref: ArtifactRef,
) -> None:
    if not run_manifest.tenant_id:
        return
    recorder = getattr(store, "record_artifact_owner", None)
    if callable(recorder):
        recorder(
            run_ref.artifact_id,
            tenant_id=run_manifest.tenant_id,
            cell_id=run_manifest.cell_id,
            writer="recover_pending_run_finalize.manifest",
        )


def _finalize_request_matches(
    run_manifest: RunManifest,
    *,
    status: str,
    errors: list[dict[str, object]] | None,
) -> bool:
    """Return whether a retry repeats the already durable terminal request."""
    if run_manifest.status != status:
        return False
    if not errors:
        return True
    return len(errors) <= len(run_manifest.errors) and run_manifest.errors[-len(errors) :] == errors


def _append_run_finalized_event(
    *,
    trace_path: Path,
    run_manifest: RunManifest,
    run_ref: ArtifactRef,
) -> None:
    JsonlTraceSink(trace_path).emit(
        TraceRecord(
            run_id=run_manifest.run_id,
            phase="core",
            event="RUN_FINALIZED",
            run_terminality=RunTerminality.TERMINAL,
            tenant_id=run_manifest.tenant_id,
            cell_id=run_manifest.cell_id,
            refs=TraceRefs(outputs=[run_ref]),
            metrics={"status_ok": 1 if run_manifest.status == "ok" else 0},
        )
    )


def _recover_pending_run_finalize_locked(
    store: ArtifactStore,
    run_dir: Path,
) -> ArtifactRef | None:
    """Resume a journal while the caller holds this run's exclusive lease."""
    journal_path = _finalize_journal_path(run_dir)
    if not journal_path.exists():
        return None
    run_manifest = _load_finalize_journal(run_dir)
    if run_manifest is None:
        raise _FinalizeRecoveryError("run_finalize_journal_not_established")

    trace_path = run_dir / "trace.jsonl"
    try:
        trace_owner = _trace_run_started_identity(trace_path)
    except (OSError, UnicodeError) as exc:
        raise _FinalizeRecoveryError("run_finalize_trace_owner_unreadable") from exc
    if trace_owner is None:
        raise _FinalizeRecoveryError("run_finalize_trace_owner_not_established")
    journal_owner = _RunOwnerIdentity(
        run_id=run_manifest.run_id,
        tenant_id=run_manifest.tenant_id,
        cell_id=run_manifest.cell_id,
    )
    if journal_owner != trace_owner:
        raise _FinalizeRecoveryError("run_finalize_journal_owner_scope_mismatch")

    # Inspect the append-only terminal fact before any CAS write. It owns the
    # reference already emitted by the old or current writer; never replace it
    # with a same-ID ref selected by a later write.
    existing_ref = _trace_terminal_run_finalized_ref(trace_path, owner=trace_owner)
    if existing_ref is not None:
        _validate_terminal_run_manifest_ref(
            store,
            run_manifest=run_manifest,
            run_ref=existing_ref,
            require_selected_profile=False,
        )
        if existing_ref.manifest_profile_sha256 is None:
            logger.warning(
                "Retaining the verified profileless terminal ref for legacy run %s; "
                "recovery does not establish a selected profile",
                run_manifest.run_id,
            )
        _clear_finalize_journal(run_dir)
        return existing_ref

    run_ref = store.put_json(
        run_manifest,
        _run_manifest_write_options(run_manifest),
        return_selected_profile=True,
    )
    _validate_terminal_run_manifest_ref(
        store,
        run_manifest=run_manifest,
        run_ref=run_ref,
        require_selected_profile=True,
    )
    _record_recovered_run_manifest_owner(
        store,
        run_manifest=run_manifest,
        run_ref=run_ref,
    )
    _append_run_finalized_event(
        trace_path=trace_path,
        run_manifest=run_manifest,
        run_ref=run_ref,
    )
    _clear_finalize_journal(run_dir)
    return run_ref


def recover_pending_run_finalize(store: ArtifactStore, run_dir: Path) -> ArtifactRef | None:
    """Resume a journal under the run-scoped cross-process finalization lease."""
    journal_path = _finalize_journal_path(run_dir)
    lock_path = run_dir / _FINALIZE_LOCK_NAME
    if not journal_path.exists() and not lock_path.exists():
        return None
    with _run_finalize_lease(run_dir):
        return _recover_pending_run_finalize_locked(store, run_dir)


def _read_run_trace_bytes(path: Path, *, failure_code: str) -> bytes:
    """Read one regular trace file without following a replaced path."""
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise _FinalizeRecoveryError(failure_code)
    flags = os.O_RDONLY | nofollow | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise _FinalizeRecoveryError(failure_code)
        with os.fdopen(descriptor, "rb") as handle:
            return handle.read()
    except _FinalizeRecoveryError:
        raise
    except OSError as exc:
        raise _FinalizeRecoveryError(failure_code) from exc


def new_run_id() -> str:
    """New run ID helper."""
    return "R_" + secrets.token_hex(8)


def _read_run_owner_records(
    store: ArtifactStore,
    trace_path: Path,
    *,
    run_id: str,
) -> tuple[list[TraceRecord], RunOwnerSnapshot | RunOwnerSnapshotV101, int]:
    """Read and validate the persisted Core owner trace and snapshot chain."""
    trace_bytes = _read_run_trace_bytes(
        trace_path,
        failure_code="run_invocation_trace_unreadable",
    )
    try:
        records = [
            TraceRecord.model_validate_json(line)
            for line in trace_bytes.decode("utf-8").splitlines()
            if line.strip()
        ]
    except (TypeError, UnicodeError, ValueError) as exc:
        raise _FinalizeRecoveryError("run_invocation_trace_invalid") from exc
    starts = [
        record for record in records if record.phase == "core" and record.event == "RUN_STARTED"
    ]
    if (
        len(starts) != 1
        or not records
        or records[0] is not starts[0]
        or starts[0].run_id != run_id
        or starts[0].run_terminality is not RunTerminality.NON_TERMINAL
    ):
        raise _FinalizeRecoveryError("run_invocation_trace_owner_invalid")
    started = starts[0]
    for record in records:
        if (
            record.run_id != started.run_id
            or record.tenant_id != started.tenant_id
            or record.cell_id != started.cell_id
        ):
            raise _FinalizeRecoveryError("run_invocation_trace_scope_mismatch")
    snapshot, _, last_snapshot_index = _run_owner_snapshot_chain(
        store,
        records=records,
        started=started,
    )
    return records, snapshot, last_snapshot_index


def _read_runtime_invocation_attempts(
    store: ArtifactStore,
    trace_path: Path,
    *,
    run_id: str,
) -> list[_RunInvocationAttempt]:
    """Read attempt bases from a fresh CAS/trace view, without producer memory."""
    _, snapshot, _ = _read_run_owner_records(store, trace_path, run_id=run_id)
    tail_ref = getattr(snapshot, "runtime_invocation_tail_ref", None)
    return _run_invocation_attempt_chain(
        store,
        tail_ref=tail_ref,
        run_manifest=snapshot.run_manifest,
    )


@dataclass
class RunContext:
    """Run context public type."""

    store: ArtifactStore
    trace: TraceSink
    run_manifest: RunManifest
    _trace_path: Path | None = None
    _audit_sink: _AuditTraceSink | None = None
    tenant_id: str | None = None
    cell_id: str | None = None
    access_scope: AccessScope | None = None
    _active_lease: _RunExecutionLease | None = None
    _owner_snapshot_ref: ArtifactRef | None = None
    _runtime_invocation_tail_ref: ArtifactRef | None = None
    _closed: bool = False
    _suspended: bool = False
    _worker_receipt_recovery_required: bool = False
    _worker_receipt_recovery_invocation_id: str | None = None
    _worker_staging: bool = field(default=False, repr=False, compare=False)
    _worker_merge_lock: threading.RLock = field(
        default_factory=threading.RLock,
        repr=False,
        compare=False,
    )
    _child_runtime_appointments: dict[tuple[str, str, str, str, str | None], object] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )

    @property
    def trace_path(self) -> Path | None:
        return self._trace_path

    def artifact_tenant_context(self) -> ArtifactTenantContextInfo | None:
        """Return this run's tenant scope after validating its selected owner snapshot.

        Direct legacy runs may remain unscoped. A durable control-job run must carry
        tenant scope in the same persisted owner snapshot that binds its run identity.
        """
        self._validate_run_owner_binding()
        tenant_context = _run_manifest_tenant_context(self.run_manifest)
        if self.run_manifest.control_job_id is not None and tenant_context is None:
            raise _FinalizeRecoveryError("run_owner_control_job_tenant_context_not_established")
        return tenant_context

    def _worker_lifecycle_capability(self) -> WorkerLifecycleCapability:
        """Create the Core-owned capability for this exact active parent run."""
        from .worker_lifecycle import WorkerLifecycleCapability

        return WorkerLifecycleCapability.for_parent(self)

    def _stage_worker_trace(self, trace: TraceSink | None) -> None:
        """Restrict this process-local context to staged, non-owner run operations."""
        lease = self._active_lease
        if lease is not None and lease._owner_pid == os.getpid():
            raise _FinalizeRecoveryError("worker_trace_parent_process_refused")
        if self._closed or self._suspended:
            raise _FinalizeRecoveryError("worker_lifecycle_parent_run_not_active")
        if trace is not None:
            self.trace = trace
        self._audit_sink = None
        self._worker_staging = True

    def _require_active_lease_owner(self) -> None:
        """Require this process to own an active run lease before terminal transitions."""
        lease = self._active_lease
        if lease is not None:
            lease.require_owner_process()

    @contextmanager
    def _parent_state_transition_lease(self, *, run_scoped: bool = True) -> Iterator[None]:
        """Serialize one parent's state transition and its durable trace effects.

        The instance lock protects in-memory lifecycle state. The run-scoped
        lease extends the same ordering across threads and processes that may
        recover or finalize this run for lifecycle/owner transitions. Ordinary
        event and input/output mutations use the same instance lock while the
        active-run lease excludes other process writers. Always acquire in this
        order; callers that already hold the transition must call their private
        ``*_locked`` body instead of nesting the public transition.
        """
        with self._worker_merge_lock:
            if not run_scoped or self._trace_path is None:
                yield
            else:
                with _run_finalize_lease(self._trace_path.parent):
                    yield

    def _require_worker_receipt_reconciled(self, *, invocation_id: str | None = None) -> None:
        """Reject unrelated mutations while an appended receipt awaits reconciliation."""
        if (
            self._worker_receipt_recovery_required
            and invocation_id != self._worker_receipt_recovery_invocation_id
        ):
            raise _FinalizeRecoveryError("worker_receipt_recovery_required")

    def _mark_worker_receipt_recovery_required(self, invocation_id: str) -> None:
        self._worker_receipt_recovery_required = True
        self._worker_receipt_recovery_invocation_id = invocation_id

    def _validate_run_owner_binding(self, *, require_store_binding: bool = False) -> None:
        """Prove the current run owner fields against the selected persisted snapshot."""
        owner_ref = self._owner_snapshot_ref
        if (
            type(owner_ref) is not ArtifactRef
            or owner_ref.kind != _RUN_OWNER_SNAPSHOT_KIND
            or owner_ref.media_type != "application/json"
            or owner_ref.manifest_profile_sha256 is None
        ):
            raise _FinalizeRecoveryError("timeout_worker_owner_snapshot_ref_required")
        try:
            snapshot = _validate_run_owner_snapshot_ref(
                self.store,
                owner_ref,
                require_registry_profile=False,
            )
        except _FinalizeRecoveryError as exc:
            raise _FinalizeRecoveryError("timeout_worker_owner_snapshot_invalid") from exc
        self._require_validated_run_owner_binding(
            snapshot, require_store_binding=require_store_binding
        )

    def _require_validated_run_owner_binding(
        self,
        snapshot: RunOwnerSnapshot | RunOwnerSnapshotV101,
        *,
        require_store_binding: bool = False,
    ) -> None:
        """Reconcile live fields with the actual Core reader's verified snapshot.

        The caller must retain the reader's fresh complete proof. This predicate
        performs no artifact admission or capability appointment by itself.
        """
        try:
            scope_digest = _access_scope_sha256(self.access_scope)
        except _FinalizeRecoveryError as exc:
            raise _FinalizeRecoveryError("timeout_worker_owner_snapshot_invalid") from exc

        persisted = snapshot.run_manifest
        current = self.run_manifest
        store_tenant_id = getattr(self.store, "_tenant_id", None)
        store_cell_id = getattr(self.store, "_cell_id", None)
        store_scope_established = store_tenant_id is not None or store_cell_id is not None
        identity_fields = (
            "run_id",
            "started_at",
            "producer",
            "env",
            "registry_bundle",
            "status",
            "finished_at",
            "trace_ref",
            "tenant_id",
            "cell_id",
            "seed",
            "parent_run_id",
            "replay_source_ref",
            "execution_profile",
            "control_job_id",
            "capability_manifest_ref",
            "environment_manifest_ref",
            "sbom_ref",
            "tee_attestation_ref",
        )
        if (
            snapshot.access_scope_sha256 != scope_digest
            or any(getattr(persisted, name) != getattr(current, name) for name in identity_fields)
            or (self.tenant_id, self.cell_id) != (current.tenant_id, current.cell_id)
            or (
                (require_store_binding or store_scope_established)
                and (store_tenant_id, store_cell_id) != (self.tenant_id, self.cell_id)
            )
            or (
                self.access_scope is not None
                and (self.access_scope.tenant_id, self.access_scope.cell_id)
                != (self.tenant_id, self.cell_id)
            )
        ):
            raise _FinalizeRecoveryError("timeout_worker_owner_inputs_mismatch")

    def _validate_timeout_worker_owner_binding(self) -> None:
        """Preserve the timeout-worker check's exact explicitly scoped-store contract."""
        self._validate_run_owner_binding(require_store_binding=True)

    @classmethod
    def start(
        cls,
        store: ArtifactStore,
        registry_bundle: ArtifactRef,
        producer: ProducerInfo | None = None,
        env: EnvInfo | None = None,
        run_dir: Path | None = None,
        run_id: str | None = None,
        *,
        tenant_id: str | None = None,
        cell_id: str | None = None,
        access_scope: AccessScope | None = None,
        parent_run_id: str | None = None,
        seed: int | None = None,
        execution_profile: str | None = None,
        control_job_id: str | None = None,
        capability_manifest_ref: ArtifactRef | None = None,
        environment_manifest_ref: ArtifactRef | None = None,
        sbom_ref: ArtifactRef | None = None,
        tee_attestation_ref: ArtifactRef | None = None,
    ) -> RunContext:
        """Start a new run, persisting its selected-profile owner before RUN_STARTED."""
        _require_return_selected_profile_writer(store, "put_json")
        run_id = run_id or new_run_id()
        run_dir = run_dir or _default_run_dir(store, run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        run_dir = run_dir.resolve(strict=True)
        trace_path = run_dir / "trace.jsonl"
        lease = _RunExecutionLease(run_dir)
        lease.acquire()
        active_lease: _RunExecutionLease | None = lease
        try:
            if os.path.lexists(trace_path) or os.path.lexists(_finalize_journal_path(run_dir)):
                raise _FinalizeRecoveryError("run_start_existing_lifecycle")
            trace_sink: TraceSink = JsonlTraceSink(trace_path)
            audit_sink = _build_run_audit_sink(
                run_id,
                run_dir,
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            ctx = cls(
                store=store,
                trace=trace_sink,
                run_manifest=RunManifest(
                    run_id=run_id,
                    registry_bundle=registry_bundle,
                    producer=producer,
                    env=env,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    parent_run_id=parent_run_id,
                    seed=seed,
                    execution_profile=execution_profile,
                    control_job_id=control_job_id,
                    capability_manifest_ref=capability_manifest_ref,
                    environment_manifest_ref=environment_manifest_ref,
                    sbom_ref=sbom_ref,
                    tee_attestation_ref=tee_attestation_ref,
                ),
                _trace_path=trace_path,
                _audit_sink=audit_sink,
                tenant_id=tenant_id,
                cell_id=cell_id,
                access_scope=access_scope,
                _active_lease=active_lease,
            )
            ctx._record_ref_owner(registry_bundle, writer="RunContext.start.registry_bundle")
            owner_ref = _persist_run_owner_snapshot(
                store,
                run_manifest=ctx.run_manifest,
                access_scope_sha256=_access_scope_sha256(access_scope),
                previous_snapshot_ref=None,
            )
            ctx._owner_snapshot_ref = owner_ref
            ctx._runtime_invocation_tail_ref = None
            ctx._emit_record(
                "core",
                "RUN_STARTED",
                run_terminality=RunTerminality.NON_TERMINAL,
                outputs=[owner_ref],
                ts=ctx.run_manifest.started_at,
            )
            active_lease = None
            return ctx
        finally:
            if active_lease is not None:
                active_lease.release()

    @classmethod
    def start_child(
        cls,
        parent: RunContext,
        *,
        store: ArtifactStore,
        parent_basis_ref: ArtifactRef,
        run_id: str,
        run_dir: Path,
    ) -> RunContext:
        """Start a distinct private run from an actual active parent attempt.

        The child uses the normal lease, trace and selected owner-snapshot writer.
        It has a fresh invocation tail and preserves the root's declared provenance;
        no new resource, budget or publication authority is created by this method.
        The custody owner persists the complete attempt binding as a typed child
        input before exposing the child to its first producer.
        """
        if type(parent) is not RunContext or cls is not RunContext:
            raise _FinalizeRecoveryError("child_run_requires_actual_parent_owner")
        if (
            type(parent_basis_ref) is not ArtifactRef
            or parent_basis_ref.manifest_profile_sha256 is None
        ):
            raise _FinalizeRecoveryError("child_run_parent_basis_profile_required")
        # Resolve actual persisted owner/attempt before the short transition;
        # child CAS work must not run under the parent lifecycle lock.
        parent._require_active_lease_owner()
        tail = deepcopy(parent._runtime_invocation_tail_ref)
        parent._validate_run_owner_binding()
        attempts = parent.read_runtime_invocation_attempts()
        matching = [item for item in attempts if item.basis_ref == parent_basis_ref]
        if len(matching) != 1 or matching[0].outcome is not None:
            raise _FinalizeRecoveryError("child_run_parent_attempt_not_active")
        if not run_id or run_id == parent.run_manifest.run_id:
            raise _FinalizeRecoveryError("child_run_identity_not_distinct")
        with parent._parent_state_transition_lease(run_scoped=False):
            parent._require_active_lease_owner()
            if (
                parent._closed
                or parent._suspended
                or parent._active_lease is None
                or parent._runtime_invocation_tail_ref != tail
            ):
                raise _FinalizeRecoveryError("child_run_parent_not_active")
            manifest = parent.run_manifest.model_copy(deep=True)
            tenant_id, cell_id = parent.tenant_id, parent.cell_id
            access_scope = deepcopy(parent.access_scope)
        # The custody owner rechecks the selected parent attempt after this
        # private preparation and before any child producer can start.
        try:
            return cls.start(
                store,
                manifest.registry_bundle,
                producer=manifest.producer,
                env=manifest.env,
                run_dir=run_dir,
                run_id=run_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
                access_scope=access_scope,
                parent_run_id=manifest.run_id,
                seed=manifest.seed,
                execution_profile=manifest.execution_profile,
                control_job_id=manifest.control_job_id,
                capability_manifest_ref=manifest.capability_manifest_ref,
                environment_manifest_ref=manifest.environment_manifest_ref,
                sbom_ref=manifest.sbom_ref,
                tee_attestation_ref=manifest.tee_attestation_ref,
            )
        except BaseException as exc:
            # Start owns its lease cleanup, but partial private trace/audit/CAS
            # effects may already exist. This locator is not a quiescence receipt.
            raise ChildRunStartUnknown(run_id=run_id, run_dir=run_dir) from exc

    @classmethod
    def resume(
        cls,
        store: ArtifactStore,
        *,
        run_id: str,
        run_dir: Path,
        registry_bundle: ArtifactRef,
        producer: ProducerInfo | None,
        env: EnvInfo | None,
        access_scope: AccessScope | None,
        allow_incomplete_worker_invocation_id: str | None = None,
    ) -> RunContext:
        """Resume one owner-bound incomplete run without emitting another RUN_STARTED.

        ``allow_incomplete_worker_invocation_id`` is reserved for a parent
        retrying the exact staged worker receipt whose prefix was durably
        appended before a writer interruption. Its source owner must still be
        the current verified manifest snapshot; its partial operations are
        excluded from reconstruction until ``merge_worker_events`` verifies
        and completes the same receipt.
        """
        _require_return_selected_profile_writer(store, "put_json")
        run_dir = run_dir.resolve(strict=True)
        if allow_incomplete_worker_invocation_id is not None and (
            type(allow_incomplete_worker_invocation_id) is not str
            or len(allow_incomplete_worker_invocation_id) != 64
            or any(
                character not in "0123456789abcdef"
                for character in allow_incomplete_worker_invocation_id
            )
        ):
            raise _FinalizeRecoveryError("run_resume_worker_invocation_id_invalid")
        lease = _RunExecutionLease(run_dir)
        lease.acquire()
        active_lease: _RunExecutionLease | None = lease
        try:
            records, started = _read_incomplete_run_trace(
                run_dir,
                run_id=run_id,
                allow_incomplete_worker_invocation_id=allow_incomplete_worker_invocation_id,
            )
            snapshot, owner_ref, last_snapshot_index = _run_owner_snapshot_chain(
                store,
                records=records,
                started=started,
                allow_incomplete_worker_invocation_id=allow_incomplete_worker_invocation_id,
            )
            if allow_incomplete_worker_invocation_id is not None:
                receipt_records = [
                    record
                    for record in records
                    if record.worker_invocation_id == allow_incomplete_worker_invocation_id
                ]
                if (
                    not receipt_records
                    or not any(
                        record.worker_receipt_phase == "started" for record in receipt_records
                    )
                    or any(record.worker_receipt_phase == "completed" for record in receipt_records)
                ):
                    raise _FinalizeRecoveryError("run_resume_worker_receipt_not_incomplete")
                first_receipt_index = min(
                    index
                    for index, record in enumerate(records)
                    if record.worker_invocation_id == allow_incomplete_worker_invocation_id
                )
                for record in records[first_receipt_index + 1 :]:
                    if record.worker_invocation_id == allow_incomplete_worker_invocation_id:
                        continue
                    if (
                        record.phase != "core"
                        or record.event != "RUN_RESUMED"
                        or record.run_terminality is not None
                        or record.refs.inputs != [owner_ref]
                        or record.refs.outputs
                    ):
                        raise _FinalizeRecoveryError("run_resume_worker_receipt_not_trace_suffix")
            manifest = snapshot.run_manifest.model_copy(deep=True)
            if (
                manifest.registry_bundle != registry_bundle
                or manifest.producer != producer
                or manifest.env != env
                or snapshot.access_scope_sha256 != _access_scope_sha256(access_scope)
                or (
                    access_scope is None
                    and (manifest.tenant_id is not None or manifest.cell_id is not None)
                )
                or (
                    access_scope is not None
                    and (
                        manifest.tenant_id != access_scope.tenant_id
                        or manifest.cell_id != access_scope.cell_id
                    )
                )
            ):
                raise _FinalizeRecoveryError("run_resume_owner_inputs_mismatch")

            inputs = list(manifest.inputs)
            outputs = list(manifest.outputs)
            for record in records[last_snapshot_index + 1 :]:
                if (
                    allow_incomplete_worker_invocation_id is not None
                    and record.worker_invocation_id == allow_incomplete_worker_invocation_id
                ):
                    continue
                if record.event == "RUN_INPUT_ADDED":
                    inputs.extend(record.refs.inputs)
                elif record.event == "RUN_OUTPUT_ADDED":
                    outputs.extend(record.refs.outputs)
            manifest.inputs = inputs
            manifest.outputs = outputs

            trace_path = run_dir / "trace.jsonl"
            ctx = cls(
                store=store,
                trace=JsonlTraceSink(trace_path),
                run_manifest=manifest,
                _trace_path=trace_path,
                _audit_sink=_build_run_audit_sink(
                    run_id,
                    run_dir,
                    tenant_id=manifest.tenant_id,
                    cell_id=manifest.cell_id,
                ),
                tenant_id=manifest.tenant_id,
                cell_id=manifest.cell_id,
                access_scope=access_scope,
                _active_lease=active_lease,
                _owner_snapshot_ref=owner_ref,
                _runtime_invocation_tail_ref=getattr(
                    snapshot,
                    "runtime_invocation_tail_ref",
                    None,
                ),
            )
            ctx._emit_record(
                "core",
                "RUN_RESUMED",
                inputs=[owner_ref],
            )
            if allow_incomplete_worker_invocation_id is not None:
                ctx._mark_worker_receipt_recovery_required(allow_incomplete_worker_invocation_id)
            active_lease = None
            return ctx
        finally:
            if active_lease is not None:
                active_lease.release()

    def _record_ref_owner(self, ref: ArtifactRef, *, writer: str) -> None:
        if self._worker_staging:
            return
        if not self.tenant_id:
            return
        recorder = getattr(self.store, "record_artifact_owner", None)
        if not callable(recorder):
            return
        recorder(
            ref.artifact_id,
            tenant_id=self.tenant_id,
            cell_id=self.cell_id,
            writer=writer,
        )

    def _append_runtime_invocation_record(
        self,
        record: RunInvocationStarted | RunInvocationCompleted,
    ) -> ArtifactRef:
        """Append one internal executor record through the selected-profile owner chain."""
        with self._parent_state_transition_lease():
            if (
                self._closed
                or self._suspended
                or self._active_lease is None
                or self._owner_snapshot_ref is None
            ):
                raise _FinalizeRecoveryError("run_invocation_owner_not_active")
            current_snapshot = _validate_run_owner_snapshot_ref(
                self.store,
                self._owner_snapshot_ref,
                require_registry_profile=False,
            )
            current_tail = getattr(current_snapshot, "runtime_invocation_tail_ref", None)
            if current_tail != self._runtime_invocation_tail_ref:
                raise _FinalizeRecoveryError("run_invocation_owner_tail_stale")
            if record.run_id != self.run_manifest.run_id:
                raise _FinalizeRecoveryError("run_invocation_run_id_mismatch")
            if record.previous_record_ref != current_tail:
                record = record.model_copy(update={"previous_record_ref": current_tail})
            if type(record) is RunInvocationCompleted:
                basis = _load_run_invocation_record(
                    self.store,
                    record.basis_ref,
                    run_manifest=self.run_manifest,
                )
                if (
                    type(basis) is not RunInvocationStarted
                    or basis.attempt_id != record.attempt_id
                    or basis.attempt_number != record.attempt_number
                    or basis.run_id != record.run_id
                ):
                    raise _FinalizeRecoveryError("run_invocation_completion_basis_mismatch")
            record_ref = _persist_run_invocation_record(
                self.store,
                record,
                run_manifest=self.run_manifest,
            )
            owner_ref = _persist_run_owner_snapshot(
                self.store,
                run_manifest=self.run_manifest,
                access_scope_sha256=_access_scope_sha256(self.access_scope),
                previous_snapshot_ref=self._owner_snapshot_ref,
                runtime_invocation_tail_ref=record_ref,
            )
            self._emit_record(
                "core",
                "RUN_CONTEXT_SNAPSHOT",
                outputs=[owner_ref],
            )
            self._owner_snapshot_ref = owner_ref
            self._runtime_invocation_tail_ref = record_ref
            return record_ref

    def _record_runtime_invocation_started(
        self,
        *,
        attempt_id: str,
        attempt_number: int,
        workflow_spec_ref: ArtifactRef,
        node_alias: str,
        component_id: str,
        input_state_ref: ArtifactRef,
        implementation_identity: RunInvocationImplementationIdentity | None = None,
    ) -> ArtifactRef:
        """Record the exact state and workflow invocation before node execution."""
        return self._append_runtime_invocation_record(
            RunInvocationStarted(
                run_id=self.run_manifest.run_id,
                attempt_id=attempt_id,
                attempt_number=attempt_number,
                workflow_spec_ref=workflow_spec_ref,
                node_alias=node_alias,
                component_id=component_id,
                input_state_ref=input_state_ref,
                previous_record_ref=self._runtime_invocation_tail_ref,
                implementation_identity=implementation_identity,
            )
        )

    def _record_runtime_invocation_completed(
        self,
        *,
        attempt_id: str,
        attempt_number: int,
        basis_ref: ArtifactRef,
        status: str,
        outcome_state_ref: ArtifactRef | None,
        output_refs: list[ArtifactRef],
    ) -> ArtifactRef:
        """Record the exact engine-observed attempt outcome and output references."""
        if status not in {"ok", "fail", "skip", "unknown"}:
            raise _FinalizeRecoveryError("run_invocation_outcome_status_invalid")
        return self._append_runtime_invocation_record(
            RunInvocationCompleted(
                run_id=self.run_manifest.run_id,
                attempt_id=attempt_id,
                attempt_number=attempt_number,
                basis_ref=basis_ref,
                previous_record_ref=self._runtime_invocation_tail_ref,
                status=status,
                outcome_state_ref=outcome_state_ref,
                output_refs=output_refs,
            )
        )

    def update_manifest(self, **changes: object) -> None:
        """Persist an allowlisted run-provenance update before execution continues."""
        with self._parent_state_transition_lease():
            allowed = {
                "execution_profile",
                "control_job_id",
                "capability_manifest_ref",
                "environment_manifest_ref",
                "sbom_ref",
                "tee_attestation_ref",
            }
            if not changes or set(changes) - allowed:
                raise ValueError("run_manifest_update_fields_invalid")
            self._require_worker_receipt_reconciled()
            if self._closed or self._suspended or self._owner_snapshot_ref is None:
                raise _FinalizeRecoveryError("run_manifest_update_owner_not_active")
            payload = self.run_manifest.model_dump(mode="python")
            payload.update(changes)
            updated = RunManifest.model_validate(payload)
            if updated == self.run_manifest:
                return
            owner_ref = _persist_run_owner_snapshot(
                self.store,
                run_manifest=updated,
                access_scope_sha256=_access_scope_sha256(self.access_scope),
                previous_snapshot_ref=self._owner_snapshot_ref,
                runtime_invocation_tail_ref=self._runtime_invocation_tail_ref,
            )
            self._emit_record(
                "core",
                "RUN_CONTEXT_SNAPSHOT",
                outputs=[owner_ref],
            )
            self.run_manifest = updated
            self._owner_snapshot_ref = owner_ref

    def suspend_for_resume(self) -> None:
        """Release this writer without finalizing so a new context can explicitly resume."""
        self._require_active_lease_owner()
        with self._parent_state_transition_lease():
            if self._active_lease is None:
                return
            if self._trace_path is None:
                raise _FinalizeRecoveryError("run_suspend_trace_not_established")
            run_dir = self._trace_path.parent
            _read_incomplete_run_trace(
                run_dir,
                run_id=self.run_manifest.run_id,
                allow_incomplete_worker_invocation_id=(
                    self._worker_receipt_recovery_invocation_id
                    if self._worker_receipt_recovery_required
                    else None
                ),
            )
            self._suspended = True
            self._closed = True
            try:
                if self._audit_sink is not None:
                    self._audit_sink.close()
            finally:
                self._audit_sink = None
                self._active_lease.release()
                self._active_lease = None

    def emit(
        self,
        phase: str,
        event: str,
        *,
        inputs: list[ArtifactRef] | None = None,
        outputs: list[ArtifactRef] | None = None,
        metrics: dict[str, float | int] | None = None,
        warnings: list[WarningRecord] | None = None,
    ) -> None:
        """Emit a non-Core trace event with optional typed warning details.

        Args:
            phase: Trace phase that owns the event.
            event: Event name to persist.
            inputs: Artifact references consumed by the event.
            outputs: Artifact references produced by the event.
            metrics: Numeric measurements associated with the event.
            warnings: Typed warnings to persist in the existing trace warning field.
        """
        if phase == "core" or (isinstance(event, str) and event.startswith("RUN_")):
            raise _FinalizeRecoveryError("run_context_owner_event_reserved")
        with self._parent_state_transition_lease(run_scoped=False):
            self._emit_record(
                phase,
                event,
                inputs=inputs,
                outputs=outputs,
                metrics=metrics,
                warnings=warnings,
            )

    def read_runtime_owner_output_refs(self) -> tuple[ArtifactRef, ...]:
        """Fresh-read owner output events and reconcile them to this run manifest.

        The method replays the persisted start record, owner snapshot chain, and
        input/output event sequence. It refuses a missing trace or any difference
        from the current in-memory input/output lists, so callers cannot establish
        an owner output by changing only ``run_manifest.outputs``.
        """
        records = self._read_runtime_owner_trace()
        _recorded_inputs, recorded_outputs = self._owner_refs_from_records(records)
        return recorded_outputs

    def read_runtime_workflow_finalization_ref(self) -> ArtifactRef:
        """Return the exact workflow transition carried by the protected terminal event.

        Legacy terminal records without this engine-supplied input remain valid run
        history, but do not establish a workflow-finalization currentness claim.
        """
        records = self._read_runtime_owner_trace()
        _recorded_inputs, recorded_outputs = self._owner_refs_from_records(records)
        terminal_records = [
            record
            for record in records
            if record.phase == "core" and record.event == "RUN_FINALIZED"
        ]
        if (
            len(terminal_records) != 1
            or records[-1] is not terminal_records[0]
            or terminal_records[0].run_terminality is not RunTerminality.TERMINAL
        ):
            raise _FinalizeRecoveryError("run_workflow_finalization_terminal_not_established")
        terminal = terminal_records[0]
        if (
            len(terminal.refs.inputs) != 1
            or len(terminal.refs.outputs) != 1
            or terminal.refs.outputs[0].kind != "core.run_manifest"
            or terminal.refs.outputs[0].media_type != "application/json"
        ):
            raise _FinalizeRecoveryError("run_workflow_finalization_terminal_ref_invalid")
        finalization_ref = terminal.refs.inputs[0]
        if finalization_ref not in recorded_outputs:
            raise _FinalizeRecoveryError("run_workflow_finalization_output_unlinked")
        return finalization_ref

    def _read_runtime_owner_trace(self) -> list[TraceRecord]:
        if self._trace_path is None:
            raise _FinalizeRecoveryError("run_owner_output_trace_not_established")
        records, _snapshot, _last_snapshot_index = _read_run_owner_records(
            self.store,
            self._trace_path,
            run_id=self.run_manifest.run_id,
        )
        recorded_inputs, recorded_outputs = self._owner_refs_from_records(records)
        if tuple(map(artifact_ref_identity_key, recorded_inputs)) != tuple(
            map(artifact_ref_identity_key, self.run_manifest.inputs)
        ) or tuple(map(artifact_ref_identity_key, recorded_outputs)) != tuple(
            map(artifact_ref_identity_key, self.run_manifest.outputs)
        ):
            raise _FinalizeRecoveryError("run_owner_refs_trace_manifest_mismatch")
        return records

    @staticmethod
    def _owner_refs_from_records(
        records: list[TraceRecord],
    ) -> tuple[tuple[ArtifactRef, ...], tuple[ArtifactRef, ...]]:
        recorded_inputs = tuple(
            ref
            for record in records[1:]
            if record.phase == "core" and record.event == "RUN_INPUT_ADDED"
            for ref in record.refs.inputs
        )
        recorded_outputs = tuple(
            ref
            for record in records[1:]
            if record.phase == "core" and record.event == "RUN_OUTPUT_ADDED"
            for ref in record.refs.outputs
        )
        return recorded_inputs, recorded_outputs

    def read_runtime_invocation_attempts(self) -> list[_RunInvocationAttempt]:
        """Fresh-read the guarded owner chain and its exact node-attempt bases.

        This reports engine-observed execution inputs and outcomes only. A missing
        chain, including a valid historical owner snapshot without the v1.0.2 tail,
        returns no invocation binding; callers must preserve that as not established.
        """
        if self._trace_path is None:
            return []
        from .child_custody import _ManagedStore

        if type(self.store) is _ManagedStore:
            return self.store._read_owned_run_invocation_attempts(self)
        return _read_runtime_invocation_attempts(
            self.store,
            self._trace_path,
            run_id=self.run_manifest.run_id,
        )

    def merge_worker_events(
        self,
        *,
        invocation_id: str,
        dispatch_sha256: str,
        owner_snapshot_ref: ArtifactRef,
        records: Sequence[TraceRecord],
    ) -> None:
        """Serialize admission of an exact parent-dispatched worker receipt."""
        with self._parent_state_transition_lease():
            self._merge_worker_events_locked(
                invocation_id=invocation_id,
                dispatch_sha256=dispatch_sha256,
                owner_snapshot_ref=owner_snapshot_ref,
                records=records,
            )

    def _merge_worker_events_locked(
        self,
        *,
        invocation_id: str,
        dispatch_sha256: str,
        owner_snapshot_ref: ArtifactRef,
        records: Sequence[TraceRecord],
    ) -> None:
        """Admit one exact staged worker event set through the active parent writer.

        Worker events are candidate execution evidence. This method binds them
        to the exact parent dispatch and current run owner, resolves and verifies
        their artifact refs, applies the narrow RunContext input/output/snapshot
        operations emitted by those events, and records the result through the
        parent's canonical sink and optional audit sink. It does not grant
        worker lifecycle authority.
        """
        if (
            self._closed
            or self._suspended
            or self._active_lease is None
            or self._trace_path is None
        ):
            raise _FinalizeRecoveryError("worker_merge_parent_run_not_active")
        trace_path = self._trace_path
        if trace_path is None:
            raise _FinalizeRecoveryError("worker_merge_parent_run_not_active")
        if not isinstance(self.trace, BatchTraceSink):
            raise _FinalizeRecoveryError("worker_merge_batch_trace_sink_required")
        if (
            type(invocation_id) is not str
            or len(invocation_id) != 64
            or any(character not in "0123456789abcdef" for character in invocation_id)
        ):
            raise _FinalizeRecoveryError("worker_merge_invocation_id_invalid")
        if (
            type(dispatch_sha256) is not str
            or len(dispatch_sha256) != 64
            or any(character not in "0123456789abcdef" for character in dispatch_sha256)
        ):
            raise _FinalizeRecoveryError("worker_merge_dispatch_digest_invalid")
        self._require_worker_receipt_reconciled(invocation_id=invocation_id)
        if (
            type(owner_snapshot_ref) is not ArtifactRef
            or owner_snapshot_ref != self._owner_snapshot_ref
        ):
            raise _FinalizeRecoveryError("worker_merge_owner_snapshot_stale")
        self._validate_timeout_worker_owner_binding()

        try:
            source_records = list(records)
        except TypeError as exc:
            raise _FinalizeRecoveryError("worker_merge_records_invalid") from exc
        admitted_records: list[TraceRecord] = []
        for record in source_records:
            if type(record) is not TraceRecord:
                raise _FinalizeRecoveryError("worker_merge_record_type_invalid")
            if (
                record.run_id != self.run_manifest.run_id
                or record.tenant_id != self.tenant_id
                or record.cell_id != self.cell_id
                or record.run_terminality is not None
                or (
                    record.event.startswith("RUN_")
                    and record.event not in _WORKER_RUN_OPERATION_EVENTS
                )
                or record.worker_invocation_id is not None
                or record.worker_dispatch_sha256 is not None
                or record.worker_receipt_phase is not None
                or record.worker_receipt_count is not None
                or record.worker_receipt_sha256 is not None
            ):
                raise _FinalizeRecoveryError("worker_merge_record_scope_or_authority_invalid")
            for ref in [*record.refs.inputs, *record.refs.outputs]:
                if type(ref) is not ArtifactRef or ref.manifest_profile_sha256 is None:
                    raise _FinalizeRecoveryError("worker_merge_artifact_profile_required")
                try:
                    verification = self.store.verify(ref)
                except (OSError, RuntimeError, TypeError, ValueError) as exc:
                    raise _FinalizeRecoveryError(
                        "worker_merge_artifact_verification_failed"
                    ) from exc
                if not verification.ok:
                    raise _FinalizeRecoveryError("worker_merge_artifact_verification_failed")
            try:
                payload = record.model_dump(mode="python", exclude_none=False)
                payload["worker_invocation_id"] = invocation_id
                payload["worker_dispatch_sha256"] = dispatch_sha256
                admitted_records.append(TraceRecord.model_validate(payload))
            except (TypeError, ValueError) as exc:
                raise _FinalizeRecoveryError("worker_merge_record_invalid") from exc

        trace_records, _started = _read_incomplete_run_trace(
            self._trace_path.parent,
            run_id=self.run_manifest.run_id,
            allow_incomplete_worker_invocation_id=invocation_id,
        )
        receipt_records = [
            record for record in trace_records if record.worker_invocation_id == invocation_id
        ]
        started_markers = [
            record for record in receipt_records if record.worker_receipt_phase == "started"
        ]
        completed_markers = [
            record for record in receipt_records if record.worker_receipt_phase == "completed"
        ]
        if completed_markers:
            raise _FinalizeRecoveryError("worker_receipt_replay_refused")
        if len(started_markers) > 1:
            raise _FinalizeRecoveryError("worker_receipt_start_marker_conflict")

        digest = _worker_trace_digest(admitted_records)
        if started_markers:
            started_marker = started_markers[0]
            if (
                receipt_records[0] is not started_marker
                or started_marker.phase != "core"
                or started_marker.event != "WORKER_INVOCATION_STARTED"
                or started_marker.worker_receipt_count != len(admitted_records)
                or started_marker.worker_receipt_sha256 != digest
                or started_marker.worker_dispatch_sha256 != dispatch_sha256
                or started_marker.refs.inputs != [owner_snapshot_ref]
                or started_marker.refs.outputs
                or started_marker.run_terminality is not None
            ):
                raise _FinalizeRecoveryError("worker_receipt_prefix_binding_mismatch")
            existing_events = [
                record for record in receipt_records if record.worker_receipt_phase is None
            ]
            if len(existing_events) > len(admitted_records) or any(
                existing.model_dump_json(exclude_none=True)
                != expected.model_dump_json(exclude_none=True)
                for existing, expected in zip(
                    existing_events,
                    admitted_records,
                    strict=False,
                )
            ):
                raise _FinalizeRecoveryError("worker_receipt_prefix_conflict")
            pending_records = admitted_records[len(existing_events) :]
        elif receipt_records:
            raise _FinalizeRecoveryError("worker_receipt_orphan_record")
        else:
            start_marker = TraceRecord(
                run_id=self.run_manifest.run_id,
                phase="core",
                event="WORKER_INVOCATION_STARTED",
                tenant_id=self.tenant_id,
                cell_id=self.cell_id,
                refs=TraceRefs(inputs=[owner_snapshot_ref]),
                worker_invocation_id=invocation_id,
                worker_dispatch_sha256=dispatch_sha256,
                worker_receipt_phase="started",
                worker_receipt_count=len(admitted_records),
                worker_receipt_sha256=digest,
            )
            pending_records = [start_marker, *admitted_records]

        completed_marker = TraceRecord(
            run_id=self.run_manifest.run_id,
            phase="core",
            event="WORKER_INVOCATION_COMPLETED",
            tenant_id=self.tenant_id,
            cell_id=self.cell_id,
            refs=TraceRefs(inputs=[owner_snapshot_ref]),
            worker_invocation_id=invocation_id,
            worker_dispatch_sha256=dispatch_sha256,
            worker_receipt_phase="completed",
            worker_receipt_count=len(admitted_records),
            worker_receipt_sha256=digest,
        )
        candidate_manifest = self.run_manifest.model_copy(deep=True)
        candidate_owner_ref = self._owner_snapshot_ref
        if candidate_owner_ref is None:
            raise _FinalizeRecoveryError("worker_merge_owner_snapshot_stale")
        scope_digest = _access_scope_sha256(self.access_scope)
        for record in admitted_records:
            candidate_manifest, candidate_owner_ref = _apply_worker_run_operation(
                self.store,
                manifest=candidate_manifest,
                owner_snapshot_ref=candidate_owner_ref,
                access_scope_sha256=scope_digest,
                record=record,
            )

        records_to_emit = [*pending_records, completed_marker]
        for record in records_to_emit:
            for ref in [*record.refs.inputs, *record.refs.outputs]:
                self._record_ref_owner(ref, writer=f"RunContext.merge_worker_events:{record.event}")

        trace_before = _read_run_trace_bytes(
            trace_path,
            failure_code="worker_merge_trace_before_append_unreadable",
        )
        expected_suffix = "".join(
            f"{record.model_dump_json(exclude_none=True)}\n" for record in records_to_emit
        ).encode("utf-8")
        try:
            self.trace.emit_many(records_to_emit)
        except Exception:
            try:
                trace_after_error = _read_run_trace_bytes(
                    trace_path,
                    failure_code="worker_merge_trace_readback_failed",
                )
            except _FinalizeRecoveryError:
                self._mark_worker_receipt_recovery_required(invocation_id)
            else:
                if trace_after_error != trace_before:
                    self._mark_worker_receipt_recovery_required(invocation_id)
            raise
        try:
            trace_after = _read_run_trace_bytes(
                trace_path,
                failure_code="worker_merge_trace_readback_failed",
            )
        except _FinalizeRecoveryError as exc:
            self._mark_worker_receipt_recovery_required(invocation_id)
            raise _FinalizeRecoveryError("worker_merge_trace_readback_failed") from exc
        if (
            not trace_after.startswith(trace_before)
            or trace_after[len(trace_before) :] != expected_suffix
        ):
            if trace_after != trace_before:
                self._mark_worker_receipt_recovery_required(invocation_id)
            raise _FinalizeRecoveryError("worker_merge_trace_readback_mismatch")
        try:
            _read_incomplete_run_trace(
                trace_path.parent,
                run_id=self.run_manifest.run_id,
            )
        except _FinalizeRecoveryError as exc:
            self._mark_worker_receipt_recovery_required(invocation_id)
            raise _FinalizeRecoveryError("worker_merge_trace_readback_failed") from exc
        self._worker_receipt_recovery_required = False
        self._worker_receipt_recovery_invocation_id = None
        self.run_manifest = candidate_manifest
        self._owner_snapshot_ref = candidate_owner_ref
        candidate_snapshot = _validate_run_owner_snapshot_ref(
            self.store,
            candidate_owner_ref,
            require_registry_profile=False,
        )
        self._runtime_invocation_tail_ref = getattr(
            candidate_snapshot,
            "runtime_invocation_tail_ref",
            None,
        )

        for record in records_to_emit:
            if self._audit_sink is not None:
                try:
                    self._audit_sink.emit(record)
                except Exception as exc:  # optional fanout follows canonical trace persistence
                    logger.warning(
                        "Optional audit trace emit failed for run %s: %s",
                        record.run_id,
                        exc,
                    )

    def _emit_record(
        self,
        phase: str,
        event: str,
        *,
        run_terminality: RunTerminality | None = None,
        inputs: list[ArtifactRef] | None = None,
        outputs: list[ArtifactRef] | None = None,
        metrics: dict[str, float | int] | None = None,
        warnings: list[WarningRecord] | None = None,
        ts: datetime | None = None,
    ) -> None:
        self._require_worker_receipt_reconciled()
        if self._closed:
            raise _FinalizeRecoveryError("run_context_writer_closed")
        if warnings is not None and any(
            not isinstance(warning, WarningRecord) for warning in warnings
        ):
            raise TypeError("run_context_trace_warning_invalid")
        warning_payloads = [warning.model_dump(mode="json") for warning in warnings or []]
        for ref in [*(inputs or []), *(outputs or [])]:
            self._record_ref_owner(ref, writer=f"RunContext.emit:{event}")
        rec = TraceRecord(
            **({"ts": ts} if ts is not None else {}),
            run_id=self.run_manifest.run_id,
            phase=phase,
            event=event,
            run_terminality=run_terminality,
            tenant_id=self.tenant_id,
            cell_id=self.cell_id,
            refs=TraceRefs(inputs=inputs or [], outputs=outputs or []),
            metrics=metrics or {},
            warnings=warning_payloads,
        )
        self.trace.emit(rec)
        if self._audit_sink is not None:
            try:
                self._audit_sink.emit(rec)
            except Exception as exc:  # optional fanout must not mask canonical trace persistence
                logger.warning("Optional audit trace emit failed for run %s: %s", rec.run_id, exc)

    def add_input(self, ref: ArtifactRef) -> None:
        with self._parent_state_transition_lease(run_scoped=False):
            if self._closed or self._suspended:
                raise _FinalizeRecoveryError("run_context_writer_closed")
            self._require_worker_receipt_reconciled()
            self._emit_record("core", "RUN_INPUT_ADDED", inputs=[ref])
            self.run_manifest.inputs.append(ref)

    def add_output(self, ref: ArtifactRef) -> None:
        with self._parent_state_transition_lease(run_scoped=False):
            if self._closed or self._suspended:
                raise _FinalizeRecoveryError("run_context_writer_closed")
            self._require_worker_receipt_reconciled()
            self._emit_record("core", "RUN_OUTPUT_ADDED", outputs=[ref])
            self.run_manifest.outputs.append(ref)

    def finalize(
        self,
        status: str = "ok",
        *,
        errors: list[dict[str, object]] | None = None,
        workflow_finalization_ref: ArtifactRef | None = None,
    ) -> ArtifactRef:
        """Finalize this run, optionally binding its selected workflow transition."""
        self._require_active_lease_owner()
        with self._worker_merge_lock:
            run_dir = self._trace_path.parent if self._trace_path is not None else None
            try:
                if self._suspended:
                    raise _FinalizeRecoveryError("run_context_suspended")
                if self._worker_receipt_recovery_required:
                    raise _FinalizeRecoveryError("worker_receipt_incomplete")
                if run_dir is None:
                    return self._finalize_locked(
                        run_dir,
                        status=status,
                        errors=errors,
                        workflow_finalization_ref=workflow_finalization_ref,
                    )
                with _run_finalize_lease(run_dir):
                    if self._suspended:
                        raise _FinalizeRecoveryError("run_context_suspended")
                    return self._finalize_locked(
                        run_dir,
                        status=status,
                        errors=errors,
                        workflow_finalization_ref=workflow_finalization_ref,
                    )
            finally:
                self._closed = True
                if self._active_lease is not None:
                    self._active_lease.release()
                    self._active_lease = None

    def _finalize_locked(
        self,
        run_dir: Path | None,
        *,
        status: str,
        errors: list[dict[str, object]] | None,
        workflow_finalization_ref: ArtifactRef | None = None,
    ) -> ArtifactRef:
        """Perform finalization while holding the run's exclusive lease."""
        if workflow_finalization_ref is not None and (
            type(workflow_finalization_ref) is not ArtifactRef
            or workflow_finalization_ref.manifest_profile_sha256 is None
            or workflow_finalization_ref not in self.run_manifest.outputs
        ):
            raise _FinalizeRecoveryError("run_finalize_workflow_transition_not_owner_linked")
        if run_dir is not None:
            journal_path = _finalize_journal_path(run_dir)
            pending_manifest = _load_finalize_journal(run_dir) if journal_path.exists() else None
            if pending_manifest is not None and not _finalize_request_matches(
                pending_manifest,
                status=status,
                errors=errors,
            ):
                raise _FinalizeRecoveryError("run_finalize_pending_request_conflict")
            recovered_ref = _recover_pending_run_finalize_locked(self.store, run_dir)
            if recovered_ref is not None:
                if workflow_finalization_ref is not None:
                    recovered_finalized_ref = _trace_terminal_run_finalized_ref(
                        self._trace_path,
                        owner=_RunOwnerIdentity(
                            run_id=self.run_manifest.run_id,
                            tenant_id=self.run_manifest.tenant_id,
                            cell_id=self.run_manifest.cell_id,
                        ),
                        expected_workflow_finalization_ref=workflow_finalization_ref,
                    )
                    if recovered_finalized_ref != recovered_ref:
                        raise _FinalizeRecoveryError(
                            "run_finalize_workflow_transition_recovery_not_established"
                        )
                return recovered_ref

            if self._trace_path is not None and self._trace_path.exists():
                expected_owner = _RunOwnerIdentity(
                    run_id=self.run_manifest.run_id,
                    tenant_id=self.run_manifest.tenant_id,
                    cell_id=self.run_manifest.cell_id,
                )
                trace_owner = _trace_run_started_identity(self._trace_path)
                if trace_owner != expected_owner:
                    raise _FinalizeRecoveryError("run_finalize_trace_owner_not_established")
                existing_ref = _trace_terminal_run_finalized_ref(
                    self._trace_path,
                    owner=trace_owner,
                    expected_workflow_finalization_ref=workflow_finalization_ref,
                )
                if existing_ref is not None:
                    _validate_terminal_run_manifest_ref(
                        self.store,
                        run_manifest=self.run_manifest,
                        run_ref=existing_ref,
                        require_selected_profile=False,
                    )
                    if not _finalize_request_matches(
                        self.run_manifest,
                        status=status,
                        errors=errors,
                    ):
                        raise _FinalizeRecoveryError("run_finalize_terminal_request_conflict")
                    return existing_ref

        self.run_manifest.status = status
        if errors:
            self.run_manifest.errors.extend(errors)
        self.run_manifest.finished_at = self.run_manifest.finished_at or datetime.now(UTC).replace(
            microsecond=0
        )

        trace_ref = None
        if self._trace_path and self._trace_path.exists():
            data = self._trace_path.read_bytes()
            trace_ref = self.store.put_bytes(
                data,
                ArtifactWriteOptions(kind="core.trace.jsonl", media_type="application/jsonl"),
            )
            self._record_ref_owner(trace_ref, writer="RunContext.finalize.trace")
            self.run_manifest.trace_ref = trace_ref

        if run_dir is not None:
            _write_finalize_journal(run_dir, self.run_manifest)
        run_ref = self.store.put_json(
            self.run_manifest,
            _run_manifest_write_options(self.run_manifest),
            return_selected_profile=True,
        )
        _validate_terminal_run_manifest_ref(
            self.store,
            run_manifest=self.run_manifest,
            run_ref=run_ref,
            require_selected_profile=True,
        )
        self._record_ref_owner(run_ref, writer="RunContext.finalize.manifest")
        self._emit_record(
            "core",
            "RUN_FINALIZED",
            run_terminality=RunTerminality.TERMINAL,
            inputs=[workflow_finalization_ref] if workflow_finalization_ref is not None else None,
            outputs=[run_ref],
            metrics={"status_ok": 1 if status == "ok" else 0},
        )
        if run_dir is not None:
            _clear_finalize_journal(run_dir)
        if self._audit_sink is not None:
            try:
                self._audit_sink.close()
            except Exception as exc:  # optional fanout shutdown cannot revoke persisted finality
                logger.debug(
                    "Failed to close audit sink for run %s: %s",
                    self.run_manifest.run_id,
                    exc,
                )
        return run_ref


def _audit_chain_enabled() -> bool:
    return os.getenv("POLISYOS_AUDIT_CHAIN_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _build_run_audit_sink(
    run_id: str,
    run_dir: Path,
    *,
    tenant_id: str | None,
    cell_id: str | None,
) -> _AuditTraceSink | None:
    if not _audit_chain_enabled():
        return None
    try:
        from polisyos.core.security.audit_sink import (
            ChainedAuditSink,
            build_default_audit_backends_from_env,
        )

        return cast(
            "_AuditTraceSink",
            ChainedAuditSink(
                chain_id=_build_audit_chain_id(run_id, tenant_id=tenant_id, cell_id=cell_id),
                local_path=run_dir / "audit.jsonl",
                backends=build_default_audit_backends_from_env(),
            ),
        )
    except (ImportError, RuntimeError, OSError, ValueError, TypeError) as exc:
        logger.debug("Failed to initialize audit chain for run %s: %s", run_id, exc)
        return None


def _default_run_dir(store: ArtifactStore, run_id: str) -> Path:
    root = getattr(store, "root", None)
    if isinstance(root, Path):
        return root / "runs" / run_id
    if isinstance(root, str):
        return Path(root) / "runs" / run_id
    return Path(".") / "runs" / run_id


def _build_audit_chain_id(run_id: str, *, tenant_id: str | None, cell_id: str | None) -> str:
    tenant = tenant_id or "global"
    cell = cell_id or "default"
    return f"{tenant}:{cell}:{run_id}"
