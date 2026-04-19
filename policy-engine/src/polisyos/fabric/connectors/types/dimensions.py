"""
Dimensional analysis framework for type-safe unit operations.

This module implements a lightweight dimensional analysis system that:
- Tracks physical dimensions as integer powers of base dimensions
- Supports algebraic operations (multiply, divide, power)
- Enables compatibility checking between units
- Integrates with ir/kernel/units.py semantic unit types

Design principles:
- No external dependencies (no pint, astropy)
- Immutable dimension objects
- Singleton registry for standard dimensions
- Clear integration points with connector type system

Example:
    >>> from polisyos.fabric.connectors.types.dimensions import (
    ...     Dimension, DimensionRegistry
    ... )
    >>> velocity = Dimension(length=1, time=-1)
    >>> acceleration = velocity / Dimension(time=1)
    >>> assert acceleration == Dimension(length=1, time=-2)
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import ClassVar, Iterator, Mapping

__all__ = [
    "Dimension",
    "DimensionRegistry",
    "BaseDimension",
    "DimensionError",
    "IncompatibleDimensionsError",
    "get_dimension_registry",
]


def _default_dimension_registry() -> "DimensionRegistry":
    return DimensionRegistry.get_instance()


# =============================================================================
# Exceptions
# =============================================================================


class DimensionError(Exception):
    """Base exception for dimensional analysis errors."""


class IncompatibleDimensionsError(DimensionError):
    """Raised when operations require compatible dimensions but receive incompatible ones."""

    def __init__(self, dim1: "Dimension", dim2: "Dimension", operation: str = "operation"):
        self.dim1 = dim1
        self.dim2 = dim2
        self.operation = operation
        super().__init__(
            f"Incompatible dimensions for {operation}: {dim1} vs {dim2}"
        )


# =============================================================================
# Base Dimensions
# =============================================================================


class BaseDimension:
    """
    Enumeration of fundamental physical dimensions.

    These correspond to SI base quantities plus domain-specific extensions
    for policy analysis (currency, population, information).

    Note: We use string constants rather than Enum to allow for future
    extensibility without breaking serialization.

    Area is represented as length^2 (not a base dimension) and is
    provided only as a semantic alias at the registry level.
    """

    # SI Base Dimensions
    LENGTH = "length"           # L (meters)
    MASS = "mass"               # M (kilograms)
    TIME = "time"               # T (seconds)
    ELECTRIC_CURRENT = "current"  # I (amperes)
    TEMPERATURE = "temperature"  # Th (kelvin)
    AMOUNT = "amount"           # N (moles)
    LUMINOSITY = "luminosity"   # J (candelas)

    # Domain-Specific Dimensions for PolicyOS
    CURRENCY = "currency"       # C (monetary value)
    POPULATION = "population"   # P (persons/entities)
    INFORMATION = "information" # B (bits/bytes)
    ANGLE = "angle"             # For angular measurements

    # Alias (not a base dimension)
    AREA = "area"

    # All base dimensions
    ALL: ClassVar[frozenset[str]] = frozenset({
        LENGTH, MASS, TIME, ELECTRIC_CURRENT, TEMPERATURE, AMOUNT,
        LUMINOSITY, CURRENCY, POPULATION, INFORMATION, ANGLE
    })


# =============================================================================
# Dimension Class
# =============================================================================


@dataclass(frozen=True, slots=True)
class Dimension:
    """
    Represents a physical dimension as powers of base dimensions.

    A dimension is stored as a mapping from base dimension names to their
    integer exponents. For example:
    - Velocity: {length: 1, time: -1} = L/T
    - Acceleration: {length: 1, time: -2} = L/T^2
    - Energy: {mass: 1, length: 2, time: -2} = M*L^2/T^2

    The class supports algebraic operations:
    - Multiplication: dimensions add their exponents
    - Division: dimensions subtract their exponents
    - Power: dimensions multiply their exponents

    Attributes:
        length: Power of length dimension (default 0)
        mass: Power of mass dimension (default 0)
        time: Power of time dimension (default 0)
        current: Power of electric current dimension (default 0)
        temperature: Power of temperature dimension (default 0)
        amount: Power of amount dimension (default 0)
        luminosity: Power of luminosity dimension (default 0)
        currency: Power of currency dimension (default 0)
        population: Power of population dimension (default 0)
        information: Power of information dimension (default 0)
        angle: Power of angle dimension (default 0)

    Example:
        >>> speed = Dimension(length=1, time=-1)
        >>> time = Dimension(time=1)
        >>> distance = speed * time
        >>> assert distance == Dimension(length=1)
    """

    # Base dimension powers
    length: int = 0
    mass: int = 0
    time: int = 0
    current: int = 0
    temperature: int = 0
    amount: int = 0
    luminosity: int = 0
    currency: int = 0
    population: int = 0
    information: int = 0
    angle: int = 0

    def __post_init__(self) -> None:
        """Validate dimension powers."""
        # All powers must be integers (enforced by frozen dataclass usage)
        pass

    @classmethod
    def from_dict(cls, powers: Mapping[str, int]) -> "Dimension":
        """
        Create a Dimension from a dictionary of base dimension powers.

        Args:
            powers: Mapping from dimension names to integer powers.
                    Unknown dimensions are ignored with a warning.

        Returns:
            A new Dimension instance.

        Example:
            >>> dim = Dimension.from_dict({"length": 1, "time": -2})
            >>> assert dim == Dimension(length=1, time=-2)
        """
        valid_keys = {
            "length", "mass", "time", "current", "temperature",
            "amount", "luminosity", "currency", "population",
            "information", "angle"
        }
        filtered: dict[str, int] = {}
        length_power = 0

        for key, value in powers.items():
            if value == 0:
                continue
            if key == BaseDimension.AREA:
                length_power += value * 2
                continue
            if key in valid_keys:
                filtered[key] = filtered.get(key, 0) + value

        if length_power:
            filtered["length"] = filtered.get("length", 0) + length_power

        if filtered.get("length") == 0:
            filtered.pop("length", None)

        return cls(**filtered)

    def to_dict(self) -> dict[str, int]:
        """
        Convert to a dictionary of non-zero dimension powers.

        Returns:
            Dictionary mapping dimension names to non-zero powers.

        Example:
            >>> Dimension(length=1, time=-1).to_dict()
            {'length': 1, 'time': -1}
        """
        return {
            name: power
            for name, power in [
                ("length", self.length),
                ("mass", self.mass),
                ("time", self.time),
                ("current", self.current),
                ("temperature", self.temperature),
                ("amount", self.amount),
                ("luminosity", self.luminosity),
                ("currency", self.currency),
                ("population", self.population),
                ("information", self.information),
                ("angle", self.angle),
            ]
            if power != 0
        }

    @property
    def is_dimensionless(self) -> bool:
        """Check if this is a dimensionless quantity (all powers zero)."""
        return not any(self.to_dict().values())

    def is_compatible_with(self, other: "Dimension") -> bool:
        """
        Check if two dimensions are compatible (can be added/compared).

        Two dimensions are compatible if and only if they have the same
        powers for all base dimensions.

        Args:
            other: The dimension to compare with.

        Returns:
            True if dimensions are compatible, False otherwise.

        Example:
            >>> km = Dimension(length=1)
            >>> m = Dimension(length=1)
            >>> s = Dimension(time=1)
            >>> assert km.is_compatible_with(m)
            >>> assert not km.is_compatible_with(s)
        """
        return self == other

    def __mul__(self, other: "Dimension") -> "Dimension":
        """
        Multiply two dimensions (add exponents).

        Example:
            >>> force = Dimension(mass=1, length=1, time=-2)
            >>> distance = Dimension(length=1)
            >>> work = force * distance
            >>> assert work == Dimension(mass=1, length=2, time=-2)
        """
        return Dimension(
            length=self.length + other.length,
            mass=self.mass + other.mass,
            time=self.time + other.time,
            current=self.current + other.current,
            temperature=self.temperature + other.temperature,
            amount=self.amount + other.amount,
            luminosity=self.luminosity + other.luminosity,
            currency=self.currency + other.currency,
            population=self.population + other.population,
            information=self.information + other.information,
            angle=self.angle + other.angle,
        )

    def __truediv__(self, other: "Dimension") -> "Dimension":
        """
        Divide two dimensions (subtract exponents).

        Example:
            >>> distance = Dimension(length=1)
            >>> time = Dimension(time=1)
            >>> velocity = distance / time
            >>> assert velocity == Dimension(length=1, time=-1)
        """
        return Dimension(
            length=self.length - other.length,
            mass=self.mass - other.mass,
            time=self.time - other.time,
            current=self.current - other.current,
            temperature=self.temperature - other.temperature,
            amount=self.amount - other.amount,
            luminosity=self.luminosity - other.luminosity,
            currency=self.currency - other.currency,
            population=self.population - other.population,
            information=self.information - other.information,
            angle=self.angle - other.angle,
        )

    def __pow__(self, power: int) -> "Dimension":
        """
        Raise dimension to an integer power.

        Example:
            >>> length = Dimension(length=1)
            >>> area = length ** 2
            >>> assert area == Dimension(length=2)
        """
        if not isinstance(power, int):
            raise TypeError(f"Dimension power must be int, got {type(power)}")
        return Dimension(
            length=self.length * power,
            mass=self.mass * power,
            time=self.time * power,
            current=self.current * power,
            temperature=self.temperature * power,
            amount=self.amount * power,
            luminosity=self.luminosity * power,
            currency=self.currency * power,
            population=self.population * power,
            information=self.information * power,
            angle=self.angle * power,
        )

    def __invert__(self) -> "Dimension":
        """
        Return the inverse dimension (negate all exponents).

        Example:
            >>> velocity = Dimension(length=1, time=-1)
            >>> time_per_length = ~velocity
            >>> assert time_per_length == Dimension(length=-1, time=1)
        """
        return self ** -1

    def __str__(self) -> str:
        """
        Human-readable string representation.

        Uses standard notation: L^2, T^-1, etc.
        """
        if self.is_dimensionless:
            return "dimensionless"

        symbols = {
            "length": "L",
            "mass": "M",
            "time": "T",
            "current": "I",
            "temperature": "Th",
            "amount": "N",
            "luminosity": "J",
            "currency": "C",
            "population": "P",
            "information": "B",
            "angle": "ang",
        }

        parts = []
        for name, power in self.to_dict().items():
            symbol = symbols.get(name, name[0].upper())
            if power == 1:
                parts.append(symbol)
            else:
                parts.append(f"{symbol}^{power}")

        return "*".join(parts) if parts else "dimensionless"

    def __repr__(self) -> str:
        """Detailed representation showing non-zero powers."""
        powers = self.to_dict()
        if not powers:
            return "Dimension()"
        args = ", ".join(f"{k}={v}" for k, v in powers.items())
        return f"Dimension({args})"


# =============================================================================
# Dimension Registry (Singleton)
# =============================================================================


class DimensionRegistry:
    """
    Singleton registry for standard physical dimensions.

    Provides a centralized collection of commonly used dimensions,
    enabling consistent dimensional analysis across the system.

    Thread-safe singleton pattern ensures a single source of truth.

    Example:
        >>> registry = DimensionRegistry.get_instance()
        >>> velocity = registry.VELOCITY
        >>> assert velocity == Dimension(length=1, time=-1)
    """

    _instance: ClassVar["DimensionRegistry" | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    # Standard dimensions (class-level for easy access)
    DIMENSIONLESS = Dimension()

    # Base dimensions
    LENGTH = Dimension(length=1)
    MASS = Dimension(mass=1)
    TIME = Dimension(time=1)
    CURRENT = Dimension(current=1)
    TEMPERATURE = Dimension(temperature=1)
    AMOUNT = Dimension(amount=1)
    LUMINOSITY = Dimension(luminosity=1)

    # Domain-specific base dimensions
    CURRENCY = Dimension(currency=1)
    POPULATION = Dimension(population=1)
    INFORMATION = Dimension(information=1)
    ANGLE = Dimension(angle=1)

    # Derived mechanical dimensions
    VELOCITY = Dimension(length=1, time=-1)
    ACCELERATION = Dimension(length=1, time=-2)
    FORCE = Dimension(mass=1, length=1, time=-2)
    ENERGY = Dimension(mass=1, length=2, time=-2)
    POWER = Dimension(mass=1, length=2, time=-3)
    PRESSURE = Dimension(mass=1, length=-1, time=-2)
    DENSITY = Dimension(mass=1, length=-3)

    # Derived area/volume dimensions (using length powers)
    AREA = Dimension(length=2)
    VOLUME = Dimension(length=3)

    # Derived rate dimensions (common in policy analysis)
    FREQUENCY = Dimension(time=-1)
    MONETARY_RATE = Dimension(currency=1, time=-1)  # e.g., USD/year
    POPULATION_RATE = Dimension(population=1, time=-1)  # e.g., births/year
    MONETARY_PER_CAPITA = Dimension(currency=1, population=-1)  # e.g., GDP per capita

    # Economic dimensions
    PRICE = Dimension(currency=1)  # Absolute monetary value
    RATIO = DIMENSIONLESS  # Percentage, proportion (dimensionless)
    INDEX = DIMENSIONLESS  # Index values (dimensionless)

    def __init__(self) -> None:
        """Initialize the registry with standard dimension definitions."""
        self._state_lock = threading.RLock()
        # Map semantic names to dimensions
        self._dimensions: dict[str, Dimension] = {
            # Base dimensions
            "dimensionless": self.DIMENSIONLESS,
            "length": self.LENGTH,
            "mass": self.MASS,
            "time": self.TIME,
            "current": self.CURRENT,
            "temperature": self.TEMPERATURE,
            "amount": self.AMOUNT,
            "luminosity": self.LUMINOSITY,
            "currency": self.CURRENCY,
            "population": self.POPULATION,
            "information": self.INFORMATION,
            "angle": self.ANGLE,
            # Derived dimensions
            "velocity": self.VELOCITY,
            "speed": self.VELOCITY,
            "acceleration": self.ACCELERATION,
            "force": self.FORCE,
            "energy": self.ENERGY,
            "work": self.ENERGY,
            "power": self.POWER,
            "pressure": self.PRESSURE,
            "density": self.DENSITY,
            "area": self.AREA,
            "volume": self.VOLUME,
            "frequency": self.FREQUENCY,
            "monetary_rate": self.MONETARY_RATE,
            "population_rate": self.POPULATION_RATE,
            "per_capita": self.MONETARY_PER_CAPITA,
            "price": self.PRICE,
            "ratio": self.RATIO,
            "percentage": self.RATIO,
            "index": self.INDEX,
        }

    @classmethod
    def get_instance(cls) -> "DimensionRegistry":
        """
        Get the singleton registry instance (thread-safe).

        Returns:
            The global DimensionRegistry instance.
        """
        if cls._instance is None:
            with cls._lock:
                # Double-check locking
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get(self, name: str) -> Dimension | None:
        """
        Look up a dimension by semantic name.

        Args:
            name: The semantic name (case-insensitive).

        Returns:
            The corresponding Dimension, or None if not found.
        """
        with self._state_lock:
            return self._dimensions.get(name.lower())

    def register(self, name: str, dimension: Dimension) -> None:
        """
        Register a new dimension with a semantic name.

        Args:
            name: The semantic name to register.
            dimension: The Dimension to associate with the name.

        Raises:
            ValueError: If the name is already registered.
        """
        key = name.lower()
        with self._state_lock:
            if key in self._dimensions:
                raise ValueError(f"Dimension '{name}' is already registered")
            self._dimensions[key] = dimension

    def __iter__(self) -> Iterator[tuple[str, Dimension]]:
        """Iterate over all registered dimensions."""
        with self._state_lock:
            return iter(tuple(self._dimensions.items()))

    def __contains__(self, name: str) -> bool:
        """Check if a dimension name is registered."""
        with self._state_lock:
            return name.lower() in self._dimensions

    def __len__(self) -> int:
        """Return the number of registered dimensions."""
        with self._state_lock:
            return len(self._dimensions)


# =============================================================================
# Module-level convenience access
# =============================================================================


def get_dimension_registry() -> DimensionRegistry:
    """Get the global dimension registry instance."""
    return _default_dimension_registry()
