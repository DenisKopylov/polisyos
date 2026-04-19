"""
Comprehensive tests for the Type System & Units Layer (Phase 2.4).

Tests cover:
1. Dimensional Analysis - Dimension algebra and compatibility
2. Unit Algebra - Parsing, conversion, compatibility
3. Temporal Semantics - Stock/Flow aggregation rules
4. Type Coercion - Safe casting with precision protection

Test Categories:
- Unit tests: Individual function/class behavior
- Integration tests: Cross-module interactions
- Edge cases: Boundary conditions and error handling
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import warnings

import pytest

# =============================================================================
# Import modules under test
# =============================================================================

from polisyos.fabric.connectors.types.dimensions import (
    Dimension,
    DimensionRegistry,
    get_dimension_registry,
)

from polisyos.fabric.connectors.types.units import (
    Unit,
    UnitParseError,
    UnitConversionError,
    get_unit_registry,
)

from polisyos.fabric.connectors.types.temporal import (
    TemporalType,
    TimeGrain,
    AggregationMethod,
    TemporalVariable,
    TimeInterval,
    StockFlowCombination,
    TemporalAggregationError,
    infer_temporal_type,
)

from polisyos.fabric.connectors.types.coercion import (
    TypeCoercion,
    CoercionPolicy,
    CoercionError,
    PrecisionLossWarning,
    safe_cast,
    can_safely_cast,
    get_coercion_path,
)


# =============================================================================
# SECTION 1: Dimensional Analysis Tests
# =============================================================================


class TestDimension:
    """Tests for the Dimension class."""

    def test_dimensionless_creation(self):
        """Test creating a dimensionless dimension."""
        dim = Dimension()
        assert dim.is_dimensionless
        assert dim.to_dict() == {}
        assert str(dim) == "dimensionless"

    def test_single_dimension(self):
        """Test creating single-dimension quantities."""
        length = Dimension(length=1)
        assert not length.is_dimensionless
        assert length.to_dict() == {"length": 1}
        assert "L" in str(length)

    def test_compound_dimension(self):
        """Test creating compound dimensions."""
        velocity = Dimension(length=1, time=-1)
        assert velocity.to_dict() == {"length": 1, "time": -1}
        assert "L" in str(velocity)
        assert "T" in str(velocity)

    def test_from_dict(self):
        """Test creating dimension from dictionary."""
        dim = Dimension.from_dict({"length": 2, "time": -2})
        assert dim == Dimension(length=2, time=-2)

    def test_from_dict_ignores_unknown(self):
        """Test that unknown dimensions are ignored."""
        dim = Dimension.from_dict({"length": 1, "unknown": 5})
        assert dim == Dimension(length=1)

    def test_from_dict_area_alias(self):
        """Test that area is normalized to length^2."""
        dim = Dimension.from_dict({"area": 1})
        assert dim == Dimension(length=2)

    def test_multiplication(self):
        """Test dimension multiplication (exponent addition)."""
        length = Dimension(length=1)
        area = length * length
        assert area == Dimension(length=2)

        # Force * distance = energy
        force = Dimension(mass=1, length=1, time=-2)
        distance = Dimension(length=1)
        energy = force * distance
        assert energy == Dimension(mass=1, length=2, time=-2)

    def test_division(self):
        """Test dimension division (exponent subtraction)."""
        distance = Dimension(length=1)
        time = Dimension(time=1)
        velocity = distance / time
        assert velocity == Dimension(length=1, time=-1)

        # Velocity / time = acceleration
        acceleration = velocity / time
        assert acceleration == Dimension(length=1, time=-2)

    def test_power(self):
        """Test raising dimension to a power."""
        length = Dimension(length=1)
        volume = length ** 3
        assert volume == Dimension(length=3)

        # Negative power
        inverse_length = length ** -1
        assert inverse_length == Dimension(length=-1)

    def test_inversion(self):
        """Test dimension inversion."""
        velocity = Dimension(length=1, time=-1)
        slowness = ~velocity
        assert slowness == Dimension(length=-1, time=1)

    def test_compatibility_same(self):
        """Test that identical dimensions are compatible."""
        dim1 = Dimension(length=1, time=-1)
        dim2 = Dimension(length=1, time=-1)
        assert dim1.is_compatible_with(dim2)

    def test_compatibility_different(self):
        """Test that different dimensions are incompatible."""
        velocity = Dimension(length=1, time=-1)
        force = Dimension(mass=1, length=1, time=-2)
        assert not velocity.is_compatible_with(force)

    def test_equality(self):
        """Test dimension equality."""
        assert Dimension(length=1) == Dimension(length=1)
        assert Dimension(length=1) != Dimension(length=2)
        assert Dimension(length=1, time=0) == Dimension(length=1)

    def test_power_type_error(self):
        """Test that non-integer powers raise TypeError."""
        dim = Dimension(length=1)
        with pytest.raises(TypeError):
            dim ** 1.5  # type: ignore


class TestDimensionRegistry:
    """Tests for the DimensionRegistry singleton."""

    def test_singleton_pattern(self):
        """Test that registry is a singleton."""
        reg1 = DimensionRegistry.get_instance()
        reg2 = DimensionRegistry.get_instance()
        assert reg1 is reg2

    def test_standard_dimensions_exist(self):
        """Test that standard dimensions are registered."""
        registry = DimensionRegistry.get_instance()

        assert registry.get("length") is not None
        assert registry.get("mass") is not None
        assert registry.get("time") is not None
        assert registry.get("velocity") is not None
        assert registry.get("energy") is not None

    def test_lookup_case_insensitive(self):
        """Test that lookup is case-insensitive."""
        registry = DimensionRegistry.get_instance()

        assert registry.get("LENGTH") == registry.get("length")
        assert registry.get("Velocity") == registry.get("velocity")

    def test_velocity_dimension(self):
        """Test that velocity dimension is correctly defined."""
        registry = DimensionRegistry.get_instance()
        velocity = registry.get("velocity")
        assert velocity == Dimension(length=1, time=-1)

    def test_area_dimension_alias(self):
        """Test that area maps to length^2."""
        registry = DimensionRegistry.get_instance()
        area = registry.get("area")
        assert area == Dimension(length=2)

    def test_energy_dimension(self):
        """Test that energy dimension is correctly defined."""
        registry = DimensionRegistry.get_instance()
        energy = registry.get("energy")
        assert energy == Dimension(mass=1, length=2, time=-2)

    def test_contains(self):
        """Test __contains__ method."""
        registry = DimensionRegistry.get_instance()
        assert "length" in registry
        assert "unknown" not in registry


# =============================================================================
# SECTION 2: Unit Algebra Tests
# =============================================================================


class TestUnit:
    """Tests for the Unit class."""

    def test_parse_simple_unit(self):
        """Test parsing simple units."""
        meter = Unit.parse("m")
        assert meter.symbol == "m"
        assert meter.dimension == Dimension(length=1)

        second = Unit.parse("s")
        assert second.dimension == Dimension(time=1)

    def test_parse_prefixed_unit(self):
        """Test parsing units with metric prefixes."""
        km = Unit.parse("km")
        assert km.dimension == Dimension(length=1)
        assert km.to_canonical_factor == Decimal("1000")

        ms = Unit.parse("ms")
        assert ms.dimension == Dimension(time=1)
        assert ms.to_canonical_factor == Decimal("0.001")

    def test_parse_prefix_token(self):
        """Test parsing prefix token + unit token (e.g., Mio EUR)."""
        mio_eur = Unit.parse("Mio EUR")
        assert mio_eur.dimension == Dimension(currency=1)
        assert mio_eur.to_canonical_factor == Decimal("1e6")

        mm_usd = Unit.parse("MM USD")
        assert mm_usd.dimension == Dimension(currency=1)
        assert mm_usd.to_canonical_factor == Decimal("1e6")

    def test_parse_compound_unit_division(self):
        """Test parsing compound units with division."""
        kmh = Unit.parse("km/h")
        assert kmh.dimension == Dimension(length=1, time=-1)

        ms = Unit.parse("m/s")
        assert ms.dimension == Dimension(length=1, time=-1)

    def test_parse_compound_unit_multiplication(self):
        """Test parsing compound units with multiplication."""
        newton_meter = Unit.parse("kg*m/s^2")
        # This should be force (Newton)
        assert newton_meter.dimension == Dimension(mass=1, length=1, time=-2)

    def test_parse_exponent_notation(self):
        """Test parsing units with exponents."""
        m2 = Unit.parse("m2")
        assert m2.dimension == Dimension(length=2)

        m_squared = Unit.parse("m^2")
        assert m_squared.dimension == Dimension(length=2)

    def test_parse_unicode_exponent(self):
        """Test parsing units with unicode exponents."""
        m2 = Unit.parse("m\u00b2")
        assert m2.dimension == Dimension(length=2)

    def test_parse_currency(self):
        """Test parsing currency units."""
        usd = Unit.parse("USD")
        assert usd.is_currency
        assert usd.dimension == Dimension(currency=1)

        eur = Unit.parse("EUR")
        assert eur.is_currency

    def test_parse_percentage(self):
        """Test parsing percentage units."""
        pct = Unit.parse("percent")
        assert pct.is_dimensionless
        assert pct.to_canonical_factor == Decimal("0.01")

    def test_parse_invalid_raises_error(self):
        """Test that invalid unit strings raise UnitParseError."""
        with pytest.raises(UnitParseError):
            Unit.parse("xyz_invalid_unit")

    def test_parse_empty_raises_error(self):
        """Test that empty strings raise UnitParseError."""
        with pytest.raises(UnitParseError):
            Unit.parse("")

    def test_compatibility_same_dimension(self):
        """Test that units with same dimension are compatible."""
        km = Unit.parse("km")
        m = Unit.parse("m")
        assert km.is_compatible_with(m)

        kmh = Unit.parse("km/h")
        ms = Unit.parse("m/s")
        assert kmh.is_compatible_with(ms)

    def test_compatibility_different_dimension(self):
        """Test that units with different dimensions are incompatible."""
        km = Unit.parse("km")
        s = Unit.parse("s")
        assert not km.is_compatible_with(s)

    def test_conversion_length(self):
        """Test converting between length units."""
        km = Unit.parse("km")
        m = Unit.parse("m")

        # 1.5 km = 1500 m
        result = km.convert_to(m, Decimal("1.5"))
        assert result == Decimal("1500")

        # 1000 m = 1 km
        result = m.convert_to(km, Decimal("1000"))
        assert result == Decimal("1")

    def test_conversion_time(self):
        """Test converting between time units."""
        hour = Unit.parse("h")
        second = Unit.parse("s")

        # 1 hour = 3600 seconds
        result = hour.convert_to(second, Decimal("1"))
        assert result == Decimal("3600")

    def test_conversion_compound(self):
        """Test converting compound units (velocity)."""
        kmh = Unit.parse("km/h")
        ms = Unit.parse("m/s")

        # 90 km/h = 25 m/s
        result = kmh.convert_to(ms, Decimal("90"))
        assert result == Decimal("25")

    def test_conversion_incompatible_raises_error(self):
        """Test that converting incompatible units raises error."""
        km = Unit.parse("km")
        s = Unit.parse("s")

        with pytest.raises(UnitConversionError):
            km.convert_to(s, 100)

    def test_temperature_conversion_celsius_to_kelvin(self):
        """Test temperature conversion with offsets."""
        degc = Unit.parse("degC")
        kelvin = Unit.parse("K")
        result = degc.convert_to(kelvin, Decimal("0"))
        assert result == Decimal("273.15")

    def test_temperature_conversion_fahrenheit_to_celsius(self):
        """Test temperature conversion with offsets (degF -> degC)."""
        degf = Unit.parse("degF")
        degc = Unit.parse("degC")
        result = degf.convert_to(degc, Decimal("32"))
        assert abs(result) < Decimal("1e-20")

    def test_currency_conversion_with_scale(self):
        """Test currency conversion preserves prefix scaling."""
        registry = get_unit_registry()
        registry.set_exchange_rate("EUR", "USD", Decimal("1.10"))

        mio_eur = Unit.parse("Mio EUR")
        usd = Unit.parse("USD")
        result = mio_eur.convert_to(usd, Decimal("2"), exchange_rates=registry.exchange_rates)
        assert result == Decimal("2200000")

    def test_multiplication(self):
        """Test unit multiplication."""
        kg = Unit.parse("kg")
        ms2 = Unit.parse("m/s^2")

        newton = kg * ms2
        # kg * m/s^2 = force (Newton)
        assert newton.dimension == Dimension(mass=1, length=1, time=-2)

    def test_division(self):
        """Test unit division."""
        m = Unit.parse("m")
        s = Unit.parse("s")

        velocity = m / s
        assert velocity.dimension == Dimension(length=1, time=-1)

    def test_power(self):
        """Test raising units to powers."""
        m = Unit.parse("m")
        m3 = m ** 3
        assert m3.dimension == Dimension(length=3)

    def test_string_serialization(self):
        """Test that units can be serialized to strings."""
        unit = Unit.parse("km/h")
        string_repr = unit.to_string()
        assert isinstance(string_repr, str)

        # Should be parseable back
        reparsed = Unit.parse(string_repr)
        assert reparsed.dimension == unit.dimension


class TestUnitConversion:
    """Detailed conversion tests."""

    def test_km_to_m(self):
        """Verify 1 km = 1000 m."""
        assert Unit.parse("km").convert_to(Unit.parse("m"), 1) == Decimal("1000")

    def test_m_to_km(self):
        """Verify 1000 m = 1 km."""
        assert Unit.parse("m").convert_to(Unit.parse("km"), 1000) == Decimal("1")

    def test_hour_to_seconds(self):
        """Verify 1 h = 3600 s."""
        assert Unit.parse("h").convert_to(Unit.parse("s"), 1) == Decimal("3600")

    def test_minute_to_seconds(self):
        """Verify 1 min = 60 s."""
        assert Unit.parse("min").convert_to(Unit.parse("s"), 1) == Decimal("60")

    def test_kg_to_g(self):
        """Verify 1 kg = 1000 g."""
        assert Unit.parse("kg").convert_to(Unit.parse("g"), 1) == Decimal("1000")

    def test_percent_to_ratio(self):
        """Verify 100 percent = 1 ratio."""
        assert Unit.parse("percent").convert_to(Unit.parse("ratio"), 100) == Decimal("1")

    def test_ratio_to_percent(self):
        """Verify 1 ratio = 100 percent."""
        assert Unit.parse("ratio").convert_to(Unit.parse("percent"), 1) == Decimal("100")

    def test_ounce_conversion_uses_precise_factor(self):
        """Verify ounce conversion uses exact international avoirdupois factor."""
        result = Unit.parse("oz").convert_to(Unit.parse("g"), 1)
        assert result == Decimal("28.349523125")

    def test_affine_conversion_factor_inverse_round_trip(self):
        """Verify affine conversion factors invert cleanly."""
        factor = Unit.parse("degF").get_conversion_factor(Unit.parse("degC"))
        result = factor.inverse().apply(Decimal("0"))
        assert abs(result - Decimal("32")) < Decimal("1e-40")

    def test_velocity_kmh_to_ms(self):
        """Verify 36 km/h = 10 m/s."""
        result = Unit.parse("km/h").convert_to(Unit.parse("m/s"), 36)
        assert result == Decimal("10")

    def test_velocity_ms_to_kmh(self):
        """Verify 10 m/s = 36 km/h."""
        result = Unit.parse("m/s").convert_to(Unit.parse("km/h"), 10)
        assert result == Decimal("36")

    def test_multi_slash_parsing(self):
        """Verify left-associative parsing for multiple slashes."""
        unit = Unit.parse("m/s/s")
        assert unit.dimension == Dimension(length=1, time=-2)

        unit2 = Unit.parse("kg/m/s^2")
        assert unit2.dimension == Dimension(mass=1, length=-1, time=-2)


class TestUnitRegistry:
    """Tests for the UnitRegistry singleton."""

    def test_singleton(self):
        """Test singleton pattern."""
        reg1 = get_unit_registry()
        reg2 = get_unit_registry()
        assert reg1 is reg2

    def test_singleton_helper_override(self, monkeypatch: pytest.MonkeyPatch):
        sentinel = object()
        monkeypatch.setattr(
            "polisyos.fabric.connectors.types._units_registry._default_unit_registry",
            lambda: sentinel,
        )

        assert get_unit_registry() is sentinel

    def test_get_unit(self):
        """Test getting units from registry."""
        registry = get_unit_registry()
        m = registry.get("m")
        assert m is not None
        assert m.dimension == Dimension(length=1)

    def test_dimension_registry_helper_override(self, monkeypatch: pytest.MonkeyPatch):
        sentinel = object()
        monkeypatch.setattr(
            "polisyos.fabric.connectors.types.dimensions._default_dimension_registry",
            lambda: sentinel,
        )

        assert get_dimension_registry() is sentinel

    def test_exchange_rates(self):
        """Test setting and using exchange rates."""
        registry = get_unit_registry()

        # Set rate: 1 EUR = 1.10 USD
        registry.set_exchange_rate("EUR", "USD", Decimal("1.10"))

        # Check rate is stored
        assert registry.get_exchange_rate("EUR", "USD") == Decimal("1.10")

        # Check inverse is also stored
        assert registry.get_exchange_rate("USD", "EUR") is not None

    def test_exchange_rates_normalize_codes_and_preserve_precision(self):
        registry = get_unit_registry()
        registry.set_exchange_rate("eur", "usd", Decimal("1.234567890123456789"))

        forward = registry.get_exchange_rate("EUR", "USD")
        reverse = registry.get_exchange_rate("USD", "EUR")

        assert forward == Decimal("1.234567890123456789")
        assert reverse is not None
        round_trip = Unit.parse("USD").convert_to(
            Unit.parse("EUR"),
            Unit.parse("EUR").convert_to(
                Unit.parse("USD"),
                Decimal("2"),
                exchange_rates=registry.exchange_rates,
            ),
            exchange_rates=registry.exchange_rates,
        )
        assert abs(round_trip - Decimal("2")) < Decimal("1e-30")

    def test_convert_with_registry(self):
        """Test conversion using registry rates."""
        registry = get_unit_registry()
        registry.set_exchange_rate("EUR", "USD", Decimal("1.10"))

        # Convert 100 EUR to USD
        result = registry.convert(100, "EUR", "USD")
        assert result == Decimal("110")


# =============================================================================
# SECTION 3: Temporal Semantics Tests
# =============================================================================


class TestTemporalType:
    """Tests for the TemporalType enum."""

    def test_stock_cannot_sum(self):
        """Test that STOCK variables cannot be summed over time."""
        assert not TemporalType.STOCK.can_sum_over_time

    def test_flow_can_sum(self):
        """Test that FLOW variables can be summed over time."""
        assert TemporalType.FLOW.can_sum_over_time

    def test_stock_default_aggregation(self):
        """Test that STOCK default aggregation is LAST."""
        assert TemporalType.STOCK.get_default_aggregation() == AggregationMethod.LAST

    def test_flow_default_aggregation(self):
        """Test that FLOW default aggregation is SUM."""
        assert TemporalType.FLOW.get_default_aggregation() == AggregationMethod.SUM

    def test_stock_allowed_aggregations(self):
        """Test that STOCK allows appropriate aggregations."""
        allowed = TemporalType.STOCK.get_allowed_aggregations()

        # Should not allow SUM
        assert AggregationMethod.SUM not in allowed

        # Should allow these
        assert AggregationMethod.LAST in allowed
        assert AggregationMethod.FIRST in allowed
        assert AggregationMethod.MEAN in allowed

    def test_flow_allowed_aggregations(self):
        """Test that FLOW allows appropriate aggregations."""
        allowed = TemporalType.FLOW.get_allowed_aggregations()

        # Should allow SUM
        assert AggregationMethod.SUM in allowed

        # Should also allow MEAN
        assert AggregationMethod.MEAN in allowed

    def test_from_kernel_slot_kind(self):
        """Test mapping from kernel SlotKind."""
        assert TemporalType.from_kernel_slot_kind("stock") == TemporalType.STOCK
        assert TemporalType.from_kernel_slot_kind("flow") == TemporalType.FLOW
        assert TemporalType.from_kernel_slot_kind("parameter") == TemporalType.PARAMETER


class TestTemporalVariable:
    """Tests for the TemporalVariable class."""

    def test_stock_variable_creation(self):
        """Test creating a stock variable."""
        inventory = TemporalVariable(
            name="inventory_level",
            temporal_type=TemporalType.STOCK,
            time_grain=TimeGrain.MONTHLY,
        )

        assert not inventory.can_sum_over_time
        assert inventory.get_aggregation_method() == AggregationMethod.LAST

    def test_flow_variable_creation(self):
        """Test creating a flow variable."""
        revenue = TemporalVariable(
            name="monthly_revenue",
            temporal_type=TemporalType.FLOW,
            time_grain=TimeGrain.MONTHLY,
        )

        assert revenue.can_sum_over_time
        assert revenue.get_aggregation_method() == AggregationMethod.SUM

    def test_validate_aggregation_stock_sum_fails(self):
        """Test that validating SUM on STOCK raises error."""
        inventory = TemporalVariable(
            name="inventory",
            temporal_type=TemporalType.STOCK,
        )

        with pytest.raises(TemporalAggregationError):
            inventory.validate_aggregation(AggregationMethod.SUM)

    def test_validate_aggregation_flow_sum_succeeds(self):
        """Test that validating SUM on FLOW succeeds."""
        revenue = TemporalVariable(
            name="revenue",
            temporal_type=TemporalType.FLOW,
        )

        # Should not raise
        revenue.validate_aggregation(AggregationMethod.SUM)

    def test_custom_aggregation(self):
        """Test setting a custom default aggregation."""
        var = TemporalVariable(
            name="average_price",
            temporal_type=TemporalType.STOCK,
            default_aggregation=AggregationMethod.MEAN,
        )

        assert var.get_aggregation_method() == AggregationMethod.MEAN

    def test_invalid_custom_aggregation_raises(self):
        """Test that invalid custom aggregation raises ValueError."""
        with pytest.raises(ValueError):
            TemporalVariable(
                name="inventory",
                temporal_type=TemporalType.STOCK,
                default_aggregation=AggregationMethod.SUM,  # Invalid for STOCK
            )

    def test_can_aggregate_to_coarser(self):
        """Test aggregation to coarser grain is allowed."""
        daily_data = TemporalVariable(
            name="daily_sales",
            temporal_type=TemporalType.FLOW,
            time_grain=TimeGrain.DAILY,
        )

        assert daily_data.can_aggregate_to(TimeGrain.MONTHLY)
        assert daily_data.can_aggregate_to(TimeGrain.ANNUAL)

    def test_cannot_aggregate_to_finer(self):
        """Test aggregation to finer grain is not allowed."""
        annual_data = TemporalVariable(
            name="annual_gdp",
            temporal_type=TemporalType.STOCK,
            time_grain=TimeGrain.ANNUAL,
        )

        assert not annual_data.can_aggregate_to(TimeGrain.DAILY)
        assert not annual_data.can_aggregate_to(TimeGrain.MONTHLY)

    def test_disaggregation_warning(self):
        """Test that disaggregation produces warning."""
        annual = TemporalVariable(
            name="annual_value",
            temporal_type=TemporalType.STOCK,
            time_grain=TimeGrain.ANNUAL,
        )

        warning = annual.get_disaggregation_warning(TimeGrain.MONTHLY)
        assert warning is not None
        assert "interpolation" in warning.lower() or "distribution" in warning.lower()


class TestTimeInterval:
    """Tests for the TimeInterval class."""

    def test_from_year(self):
        """Test creating annual interval."""
        interval = TimeInterval.from_year(2024)

        assert interval.start == date(2024, 1, 1)
        assert interval.end == date(2024, 12, 31)
        assert interval.grain == TimeGrain.ANNUAL

    def test_from_quarter(self):
        """Test creating quarterly intervals."""
        q1 = TimeInterval.from_quarter(2024, 1)
        assert q1.start == date(2024, 1, 1)
        assert q1.end == date(2024, 3, 31)

        q4 = TimeInterval.from_quarter(2024, 4)
        assert q4.start == date(2024, 10, 1)
        assert q4.end == date(2024, 12, 31)

    def test_from_month(self):
        """Test creating monthly intervals."""
        jan = TimeInterval.from_month(2024, 1)
        assert jan.start == date(2024, 1, 1)
        assert jan.end == date(2024, 1, 31)

        feb = TimeInterval.from_month(2024, 2)
        assert feb.end == date(2024, 2, 29)  # Leap year

    def test_contains(self):
        """Test point containment."""
        q1 = TimeInterval.from_quarter(2024, 1)

        assert q1.contains(date(2024, 2, 15))
        assert not q1.contains(date(2024, 4, 1))

    def test_overlaps(self):
        """Test interval overlap."""
        jan = TimeInterval.from_month(2024, 1)
        q1 = TimeInterval.from_quarter(2024, 1)

        assert jan.overlaps(q1)

        q2 = TimeInterval.from_quarter(2024, 2)
        assert not jan.overlaps(q2)


class TestStockFlowCombination:
    """Tests for Stock/Flow combination rules."""

    def test_can_add_same_types(self):
        """Test that same temporal types can be added."""
        assert StockFlowCombination.can_add(TemporalType.STOCK, TemporalType.STOCK)
        assert StockFlowCombination.can_add(TemporalType.FLOW, TemporalType.FLOW)

    def test_cannot_add_mixed_types(self):
        """Test that mixing Stock and Flow in addition is invalid."""
        assert not StockFlowCombination.can_add(TemporalType.STOCK, TemporalType.FLOW)
        assert not StockFlowCombination.can_add(TemporalType.FLOW, TemporalType.STOCK)

    def test_addition_result_preserves_type(self):
        """Test that adding same types preserves the type."""
        assert (
            StockFlowCombination.addition_result(TemporalType.STOCK, TemporalType.STOCK)
            == TemporalType.STOCK
        )
        assert (
            StockFlowCombination.addition_result(TemporalType.FLOW, TemporalType.FLOW)
            == TemporalType.FLOW
        )

    def test_addition_mixed_raises(self):
        """Test that mixed addition raises ValueError."""
        with pytest.raises(ValueError):
            StockFlowCombination.addition_result(TemporalType.STOCK, TemporalType.FLOW)

    def test_multiplication_with_parameter(self):
        """Test multiplying by parameter preserves type."""
        assert (
            StockFlowCombination.multiplication_result(
                TemporalType.PARAMETER, TemporalType.STOCK
            )
            == TemporalType.STOCK
        )
        assert (
            StockFlowCombination.multiplication_result(
                TemporalType.PARAMETER, TemporalType.FLOW
            )
            == TemporalType.FLOW
        )


class TestInferTemporalType:
    """Tests for temporal type inference."""

    def test_infer_stock_from_name(self):
        """Test inferring STOCK from variable name."""
        assert infer_temporal_type("inventory_level") == TemporalType.STOCK
        assert infer_temporal_type("population_total") == TemporalType.STOCK
        assert infer_temporal_type("account_balance") == TemporalType.STOCK

    def test_infer_flow_from_name(self):
        """Test inferring FLOW from variable name."""
        assert infer_temporal_type("monthly_revenue") == TemporalType.FLOW
        assert infer_temporal_type("sales_income") == TemporalType.FLOW
        assert infer_temporal_type("quarterly_expenses") == TemporalType.FLOW

    def test_infer_parameter_from_name(self):
        """Test inferring PARAMETER from variable name."""
        assert infer_temporal_type("tax_rate_coefficient") == TemporalType.PARAMETER
        assert infer_temporal_type("threshold_limit") == TemporalType.PARAMETER
        assert infer_temporal_type("interest_rate") == TemporalType.PARAMETER

    def test_keyword_matching_uses_tokens_not_substrings(self):
        assert infer_temporal_type("discount_code") == TemporalType.DERIVED
        assert infer_temporal_type("country_code") == TemporalType.DERIVED
        assert infer_temporal_type("discount_rate") == TemporalType.PARAMETER


# =============================================================================
# SECTION 4: Type Coercion Tests
# =============================================================================


class TestTypeCoercion:
    """Tests for the TypeCoercion class."""

    def test_int_widening_allowed(self):
        """Test that integer widening is allowed."""
        result = safe_cast(42, "int64", policy=CoercionPolicy.STRICT)
        assert result == 42

    def test_int_narrowing_blocked_strict(self):
        """Test that integer narrowing is blocked in strict mode."""
        large_value = 2**31  # Too large for int32

        with pytest.raises(CoercionError):
            safe_cast(large_value, "int32", policy=CoercionPolicy.STRICT)

    def test_float_to_int_exact(self):
        """Test that exact float-to-int conversion is allowed."""
        result = safe_cast(42.0, "int32", policy=CoercionPolicy.STRICT)
        assert result == 42

    def test_float_to_int_non_exact_blocked(self):
        """Test that non-exact float-to-int is blocked in strict mode."""
        with pytest.raises(CoercionError):
            safe_cast(3.14159, "int32", policy=CoercionPolicy.STRICT)

    def test_float_to_int_lenient(self):
        """Test that non-exact float-to-int is allowed in lenient mode."""
        result = safe_cast(3.14159, "int32", policy=CoercionPolicy.LENIENT)
        assert result == 3  # Truncated

    def test_warn_policy_emits_warning(self):
        """Test that WARN policy emits PrecisionLossWarning."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            safe_cast(3.14159, "int32", policy=CoercionPolicy.WARN)
            assert any(isinstance(w.message, PrecisionLossWarning) for w in caught)

    def test_int_to_float(self):
        """Test integer to float conversion."""
        result = safe_cast(42, "float64")
        assert result == 42.0

    def test_large_int_to_float_strict(self):
        """Test that large int to float warns about precision loss."""
        large_int = 2**60  # Too large for float64 exact representation

        # In strict mode, this should fail
        with pytest.raises(CoercionError):
            safe_cast(large_int, "float32", policy=CoercionPolicy.STRICT)

    def test_string_to_int(self):
        """Test string to integer conversion."""
        result = safe_cast("42", "int32")
        assert result == 42

    def test_string_to_int_invalid(self):
        """Test that invalid string raises error."""
        with pytest.raises(CoercionError):
            safe_cast("not_a_number", "int32")

    def test_string_to_float(self):
        """Test string to float conversion."""
        result = safe_cast("3.14159", "float64")
        assert abs(result - 3.14159) < 1e-10

    def test_string_to_float_supports_locale_decimal(self):
        result = safe_cast("1.000,50", "float64")
        assert result == 1000.5

    def test_string_to_decimal_supports_scientific_notation(self):
        result = safe_cast("1,23e3", "decimal")
        assert result == Decimal("1.23E+3")

    def test_string_to_bool(self):
        """Test string to boolean conversion."""
        assert safe_cast("true", "boolean") is True
        assert safe_cast("false", "boolean") is False
        assert safe_cast("yes", "boolean") is True
        assert safe_cast("no", "boolean") is False
        assert safe_cast("1", "boolean") is True
        assert safe_cast("0", "boolean") is False

    def test_empty_string_to_bool_is_invalid(self):
        with pytest.raises(CoercionError):
            safe_cast("", "boolean")

    def test_string_to_date(self):
        """Test string to date conversion."""
        result = safe_cast("2024-01-15", "date")
        assert result == date(2024, 1, 15)

    def test_string_to_date_invalid(self):
        """Test that invalid date string raises error."""
        with pytest.raises(CoercionError):
            safe_cast("not-a-date", "date")

    def test_string_to_datetime(self):
        """Test string to datetime conversion."""
        result = safe_cast("2024-01-15T10:30:00", "datetime")
        assert result == datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

    def test_unix_timestamp_to_datetime_is_utc(self):
        result = safe_cast(0, "datetime")
        assert result == datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_future_datetime_is_clamped_in_warn_mode(self):
        result = TypeCoercion(policy=CoercionPolicy.WARN).coerce(
            "2999-01-01T00:00:00Z",
            "string",
            "datetime",
        )
        assert result.success is True
        assert result.value.tzinfo == timezone.utc
        assert any("clock-skew tolerance" in warning for warning in result.warnings)

    def test_datetime_to_date_with_time(self):
        """Test datetime to date with non-zero time in strict mode."""
        dt = datetime(2024, 1, 15, 10, 30, 0)

        with pytest.raises(CoercionError):
            safe_cast(dt, "date", policy=CoercionPolicy.STRICT)

    def test_datetime_to_date_at_midnight(self):
        """Test datetime to date at midnight is allowed."""
        dt = datetime(2024, 1, 15, 0, 0, 0)
        result = safe_cast(dt, "date", policy=CoercionPolicy.STRICT)
        assert result == date(2024, 1, 15)

    def test_decimal_conversion(self):
        """Test Decimal type conversion."""
        result = safe_cast("123.456", "decimal")
        assert result == Decimal("123.456")

        result = safe_cast(42, "decimal")
        assert result == Decimal("42")

    def test_any_to_string(self):
        """Test that most types can convert to string."""
        assert safe_cast(42, "string") == "42"
        assert safe_cast(3.14, "string") == "3.14"
        assert safe_cast(True, "string") == "True"

    def test_none_raises_error(self):
        """Test that None cannot be coerced."""
        with pytest.raises(CoercionError):
            safe_cast(None, "int32")


