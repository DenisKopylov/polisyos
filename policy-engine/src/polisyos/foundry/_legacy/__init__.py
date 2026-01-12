# Legacy Foundry APIs (SimulationKernel/basic_simulation).
# Use patch VM / ProgramGraph runtime instead.
from __future__ import annotations

import warnings

warnings.warn(
    "polisyos.foundry._legacy is deprecated; migrate to ProgramGraph/patch VM.",
    DeprecationWarning,
    stacklevel=2,
)

