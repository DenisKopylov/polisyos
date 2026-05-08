"""Compatibility facade for the split runtime control service modules."""

from __future__ import annotations

from pathlib import Path

__path__ = [str(Path(__file__).with_suffix(""))]

from polisyos.runtime.http.services.control.api import *  # noqa: E402,F403
from polisyos.runtime.http.services.control.api import __all__  # noqa: E402,F401
