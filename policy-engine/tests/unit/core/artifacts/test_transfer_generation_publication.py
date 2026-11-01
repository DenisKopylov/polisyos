"""Actual filesystem generation and consumer witnesses for reusable CAS exports."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import runpy
import socket
import stat
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import ExportResourceError, FileSystemCAS, PutOptions
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

    def write_live(path=None, mode="r", *args, **kwargs):
        candidate = Path(path) if path is not None else None
        if mode == "w:gz" and candidate is not None and ".staging-" in candidate.name:
            live_name = candidate.name.split(".staging-", 1)[0].removeprefix(".")
            live = candidate.with_name(live_name)
            if live.exists():
                path = live
                # Bypass the actual descriptor-owned stream, not only a pathname marker.
                kwargs.pop("fileobj", None)
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
    if compress:
        assert list(tmp_path.glob(f".{target.name}.staging-*"))
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
            target=runpy.run_path,
            args=(str(Path(__file__).resolve()),),
            kwargs={
                "run_name": "__e02_transfer_worker__",
                "init_globals": {
                    "e02_worker_name": "_archive_path_probe",
                    "e02_worker_args": (str(source.root), str(target), child),
                },
            },
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
        # Admission retains one permanent coordination inode, not a generation.
        lock_path = target.with_name(f".{target.name}.export.lock")
        assert list(tmp_path.glob(f".{target.name}.*")) == [lock_path]
        assert lock_path.is_file() and lock_path.stat().st_size == 0
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
        target=runpy.run_path,
        args=(str(Path(__file__).resolve()),),
        kwargs={
            "run_name": "__e02_transfer_worker__",
            "init_globals": {
                "e02_worker_name": "_pause_after_publication_syscall",
                "e02_worker_args": (str(store.root), str(target), compress, child),
            },
        },
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
            tmp_path.glob(".export.tar.gz.staging-*" if compress else ".export.generation-*")
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
    with pytest.raises(OSError, match="publication syscall failure") as refusal:
        source.export_subgraph([new], target, compress=compress)
    monkeypatch.setattr(transfer.os, "replace", original_replace)
    monkeypatch.setattr(transfer, "_exchange_directory_generation", original_exchange)
    assert _package_bytes(target) == before
    _assert_imported(target, tmp_path / "refused-reader", OLD)
    if not compress:
        assert isinstance(refusal.value, transfer.ExportDurabilityError)
        assert refusal.value.replaced is False
        assert refusal.value.staging_path is not None and refusal.value.staging_path.is_dir()
    if compress:
        assert list(tmp_path.glob(f".{target.name}.staging-*"))


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
    if not compress:
        assert isinstance(refusal.value, transfer.ExportDurabilityError)
        assert refusal.value.replaced is False
        assert refusal.value.staging_path is not None and refusal.value.staging_path.is_dir()
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
    with pytest.raises(transfer.ExportDurabilityError, match="rename is unavailable") as refusal:
        source.export_subgraph([new], target, compress=False)
    assert isinstance(refusal.value.__cause__, NotImplementedError)
    assert refusal.value.replaced is False
    assert refusal.value.staging_path is not None and refusal.value.staging_path.is_dir()
    monkeypatch.undo()
    assert _package_bytes(target) == old_bytes
    _assert_imported(target, tmp_path / "unsupported-reader", OLD)


@pytest.mark.parametrize(
    "kind", ["regular_symlink", "dangling_symlink", "fifo", "socket", "fifo_at_open"]
)
def test_import_archive_binds_the_supplied_regular_path_before_streaming(
    tmp_path: Path, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = FileSystemCAS(tmp_path / "source")
    incoming = _put(source, NEW)
    legitimate = source.export_subgraph([incoming], tmp_path / "legitimate.tar.gz").output_path
    legitimate_bytes = legitimate.read_bytes()
    alias = tmp_path / "input.tar.gz"
    sock = None
    if kind == "regular_symlink":
        alias.symlink_to(legitimate)
    elif kind == "dangling_symlink":
        alias.symlink_to(tmp_path / "absent")
    elif kind == "fifo":
        os.mkfifo(alias)
    elif kind == "socket":
        sock = socket.socket(socket.AF_UNIX)
        previous_cwd = Path.cwd()
        monkeypatch.chdir(tmp_path)
        sock.bind(alias.name)
        monkeypatch.chdir(previous_cwd)
    else:
        alias.write_bytes(legitimate_bytes)
    receiver = FileSystemCAS(tmp_path / "receiver")
    prior = _put(receiver, OLD)
    owner_bytes = {
        p.relative_to(receiver.root).as_posix(): p.read_bytes()
        for p in receiver.root.rglob("*")
        if p.is_file()
    }
    before = alias.lstat()
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(
        target=runpy.run_path,
        args=(str(Path(__file__).resolve()),),
        kwargs={
            "run_name": "__e02_transfer_worker__",
            "init_globals": {
                "e02_worker_name": "_import_path_probe",
                "e02_worker_args": (str(receiver.root), str(alias), kind == "fifo_at_open", child),
            },
        },
    )
    process.start()
    try:
        assert parent.poll(20), "import path probe did not start"
        assert parent.recv() == "ready"
        assert parent.poll(2), "import opened a nonregular archive and blocked"
        result = parent.recv()
        assert result["type"] == "ValueError", result
        if kind in {"regular_symlink", "dangling_symlink"}:
            assert result["message"] == "Transfer source must not be a symlink"
        else:
            assert "regular file" in result["message"]
        if kind == "fifo_at_open":
            assert result["substituted"]
            assert stat.S_ISFIFO(alias.lstat().st_mode)
            assert alias.with_name("retained-before-open.tar.gz").read_bytes() == legitimate_bytes
        else:
            after = alias.lstat()
            assert (after.st_ino, stat.S_IFMT(after.st_mode)) == (
                before.st_ino,
                stat.S_IFMT(before.st_mode),
            )
        process.join(20)
        assert process.exitcode == 0
        assert legitimate.read_bytes() == legitimate_bytes
        assert {
            p.relative_to(receiver.root).as_posix(): p.read_bytes()
            for p in receiver.root.rglob("*")
            if p.is_file()
        } == owner_bytes
        reopened = FileSystemCAS(receiver.root)
        assert reopened.get_bytes(prior) == OLD
        assert reopened.verify(prior).ok
        assert not reopened.has(incoming)
        assert not list(receiver.root.glob(".cas-import-*"))
    finally:
        if process.is_alive():
            process.terminate()
        process.join(20)
        parent.close()
        child.close()
        if sock is not None:
            sock.close()


def _import_path_probe(cas_root: str, source_name: str, substitute: bool, connection: Any) -> None:
    import builtins

    source = Path(source_name)
    real_open = builtins.open
    real_os_open = transfer.os.open
    substituted = False

    def exchange_source(path) -> None:
        nonlocal substituted
        if not substitute or substituted or not isinstance(path, (str, os.PathLike)):
            return
        if Path(path) == source:
            source.rename(source.with_name("retained-before-open.tar.gz"))
            os.mkfifo(source)
            substituted = True

    def open_stream(path, *args, **kwargs):
        exchange_source(path)
        return real_open(path, *args, **kwargs)

    def open_descriptor(path, *args, **kwargs):
        exchange_source(path)
        return real_os_open(path, *args, **kwargs)

    builtins.open = open_stream
    transfer.os.open = open_descriptor
    store = FileSystemCAS(Path(cas_root))
    connection.send("ready")
    try:
        store.import_subgraph(source, verify_integrity=True)
    except Exception as error:
        connection.send(
            {"type": type(error).__name__, "message": str(error), "substituted": substituted}
        )
    else:
        connection.send(
            {
                "type": "published",
                "message": "nonregular input was admitted",
                "substituted": substituted,
            }
        )


if __name__ == "__e02_transfer_worker__":
    # runpy is importable in a fresh spawn child even when pytest importlib
    # assigns this native file a test-only module name absent from sys.path.
    globals()[globals()["e02_worker_name"]](*globals()["e02_worker_args"])


@pytest.mark.parametrize("foreign_entry", ["note", "replaced_member"])
def test_late_foreign_entry_survives_directory_generation_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    foreign_entry: str,
) -> None:
    """A preflight census never authorizes deleting a later user's bytes."""
    source = FileSystemCAS(tmp_path / "cas")
    old = _put(source, OLD)
    new = _put(source, NEW)
    target = tmp_path / "export"
    source.export_subgraph([old], target, compress=False)
    original = transfer._validate_directory_export
    relative = (
        Path("user-note.txt")
        if foreign_entry == "note"
        else next(Path(name) for name in _package_bytes(target) if name.endswith(".blob"))
    )
    foreign_bytes = b"user bytes introduced after the export ownership census"
    injected = False

    def add_after_preflight(path: Path):
        nonlocal injected
        owned = original(path)
        if path == target and not injected:
            (path / relative).write_bytes(foreign_bytes)
            injected = True
        return owned

    monkeypatch.setattr(transfer, "_validate_directory_export", add_after_preflight)
    report = source.export_subgraph([new], target, compress=False)
    assert injected
    _assert_complete(target, NEW)
    _assert_imported(target, tmp_path / "new-reader", NEW)
    retained = [
        path
        for path in tmp_path.glob(".export.*")
        if path.is_dir()
        and (path / relative).is_file()
        and (path / relative).read_bytes() == foreign_bytes
    ]
    assert len(retained) == 1, "late user-owned bytes were deleted with the old export"
    assert report.previous_generation == retained[0]
    assert relative.as_posix() not in _package_bytes(target) or foreign_entry == "replaced_member"


