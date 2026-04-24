#!/usr/bin/env python3
"""Run the Phase 8 benchmark/research hygiene gate for authored assets."""

from __future__ import annotations

import argparse

from ._common import run_command
from ._repo_hygiene import BENCHMARK_RESEARCH_SCOPE, expand_files, pre_commit_hook, uv_run

_PHASE8_RUFF_SELECT = "E,F,I,UP"
_PHASE8_RUFF_IGNORE = "E402,E501"


def _build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=(
            "Run the Phase 8 benchmark/research hygiene contract: Ruff on authored "
            "Python plus shell/YAML checks for wrapper assets, while leaving "
            "markdown, JSON, logs, and result bundles out of scope."
        )
    )


def main(argv: list[str] | None = None) -> int:
    _build_parser().parse_args(argv)

    shell_files = expand_files(BENCHMARK_RESEARCH_SCOPE, suffixes=(".sh",))
    yaml_files = expand_files(BENCHMARK_RESEARCH_SCOPE, suffixes=(".yaml", ".yml"))

    commands = [
        uv_run(
            "ruff check benchmark/research authored Python",
            "ruff",
            "check",
            "--select",
            _PHASE8_RUFF_SELECT,
            "--ignore",
            _PHASE8_RUFF_IGNORE,
            *BENCHMARK_RESEARCH_SCOPE,
        ),
        uv_run(
            "ruff format --check benchmark/research authored Python",
            "ruff",
            "format",
            "--check",
            *BENCHMARK_RESEARCH_SCOPE,
        ),
    ]

    if shell_files:
        commands.extend(
            [
                pre_commit_hook(
                    "shfmt",
                    label="shfmt benchmark/research shell",
                    files=shell_files,
                ),
                pre_commit_hook(
                    "shellcheck",
                    label="shellcheck benchmark/research shell",
                    files=shell_files,
                ),
            ]
        )

    if yaml_files:
        commands.append(
            pre_commit_hook(
                "yamllint",
                label="yamllint benchmark/research YAML",
                files=yaml_files,
            )
        )

    for command in commands:
        run_command(command)

    print("[benchmark-surfaces] phase 8 benchmark/research checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
