"""Selection-to-executable binding with colliding identities and warm caches."""

from __future__ import annotations

import concurrent.futures
import gc
import threading
import weakref
from dataclasses import replace
from typing import Any, ClassVar

import jax.numpy as jnp
import pytest

import polisyos.foundry.methods.backends.chain_executor as chain_executor
from polisyos.foundry.methods._internal.executable_identity import (
    _ExecutableIdentity,
    _signature_binding,
)
from polisyos.foundry.methods.backends.async_chain_executor import AsyncChainExecutionError
from polisyos.foundry.methods.backends.jax_runner import JaxRunner
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
from polisyos.foundry.methods.compiler import CompilationCache, MethodCompiler
from polisyos.foundry.methods.components.composer import MethodComposer
from polisyos.foundry.methods.exceptions import CompilationError, MethodContractError
from polisyos.foundry.methods.selection.registry import MethodRegistry

_SLOT = SlotSpec(name="signal", slot_type=SlotType.SCALAR, unit=Unit("none", "1"))
_PRODUCER_SIG = MethodSignature(
    name="selected",
    namespace="tests.c60_scope",
    version="1.0.0",
    input_slots=frozenset(),
    output_slots=frozenset({_SLOT}),
    parameters=(),
    fidelity=FidelityLevel.LOW,
    complexity=ComplexityClass.O_1,
    backend=ComputeBackend.JAX,
    supports_jit=True,
)
_CONSUMER_SIG = MethodSignature(
    name="consumer",
    namespace="tests.c60_scope",
    version="1.0.0",
    input_slots=frozenset({_SLOT}),
    output_slots=frozenset(),
    parameters=(),
    fidelity=FidelityLevel.LOW,
    complexity=ComplexityClass.O_1,
    backend=ComputeBackend.JAX,
    supports_jit=True,
)
_META = MethodMetadata(description="C60 selected implementation")


class _First:
    signature: ClassVar[MethodSignature] = _PRODUCER_SIG
    metadata: ClassVar[MethodMetadata] = _META

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> Any:
        return state + 1.0


class _Second:
    signature: ClassVar[MethodSignature] = _PRODUCER_SIG
    metadata: ClassVar[MethodMetadata] = _META

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> Any:
        return state + 10.0


class _Consumer:
    signature: ClassVar[MethodSignature] = _CONSUMER_SIG
    metadata: ClassVar[MethodMetadata] = _META

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> Any:
        return state * 3.0


def _registries_and_chain():
    first = MethodRegistry._create_fresh()
    second = MethodRegistry._create_fresh()

    class LocalFirst(_First):
        pass

    class LocalSecond(_Second):
        pass

    first.register(LocalFirst)
    first.register(_Consumer)
    second.register(LocalSecond)
    second.register(_Consumer)
    composer = MethodComposer(registry=first)
    producer = composer.add(_PRODUCER_SIG.fqn)
    consumer = composer.add(_CONSUMER_SIG.fqn)
    composer.connect(producer, consumer, {"signal": "signal"})
    return first, second, composer.build()


