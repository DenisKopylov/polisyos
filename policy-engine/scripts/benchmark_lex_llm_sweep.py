#!/usr/bin/env python3
"""Compatibility wrapper for ``tools.benchmarks.benchmark_lex_llm_sweep``."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools._lib.compat import run_module_entrypoint, warn_legacy_entrypoint

_TARGET = "tools.benchmarks.benchmark_lex_llm_sweep"


if __name__ == "__main__":
    warn_legacy_entrypoint(
        "scripts/benchmark_lex_llm_sweep.py", "polisyos-tools benchmarks benchmark-lex-llm-sweep"
    )
    raise SystemExit(run_module_entrypoint(_TARGET))
