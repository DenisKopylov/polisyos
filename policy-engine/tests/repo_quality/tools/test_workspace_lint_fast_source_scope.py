from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from tools.devx.workspace import _repo_hygiene, benchmark_surfaces, format_check, lint_fast

if TYPE_CHECKING:
    from tools.devx.workspace._common import CommandSpec


def _ruff_show_files(ruff_args: tuple[str, ...], *, cwd: Path) -> set[str]:
    """Resolve Ruff's actual file set without running rules or writing a cache."""

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


def _git_python_paths(roots: tuple[str, ...], *, include_untracked: bool = True) -> set[str]:
    """Build the independent current-file denominator from Git's index/worktree."""

    product_root = _repo_hygiene.PRODUCT_ROOT.resolve()
    git_root = _repo_hygiene.GIT_ROOT.resolve()
    product_prefix = product_root.relative_to(git_root).as_posix()
    git_roots = tuple(
        f"{product_prefix}/{root}" if product_prefix != "." else root for root in roots
    )
    git_args = ["git", "ls-files", "--cached"]
    if include_untracked:
        git_args.extend(("--others", "--exclude-standard"))
    completed = subprocess.run(
        [*git_args, "-z", "--", *git_roots],
        cwd=git_root,
        check=True,
        capture_output=True,
    )
    result: set[str] = set()
    for raw_path in completed.stdout.split(b"\0"):
        if not raw_path:
            continue
        workspace_path = Path(raw_path.decode("utf-8")).as_posix()
        relative = (
            workspace_path.removeprefix(f"{product_prefix}/")
            if product_prefix != "."
            else workspace_path
        )
        if relative.endswith((".py", ".pyi")) and (product_root / relative).is_file():
            result.add(relative)
    return result


def _ignored_python_paths(paths: set[str]) -> set[str]:
    """Return only Git-ignored paths among an already-bounded Python set."""

    product_root = _repo_hygiene.PRODUCT_ROOT.resolve()
    git_root = _repo_hygiene.GIT_ROOT.resolve()
    product_prefix = product_root.relative_to(git_root).as_posix()
    workspace_paths = tuple(
        f"{product_prefix}/{path}" if product_prefix != "." else path for path in sorted(paths)
    )
    completed = subprocess.run(
        ["git", "check-ignore", "--no-index", "-z", "--stdin"],
        cwd=git_root,
        input=b"\0".join(path.encode("utf-8") for path in workspace_paths) + b"\0",
        check=False,
        capture_output=True,
    )
    assert completed.returncode in (0, 1), completed.stderr.decode("utf-8", errors="replace")
    result: set[str] = set()
    for raw_path in completed.stdout.split(b"\0"):
        if not raw_path:
            continue
        workspace_path = Path(raw_path.decode("utf-8")).as_posix()
        relative = (
            workspace_path.removeprefix(f"{product_prefix}/")
            if product_prefix != "."
            else workspace_path
        )
        result.add(relative)
    return result


def _under_any(path: str, roots: tuple[str, ...]) -> bool:
    return any(path == root or path.startswith(f"{root.rstrip('/')}/") for root in roots)


def _current_python_paths(
    roots: tuple[str, ...],
    *,
    exclude_roots: tuple[str, ...] = (),
    include_ignored_roots: tuple[str, ...] = (),
    include_untracked: bool = True,
) -> set[str]:
    candidates = _git_python_paths(roots, include_untracked=include_untracked)
    ignored = _ignored_python_paths(candidates)
    active_ignored = {
        path for path in candidates if path in ignored and _under_any(path, include_ignored_roots)
    }
    return {
        path
        for path in candidates
        if not _under_any(path, exclude_roots) and (path not in ignored or path in active_ignored)
    }


