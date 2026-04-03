"""Public governance profiles module API."""
from __future__ import annotations

import warnings

from polisyos.core.governance.profiles import ProfileLevel, ValidationProfile

warnings.warn(
    "polisyos.scientist.governance.profiles is deprecated; use polisyos.core.governance.profiles",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["ProfileLevel", "ValidationProfile"]
