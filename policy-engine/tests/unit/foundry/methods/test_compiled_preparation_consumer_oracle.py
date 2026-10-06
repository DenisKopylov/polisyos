"""Independent seeded numerical consumers of compiler preparation and warmup.

The random primitive is the actual JAX backend. The numerical oracle separately
combines its known seeded draws with Python/NumPy arithmetic; this is not an
independent validation of JAX's random-number implementation or distribution.
"""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, ClassVar, NamedTuple

import jax
import jax.numpy as jnp
import numpy as np
import pytest

import polisyos.foundry.methods.compiler as compiler_module
from polisyos.foundry.methods.base import (
    ComplexityClass,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.compiler import CompilationCache, MethodCompiler
from polisyos.foundry.methods.components.composer import MethodComposer
from polisyos.foundry.methods.selection.registry import MethodRegistry


class _State(NamedTuple):
    values: Any
    draws: Any
    total: Any


def _slot(name: str, shape: tuple[str, ...] = ()) -> SlotSpec:
    return SlotSpec(
        name, SlotType.VECTOR if shape else SlotType.SCALAR, Unit("value", "1"), shape=shape
    )


class _Draw:
    signature: ClassVar = MethodSignature(
        name="draw",
        namespace="tests.independent_preparation",
        version="1.0.0",
        input_slots=frozenset({_slot("values", ("n",))}),
        output_slots=frozenset({_slot("draws", ("n",))}),
        parameters=(
            ParameterSpec("seed", default=11),
            ParameterSpec("scale", default=0.5, is_static=True),
        ),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
    )
    metadata: ClassVar = MethodMetadata(description="Known-shape real JAX seeded draw")

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: _State) -> _State:
        return fallback_state._replace(**bound_inputs)

    @staticmethod
    def dematerialize_output(output: _State) -> dict[str, Any]:
        return {"draws": output.draws}

    @staticmethod
    def pure_step(state: _State, params: Mapping[str, Any]) -> _State:
        noise = jax.random.uniform(jax.random.PRNGKey(params["seed"]), state.values.shape)
        return state._replace(draws=state.values + params["scale"] * noise)


class _Reduce:
    signature: ClassVar = MethodSignature(
        name="reduce",
        namespace="tests.independent_preparation",
        version="1.0.0",
        input_slots=frozenset({_slot("draws", ("n",))}),
        output_slots=frozenset({_slot("total")}),
        parameters=(ParameterSpec("offset", default=0.25),),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        requires=frozenset({_Draw.signature.fqn}),
    )
    metadata: ClassVar = MethodMetadata(description="Actual bound stochastic draw reduction")

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: _State) -> _State:
        return fallback_state._replace(**bound_inputs)

    @staticmethod
    def dematerialize_output(output: _State) -> dict[str, Any]:
        return {"total": output.total}

    @staticmethod
    def pure_step(state: _State, params: Mapping[str, Any]) -> _State:
        return state._replace(total=jnp.sum(state.draws * state.draws) + params["offset"])


def _state() -> _State:
    values = jnp.asarray([1.0, -2.0, 0.5, 3.0], dtype=jnp.float32)
    return _State(values, jnp.zeros_like(values), jnp.asarray(0.0, dtype=jnp.float32))


def _oracle(state: _State, seed: int, scale: float, offset: float) -> tuple[np.ndarray, float]:
    """Use the backend RNG, then separately recompute the numerical transformation."""
    noise = np.asarray(jax.random.uniform(jax.random.PRNGKey(seed), state.values.shape))
    draws = np.asarray(state.values) + np.float32(scale) * noise
    return draws, math.fsum(float(value) ** 2 for value in draws) + offset


def _owner(scale: float) -> tuple[MethodCompiler, Any, Any, Any]:
    registry = MethodRegistry._create_fresh()
    registry.register(_Draw)
    registry.register(_Reduce)
    composer = MethodComposer(registry=registry)
    reducer = composer.add(_Reduce.signature.fqn)
    producer = composer.add(_Draw.signature.fqn, scale=scale)
    composer.connect(producer, reducer)
    return (
        MethodCompiler(registry=registry, cache=CompilationCache()),
        composer.build(),
        producer,
        reducer,
    )


@contextmanager
def _body_observer() -> Iterator[dict[str, int]]:
    calls = {"draw": 0, "reduce": 0}
    codes = {_Draw.pure_step.__code__: "draw", _Reduce.pure_step.__code__: "reduce"}
    previous = sys.getprofile()

    def observe(frame: Any, event: str, _arg: Any) -> None:
        if event == "call" and frame.f_code in codes:
            calls[codes[frame.f_code]] += 1

    sys.setprofile(observe)
    try:
        yield calls
    finally:
        sys.setprofile(previous)


