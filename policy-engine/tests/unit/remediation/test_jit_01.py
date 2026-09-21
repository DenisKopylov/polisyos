"""Deterministic witnesses for the JIT-01 compiler repairs."""

from __future__ import annotations

import concurrent.futures
import threading
import time
from collections.abc import Mapping
from typing import Any, NamedTuple

import jax.numpy as jnp
import pytest

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
from polisyos.foundry.methods.compiler import CompilationCache, MethodCompiler, reset_global_cache
from polisyos.foundry.methods.components.composer import MethodComposer
from polisyos.foundry.methods.exceptions import CompilationError
from polisyos.foundry.methods.registry import MethodRegistry


class ScalarState(NamedTuple):
    value: jnp.ndarray
    result: jnp.ndarray


class ChainState(NamedTuple):
    values: jnp.ndarray
    total: jnp.ndarray
    result: jnp.ndarray


class UnknownShapeState(NamedTuple):
    values: jnp.ndarray
    unknown: jnp.ndarray
    result: jnp.ndarray


def _method(
    *,
    name: str,
    namespace: str,
    input_slots: frozenset[SlotSpec],
    output_slots: frozenset[SlotSpec],
    parameters: tuple[ParameterSpec, ...] = (),
    pure_step: Any,
) -> type:
    signature = MethodSignature(
        name=name,
        namespace=namespace,
        version="1.0.0",
        input_slots=input_slots,
        output_slots=output_slots,
        parameters=parameters,
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
    )
    metadata = MethodMetadata(description=f"JIT-01 witness: {name}", tags=frozenset({"test"}))
    return type(
        f"{name.title().replace('_', '')}Method",
        (),
        {"signature": signature, "metadata": metadata, "pure_step": staticmethod(pure_step)},
    )


@pytest.fixture(autouse=True)
def _reset_registry_and_cache():
    reset_global_cache()
    MethodRegistry.reset_instance()
    yield
    reset_global_cache()
    MethodRegistry.reset_instance()


@pytest.fixture
def scalar_slots() -> tuple[SlotSpec, SlotSpec]:
    unit = Unit("value", "unit")
    return (
        SlotSpec("value", SlotType.SCALAR, unit, shape=()),
        SlotSpec("result", SlotType.SCALAR, unit, shape=()),
    )


def test_dynamic_defaults_bind_per_handle_without_rebuilding_kernel(scalar_slots):
    value_slot, result_slot = scalar_slots
    builds = 0

    def pure_step(state: ScalarState, params: Mapping[str, Any]) -> ScalarState:
        return state._replace(result=state.value * params["coefficient"])

    method = _method(
        name="dynamic_scale",
        namespace="jit01",
        input_slots=frozenset({value_slot}),
        output_slots=frozenset({result_slot}),
        parameters=(ParameterSpec("coefficient", default=2.0, is_static=False),),
        pure_step=pure_step,
    )
    registry = MethodRegistry.get_instance()
    registry.register(method)

    class CountingCompiler(MethodCompiler):
        def _compile_method(self, *args, **kwargs):
            nonlocal builds
            builds += 1
            return super()._compile_method(*args, **kwargs)

    state = ScalarState(value=jnp.asarray(10.0), result=jnp.asarray(0.0))
    compiler = CountingCompiler(registry=registry, cache=CompilationCache())
    cold = compiler.compile(
        method_name="jit01.dynamic_scale@1.0.0",
        params={"coefficient": 2.0},
        sample_inputs={"value": state.value},
        jit=False,
    )
    warm = compiler.compile(
        method_name="jit01.dynamic_scale@1.0.0",
        params={"coefficient": 3.0},
        sample_inputs={"value": state.value},
        jit=False,
    )

    assert builds == 1
    assert cold is not warm
    assert float(cold.step_fn(state, {}).result) == 20.0
    assert float(warm.step_fn(state, {}).result) == 30.0


@pytest.mark.integration
def test_native_jax_dynamic_defaults_rebind_without_recompile(scalar_slots):
    value_slot, result_slot = scalar_slots

    def pure_step(state: ScalarState, params: Mapping[str, Any]) -> ScalarState:
        return state._replace(result=state.value * params["coefficient"])

    method = _method(
        name="native_scale",
        namespace="jit01",
        input_slots=frozenset({value_slot}),
        output_slots=frozenset({result_slot}),
        parameters=(ParameterSpec("coefficient", default=2.0, is_static=False),),
        pure_step=pure_step,
    )
    registry = MethodRegistry.get_instance()
    registry.register(method)

    state = ScalarState(value=jnp.asarray(10.0), result=jnp.asarray(0.0))
    compiler = MethodCompiler(registry=registry, cache=CompilationCache())
    cold = compiler.compile(
        method_name="jit01.native_scale@1.0.0",
        params={"coefficient": 2.0},
        sample_inputs={"value": state.value},
        jit=True,
    )
    warm = compiler.compile(
        method_name="jit01.native_scale@1.0.0",
        params={"coefficient": 3.0},
        sample_inputs={"value": state.value},
        jit=True,
    )

    assert float(cold.step_fn(state, {}).result) == 20.0
    assert float(warm.step_fn(state, {}).result) == 30.0


