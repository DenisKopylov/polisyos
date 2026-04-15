"""Base unit definitions, standard units registry, and conversion factors."""
from __future__ import annotations

from decimal import Decimal, localcontext
from typing import NamedTuple

from polisyos.fabric.connectors.types.dimensions import (
    Dimension,
    DimensionRegistry,
)

__all__ = [
    "BaseUnit",
    "STANDARD_UNITS",
    "ConversionFactor",
    "SUPERSCRIPT_MAP",
]


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


SUPERSCRIPT_MAP = {
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
        "lb": BaseUnit("lb", registry.MASS, Decimal("0.45359237"), ("pound", "pounds", "lbs"), "mass"),
        "oz": BaseUnit("oz", registry.MASS, Decimal("0.028349523125"), ("ounce", "ounces"), "mass"),
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
        "USD": BaseUnit("USD", registry.CURRENCY, Decimal("1"), ("usd", "dollar", "dollars", "$"), "currency"),
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
    with localcontext() as ctx:
        ctx.prec = max(ctx.prec, 50)
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
        if self.multiplier == 0:
            raise ZeroDivisionError("conversion multiplier cannot be zero")
        with localcontext() as ctx:
            ctx.prec = max(ctx.prec, 50)
            inverse_multiplier = Decimal("1") / self.multiplier
            inverse_offset = -(self.offset / self.multiplier)
        return ConversionFactor(
            multiplier=inverse_multiplier,
            offset=inverse_offset,
            requires_rate=self.requires_rate,
        )
