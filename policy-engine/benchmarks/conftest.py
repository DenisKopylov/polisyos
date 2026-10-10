"""Source-path bootstrap for explicit PolicyOS benchmark collection."""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap
# Make sure `policy-engine/src` is importable whether running via pytest
# from the repo root or directly as a script.
# ---------------------------------------------------------------------------

_BENCH_DIR = Path(__file__).resolve().parent
_SRC_DIR = _BENCH_DIR.parent / "src"

if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
