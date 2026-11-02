"""Deterministic witnesses for the JIT-01 compiler repairs."""

from __future__ import annotations

import concurrent.futures
import json
import threading
import time
import tracemalloc
from collections.abc import Mapping
from dataclasses import replace
from typing import Any, NamedTuple

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
from polisyos.foundry.methods.compiler import CompilationCache, MethodCompiler, reset_global_cache
from polisyos.foundry.methods.components.composer import MethodComposer
from polisyos.foundry.methods.exceptions import CompilationError, ParameterValidationError
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
    fresh = MethodCompiler(registry=registry, cache=CompilationCache()).compile(
        method_name=method.signature.fqn,
        params={"coefficient": 3.0},
        sample_inputs={"value": state.value},
        jit=True,
    )
    assert float(fresh(state, {}).result.block_until_ready()) == 30.0
    assert cold._kernel is warm._kernel
    assert fresh._kernel is not warm._kernel
    assert float(warm(state, {"coefficient": 4.0}).result.block_until_ready()) == 40.0
    assert float(cold(state, {}).result.block_until_ready()) == 20.0
    with pytest.raises(ParameterValidationError, match="Unknown dynamic"):
        warm(state, {"undeclared": 4.0})


def test_native_array_defaults_and_static_override_admission(scalar_slots):
    value, result = scalar_slots

    def pure_step(state, params):
        return state._replace(result=state.value * params["coefficient"] + params["offset"])

    method = _method(
        name="vector_defaults",
        namespace="jit01",
        input_slots=frozenset({value}),
        output_slots=frozenset({result}),
        parameters=(
            ParameterSpec("coefficient", default=2.0, is_static=False),
            ParameterSpec("offset", default=0.0, is_static=True),
        ),
        pure_step=pure_step,
    )
    registry = MethodRegistry.get_instance()
    registry.register(method)
    compiler = MethodCompiler(registry=registry, cache=CompilationCache())
    state = ScalarState(jnp.asarray(10.0), jnp.zeros((2,)))
    first = compiler.compile(
        method.signature.fqn, {"coefficient": jnp.asarray([2.0, 3.0])}, {"value": state.value}
    )
    second = compiler.compile(
        method.signature.fqn, {"coefficient": jnp.asarray([4.0, 5.0])}, {"value": state.value}
    )
    assert first._kernel is second._kernel
    np.testing.assert_array_equal(first(state, {}).result.block_until_ready(), [20.0, 30.0])
    np.testing.assert_array_equal(second(state, {}).result.block_until_ready(), [40.0, 50.0])
    np.testing.assert_array_equal(first(state, {}).result.block_until_ready(), [20.0, 30.0])
    with pytest.raises(ParameterValidationError, match="Static parameters"):
        first(state, {"offset": 1.0})


