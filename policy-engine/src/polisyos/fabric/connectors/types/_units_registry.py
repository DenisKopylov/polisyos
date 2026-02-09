"""Singleton UnitRegistry with exchange rate management and convenience functions."""
from __future__ import annotations

import threading
from decimal import Decimal
from typing import ClassVar, Iterator, Mapping

from ._units_base import BaseUnit, STANDARD_UNITS
from ._units_core import Unit
from ._units_errors import UnitParseError

__all__ = [
    "UnitRegistry",
    "get_unit_registry",
    "parse_unit",
]


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
