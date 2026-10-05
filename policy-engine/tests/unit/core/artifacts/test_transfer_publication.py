"""Filesystem fault controls for publishing complete CAS transfer generations."""

from __future__ import annotations

import multiprocessing
import os
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import Any

import pytest

from polisyos.core.artifacts._atomic_write import AtomicFileDurabilityError
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions


def _artifact(store: FileSystemCAS, payload: bytes) -> ArtifactRef:
    return store.put_bytes(
        payload,
        PutOptions(kind="tests.transfer.publication", media_type="application/octet-stream"),
    )


def _read_package(archive: Path, root: Path, ref: ArtifactRef, payload: bytes) -> None:
    reopened = FileSystemCAS(root)
    report = reopened.import_subgraph(archive, verify_integrity=True)
    assert report.verification_failed == []
    assert reopened.get_bytes(ref) == payload
    assert reopened.get_manifest(ref).kind == ref.kind


@pytest.mark.parametrize("failure", ["member", "replace", "fsync"])
def test_failed_archive_replacement_keeps_previous_verified_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """A failed export cannot turn the previous complete inventory into partial bytes."""
    source = FileSystemCAS(tmp_path / "source")
    first = _artifact(source, b"first verified generation")
    second = _artifact(source, b"second replacement generation")
    archive = tmp_path / "current.tar.gz"
    source.export_subgraph([first], archive)
    previous = archive.read_bytes()
    _read_package(archive, tmp_path / "before", first, b"first verified generation")

    with monkeypatch.context() as faults:
        if failure == "member":
            original_addfile = tarfile.TarFile.addfile
            writes = 0

            def fail_member(self: tarfile.TarFile, *args: object, **kwargs: object) -> None:
                nonlocal writes
                writes += 1
                if writes == 2:
                    raise OSError("injected archive member failure")
                original_addfile(self, *args, **kwargs)

            faults.setattr(tarfile.TarFile, "addfile", fail_member)
        elif failure == "replace":
            original_replace = os.replace

            def fail_replace(src: Path, dst: Path) -> None:
                if Path(dst) == archive:
                    raise OSError("injected archive replace failure")
                original_replace(src, dst)

            faults.setattr(os, "replace", fail_replace)
        else:

            def fail_fsync(_descriptor: int) -> None:
                raise OSError("injected archive fsync failure")

            faults.setattr(os, "fsync", fail_fsync)

        with pytest.raises(OSError, match="injected archive"):
            source.export_subgraph([second], archive)

    assert archive.read_bytes() == previous
    _read_package(archive, tmp_path / "after", first, b"first verified generation")
    assert not list(tmp_path.glob(".current.tar.gz.staging-*"))


def test_archive_replacement_publishes_only_new_inventory(tmp_path: Path) -> None:
    """Successful replacement is read back through the actual receiving CAS."""
    source = FileSystemCAS(tmp_path / "source")
    first = _artifact(source, b"generation a")
    second = _artifact(source, b"generation b")
    archive = tmp_path / "current.tar.gz"
    source.export_subgraph([first], archive)
    archive.chmod(0o640)
    source.export_subgraph([second], archive)

    target = FileSystemCAS(tmp_path / "target")
    report = target.import_subgraph(archive, verify_integrity=True)
    assert report.verification_failed == []
    assert target.get_bytes(second) == b"generation b"
    assert not target.has(first)
    assert archive.stat().st_mode & 0o7777 == 0o640


def test_archive_parent_sync_failure_reports_published_complete_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After rename, sync failure is explicit while the new archive remains readable."""
    import polisyos.core.artifacts._transfer_ops as transfer_ops

    source = FileSystemCAS(tmp_path / "source")
    first = _artifact(source, b"old generation")
    second = _artifact(source, b"new generation")
    archive = tmp_path / "current.tar.gz"
    source.export_subgraph([first], archive)

    def fail_directory_sync(_directory: Path) -> None:
        raise OSError("injected archive parent fsync failure")

    with monkeypatch.context() as faults:
        faults.setattr(transfer_ops, "fsync_directory", fail_directory_sync)
        with pytest.raises(AtomicFileDurabilityError, match="parent directory sync") as caught:
            source.export_subgraph([second], archive)
    assert caught.value.replaced is True
    _read_package(archive, tmp_path / "reopened", second, b"new generation")
    assert not list(tmp_path.glob(".current.tar.gz.staging-*"))


def _pause_archive_writer(source_root: str, archive: str, ref_json: str, ready: Any) -> None:
    """Hold a real child writer after a completed member but before archive close."""
    original_addfile = tarfile.TarFile.addfile
    paused = False
    hold = multiprocessing.Event()

    def pause_member(self: tarfile.TarFile, *args: object, **kwargs: object) -> None:
        nonlocal paused
        original_addfile(self, *args, **kwargs)
        if not paused:
            paused = True
            ready.set()
            hold.wait()

    tarfile.TarFile.addfile = pause_member
    source = FileSystemCAS(Path(source_root))
    source.export_subgraph([ArtifactRef.model_validate_json(ref_json)], Path(archive))


def test_killed_archive_writer_keeps_previous_package_for_restarted_consumer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SIGKILL before publication leaves only a private stage and the complete old package."""
    source = FileSystemCAS(tmp_path / "source")
    first = _artifact(source, b"previous generation survives kill")
    second = _artifact(source, b"interrupted replacement")
    archive = tmp_path / "current.tar.gz"
    source.export_subgraph([first], archive)
    previous = archive.read_bytes()
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    child = context.Process(
        target=_pause_archive_writer,
        args=(str(source.root), str(archive), second.model_dump_json(), ready),
    )
    child.start()
    try:
        assert ready.wait(timeout=10), "child did not reach archive member boundary"
        child.kill()
        child.join(timeout=10)
        assert not child.is_alive()
        assert child.exitcode != 0
    finally:
        if child.is_alive():
            child.kill()
            child.join(timeout=10)
    assert archive.read_bytes() == previous
    assert list(tmp_path.glob(".current.tar.gz.staging-*"))
    _read_package(archive, tmp_path / "restarted", first, b"previous generation survives kill")


def test_concurrent_archive_writers_publish_one_complete_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contending writers use private stages; the winning package never mixes members."""
    source = FileSystemCAS(tmp_path / "source")
    first = _artifact(source, b"concurrent generation one")
    second = _artifact(source, b"concurrent generation two")
    archive = tmp_path / "current.tar.gz"
    source.export_subgraph([first], archive)
    gate = Barrier(2)
    original_addfile = tarfile.TarFile.addfile

    def synchronize_metadata(
        self: tarfile.TarFile, info: tarfile.TarInfo, fileobj: Any = None
    ) -> None:
        original_addfile(self, info, fileobj)
        if info.name == "export_manifest.json":
            gate.wait(timeout=10)

    with monkeypatch.context() as faults:
        faults.setattr(tarfile.TarFile, "addfile", synchronize_metadata)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(source.export_subgraph, [ref], archive) for ref in (first, second)
            ]
            for future in futures:
                assert future.result(timeout=10).exported_artifacts == 1

    reopened = FileSystemCAS(tmp_path / "reopened")
    report = reopened.import_subgraph(archive, verify_integrity=True)
    assert report.verification_failed == []
    assert reopened.has(first) != reopened.has(second)
    chosen = first if reopened.has(first) else second
    assert reopened.get_bytes(chosen) == source.get_bytes(chosen)
    assert not list(tmp_path.glob(".current.tar.gz.staging-*"))