def test_native_dispatcher_keeps_current_defaults_seed_and_selected_implementation(scalar_slots):
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
    from polisyos.foundry.methods.backends.jax_runner import JaxRunner
    from polisyos.foundry.methods.base import ComputeBackend
    from polisyos.foundry.methods.selection.history import SelectionHistoryStore

    value, result = scalar_slots

    def first_step(state, params):
        draw = jax.random.uniform(params["__rng__"], shape=state.shape, dtype=state.dtype)
        return state * params["coefficient"] + params["__seed__"] + draw

    def second_step(state, params):
        return first_step(state, params) + 100.0

    methods = [
        _method(
            name="selected_dispatch",
            namespace="jit01",
            input_slots=frozenset({value}),
            output_slots=frozenset({result}),
            parameters=(ParameterSpec("coefficient", default=2.0, is_static=False),),
            pure_step=step,
        )
        for step in (first_step, second_step)
    ]
    registry = MethodRegistry.get_instance()
    registry.register(methods[0])
    builds = []
    selected = []
    actual_calls = []
    kernels = []

    class ObservedCompiler(MethodCompiler):
        def _compile_method(self, *args, **kwargs):
            builds.append(kwargs["method_class"])
            return super()._compile_method(*args, **kwargs)

        def _compile_resolved(self, *, method_class, params, **kwargs):
            selected.append((method_class, dict(params)))
            compiled = super()._compile_resolved(method_class=method_class, params=params, **kwargs)
            kernels.append(compiled._kernel)

            def observed(state, runtime_params):
                actual_calls.append(
                    (runtime_params["__seed__"], np.asarray(runtime_params["__rng__"]))
                )
                return compiled(state, runtime_params)

            return replace(compiled, step_fn=observed)

    compiler = ObservedCompiler(registry=registry, cache=CompilationCache())
    dispatcher = MethodDispatcher(
        runtime_history=SelectionHistoryStore(), enable_runtime_selection=False
    )
    dispatcher.register_runner(JaxRunner(compiler))
    state = jnp.asarray(10.0, dtype=jnp.float32)
    requests = [
        (methods[0], 2.0, 7),
        (methods[0], 3.0, 7),
        (methods[1], 3.0, 7),
        (methods[0], 3.0, 8),
    ]
    for method, coefficient, seed in requests:
        response = dispatcher.dispatch(
            method_class=method,
            signature=method.signature,
            state=state,
            params={"coefficient": coefficient},
            seed=seed,
        )
        expected = (
            10.0 * coefficient
            + seed
            + float(jax.random.uniform(jax.random.PRNGKey(seed), shape=(), dtype=jnp.float32))
        )
        if method is methods[1]:
            expected += 100.0
        assert float(response.output.block_until_ready()) == pytest.approx(expected, abs=1e-5)
        assert response.reproducibility.backend is ComputeBackend.JAX
        assert response.reproducibility.seed == seed
    assert builds == methods
    assert kernels[0] is kernels[1] is kernels[3]
    assert kernels[2] is not kernels[0]
    assert selected == [
        (method, {"coefficient": coefficient}) for method, coefficient, _ in requests
    ]
    for (actual_seed, key), (_, _, expected_seed) in zip(actual_calls, requests, strict=True):
        assert actual_seed == expected_seed
        np.testing.assert_array_equal(key, np.asarray(jax.random.PRNGKey(expected_seed)))


@pytest.mark.parametrize("fault_at", ["recheck", "build", "publication"])
@pytest.mark.parametrize("base_exception", [False, True])
def test_all_leader_terminal_failures_release_actual_joined_follower(
    scalar_slots,
    fault_at,
    base_exception,
):
    value, result = scalar_slots
    role = threading.local()
    claimed = threading.Event()
    joined = threading.Event()

    class ControlledStop(BaseException):
        pass

    def fail():
        error = ControlledStop if base_exception else RuntimeError
        raise error(f"controlled-{fault_at}")

    class TerminalCache(CompilationCache):
        def _recheck_after_claim(self, *args, **kwargs):
            if role.name == "leader" and fault_at == "recheck":
                fail()
            return super()._recheck_after_claim(*args, **kwargs)

        def claim_flight(self, key):
            flight, leader = super().claim_flight(key)
            if leader:
                claimed.set()
                assert joined.wait(timeout=5)
            else:
                joined.set()
            return flight, leader

        def _put_unlocked(self, *args, **kwargs):
            if fault_at == "publication":
                fail()
            return super()._put_unlocked(*args, **kwargs)

    class TerminalCompiler(MethodCompiler):
        def _compile_method(self, *args, **kwargs):
            if fault_at == "build":
                fail()
            return super()._compile_method(*args, **kwargs)

    def step(state, params):
        return state._replace(result=state.value * 2)

    method = _method(
        name="terminal_paths",
        namespace="jit01",
        input_slots=frozenset({value}),
        output_slots=frozenset({result}),
        pure_step=step,
    )
    registry = MethodRegistry.get_instance()
    registry.register(method)
    cache = TerminalCache()
    compiler = TerminalCompiler(registry=registry, cache=cache)

    def compile_one(name):
        role.name = name
        return compiler.compile(method.signature.fqn, sample_inputs={"value": jnp.asarray(10.0)})

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(compile_one, "leader")
        assert claimed.wait(timeout=5)
        follower = pool.submit(compile_one, "follower")
        errors = [future.exception(timeout=5) for future in (leader, follower)]
    expected = ControlledStop if base_exception else CompilationError
    assert all(isinstance(error, expected) for error in errors)
    assert all(f"controlled-{fault_at}" in str(error) for error in errors)
    assert cache._flights == {} and cache.stats["size"] == 0


