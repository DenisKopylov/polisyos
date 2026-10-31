from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event
from typing import TYPE_CHECKING, Any

import pytest

from polisyos.core.artifacts import ArtifactOwnershipError
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ArtifactTenantContextInfo,
    CanonInfo,
    ProducerInfo,
    SchemaInfo,
    WarningRecord,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.audit import AuditPackageAssembler
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.run import context as run_context
from polisyos.core.run.context import RunContext
from polisyos.core.run.manifest import RunOwnerSnapshot, RunOwnerSnapshotV101
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.core.trace import RunTerminality, TraceRecord
from polisyos.core.trace.record import TraceRefs


def _fork_run_action(action: Any, run: RunContext) -> dict[str, Any]:
    """Run one probe in a forked process and return its refusal/state readback."""
    read_fd, write_fd = os.pipe()
    child_pid = os.fork()
    if child_pid == 0:
        os.close(read_fd)
        try:
            try:
                value = action()
                outcome = {"kind": "returned", "value": str(value)}
            except run_context._FinalizeRecoveryError as exc:
                outcome = {"kind": "refused", "reason": str(exc)}
            except BaseException as exc:
                outcome = {"kind": "unexpected", "error": type(exc).__name__}
            trace_path = run.trace_path
            outcome.update(
                {
                    "closed": run._closed,
                    "suspended": run._suspended,
                    "trace_sha256": (
                        hashlib.sha256(trace_path.read_bytes()).hexdigest()
                        if trace_path is not None
                        else None
                    ),
                }
            )
            os.write(write_fd, json.dumps(outcome, sort_keys=True).encode("utf-8"))
        finally:
            os.close(write_fd)
            os._exit(0)

    os.close(write_fd)
    result_bytes = bytearray()
    while chunk := os.read(read_fd, 4096):
        result_bytes.extend(chunk)
    os.close(read_fd)
    _, wait_status = os.waitpid(child_pid, 0)
    if not os.WIFEXITED(wait_status) or os.WEXITSTATUS(wait_status) != 0:
        raise AssertionError("forked run-context probe did not exit cleanly")
    return json.loads(result_bytes.decode("utf-8"))


if TYPE_CHECKING:
    from pathlib import Path


def _record_lease_event(
    event_queue: Any | None,
    event_sequence: Any,
    actor: str,
    phase: str,
    *,
    parent_events: list[tuple[int, str, str]] | None = None,
) -> tuple[int, str, str]:
    """Record an ordered lifecycle phase observed at the real flock boundary."""
    with event_sequence.get_lock():
        event_sequence.value += 1
        event = (event_sequence.value, actor, phase)
    if event_queue is not None:
        event_queue.put(event)
    if parent_events is not None:
        parent_events.append(event)
    return event


def _observed_flock(
    lock_path: Path,
    actor: str,
    event_queue: Any | None,
    event_sequence: Any,
    *,
    parent_events: list[tuple[int, str, str]] | None = None,
) -> Any:
    """Wrap flock and emit phases only for this run's actual lock inode."""
    import fcntl
    import os

    original_flock = fcntl.flock

    def _is_run_lock(descriptor: int) -> bool:
        try:
            opened = os.fstat(descriptor)
            named = os.stat(lock_path, follow_symlinks=False)
        except OSError:
            return False
        return (opened.st_dev, opened.st_ino) == (named.st_dev, named.st_ino)

    def _recorded_flock(descriptor: int, operation: int) -> Any:
        if not _is_run_lock(descriptor):
            return original_flock(descriptor, operation)
        if operation == fcntl.LOCK_EX:
            _record_lease_event(
                event_queue,
                event_sequence,
                actor,
                "claim_attempt",
                parent_events=parent_events,
            )
            result = original_flock(descriptor, operation)
            _record_lease_event(
                event_queue,
                event_sequence,
                actor,
                "lease_acquired",
                parent_events=parent_events,
            )
            return result
        if operation == fcntl.LOCK_UN:
            _record_lease_event(
                event_queue,
                event_sequence,
                actor,
                "lease_unlock_attempt",
                parent_events=parent_events,
            )
            result = original_flock(descriptor, operation)
            _record_lease_event(
                event_queue,
                event_sequence,
                actor,
                "lease_released",
                parent_events=parent_events,
            )
            return result
        return original_flock(descriptor, operation)

    return _recorded_flock


def _wait_for_lease_event(
    event_queue: Any,
    observed_events: list[tuple[int, str, str]],
    *,
    phase: str,
    actor: str | None = None,
    other_than: str | None = None,
) -> tuple[int, str, str]:
    """Wait for a positive observed phase, retaining every event read."""

    def _matches(event: tuple[int, str, str]) -> bool:
        return (
            event[2] == phase
            and (actor is None or event[1] == actor)
            and (other_than is None or event[1] != other_than)
        )

    while not any(_matches(event) for event in observed_events):
        event = event_queue.get(timeout=30)
        observed_events.append(event)
        if actor is not None and event[1] == actor and event[2].startswith("worker_error:"):
            pytest.fail(f"{actor} worker failed before {phase}: {event[2]}")
        if actor is not None and event[1] == actor and event[2] == "worker_done":
            pytest.fail(f"{actor} worker exited before observed {phase}")
    return next(event for event in observed_events if _matches(event))


def _collect_lease_worker_events(
    event_queue: Any,
    observed_events: list[tuple[int, str, str]],
    worker_ids: set[str],
) -> None:
    """Drain each worker through its final event after processes have joined."""
    done = {
        event[1]
        for event in observed_events
        if event[2] == "worker_done" and event[1] in worker_ids
    }
    while done != worker_ids:
        event = event_queue.get(timeout=30)
        observed_events.append(event)
        if event[2] == "worker_done" and event[1] in worker_ids:
            done.add(event[1])


def _event_sequence(
    events: list[tuple[int, str, str]],
    *,
    actor: str,
    phase: str,
) -> int:
    matching = [
        seq
        for seq, event_actor, event_phase in events
        if event_actor == actor and event_phase == phase
    ]
    assert len(matching) == 1, (actor, phase, events)
    return matching[0]


def _assert_serialized_recovery_events(
    events: list[tuple[int, str, str]],
    *,
    scan_actor: str,
    contender_actor: str,
    release_sequence: int,
) -> None:
    scan = _event_sequence(events, actor=scan_actor, phase="terminal_scan")
    scan_claim = _event_sequence(events, actor=scan_actor, phase="claim_attempt")
    scan_acquired = _event_sequence(events, actor=scan_actor, phase="lease_acquired")
    contender_claim = _event_sequence(events, actor=contender_actor, phase="claim_attempt")
    scan_unlock = _event_sequence(events, actor=scan_actor, phase="lease_unlock_attempt")
    contender_acquired = _event_sequence(events, actor=contender_actor, phase="lease_acquired")
    _event_sequence(events, actor=scan_actor, phase="lease_released")
    _event_sequence(events, actor=contender_actor, phase="lease_unlock_attempt")
    _event_sequence(events, actor=contender_actor, phase="lease_released")

    assert scan_claim < scan_acquired < scan
    assert contender_claim < release_sequence
    assert release_sequence < scan_unlock < contender_acquired
    assert not any(
        seq < release_sequence
        for seq, actor, phase in events
        if actor == contender_actor and phase == "lease_acquired"
    )
    for seq, actor, phase in events:
        if phase == "terminal_scan":
            acquired = _event_sequence(events, actor=actor, phase="lease_acquired")
            assert acquired < seq


def _recover_in_process(
    store_root: str,
    run_dir: str,
    worker_id: str,
    operation: str,
    start_barrier: Any,
    event_queue: Any,
    event_sequence: Any,
    release_scan: Any,
    results: Any,
    bypass_lease: bool = False,
    operation_release: Any | None = None,
) -> None:
    """Call the real reader/recovery path from a distinct OS process."""
    from polisyos.runtime.http.services.adapters.core_run import load_core_run

    try:
        _record_lease_event(
            event_queue,
            event_sequence,
            worker_id,
            "worker_entered",
        )
        from contextlib import AbstractContextManager, nullcontext
        from pathlib import Path

        store = FileSystemCAS(Path(store_root))
        original_scan = run_context._trace_terminal_run_finalized_ref
        if bypass_lease:

            def _without_lease(_run_dir: Path) -> AbstractContextManager[None]:
                return nullcontext()

            run_context._run_finalize_lease = _without_lease
        else:
            import fcntl

            fcntl.flock = _observed_flock(
                Path(run_dir) / ".finalize.lock",
                worker_id,
                event_queue,
                event_sequence,
            )

        def _observed_scan(trace_path: Path, *, owner: Any) -> Any:
            snapshot = original_scan(trace_path, owner=owner)
            _record_lease_event(
                event_queue,
                event_sequence,
                worker_id,
                "terminal_scan",
            )
            if not release_scan.wait(timeout=30):
                raise TimeoutError("test did not release the held terminal scan")
            return snapshot

        run_context._trace_terminal_run_finalized_ref = _observed_scan
        _record_lease_event(
            event_queue,
            event_sequence,
            worker_id,
            "worker_ready",
        )
        start_barrier.wait(timeout=30)
        if operation_release is not None:
            _record_lease_event(
                event_queue,
                event_sequence,
                worker_id,
                "worker_waiting_for_operation",
            )
            if not operation_release.wait(timeout=30):
                raise TimeoutError("test did not release the prewarmed recovery operation")
        _record_lease_event(
            event_queue,
            event_sequence,
            worker_id,
            "worker_before_operation",
        )
        if operation == "load":
            loaded = load_core_run(store=store, run_dir=Path(run_dir))
            results.put(
                (
                    "ok",
                    worker_id,
                    "load",
                    loaded.run_id if loaded is not None else None,
                    loaded.status if loaded is not None else None,
                    loaded.manifest_ref.model_dump_json()
                    if loaded is not None and loaded.manifest_ref is not None
                    else None,
                )
            )
        elif operation == "recover":
            recovered = run_context.recover_pending_run_finalize(store, Path(run_dir))
            results.put(
                (
                    "ok",
                    worker_id,
                    "recover",
                    recovered.model_dump_json() if recovered is not None else None,
                )
            )
        else:
            raise ValueError(f"unsupported recovery test operation: {operation}")
    except Exception as exc:
        cleanup_error: str | None = None
        try:
            start_barrier.abort()
        except Exception as cleanup_exc:
            cleanup_error = f"{type(cleanup_exc).__name__}: {cleanup_exc}"
        results.put(("error", worker_id, type(exc).__name__, str(exc)))
        worker_error = f"worker_error:{type(exc).__name__}:{exc}"
        if cleanup_error is not None:
            worker_error = f"{worker_error};barrier_abort_error:{cleanup_error}"
        _record_lease_event(
            event_queue,
            event_sequence,
            worker_id,
            worker_error,
        )
    finally:
        _record_lease_event(
            event_queue,
            event_sequence,
            worker_id,
            "worker_done",
        )


def _assert_core_and_audit_reopen(
    store: FileSystemCAS,
    run_dir: Path,
    *,
    run_id: str,
    output_path: Path,
) -> ArtifactRef:
    from polisyos.runtime.http.services.adapters.core_run import load_core_run

    core = load_core_run(store=store, run_dir=run_dir)
    assert core is not None
    assert core.run_id == run_id
    assert core.status == "ok"
    assert core.manifest_ref is not None
    terminal = _terminal_records(run_dir)
    assert len(terminal) == 1
    assert terminal[0].refs.outputs == [core.manifest_ref]

    audit = AuditPackageAssembler(cas=FileSystemCAS(store.root), runs_dir=run_dir.parent)
    exported = audit.export(run_id, output_path)
    assert exported.run_id == run_id
    assert exported.archive_path.exists()
    assert len(_terminal_records(run_dir)) == 1
    return core.manifest_ref


def _bootstrap_registry_bundle(store: FileSystemCAS, *, selected_profile: bool = False):
    slot_ref = store.put_json(
        {"slots": {}},
        PutOptions(kind="core.registry.slots", media_type="application/json"),
    )
    merge_ref = store.put_json(
        {"merge_rules": {}},
        PutOptions(kind="core.registry.merge", media_type="application/json"),
    )
    con_ref = store.put_json(
        {"constraints": {}},
        PutOptions(kind="core.registry.constraints", media_type="application/json"),
    )
    mech_ref = store.put_json(
        {"mechanisms": {}},
        PutOptions(kind="core.registry.mechanisms", media_type="application/json"),
    )
    trust_ref = store.put_json(
        {"trust_policies": {}},
        PutOptions(kind="core.registry.trust", media_type="application/json"),
    )

    bundle_payload = {
        "slot_registry": slot_ref.model_dump(),
        "merge_registry": merge_ref.model_dump(),
        "constraint_registry": con_ref.model_dump(),
        "mechanism_registry": mech_ref.model_dump(),
        "trust_registry": trust_ref.model_dump(),
    }
    bundle_ref = store.put_json(
        bundle_payload,
        PutOptions(kind="core.registry.bundle", media_type="application/json"),
        return_selected_profile=selected_profile,
    )
    return bundle_ref


def _write_selected_manifest_view_for_test(
    store: FileSystemCAS,
    ref: ArtifactRef,
    options: ArtifactWriteOptions,
) -> ArtifactRef:
    """Materialize an adversarial selected view directly in the temporary test CAS."""
    payload = store.get_bytes(ref)
    manifest = run_context.ManifestLifecycle.build(
        artifact_id=ref.artifact_id,
        data=payload,
        sha=hashlib.sha256(payload).hexdigest(),
        opts=options,
    )
    profile_sha256 = run_context.ManifestLifecycle.profile_sha256(manifest)
    path = store._layout.view_manifest_path(ref.artifact_id, profile_sha256)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(run_context.ManifestLifecycle.to_bytes(manifest))
    return ref.model_copy(update={"manifest_profile_sha256": profile_sha256})


def test_run_context_emits_trace_and_writes_run_manifest(
    store: FileSystemCAS, tmp_path: Path, producer, env_info
):
    bundle_ref = _bootstrap_registry_bundle(store)

    run_dir = tmp_path / "runs" / "R_test"
    ctx = RunContext.start(
        store=store,
        registry_bundle=bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
    )

    inp = store.put_json(
        {"policy": "noop"},
        PutOptions(kind="ir.policy_spec", media_type="application/json"),
    )
    out = store.put_json(
        {"result": "ok"},
        PutOptions(kind="core.output", media_type="application/json"),
    )

    ctx.add_input(inp)
    ctx.add_output(out)

    run_ref = ctx.finalize(status="ok")

    assert run_ref.manifest_profile_sha256 is not None
    selected_manifest = store.get_manifest_by_profile(
        run_ref.artifact_id, run_ref.manifest_profile_sha256
    )
    assert selected_manifest.artifact_id == run_ref.artifact_id
    assert selected_manifest.kind == "core.run_manifest"
    assert store.has(run_ref.artifact_id)
    rep = store.verify(run_ref.artifact_id)
    assert rep.ok is True

    run_manifest = store.get_bytes(run_ref.artifact_id).decode("utf-8")
    assert '"status":"ok"' in run_manifest
    assert str(bundle_ref.artifact_id) in run_manifest
    assert str(inp.artifact_id) in run_manifest
    assert str(out.artifact_id) in run_manifest
    assert '"trace_ref"' in run_manifest
    assert len(_terminal_records(run_dir)) == 1
    terminal_ref = next(
        ref for ref in _terminal_records(run_dir)[0].refs.outputs if ref.kind == "core.run_manifest"
    )
    assert terminal_ref == run_ref
    assert (run_dir / ".finalize-journal.json").exists() is False


