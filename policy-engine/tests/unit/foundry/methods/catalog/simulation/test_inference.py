from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.foundry.methods import MethodComposer, execute_heterogeneous_chain
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)


def _register_seed_source(registry, output_slot: SlotSpec) -> str:
    """Register a small declared producer for an estimator's real input slot."""
    input_slot = SlotSpec(
        name="seed",
        slot_type=output_slot.slot_type,
        unit=output_slot.unit,
        shape=output_slot.shape,
    )

    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        return {output_slot.name: state["seed"]}

    producer = type(
        f"{output_slot.name.title()}SeedSource",
        (),
        {
            "signature": MethodSignature(
                name=f"seed_{output_slot.name}",
                namespace="tests.simulation.inference",
                version="1.0.0",
                input_slots=frozenset({input_slot}),
                output_slots=frozenset({output_slot}),
                parameters=(),
                fidelity=FidelityLevel.MEDIUM,
                complexity=ComplexityClass.O_N,
                backend=ComputeBackend.NUMPY,
                supports_jit=False,
                supports_vmap=False,
                supports_grad=False,
            ),
            "metadata": MethodMetadata(
                description="Test producer that forwards a declared input slot.",
                tags=frozenset({"test", "simulation", "inference"}),
            ),
            "pure_step": staticmethod(pure_step),
        },
    )
    return registry.register(producer)


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestMonteCarloInference:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "simulation.inference.monte_carlo@1.0.0")
        rng = np.random.default_rng(42)
        state = {"samples": rng.normal(5, 1, size=(100, 3))}
        result = method.pure_step(state, {"confidence_level": 0.95})
        assert isinstance(result, dict)


class TestBootstrapInference:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "simulation.inference.bootstrap@1.0.0")
        rng = np.random.default_rng(42)
        state = {"data": rng.normal(10, 2, size=50)}
        result = method.pure_step(state, {"n_bootstrap": 200, "confidence_level": 0.95, "seed": 42})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "simulation.inference.bootstrap@1.0.0")
        state = {"data": np.array([1.0, 2.0, 3.0, 4.0, 5.0])}
        result = method.pure_step(state, {"n_bootstrap": 100, "seed": 0})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))


class TestPermutationTest:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "simulation.inference.permutation_test@1.0.0")
        rng = np.random.default_rng(42)
        state = {
            "group_a": rng.normal(10, 2, size=20),
            "group_b": rng.normal(12, 2, size=20),
        }
        result = method.pure_step(state, {"n_permutations": 500, "seed": 42})
        assert isinstance(result, dict)

@pytest.mark.parametrize(
    ("method_fqn", "slot_name", "slot_type", "shape", "values", "params", "expected"),
    [
        (
            "simulation.inference.monte_carlo@1.0.0",
            "samples",
            SlotType.MATRIX,
            ("n_simulations", "n_outputs"),
            np.arange(12, dtype=float).reshape(6, 2),
            {},
            {"means": [5.0, 6.0], "n_simulations": 6},
        ),
        (
            "simulation.inference.bootstrap@1.0.0",
            "data",
            SlotType.VECTOR,
            ("n_obs",),
            np.arange(1, 6, dtype=float),
            {"n_bootstrap": 64, "seed": 7},
            {"point_estimate": 3.0, "n_bootstrap": 64},
        ),
    ],
)
def test_named_input_chain_result_survives_fresh_cas_read(
    isolated_registry,
    tmp_path,
    method_fqn,
    slot_name,
    slot_type,
    shape,
    values,
    params,
    expected,
) -> None:
    slot = SlotSpec(
        name=slot_name,
        slot_type=slot_type,
        unit=Unit("value", "amount"),
        shape=shape,
    )
    source_fqn = _register_seed_source(isolated_registry, slot)
    composer = MethodComposer(registry=isolated_registry)
    source = composer.add(source_fqn)
    estimator = composer.add(method_fqn, **params)
    composer.connect(source, estimator)

    execution = execute_heterogeneous_chain(
        composer.build(validate_semantics=False),
        state={"seed": values},
        registry=isolated_registry,
        seed=13,
    )

    assert len(execution.node_results) == 2
    assert isinstance(execution.final_state, Mapping)
    estimator_result = execution.final_state["result"]
    for key, value in expected.items():
        assert estimator_result[key] == value

    payload = json.dumps(
        execution.final_state, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    cas_root = tmp_path / "simulation-inference-cas"
    ref = FileSystemCAS(cas_root).put_bytes(
        payload,
        PutOptions(
            kind="test.foundry.simulation-inference-result",
            media_type="application/json",
            schema=SchemaInfo(name="test.simulation-inference-result", version="1.0.0"),
            producer=ProducerInfo(component="tests.simulation.inference", version="1.0.0"),
        ),
    )

    fresh_consumer = FileSystemCAS(cas_root)
    assert json.loads(fresh_consumer.get_bytes(ref)) == execution.final_state


@pytest.mark.parametrize(
    ("method_fqn", "slot_name"),
    [
        ("simulation.inference.monte_carlo@1.0.0", "samples"),
        ("simulation.inference.bootstrap@1.0.0", "data"),
    ],
)
def test_named_input_materializer_rejects_missing_or_malformed_slots(
    isolated_registry, method_fqn, slot_name
) -> None:
    method = isolated_registry.get(method_fqn)
    value = np.array([1.0, 2.0])
    malformed_cases = (
        ({}, {}),
        ({}, {f"{slot_name}_alias": value}),
        ({f"{slot_name}_alias": value}, {}),
        ({slot_name: value, "unexpected": value}, {}),
    )

    for bound_inputs, fallback_state in malformed_cases:
        with pytest.raises(ValueError, match=slot_name):
            method.materialize_input(bound_inputs, fallback_state)
