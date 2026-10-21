"""Lazy public facade for shared IR model-layer vocabulary."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.ir.api import MODEL_LAYER_FACADE_EXPORTS, lazy_dir, resolve_lazy_export

if TYPE_CHECKING:
    from polisyos.ir.model_layer.types import (
        EntityType as EntityType,
    )
    from polisyos.ir.model_layer.types import (
        OptimizationDirection as OptimizationDirection,
    )
    from polisyos.ir.model_layer.types import (
        SelectorOperator as SelectorOperator,
    )
    from polisyos.ir.model_layer.types import (
        TimeFrequency as TimeFrequency,
    )
    from polisyos.ir.model_layer.types import (
        TimeUnit as TimeUnit,
    )
    from polisyos.ir.model_layer.types import (
        TranslatableString as TranslatableString,
    )

__all__ = sorted(MODEL_LAYER_FACADE_EXPORTS)


def __getattr__(name: str) -> object:
    return resolve_lazy_export(name, namespace=globals(), exports=MODEL_LAYER_FACADE_EXPORTS)


def __dir__() -> list[str]:
    return lazy_dir(globals(), MODEL_LAYER_FACADE_EXPORTS)
