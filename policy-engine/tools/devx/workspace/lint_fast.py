#!/usr/bin/env python3
"""Run the fast repository-wide lint contract for authored files."""

from __future__ import annotations

import argparse

from ._common import CommandSpec, run_command
from ._repo_hygiene import (
    AUTHORED_PYTHON_LINT_SCOPE,
    PHASE8_LIMITED_PYTHON_SCOPE,
    current_python_files,
    ensure_executable,
    evidence_python_files,
    frontend_npm_runs,
    pre_commit_hook,
    uv_run,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the fast authored-file lint surface: Python Ruff, markdownlint, "
            "yamllint, shellcheck, actionlint, and optional frontend ESLint."
        )
    )
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="Skip frontend ESLint.",
    )
    parser.add_argument(
        "--skip-docs",
        action="store_true",
        help="Skip markdownlint on docs and README surfaces.",
    )
    return parser


def _authored_python_ruff_check() -> CommandSpec:
    """Build the strict authored-Python Ruff check from current source files."""

    python_files = current_python_files(
        AUTHORED_PYTHON_LINT_SCOPE,
        exclude_roots=PHASE8_LIMITED_PYTHON_SCOPE,
    )
    return uv_run("ruff check", "ruff", "check", *python_files)


def _evidence_python_ruff_check() -> CommandSpec:
    """Build the Ruff check for the complete indexed E02 evidence role."""

    python_files = evidence_python_files()
    return uv_run("ruff check current E02 evidence Python role", "ruff", "check", *python_files)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    commands = [
        _authored_python_ruff_check(),
        _evidence_python_ruff_check(),
        pre_commit_hook("yamllint", label="yamllint authored YAML"),
        pre_commit_hook("shellcheck", label="shellcheck authored shell"),
        pre_commit_hook("actionlint", label="actionlint workflows"),
    ]

    if not args.skip_docs:
        commands.insert(
            1,
            pre_commit_hook("markdownlint-cli2", label="markdownlint authored docs"),
        )

    if not args.skip_frontend:
        ensure_executable("corepack", reason="run frontend ESLint", skip_hint="--skip-frontend")
        commands[1:1] = frontend_npm_runs("lint", label="pnpm lint")

    for command in commands:
        run_command(command)

    print("[lint-fast] authored lint checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
