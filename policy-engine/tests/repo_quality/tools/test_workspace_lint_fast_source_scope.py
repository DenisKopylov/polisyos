from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from tools.devx.workspace import _repo_hygiene, lint_fast

if TYPE_CHECKING:
    from tools.devx.workspace._common import CommandSpec


def _ruff_show_files(ruff_args: tuple[str, ...], *, cwd: Path) -> set[str]:
    """Resolve Ruff's actual file set without running lint rules or writing cache."""

    assert ruff_args
    assert ruff_args[0] == "check"
    args = list(ruff_args)
    args[1:1] = ["--show-files", "--no-cache"]
    completed = subprocess.run(
        [sys.executable, "-m", "ruff", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)
    product_root = _repo_hygiene.PRODUCT_ROOT.resolve()
    return {
        Path(raw_path).resolve().relative_to(product_root).as_posix()
        for raw_path in completed.stdout.splitlines()
        if raw_path
    }


def _ruff_args(spec: CommandSpec) -> tuple[str, ...]:
    ruff_index = spec.argv.index("ruff")
    return spec.argv[ruff_index + 1 :]


def _tracked_python_paths(paths: tuple[str, ...]) -> set[str]:
    """Enumerate tracked and new authored Python files under the supplied roots."""

    product_root = _repo_hygiene.PRODUCT_ROOT.resolve()
    git_root = _repo_hygiene.GIT_ROOT.resolve()
    product_prefix = product_root.relative_to(git_root).as_posix()
    git_paths = tuple(
        f"{product_prefix}/{path}" if product_prefix != "." else path for path in paths
    )
    completed = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            *git_paths,
        ],
        cwd=git_root,
        check=True,
        capture_output=True,
    )
    result: set[str] = set()
    for raw_path in completed.stdout.split(b"\0"):
        if not raw_path:
            continue
        path = raw_path.decode("utf-8")
        relative = path.removeprefix(f"{product_prefix}/") if product_prefix != "." else path
        if relative.endswith((".py", ".pyi")):
            result.add(relative)
    return result


def _is_under_any(path: str, roots: tuple[str, ...]) -> bool:
    return any(path == root or path.startswith(f"{root}/") for root in roots)


def test_lint_fast_ruff_scope_covers_authored_files_and_rejects_basename_escape() -> None:
    full_authored = _ruff_show_files(
        ("check", *_repo_hygiene.AUTHORED_PYTHON_FORMAT_SCOPE),
        cwd=_repo_hygiene.PRODUCT_ROOT,
    )
    phase8 = _ruff_show_files(
        (
            "check",
            "--select",
            "E,F,I,UP",
            "--ignore",
            "E402,E501",
            *_repo_hygiene.BENCHMARK_RESEARCH_SCOPE,
        ),
        cwd=_repo_hygiene.PRODUCT_ROOT,
    )
    native_spec = lint_fast._authored_python_ruff_check()
    native = _ruff_show_files(_ruff_args(native_spec), cwd=native_spec.cwd)
    expected_native = full_authored - phase8

    assert phase8 <= full_authored
    assert native == expected_native
    assert native.isdisjoint(phase8)
    assert native | phase8 == full_authored

    source_and_test_python = _tracked_python_paths(("src/polisyos", "tests"))
    actual_source_and_test = {
        path for path in native | phase8 if path.startswith(("src/polisyos/", "tests/"))
    }
    assert actual_source_and_test == source_and_test_python
    assert {
        path
        for path in source_and_test_python
        if not _is_under_any(path, _repo_hygiene.PHASE8_LIMITED_PYTHON_SCOPE)
    } <= native

    legacy_excludes = tuple(
        argument
        for path in _repo_hygiene.PHASE8_LIMITED_PYTHON_SCOPE
        for argument in ("--extend-exclude", path)
    )
    legacy_native = _ruff_show_files(
        ("check", *legacy_excludes, *_repo_hygiene.AUTHORED_PYTHON_LINT_SCOPE),
        cwd=_repo_hygiene.PRODUCT_ROOT,
    )
    nested_benchmarks_outside_phase8 = {
        path
        for path in full_authored
        if "benchmarks" in Path(path).parts
        and not _is_under_any(path, _repo_hygiene.PHASE8_LIMITED_PYTHON_SCOPE)
    }
    assert nested_benchmarks_outside_phase8
    assert expected_native - legacy_native == nested_benchmarks_outside_phase8

    # Keep the declared Phase 8 scope intact, but remove one root from the
    # runtime command to prove that its actual exclusion changes Ruff's file set.
    research_root = "tools/research"
    research_root_pattern = f"{research_root}/**"
    assert research_root in _repo_hygiene.PHASE8_LIMITED_PYTHON_SCOPE
    assert research_root_pattern in _repo_hygiene.PHASE8_LIMITED_PYTHON_RUFF_EXCLUDES
    research_children = tuple(
        path
        for path in _repo_hygiene.PHASE8_LIMITED_PYTHON_SCOPE
        if path.startswith(f"{research_root}/")
    )
    research_root_only = {
        path
        for path in phase8
        if _is_under_any(path, (research_root,)) and not _is_under_any(path, research_children)
    }
    assert research_root_only
    without_research_root_excludes = tuple(
        argument
        for pattern in _repo_hygiene.PHASE8_LIMITED_PYTHON_RUFF_EXCLUDES
        if pattern != research_root_pattern
        for argument in ("--extend-exclude", pattern)
    )
    without_research_root = _ruff_show_files(
        ("check", *without_research_root_excludes, *_repo_hygiene.AUTHORED_PYTHON_LINT_SCOPE),
        cwd=_repo_hygiene.PRODUCT_ROOT,
    )
    assert research_root_only.isdisjoint(native)
    assert research_root_only <= without_research_root
    assert without_research_root - expected_native == research_root_only
    assert nested_benchmarks_outside_phase8.isdisjoint(native)
