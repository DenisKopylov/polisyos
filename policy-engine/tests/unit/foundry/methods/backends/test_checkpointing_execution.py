"""Execute compiled Foundry checkpoints through the real NumPy dispatcher."""

from __future__ import annotations

import fcntl
import multiprocessing
import os
import stat
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from typing import Any, ClassVar
from uuid import uuid4

import numpy as np
import pytest

from polisyos.foundry.methods.backends.chain_executor import execute_heterogeneous_chain
from polisyos.foundry.methods.backends.checkpointing import (
    ChainCheckpoint,
    CheckpointDigestMismatchError,
    CheckpointingChainExecutor,
    CheckpointSaveError,
    _snapshot_node_result,
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
    replayed = CheckpointingChainExecutor(registry=registry).execute(
        chain, {"value": 3.0}, params_per_node=overrides, checkpoint=restored, seed=7
    )
    assert replayed.node_results[0][1].output["value"] == 11.0
    assert (
        replayed.node_results[0][1].reproducibility
        == checkpointed.node_results[0][1].reproducibility
    )
    missing_history = replace(restored, node_results=[], history_complete=False)
    limited_replay = CheckpointingChainExecutor(registry=registry).execute(
        chain, {"value": 3.0}, params_per_node=overrides, checkpoint=missing_history, seed=7
    )
    assert limited_replay.final_state["value"] == 11.0
    assert limited_replay.node_results == ()
    assert limited_replay.reproducibility_contract["history_limitation"] == (
        "checkpoint_per_node_history_missing"
    )
    with pytest.raises(CheckpointDigestMismatchError, match="execution identity"):
        CheckpointingChainExecutor(registry=registry).execute(
            chain,
            {"value": 3.0},
            params_per_node={node.id: {"factor": 4.0, "offset": 2.0}},
            checkpoint=restored,
            seed=7,
        )
    with pytest.raises(ValueError, match="Unknown parameters"):
        CheckpointingChainExecutor(registry=registry).execute(
            chain, {"value": 3.0}, params_per_node={node.id: {"unknown": 1}}, seed=7
        )


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


def _publish_checkpoint_series(path, value: float) -> None:
    for _ in range(4):
        ChainCheckpoint(
            chain_digest="process_concurrency",
            completed_fqns=[],
            completed_node_ids=[],
            intermediate_state={"arr": np.array([value]), "other": np.array([10.0 * value])},
        ).save(path)


def test_process_writers_and_concurrent_reader_observe_one_complete_generation(tmp_path) -> None:
    """Independent processes and a live reader agree on paired sidecar values."""
    path = tmp_path / "checkpoint_process.json"
    _publish_checkpoint_series(path, 1.0)
    context = multiprocessing.get_context("spawn")
    writers = [
        context.Process(target=_publish_checkpoint_series, args=(path, value))
        for value in (2.0, 3.0, 4.0, 5.0)
    ]
    observed = set()
    try:
        for writer in writers:
            writer.start()
        deadline = time.monotonic() + 60.0
        while any(writer.is_alive() for writer in writers):
            assert time.monotonic() < deadline, "checkpoint writer did not finish"
            checkpoint = ChainCheckpoint.load(path)
            pair = (
                checkpoint.intermediate_state["arr"].item(),
                checkpoint.intermediate_state["other"].item(),
            )
            assert pair in {(value, 10.0 * value) for value in (1.0, 2.0, 3.0, 4.0, 5.0)}
            observed.add(pair)
        for writer in writers:
            writer.join(timeout=1.0)
            assert writer.exitcode == 0
        assert observed
        reopened = ChainCheckpoint.load(path)
        assert reopened.intermediate_state["other"].item() == (
            10.0 * reopened.intermediate_state["arr"].item()
        )
    finally:
        for writer in writers:
            if writer.is_alive():
                writer.terminate()
            if writer.pid is not None:
                writer.join(timeout=5.0)


def test_failed_history_only_save_cannot_delete_a_peer_published_sidecar(
    tmp_path, monkeypatch, registry
) -> None:
    """Rollback retains the writer lock until its sidecars are cleaned up."""
    import polisyos.foundry.methods.backends.checkpointing as checkpointing

    method = _method(
        "array_output",
        lambda state, _params: np.array([float(state["value"])]),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="output",
                    slot_type=SlotType.VECTOR,
                    unit=Unit(dimension="dimensionless", symbol="1"),
                    shape=(1,),
                )
            }
        ),
    )
    registry.register(method, override=True)
    dispatcher = MethodDispatcher.get_instance()
    node_id = uuid4()
    snapshots = []
    for value in (1.0, 2.0):
        result = dispatcher.dispatch(
            method_class=method,
            signature=method.signature,
            state={"value": value},
            params={},
            seed=7,
        )
        snapshots.append(_snapshot_node_result(node_id, method.signature.fqn, result))

    path = tmp_path / "checkpoint_history_race.json"
    local = threading.local()
    cleanup_paused = threading.Event()
    release_cleanup = threading.Event()
    atomic_write = checkpointing._atomic_write_bytes
    cleanup = checkpointing._cleanup_paths

    def fail_first_manifest(*args, **kwargs):
        if getattr(local, "failing_writer", False):
            raise OSError("injected failure before first manifest publication")
        return atomic_write(*args, **kwargs)

    def pause_failed_rollback(paths):
        if getattr(local, "failing_writer", False) and any(p.suffix == ".npy" for p in paths):
            cleanup_paused.set()
            assert release_cleanup.wait(timeout=10.0), "rollback release was not received"
        cleanup(paths)

    monkeypatch.setattr(checkpointing, "_atomic_write_bytes", fail_first_manifest)
    monkeypatch.setattr(checkpointing, "_cleanup_paths", pause_failed_rollback)

    def save_snapshot(index: int) -> None:
        local.failing_writer = index == 0
        ChainCheckpoint(
            chain_digest="history_race",
            completed_fqns=[method.signature.fqn],
            completed_node_ids=[str(node_id)],
            intermediate_state={"scalar": index + 1},
            node_results=[snapshots[index]],
            history_complete=True,
        ).save(path)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(save_snapshot, 0)
        try:
            assert cleanup_paused.wait(timeout=10.0), "failed writer never reached rollback"
            # Query the operating system's actual lock to choose a deterministic
            # schedule for both implementations, without inspecting code markers.
            with path.with_name(f".{path.name}.lock").open("a+b") as lock_file:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    rollback_holds_lock = True
                else:
                    rollback_holds_lock = False
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            second = pool.submit(save_snapshot, 1)
            if not rollback_holds_lock:
                second.result(timeout=10.0)
            release_cleanup.set()
            with pytest.raises(CheckpointSaveError, match="first manifest publication"):
                first.result(timeout=10.0)
            second.result(timeout=10.0)
        finally:
            release_cleanup.set()

    loaded = ChainCheckpoint.load(path)
    np.testing.assert_array_equal(loaded.node_results[0]["output"], np.array([2.0]))
