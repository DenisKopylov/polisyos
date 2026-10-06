"""Actual JAX/cache and compiled-edge consumers for the current E02 lane."""

from __future__ import annotations

import sys
import threading
from dataclasses import replace
from typing import ClassVar, NamedTuple

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
from polisyos.foundry.methods.compiler import CompilationCache, MethodCompiler
from polisyos.foundry.methods.components.composer import MethodComposer
from polisyos.foundry.methods.exceptions import CompilationError
from polisyos.foundry.methods.selection.registry import MethodRegistry


def _slot(name):
    return SlotSpec(name, SlotType.SCALAR, Unit("count", "1"), shape=())


_SIGNATURE = MethodSignature(
    name="scale",
    namespace="tests.compiler_e02",
    version="1.0.0",
    input_slots=frozenset({_slot("value")}),
    output_slots=frozenset({_slot("result")}),
    parameters=(ParameterSpec("factor", default=2.0),),
    fidelity=FidelityLevel.LOW,
    complexity=ComplexityClass.O_1,
)
_METADATA = MethodMetadata(description="Actual JAX compiler arithmetic", tags=frozenset({"test"}))


class _State(NamedTuple):
    value: object
    result: object


class _Original:
    signature: ClassVar = _SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return state._replace(result=state.value * params["factor"])


class _Replacement:
    signature: ClassVar = _SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return state._replace(result=state.value * (params["factor"] + 1))


class _HelperSource:
    signature: ClassVar = _SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def scale(value, factor):
        return value * factor

    @staticmethod
    def pure_step(state, params):
        return state._replace(result=_HelperSource.scale(state.value, params["factor"]))


def _changed_scale(value, factor):
    return value * (factor + 1)


def _compiler(method=_Original, cache=None):
    registry = MethodRegistry._create_fresh()
    registry.register(method)
    return MethodCompiler(registry=registry, cache=cache or CompilationCache()), registry


def _handle(compiler, factor=2.0):
    return compiler.compile(
        _SIGNATURE.fqn,
        params={"factor": factor},
        sample_inputs={"value": jnp.asarray(10.0)},
        jit=True,
    )


def _value(handle):
    return float(handle(_State(jnp.asarray(10.0), jnp.asarray(0.0)), {}).result.block_until_ready())


def test_real_jax_same_fqn_source_replacement_matches_cold_preserves_old_handle():
    compiler, registry = _compiler()
    old = _handle(compiler)
    assert _value(old) == 20
    registry.register(_Replacement, override=True)
    warm = _handle(compiler)
    cold = _handle(MethodCompiler(registry=registry, cache=CompilationCache()))
    assert _value(cold) == _value(warm) == 30
    assert _value(old) == 20
    assert warm._kernel is not old._kernel


def test_real_jax_same_class_helper_replacement_matches_cold_preserves_old_handle():
    compiler, registry = _compiler(_HelperSource)
    old = _handle(compiler)
    assert _value(old) == 20
    original = vars(_HelperSource)["scale"]
    try:
        _HelperSource.scale = staticmethod(_changed_scale)
        warm = _handle(compiler)
        cold = _handle(MethodCompiler(registry=registry, cache=CompilationCache()))
        assert _value(cold) == _value(warm) == 30
        assert _value(old) == 20
        assert warm._kernel is not old._kernel
    finally:
        _HelperSource.scale = original


