"""Public passes safety pass module API."""
from __future__ import annotations

import warnings

from polisyos.core.governance.passes.safety_pass import SafetyPass

warnings.warn(
    "polisyos.scientist.governance.passes.safety_pass is deprecated; use polisyos.core.governance.passes.safety_pass",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["SafetyPass"]