@pytest.mark.parametrize("executor_mode", ("sequential", "async"))
@pytest.mark.parametrize("order", (("first", "second"), ("second", "first")))
def test_public_registry_selection_survives_warmed_compiled_caches(
    executor_mode, order, monkeypatch
):
    """Identical FQN/signature does not authorize another registry's executable."""
    first, second, chain = _registries_and_chain()
    registries = {"first": first, "second": second}
    expected = {"first": 9.0, "second": 36.0}
    methods = {
        "first": first.get(_PRODUCER_SIG.fqn),
        "second": second.get(_PRODUCER_SIG.fqn),
    }
    assert methods["first"] is not methods["second"]
    fused_results = []
    fused_builds = []
    resolved_methods = []
    compiler_builds = []
    actual_fused_result = chain_executor._build_fused_result
    actual_fused_build = chain_executor._compile_fused_pair_kernel
    actual_resolved = MethodCompiler._compile_resolved
    actual_compiler_build = MethodCompiler._compile_method

    def observe_fused(*args, **kwargs):
        result = actual_fused_result(*args, **kwargs)
        fused_results.append(result)
        return result

    def observe_fused_build(*args, **kwargs):
        fused_builds.append(args[0])
        return actual_fused_build(*args, **kwargs)

    def observe_resolved(self, *, method_class, **kwargs):
        result = actual_resolved(self, method_class=method_class, **kwargs)
        resolved_methods.append(method_class)
        return result

    def observe_compiler_build(self, *args, **kwargs):
        compiler_builds.append(kwargs["method_class"])
        return actual_compiler_build(self, *args, **kwargs)

    monkeypatch.setattr(chain_executor, "_build_fused_result", observe_fused)
    monkeypatch.setattr(chain_executor, "_compile_fused_pair_kernel", observe_fused_build)
    monkeypatch.setattr(MethodCompiler, "_compile_resolved", observe_resolved)
    monkeypatch.setattr(MethodCompiler, "_compile_method", observe_compiler_build)
    # The class identities are fresh, but the process caches are not reset.
    # Warm one implementation, the other, then reuse both without clearing.
    seen = set()
    for choice in order + order[::-1]:
        prior_fused = len(fused_results)
        prior_resolved = len(resolved_methods)
        prior_fused_builds = len(fused_builds)
        prior_compiler_builds = len(compiler_builds)
        result = chain.execute_heterogeneous(
            state=jnp.asarray(2.0), registry=registries[choice], executor_mode=executor_mode
        )
        assert float(result.final_state) == pytest.approx(expected[choice])
        if executor_mode == "sequential":
            assert len(fused_results) == prior_fused + 2
            assert len(fused_builds) == prior_fused_builds + (choice not in seen)
            assert all(
                actual is recorded
                for (_, actual), recorded in zip(result.node_results, fused_results[-2:])
            )
        else:
            assert len(fused_results) == prior_fused
            assert resolved_methods[prior_resolved:] == [methods[choice], _Consumer]
            new_builds = compiler_builds[prior_compiler_builds:]
            assert sum(method is methods[choice] for method in new_builds) == (choice not in seen)
        seen.add(choice)


def test_cache_get_without_implementation_is_unknown_when_ambiguous():
    """Public cache access never picks one of two same-specialization methods."""
    first, second, _chain = _registries_and_chain()
    cache = CompilationCache()
    a = MethodCompiler(registry=first, cache=cache).compile(_PRODUCER_SIG.fqn, jit=False)
    assert cache.get(a.specialization) is a
    assert cache.put(a.specialization, a)
    assert cache.get(a.specialization) is a
    flight, leader = cache.claim_flight("public-roundtrip")
    assert leader
    assert cache.publish_flight(
        "public-roundtrip", flight, a.specialization, a, token=cache.current_token()
    )
    assert cache.get(a.specialization) is a
    b = MethodCompiler(registry=second, cache=cache).compile(_PRODUCER_SIG.fqn, jit=False)
    assert a.specialization == b.specialization
    assert a.specialization.cache_key == b.specialization.cache_key
    assert float(a(jnp.asarray(2.0), {})) == pytest.approx(3.0)
    assert float(b(jnp.asarray(2.0), {})) == pytest.approx(12.0)
    assert cache.contains(a.specialization)
    assert cache.get(a.specialization) is None
    assert cache.invalidate(a.specialization)
    assert not cache.contains(a.specialization)


def test_callable_replacement_with_same_class_does_not_reuse_old_compilation(monkeypatch):
    """A selected class whose pure_step changes gets a distinct executable."""
    registry = MethodRegistry._create_fresh()
    registry.register(_First)
    cache = CompilationCache()
    compiler = MethodCompiler(registry=registry, cache=cache)
    old = compiler.compile(_PRODUCER_SIG.fqn, jit=False)

    def replacement(state, params):
        return state + 20.0

    monkeypatch.setattr(_First, "pure_step", staticmethod(replacement))
    fresh = compiler.compile(_PRODUCER_SIG.fqn, jit=False)
    assert float(old(jnp.asarray(2.0), {})) == pytest.approx(3.0)
    assert float(fresh(jnp.asarray(2.0), {})) == pytest.approx(22.0)
    assert cache.get(old.specialization) is None


