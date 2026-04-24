"""Curated lazy facade for analytics IR contracts.

The stable compatibility boundary for broad consumers is still
``polisyos.ir``. This package-level facade is intentionally narrower: it
re-exports the most common analytics contracts without mirroring every symbol
from every analytics module. Advanced or module-specific APIs should be
imported from their defining submodules.
"""

from __future__ import annotations

from typing import Any

from polisyos.ir._lazy_facade import lazy_dir, resolve_lazy_export
from polisyos.ir.public_surface import ANALYTICS_FACADE_EXPORTS

__all__ = sorted(ANALYTICS_FACADE_EXPORTS)


def __getattr__(name: str) -> Any:
    return resolve_lazy_export(
        name,
        namespace=globals(),
        exports=ANALYTICS_FACADE_EXPORTS,
    )


def __dir__() -> list[str]:
    return lazy_dir(globals(), ANALYTICS_FACADE_EXPORTS)
