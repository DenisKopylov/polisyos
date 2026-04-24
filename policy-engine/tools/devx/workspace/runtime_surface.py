#!/usr/bin/env python3
"""Run the Phase 5B runtime lint, type, boundary, and API contract gate."""

from __future__ import annotations

import argparse

from ._common import run_command
from ._repo_hygiene import uv_run

RUNTIME_SCOPE = ("src/polisyos/runtime", "tests/runtime")
RUNTIME_SOURCE_SCOPE = ("src/polisyos/runtime",)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Phase 5B runtime gate: Ruff over runtime source/tests, "
            "source type checks, OpenAPI/client drift check, and owning tests."
        )
    )
    parser.add_argument(
        "--skip-types",
        action="store_true",
        help="Skip mypy and basedpyright.",
    )
    parser.add_argument(
        "--skip-openapi",
        action="store_true",
        help="Skip the runtime OpenAPI/client drift check.",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip tests/runtime.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    commands = [
        uv_run(
            "ruff format --check runtime surface",
            "ruff",
            "format",
            "--check",
            *RUNTIME_SCOPE,
        ),
        uv_run(
            "ruff check runtime surface",
            "ruff",
            "check",
            *RUNTIME_SCOPE,
        ),
    ]

    if not args.skip_types:
        commands.extend(
            [
                uv_run("mypy runtime source", "mypy", *RUNTIME_SOURCE_SCOPE),
                uv_run("basedpyright runtime source", "basedpyright", *RUNTIME_SOURCE_SCOPE),
            ]
        )

    if not args.skip_openapi:
        commands.append(
            uv_run(
                "runtime API contract",
                "python",
                "tools/runtime/check_runtime_api_contract.py",
            )
        )

    if not args.skip_tests:
        commands.append(uv_run("pytest runtime", "pytest", "tests/runtime"))

    for command in commands:
        run_command(command)

    print("[runtime-surface] Phase 5B runtime gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