def test_in_place_code_replacement_creates_new_compiler_binding(monkeypatch):
    registry = MethodRegistry._create_fresh()
    registry.register(_First)
    cache = CompilationCache()
    compiler = MethodCompiler(registry=registry, cache=cache)
    first = compiler.compile(_PRODUCER_SIG.fqn, jit=False)
    assert float(first(jnp.asarray(2.0), {})) == pytest.approx(3.0)

    def replacement(state, params):
        return state + 20.0

    monkeypatch.setattr(_First.pure_step, "__code__", replacement.__code__)
    second = compiler.compile(_PRODUCER_SIG.fqn, jit=False)
    assert float(second(jnp.asarray(2.0), {})) == pytest.approx(22.0)
    assert cache.get(first.specialization) is None


def test_parallel_compilers_do_not_share_a_flight_across_selected_classes():
    first, second, _chain = _registries_and_chain()
    cache = CompilationCache()
    entered_first = threading.Event()
    entered_second = threading.Event()
    release = threading.Event()

    class CoordinatedCompiler(MethodCompiler):
        def __init__(self, registry, entered):
            super().__init__(registry=registry, cache=cache)
            self.entered = entered

        def _compile_method(self, *args, **kwargs):
            self.entered.set()
            if not release.wait(timeout=30):
                raise TimeoutError("coordinated compiler was not released")
            return super()._compile_method(*args, **kwargs)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(
            CoordinatedCompiler(first, entered_first).compile, _PRODUCER_SIG.fqn, jit=False
        )
        try:
            assert entered_first.wait(timeout=30)
            second_future = pool.submit(
                CoordinatedCompiler(second, entered_second).compile, _PRODUCER_SIG.fqn, jit=False
            )
            both_built = entered_second.wait(timeout=10)
        finally:
            release.set()
        assert both_built, "distinct implementations must not share an in-flight build"
        a = first_future.result(timeout=30)
        b = second_future.result(timeout=30)
    assert float(a(jnp.asarray(2.0), {})) == pytest.approx(3.0)
    assert float(b(jnp.asarray(2.0), {})) == pytest.approx(12.0)


def test_same_class_new_signature_is_a_distinct_compilation(monkeypatch):
    registry = MethodRegistry._create_fresh()
    registry.register(_First)
    cache = CompilationCache()
    compiler = MethodCompiler(registry=registry, cache=cache)
    first = compiler.compile(_PRODUCER_SIG.fqn, jit=False)
    changed = replace(_PRODUCER_SIG, supports_vmap=False)
    monkeypatch.setattr(_First, "signature", changed)
    second = compiler.compile(_PRODUCER_SIG.fqn, jit=False)
    assert first.signature == _PRODUCER_SIG
    assert second.signature == changed
    assert first.specialization == second.specialization
    assert cache.get(first.specialization) is None


def test_admitted_signature_is_frozen_during_compiler_dispatch(monkeypatch):
    registry = MethodRegistry._create_fresh()
    registry.register(_First)
    changed = replace(_PRODUCER_SIG, supports_vmap=False)
    captured = []

    class RebindingCompiler(MethodCompiler):
        def compile(self, method_name, params=None, *, jit=True):
            monkeypatch.setattr(_First, "signature", changed)
            result = super().compile(method_name, params, jit=jit)
            captured.append(result.signature)
            return result

    runner = JaxRunner(RebindingCompiler(registry=registry, cache=CompilationCache()))
    result = runner.execute(
        method_class=_First, signature=_PRODUCER_SIG, state=jnp.asarray(2.0), params={}, seed=0
    )
    assert float(result.output) == pytest.approx(3.0)
    assert captured == [_PRODUCER_SIG]


