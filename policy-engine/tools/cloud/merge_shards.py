from __future__ import annotations

import sys
from pathlib import Path

for _candidate in Path(__file__).resolve().parents:
    if (_candidate / "tools").is_dir() and (_candidate / "pyproject.toml").exists():
        sys.path.insert(0, str(_candidate))
        break

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools._lib.compat import expose_module, run_module_entrypoint

_TARGET = "tools.ops.cloud.merge_shards"

expose_module(globals(), _TARGET)


if __name__ == "__main__":
    raise SystemExit(run_module_entrypoint(_TARGET))
