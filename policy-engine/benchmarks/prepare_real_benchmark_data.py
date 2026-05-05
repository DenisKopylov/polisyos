"""Compatibility wrapper for benchmark real-data preparation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.lib.compat import run_module_entrypoint, warn_legacy_entrypoint

_TARGET = "tools.research.benchmarks.prepare_real_benchmark_data"


if __name__ == "__main__":
    warn_legacy_entrypoint(
        "benchmarks/prepare_real_benchmark_data.py",
        "polisyos-tools benchmarks prepare-real-benchmark-data",
    )
    raise SystemExit(run_module_entrypoint(_TARGET))