@pytest.mark.parametrize("executor_mode", ("sequential", "async"))
def test_selected_signature_mismatch_refuses_before_method_execution(executor_mode):
    first, _second, chain = _registries_and_chain()
    calls = []

    class ChangedSignature(_First):
        signature = replace(_PRODUCER_SIG, supports_vmap=False)

        @staticmethod
        def pure_step(state, params):
            calls.append("executed")
            return state + 100.0

    first.register(ChangedSignature, override=True)
    if executor_mode == "sequential":
        with pytest.raises(MethodContractError, match="Selected method signature differs"):
            chain.execute_heterogeneous(state=jnp.asarray(2.0), registry=first)
    else:
        with pytest.raises(AsyncChainExecutionError) as caught:
            chain.execute_heterogeneous(
                state=jnp.asarray(2.0), registry=first, executor_mode="async"
            )
        assert len(caught.value.node_errors) == 1
        assert isinstance(caught.value.node_errors[0].error, MethodContractError)
    assert calls == []


def test_signature_binding_rejects_slot_bounds_hidden_by_abi_digest(monkeypatch):
    """The ABI digest omits bounds, but linker warning inputs must stay bound."""
    registry, _other, chain = _registries_and_chain()
    method = registry.get(_PRODUCER_SIG.fqn)
    cache = CompilationCache()
    compiler = MethodCompiler(registry=registry, cache=cache)
    first = compiler.compile(_PRODUCER_SIG.fqn, jit=False)
    changed = replace(_PRODUCER_SIG, output_slots=frozenset({replace(_SLOT, bounds=(10, 20))}))
    assert changed.stable_digest() == _PRODUCER_SIG.stable_digest()
    monkeypatch.setattr(method, "signature", changed)
    second = compiler.compile(_PRODUCER_SIG.fqn, jit=False)
    assert next(iter(second.signature.output_slots)).bounds == (10, 20)
    assert first.specialization == second.specialization
    assert cache.get(first.specialization) is None
    with pytest.raises(MethodContractError, match="Selected method signature differs"):
        chain.execute_heterogeneous(state=jnp.asarray(2.0), registry=registry)


def test_numeric_equivalent_slot_bounds_are_accepted_and_cache_reused(monkeypatch):
    """Equivalent numeric bounds preserve the selected call and its warm cache."""
    integer_slot = replace(_SLOT, bounds=(0, 1))
    float_slot = replace(_SLOT, bounds=(-0.0, 1.0))

    class NumericBounds(_First):
        signature = replace(_PRODUCER_SIG, output_slots=frozenset({integer_slot}))

    registry = MethodRegistry._create_fresh()
    registry.register(NumericBounds)
    registry.register(_Consumer)
    composer = MethodComposer(registry=registry)
    first_node = composer.add(_PRODUCER_SIG.fqn)
    second_node = composer.add(_CONSUMER_SIG.fqn)
    composer.connect(first_node, second_node, {"signal": "signal"})
    chain = composer.build()
    cache = CompilationCache()
    compiler = MethodCompiler(registry=registry, cache=cache)
    first = compiler.compile(_PRODUCER_SIG.fqn, jit=False)
    equivalent = replace(_PRODUCER_SIG, output_slots=frozenset({float_slot}))
    monkeypatch.setattr(NumericBounds, "signature", equivalent)
    second = compiler.compile(_PRODUCER_SIG.fqn, jit=False)
    assert second is first
    result = chain.execute_heterogeneous(state=jnp.asarray(2.0), registry=registry)
    assert float(result.final_state) == pytest.approx(9.0)

    huge = 10**20 + 1
    exact = replace(_PRODUCER_SIG, output_slots=frozenset({replace(_SLOT, bounds=(huge, huge))}))
    rounded = replace(
        _PRODUCER_SIG, output_slots=frozenset({replace(_SLOT, bounds=(float(huge), float(huge)))})
    )
    assert huge != float(huge)
    assert exact.stable_digest() == rounded.stable_digest()
    assert _signature_binding(exact) != _signature_binding(rounded)


