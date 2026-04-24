"""
Foundry Methods Type Utilities.

This subpackage provides predefined units and unit compatibility helpers.
"""

from __future__ import annotations

from polisyos.foundry.methods.types.checker import (
    AdapterPlan,
    IncompatibilityReason,
    ShapeAdapter,
    ShapeAdapterKind,
    SlotCompatibility,
    TypeAdapter,
    TypeAdapterKind,
    UnitAdapter,
    UnitAdapterKind,
    check_multiple_compatibility,
    check_slot_compatibility,
    find_compatible_slots,
)
from polisyos.foundry.methods.types.units import Units, get_scale_factor, units_compatible

__all__ = [
    "AdapterPlan",
    "IncompatibilityReason",
    "ShapeAdapter",
    "ShapeAdapterKind",
    "SlotCompatibility",
    "TypeAdapter",
    "TypeAdapterKind",
    "UnitAdapter",
    "UnitAdapterKind",
    "Units",
    "check_multiple_compatibility",
    "check_slot_compatibility",
    "find_compatible_slots",
    "get_scale_factor",
    "units_compatible",
]