class TestCanSafelyCast:
    """Tests for the can_safely_cast function."""

    def test_int_widening(self):
        """Test that int widening is safe."""
        assert can_safely_cast(42, "int64")

    def test_int_overflow(self):
        """Test that overflowing int is not safe."""
        assert not can_safely_cast(2**31, "int32")

    def test_float_to_int_exact(self):
        """Test that exact float to int is safe."""
        assert can_safely_cast(42.0, "int32")

    def test_float_to_int_non_exact(self):
        """Test that non-exact float to int is not safe."""
        assert not can_safely_cast(3.14, "int32")


class TestCoercionPath:
    """Tests for coercion path finding."""

    def test_same_type(self):
        """Test that same type has trivial path."""
        path = get_coercion_path("int32", "int32")
        assert path == ["int32"]

    def test_int_widening_path(self):
        """Test path for integer widening."""
        path = get_coercion_path("int32", "int64")
        assert path is not None
        assert "int64" in path

    def test_int_to_float_path(self):
        """Test path from int to float."""
        path = get_coercion_path("int32", "float64")
        assert path is not None

    def test_string_to_int_path(self):
        """Test path from string to int."""
        path = get_coercion_path("string", "int32")
        assert path is not None

    def test_date_datetime_path(self):
        """Test path between date types."""
        assert get_coercion_path("date", "datetime") is not None
        assert get_coercion_path("datetime", "date") is not None


