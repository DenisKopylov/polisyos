"""Compatibility shim for lazy facade helpers.

Use :mod:`polisyos.ir.api` for new code.
"""

from __future__ import annotations

import warnings

from polisyos.ir.api import LazyExportMap, lazy_dir, resolve_lazy_export

warnings.warn(
    (
        "polisyos.ir._lazy_facade is a deprecated IR compatibility import; use "
        "polisyos.ir.api instead. This shim is scheduled for removal after 2026-12-31; "
        "see docs/archive/reports/REPOSITORY_BEST_IN_CLASS_LAST_MILE_IMPORT_MAP.md"
        "#ir-shell-packages."
    ),
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["LazyExportMap", "lazy_dir", "resolve_lazy_export"]