def test_fused_pair_checks_second_signature_before_first_method(monkeypatch):
    registry, _other, chain = _registries_and_chain()
    first_method = registry.get(_PRODUCER_SIG.fqn)
    calls = []

    def observed_first(state, params):
        calls.append("first executed")
        return state + 1.0

    class ChangedConsumer(_Consumer):
        signature = replace(_CONSUMER_SIG, supports_vmap=False)

    monkeypatch.setattr(first_method, "pure_step", staticmethod(observed_first))
    registry.register(ChangedConsumer, override=True)
    with pytest.raises(MethodContractError, match="Selected method signature differs"):
        chain.execute_heterogeneous(state=jnp.asarray(2.0), registry=registry)
    assert calls == []


def test_fusion_keeps_the_selected_first_class_when_registry_changes(monkeypatch):
    first, second, chain = _registries_and_chain()
    original_get = first.get
    other = second.get(_PRODUCER_SIG.fqn)
    lookups = []
    produced = []
    actual_result = chain_executor._build_fused_result

    def changing_get(name, *args, **kwargs):
        if name == _PRODUCER_SIG.fqn:
            lookups.append(name)
            if len(lookups) > 1:
                return other
        return original_get(name, *args, **kwargs)

    def observe_result(*args, **kwargs):
        result = actual_result(*args, **kwargs)
        produced.append(result)
        return result

    monkeypatch.setattr(first, "get", changing_get)
    monkeypatch.setattr(chain_executor, "_build_fused_result", observe_result)
    result = chain.execute_heterogeneous(state=jnp.asarray(2.0), registry=first)
    assert len(lookups) == 1
    assert float(result.final_state) == pytest.approx(9.0)
    assert len(produced) == 2
    assert all(actual is recorded for (_, actual), recorded in zip(result.node_results, produced))


def test_identity_does_not_treat_code_marker_as_python_function():
    """An opaque callable cannot obtain cache reuse by exposing a code marker."""

    def operation(state, params):
        return state

    class OpaqueProxy:
        __code__ = operation.__code__

        def __call__(self, state, params):
            return state

    proxy = OpaqueProxy()
    assert _ExecutableIdentity(_First, operation, "sig") == _ExecutableIdentity(
        _First, operation, "sig"
    )
    assert _ExecutableIdentity(_First, proxy, "sig") != _ExecutableIdentity(_First, proxy, "sig")


def test_identity_retains_objects_and_ignores_custom_equality():
    """Identity keys cannot collide by equality or address reuse while cached."""

    class EqualMeta(type):
        def __eq__(cls, other):
            return isinstance(other, EqualMeta)

        def __hash__(cls):
            return 1

    def operation(state, params):
        return state

    one = EqualMeta("One", (), {"pure_step": staticmethod(operation)})
    two = EqualMeta("Two", (), {"pure_step": staticmethod(operation)})
    assert one == two
    key_one = _ExecutableIdentity(one, one.pure_step, "sig")
    key_two = _ExecutableIdentity(two, two.pure_step, "sig")
    assert key_one != key_two
    assert len({key_one, key_two}) == 2
    reference = weakref.ref(one)
    del one
    gc.collect()
    assert reference() is not None


def test_real_compiler_override_signature_and_unbound_handle():
    """Compatible overrides retain their signature; unbound returned handles refuse."""
    registry, _, _ = _registries_and_chain()
    cache = CompilationCache()
    good = MethodCompiler(registry=registry, cache=cache).compile(_PRODUCER_SIG.fqn, jit=False)

    class ForwardingCompiler(MethodCompiler):
        def compile(self, method_name, params=None, *, jit=True):
            return super().compile(method_name, params, jit=jit)

    runner = JaxRunner(ForwardingCompiler(registry=registry, cache=cache))
    result = runner.execute(
        method_class=_First, signature=_PRODUCER_SIG, state=jnp.asarray(2.0), params={}, seed=0
    )
    assert float(result.output) == pytest.approx(3.0)

    class UnboundCompiler(MethodCompiler):
        def compile(self, method_name, params=None, *, jit=True):
            return replace(good, _implementation_identity=None)

    runner = JaxRunner(UnboundCompiler(registry=registry, cache=cache))
    with pytest.raises(CompilationError, match="did not bind the selected implementation"):
        runner.execute(
            method_class=_First, signature=_PRODUCER_SIG, state=jnp.asarray(2.0), params={}, seed=0
        )
