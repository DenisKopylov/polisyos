#!/usr/bin/env python3
"""Compatibility wrapper for ``tools.foundry.update_signature_baseline``."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools._lib.compat import run_module_entrypoint, warn_legacy_entrypoint

_TARGET = "tools.foundry.update_signature_baseline"


if __name__ == "__main__":
    warn_legacy_entrypoint("scripts/update_signature_baseline.py", "polisyos-tools foundry update-signature-baseline")
    raise SystemExit(run_module_entrypoint(_TARGET))
