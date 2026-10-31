from __future__ import annotations

import errno
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tools.lib import runner


def test_filesystem_write_boundary_confines_native_and_python_writers(tmp_path: Path) -> None:
    """Confine persistent writes while native Git uses the nonpersistent null sink."""
    git = shutil.which("git")
    if git is None:
        pytest.skip("read-only Git probe requires the Git executable")
    if sys.platform != "darwin" and not sys.platform.startswith("linux"):
        pytest.skip("native filesystem write fence requires macOS or Linux")
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    protected = checkout / "source.txt"
    protected.write_text("source preimage\n", encoding="utf-8")
    git_env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    git_env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_OPTIONAL_LOCKS="0")
    subprocess.run(
        [git, "init", "--quiet", str(checkout)], env=git_env, capture_output=True, check=True
    )
    subprocess.run(
        [git, "add", "--", "source.txt"], cwd=checkout, env=git_env, capture_output=True, check=True
    )
    null_before = os.stat(os.devnull, follow_symlinks=False)
    assert stat.S_ISCHR(null_before.st_mode)
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
            f"git = {git!r}",
            "fd = os.open(os.devnull, os.O_RDWR)",
            "try:",
            "    discarded = os.write(fd, b'discarded-data')",
            "    assert os.read(fd, 1) == b''",
            "finally: os.close(fd)",
            "listed = subprocess.run([git, 'ls-files', '--cached', '-z', '--', '.'], capture_output=True, check=True)",
            "assert listed.stdout == b'source.txt\\0'",
            "def attempt(path):",
            "    try:",
            "        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)",
            "        try: os.write(fd, b'changed\\n')",
            "        finally: os.close(fd)",
            "    except OSError as error:",
            "        return {'result': 'denied', 'errno': error.errno}",
            "    return {'result': 'written', 'errno': None}",
            "def unlink_attempt(path):",
            "    try: path.unlink()",
            "    except OSError as error: return {'result': 'denied', 'errno': error.errno}",
            "    return {'result': 'unlinked', 'errno': None}",
            "os.symlink(protected, scratch / 'checkout-alias')",
            "shell = subprocess.run(['/bin/sh', '-c', 'printf blocked > \"$1\"', 'probe', str(protected)], capture_output=True, text=True, check=False)",
            "print(json.dumps({'checkout': attempt(protected), 'outside': attempt(outside), 'outside_create': attempt(outside.with_name('outside-new.txt')), 'outside_unlink': unlink_attempt(outside), 'symlink': attempt(scratch / 'checkout-alias'), 'allowed': attempt(scratch / 'allowed.txt'), 'shell_returncode': shell.returncode, 'shell_stderr': shell.stderr, 'discarded': discarded}, sort_keys=True))",
        )
    )
    try:
        completed = runner.run_with_filesystem_write_boundary(
            [sys.executable, "-B", "-c", code, str(protected), str(outside), str(scratch)],
            repo_root=checkout,
            cwd=checkout,
            writable_root=scratch,
            env=git_env,
        )
    except runner.FilesystemWriteBoundaryUnavailableError as error:
        pytest.skip(f"native filesystem write fence unavailable: {error.backend}: {error}")

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout.strip())
    assert report["checkout"]["result"] == "denied"
    assert report["outside"]["result"] == "denied"
    assert report["outside_create"]["result"] == "denied"
    assert report["outside_unlink"]["result"] == "denied"
    assert report["discarded"] == len(b"discarded-data")
    assert report["symlink"]["result"] == "denied"
    assert report["allowed"]["result"] == "written"
    assert report["shell_returncode"] != 0
    denied_errnos = {errno.EPERM, errno.EACCES, errno.EROFS}
    assert report["checkout"]["errno"] in denied_errnos
    assert report["outside"]["errno"] in denied_errnos
    assert report["outside_create"]["errno"] in denied_errnos
    assert report["outside_unlink"]["errno"] in denied_errnos
    assert report["symlink"]["errno"] in denied_errnos
    assert protected.read_text(encoding="utf-8") == "source preimage\n"
    assert outside.read_text(encoding="utf-8") == "outside preimage\n"
    assert allowed.read_bytes() == b"changed\n"
    assert not outside.with_name("outside-new.txt").exists()
    null_after = os.stat(os.devnull, follow_symlinks=False)
    assert (null_after.st_mode, null_after.st_rdev, null_after.st_ino) == (
        null_before.st_mode,
        null_before.st_rdev,
        null_before.st_ino,
    )


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


def test_external_temporary_base_uses_default_only_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An absent temp setting selects the default across disjoint checkout roots."""
    if os.name != "posix":
        with pytest.raises(runner.FilesystemWriteBoundaryUnavailableError) as error:
            runner.resolve_external_temporary_base(Path.cwd(), env={})
        pytest.skip(f"no POSIX temporary default: {error.value.backend}: {error.value}")

    default_base = Path("/tmp").resolve(strict=True)
    external_parent = (default_base.parent / "var" / "tmp").resolve(strict=True)
    assert external_parent != default_base
    assert not external_parent.is_relative_to(default_base)
    assert not default_base.is_relative_to(external_parent)

    gettempdir_calls = 0

    def unexpected_gettempdir() -> str:
        nonlocal gettempdir_calls
        gettempdir_calls += 1
        raise AssertionError("default resolution must not probe tempfile.gettempdir")

    monkeypatch.setattr(tempfile, "gettempdir", unexpected_gettempdir)
    with tempfile.TemporaryDirectory(
        prefix="polisyos-default-temp-checkout-",
        dir=external_parent,
    ) as external_root:
        checkout = Path(external_root) / "checkout"
        checkout.mkdir()
        protected = checkout / "source.txt"
        protected.write_text("protected\n", encoding="utf-8")

        selected = runner.resolve_external_temporary_base(checkout, env={})

        assert selected == default_base
        assert selected.is_absolute()
        assert selected.is_dir()
        assert selected == selected.resolve(strict=True)
        assert not selected.is_relative_to(checkout.resolve())
        assert not checkout.resolve().is_relative_to(selected)
        assert sorted(path.name for path in checkout.iterdir()) == ["source.txt"]
        assert protected.read_text(encoding="utf-8") == "protected\n"

    with tempfile.TemporaryDirectory(
        prefix="polisyos-default-temp-ancestor-",
        dir=default_base,
    ) as default_root:
        nested_checkout = Path(default_root) / "checkout"
        nested_checkout.mkdir()
        protected = nested_checkout / "source.txt"
        protected.write_text("protected\n", encoding="utf-8")

        with pytest.raises(ValueError, match="outside and not an ancestor"):
            runner.resolve_external_temporary_base(nested_checkout, env={})

        assert sorted(path.name for path in nested_checkout.iterdir()) == ["source.txt"]
        assert protected.read_text(encoding="utf-8") == "protected\n"

    assert gettempdir_calls == 0