def test_manifest_read_failure_preserves_previous_archive_bytes_and_fresh_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real source failure after blob streaming must leave complete archive A."""
    from contextlib import contextmanager

    source = FileSystemCAS(tmp_path / "cas")
    old = _put(source, OLD)
    new = _put(source, NEW)
    target = tmp_path / "export.tar.gz"
    source.export_subgraph([old], target)
    original_bytes = target.read_bytes()
    original_open = source.open_member
    streamed = False

    @contextmanager
    def fail_manifest(request, member, **kwargs):
        nonlocal streamed
        if member == "manifest":
            assert streamed
            raise OSError("controlled source manifest read failure")
        with original_open(request, member, **kwargs) as stream:
            if member == "blob":
                streamed = True
            yield stream

    with monkeypatch.context() as fault:
        fault.setattr(source, "open_member", fail_manifest)
        with pytest.raises(OSError, match="controlled source manifest read failure"):
            source.export_subgraph([new], target)
    assert streamed
    assert target.read_bytes() == original_bytes, (
        "failed B overwrote the previously valid archive A"
    )
    assert list(tmp_path.glob(".export.tar.gz.staging-*"))
    _assert_complete(target, OLD)
    _assert_imported(target, tmp_path / "fresh-reader", OLD)


@pytest.mark.parametrize("compress", [False, True])
def test_exception_after_actual_publication_preserves_the_observed_old_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    compress: bool,
) -> None:
    """A post-syscall exception must not let finally delete the exchanged old tree."""
    from polisyos.core.artifacts import ExportDurabilityError

    source = FileSystemCAS(tmp_path / "cas")
    old = _put(source, OLD)
    new = _put(source, NEW)
    target = tmp_path / ("export.tar.gz" if compress else "export")
    source.export_subgraph([old], target, compress=compress)
    before = _package_bytes(target)
    original_exchange = transfer._exchange_directory_generation
    note = b"late user note survives publication and exception cleanup"

    def exchange_then_fail(stage, current):
        if not compress:
            (current / "user-note.txt").write_bytes(note)
        original_exchange(stage, current)
        raise OSError("controlled failure after visible exchange")

    with monkeypatch.context() as failure:
        failure.setattr(transfer, "_exchange_directory_generation", exchange_then_fail)
        with pytest.raises(ExportDurabilityError) as refusal:
            source.export_subgraph([new], target, compress=compress)
    assert refusal.value.replaced is True
    previous = refusal.value.previous_generation
    assert previous is not None and previous.exists()
    retained = _package_bytes(previous)
    if not compress:
        assert retained.pop("user-note.txt") == note
    assert retained == before
    _assert_complete(target, NEW)
    _assert_imported(target, tmp_path / "new-reader", NEW)
    assert ExportDurabilityError is transfer.ExportDurabilityError


def test_archive_replace_refusal_reports_retained_bytes_without_claiming_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed exchange exposes its retained private stage and still-selected A."""
    source = FileSystemCAS(tmp_path / "cas")
    old = _put(source, OLD)
    new = _put(source, NEW)
    target = tmp_path / "export.tar.gz"
    source.export_subgraph([old], target)
    before = target.read_bytes()
    original = transfer._exchange_directory_generation

    def refuse_replace(stage, destination, *args, **kwargs):
        if Path(destination) == target:
            raise OSError("controlled archive replacement refusal")
        return original(stage, destination, *args, **kwargs)

    with monkeypatch.context() as failure:
        failure.setattr(transfer, "_exchange_directory_generation", refuse_replace)
        with pytest.raises(transfer.ExportDurabilityError) as refusal:
            source.export_subgraph([new], target)
    assert refusal.value.replaced is False
    previous = refusal.value.previous_generation
    assert previous is None
    assert target.read_bytes() == before
    assert list(tmp_path.glob(".export.tar.gz.staging-*"))
    _assert_imported(target, tmp_path / "retained-reader", OLD)


