"""Finite retained resources and target-local cooperating export admission."""

from __future__ import annotations

import hashlib
import multiprocessing
import os
import runpy
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pytest

from polisyos.core.artifacts import ExportResourceError, FileSystemCAS, PutOptions
from polisyos.core.artifacts import _transfer_ops as transfer
from polisyos.core.artifacts._export_admission import _ExportAdmission


@pytest.fixture(autouse=True)
def _resource_property_removal(monkeypatch):
    if os.environ.get("E02_CAS02_REMOVAL") != "export-admission":
        return

    @contextmanager
    def bypass(target, *, validate_target, **_limits):
        validate_target()
        admission = _ExportAdmission(target, target.with_name(".removed-export-lock"), 2**63, 2**63)
        admission.stage_limit_bytes = 2**63
        yield admission

    monkeypatch.setattr(transfer, "_export_target_admission", bypass)


def _put(store, data):
    return store.put_bytes(
        data, PutOptions(kind="tests.export.budget", media_type="application/octet-stream")
    )


def _logical_bytes(path):
    return (
        path.stat().st_size
        if path.is_file()
        else sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
    )


def _payload_snapshot(path):
    return (
        path.read_bytes()
        if path.is_file()
        else {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()}
    )


@pytest.mark.parametrize("compress", [False, True])
def test_retention_count_refuses_before_source_consumption(compress, tmp_path):
    source = FileSystemCAS(tmp_path / "cas")
    old, new = _put(source, b"old complete"), _put(source, b"new complete")
    target = tmp_path / ("export.tar.gz" if compress else "export")
    first = source.export_subgraph([old], target, compress=compress, max_retained_generations=1)
    assert first.retained_paths == ()
    replacement = source.export_subgraph(
        [new], target, compress=compress, max_retained_generations=1
    )
    assert replacement.previous_generation is not None
    assert replacement.retained_paths == (replacement.previous_generation,)
    assert replacement.retained_bytes == _logical_bytes(replacement.previous_generation)
    before, previous = _payload_snapshot(target), _payload_snapshot(replacement.previous_generation)
    consumed = []

    def inventory():
        consumed.append(old)
        yield old

    if os.environ.get("E02_CAS02_REMOVAL") == "export-admission":
        over_limit = source.export_subgraph(
            inventory(), target, compress=compress, max_retained_generations=1
        )
        assert len(over_limit.retained_paths) == 2
        fresh = FileSystemCAS(tmp_path / "over-limit-reader")
        assert not fresh.import_subgraph(target, verify_integrity=True).verification_failed
        assert fresh.get_bytes(old) == b"old complete"
        pytest.fail(
            f"REMOVAL_ACTUAL_RETAINED_OVER_LIMIT: retained={len(over_limit.retained_paths)} "
            f"requested_limit=1; bypass_effective_limit={over_limit.max_retained_generations}; "
            f"source_consumed={len(consumed)}; "
            "new generation is readable",
            pytrace=False,
        )
    with pytest.raises(ExportResourceError) as refusal:
        source.export_subgraph(inventory(), target, compress=compress, max_retained_generations=1)
    assert refusal.value.reason == "retention_limit"
    assert refusal.value.replaced is False
    assert consumed == []
    assert _payload_snapshot(target) == before
    assert _payload_snapshot(replacement.previous_generation) == previous
    assert refusal.value.occupied_paths == replacement.retained_paths


