#!/usr/bin/env python3
"""Lint authored Markdown docs and package READMEs."""

from __future__ import annotations

import argparse

from ._common import run_command
from ._repo_hygiene import expand_markdown_files, pre_commit_hook


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run markdownlint-cli2 on the authored docs surface: docs pages, "
            "top-level markdown, and package README/CONTRIBUTING files while "
            "excluding docs/archive."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional markdown files or directories to lint instead of the full authored scope.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    files = expand_markdown_files(args.paths) if args.paths else None
    if args.paths and not files:
        raise SystemExit("No in-scope markdown files discovered for the requested paths.")

    run_command(
        pre_commit_hook(
            "markdownlint-cli2",
            label="markdownlint authored docs",
            files=files,
        )
    )
    print("[docs-style] authored markdown style checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
