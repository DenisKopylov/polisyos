from __future__ import annotations

import sys
from pathlib import Path

for _candidate in Path(__file__).resolve().parents:
    if (_candidate / "tools").is_dir() and (_candidate / "pyproject.toml").exists():
        sys.path.insert(0, str(_candidate))
        break

from collections.abc import Sequence

from tools._lib.compat import expose_module, run_module_entrypoint

_TARGET = "tools.research.benchmarks.build_release_summary"

expose_module(globals(), _TARGET)


def main(argv: Sequence[str] | None = None) -> int:
    return run_module_entrypoint(_TARGET, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
