"""Compatibility surface for a Phase 4.1 split module."""

from __future__ import annotations

from . import core as _core
globals().update({name: getattr(_core, name) for name in dir(_core) if not name.startswith("__")})
from . import transport as _transport
globals().update({name: getattr(_transport, name) for name in dir(_transport) if not name.startswith("__")})
from . import counterfactual as _counterfactual
globals().update({name: getattr(_counterfactual, name) for name in dir(_counterfactual) if not name.startswith("__")})
from . import api as _api
globals().update({name: getattr(_api, name) for name in dir(_api) if not name.startswith("__")})

__all__ = [name for name in globals() if not name.startswith("__") and not name.startswith("_")]
