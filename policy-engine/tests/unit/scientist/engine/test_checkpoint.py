from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from polisyos.common.async_tools import run_coro_sync
from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
from polisyos.core.artifacts.backends.config import ArtifactStoreConfig
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.scientist.engine.checkpoint import (
    CASCheckpointHook,
    CheckpointCorruptedError,
    CheckpointHistory,
    CheckpointHistoryEntry,
    CheckpointMetadataConflictError,
    RunLockError,
    acquire_run_lock,
    compute_workflow_fingerprint,
    create_checkpoint,
    create_checkpoint_async,
    load_checkpoint,
    load_checkpoint_head,
    load_checkpoint_history,
    materialize_checkpoint_state,
    resolve_latest_checkpoint,
    restore_checkpoint_hook_from_runtime_metadata,
    resume_from_checkpoint,
    serialize_checkpoint_hook_runtime_metadata,
    update_checkpoint_head,
    write_checkpoint_history,
)
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec

if TYPE_CHECKING:
    from pathlib import Path


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
    created = create_checkpoint(
        store,
        run_id=state.run_id,
        state=state.model_dump(mode="python", by_alias=True, exclude_none=False),
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
        checkpoint_ref=created.checkpoint_ref,
        sequence_number=0,
        node_alias="start",
        writer_pid=123,
        writer_hostname="localhost",
    )

    head = load_checkpoint_head(run_dir)
    assert head is not None
    assert head.run_id == "R_head"
    assert head.sequence_number == 0
    assert head.checkpoint_ref.artifact_id == created.checkpoint_ref.artifact_id


