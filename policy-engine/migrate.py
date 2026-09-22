#!/usr/bin/env python3
"""Compatibility entrypoint for the canonical migration runner."""

from __future__ import annotations

from collections.abc import Sequence

from tools.lib.imports import ensure_repo_import_roots


def main(argv: Sequence[str] | None = None) -> int:
    """Delegate the historical root command to the single canonical executor."""
    ensure_repo_import_roots(__file__)
    from tools.ops_runners.migrations.migrate import main as canonical_main

    return canonical_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