@pytest.mark.parametrize("fault_stage", ["write", "tar_close"])
def test_archive_write_and_footer_failure_keep_prior_package_and_user_siblings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault_stage: str,
) -> None:
    """Neither a streamed-write error nor a completed-footer error selects partial B."""
    source = FileSystemCAS(tmp_path / "cas")
    old = _put(source, OLD)
    new = _put(source, NEW)
    target = tmp_path / "export.tar.gz"
    source.export_subgraph([old], target)
    original_bytes = target.read_bytes()
    sibling = tmp_path / "user-archive.tar.gz"
    sibling.write_bytes(b"unrelated user archive")
    addfile = tarfile.TarFile.addfile
    close = tarfile.TarFile.close
    failed = False

    def fail_write(archive, info, fileobj=None):
        nonlocal failed
        result = addfile(archive, info, fileobj)
        if not failed and info.name.endswith(".blob"):
            failed = True
            raise OSError("controlled archive streamed write failure")
        return result

    def fail_close(archive):
        nonlocal failed
        was_open = not archive.closed
        result = close(archive)
        if was_open and archive.mode == "w" and not failed:
            failed = True
            raise OSError("controlled archive footer close failure")
        return result

    with monkeypatch.context() as failure:
        if fault_stage == "write":
            failure.setattr(tarfile.TarFile, "addfile", fail_write)
        else:
            failure.setattr(tarfile.TarFile, "close", fail_close)
        with pytest.raises(OSError, match="controlled archive"):
            source.export_subgraph([new], target)
    assert failed
    assert target.read_bytes() == original_bytes
    assert sibling.read_bytes() == b"unrelated user archive"
    assert list(tmp_path.glob(".export.tar.gz.staging-*"))
    _assert_imported(target, tmp_path / "prior-reader", OLD)


