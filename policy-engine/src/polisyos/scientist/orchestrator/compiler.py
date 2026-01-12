"""Legacy compiler stub (PolicyRequestIR)."""
from __future__ import annotations

import warnings

warnings.warn(
    "polisyos.scientist.orchestrator.compiler (PolicyRequestIR) is deprecated; use Surface IR compiler.",
    DeprecationWarning,
    stacklevel=2,
)

from polisyos.scientist._legacy.compiler import compile_policy  # noqa: F401
