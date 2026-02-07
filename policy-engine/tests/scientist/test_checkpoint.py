from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.scientist.engine.checkpoint import (
    CASCheckpointHook,
    CheckpointCorruptedError,
    RunLockError,
    acquire_run_lock,
    compute_workflow_fingerprint,
    create_checkpoint,
    load_checkpoint_head,
    resolve_latest_checkpoint,
    update_checkpoint_head,
)
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec


def _workflow(node_id: str = "scientist.node_noop@1.0.0") -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="wf_checkpoint",
        required_binds=["run_id"],
        nodes=[NodeInvocation(alias="start", node_id=node_id)],
    )


def test_compute_workflow_fingerprint_changes_on_spec_change() -> None:
    w_a = _workflow("scientist.node_noop@1.0.0")
    w_b = _workflow("scientist.node_noop@1.0.1")

    fp_a = compute_workflow_fingerprint(w_a)
    fp_b = compute_workflow_fingerprint(w_b)

    assert len(fp_a) == 64
    assert len(fp_b) == 64
    assert fp_a != fp_b


def test_checkpoint_head_roundtrip(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    state = ExperimentState(run_id="R_head")
    checkpoint_ref, _ = create_checkpoint(
        store,
        state,
        sequence_number=0,
        completed_node_alias="start",
        completed_node_id="scientist.node_noop@1.0.0",
        completed_nodes=["start"],
        workflow_id="wf_checkpoint",
        workflow_fingerprint="a" * 64,
        fsm_phase="INTAKE",
        cache_entry_refs=[],
    )

    run_dir = tmp_path / "runs" / "R_head"
    update_checkpoint_head(
        run_dir,
        run_id="R_head",
        checkpoint_ref=checkpoint_ref,
        sequence_number=0,
        node_alias="start",
        writer_pid=123,
        writer_hostname="localhost",
    )

    head = load_checkpoint_head(run_dir)
    assert head is not None
    assert head.run_id == "R_head"
    assert head.sequence_number == 0
    assert head.checkpoint_ref.artifact_id == checkpoint_ref.artifact_id


def test_resolve_latest_checkpoint_success(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    state = ExperimentState(run_id="R_resolve", params={"phase": "EXECUTE"})
    checkpoint_ref, _ = create_checkpoint(
        store,
        state,
        sequence_number=2,
        completed_node_alias="compile",
        completed_node_id="scientist.node_compile_foundry@1.0.0",
        completed_nodes=["start", "compile"],
        workflow_id="wf_checkpoint",
        workflow_fingerprint="b" * 64,
        fsm_phase="EXECUTE",
        cache_entry_refs=[],
    )

    run_dir = tmp_path / "runs" / "R_resolve"
    update_checkpoint_head(
        run_dir,
        run_id="R_resolve",
        checkpoint_ref=checkpoint_ref,
        sequence_number=2,
        node_alias="compile",
        writer_pid=111,
        writer_hostname="localhost",
    )

    head, checkpoint = resolve_latest_checkpoint(store, "R_resolve") or (None, None)
    assert head is not None
    assert checkpoint is not None
    assert head.sequence_number == 2
    assert checkpoint.metadata.completed_nodes == ["start", "compile"]


def test_resolve_latest_checkpoint_detects_corruption(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    run_dir = tmp_path / "runs" / "R_bad"
    run_dir.mkdir(parents=True, exist_ok=True)

    bogus = store.put_json(
        {"hello": "world"},
        PutOptions(kind="test.payload", media_type="application/json"),
    )
    update_checkpoint_head(
        run_dir,
        run_id="R_bad",
        checkpoint_ref=bogus,
        sequence_number=0,
        node_alias="start",
        writer_pid=999,
        writer_hostname="localhost",
    )

    with pytest.raises(CheckpointCorruptedError):
        resolve_latest_checkpoint(store, "R_bad")


def test_run_lock_conflict(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "R_lock"
    lock_a = acquire_run_lock(run_dir, run_id="R_lock", mode="run")
    try:
        with pytest.raises(RunLockError):
            acquire_run_lock(run_dir, run_id="R_lock", mode="resume")
    finally:
        lock_a.release()


def test_checkpoint_hook_disabled_by_policy(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    hook = CASCheckpointHook(
        store=store,
        run_dir=tmp_path / "runs" / "R_off",
        checkpoint_policy="off",
    )
    result = hook.on_node_complete(
        state=ExperimentState(run_id="R_off"),
        alias="start",
        node_id="scientist.node_noop@1.0.0",
        completed_nodes=["start"],
        workflow_id="wf_checkpoint",
        workflow_fingerprint="c" * 64,
        cache_entry_ref=None,
    )
    assert result is None
