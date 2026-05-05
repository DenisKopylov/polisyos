"""Deprecated reference stub for the removed Foundry engine export demo."""

from __future__ import annotations

import sys
from collections.abc import Sequence

__all__ = ("main",)


def main(argv: Sequence[str] | None = None) -> int:
    """Explain the current replacement instead of importing removed engine APIs."""
    _ = argv
    sys.stderr.write(
        "run_export_demo is deprecated: polisyos.foundry.engine was removed. "
        "Use `polisyos-tools runtime export-runtime-openapi` for the maintained "
        "runtime export surface, or rebuild this demo on current Foundry contracts.\n"
    )
    return 1
