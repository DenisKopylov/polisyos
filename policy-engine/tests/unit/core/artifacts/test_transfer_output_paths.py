"""Real archive publication controls for the output path's filesystem identity."""

from __future__ import annotations

import multiprocessing
import os
import stat
import tarfile
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions


def _artifact(source: FileSystemCAS, payload: bytes) -> ArtifactRef:
    return source.put_bytes(
        payload,
        PutOptions(kind="tests.transfer.output_path", media_type="application/octet-stream"),
    )


def _try_archive_output(source_root: str, output: str, ref_json: str, results: Any) -> None:
    """Run a real export in a bounded child so a FIFO regression cannot block pytest."""
    calls = 0
    original_open = tarfile.open

    def count_open(*args: Any, **kwargs: Any) -> tarfile.TarFile:
        nonlocal calls
        calls += 1
        return original_open(*args, **kwargs)

    tarfile.open = count_open
    source = FileSystemCAS(Path(source_root))
    try:
        report = source.export_subgraph([ArtifactRef.model_validate_json(ref_json)], Path(output))
    except Exception as exc:
        results.put({"exception": type(exc).__name__, "message": str(exc), "tar_opens": calls})
    else:
        results.put({"exported_artifacts": report.exported_artifacts, "tar_opens": calls})


@pytest.mark.parametrize("kind", ["regular-symlink", "dangling-symlink", "fifo", "directory"])
def test_archive_refuses_output_alias_or_nonregular_entry_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """Refusal preserves the real previous package and the output entry itself."""
    source = FileSystemCAS(tmp_path / "source")
    first = _artifact(source, b"previous verified package")
    second = _artifact(source, b"replacement must not be published")
    published = tmp_path / "published.tar.gz"
    source.export_subgraph([first], published)
    previous = published.read_bytes()
    before = FileSystemCAS(tmp_path / "before")
    assert before.import_subgraph(published, verify_integrity=True).verification_failed == []
    assert before.get_bytes(first) == b"previous verified package"

    output = tmp_path / "alias.tar.gz"
    missing = tmp_path / "missing.tar.gz"
    if kind == "regular-symlink":
        output.symlink_to(published.name)
    elif kind == "dangling-symlink":
        output.symlink_to(missing.name)
    elif kind == "fifo":
        os.mkfifo(output, 0o600)
    else:
        output.mkdir()
        (output / "sentinel").write_bytes(b"directory contents remain unchanged")
    prior_entry = output.lstat()
    prior_link = os.readlink(output) if output.is_symlink() else None

    monkeypatch.syspath_prepend(str(Path(__file__).parent))
    context = multiprocessing.get_context("spawn")
    results = context.Queue()
    child = context.Process(
        target=_try_archive_output,
        args=(str(source.root), str(output), second.model_dump_json(), results),
    )
    child.start()
    try:
        child.join(timeout=10)
        assert not child.is_alive(), "archive export blocked on a nonregular output"
        assert child.exitcode == 0
        observed = results.get(timeout=2)
    finally:
        if child.is_alive():
            child.kill()
            child.join(timeout=10)
        results.close()
        results.join_thread()

    assert published.read_bytes() == previous
    after = FileSystemCAS(tmp_path / "after")
    assert after.import_subgraph(published, verify_integrity=True).verification_failed == []
    assert after.get_bytes(first) == b"previous verified package"
    assert not after.has(second)
    assert not missing.exists()
    assert output.lstat().st_ino == prior_entry.st_ino, observed
    assert stat.S_IFMT(output.lstat().st_mode) == stat.S_IFMT(prior_entry.st_mode), observed
    if prior_link is not None:
        assert output.is_symlink()
        assert os.readlink(output) == prior_link
    if kind == "directory":
        assert (output / "sentinel").read_bytes() == b"directory contents remain unchanged"
    assert not list(tmp_path.glob(".alias.tar.gz.staging-*"))
    assert observed["exception"] == "ValueError", observed
    assert "regular file" in observed["message"]
    assert observed["tar_opens"] == 0


@pytest.mark.parametrize("mode", [0o600, 0o640, 0o644])
def test_regular_archive_replacement_retains_mode_and_exact_new_package(
    tmp_path: Path, mode: int
) -> None:
    """Regular outputs retain the existing mode contract and full new inventory."""
    source = FileSystemCAS(tmp_path / "source")
    first = _artifact(source, b"old regular package")
    second = _artifact(source, b"new regular package")
    output = tmp_path / "regular.tar.gz"
    source.export_subgraph([first], output)
    output.chmod(mode)
    source.export_subgraph([second], output)
    reopened = FileSystemCAS(tmp_path / "reopened")
    report = reopened.import_subgraph(output, verify_integrity=True)
    assert report.verification_failed == []
    assert reopened.get_bytes(second) == b"new regular package"
    assert not reopened.has(first)
    assert stat.S_ISREG(output.lstat().st_mode)
    assert stat.S_IMODE(output.lstat().st_mode) == mode
