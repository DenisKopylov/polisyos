#!/usr/bin/env python3
"""Run the full authored lint contract used by CI and nightly sweeps."""

from __future__ import annotations

import argparse

from ._common import run_command
from ._repo_hygiene import (
    HELM_CHART_DIRS,
    REGO_SCOPE,
    ensure_executable,
    frontend_npm_runs,
    helm_lint_command,
    uv_run,
    workspace_command,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full authored lint surface: fast lint, format checks, "
            "curated type-checking, frontend typecheck, Helm chart lint, "
            "and Rego strict/test gates."
        )
    )
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="Skip frontend lint, format, and typecheck.",
    )
    parser.add_argument(
        "--skip-docs",
        action="store_true",
        help="Skip markdownlint in the fast lint pass.",
    )
    parser.add_argument(
        "--skip-policy",
        action="store_true",
        help="Skip Rego formatting/check/test passes.",
    )
    parser.add_argument(
        "--skip-helm",
        action="store_true",
        help="Skip Helm chart lint.",
    )
    parser.add_argument(
        "--skip-types",
        action="store_true",
        help="Skip curated Python and frontend type checks.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    lint_fast_args: list[str] = []
    if args.skip_frontend:
        lint_fast_args.append("--skip-frontend")
    if args.skip_docs:
        lint_fast_args.append("--skip-docs")

    format_check_args: list[str] = []
    if args.skip_frontend:
        format_check_args.append("--skip-frontend")
    if args.skip_policy:
        format_check_args.append("--skip-rego")

    commands = [
        workspace_command(
            "lint-fast",
            label="workspace lint-fast",
            args=tuple(lint_fast_args),
        ),
        workspace_command(
            "format-check",
            label="workspace format-check",
            args=tuple(format_check_args),
        ),
    ]

    if not args.skip_types:
        commands.extend(
            [
                workspace_command(
                    "python-base-mypy",
                    label="workspace python-base-mypy",
                ),
                workspace_command(
                    "python-base-basedpyright",
                    label="workspace python-base-basedpyright",
                ),
            ]
        )
        if not args.skip_frontend:
            ensure_executable(
                "corepack",
                reason="run frontend typecheck",
                skip_hint="--skip-frontend",
            )
            commands.extend(frontend_npm_runs("typecheck", label="pnpm typecheck"))
            commands.extend(
                frontend_npm_runs(
                    "check:architecture",
                    label="pnpm check:architecture",
                )
            )

    runtime_args: tuple[str, ...] = ("--skip-types",) if args.skip_types else ()
    commands.append(
        workspace_command(
            "runtime-surface",
            label="workspace runtime-surface",
            args=runtime_args,
        )
    )
    commands.append(
        workspace_command(
            "benchmark-surfaces",
            label="workspace benchmark-surfaces",
        )
    )

    if not args.skip_helm and HELM_CHART_DIRS:
        ensure_executable(
            "helm",
            reason="run Helm chart lint",
            skip_hint="--skip-helm",
        )
        commands.extend(helm_lint_command(chart_path) for chart_path in HELM_CHART_DIRS)

    if not args.skip_policy:
        ensure_executable(
            "opa",
            reason="run Rego strict and test gates",
            skip_hint="--skip-policy",
        )
        commands.extend(
            uv_run(
                f"opa check --strict {rego_root}",
                "opa",
                "check",
                "--strict",
                rego_root,
            )
            for rego_root in REGO_SCOPE
        )
        commands.append(
            uv_run(
                "opa test --fail-on-empty",
                "opa",
                "test",
                "--fail-on-empty",
                "ops/policy/policies",
            )
        )

    for command in commands:
        run_command(command)

    print("[lint-full] full authored lint checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