@pytest.mark.parametrize("timeout", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_flight_timeout_refuses_before_registry_or_build(timeout):
    cache = CompilationCache()
    compiler = MethodCompiler(registry=object(), cache=cache)
    with pytest.raises(ValueError, match="finite and greater than zero"):
        compiler.compile("not.looked.up@1.0.0", flight_timeout=timeout)
    assert cache._flights == {} and cache.stats["size"] == 0


def test_explicit_native_warmup_counts_three_actual_invocations(scalar_slots):
    value, result = scalar_slots
    calls = []
    traces = []

    def step(state, params):
        traces.append("trace")
        return state._replace(result=state.value * 2)

    method = _method(
        name="explicit_warmup",
        namespace="jit01",
        input_slots=frozenset({value}),
        output_slots=frozenset({result}),
        pure_step=step,
    )
    registry = MethodRegistry.get_instance()
    registry.register(method)

    class ObservedCompiler(MethodCompiler):
        def compile(self, *args, **kwargs):
            compiled = super().compile(*args, **kwargs)

            def observed(state, params):
                calls.append("invocation")
                output = compiled(state, params)
                assert float(output.result.block_until_ready()) == 20.0
                return output

            return replace(compiled, step_fn=observed)

    compiler = ObservedCompiler(registry=registry, cache=CompilationCache())
    state = ScalarState(jnp.asarray(10.0), jnp.asarray(0.0))
    compiler.warmup(method.signature.fqn, {}, {"value": state.value}, state, n_warmup=3)
    assert calls == ["invocation"] * 3
    assert traces == ["trace"]


def test_cache_miss_before_new_claim_reuses_published_kernel_and_wakes_joined_follower(
    scalar_slots,
):
    """A genuine earlier miss must not duplicate a just-published native wrapper."""
    value_slot, result_slot = scalar_slots

    def pure_step(state: ScalarState, params: Mapping[str, Any]) -> ScalarState:
        return state._replace(result=state.value * params["coefficient"])

    method = _method(
        name="miss_claim_scale",
        namespace="jit01",
        input_slots=frozenset({value_slot}),
        output_slots=frozenset({result_slot}),
        parameters=(ParameterSpec("coefficient", default=2.0, is_static=False),),
        pure_step=pure_step,
    )
    registry = MethodRegistry.get_instance()
    registry.register(method)
    role = threading.local()
    build_started = threading.Event()
    finish_build = threading.Event()
    delayed_missed = threading.Event()
    follower_missed = threading.Event()
    allow_new_claim = threading.Event()
    new_claimed = threading.Event()
    follower_joined = threading.Event()
    builds = 0

    class CoordinatedCache(CompilationCache):
        def claim_flight(self, key):
            current = role.name
            if current == "delayed":
                delayed_missed.set()
                assert allow_new_claim.wait(timeout=5)
            elif current == "follower":
                follower_missed.set()
                assert new_claimed.wait(timeout=5)
            flight, leader = super().claim_flight(key)
            if current == "delayed":
                assert leader
                new_claimed.set()
                assert follower_joined.wait(timeout=5)
            elif current == "follower":
                assert not leader
                follower_joined.set()
            return flight, leader

    class CountingCompiler(MethodCompiler):
        def _compile_method(self, *args, **kwargs):
            nonlocal builds
            builds += 1
            if builds == 1:
                build_started.set()
                assert finish_build.wait(timeout=5)
            return super()._compile_method(*args, **kwargs)

    cache = CoordinatedCache()
    first = CountingCompiler(registry=registry, cache=cache)
    second = CountingCompiler(registry=registry, cache=cache)
    state = ScalarState(value=jnp.asarray(10.0), result=jnp.asarray(0.0))

    def compile_one(name, compiler, coefficient):
        role.name = name
        return compiler.compile(
            method_name=method.signature.fqn,
            params={"coefficient": coefficient},
            sample_inputs={"value": state.value},
            jit=True,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        leader = pool.submit(compile_one, "leader", first, 2.0)
        assert build_started.wait(timeout=5)
        delayed = pool.submit(compile_one, "delayed", second, 3.0)
        follower = pool.submit(compile_one, "follower", first, 4.0)
        assert delayed_missed.wait(timeout=5)
        assert follower_missed.wait(timeout=5)
        finish_build.set()
        old = leader.result(timeout=5)
        assert not cache._flights
        allow_new_claim.set()
        current = delayed.result(timeout=5)
        joined = follower.result(timeout=5)

    assert builds == 1
    assert old._kernel is current._kernel is joined._kernel
    assert [
        float(handle(state, {}).result.block_until_ready()) for handle in (old, current, joined)
    ] == [
        20.0,
        30.0,
        40.0,
    ]
    assert float(old(state, {}).result.block_until_ready()) == 20.0
    assert not cache._flights


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


def test_declared_shape_metadata_does_not_invent_downstream_dtype(record_property, tmp_path):
    """Native lazy tracing consumes the producer's actual integer output."""
    unit = Unit("value", "unit")
    values = SlotSpec("values", SlotType.VECTOR, unit, shape=("n",))
    total = SlotSpec("total", SlotType.SCALAR, unit, shape=())
    result = SlotSpec("result", SlotType.SCALAR, unit, shape=())
    traces = {"producer": [], "consumer": []}

    def produce(state, params):
        traces["producer"].append(str(state.values.dtype))
        return state._replace(total=jnp.asarray(jnp.sum(state.values), dtype=jnp.int32))

    def consume(state, params):
        traces["consumer"].append(str(state.total.dtype))
        return state._replace(result=state.total * 2)

    registry = MethodRegistry.get_instance()
    for name, inputs, outputs, fn in (
        ("dtype_producer", {values}, {total}, produce),
        ("dtype_consumer", {total}, {result}, consume),
    ):
        registry.register(
            _method(
                name=name,
                namespace="jit01",
                input_slots=frozenset(inputs),
                output_slots=frozenset(outputs),
                pure_step=fn,
            )
        )
    composer = MethodComposer(registry=registry)
    a = composer.add("jit01.dtype_producer@1.0.0")
    b = composer.add("jit01.dtype_consumer@1.0.0")
    composer.connect(a, b)
    chain = composer.build()
    state = ChainState(
        jnp.asarray([1.25, 1.75], dtype=jnp.float32),
        jnp.zeros((7,), dtype=jnp.float32),
        jnp.asarray(0.0, dtype=jnp.float32),
    )
    compiler = MethodCompiler(registry=registry, cache=CompilationCache())
    started = time.perf_counter()
    executor = compiler.compile_chain(chain, state)
    wrapper_seconds = time.perf_counter() - started
    assert traces == {"producer": [], "consumer": []}
    started = time.perf_counter()
    warm = compiler.compile_chain(chain, state)
    warm_wrapper_seconds = time.perf_counter() - started
    assert traces == {"producer": [], "consumer": []}
    assert all(
        x[1]._kernel is y[1]._kernel
        for x, y in zip(executor.compiled_methods, warm.compiled_methods, strict=True)
    )
    downstream = executor.compiled_methods[1][1]
    declared = dict(downstream.specialization.input_shapes)["total"]
    started = time.perf_counter()
    first = executor(state)
    first.result.block_until_ready()
    first_seconds = time.perf_counter() - started
    assert int(first.result) == 6
    assert str(first.total.dtype) == str(first.result.dtype) == "int32"
    started = time.perf_counter()
    second = warm(state)
    second.result.block_until_ready()
    warm_seconds = time.perf_counter() - started
    assert int(second.result) == 6
    assert traces == {"producer": ["float32"], "consumer": ["int32"]}
    # Explicit diagnostic stages are outside prepare and do no numerical step.
    current = state._replace(total=jnp.asarray(3, dtype=jnp.int32))
    started = time.perf_counter()
    traced = downstream._kernel.step_core.trace(current, (), {})
    trace_seconds = time.perf_counter() - started
    started = time.perf_counter()
    lowered = traced.lower()
    lower_seconds = time.perf_counter() - started
    started = time.perf_counter()
    machine = lowered.compile()
    machine_seconds = time.perf_counter() - started
    assert int(machine(current, (), {}).result.block_until_ready()) == 6
    # A different actual runtime dtype causes a native trace, not a guessed cast.
    float_current = current._replace(total=jnp.asarray(3.0, dtype=jnp.float32))
    floating = downstream(float_current, {})
    assert float(floating.result.block_until_ready()) == 6.0
    assert "float32" in traces["consumer"]
    profile = {
        "jax": jax.__version__,
        "jax_enable_x64": jax.config.jax_enable_x64,
        "backend": jax.default_backend(),
        "planning_dtype": declared.dtype,
        "actual_dtype": str(first.total.dtype),
        "explicit_stage_cache_state": "after first and warm execution; may reuse native caches",
        "timing_claim": "separate observed calls, not cold phase costs or speedup",
        "traces": traces,
        "wrapper_seconds": wrapper_seconds,
        "warm_wrapper_seconds": warm_wrapper_seconds,
        "trace_seconds": trace_seconds,
        "lower_seconds": lower_seconds,
        "machine_compile_seconds": machine_seconds,
        "first_execution_seconds": first_seconds,
        "warm_execution_seconds": warm_seconds,
    }
    record_property("native_dtype_profile", json.dumps(profile, sort_keys=True))
    assert declared.shape == ()
    assert declared.dtype == "unknown"
    assert state.total.shape == (7,) and str(state.total.dtype) == "float32"
    from polisyos.foundry.methods.artifacts import MethodArtifact

    artifact = MethodArtifact.from_method(
        registry.get("jit01.dtype_consumer@1.0.0"), downstream.specialization
    )
    path = tmp_path / "prepared-method.json"
    path.write_bytes(artifact.to_canonical_bytes())
    reopened = MethodArtifact.from_canonical_bytes(path.read_bytes())
    assert reopened.specialization == downstream.specialization
    assert dict(reopened.specialization.input_shapes)["total"].dtype == "unknown"


def test_declared_shape_preparation_keeps_metadata_without_output_allocation(
    monkeypatch,
    record_property,
):
    """Large declared shapes stay abstract rather than reserving output storage."""
    unit = Unit("value", "unit")
    values = SlotSpec("values", SlotType.VECTOR, unit, shape=("n",))
    total = SlotSpec("total", SlotType.VECTOR, unit, shape=("n",))
    calls = []

    def step(state, params):
        calls.append("executed")
        return state._replace(total=state.values)

    registry = MethodRegistry.get_instance()
    method = _method(
        name="abstract_output",
        namespace="jit01",
        input_slots=frozenset({values}),
        output_slots=frozenset({total}),
        pure_step=step,
    )
    registry.register(method)
    composer = MethodComposer(registry=registry)
    composer.add(method.signature.fqn)
    chain = composer.build()
    original_empty = np.empty

    def bounded_empty(shape, *args, **kwargs):
        assert np.prod(shape) < 100_000, "declared shape unexpectedly allocates output storage"
        return original_empty(shape, *args, **kwargs)

    monkeypatch.setattr(compiler_module.np, "empty", bounded_empty)
    compiler = MethodCompiler(registry=registry, cache=CompilationCache())
    observations = []
    for size in (16, 1_000_000_000):
        sample = ChainState(
            jax.ShapeDtypeStruct((size,), np.float32),
            jax.ShapeDtypeStruct((size,), np.float32),
            jax.ShapeDtypeStruct((), np.float32),
        )
        tracemalloc.start()
        executor = compiler.compile_chain(chain, sample)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert len(executor) == 1 and calls == []
        observations.append({"elements": size, "traced_python_peak_bytes": peak})
    record_property("abstract_shape_allocation", json.dumps(observations))
    assert observations[1]["traced_python_peak_bytes"] < 1_000_000
