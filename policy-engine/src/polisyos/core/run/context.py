"""Public run context module API."""

from __future__ import annotations

import errno
import json
import os
import secrets
import stat
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from polisyos.common.logger import get_logger
from polisyos.common.serialization import fast_json_dumps

from ..artifacts import ManifestLifecycle
from ..artifacts._atomic_write import AtomicFileWriter
from ..artifacts.manifest import ArtifactRef, CanonInfo, EnvInfo, InputRef, ProducerInfo, SchemaInfo
from ..artifacts.protocol import _require_return_selected_profile_writer
from ..artifacts.write_contract import ArtifactWriteOptions
from ..canon import CanonSpec, content_hash, from_canonical_bytes, to_canonical_bytes
from ..trace import RunTerminality
from ..trace.record import TraceRecord, TraceRefs
from ..trace.sink import JsonlTraceSink, TraceSink
from .manifest import RunManifest, RunOwnerSnapshot

if TYPE_CHECKING:
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
_RUN_OWNER_SNAPSHOT_SCHEMA_VERSION = "1.0.1"
_RUN_OWNER_SNAPSHOT_CANON = CanonSpec(exclude_none=False)
_RUN_OWNER_SCOPE_CANON = CanonSpec(
    name="polisyos.core.run.owner-scope",
    version="1.0",
    forbid_floats=False,
    sort_keys=True,
)
_ACTIVE_RUN_THREAD_LOCKS: dict[Path, threading.Lock] = {}
_ACTIVE_RUN_THREAD_LOCKS_GUARD = threading.Lock()


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


