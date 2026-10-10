from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest

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
from polisyos.foundry.methods.exceptions import MethodContractError


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestMorris:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "sensitivity.global.morris@1.0.0")
        rng = np.random.default_rng(42)
        n_trajectories, n_factors = 10, 3
        state = {
            "model_outputs": rng.normal(0, 1, size=(n_trajectories, n_factors + 1)),
            "parameter_levels": rng.uniform(0, 1, size=(n_trajectories, n_factors + 1, n_factors)),
        }
        result = method.pure_step(state, {})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "sensitivity.global.morris@1.0.0")
        rng = np.random.default_rng(0)
        n_trajectories, n_factors = 8, 2
        state = {
            "model_outputs": rng.normal(0, 1, size=(n_trajectories, n_factors + 1)),
            "parameter_levels": rng.uniform(0, 1, size=(n_trajectories, n_factors + 1, n_factors)),
        }
        result = method.pure_step(state, {})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))


def _register_morris_source(registry, *, rank_two_levels: bool = False) -> str:
    """Register a source that emits genuine OAT levels and their model outputs."""
    n_trajectories, n_factors = 3, 2
    levels = np.empty((n_trajectories, n_factors + 1, n_factors), dtype=float)
    for trajectory in range(n_trajectories):
        current = np.full(n_factors, 0.25, dtype=float)
        levels[trajectory, 0] = current
        for step in range(n_factors):
            current = current.copy()
            current[(step + trajectory) % n_factors] = 0.75
            levels[trajectory, step + 1] = current

    model_outputs = levels.sum(axis=2)
    parameter_levels = levels[0] if rank_two_levels else levels
    parameter_shape = (
        ("n_factors_plus_1", "n_factors")
        if rank_two_levels
        else ("n_trajectories", "n_factors_plus_1", "n_factors")
    )

    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        del state, params
        return {
            "model_outputs": model_outputs,
            "parameter_levels": parameter_levels,
        }

    producer = type(
        "MorrisInputSource",
        (),
        {
            "signature": MethodSignature(
                name="morris_input_source_rank_two" if rank_two_levels else "morris_input_source",
                namespace="tests.sensitivity.screening",
                version="1.0.0",
                input_slots=frozenset(),
                output_slots=frozenset(
                    {
                        SlotSpec(
                            "model_outputs",
                            SlotType.MATRIX,
                            Unit("response", "value"),
                            shape=("n_trajectories", "n_factors_plus_1"),
                        ),
                        SlotSpec(
                            "parameter_levels",
                            SlotType.TENSOR,
                            Unit("level", "value"),
                            shape=parameter_shape,
                        ),
                    }
                ),
                parameters=(),
                fidelity=FidelityLevel.LOW,
                complexity=ComplexityClass.O_N,
                backend=ComputeBackend.NUMPY,
                supports_jit=False,
                supports_vmap=False,
                supports_grad=False,
            ),
            "metadata": MethodMetadata(
                description="Controlled test producer for Morris OAT inputs.",
                tags=frozenset({"test", "sensitivity", "morris"}),
            ),
            "pure_step": staticmethod(pure_step),
        },
    )
    return registry.register(producer)


def _morris_chain(registry, *, rank_two_levels: bool = False):
    source_fqn = _register_morris_source(registry, rank_two_levels=rank_two_levels)
    composer = MethodComposer(registry=registry)
    source = composer.add(source_fqn)
    screening = composer.add("sensitivity.global.morris@1.0.0")
    composer.connect(source, screening)
    return composer.build(validate_semantics=False)


def test_morris_dispatches_real_three_dimensional_chain(isolated_registry) -> None:
    execution = execute_heterogeneous_chain(
        _morris_chain(isolated_registry),
        state={},
        registry=isolated_registry,
        seed=13,
    )

    assert len(execution.node_results) == 2
    result = execution.final_state["result"]
    assert result["n_trajectories"] == 3
    assert result["n_factors"] == 2
    np.testing.assert_allclose(result["mu_star"], np.ones(2), atol=1e-12)


def test_morris_chain_rejects_rank_two_levels(isolated_registry) -> None:
    with pytest.raises(
        MethodContractError,
        match="input slot 'parameter_levels' expected rank 3, got 2",
    ):
        execute_heterogeneous_chain(
            _morris_chain(isolated_registry, rank_two_levels=True),
            state={},
            registry=isolated_registry,
            seed=13,
        )