class TestCoercionPolicy:
    """Tests for different coercion policies."""

    def test_strict_blocks_precision_loss(self):
        """Test that STRICT policy blocks precision loss."""
        coercer = TypeCoercion(policy=CoercionPolicy.STRICT)

        result = coercer.coerce(3.14159, "float", "int32")
        assert not result.success

    def test_lenient_allows_precision_loss(self):
        """Test that LENIENT policy allows precision loss."""
        coercer = TypeCoercion(policy=CoercionPolicy.LENIENT)

        result = coercer.coerce(3.14159, "float", "int32")
        assert result.success
        assert result.precision_loss

    def test_warn_policy_flags_precision_loss(self):
        """Test that WARN policy flags precision loss."""
        coercer = TypeCoercion(policy=CoercionPolicy.WARN)

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = coercer.coerce(3.14159, "float", "int32")
        assert result.success
        assert result.precision_loss
        assert len(result.warnings) > 0


# =============================================================================
# SECTION 5: Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests across modules."""

    def test_unit_dimension_consistency(self):
        """Test that unit dimensions are consistent with DimensionRegistry."""
        registry = DimensionRegistry.get_instance()

        # Velocity
        velocity_unit = Unit.parse("m/s")
        velocity_dim = registry.get("velocity")
        assert velocity_unit.dimension == velocity_dim

        # Energy
        # Create J = kg * m^2 / s^2
        kg = Unit.parse("kg")
        m = Unit.parse("m")
        s = Unit.parse("s")
        joule = kg * (m ** 2) / (s ** 2)
        energy_dim = registry.get("energy")
        assert joule.dimension == energy_dim

    def test_unit_conversion_algebra(self):
        """Test that unit algebra is consistent with conversions."""
        # Create velocity from components
        km = Unit.parse("km")
        h = Unit.parse("h")
        v1 = km / h

        # Parse directly
        v2 = Unit.parse("km/h")

        # Should be compatible
        assert v1.is_compatible_with(v2)

        # Convert to same value
        ms = Unit.parse("m/s")
        val1 = v1.convert_to(ms, 36)
        val2 = v2.convert_to(ms, 36)
        assert val1 == val2

    def test_temporal_with_unit(self):
        """Test temporal variable with unit specification."""
        revenue = TemporalVariable(
            name="quarterly_revenue",
            temporal_type=TemporalType.FLOW,
            time_grain=TimeGrain.QUARTERLY,
            unit_expression="Mio USD",
        )

        # Should be able to parse the unit
        unit = Unit.parse(revenue.unit_expression)
        assert unit.is_currency

    def test_coercion_preserves_value_semantics(self):
        """Test that coercion preserves mathematical meaning."""
        # 100 percent = 1.0 ratio
        pct_value = Decimal("100")

        # Coerce to float
        float_value = safe_cast(pct_value, "float64")

        # Convert using units
        pct_unit = Unit.parse("percent")
        ratio_unit = Unit.parse("ratio")
        ratio_value = pct_unit.convert_to(ratio_unit, float_value)

        assert ratio_value == Decimal("1")


