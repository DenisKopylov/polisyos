from __future__ import annotations

import sys
from pathlib import Path

for _candidate in Path(__file__).resolve().parents:
    if (_candidate / "tools").is_dir() and (_candidate / "pyproject.toml").exists():
        sys.path.insert(0, str(_candidate))
        break

from tools._lib.compat import expose_module

_TARGET = "tools.devx.architecture"

expose_module(globals(), _TARGET)
