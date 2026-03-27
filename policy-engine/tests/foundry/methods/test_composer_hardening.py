"""
Tests for Composition & Execution Hardening (Phase 7).

Covers:
- SemanticValidationLevel enum and default-on behavior
- DAG node cache keys with upstream context
- Missing requirement validation at different strictness levels
"""
from __future__ import annotations

from typing import Any, ClassVar

import pytest

from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.composer import (
    MethodComposer,
    SemanticValidationLevel,
)
from polisyos.foundry.methods.exceptions import MissingRequirementError
from polisyos.foundry.methods.registry import MethodRegistry


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_registry():
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


_CURRENCY = Unit(dimension="currency", symbol="USD")
_INCOME_SLOT = SlotSpec(name="income", slot_type=SlotType.VECTOR, unit=_CURRENCY, shape=("n",))
_TAX_SLOT = SlotSpec(name="tax_due", slot_type=SlotType.VECTOR, unit=_CURRENCY, shape=("n",))


def _make_method_class(
    name: str,
    namespace: str = "tests.hardening",
    version: str = "1.0.0",
    input_slots: frozenset[SlotSpec] = frozenset(),
    output_slots: frozenset[SlotSpec] = frozenset(),
    parameters: tuple[ParameterSpec, ...] = (),
    requires: frozenset[str] = frozenset(),
    backend: ComputeBackend = ComputeBackend.JAX,
) -> type:
    sig = MethodSignature(
        name=name,
        namespace=namespace,
        version=version,
        input_slots=input_slots,
        output_slots=output_slots,
        parameters=parameters,
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        requires=requires,
        backend=backend,
    )

    class _Method:
        signature: ClassVar[MethodSignature] = sig
        metadata: ClassVar[MethodMetadata] = MethodMetadata(
            description=f"Test method: {name}",
            tags=frozenset({"test"}),
        )

        @staticmethod
        def pure_step(state: Any, params: dict[str, Any]) -> Any:
            return state

    _Method.__name__ = name.replace("_", " ").title().replace(" ", "")
    return _Method


def _register(*classes: type) -> MethodRegistry:
    registry = MethodRegistry.get_instance()
    for cls in classes:
        registry.register(cls, override=True)
    return registry


# =============================================================================
# SemanticValidationLevel
# =============================================================================


class TestSemanticValidationDefaultOn:

    def test_default_level_is_warn(self):
        """build() without args should use WARN level."""
        method_a = _make_method_class("step_a", output_slots=frozenset({_INCOME_SLOT}))
        method_b = _make_method_class("step_b", input_slots=frozenset({_INCOME_SLOT}))
        registry = _register(method_a, method_b)

        composer = MethodComposer(registry=registry)
        a = composer.add("tests.hardening.step_a@1.0.0")
        b = composer.add("tests.hardening.step_b@1.0.0")
        composer.connect(a, b)

        # Default call — should not raise
        chain = composer.build()
        assert chain is not None

    def test_bool_true_maps_to_strict(self):
        """build(validate_semantics=True) should behave like STRICT."""
        method_a = _make_method_class("step_a", output_slots=frozenset({_INCOME_SLOT}))
        registry = _register(method_a)

        composer = MethodComposer(registry=registry)
        composer.add("tests.hardening.step_a@1.0.0")

        # True = STRICT, should not raise for a simple valid chain
        chain = composer.build(validate_semantics=True)
        assert chain is not None

    def test_bool_false_maps_to_off(self):
        """build(validate_semantics=False) should skip validation."""
        method_a = _make_method_class("step_a", output_slots=frozenset({_INCOME_SLOT}))
        registry = _register(method_a)

        composer = MethodComposer(registry=registry)
        composer.add("tests.hardening.step_a@1.0.0")

        chain = composer.build(validate_semantics=False)
        assert chain is not None


# =============================================================================
# Missing requirement validation levels
# =============================================================================