def _file_arguments(args: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(argument for argument in args if argument.endswith((".py", ".pyi")))


def test_runtime_ruff_routes_select_current_typed_sources_and_reject_removal() -> None:
    authored = _current_python_paths(_repo_hygiene.AUTHORED_PYTHON_FORMAT_SCOPE)
    phase8_roots = _repo_hygiene.PHASE8_LIMITED_PYTHON_SCOPE
    phase8 = _current_python_paths(phase8_roots)
    strict = _current_python_paths(
        _repo_hygiene.AUTHORED_PYTHON_LINT_SCOPE,
        exclude_roots=phase8_roots,
    )
    evidence = _current_python_paths(
        _repo_hygiene.EVIDENCE_PYTHON_SCOPE,
        include_ignored_roots=_repo_hygiene.ACTIVE_IGNORED_EVIDENCE_PYTHON_SCOPE,
        include_untracked=False,
    )
    q2_role = _current_python_paths(
        _repo_hygiene.ACTIVE_IGNORED_EVIDENCE_PYTHON_SCOPE,
        include_ignored_roots=_repo_hygiene.ACTIVE_IGNORED_EVIDENCE_PYTHON_SCOPE,
        include_untracked=False,
    )
    evidence_candidates = _git_python_paths(
        _repo_hygiene.EVIDENCE_PYTHON_SCOPE, include_untracked=False
    )
    ignored_evidence = _ignored_python_paths(evidence_candidates)
    expected_evidence = (evidence_candidates - ignored_evidence) | (q2_role & ignored_evidence)

    assert strict.isdisjoint(phase8)
    assert strict.isdisjoint(evidence)
    assert phase8.isdisjoint(evidence)
    assert strict | phase8 == authored
    assert authored.isdisjoint(evidence)
    assert strict | phase8 | evidence == authored | evidence
    assert evidence == expected_evidence
    assert evidence & ignored_evidence == q2_role & ignored_evidence
    assert (
        "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/q2-freeze-input-audit-v2-20261011.py"
        in evidence
    )
    assert q2_role

    authored_spec = lint_fast._authored_python_ruff_check()
    phase8_spec = benchmark_surfaces._phase8_ruff_check()
    evidence_spec = lint_fast._evidence_python_ruff_check()
    authored_args = _ruff_args(authored_spec)
    phase8_args = _ruff_args(phase8_spec)
    evidence_args = _ruff_args(evidence_spec)

    assert authored_args == ("check", *sorted(strict))
    assert phase8_args == (
        "check",
        "--select",
        "E,F,I,UP",
        "--ignore",
        "E402,E501",
        *sorted(phase8),
    )
    assert evidence_args == ("check", *sorted(evidence))
    assert _ruff_show_files(authored_args, cwd=authored_spec.cwd) == strict
    assert _ruff_show_files(phase8_args, cwd=phase8_spec.cwd) == phase8
    assert _ruff_show_files(evidence_args, cwd=evidence_spec.cwd) == evidence
    assert all(path.endswith((".py", ".pyi")) for path in strict | phase8 | evidence)
    assert not any(path.endswith(".toml") for path in strict | phase8 | evidence)

    authored_format_args = _ruff_args(format_check._authored_python_ruff_format_check())
    evidence_format_args = _ruff_args(format_check._evidence_python_ruff_format_check())
    phase8_format_args = _ruff_args(benchmark_surfaces._phase8_ruff_format_check())
    assert _file_arguments(authored_format_args) == tuple(sorted(authored))
    assert _file_arguments(evidence_format_args) == tuple(sorted(evidence))
    assert _file_arguments(phase8_format_args) == tuple(sorted(phase8))

    architecture = {path for path in strict if path.startswith("architecture/")}
    assert architecture
    without_architecture = tuple(path for path in authored_args if path not in architecture)
    selected_without_architecture = _ruff_show_files(
        without_architecture,
        cwd=authored_spec.cwd,
    )
    assert strict - selected_without_architecture == architecture

    research_root = "tools/research"
    research_files = {path for path in phase8 if _under_any(path, (research_root,))}
    assert research_files
    phase8_without_research = tuple(path for path in phase8_args if path not in research_files)
    selected_without_research = _ruff_show_files(
        phase8_without_research,
        cwd=phase8_spec.cwd,
    )
    assert phase8 - selected_without_research == research_files

    results_root = "docs/research/e02-cloud-test-plan/results"
    evidence_without_results = _current_python_paths(
        tuple(root for root in _repo_hygiene.EVIDENCE_PYTHON_SCOPE if root != results_root),
        include_ignored_roots=_repo_hygiene.ACTIVE_IGNORED_EVIDENCE_PYTHON_SCOPE,
        include_untracked=False,
    )
    result_files = {path for path in evidence if _under_any(path, (results_root,))}
    evidence_without_results_spec = (
        "check",
        *sorted(evidence_without_results),
    )
    selected_without_results = _ruff_show_files(
        evidence_without_results_spec,
        cwd=evidence_spec.cwd,
    )
    assert result_files
    assert evidence - selected_without_results == result_files

    try:
        _repo_hygiene.current_python_files(("docs/reference",))
    except SystemExit:
        pass
    else:
        raise AssertionError(
            "An empty Python route must fail closed, never report a green Ruff run."
        )
