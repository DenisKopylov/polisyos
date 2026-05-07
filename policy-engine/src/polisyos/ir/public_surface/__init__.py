"""Compatibility shim for the IR public-surface manifest.

Use :mod:`polisyos.ir.api` for new code.
"""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_impl = _import_module("polisyos.ir.api")
_sys.modules[__name__] = _impl
