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


def _history_array_checkpoints(tmp_path):
    import numpy as np

    method = _method(
        "history_array",
        output="output",
        step=lambda state, params: np.asarray(params["value"]),
        parameters=(ParameterSpec(name="value", default=1),),
    )
    registry = MethodRegistry.get_instance()
    composer = MethodComposer(registry=registry)
    node = composer.add(method.signature.fqn)
    chain = composer.build(validate_semantics=False)
    checkpoints = []
    for value in (1, 2):
        directory = tmp_path / f"producer-{value}"
        CheckpointingChainExecutor(registry=registry, checkpoint_dir=directory).execute(
            chain, initial_state={}, params_per_node={node.id: {"value": value}}, seed=23
        )
        checkpoint = ChainCheckpoint.load(next(directory.glob("checkpoint*.json")))
        assert checkpoint.intermediate_state == {}
        assert checkpoint.history_complete
        checkpoints.append(checkpoint)
    return chain, registry, node, checkpoints


def test_manifest_directory_fsync_fault_preserves_published_history_consumer(tmp_path, monkeypatch):
    import numpy as np

    import polisyos.foundry.methods.backends.checkpointing as module

    chain, registry, node, checkpoints = _history_array_checkpoints(tmp_path)
    path = tmp_path / "shared.json"
    original_fsync = module._fsync_dir

    def fail_after_manifest_publish(directory):
        if directory == path.parent and path.exists():
            raise OSError("injected manifest parent fsync fault")
        original_fsync(directory)

    monkeypatch.setattr(module, "_fsync_dir", fail_after_manifest_publish)
    with pytest.raises(module.CheckpointPublicationUncertainError):
        checkpoints[1].save(path)
    # Atomic replacement has happened: this consumer must retain the published
    # array, even while its durability outcome remains uncertain.
    checkpoint = ChainCheckpoint.load(path)
    result = CheckpointingChainExecutor(registry=registry).execute(
        chain,
        initial_state={},
        params_per_node={node.id: {"value": 2}},
        checkpoint=checkpoint,
        seed=23,
    )
    np.testing.assert_array_equal(result.node_results[0][1].output, np.asarray(2))
    assert result.node_results[0][1].reproducibility.seed == 23


