"""Execute compiled Foundry checkpoints through the real NumPy dispatcher."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from typing import Any, ClassVar

import numpy as np
import pytest

from polisyos.foundry.methods.backends.chain_executor import execute_heterogeneous_chain
from polisyos.foundry.methods.backends.checkpointing import (
    ChainCheckpoint,
    CheckpointDigestMismatchError,
    CheckpointingChainExecutor,
    CheckpointSaveError,
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
from polisyos.foundry.methods.selection.registry import MethodRegistry


def _slot(name: str) -> SlotSpec:
    return SlotSpec(
        name=name,
        slot_type=SlotType.SCALAR,
        unit=Unit(dimension="dimensionless", symbol="1"),
        shape=(),
    )


def _method(
    name: str,
    step: Callable[[Any, dict[str, Any]], Any],
    *,
    input_slots: frozenset[SlotSpec] = frozenset(),
    output_slots: frozenset[SlotSpec],
    parameters: tuple[ParameterSpec, ...] = (),
) -> type:
    signature = MethodSignature(
        name=name,
        namespace="tests.checkpoint_execution",
        version="1.0.0",
        input_slots=input_slots,
        output_slots=output_slots,
        parameters=parameters,
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    class Method:
        metadata: ClassVar[MethodMetadata] = MethodMetadata(description=name)

        @staticmethod
        def pure_step(state: Any, params: dict[str, Any]) -> Any:
            return step(state, params)

    Method.signature = signature
    return Method


@pytest.fixture
def registry():
    MethodRegistry.reset_instance()
    yield MethodRegistry.get_instance()
    MethodRegistry.reset_instance()


@pytest.mark.parametrize("declares_seed", [False, True])
def test_checkpoint_execution_preserves_static_dynamic_and_override_payload(
    tmp_path, registry, declares_seed
) -> None:
    """Runtime seed must not become an unknown parameter; static values survive."""
    parameters = (
        ParameterSpec(name="factor", default=2.0, is_static=True),
        ParameterSpec(name="offset", default=1.0, is_static=False),
    )
    if declares_seed:
        parameters += (ParameterSpec(name="seed", default=0, is_static=False),)
    method = _method(
        "multiply",
        lambda state, params: {
            "value": float(state["value"]) * params["factor"] + params["offset"]
        },
        output_slots=frozenset({_slot("value")}),
        parameters=parameters,
    )
    registry.register(method, override=True)
    composer = MethodComposer(registry=registry)
    node = composer.add(method.signature.fqn, factor=3.0, offset=1.0)
    chain = composer.build(validate_semantics=False)
    overrides = {node.id: {"offset": 2.0}}
    sequential = execute_heterogeneous_chain(
        chain,
        state={"value": 3.0},
        params_per_node=overrides,
        registry=registry,
        executor_mode="sequential",
        seed=7,
    )
    checkpointed = CheckpointingChainExecutor(checkpoint_dir=tmp_path, registry=registry).execute(
        chain, {"value": 3.0}, params_per_node=overrides, seed=7
    )
    assert sequential.final_state["value"] == 11.0
    assert checkpointed.final_state["value"] == 11.0
    restored = ChainCheckpoint.load(next(tmp_path.glob("checkpoint_*.json")))
    assert restored.node_results[0]["output"]["value"] == 11.0


def test_checkpoint_resume_materializes_saved_slot_outputs_and_original_history(
    tmp_path, registry
) -> None:
    """Saved product feeds a renamed input after restart, preserving 6 then 7."""
    multiply = _method(
        "multiply_bound",
        lambda state, params: {"product": float(state["value"]) * params["factor"]},
        output_slots=frozenset({_slot("product")}),
        parameters=(
            ParameterSpec(name="factor", default=2.0, is_static=True),
            ParameterSpec(name="seed", default=0, is_static=False),
        ),
    )
    add = _method(
        "add_bound",
        lambda state, params: {"total": float(state) + params["offset"]},
        input_slots=frozenset({_slot("input_value")}),
        output_slots=frozenset({_slot("total")}),
        parameters=(
            ParameterSpec(name="offset", default=1.0, is_static=False),
            ParameterSpec(name="seed", default=0, is_static=False),
        ),
    )
    registry.register(multiply, override=True)
    registry.register(add, override=True)
    composer = MethodComposer(registry=registry)
    source = composer.add(multiply.signature.fqn, factor=2.0)
    target = composer.add(add.signature.fqn)
    composer.connect(source, target, slot_mapping={"product": "input_value"})
    chain = composer.build(validate_semantics=False)
    cold = CheckpointingChainExecutor(checkpoint_dir=tmp_path, registry=registry).execute(
        chain, {"value": 3.0}, seed=7
    )
    checkpoint = ChainCheckpoint.load(next(tmp_path.glob("*_0000_*.json")))
    resumed = CheckpointingChainExecutor(registry=registry).execute(
        chain, {"value": 3.0}, checkpoint=checkpoint, seed=7
    )
    assert cold.final_state["total"] == resumed.final_state["total"] == 7.0
    assert [result.output for _, result in resumed.node_results] == [
        {"product": 6.0},
        {"total": 7.0},
    ]
    assert resumed.node_results[0][1].reproducibility == cold.node_results[0][1].reproducibility
    with pytest.raises(CheckpointDigestMismatchError, match="execution identity"):
        CheckpointingChainExecutor(registry=registry).execute(
            chain, {"value": 4.0}, checkpoint=checkpoint, seed=7
        )


def test_directory_fsync_failure_after_manifest_replace_preserves_readable_generation(
    tmp_path, monkeypatch
) -> None:
    """A failed directory sync must not delete the newly referenced sidecars."""
    path = tmp_path / "checkpoint_fsync.json"
    ChainCheckpoint(
        chain_digest="fsync",
        completed_fqns=[],
        completed_node_ids=[],
        intermediate_state={"arr": np.array([1.0]), "other": np.array([10.0])},
    ).save(path)
    old_manifest = path.read_bytes()
    fsync = os.fsync
    injected = False

    def fail_manifest_directory_sync(fd: int) -> None:
        nonlocal injected
        if stat.S_ISDIR(os.fstat(fd).st_mode) and path.read_bytes() != old_manifest:
            injected = True
            raise OSError("injected directory fsync failure after manifest replace")
        fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_manifest_directory_sync)
    with pytest.raises(CheckpointSaveError, match="directory fsync failure"):
        ChainCheckpoint(
            chain_digest="fsync",
            completed_fqns=[],
            completed_node_ids=[],
            intermediate_state={"arr": np.array([2.0]), "other": np.array([20.0])},
        ).save(path)
    assert injected
    loaded = ChainCheckpoint.load(path)
    values = (loaded.intermediate_state["arr"].item(), loaded.intermediate_state["other"].item())
    assert values in ((1.0, 10.0), (2.0, 20.0))
