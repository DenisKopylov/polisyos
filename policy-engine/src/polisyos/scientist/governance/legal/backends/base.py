"""Public backends base module API."""
from __future__ import annotations

import warnings

from polisyos.core.governance.legal.backends.base import RuleBackend

warnings.warn(
    "polisyos.scientist.governance.legal.backends.base is deprecated; use polisyos.core.governance.legal.backends.base",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["RuleBackend"]