@pytest.mark.parametrize("jit", [False, True])
@pytest.mark.parametrize("infer_shapes", [False, True])
def test_cold_warm_preparation_preserves_independent_seeded_numerical_repetitions(
    tmp_path: Path, jit: bool, infer_shapes: bool
) -> None:
    state = _state()
    compiler, chain, producer, reducer = _owner(scale=0.5)
    observations: dict[str, Any] = {"jit": jit, "infer_shapes": infer_shapes, "repetitions": []}
    with _body_observer() as calls:
        cold = compiler.compile_chain(chain, state, jit=jit, infer_shapes=infer_shapes)
        warm = compiler.compile_chain(chain, state, jit=jit, infer_shapes=infer_shapes)
        assert calls == {"draw": 0, "reduce": 0}
        observations["preparation_body_entries"] = dict(calls)
        for index, seed in enumerate((11, 23, 47, 11)):
            executor = cold if index == 0 else warm
            result = executor(state, {producer.id: {"seed": seed}, reducer.id: {"offset": 0.75}})
            result.total.block_until_ready()
            expected_draws, expected_total = _oracle(state, seed, 0.5, 0.75)
            np.testing.assert_allclose(
                np.asarray(result.draws), expected_draws, rtol=1e-6, atol=1e-7
            )
            assert float(result.total) == pytest.approx(expected_total, rel=1e-6)
            observations["repetitions"].append(
                {
                    "seed": seed,
                    "draws": np.asarray(result.draws).tolist(),
                    "total": float(result.total),
                    "oracle_total": expected_total,
                }
            )
        assert observations["repetitions"][0] == observations["repetitions"][3]
        assert len({row["total"] for row in observations["repetitions"]}) == 3
        assert calls == {"draw": 1 if jit else 4, "reduce": 1 if jit else 4}
        observations["runtime_python_body_entries"] = dict(calls)
    np.testing.assert_array_equal(np.asarray(state.draws), np.zeros(4, dtype=np.float32))
    # A different static specialization has its own real result; dynamic seed
    # repetitions above did not reuse an earlier scientific result.
    second_compiler, second_chain, second_producer, _ = _owner(scale=1.5)
    with _body_observer() as second_calls:
        second = second_compiler.compile_chain(
            second_chain, state, jit=jit, infer_shapes=infer_shapes
        )
        assert second_calls == {"draw": 0, "reduce": 0}
        result = second(state, {second_producer.id: {"seed": 23}})
        result.total.block_until_ready()
    expected_draws, expected_total = _oracle(state, 23, 1.5, 0.25)
    np.testing.assert_allclose(np.asarray(result.draws), expected_draws, rtol=1e-6, atol=1e-7)
    assert float(result.total) == pytest.approx(expected_total, rel=1e-6)
    observations["different_static_result"] = {
        "scale": 1.5,
        "seed": 23,
        "total": float(result.total),
        "oracle_total": expected_total,
    }
    (tmp_path / "numerical-observations.json").write_text(json.dumps(observations, indent=2) + "\n")


def test_explicit_numerical_warmup_is_separate_from_preparation_and_future_seeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _state()
    compiler, chain, producer, _ = _owner(scale=0.5)
    warmed_outputs: list[list[float]] = []
    original_block = compiler_module._block_until_ready

    def record_actual_warmup(value: _State) -> None:
        original_block(value)
        warmed_outputs.append(np.asarray(value.draws).tolist())

    monkeypatch.setattr(compiler_module, "_block_until_ready", record_actual_warmup)
    with _body_observer() as calls:
        compiler.compile_chain(chain, state, jit=True, infer_shapes=True)
        assert calls == {"draw": 0, "reduce": 0}
        handle = compiler.warmup(
            _Draw.signature.fqn,
            params={"seed": 997, "scale": 0.5},
            sample_inputs={"values": state.values},
            sample_state=state,
            n_warmup=2,
        )
        assert calls == {"draw": 1, "reduce": 0}
        expected, _ = _oracle(state, 997, 0.5, 0.0)
        assert len(warmed_outputs) == 2
        for output in warmed_outputs:
            np.testing.assert_allclose(output, expected, rtol=1e-6, atol=1e-7)
        prepared = compiler.compile_chain(chain, state, jit=True, infer_shapes=True)
        assert calls == {"draw": 1, "reduce": 0}
        actual = prepared(state, {producer.id: {"seed": 23}})
        actual.total.block_until_ready()
        expected_draws, expected_total = _oracle(state, 23, 0.5, 0.25)
        np.testing.assert_allclose(np.asarray(actual.draws), expected_draws, rtol=1e-6, atol=1e-7)
        assert float(actual.total) == pytest.approx(expected_total, rel=1e-6)
        direct = handle(state, {"seed": 47})
        direct.draws.block_until_ready()
        expected_direct, _ = _oracle(state, 47, 0.5, 0.0)
        np.testing.assert_allclose(np.asarray(direct.draws), expected_direct, rtol=1e-6, atol=1e-7)
    observations = {
        "explicit_warmup_numerical_outputs": warmed_outputs,
        "following_seed": 23,
        "following_total": float(actual.total),
        "following_oracle_total": expected_total,
        "direct_seed": 47,
        "direct_draws": np.asarray(direct.draws).tolist(),
    }
    (tmp_path / "numerical-observations.json").write_text(json.dumps(observations, indent=2) + "\n")
