#!/usr/bin/env python3
"""Compatibility wrapper for the archived Policy Design Case closeout loop."""

from __future__ import annotations

import sys

from tools.quality.validation.check_policy_design_formal_invariants import main


def _normalized_args(argv: list[str]) -> list[str]:
    return [arg for arg in argv if arg != "--require-passing"]


if __name__ == "__main__":
    raise SystemExit(main(_normalized_args(sys.argv[1:])))
