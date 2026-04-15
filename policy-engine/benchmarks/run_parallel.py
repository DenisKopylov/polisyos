"""Compatibility wrapper for the zoned parallel benchmark runner."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools._lib.compat import run_module_entrypoint, warn_legacy_entrypoint

_TARGET = "tools.research.benchmarks.run_parallel"


if __name__ == "__main__":
    warn_legacy_entrypoint("benchmarks/run_parallel.py", "polisyos-tools benchmarks run-parallel")
    raise SystemExit(run_module_entrypoint(_TARGET))
