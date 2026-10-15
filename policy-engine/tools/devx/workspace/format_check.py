#!/usr/bin/env python3
"""Run repository-wide formatter checks for authored surfaces."""

from __future__ import annotations

import argparse

from ._common import CommandSpec, run_command
from ._repo_hygiene import (
    AUTHORED_PYTHON_FORMAT_SCOPE,
    REGO_SCOPE,
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
            "Check authored Python, frontend, shell, TOML, and Rego formatting "
            "without rewriting files."
        )
    )
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="Skip frontend Prettier checks.",
    )
    parser.add_argument(
        "--skip-rego",
        action="store_true",
        help="Skip Rego formatting checks.",
    )
    return parser


def _authored_python_ruff_format_check() -> CommandSpec:
    """Build the formatter check from the complete authored Python role union."""

    python_files = current_python_files(AUTHORED_PYTHON_FORMAT_SCOPE)
    return uv_run("ruff format --check", "ruff", "format", "--check", *python_files)


def _evidence_python_ruff_format_check() -> CommandSpec:
    """Build the formatter check for the complete indexed E02 evidence role."""

    python_files = evidence_python_files()
    return uv_run(
        "ruff format --check current E02 evidence Python role",
        "ruff",
        "format",
        "--check",
        *python_files,
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    commands = [
        _authored_python_ruff_format_check(),
        _evidence_python_ruff_format_check(),
        pre_commit_hook("shfmt", label="shfmt authored shell"),
        pre_commit_hook("taplo-format", label="taplo format check"),
    ]

    if not args.skip_frontend:
        ensure_executable(
            "npm",
            reason="run frontend format checks",
            skip_hint="--skip-frontend",
        )
        commands[1:1] = frontend_npm_runs("format:check", label="npm format:check")

    if not args.skip_rego:
        ensure_executable(
            "opa",
            reason="check Rego formatting",
            skip_hint="--skip-rego",
        )
        commands.append(
            uv_run(
                "opa fmt --fail",
                "opa",
                "fmt",
                "--fail",
                "--list",
                *REGO_SCOPE,
            )
        )

    for command in commands:
        run_command(command)

    print("[format-check] authored formatter checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
