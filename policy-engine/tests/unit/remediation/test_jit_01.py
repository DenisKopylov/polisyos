"""Deterministic witnesses for the JIT-01 compiler repairs."""

from __future__ import annotations

import concurrent.futures
import sys
import threading
import time
from collections.abc import Mapping
from contextlib import contextmanager
from typing import Any, NamedTuple

import jax.numpy as jnp
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
    output_names = tuple(sorted(slot.name for slot in output_slots))

    def materialize_input(bound_inputs, fallback_state):
        # These fixture methods deliberately consume a complete namedtuple.
        # Make that contract explicit while still consuming the actual binding.
        if hasattr(fallback_state, "_replace"):
            return fallback_state._replace(**bound_inputs)
        if len(bound_inputs) == 1:
            return next(iter(bound_inputs.values()))
        return fallback_state

    def dematerialize_output(output):
        return {slot: getattr(output, slot, output) for slot in output_names}

    return type(
        f"{name.title().replace('_', '')}Method",
        (),
        {
            "signature": signature,
            "metadata": metadata,
            "pure_step": staticmethod(pure_step),
            "materialize_input": staticmethod(materialize_input),
            "dematerialize_output": staticmethod(dematerialize_output),
        },
    )


@contextmanager
def _observe_bodies(calls, **methods):
    """Count actual body entries outside the method implementation closures."""
    names = {method.__code__: name for name, method in methods.items()}

    def observe(frame, event, arg):
        del arg
        if event == "call" and frame.f_code in names:
            calls[names[frame.f_code]] += 1

    previous = sys.getprofile()
    sys.setprofile(observe)
    try:
        yield
    finally:
        sys.setprofile(previous)


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
    first_publish_entered = threading.Event()
    release_publish = threading.Event()
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
    original_publish = cache.publish_flight
    publish_calls = 0

    def gated_publish(*args, **kwargs):
        nonlocal publish_calls
        publish_calls += 1
        if publish_calls == 1:
            first_publish_entered.set()
            assert release_publish.wait(timeout=2)
        return original_publish(*args, **kwargs)

    cache.publish_flight = gated_publish
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
            with cache._flight_lock:
                in_flight = tuple(cache._flights.values())
            if in_flight:
                break
            time.sleep(0.001)
        else:
            pytest.fail("follower did not join the in-flight compilation")

        release_compile.set()
        assert first_publish_entered.wait(timeout=2)
        assert not duplicate_compile_entered.wait(timeout=0.2)
        release_publish.set()

        leader_result = leader.result(timeout=2)
        follower_result = follower.result(timeout=2)

    assert calls == 1
    assert leader_result is follower_result


