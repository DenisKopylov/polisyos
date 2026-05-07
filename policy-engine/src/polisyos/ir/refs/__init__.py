"""Compatibility shim for artifact reference contracts.

Use :mod:`polisyos.ir.references` for new code.
"""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_impl = _import_module("polisyos.ir.references.refs")
_sys.modules[__name__] = _impl