def test_archive_cleanup_preserves_a_foreign_file_at_the_vacated_stage_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = FileSystemCAS(tmp_path / "cas")
    new = _put(source, NEW)
    target = tmp_path / "export.tar.gz"
    original = transfer._rename_export_generation
    foreign: list[Path] = []

    def publish_then_create(stage, destination, *, exchange):
        original(stage, destination, exchange=exchange)
        if Path(destination) == target:
            assert exchange is False
            Path(stage).write_bytes(b"foreign file at a vacated private-stage name")
            foreign.append(Path(stage))

    monkeypatch.setattr(transfer, "_rename_export_generation", publish_then_create)
    report = source.export_subgraph([new], target)
    assert report.previous_generation is None
    assert (
        len(foreign) == 1
        and foreign[0].read_bytes() == b"foreign file at a vacated private-stage name"
    )
    _assert_complete(target, NEW)
    _assert_imported(target, tmp_path / "reader", NEW)


@pytest.mark.parametrize("compress", [False, True])
def test_concurrent_writer_generation_is_the_one_actually_retained(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    compress: bool,
) -> None:
    source = FileSystemCAS(tmp_path / "cas")
    old, intervening, final = (
        _put(source, value) for value in (OLD, NEW, b"final third generation")
    )
    target = tmp_path / ("export.tar.gz" if compress else "export")
    other = tmp_path / ("concurrent.tar.gz" if compress else "concurrent")
    source.export_subgraph([old], target, compress=compress)
    source.export_subgraph([intervening], other, compress=compress)
    original = transfer._exchange_directory_generation
    injected = False

    def select_intervening_first(stage, current):
        nonlocal injected
        if Path(current) == target and not injected:
            injected = True
            original(other, current)
        original(stage, current)

    monkeypatch.setattr(transfer, "_exchange_directory_generation", select_intervening_first)
    report = source.export_subgraph([final], target, compress=compress)
    assert injected and report.previous_generation is not None
    _assert_complete(target, b"final third generation")
    _assert_complete(report.previous_generation, NEW)
    _assert_complete(other, OLD)
    _assert_imported(report.previous_generation, tmp_path / "intervening-reader", NEW)