def test_single_flight_is_shared_by_compiler_instances(scalar_slots):
    value_slot, result_slot = scalar_slots

    def pure_step(state: ScalarState, params: Mapping[str, Any]) -> ScalarState:
        return state._replace(result=state.value * params["coefficient"])

    method = _method(
        name="shared_single_flight_scale",
        namespace="jit01",
        input_slots=frozenset({value_slot}),
        output_slots=frozenset({result_slot}),
        parameters=(ParameterSpec("coefficient", default=2.0, is_static=False),),
        pure_step=pure_step,
    )
    registry = MethodRegistry.get_instance()
    registry.register(method)

    cache = CompilationCache()
    first_compile_started = threading.Event()
    release_compile = threading.Event()
    calls = 0

    class CoordinatedCompiler(MethodCompiler):
        def _compile_method(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                first_compile_started.set()
                assert release_compile.wait(timeout=2)
            return super()._compile_method(*args, **kwargs)

    compiler_a = CoordinatedCompiler(registry=registry, cache=cache)
    compiler_b = CoordinatedCompiler(registry=registry, cache=cache)
    state = ScalarState(value=jnp.asarray(10.0), result=jnp.asarray(0.0))

    def compile_one(compiler: MethodCompiler):
        return compiler.compile(
            method_name="jit01.shared_single_flight_scale@1.0.0",
            params={"coefficient": 2.0},
            sample_inputs={"value": state.value},
            jit=False,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        leader = executor.submit(compile_one, compiler_a)
        assert first_compile_started.wait(timeout=2)
        follower = executor.submit(compile_one, compiler_b)

        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            with cache._flight_lock:
                if cache._flights:
                    break
            time.sleep(0.001)
        else:
            pytest.fail("second compiler did not join the shared flight")

        release_compile.set()
        leader_result = leader.result(timeout=2)
        follower_result = follower.result(timeout=2)

    assert calls == 1
    assert leader_result is follower_result


def test_single_flight_follower_honors_deadline_and_cancellation(scalar_slots):
    value_slot, result_slot = scalar_slots

    def pure_step(state: ScalarState, params: Mapping[str, Any]) -> ScalarState:
        return state._replace(result=state.value * params["coefficient"])

    method = _method(
        name="bounded_single_flight_scale",
        namespace="jit01",
        input_slots=frozenset({value_slot}),
        output_slots=frozenset({result_slot}),
        parameters=(ParameterSpec("coefficient", default=2.0, is_static=False),),
        pure_step=pure_step,
    )
    registry = MethodRegistry.get_instance()
    registry.register(method)

    cache = CompilationCache()
    leader_started = threading.Event()
    release_leader = threading.Event()
    calls = 0

    class HangingCompiler(MethodCompiler):
        def _compile_method(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                leader_started.set()
                assert release_leader.wait(timeout=2)
            return super()._compile_method(*args, **kwargs)

    compiler = HangingCompiler(registry=registry, cache=cache)
    state = ScalarState(value=jnp.asarray(10.0), result=jnp.asarray(0.0))

    def compile_leader():
        return compiler.compile(
            method_name="jit01.bounded_single_flight_scale@1.0.0",
            params={"coefficient": 2.0},
            sample_inputs={"value": state.value},
            jit=False,
        )

    def compile_follower(*, cancel_event=None):
        return compiler.compile(
            method_name="jit01.bounded_single_flight_scale@1.0.0",
            params={"coefficient": 2.0},
            sample_inputs={"value": state.value},
            jit=False,
            flight_timeout=0.05,
            cancel_event=cancel_event,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        leader = executor.submit(compile_leader)
        assert leader_started.wait(timeout=2)

        timed_out = executor.submit(compile_follower)
        with pytest.raises(CompilationError, match="deadline"):
            timed_out.result(timeout=1)

        cancelled_event = threading.Event()
        cancelled = executor.submit(compile_follower, cancel_event=cancelled_event)
        cancelled_event.set()
        with pytest.raises(CompilationError, match="cancelled"):
            cancelled.result(timeout=1)

        assert calls == 1
        release_leader.set()
        leader.result(timeout=2)


def test_single_flight_retries_when_invalidation_wins_result_delivery(
    scalar_slots,
    monkeypatch,
):
    value_slot, result_slot = scalar_slots

    def pure_step(state: ScalarState, params: Mapping[str, Any]) -> ScalarState:
        return state._replace(result=state.value * params["coefficient"])

    method = _method(
        name="invalidation_race_scale",
        namespace="jit01",
        input_slots=frozenset({value_slot}),
        output_slots=frozenset({result_slot}),
        parameters=(ParameterSpec("coefficient", default=2.0, is_static=False),),
        pure_step=pure_step,
    )
    registry = MethodRegistry.get_instance()
    registry.register(method)

    cache = CompilationCache()
    first_compile_started = threading.Event()
    release_compile = threading.Event()
    publication_ready = threading.Event()
    release_publication = threading.Event()
    follower_wait_entered = threading.Event()
    release_follower = threading.Event()
    publish_calls = 0
    calls = 0

    class CountingCompiler(MethodCompiler):
        def _compile_method(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                first_compile_started.set()
                assert release_compile.wait(timeout=2)
            return super()._compile_method(*args, **kwargs)

    compiler_a = CountingCompiler(registry=registry, cache=cache)
    compiler_b = CountingCompiler(registry=registry, cache=cache)
    original_publish = cache.publish_flight
    original_wait = compiler_module._wait_for_flight
    wait_calls = 0

    def gated_publish(*args, **kwargs):
        nonlocal publish_calls
        publish_calls += 1
        if publish_calls == 1:
            published = original_publish(*args, **kwargs)
            publication_ready.set()
            assert release_publication.wait(timeout=2)
            return published
        return original_publish(*args, **kwargs)

    def gated_wait(*args, **kwargs):
        nonlocal wait_calls
        result = original_wait(*args, **kwargs)
        wait_calls += 1
        if wait_calls == 1:
            follower_wait_entered.set()
            assert release_follower.wait(timeout=2)
        return result

    cache.publish_flight = gated_publish
    monkeypatch.setattr(compiler_module, "_wait_for_flight", gated_wait)
    state = ScalarState(value=jnp.asarray(10.0), result=jnp.asarray(0.0))

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        leader = executor.submit(
            compiler_a.compile,
            method_name="jit01.invalidation_race_scale@1.0.0",
            params={"coefficient": 2.0},
            sample_inputs={"value": state.value},
            jit=False,
        )
        assert first_compile_started.wait(timeout=2)
        follower = executor.submit(
            compiler_b.compile,
            method_name="jit01.invalidation_race_scale@1.0.0",
            params={"coefficient": 2.0},
            sample_inputs={"value": state.value},
            jit=False,
        )
        release_compile.set()
        assert publication_ready.wait(timeout=2)
        assert follower_wait_entered.wait(timeout=2)
        assert cache.invalidate_all() == 1
        release_publication.set()
        release_follower.set()
        leader_result = leader.result(timeout=2)
        follower_result = follower.result(timeout=2)

    assert calls == 2
    assert publish_calls == 2
    assert cache.stats["generation"] == 1
    assert leader_result is follower_result
    assert cache.get(leader_result.specialization) is leader_result


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
        return state._replace(total=jnp.sum(state.values))

    def result_step(state: ChainState, params: Mapping[str, Any]) -> ChainState:
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
    with _observe_bodies(calls, sum=sum_step, result=result_step):
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
        return state._replace(unknown=state.values[: int(params.get("count", 1))])

    def consumer(state: UnknownShapeState, params: Mapping[str, Any]) -> UnknownShapeState:
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
    with (
        _observe_bodies(calls, producer=producer, consumer=consumer),
        pytest.raises(CompilationError, match="data-dependent"),
    ):
        compiler.compile_chain(chain, sample_state, jit=False, infer_shapes=True)
    assert calls == {"producer": 0, "consumer": 0}
