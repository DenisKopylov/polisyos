"""Stable registry facade for kernel slots, units, metrics, and merge contracts.

Names in ``__all__`` are resolved lazily so importing ``polisyos.ir.kernel``
does not eagerly instantiate default registries or pull the full kernel module
graph into process startup. Treat this facade as the documented public surface
for registry-aware runtime code.
"""

from __future__ import annotations

from typing import Any

from polisyos.ir.api import KERNEL_FACADE_EXPORTS, lazy_dir, resolve_lazy_export

__all__ = sorted(KERNEL_FACADE_EXPORTS)


def __getattr__(name: str) -> Any:
    return resolve_lazy_export(
        name,
        namespace=globals(),
        exports=KERNEL_FACADE_EXPORTS,
    )


def __dir__() -> list[str]:
    return lazy_dir(globals(), KERNEL_FACADE_EXPORTS)