@pytest.mark.parametrize("changed_side", ["inputs", "outputs"])
def test_owner_trace_matches_typed_refs_by_full_selected_identity(
    store: FileSystemCAS, tmp_path: Path, producer: Any, env_info: Any, changed_side: str
) -> None:
    """Decoded trace refs may lose their subclass but never their selected profile."""
    from polisyos.core.contracts.scientist import DecisionPacketRef

    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    ctx = RunContext.start(
        store=store,
        registry_bundle=bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=tmp_path / "runs" / f"typed-ref-{changed_side}",
    )
    refs = [
        store.put_json(
            {"same": "bytes"},
            PutOptions(
                kind="scientist.decision_packet",
                media_type="application/json",
                schema=SchemaInfo(name=f"tests.Packet{name}", version="1"),
            ),
            return_selected_profile=True,
        )
        for name in ("A", "B")
    ]
    assert refs[0].artifact_id == refs[1].artifact_id
    assert refs[0].manifest_profile_sha256 != refs[1].manifest_profile_sha256
    typed = [DecisionPacketRef.model_validate(ref.model_dump()) for ref in refs]
    ctx.add_input(typed[0])
    ctx.add_output(typed[0])
    ctx.add_input(typed[1])
    ctx.add_output(typed[1])
    records = ctx._read_runtime_owner_trace()
    recorded_inputs, recorded_outputs = ctx._owner_refs_from_records(records)
    assert type(recorded_inputs[0]) is ArtifactRef
    assert type(recorded_outputs[0]) is ArtifactRef
    selected = getattr(ctx.run_manifest, changed_side)
    selected[0] = typed[1]
    with pytest.raises(
        run_context._FinalizeRecoveryError, match="run_owner_refs_trace_manifest_mismatch"
    ):
        ctx._read_runtime_owner_trace()
    selected[0] = typed[0]
    selected.reverse()
    with pytest.raises(
        run_context._FinalizeRecoveryError, match="run_owner_refs_trace_manifest_mismatch"
    ):
        ctx._read_runtime_owner_trace()
    selected.reverse()
    ctx.finalize()


