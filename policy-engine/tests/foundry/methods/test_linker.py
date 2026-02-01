"""
Unit tests for Slot Linker and Compatibility Checker.
"""
from __future__ import annotations

import pytest

from polisyos.foundry.methods.base import (
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
    FidelityLevel,
    ComplexityClass,
)
from polisyos.foundry.methods.exceptions import (
    ShapeMismatchError,
    SlotConnectionError,
    UnitMismatchError,
)
from polisyos.foundry.methods.linker import (
    LinkerConfig,
    SlotLinker,
    check_linkable,
    link_methods,
)
from polisyos.foundry.methods.types.checker import (
    IncompatibilityReason,
    ShapeAdapterKind,
    TypeAdapterKind,
    UnitAdapterKind,
    check_multiple_compatibility,
    check_slot_compatibility,
    find_compatible_slots,
)


# =============================================================================
# Test Fixtures
# =============================================================================


class TestUnits:
    """Test unit definitions (mirrors Units class)."""

    USD = Unit("currency", "USD")
    EUR = Unit("currency", "EUR")
    UAH = Unit("currency", "UAH")

    FRACTION = Unit("ratio", "1", scale=1.0)
    PERCENT = Unit("ratio", "%", scale=0.01)
    BASIS_POINTS = Unit("ratio", "bp", scale=0.0001)

    YEAR = Unit("time", "yr", scale=1.0)
    MONTH = Unit("time", "mo", scale=1 / 12)
    QUARTER = Unit("time", "qtr", scale=0.25)

    METER = Unit("distance", "m", scale=1.0)
    KILOMETER = Unit("distance", "km", scale=1000.0)

    UNITLESS = Unit("none", "1")


@pytest.fixture
def units() -> type[TestUnits]:
    return TestUnits


def make_slot(
    name: str,
    slot_type: SlotType = SlotType.SCALAR,
    unit: Unit | None = None,
    shape: tuple = (),
    bounds: tuple = (None, None),
) -> SlotSpec:
    if unit is None:
        unit = TestUnits.UNITLESS
    return SlotSpec(
        name=name,
        slot_type=slot_type,
        unit=unit,
        shape=shape,
        bounds=bounds,
    )


def make_signature(
    name: str,
    namespace: str = "test",
    version: str = "1.0.0",
    inputs: list[SlotSpec] | None = None,
    outputs: list[SlotSpec] | None = None,
) -> MethodSignature:
    return MethodSignature(
        name=name,
        namespace=namespace,
        version=version,
        input_slots=frozenset(inputs or []),
        output_slots=frozenset(outputs or []),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
    )


# =============================================================================
# Unit Dimension Compatibility Tests
# =============================================================================


class TestUnitDimensionCompatibility:
    def test_same_dimension_compatible(self, units):
        src = make_slot("a", unit=units.USD)
        tgt = make_slot("b", unit=units.USD)

        result = check_slot_compatibility(src, tgt)

        assert result.compatible is True
        assert result.reason is None
        assert result.adapter_plan.unit.kind == UnitAdapterKind.NONE

    def test_currency_requires_fx_rate(self, units):
        src = make_slot("a", unit=units.USD)
        tgt = make_slot("b", unit=units.EUR)

        result = check_slot_compatibility(src, tgt)

        assert result.compatible is True
        assert result.requires_conversion is True
        assert result.adapter_plan.unit.kind == UnitAdapterKind.FX_RATE
        assert result.requires_fx_rate is True
        assert result.conversion_factor is None

    def test_different_dimension_incompatible(self, units):
        src = make_slot("a", unit=units.USD)
        tgt = make_slot("b", unit=units.YEAR)

        result = check_slot_compatibility(src, tgt)

        assert result.compatible is False
        assert result.reason == IncompatibilityReason.UNIT_DIMENSION_MISMATCH


# =============================================================================
# Unit Scale Conversion Tests
# =============================================================================


