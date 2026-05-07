"""Compatibility facade for Fabric numeric parsing helpers."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_impl = _import_module("polisyos.fabric._internal.numeric_parsing")
_sys.modules[__name__] = _impl
