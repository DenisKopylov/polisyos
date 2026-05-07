"""Compatibility facade for Fabric product integration bridges."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_impl = _import_module("polisyos.fabric._internal.compatibility")
_sys.modules[__name__] = _impl
