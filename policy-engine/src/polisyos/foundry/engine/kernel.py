"""Legacy SimulationKernel (deprecated)."""
from __future__ import annotations

import warnings

warnings.warn(
    "polisyos.foundry.engine.kernel is deprecated; use polisyos.foundry.runtime.",
    DeprecationWarning,
    stacklevel=2,
)

from polisyos.foundry._legacy.engine.kernel import SimulationKernel  # noqa: F401
