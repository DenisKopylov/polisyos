#!/usr/bin/env python3
"""Compatibility wrapper for ``tools.data.record_fixtures``."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools._lib.compat import run_module_entrypoint, warn_legacy_entrypoint

_TARGET = "tools.data.record_fixtures"


if __name__ == "__main__":
    warn_legacy_entrypoint("scripts/record_fixtures.py", "polisyos-tools data record-fixtures")
    raise SystemExit(run_module_entrypoint(_TARGET))
