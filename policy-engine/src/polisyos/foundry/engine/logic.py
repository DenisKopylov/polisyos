"""Legacy engine logic (deprecated)."""
from __future__ import annotations

import warnings

warnings.warn(
    "polisyos.foundry.engine.logic is deprecated; use patch-based runtime instead.",
    DeprecationWarning,
    stacklevel=2,
)

from polisyos.foundry._legacy.engine.logic import *  # noqa: F401,F403
