"""Compatibility wrapper for benchmark release summary generation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools._lib.compat import run_module_entrypoint, warn_legacy_entrypoint

_TARGET = "tools.research.benchmarks.build_release_summary"


if __name__ == "__main__":
    warn_legacy_entrypoint(
        "benchmarks/build_release_summary.py",
        "polisyos-tools benchmarks build-release-summary",
    )
    raise SystemExit(run_module_entrypoint(_TARGET))
