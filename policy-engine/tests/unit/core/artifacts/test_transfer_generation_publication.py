"""Actual filesystem generation and consumer witnesses for reusable CAS exports."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import socket
import stat
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.artifacts import _transfer_ops as transfer
from polisyos.core.artifacts.manifest import ProducerInfo

OLD = b"complete previous export generation"
NEW = b"complete replacement export generation"


@pytest.fixture(autouse=True)
def _archive_property_removal_control(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit test-only probe removes private staging while retaining its markers."""
    if os.environ.get("E02_B_PROPERTY_REMOVAL") != "cas-private-archive":
        return
    original = tarfile.open

    def write_live(path, mode="r", *args, **kwargs):
        candidate = Path(path)
        if mode == "w:gz" and ".staging-" in candidate.name:
            live_name = candidate.name.split(".staging-", 1)[0].removeprefix(".")
            live = candidate.with_name(live_name)
            if live.exists():
                path = live
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(tarfile, "open", write_live)


def _put(store: FileSystemCAS, payload: bytes):
    return store.put_bytes(
        payload,
        PutOptions(
            kind="tests.transfer-generation",
            media_type="application/octet-stream",
            producer=ProducerInfo(component="tests.transfer-generation", version="1"),
        ),
    )


def _package_bytes(path: Path) -> dict[str, bytes]:
    if path.is_dir():
        return {
            file.relative_to(path).as_posix(): file.read_bytes()
            for file in path.rglob("*")
            if file.is_file()
        }
    with tarfile.open(path, "r:*") as archive:
        result = {}
        for member in archive.getmembers():
            if member.isfile():
                reader = archive.extractfile(member)
                assert reader is not None
                with reader:
                    result[member.name] = reader.read()
        return result


def _assert_complete(path: Path, payload: bytes, *, manifests: bool = True) -> None:
    members = _package_bytes(path)
    inventory = json.loads(members.pop("export_manifest.json"))
    assert set(inventory["members"]) == set(members)
    assert {row["path"] for row in inventory["member_bindings"]} == set(members)
    for binding in inventory["member_bindings"]:
        data = members[binding["path"]]
        assert binding["sha256"] == hashlib.sha256(data).hexdigest()
        assert binding["byte_size"] == len(data)
    assert [data for name, data in members.items() if name.endswith(".blob")] == [payload]
    assert any(name.endswith(".manifest.json") for name in members) == manifests


def _assert_imported(path: Path, receiving_root: Path, payload: bytes) -> None:
    receiver = FileSystemCAS(receiving_root)
    result = receiver.import_subgraph(path, verify_integrity=True)
    assert not result.verification_failed
    assert result.imported_refs
    assert {ref.artifact_id.hex for ref in result.imported_refs} == {
        hashlib.sha256(payload).hexdigest()
    }
    reopened = FileSystemCAS(receiving_root)
    for ref in result.imported_refs:
        assert reopened.get_bytes(ref) == payload
        assert reopened.verify(ref).ok


@pytest.mark.parametrize("compress", [False, True])
def test_same_destination_retains_complete_history_and_exact_new_inventory(
    tmp_path: Path, compress: bool
) -> None:
    source = FileSystemCAS(tmp_path / "cas")
    old = _put(source, OLD)
    new = _put(source, NEW)
    target = tmp_path / ("export.tar.gz" if compress else "export")
    first = source.export_subgraph([old], target, compress=compress)
    target.chmod(0o640 if compress else 0o750)
    prior = _package_bytes(first.output_path)
    second = source.export_subgraph([new], target, compress=compress)
    assert second.previous_generation is not None
    assert _package_bytes(second.previous_generation) == prior
    assert stat.S_IMODE(target.stat().st_mode) == (0o640 if compress else 0o750)
    _assert_complete(target, NEW)
    _assert_imported(target, tmp_path / "new-reader", NEW)
    _assert_imported(second.previous_generation, tmp_path / "old-reader", OLD)
    third = source.export_subgraph([old], target, compress=compress, include_manifests=False)
    assert third.previous_generation is not None
    _assert_complete(third.previous_generation, NEW)
    _assert_complete(target, OLD, manifests=False)