@pytest.mark.parametrize("compress", [False, True])
def test_oversized_failed_stage_remains_within_reserved_logical_bytes(compress, tmp_path):
    source = FileSystemCAS(tmp_path / "cas")
    old, large = (
        _put(source, b"valid old"),
        _put(source, hashlib.shake_256(b"CAS02 fixed stage-limit fixture v1").digest(64 * 1024)),
    )
    target = tmp_path / ("export.tar.gz" if compress else "export")
    source.export_subgraph([old], target, compress=compress)
    before = _payload_snapshot(target)
    with pytest.raises(ExportResourceError) as refusal:
        source.export_subgraph([large], target, compress=compress, max_retained_bytes=16 * 1024)
    error = refusal.value
    assert error.reason == "stage_byte_limit"
    assert error.replaced is False
    assert error.staging_path is not None and error.staging_path.exists()
    assert error.occupied_bytes == sum(_logical_bytes(p) for p in error.occupied_paths)
    assert error.occupied_bytes <= 16 * 1024
    assert _payload_snapshot(target) == before
    fresh = FileSystemCAS(tmp_path / "fresh")
    imported = fresh.import_subgraph(target, verify_integrity=True)
    assert not imported.verification_failed
    assert fresh.get_bytes(old) == b"valid old"


@pytest.mark.parametrize("compress", [False, True])
def test_same_target_busy_refuses_before_source_or_member_work(compress, tmp_path, monkeypatch):
    source = FileSystemCAS(tmp_path / "cas")
    old, new = _put(source, b"old"), _put(source, b"new")
    target = tmp_path / ("export.tar.gz" if compress else "export")
    source.export_subgraph([old], target, compress=compress)
    entered, release = threading.Event(), threading.Event()
    original = source.open_member

    @contextmanager
    def hold(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        with original(*args, **kwargs) as stream:
            yield stream

    monkeypatch.setattr(source, "open_member", hold)
    consumed = []

    def inventory():
        consumed.append(new)
        yield new

    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(source.export_subgraph, [new], target, compress=compress)
        try:
            assert entered.wait(5)
            with pytest.raises(ExportResourceError) as refusal:
                source.export_subgraph(inventory(), target, compress=compress)
            assert refusal.value.reason == "busy"
            assert consumed == []
            assert refusal.value.lock_path.is_file()
        finally:
            release.set()
        result = first.result(timeout=5)
    assert result.previous_generation is not None


@pytest.mark.parametrize("compress", [False, True])
def test_foreign_reserved_entries_are_counted_and_never_reclaimed(compress, tmp_path):
    source = FileSystemCAS(tmp_path / "cas")
    ref = _put(source, b"valid")
    target = tmp_path / ("export.tar.gz" if compress else "export")
    source.export_subgraph([ref], target, compress=compress)
    foreign = target.with_name(f".{target.name}.previous-user-file")
    foreign.write_bytes(b"unclassified foreign bytes")
    before = _payload_snapshot(target)
    with pytest.raises(ExportResourceError) as refusal:
        source.export_subgraph([ref], target, compress=compress, max_retained_generations=1)
    assert refusal.value.reason == "retention_limit"
    assert foreign in refusal.value.occupied_paths
    assert foreign.read_bytes() == b"unclassified foreign bytes"
    assert _payload_snapshot(target) == before


@pytest.mark.parametrize("compress", [False, True])
def test_unmeasurable_retained_entry_after_selection_never_claims_rollback(
    compress, tmp_path, monkeypatch
):
    source = FileSystemCAS(tmp_path / "cas")
    old, new = _put(source, b"previous"), _put(source, b"selected new")
    target = tmp_path / ("export.tar.gz" if compress else "export")
    source.export_subgraph([old], target, compress=compress)
    sentinel = tmp_path / "foreign-sentinel"
    sentinel.write_bytes(b"foreign retained bytes")
    foreign = target.with_name(f".{target.name}.previous-foreign-link")
    original = transfer._rename_export_generation

    def publish_and_introduce_unmeasurable_entry(stage, selected, *, exchange):
        result = original(stage, selected, exchange=exchange)
        if selected == target:
            foreign.symlink_to(sentinel)
        return result

    monkeypatch.setattr(
        transfer, "_rename_export_generation", publish_and_introduce_unmeasurable_entry
    )
    with pytest.raises(ExportResourceError) as refusal:
        source.export_subgraph([new], target, compress=compress)
    assert refusal.value.reason == "unmeasurable_retained_entry"
    assert refusal.value.replaced is True, "capacity measurement failure is not rollback"
    assert foreign.is_symlink()
    assert sentinel.read_bytes() == b"foreign retained bytes"
    fresh = FileSystemCAS(tmp_path / "fresh")
    accepted = fresh.import_subgraph(target, verify_integrity=True)
    assert not accepted.verification_failed
    assert fresh.get_bytes(new) == b"selected new"


def _native_held_export(cas_root, target, compress, artifact_id, connection):
    store = FileSystemCAS(Path(cas_root))
    original = store.open_member
    announced = False

    @contextmanager
    def hold(*args, **kwargs):
        nonlocal announced
        if not announced:
            announced = True
            connection.send("held")
            assert connection.recv() == "release"
        with original(*args, **kwargs) as stream:
            yield stream

    store.open_member = hold
    report = store.export_subgraph([artifact_id], Path(target), compress=compress)
    connection.send({"selected": str(report.output_path)})


@pytest.mark.parametrize("compress", [False, True])
@pytest.mark.parametrize("termination", ["release", "kill"])
def test_native_process_lock_and_abandoned_stage_census(compress, termination, tmp_path):
    source = FileSystemCAS(tmp_path / "cas")
    old, new = _put(source, b"old process generation"), _put(source, b"new process generation")
    target = tmp_path / ("export.tar.gz" if compress else "export")
    source.export_subgraph([old], target, compress=compress)
    previous = _payload_snapshot(target)
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(
        target=runpy.run_path,
        args=(str(Path(__file__).resolve()),),
        kwargs={
            "run_name": "__export_admission_worker__",
            "init_globals": {
                "export_worker_args": (
                    str(source.root),
                    str(target),
                    compress,
                    str(new.artifact_id),
                    child,
                ),
            },
        },
    )
    process.start()
    consumed = []

    def competing_source():
        consumed.append(new)
        yield new

    try:
        assert parent.poll(15), "native export did not acquire its real lease/stage"
        assert parent.recv() == "held"
        with pytest.raises(ExportResourceError) as busy:
            source.export_subgraph(competing_source(), target, compress=compress)
        assert busy.value.reason == "busy"
        assert consumed == []
        if termination == "release":
            parent.send("release")
            assert parent.poll(15)
            assert parent.recv()["selected"] == str(target)
            process.join(15)
            assert process.exitcode == 0
        else:
            process.kill()
            process.join(15)
            assert not process.is_alive()
            assert _payload_snapshot(target) == previous
            # Kernel lock release is not permission to erase the interrupted stage.
            with pytest.raises(ExportResourceError) as capacity:
                source.export_subgraph(
                    competing_source(), target, compress=compress, max_retained_generations=1
                )
            assert capacity.value.reason == "retention_limit", (
                "stale process lock must not remain busy"
            )
            assert consumed == []
            assert len(capacity.value.occupied_paths) == 1
            result = source.export_subgraph(
                [new], target, compress=compress, max_retained_generations=2
            )
            assert len(result.retained_paths) == 2
        fresh = FileSystemCAS(tmp_path / "fresh")
        result = fresh.import_subgraph(target, verify_integrity=True)
        assert not result.verification_failed
        assert fresh.get_bytes(new) == b"new process generation"
    finally:
        if process.is_alive():
            process.kill()
        process.join(15)
        parent.close()
        child.close()


@pytest.mark.parametrize("compress", [False, True])
def test_displaced_target_byte_budget_refuses_before_source_iteration(compress, tmp_path):
    source = FileSystemCAS(tmp_path / "cas")
    ref = _put(source, hashlib.shake_256(b"CAS02 fixed target-limit fixture v1").digest(32 * 1024))
    target = tmp_path / ("export.tar.gz" if compress else "export")
    source.export_subgraph([ref], target, compress=compress)
    before = _payload_snapshot(target)
    consumed = []

    def source_ids():
        consumed.append(ref)
        yield ref

    with pytest.raises(ExportResourceError) as refusal:
        source.export_subgraph(source_ids(), target, compress=compress, max_retained_bytes=1)
    assert refusal.value.reason == "retention_limit"
    assert refusal.value.replaced is False
    assert consumed == []
    assert _payload_snapshot(target) == before


@pytest.mark.parametrize("compress", [False, True])
def test_unlock_failure_preserves_visibility_and_releases_local_gate(
    compress, tmp_path, monkeypatch
):
    import fcntl

    source = FileSystemCAS(tmp_path / "cas")
    ref = _put(source, b"complete selected generation")
    target = tmp_path / ("export.tar.gz" if compress else "export")
    original = fcntl.flock
    failed = False

    def unlock_then_report_error(descriptor, operation):
        nonlocal failed
        result = original(descriptor, operation)
        if operation == fcntl.LOCK_UN and not failed:
            failed = True
            raise OSError("controlled native unlock diagnostic failure")
        return result

    # Source owner locks finish before the target lease release; select the
    # permanent target lock inode, not unrelated CAS coordinator locks.
    def fail_target_unlock(descriptor, operation):
        metadata = os.fstat(descriptor)
        lock_path = target.with_name(f".{target.name}.export.lock")
        if lock_path.exists() and metadata.st_ino == lock_path.stat().st_ino:
            return unlock_then_report_error(descriptor, operation)
        return original(descriptor, operation)

    monkeypatch.setattr(fcntl, "flock", fail_target_unlock)
    with pytest.raises(ExportResourceError) as refusal:
        source.export_subgraph([ref], target, compress=compress)
    assert failed
    assert refusal.value.reason == "lock_release_unavailable"
    assert refusal.value.replaced is True
    fresh = FileSystemCAS(tmp_path / "fresh")
    assert not fresh.import_subgraph(target, verify_integrity=True).verification_failed
    assert fresh.get_bytes(ref) == b"complete selected generation"
    # A reported release error must not permanently strand the in-process gate.
    second = source.export_subgraph([ref], target, compress=compress)
    assert second.previous_generation is not None


@pytest.mark.parametrize("compress", [False, True])
def test_parent_enumeration_failure_after_actual_selection_keeps_typed_visibility(
    compress, tmp_path, monkeypatch
):
    source = FileSystemCAS(tmp_path / "cas")
    old, new = _put(source, b"old snapshot"), _put(source, b"new snapshot")
    target = tmp_path / ("export.tar.gz" if compress else "export")
    source.export_subgraph([old], target, compress=compress)
    selected = False
    original_rename, original_iterdir = transfer._rename_export_generation, Path.iterdir

    def rename(*args, **kwargs):
        nonlocal selected
        result = original_rename(*args, **kwargs)
        selected = True
        return result

    def refuse_enumeration(path):
        if selected and path == target.parent:
            raise OSError("controlled namespace observation unavailable")
        return original_iterdir(path)

    with monkeypatch.context() as failure:
        failure.setattr(transfer, "_rename_export_generation", rename)
        failure.setattr(Path, "iterdir", refuse_enumeration)
        with pytest.raises(ExportResourceError) as refusal:
            source.export_subgraph([new], target, compress=compress)
    error = refusal.value
    assert error.replaced is True
    assert error.occupied_bytes is None
    assert error.staging_path is not None and error.staging_path.exists()
    fresh = FileSystemCAS(tmp_path / "fresh")
    assert not fresh.import_subgraph(target, verify_integrity=True).verification_failed
    assert fresh.get_bytes(new) == b"new snapshot"
    previous = FileSystemCAS(tmp_path / "previous")
    assert not previous.import_subgraph(
        error.staging_path, verify_integrity=True
    ).verification_failed
    assert previous.get_bytes(old) == b"old snapshot"


if __name__ == "__export_admission_worker__":
    _native_held_export(*globals()["export_worker_args"])
