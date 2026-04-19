"""Compatibility wrapper for the zoned parallel benchmark runner."""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TARGET = "tools.research.benchmarks.run_parallel"

if __name__ != "__main__":
    _impl = import_module(_TARGET)
    _parent = sys.modules.get(__package__)
    if _parent is not None:
        setattr(_parent, "run_parallel", _impl)
    sys.modules[__name__] = _impl
    globals().update(vars(_impl))


if __name__ == "__main__":
    from tools._lib.compat import run_module_entrypoint, warn_legacy_entrypoint

    warn_legacy_entrypoint("benchmarks/run_parallel.py", "polisyos-tools benchmarks run-parallel")
    raise SystemExit(run_module_entrypoint(_TARGET))
