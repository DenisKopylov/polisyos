from __future__ import annotations

import errno
import json
import sys
from pathlib import Path

import pytest

from tools.lib import runner


def test_filesystem_write_boundary_confines_native_and_python_writers(tmp_path: Path) -> None:
    """Allow writes only in a fresh scratch subtree for the process tree."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    protected = checkout / "source.txt"
    protected.write_text("source preimage\n", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside preimage\n", encoding="utf-8")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    allowed = scratch / "allowed.txt"
    alias = scratch / "checkout-alias"
    code = "\n".join(
        (
            "import json, os, subprocess, sys",
            "from pathlib import Path",
            "protected, outside, scratch = map(Path, sys.argv[1:])",
            "def attempt(path):",
            "    try:",
            "        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)",
            "        try: os.write(fd, b'changed\\n')",
            "        finally: os.close(fd)",
            "    except OSError as error:",
            "        return {'result': 'denied', 'errno': error.errno}",
            "    return {'result': 'written', 'errno': None}",
            "os.symlink(protected, scratch / 'checkout-alias')",
            "shell = subprocess.run(['/bin/sh', '-c', 'printf blocked > \"$1\"', 'probe', str(protected)], capture_output=True, text=True, check=False)",
            "print(json.dumps({'checkout': attempt(protected), 'outside': attempt(outside), 'symlink': attempt(scratch / 'checkout-alias'), 'allowed': attempt(scratch / 'allowed.txt'), 'shell_returncode': shell.returncode, 'shell_stderr': shell.stderr}, sort_keys=True))",
        )
    )
    try:
        completed = runner.run_with_filesystem_write_boundary(
            [sys.executable, "-B", "-c", code, str(protected), str(outside), str(scratch)],
            repo_root=checkout,
            cwd=checkout,
            writable_root=scratch,
        )
    except runner.FilesystemWriteBoundaryUnavailableError as error:
        pytest.skip(f"native filesystem write fence unavailable: {error.backend}: {error}")

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout.strip())
    assert report["checkout"]["result"] == "denied"
    assert report["outside"]["result"] == "denied"
    assert report["symlink"]["result"] == "denied"
    assert report["allowed"]["result"] == "written"
    assert report["shell_returncode"] != 0
    denied_errnos = {errno.EPERM, errno.EACCES, errno.EROFS}
    assert report["checkout"]["errno"] in denied_errnos
    assert report["outside"]["errno"] in denied_errnos
    assert report["symlink"]["errno"] in denied_errnos
    assert protected.read_text(encoding="utf-8") == "source preimage\n"
    assert outside.read_text(encoding="utf-8") == "outside preimage\n"
    assert allowed.read_bytes() == b"changed\n"


def test_filesystem_write_boundary_rejects_scratch_inside_checkout(tmp_path: Path) -> None:
    """The protected checkout can never also be the writable probe root."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    writable = checkout / "scratch"
    writable.mkdir()
    with pytest.raises(ValueError, match="outside the read-only checkout"):
        runner.run_with_filesystem_write_boundary(
            [sys.executable, "-B", "-c", "pass"],
            repo_root=checkout,
            cwd=checkout,
            writable_root=writable,
        )


def test_filesystem_write_boundary_marks_unsupported_platform_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unsupported platforms fail closed with an explicit backend identity."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setattr(runner.sys, "platform", "win32")
    with pytest.raises(runner.FilesystemWriteBoundaryUnavailableError) as error:
        runner.run_with_filesystem_write_boundary(
            [sys.executable, "-B", "-c", "pass"],
            repo_root=checkout,
            cwd=checkout,
            writable_root=scratch,
        )
    assert error.value.backend == "unsupported-platform"


def test_filesystem_write_boundary_rejects_symlinked_scratch_path(
    tmp_path: Path,
) -> None:
    """A scratch locator cannot escape validation through a symlink."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    alias = tmp_path / "scratch-alias"
    alias.symlink_to(scratch, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink components"):
        runner.run_with_filesystem_write_boundary(
            [sys.executable, "-B", "-c", "pass"],
            repo_root=checkout,
            cwd=checkout,
            writable_root=alias,
        )


def test_filesystem_write_boundary_marks_missing_linux_backend_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Linux without bubblewrap returns an explicit unavailable result."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setattr(runner.sys, "platform", "linux")
    monkeypatch.setattr(runner.shutil, "which", lambda _name: None)

    with pytest.raises(runner.FilesystemWriteBoundaryUnavailableError) as error:
        runner.run_with_filesystem_write_boundary(
            [sys.executable, "-B", "-c", "pass"],
            repo_root=checkout,
            cwd=checkout,
            writable_root=scratch,
        )

    assert error.value.backend == "linux-bubblewrap-unavailable"


def test_external_temporary_base_is_rejected_before_any_allocation(tmp_path: Path) -> None:
    """Reject checkout and symlinked bases before callers create scratch paths."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "source.txt").write_text("protected\n", encoding="utf-8")

    with pytest.raises(ValueError, match="outside and not an ancestor"):
        runner.resolve_external_temporary_base(checkout, env={"TMPDIR": str(checkout)})
    assert sorted(path.name for path in checkout.iterdir()) == ["source.txt"]
    assert (checkout / "source.txt").read_text(encoding="utf-8") == "protected\n"

    physical_parent = tmp_path / "physical-parent"
    physical_parent.mkdir()
    (physical_parent / "candidate").mkdir()
    symlink_parent = tmp_path / "symlink-parent"
    symlink_parent.symlink_to(physical_parent, target_is_directory=True)
    selected = symlink_parent / "candidate"
    with pytest.raises(ValueError, match="without symlink components"):
        runner.resolve_external_temporary_base(checkout, env={"TMPDIR": str(selected)})
    assert (physical_parent / "candidate").is_dir()
    assert sorted(path.name for path in physical_parent.iterdir()) == ["candidate"]


def test_external_temporary_base_does_not_fallback_from_malformed_value(
    tmp_path: Path,
) -> None:
    """An explicit malformed temp setting fails instead of selecting a default."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    for value in ("", str(tmp_path / "missing")):
        with pytest.raises(ValueError):
            runner.resolve_external_temporary_base(checkout, env={"TMPDIR": value})
    assert sorted(path.name for path in tmp_path.iterdir()) == ["checkout"]


def test_external_temporary_base_uses_default_only_when_unset(tmp_path: Path) -> None:
    """An absent temp setting uses the canonical POSIX default without probing writes."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    try:
        selected = runner.resolve_external_temporary_base(checkout, env={})
    except runner.FilesystemWriteBoundaryUnavailableError as error:
        pytest.skip(f"no POSIX temporary default: {error.backend}: {error}")

    assert selected.is_absolute()
    assert selected.is_dir()
    assert selected == selected.resolve(strict=True)
    assert not selected.is_relative_to(checkout.resolve())
    assert list(checkout.iterdir()) == []
