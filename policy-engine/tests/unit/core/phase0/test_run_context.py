from __future__ import annotations

import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier, Event
from typing import TYPE_CHECKING, Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.audit import AuditPackageAssembler
from polisyos.core.run import context as run_context
from polisyos.core.run.context import RunContext
from polisyos.core.trace import RunTerminality, TraceRecord
from polisyos.runtime.http.services.adapters.core_run import load_core_run

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
        observed_events.append(event_queue.get(timeout=30))
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
) -> None:
    """Call the real reader/recovery path from a distinct OS process."""
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
    try:
        start_barrier.wait(timeout=30)
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
        results.put(("error", worker_id, type(exc).__name__, str(exc)))
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


def _bootstrap_registry_bundle(store: FileSystemCAS):
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
    )
    return bundle_ref


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
        ref
        for ref in _terminal_records(run_dir)[0].refs.outputs
        if ref.kind == "core.run_manifest"
    )
    assert terminal_ref == run_ref
    assert (run_dir / ".finalize-journal.json").exists() is False


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
    results = mp.Queue()
    parent_events: list[tuple[int, str, str]] = []
    observed_events: list[tuple[int, str, str]] = []
    worker_ids = {"reader"}
    import fcntl

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
    reader = mp.Process(
        target=_recover_in_process,
        args=(
            str(store.root),
            str(run_dir),
            "reader",
            "load",
            mp.Barrier(1),
            lease_events,
            event_sequence,
            release_scan,
            results,
        ),
    )
    release_sequence = None
    with ThreadPoolExecutor(max_workers=1) as executor:
        finalize = executor.submit(ctx.finalize, status="ok")
        try:
            assert finalize_entered.wait(timeout=30)
            reader.start()
            reader_claim = _wait_for_lease_event(
                lease_events,
                observed_events,
                phase="claim_attempt",
                actor="reader",
            )
            assert reader_claim[1] == "reader"
        finally:
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
) -> RunContext:
    bundle_ref = _bootstrap_registry_bundle(store)
    ctx = RunContext.start(
        store=store,
        registry_bundle=bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=tmp_path / "runs" / run_id,
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
    ctx = _run_context_with_output(
        store, tmp_path, run_id="R_current_terminal", producer=producer, env_info=env_info
    )
    terminal = _leave_current_terminal_journal(ctx, monkeypatch)
    selected_ref = next(ref for ref in terminal.refs.outputs if ref.kind == "core.run_manifest")
    assert selected_ref.manifest_profile_sha256 is not None
    writes = _count_run_manifest_writes(store, monkeypatch)

    recovered = run_context.recover_pending_run_finalize(store, ctx.trace_path.parent)

    assert recovered == selected_ref
    assert writes == []
    assert len(_terminal_records(ctx.trace_path.parent)) == 1
    loaded = load_core_run(store=store, run_dir=ctx.trace_path.parent)
    assert loaded is not None
    assert loaded.manifest_ref == selected_ref
    assert loaded.manifest_ref.manifest_profile_sha256 == selected_ref.manifest_profile_sha256


def test_recovery_writes_once_after_cas_before_event_crash(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    assert len(_terminal_records(ctx.trace_path.parent)) == (2 if conflict == "duplicate-terminal" else 1)


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