class TestUnitScaleConversion:
    def test_same_scale_no_conversion(self, units):
        src = make_slot("a", unit=units.USD)
        tgt = make_slot("b", unit=units.USD)

        result = check_slot_compatibility(src, tgt)

        assert result.compatible is True
        assert result.requires_conversion is False
        assert result.conversion_factor == 1.0

    def test_percent_to_fraction_conversion(self, units):
        src = make_slot("rate", unit=units.PERCENT)
        tgt = make_slot("ratio", unit=units.FRACTION)

        result = check_slot_compatibility(src, tgt)

        assert result.compatible is True
        assert result.adapter_plan.unit.kind == UnitAdapterKind.LINEAR_SCALE
        assert abs(result.conversion_factor - 0.01) < 1e-9

    def test_fraction_to_percent_conversion(self, units):
        src = make_slot("ratio", unit=units.FRACTION)
        tgt = make_slot("rate", unit=units.PERCENT)

        result = check_slot_compatibility(src, tgt)

        assert result.compatible is True
        assert result.adapter_plan.unit.kind == UnitAdapterKind.LINEAR_SCALE
        assert abs(result.conversion_factor - 100.0) < 1e-9

    def test_kilometer_to_meter_conversion(self, units):
        src = make_slot("distance", unit=units.KILOMETER)
        tgt = make_slot("length", unit=units.METER)

        result = check_slot_compatibility(src, tgt)

        assert result.compatible is True
        assert result.adapter_plan.unit.kind == UnitAdapterKind.LINEAR_SCALE
        assert abs(result.conversion_factor - 1000.0) < 1e-9

    def test_meter_to_kilometer_conversion(self, units):
        src = make_slot("length", unit=units.METER)
        tgt = make_slot("distance", unit=units.KILOMETER)

        result = check_slot_compatibility(src, tgt)

        assert result.compatible is True
        assert result.adapter_plan.unit.kind == UnitAdapterKind.LINEAR_SCALE
        assert abs(result.conversion_factor - 0.001) < 1e-9

    def test_basis_points_to_fraction(self, units):
        src = make_slot("spread", unit=units.BASIS_POINTS)
        tgt = make_slot("ratio", unit=units.FRACTION)

        result = check_slot_compatibility(src, tgt)

        assert result.compatible is True
        assert result.adapter_plan.unit.kind == UnitAdapterKind.LINEAR_SCALE
        assert abs(result.conversion_factor - 0.0001) < 1e-9

    def test_month_to_year_conversion(self, units):
        src = make_slot("period", unit=units.MONTH)
        tgt = make_slot("duration", unit=units.YEAR)

        result = check_slot_compatibility(src, tgt)

        assert result.compatible is True
        assert result.adapter_plan.unit.kind == UnitAdapterKind.LINEAR_SCALE
        assert abs(result.conversion_factor - (1 / 12)) < 1e-9


# =============================================================================
# SlotType Compatibility Tests
# =============================================================================