def test_history_only_failed_writer_cannot_delete_peer_publication(tmp_path, monkeypatch):
    import fcntl
    import threading

    import numpy as np

    import polisyos.foundry.methods.backends.checkpointing as module

    chain, registry, node, checkpoints = _history_array_checkpoints(tmp_path)
    path = tmp_path / "shared.json"
    rollback_entered = threading.Event()
    release_rollback = threading.Event()
    errors = []
    original_write = module._atomic_write_bytes
    original_cleanup = module._cleanup_paths

    def fail_first_manifest(tmp, target, data, **kwargs):
        if target == path and threading.current_thread().name == "fault-writer":
            raise OSError("injected failure before manifest replacement")
        return original_write(tmp, target, data, **kwargs)

    paused = False

    def pause_actual_rollback(paths):
        nonlocal paused
        if threading.current_thread().name == "fault-writer" and not paused:
            paused = True
            rollback_entered.set()
            if not release_rollback.wait(10):
                raise RuntimeError("fixture rollback synchronization did not complete")
        return original_cleanup(paths)

    def first_writer():
        try:
            checkpoints[0].save(path)
        except BaseException as exc:
            errors.append(exc)

    monkeypatch.setattr(module, "_atomic_write_bytes", fail_first_manifest)
    monkeypatch.setattr(module, "_cleanup_paths", pause_actual_rollback)
    worker = threading.Thread(target=first_writer, name="fault-writer")
    worker.start()
    try:
        assert rollback_entered.wait(10)
        lock_path = path.with_name(f".{path.name}.lock")
        with lock_path.open("a+b") as probe:
            try:
                fcntl.flock(probe.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                # A correct publication owner still owns its rollback. Finish
                # it, then let the genuine peer publish normally.
                release_rollback.set()
                worker.join(10)
                checkpoints[1].save(path)
            else:
                # The old implementation exposes an unlocked rollback window.
                # Publish a genuine peer before allowing that rollback to run.
                fcntl.flock(probe.fileno(), fcntl.LOCK_UN)
                checkpoints[1].save(path)
                release_rollback.set()
                worker.join(10)
        assert not worker.is_alive()
        assert len(errors) == 1 and isinstance(errors[0], CheckpointSaveError)
        checkpoint = ChainCheckpoint.load(path)
        result = CheckpointingChainExecutor(registry=registry).execute(
            chain,
            initial_state={},
            params_per_node={node.id: {"value": 2}},
            checkpoint=checkpoint,
            seed=23,
        )
        np.testing.assert_array_equal(result.node_results[0][1].output, np.asarray(2))
        np.testing.assert_array_equal(
            result.node_results[0][1].slot_outputs["output"], np.asarray(2)
        )
    finally:
        release_rollback.set()
        worker.join(10)


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


@pytest.mark.parametrize(
    "incomplete_provenance", ["header", "unknown_header", "missing_header", "original_warning"]
)
def test_present_rows_do_not_restore_incomplete_history_authority(tmp_path, incomplete_provenance):
    chain, registry, calls = _bound_chain()
    writer_dir = tmp_path / "writer"
    CheckpointingChainExecutor(registry=registry, checkpoint_dir=writer_dir).execute(
        chain, initial_state={"x": 4}, seed=7
    )
    checkpoint = ChainCheckpoint.load(next(writer_dir.glob("*_0000_*.json")))
    assert checkpoint.history_complete
    assert len(checkpoint.node_results) == checkpoint.n_completed == 1
    if incomplete_provenance in {"header", "missing_header"}:
        checkpoint.history_complete = False
    elif incomplete_provenance == "unknown_header":
        checkpoint.history_complete = "unknown"
    else:
        checkpoint.node_results[0]["warnings"].append("history_incomplete")
    path = tmp_path / "incomplete-provenance.json"
    checkpoint.save(path)
    if incomplete_provenance == "missing_header":
        import json

        data = json.loads(path.read_text())
        if data.get("checkpoint_format") == "generation-v1":
            data = json.loads((path.parent / data["snapshot_ref"]).read_text())
        # Exercise the retained direct-JSON legacy profile with a genuinely
        # missing header, rather than changing the generation pointer schema.
        del data["history_complete"]
        path.write_text(json.dumps(data))
    checkpoint = ChainCheckpoint.load(path)
    calls.clear()
    resumed_dir = tmp_path / "resumed"
    result = CheckpointingChainExecutor(registry=registry, checkpoint_dir=resumed_dir).execute(
        chain, initial_state={"x": 4}, checkpoint=checkpoint, seed=7
    )
    # The original slot is available for real suffix arithmetic, while its
    # explicitly incomplete provenance must survive result and republishing.
    assert calls == ["add"]
    assert result.final_state["total"] == 13
    assert len(result.node_results) == 2
    assert result.missing_history_node_ids == ()
    assert not result.history_complete
    assert result.reproducibility_contract["history_complete"] is False
    persisted = ChainCheckpoint.load(next(resumed_dir.glob("*_0001_*.json")))
    assert not persisted.history_complete
    assert len(persisted.node_results) == 2
    calls.clear()
    again = CheckpointingChainExecutor(registry=registry).execute(
        chain, initial_state={"x": 4}, checkpoint=persisted, seed=7
    )
    assert calls == []
    assert not again.history_complete


_CHECKPOINT_PROCESS_DRIVER = r"""
import hashlib, json, pathlib, runpy, sys, threading, time
import numpy as np
import polisyos.foundry.methods.backends.checkpointing as module

source, mode, manifest_text, fixture_text, ready_text, go_text, value_text, result_text = sys.argv[1:]
manifest, fixture, ready, go, result_path = map(pathlib.Path, (manifest_text, fixture_text, ready_text, go_text, result_text))
value = int(value_text)
namespace = runpy.run_path(source)

def observe():
    checkpoint = module.ChainCheckpoint.load(manifest)
    node_id, original = module._restore_node_result(checkpoint.node_results[0], checkpoint)
    assert str(node_id) == checkpoint.completed_node_ids[0]
    assert original.reproducibility.seed == 23
    assert original.reproducibility.backend.value == 'numpy'
    actual = int(original.output)
    assert actual in (1, 2)
    np.testing.assert_array_equal(original.slot_outputs['output'], original.output)
    return actual

if mode == 'reader':
    seen = {observe()}; count = 1
    ready.write_text('ready')
    while not go.exists(): time.sleep(0.005)
    while not all((fixture.parent / f'writer-{v}.done').exists() for v in (1, 2)):
        seen.add(observe()); count += 1
    seen.add(observe()); count += 1
    result_path.write_text(json.dumps({'observations': count, 'values_seen': sorted(seen),
        'module_path': module.__file__, 'module_sha256': hashlib.sha256(pathlib.Path(module.__file__).read_bytes()).hexdigest()}))
else:
    chain, registry, node, checkpoints = namespace['_history_array_checkpoints'](fixture)
    checkpoint = checkpoints[value - 1]
    if mode in ('kill_before_pointer', 'kill_after_pointer'):
        original_write = module._atomic_write_bytes
        def pause_write(tmp, target, data, *, on_publish=None):
            if target != manifest:
                return original_write(tmp, target, data, on_publish=on_publish)
            if mode == 'kill_before_pointer':
                ready.write_text('ready'); threading.Event().wait()
            def after_publish():
                on_publish(); ready.write_text('ready'); threading.Event().wait()
            return original_write(tmp, target, data, on_publish=after_publish)
        module._atomic_write_bytes = pause_write
        checkpoint.save(manifest)
    else:
        ready.write_text('ready')
        while not go.exists(): time.sleep(0.005)
        for iteration in range(25): checkpoint.save(manifest)
        result_path.write_text(json.dumps({'writes': 25, 'module_path': module.__file__,
            'module_sha256': hashlib.sha256(pathlib.Path(module.__file__).read_bytes()).hexdigest()}))
        (fixture.parent / f'writer-{value}.done').write_text('done')
"""


def _checkpoint_process(tmp_path, *, mode, manifest, value, go):
    import os
    import subprocess
    import sys
    from pathlib import Path

    fixture = tmp_path / f"process-{mode}-{value}"
    fixture.mkdir()
    ready = fixture / "ready"
    result_path = fixture / "result.json"
    argv = [
        sys.executable,
        "-c",
        _CHECKPOINT_PROCESS_DRIVER,
        str(Path(__file__).resolve()),
        mode,
        str(manifest),
        str(fixture),
        str(ready),
        str(go),
        str(value),
        str(result_path),
    ]
    env = os.environ.copy()
    env["POLISYOS_METRICS_PORT"] = "0"
    stdout = (fixture / "stdout.txt").open("wb")
    stderr = (fixture / "stderr.txt").open("wb")
    child = subprocess.Popen(argv, env=env, stdout=stdout, stderr=stderr)
    stdout.close()
    stderr.close()
    return child, ready, result_path


def _await_checkpoint_process_ready(child, ready):
    import time

    deadline = time.monotonic() + 30
    while not ready.exists():
        assert child.poll() is None, (ready.parent / "stderr.txt").read_text()
        assert time.monotonic() < deadline, "real subprocess did not reach fixture boundary"
        time.sleep(0.005)


@pytest.mark.parametrize("stage", ["before_pointer", "after_pointer"])
def test_process_kill_selects_only_complete_old_or_new_history(tmp_path, stage):
    import signal

    import numpy as np

    from polisyos.foundry.methods.backends.checkpointing import _restore_node_result

    chain, registry, node, checkpoints = _history_array_checkpoints(tmp_path)
    manifest = tmp_path / "shared.json"
    checkpoints[0].save(manifest)
    child, ready, _ = _checkpoint_process(
        tmp_path, mode=f"kill_{stage}", manifest=manifest, value=2, go=tmp_path / "go"
    )
    try:
        _await_checkpoint_process_ready(child, ready)
        child.kill()
        assert child.wait(timeout=10) == -signal.SIGKILL
        checkpoint = ChainCheckpoint.load(manifest)
        restored_id, result = _restore_node_result(checkpoint.node_results[0], checkpoint)
        assert str(restored_id) == checkpoint.completed_node_ids[0]
        expected = 1 if stage == "before_pointer" else 2
        np.testing.assert_array_equal(result.output, np.asarray(expected))
        np.testing.assert_array_equal(result.slot_outputs["output"], np.asarray(expected))
        assert result.reproducibility.seed == 23
        if stage == "before_pointer":
            resumed = CheckpointingChainExecutor(registry=registry).execute(
                chain,
                initial_state={},
                params_per_node={node.id: {"value": 1}},
                checkpoint=checkpoint,
                seed=23,
            )
            np.testing.assert_array_equal(resumed.node_results[0][1].output, np.asarray(1))
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)


