"""
Tests for types module, including Units library and utility functions.
"""

from __future__ import annotations

import pytest
from polisyos.foundry.methods import Unit
from polisyos.foundry.methods.types.units import (
    Units,
    get_scale_factor,
    units_compatible,
)


class TestCurrencyUnits:
    def test_uah_exists(self):
        assert Units.UAH.dimension == "currency"
        assert Units.UAH.symbol == "UAH"
        assert Units.UAH.scale == 1.0

    def test_usd_exists(self):
        assert Units.USD.dimension == "currency"
        assert Units.USD.symbol == "USD"

    def test_eur_exists(self):
        assert Units.EUR.dimension == "currency"
        assert Units.EUR.symbol == "EUR"

    def test_all_currencies_same_scale(self):
        currencies = [Units.UAH, Units.USD, Units.EUR, Units.GBP, Units.JPY]
        for c in currencies:
            assert c.scale == 1.0


class TestRatioUnits:
    def test_fraction_is_base(self):
        assert Units.FRACTION.dimension == "ratio"
        assert Units.FRACTION.scale == 1.0

    def test_percent_scale(self):
        assert Units.PERCENT.dimension == "ratio"
        assert Units.PERCENT.symbol == "%"
        assert Units.PERCENT.scale == 0.01

    def test_basis_points_scale(self):
        assert Units.BASIS_POINTS.dimension == "ratio"
        assert Units.BASIS_POINTS.symbol == "bp"
        assert Units.BASIS_POINTS.scale == 0.0001

    def test_permille_scale(self):
        assert Units.PERMILLE.dimension == "ratio"
        assert Units.PERMILLE.scale == 0.001


class TestTimeUnits:
    def test_year_is_base(self):
        assert Units.YEAR.dimension == "time"
        assert Units.YEAR.scale == 1.0

    def test_quarter_scale(self):
        assert Units.QUARTER.dimension == "time"
        assert Units.QUARTER.scale == 0.25

    def test_month_scale(self):
        assert Units.MONTH.dimension == "time"
        assert Units.MONTH.scale == pytest.approx(1 / 12)

    def test_week_scale(self):
        assert Units.WEEK.dimension == "time"
        assert Units.WEEK.scale == pytest.approx(1 / 52)

    def test_day_scale(self):
        assert Units.DAY.dimension == "time"
        assert Units.DAY.scale == pytest.approx(1 / 365)


class TestCountUnits:
    def test_persons_exists(self):
        assert Units.PERSONS.dimension == "count"
        assert Units.PERSONS.symbol == "persons"

    def test_households_exists(self):
        assert Units.HOUSEHOLDS.dimension == "count"
        assert Units.HOUSEHOLDS.symbol == "households"

    def test_firms_exists(self):
        assert Units.FIRMS.dimension == "count"
        assert Units.FIRMS.symbol == "firms"


class TestDimensionlessUnits:
    def test_unitless_exists(self):
        assert Units.UNITLESS.dimension == "none"
        assert Units.UNITLESS.symbol == "1"

    def test_index_exists(self):
        assert Units.INDEX.dimension == "none"
        assert Units.INDEX.symbol == "idx"

    def test_boolean_exists(self):
        assert Units.BOOLEAN.dimension == "none"
        assert Units.BOOLEAN.symbol == "bool"


class TestUnitsCompatible:
    def test_same_unit_compatible(self):
        assert units_compatible(Units.USD, Units.USD)
        assert units_compatible(Units.PERCENT, Units.PERCENT)

    def test_same_dimension_compatible(self):
        assert units_compatible(Units.USD, Units.EUR)
        assert units_compatible(Units.PERCENT, Units.FRACTION)
        assert units_compatible(Units.YEAR, Units.MONTH)
        assert units_compatible(Units.PERSONS, Units.HOUSEHOLDS)

    def test_different_dimension_incompatible(self):
        assert not units_compatible(Units.USD, Units.PERCENT)
        assert not units_compatible(Units.YEAR, Units.PERSONS)
        assert not units_compatible(Units.FRACTION, Units.UAH)
        assert not units_compatible(Units.UNITLESS, Units.USD)

    def test_custom_units_compatibility(self):
        energy1 = Unit("energy", "kWh")
        energy2 = Unit("energy", "MWh", scale=1000.0)
        mass = Unit("mass", "kg")
        assert units_compatible(energy1, energy2)
        assert not units_compatible(energy1, mass)


class TestGetScaleFactor:
    def test_same_unit_scale_one(self):
        assert get_scale_factor(Units.USD, Units.USD) == 1.0
        assert get_scale_factor(Units.PERCENT, Units.PERCENT) == 1.0

    def test_percent_to_fraction(self):
        factor = get_scale_factor(Units.PERCENT, Units.FRACTION)
        assert factor == pytest.approx(0.01)

    def test_fraction_to_percent(self):
        factor = get_scale_factor(Units.FRACTION, Units.PERCENT)
        assert factor == pytest.approx(100.0)

    def test_month_to_year(self):
        factor = get_scale_factor(Units.MONTH, Units.YEAR)
        assert factor == pytest.approx(1 / 12)

    def test_year_to_month(self):
        factor = get_scale_factor(Units.YEAR, Units.MONTH)
        assert factor == pytest.approx(12.0)

    def test_incompatible_returns_none(self):
        assert get_scale_factor(Units.USD, Units.PERCENT) is None
        assert get_scale_factor(Units.YEAR, Units.PERSONS) is None


class TestCustomUnits:
    def test_create_custom_unit(self):
        energy = Unit("energy", "kWh", scale=1.0)
        assert energy.dimension == "energy"
        assert energy.symbol == "kWh"
        assert energy.scale == 1.0

    def test_custom_unit_hashable(self):
        energy = Unit("energy", "kWh")
        assert isinstance(hash(energy), int)

    def test_custom_unit_in_dict(self):
        kwh = Unit("energy", "kWh")
        mwh = Unit("energy", "MWh", scale=1000.0)
        conversions = {
            kwh: "kilowatt-hours",
            mwh: "megawatt-hours",
        }
        assert conversions[kwh] == "kilowatt-hours"
        assert conversions[mwh] == "megawatt-hours"

    def test_custom_unit_compatible_with_builtin(self):
        custom_currency = Unit("currency", "BTC")
        assert units_compatible(custom_currency, Units.USD)

    def test_custom_unit_scale_factor(self):
        kwh = Unit("energy", "kWh", scale=1.0)
        mwh = Unit("energy", "MWh", scale=1000.0)
        factor = get_scale_factor(kwh, mwh)
        assert factor == pytest.approx(0.001)
        factor = get_scale_factor(mwh, kwh)
        assert factor == pytest.approx(1000.0)


class TestUnitRepr:
    def test_repr_without_scale(self):
        unit = Unit("currency", "USD")
        r = repr(unit)
        assert "currency" in r
        assert "USD" in r
        assert "scale=" not in r

    def test_repr_with_scale(self):
        unit = Unit("ratio", "%", scale=0.01)
        r = repr(unit)
        assert "scale=" in r
        assert "0.01" in r