class TestSlotTypeCompatibility:
    def test_scalar_to_scalar(self, units):
        src = make_slot("a", SlotType.SCALAR, unit=units.UNITLESS)
        tgt = make_slot("b", SlotType.SCALAR, unit=units.UNITLESS)

        result = check_slot_compatibility(src, tgt)
        assert result.compatible is True

    def test_scalar_promotes_to_vector(self, units):
        src = make_slot("a", SlotType.SCALAR, unit=units.UNITLESS)
        tgt = make_slot("b", SlotType.VECTOR, unit=units.UNITLESS, shape=(10,))

        result = check_slot_compatibility(src, tgt)
        assert result.compatible is True
        assert result.adapter_plan.shape.kind == ShapeAdapterKind.BROADCAST_TO

    def test_scalar_promotes_to_tensor(self, units):
        src = make_slot("a", SlotType.SCALAR, unit=units.UNITLESS)
        tgt = make_slot("b", SlotType.TENSOR, unit=units.UNITLESS, shape=(10, 20))

        result = check_slot_compatibility(src, tgt)
        assert result.compatible is True
        assert result.adapter_plan.shape.kind == ShapeAdapterKind.BROADCAST_TO

    def test_vector_to_matrix_expand_dims(self, units):
        src = make_slot("a", SlotType.VECTOR, unit=units.UNITLESS, shape=(10,))
        tgt = make_slot("b", SlotType.MATRIX, unit=units.UNITLESS, shape=(10, 1))

        result = check_slot_compatibility(src, tgt)
        assert result.compatible is True
        assert result.adapter_plan.shape.kind == ShapeAdapterKind.EXPAND_DIMS
        assert result.adapter_plan.slot_type.kind == TypeAdapterKind.VECTOR_TO_MATRIX

    def test_vector_to_scalar_incompatible(self, units):
        src = make_slot("a", SlotType.VECTOR, unit=units.UNITLESS, shape=(10,))
        tgt = make_slot("b", SlotType.SCALAR, unit=units.UNITLESS)

        result = check_slot_compatibility(src, tgt)
        assert result.compatible is False
        assert result.reason == IncompatibilityReason.SLOT_TYPE_INCOMPATIBLE

    def test_tensor_accepts_everything(self, units):
        tgt = make_slot("target", SlotType.TENSOR, unit=units.UNITLESS, shape=(10,))

        for src_type in [SlotType.SCALAR, SlotType.VECTOR, SlotType.MATRIX, SlotType.TENSOR]:
            shape = () if src_type == SlotType.SCALAR else (10,)
            src = make_slot("source", src_type, unit=units.UNITLESS, shape=shape)
            result = check_slot_compatibility(src, tgt)
            assert result.compatible is True


# =============================================================================
# Shape Broadcasting Tests
# =============================================================================


class TestShapeBroadcasting:
    def test_exact_shape_match(self, units):
        src = make_slot("a", SlotType.TENSOR, unit=units.UNITLESS, shape=(10, 20))
        tgt = make_slot("b", SlotType.TENSOR, unit=units.UNITLESS, shape=(10, 20))

        result = check_slot_compatibility(src, tgt)
        assert result.compatible is True
        assert result.adapter_plan.shape.kind == ShapeAdapterKind.IDENTITY

    def test_scalar_broadcasts_to_any_shape(self, units):
        src = make_slot("a", SlotType.SCALAR, unit=units.UNITLESS, shape=())
        tgt = make_slot("b", SlotType.TENSOR, unit=units.UNITLESS, shape=(10, 20, 30))

        result = check_slot_compatibility(src, tgt)
        assert result.compatible is True
        assert result.adapter_plan.shape.kind == ShapeAdapterKind.BROADCAST_TO

    def test_trailing_dimension_broadcast(self, units):
        src = make_slot("a", SlotType.TENSOR, unit=units.UNITLESS, shape=(10,))
        tgt = make_slot("b", SlotType.TENSOR, unit=units.UNITLESS, shape=(5, 10))

        result = check_slot_compatibility(src, tgt)
        assert result.compatible is True
        assert result.adapter_plan.shape.kind == ShapeAdapterKind.BROADCAST_TO

    def test_leading_one_broadcast(self, units):
        src = make_slot("a", SlotType.TENSOR, unit=units.UNITLESS, shape=(1, 10))
        tgt = make_slot("b", SlotType.TENSOR, unit=units.UNITLESS, shape=(5, 10))

        result = check_slot_compatibility(src, tgt)
        assert result.compatible is True
        assert result.adapter_plan.shape.kind == ShapeAdapterKind.BROADCAST_TO

    def test_incompatible_shapes_fail(self, units):
        src = make_slot("a", SlotType.TENSOR, unit=units.UNITLESS, shape=(3, 4))
        tgt = make_slot("b", SlotType.TENSOR, unit=units.UNITLESS, shape=(5, 4))

        result = check_slot_compatibility(src, tgt, strict_shape=False)

        assert result.compatible is False
        assert result.reason == IncompatibilityReason.SHAPE_MISMATCH

    def test_directional_broadcast_rejects_shrink(self, units):
        src = make_slot("a", SlotType.TENSOR, unit=units.UNITLESS, shape=(10,))
        tgt = make_slot("b", SlotType.TENSOR, unit=units.UNITLESS, shape=(10, 1))

        result = check_slot_compatibility(src, tgt)

        assert result.compatible is False
        assert result.reason == IncompatibilityReason.SHAPE_MISMATCH

    def test_strict_shape_mismatch_fails(self, units):
        src = make_slot("a", SlotType.TENSOR, unit=units.UNITLESS, shape=(10,))
        tgt = make_slot("b", SlotType.TENSOR, unit=units.UNITLESS, shape=(10, 20))

        result = check_slot_compatibility(src, tgt, strict_shape=True)

        assert result.compatible is False
        assert result.reason == IncompatibilityReason.SHAPE_MISMATCH

    def test_symbolic_dimensions_compatible(self, units):
        src = make_slot("a", SlotType.VECTOR, unit=units.UNITLESS, shape=("N_AGENTS",))
        tgt = make_slot("b", SlotType.VECTOR, unit=units.UNITLESS, shape=("N_AGENTS",))

        result = check_slot_compatibility(src, tgt)
        assert result.compatible is True
        assert result.has_warnings is False

    def test_symbolic_mismatch_warns(self, units):
        src = make_slot("a", SlotType.VECTOR, unit=units.UNITLESS, shape=("N_AGENTS",))
        tgt = make_slot("b", SlotType.VECTOR, unit=units.UNITLESS, shape=("N_SECTORS",))

        result = check_slot_compatibility(src, tgt)
        assert result.compatible is True
        assert result.has_warnings is True
        assert "symbolic" in result.warnings[0].lower()