def test_owned_archive_descriptor_never_truncates_a_swapped_stage_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = FileSystemCAS(tmp_path / "cas")
    old, new = _put(source, OLD), _put(source, NEW)
    target = tmp_path / "export.tar.gz"
    source.export_subgraph([old], target)
    before = target.read_bytes()
    sentinel = tmp_path / "foreign-data"
    sentinel.write_bytes(b"foreign bytes must never be truncated")
    original = tarfile.open
    swapped: list[Path] = []

    def swap_stage_path(name=None, mode="r", *args, **kwargs):
        if mode == "w:gz" and not swapped:
            assert kwargs.get("fileobj") is not None
            stage = Path(name)
            stage.unlink()
            stage.symlink_to(sentinel)
            swapped.append(stage)
        return original(name, mode, *args, **kwargs)

    monkeypatch.setattr(tarfile, "open", swap_stage_path)
    # The finite admission layer rejects an unmeasurable symlink before the
    # later native publication identity check; it must preserve the same bytes.
    with pytest.raises(ExportResourceError, match="unmeasurable_retained_entry") as refusal:
        source.export_subgraph([new], target)
    assert refusal.value.reason == "unmeasurable_retained_entry"
    assert refusal.value.replaced is False
    assert swapped and swapped[0].is_symlink()
    assert refusal.value.staging_path == swapped[0]
    assert refusal.value.occupied_paths == (swapped[0],)
    assert refusal.value.occupied_bytes is None
    assert sentinel.read_bytes() == b"foreign bytes must never be truncated"
    assert target.read_bytes() == before


@pytest.mark.parametrize("compress", [False, True])
def test_first_publication_never_clobbers_an_entry_created_after_the_missing_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    compress: bool,
) -> None:
    source = FileSystemCAS(tmp_path / "cas")
    new = _put(source, NEW)
    target = tmp_path / ("export.tar.gz" if compress else "export")
    original = transfer._rename_export_generation
    injected = False

    def create_foreign_entry(stage, current, *, exchange):
        nonlocal injected
        if Path(current) == target and not exchange:
            injected = True
            if compress:
                target.write_bytes(b"late foreign file")
            else:
                target.mkdir()
                (target / "user-note.txt").write_bytes(b"late foreign directory child")
        original(stage, current, exchange=exchange)

    monkeypatch.setattr(transfer, "_rename_export_generation", create_foreign_entry)
    with pytest.raises(transfer.ExportDurabilityError) as refusal:
        source.export_subgraph([new], target, compress=compress)
    assert injected and refusal.value.replaced is False
    if compress:
        assert target.read_bytes() == b"late foreign file"
    else:
        assert (target / "user-note.txt").read_bytes() == b"late foreign directory child"
        assert refusal.value.staging_path is not None and refusal.value.staging_path.is_dir()


