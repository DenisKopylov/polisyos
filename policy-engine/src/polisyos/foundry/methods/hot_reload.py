"""Compatibility facade for compiler hot reload utilities."""

from __future__ import annotations

import sys

from .compiler import hot_reload as _hot_reload

sys.modules[__name__] = _hot_reload