# =============================================================================
# Bounds Overlap Tests
# =============================================================================


class TestBoundsOverlap:
    def test_unbounded_to_unbounded(self, units):
        src = make_slot("a", unit=units.UNITLESS, bounds=(None, None))
        tgt = make_slot("b", unit=units.UNITLESS, bounds=(None, None))

        result = check_slot_compatibility(src, tgt)
        assert result.compatible is True
        assert result.has_warnings is False

    def test_source_within_target(self, units):
        src = make_slot("a", unit=units.UNITLESS, bounds=(0.0, 1.0))
        tgt = make_slot("b", unit=units.UNITLESS, bounds=(-1.0, 2.0))

        result = check_slot_compatibility(src, tgt)
        assert result.compatible is True
        assert result.has_warnings is False

    def test_partial_overlap_warning(self, units):
        src = make_slot("a", unit=units.UNITLESS, bounds=(0.0, 2.0))
        tgt = make_slot("b", unit=units.UNITLESS, bounds=(0.0, 1.0))

        result = check_slot_compatibility(src, tgt)
        assert result.compatible is True
        assert result.has_warnings is True

    def test_no_overlap_warning(self, units):
        src = make_slot("a", unit=units.UNITLESS, bounds=(5.0, 10.0))
        tgt = make_slot("b", unit=units.UNITLESS, bounds=(0.0, 1.0))

        result = check_slot_compatibility(src, tgt)
        assert result.compatible is True
        assert result.has_warnings is True


# =============================================================================
# SlotLinker Explicit Mode Tests
# =============================================================================