def test_create_checkpoint_async_repeated_soak_smoke(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    async_store = AsyncArtifactStoreAdapter(store)
    state = ExperimentState(run_id="R_async_checkpoint", params={"phase": "INTAKE"})

    async def _exercise() -> list[str]:
        refs: list[str] = []
        previous_ref = None
        previous_state = None
        previous_chain_depth = 0
        for sequence in range(24):
            created = await create_checkpoint_async(
                async_store,
                run_id=state.run_id,
                state=state.model_dump(mode="python", by_alias=True, exclude_none=False),
                sequence_number=sequence,
                completed_node_alias=f"step_{sequence}",
                completed_node_id=f"scientist.node_step_{sequence}@1.0.0",
                completed_nodes=[f"step_{index}" for index in range(sequence + 1)],
                workflow_id="wf_checkpoint",
                workflow_fingerprint="a" * 64,
                fsm_phase="INTAKE",
                cache_entry_refs=[],
                previous_state=previous_state,
                previous_checkpoint_ref=previous_ref,
                previous_chain_depth=previous_chain_depth,
            )
            refs.append(str(created.checkpoint_ref.artifact_id))
            previous_ref = created.checkpoint_ref
            previous_state = state.model_dump(mode="python", by_alias=True, exclude_none=False)
            previous_chain_depth = created.chain_depth
        return refs

    refs = run_coro_sync(_exercise())
    assert len(refs) == 24
    assert len(set(refs)) == 24


def test_checkpoint_hook_async_repeated_writes_soak_smoke(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    run_dir = tmp_path / "runs" / "R_hook_async"
    hook = CASCheckpointHook(store=store, run_dir=run_dir)
    state = ExperimentState(run_id="R_hook_async", params={"phase": "EXECUTE", "step": 0})

    async def _exercise() -> list[int]:
        sequence_numbers: list[int] = []
        for index in range(20):
            state.params["step"] = index
            result = await hook.on_node_complete_async(
                state=state,
                alias=f"step_{index}",
                node_id=f"scientist.node_step_{index}@1.0.0",
                completed_nodes=[f"step_{item}" for item in range(index + 1)],
                workflow_id="wf_checkpoint",
                workflow_fingerprint="b" * 64,
                cache_entry_ref=None,
            )
            assert result is not None
            sequence_numbers.append(result.sequence_number)
        return sequence_numbers

    sequence_numbers = run_coro_sync(_exercise())
    assert sequence_numbers == list(range(20))
    head = load_checkpoint_head(run_dir)
    assert head is not None
    assert head.sequence_number == 19


def test_checkpoint_head_invalid_json_raises_typed_error(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "R_head_bad_json"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "checkpoint_head.json").write_text("{not-json", encoding="utf-8")

    with pytest.raises(CheckpointCorruptedError, match="checkpoint head"):
        load_checkpoint_head(run_dir)


def test_checkpoint_history_invalid_json_raises_typed_error(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "R_history_bad_json"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "checkpoint_history.json").write_text("{not-json", encoding="utf-8")

    with pytest.raises(CheckpointCorruptedError, match="checkpoint history"):
        load_checkpoint_history(run_dir)


def test_resolve_latest_checkpoint_success(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    state = ExperimentState(run_id="R_resolve", params={"phase": "EXECUTE"})
    created = create_checkpoint(
        store,
        run_id=state.run_id,
        state=state.model_dump(mode="python", by_alias=True, exclude_none=False),
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
        checkpoint_ref=created.checkpoint_ref,
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


def test_resolve_latest_checkpoint_repairs_history_when_head_is_newer(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_reconcile_history"

    state_v0 = ExperimentState(run_id=run_id, params={"phase": "PLAN"})
    created_v0 = create_checkpoint(
        store,
        run_id=run_id,
        state=state_v0.model_dump(mode="python", by_alias=True, exclude_none=False),
        sequence_number=0,
        completed_node_alias="start",
        completed_node_id="scientist.node_noop@1.0.0",
        completed_nodes=["start"],
        workflow_id="wf_checkpoint",
        workflow_fingerprint="c" * 64,
        fsm_phase="PLAN",
        cache_entry_refs=[],
    )
    state_v1 = ExperimentState(run_id=run_id, params={"phase": "EXECUTE", "step2": 1})
    created_v1 = create_checkpoint(
        store,
        run_id=run_id,
        state=state_v1.model_dump(mode="python", by_alias=True, exclude_none=False),
        sequence_number=1,
        completed_node_alias="step2",
        completed_node_id="scientist.node_step_two@1.0.0",
        completed_nodes=["start", "step2"],
        workflow_id="wf_checkpoint",
        workflow_fingerprint="c" * 64,
        fsm_phase="EXECUTE",
        cache_entry_refs=[],
    )

    run_dir = tmp_path / "runs" / run_id
    update_checkpoint_head(
        run_dir,
        run_id=run_id,
        checkpoint_ref=created_v1.checkpoint_ref,
        sequence_number=1,
        node_alias="step2",
        writer_pid=321,
        writer_hostname="localhost",
    )
    write_checkpoint_history(
        run_dir,
        CheckpointHistory(
            entries=[
                CheckpointHistoryEntry(
                    run_id=run_id,
                    checkpoint_ref=created_v0.checkpoint_ref,
                    sequence_number=0,
                    node_alias="start",
                    writer_pid=123,
                    writer_hostname="localhost",
                    updated_at=load_checkpoint_head(run_dir).updated_at,
                )
            ]
        ),
    )

    resolved = resolve_latest_checkpoint(store, run_id)

    assert resolved is not None
    head, checkpoint = resolved
    assert head.sequence_number == 1
    assert checkpoint.metadata.sequence_number == 1
    repaired_history = load_checkpoint_history(run_dir)
    assert repaired_history is not None
    assert max(entry.sequence_number for entry in repaired_history.entries) == 1
    assert any(
        str(entry.checkpoint_ref.artifact_id) == str(created_v1.checkpoint_ref.artifact_id)
        for entry in repaired_history.entries
    )


def test_resolve_latest_checkpoint_rejects_head_history_conflict(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_head_history_conflict"
    state = ExperimentState(run_id=run_id, params={"phase": "EXECUTE"})
    checkpoint_a = create_checkpoint(
        store,
        run_id=run_id,
        state=state.model_dump(mode="python", by_alias=True, exclude_none=False),
        sequence_number=0,
        completed_node_alias="step_a",
        completed_node_id="scientist.node_step_a@1.0.0",
        completed_nodes=["step_a"],
        workflow_id="wf_checkpoint",
        workflow_fingerprint="d" * 64,
        fsm_phase="EXECUTE",
        cache_entry_refs=[],
    )
    checkpoint_b = create_checkpoint(
        store,
        run_id=run_id,
        state=ExperimentState(
            run_id=run_id,
            params={"phase": "EXECUTE", "branch": "b"},
        ).model_dump(mode="python", by_alias=True, exclude_none=False),
        sequence_number=0,
        completed_node_alias="step_b",
        completed_node_id="scientist.node_step_b@1.0.0",
        completed_nodes=["step_b"],
        workflow_id="wf_checkpoint",
        workflow_fingerprint="d" * 64,
        fsm_phase="EXECUTE",
        cache_entry_refs=[],
    )

    run_dir = tmp_path / "runs" / run_id
    update_checkpoint_head(
        run_dir,
        run_id=run_id,
        checkpoint_ref=checkpoint_a.checkpoint_ref,
        sequence_number=0,
        node_alias="step_a",
        writer_pid=111,
        writer_hostname="localhost",
    )
    head = load_checkpoint_head(run_dir)
    assert head is not None
    write_checkpoint_history(
        run_dir,
        CheckpointHistory(
            entries=[
                CheckpointHistoryEntry(
                    run_id=run_id,
                    checkpoint_ref=checkpoint_b.checkpoint_ref,
                    sequence_number=0,
                    node_alias="step_b",
                    writer_pid=222,
                    writer_hostname="localhost",
                    updated_at=head.updated_at,
                )
            ]
        ),
    )

    with pytest.raises(CheckpointMetadataConflictError, match="head/history"):
        resolve_latest_checkpoint(store, run_id)


def test_resolve_latest_checkpoint_rejects_divergent_latest_history_entries(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_history_divergent_latest"
    checkpoint_a = create_checkpoint(
        store,
        run_id=run_id,
        state=ExperimentState(run_id=run_id, params={"branch": "a"}).model_dump(
            mode="python",
            by_alias=True,
            exclude_none=False,
        ),
        sequence_number=1,
        completed_node_alias="step_a",
        completed_node_id="scientist.node_step_a@1.0.0",
        completed_nodes=["step_a"],
        workflow_id="wf_checkpoint",
        workflow_fingerprint="e" * 64,
        fsm_phase="EXECUTE",
        cache_entry_refs=[],
    )
    checkpoint_b = create_checkpoint(
        store,
        run_id=run_id,
        state=ExperimentState(run_id=run_id, params={"branch": "b"}).model_dump(
            mode="python",
            by_alias=True,
            exclude_none=False,
        ),
        sequence_number=1,
        completed_node_alias="step_b",
        completed_node_id="scientist.node_step_b@1.0.0",
        completed_nodes=["step_b"],
        workflow_id="wf_checkpoint",
        workflow_fingerprint="e" * 64,
        fsm_phase="EXECUTE",
        cache_entry_refs=[],
    )

    run_dir = tmp_path / "runs" / run_id
    update_checkpoint_head(
        run_dir,
        run_id=run_id,
        checkpoint_ref=checkpoint_a.checkpoint_ref,
        sequence_number=1,
        node_alias="step_a",
        writer_pid=111,
        writer_hostname="localhost",
    )
    head = load_checkpoint_head(run_dir)
    assert head is not None
    write_checkpoint_history(
        run_dir,
        CheckpointHistory(
            entries=[
                CheckpointHistoryEntry(
                    run_id=run_id,
                    checkpoint_ref=checkpoint_a.checkpoint_ref,
                    sequence_number=1,
                    node_alias="step_a",
                    writer_pid=111,
                    writer_hostname="localhost",
                    updated_at=head.updated_at,
                ),
                CheckpointHistoryEntry(
                    run_id=run_id,
                    checkpoint_ref=checkpoint_b.checkpoint_ref,
                    sequence_number=1,
                    node_alias="step_b",
                    writer_pid=222,
                    writer_hostname="localhost",
                    updated_at=head.updated_at,
                ),
            ]
        ),
    )

    with pytest.raises(
        CheckpointMetadataConflictError,
        match="multiple conflicting latest entries",
    ):
        resolve_latest_checkpoint(store, run_id)


def test_resolve_latest_checkpoint_rejects_head_artifact_metadata_mismatch(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_head_artifact_mismatch"
    created = create_checkpoint(
        store,
        run_id=run_id,
        state=ExperimentState(run_id=run_id, params={"phase": "EXECUTE"}).model_dump(
            mode="python",
            by_alias=True,
            exclude_none=False,
        ),
        sequence_number=0,
        completed_node_alias="step_a",
        completed_node_id="scientist.node_step_a@1.0.0",
        completed_nodes=["step_a"],
        workflow_id="wf_checkpoint",
        workflow_fingerprint="f" * 64,
        fsm_phase="EXECUTE",
        cache_entry_refs=[],
    )

    run_dir = tmp_path / "runs" / run_id
    update_checkpoint_head(
        run_dir,
        run_id=run_id,
        checkpoint_ref=created.checkpoint_ref,
        sequence_number=0,
        node_alias="step_b",
        writer_pid=111,
        writer_hostname="localhost",
    )

    with pytest.raises(
        CheckpointCorruptedError,
        match=r"metadata mismatch.*node_alias",
    ):
        resolve_latest_checkpoint(store, run_id)


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


def test_checkpoint_hook_gc_failure_does_not_rollback_commit_bookkeeping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_gc_failure"
    run_dir = tmp_path / "runs" / run_id
    hook = CASCheckpointHook(
        store=store,
        run_dir=run_dir,
        checkpoint_policy="strict",
    )

    def _raise_gc(*args, **kwargs):
        raise OSError("gc unavailable")

    monkeypatch.setattr(
        "polisyos.scientist.engine.checkpoint.gc_checkpoints",
        _raise_gc,
    )

    first = hook.on_node_complete(
        state=ExperimentState(run_id=run_id, params={"phase": "PLAN", "step": 1}),
        alias="step1",
        node_id="scientist.node_step_one@1.0.0",
        completed_nodes=["step1"],
        workflow_id="wf_checkpoint",
        workflow_fingerprint="e" * 64,
        cache_entry_ref=None,
    )
    second = hook.on_node_complete(
        state=ExperimentState(run_id=run_id, params={"phase": "EXECUTE", "step": 2}),
        alias="step2",
        node_id="scientist.node_step_two@1.0.0",
        completed_nodes=["step1", "step2"],
        workflow_id="wf_checkpoint",
        workflow_fingerprint="e" * 64,
        cache_entry_ref=None,
    )

    assert first is not None
    assert second is not None
    assert first.sequence_number == 0
    assert second.sequence_number == 1
    head = load_checkpoint_head(run_dir)
    assert head is not None
    assert head.sequence_number == 1
    resolved = resolve_latest_checkpoint(store, run_id)
    assert resolved is not None
    assert resolved[0].sequence_number == 1


def test_checkpoint_hook_runtime_metadata_roundtrip_preserves_sequence(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_checkpoint_roundtrip"
    run_dir = tmp_path / "runs" / run_id
    hook = CASCheckpointHook(
        store=store,
        run_dir=run_dir,
        checkpoint_policy="strict",
    )

    first = hook.on_node_complete(
        state=ExperimentState(run_id=run_id, params={"phase": "PLAN", "step": 1}),
        alias="step1",
        node_id="scientist.node_step_one@1.0.0",
        completed_nodes=["step1"],
        workflow_id="wf_checkpoint",
        workflow_fingerprint="f" * 64,
        cache_entry_ref=None,
    )
    metadata = serialize_checkpoint_hook_runtime_metadata(hook)
    restored = restore_checkpoint_hook_from_runtime_metadata(metadata)

    assert metadata is not None
    assert restored is not None

    second = restored.on_node_complete(
        state=ExperimentState(run_id=run_id, params={"phase": "EXECUTE", "step": 2}),
        alias="step2",
        node_id="scientist.node_step_two@1.0.0",
        completed_nodes=["step1", "step2"],
        workflow_id="wf_checkpoint",
        workflow_fingerprint="f" * 64,
        cache_entry_ref=None,
    )

    assert first is not None
    assert second is not None
    assert first.sequence_number == 0
    assert second.sequence_number == 1
    resolved = resolve_latest_checkpoint(store, run_id)
    assert resolved is not None
    assert resolved[0].sequence_number == 1


def test_checkpoint_hook_runtime_metadata_serializes_store_config(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    run_dir = tmp_path / "runs" / "R_checkpoint_config"
    hook = CASCheckpointHook(
        store=store,
        store_config=ArtifactStoreConfig(backend="filesystem", root=str(tmp_path / "cas")),
        run_dir=run_dir,
        checkpoint_policy="strict",
    )

    metadata = serialize_checkpoint_hook_runtime_metadata(hook)
    restored = restore_checkpoint_hook_from_runtime_metadata(metadata)

    assert metadata is not None
    assert metadata["store_config"] == {
        "backend": "filesystem",
        "root": str(tmp_path / "cas"),
        "bucket": None,
        "prefix": "polisyos-cas",
        "region": "us-east-1",
        "local_cache_dir": None,
    }
    assert restored is not None
    restored_metadata = restored.export_runtime_metadata()
    assert restored_metadata is not None
    assert restored_metadata["store_config"] == metadata["store_config"]


def test_restore_checkpoint_hook_from_runtime_metadata_rejects_invalid_store_config() -> None:
    restored = restore_checkpoint_hook_from_runtime_metadata(
        {
            "run_dir": "_build/.tmp/polisyos-invalid-checkpoint",
            "store_config": {"backend": 17},
        }
    )

    assert restored is None


def test_checkpoint_hook_async_path_uses_async_artifact_store_adapter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path)
    hook = CASCheckpointHook(
        store=store,
        run_dir=tmp_path / "runs" / "R_async_hook",
        checkpoint_policy="strict",
    )
    state = ExperimentState(run_id="R_async_hook", params={"phase": "EXECUTE"})
    calls: list[str] = []
    original_put_json = AsyncArtifactStoreAdapter.put_json

    async def _tracked_put_json(self, obj, opts, canon_spec=None):
        calls.append("put_json")
        return await original_put_json(self, obj, opts, canon_spec=canon_spec)

    monkeypatch.setattr(AsyncArtifactStoreAdapter, "put_json", _tracked_put_json)

    result = asyncio.run(
        hook.on_node_complete_async(
            state=state,
            alias="start",
            node_id="scientist.node_noop@1.0.0",
            completed_nodes=["start"],
            workflow_id="wf_checkpoint",
            workflow_fingerprint="f" * 64,
            cache_entry_ref=None,
        )
    )

    assert result is not None
    assert calls == ["put_json"]
    head = load_checkpoint_head(tmp_path / "runs" / "R_async_hook")
    assert head is not None


def test_resume_requires_cache_refs_for_completed_cacheable_nodes(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_resume_missing_cache"
    workflow = _workflow("scientist.node_cached_counter@1.0.0")
    state = ExperimentState(run_id=run_id)
    created = create_checkpoint(
        store,
        run_id=state.run_id,
        state=state.model_dump(mode="python", by_alias=True, exclude_none=False),
        sequence_number=0,
        completed_node_alias="start",
        completed_node_id="scientist.node_cached_counter@1.0.0",
        completed_nodes=["start"],
        workflow_id=workflow.workflow_id,
        workflow_fingerprint=compute_workflow_fingerprint(workflow),
        fsm_phase="EXECUTE",
        cache_entry_refs=[],
    )
    update_checkpoint_head(
        tmp_path / "runs" / run_id,
        run_id=run_id,
        checkpoint_ref=created.checkpoint_ref,
        sequence_number=0,
        node_alias="start",
        writer_pid=123,
        writer_hostname="localhost",
    )

    with pytest.raises(CheckpointCorruptedError, match="cache seed refs"):
        resume_from_checkpoint(store, run_id, workflow=workflow)


def test_incremental_checkpoint_materializes_full_state(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    base_state = ExperimentState(run_id="R_incremental", params={"phase": "PLAN", "step1": 1})
    base = create_checkpoint(
        store,
        run_id=base_state.run_id,
        state=base_state.model_dump(mode="python", by_alias=True, exclude_none=False),
        sequence_number=0,
        completed_node_alias="step1",
        completed_node_id="scientist.node_step_one@1.0.0",
        completed_nodes=["step1"],
        workflow_id="wf_checkpoint",
        workflow_fingerprint="d" * 64,
        fsm_phase="PLAN",
        cache_entry_refs=[],
    )
    next_state = base_state.model_copy(deep=True)
    next_state.params["step2"] = 2
    incremental = create_checkpoint(
        store,
        run_id=next_state.run_id,
        state=next_state.model_dump(mode="python", by_alias=True, exclude_none=False),
        sequence_number=1,
        completed_node_alias="step2",
        completed_node_id="scientist.node_step_two@1.0.0",
        completed_nodes=["step1", "step2"],
        workflow_id="wf_checkpoint",
        workflow_fingerprint="d" * 64,
        fsm_phase="EXECUTE",
        cache_entry_refs=[],
        previous_state=base_state.model_dump(mode="python", by_alias=True, exclude_none=False),
        previous_checkpoint_ref=base.checkpoint_ref,
        previous_chain_depth=base.chain_depth,
    )

    raw_incremental = load_checkpoint(store, incremental.checkpoint_ref)
    assert raw_incremental.metadata.snapshot_mode == "incremental"
    assert raw_incremental.state is None
    assert raw_incremental.base_checkpoint_ref == base.checkpoint_ref
    assert materialize_checkpoint_state(store, incremental.checkpoint_ref)["params"]["step2"] == 2