def test_single_flight_publishes_before_followers_are_notified(scalar_slots):
    value_slot, result_slot = scalar_slots

    def pure_step(state: ScalarState, params: Mapping[str, Any]) -> ScalarState:
        return state._replace(result=state.value * params["coefficient"])

    method = _method(
        name="single_flight_scale",
        namespace="jit01",
        input_slots=frozenset({value_slot}),
        output_slots=frozenset({result_slot}),
        parameters=(ParameterSpec("coefficient", default=2.0, is_static=False),),
        pure_step=pure_step,
    )
    registry = MethodRegistry.get_instance()
    registry.register(method)

    cache = CompilationCache()
    first_compile_returned = threading.Event()
    release_compile = threading.Event()
    first_put_entered = threading.Event()
    release_put = threading.Event()
    duplicate_compile_entered = threading.Event()
    calls = 0

    class CoordinatedCompiler(MethodCompiler):
        def _compile_method(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                first_compile_returned.set()
                assert release_compile.wait(timeout=2)
            else:
                duplicate_compile_entered.set()
            return super()._compile_method(*args, **kwargs)

    compiler = CoordinatedCompiler(registry=registry, cache=cache)
    original_put = cache.put
    put_calls = 0

    def gated_put(*args, **kwargs):
        nonlocal put_calls
        put_calls += 1
        if put_calls == 1:
            first_put_entered.set()
            assert release_put.wait(timeout=2)
        return original_put(*args, **kwargs)

    cache.put = gated_put
    state = ScalarState(value=jnp.asarray(10.0), result=jnp.asarray(0.0))

    def compile_one():
        return compiler.compile(
            method_name="jit01.single_flight_scale@1.0.0",
            params={"coefficient": 2.0},
            sample_inputs={"value": state.value},
            jit=False,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        leader = executor.submit(compile_one)
        assert first_compile_returned.wait(timeout=2)
        follower = executor.submit(compile_one)

        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            with compiler._inflight_lock:
                in_flight = tuple(compiler._inflight.values())
            if in_flight:
                break
            time.sleep(0.001)
        else:
            pytest.fail("follower did not join the in-flight compilation")

        release_compile.set()
        assert first_put_entered.wait(timeout=2)
        assert not duplicate_compile_entered.wait(timeout=0.2)
        release_put.set()

        leader_result = leader.result(timeout=2)
        follower_result = follower.result(timeout=2)

    assert calls == 1
    assert leader_result is follower_result


def test_single_flight_error_releases_all_followers(scalar_slots):
    value_slot, result_slot = scalar_slots

    def pure_step(state: ScalarState, params: Mapping[str, Any]) -> ScalarState:
        return state._replace(result=state.value * params["coefficient"])

    method = _method(
        name="failing_scale",
        namespace="jit01",
        input_slots=frozenset({value_slot}),
        output_slots=frozenset({result_slot}),
        parameters=(ParameterSpec("coefficient", default=2.0, is_static=False),),
        pure_step=pure_step,
    )
    registry = MethodRegistry.get_instance()
    registry.register(method)
    calls = 0
    failure_started = threading.Event()
    release_failure = threading.Event()

    class FailingCompiler(MethodCompiler):
        def _compile_method(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                failure_started.set()
                assert release_failure.wait(timeout=2)
            raise RuntimeError("controlled compile failure")

    compiler = FailingCompiler(registry=registry, cache=CompilationCache())
    state = ScalarState(value=jnp.asarray(10.0), result=jnp.asarray(0.0))

    def compile_one():
        return compiler.compile(
            method_name="jit01.failing_scale@1.0.0",
            params={"coefficient": 2.0},
            sample_inputs={"value": state.value},
            jit=False,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        leader = executor.submit(compile_one)
        assert failure_started.wait(timeout=2)
        followers = [executor.submit(compile_one) for _ in range(2)]
        time.sleep(0.05)
        release_failure.set()
        futures = [leader, *followers]
        errors = [future.exception(timeout=2) for future in futures]

    assert calls == 1
    assert all(isinstance(error, CompilationError) for error in errors)
    assert all("controlled compile failure" in str(error) for error in errors)


def test_chain_shape_inference_uses_declared_shapes_without_pure_step(scalar_slots):
    del scalar_slots
    unit = Unit("value", "unit")
    values_slot = SlotSpec("values", SlotType.VECTOR, unit, shape=("n",))
    total_slot = SlotSpec("total", SlotType.SCALAR, unit, shape=())
    result_slot = SlotSpec("result", SlotType.SCALAR, unit, shape=())
    calls = {"sum": 0, "result": 0}

    def sum_step(state: ChainState, params: Mapping[str, Any]) -> ChainState:
        calls["sum"] += 1
        return state._replace(total=jnp.sum(state.values))

    def result_step(state: ChainState, params: Mapping[str, Any]) -> ChainState:
        calls["result"] += 1
        return state._replace(result=state.total * 0.1)

    sum_method = _method(
        name="sum_values",
        namespace="jit01",
        input_slots=frozenset({values_slot}),
        output_slots=frozenset({total_slot}),
        pure_step=sum_step,
    )
    result_method = _method(
        name="make_result",
        namespace="jit01",
        input_slots=frozenset({total_slot}),
        output_slots=frozenset({result_slot}),
        pure_step=result_step,
    )
    registry = MethodRegistry.get_instance()
    registry.register(sum_method)
    registry.register(result_method)

    composer = MethodComposer(registry=registry)
    sum_node = composer.add("jit01.sum_values@1.0.0")
    result_node = composer.add("jit01.make_result@1.0.0")
    composer.connect(sum_node, result_node)
    chain = composer.build()
    sample_state = ChainState(
        values=jnp.ones((5,)),
        total=jnp.zeros((5,)),
        result=jnp.asarray(0.0),
    )

    compiler = MethodCompiler(registry=registry, cache=CompilationCache())
    executor = compiler.compile_chain(chain, sample_state, jit=False, infer_shapes=True)

    assert calls == {"sum": 0, "result": 0}
    total_shape = dict(executor.compiled_methods[1][1].specialization.input_shapes)["total"]
    assert total_shape.shape == ()

    output = executor(sample_state)
    assert calls == {"sum": 1, "result": 1}
    assert float(output.result) == 0.5


def test_chain_shape_inference_refuses_unknown_data_dependent_shape(scalar_slots):
    del scalar_slots
    unit = Unit("value", "unit")
    values_slot = SlotSpec("values", SlotType.VECTOR, unit, shape=("n",))
    unknown_slot = SlotSpec("unknown", SlotType.VECTOR, unit, shape=(None,))
    result_slot = SlotSpec("result", SlotType.SCALAR, unit, shape=())
    calls = {"producer": 0, "consumer": 0}

    def producer(state: UnknownShapeState, params: Mapping[str, Any]) -> UnknownShapeState:
        calls["producer"] += 1
        return state._replace(unknown=state.values[: int(params.get("count", 1))])

    def consumer(state: UnknownShapeState, params: Mapping[str, Any]) -> UnknownShapeState:
        calls["consumer"] += 1
        return state._replace(result=jnp.sum(state.unknown))

    producer_method = _method(
        name="data_dependent",
        namespace="jit01",
        input_slots=frozenset({values_slot}),
        output_slots=frozenset({unknown_slot}),
        pure_step=producer,
    )
    consumer_method = _method(
        name="consume_unknown",
        namespace="jit01",
        input_slots=frozenset({unknown_slot}),
        output_slots=frozenset({result_slot}),
        pure_step=consumer,
    )
    registry = MethodRegistry.get_instance()
    registry.register(producer_method)
    registry.register(consumer_method)

    composer = MethodComposer(registry=registry)
    producer_node = composer.add("jit01.data_dependent@1.0.0")
    consumer_node = composer.add("jit01.consume_unknown@1.0.0")
    composer.connect(producer_node, consumer_node)
    chain = composer.build()
    sample_state = UnknownShapeState(
        values=jnp.ones((5,)),
        unknown=jnp.ones((5,)),
        result=jnp.asarray(0.0),
    )

    compiler = MethodCompiler(registry=registry, cache=CompilationCache())
    with pytest.raises(CompilationError, match="data-dependent"):
        compiler.compile_chain(chain, sample_state, jit=False, infer_shapes=True)
    assert calls == {"producer": 0, "consumer": 0}
