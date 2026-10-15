#!/usr/bin/env python3
"""Shared repo-hygiene contract for workspace lint and format commands."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from ._common import FRONTEND_WORKSPACES, GIT_ROOT, PRODUCT_ROOT, CommandSpec, uv_command

AUTHORED_PYTHON_FORMAT_SCOPE: tuple[str, ...] = (
    "src/polisyos",
    "tests",
    "tools",
    "architecture",
    "apps",
    "workers/dowhy-014",
    "dev-oracles/rdd-cct",
    "benchmarks",
    "schemas",
    "examples",
    "ops/cloud/gcp/upload_gonka_secrets.py",
    "jax_bootstrap.py",
    "migrate.py",
)
PHASE8_LIMITED_PYTHON_SCOPE: tuple[str, ...] = (
    "benchmarks",
    "tools/research/benchmarks",
    "tools/research/demos",
    "tools/research",
)
# Ruff treats a slashless exclusion as a match on any path component. Anchor each
# Phase 8 tree so nested src/polisyos/**/benchmarks and tests/**/benchmarks stay in
# the authored lint contract.
PHASE8_LIMITED_PYTHON_RUFF_EXCLUDES: tuple[str, ...] = tuple(
    f"{path}/**" for path in PHASE8_LIMITED_PYTHON_SCOPE
)
AUTHORED_PYTHON_LINT_SCOPE: tuple[str, ...] = tuple(
    path for path in AUTHORED_PYTHON_FORMAT_SCOPE if path not in PHASE8_LIMITED_PYTHON_SCOPE
)
AUTHORED_PYTHON_SCOPE = AUTHORED_PYTHON_FORMAT_SCOPE
# Current evidence-producing/verification scripts live in handoff and plan roots.
# Keep them in a dedicated check so archived snapshots are not treated as source.
EVIDENCE_PYTHON_SCOPE: tuple[str, ...] = (
    "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL",
    "docs/research/e02-cloud-test-plan/closure-decisions",
    "docs/research/e02-cloud-test-plan/execution-organization",
    "docs/research/e02-cloud-test-plan/execution-prompts/unified-local-2026-10-09",
    "docs/research/e02-cloud-test-plan/full-run",
    "docs/research/e02-cloud-test-plan/results",
    "docs/research/e02-cloud-test-plan/verification/F/api-20261006",
    "docs/plans/active/agent-packages",
    "docs/research/policy-operations",
    "docs/superpowers/research",
)
# The Q2 raw subtree is an active, tracked producer/consumer fixture set used by
# the archive, wheel, sdist, and installed-origin gates. Other ignored raw
# snapshots remain outside the evidence route.
ACTIVE_IGNORED_EVIDENCE_PYTHON_SCOPE: tuple[str, ...] = (
    "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw",
)
MYPY_CONFIG = "architecture/tooling/mypy/generated.ini"
PYTHON_BASE_LAYERS: tuple[tuple[str, str, str], ...] = (
    ("common", "src/polisyos/common", "tests/unit/common"),
    ("ir", "src/polisyos/ir", "tests/unit/ir"),
    ("core", "src/polisyos/core", "tests/unit/core"),
)
BENCHMARK_RESEARCH_SCOPE: tuple[str, ...] = PHASE8_LIMITED_PYTHON_SCOPE
REGO_SCOPE: tuple[str, ...] = (
    "ops/policy/policies",
    "ops/cloud/helm/polisyos-cell/policies",
)
HELM_CHART_DIRS: tuple[str, ...] = tuple(
    sorted(
        chart_file.parent.relative_to(PRODUCT_ROOT).as_posix()
        for chart_file in (PRODUCT_ROOT / "ops" / "cloud" / "helm").glob("*/Chart.yaml")
    )
)
_SKIP_SEGMENTS = {
    ".venv",
    ".venv_codex",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
    "_build",
    "_cache",
    "node_modules",
    "__pycache__",
    "coverage",
    "dist",
    "site",
    "storybook-static",
}
_DEFAULT_MARKDOWN_EXCLUDES = ("docs/archive/",)
_WORKSPACE_PREFIX = (
    PRODUCT_ROOT.resolve().relative_to(GIT_ROOT.resolve()).as_posix()
    if PRODUCT_ROOT.resolve() != GIT_ROOT.resolve()
    else ""
)


def _workspace_relative(raw_path: str) -> str:
    relative = Path(raw_path).as_posix()
    if not _WORKSPACE_PREFIX:
        return relative
    return f"{_WORKSPACE_PREFIX}/{relative}"


def _resolve_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = PRODUCT_ROOT / path
    return path.resolve()


def _relative_path(path: Path) -> Path:
    return path.resolve().relative_to(PRODUCT_ROOT)


def _is_skipped(path: Path, *, exclude_prefixes: tuple[str, ...]) -> bool:
    relative = _relative_path(path).as_posix()
    if any(part in _SKIP_SEGMENTS for part in path.parts):
        return True
    return any(relative.startswith(prefix) for prefix in exclude_prefixes)


def expand_files(
    raw_paths: list[str] | tuple[str, ...],
    *,
    suffixes: tuple[str, ...],
    exclude_prefixes: tuple[str, ...] = (),
) -> list[str]:
    """Expand files/directories into repo-relative file paths for targeted runs."""

    resolved: list[str] = []
    seen: set[str] = set()
    for raw_path in raw_paths:
        candidate = _resolve_path(raw_path)
        if not candidate.exists():
            raise SystemExit(f"Path does not exist: {raw_path}")

        matches: list[Path]
        if candidate.is_file():
            matches = [candidate] if candidate.suffix in suffixes else []
        else:
            matches = [
                file_path
                for file_path in candidate.rglob("*")
                if file_path.is_file() and file_path.suffix in suffixes
            ]

        for match in sorted(matches):
            if _is_skipped(match, exclude_prefixes=exclude_prefixes):
                continue
            relative = _relative_path(match).as_posix()
            if relative in seen:
                continue
            seen.add(relative)
            resolved.append(relative)
    return resolved


def _is_under_scope(path: str, roots: tuple[str, ...]) -> bool:
    """Return whether a product-relative path belongs to a declared role root."""

    return any(path == root or path.startswith(f"{root.rstrip('/')}/") for root in roots)


def current_python_files(
    raw_paths: tuple[str, ...],
    *,
    exclude_roots: tuple[str, ...] = (),
    include_ignored_roots: tuple[str, ...] = (),
    include_untracked: bool = True,
) -> list[str]:
    """Select index and optionally nonignored Python files from declared role roots.

    Tracked ignored files are admitted only under an explicitly active role root.
    Paths are returned explicitly so Ruff's directory-level exclusions cannot
    turn a nonempty role into an empty successful run.
    """

    roots = tuple(Path(raw_path).as_posix().rstrip("/") for raw_path in raw_paths)
    exclusions = tuple(Path(raw_path).as_posix().rstrip("/") for raw_path in exclude_roots)
    ignored_roots = tuple(
        Path(raw_path).as_posix().rstrip("/") for raw_path in include_ignored_roots
    )
    if not roots:
        raise SystemExit("No Python role roots are declared.")
    for raw_path in (*roots, *exclusions, *ignored_roots):
        candidate = _resolve_path(raw_path)
        if not candidate.exists():
            raise SystemExit(f"Python role path does not exist: {raw_path}")
    if any(not _is_under_scope(root, roots) for root in ignored_roots):
        raise SystemExit("Ignored Python role roots must be nested under a selected role root.")

    git_roots = tuple(_workspace_relative(root) for root in roots)
    git_args = ["git", "ls-files", "--cached"]
    if include_untracked:
        git_args.extend(("--others", "--exclude-standard"))
    git_args.extend(("-z", "--", *git_roots))
    completed = subprocess.run(
        git_args,
        cwd=GIT_ROOT,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = os.fsdecode(completed.stderr).strip()
        raise SystemExit(f"Could not enumerate current Python role paths: {detail}")

    candidates: set[str] = set()
    for raw_path in completed.stdout.split(b"\0"):
        if not raw_path:
            continue
        workspace_path = Path(os.fsdecode(raw_path)).as_posix()
        if _WORKSPACE_PREFIX:
            prefix = f"{_WORKSPACE_PREFIX}/"
            if not workspace_path.startswith(prefix):
                continue
            relative = workspace_path.removeprefix(prefix)
        else:
            relative = workspace_path
        if not relative.endswith((".py", ".pyi")):
            continue
        if not _is_under_scope(relative, roots) or _is_under_scope(relative, exclusions):
            continue
        if any(part in _SKIP_SEGMENTS for part in Path(relative).parts):
            continue
        if (GIT_ROOT / workspace_path).is_file():
            candidates.add(relative)

    if not candidates:
        raise SystemExit(f"No current Python files found under declared roles: {roots}")

    workspace_candidates = tuple(_workspace_relative(relative) for relative in sorted(candidates))
    ignored_result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-z", "--stdin"],
        cwd=GIT_ROOT,
        input=b"\0".join(os.fsencode(path) for path in workspace_candidates) + b"\0",
        check=False,
        capture_output=True,
    )
    if ignored_result.returncode not in (0, 1):
        detail = os.fsdecode(ignored_result.stderr).strip()
        raise SystemExit(f"Could not classify ignored Python role paths: {detail}")
    ignored = {
        Path(os.fsdecode(raw_path)).as_posix().removeprefix(f"{_WORKSPACE_PREFIX}/")
        if _WORKSPACE_PREFIX
        else Path(os.fsdecode(raw_path)).as_posix()
        for raw_path in ignored_result.stdout.split(b"\0")
        if raw_path
    }
    selected = sorted(
        path for path in candidates if path not in ignored or _is_under_scope(path, ignored_roots)
    )
    if not selected:
        raise SystemExit(f"No active current Python files found under declared roles: {roots}")
    return selected


def evidence_python_files() -> list[str]:
    """Return the complete current Python evidence role, including active Q2 sources."""

    return current_python_files(
        EVIDENCE_PYTHON_SCOPE,
        include_ignored_roots=ACTIVE_IGNORED_EVIDENCE_PYTHON_SCOPE,
        include_untracked=False,
    )


def expand_markdown_files(raw_paths: list[str] | tuple[str, ...]) -> list[str]:
    """Expand targeted markdown paths while keeping archive docs out of scope."""

    return expand_files(
        raw_paths,
        suffixes=(".md",),
        exclude_prefixes=_DEFAULT_MARKDOWN_EXCLUDES,
    )


def ensure_executable(binary: str, *, reason: str, skip_hint: str | None = None) -> None:
    """Fail with a friendly message when an optional external tool is missing."""

    if shutil.which(binary) is not None:
        return
    suffix = f" Re-run with {skip_hint} to skip this surface." if skip_hint else ""
    raise SystemExit(f"`{binary}` is required to {reason}.{suffix}")


def uv_run(label: str, *args: str, cwd: Path = PRODUCT_ROOT) -> CommandSpec:
    """Return a CommandSpec that runs inside the workspace uv environment."""

    uv = uv_command()
    return CommandSpec(label=label, argv=(*uv, "run", *args), cwd=cwd)


def npm_run(label: str, *args: str, workspace: Path | None = None) -> CommandSpec:
    """Return a CommandSpec for a frontend pnpm script."""

    cwd = FRONTEND_WORKSPACES[0] if workspace is None else workspace
    workspace_label = cwd.relative_to(PRODUCT_ROOT).as_posix()
    return CommandSpec(
        label=f"{label} [{workspace_label}]",
        argv=("corepack", "pnpm", "run", *args),
        cwd=cwd,
    )


def frontend_npm_runs(script: str, *, label: str) -> list[CommandSpec]:
    """Return one pnpm command per frontend workspace."""

    return [npm_run(label, script, workspace=workspace) for workspace in FRONTEND_WORKSPACES]


def pre_commit_hook(
    hook_id: str,
    *,
    label: str,
    files: list[str] | None = None,
) -> CommandSpec:
    """Run one configured pre-commit hook either on specific files or all files."""

    uv = uv_command()
    argv = [
        *uv,
        "run",
        "pre-commit",
        "run",
        "--config",
        _workspace_relative(".pre-commit-config.yaml"),
        hook_id,
    ]
    if files:
        argv.extend(["--files", *(_workspace_relative(file_path) for file_path in files)])
    else:
        argv.append("--all-files")
    return CommandSpec(label=label, argv=tuple(argv), cwd=GIT_ROOT)


def pre_commit_install(*, label: str = "pre-commit install") -> CommandSpec:
    """Install hooks for the workspace-local pre-commit configuration."""

    uv = uv_command()
    return CommandSpec(
        label=label,
        argv=(
            *uv,
            "run",
            "pre-commit",
            "install",
            "--config",
            _workspace_relative(".pre-commit-config.yaml"),
        ),
        cwd=GIT_ROOT,
    )


def helm_lint_command(chart_path: str) -> CommandSpec:
    """Return a CommandSpec for `helm lint` against one chart directory."""

    values_file = PRODUCT_ROOT / chart_path / "values.lint.yaml"
    argv = ["helm", "lint", chart_path]
    if values_file.exists():
        argv.extend(["-f", f"{chart_path}/values.lint.yaml"])
    return CommandSpec(
        label=f"helm lint {chart_path}",
        argv=tuple(argv),
        cwd=PRODUCT_ROOT,
    )


def workspace_command(command: str, *, label: str, args: tuple[str, ...] = ()) -> CommandSpec:
    """Invoke another canonical workspace command through the compatibility shim."""

    module_path = f"tools/devx/workspace/{command.replace('-', '_')}.py"
    return CommandSpec(
        label=label,
        argv=(sys.executable, module_path, *args),
        cwd=PRODUCT_ROOT,
    )