@pytest.mark.parametrize("compress", [False, True])
def test_streamed_write_failure_preserves_old_generation_and_no_false_inventory(
    tmp_path: Path, compress: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = FileSystemCAS(tmp_path / "cas")
    old = _put(source, OLD)
    new = _put(source, NEW)
    target = tmp_path / ("export.tar.gz" if compress else "export")
    source.export_subgraph([old], target, compress=compress)
    prior = _package_bytes(target)
    original = transfer.os.fsync

    def fail_file_sync(descriptor: int) -> None:
        if stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("injected file sync boundary")
        original(descriptor)

    monkeypatch.setattr(transfer.os, "fsync", fail_file_sync)
    with pytest.raises(OSError, match="file sync boundary"):
        source.export_subgraph([new], target, compress=compress)
    monkeypatch.setattr(transfer.os, "fsync", original)
    assert _package_bytes(target) == prior
    assert not list(tmp_path.glob(f".{target.name}.staging-*"))
    _assert_imported(target, tmp_path / "reader-after-refusal", OLD)


@pytest.mark.parametrize(
    "kind", ["regular_symlink", "dangling_symlink", "fifo", "socket", "directory"]
)
def test_archive_refuses_nonregular_final_path_before_staging(
    tmp_path: Path, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = FileSystemCAS(tmp_path / "cas")
    old = _put(source, OLD)
    _put(source, NEW)
    referent = tmp_path / "old-package.tar.gz"
    source.export_subgraph([old], referent)
    old_bytes = referent.read_bytes()
    target = tmp_path / "alias.tar.gz"
    sock = None
    if kind == "regular_symlink":
        target.symlink_to(referent)
    elif kind == "dangling_symlink":
        target.symlink_to(tmp_path / "absent")
    elif kind == "fifo":
        os.mkfifo(target)
    elif kind == "socket":
        sock = socket.socket(socket.AF_UNIX)
        original_cwd = Path.cwd()
        monkeypatch.chdir(tmp_path)
        sock.bind(target.name)
        monkeypatch.chdir(original_cwd)
    else:
        target.mkdir()
    before = target.lstat()
    try:
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe()
        process = context.Process(
            target=_archive_path_probe, args=(str(source.root), str(target), child)
        )
        process.start()
        try:
            assert parent.poll(20), "path probe did not start"
            assert parent.recv() == "ready"
            assert parent.poll(2), "archive opened a nonregular path and blocked"
            result = parent.recv()
            assert result["type"] == "ValueError"
            assert "regular file" in result["message"]
            process.join(20)
            assert process.exitcode == 0
        finally:
            if process.is_alive():
                process.terminate()
            process.join(20)
            parent.close()
            child.close()
        after = target.lstat()
        assert (after.st_ino, stat.S_IFMT(after.st_mode)) == (
            before.st_ino,
            stat.S_IFMT(before.st_mode),
        )
        assert referent.read_bytes() == old_bytes
        assert not list(tmp_path.glob(f".{target.name}.*"))
    finally:
        if sock is not None:
            sock.close()


def _archive_path_probe(cas_root: str, target: str, connection: Any) -> None:
    store = FileSystemCAS(Path(cas_root))
    ref = _put(store, NEW)
    connection.send("ready")
    try:
        store.export_subgraph([ref], Path(target))
    except Exception as error:
        connection.send({"type": type(error).__name__, "message": str(error)})
    else:
        connection.send({"type": "published", "message": "nonregular path was replaced"})


def _pause_after_publication_syscall(
    cas_root: str, target: str, compress: bool, connection: Any
) -> None:
    """Pause the real producer after each actual rename/swap affecting its public path."""
    destination = Path(target)
    original_replace = transfer.os.replace

    def observe() -> None:
        connection.send({"public_exists": destination.exists()})
        connection.recv()

    def replace(source_path, target_path, *args, **kwargs):
        result = original_replace(source_path, target_path, *args, **kwargs)
        if Path(source_path) == destination or Path(target_path) == destination:
            observe()
        return result

    transfer.os.replace = replace
    if os.environ.get("E02_B_PROPERTY_REMOVAL") == "cas-atomic-directory":

        def rename_with_gap(stage, current):
            previous = Path(tempfile.mkdtemp(prefix=".removed-atomicity-", dir=current.parent))
            previous.rmdir()
            transfer.os.replace(current, previous)
            transfer.os.replace(stage, current)
            transfer.os.replace(previous, stage)

        transfer._exchange_directory_generation = rename_with_gap
    if hasattr(transfer, "_exchange_directory_generation"):
        original_exchange = transfer._exchange_directory_generation

        def exchange(stage, current):
            result = original_exchange(stage, current)
            observe()
            return result

        transfer._exchange_directory_generation = exchange
    store = FileSystemCAS(Path(cas_root))
    ref = _put(store, NEW)
    store.export_subgraph([ref], destination, compress=compress)
    connection.send({"finished": True})


@pytest.mark.parametrize("compress", [False, True])
def test_process_interruption_after_each_publication_syscall_leaves_a_complete_generation(
    tmp_path: Path,
    compress: bool,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    old = _put(store, OLD)
    _put(store, NEW)
    target = tmp_path / ("export.tar.gz" if compress else "export")
    store.export_subgraph([old], target, compress=compress)
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(
        target=_pause_after_publication_syscall,
        args=(str(store.root), str(target), compress, child),
    )
    process.start()
    try:
        assert parent.poll(20), "producer did not reach its real publication syscall"
        observed = parent.recv()
        assert observed["public_exists"], "two-rename publication exposed an absent generation"
        _assert_complete(target, NEW)
        process.terminate()
        process.join(20)
        assert not process.is_alive()
        _assert_imported(target, tmp_path / "after-process-stop", NEW)
        previous = list(
            tmp_path.glob(".export.tar.gz.previous-*" if compress else ".export.generation-*")
        )
        assert len(previous) == 1
        _assert_complete(previous[0], OLD)
        _assert_imported(previous[0], tmp_path / "old-after-process-stop", OLD)
    finally:
        if process.is_alive():
            process.terminate()
        process.join(20)
        parent.close()
        child.close()


@pytest.mark.parametrize("compress", [False, True])
def test_import_reader_remains_on_the_generation_pinned_before_concurrent_replacement(
    tmp_path: Path, compress: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = FileSystemCAS(tmp_path / "cas")
    old = _put(source, OLD)
    new = _put(source, NEW)
    target = tmp_path / ("export.tar.gz" if compress else "export")
    source.export_subgraph([old], target, compress=compress)
    swapped = False

    def swap() -> None:
        nonlocal swapped
        if not swapped:
            swapped = True
            source.export_subgraph([new], target, compress=compress)

    if compress:
        original_extract = tarfile.TarFile.extractfile

        def extract(archive, member):
            reader = original_extract(archive, member)
            name = member.name if isinstance(member, tarfile.TarInfo) else member
            if name == "export_manifest.json":
                swap()
            return reader

        monkeypatch.setattr(tarfile.TarFile, "extractfile", extract)
    else:
        original_inventory = transfer._read_directory_inventory

        def read_inventory(descriptor):
            data = original_inventory(descriptor)
            swap()
            return data

        monkeypatch.setattr(transfer, "_read_directory_inventory", read_inventory)
    _assert_imported(target, tmp_path / "pinned-reader", OLD)
    assert swapped
    _assert_complete(target, NEW)


@pytest.mark.parametrize("compress", [False, True])
def test_publication_syscall_failure_leaves_complete_previous_generation(
    tmp_path: Path, compress: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = FileSystemCAS(tmp_path / "cas")
    old = _put(source, OLD)
    new = _put(source, NEW)
    target = tmp_path / ("export.tar.gz" if compress else "export")
    source.export_subgraph([old], target, compress=compress)
    before = _package_bytes(target)
    original_replace = transfer.os.replace
    original_exchange = transfer._exchange_directory_generation

    def refuse_replace(stage, destination, *args, **kwargs):
        if Path(destination) == target:
            raise OSError("injected publication syscall failure")
        return original_replace(stage, destination, *args, **kwargs)

    def refuse_exchange(stage, destination):
        raise OSError("injected publication syscall failure")

    monkeypatch.setattr(transfer.os, "replace", refuse_replace)
    monkeypatch.setattr(transfer, "_exchange_directory_generation", refuse_exchange)
    with pytest.raises(OSError, match="publication syscall failure"):
        source.export_subgraph([new], target, compress=compress)
    monkeypatch.setattr(transfer.os, "replace", original_replace)
    monkeypatch.setattr(transfer, "_exchange_directory_generation", original_exchange)
    assert _package_bytes(target) == before
    _assert_imported(target, tmp_path / "refused-reader", OLD)
    assert not list(tmp_path.glob(f".{target.name}.generation-*"))
    assert not list(tmp_path.glob(f".{target.name}.staging-*"))


@pytest.mark.parametrize("compress", [False, True])
def test_post_publication_directory_sync_failure_retains_old_and_new_readable_generations(
    tmp_path: Path, compress: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = FileSystemCAS(tmp_path / "cas")
    old = _put(source, OLD)
    new = _put(source, NEW)
    target = tmp_path / ("export.tar.gz" if compress else "export")
    source.export_subgraph([old], target, compress=compress)
    old_bytes = _package_bytes(target)
    original_sync = transfer.fsync_directory
    parent_syncs = 0

    def refuse_after_publication(directory):
        nonlocal parent_syncs
        if Path(directory) == target.parent:
            parent_syncs += 1
            if parent_syncs == (2 if compress else 1):
                raise OSError("injected post-publication directory sync failure")
        original_sync(directory)

    monkeypatch.setattr(transfer, "fsync_directory", refuse_after_publication)
    with pytest.raises(transfer.ExportDurabilityError) as refusal:
        source.export_subgraph([new], target, compress=compress)
    monkeypatch.setattr(transfer, "fsync_directory", original_sync)
    assert refusal.value.replaced
    previous = refusal.value.previous_generation
    assert previous is not None
    assert _package_bytes(previous) == old_bytes
    _assert_complete(target, NEW)
    _assert_imported(target, tmp_path / "uncertain-new-reader", NEW)
    _assert_imported(previous, tmp_path / "uncertain-old-reader", OLD)


@pytest.mark.parametrize("compress", [False, True])
def test_prepublication_directory_sync_refusal_keeps_the_old_package(
    tmp_path: Path, compress: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = FileSystemCAS(tmp_path / "cas")
    old = _put(source, OLD)
    new = _put(source, NEW)
    target = tmp_path / ("export.tar.gz" if compress else "export")
    source.export_subgraph([old], target, compress=compress)
    old_bytes = _package_bytes(target)
    original_sync = transfer.fsync_directory

    def refuse_directory(directory):
        raise OSError("injected pre-publication directory sync failure")

    monkeypatch.setattr(transfer, "fsync_directory", refuse_directory)
    with pytest.raises(OSError, match=r"pre-publication|publication has not occurred") as refusal:
        source.export_subgraph([new], target, compress=compress)
    monkeypatch.setattr(transfer, "fsync_directory", original_sync)
    if compress:
        assert isinstance(refusal.value, transfer.ExportDurabilityError)
        assert not refusal.value.replaced
        assert refusal.value.previous_generation is not None
        assert _package_bytes(refusal.value.previous_generation) == old_bytes
    assert _package_bytes(target) == old_bytes
    _assert_imported(target, tmp_path / "old-pre-sync-reader", OLD)


def test_unavailable_native_exchange_refuses_before_removing_the_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = FileSystemCAS(tmp_path / "cas")
    old = _put(source, OLD)
    new = _put(source, NEW)
    target = tmp_path / "export"
    source.export_subgraph([old], target, compress=False)
    old_bytes = _package_bytes(target)
    monkeypatch.setattr(transfer.sys, "platform", "unsupported-atomic-exchange")
    with pytest.raises(NotImplementedError, match="exchange is unavailable"):
        source.export_subgraph([new], target, compress=False)
    monkeypatch.undo()
    assert _package_bytes(target) == old_bytes
    assert not list(tmp_path.glob(".export.generation-*"))
    _assert_imported(target, tmp_path / "unsupported-reader", OLD)
