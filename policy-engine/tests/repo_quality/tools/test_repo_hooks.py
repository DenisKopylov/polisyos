"""Exercise repository hook installation and real Git/Lefthook failure propagation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DASHBOARD = Path("policy-engine/apps/runtime-dashboard")
HOOK_NAMES = ("pre-commit", "pre-push")


def _run(
    *command: str, cwd: Path, env: dict[str, str], check: bool = True
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command, cwd=cwd, env=env, text=True, capture_output=True, timeout=30, check=False
    )
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.fixture
def hook_env(tmp_path: Path) -> dict[str, str]:
    """Use an installed real Lefthook without running its installer in the owner checkout."""
    configured = os.environ.get("POLISYOS_TEST_LEFTHOOK")
    binary = (
        Path(configured)
        if configured
        else PROJECT_ROOT / "apps/runtime-dashboard/node_modules/.bin/lefthook"
    )
    if not binary.exists():
        pytest.skip(
            "Install dashboard dependencies or set POLISYOS_TEST_LEFTHOOK for real hook tests"
        )
    env = {
        key: os.environ[key]
        for key in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT")
        if key in os.environ
    }
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "lefthook").symlink_to(binary.resolve())
    env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["POLISYOS_TEST_LEFTHOOK"] = str(binary.resolve())
    return env


def _seed(repo: Path, env: dict[str, str]) -> Path:
    repo.mkdir()
    _run("git", "init", "-b", "main", cwd=repo, env=env)
    _run("git", "config", "user.name", "Hook test", cwd=repo, env=env)
    _run("git", "config", "user.email", "hook-test@example.invalid", cwd=repo, env=env)
    (repo / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    for relative in (
        "apps/runtime-dashboard/package.json",
        "apps/runtime-dashboard/lefthook.yml",
        "tools/design/check-reduced-motion.ts",
        "tools/design/_a11yColor.ts",
        "tools/devx/install_repo_hooks.mjs",
    ):
        source = PROJECT_ROOT / relative
        if source.exists():
            target = repo / "policy-engine" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    _run("git", "add", ".", cwd=repo, env=env)
    _run("git", "commit", "-m", "fixture", cwd=repo, env=env)
    _provision_binary(repo, env)
    return repo


def _provision_binary(repo: Path, env: dict[str, str]) -> None:
    binary = repo / DASHBOARD / "node_modules/.bin/lefthook"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.symlink_to(env["POLISYOS_TEST_LEFTHOOK"])


def _prepare(repo: Path, env: dict[str, str]) -> None:
    manifest = json.loads((repo / DASHBOARD / "package.json").read_text(encoding="utf-8"))
    _run("sh", "-c", manifest["scripts"]["prepare"], cwd=repo / DASHBOARD, env=env)


def _hook_bytes(directory: Path) -> dict[str, bytes]:
    return {name: (directory / name).read_bytes() for name in HOOK_NAMES}


def test_shared_hook_contains_no_worktree_specific_path(
    tmp_path: Path, hook_env: dict[str, str]
) -> None:
    repo = _seed(tmp_path / "first station", hook_env)
    hooks = repo / ".git/hooks"
    _run("git", "config", "core.hooksPath", str(hooks), cwd=repo, env=hook_env)
    preserved = {"pre-commit.old": b"original hook\n", "post-checkout": b"#!/bin/sh\nexit 0\n"}
    for name, content in preserved.items():
        (hooks / name).write_bytes(content)
    preserved = {
        entry.name: entry.read_bytes()
        for entry in hooks.iterdir()
        if entry.is_file() and entry.name not in HOOK_NAMES
    }
    _prepare(repo, hook_env)
    expected = _hook_bytes(hooks)
    other = tmp_path / "second station"
    _run("git", "worktree", "add", "--detach", str(other), "HEAD", cwd=repo, env=hook_env)
    _provision_binary(other, hook_env)
    for station in (other, repo, other):
        # Dependency postinstall can force-regenerate first; prepare must restore stable bytes.
        native_env = {
            **hook_env,
            "LEFTHOOK_CONFIG": str(station / DASHBOARD / "lefthook.yml"),
        }
        _run(
            str(station / DASHBOARD / "node_modules/.bin/lefthook"),
            "install",
            "-f",
            cwd=station,
            env=native_env,
        )
        _prepare(station, {**hook_env, "CI": "true"})
        assert _hook_bytes(hooks) == expected
    for content in expected.values():
        assert str(tmp_path).encode() not in content
    for name, content in preserved.items():
        assert (hooks / name).read_bytes() == content


def test_real_commit_refuses_a_declared_reduced_motion_violation(
    tmp_path: Path, hook_env: dict[str, str]
) -> None:
    repo = _seed(tmp_path / "commit station", hook_env)
    _prepare(repo, hook_env)
    before = _hook_bytes(repo / ".git/hooks")
    other = tmp_path / "linked commit station"
    _run("git", "worktree", "add", "--detach", str(other), "HEAD", cwd=repo, env=hook_env)
    _provision_binary(other, hook_env)
    # Select the real declared command; unrelated frontend dependencies are outside this fixture.
    env = {**hook_env, "LEFTHOOK_EXCLUDE": "prettier,eslint,check-contrast"}
    for station in (repo, other):
        src = station / DASHBOARD / "src"
        provider = src / "app/providers/AppProviders.tsx"
        provider.parent.mkdir(parents=True)
        provider.write_text("// ReducedMotionProvider\n", encoding="utf-8")
        (src / "styles.css").write_text(
            "@media (prefers-reduced-motion: reduce) {}\n", encoding="utf-8"
        )
        motion = src / "violating-motion.tsx"
        motion.write_text(
            'import { animate } from "motion/react";\nanimate(".target", {});\n', encoding="utf-8"
        )
        _run("git", "add", ".", cwd=station, env=hook_env)
        result = _run("git", "commit", "-m", "must be refused", cwd=station, env=env, check=False)
        output = result.stdout + result.stderr
        assert result.returncode != 0, output
        assert "Imperative motion calls without reduced-motion guards" in output
        assert "violating-motion.tsx" in output
        assert "No config files" not in output
        assert (
            _run("git", "rev-list", "--count", "HEAD", cwd=station, env=hook_env).stdout.strip()
            == "1"
        )
        assert _hook_bytes(repo / ".git/hooks") == before
        motion.write_text(
            '// useReducedMotion\nimport { animate } from "motion/react";\nanimate(".target", {});\n',
            encoding="utf-8",
        )
        _run("git", "add", ".", cwd=station, env=hook_env)
        _run("git", "commit", "-m", "guarded motion", cwd=station, env=env)


@pytest.mark.parametrize("missing", ["binary", "config"])
def test_missing_hook_requirement_refuses_commit(
    tmp_path: Path, hook_env: dict[str, str], missing: str
) -> None:
    repo = _seed(tmp_path / missing, hook_env)
    _prepare(repo, hook_env)
    path = (
        repo / DASHBOARD / ("node_modules/.bin/lefthook" if missing == "binary" else "lefthook.yml")
    )
    path.unlink()
    result = _run(
        "git",
        "commit",
        "--allow-empty",
        "-m",
        "must be refused",
        cwd=repo,
        env=hook_env,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert f"PolicyOS hook: missing {missing}" in output
    assert "No config files" not in output


def test_commit_refuses_autofixes_that_are_absent_from_index(
    tmp_path: Path, hook_env: dict[str, str]
) -> None:
    """Refuse a real successful formatter when the accepted index would retain its findings."""
    modules = Path(
        os.environ.get(
            "POLISYOS_TEST_DASHBOARD_MODULES",
            str(PROJECT_ROOT / "apps/runtime-dashboard/node_modules"),
        )
    ).resolve()
    if not (modules / ".bin/prettier").exists():
        pytest.skip("Install dashboard dependencies or set POLISYOS_TEST_DASHBOARD_MODULES")
    repo = _seed(tmp_path / "autofix station", hook_env)
    local_modules = repo / DASHBOARD / "node_modules"
    (local_modules / ".bin/lefthook").unlink()
    (local_modules / ".bin").rmdir()
    local_modules.rmdir()
    local_modules.symlink_to(modules, target_is_directory=True)
    # A dependency symlink needs the same exclusion as the installed directory.
    (repo / ".git/info/exclude").write_text("node_modules\n", encoding="utf-8")
    _prepare(repo, hook_env)
    relative = (DASHBOARD / "formatting.json").as_posix()
    target = repo / relative
    unformatted = '{"a":1}'
    target.write_text(unformatted, encoding="utf-8")
    _run("git", "add", relative, cwd=repo, env=hook_env)
    head = _run("git", "rev-parse", "HEAD", cwd=repo, env=hook_env).stdout
    env = {**hook_env, "LEFTHOOK_EXCLUDE": "eslint,check-contrast,check-reduced-motion"}
    result = _run(
        "git", "commit", "-m", "must retain no formatter findings", cwd=repo, env=env, check=False
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "prettier" in output
    assert "No config files" not in output
    assert _run("git", "rev-parse", "HEAD", cwd=repo, env=hook_env).stdout == head
    assert _run("git", "show", ":" + relative, cwd=repo, env=hook_env).stdout == unformatted
    formatted = target.read_text(encoding="utf-8")
    assert formatted != unformatted
    _run("git", "add", relative, cwd=repo, env=hook_env)
    _run("git", "commit", "-m", "commit the checked formatted bytes", cwd=repo, env=env)
    assert _run("git", "show", "HEAD:" + relative, cwd=repo, env=hook_env).stdout == formatted


def test_existing_generated_hooks_receive_runtime_config_without_new_commands(
    tmp_path: Path, hook_env: dict[str, str]
) -> None:
    """Normalize stale generated entrypoints while preserving backups and user hooks."""
    repo = _seed(tmp_path / "stale-hook station", hook_env)
    config = repo / DASHBOARD / "lefthook.yml"
    original = config.read_text(encoding="utf-8")
    config.write_text(
        original + "\nprepare-commit-msg:\n  commands:\n    fixture:\n      run: exit 0\n",
        encoding="utf-8",
    )
    _run(
        str(repo / DASHBOARD / "node_modules/.bin/lefthook"),
        "install",
        "prepare-commit-msg",
        "-f",
        cwd=repo,
        env={**hook_env, "LEFTHOOK_CONFIG": str(config)},
    )
    config.write_text(original, encoding="utf-8")
    hooks = repo / ".git/hooks"
    native = (hooks / "prepare-commit-msg").read_bytes()
    assert b'call_lefthook run "prepare-commit-msg"' in native
    selected = {
        **hook_env,
        "LEFTHOOK_EXCLUDE": "prettier,eslint,check-contrast,check-reduced-motion",
    }
    before = _run(
        "git", "commit", "--allow-empty", "-m", "stale generated hook", cwd=repo, env=selected
    )
    assert "No config files" in before.stdout + before.stderr
    other = tmp_path / "linked stale-hook station"
    _run("git", "worktree", "add", "--detach", str(other), "HEAD", cwd=repo, env=hook_env)
    _provision_binary(other, hook_env)
    # Even recognizable generated bytes in backup/sample/temp files are not live hooks.
    generated_backup = b"#!/bin/sh\n# PolicyOS checkout-local Lefthook dispatcher.\nexit 0\n"
    for name in (
        "pre-commit.old",
        "prepare-commit-msg.old",
        "pre-push.sample",
        "pre-push.policyos-123",
    ):
        (hooks / name).write_bytes(generated_backup)
    user_hook = hooks / "commit-msg"
    user_hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    user_hook.chmod(0o755)
    managed = (*HOOK_NAMES, "prepare-commit-msg")
    preserved = {
        entry.name: entry.read_bytes()
        for entry in hooks.iterdir()
        if entry.is_file() and entry.name not in managed
    }
    expected: dict[str, bytes] | None = None
    for station in (repo, other, repo):
        _prepare(station, hook_env)
        current = {name: (hooks / name).read_bytes() for name in managed}
        if expected is None:
            expected = current
        assert current == expected
        result = _run(
            "git",
            "commit",
            "--allow-empty",
            "-m",
            "configured undeclared hook",
            cwd=station,
            env=selected,
        )
        assert "No config files" not in result.stdout + result.stderr
        for content in current.values():
            assert str(tmp_path).encode() not in content
        assert {name: (hooks / name).read_bytes() for name in managed} == expected
        assert {name: (hooks / name).read_bytes() for name in preserved} == preserved


@pytest.mark.parametrize("backup_exists", [False, True])
def test_primary_user_hook_with_lefthook_named_helper_is_preserved(
    tmp_path: Path, hook_env: dict[str, str], backup_exists: bool
) -> None:
    """Use generated ownership, not a helper name, before replacing a primary hook."""
    repo = _seed(tmp_path / "user-hook station", hook_env)
    primary = repo / ".git/hooks/pre-commit"
    backup = primary.with_name("pre-commit.old")
    user_bytes = (
        b"#!/bin/sh\n"
        b"call_lefthook() { printf 'user-authored helper\\n'; }\n"
        b"printf 'independent user hook\\n'\n"
    )
    primary.write_bytes(user_bytes)
    primary.chmod(0o755)
    old_bytes = b"#!/bin/sh\nprintf 'existing original hook\\n'\n"
    if backup_exists:
        backup.write_bytes(old_bytes)
    manifest = json.loads((repo / DASHBOARD / "package.json").read_text(encoding="utf-8"))
    result = _run(
        "sh", "-c", manifest["scripts"]["prepare"], cwd=repo / DASHBOARD, env=hook_env, check=False
    )
    if backup_exists:
        assert result.returncode != 0, result.stdout + result.stderr
        assert "Refusing to replace user hook" in result.stderr
        assert primary.read_bytes() == user_bytes
        assert backup.read_bytes() == old_bytes
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert backup.is_file(), "The installer must preserve the user hook before replacement."
        assert backup.read_bytes() == user_bytes
        assert primary.read_bytes() != user_bytes
