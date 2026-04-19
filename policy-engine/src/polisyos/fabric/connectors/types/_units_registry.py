"""Singleton UnitRegistry with exchange rate management and convenience functions."""
from __future__ import annotations

import threading
from decimal import Decimal, InvalidOperation, localcontext
from types import MappingProxyType
from typing import ClassVar, Iterator, Mapping

from ._units_base import STANDARD_UNITS, BaseUnit
from ._units_core import Unit
from ._units_errors import UnitParseError

__all__ = [
    "UnitRegistry",
    "get_unit_registry",
    "parse_unit",
]


def _default_unit_registry() -> "UnitRegistry":
    return UnitRegistry.get_instance()


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
        self._state_lock = threading.RLock()

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
        with self._state_lock:
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
        with self._state_lock:
            self._custom_units[symbol] = unit

    @staticmethod
    def _normalize_currency_code(currency: str) -> str:
        code = str(currency).strip().upper()
        if not code:
            raise ValueError("currency code cannot be empty")
        return code

    @staticmethod
    def _normalize_exchange_rate(rate: Decimal) -> Decimal:
        try:
            normalized = rate if isinstance(rate, Decimal) else Decimal(str(rate))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("exchange rate must be a finite Decimal-compatible value") from exc
        if not normalized.is_finite() or normalized <= 0:
            raise ValueError("exchange rate must be positive and finite")
        return normalized

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
        normalized_from = self._normalize_currency_code(from_currency)
        normalized_to = self._normalize_currency_code(to_currency)
        normalized_rate = self._normalize_exchange_rate(rate)

        if normalized_from == normalized_to:
            normalized_rate = Decimal("1")

        with self._state_lock:
            with localcontext() as ctx:
                ctx.prec = max(ctx.prec, 50)
                inverse_rate = Decimal("1") / normalized_rate
            self._exchange_rates[(normalized_from, normalized_to)] = normalized_rate
            self._exchange_rates[(normalized_to, normalized_from)] = inverse_rate

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
        normalized_from = self._normalize_currency_code(from_currency)
        normalized_to = self._normalize_currency_code(to_currency)
        with self._state_lock:
            return self._exchange_rates.get((normalized_from, normalized_to))

    @property
    def exchange_rates(self) -> Mapping[tuple[str, str], Decimal]:
        """Get all registered exchange rates."""
        with self._state_lock:
            return MappingProxyType(dict(self._exchange_rates))

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

        with self._state_lock:
            exchange_rates = dict(self._exchange_rates)

        return from_unit.convert_to(
            to_unit,
            value,
            exchange_rates=exchange_rates,
        )

    def __iter__(self) -> Iterator[tuple[str, BaseUnit]]:
        """Iterate over standard units."""
        return iter(STANDARD_UNITS.items())


# =============================================================================
# Module-level convenience
# =============================================================================


def get_unit_registry() -> UnitRegistry:
    """Get the global unit registry instance."""
    return _default_unit_registry()


def parse_unit(unit_str: str) -> Unit:
    """Parse a unit string (convenience function)."""
    return Unit.parse(unit_str)
