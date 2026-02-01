"""
Test fixtures for Foundry Methods test suite.
"""
from __future__ import annotations

import os
from typing import Any, NamedTuple

import pytest

os.environ["JAX_PLATFORM_NAME"] = "cpu"
os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"

import jax.numpy as jnp

from polisyos.foundry.methods import (
    ComplexityClass,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.types.units import Units


@pytest.fixture
def sample_unit() -> Unit:
    return Units.UAH


@pytest.fixture
def custom_unit() -> Unit:
    return Unit("energy", "kWh", scale=1.0)


@pytest.fixture
def income_slot(sample_unit: Unit) -> SlotSpec:
    return SlotSpec(
        name="gross_income",
        slot_type=SlotType.VECTOR,
        unit=sample_unit,
        shape=("n_agents",),
        description="Gross income per agent",
        bounds=(0.0, None),
    )


@pytest.fixture
def tax_slot(sample_unit: Unit) -> SlotSpec:
    return SlotSpec(
        name="tax_due",
        slot_type=SlotType.VECTOR,
        unit=sample_unit,
        shape=("n_agents",),
        description="Tax amount due per agent",
        bounds=(0.0, None),
    )


@pytest.fixture
def rate_slot() -> SlotSpec:
    return SlotSpec(
        name="effective_rate",
        slot_type=SlotType.VECTOR,
        unit=Units.PERCENT,
        shape=("n_agents",),
        description="Effective tax rate per agent",
    )


@pytest.fixture
def scalar_slot() -> SlotSpec:
    return SlotSpec(
        name="total_revenue",
        slot_type=SlotType.SCALAR,
        unit=Units.UAH,
        shape=(),
        description="Total tax revenue",
    )


@pytest.fixture
def rate_param() -> ParameterSpec:
    return ParameterSpec(
        name="tax_rate",
        default=0.18,
        is_static=False,
        bounds=(0.0, 1.0),
        description="Flat tax rate",
    )


@pytest.fixture
def static_param() -> ParameterSpec:
    return ParameterSpec(
        name="n_brackets",
        default=5,
        is_static=True,
        bounds=(1, 20),
        description="Number of tax brackets",
    )


@pytest.fixture
def array_param() -> ParameterSpec:
    return ParameterSpec(
        name="bracket_rates",
        default=jnp.array([0.0, 0.18, 0.20, 0.22, 0.25]),
        is_static=False,
        description="Tax rates per bracket",
    )


@pytest.fixture
def flat_tax_signature(
    income_slot: SlotSpec,
    tax_slot: SlotSpec,
    rate_param: ParameterSpec,
) -> MethodSignature:
    return MethodSignature(
        name="flat_tax",
        namespace="fiscal.taxation",
        version="1.0.0",
        input_slots=frozenset({income_slot}),
        output_slots=frozenset({tax_slot}),
        parameters=(rate_param,),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        supports_jit=True,
        supports_vmap=True,
        supports_grad=True,
    )


@pytest.fixture
def progressive_tax_signature(
    income_slot: SlotSpec,
    tax_slot: SlotSpec,
    rate_slot: SlotSpec,
    static_param: ParameterSpec,
    array_param: ParameterSpec,
) -> MethodSignature:
    return MethodSignature(
        name="progressive_tax",
        namespace="fiscal.taxation",
        version="1.0.0",
        input_slots=frozenset({income_slot}),
        output_slots=frozenset({tax_slot, rate_slot}),
        parameters=(static_param, array_param),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        requires=frozenset(),
        conflicts_with=frozenset({"fiscal.taxation.flat_tax@1.0.0"}),
    )


@pytest.fixture
def minimal_signature() -> MethodSignature:
    return MethodSignature(
        name="noop",
        namespace="test",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
    )


@pytest.fixture
def sample_metadata() -> MethodMetadata:
    return MethodMetadata(
        description="A flat tax applies the same rate to all income levels.",
        tags=frozenset({"taxation", "fiscal", "simple"}),
        citations=("smith2020taxation", "jones2019policy"),
        equations={"tax": r"T = r * Y"},
    )


class FlatTaxState(NamedTuple):
    income: jnp.ndarray
    tax_due: jnp.ndarray


@pytest.fixture
def sample_state() -> FlatTaxState:
    return FlatTaxState(
        income=jnp.array([1000.0, 2000.0, 3000.0]),
        tax_due=jnp.zeros(3),
    )


@pytest.fixture
def sample_params() -> dict[str, Any]:
    return {"tax_rate": 0.18}


@pytest.fixture
def valid_method_class(flat_tax_signature: MethodSignature):
    class FlatTax:
        signature = flat_tax_signature
        metadata = MethodMetadata(
            description="Flat tax implementation",
            tags=frozenset({"test"}),
        )

        @staticmethod
        def pure_step(state: FlatTaxState, params: dict[str, Any]) -> FlatTaxState:
            tax = state.income * params["tax_rate"]
            return state._replace(tax_due=tax)

    return FlatTax