@pytest.mark.parametrize("compress", [False, True])
def test_post_syscall_inode_mismatch_is_unavailable_without_erasing_any_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    compress: bool,
) -> None:
    source = FileSystemCAS(tmp_path / "cas")
    old, foreign, new = (_put(source, value) for value in (OLD, b"foreign staged generation", NEW))
    target = tmp_path / ("export.tar.gz" if compress else "export")
    foreign_path = tmp_path / ("foreign.tar.gz" if compress else "foreign")
    moved_owned = tmp_path / ("moved-owned.tar.gz" if compress else "moved-owned")
    source.export_subgraph([old], target, compress=compress)
    source.export_subgraph([foreign], foreign_path, compress=compress)
    original = transfer._rename_export_generation
    injected = False

    def replace_private_name(stage, current, *, exchange):
        nonlocal injected
        if Path(current) == target and not injected:
            injected = True
            original(stage, moved_owned, exchange=False)
            original(foreign_path, stage, exchange=False)
        original(stage, current, exchange=exchange)

    monkeypatch.setattr(transfer, "_rename_export_generation", replace_private_name)
    with pytest.raises(transfer.ExportDurabilityError, match="owned staged inode") as refusal:
        source.export_subgraph([new], target, compress=compress)
    assert injected and refusal.value.replaced is None
    assert refusal.value.previous_generation is not None
    _assert_complete(refusal.value.previous_generation, OLD)
    _assert_complete(target, b"foreign staged generation")
    _assert_complete(moved_owned, NEW)


def test_displaced_symlink_is_preserved_but_never_reported_as_a_trusted_archive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = FileSystemCAS(tmp_path / "cas")
    old, new = _put(source, OLD), _put(source, NEW)
    target = tmp_path / "export.tar.gz"
    source.export_subgraph([old], target)
    saved = tmp_path / "saved-original.tar.gz"
    sentinel = tmp_path / "user-data"
    sentinel.write_bytes(b"foreign symlink referent")
    original = transfer._rename_export_generation

    def swap_target_entry(stage, current, *, exchange):
        if Path(current) == target:
            original(target, saved, exchange=False)
            target.symlink_to(sentinel)
        original(stage, current, exchange=exchange)

    monkeypatch.setattr(transfer, "_rename_export_generation", swap_target_entry)
    with pytest.raises(transfer.ExportDurabilityError, match="untrusted kind") as refusal:
        source.export_subgraph([new], target)
    assert refusal.value.replaced is True
    assert (
        refusal.value.previous_generation is not None
        and refusal.value.previous_generation.is_symlink()
    )
    assert sentinel.read_bytes() == b"foreign symlink referent"
    _assert_complete(target, NEW)
    _assert_complete(saved, OLD)


def test_failed_directory_stage_keeps_a_late_foreign_child_and_exposes_its_locator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = FileSystemCAS(tmp_path / "cas")
    old, new = _put(source, OLD), _put(source, NEW)
    target = tmp_path / "export"
    source.export_subgraph([old], target, compress=False)
    before = _package_bytes(target)

    def add_foreign_child_and_fail(stage):
        (stage / "user-note.txt").write_bytes(b"foreign child in a failed stage")
        raise OSError("controlled staging sync failure")

    monkeypatch.setattr(transfer, "_sync_directory_generation", add_foreign_child_and_fail)
    with pytest.raises(
        transfer.ExportDurabilityError, match="controlled staging sync failure"
    ) as refusal:
        source.export_subgraph([new], target, compress=False)
    assert refusal.value.replaced is False
    assert refusal.value.staging_path is not None
    assert (
        refusal.value.staging_path / "user-note.txt"
    ).read_bytes() == b"foreign child in a failed stage"
    assert _package_bytes(target) == before
