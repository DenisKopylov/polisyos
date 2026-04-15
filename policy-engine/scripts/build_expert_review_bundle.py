#!/usr/bin/env python3
"""Compatibility wrapper for ``tools.data.build_expert_review_bundle``."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools._lib.compat import run_module_entrypoint, warn_legacy_entrypoint

_TARGET = "tools.data.build_expert_review_bundle"


if __name__ == "__main__":
    warn_legacy_entrypoint("scripts/build_expert_review_bundle.py", "polisyos-tools data build-expert-review-bundle")
    raise SystemExit(run_module_entrypoint(_TARGET))