@pytest.mark.parametrize(
    ("first_operation", "second_operation"),
    [("load", "load"), ("recover", "load")],
)
def test_independent_recovery_callers_share_one_run_lease(
    first_operation: str,
    second_operation: str,
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _run_context_with_output(
        store,
        tmp_path,
        run_id=f"R_parallel_recovery_{first_operation}_{second_operation}",
        producer=producer,
        env_info=env_info,
    )
    original_put_json = store.put_json
    should_fail = True

    def _failing_put_json(obj, opts=None, canon_spec=None, *, return_selected_profile=False):
        nonlocal should_fail
        if should_fail and getattr(opts, "kind", None) == "core.run_manifest":
            should_fail = False
            raise OSError("simulated finalize crash")
        return original_put_json(
            obj,
            opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )

    monkeypatch.setattr(store, "put_json", _failing_put_json)
    with pytest.raises(OSError, match="simulated finalize crash"):
        ctx.finalize(status="ok")
    monkeypatch.setattr(store, "put_json", original_put_json)

    run_dir = ctx.trace_path.parent
    assert (run_dir / ".finalize-journal.json").exists()
    mp = multiprocessing.get_context("spawn")
    start_barrier = mp.Barrier(3)
    lease_events = mp.Queue()
    event_sequence = mp.Value("i", 0)
    release_scan = mp.Event()
    results = mp.Queue()
    parent_events: list[tuple[int, str, str]] = []
    worker_ids = {"worker-0", "worker-1"}
    operations = [first_operation, second_operation]
    workers = [
        mp.Process(
            target=_recover_in_process,
            args=(
                str(store.root),
                str(run_dir),
                f"worker-{index}",
                operation,
                start_barrier,
                lease_events,
                event_sequence,
                release_scan,
                results,
            ),
        )
        for index, operation in enumerate(operations)
    ]
    observed_events: list[tuple[int, str, str]] = []
    first_scan: tuple[int, str, str] | None = None
    contender_claim: tuple[int, str, str] | None = None
    try:
        for worker in workers:
            worker.start()
        start_barrier.wait(timeout=30)
        first_scan = _wait_for_lease_event(
            lease_events,
            observed_events,
            phase="terminal_scan",
        )
        contender_claim = _wait_for_lease_event(
            lease_events,
            observed_events,
            phase="claim_attempt",
            other_than=first_scan[1],
        )
        assert contender_claim[1] != first_scan[1]
    finally:
        release_sequence = _record_lease_event(
            None,
            event_sequence,
            "parent",
            "release_scan",
            parent_events=parent_events,
        )[0]
        release_scan.set()
        for worker in workers:
            if worker.pid is not None:
                worker.join(timeout=30)
                if worker.is_alive():
                    worker.terminate()
                    worker.join(timeout=5)
        if all(worker.exitcode == 0 for worker in workers):
            _collect_lease_worker_events(lease_events, observed_events, worker_ids)
        lease_events.close()

    assert all(worker.exitcode == 0 for worker in workers)
    assert first_scan is not None and contender_claim is not None
    events = sorted([*observed_events, *parent_events])
    _assert_serialized_recovery_events(
        events,
        scan_actor=first_scan[1],
        contender_actor=contender_claim[1],
        release_sequence=release_sequence,
    )

    outcomes = [results.get(timeout=5) for _ in workers]
    results.close()
    assert all(outcome[0] == "ok" for outcome in outcomes), outcomes
    observed_refs: list[ArtifactRef] = []
    for outcome in outcomes:
        if outcome[2] == "load":
            assert outcome[3:5] == (ctx.run_manifest.run_id, "ok"), outcome
            assert outcome[5] is not None, outcome
            observed_refs.append(ArtifactRef.model_validate_json(outcome[5]))
        else:
            assert outcome[2] == "recover", outcome
            if outcome[3] is not None:
                observed_refs.append(ArtifactRef.model_validate_json(outcome[3]))
    assert not (run_dir / ".finalize-journal.json").exists()
    strict_ref = _assert_core_and_audit_reopen(
        store,
        run_dir,
        run_id=ctx.run_manifest.run_id,
        output_path=tmp_path / "parallel-recovery-audit.zip",
    )
    assert observed_refs
    assert all(ref == strict_ref for ref in observed_refs)


def test_removing_run_lease_reopens_duplicate_terminal_events(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The scan barrier exposes duplicate terminal writes when arbitration is removed."""
    ctx = _run_context_with_output(
        store,
        tmp_path,
        run_id="R_removed_finalize_lease_probe",
        producer=producer,
        env_info=env_info,
    )
    original_put_json = store.put_json
    should_fail = True

    def _failing_put_json(obj, opts=None, canon_spec=None, *, return_selected_profile=False):
        nonlocal should_fail
        if should_fail and getattr(opts, "kind", None) == "core.run_manifest":
            should_fail = False
            raise OSError("simulated finalize crash")
        return original_put_json(
            obj,
            opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )

    monkeypatch.setattr(store, "put_json", _failing_put_json)
    with pytest.raises(OSError, match="simulated finalize crash"):
        ctx.finalize(status="ok")
    monkeypatch.setattr(store, "put_json", original_put_json)

    run_dir = ctx.trace_path.parent
    mp = multiprocessing.get_context("spawn")
    start_barrier = mp.Barrier(3)
    lease_events = mp.Queue()
    event_sequence = mp.Value("i", 0)
    release_scan = mp.Event()
    results = mp.Queue()
    worker_ids = {"unleased-0", "unleased-1"}
    workers = [
        mp.Process(
            target=_recover_in_process,
            args=(
                str(store.root),
                str(run_dir),
                f"unleased-{index}",
                "recover",
                start_barrier,
                lease_events,
                event_sequence,
                release_scan,
                results,
                True,
            ),
        )
        for index in range(2)
    ]
    observed_events: list[tuple[int, str, str]] = []
    try:
        for worker in workers:
            worker.start()
        start_barrier.wait(timeout=30)
        scan_actors = set()
        while scan_actors != worker_ids:
            event = lease_events.get(timeout=30)
            observed_events.append(event)
            if event[2] == "terminal_scan" and event[1] in worker_ids:
                scan_actors.add(event[1])
    finally:
        release_scan.set()
        for worker in workers:
            if worker.pid is not None:
                worker.join(timeout=30)
                if worker.is_alive():
                    worker.terminate()
                    worker.join(timeout=5)
        if all(worker.exitcode == 0 for worker in workers):
            _collect_lease_worker_events(lease_events, observed_events, worker_ids)
        lease_events.close()

    assert all(worker.exitcode == 0 for worker in workers)
    assert {event[1] for event in observed_events if event[2] == "terminal_scan"} == worker_ids
    assert not any(event[2] in {"claim_attempt", "lease_acquired"} for event in observed_events)
    outcomes = [results.get(timeout=5) for _ in workers]
    results.close()
    assert all(outcome[0] == "ok" for outcome in outcomes), outcomes
    assert len(_terminal_records(run_dir)) == 2


def test_finalize_and_reader_recovery_share_one_run_lease(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _run_context_with_output(
        store,
        tmp_path,
        run_id="R_finalize_reader_race",
        producer=producer,
        env_info=env_info,
    )
    run_dir = ctx.trace_path.parent
    original_put_json = store.put_json
    finalize_entered = Event()
    release_finalize = Event()

    def _blocking_put_json(obj, opts=None, canon_spec=None, *, return_selected_profile=False):
        if getattr(opts, "kind", None) == "core.run_manifest":
            _record_lease_event(
                None,
                event_sequence,
                "finalizer",
                "cas_blocked",
                parent_events=parent_events,
            )
            finalize_entered.set()
            if not release_finalize.wait(timeout=30):
                raise TimeoutError("test did not release normal finalization")
        return original_put_json(
            obj,
            opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )

    mp = multiprocessing.get_context("spawn")
    lease_events = mp.Queue()
    event_sequence = mp.Value("i", 0)
    release_scan = mp.Event()
    operation_release = mp.Event()
    results = mp.Queue()
    parent_events: list[tuple[int, str, str]] = []
    observed_events: list[tuple[int, str, str]] = []
    worker_ids = {"reader"}
    import fcntl

    reader_barrier = mp.Barrier(1)
    # Keep every spawn input alive through the child lifetime. Process.start() can
    # return before the child unpickles its args and drops the process-owned tuple.
    reader_process_inputs = (
        str(store.root),
        str(run_dir),
        "reader",
        "load",
        reader_barrier,
        lease_events,
        event_sequence,
        release_scan,
        results,
        False,
        operation_release,
    )
    reader = mp.Process(
        target=_recover_in_process,
        args=reader_process_inputs,
    )
    release_sequence = None
    finalize = None
    with ThreadPoolExecutor(max_workers=1) as executor:
        try:
            reader.start()
            reader_ready = _wait_for_lease_event(
                lease_events,
                observed_events,
                phase="worker_ready",
                actor="reader",
            )
            assert reader_ready[1] == "reader"
            reader_waiting = _wait_for_lease_event(
                lease_events,
                observed_events,
                phase="worker_waiting_for_operation",
                actor="reader",
            )
            assert reader_waiting[1] == "reader"
            monkeypatch.setattr(
                fcntl,
                "flock",
                _observed_flock(
                    run_dir / ".finalize.lock",
                    "finalizer",
                    None,
                    event_sequence,
                    parent_events=parent_events,
                ),
            )
            monkeypatch.setattr(store, "put_json", _blocking_put_json)
            finalize = executor.submit(ctx.finalize, status="ok")
            assert finalize_entered.wait(timeout=30)
            operation_release.set()
            reader_before_operation = _wait_for_lease_event(
                lease_events,
                observed_events,
                phase="worker_before_operation",
                actor="reader",
            )
            assert reader_before_operation[1] == "reader"
            reader_claim = _wait_for_lease_event(
                lease_events,
                observed_events,
                phase="claim_attempt",
                actor="reader",
            )
            assert reader_claim[1] == "reader"
        finally:
            operation_release.set()
            if finalize is not None:
                release_sequence = _record_lease_event(
                    None,
                    event_sequence,
                    "parent",
                    "release_finalize",
                    parent_events=parent_events,
                )[0]
                release_finalize.set()
            release_scan.set()
            if reader.pid is not None:
                reader.join(timeout=30)
                if reader.is_alive():
                    reader.terminate()
                    reader.join(timeout=5)
            if reader.exitcode == 0:
                _collect_lease_worker_events(lease_events, observed_events, worker_ids)
            lease_events.close()
        assert finalize is not None
        finalized_ref = finalize.result(timeout=30)

    assert reader.exitcode == 0
    reader_result = results.get(timeout=5)
    results.close()
    assert reader_result == (
        "ok",
        "reader",
        "load",
        ctx.run_manifest.run_id,
        "ok",
        finalized_ref.model_dump_json(),
    )
    events = sorted([*observed_events, *parent_events])
    finalizer_acquired = _event_sequence(events, actor="finalizer", phase="lease_acquired")
    cas_blocked = _event_sequence(events, actor="finalizer", phase="cas_blocked")
    reader_claim = _event_sequence(events, actor="reader", phase="claim_attempt")
    finalizer_unlock = _event_sequence(events, actor="finalizer", phase="lease_unlock_attempt")
    reader_acquired = _event_sequence(events, actor="reader", phase="lease_acquired")
    assert release_sequence is not None
    assert finalizer_acquired < cas_blocked < reader_claim < release_sequence
    assert release_sequence < finalizer_unlock < reader_acquired
    for seq, actor, phase in events:
        if phase == "terminal_scan":
            acquired = _event_sequence(events, actor=actor, phase="lease_acquired")
            assert acquired < seq
    assert not (run_dir / ".finalize-journal.json").exists()
    assert len(_terminal_records(run_dir)) == 1
    assert finalized_ref == _terminal_records(run_dir)[0].refs.outputs[0]
    strict_ref = _assert_core_and_audit_reopen(
        store,
        run_dir,
        run_id=ctx.run_manifest.run_id,
        output_path=tmp_path / "finalize-reader-audit.zip",
    )
    assert strict_ref == finalized_ref


def test_concurrent_repeat_finalize_returns_the_same_terminal_ref(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    ctx = _run_context_with_output(
        store,
        tmp_path,
        run_id="R_repeated_finalize_race",
        producer=producer,
        env_info=env_info,
    )
    start = Barrier(3)

    def _finalize_after_barrier() -> ArtifactRef:
        start.wait(timeout=30)
        return ctx.finalize(status="ok")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_finalize_after_barrier) for _ in range(2)]
        start.wait(timeout=30)
        refs = [future.result(timeout=30) for future in futures]

    assert refs[0] == refs[1]
    assert not (ctx.trace_path.parent / ".finalize-journal.json").exists()
    _assert_core_and_audit_reopen(
        store,
        ctx.trace_path.parent,
        run_id=ctx.run_manifest.run_id,
        output_path=tmp_path / "repeat-finalize-audit.zip",
    )


def test_run_context_finalize_recovery_repairs_pending_manifest(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.services.adapters.core_run import load_core_run

    bundle_ref = _bootstrap_registry_bundle(store)
    run_dir = tmp_path / "runs" / "R_recover"

    ctx = RunContext.start(
        store=store,
        registry_bundle=bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
    )
    out = store.put_json(
        {"result": "ok"},
        PutOptions(kind="core.output", media_type="application/json"),
    )
    ctx.add_output(out)

    original_put_json = store.put_json
    should_fail = True

    def _failing_put_json(obj, opts=None, canon_spec=None, *, return_selected_profile=False):
        nonlocal should_fail
        kind = getattr(opts, "kind", None)
        if should_fail and kind == "core.run_manifest":
            should_fail = False
            raise OSError("simulated finalize crash")
        return original_put_json(
            obj,
            opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )

    monkeypatch.setattr(store, "put_json", _failing_put_json)

    with pytest.raises(OSError, match="simulated finalize crash"):
        ctx.finalize(status="ok")

    journal_path = run_dir / ".finalize-journal.json"
    assert journal_path.exists()

    monkeypatch.setattr(store, "put_json", original_put_json)
    loaded = load_core_run(store=store, run_dir=run_dir)

    assert loaded is not None
    assert loaded.status == "ok"
    assert loaded.manifest_ref is not None
    assert loaded.manifest_ref.manifest_profile_sha256 is not None
    recovered_manifest = store.get_manifest_by_profile(
        loaded.manifest_ref.artifact_id,
        loaded.manifest_ref.manifest_profile_sha256,
    )
    assert recovered_manifest.artifact_id == loaded.manifest_ref.artifact_id
    assert recovered_manifest.kind == "core.run_manifest"
    assert journal_path.exists() is False
    assert "RUN_FINALIZED" in (run_dir / "trace.jsonl").read_text(encoding="utf-8")


def _run_context_with_output(
    store: FileSystemCAS,
    tmp_path: Path,
    *,
    run_id: str,
    producer,
    env_info,
    tenant_id: str | None = None,
    cell_id: str | None = None,
) -> RunContext:
    bundle_ref = _bootstrap_registry_bundle(store)
    ctx = RunContext.start(
        store=store,
        registry_bundle=bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=tmp_path / "runs" / run_id,
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    ctx.add_output(
        store.put_json(
            {"result": "ok"},
            PutOptions(kind="core.output", media_type="application/json"),
        )
    )
    return ctx


def _terminal_records(run_dir: Path) -> list[TraceRecord]:
    records: list[TraceRecord] = []
    for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = TraceRecord.model_validate_json(line)
        if record.phase == "core" and record.event == "RUN_FINALIZED":
            records.append(record)
    return records


def _leave_pending_finalize_journal(
    ctx: RunContext,
    store: FileSystemCAS,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leave a valid journal after a real finalize attempt stops before its CAS write."""
    original_put_json = store.put_json

    def _fail_run_manifest_write(
        obj,
        opts=None,
        canon_spec=None,
        *,
        return_selected_profile=False,
    ):
        if getattr(opts, "kind", None) == "core.run_manifest":
            raise OSError("simulated finalize crash before manifest write")
        return original_put_json(
            obj,
            opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )

    monkeypatch.setattr(store, "put_json", _fail_run_manifest_write)
    try:
        with pytest.raises(OSError, match="before manifest write"):
            ctx.finalize(status="ok")
    finally:
        monkeypatch.setattr(store, "put_json", original_put_json)
    assert (ctx.trace_path.parent / ".finalize-journal.json").exists()


def _leave_current_terminal_journal(
    ctx: RunContext,
    monkeypatch: pytest.MonkeyPatch,
) -> TraceRecord:
    original_clear = run_context._clear_finalize_journal

    def _crash_after_terminal_append(_run_dir: Path) -> None:
        raise OSError("simulated crash after terminal append")

    monkeypatch.setattr(run_context, "_clear_finalize_journal", _crash_after_terminal_append)
    with pytest.raises(OSError, match="after terminal append"):
        ctx.finalize(status="ok")
    monkeypatch.setattr(run_context, "_clear_finalize_journal", original_clear)
    records = _terminal_records(ctx.trace_path.parent)
    assert len(records) == 1
    return records[0]


def _leave_legacy_profileless_terminal_journal(
    ctx: RunContext,
    store: FileSystemCAS,
) -> TraceRecord:
    run_dir = ctx.trace_path.parent
    ctx.run_manifest.status = "ok"
    ctx.run_manifest.finished_at = datetime.now(UTC).replace(microsecond=0)
    trace_ref = store.put_bytes(
        ctx.trace_path.read_bytes(),
        PutOptions(kind="core.trace.jsonl", media_type="application/jsonl"),
    )
    ctx._record_ref_owner(trace_ref, writer="RunContext.finalize.trace")
    ctx.run_manifest.trace_ref = trace_ref
    run_context._write_finalize_journal(run_dir, ctx.run_manifest)
    legacy_ref = store.put_json(
        ctx.run_manifest,
        run_context._run_manifest_write_options(ctx.run_manifest),
    )
    assert legacy_ref.manifest_profile_sha256 is None
    ctx._record_ref_owner(legacy_ref, writer="RunContext.finalize.manifest")
    ctx._emit_record(
        "core",
        "RUN_FINALIZED",
        run_terminality=RunTerminality.TERMINAL,
        outputs=[legacy_ref],
        metrics={"status_ok": 1},
    )
    # This is the old writer's durable state immediately before journal clear.
    records = _terminal_records(run_dir)
    assert len(records) == 1
    return records[0]


def _count_run_manifest_writes(
    store: FileSystemCAS,
    monkeypatch: pytest.MonkeyPatch,
) -> list[object]:
    original_put_json = store.put_json
    writes: list[object] = []

    def _counting_put_json(obj, opts=None, canon_spec=None, *, return_selected_profile=False):
        if getattr(opts, "kind", None) == "core.run_manifest":
            writes.append(obj)
        return original_put_json(
            obj,
            opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )

    monkeypatch.setattr(store, "put_json", _counting_put_json)
    return writes


def test_recovery_preserves_legacy_profileless_terminal_fact_without_replay(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.services.adapters.core_run import load_core_run

    ctx = _run_context_with_output(
        store, tmp_path, run_id="R_legacy_terminal", producer=producer, env_info=env_info
    )
    terminal = _leave_legacy_profileless_terminal_journal(ctx, store)
    legacy_ref = next(ref for ref in terminal.refs.outputs if ref.kind == "core.run_manifest")
    writes = _count_run_manifest_writes(store, monkeypatch)

    recovered = ctx.finalize(status="ok")

    assert recovered == legacy_ref
    assert recovered.manifest_profile_sha256 is None
    assert writes == []
    assert len(_terminal_records(ctx.trace_path.parent)) == 1
    assert (ctx.trace_path.parent / ".finalize-journal.json").exists() is False

    loaded = load_core_run(store=store, run_dir=ctx.trace_path.parent)
    assert loaded is not None
    assert loaded.run_terminality is RunTerminality.TERMINAL
    assert loaded.manifest_ref == legacy_ref
    assert loaded.manifest_ref.manifest_profile_sha256 is None


def test_completed_legacy_read_does_not_create_finalize_lock(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    from polisyos.runtime.http.services.adapters.core_run import load_core_run

    ctx = _run_context_with_output(
        store,
        tmp_path,
        run_id="R_legacy_completed_read_no_lock",
        producer=producer,
        env_info=env_info,
    )
    run_dir = ctx.trace_path.parent
    terminal = _leave_legacy_profileless_terminal_journal(ctx, store)
    run_context._clear_finalize_journal(run_dir)
    assert not (run_dir / ".finalize.lock").exists()

    loaded = load_core_run(store=store, run_dir=run_dir)

    assert loaded is not None
    assert loaded.manifest_ref is not None
    assert loaded.manifest_ref.manifest_profile_sha256 is None
    assert loaded.manifest_ref == terminal.refs.outputs[0]
    assert not (run_dir / ".finalize.lock").exists()


def test_recovery_reuses_current_full_terminal_ref_after_clear_crash(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.services.adapters.core_run import load_core_run

    ctx = _run_context_with_output(
        store, tmp_path, run_id="R_current_terminal", producer=producer, env_info=env_info
    )
    terminal = _leave_current_terminal_journal(ctx, monkeypatch)
    selected_ref = next(ref for ref in terminal.refs.outputs if ref.kind == "core.run_manifest")
    assert selected_ref.manifest_profile_sha256 is not None
    writes = _count_run_manifest_writes(store, monkeypatch)

    recovered = run_context.recover_pending_run_finalize(
        store,
        ctx.trace_path.parent,
        expected_owner=None,
    )

    assert recovered == selected_ref
    assert writes == []
    assert len(_terminal_records(ctx.trace_path.parent)) == 1
    loaded = load_core_run(store=store, run_dir=ctx.trace_path.parent)
    assert loaded is not None
    assert loaded.manifest_ref == selected_ref
    assert loaded.manifest_ref.manifest_profile_sha256 == selected_ref.manifest_profile_sha256


def test_recovery_completes_exact_matching_expected_owner(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _run_context_with_output(
        store, tmp_path, run_id="R_expected_owner_match", producer=producer, env_info=env_info
    )
    _leave_pending_finalize_journal(ctx, store, monkeypatch)
    expected_owner = (
        ctx.run_manifest.run_id,
        ctx.run_manifest.tenant_id,
        ctx.run_manifest.cell_id,
    )
    writes = _count_run_manifest_writes(store, monkeypatch)

    recovered = run_context.recover_pending_run_finalize(
        store,
        ctx.trace_path.parent,
        expected_owner=expected_owner,
    )

    assert recovered is not None
    assert len(writes) == 1
    assert writes[0].run_id == expected_owner[0]
    terminal = _terminal_records(ctx.trace_path.parent)
    assert len(terminal) == 1
    assert (terminal[0].run_id, terminal[0].tenant_id, terminal[0].cell_id) == expected_owner
    assert terminal[0].refs.outputs == [recovered]
    assert not (ctx.trace_path.parent / ".finalize-journal.json").exists()


def test_recovery_refuses_owner_swap_before_journal_or_mutation(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admitted = _run_context_with_output(
        store, tmp_path, run_id="R_expected_owner_scope", producer=producer, env_info=env_info
    )
    _leave_pending_finalize_journal(admitted, store, monkeypatch)
    admitted_dir = admitted.trace_path.parent
    admitted_trace = admitted_dir / "trace.jsonl"
    admitted_journal = admitted_dir / ".finalize-journal.json"
    admitted_trace_bytes = admitted_trace.read_bytes()
    admitted_journal_bytes = admitted_journal.read_bytes()
    expected_owner = (
        admitted.run_manifest.run_id,
        admitted.run_manifest.tenant_id,
        admitted.run_manifest.cell_id,
    )
    assert run_context._trace_run_started_identity(admitted_trace) == run_context._RunOwnerIdentity(
        run_id=expected_owner[0],
        tenant_id=expected_owner[1],
        cell_id=expected_owner[2],
    )

    foreign_tenant = "tenant_expected_owner_B"
    foreign_cell = "cell_expected_owner_B"
    with tenant_scope(None, tenant_id=foreign_tenant, cell_id=foreign_cell):
        foreign = _run_context_with_output(
            store,
            tmp_path / "foreign",
            run_id=expected_owner[0],
            producer=producer,
            env_info=env_info,
            tenant_id=foreign_tenant,
            cell_id=foreign_cell,
        )
        _leave_pending_finalize_journal(foreign, store, monkeypatch)
    foreign_dir = foreign.trace_path.parent
    foreign_trace_bytes = foreign.trace_path.read_bytes()
    foreign_journal_bytes = (foreign_dir / ".finalize-journal.json").read_bytes()
    foreign_trace_owner = run_context._trace_run_started_identity(foreign.trace_path)
    foreign_manifest = run_context._load_finalize_journal(foreign_dir)
    assert foreign_trace_owner is not None
    assert foreign_manifest is not None
    assert foreign_trace_owner == run_context._RunOwnerIdentity(
        run_id=expected_owner[0],
        tenant_id=foreign_tenant,
        cell_id=foreign_cell,
    )
    assert (
        run_context._RunOwnerIdentity(
            run_id=foreign_manifest.run_id,
            tenant_id=foreign_manifest.tenant_id,
            cell_id=foreign_manifest.cell_id,
        )
        == foreign_trace_owner
    )

    admitted_trace.write_bytes(foreign_trace_bytes)
    admitted_journal.write_bytes(foreign_journal_bytes)
    swapped_trace_bytes = admitted_trace.read_bytes()
    swapped_journal_bytes = admitted_journal.read_bytes()
    journal_loads: list[Path] = []
    trace_appends: list[Path] = []
    journal_clears: list[Path] = []
    original_load = run_context._load_finalize_journal
    original_append = run_context._append_run_finalized_event
    original_clear = run_context._clear_finalize_journal
    original_put_bytes = store.put_bytes

    def _observe_load(run_dir: Path):
        journal_loads.append(run_dir)
        return original_load(run_dir)

    def _observe_append(*, trace_path: Path, **kwargs) -> None:
        trace_appends.append(trace_path)
        original_append(trace_path=trace_path, **kwargs)

    def _observe_clear(run_dir: Path) -> None:
        journal_clears.append(run_dir)
        original_clear(run_dir)

    cas_writes: list[str] = []

    def _observe_put_bytes(*args, **kwargs):
        cas_writes.append("put_bytes")
        return original_put_bytes(*args, **kwargs)

    monkeypatch.setattr(run_context, "_load_finalize_journal", _observe_load)
    monkeypatch.setattr(run_context, "_append_run_finalized_event", _observe_append)
    monkeypatch.setattr(run_context, "_clear_finalize_journal", _observe_clear)
    monkeypatch.setattr(store, "put_bytes", _observe_put_bytes)
    writes = _count_run_manifest_writes(store, monkeypatch)

    with pytest.raises(
        ArtifactOwnershipError,
        match="run_finalize_expected_owner_mismatch",
    ):
        run_context.recover_pending_run_finalize(
            store,
            admitted_dir,
            expected_owner=expected_owner,
        )

    assert journal_loads == []
    assert writes == []
    assert cas_writes == []
    assert trace_appends == []
    assert journal_clears == []
    assert admitted_trace.read_bytes() == swapped_trace_bytes
    assert admitted_journal.read_bytes() == swapped_journal_bytes
    assert _terminal_records(admitted_dir) == []
    assert admitted_trace_bytes != swapped_trace_bytes
    assert admitted_journal_bytes != swapped_journal_bytes


def test_recovery_validates_expected_owner_shape_before_filesystem_io(
    store: FileSystemCAS,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_run_dir = tmp_path / "not-created"

    def _unexpected_path_io(_path, *args, **kwargs):
        raise AssertionError("malformed expected_owner reached filesystem access")

    monkeypatch.setattr(run_context.Path, "exists", _unexpected_path_io)

    with pytest.raises(TypeError, match="three-item tuple"):
        run_context.recover_pending_run_finalize(
            store,
            missing_run_dir,
            expected_owner=("R_malformed", None),  # type: ignore[arg-type]
        )


def test_recovery_writes_once_after_cas_before_event_crash(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.services.adapters.core_run import load_core_run

    ctx = _run_context_with_output(
        store, tmp_path, run_id="R_after_cas", producer=producer, env_info=env_info
    )
    original_emit = ctx._emit_record

    def _crash_before_terminal_event(phase, event, **kwargs):
        if phase == "core" and event == "RUN_FINALIZED":
            raise OSError("simulated crash after CAS write")
        return original_emit(phase, event, **kwargs)

    monkeypatch.setattr(ctx, "_emit_record", _crash_before_terminal_event)
    with pytest.raises(OSError, match="after CAS write"):
        ctx.finalize(status="ok")
    monkeypatch.setattr(ctx, "_emit_record", original_emit)
    assert (ctx.trace_path.parent / ".finalize-journal.json").exists()
    assert _terminal_records(ctx.trace_path.parent) == []

    loaded = load_core_run(store=store, run_dir=ctx.trace_path.parent)

    assert loaded is not None
    assert loaded.run_terminality is RunTerminality.TERMINAL
    assert loaded.manifest_ref is not None
    assert loaded.manifest_ref.manifest_profile_sha256 is not None
    assert len(_terminal_records(ctx.trace_path.parent)) == 1
    assert (ctx.trace_path.parent / ".finalize-journal.json").exists() is False


@pytest.mark.parametrize("conflict", ["duplicate-terminal", "foreign-owner"])
def test_recovery_refuses_conflicting_terminal_history_without_writes(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
    conflict: str,
) -> None:
    ctx = _run_context_with_output(
        store, tmp_path, run_id=f"R_conflict_{conflict}", producer=producer, env_info=env_info
    )
    terminal = _leave_current_terminal_journal(ctx, monkeypatch)
    trace_path = ctx.trace_path
    assert trace_path is not None
    if conflict == "duplicate-terminal":
        with trace_path.open("a", encoding="utf-8") as handle:
            handle.write(terminal.model_dump_json(exclude_none=True) + "\n")
    else:
        records = [
            TraceRecord.model_validate_json(line)
            for line in trace_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        index = next(i for i, record in enumerate(records) if record.event == "RUN_FINALIZED")
        records[index] = records[index].model_copy(update={"tenant_id": "foreign-tenant"})
        trace_path.write_text(
            "\n".join(record.model_dump_json(exclude_none=True) for record in records) + "\n",
            encoding="utf-8",
        )
    writes = _count_run_manifest_writes(store, monkeypatch)

    with pytest.raises(run_context._FinalizeRecoveryError):
        run_context.recover_pending_run_finalize(store, ctx.trace_path.parent)

    assert writes == []
    assert (ctx.trace_path.parent / ".finalize-journal.json").exists()
    assert len(_terminal_records(ctx.trace_path.parent)) == (
        2 if conflict == "duplicate-terminal" else 1
    )


def test_recovery_rejects_same_content_id_with_conflicting_manifest_profile(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _run_context_with_output(
        store, tmp_path, run_id="R_profile_conflict", producer=producer, env_info=env_info
    )
    terminal = _leave_current_terminal_journal(ctx, monkeypatch)
    original_ref = next(ref for ref in terminal.refs.outputs if ref.kind == "core.run_manifest")
    original_manifest = store.get_manifest(original_ref)
    conflicting_ref = store.put_bytes(
        store.get_bytes(original_ref),
        PutOptions(
            kind="core.run_manifest",
            media_type="application/json",
            schema=original_manifest.artifact_schema,
            producer=ProducerInfo(component="tests.foreign-run-manifest", version="0"),
            env=original_manifest.env,
            inputs=original_manifest.inputs,
        ),
        return_selected_profile=True,
    )
    assert conflicting_ref.artifact_id == original_ref.artifact_id
    assert conflicting_ref.manifest_profile_sha256 is not None
    assert conflicting_ref.manifest_profile_sha256 != original_ref.manifest_profile_sha256
    trace_path = ctx.trace_path
    assert trace_path is not None
    records = [
        TraceRecord.model_validate_json(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    index = next(i for i, record in enumerate(records) if record.event == "RUN_FINALIZED")
    records[index].refs.outputs = [
        conflicting_ref if ref.kind == "core.run_manifest" else ref
        for ref in records[index].refs.outputs
    ]
    trace_path.write_text(
        "\n".join(record.model_dump_json(exclude_none=True) for record in records) + "\n",
        encoding="utf-8",
    )
    writes = _count_run_manifest_writes(store, monkeypatch)

    with pytest.raises(
        run_context._FinalizeRecoveryError,
        match="run_finalize_manifest_write_profile_mismatch",
    ):
        run_context.recover_pending_run_finalize(store, ctx.trace_path.parent)

    assert writes == []
    assert (ctx.trace_path.parent / ".finalize-journal.json").exists()
    assert len(_terminal_records(ctx.trace_path.parent)) == 1


def test_recovery_refuses_terminal_event_when_cas_proof_is_deleted(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _run_context_with_output(
        store, tmp_path, run_id="R_missing_terminal_proof", producer=producer, env_info=env_info
    )
    terminal = _leave_current_terminal_journal(ctx, monkeypatch)
    selected_ref = next(ref for ref in terminal.refs.outputs if ref.kind == "core.run_manifest")
    blob_path, _ = store._paths(selected_ref.artifact_id)
    blob_path.unlink()
    writes = _count_run_manifest_writes(store, monkeypatch)

    with pytest.raises(run_context._FinalizeRecoveryError):
        run_context.recover_pending_run_finalize(store, ctx.trace_path.parent)

    assert writes == []
    assert (ctx.trace_path.parent / ".finalize-journal.json").exists()
    assert len(_terminal_records(ctx.trace_path.parent)) == 1


def test_core_loader_refuses_terminal_manifest_bytes_that_disagree_with_journal(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.services.adapters.core_run import load_core_run

    ctx = _run_context_with_output(
        store, tmp_path, run_id="R_payload_conflict", producer=producer, env_info=env_info
    )
    terminal = _leave_current_terminal_journal(ctx, monkeypatch)
    original_ref = next(ref for ref in terminal.refs.outputs if ref.kind == "core.run_manifest")
    changed_manifest = ctx.run_manifest.model_copy(update={"status": "failed"})
    conflicting_ref = store.put_json(
        changed_manifest,
        run_context._run_manifest_write_options(changed_manifest),
        return_selected_profile=True,
    )
    assert conflicting_ref.artifact_id != original_ref.artifact_id
    assert conflicting_ref.manifest_profile_sha256 is not None
    trace_path = ctx.trace_path
    assert trace_path is not None
    records = [
        TraceRecord.model_validate_json(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    index = next(i for i, record in enumerate(records) if record.event == "RUN_FINALIZED")
    records[index].refs.outputs = [
        conflicting_ref if ref.kind == "core.run_manifest" else ref
        for ref in records[index].refs.outputs
    ]
    trace_path.write_text(
        "\n".join(record.model_dump_json(exclude_none=True) for record in records) + "\n",
        encoding="utf-8",
    )
    writes = _count_run_manifest_writes(store, monkeypatch)

    with pytest.raises(run_context._FinalizeRecoveryError):
        load_core_run(store=store, run_dir=ctx.trace_path.parent)

    assert writes == []
    assert (ctx.trace_path.parent / ".finalize-journal.json").exists()
    assert len(_terminal_records(ctx.trace_path.parent)) == 1


def test_run_owner_snapshot_round_trips_through_core_canonical_codec(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_id = "R_owner_snapshot_core_canonical_round_trip"
    run_dir = tmp_path / "runs" / run_id
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id=run_id,
    )
    run.suspend_for_resume()

    trace_path = run_dir / "trace.jsonl"
    start = TraceRecord.model_validate_json(trace_path.read_text(encoding="utf-8").splitlines()[0])
    assert start.event == "RUN_STARTED"
    owner_ref = start.refs.outputs[0]
    payload = store.get_bytes(owner_ref)
    decoded = from_canonical_bytes(payload)

    assert isinstance(decoded, dict)
    assert decoded["schema_version"] == "1.0.2"
    assert "access_scope_sha256" in decoded
    assert decoded["access_scope_sha256"] is None
    assert "previous_snapshot_ref" in decoded
    assert decoded["previous_snapshot_ref"] is None
    assert "runtime_invocation_tail_ref" in decoded
    assert decoded["runtime_invocation_tail_ref"] is None
    assert isinstance(decoded["run_manifest"]["started_at"], datetime)
    snapshot = RunOwnerSnapshot.model_validate(decoded)
    assert snapshot.run_manifest.started_at == start.ts
    assert to_canonical_bytes(snapshot, CanonSpec(exclude_none=False)) == payload

    manifest = store.get_manifest(owner_ref)
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.version == "1.0.2"
    assert manifest.canon is not None
    assert manifest.canon.exclude_none is False
    assert manifest.inputs[0].artifact_id == bundle_ref.artifact_id
    assert manifest.inputs[0].manifest_profile_sha256 == bundle_ref.manifest_profile_sha256
    assert store.verify(owner_ref).ok


def test_legacy_v101_owner_bytes_remain_exact_and_read_as_unbound_history(
    store: FileSystemCAS,
    tmp_path: Path,
    producer: Any,
    env_info: Any,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_id = "R_owner_snapshot_legacy_v101_read"
    run_dir = tmp_path / "runs" / run_id
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id=run_id,
    )
    run.suspend_for_resume()

    legacy_snapshot = RunOwnerSnapshotV101(
        schema_version="1.0.1",
        run_manifest=run.run_manifest.model_copy(deep=True),
        access_scope_sha256=None,
        previous_snapshot_ref=None,
    )
    old_wire = to_canonical_bytes(legacy_snapshot, CanonSpec(exclude_none=False))
    legacy_ref = store.put_json(
        legacy_snapshot,
        run_context._run_owner_snapshot_write_options(legacy_snapshot),
        canon_spec=CanonSpec(exclude_none=False),
        return_selected_profile=True,
    )
    assert store.get_bytes(legacy_ref) == old_wire
    assert store.verify(legacy_ref).ok
    legacy_manifest = store.get_manifest(legacy_ref)
    assert legacy_manifest.artifact_schema is not None
    assert legacy_manifest.artifact_schema.version == "1.0.1"
    decoded_legacy = run_context._validate_run_owner_snapshot_ref(
        store,
        legacy_ref,
        require_registry_profile=False,
    )
    assert type(decoded_legacy) is RunOwnerSnapshotV101
    assert decoded_legacy.schema_version == "1.0.1"
    assert getattr(decoded_legacy, "runtime_invocation_tail_ref", None) is None

    trace_path = run_dir / "trace.jsonl"
    records = [
        TraceRecord.model_validate_json(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert records[0].event == "RUN_STARTED"
    records[0].refs.outputs = [legacy_ref]
    trace_path.write_text(
        "\n".join(record.model_dump_json(exclude_none=True) for record in records) + "\n",
        encoding="utf-8",
    )

    # Historical v1.0.1 owner chains remain readable, but an absent attempt tail
    # does not become a positive selection binding.
    assert run_context._read_runtime_invocation_attempts(store, trace_path, run_id=run_id) == []


@pytest.mark.parametrize(
    "damage",
    ["missing-access-scope", "missing-previous-snapshot", "legacy-r379-format"],
)
def test_run_owner_snapshot_refuses_missing_required_nullable_wire_fields(
    damage: str,
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_id = f"R_owner_snapshot_bad_wire_{damage}"
    run_dir = tmp_path / "runs" / run_id
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id=run_id,
    )
    run.suspend_for_resume()

    trace_path = run_dir / "trace.jsonl"
    records = [
        TraceRecord.model_validate_json(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    original_ref = records[0].refs.outputs[0]
    decoded = from_canonical_bytes(store.get_bytes(original_ref))
    assert isinstance(decoded, dict)
    valid_snapshot = RunOwnerSnapshot.model_validate(decoded)
    options = run_context._run_owner_snapshot_write_options(valid_snapshot)
    malformed = dict(decoded)
    canon_spec = CanonSpec(exclude_none=False)
    writer_options = options
    if damage == "missing-access-scope":
        malformed.pop("access_scope_sha256")
    elif damage == "missing-previous-snapshot":
        malformed.pop("previous_snapshot_ref")
    else:
        # Reproduce the exact R379 persisted profile: tagged datetime plus
        # excluded required-null fields, old schema and old CanonInfo.
        malformed["schema_version"] = "1.0.0"
        # The R379 Pydantic writer omitted these required nullable keys under
        # exclude_none=True; a raw dict would otherwise preserve explicit nulls.
        malformed.pop("access_scope_sha256")
        malformed.pop("previous_snapshot_ref")
        canon_spec = CanonSpec()
        writer_options = replace(
            options,
            schema=SchemaInfo(name=run_context._RUN_OWNER_SNAPSHOT_SCHEMA, version="1.0.0"),
            canon=CanonInfo.from_spec(canon_spec),
        )
    malformed_ref = store.put_json(
        malformed,
        writer_options,
        canon_spec=canon_spec,
        return_selected_profile=True,
    )
    if damage == "legacy-r379-format":
        legacy_manifest = store.get_manifest(malformed_ref)
        assert legacy_manifest.artifact_schema is not None
        assert legacy_manifest.artifact_schema.version == "1.0.0"
        assert legacy_manifest.canon is not None and legacy_manifest.canon.exclude_none is True
    records[0].refs.outputs = [malformed_ref]
    trace_path.write_text(
        "\n".join(record.model_dump_json(exclude_none=True) for record in records) + "\n",
        encoding="utf-8",
    )
    before = trace_path.read_bytes()

    with pytest.raises(
        run_context._FinalizeRecoveryError,
        match="run_resume_owner_snapshot_schema_invalid",
    ):
        RunContext.resume(
            store,
            run_id=run_id,
            run_dir=run_dir,
            registry_bundle=bundle_ref,
            producer=producer,
            env=env_info,
            access_scope=None,
        )

    assert trace_path.read_bytes() == before
    assert store.verify(malformed_ref).ok
    assert [record.event for record in _terminal_records(run_dir)] == []


@pytest.mark.parametrize(
    "damage",
    ["ownerless", "profileless", "deleted-bytes", "start-time", "registry-profileless"],
)
def test_incomplete_resume_requires_the_exact_selected_owner_snapshot(
    damage: str,
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(
        store, selected_profile=damage != "registry-profileless"
    )
    run_dir = tmp_path / "runs" / f"R_resume_owner_{damage}"
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id=f"R_resume_owner_{damage}",
    )
    run.suspend_for_resume()
    trace_path = run_dir / "trace.jsonl"
    records = [
        TraceRecord.model_validate_json(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    owner = records[0]
    assert owner.event == "RUN_STARTED"
    owner_ref = owner.refs.outputs[0]
    if damage == "ownerless":
        owner.refs.outputs = []
    elif damage == "profileless":
        owner.refs.outputs = [owner_ref.model_copy(update={"manifest_profile_sha256": None})]
    elif damage == "deleted-bytes":
        blob_path, _manifest_path = store._paths(owner_ref.artifact_id)
        blob_path.unlink()
    elif damage == "start-time":
        owner.ts += timedelta(seconds=1)
    else:
        assert damage == "registry-profileless"
    trace_path.write_text(
        "\n".join(record.model_dump_json(exclude_none=True) for record in records) + "\n",
        encoding="utf-8",
    )
    before = trace_path.read_bytes()

    with pytest.raises(run_context._FinalizeRecoveryError, match="run_resume_"):
        RunContext.resume(
            store,
            run_id=run.run_manifest.run_id,
            run_dir=run_dir,
            registry_bundle=bundle_ref,
            producer=producer,
            env=env_info,
            access_scope=None,
        )

    assert trace_path.read_bytes() == before
    assert [record.event for record in _terminal_records(run_dir)] == []


@pytest.mark.parametrize("mismatch", ["registry", "producer", "environment", "scope"])
def test_incomplete_resume_rejects_changed_owner_inputs(
    mismatch: str,
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    scope = AccessScope.for_service(
        tenant_id="tenant-resume-owner",
        cell_id="cell-resume-owner",
        spiffe_id="spiffe://policyos/resume-owner",
    )
    run_dir = tmp_path / "runs" / f"R_resume_owner_mismatch_{mismatch}"
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id=f"R_resume_owner_mismatch_{mismatch}",
        tenant_id=scope.tenant_id,
        cell_id=scope.cell_id,
        access_scope=scope,
    )
    run.suspend_for_resume()
    before = (run_dir / "trace.jsonl").read_bytes()
    resume_registry = bundle_ref
    resume_producer = producer
    resume_env = env_info
    resume_scope = scope
    if mismatch == "registry":
        current = bundle_ref.manifest_profile_sha256
        replacement = "0" if current is None or current[7] != "0" else "1"
        resume_registry = bundle_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + replacement * 64}
        )
    elif mismatch == "producer":
        resume_producer = producer.model_copy(update={"version": f"{producer.version}-different"})
    elif mismatch == "environment":
        resume_env = env_info.model_copy(update={"platform": f"{env_info.platform}-different"})
    else:
        resume_scope = AccessScope.for_service(
            tenant_id=scope.tenant_id,
            cell_id=scope.cell_id,
            spiffe_id="spiffe://policyos/other-owner",
        )

    with pytest.raises(
        run_context._FinalizeRecoveryError,
        match="run_resume_owner_inputs_mismatch",
    ):
        RunContext.resume(
            store,
            run_id=run.run_manifest.run_id,
            run_dir=run_dir,
            registry_bundle=resume_registry,
            producer=resume_producer,
            env=resume_env,
            access_scope=resume_scope,
        )

    assert (run_dir / "trace.jsonl").read_bytes() == before
    assert [record.event for record in _terminal_records(run_dir)] == []


def test_incomplete_resume_restores_versioned_manifest_and_finishes_once(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    from polisyos.runtime.http.services.adapters.core_run import load_core_run

    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_id = "R_resume_owner_snapshot_chain"
    run_dir = tmp_path / "runs" / run_id
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id=run_id,
    )
    run.update_manifest(execution_profile="profile-e02", control_job_id="job-e02")
    output_ref = store.put_json(
        {"result": "resume"},
        PutOptions(kind="core.output", media_type="application/json"),
    )
    run.add_output(output_ref)
    run.suspend_for_resume()

    resumed = RunContext.resume(
        store,
        run_id=run_id,
        run_dir=run_dir,
        registry_bundle=bundle_ref,
        producer=producer,
        env=env_info,
        access_scope=None,
    )
    assert resumed.run_manifest.execution_profile == "profile-e02"
    assert resumed.run_manifest.control_job_id == "job-e02"
    assert resumed.run_manifest.outputs == [output_ref]
    run_ref = resumed.finalize(status="ok")

    records = [
        TraceRecord.model_validate_json(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert sum(record.event == "RUN_STARTED" for record in records) == 1
    assert sum(record.event == "RUN_CONTEXT_SNAPSHOT" for record in records) == 1
    assert sum(record.event == "RUN_RESUMED" for record in records) == 1
    assert sum(record.event == "RUN_FINALIZED" for record in records) == 1
    terminal = load_core_run(store=store, run_dir=run_dir)
    assert terminal is not None
    assert terminal.manifest_ref == run_ref
    assert terminal.run_terminality is RunTerminality.TERMINAL


def test_start_refuses_a_second_start_but_allows_explicit_resume(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_id = "R_start_then_explicit_resume"
    run_dir = tmp_path / "runs" / run_id
    first = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id=run_id,
    )
    first.suspend_for_resume()
    trace_path = run_dir / "trace.jsonl"
    before = trace_path.read_bytes()

    with pytest.raises(
        run_context._FinalizeRecoveryError,
        match="run_start_existing_lifecycle",
    ):
        RunContext.start(
            store,
            bundle_ref,
            producer=producer,
            env=env_info,
            run_dir=run_dir,
            run_id=run_id,
        )

    assert trace_path.read_bytes() == before
    resumed = RunContext.resume(
        store,
        run_id=run_id,
        run_dir=run_dir,
        registry_bundle=bundle_ref,
        producer=producer,
        env=env_info,
        access_scope=None,
    )
    resumed.finalize(status="ok")
    assert len(_terminal_records(run_dir)) == 1


def test_tenant_run_snapshot_resume_and_terminal_profiles_keep_manifest_owner(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    tenant_id = "tenant-run-owner-profile"
    cell_id = "cell-run-owner-profile"
    scope = AccessScope.for_service(
        tenant_id=tenant_id,
        cell_id=cell_id,
        spiffe_id="spiffe://policyos/run-owner-profile",
    )
    tenant_store = store.for_tenant(tenant_id, cell_id)
    run_id = "R_tenant_owner_profile_replay"
    run_dir = tmp_path / "runs" / run_id

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        bundle_ref = _bootstrap_registry_bundle(tenant_store, selected_profile=True)
        run = RunContext.start(
            tenant_store,
            bundle_ref,
            producer=producer,
            env=env_info,
            run_dir=run_dir,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            access_scope=scope,
        )
        first_owner_ref = run._owner_snapshot_ref
        assert first_owner_ref is not None
        expected_context = ArtifactTenantContextInfo(tenant_id=tenant_id, cell_id=cell_id)
        assert tenant_store.get_manifest(first_owner_ref).tenant_context == expected_context

        run.update_manifest(execution_profile="tenant-bound")
        updated_owner_ref = run._owner_snapshot_ref
        assert updated_owner_ref is not None
        assert tenant_store.get_manifest(updated_owner_ref).tenant_context == expected_context
        run.suspend_for_resume()

        resumed = RunContext.resume(
            tenant_store,
            run_id=run_id,
            run_dir=run_dir,
            registry_bundle=bundle_ref,
            producer=producer,
            env=env_info,
            access_scope=scope,
        )
        assert resumed.run_manifest.execution_profile == "tenant-bound"
        resumed_owner_ref = resumed._owner_snapshot_ref
        assert resumed_owner_ref is not None
        assert tenant_store.get_manifest(resumed_owner_ref).tenant_context == expected_context
        terminal_ref = resumed.finalize(status="ok")
        assert tenant_store.get_manifest(terminal_ref).tenant_context == expected_context
        with pytest.raises(
            run_context._FinalizeRecoveryError,
            match="run_finalize_manifest_ref_contract_mismatch",
        ):
            run_context._validate_terminal_run_manifest_ref(
                tenant_store,
                run_manifest=resumed.run_manifest,
                run_ref=terminal_ref.model_copy(update={"manifest_profile_sha256": None}),
                require_selected_profile=False,
            )

    terminal_records = _terminal_records(run_dir)
    assert len(terminal_records) == 1
    assert terminal_records[0].refs.outputs == [terminal_ref]


@pytest.mark.parametrize(
    ("run_tenant_id", "run_cell_id", "stored_tenant_id", "stored_cell_id"),
    [
        ("tenant-owner", "cell-owner", "tenant-other", "cell-owner"),
        ("tenant-owner", "cell-owner", "tenant-owner", "cell-other"),
        (None, None, "tenant-unclaimed", "cell-unclaimed"),
    ],
)
def test_owner_snapshot_refuses_supplied_tenant_profile_that_disagrees_with_run_owner(
    run_tenant_id: str | None,
    run_cell_id: str | None,
    stored_tenant_id: str,
    stored_cell_id: str,
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_id = f"R_owner_profile_mismatch_{stored_tenant_id}_{stored_cell_id}"
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=tmp_path / "runs" / run_id,
        run_id=run_id,
        tenant_id=run_tenant_id,
        cell_id=run_cell_id,
    )
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    snapshot = run_context._validate_run_owner_snapshot_ref(store, owner_ref)
    options = run_context._run_owner_snapshot_write_options(snapshot)
    wrong_profile_ref = _write_selected_manifest_view_for_test(
        store,
        owner_ref,
        replace(
            options,
            tenant_context=ArtifactTenantContextInfo(
                tenant_id=stored_tenant_id,
                cell_id=stored_cell_id,
            ),
        ),
    )

    with pytest.raises(
        run_context._FinalizeRecoveryError,
        match="run_resume_owner_snapshot_tenant_context_mismatch",
    ):
        run_context._validate_run_owner_snapshot_ref(store, wrong_profile_ref)
    run.suspend_for_resume()


def test_owner_snapshot_accepts_only_exact_selected_legacy_profile_without_tenant_context(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_id = "R_owner_snapshot_legacy_profile"
    scope = AccessScope.for_service(
        tenant_id="tenant-legacy-owner",
        cell_id="cell-legacy-owner",
        spiffe_id="spiffe://policyos/legacy-owner",
    )
    run_dir = tmp_path / "runs" / run_id
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id=run_id,
        tenant_id=scope.tenant_id,
        cell_id=scope.cell_id,
        access_scope=scope,
    )
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    snapshot = run_context._validate_run_owner_snapshot_ref(store, owner_ref)
    legacy_options = replace(
        run_context._run_owner_snapshot_write_options(snapshot),
        tenant_context=None,
    )
    legacy_ref = _write_selected_manifest_view_for_test(
        store,
        owner_ref,
        legacy_options,
    )
    assert legacy_ref.manifest_profile_sha256 is not None
    assert store.get_manifest(legacy_ref).tenant_context is None
    assert run_context._validate_run_owner_snapshot_ref(store, legacy_ref) == snapshot

    trace_path = run_dir / "trace.jsonl"
    start_record = TraceRecord.model_validate_json(trace_path.read_text(encoding="utf-8"))
    start_record = start_record.model_copy(
        update={
            "refs": TraceRefs(
                inputs=start_record.refs.inputs,
                outputs=[legacy_ref],
            )
        }
    )
    trace_path.write_text(start_record.model_dump_json(exclude_none=True) + "\n", encoding="utf-8")
    run.suspend_for_resume()
    resumed = RunContext.resume(
        store,
        run_id=run_id,
        run_dir=run_dir,
        registry_bundle=bundle_ref,
        producer=producer,
        env=env_info,
        access_scope=scope,
    )
    assert resumed.run_manifest.tenant_id == scope.tenant_id
    terminal_ref = resumed.finalize(status="ok")
    assert store.get_manifest(terminal_ref).tenant_context == ArtifactTenantContextInfo(
        tenant_id=scope.tenant_id,
        cell_id=scope.cell_id,
    )

    profileless_ref = legacy_ref.model_copy(update={"manifest_profile_sha256": None})
    with pytest.raises(
        run_context._FinalizeRecoveryError,
        match="run_resume_owner_snapshot_ref_invalid",
    ):
        run_context._validate_run_owner_snapshot_ref(store, profileless_ref)
    monkeypatch.setattr(FileSystemCAS, "get_raw_manifest_bytes", None)
    with pytest.raises(
        run_context._FinalizeRecoveryError,
        match="run_resume_owner_snapshot_tenant_context_mismatch_legacy_profile_not_proven",
    ):
        run_context._validate_run_owner_snapshot_ref(store, legacy_ref)
    monkeypatch.undo()

    legacy_view_path = store._layout.view_manifest_path(
        legacy_ref.artifact_id,
        legacy_ref.manifest_profile_sha256,
    )
    legacy_view_path.write_bytes(legacy_view_path.read_bytes() + b" ")
    with pytest.raises(
        run_context._FinalizeRecoveryError,
        match="run_resume_owner_snapshot_tenant_context_mismatch_legacy_profile_mismatch",
    ):
        run_context._validate_run_owner_snapshot_ref(store, legacy_ref)


def test_worker_trace_receipt_merges_once_through_parent_context(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_dir = tmp_path / "runs" / "R_worker_receipt_merge"
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id="R_worker_receipt_merge",
    )
    output_ref = store.put_json(
        {"candidate": "worker output"},
        PutOptions(kind="core.worker_candidate", media_type="application/json"),
        return_selected_profile=True,
    )
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    event = TraceRecord(
        run_id=run.run_manifest.run_id,
        phase="worker",
        event="NODE_OUTPUT_CANDIDATE",
        tenant_id=run.tenant_id,
        cell_id=run.cell_id,
        refs={"outputs": [output_ref]},
    )
    before = (run_dir / "trace.jsonl").read_bytes()
    invocation_id = "a" * 64

    run.merge_worker_events(
        invocation_id=invocation_id,
        dispatch_sha256="1" * 64,
        owner_snapshot_ref=owner_ref,
        records=[event],
    )

    records = [
        TraceRecord.model_validate_json(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [record.event for record in records[1:]] == [
        "WORKER_INVOCATION_STARTED",
        "NODE_OUTPUT_CANDIDATE",
        "WORKER_INVOCATION_COMPLETED",
    ]
    assert records[1].worker_invocation_id == invocation_id
    assert records[2].worker_invocation_id == invocation_id
    assert records[3].worker_invocation_id == invocation_id
    assert records[1].worker_dispatch_sha256 == "1" * 64
    assert records[2].worker_dispatch_sha256 == "1" * 64
    assert records[3].worker_dispatch_sha256 == "1" * 64
    assert records[2].ts == event.ts
    assert records[1].refs.inputs == [owner_ref]
    assert records[1].worker_receipt_count == 1
    assert store.verify(output_ref).ok
    assert (run_dir / "trace.jsonl").read_bytes() != before

    after = (run_dir / "trace.jsonl").read_bytes()
    with pytest.raises(run_context._FinalizeRecoveryError, match="worker_receipt_replay"):
        run.merge_worker_events(
            invocation_id=invocation_id,
            dispatch_sha256="1" * 64,
            owner_snapshot_ref=owner_ref,
            records=[event],
        )
    assert (run_dir / "trace.jsonl").read_bytes() == after
    run.suspend_for_resume()


def test_worker_receipt_applies_verified_run_manifest_and_io_operations(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_dir = tmp_path / "runs" / "R_worker_manifest_operations"
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id="R_worker_manifest_operations",
    )
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    input_ref = store.put_json(
        {"source": "worker input"},
        PutOptions(kind="core.worker_input", media_type="application/json"),
        return_selected_profile=True,
    )
    output_ref = store.put_json(
        {"source": "worker output"},
        PutOptions(kind="core.worker_output", media_type="application/json"),
        return_selected_profile=True,
    )
    worker_manifest = run.run_manifest.model_copy(deep=True)
    worker_manifest.execution_profile = "candidate-profile"
    updated_owner_ref = run_context._persist_run_owner_snapshot(
        store,
        run_manifest=worker_manifest,
        access_scope_sha256=run_context._access_scope_sha256(run.access_scope),
        previous_snapshot_ref=owner_ref,
    )
    records = [
        TraceRecord(
            run_id=run.run_manifest.run_id,
            phase="core",
            event="RUN_CONTEXT_SNAPSHOT",
            tenant_id=run.tenant_id,
            cell_id=run.cell_id,
            refs={"outputs": [updated_owner_ref]},
        ),
        TraceRecord(
            run_id=run.run_manifest.run_id,
            phase="core",
            event="RUN_INPUT_ADDED",
            tenant_id=run.tenant_id,
            cell_id=run.cell_id,
            refs={"inputs": [input_ref]},
        ),
        TraceRecord(
            run_id=run.run_manifest.run_id,
            phase="core",
            event="RUN_OUTPUT_ADDED",
            tenant_id=run.tenant_id,
            cell_id=run.cell_id,
            refs={"outputs": [output_ref]},
        ),
    ]

    run.merge_worker_events(
        invocation_id="f" * 64,
        dispatch_sha256="6" * 64,
        owner_snapshot_ref=owner_ref,
        records=records,
    )

    assert run.run_manifest.execution_profile == "candidate-profile"
    assert run.run_manifest.inputs[-1] == input_ref
    assert run.run_manifest.outputs[-1] == output_ref
    assert run._owner_snapshot_ref == updated_owner_ref
    durable = [
        TraceRecord.model_validate_json(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [record.event for record in durable[-5:]] == [
        "WORKER_INVOCATION_STARTED",
        "RUN_CONTEXT_SNAPSHOT",
        "RUN_INPUT_ADDED",
        "RUN_OUTPUT_ADDED",
        "WORKER_INVOCATION_COMPLETED",
    ]
    assert durable[-3].refs.inputs == [input_ref]
    assert durable[-2].refs.outputs == [output_ref]
    run.suspend_for_resume()


def test_worker_receipt_recovers_typed_operation_prefix_without_reapplying_effects(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_dir = tmp_path / "runs" / "R_worker_operation_prefix"
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id="R_worker_operation_prefix",
    )
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    input_ref = store.put_json(
        {"source": "worker input"},
        PutOptions(kind="core.worker_input", media_type="application/json"),
        return_selected_profile=True,
    )
    worker_manifest = run.run_manifest.model_copy(deep=True)
    worker_manifest.execution_profile = "worker-profile-after-prefix"
    updated_owner_ref = run_context._persist_run_owner_snapshot(
        store,
        run_manifest=worker_manifest,
        access_scope_sha256=run_context._access_scope_sha256(run.access_scope),
        previous_snapshot_ref=owner_ref,
    )
    events = [
        TraceRecord(
            run_id=run.run_manifest.run_id,
            phase="core",
            event="RUN_CONTEXT_SNAPSHOT",
            tenant_id=run.tenant_id,
            cell_id=run.cell_id,
            refs={"outputs": [updated_owner_ref]},
        ),
        TraceRecord(
            run_id=run.run_manifest.run_id,
            phase="core",
            event="RUN_INPUT_ADDED",
            tenant_id=run.tenant_id,
            cell_id=run.cell_id,
            refs={"inputs": [input_ref]},
        ),
    ]
    sink = run.trace
    emit_many = sink.emit_many

    def _append_typed_prefix(records) -> None:
        emit_many(records[:3])
        raise OSError("simulated crash after typed operation prefix")

    monkeypatch.setattr(sink, "emit_many", _append_typed_prefix)
    with pytest.raises(OSError, match="typed operation prefix"):
        run.merge_worker_events(
            invocation_id="7" * 64,
            dispatch_sha256="8" * 64,
            owner_snapshot_ref=owner_ref,
            records=events,
        )
    durable_prefix = (run_dir / "trace.jsonl").read_bytes()
    assert run.run_manifest.execution_profile is None
    assert input_ref not in run.run_manifest.inputs
    with pytest.raises(
        run_context._FinalizeRecoveryError,
        match="worker_receipt_prefix_binding_mismatch",
    ):
        run.merge_worker_events(
            invocation_id="7" * 64,
            dispatch_sha256="9" * 64,
            owner_snapshot_ref=owner_ref,
            records=events,
        )
    assert (run_dir / "trace.jsonl").read_bytes() == durable_prefix
    monkeypatch.setattr(sink, "emit_many", emit_many)

    run.merge_worker_events(
        invocation_id="7" * 64,
        dispatch_sha256="8" * 64,
        owner_snapshot_ref=owner_ref,
        records=events,
    )

    assert run.run_manifest.execution_profile == "worker-profile-after-prefix"
    assert run.run_manifest.inputs.count(input_ref) == 1
    durable = [
        TraceRecord.model_validate_json(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert sum(record.event == "RUN_CONTEXT_SNAPSHOT" for record in durable) == 1
    assert sum(record.event == "RUN_INPUT_ADDED" for record in durable) == 1
    assert sum(record.event == "WORKER_INVOCATION_COMPLETED" for record in durable) == 1
    run.suspend_for_resume()


def test_worker_trace_receipt_recovers_only_an_exact_complete_record_prefix(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_dir = tmp_path / "runs" / "R_worker_receipt_prefix"
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id="R_worker_receipt_prefix",
    )
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    events = [
        TraceRecord(
            run_id=run.run_manifest.run_id,
            phase="worker",
            event=f"candidate_{index}",
            tenant_id=run.tenant_id,
            cell_id=run.cell_id,
        )
        for index in range(2)
    ]
    sink = run.trace
    emit_many = sink.emit_many

    def _append_only_prefix(records) -> None:
        emit_many(records[:2])
        raise OSError("simulated crash after a complete JSONL record prefix")

    monkeypatch.setattr(sink, "emit_many", _append_only_prefix)
    with pytest.raises(OSError, match="simulated crash"):
        run.merge_worker_events(
            invocation_id="b" * 64,
            dispatch_sha256="2" * 64,
            owner_snapshot_ref=owner_ref,
            records=events,
        )
    prefix = (run_dir / "trace.jsonl").read_bytes()
    monkeypatch.setattr(sink, "emit_many", emit_many)

    run.merge_worker_events(
        invocation_id="b" * 64,
        dispatch_sha256="2" * 64,
        owner_snapshot_ref=owner_ref,
        records=events,
    )

    records = [
        TraceRecord.model_validate_json(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert sum(record.event == "WORKER_INVOCATION_STARTED" for record in records) == 1
    assert sum(record.event == "candidate_0" for record in records) == 1
    assert sum(record.event == "candidate_1" for record in records) == 1
    assert sum(record.event == "WORKER_INVOCATION_COMPLETED" for record in records) == 1
    assert (run_dir / "trace.jsonl").read_bytes().startswith(prefix)
    run.suspend_for_resume()


def test_incomplete_worker_receipt_refuses_resume_and_finalization(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_id = "R_worker_incomplete_resume_refusal"
    run_dir = tmp_path / "runs" / run_id
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id=run_id,
    )
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    events = [
        TraceRecord(
            run_id=run_id,
            phase="worker",
            event="candidate",
            tenant_id=run.tenant_id,
            cell_id=run.cell_id,
        )
    ]
    sink = run.trace
    emit_many = sink.emit_many

    def _append_start_only(records) -> None:
        emit_many(records[:1])
        raise OSError("simulated crash after receipt start")

    monkeypatch.setattr(sink, "emit_many", _append_start_only)
    with pytest.raises(OSError, match="receipt start"):
        run.merge_worker_events(
            invocation_id="9" * 64,
            dispatch_sha256="a" * 64,
            owner_snapshot_ref=owner_ref,
            records=events,
        )
    before = (run_dir / "trace.jsonl").read_bytes()

    with pytest.raises(run_context._FinalizeRecoveryError, match="worker_receipt_incomplete"):
        run.finalize(status="ok")

    assert (run_dir / "trace.jsonl").read_bytes() == before
    assert not store.root.joinpath("runs", run_id, "finalized.json").exists()
    with pytest.raises(run_context._FinalizeRecoveryError, match="worker_receipt_incomplete"):
        RunContext.resume(
            store,
            run_id=run_id,
            run_dir=run_dir,
            registry_bundle=bundle_ref,
            producer=producer,
            env=env_info,
            access_scope=None,
        )
    assert (run_dir / "trace.jsonl").read_bytes() == before


def test_resume_recovers_exact_incomplete_worker_prefix_without_double_applying_manifest_ops(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_id = "R_worker_resume_prefix_recovery"
    run_dir = tmp_path / "runs" / run_id
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id=run_id,
    )
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    input_ref = store.put_json(
        {"source": "worker input"},
        PutOptions(kind="core.worker_input", media_type="application/json"),
        return_selected_profile=True,
    )
    worker_manifest = run.run_manifest.model_copy(deep=True)
    worker_manifest.execution_profile = "resumed-worker-profile"
    updated_owner_ref = run_context._persist_run_owner_snapshot(
        store,
        run_manifest=worker_manifest,
        access_scope_sha256=run_context._access_scope_sha256(run.access_scope),
        previous_snapshot_ref=owner_ref,
    )
    events = [
        TraceRecord(
            run_id=run_id,
            phase="core",
            event="RUN_CONTEXT_SNAPSHOT",
            tenant_id=run.tenant_id,
            cell_id=run.cell_id,
            refs={"outputs": [updated_owner_ref]},
        ),
        TraceRecord(
            run_id=run_id,
            phase="core",
            event="RUN_INPUT_ADDED",
            tenant_id=run.tenant_id,
            cell_id=run.cell_id,
            refs={"inputs": [input_ref]},
        ),
    ]
    invocation_id = "e" * 64
    dispatch_digest = "f" * 64
    sink = run.trace
    emit_many = sink.emit_many

    def _append_complete_snapshot_prefix(records) -> None:
        emit_many(records[:2])
        raise OSError("simulated worker writer crash after snapshot prefix")

    monkeypatch.setattr(sink, "emit_many", _append_complete_snapshot_prefix)
    with pytest.raises(OSError, match="snapshot prefix"):
        run.merge_worker_events(
            invocation_id=invocation_id,
            dispatch_sha256=dispatch_digest,
            owner_snapshot_ref=owner_ref,
            records=events,
        )
    prefix = (run_dir / "trace.jsonl").read_bytes()

    # Model process death: OS releases the lease, but no lifecycle cleanup or
    # trace repair ran in the crashed writer.
    assert run._active_lease is not None
    run._active_lease.release()
    run._active_lease = None
    run._closed = True
    run._suspended = True

    with pytest.raises(run_context._FinalizeRecoveryError, match="worker_receipt_incomplete"):
        RunContext.resume(
            store,
            run_id=run_id,
            run_dir=run_dir,
            registry_bundle=bundle_ref,
            producer=producer,
            env=env_info,
            access_scope=None,
            allow_incomplete_worker_invocation_id="1" * 64,
        )
    assert (run_dir / "trace.jsonl").read_bytes() == prefix

    resumed = RunContext.resume(
        store,
        run_id=run_id,
        run_dir=run_dir,
        registry_bundle=bundle_ref,
        producer=producer,
        env=env_info,
        access_scope=None,
        allow_incomplete_worker_invocation_id=invocation_id,
    )
    assert resumed._owner_snapshot_ref == owner_ref
    assert resumed.run_manifest.execution_profile is None
    assert input_ref not in resumed.run_manifest.inputs

    resumed.merge_worker_events(
        invocation_id=invocation_id,
        dispatch_sha256=dispatch_digest,
        owner_snapshot_ref=owner_ref,
        records=events,
    )
    assert resumed.run_manifest.execution_profile == "resumed-worker-profile"
    assert resumed.run_manifest.inputs.count(input_ref) == 1
    assert resumed._owner_snapshot_ref == updated_owner_ref
    records = [
        TraceRecord.model_validate_json(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert sum(record.event == "RUN_CONTEXT_SNAPSHOT" for record in records) == 1
    assert sum(record.event == "RUN_INPUT_ADDED" for record in records) == 1
    assert sum(record.event == "WORKER_INVOCATION_STARTED" for record in records) == 1
    assert sum(record.event == "WORKER_INVOCATION_COMPLETED" for record in records) == 1
    assert (run_dir / "trace.jsonl").read_bytes().startswith(prefix)
    resumed.suspend_for_resume()


def test_completed_worker_receipt_resume_checks_exact_event_body(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_id = "R_worker_receipt_body_binding"
    run_dir = tmp_path / "runs" / run_id
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id=run_id,
    )
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    event = TraceRecord(
        run_id=run_id,
        phase="worker",
        event="candidate_original",
        tenant_id=run.tenant_id,
        cell_id=run.cell_id,
    )
    run.merge_worker_events(
        invocation_id="b" * 64,
        dispatch_sha256="c" * 64,
        owner_snapshot_ref=owner_ref,
        records=[event],
    )
    run.suspend_for_resume()

    trace_path = run_dir / "trace.jsonl"
    records = [
        TraceRecord.model_validate_json(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    event_index = next(
        index for index, record in enumerate(records) if record.event == "candidate_original"
    )
    records[event_index] = records[event_index].model_copy(update={"event": "candidate_tampered"})
    trace_path.write_text(
        "".join(f"{record.model_dump_json(exclude_none=True)}\n" for record in records),
        encoding="utf-8",
    )
    before = trace_path.read_bytes()

    with pytest.raises(
        run_context._FinalizeRecoveryError,
        match="worker_receipt_completed_body_mismatch",
    ):
        RunContext.resume(
            store,
            run_id=run_id,
            run_dir=run_dir,
            registry_bundle=bundle_ref,
            producer=producer,
            env=env_info,
            access_scope=None,
        )

    assert trace_path.read_bytes() == before


def test_worker_trace_receipt_concurrent_replay_is_admitted_once(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_dir = tmp_path / "runs" / "R_worker_receipt_concurrent_replay"
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id="R_worker_receipt_concurrent_replay",
    )
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    event = TraceRecord(
        run_id=run.run_manifest.run_id,
        phase="worker",
        event="candidate",
        tenant_id=run.tenant_id,
        cell_id=run.cell_id,
    )

    def _merge() -> str:
        try:
            run.merge_worker_events(
                invocation_id="e" * 64,
                dispatch_sha256="5" * 64,
                owner_snapshot_ref=owner_ref,
                records=[event],
            )
        except run_context._FinalizeRecoveryError as exc:
            return str(exc)
        return "accepted"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _index: _merge(), range(2)))

    assert outcomes.count("accepted") == 1
    assert outcomes.count("worker_receipt_replay_refused") == 1
    records = [
        TraceRecord.model_validate_json(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert sum(record.event == "candidate" for record in records) == 1
    assert sum(record.event == "WORKER_INVOCATION_STARTED" for record in records) == 1
    assert sum(record.event == "WORKER_INVOCATION_COMPLETED" for record in records) == 1
    run.suspend_for_resume()


@pytest.mark.parametrize(
    ("tail", "reason"),
    [
        (b'{"partial":\xff', "run_resume_trace_unreadable"),
        (b'{"partial":', "run_resume_trace_record_invalid"),
    ],
)
def test_worker_trace_receipt_refuses_malformed_tail_without_mutation(
    tail: bytes,
    reason: str,
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_dir = tmp_path / "runs" / "R_worker_receipt_malformed_tail"
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id="R_worker_receipt_malformed_tail",
    )
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    trace_path = run_dir / "trace.jsonl"
    with trace_path.open("ab") as handle:
        handle.write(tail)
    before = trace_path.read_bytes()

    with pytest.raises(run_context._FinalizeRecoveryError, match=reason):
        run.merge_worker_events(
            invocation_id="c" * 64,
            dispatch_sha256="3" * 64,
            owner_snapshot_ref=owner_ref,
            records=[],
        )

    assert trace_path.read_bytes() == before
    assert run._active_lease is not None
    run._active_lease.release()
    run._active_lease = None
    run._closed = True


@pytest.mark.parametrize("damage", ["stale_owner", "lifecycle_event"])
def test_worker_trace_receipt_refuses_stale_or_lifecycle_input_without_mutation(
    damage: str,
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_dir = tmp_path / "runs" / f"R_worker_receipt_{damage}"
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id=f"R_worker_receipt_{damage}",
    )
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    if damage == "stale_owner":
        run.update_manifest(execution_profile="updated-after-dispatch")
        records = [
            TraceRecord(
                run_id=run.run_manifest.run_id,
                phase="worker",
                event="candidate",
                tenant_id=run.tenant_id,
                cell_id=run.cell_id,
            )
        ]
        expected = "worker_merge_owner_snapshot_stale"
    else:
        records = [
            TraceRecord(
                run_id=run.run_manifest.run_id,
                phase="worker",
                event="RUN_FINALIZED",
                tenant_id=run.tenant_id,
                cell_id=run.cell_id,
            )
        ]
        expected = "worker_merge_record_scope_or_authority_invalid"
    before = (run_dir / "trace.jsonl").read_bytes()

    with pytest.raises(run_context._FinalizeRecoveryError, match=expected):
        run.merge_worker_events(
            invocation_id="d" * 64,
            dispatch_sha256="4" * 64,
            owner_snapshot_ref=owner_ref,
            records=records,
        )

    assert (run_dir / "trace.jsonl").read_bytes() == before
    run.suspend_for_resume()


def test_start_requires_selected_profile_writer_before_creating_run_state(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store)
    original_put_json = store.put_json

    def legacy_writer(obj, opts, canon_spec=None):
        return original_put_json(obj, opts, canon_spec)

    monkeypatch.setattr(store, "put_json", legacy_writer)
    run_dir = tmp_path / "runs" / "R_selected_profile_writer_required"

    with pytest.raises(
        NotImplementedError,
        match="artifact_store_return_selected_profile_unsupported",
    ):
        RunContext.start(
            store,
            bundle_ref,
            producer=producer,
            env=env_info,
            run_dir=run_dir,
            run_id="R_selected_profile_writer_required",
        )

    assert not run_dir.exists()


@pytest.mark.parametrize("entry_name", ["trace.jsonl", ".finalize-journal.json"])
def test_start_refuses_a_broken_lifecycle_symlink(
    entry_name: str,
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_id = f"R_broken_lifecycle_link_{entry_name.replace('.', '_')}"
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    entry_path = run_dir / entry_name
    missing_target = tmp_path / "outside-target.jsonl"
    entry_path.symlink_to(missing_target)

    with pytest.raises(
        run_context._FinalizeRecoveryError,
        match="run_start_existing_lifecycle",
    ):
        RunContext.start(
            store,
            bundle_ref,
            producer=producer,
            env=env_info,
            run_dir=run_dir,
            run_id=run_id,
        )

    assert entry_path.is_symlink()
    assert not missing_target.exists()
    assert not (run_dir / "trace.jsonl").is_file()


def test_resume_refuses_an_already_terminal_owner_snapshot(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_id = "R_resume_terminal_refusal"
    run_dir = tmp_path / "runs" / run_id
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id=run_id,
    )
    run.finalize(status="ok")
    trace_path = run_dir / "trace.jsonl"
    before = trace_path.read_bytes()

    with pytest.raises(
        run_context._FinalizeRecoveryError,
        match="run_resume_trace_not_incomplete",
    ):
        RunContext.resume(
            store,
            run_id=run_id,
            run_dir=run_dir,
            registry_bundle=bundle_ref,
            producer=producer,
            env=env_info,
            access_scope=None,
        )

    assert trace_path.read_bytes() == before


def _worker_manifest_snapshot_event(
    run: RunContext,
    store: FileSystemCAS,
    *,
    execution_profile: str,
) -> tuple[ArtifactRef, list[TraceRecord]]:
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    worker_manifest = run.run_manifest.model_copy(deep=True)
    worker_manifest.execution_profile = execution_profile
    next_owner_ref = run_context._persist_run_owner_snapshot(
        store,
        run_manifest=worker_manifest,
        access_scope_sha256=run_context._access_scope_sha256(run.access_scope),
        previous_snapshot_ref=owner_ref,
    )
    return owner_ref, [
        TraceRecord(
            run_id=run.run_manifest.run_id,
            phase="core",
            event="RUN_CONTEXT_SNAPSHOT",
            tenant_id=run.tenant_id,
            cell_id=run.cell_id,
            refs={"outputs": [next_owner_ref]},
        )
    ]


def test_worker_merge_wins_run_state_lease_before_manifest_update(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_dir = tmp_path / "runs" / "R_worker_merge_update_order"
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id="R_worker_merge_update_order",
    )
    owner_ref, records = _worker_manifest_snapshot_event(
        run,
        store,
        execution_profile="worker-profile",
    )
    original_emit_many = run.trace.emit_many
    merge_append_entered = Event()
    allow_merge_append = Event()
    update_entered = Event()
    update_persist_entered = Event()
    original_persist = run_context._persist_run_owner_snapshot

    def _observe_parent_update_persist(*args, **kwargs):
        if kwargs["run_manifest"].execution_profile == "parent-profile":
            update_persist_entered.set()
        return original_persist(*args, **kwargs)

    def _pause_worker_batch(batch) -> None:
        if any(record.worker_receipt_phase == "started" for record in batch):
            merge_append_entered.set()
            if not allow_merge_append.wait(timeout=10):
                raise TimeoutError("test did not release worker batch append")
        original_emit_many(batch)

    def _update_manifest() -> None:
        update_entered.set()
        run.update_manifest(execution_profile="parent-profile")

    monkeypatch.setattr(run.trace, "emit_many", _pause_worker_batch)
    monkeypatch.setattr(
        run_context,
        "_persist_run_owner_snapshot",
        _observe_parent_update_persist,
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        merge = executor.submit(
            run.merge_worker_events,
            invocation_id="1" * 64,
            dispatch_sha256="2" * 64,
            owner_snapshot_ref=owner_ref,
            records=records,
        )
        assert merge_append_entered.wait(timeout=10)
        update = executor.submit(_update_manifest)
        try:
            assert update_entered.wait(timeout=10)
            assert not update_persist_entered.wait(timeout=0.5), (
                "manifest update persisted while worker admission held the parent lease"
            )
            assert not update.done(), "manifest update crossed the active worker admission"
        finally:
            allow_merge_append.set()
        merge.result(timeout=10)
        update.result(timeout=10)

    assert run.run_manifest.execution_profile == "parent-profile"
    owner_snapshot_ref = run._owner_snapshot_ref
    assert owner_snapshot_ref is not None
    current_snapshot = run_context._validate_run_owner_snapshot_ref(
        store,
        owner_snapshot_ref,
        require_registry_profile=False,
    )
    assert current_snapshot.previous_snapshot_ref is not None
    worker_snapshot = run_context._validate_run_owner_snapshot_ref(
        store,
        current_snapshot.previous_snapshot_ref,
        require_registry_profile=False,
    )
    assert worker_snapshot.run_manifest.execution_profile == "worker-profile"
    durable = [
        TraceRecord.model_validate_json(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert durable.index(
        next(r for r in durable if r.event == "WORKER_INVOCATION_COMPLETED")
    ) < max(index for index, record in enumerate(durable) if record.event == "RUN_CONTEXT_SNAPSHOT")
    run.suspend_for_resume()


def test_manifest_update_wins_run_state_lease_and_refuses_stale_worker_dispatch(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_dir = tmp_path / "runs" / "R_update_worker_merge_order"
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id="R_update_worker_merge_order",
    )
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    event = TraceRecord(
        run_id=run.run_manifest.run_id,
        phase="worker",
        event="candidate_after_dispatch",
        tenant_id=run.tenant_id,
        cell_id=run.cell_id,
    )
    original_persist = run_context._persist_run_owner_snapshot
    snapshot_persisted = Event()
    allow_update_to_publish = Event()
    merge_attempted = Event()

    def _pause_snapshot_persist(*args, **kwargs):
        result = original_persist(*args, **kwargs)
        snapshot_persisted.set()
        if not allow_update_to_publish.wait(timeout=10):
            raise TimeoutError("test did not release manifest update")
        return result

    def _merge() -> str:
        merge_attempted.set()
        try:
            run.merge_worker_events(
                invocation_id="3" * 64,
                dispatch_sha256="4" * 64,
                owner_snapshot_ref=owner_ref,
                records=[event],
            )
        except run_context._FinalizeRecoveryError as exc:
            return str(exc)
        return "accepted"

    monkeypatch.setattr(run_context, "_persist_run_owner_snapshot", _pause_snapshot_persist)
    with ThreadPoolExecutor(max_workers=2) as executor:
        update = executor.submit(run.update_manifest, execution_profile="parent-wins")
        assert snapshot_persisted.wait(timeout=10)
        merge = executor.submit(_merge)
        try:
            assert merge_attempted.wait(timeout=10)
            Event().wait(timeout=0.1)
            assert not merge.done(), "stale worker dispatch crossed the owner update"
        finally:
            allow_update_to_publish.set()
        update.result(timeout=10)
        assert merge.result(timeout=10) == "worker_merge_owner_snapshot_stale"

    assert run.run_manifest.execution_profile == "parent-wins"
    trace_after_update = (run_dir / "trace.jsonl").read_bytes()
    assert b"candidate_after_dispatch" not in trace_after_update
    run.suspend_for_resume()


def test_finalize_wins_run_state_lease_and_refuses_late_worker_dispatch(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_dir = tmp_path / "runs" / "R_finalize_worker_merge_order"
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id="R_finalize_worker_merge_order",
    )
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    event = TraceRecord(
        run_id=run.run_manifest.run_id,
        phase="worker",
        event="candidate_after_terminal",
        tenant_id=run.tenant_id,
        cell_id=run.cell_id,
    )
    original_emit_many = run.trace.emit_many
    terminal_append_entered = Event()
    allow_terminal_append = Event()
    merge_attempted = Event()

    def _pause_terminal_batch(batch) -> None:
        if any(record.event == "RUN_FINALIZED" for record in batch):
            terminal_append_entered.set()
            if not allow_terminal_append.wait(timeout=10):
                raise TimeoutError("test did not release finalization append")
        original_emit_many(batch)

    def _merge() -> str:
        merge_attempted.set()
        try:
            run.merge_worker_events(
                invocation_id="5" * 64,
                dispatch_sha256="6" * 64,
                owner_snapshot_ref=owner_ref,
                records=[event],
            )
        except run_context._FinalizeRecoveryError as exc:
            return str(exc)
        return "accepted"

    monkeypatch.setattr(run.trace, "emit_many", _pause_terminal_batch)
    with ThreadPoolExecutor(max_workers=2) as executor:
        finalize = executor.submit(run.finalize, status="ok")
        assert terminal_append_entered.wait(timeout=10)
        merge = executor.submit(_merge)
        try:
            assert merge_attempted.wait(timeout=10)
            Event().wait(timeout=0.1)
            assert not merge.done(), "worker admission crossed terminal finalization"
        finally:
            allow_terminal_append.set()
        finalize.result(timeout=10)
        assert merge.result(timeout=10) == "worker_merge_parent_run_not_active"

    durable = [
        TraceRecord.model_validate_json(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert durable[-1].event == "RUN_FINALIZED"
    assert not any(record.event == "candidate_after_terminal" for record in durable)


def test_suspend_wins_run_state_lease_and_refuses_late_worker_dispatch(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_dir = tmp_path / "runs" / "R_suspend_worker_merge_order"
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id="R_suspend_worker_merge_order",
    )
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    event = TraceRecord(
        run_id=run.run_manifest.run_id,
        phase="worker",
        event="candidate_after_suspend",
        tenant_id=run.tenant_id,
        cell_id=run.cell_id,
    )
    original_read = run_context._read_incomplete_run_trace
    suspend_read_entered = Event()
    allow_suspend_read = Event()
    merge_attempted = Event()
    read_count = 0

    def _pause_suspend_read(run_dir_arg, **kwargs):
        nonlocal read_count
        read_count += 1
        if read_count == 1:
            suspend_read_entered.set()
            if not allow_suspend_read.wait(timeout=10):
                raise TimeoutError("test did not release suspension")
        return original_read(run_dir_arg, **kwargs)

    def _merge() -> str:
        merge_attempted.set()
        try:
            run.merge_worker_events(
                invocation_id="b" * 64,
                dispatch_sha256="c" * 64,
                owner_snapshot_ref=owner_ref,
                records=[event],
            )
        except run_context._FinalizeRecoveryError as exc:
            return str(exc)
        return "accepted"

    monkeypatch.setattr(run_context, "_read_incomplete_run_trace", _pause_suspend_read)
    with ThreadPoolExecutor(max_workers=2) as executor:
        suspend = executor.submit(run.suspend_for_resume)
        assert suspend_read_entered.wait(timeout=10)
        merge = executor.submit(_merge)
        try:
            assert merge_attempted.wait(timeout=10)
            Event().wait(timeout=0.1)
            assert not merge.done(), "worker admission crossed run suspension"
        finally:
            allow_suspend_read.set()
        suspend.result(timeout=10)
        assert merge.result(timeout=10) == "worker_merge_parent_run_not_active"

    durable = [
        TraceRecord.model_validate_json(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert not any(record.event == "candidate_after_suspend" for record in durable)
    assert not any(record.event == "WORKER_INVOCATION_STARTED" for record in durable)


def test_worker_merge_requires_exact_durable_batch_readback(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_dir = tmp_path / "runs" / "R_worker_merge_readback"
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id="R_worker_merge_readback",
    )
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    event = TraceRecord(
        run_id=run.run_manifest.run_id,
        phase="worker",
        event="candidate_without_durable_append",
        tenant_id=run.tenant_id,
        cell_id=run.cell_id,
    )
    before_trace = (run_dir / "trace.jsonl").read_bytes()
    before_manifest = run.run_manifest.model_copy(deep=True)
    before_owner = run._owner_snapshot_ref
    monkeypatch.setattr(run.trace, "emit_many", lambda _records: None)

    with pytest.raises(
        run_context._FinalizeRecoveryError,
        match="worker_merge_trace_readback_mismatch",
    ):
        run.merge_worker_events(
            invocation_id="7" * 64,
            dispatch_sha256="8" * 64,
            owner_snapshot_ref=owner_ref,
            records=[event],
        )

    assert (run_dir / "trace.jsonl").read_bytes() == before_trace
    assert run.run_manifest == before_manifest
    assert run._owner_snapshot_ref == before_owner
    run.suspend_for_resume()


def test_worker_merge_readback_failure_preserves_receipt_for_exact_resume_recovery(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_id = "R_worker_merge_readback_recovery"
    run_dir = tmp_path / "runs" / run_id
    run = RunContext.start(
        store,
        bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id=run_id,
    )
    owner_ref, records = _worker_manifest_snapshot_event(
        run,
        store,
        execution_profile="replayed-worker-profile",
    )
    original_read = run_context._read_incomplete_run_trace
    read_count = 0

    # The first read validates existing trace state; fail the second, after the
    # canonical batch append, to model a reader that cannot confirm the append.
    def _fail_post_append_read(run_dir_arg, **kwargs):
        nonlocal read_count
        read_count += 1
        if read_count == 2:
            raise run_context._FinalizeRecoveryError("simulated_worker_readback_failure")
        return original_read(run_dir_arg, **kwargs)

    monkeypatch.setattr(run_context, "_read_incomplete_run_trace", _fail_post_append_read)
    original_manifest = run.run_manifest.model_copy(deep=True)
    with pytest.raises(
        run_context._FinalizeRecoveryError,
        match="worker_merge_trace_readback_failed",
    ):
        run.merge_worker_events(
            invocation_id="9" * 64,
            dispatch_sha256="a" * 64,
            owner_snapshot_ref=owner_ref,
            records=records,
        )

    durable = [
        TraceRecord.model_validate_json(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [record.event for record in durable[-3:]] == [
        "WORKER_INVOCATION_STARTED",
        "RUN_CONTEXT_SNAPSHOT",
        "WORKER_INVOCATION_COMPLETED",
    ]
    assert run.run_manifest == original_manifest
    assert run._owner_snapshot_ref == owner_ref
    with pytest.raises(
        run_context._FinalizeRecoveryError,
        match="worker_receipt_recovery_required",
    ):
        run.update_manifest(execution_profile="must-wait-for-resume")

    monkeypatch.setattr(run_context, "_read_incomplete_run_trace", original_read)
    run.suspend_for_resume()
    resumed = RunContext.resume(
        store,
        run_id=run_id,
        run_dir=run_dir,
        registry_bundle=bundle_ref,
        producer=producer,
        env=env_info,
        access_scope=None,
    )
    assert resumed.run_manifest.execution_profile == "replayed-worker-profile"
    assert resumed._owner_snapshot_ref == records[0].refs.outputs[0]
    resumed.suspend_for_resume()


def test_owner_snapshot_with_mislinked_present_invocation_tail_is_rejected(
    store: FileSystemCAS,
    tmp_path: Path,
    producer: Any,
    env_info: Any,
) -> None:
    """A present but mislinked owner tail cannot fall back to earlier attempts."""
    from uuid import uuid4

    from polisyos.core.run.manifest import RunInvocationStarted
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

    bundle_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run_id = "R_owner_snapshot_mislinked_present_invocation_tail"
    run_dir = tmp_path / "runs" / run_id
    run = RunContext.start(
        store=store,
        registry_bundle=bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
        run_id=run_id,
    )
    component_id = "scientist.node_owner_tail_probe@1.0.0"
    workflow = WorkflowSpec(
        workflow_id="owner_tail_probe",
        nodes=[NodeInvocation(alias="attempt", node_id=component_id)],
    )
    workflow_ref = store.put_json(
        workflow.model_dump(),
        PutOptions(
            kind="scientist.workflow_spec",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.WorkflowSpec",
                version="1.0",
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    state = ExperimentState(run_id=run_id)
    input_ref = store.put_json(
        state.model_dump(),
        PutOptions(
            kind="scientist.experiment_state",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.ExperimentState",
                version=state.schema_version,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    run._record_runtime_invocation_started(
        attempt_id=str(uuid4()),
        attempt_number=1,
        workflow_spec_ref=workflow_ref,
        node_alias="attempt",
        component_id=component_id,
        input_state_ref=input_ref,
    )
    original_attempts = run.read_runtime_invocation_attempts()
    assert len(original_attempts) == 1
    original = original_attempts[0]

    malformed = RunInvocationStarted(
        run_id=run_id,
        attempt_id=str(uuid4()),
        attempt_number=2,
        workflow_spec_ref=original.basis.workflow_spec_ref,
        node_alias="attempt",
        component_id=component_id,
        input_state_ref=original.basis.input_state_ref,
        # Deliberately drop the current owner tail: the schema and CAS bytes remain valid.
        previous_record_ref=None,
    )
    malformed_ref = run_context._persist_run_invocation_record(
        store, malformed, run_manifest=run.run_manifest
    )
    current_owner = run_context._validate_run_owner_snapshot_ref(
        store,
        run._owner_snapshot_ref,
        require_registry_profile=False,
    )
    assert isinstance(current_owner, RunOwnerSnapshot)
    bad_snapshot_ref = run_context._persist_run_owner_snapshot(
        store,
        run_manifest=run.run_manifest,
        access_scope_sha256=current_owner.access_scope_sha256,
        previous_snapshot_ref=run._owner_snapshot_ref,
        runtime_invocation_tail_ref=malformed_ref,
    )
    run._emit_record("core", "RUN_CONTEXT_SNAPSHOT", outputs=[bad_snapshot_ref])

    with pytest.raises(
        run_context._FinalizeRecoveryError,
        match="run_resume_invocation_tail_chain_invalid",
    ):
        run.read_runtime_invocation_attempts()


def test_run_context_emit_persists_warning_in_existing_trace_field(
    store: FileSystemCAS, tmp_path: Path, producer, env_info
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store)
    run_dir = tmp_path / "runs" / "R_budget_warning"
    ctx = RunContext.start(
        store=store,
        registry_bundle=bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
    )
    warning = WarningRecord(
        code="budget_threshold",
        msg="Budget threshold reached.",
        data={"budget_key": "read"},
    )

    try:
        ctx.emit(
            "scientist.budget",
            "BUDGET_ALERT",
            metrics={"threshold_pct": 80},
            warnings=[warning],
        )
        ctx.emit("test", "NO_WARNING")
        trace_path = run_dir / "trace.jsonl"
        before_invalid = trace_path.read_bytes()
        emit_member = "emit"
        dynamic_emit = getattr(ctx, emit_member)
        with pytest.raises(TypeError, match="run_context_trace_warning_invalid"):
            dynamic_emit("test", "INVALID_WARNING", warnings=[{"code": "bad"}])
        assert trace_path.read_bytes() == before_invalid
    finally:
        ctx.finalize(status="ok")

    records = [
        TraceRecord.model_validate_json(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    alert = next(record for record in records if record.event == "BUDGET_ALERT")
    ordinary = next(record for record in records if record.event == "NO_WARNING")
    assert alert.phase == "scientist.budget"
    assert alert.metrics == {"threshold_pct": 80}
    assert alert.warnings == [
        {
            "code": "budget_threshold",
            "msg": "Budget threshold reached.",
            "data": {"budget_key": "read"},
        }
    ]
    assert ordinary.warnings == []
    assert next(record for record in records if record.event == "RUN_STARTED").warnings == []


def test_run_context_warning_argument_preserves_owner_and_closed_guards(
    store: FileSystemCAS, tmp_path: Path, producer, env_info
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store)
    run_dir = tmp_path / "runs" / "R_budget_warning_guards"
    ctx = RunContext.start(
        store=store,
        registry_bundle=bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
    )
    warning = WarningRecord(code="budget_threshold", msg="Budget threshold reached.")
    trace_path = run_dir / "trace.jsonl"
    before_reserved = trace_path.read_bytes()
    with pytest.raises(ValueError, match="run_context_owner_event_reserved"):
        ctx.emit("core", "RUN_FINALIZED", warnings=[warning])
    assert trace_path.read_bytes() == before_reserved

    ctx.finalize(status="ok")
    after_finalize = trace_path.read_bytes()
    with pytest.raises(ValueError, match="run_context_writer_closed"):
        ctx.emit("test", "AFTER_CLOSE", warnings=[warning])
    assert trace_path.read_bytes() == after_finalize


def test_run_context_pid_mismatch_refuses_terminal_transitions_and_unlock(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store)
    run_dir = tmp_path / "runs" / "R_simulated_inherited_active_lease"
    run = RunContext.start(
        store=store,
        registry_bundle=bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
    )
    active_lease = run._active_lease
    assert active_lease is not None
    original_owner_pid = active_lease._owner_pid
    assert original_owner_pid == os.getpid()
    before_trace = (run_dir / "trace.jsonl").read_bytes()

    active_lease._owner_pid = original_owner_pid + 1
    terminal_actions = [
        lambda: run.finalize(status="ok"),
        lambda: RunContext.finalize.__get__(run, RunContext)(status="ok"),
        run.suspend_for_resume,
        lambda: RunContext.suspend_for_resume.__get__(run, RunContext)(),
    ]
    for action in terminal_actions:
        with pytest.raises(
            run_context._FinalizeRecoveryError,
            match="run_execution_lease_inherited_process",
        ):
            action()
        assert run._closed is False
        assert run._suspended is False
        assert (run_dir / "trace.jsonl").read_bytes() == before_trace

    class _FcntlRecorder:
        LOCK_UN = 8

        def __init__(self) -> None:
            self.operations: list[int] = []

        def flock(self, descriptor: int, operation: int) -> None:
            self.operations.append(operation)

    recorder = _FcntlRecorder()
    closed_descriptors: list[int] = []
    child_copy = run_context._RunExecutionLease(tmp_path)
    child_copy._descriptor = 901
    child_copy._fcntl = recorder
    child_copy._owner_pid = os.getpid() + 1
    with monkeypatch.context() as patcher:
        patcher.setattr(
            run_context.os,
            "close",
            lambda descriptor: closed_descriptors.append(descriptor),
        )
        patcher.setattr(child_copy, "_release_thread_lock", lambda: None)
        child_copy.release()
    assert recorder.operations == []
    assert closed_descriptors == [901]
    assert child_copy._descriptor is None
    assert child_copy._owner_pid is None

    active_lease._owner_pid = original_owner_pid
    run.finalize(status="ok")


@pytest.mark.skipif(
    sys.platform != "linux" or not hasattr(os, "fork"),
    reason="run execution lease inheritance requires Linux fork/flock semantics",
)
def test_fork_inherited_run_lease_cannot_terminalize_or_unlock_parent(
    store: FileSystemCAS, tmp_path: Path, producer, env_info
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store)
    run_dir = tmp_path / "runs" / "R_fork_inherited_active_lease"
    run = RunContext.start(
        store=store,
        registry_bundle=bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
    )
    active_lease = run._active_lease
    assert active_lease is not None
    assert active_lease._owner_pid == os.getpid()
    before_trace = (run_dir / "trace.jsonl").read_bytes()
    before_digest = hashlib.sha256(before_trace).hexdigest()

    terminal_actions = [
        ("instance_finalize", lambda: run.finalize(status="ok")),
        (
            "class_finalize_dispatch",
            lambda: RunContext.finalize.__get__(run, RunContext)(status="ok"),
        ),
        ("instance_suspend", run.suspend_for_resume),
        (
            "class_suspend_dispatch",
            lambda: RunContext.suspend_for_resume.__get__(run, RunContext)(),
        ),
    ]
    try:
        for _, action in terminal_actions:
            child = _fork_run_action(action, run)
            assert child["kind"] == "refused"
            assert child["reason"] == "run_execution_lease_inherited_process"
            assert child["closed"] is False
            assert child["suspended"] is False
            assert child["trace_sha256"] == before_digest
            assert (run_dir / "trace.jsonl").read_bytes() == before_trace
            assert run._closed is False
            assert run._suspended is False

        child_release = _fork_run_action(active_lease.release, run)
        assert child_release["kind"] == "returned"
        assert child_release["closed"] is False
        assert child_release["suspended"] is False
        assert child_release["trace_sha256"] == before_digest
        assert (run_dir / "trace.jsonl").read_bytes() == before_trace

        def _attempt_new_lease() -> str:
            run_context._ACTIVE_RUN_THREAD_LOCKS.clear()
            contender = run_context._RunExecutionLease(run_dir)
            try:
                contender.acquire()
            except run_context._FinalizeRecoveryError as exc:
                return str(exc)
            contender.release()
            return "acquired"

        contender = _fork_run_action(_attempt_new_lease, run)
        assert contender["kind"] == "returned"
        assert contender["value"] == "run_execution_lease_busy"
        assert (run_dir / "trace.jsonl").read_bytes() == before_trace
        assert run._closed is False
        assert run._suspended is False

        run.finalize(status="ok")
        finalized_lines = (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        finalized = [TraceRecord.model_validate_json(line) for line in finalized_lines]
        assert finalized[-1].event == "RUN_FINALIZED"
    finally:
        if not run._closed:
            run.finalize(status="ok")

    child_run_dir = tmp_path / "runs" / "R_fork_child_owned_lease"

    def _start_and_finalize_child_run() -> str:
        child_run = RunContext.start(
            store=store,
            registry_bundle=bundle_ref,
            producer=producer,
            env=env_info,
            run_dir=child_run_dir,
        )
        child_run.finalize(status="ok")
        return child_run.run_manifest.run_id

    fresh_child = _fork_run_action(_start_and_finalize_child_run, run)
    assert fresh_child["kind"] == "returned"
    assert fresh_child["value"] == "R_fork_child_owned_lease"
    child_trace_lines = (child_run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    child_trace = [TraceRecord.model_validate_json(line) for line in child_trace_lines]
    assert child_trace[-1].event == "RUN_FINALIZED"


def test_artifact_tenant_context_is_bound_to_the_selected_run_owner(
    store: FileSystemCAS,
    producer: Any,
    env_info: Any,
) -> None:
    tenant_id = "tenant-run-context-owner"
    cell_id = "cell-run-context-owner"
    tenant_store = store.for_tenant(tenant_id, cell_id)
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        registry_ref = _bootstrap_registry_bundle(tenant_store, selected_profile=True)
        run = RunContext.start(
            store=tenant_store,
            registry_bundle=registry_ref,
            producer=producer,
            env=env_info,
            run_id="R_artifact_tenant_context_owner",
            tenant_id=tenant_id,
            cell_id=cell_id,
            access_scope=None,
        )
        try:
            run.update_manifest(control_job_id="job_artifact_tenant_context_owner")
            assert run.artifact_tenant_context() == ArtifactTenantContextInfo(
                tenant_id=tenant_id,
                cell_id=cell_id,
            )

            run.tenant_id = "tenant-forged"
            with pytest.raises(
                run_context._FinalizeRecoveryError,
                match="timeout_worker_owner_inputs_mismatch",
            ):
                run.artifact_tenant_context()
            run.tenant_id = tenant_id
        finally:
            run.finalize(status="ok")


def test_artifact_tenant_context_preserves_legacy_unscoped_runs_and_refuses_unscoped_jobs(
    store: FileSystemCAS,
    producer: Any,
    env_info: Any,
) -> None:
    registry_ref = _bootstrap_registry_bundle(store, selected_profile=True)
    run = RunContext.start(
        store=store,
        registry_bundle=registry_ref,
        producer=producer,
        env=env_info,
        run_id="R_artifact_tenant_context_unscoped",
        access_scope=None,
    )
    try:
        assert run.artifact_tenant_context() is None
        run.update_manifest(control_job_id="job_without_scope")
        with pytest.raises(
            run_context._FinalizeRecoveryError,
            match="run_owner_control_job_tenant_context_not_established",
        ):
            run.artifact_tenant_context()
    finally:
        run.finalize(status="ok")
