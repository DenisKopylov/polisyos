"""Metric prefix enum and prefix-factor lookup table."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

__all__ = [
    "PREFIX_FACTORS",
    "MetricPrefix",
]


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
    MIO = ("Mio", Decimal("1e6"))  # Million (common in European data)
    MRD = ("Mrd", Decimal("1e9"))  # Milliard (European billion)
    BN = ("Bn", Decimal("1e9"))  # Billion (US)
    TN = ("Tn", Decimal("1e12"))  # Trillion

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
    def from_symbol(cls, symbol: str) -> MetricPrefix | None:
        """Look up a prefix by its symbol."""
        for prefix in cls:
            if prefix.symbol == symbol:
                return prefix
        return None


# Prefix lookup table for parsing
PREFIX_FACTORS: dict[str, Decimal] = {prefix.symbol: prefix.factor for prefix in MetricPrefix}

# Additional aliases
PREFIX_FACTORS.update(
    {
        "K": Decimal("1e3"),  # Uppercase K for kilo (common variant)
        "MM": Decimal("1e6"),  # MM for millions (financial notation)
        "B": Decimal("1e9"),  # B for billions
        "bio": Decimal("1e9"),  # bio for billions (European)
        "tril": Decimal("1e12"),  # trillion abbreviation
        "micro": Decimal("1e-6"),
        "nano": Decimal("1e-9"),
        "pico": Decimal("1e-12"),
        "u": Decimal("1e-6"),
    }
)
