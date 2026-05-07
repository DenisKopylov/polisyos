"""Compatibility facade for Fabric ingestion provider dependencies."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_impl = _import_module("polisyos.fabric.ingestion.providers")
_sys.modules[__name__] = _impl
