"""Deprecated compatibility shim for the core legal governance pass.

The `LegalPass` implementation is owned by
`polisyos.core.governance.passes.legal_pass`; this module preserves the legacy
Scientist import path and emits a deprecation warning on import.
"""

from __future__ import annotations

import warnings

from polisyos.core.governance.passes.legal_pass import LegalPass

warnings.warn(
    "polisyos.scientist.governance.passes.legal_pass is deprecated; use polisyos.core.governance.passes.legal_pass",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["LegalPass"]
