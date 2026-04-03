"""Public materialize rules module API."""
from __future__ import annotations

from enum import Enum

from polisyos.ir.world.predicates import (
    WORLD_ARTIFACT_ID,
    WORLD_KIND,
    WORLD_LABEL,
    WORLD_PROPS_REF,
)


class MergeStrategy(str, Enum):
    """Merge strategy data model."""
    ERROR_ON_CONFLICT = "error_on_conflict"
    PREFER_NON_NULL_LAST_TX = "prefer_non_null_last_tx"
    LAST_TX = "last_tx"
    FIRST_TX = "first_tx"


WORLD_ATTR_MERGE_RULES: dict[str, MergeStrategy] = {
    WORLD_KIND: MergeStrategy.ERROR_ON_CONFLICT,
    WORLD_LABEL: MergeStrategy.PREFER_NON_NULL_LAST_TX,
    WORLD_ARTIFACT_ID: MergeStrategy.PREFER_NON_NULL_LAST_TX,
    WORLD_PROPS_REF: MergeStrategy.PREFER_NON_NULL_LAST_TX,
}

WORLD_ATTR_PREDICATES: tuple[str, ...] = tuple(WORLD_ATTR_MERGE_RULES.keys())

__all__ = [
    "MergeStrategy",
    "WORLD_ATTR_MERGE_RULES",
    "WORLD_ATTR_PREDICATES",
]