class TestSlotLinkerExplicit:
    def test_explicit_single_binding(self, units):
        producer = make_signature(
            "producer",
            outputs=[make_slot("revenue", unit=units.USD)],
        )
        consumer = make_signature(
            "consumer",
            inputs=[make_slot("income", unit=units.EUR)],
        )

        linker = SlotLinker()
        result = linker.link(
            producer,
            consumer,
            explicit_mapping={"revenue": "income"},
        )

        assert result.binding_count == 1
        assert result.bindings[0].source_slot == "revenue"
        assert result.bindings[0].target_slot == "income"

    def test_explicit_invalid_source_raises(self, units):
        producer = make_signature(
            "producer",
            outputs=[make_slot("revenue", unit=units.USD)],
        )
        consumer = make_signature(
            "consumer",
            inputs=[make_slot("income", unit=units.USD)],
        )

        linker = SlotLinker()
        with pytest.raises(SlotConnectionError) as exc:
            linker.link(
                producer,
                consumer,
                explicit_mapping={"nonexistent": "income"},
            )
        assert "nonexistent" in str(exc.value)

    def test_explicit_invalid_target_raises(self, units):
        producer = make_signature(
            "producer",
            outputs=[make_slot("revenue", unit=units.USD)],
        )
        consumer = make_signature(
            "consumer",
            inputs=[make_slot("income", unit=units.USD)],
        )

        linker = SlotLinker()
        with pytest.raises(SlotConnectionError) as exc:
            linker.link(
                producer,
                consumer,
                explicit_mapping={"revenue": "nonexistent"},
            )
        assert "nonexistent" in str(exc.value)

    def test_explicit_unit_mismatch_raises(self, units):
        producer = make_signature(
            "producer",
            outputs=[make_slot("revenue", unit=units.USD)],
        )
        consumer = make_signature(
            "consumer",
            inputs=[make_slot("duration", unit=units.YEAR)],
        )

        linker = SlotLinker()
        with pytest.raises(UnitMismatchError) as exc:
            linker.link(
                producer,
                consumer,
                explicit_mapping={"revenue": "duration"},
            )
        assert exc.value.source_slot == "revenue"
        assert exc.value.target_slot == "duration"

    def test_explicit_tracks_unconnected(self, units):
        producer = make_signature(
            "producer",
            outputs=[make_slot("a", unit=units.UNITLESS)],
        )
        consumer = make_signature(
            "consumer",
            inputs=[
                make_slot("x", unit=units.UNITLESS),
                make_slot("y", unit=units.UNITLESS),
            ],
        )

        linker = SlotLinker()
        result = linker.link(
            producer,
            consumer,
            explicit_mapping={"a": "x"},
        )

        assert result.has_unconnected is True
        assert "y" in result.unconnected_inputs


# =============================================================================
# SlotLinker Auto Mode Tests
# =============================================================================


class TestSlotLinkerAuto:
    def test_auto_matches_by_name(self, units):
        producer = make_signature(
            "producer",
            outputs=[
                make_slot("revenue", unit=units.USD),
                make_slot("cost", unit=units.USD),
            ],
        )
        consumer = make_signature(
            "consumer",
            inputs=[
                make_slot("revenue", unit=units.EUR),
                make_slot("other", unit=units.USD),
            ],
        )

        linker = SlotLinker()
        result = linker.link(producer, consumer)

        revenue_binding = result.get_binding("revenue")
        assert revenue_binding is not None
        assert revenue_binding.source_slot == "revenue"

    def test_auto_matches_by_type(self, units):
        producer = make_signature(
            "producer",
            outputs=[make_slot("output_a", unit=units.PERCENT)],
        )
        consumer = make_signature(
            "consumer",
            inputs=[make_slot("input_rate", unit=units.FRACTION)],
        )

        linker = SlotLinker()
        result = linker.link(producer, consumer)

        assert result.binding_count == 1
        assert result.bindings[0].source_slot == "output_a"
        assert result.bindings[0].target_slot == "input_rate"
        assert "auto-linked" in str(result.warnings).lower()

    def test_auto_prefers_best_score(self, units):
        producer = make_signature(
            "producer",
            outputs=[
                make_slot("a_usd", unit=units.USD),
                make_slot("b_eur", unit=units.EUR),
            ],
        )
        consumer = make_signature(
            "consumer",
            inputs=[make_slot("income", unit=units.USD)],
        )

        config = LinkerConfig(prefer_exact_names=False)
        linker = SlotLinker(config)
        result = linker.link(producer, consumer)

        assert result.binding_count == 1
        assert result.bindings[0].source_slot == "a_usd"

    def test_auto_deterministic_tiebreak(self, units):
        producer = make_signature(
            "producer",
            outputs=[
                make_slot("z_usd", unit=units.USD),
                make_slot("a_usd", unit=units.USD),
            ],
        )
        consumer = make_signature(
            "consumer",
            inputs=[make_slot("income", unit=units.USD)],
        )

        config = LinkerConfig(prefer_exact_names=False)
        linker = SlotLinker(config)
        result = linker.link(producer, consumer)

        assert result.binding_count == 1
        assert result.bindings[0].source_slot == "a_usd"

    def test_auto_prefers_type_over_exact_name_when_disabled(self, units):
        producer = make_signature(
            "producer",
            outputs=[
                make_slot("rate", unit=units.EUR),
                make_slot("best", unit=units.USD),
            ],
        )
        consumer = make_signature(
            "consumer",
            inputs=[make_slot("rate", unit=units.USD)],
        )

        config = LinkerConfig(prefer_exact_names=False)
        linker = SlotLinker(config)
        result = linker.link(producer, consumer)

        assert result.binding_count == 1
        assert result.bindings[0].source_slot == "best"

    def test_auto_warns_incompatible_same_name(self, units):
        producer = make_signature(
            "producer",
            outputs=[make_slot("value", unit=units.USD)],
        )
        consumer = make_signature(
            "consumer",
            inputs=[make_slot("value", unit=units.YEAR)],
        )

        linker = SlotLinker()
        result = linker.link(producer, consumer)

        assert result.binding_count == 0
        assert "value" in str(result.warnings)
        assert "incompatible" in str(result.warnings).lower()


