"""Compatibility surface for a Phase 4.1 split module."""

from __future__ import annotations

from . import identification as _identification
globals().update({name: getattr(_identification, name) for name in dir(_identification) if not name.startswith("__")})
from . import estimation as _estimation
globals().update({name: getattr(_estimation, name) for name in dir(_estimation) if not name.startswith("__")})
from . import api as _api
globals().update({name: getattr(_api, name) for name in dir(_api) if not name.startswith("__")})

__all__ = [name for name in globals() if not name.startswith("__") and not name.startswith("_")]