def test_fresh_process_reader_observes_complete_generations_from_two_process_writers(tmp_path):
    import hashlib
    import json
    from pathlib import Path

    import polisyos.foundry.methods.backends.checkpointing as module

    _, _, _, checkpoints = _history_array_checkpoints(tmp_path)
    manifest = tmp_path / "shared.json"
    checkpoints[0].save(manifest)
    go = tmp_path / "go"
    children = [
        _checkpoint_process(tmp_path, mode="writer", manifest=manifest, value=value, go=go)
        for value in (1, 2)
    ]
    children.append(_checkpoint_process(tmp_path, mode="reader", manifest=manifest, value=0, go=go))
    try:
        for child, ready, _ in children:
            _await_checkpoint_process_ready(child, ready)
        go.write_text("go")
        for child, ready, _ in children:
            assert child.wait(timeout=30) == 0, (ready.parent / "stderr.txt").read_text()
        packets = [json.loads(result.read_text()) for _, _, result in children]
        assert [packet["writes"] for packet in packets[:2]] == [25, 25]
        assert packets[2]["observations"] > 1
        assert set(packets[2]["values_seen"]) <= {1, 2}
        expected_hash = hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        for packet in packets:
            assert packet["module_path"] == module.__file__
            assert packet["module_sha256"] == expected_hash
    finally:
        go.touch()
        for child, _, _ in children:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)
