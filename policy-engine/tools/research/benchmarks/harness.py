"""Compatibility shim for benchmark support code owned by the root package."""

from __future__ import annotations

from tools._lib.compat import expose_module

_TARGET = "benchmarks.harness"

expose_module(globals(), _TARGET)
