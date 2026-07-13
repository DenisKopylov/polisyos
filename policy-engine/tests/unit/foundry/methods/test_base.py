"""
Tests for core types in base.py.
"""

from __future__ import annotations

import dataclasses

import jax.numpy as jnp
import pytest

from polisyos.foundry.methods import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    parse_fqn,
)
from polisyos.foundry.methods.types.units import Units
from polisyos.ir.analytics.uncertainty import (
    OutputContractCapability,
    value_uncertainty_output_contract,
)


class TestUnitImmutability:
    def test_cannot_modify_dimension(self, sample_unit: Unit):
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_unit.dimension = "other"  # type: ignore

    def test_cannot_modify_symbol(self, sample_unit: Unit):
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_unit.symbol = "XXX"  # type: ignore

    def test_cannot_modify_scale(self, sample_unit: Unit):
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_unit.scale = 2.0  # type: ignore


class TestSlotSpecImmutability:
    def test_cannot_modify_name(self, income_slot: SlotSpec):
        with pytest.raises(dataclasses.FrozenInstanceError):
            income_slot.name = "changed"  # type: ignore

    def test_cannot_modify_slot_type(self, income_slot: SlotSpec):
        with pytest.raises(dataclasses.FrozenInstanceError):
            income_slot.slot_type = SlotType.SCALAR  # type: ignore

    def test_cannot_modify_unit(self, income_slot: SlotSpec):
        with pytest.raises(dataclasses.FrozenInstanceError):
            income_slot.unit = Units.USD  # type: ignore


class TestParameterSpecImmutability:
    def test_cannot_modify_name(self, rate_param: ParameterSpec):
        with pytest.raises(dataclasses.FrozenInstanceError):
            rate_param.name = "changed"  # type: ignore

    def test_cannot_modify_default(self, rate_param: ParameterSpec):
        with pytest.raises(dataclasses.FrozenInstanceError):
            rate_param.default = 0.5  # type: ignore

    def test_cannot_modify_is_static(self, rate_param: ParameterSpec):
        with pytest.raises(dataclasses.FrozenInstanceError):
            rate_param.is_static = True  # type: ignore


class TestMethodSignatureImmutability:
    def test_cannot_modify_name(self, flat_tax_signature: MethodSignature):
        with pytest.raises(dataclasses.FrozenInstanceError):
            flat_tax_signature.name = "changed"  # type: ignore

    def test_cannot_modify_namespace(self, flat_tax_signature: MethodSignature):
        with pytest.raises(dataclasses.FrozenInstanceError):
            flat_tax_signature.namespace = "changed"  # type: ignore

    def test_cannot_modify_version(self, flat_tax_signature: MethodSignature):
        with pytest.raises(dataclasses.FrozenInstanceError):
            flat_tax_signature.version = "2.0.0"  # type: ignore


class TestMethodMetadataImmutability:
    def test_cannot_modify_description(self, sample_metadata: MethodMetadata):
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_metadata.description = "changed"  # type: ignore

    def test_equations_mapping_is_immutable(self):
        eq = {"x": "y"}
        metadata = MethodMetadata(description="x", equations=eq)
        eq["x"] = "z"
        assert metadata.equations["x"] == "y"
        with pytest.raises(TypeError):
            metadata.equations["x"] = "z"  # type: ignore

    def test_sbi_contract_mappings_are_immutable_and_stable(self):
        regime_schema = {"variables": [{"name": "policy_regime"}]}
        variables = regime_schema["variables"]
        metadata = MethodMetadata(
            description="sbi",
            simulator_regime_schema=regime_schema,
            summary_schema_ref="artifact://summary",
            identifiable_target={"equivalence_classes_allowed": True},
            coverage_contract={"locality": "conditional_on_regime"},
            diagnostic_contract={"support_required": True},
        )
        regime_schema["variables"] = []
        variables[0]["name"] = "mutated"

        assert metadata.simulator_regime_schema["variables"] == [{"name": "policy_regime"}]
        assert metadata.stable_digest() == metadata.stable_digest()
        with pytest.raises(TypeError):
            metadata.diagnostic_contract["support_required"] = False  # type: ignore


class TestUnitValidation:
    def test_scale_must_be_positive(self):
        with pytest.raises(ValueError):
            Unit("ratio", "x", scale=0.0)
        with pytest.raises(ValueError):
            Unit("ratio", "x", scale=-1.0)


