"""
Predefined Units Library for PolicyOS.

Design principles:
1. Units are for labeling and compatibility checks only.
2. No runtime conversion logic - exchange rates are data.
3. scale is for sub-unit relationships within a dimension.
4. Unit.scale must be > 0 (used for conversion factors).
"""

from __future__ import annotations

from polisyos.foundry.methods.base import Unit


class Units:
    """Standard unit library for PolicyOS."""

    # ------------------------------------------------------------------
    # Currency (all scale=1.0; exchange rates are data)
    # ------------------------------------------------------------------
    UAH = Unit("currency", "UAH")
    USD = Unit("currency", "USD")
    EUR = Unit("currency", "EUR")
    GBP = Unit("currency", "GBP")
    JPY = Unit("currency", "JPY")
    CHF = Unit("currency", "CHF")
    CNY = Unit("currency", "CNY")
    PLN = Unit("currency", "PLN")

    # ------------------------------------------------------------------
    # Ratios (scale relative to FRACTION)
    # ------------------------------------------------------------------
    FRACTION = Unit("ratio", "1", scale=1.0)
    PERCENT = Unit("ratio", "%", scale=0.01)
    BASIS_POINTS = Unit("ratio", "bp", scale=0.0001)
    PERMILLE = Unit("ratio", "‰", scale=0.001)

    # ------------------------------------------------------------------
    # Time (scale relative to YEAR)
    # ------------------------------------------------------------------
    YEAR = Unit("time", "yr", scale=1.0)
    QUARTER = Unit("time", "qtr", scale=0.25)
    MONTH = Unit("time", "mo", scale=1 / 12)
    WEEK = Unit("time", "wk", scale=1 / 52)
    DAY = Unit("time", "day", scale=1 / 365)

    # ------------------------------------------------------------------
    # Counts / discrete
    # ------------------------------------------------------------------
    PERSONS = Unit("count", "persons")
    HOUSEHOLDS = Unit("count", "households")
    FIRMS = Unit("count", "firms")
    JOBS = Unit("count", "jobs")
    UNITS = Unit("count", "units")

    # ------------------------------------------------------------------
    # Dimensionless / index
    # ------------------------------------------------------------------
    UNITLESS = Unit("none", "1")
    INDEX = Unit("none", "idx")
    BOOLEAN = Unit("none", "bool")

    # ------------------------------------------------------------------
    # Rates (per time unit)
    # ------------------------------------------------------------------
    PER_YEAR = Unit("rate", "/yr", scale=1.0)
    PER_MONTH = Unit("rate", "/mo", scale=12.0)
    PER_DAY = Unit("rate", "/day", scale=365.0)

    # ------------------------------------------------------------------
    # Economic quantities
    # ------------------------------------------------------------------
    GDP_POINTS = Unit("gdp", "pp", scale=0.01)
    EMPLOYMENT_RATE = Unit("employment", "emp_rate")
    INFLATION_RATE = Unit("inflation", "inf_rate")


def units_compatible(a: Unit, b: Unit) -> bool:
    """Return True if units share the same dimension."""
    return a.dimension == b.dimension


def get_scale_factor(from_unit: Unit, to_unit: Unit) -> float | None:
    """
    Calculate the scale factor to convert from one unit to another.

    Returns None if units are incompatible (different dimensions).
    """
    if not units_compatible(from_unit, to_unit):
        return None
    return from_unit.scale / to_unit.scale
