"""Legacy basic simulation demo (deprecated)."""
from __future__ import annotations

import warnings

warnings.warn(
    "polisyos.foundry.basic_simulation is deprecated; use ProgramGraph demos instead.",
    DeprecationWarning,
    stacklevel=2,
)

from polisyos.foundry._legacy.basic_simulation import (  # noqa: F401
    analyze_simulation_results,
    simple_policy_simulation,
)
