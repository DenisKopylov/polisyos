"""Compatibility shim for benchmark metrics owned by the root package."""

from __future__ import annotations

from tools.lib.compat import expose_module

_TARGET = "benchmarks.metrics"

expose_module(globals(), _TARGET)
