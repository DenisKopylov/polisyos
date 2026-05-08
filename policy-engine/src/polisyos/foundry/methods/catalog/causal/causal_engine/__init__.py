"""Compatibility surface for the Phase 4.1 CausalEngine split."""

from __future__ import annotations

from . import artifacts as _artifacts
from .api import CausalEngine

globals().update(
    {name: getattr(_artifacts, name) for name in dir(_artifacts) if not name.startswith("__")}
)
globals()["CausalEngine"] = CausalEngine

__all__ = [name for name in globals() if not name.startswith("__") and name != "_artifacts"]