class TestSlotSpecValidation:
    def test_scalar_requires_empty_shape(self, sample_unit: Unit):
        with pytest.raises(ValueError):
            SlotSpec(
                name="bad",
                slot_type=SlotType.SCALAR,
                unit=sample_unit,
                shape=("n_agents",),
            )

    def test_contract_id_must_be_non_empty_string(self, sample_unit: Unit):
        with pytest.raises(TypeError):
            SlotSpec(
                name="bad",
                slot_type=SlotType.SCALAR,
                unit=sample_unit,
                contract_id="",
            )

    def test_contract_owner_without_capability_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="slot_contract_owner_requires_capability"):
            SlotSpec(
                name="result",
                slot_type=SlotType.SCALAR,
                unit=Unit("value", "json"),
                contract_id="test.output.v1",
                contract_owner="tests.native:Output",
            )

    def test_legacy_fifth_positional_argument_remains_shape(self) -> None:
        slot = SlotSpec(
            "vector",
            SlotType.VECTOR,
            Unit("value", "1"),
            "test.vector.v1",
            ("n",),
        )

        assert slot.shape == ("n",)
        assert slot.contract_capabilities == frozenset()


class TestParameterSpecValidation:
    def test_bounds_must_be_ordered(self):
        with pytest.raises(ValueError):
            ParameterSpec(name="rate", default=0.1, bounds=(1.0, 0.0))


class TestMethodSignatureValidation:
    def test_duplicate_param_names_rejected(self, income_slot: SlotSpec, tax_slot: SlotSpec):
        p1 = ParameterSpec(name="rate", default=0.1)
        p2 = ParameterSpec(name="rate", default=0.2)
        with pytest.raises(ValueError):
            MethodSignature(
                name="dup_param",
                namespace="test",
                version="1.0.0",
                input_slots=frozenset({income_slot}),
                output_slots=frozenset({tax_slot}),
                parameters=(p1, p2),
                fidelity=FidelityLevel.LOW,
                complexity=ComplexityClass.O_N,
            )

    def test_invalid_semver_rejected(self, income_slot: SlotSpec, tax_slot: SlotSpec):
        with pytest.raises(ValueError):
            MethodSignature(
                name="bad",
                namespace="test",
                version="1",
                input_slots=frozenset({income_slot}),
                output_slots=frozenset({tax_slot}),
                parameters=(),
                fidelity=FidelityLevel.LOW,
                complexity=ComplexityClass.O_1,
            )

    def test_invalid_method_ref_rejected(self, income_slot: SlotSpec, tax_slot: SlotSpec):
        with pytest.raises(ValueError):
            MethodSignature(
                name="bad_ref",
                namespace="test",
                version="1.0.0",
                input_slots=frozenset({income_slot}),
                output_slots=frozenset({tax_slot}),
                parameters=(),
                fidelity=FidelityLevel.LOW,
                complexity=ComplexityClass.O_1,
                requires=frozenset({"not_a_fqn"}),
            )

    def test_non_jax_backend_rejects_jax_flags(self, income_slot: SlotSpec, tax_slot: SlotSpec):
        with pytest.raises(ValueError):
            MethodSignature(
                name="bad_non_jax",
                namespace="test",
                version="1.0.0",
                input_slots=frozenset({income_slot}),
                output_slots=frozenset({tax_slot}),
                parameters=(),
                fidelity=FidelityLevel.LOW,
                complexity=ComplexityClass.O_1,
                backend=ComputeBackend.NUMPY,
                supports_jit=True,
                supports_vmap=False,
                supports_grad=False,
            )


class TestHashing:
    def test_identical_units_same_hash(self):
        u1 = Unit("currency", "USD", 1.0)
        u2 = Unit("currency", "USD", 1.0)
        assert hash(u1) == hash(u2)

    def test_different_dimension_different_hash(self):
        u1 = Unit("currency", "USD")
        u2 = Unit("ratio", "USD")
        assert hash(u1) != hash(u2)

    def test_slot_usable_in_frozenset(self):
        s1 = SlotSpec(name="a", slot_type=SlotType.SCALAR, unit=Units.UAH)
        s2 = SlotSpec(name="b", slot_type=SlotType.SCALAR, unit=Units.UAH)
        s3 = SlotSpec(name="a", slot_type=SlotType.SCALAR, unit=Units.UAH)
        slots = frozenset({s1, s2, s3})
        assert len(slots) == 2

    def test_contract_id_participates_in_slot_identity(self):
        s1 = SlotSpec(name="a", slot_type=SlotType.SCALAR, unit=Units.UAH, contract_id="c1")
        s2 = SlotSpec(name="a", slot_type=SlotType.SCALAR, unit=Units.UAH, contract_id="c2")
        assert hash(s1) != hash(s2)
        assert s1 != s2

    def test_output_capability_participates_in_slot_identity_and_digest(self):
        plain = SlotSpec(
            name="result",
            slot_type=SlotType.SCALAR,
            unit=Unit("value", "json"),
            contract_id="test.output.v1",
        )
        capable = SlotSpec(
            name="result",
            slot_type=SlotType.SCALAR,
            unit=Unit("value", "json"),
            contract_id="test.output.v1",
            contract_capabilities=frozenset(
                {OutputContractCapability.VALUE_UNCERTAINTY_PROJECTION}
            ),
            contract_owner="tests.native:Output",
        )

        assert plain != capable
        assert hash(plain) != hash(capable)
        assert plain.stable_digest() != capable.stable_digest()

    def test_output_contract_rejects_incomplete_projection_interface(self):
        class _IncompleteProjectionOwner:
            contract_id = "test.incomplete_projection.v1"
            output_contract_declaration = value_uncertainty_output_contract(contract_id)

            def to_value_uncertainty(self, *, estimand: object) -> None:
                del estimand
                return None

        with pytest.raises(ValueError, match="output_contract_value_projector_missing"):
            SlotSpec.for_output_contract(
                "result",
                SlotType.SCALAR,
                Unit("value", "json"),
                output_contract=_IncompleteProjectionOwner,
            )

    def test_array_param_hashable(self):
        arr = jnp.array([0.1, 0.2, 0.3])
        p = ParameterSpec(name="rates", default=arr, is_static=False)
        assert isinstance(hash(p), int)


