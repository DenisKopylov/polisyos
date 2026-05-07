"""Lazy public facade for world-model claims, provenance, ids, and quality records."""

from __future__ import annotations

from typing import Any

from polisyos.ir.api import WORLD_FACADE_EXPORTS, lazy_dir, resolve_lazy_export

__all__ = sorted(WORLD_FACADE_EXPORTS)


def __getattr__(name: str) -> Any:
    return resolve_lazy_export(
        name,
        namespace=globals(),
        exports=WORLD_FACADE_EXPORTS,
    )


def __dir__() -> list[str]:
    return lazy_dir(globals(), WORLD_FACADE_EXPORTS)
