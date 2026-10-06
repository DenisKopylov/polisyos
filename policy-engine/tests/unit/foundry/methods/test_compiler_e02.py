"""E02 actual-kernel specialization and failed-publication witnesses."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from typing import Any, NamedTuple

import jax.numpy as jnp
import pytest

from polisyos.foundry.methods.base import (
    ComplexityClass,
    FidelityLevel,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.compiler import CompilationCache, MethodCompiler
from polisyos.foundry.methods.compiler.specialization import BackendSpec
from polisyos.foundry.methods.exceptions import CompilationError


class _State(NamedTuple):
    value: Any
    result: Any


class _Method:
    signature = MethodSignature(
        name="axes",
        namespace="e02",
        version="1.0.0",
        input_slots=frozenset({SlotSpec("value", SlotType.VECTOR, Unit("x", "x"), shape=("n",))}),
        output_slots=frozenset({SlotSpec("result", SlotType.VECTOR, Unit("x", "x"), shape=("n",))}),
        parameters=(
            ParameterSpec("offset", default=0.0, is_static=True),
            ParameterSpec("scale", default=2.0, is_static=False),
        ),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
    )

    @staticmethod
    def pure_step(state: _State, params: Any) -> _State:
        return state._replace(result=state.value * params["scale"] + params["offset"])


class _Registry:
    def get(self, name: str) -> type[_Method]:
        assert name == "e02.axes@1.0.0"
        return _Method


@pytest.mark.parametrize("axis", ["static", "shape", "dtype", "backend"])
def test_real_invocation_preserves_warm_kernel_and_invalidates_each_axis(axis: str) -> None:
    """A key difference is proven by separate invoked kernels, not its string alone."""
    compiler = MethodCompiler(registry=_Registry(), cache=CompilationCache())
    backend = BackendSpec.current()
    state = _State(jnp.array([10.0], dtype=jnp.float32), jnp.zeros((1,)))
    arguments = {"sample_inputs": {"value": state.value}, "backend": backend, "jit": True}
    cold = compiler.compile("e02.axes@1.0.0", params={"scale": 2.0}, **arguments)
    warm = compiler.compile("e02.axes@1.0.0", params={"scale": 3.0}, **arguments)
    assert cold._kernel is warm._kernel
    assert cold.step_fn(state, {}).result.tolist() == [20.0]
    assert warm.step_fn(state, {}).result.tolist() == [30.0]
    assert cold.step_fn(state, {}).result.tolist() == [20.0]

    params = {"scale": 3.0}
    if axis == "static":
        params["offset"] = 5.0
    elif axis == "shape":
        state = _State(jnp.array([10.0, 11.0]), jnp.zeros((2,)))
    elif axis == "dtype":
        state = _State(jnp.array([10], dtype=jnp.int32), jnp.zeros((1,)))
    else:
        arguments["backend"] = replace(backend, config_fingerprint="independent-e02-axis")
    arguments["sample_inputs"] = {"value": state.value}
    changed = compiler.compile("e02.axes@1.0.0", params=params, **arguments)
    assert changed._kernel is not cold._kernel
    expected = [35.0] if axis == "static" else [30.0, 33.0] if axis == "shape" else [30.0]
    assert changed.step_fn(state, {}).result.tolist() == expected


def test_failed_publication_unblocks_followers_and_next_build() -> None:
    """A failure at publication releases the flight after real kernel construction."""
    cache = CompilationCache()
    compiler = MethodCompiler(registry=_Registry(), cache=cache)
    entered = threading.Event()
    proceed = threading.Event()
    follower_joined = threading.Event()
    original_publish = cache.publish_flight
    original_claim = cache.claim_flight

    def fail_publish(*args: Any, **kwargs: Any) -> bool:
        entered.set()
        assert proceed.wait(timeout=2)
        raise OSError("injected cache publication failure")

    def observe_claim(*args: Any, **kwargs: Any) -> Any:
        flight, leader = original_claim(*args, **kwargs)
        if not leader:
            follower_joined.set()
        return flight, leader

    cache.publish_flight = fail_publish
    cache.claim_flight = observe_claim

    def build() -> Any:
        return compiler.compile(
            "e02.axes@1.0.0", sample_inputs={"value": jnp.array([10.0])}, jit=False
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        leader = executor.submit(build)
        assert entered.wait(timeout=2)
        follower = executor.submit(build)
        assert follower_joined.wait(timeout=2)
        proceed.set()
        for future in [leader, follower]:
            with pytest.raises(CompilationError, match="publication failure"):
                future.result(timeout=2)

    assert cache._flights == {}
    cache.publish_flight = original_publish
    repaired = build()
    assert repaired.step_fn(_State(jnp.array([10.0]), jnp.zeros((1,))), {}).result.tolist() == [
        20.0
    ]
