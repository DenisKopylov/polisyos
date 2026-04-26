"""Compatibility import point for schema contracts under the pipeline namespace."""

from __future__ import annotations

from polisyos.data_forge.kernel.schemas import (
    CompatibilityMode,
    SchemaRegistry,
    SchemaVersion,
)

__all__ = ["CompatibilityMode", "SchemaRegistry", "SchemaVersion"]
