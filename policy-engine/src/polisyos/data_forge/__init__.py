"""Minimal Data Forge public surface for runtime-safe read APIs."""

from __future__ import annotations

from . import read_api
from ._version import __version__

__all__ = ["__version__", "read_api"]
