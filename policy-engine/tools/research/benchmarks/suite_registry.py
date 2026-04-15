"""Compatibility shim for benchmark suite registry owned by the root package."""

from __future__ import annotations

from tools._lib.compat import expose_module, run_module_entrypoint

_TARGET = "benchmarks.suite_registry"

expose_module(globals(), _TARGET)


if __name__ == "__main__":
    raise SystemExit(run_module_entrypoint(_TARGET))
