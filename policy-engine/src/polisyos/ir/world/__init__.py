"""Lazy public facade for world-model claims, provenance, ids, and quality records."""
from __future__ import annotations

from typing import Any

from polisyos.ir._lazy_facade import lazy_dir, resolve_lazy_export
from polisyos.ir.public_surface import WORLD_FACADE_EXPORTS

__all__ = sorted(WORLD_FACADE_EXPORTS)


def __getattr__(name: str) -> Any:
    return resolve_lazy_export(
        name,
        namespace=globals(),
        exports=WORLD_FACADE_EXPORTS,
    )


def __dir__() -> list[str]:
    return lazy_dir(globals(), WORLD_FACADE_EXPORTS)
