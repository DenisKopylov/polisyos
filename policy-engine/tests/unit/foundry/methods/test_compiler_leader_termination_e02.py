"""Real single-flight leader terminal faults and native JAX retry consumers."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any, ClassVar, NamedTuple

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
from polisyos.foundry.methods.compiler import CompilationCache, MethodCompiler
from polisyos.foundry.methods.exceptions import CompilationError
from polisyos.foundry.methods.selection.registry import MethodRegistry


class _State(NamedTuple):
    value: Any
    result: Any


_SIGNATURE = MethodSignature(
    name="terminal_scale",
    namespace="tests.compiler_leader_termination_e02",
    version="1.0.0",
    input_slots=frozenset({SlotSpec("value", SlotType.SCALAR, Unit("count", "1"), shape=())}),
    output_slots=frozenset({SlotSpec("result", SlotType.SCALAR, Unit("count", "1"), shape=())}),
    parameters=(ParameterSpec("factor", default=2.0),),
    fidelity=FidelityLevel.LOW,
    complexity=ComplexityClass.O_1,
)


class _Scale:
    signature: ClassVar = _SIGNATURE
    metadata: ClassVar = MethodMetadata(description="Real native terminal-flight control")

    @staticmethod
    def pure_step(state: _State, params: dict[str, Any]) -> _State:
        return state._replace(result=state.value * params["factor"])


@pytest.mark.parametrize("fault_kind", ["cancelled", "system-exit", "publication"])
def test_actual_leader_terminal_fault_releases_follower_and_fresh_native_retry(
    monkeypatch: pytest.MonkeyPatch, fault_kind: str
) -> None:
    """A real joined follower sees terminal state before a fresh JAX build can enter."""
    source_file = Path(compiler_module.__file__).resolve()
    source_hash = hashlib.sha256(source_file.read_bytes()).hexdigest()
    expected_hash = os.environ.get("E02_B_JIT_EXPECTED_COMPILER_SHA256")
    if expected_hash is not None:
        assert source_hash == expected_hash, "actual imported compiler is outside the admitted pin"
    print(json.dumps({"compiler_origin": str(source_file), "compiler_sha256": source_hash}))

    fault: BaseException
    if fault_kind == "cancelled":
        fault = asyncio.CancelledError("actual leader cancelled during compilation")
    elif fault_kind == "system-exit":
        fault = SystemExit("actual leader exited during compilation")
    else:
        fault = RuntimeError("actual compiler publication unavailable")

    registry = MethodRegistry._create_fresh()
    registry.register(_Scale)
    cache = CompilationCache()
    leader_entered = threading.Event()
    follower_entered = threading.Event()
    release_failure = threading.Event()
    counter_lock = threading.Lock()
    calls = {"build": 0, "publication": 0}
    errors: dict[str, BaseException] = {}
    joined_flights: list[Any] = []
    original_wait = compiler_module._wait_for_flight
    original_publish = cache.publish_flight

    def observe_actual_wait(flight: Any, **kwargs: Any) -> str:
        joined_flights.append(flight)
        follower_entered.set()
        return original_wait(flight, **kwargs)

    monkeypatch.setattr(compiler_module, "_wait_for_flight", observe_actual_wait)

    class FaultCompiler(MethodCompiler):
        def _compile_method(self, *args: Any, **kwargs: Any) -> Any:
            with counter_lock:
                calls["build"] += 1
                attempt = calls["build"]
            if attempt == 1 and fault_kind != "publication":
                leader_entered.set()
                assert release_failure.wait(5), "test owner did not release the actual leader"
                raise fault
            return super()._compile_method(*args, **kwargs)

    def observe_actual_publication(*args: Any, **kwargs: Any) -> bool:
        with counter_lock:
            calls["publication"] += 1
            attempt = calls["publication"]
        if attempt == 1 and fault_kind == "publication":
            leader_entered.set()
            assert release_failure.wait(5), "test owner did not release real publication"
            raise fault
        return original_publish(*args, **kwargs)

    monkeypatch.setattr(cache, "publish_flight", observe_actual_publication)
    leader_compiler = FaultCompiler(registry=registry, cache=cache)
    follower_compiler = FaultCompiler(registry=registry, cache=cache)
    sample = jnp.asarray(10.0)

    def compile_one(compiler: MethodCompiler, factor: float = 2.0) -> Any:
        return compiler.compile(
            _SIGNATURE.fqn,
            params={"factor": factor},
            sample_inputs={"value": sample},
            jit=True,
            flight_timeout=5.0,
        )

    def attempt(role: str, compiler: MethodCompiler) -> None:
        try:
            compile_one(compiler)
        except BaseException as error:
            errors[role] = error

    # Two intentional roles exercise ownership; this does not restrict the test runner.
    leader = threading.Thread(target=attempt, args=("leader", leader_compiler), daemon=True)
    follower = threading.Thread(target=attempt, args=("follower", follower_compiler), daemon=True)
    leader.start()
    try:
        assert leader_entered.wait(5), "real leader never reached its fault boundary"
        follower.start()
        assert follower_entered.wait(5), "no actual follower entered the canonical wait"
        assert len(joined_flights) == 1
        flight = joined_flights[0]
        assert not flight.event.is_set() and flight.error is None
        assert calls["build"] == 1
        release_failure.set()
        leader.join(2)
        follower.join(2)
        assert not leader.is_alive() and not follower.is_alive(), "terminal flight failed to drain"
        assert set(errors) == {"leader", "follower"}
        assert flight.error is fault and flight.event.is_set() and flight.result is None
        assert cache._flights == {} and cache.stats["size"] == 0
        if fault_kind == "publication":
            assert isinstance(errors["leader"], CompilationError)
            assert errors["leader"].__cause__ is fault
            assert isinstance(errors["follower"], CompilationError)
            assert errors["follower"].method_fqn == _SIGNATURE.fqn
            assert errors["follower"].reason == str(fault)
        else:
            assert errors["leader"] is fault and errors["follower"] is fault

        # Recovery uses the canonical compiler and a real JAX kernel, never a fake handle.
        retry = compile_one(leader_compiler)
        warm = compile_one(follower_compiler, 3.0)
        state = _State(sample, jnp.asarray(0.0))
        retry_value = float(retry(state, {}).result.block_until_ready())
        warm_value = float(warm(state, {}).result.block_until_ready())
        old_value = float(retry(state, {}).result.block_until_ready())
        assert (retry_value, warm_value, old_value) == (20.0, 30.0, 20.0)
        assert retry._kernel is warm._kernel
        assert calls["build"] == 2 and cache.stats["size"] == 1 and cache._flights == {}
        print(
            json.dumps(
                {
                    "fault_kind": fault_kind,
                    "actual_follower_entries": len(joined_flights),
                    "terminal_error_identity": flight.error is fault,
                    "leader_error_type": type(errors["leader"]).__name__,
                    "follower_error_type": type(errors["follower"]).__name__,
                    "compile_body_entries": calls["build"],
                    "publication_entries": calls["publication"],
                    "retired_claims": len(cache._flights),
                    "native_values": [retry_value, warm_value, old_value],
                    "warm_kernel_identity": retry._kernel is warm._kernel,
                }
            )
        )
    finally:
        release_failure.set()
        leader.join(5)
        if follower.ident is not None:
            # Teardown rescue cannot satisfy the deciding assertions above.
            for pending in joined_flights:
                pending.event.set()
            follower.join(5)
