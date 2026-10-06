"""Independent seeded numerical consumers of compiler preparation and warmup.

The random primitive is the actual JAX backend. The numerical oracle separately
combines its known seeded draws with Python/NumPy arithmetic; this is not an
independent validation of JAX's random-number implementation or distribution.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import threading
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
    ComputeBackend,
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


def _ordering_owner() -> tuple[Any, Any, Any, Any]:
    registry = MethodRegistry._create_fresh()
    registry.register(_Draw)
    registry.register(_Reduce)
    composer = MethodComposer(registry=registry)
    reducer = composer.add(_Reduce.signature.fqn)
    producer = composer.add(_Draw.signature.fqn, scale=0.5)
    return registry, composer.build(), producer, reducer


def _parallel_signature(
    name: str, output: str, *, requires: frozenset[str] = frozenset(), window: bool = False
) -> MethodSignature:
    return MethodSignature(
        name=name,
        namespace="tests.independent_plan_parallel",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset({_slot(output)}),
        parameters=(ParameterSpec("window", default=20, is_static=True),) if window else (),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
        requires=requires,
    )


class _ParallelRequired:
    signature: ClassVar = _parallel_signature("required", "required", window=True)
    metadata: ClassVar = MethodMetadata(description="Real independent required branch")

    @staticmethod
    def pure_step(state: dict[str, Any], params: Mapping[str, Any]) -> dict[str, float]:
        state["events"].append(["required", "entered", params["window"]])
        state["barrier"].wait()
        value = math.fsum(float(item) ** 2 for item in state["values"][: params["window"]])
        state["events"].append(["required", "computed", value])
        return {"required": value}


class _ParallelSibling:
    signature: ClassVar = _parallel_signature("sibling", "sibling")
    metadata: ClassVar = MethodMetadata(description="Real independent sibling branch")

    @staticmethod
    def pure_step(state: dict[str, Any], _params: Mapping[str, Any]) -> dict[str, float]:
        state["events"].append(["sibling", "entered"])
        state["barrier"].wait()
        value = math.fsum(float(item) for item in state["values"])
        state["events"].append(["sibling", "computed", value])
        return {"sibling": value}


class _ParallelDependent:
    signature: ClassVar = _parallel_signature(
        "dependent", "dependent", requires=frozenset({_ParallelRequired.signature.fqn})
    )
    metadata: ClassVar = MethodMetadata(description="Real consumer of required branch value")

    @staticmethod
    def pure_step(state: dict[str, Any], _params: Mapping[str, Any]) -> dict[str, float]:
        value = state["required"] + 7.0
        state["events"].append(["dependent", "computed", value])
        return {"dependent": value}


@pytest.mark.parametrize("mode", ["async", "auto"])
def test_reopened_plan_keeps_independent_real_branches_parallel(tmp_path: Path, mode: str) -> None:
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.foundry.methods.artifacts import (
        CompiledChainPlan,
        load_compiled_chain_plan,
        store_compiled_chain_plan,
    )

    registry = MethodRegistry._create_fresh()
    for method in (_ParallelRequired, _ParallelSibling, _ParallelDependent):
        registry.register(method)
    composer = MethodComposer(registry=registry)
    dependent = composer.add(_ParallelDependent.signature.fqn)
    required = composer.add(_ParallelRequired.signature.fqn)
    sibling = composer.add(_ParallelSibling.signature.fqn)
    chain = composer.build()
    plan = CompiledChainPlan.from_chain(chain)
    ref = store_compiled_chain_plan(FileSystemCAS(tmp_path / "cas"), plan)
    restored = load_compiled_chain_plan(FileSystemCAS(tmp_path / "cas"), ref, registry=registry)
    assert restored.dag.edges == {}
    assert set(restored.dag.compute_parallel_levels()[0]) == {required.id, sibling.id}
    events: list[list[Any]] = []
    result = restored.execute_heterogeneous(
        state={
            "values": [2.0, -3.0, 4.0],
            "barrier": threading.Barrier(2, timeout=5),
            "events": events,
        },
        registry=registry,
        executor_mode=mode,
    )
    assert result.final_state["required"] == 29.0
    assert result.final_state["sibling"] == 3.0
    assert result.final_state["dependent"] == 36.0
    assert {event[0] for event in events[:2]} == {"required", "sibling"}
    assert all(event[1] == "entered" for event in events[:2])
    assert ["required", "entered", 20] in events
    assert events[-1] == ["dependent", "computed", 36.0]
    assert {node_id for node_id, _ in result.node_results} == {
        required.id,
        sibling.id,
        dependent.id,
    }
    (tmp_path / "reopened-parallel-observations.json").write_text(
        json.dumps(
            {
                "mode": mode,
                "ref": ref.model_dump(mode="json"),
                "events": events,
                "node_results": [str(node_id) for node_id, _ in result.node_results],
                "numeric_results": {
                    name: result.final_state[name] for name in ("required", "sibling", "dependent")
                },
            },
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("mode", ["sequential", "async", "auto", "compiled", "compiled-jit"])
def test_canonical_plan_cas_reopen_preserves_requires_only_numerical_execution(
    tmp_path: Path, mode: str
) -> None:
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.foundry.methods.artifacts import (
        CompiledChainPlan,
        load_compiled_chain_plan,
        store_compiled_chain_plan,
    )

    registry, chain, producer, reducer = _ordering_owner()
    state = _state()
    with _body_observer() as calls:
        assert chain.dag.edges == {}
        plan = CompiledChainPlan.from_chain(chain)
        cas = FileSystemCAS(tmp_path / "cas")
        ref = store_compiled_chain_plan(cas, plan)
        reopened = FileSystemCAS(tmp_path / "cas")
        wire = reopened.get_bytes(ref)
        assert wire == plan.to_canonical_bytes()
        restored = load_compiled_chain_plan(reopened, ref, registry=registry)
        assert calls == {"draw": 0, "reduce": 0}
    assert tuple(restored.execution_order) == (producer.id, reducer.id)
    assert restored.dag.edges == {}
    assert restored.get_node(producer.id).static_params == producer.static_params
    params = {producer.id: {"seed": 23}, reducer.id: {"offset": 0.75}}
    observed_order = list(restored.execution_order)
    if mode.startswith("compiled"):
        executor = MethodCompiler(registry=registry, cache=CompilationCache()).compile_chain(
            restored, state, jit=mode == "compiled-jit", infer_shapes=True
        )
        result = executor(state, params)
    else:
        from polisyos.foundry.methods.backends.chain_executor import execute_heterogeneous_chain
        from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
        from polisyos.foundry.methods.backends.jax_runner import JaxRunner

        # The real JAX runner owns its compiler. Bind the same explicit registry
        # used to restore this plan instead of relying on an unrelated singleton.
        dispatcher = MethodDispatcher()
        dispatcher.register_runner(JaxRunner(MethodCompiler(registry=registry)))
        execution = execute_heterogeneous_chain(
            restored,
            state=state,
            params_per_node=params,
            registry=registry,
            dispatcher=dispatcher,
            executor_mode=mode,
        )
        observed_order = [node_id for node_id, _ in execution.node_results]
        result = execution.final_state
    result.total.block_until_ready()
    expected_draws, expected_total = _oracle(state, 23, 0.5, 0.75)
    (tmp_path / "reopened-plan-observations.json").write_text(
        json.dumps(
            {
                "mode": mode,
                "ref": ref.model_dump(mode="json"),
                "wire_sha256": hashlib.sha256(wire).hexdigest(),
                "execution_order": [str(value) for value in restored.execution_order],
                "actual_node_result_order": [str(value) for value in observed_order],
                "predecessors": {
                    str(key): sorted(str(value) for value in values)
                    for key, values in restored.dag.predecessors.items()
                },
                "data_flow_edge_count": len(restored.dag.edges),
                "seed": 23,
                "offset": 0.75,
                "draws": np.asarray(result.draws).tolist(),
                "total": float(result.total),
                "oracle_total": expected_total,
            },
            indent=2,
        )
        + "\n"
    )
    np.testing.assert_allclose(np.asarray(result.draws), expected_draws, rtol=1e-6, atol=1e-7)
    assert float(result.total) == pytest.approx(expected_total, rel=1e-6)
    assert tuple(observed_order) == (producer.id, reducer.id)
    assert restored.dag.predecessors[reducer.id] == frozenset({producer.id})


@pytest.mark.parametrize("damage", ["required-edge", "required-node", "cycle"])
def test_reopened_plan_refuses_damaged_effective_graph_before_scientific_bodies(
    tmp_path: Path, damage: str
) -> None:
    from polisyos.core.artifacts import FileSystemCAS, artifact_manifest_profile_sha256
    from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.canon import CanonSpec, to_canonical_bytes
    from polisyos.foundry.methods.artifacts import CompiledChainPlan, load_compiled_chain_plan
    from polisyos.foundry.methods.exceptions import CyclicDependencyError, MissingRequirementError

    registry, chain, producer, reducer = _ordering_owner()
    payload = json.loads(CompiledChainPlan.from_chain(chain).to_canonical_bytes())
    producer_id, reducer_id = str(producer.id), str(reducer.id)
    if damage == "required-edge":
        payload["predecessors"][reducer_id] = []
        expected_error, message = ValueError, "effective dependency mismatch"
    elif damage == "required-node":
        payload["nodes"] = [node for node in payload["nodes"] if node["node_id"] != producer_id]
        payload["nodes"][0]["insertion_order"] = 0
        payload["execution_order"] = [reducer_id]
        del payload["predecessors"][producer_id]
        payload["predecessors"][reducer_id] = []
        del payload["cache_keys"][producer_id]
        expected_error, message = MissingRequirementError, "draw"
    else:
        payload["predecessors"][producer_id] = [reducer_id]
        expected_error, message = CyclicDependencyError, "draw|reduce"
    wire = to_canonical_bytes(payload, CanonSpec(forbid_floats=False, exclude_none=False))
    cas = FileSystemCAS(tmp_path / "cas")
    ref = cas.put_bytes(
        wire,
        PutOptions(
            kind="foundry.compiled_chain_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.compiled_chain_plan", version="1.0.0"),
        ),
    )
    ref = ArtifactRef(
        artifact_id=ref.artifact_id,
        kind=ref.kind,
        media_type=ref.media_type,
        manifest_profile_sha256=artifact_manifest_profile_sha256(cas.get_manifest(ref)),
    )
    with _body_observer() as calls:
        with pytest.raises(expected_error, match=message) as refusal:
            load_compiled_chain_plan(FileSystemCAS(tmp_path / "cas"), ref, registry=registry)
        assert calls == {"draw": 0, "reduce": 0}
    (tmp_path / "damaged-plan-observations.json").write_text(
        json.dumps(
            {
                "damage": damage,
                "ref": ref.model_dump(mode="json"),
                "wire_sha256": hashlib.sha256(wire).hexdigest(),
                "refusal_type": type(refusal.value).__name__,
                "refusal": str(refusal.value),
                "body_entries": calls,
            },
            indent=2,
        )
        + "\n"
    )
