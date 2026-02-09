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

import re
import threading
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from functools import cached_property
from typing import ClassVar, Iterator, Mapping, NamedTuple

from polisyos.fabric.connectors.types.dimensions import (
    Dimension,
    DimensionRegistry,
    IncompatibleDimensionsError,
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


# =============================================================================
# Exceptions
# =============================================================================


class UnitParseError(ValueError):
    """Raised when a unit string cannot be parsed."""

    def __init__(self, unit_str: str, reason: str = ""):
        self.unit_str = unit_str
        self.reason = reason
        msg = f"Cannot parse unit '{unit_str}'"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class UnitConversionError(ValueError):
    """Raised when unit conversion is not possible."""

    def __init__(
        self,
        source: "Unit",
        target: "Unit",
        reason: str = "incompatible dimensions",
    ):
        self.source = source
        self.target = target
        self.reason = reason
        super().__init__(
            f"Cannot convert from '{source}' to '{target}': {reason}"
        )


# =============================================================================
# Metric Prefixes
# =============================================================================


class MetricPrefix(Enum):
    """
    SI metric prefixes with their multiplication factors.

    These are used for parsing prefixed units like "km", "MHz", "Mio".
    """

    # Large prefixes
    YOTTA = ("Y", Decimal("1e24"))
    ZETTA = ("Z", Decimal("1e21"))
    EXA = ("E", Decimal("1e18"))
    PETA = ("P", Decimal("1e15"))
    TERA = ("T", Decimal("1e12"))
    GIGA = ("G", Decimal("1e9"))
    MEGA = ("M", Decimal("1e6"))
    KILO = ("k", Decimal("1e3"))
    HECTO = ("h", Decimal("1e2"))
    DECA = ("da", Decimal("1e1"))

    # Small prefixes
    DECI = ("d", Decimal("1e-1"))
    CENTI = ("c", Decimal("1e-2"))
    MILLI = ("m", Decimal("1e-3"))
    MICRO = ("\u03bc", Decimal("1e-6"))
    NANO = ("n", Decimal("1e-9"))
    PICO = ("p", Decimal("1e-12"))
    FEMTO = ("f", Decimal("1e-15"))
    ATTO = ("a", Decimal("1e-18"))
    ZEPTO = ("z", Decimal("1e-21"))
    YOCTO = ("y", Decimal("1e-24"))

    # Common non-SI prefixes used in data
    MIO = ("Mio", Decimal("1e6"))      # Million (common in European data)
    MRD = ("Mrd", Decimal("1e9"))      # Milliard (European billion)
    BN = ("Bn", Decimal("1e9"))        # Billion (US)
    TN = ("Tn", Decimal("1e12"))       # Trillion

    def __init__(self, symbol: str, factor: Decimal):
        self._symbol = symbol
        self._factor = factor

    @property
    def symbol(self) -> str:
        return self._symbol

    @property
    def factor(self) -> Decimal:
        return self._factor

    @classmethod
    def from_symbol(cls, symbol: str) -> "MetricPrefix" | None:
        """Look up a prefix by its symbol."""
        for prefix in cls:
            if prefix.symbol == symbol:
                return prefix
        return None


# Prefix lookup table for parsing
PREFIX_FACTORS: dict[str, Decimal] = {
    prefix.symbol: prefix.factor for prefix in MetricPrefix
}

# Additional aliases
PREFIX_FACTORS.update({
    "K": Decimal("1e3"),      # Uppercase K for kilo (common variant)
    "MM": Decimal("1e6"),     # MM for millions (financial notation)
    "B": Decimal("1e9"),      # B for billions
    "bio": Decimal("1e9"),    # bio for billions (European)
    "tril": Decimal("1e12"),  # trillion abbreviation
    "micro": Decimal("1e-6"),
    "nano": Decimal("1e-9"),
    "pico": Decimal("1e-12"),
    "u": Decimal("1e-6"),
})


# =============================================================================
# Base Unit Definitions
# =============================================================================


class BaseUnit(NamedTuple):
    """
    Definition of a base unit with its properties.

    Attributes:
        symbol: The canonical symbol (e.g., "m", "s", "USD")
        dimension: The physical dimension
        to_si_factor: Conversion factor to SI base unit (or canonical unit)
        aliases: Alternative names/symbols for this unit
        category: Grouping for UI/documentation
        to_si_offset: Affine offset to canonical unit (used for temperature)
    """

    symbol: str
    dimension: Dimension
    to_si_factor: Decimal = Decimal("1")
    aliases: tuple[str, ...] = ()
    category: str = "other"
    to_si_offset: Decimal = Decimal("0")


# Standard unit definitions
# These are the canonical units that form the basis of the unit system
STANDARD_UNITS: dict[str, BaseUnit] = {}


_SUPERSCRIPT_MAP = {
    "\u2070": "0",
    "\u00b9": "1",
    "\u00b2": "2",
    "\u00b3": "3",
    "\u2074": "4",
    "\u2075": "5",
    "\u2076": "6",
    "\u2077": "7",
    "\u2078": "8",
    "\u2079": "9",
    "\u207b": "-",
}


def _register_units() -> None:
    """Register all standard units."""
    global STANDARD_UNITS

    registry = DimensionRegistry.get_instance()

    # Length units
    STANDARD_UNITS.update({
        "m": BaseUnit("m", registry.LENGTH, Decimal("1"), ("meter", "meters", "metre", "metres"), "length"),
        "km": BaseUnit("km", registry.LENGTH, Decimal("1000"), ("kilometer", "kilometers"), "length"),
        "cm": BaseUnit("cm", registry.LENGTH, Decimal("0.01"), ("centimeter", "centimeters"), "length"),
        "mm": BaseUnit("mm", registry.LENGTH, Decimal("0.001"), ("millimeter", "millimeters"), "length"),
        "mi": BaseUnit("mi", registry.LENGTH, Decimal("1609.344"), ("mile", "miles"), "length"),
        "ft": BaseUnit("ft", registry.LENGTH, Decimal("0.3048"), ("foot", "feet"), "length"),
        "in": BaseUnit("in", registry.LENGTH, Decimal("0.0254"), ("inch", "inches"), "length"),
        "yd": BaseUnit("yd", registry.LENGTH, Decimal("0.9144"), ("yard", "yards"), "length"),
        "nm": BaseUnit("nm", registry.LENGTH, Decimal("1852"), ("nautical_mile", "nmi"), "length"),
    })

    # Time units
    STANDARD_UNITS.update({
        "s": BaseUnit("s", registry.TIME, Decimal("1"), ("sec", "second", "seconds"), "time"),
        "ms": BaseUnit("ms", registry.TIME, Decimal("0.001"), ("millisecond", "milliseconds"), "time"),
        "min": BaseUnit("min", registry.TIME, Decimal("60"), ("minute", "minutes"), "time"),
        "h": BaseUnit("h", registry.TIME, Decimal("3600"), ("hr", "hour", "hours"), "time"),
        "d": BaseUnit("d", registry.TIME, Decimal("86400"), ("day", "days"), "time"),
        "wk": BaseUnit("wk", registry.TIME, Decimal("604800"), ("week", "weeks"), "time"),
        "mo": BaseUnit("mo", registry.TIME, Decimal("2629746"), ("month", "months"), "time"),  # Average month
        "yr": BaseUnit("yr", registry.TIME, Decimal("31556952"), ("year", "years", "y", "a"), "time"),  # Average year
    })

    # Mass units
    STANDARD_UNITS.update({
        "kg": BaseUnit("kg", registry.MASS, Decimal("1"), ("kilogram", "kilograms"), "mass"),
        "g": BaseUnit("g", registry.MASS, Decimal("0.001"), ("gram", "grams"), "mass"),
        "mg": BaseUnit("mg", registry.MASS, Decimal("0.000001"), ("milligram", "milligrams"), "mass"),
        "t": BaseUnit("t", registry.MASS, Decimal("1000"), ("tonne", "tonnes", "metric_ton"), "mass"),
        "lb": BaseUnit("lb", registry.MASS, Decimal("0.453592"), ("pound", "pounds", "lbs"), "mass"),
        "oz": BaseUnit("oz", registry.MASS, Decimal("0.0283495"), ("ounce", "ounces"), "mass"),
    })

    # Area units
    STANDARD_UNITS.update({
        "m2": BaseUnit("m2", registry.AREA, Decimal("1"), ("m\u00b2", "sq_m", "sqm", "square_meter"), "area"),
        "km2": BaseUnit("km2", registry.AREA, Decimal("1000000"), ("km\u00b2", "sq_km", "sqkm", "square_kilometer"), "area"),
        "ha": BaseUnit("ha", registry.AREA, Decimal("10000"), ("hectare", "hectares"), "area"),
        "acre": BaseUnit("acre", registry.AREA, Decimal("4046.86"), ("acres", "ac"), "area"),
    })

    # Volume units
    STANDARD_UNITS.update({
        "m3": BaseUnit("m3", registry.VOLUME, Decimal("1"), ("m\u00b3", "cubic_meter"), "volume"),
        "L": BaseUnit("L", registry.VOLUME, Decimal("0.001"), ("l", "liter", "liters", "litre", "litres"), "volume"),
        "mL": BaseUnit("mL", registry.VOLUME, Decimal("0.000001"), ("ml", "milliliter", "milliliters"), "volume"),
    })

    # Currency units (factors are placeholders - real rates injected at runtime)
    STANDARD_UNITS.update({
        "USD": BaseUnit("USD", registry.CURRENCY, Decimal("1"), ("usd", "dollar", "dollars", "$") , "currency"),
        "EUR": BaseUnit("EUR", registry.CURRENCY, Decimal("1"), ("eur", "euro", "euros", "\u20ac"), "currency"),
        "GBP": BaseUnit("GBP", registry.CURRENCY, Decimal("1"), ("gbp", "pound", "pounds", "\u00a3"), "currency"),
        "UAH": BaseUnit("UAH", registry.CURRENCY, Decimal("1"), ("uah", "hryvnia", "hryvnias", "\u20b4"), "currency"),
        "JPY": BaseUnit("JPY", registry.CURRENCY, Decimal("1"), ("jpy", "yen", "\u00a5"), "currency"),
        "CHF": BaseUnit("CHF", registry.CURRENCY, Decimal("1"), ("chf", "franc", "francs"), "currency"),
        "CNY": BaseUnit("CNY", registry.CURRENCY, Decimal("1"), ("cny", "yuan", "rmb", "renminbi"), "currency"),
    })

    # Population/Count units
    STANDARD_UNITS.update({
        "persons": BaseUnit("persons", registry.POPULATION, Decimal("1"), ("person", "people", "capita", "inhabitants"), "population"),
        "households": BaseUnit("households", registry.POPULATION, Decimal("1"), ("household", "hh"), "population"),
    })

    # Dimensionless units
    STANDARD_UNITS.update({
        "ratio": BaseUnit("ratio", registry.DIMENSIONLESS, Decimal("1"), (), "dimensionless"),
        "percent": BaseUnit("percent", registry.DIMENSIONLESS, Decimal("0.01"), ("%", "pct", "percentage"), "dimensionless"),
        "permille": BaseUnit("permille", registry.DIMENSIONLESS, Decimal("0.001"), ("\u2030", "permil"), "dimensionless"),
        "ppm": BaseUnit("ppm", registry.DIMENSIONLESS, Decimal("0.000001"), ("parts_per_million",), "dimensionless"),
        "ppb": BaseUnit("ppb", registry.DIMENSIONLESS, Decimal("0.000000001"), ("parts_per_billion",), "dimensionless"),
    })

    # Index units (special dimensionless)
    STANDARD_UNITS.update({
        "index": BaseUnit("index", registry.INDEX, Decimal("1"), ("idx",), "dimensionless"),
        "points": BaseUnit("points", registry.INDEX, Decimal("1"), ("pt", "point"), "dimensionless"),
    })

    # Temperature (handled specially due to offset)
    celsius_offset = Decimal("273.15")
    fahrenheit_factor = Decimal("5") / Decimal("9")
    fahrenheit_offset = celsius_offset - (Decimal("32") * fahrenheit_factor)

    STANDARD_UNITS.update({
        "K": BaseUnit("K", registry.TEMPERATURE, Decimal("1"), ("kelvin",), "temperature"),
        "degC": BaseUnit(
            "degC",
            registry.TEMPERATURE,
            Decimal("1"),
            ("\u00b0C", "C", "celsius"),
            "temperature",
            celsius_offset,
        ),
        "degF": BaseUnit(
            "degF",
            registry.TEMPERATURE,
            fahrenheit_factor,
            ("\u00b0F", "F", "fahrenheit"),
            "temperature",
            fahrenheit_offset,
        ),
    })

    # Energy units
    STANDARD_UNITS.update({
        "J": BaseUnit("J", registry.ENERGY, Decimal("1"), ("joule", "joules"), "energy"),
        "kJ": BaseUnit("kJ", registry.ENERGY, Decimal("1000"), ("kilojoule",), "energy"),
        "MJ": BaseUnit("MJ", registry.ENERGY, Decimal("1000000"), ("megajoule",), "energy"),
        "kWh": BaseUnit("kWh", registry.ENERGY, Decimal("3600000"), ("kilowatt_hour",), "energy"),
        "cal": BaseUnit("cal", registry.ENERGY, Decimal("4.184"), ("calorie", "calories"), "energy"),
        "kcal": BaseUnit("kcal", registry.ENERGY, Decimal("4184"), ("kilocalorie",), "energy"),
    })

    # Power units
    STANDARD_UNITS.update({
        "W": BaseUnit("W", registry.ENERGY / registry.TIME, Decimal("1"), ("watt", "watts"), "power"),
        "kW": BaseUnit("kW", registry.ENERGY / registry.TIME, Decimal("1000"), ("kilowatt",), "power"),
        "MW": BaseUnit("MW", registry.ENERGY / registry.TIME, Decimal("1000000"), ("megawatt",), "power"),
        "GW": BaseUnit("GW", registry.ENERGY / registry.TIME, Decimal("1000000000"), ("gigawatt",), "power"),
        "hp": BaseUnit("hp", registry.ENERGY / registry.TIME, Decimal("745.7"), ("horsepower",), "power"),
    })


# Initialize on import
_register_units()


# =============================================================================
# Conversion Factor
# =============================================================================


class ConversionFactor(NamedTuple):
    """
    Represents a conversion between two units.

    Attributes:
        multiplier: The factor to multiply the value by
        offset: The offset to add (for temperature conversions)
        requires_rate: True if conversion requires dynamic exchange rate
    """

    multiplier: Decimal
    offset: Decimal = Decimal("0")
    requires_rate: bool = False

    def apply(self, value: float | Decimal) -> Decimal:
        """Apply the conversion factor to a value."""
        decimal_value = Decimal(str(value)) if isinstance(value, float) else value
        return decimal_value * self.multiplier + self.offset

    def inverse(self) -> "ConversionFactor":
        """Get the inverse conversion factor."""
        return ConversionFactor(
            multiplier=Decimal("1") / self.multiplier,
            offset=-self.offset / self.multiplier,
            requires_rate=self.requires_rate,
        )


# =============================================================================
# Unit Class
# =============================================================================


@dataclass(frozen=True)
class Unit:
    """
    Represents a physical unit with support for algebraic operations.

    A Unit combines:
    - A base unit symbol (e.g., "m", "s", "USD")
    - A metric prefix multiplier (e.g., 1000 for "km")
    - Compound unit structure (e.g., "km/h" = km * h^-1)

    The class supports:
    - Parsing from strings ("km/h", "Mio EUR", "m/s^2")
    - Algebraic operations (multiply, divide, power)
    - Conversion between compatible units
    - Dimensional analysis

    Example:
        >>> velocity = Unit.parse("km/h")
        >>> distance = Unit.parse("km")
        >>> time = distance / velocity  # Results in hours
        >>> assert velocity.dimension == Dimension(length=1, time=-1)
    """

    # The canonical symbol or compound expression
    symbol: str

    # The physical dimension
    dimension: Dimension

    # Conversion factor to canonical (SI) units
    to_canonical_factor: Decimal = Decimal("1")

    # Affine offset to canonical units (used for temperature)
    to_canonical_offset: Decimal = Decimal("0")

    # For compound units: the component structure
    # Maps base unit symbols to their powers
    _components: tuple[tuple[str, int], ...] = field(default=())

    # Cached string representation
    _display_str: str | None = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        """Validate unit construction."""
        # Ensure dimension is valid
        if not isinstance(self.dimension, Dimension):
            raise TypeError(f"dimension must be Dimension, got {type(self.dimension)}")

    @classmethod
    def parse(cls, unit_str: str) -> "Unit":
        """
        Parse a unit string into a Unit object.

        Supports formats:
        - Simple: "m", "s", "USD"
        - Prefixed: "km", "MHz", "Mio EUR"
        - Compound: "km/h", "m/s^2", "kg*m/s^2"
        - With exponents: "m2", "m^2", "m^2"

        Args:
            unit_str: The unit string to parse.

        Returns:
            A Unit object representing the parsed unit.

        Raises:
            UnitParseError: If the string cannot be parsed.

        Example:
            >>> Unit.parse("km/h")
            Unit(symbol='km/h', dimension=Dimension(length=1, time=-1), ...)
        """
        if not unit_str or not unit_str.strip():
            raise UnitParseError(unit_str, "empty unit string")

        unit_str = unit_str.strip()

        # Handle special cases
        if unit_str in ("1", "dimensionless", "unitless", "-"):
            return cls.dimensionless()

        # Parse compound units (division and multiplication)
        return cls._parse_compound(unit_str)

    @classmethod
    def _parse_compound(cls, unit_str: str) -> "Unit":
        """Parse a potentially compound unit string."""
        # Normalize the string
        normalized = unit_str.replace("\u00b7", "*").replace("\u00d7", "*")

        # Handle "per" notation (e.g., "km per hour")
        normalized = re.sub(r"\s+per\s+", "/", normalized, flags=re.IGNORECASE)

        # Split by / for numerator and denominator (left-associative)
        if "/" in normalized:
            parts = [p.strip() for p in normalized.split("/")]
            if any(not p for p in parts):
                raise UnitParseError(unit_str, "invalid division syntax")
            result = cls._parse_product(parts[0])
            for part in parts[1:]:
                result = result / cls._parse_product(part)
            return result

        return cls._parse_product(normalized)

    @classmethod
    def _parse_product(cls, unit_str: str) -> "Unit":
        """Parse a product of units (e.g., 'kg*m')."""
        # Split by multiplication signs
        parts = re.split(r"[\*\s]+", unit_str)
        parts = [p.strip() for p in parts if p.strip()]

        if not parts:
            raise UnitParseError(unit_str, "no unit components found")

        # Handle prefix token followed by unit token (e.g., "Mio EUR")
        if (
            len(parts) == 2
            and parts[0] in PREFIX_FACTORS
            and parts[0] not in STANDARD_UNITS
        ):
            prefix_symbol = parts[0]
            base_unit = cls._parse_single(parts[1])
            if base_unit.to_canonical_offset != 0:
                raise UnitParseError(unit_str, "affine units cannot be prefixed")
            if len(base_unit._components) != 1:
                raise UnitParseError(unit_str, "prefix can only apply to base units")
            return cls(
                symbol=f"{prefix_symbol} {base_unit.symbol}",
                dimension=base_unit.dimension,
                to_canonical_factor=base_unit.to_canonical_factor * PREFIX_FACTORS[prefix_symbol],
                to_canonical_offset=base_unit.to_canonical_offset,
                _components=base_unit._components,
            )

        result = cls._parse_single(parts[0])
        for part in parts[1:]:
            result = result * cls._parse_single(part)

        return result

    @classmethod
    def _parse_single(cls, unit_str: str) -> "Unit":
        """Parse a single unit with optional prefix and exponent."""
        if not unit_str:
            raise UnitParseError(unit_str, "empty component")

        # Extract exponent (e.g., "m2", "m^2", "m^2")
        exponent = 1
        exp_match = re.match(r"(.+?)[\^]?([-]?\d+)$", unit_str)
        if exp_match:
            base_str = exp_match.group(1)
            exp_str = exp_match.group(2)
            try:
                exponent = int(exp_str)
                unit_str = base_str
            except ValueError:
                pass
        else:
            # Handle superscript exponents
            idx = len(unit_str)
            while idx > 0 and unit_str[idx - 1] in _SUPERSCRIPT_MAP:
                idx -= 1
            if idx < len(unit_str):
                exp_str = "".join(_SUPERSCRIPT_MAP[ch] for ch in unit_str[idx:])
                try:
                    exponent = int(exp_str)
                    unit_str = unit_str[:idx]
                except ValueError:
                    pass

        # Look up the base unit
        base_unit = cls._lookup_base_unit(unit_str)

        if exponent != 1:
            return base_unit ** exponent

        return base_unit

    @classmethod
    def _lookup_base_unit(cls, unit_str: str) -> "Unit":
        """Look up a base unit, handling prefixes."""
        # First, try direct lookup
        if unit_str in STANDARD_UNITS:
            base = STANDARD_UNITS[unit_str]
            return cls(
                symbol=unit_str,
                dimension=base.dimension,
                to_canonical_factor=base.to_si_factor,
                to_canonical_offset=base.to_si_offset,
                _components=((unit_str, 1),),
            )

        # Try lowercase
        unit_lower = unit_str.lower()
        for symbol, base in STANDARD_UNITS.items():
            if symbol.lower() == unit_lower or unit_lower in [a.lower() for a in base.aliases]:
                return cls(
                    symbol=symbol,
                    dimension=base.dimension,
                    to_canonical_factor=base.to_si_factor,
                    to_canonical_offset=base.to_si_offset,
                    _components=((symbol, 1),),
                )

        # Try stripping common prefixes
        for prefix_symbol, prefix_factor in sorted(
            PREFIX_FACTORS.items(),
            key=lambda x: len(x[0]),
            reverse=True,  # Try longer prefixes first
        ):
            if unit_str.startswith(prefix_symbol) and len(unit_str) > len(prefix_symbol):
                remainder = unit_str[len(prefix_symbol):]

                # Look up the remainder
                if remainder in STANDARD_UNITS:
                    base = STANDARD_UNITS[remainder]
                    if base.to_si_offset != 0:
                        raise UnitParseError(unit_str, "affine units cannot be prefixed")
                    return cls(
                        symbol=unit_str,
                        dimension=base.dimension,
                        to_canonical_factor=base.to_si_factor * prefix_factor,
                        to_canonical_offset=base.to_si_offset,
                        _components=((remainder, 1),),
                    )

                # Try lowercase remainder
                for symbol, base in STANDARD_UNITS.items():
                    if symbol.lower() == remainder.lower():
                        if base.to_si_offset != 0:
                            raise UnitParseError(unit_str, "affine units cannot be prefixed")
                        return cls(
                            symbol=f"{prefix_symbol}{symbol}",
                            dimension=base.dimension,
                            to_canonical_factor=base.to_si_factor * prefix_factor,
                            to_canonical_offset=base.to_si_offset,
                            _components=((symbol, 1),),
                        )

        # Unknown unit - create as generic
        raise UnitParseError(unit_str, f"unknown unit '{unit_str}'")

    @classmethod
    def dimensionless(cls) -> "Unit":
        """Create a dimensionless unit."""
        return cls(
            symbol="1",
            dimension=Dimension(),
            to_canonical_factor=Decimal("1"),
            to_canonical_offset=Decimal("0"),
            _components=(),
        )

    @classmethod
    def from_kernel_unit(cls, unit_id: str) -> "Unit":
        """
        Create a Unit from an ir/kernel/units.py unit ID.

        This bridges the connector type system with the kernel unit registry.

        Args:
            unit_id: The unit ID from the kernel registry.

        Returns:
            A corresponding Unit object.
        """
        # Map kernel unit IDs to our unit system
        kernel_mapping = {
            "usd": "USD",
            "uah": "UAH",
            "eur": "EUR",
            "ratio": "ratio",
            "percent": "percent",
            "year": "yr",
            "month": "mo",
            "per_step": "1",  # Dimensionless for simulation steps
        }

        mapped_symbol = kernel_mapping.get(unit_id, unit_id)

        try:
            return cls.parse(mapped_symbol)
        except UnitParseError:
            # Unknown kernel unit - return as generic dimensionless
            return cls(
                symbol=unit_id,
                dimension=Dimension(),
                to_canonical_factor=Decimal("1"),
                to_canonical_offset=Decimal("0"),
                _components=(),
            )

    @cached_property
    def is_dimensionless(self) -> bool:
        """Check if this is a dimensionless unit."""
        return self.dimension.is_dimensionless

    @cached_property
    def is_currency(self) -> bool:
        """Check if this is a currency unit."""
        return self.dimension == Dimension(currency=1)

    def _currency_code(self) -> str:
        if self._components and len(self._components) == 1 and self._components[0][1] == 1:
            return self._components[0][0]
        return self.symbol

    @cached_property
    def base_symbol(self) -> str:
        """Get the base symbol without any prefix."""
        if self._components:
            # For compound units, join components
            parts = []
            for sym, power in self._components:
                if power == 1:
                    parts.append(sym)
                elif power == -1:
                    parts.append(f"1/{sym}")
                else:
                    parts.append(f"{sym}^{power}")
            return "*".join(parts)
        return self.symbol

    def is_compatible_with(self, other: "Unit") -> bool:
        """
        Check if two units are dimensionally compatible.

        Compatible units can be converted between each other
        (e.g., km and m are compatible, km and s are not).

        Args:
            other: The unit to check compatibility with.

        Returns:
            True if units are compatible, False otherwise.
        """
        return self.dimension.is_compatible_with(other.dimension)

    def get_conversion_factor(self, target: "Unit") -> ConversionFactor:
        """
        Get the conversion factor from this unit to the target unit.

        Args:
            target: The target unit to convert to.

        Returns:
            A ConversionFactor that can convert values.

        Raises:
            UnitConversionError: If conversion is not possible.
        """
        if not self.is_compatible_with(target):
            raise UnitConversionError(self, target, "incompatible dimensions")

        # Check if this is a currency conversion (ignore prefixes)
        requires_rate = False
        if self.is_currency and target.is_currency:
            requires_rate = self._currency_code() != target._currency_code()

        # Calculate the conversion factor (affine aware)
        # value_target = (value_source * f_s + o_s - o_t) / f_t
        multiplier = self.to_canonical_factor / target.to_canonical_factor
        offset = (self.to_canonical_offset - target.to_canonical_offset) / target.to_canonical_factor

        return ConversionFactor(
            multiplier=multiplier,
            offset=offset,
            requires_rate=requires_rate,
        )

    def convert_to(
        self,
        target: "Unit",
        value: float | Decimal,
        *,
        exchange_rates: Mapping[tuple[str, str], Decimal] | None = None,
    ) -> Decimal:
        """
        Convert a value from this unit to the target unit.

        Args:
            target: The target unit to convert to.
            value: The value to convert.
            exchange_rates: Optional mapping of (from_currency, to_currency) -> rate.
                           Required for currency conversions between different currencies.

        Returns:
            The converted value as a Decimal.

        Raises:
            UnitConversionError: If conversion is not possible.

        Example:
            >>> km = Unit.parse("km")
            >>> m = Unit.parse("m")
            >>> km.convert_to(m, 1.5)  # 1.5 km -> 1500 m
            Decimal('1500')
        """
        factor = self.get_conversion_factor(target)

        # Handle currency conversion
        if factor.requires_rate:
            if exchange_rates is None:
                raise UnitConversionError(
                    self, target,
                    f"exchange rate required for {self.symbol} -> {target.symbol}"
                )

            from_currency = self._currency_code()
            to_currency = target._currency_code()
            rate_key = (from_currency, to_currency)
            if rate_key not in exchange_rates:
                # Try reverse rate
                reverse_key = (to_currency, from_currency)
                if reverse_key in exchange_rates:
                    rate = Decimal("1") / exchange_rates[reverse_key]
                else:
                    raise UnitConversionError(
                        self, target,
                        f"exchange rate not found for {self.symbol} -> {target.symbol}"
                    )
            else:
                rate = exchange_rates[rate_key]

            factor = ConversionFactor(
                multiplier=factor.multiplier * rate,
                offset=factor.offset,
            )

        return factor.apply(value)

    def _assert_linear(self, other: "Unit" | None = None, operation: str = "operation") -> None:
        if self.to_canonical_offset != 0:
            raise ValueError(
                f"Cannot {operation} affine unit '{self.symbol}'; use absolute conversions only"
            )
        if other is not None and other.to_canonical_offset != 0:
            raise ValueError(
                f"Cannot {operation} affine unit '{other.symbol}'; use absolute conversions only"
            )

    def __mul__(self, other: "Unit") -> "Unit":
        """
        Multiply two units (add dimensions).

        Example:
            >>> force = Unit.parse("kg") * Unit.parse("m/s^2")
            >>> assert force.symbol == "kg*m/s^2"
        """
        self._assert_linear(other, operation="multiply")
        new_dimension = self.dimension * other.dimension
        new_factor = self.to_canonical_factor * other.to_canonical_factor

        # Combine components
        components: dict[str, int] = {}
        for sym, power in self._components:
            components[sym] = components.get(sym, 0) + power
        for sym, power in other._components:
            components[sym] = components.get(sym, 0) + power

        # Remove zero-power components
        components = {k: v for k, v in components.items() if v != 0}

        # Build symbol
        new_symbol = self._build_compound_symbol(components)

        return Unit(
            symbol=new_symbol,
            dimension=new_dimension,
            to_canonical_factor=new_factor,
            to_canonical_offset=Decimal("0"),
            _components=tuple(sorted(components.items())),
        )

    def __truediv__(self, other: "Unit") -> "Unit":
        """
        Divide two units (subtract dimensions).

        Example:
            >>> velocity = Unit.parse("m") / Unit.parse("s")
            >>> assert velocity.dimension == Dimension(length=1, time=-1)
        """
        self._assert_linear(other, operation="divide")
        new_dimension = self.dimension / other.dimension
        new_factor = self.to_canonical_factor / other.to_canonical_factor

        # Combine components (subtract other's powers)
        components: dict[str, int] = {}
        for sym, power in self._components:
            components[sym] = components.get(sym, 0) + power
        for sym, power in other._components:
            components[sym] = components.get(sym, 0) - power

        # Remove zero-power components
        components = {k: v for k, v in components.items() if v != 0}

        # Build symbol
        new_symbol = self._build_compound_symbol(components)

        return Unit(
            symbol=new_symbol,
            dimension=new_dimension,
            to_canonical_factor=new_factor,
            to_canonical_offset=Decimal("0"),
            _components=tuple(sorted(components.items())),
        )

    def __pow__(self, power: int) -> "Unit":
        """
        Raise a unit to an integer power.

        Example:
            >>> area = Unit.parse("m") ** 2
            >>> assert area.dimension == Dimension(length=2)
        """
        if not isinstance(power, int):
            raise TypeError(f"Unit power must be int, got {type(power)}")

        self._assert_linear(operation="exponentiate")
        new_dimension = self.dimension ** power
        new_factor = self.to_canonical_factor ** power

        # Scale components
        components = {sym: p * power for sym, p in self._components}
        components = {k: v for k, v in components.items() if v != 0}

        # Build symbol
        new_symbol = self._build_compound_symbol(components)

        return Unit(
            symbol=new_symbol,
            dimension=new_dimension,
            to_canonical_factor=new_factor,
            to_canonical_offset=Decimal("0"),
            _components=tuple(sorted(components.items())),
        )

    def __invert__(self) -> "Unit":
        """Return the inverse unit (reciprocal)."""
        self._assert_linear(operation="invert")
        return self ** -1

    @staticmethod
    def _build_compound_symbol(components: dict[str, int]) -> str:
        """Build a compound unit symbol from components."""
        if not components:
            return "1"

        # Separate positive and negative powers
        numerator = [(sym, p) for sym, p in sorted(components.items()) if p > 0]
        denominator = [(sym, -p) for sym, p in sorted(components.items()) if p < 0]

        def format_part(parts: list[tuple[str, int]]) -> str:
            result = []
            for sym, power in parts:
                if power == 1:
                    result.append(sym)
                else:
                    result.append(f"{sym}^{power}")
            return "*".join(result) if result else "1"

        num_str = format_part(numerator)

        if not denominator:
            return num_str if num_str != "1" else "1"

        denom_str = format_part(denominator)

        if num_str == "1":
            return f"1/{denom_str}"

        return f"{num_str}/{denom_str}"

    def __str__(self) -> str:
        """Return the unit symbol."""
        return self.symbol

    def __repr__(self) -> str:
        """Detailed representation."""
        return (
            f"Unit(symbol={self.symbol!r}, "
            f"dimension={self.dimension!r}, "
            f"to_canonical_factor={self.to_canonical_factor}, "
            f"to_canonical_offset={self.to_canonical_offset})"
        )

    def to_string(self) -> str:
        """Serialize to a string format for storage/transmission."""
        return self.symbol


# =============================================================================
# Unit Registry (Singleton)
# =============================================================================


class UnitRegistry:
    """
    Singleton registry for managing units and their definitions.

    Provides centralized access to:
    - Standard unit definitions
    - Custom unit registration
    - Unit lookup by symbol or alias
    - Currency exchange rate management

    Example:
        >>> registry = UnitRegistry.get_instance()
        >>> km = registry.get("km")
        >>> registry.set_exchange_rate("EUR", "USD", Decimal("1.10"))
    """

    _instance: ClassVar["UnitRegistry" | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        """Initialize the registry."""
        self._custom_units: dict[str, Unit] = {}
        self._exchange_rates: dict[tuple[str, str], Decimal] = {}

    @classmethod
    def get_instance(cls) -> "UnitRegistry":
        """Get the singleton registry instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get(self, symbol: str) -> Unit | None:
        """
        Look up a unit by symbol or alias.

        Args:
            symbol: The unit symbol or alias.

        Returns:
            The Unit if found, None otherwise.
        """
        # Check custom units first
        if symbol in self._custom_units:
            return self._custom_units[symbol]

        # Try to parse
        try:
            return Unit.parse(symbol)
        except UnitParseError:
            return None

    def register(self, symbol: str, unit: Unit) -> None:
        """
        Register a custom unit.

        Args:
            symbol: The symbol to register.
            unit: The Unit to associate.
        """
        self._custom_units[symbol] = unit

    def set_exchange_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate: Decimal,
    ) -> None:
        """
        Set an exchange rate between two currencies.

        Args:
            from_currency: Source currency code (e.g., "EUR").
            to_currency: Target currency code (e.g., "USD").
            rate: The exchange rate (how many target units per source unit).
        """
        self._exchange_rates[(from_currency, to_currency)] = rate
        # Also set inverse rate
        self._exchange_rates[(to_currency, from_currency)] = Decimal("1") / rate

    def get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str,
    ) -> Decimal | None:
        """
        Get the exchange rate between two currencies.

        Returns:
            The rate if available, None otherwise.
        """
        return self._exchange_rates.get((from_currency, to_currency))

    @property
    def exchange_rates(self) -> Mapping[tuple[str, str], Decimal]:
        """Get all registered exchange rates."""
        return dict(self._exchange_rates)

    def convert(
        self,
        value: float | Decimal,
        from_unit: str | Unit,
        to_unit: str | Unit,
    ) -> Decimal:
        """
        Convert a value between units using registry rates.

        Args:
            value: The value to convert.
            from_unit: Source unit (string or Unit).
            to_unit: Target unit (string or Unit).

        Returns:
            The converted value.
        """
        if isinstance(from_unit, str):
            from_unit = Unit.parse(from_unit)
        if isinstance(to_unit, str):
            to_unit = Unit.parse(to_unit)

        return from_unit.convert_to(
            to_unit,
            value,
            exchange_rates=self._exchange_rates,
        )

    def __iter__(self) -> Iterator[tuple[str, BaseUnit]]:
        """Iterate over standard units."""
        return iter(STANDARD_UNITS.items())


# =============================================================================
# Module-level convenience
# =============================================================================


def get_unit_registry() -> UnitRegistry:
    """Get the global unit registry instance."""
    return UnitRegistry.get_instance()


def parse_unit(unit_str: str) -> Unit:
    """Parse a unit string (convenience function)."""
    return Unit.parse(unit_str)
