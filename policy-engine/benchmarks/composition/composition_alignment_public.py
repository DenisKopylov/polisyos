from __future__ import annotations

import sys
from pathlib import Path

_BENCH_ROOT = Path(__file__).resolve().parents[2]
_SRC = _BENCH_ROOT / "src"
for _path in (str(_SRC), str(_BENCH_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from benchmarks.advanced.common import main_for_suite


if __name__ == "__main__":
    raise SystemExit(
        main_for_suite(
            "composition_alignment_public",
            description="Academic public composition-alignment benchmark",
        )
    )
