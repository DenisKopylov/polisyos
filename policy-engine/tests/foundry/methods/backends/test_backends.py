from __future__ import annotations

from typing import Any, ClassVar

import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.methods import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodComposer,
    MethodMetadata,
    MethodRegistry,
    MethodSignature,
    ParameterSpec,
    execute_heterogeneous_chain,
)
from polisyos.foundry.methods.backends.adapters import adapt_state
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.jax_runner import JaxRunner
from polisyos.foundry.methods.backends.numpy_runner import NumpyRunner
from polisyos.foundry.methods.backends.solver_runner import SolverRunner


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _register_method(cls: type) -> type:
    registry = MethodRegistry.get_instance()
    registry.register(cls, override=True)
    return cls


class _JaxIncrement:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="jax_increment",
        namespace="tests.polyglot",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(ParameterSpec(name="delta", default=1.0),),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="jax increment")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> Any:
        return state + params["delta"]


class _NumpyIncrement:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="numpy_increment",
        namespace="tests.polyglot",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(ParameterSpec(name="delta", default=1.0),),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="numpy increment")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> Any:
        return np.asarray(state) + float(params["delta"])


class _SolverToy:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="solver_toy",
        namespace="tests.polyglot",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(ParameterSpec(name="x", default=1.0),),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.SOLVER,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="solver toy")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> tuple[dict[str, float], dict[str, Any]]:
        return (
            {"x": float(params["x"])},
            {"status": "optimal", "gap": 0.0, "iterations": 4},
        )


def test_adapters_roundtrip_between_jax_and_numpy():
    arr = jnp.array([1.0, 2.0], dtype=jnp.float32)
    as_numpy = adapt_state(
        arr,
        source_backend=ComputeBackend.JAX,
        target_backend=ComputeBackend.NUMPY,
    )
    assert isinstance(as_numpy, np.ndarray)
    as_jax = adapt_state(
        as_numpy,
        source_backend=ComputeBackend.NUMPY,
        target_backend=ComputeBackend.JAX,
    )
    assert np.allclose(np.asarray(as_jax), np.asarray(arr))


def test_numpy_runner_executes():
    method = _register_method(_NumpyIncrement)
    runner = NumpyRunner()
    result = runner.execute(
        method_class=method,
        signature=method.signature,
        state=np.array([1.0, 2.0]),
        params={"delta": 2.5},
        seed=42,
    )
    assert np.allclose(result.output, np.array([3.5, 4.5]))
    assert result.reproducibility.backend == ComputeBackend.NUMPY


def test_solver_runner_extracts_status():
    method = _register_method(_SolverToy)
    runner = SolverRunner()
    result = runner.execute(
        method_class=method,
        signature=method.signature,
        state={},
        params={"x": 3.0},
        seed=11,
    )
    assert result.output["x"] == 3.0
    assert result.reproducibility.solver_status is not None
    assert result.reproducibility.solver_status.value == "optimal"


def test_jax_runner_executes():
    method = _register_method(_JaxIncrement)
    runner = JaxRunner()
    result = runner.execute(
        method_class=method,
        signature=method.signature,
        state=jnp.array([1.0, 2.0]),
        params={"delta": 2.0},
        seed=0,
    )
    assert np.allclose(np.asarray(result.output), np.array([3.0, 4.0]))
    assert result.reproducibility.backend == ComputeBackend.JAX


def test_execute_heterogeneous_chain_numpy_to_jax():
    _register_method(_NumpyIncrement)
    _register_method(_JaxIncrement)

    composer = MethodComposer(registry=MethodRegistry.get_instance())
    node_np = composer.add("tests.polyglot.numpy_increment@1.0.0", delta=1.0)
    node_jax = composer.add("tests.polyglot.jax_increment@1.0.0", delta=2.0)
    chain = composer.build()

    result = execute_heterogeneous_chain(chain, state=np.array([1.0]))
    assert len(result.node_results) == 2
    assert np.allclose(np.asarray(result.final_state), np.array([4.0]))
    assert result.node_results[0][0] == node_np.id
    assert result.node_results[1][0] == node_jax.id