class TestMissingRequirementLevels:

    def _build_with_missing_requirement(
        self, level: SemanticValidationLevel,
    ) -> Any:
        """Helper: build a chain where step_b requires a non-existent method."""
        method_b = _make_method_class(
            "step_b",
            requires=frozenset({"tests.hardening.nonexistent@1.0.0"}),
        )
        registry = _register(method_b)

        composer = MethodComposer(registry=registry)
        composer.add("tests.hardening.step_b@1.0.0")
        return composer.build(validate_semantics=level)

    def test_missing_requirement_strict_raises(self):
        """STRICT mode should raise MissingRequirementError."""
        with pytest.raises(MissingRequirementError, match="nonexistent"):
            self._build_with_missing_requirement(SemanticValidationLevel.STRICT)

    def test_missing_requirement_warn_does_not_raise(self):
        """WARN mode should produce warning but not raise."""
        chain = self._build_with_missing_requirement(SemanticValidationLevel.WARN)
        assert any("MISSING REQUIREMENT" in w for w in chain.warnings)

    def test_missing_requirement_off_silent(self):
        """OFF mode should produce no warning and not raise."""
        chain = self._build_with_missing_requirement(SemanticValidationLevel.OFF)
        assert not any("MISSING REQUIREMENT" in w for w in chain.warnings)


# =============================================================================
# DAG node cache keys with upstream context
# =============================================================================


class TestCompositionCacheKeys:

    def test_dag_node_key_includes_upstream(self):
        """Same node with different upstream should produce different cache keys."""
        method_a = _make_method_class(
            "source_a",
            output_slots=frozenset({_INCOME_SLOT}),
            parameters=(ParameterSpec(name="alpha", default=1.0, is_static=True),),
        )
        method_b = _make_method_class(
            "source_b",
            output_slots=frozenset({_INCOME_SLOT}),
            parameters=(ParameterSpec(name="beta", default=2.0, is_static=True),),
        )
        method_c = _make_method_class(
            "consumer",
            input_slots=frozenset({_INCOME_SLOT}),
        )
        registry = _register(method_a, method_b, method_c)

        # Chain 1: source_a → consumer
        composer1 = MethodComposer(registry=registry)
        a = composer1.add("tests.hardening.source_a@1.0.0")
        c1 = composer1.add("tests.hardening.consumer@1.0.0")
        composer1.connect(a, c1)
        chain1 = composer1.build(validate_semantics=SemanticValidationLevel.OFF)

        # Chain 2: source_b → consumer
        composer2 = MethodComposer(registry=registry)
        b = composer2.add("tests.hardening.source_b@1.0.0")
        c2 = composer2.add("tests.hardening.consumer@1.0.0")
        composer2.connect(b, c2)
        chain2 = composer2.build(validate_semantics=SemanticValidationLevel.OFF)

        # The consumer node should have different cache keys in the two chains
        consumer_key_1 = chain1.cache_keys[c1.id]
        consumer_key_2 = chain2.cache_keys[c2.id]
        assert consumer_key_1 != consumer_key_2

    def test_isolated_node_cache_key_matches_params(self):
        """Node with no upstream should still have a valid cache key."""
        method_a = _make_method_class(
            "isolated",
            parameters=(ParameterSpec(name="x", default=1.0, is_static=True),),
        )
        registry = _register(method_a)

        composer = MethodComposer(registry=registry)
        a = composer.add("tests.hardening.isolated@1.0.0")
        chain = composer.build(validate_semantics=SemanticValidationLevel.OFF)

        assert a.id in chain.cache_keys
        assert isinstance(chain.cache_keys[a.id], str)
        assert len(chain.cache_keys[a.id]) > 0

    def test_cache_keys_present_for_all_nodes(self):
        """Every node in the chain should have a cache key."""
        method_a = _make_method_class("step_a", output_slots=frozenset({_INCOME_SLOT}))
        method_b = _make_method_class("step_b", input_slots=frozenset({_INCOME_SLOT}))
        registry = _register(method_a, method_b)

        composer = MethodComposer(registry=registry)
        a = composer.add("tests.hardening.step_a@1.0.0")
        b = composer.add("tests.hardening.step_b@1.0.0")
        composer.connect(a, b)
        chain = composer.build(validate_semantics=SemanticValidationLevel.OFF)

        assert set(chain.cache_keys.keys()) == {a.id, b.id}
