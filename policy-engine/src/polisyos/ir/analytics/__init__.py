"""Curated lazy facade for analytics IR contracts.

The stable compatibility boundary for broad consumers is still
``polisyos.ir``. This package-level facade is intentionally narrower: it
re-exports the most common analytics contracts without mirroring every symbol
from every analytics module. Advanced or module-specific APIs should be
imported from their defining submodules.
"""

from __future__ import annotations

import importlib
from typing import Any

from polisyos.ir.api import ANALYTICS_FACADE_EXPORTS, lazy_dir, resolve_lazy_export

__all__ = sorted(ANALYTICS_FACADE_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in ANALYTICS_FACADE_EXPORTS:
        try:
            module = importlib.import_module(f"{__name__}.{name}")
        except ModuleNotFoundError as exc:
            if exc.name != f"{__name__}.{name}":
                raise
        else:
            globals()[name] = module
            return module
    return resolve_lazy_export(
        name,
        namespace=globals(),
        exports=ANALYTICS_FACADE_EXPORTS,
    )


def __dir__() -> list[str]:
    return lazy_dir(globals(), ANALYTICS_FACADE_EXPORTS)
