"""Public backends stub module API."""
from __future__ import annotations

import warnings

from polisyos.core.governance.legal.backends.stub import StubBackend

warnings.warn(
    "polisyos.scientist.governance.legal.backends.stub is deprecated; use polisyos.core.governance.legal.backends.stub",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["StubBackend"]
