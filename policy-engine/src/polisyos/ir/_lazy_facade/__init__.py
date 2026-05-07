"""Compatibility shim for lazy facade helpers.

Use :mod:`polisyos.ir.api` for new code.
"""

from __future__ import annotations

from polisyos.ir.api import LazyExportMap, lazy_dir, resolve_lazy_export

__all__ = ["LazyExportMap", "lazy_dir", "resolve_lazy_export"]
