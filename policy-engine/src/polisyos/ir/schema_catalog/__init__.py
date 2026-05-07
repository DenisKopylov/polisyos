"""Compatibility shim for the IR schema catalog.

Use :mod:`polisyos.ir.schemas` for new code.
"""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_impl = _import_module("polisyos.ir.schemas.catalog")
_sys.modules[__name__] = _impl