def test_actual_miss_before_claim_rechecks_peer_terminal_publication():
    first_miss = threading.Event()
    release_first = threading.Event()
    build_lock = threading.Lock()

    class PausedCache(CompilationCache):
        def get(self, *args, **kwargs):
            result = super().get(*args, **kwargs)
            if (
                result is None
                and threading.current_thread().name == "e02-first-compiler"
                and not first_miss.is_set()
            ):
                first_miss.set()
                assert release_first.wait(5), "fixture peer did not publish"
            return result

    class CountingCompiler(MethodCompiler):
        builds = 0

        def _compile_method(self, *args, **kwargs):
            with build_lock:
                self.builds += 1
            return super()._compile_method(*args, **kwargs)

    cache = PausedCache()
    _, registry = _compiler(cache=cache)
    compiler = CountingCompiler(registry=registry, cache=cache)
    first_handles, errors = [], []

    def first():
        try:
            first_handles.append(_handle(compiler))
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=first, name="e02-first-compiler")
    thread.start()
    try:
        assert first_miss.wait(5), "fixture did not reach the real cache miss"
        second = _handle(compiler)
        assert _value(second) == 20
    finally:
        release_first.set()
        thread.join(5)
    assert not thread.is_alive(), "owned compiler did not drain"
    assert not errors
    assert _value(first_handles[0]) == 20
    assert compiler.builds == 1
    assert first_handles[0]._kernel is second._kernel


def test_unestablished_mutable_code_capture_is_typed_compiler_boundary():
    factors = [2]

    class Mutable:
        signature: ClassVar = _SIGNATURE
        metadata: ClassVar = _METADATA

        @staticmethod
        def pure_step(state, params):
            return state._replace(result=state.value * factors[0])

    compiler, _ = _compiler(Mutable)
    with pytest.raises(CompilationError, match="source identity is unavailable for list"):
        _handle(compiler)
    control, _ = _compiler()
    assert _value(_handle(control)) == 20


_PRODUCER_SIGNATURE = replace(
    _SIGNATURE,
    name="producer",
    output_slots=frozenset({_slot("product")}),
    parameters=(ParameterSpec("factor", default=2.0, is_static=True),),
)
_CONSUMER_SIGNATURE = replace(
    _SIGNATURE,
    name="consumer",
    input_slots=frozenset({_slot("operand")}),
    parameters=(ParameterSpec("increment", default=1.0),),
    requires=frozenset({_PRODUCER_SIGNATURE.fqn}),
)


class _Producer:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": state["value"] * params["factor"]}


class _Consumer:
    signature: ClassVar = _CONSUMER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"result": state + params["increment"]}


@pytest.mark.parametrize("jit", [False, True])
def test_real_required_compiled_alias_edge_has_no_numeric_preparation(jit):
    registry = MethodRegistry._create_fresh()
    registry.register(_Producer)
    registry.register(_Consumer)
    composer = MethodComposer(registry=registry)
    consumer = composer.add(_CONSUMER_SIGNATURE.fqn, increment=1.0)
    producer = composer.add(_PRODUCER_SIGNATURE.fqn, factor=2.0)
    composer.connect(producer, consumer, {"product": "operand"})
    chain = composer.build()
    compiler = MethodCompiler(registry=registry, cache=CompilationCache())
    # Observe actual Python body entries outside their scientific closures.
    # JIT tracing and numerical execution remain distinct observations.
    code_names = {
        _Producer.pure_step.__code__: "producer",
        _Consumer.pure_step.__code__: "consumer",
    }
    calls = {"producer": 0, "consumer": 0}

    def observe(frame, event, arg):
        del arg
        if event == "call" and frame.f_code in code_names:
            calls[code_names[frame.f_code]] += 1

    previous = sys.getprofile()
    sys.setprofile(observe)
    try:
        cold = compiler.compile_chain(chain, {"value": jnp.asarray(3.0)}, jit=jit)
        warm = compiler.compile_chain(chain, {"value": jnp.asarray(3.0)}, jit=jit)
        assert calls == {"producer": 0, "consumer": 0}
        shape = dict(cold.compiled_methods[1][1].specialization.input_shapes)["operand"]
        assert shape.shape == ()
        first = cold({"value": jnp.asarray(3.0)})
        second = warm({"value": jnp.asarray(3.0)})
        assert float(first["result"].block_until_ready()) == 7
        assert float(second["result"].block_until_ready()) == 7
        expected = 1 if jit else 2
        assert calls == {"producer": expected, "consumer": expected}
    finally:
        sys.setprofile(previous)