# =============================================================================
# Integration Tests
# =============================================================================


class TestLinkerIntegration:
    def test_tax_to_budget_chain(self, units):
        tax_sig = make_signature(
            name="progressive_tax",
            namespace="fiscal",
            version="1.0.0",
            inputs=[
                make_slot("income", SlotType.VECTOR, unit=units.USD, shape=("N_AGENTS",)),
            ],
            outputs=[
                make_slot("revenue", SlotType.SCALAR, unit=units.USD),
                make_slot("effective_rate", SlotType.VECTOR, unit=units.PERCENT, shape=("N_AGENTS",)),
            ],
        )

        budget_sig = make_signature(
            name="budget_allocation",
            namespace="fiscal",
            version="1.0.0",
            inputs=[
                make_slot("revenue", SlotType.SCALAR, unit=units.USD),
                make_slot("priorities", SlotType.VECTOR, unit=units.UNITLESS, shape=("N_SECTORS",)),
            ],
            outputs=[
                make_slot("allocation", SlotType.VECTOR, unit=units.USD, shape=("N_SECTORS",)),
            ],
        )

        result = link_methods(tax_sig, budget_sig)

        assert result.binding_count == 1
        assert result.bindings[0].source_slot == "revenue"
        assert result.bindings[0].target_slot == "revenue"
        assert result.has_unconnected is True
        assert "priorities" in result.unconnected_inputs

    def test_conversion_chain(self, units):
        percent_producer = make_signature(
            "interest_calc",
            outputs=[make_slot("rate", unit=units.PERCENT)],
        )
        fraction_consumer = make_signature(
            "growth_model",
            inputs=[make_slot("rate", unit=units.FRACTION)],
        )

        result = link_methods(percent_producer, fraction_consumer)

        assert result.binding_count == 1
        assert result.requires_conversions is True
        assert abs(result.bindings[0].conversion_factor - 0.01) < 1e-9

    def test_check_linkable_utility(self, units):
        compatible_producer = make_signature(
            "a",
            outputs=[make_slot("x", unit=units.USD)],
        )
        compatible_consumer = make_signature(
            "b",
            inputs=[make_slot("x", unit=units.EUR)],
        )
        incompatible_consumer = make_signature(
            "c",
            inputs=[make_slot("y", unit=units.YEAR)],
        )

        assert check_linkable(compatible_producer, compatible_consumer) is True
        assert check_linkable(compatible_producer, incompatible_consumer) is False


# =============================================================================
# Batch Operation Tests
# =============================================================================


