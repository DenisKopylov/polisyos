"""Core Unit class with parsing, compatibility, conversion, and arithmetic."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from functools import cached_property
from typing import Mapping

from polisyos.fabric.connectors.types.dimensions import Dimension

from ._units_base import (
    BaseUnit,
    ConversionFactor,
    STANDARD_UNITS,
    SUPERSCRIPT_MAP,
)
from ._units_errors import UnitConversionError, UnitParseError
from ._units_prefixes import PREFIX_FACTORS

__all__ = [
    "Unit",
]


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
            while idx > 0 and unit_str[idx - 1] in SUPERSCRIPT_MAP:
                idx -= 1
            if idx < len(unit_str):
                exp_str = "".join(SUPERSCRIPT_MAP[ch] for ch in unit_str[idx:])
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
