"""Legacy SimulationKernel entrypoint (deprecated)."""
from __future__ import annotations

import warnings

warnings.warn(
    "polisyos.foundry.engine is deprecated; use ProgramGraph runtime (foundry.runtime/patch_vm).",
    DeprecationWarning,
    stacklevel=2,
)

from polisyos.foundry._legacy.engine.kernel import SimulationKernel  # noqa: F401
