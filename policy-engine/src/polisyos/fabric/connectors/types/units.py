"""
Unit algebra system for type-safe data operations.

This module implements a comprehensive unit system that:
- Parses string representations (e.g., "km/h", "USD", "Mio EUR")
- Performs unit conversion with proper factor handling
- Checks dimensional compatibility between units
- Integrates with ir/kernel/units.py for canonical unit types

Design principles:
- Lightweight (no pint/astropy dependency)
- Immutable unit objects
- Clear separation of dimension checking vs conversion
- Extensible for future currency rate injection

The system handles three types of conversions:
1. Metric prefixes (km -> m, Mio -> 1e6)
2. Within-system conversions (hours -> seconds, km -> m)
3. Currency placeholder (USD -> EUR requires external rates)

Example:
    >>> from polisyos.fabric.connectors.types.units import Unit
    >>> speed_kmh = Unit.parse("km/h")
    >>> speed_ms = Unit.parse("m/s")
    >>> assert speed_kmh.is_compatible_with(speed_ms)
    >>> value_ms = speed_kmh.convert_to(speed_ms, 90.0)  # 90 km/h -> 25 m/s
"""
from __future__ import annotations

from polisyos.fabric.connectors.types._units_base import (
    BaseUnit,
    ConversionFactor,
)
from polisyos.fabric.connectors.types._units_core import (
    Unit,
)
from polisyos.fabric.connectors.types._units_errors import (
    UnitConversionError,
    UnitParseError,
)
from polisyos.fabric.connectors.types._units_prefixes import (
    MetricPrefix,
)
from polisyos.fabric.connectors.types._units_registry import (
    UnitRegistry,
    get_unit_registry,
    parse_unit,
)

__all__ = [
    "Unit",
    "UnitRegistry",
    "ConversionFactor",
    "UnitParseError",
    "UnitConversionError",
    "MetricPrefix",
    "BaseUnit",
    "get_unit_registry",
    "parse_unit",
]
