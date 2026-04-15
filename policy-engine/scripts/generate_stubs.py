#!/usr/bin/env python3
"""Compatibility wrapper for ``tools.foundry.generate_stubs``."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools._lib.compat import run_module_entrypoint, warn_legacy_entrypoint

_TARGET = "tools.foundry.generate_stubs"


if __name__ == "__main__":
    warn_legacy_entrypoint("scripts/generate_stubs.py", "polisyos-tools foundry generate-stubs")
    raise SystemExit(run_module_entrypoint(_TARGET))
