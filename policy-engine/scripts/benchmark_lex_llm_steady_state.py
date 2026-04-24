#!/usr/bin/env python3
"""Compatibility wrapper for ``tools.benchmarks.benchmark_lex_llm_steady_state``."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools._lib.compat import expose_module, run_module_entrypoint, warn_legacy_entrypoint

_TARGET = "tools.benchmarks.benchmark_lex_llm_steady_state"

expose_module(globals(), _TARGET)


if __name__ == "__main__":
    warn_legacy_entrypoint(
        "scripts/benchmark_lex_llm_steady_state.py",
        "polisyos-tools benchmarks benchmark-lex-llm-steady-state",
    )
    raise SystemExit(run_module_entrypoint(_TARGET))
