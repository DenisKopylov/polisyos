#!/usr/bin/env python3
"""Compatibility wrapper for the Phase 5B runtime surface gate."""

from __future__ import annotations

from tools._lib.compat import expose_module, run_module_entrypoint

_TARGET = "tools.devx.workspace.runtime_surface"

expose_module(globals(), _TARGET)


if __name__ == "__main__":
    raise SystemExit(run_module_entrypoint(_TARGET))
