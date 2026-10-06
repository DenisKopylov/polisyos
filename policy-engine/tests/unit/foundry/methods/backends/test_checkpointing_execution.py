"""Exercise checkpoint execution through real composed registry methods."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from typing import Any, ClassVar

import pytest

from polisyos.foundry.methods.backends.async_chain_executor import (
    AsyncChainExecutionError,
    AsyncChainExecutor,
)
from polisyos.foundry.methods.backends.chain_executor import execute_heterogeneous_chain
from polisyos.foundry.methods.backends.checkpointing import (
    ChainCheckpoint,
    CheckpointDigestMismatchError,
    CheckpointingChainExecutor,
    CheckpointLoadError,
)
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
from polisyos.foundry.methods.components.composer import MethodComposer
from polisyos.foundry.methods.exceptions import MethodContractError
from polisyos.foundry.methods.selection.registry import MethodRegistry


@pytest.fixture(autouse=True)
def isolated_registry():
    """Use a fresh registry for each real execution fixture."""
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


def _slot(name: str) -> SlotSpec:
    return SlotSpec(
        name=name,
        slot_type=SlotType.SCALAR,
        unit=Unit(dimension="count", symbol="1"),
        shape=(),
    )


def _method(
    name: str,
    *,
    output: str,
    step: Callable[[Any, Mapping[str, Any]], Any],
    inputs: tuple[str, ...] = (),
    parameters: tuple[ParameterSpec, ...] = (),
    requires: frozenset[str] = frozenset(),
) -> type:
    signature = MethodSignature(
        name=name,
        namespace="tests.checkpoint_execution",
        version="1.0.0",
        input_slots=frozenset(_slot(name) for name in inputs),
        output_slots=frozenset({_slot(output)}),
        parameters=parameters,
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
        requires=requires,
    )

    class RegisteredMethod:
        metadata: ClassVar[MethodMetadata] = MethodMetadata(
            description="Deterministic arithmetic execution fixture",
            tags=frozenset({"test"}),
        )

        @staticmethod
        def pure_step(state: Any, params: dict[str, Any]) -> Any:
            return step(state, params)

    RegisteredMethod.signature = signature
    MethodRegistry.get_instance().register(RegisteredMethod, override=True)
    return RegisteredMethod


@pytest.mark.parametrize("mode", ["sequential", "async", "checkpoint"])
def test_static_dynamic_override_payload_is_identical_in_every_executor(tmp_path, mode):
    """A declared static factor reaches actual arithmetic without repeating it."""
    received = []

    def step(state, params):
        received.append(dict(params))
        return {"value": state["x"] * params["factor"] + params["offset"]}

    method = _method(
        "affine",
        output="value",
        step=step,
        parameters=(
            ParameterSpec(name="factor", default=2, is_static=True),
            ParameterSpec(name="offset", default=1, is_static=False),
        ),
    )
    registry = MethodRegistry.get_instance()
    composer = MethodComposer(registry=registry)
    node = composer.add(method.signature.fqn, factor=3, offset=2)
    chain = composer.build(validate_semantics=False)
    overrides = {node.id: {"offset": 5}}
    if mode == "checkpoint":
        result = CheckpointingChainExecutor(registry=registry).execute(
            chain, initial_state={"x": 4}, params_per_node=overrides, seed=17
        )
    elif mode == "async":
        result = asyncio.run(
            AsyncChainExecutor(registry=registry).execute(
                chain, initial_state={"x": 4}, params_map=overrides, seed=17
            )
        )
    else:
        result = execute_heterogeneous_chain(
            chain,
            state={"x": 4},
            params_per_node=overrides,
            registry=registry,
            executor_mode="sequential",
            seed=17,
        )
    assert result.node_results[0][1].output == {"value": 17}
    assert result.final_state["value"] == 17
    assert [
        {name: value for name, value in params.items() if not name.startswith("__")}
        for params in received
    ] == [{"factor": 3, "offset": 5}]
    assert result.node_results[0][1].reproducibility.seed == 17


def _bound_chain():
    calls = []

    def multiply(state, params):
        calls.append("multiply")
        return {"product": state["x"] * params["factor"]}

    def add(state, params):
        calls.append("add")
        # The declared single-slot input is a scalar, not the accumulated context.
        return {"total": state + params["increment"]}

    first = _method(
        "multiply",
        output="product",
        step=multiply,
        parameters=(
            ParameterSpec(name="factor", default=3, is_static=True),
            ParameterSpec(name="seed", default=7, is_static=False),
        ),
    )
    second = _method(
        "add",
        output="total",
        inputs=("operand",),
        step=add,
        parameters=(
            ParameterSpec(name="increment", default=1, is_static=False),
            ParameterSpec(name="seed", default=7, is_static=False),
        ),
    )
    registry = MethodRegistry.get_instance()
    composer = MethodComposer(registry=registry)
    producer = composer.add(first.signature.fqn)
    consumer = composer.add(second.signature.fqn)
    composer.connect(producer, consumer, slot_mapping={"product": "operand"})
    return composer.build(validate_semantics=False), registry, calls


def test_checkpoint_consumes_actual_bound_slot_through_canonical_materializer(tmp_path):
    """The checkpoint consumer sees product=12 and independently computes 13."""
    chain, registry, calls = _bound_chain()
    result = CheckpointingChainExecutor(registry=registry, checkpoint_dir=tmp_path).execute(
        chain, initial_state={"x": 4}, seed=7
    )
    assert result.final_state["total"] == 13
    assert [item.output for _, item in result.node_results] == [
        {"product": 12},
        {"total": 13},
    ]
    assert calls == ["multiply", "add"]


def test_resume_materializes_bound_slot_from_original_per_node_history(tmp_path):
    """Resume consumes the persisted producer slot and does not rerun that producer."""
    chain, registry, calls = _bound_chain()
    writer = CheckpointingChainExecutor(registry=registry, checkpoint_dir=tmp_path)
    writer.execute(chain, initial_state={"x": 4}, seed=7)
    path = next(tmp_path.glob("*_0000_*.json"))
    checkpoint = ChainCheckpoint.load(path)
    calls.clear()
    result = CheckpointingChainExecutor(registry=registry).execute(
        chain, initial_state={"x": 4}, checkpoint=checkpoint, seed=7
    )
    assert result.final_state["total"] == 13
    assert [item.output for _, item in result.node_results] == [
        {"product": 12},
        {"total": 13},
    ]
    assert [item.reproducibility.seed for _, item in result.node_results] == [7, 7]
    assert calls == ["add"]


@pytest.mark.parametrize("mode", ["sequential", "async", "checkpoint"])
def test_unknown_override_is_refused_before_actual_method_execution(mode):
    calls = []
    method = _method("strict", output="value", step=lambda state, params: calls.append(state))
    registry = MethodRegistry.get_instance()
    composer = MethodComposer(registry=registry)
    node = composer.add(method.signature.fqn)
    chain = composer.build(validate_semantics=False)
    overrides = {node.id: {"typo": 9}}
    if mode == "async":
        with pytest.raises(AsyncChainExecutionError) as caught:
            asyncio.run(
                AsyncChainExecutor(registry=registry).execute(
                    chain, initial_state={}, params_map=overrides
                )
            )
        assert isinstance(caught.value.node_errors[0].error, ValueError)
        assert "Unknown parameters" in str(caught.value.node_errors[0].error)
    elif mode == "checkpoint":
        with pytest.raises(ValueError, match="Unknown parameters"):
            CheckpointingChainExecutor(registry=registry).execute(
                chain, initial_state={}, params_per_node=overrides
            )
    else:
        with pytest.raises(ValueError, match="Unknown parameters"):
            execute_heterogeneous_chain(
                chain,
                state={},
                params_per_node=overrides,
                registry=registry,
                executor_mode="sequential",
            )
    assert calls == []


@pytest.mark.parametrize("change", ["static", "override"])
def test_changed_effective_payload_refuses_warm_checkpoint(tmp_path, change):
    chain, registry, calls = _bound_chain()
    writer = CheckpointingChainExecutor(registry=registry, checkpoint_dir=tmp_path)
    writer.execute(chain, initial_state={"x": 4}, seed=7)
    checkpoint = ChainCheckpoint.load(next(tmp_path.glob("*_0000_*.json")))
    node_id = chain.execution_order[0]
    if change == "static":
        from dataclasses import replace
        from types import MappingProxyType

        node = chain.get_node(node_id)
        nodes = dict(chain.dag.nodes)
        nodes[node_id] = replace(node, static_params=MappingProxyType({"factor": 5}))
        # The effective plan must change even when the method FQN is unchanged.
        chain = replace(chain, dag=replace(chain.dag, nodes=MappingProxyType(nodes)))
        overrides = None
    else:
        overrides = {node_id: {"factor": 5}}
    calls.clear()
    with pytest.raises(CheckpointDigestMismatchError):
        writer.execute(
            chain,
            initial_state={"x": 4},
            params_per_node=overrides,
            checkpoint=checkpoint,
            seed=7,
        )
    assert calls == []


def _context_chain():
    calls = []

    def first_step(state, params):
        calls.append("first")
        return {"product": state["x"] * 3}

    first = _method("context_first", output="product", step=first_step)

    def second_step(state, params):
        calls.append("second")
        return {"total": state["product"] + 1}

    second = _method(
        "context_second",
        output="total",
        step=second_step,
        requires=frozenset({first.signature.fqn}),
    )
    registry = MethodRegistry.get_instance()
    composer = MethodComposer(registry=registry)
    composer.add(first.signature.fqn)
    composer.add(second.signature.fqn)
    return composer.build(validate_semantics=False), registry, calls


def test_missing_history_preserves_frontier_and_known_suffix_through_filesystem(tmp_path):
    chain, registry, calls = _context_chain()
    writer_dir = tmp_path / "writer"
    CheckpointingChainExecutor(registry=registry, checkpoint_dir=writer_dir).execute(
        chain, initial_state={"x": 4}, seed=7
    )
    checkpoint = ChainCheckpoint.load(next(writer_dir.glob("*_0000_*.json")))
    checkpoint.node_results = []
    # A stale flag cannot turn absent original records into complete history.
    checkpoint.history_complete = True
    damaged = tmp_path / "history-omitted.json"
    checkpoint.save(damaged)
    checkpoint = ChainCheckpoint.load(damaged)
    resumed_dir = tmp_path / "resumed"
    calls.clear()
    result = CheckpointingChainExecutor(registry=registry, checkpoint_dir=resumed_dir).execute(
        chain, initial_state={"x": 4}, checkpoint=checkpoint, seed=7
    )
    assert calls == ["second"]
    assert result.final_state["total"] == 13
    assert not result.history_complete
    assert result.missing_history_node_ids == (chain.execution_order[0],)
    assert [item.output for _, item in result.node_results] == [{"total": 13}]
    assert result.reproducibility_contract["history_complete"] is False
    persisted = ChainCheckpoint.load(next(resumed_dir.glob("*_0001_*.json")))
    assert persisted.completed_node_ids == [str(node) for node in chain.execution_order]
    assert not persisted.history_complete
    assert [row["node_id"] for row in persisted.node_results] == [str(chain.execution_order[1])]
    calls.clear()
    again = CheckpointingChainExecutor(registry=registry).execute(
        chain, initial_state={"x": 4}, checkpoint=persisted, seed=7
    )
    assert calls == []
    assert not again.history_complete
    assert again.missing_history_node_ids == (chain.execution_order[0],)
    assert [item.output for _, item in again.node_results] == [{"total": 13}]


def test_missing_bound_history_refuses_before_consumer_dispatch(tmp_path):
    chain, registry, calls = _bound_chain()
    writer = CheckpointingChainExecutor(registry=registry, checkpoint_dir=tmp_path)
    writer.execute(chain, initial_state={"x": 4}, seed=7)
    checkpoint = ChainCheckpoint.load(next(tmp_path.glob("*_0000_*.json")))
    checkpoint.node_results = []
    checkpoint.history_complete = False
    calls.clear()
    with pytest.raises(MethodContractError, match="has not produced slot outputs"):
        writer.execute(chain, initial_state={"x": 4}, checkpoint=checkpoint, seed=7)
    assert calls == []


def test_foreign_history_is_not_admitted_as_original_result(tmp_path):
    from uuid import uuid4

    chain, registry, calls = _bound_chain()
    writer = CheckpointingChainExecutor(registry=registry, checkpoint_dir=tmp_path)
    writer.execute(chain, initial_state={"x": 4}, seed=7)
    checkpoint = ChainCheckpoint.load(next(tmp_path.glob("*_0000_*.json")))
    checkpoint.node_results[0]["node_id"] = str(uuid4())
    calls.clear()
    with pytest.raises(CheckpointLoadError, match="history does not match"):
        writer.execute(chain, initial_state={"x": 4}, checkpoint=checkpoint, seed=7)
    assert calls == []
