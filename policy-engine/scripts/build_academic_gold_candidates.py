#!/usr/bin/env python3
"""Compatibility wrapper for ``tools.data.build_academic_gold_candidates``."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools._lib.compat import run_module_entrypoint, warn_legacy_entrypoint

_TARGET = "tools.data.build_academic_gold_candidates"


if __name__ == "__main__":
    warn_legacy_entrypoint("scripts/build_academic_gold_candidates.py", "polisyos-tools data build-academic-gold-candidates")
    raise SystemExit(run_module_entrypoint(_TARGET))