class TestBatchOperations:
    def test_check_multiple_compatibility(self, units):
        pairs = [
            (make_slot("a", unit=units.USD), make_slot("b", unit=units.EUR)),
            (make_slot("c", unit=units.PERCENT), make_slot("d", unit=units.FRACTION)),
            (make_slot("e", unit=units.USD), make_slot("f", unit=units.YEAR)),
        ]

        results = check_multiple_compatibility(pairs)

        assert len(results) == 3
        assert results[0].compatible is True
        assert results[1].compatible is True
        assert results[2].compatible is False

    def test_find_compatible_slots(self, units):
        sources = [
            make_slot("revenue_usd", unit=units.USD),
            make_slot("revenue_eur", unit=units.EUR),
            make_slot("duration", unit=units.YEAR),
        ]
        target = make_slot("income", unit=units.UAH)

        compatible = find_compatible_slots(sources, target)

        assert len(compatible) == 2
        names = [s.name for s, _ in compatible]
        assert "revenue_usd" in names
        assert "revenue_eur" in names
        assert "duration" not in names


# =============================================================================
# Configuration Tests
# =============================================================================


class TestLinkerConfiguration:
    def test_strict_config(self, units):
        config = LinkerConfig.strict()

        producer = make_signature(
            "producer",
            outputs=[make_slot("x", SlotType.TENSOR, unit=units.UNITLESS, shape=(10,))],
        )
        consumer = make_signature(
            "consumer",
            inputs=[make_slot("x", SlotType.TENSOR, unit=units.UNITLESS, shape=(10, 1))],
        )

        linker = SlotLinker(config)
        with pytest.raises(ShapeMismatchError):
            linker.link(producer, consumer, explicit_mapping={"x": "x"})

    def test_strict_config_rejects_partial_links(self, units):
        config = LinkerConfig.strict()

        producer = make_signature(
            "producer",
            outputs=[make_slot("a", unit=units.UNITLESS)],
        )
        consumer = make_signature(
            "consumer",
            inputs=[
                make_slot("a", unit=units.UNITLESS),
                make_slot("b", unit=units.UNITLESS),
            ],
        )

        linker = SlotLinker(config)
        with pytest.raises(SlotConnectionError) as exc:
            linker.link(producer, consumer)
        assert "unconnected" in str(exc.value).lower()
        assert "b" in str(exc.value)

    def test_permissive_config(self, units):
        config = LinkerConfig.permissive()

        producer = make_signature(
            "producer",
            outputs=[make_slot("a", unit=units.UNITLESS)],
        )
        consumer = make_signature(
            "consumer",
            inputs=[
                make_slot("a", unit=units.UNITLESS),
                make_slot("b", unit=units.UNITLESS),
            ],
        )

        linker = SlotLinker(config)
        result = linker.link(producer, consumer)

        assert result.binding_count == 1
        assert result.has_unconnected is True

    def test_allow_unsafe_shapes(self, units):
        config = LinkerConfig(allow_unsafe_shapes=True)

        producer = make_signature(
            "producer",
            outputs=[make_slot("x", SlotType.TENSOR, unit=units.UNITLESS, shape=(3, 4))],
        )
        consumer = make_signature(
            "consumer",
            inputs=[make_slot("x", SlotType.TENSOR, unit=units.UNITLESS, shape=(5, 4))],
        )

        linker = SlotLinker(config)
        result = linker.link(producer, consumer, explicit_mapping={"x": "x"})

        assert result.binding_count == 1
        assert result.warnings


# =============================================================================
# Error Message Quality Tests
# =============================================================================


class TestErrorMessages:
    def test_unit_mismatch_error_details(self, units):
        with pytest.raises(UnitMismatchError) as exc:
            raise UnitMismatchError("source_a", "target_b", "USD", "yr")

        assert "source_a" in str(exc.value)
        assert "target_b" in str(exc.value)
        assert "USD" in str(exc.value)
        assert "yr" in str(exc.value)

    def test_shape_mismatch_error_details(self, units):
        with pytest.raises(ShapeMismatchError) as exc:
            raise ShapeMismatchError("a", "b", (10, 20), (5, 5))

        assert "a" in str(exc.value)
        assert "b" in str(exc.value)
        assert "(10, 20)" in str(exc.value)
        assert "(5, 5)" in str(exc.value)
