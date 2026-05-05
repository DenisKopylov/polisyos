#!/usr/bin/env python3
"""Compatibility wrapper for the canonical JAX simulation benchmark entry point."""

from __future__ import annotations

import sys

from tools.lib.imports import repo_root_from

sys.path.insert(0, str(repo_root_from(__file__)))

from .jax.bench_simulation import main

if __name__ == "__main__":
    raise SystemExit(main())
