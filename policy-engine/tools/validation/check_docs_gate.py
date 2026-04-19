from __future__ import annotations

import sys
from pathlib import Path


def _load_compat() -> tuple[object, object]:
    for _candidate in Path(__file__).resolve().parents:
        if (_candidate / "tools").is_dir() and (_candidate / "pyproject.toml").exists():
            sys.path.insert(0, str(_candidate))
            break
    from tools._lib.compat import expose_module, run_module_entrypoint

    return expose_module, run_module_entrypoint


expose_module, run_module_entrypoint = _load_compat()

_TARGET = "tools.quality.validation.check_docs_gate"

expose_module(globals(), _TARGET)


if __name__ == "__main__":
    raise SystemExit(run_module_entrypoint(_TARGET))