# =============================================================================
# SECTION 6: Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_dimension_zero_power(self):
        """Test that zero powers are excluded from to_dict."""
        dim = Dimension(length=1, time=0)
        assert "time" not in dim.to_dict()

    def test_unit_parse_whitespace(self):
        """Test that units handle whitespace."""
        assert Unit.parse("  km  ").dimension == Dimension(length=1)

    def test_unit_dimensionless_string(self):
        """Test parsing dimensionless units."""
        for s in ["1", "dimensionless", "unitless", "-"]:
            unit = Unit.parse(s)
            assert unit.is_dimensionless

    def test_temporal_interval_invalid(self):
        """Test that invalid intervals raise error."""
        with pytest.raises(ValueError):
            TimeInterval(
                start=date(2024, 12, 31),
                end=date(2024, 1, 1),  # End before start
            )

    def test_coercion_nan_float(self):
        """Test coercion of NaN values."""
        with pytest.raises(CoercionError):
            safe_cast(float("nan"), "int32")

    def test_coercion_inf_float(self):
        """Test coercion of infinity values."""
        with pytest.raises(CoercionError):
            safe_cast(float("inf"), "decimal")

    def test_coercion_very_large_decimal_string(self):
        """Test coercion of large decimal strings."""
        large_str = "1" + "0" * 100  # 10^100
        result = safe_cast(large_str, "decimal")
        assert result == Decimal(large_str)

    def test_unit_negative_exponent(self):
        """Test parsing negative exponents."""
        # m/s^2 = m*s^-2
        unit = Unit.parse("m/s^2")
        assert unit.dimension == Dimension(length=1, time=-2)


# =============================================================================
# SECTION 7: Performance and Regression Tests
# =============================================================================


class TestPerformance:
    """Performance-related tests."""

    def test_dimension_registry_singleton_performance(self):
        """Test that singleton doesn't create new instances."""
        # First call
        reg1 = DimensionRegistry.get_instance()

        # Many subsequent calls
        for _ in range(1000):
            reg = DimensionRegistry.get_instance()
            assert reg is reg1

    def test_unit_parsing_cached(self):
        """Test that common units parse efficiently."""
        # Parse many times
        for _ in range(100):
            Unit.parse("km/h")
            Unit.parse("USD")
            Unit.parse("percent")

    def test_conversion_factor_computation(self):
        """Test that conversion factors are computed correctly."""
        km = Unit.parse("km")
        m = Unit.parse("m")

        # Get factor multiple times
        for _ in range(100):
            factor = km.get_conversion_factor(m)
            assert factor.multiplier == Decimal("1000")
