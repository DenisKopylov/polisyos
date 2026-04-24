from __future__ import annotations

import importlib
import sys
from pathlib import Path

for _candidate in Path(__file__).resolve().parents:
    if (_candidate / "tools").is_dir() and (_candidate / "pyproject.toml").exists():
        sys.path.insert(0, str(_candidate))
        break

_compat = importlib.import_module("tools._lib.compat")
expose_module = _compat.expose_module
run_module_entrypoint = _compat.run_module_entrypoint

_TARGET = "tools.devx.workspace.benchmark_surfaces"

expose_module(globals(), _TARGET)


if __name__ == "__main__":
    raise SystemExit(run_module_entrypoint(_TARGET))