class _RunExecutionLease:
    """Hold one run's writer lease until finalization, suspension, or process exit."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self._run_key: Path | None = None
        self._thread_lock: threading.Lock | None = None
        self._descriptor: int | None = None
        self._fcntl: object | None = None

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
        self._descriptor = None
        self._fcntl = None
        try:
            if descriptor is not None and fcntl is not None:
                try:
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


class _AuditTraceSink(Protocol):
    """Trace sink protocol that also supports explicit shutdown."""

    def emit(self, rec: TraceRecord) -> None: ...

    def close(self) -> None: ...


def _run_manifest_write_options(run_manifest: RunManifest) -> ArtifactWriteOptions:
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
            )
        ],
    )


def _run_owner_snapshot_write_options(
    snapshot: RunOwnerSnapshot,
) -> ArtifactWriteOptions:
    inputs = [
        InputRef(
            artifact_id=snapshot.run_manifest.registry_bundle.artifact_id,
            role="registry_bundle",
            manifest_profile_sha256=(
                snapshot.run_manifest.registry_bundle.manifest_profile_sha256
            ),
        )
    ]
    if snapshot.previous_snapshot_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=snapshot.previous_snapshot_ref.artifact_id,
                role="previous_owner_snapshot",
                manifest_profile_sha256=(
                    snapshot.previous_snapshot_ref.manifest_profile_sha256
                ),
            )
        )
    canon = _RUN_OWNER_SNAPSHOT_CANON
    return ArtifactWriteOptions(
        kind=_RUN_OWNER_SNAPSHOT_KIND,
        media_type="application/json",
        schema=SchemaInfo(
            name=_RUN_OWNER_SNAPSHOT_SCHEMA,
            version=_RUN_OWNER_SNAPSHOT_SCHEMA_VERSION,
        ),
        producer=snapshot.run_manifest.producer,
        env=snapshot.run_manifest.env,
        inputs=inputs,
        canon=CanonInfo.from_spec(canon),
    )


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


def _persist_run_owner_snapshot(
    store: ArtifactStore,
    *,
    run_manifest: RunManifest,
    access_scope_sha256: str | None,
    previous_snapshot_ref: ArtifactRef | None,
) -> ArtifactRef:
    snapshot = RunOwnerSnapshot(
        schema_version=_RUN_OWNER_SNAPSHOT_SCHEMA_VERSION,
        run_manifest=run_manifest.model_copy(deep=True),
        access_scope_sha256=access_scope_sha256,
        previous_snapshot_ref=previous_snapshot_ref,
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
) -> RunOwnerSnapshot:
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
        try:
            snapshot = RunOwnerSnapshot.model_validate(decoded)
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
        ManifestLifecycle.validate_profile(
            artifact_manifest,
            data_size=len(payload),
            opts=options,
        )
        if artifact_manifest.inputs != options.inputs:
            raise _FinalizeRecoveryError("run_resume_owner_snapshot_lineage_mismatch")
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
        snapshot.schema_version != _RUN_OWNER_SNAPSHOT_SCHEMA_VERSION
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
        record
        for record in records
        if record.phase == "core" and record.event == "RUN_STARTED"
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
    return records, owner


def _run_owner_snapshot_chain(
    store: ArtifactStore,
    *,
    records: list[TraceRecord],
    started: TraceRecord,
) -> tuple[RunOwnerSnapshot, ArtifactRef, int]:
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
            before = snapshot.run_manifest
            after = next_snapshot.run_manifest
            immutable_fields = (
                "run_id", "started_at", "producer", "env", "registry_bundle",
                "tenant_id", "cell_id", "seed", "parent_run_id", "replay_source_ref",
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
) -> ArtifactRef | None:
    """Read one strict terminal fact, preserving the exact manifest selector."""
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
        record
        for record in records
        if record.phase == "core" and record.event == "RUN_STARTED"
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

    finalized = [
        record
        for record in records
        if record.phase == "core" and record.event == "RUN_FINALIZED"
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
    manifest_outputs = [
        output for output in terminal.refs.outputs if output.kind == "core.run_manifest"
    ]
    if (
        len(manifest_outputs) != 1
        or manifest_outputs[0].media_type != "application/json"
    ):
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
        or (require_selected_profile and run_ref.manifest_profile_sha256 is None)
    ):
        raise _FinalizeRecoveryError("run_finalize_manifest_ref_contract_mismatch")

    try:
        verification = store.verify(run_ref)
        if not verification.ok:
            raise _FinalizeRecoveryError("run_finalize_manifest_cas_verification_failed")
        artifact_manifest = store.get_manifest(run_ref)
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
        ManifestLifecycle.validate_profile(
            artifact_manifest,
            data_size=len(manifest_bytes),
            opts=profile_options,
        )
    except ValueError as exc:
        raise _FinalizeRecoveryError(
            "run_finalize_manifest_write_profile_mismatch"
        ) from exc


def _trace_run_started_identity(trace_path: Path) -> _RunOwnerIdentity | None:
    if not trace_path.exists():
        return None
    owners: set[_RunOwnerIdentity] = set()
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = TraceRecord.model_validate_json(line)
        except (TypeError, ValueError):
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
    return (
        len(errors) <= len(run_manifest.errors)
        and run_manifest.errors[-len(errors) :] == errors
    )


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


def new_run_id() -> str:
    """New run ID helper."""
    return "R_" + secrets.token_hex(8)


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
    _closed: bool = False
    _suspended: bool = False

    @property
    def trace_path(self) -> Path | None:
        return self._trace_path

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
    ) -> RunContext:
        """Start a new run, persisting its selected-profile owner before RUN_STARTED."""
        _require_return_selected_profile_writer(store, "put_json")
        run_id = run_id or new_run_id()
        run_dir = run_dir or _default_run_dir(store, run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        run_dir = run_dir.resolve(strict=True)
        trace_path = run_dir / "trace.jsonl"
        active_lease = _RunExecutionLease(run_dir)
        active_lease.acquire()
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
    ) -> RunContext:
        """Resume one owner-bound incomplete run without emitting another RUN_STARTED."""
        _require_return_selected_profile_writer(store, "put_json")
        run_dir = run_dir.resolve(strict=True)
        active_lease = _RunExecutionLease(run_dir)
        active_lease.acquire()
        try:
            records, started = _read_incomplete_run_trace(run_dir, run_id=run_id)
            snapshot, owner_ref, last_snapshot_index = _run_owner_snapshot_chain(
                store,
                records=records,
                started=started,
            )
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
            )
            ctx._emit_record(
                "core",
                "RUN_RESUMED",
                inputs=[owner_ref],
            )
            active_lease = None
            return ctx
        finally:
            if active_lease is not None:
                active_lease.release()

    def _record_ref_owner(self, ref: ArtifactRef, *, writer: str) -> None:
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

    def update_manifest(self, **changes: object) -> None:
        """Persist an allowlisted run-provenance update before execution continues."""
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
        if self._closed or self._owner_snapshot_ref is None:
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
        if self._active_lease is None:
            return
        if self._trace_path is None:
            raise _FinalizeRecoveryError("run_suspend_trace_not_established")
        run_dir = self._trace_path.parent
        with _run_finalize_lease(run_dir):
            if self._active_lease is None:
                return
            _read_incomplete_run_trace(
                run_dir,
                run_id=self.run_manifest.run_id,
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
    ) -> None:
        self._emit_record(
            phase,
            event,
            inputs=inputs,
            outputs=outputs,
            metrics=metrics,
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
        ts: datetime | None = None,
    ) -> None:
        if self._closed:
            raise _FinalizeRecoveryError("run_context_writer_closed")
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
        )
        self.trace.emit(rec)
        if self._audit_sink is not None:
            try:
                self._audit_sink.emit(rec)
            except Exception as exc:  # optional fanout must not mask canonical trace persistence
                logger.warning("Optional audit trace emit failed for run %s: %s", rec.run_id, exc)

    def add_input(self, ref: ArtifactRef) -> None:
        self.run_manifest.inputs.append(ref)
        self.emit("core", "RUN_INPUT_ADDED", inputs=[ref])

    def add_output(self, ref: ArtifactRef) -> None:
        self.run_manifest.outputs.append(ref)
        self.emit("core", "RUN_OUTPUT_ADDED", outputs=[ref])

    def finalize(
        self,
        status: str = "ok",
        *,
        errors: list[dict[str, object]] | None = None,
    ) -> ArtifactRef:
        if self._suspended:
            raise _FinalizeRecoveryError("run_context_suspended")
        run_dir = self._trace_path.parent if self._trace_path is not None else None
        try:
            if run_dir is None:
                return self._finalize_locked(run_dir, status=status, errors=errors)
            with _run_finalize_lease(run_dir):
                if self._suspended:
                    raise _FinalizeRecoveryError("run_context_suspended")
                return self._finalize_locked(run_dir, status=status, errors=errors)
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
    ) -> ArtifactRef:
        """Perform finalization while holding the run's exclusive lease."""
        if run_dir is not None:
            journal_path = _finalize_journal_path(run_dir)
            pending_manifest = (
                _load_finalize_journal(run_dir) if journal_path.exists() else None
            )
            if pending_manifest is not None and not _finalize_request_matches(
                pending_manifest,
                status=status,
                errors=errors,
            ):
                raise _FinalizeRecoveryError("run_finalize_pending_request_conflict")
            recovered_ref = _recover_pending_run_finalize_locked(self.store, run_dir)
            if recovered_ref is not None:
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
