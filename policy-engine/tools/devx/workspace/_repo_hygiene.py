#!/usr/bin/env python3
"""Shared repo-hygiene contract for workspace lint and format commands."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from ._common import FRONTEND_WORKSPACES, GIT_ROOT, PRODUCT_ROOT, CommandSpec, uv_command

AUTHORED_PYTHON_FORMAT_SCOPE: tuple[str, ...] = (
    "src/polisyos",
    "tests",
    "tools",
    "benchmarks",
    "schemas",
    "scripts",
    "examples",
    "gcp/upload_gonka_secrets.py",
    "jax_bootstrap.py",
    "migrate.py",
)
PHASE8_LIMITED_PYTHON_SCOPE: tuple[str, ...] = (
    "benchmarks",
    "tools/benchmarks",
    "tools/demos",
    "tools/research",
)
AUTHORED_PYTHON_LINT_SCOPE: tuple[str, ...] = tuple(
    path for path in AUTHORED_PYTHON_FORMAT_SCOPE if path not in PHASE8_LIMITED_PYTHON_SCOPE
)
AUTHORED_PYTHON_SCOPE = AUTHORED_PYTHON_FORMAT_SCOPE
PYTHON_BASE_LAYERS: tuple[tuple[str, str, str], ...] = (
    ("common", "src/polisyos/common", "tests/common"),
    ("ir", "src/polisyos/ir", "tests/ir"),
    ("core", "src/polisyos/core", "tests/core"),
)
BENCHMARK_RESEARCH_SCOPE: tuple[str, ...] = (
    "benchmarks",
    "tools/benchmarks",
    "tools/demos",
    "tools/research",
)
REGO_SCOPE: tuple[str, ...] = (
    "ops/opa/policies",
    "ops/helm/polisyos-cell/policies",
)
HELM_CHART_DIRS: tuple[str, ...] = tuple(
    sorted(
        chart_file.parent.relative_to(PRODUCT_ROOT).as_posix()
        for chart_file in (PRODUCT_ROOT / "ops" / "helm").glob("*/Chart.yaml")
    )
)
_SKIP_SEGMENTS = {
    ".venv",
    ".venv_codex",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
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
    """Return a CommandSpec for a frontend npm script."""

    cwd = FRONTEND_WORKSPACES[0] if workspace is None else workspace
    workspace_label = cwd.relative_to(PRODUCT_ROOT).as_posix()
    return CommandSpec(label=f"{label} [{workspace_label}]", argv=("npm", "run", *args), cwd=cwd)


def frontend_npm_runs(script: str, *, label: str) -> list[CommandSpec]:
    """Return one npm command per frontend workspace."""

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

    module_path = f"tools/workspace/{command.replace('-', '_')}.py"
    return CommandSpec(
        label=label,
        argv=(sys.executable, module_path, *args),
        cwd=PRODUCT_ROOT,
    )
