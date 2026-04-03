"""Deprecated compatibility shim for the core safety governance pass.

`SafetyPass` is implemented in `polisyos.core.governance.passes.safety_pass`.
The Scientist-local module remains as a warning-emitting alias for existing
configs and generated reference docs.
"""
from __future__ import annotations

import warnings

from polisyos.core.governance.passes.safety_pass import SafetyPass

warnings.warn(
    "polisyos.scientist.governance.passes.safety_pass is deprecated; use polisyos.core.governance.passes.safety_pass",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["SafetyPass"]
