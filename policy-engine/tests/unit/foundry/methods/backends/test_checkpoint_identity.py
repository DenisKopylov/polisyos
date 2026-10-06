"""Checkpoint identity witnesses using actual registry methods and required edges."""

from __future__ import annotations

from dataclasses import replace
from typing import ClassVar

import pytest

from polisyos.foundry.methods.backends.checkpointing import (
    ChainCheckpoint,
    CheckpointDigestMismatchError,
    CheckpointingChainExecutor,
)
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
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
from polisyos.foundry.methods.selection.registry import MethodRegistry


def _slot(name):
    return SlotSpec(name, SlotType.SCALAR, Unit("count", "1"), shape=())


_PRODUCER_SIGNATURE = MethodSignature(
    name="source",
    namespace="tests.checkpoint_identity",
    version="1.0.0",
    input_slots=frozenset(),
    output_slots=frozenset({_slot("product")}),
    parameters=(ParameterSpec("factor", default=2, is_static=True),),
    backend=ComputeBackend.NUMPY,
    fidelity=FidelityLevel.LOW,
    complexity=ComplexityClass.O_1,
    supports_jit=False,
    supports_vmap=False,
    supports_grad=False,
)
_CONSUMER_SIGNATURE = replace(
    _PRODUCER_SIGNATURE,
    name="consumer",
    input_slots=frozenset({_slot("operand")}),
    output_slots=frozenset({_slot("total")}),
    parameters=(ParameterSpec("increment", default=1),),
    requires=frozenset({_PRODUCER_SIGNATURE.fqn}),
)
_METADATA = MethodMetadata(description="Checkpoint identity arithmetic", tags=frozenset({"test"}))


class _Original:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": state["x"] * params["factor"]}


class _Replacement:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": state["x"] * (params["factor"] + 1)}


class _ChangedABI:
    signature: ClassVar = replace(
        _PRODUCER_SIGNATURE, parameters=(ParameterSpec("factor", default=3, is_static=True),)
    )
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": state["x"] * params["factor"]}


class _Consumer:
    signature: ClassVar = _CONSUMER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"total": state + params["increment"]}


class _Unrelated:
    signature: ClassVar = replace(_PRODUCER_SIGNATURE, name="unrelated")
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": state["x"] + params["factor"]}


class _RecordingDispatcher:
    def __init__(self):
        self.calls = []

    def dispatch(self, **kwargs):
        self.calls.append(kwargs["signature"].fqn)
        return MethodDispatcher.get_instance().dispatch(**kwargs)


def _chain():
    registry = MethodRegistry._create_fresh()
    registry.register(_Original)
    registry.register(_Consumer)
    composer = MethodComposer(registry=registry)
    first = composer.add(_Original.signature.fqn)
    second = composer.add(_Consumer.signature.fqn)
    composer.connect(first, second, {"product": "operand"})
    chain = composer.build(validate_semantics=False)
    assert chain.dag.predecessors[second.id] == frozenset({first.id})
    return chain, registry


@pytest.mark.parametrize("replacement", [_Replacement, _ChangedABI], ids=["source", "abi"])
def test_actual_registry_source_or_abi_replacement_refuses_original_history(tmp_path, replacement):
    chain, registry = _chain()
    dispatcher = _RecordingDispatcher()
    producer = CheckpointingChainExecutor(
        registry=registry, dispatcher=dispatcher, checkpoint_dir=tmp_path
    )
    original = producer.execute(chain, initial_state={"x": 3}, seed=7)
    assert [row.output for _, row in original.node_results] == [{"product": 6}, {"total": 7}]
    checkpoint = ChainCheckpoint.load(next(tmp_path.glob("*_0001_*.json")))
    registry.register(replacement, override=True)
    if replacement is _Replacement:
        cold = CheckpointingChainExecutor(registry=registry).execute(
            chain, initial_state={"x": 3}, seed=7
        )
        assert cold.final_state["total"] == 10
        assert (
            replacement.signature.stable_digest()
            == chain.get_signature(chain.execution_order[0]).stable_digest()
        )
    dispatcher.calls.clear()
    with pytest.raises(CheckpointDigestMismatchError):
        producer.execute(chain, initial_state={"x": 3}, checkpoint=checkpoint, seed=7)
    assert dispatcher.calls == []


def test_unrelated_registration_preserves_exact_effective_checkpoint_request(tmp_path):
    chain, registry = _chain()
    dispatcher = _RecordingDispatcher()
    executor = CheckpointingChainExecutor(
        registry=registry, dispatcher=dispatcher, checkpoint_dir=tmp_path
    )
    original = executor.execute(chain, initial_state={"x": 3}, seed=7)
    checkpoint = ChainCheckpoint.load(next(tmp_path.glob("*_0001_*.json")))
    registry.register(_Unrelated)
    dispatcher.calls.clear()
    resumed = executor.execute(chain, initial_state={"x": 3}, checkpoint=checkpoint, seed=7)
    assert dispatcher.calls == []
    assert resumed.final_state["total"] == 7
    assert [row.reproducibility for _, row in resumed.node_results] == [
        row.reproducibility for _, row in original.node_results
    ]