class TestStableDigests:
    def test_unit_stable_digest_deterministic(self):
        u1 = Unit("currency", "USD", 1.0)
        u2 = Unit("currency", "USD", 1.0)
        u3 = Unit("currency", "EUR", 1.0)
        assert u1.stable_digest() == u2.stable_digest()
        assert u1.stable_digest() != u3.stable_digest()

    def test_parameter_stable_digest_for_arrays(self):
        arr1 = jnp.array([0.1, 0.2, 0.3])
        arr2 = jnp.array([0.1, 0.2, 0.3])
        p1 = ParameterSpec(name="rates", default=arr1, is_static=False)
        p2 = ParameterSpec(name="rates", default=arr2, is_static=False)
        assert p1.stable_digest() == p2.stable_digest()

    def test_signature_abi_digest_deterministic(self, flat_tax_signature: MethodSignature):
        sig2 = MethodSignature(
            name=flat_tax_signature.name,
            namespace=flat_tax_signature.namespace,
            version=flat_tax_signature.version,
            input_slots=flat_tax_signature.input_slots,
            output_slots=flat_tax_signature.output_slots,
            parameters=flat_tax_signature.parameters,
            fidelity=flat_tax_signature.fidelity,
            complexity=flat_tax_signature.complexity,
        )
        assert flat_tax_signature.abi_digest() == sig2.abi_digest()

    def test_signature_backend_default_keeps_legacy_digest(
        self,
        flat_tax_signature: MethodSignature,
    ):
        explicit_default = MethodSignature(
            name=flat_tax_signature.name,
            namespace=flat_tax_signature.namespace,
            version=flat_tax_signature.version,
            input_slots=flat_tax_signature.input_slots,
            output_slots=flat_tax_signature.output_slots,
            parameters=flat_tax_signature.parameters,
            fidelity=flat_tax_signature.fidelity,
            complexity=flat_tax_signature.complexity,
            backend=ComputeBackend.JAX,
        )
        assert flat_tax_signature.abi_digest() == explicit_default.abi_digest()


class TestProperties:
    def test_fqn_format(self, flat_tax_signature: MethodSignature):
        assert flat_tax_signature.fqn == "fiscal.taxation.flat_tax@1.0.0"

    def test_static_param_names(self, progressive_tax_signature: MethodSignature):
        assert "n_brackets" in progressive_tax_signature.static_param_names
        assert "bracket_rates" not in progressive_tax_signature.static_param_names

    def test_dynamic_param_names(self, progressive_tax_signature: MethodSignature):
        assert "bracket_rates" in progressive_tax_signature.dynamic_param_names
        assert "n_brackets" not in progressive_tax_signature.dynamic_param_names

    def test_get_input_slot(self, flat_tax_signature: MethodSignature):
        slot = flat_tax_signature.get_input_slot("gross_income")
        assert slot is not None
        assert slot.name == "gross_income"

    def test_get_output_slot(self, flat_tax_signature: MethodSignature):
        slot = flat_tax_signature.get_output_slot("tax_due")
        assert slot is not None
        assert slot.name == "tax_due"


class TestParseFqn:
    def test_parse_fqn(self):
        namespace, name, version = parse_fqn("a.b.c@1.2.3")
        assert namespace == "a.b"
        assert name == "c"
        assert version == "1.2.3"
