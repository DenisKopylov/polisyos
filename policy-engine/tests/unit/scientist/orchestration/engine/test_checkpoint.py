from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

from polisyos.common.async_tools import run_coro_sync
from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
from polisyos.core.artifacts.backends.config import ArtifactStoreConfig
from polisyos.core.artifacts.manifest import CanonInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.scientist.orchestration.engine.checkpoint import (
    CHECKPOINT_KIND,
    CHECKPOINT_SCHEMA_VERSION,
    COMPLETED_NODE_STATUS_CONTRACT,
    CASCheckpointHook,
    CheckpointCorruptedError,
    CheckpointError,
    CheckpointHistory,
    CheckpointHistoryEntry,
    CheckpointMetadataConflictError,
    CheckpointScopeMismatchError,
    CheckpointStatusNotEstablishedError,
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
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

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


@pytest.mark.parametrize("use_async_producer", [False, True])
def test_checkpoint_producers_reject_caller_asserted_scope(
    tmp_path: Path,
    use_async_producer: bool,
) -> None:
    store = FileSystemCAS(tmp_path)
    state = ExperimentState(run_id="R_scope_intake")
    kwargs = {
        "run_id": state.run_id,
        "state": state.model_dump(mode="python", by_alias=True, exclude_none=False),
        "sequence_number": 0,
        "completed_node_alias": "start",
        "completed_node_id": "scientist.node_noop@1.0.0",
        "completed_nodes": ["start"],
        "workflow_id": "wf_checkpoint",
        "workflow_fingerprint": "a" * 64,
        "fsm_phase": "INTAKE",
        "cache_entry_refs": [],
        "tenant_id": "tenant-b",
        "cell_id": "cell-b",
    }

    def _produce() -> None:
        if use_async_producer:
            run_coro_sync(create_checkpoint_async(AsyncArtifactStoreAdapter(store), **kwargs))
        else:
            create_checkpoint(store, **kwargs)

    with (
        tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"),
        pytest.raises(CheckpointScopeMismatchError, match="scope mismatch"),
    ):
        _produce()


def test_checkpoint_producer_captures_active_scope_when_omitted(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    state = ExperimentState(run_id="R_scope_capture")

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
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

    checkpoint = load_checkpoint(store, created.checkpoint_ref)
    assert checkpoint.metadata.tenant_id == "tenant-a"
    assert checkpoint.metadata.cell_id == "cell-a"


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
        "polisyos.scientist.orchestration.engine.checkpoint.gc_checkpoints",
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
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        hook = CASCheckpointHook(
            store=store,
            run_dir=run_dir,
            checkpoint_policy="strict",
        )

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
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

    assert metadata is not None
    assert metadata["tenant_id"] == "tenant-a"
    assert metadata["cell_id"] == "cell-a"
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        restored = restore_checkpoint_hook_from_runtime_metadata(metadata)
    assert restored is not None

    with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-a"):
        with pytest.raises(CheckpointError, match="scope mismatch"):
            restore_checkpoint_hook_from_runtime_metadata(metadata)

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
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
    assert resolved[1].metadata.tenant_id == "tenant-a"
    assert resolved[1].metadata.cell_id == "cell-a"


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
    selected_profile_requests: list[bool] = []
    original_put_json = AsyncArtifactStoreAdapter.put_json

    async def _tracked_put_json(
        self,
        obj,
        opts,
        canon_spec=None,
        *,
        return_selected_profile=False,
    ):
        selected_profile_requests.append(return_selected_profile)
        return await original_put_json(
            self,
            obj,
            opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )

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
    assert selected_profile_requests == [True]
    head = load_checkpoint_head(tmp_path / "runs" / "R_async_hook")
    assert head is not None


def test_resume_allows_valid_state_without_cache_refs(tmp_path: Path) -> None:
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
        completed_node_status_contract=COMPLETED_NODE_STATUS_CONTRACT,
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

    resumed = resume_from_checkpoint(store, run_id, workflow=workflow)

    assert resumed.report.status == "ok"
    assert resumed.report.nodes == []
    assert not (tmp_path / "runs" / run_id / "trace.jsonl").exists()


@pytest.mark.parametrize("async_writer", [False, True], ids=["sync", "async"])
def test_checkpoint_writer_and_resume_preserve_selected_profile(
    tmp_path: Path,
    async_writer: bool,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = f"R_selected_profile_{async_writer}"
    workflow = _workflow("scientist.node_cached_counter@1.0.0")
    state = ExperimentState(run_id=run_id)
    checkpoint_args = {
        "run_id": run_id,
        "state": state.model_dump(mode="python", by_alias=True, exclude_none=False),
        "sequence_number": 0,
        "completed_node_alias": "start",
        "completed_node_id": "scientist.node_cached_counter@1.0.0",
        "completed_nodes": ["start"],
        "completed_node_status_contract": COMPLETED_NODE_STATUS_CONTRACT,
        "workflow_id": workflow.workflow_id,
        "workflow_fingerprint": compute_workflow_fingerprint(workflow),
        "fsm_phase": "EXECUTE",
        "cache_entry_refs": [],
    }

    if async_writer:
        created = run_coro_sync(
            create_checkpoint_async(AsyncArtifactStoreAdapter(store), **checkpoint_args)
        )
    else:
        created = create_checkpoint(store, **checkpoint_args)

    selected_profile = created.checkpoint_ref.manifest_profile_sha256
    assert selected_profile is not None
    run_dir = tmp_path / "runs" / run_id
    bare_legacy_ref = created.checkpoint_ref.model_copy(update={"manifest_profile_sha256": None})
    update_checkpoint_head(
        run_dir,
        run_id=run_id,
        checkpoint_ref=bare_legacy_ref,
        sequence_number=0,
        node_alias="start",
        writer_pid=123,
        writer_hostname="localhost",
    )

    resolved = resolve_latest_checkpoint(store, run_id, run_dir=run_dir)
    assert resolved is not None
    resolved_head, checkpoint = resolved
    assert resolved_head.checkpoint_ref.manifest_profile_sha256 == selected_profile
    assert checkpoint.metadata.run_id == run_id
    assert checkpoint.state is not None
    assert load_checkpoint_head(run_dir).checkpoint_ref.manifest_profile_sha256 is None

    resumed = resume_from_checkpoint(store, run_id, workflow=workflow)
    assert resumed.report.status == "ok"
    assert resumed.report.nodes == []


def test_resume_accepts_legacy_nested_checkpoint_schema_under_current_manifest(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_legacy_checkpoint_payload_schema"
    workflow = _workflow("scientist.node_cached_counter@1.0.0")
    state = ExperimentState(run_id=run_id)
    created = create_checkpoint(
        store,
        run_id=run_id,
        state=state.model_dump(mode="python", by_alias=True, exclude_none=False),
        sequence_number=0,
        completed_node_alias="start",
        completed_node_id="scientist.node_cached_counter@1.0.0",
        completed_nodes=["start"],
        completed_node_status_contract=COMPLETED_NODE_STATUS_CONTRACT,
        workflow_id=workflow.workflow_id,
        workflow_fingerprint=compute_workflow_fingerprint(workflow),
        fsm_phase="EXECUTE",
        cache_entry_refs=[],
    )
    current = load_checkpoint(store, created.checkpoint_ref)
    legacy_payload = current.model_copy(
        update={
            "metadata": current.metadata.model_copy(update={"schema_version": "1.0"}),
        }
    )
    legacy_ref = store.put_json(
        legacy_payload.model_dump(mode="python", by_alias=True, exclude_none=False),
        PutOptions(
            kind=CHECKPOINT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.checkpoint.CheckpointArtifact",
                version=CHECKPOINT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    run_dir = tmp_path / "runs" / run_id
    update_checkpoint_head(
        run_dir,
        run_id=run_id,
        checkpoint_ref=legacy_ref,
        sequence_number=0,
        node_alias="start",
        writer_pid=123,
        writer_hostname="localhost",
    )

    resumed = resume_from_checkpoint(store, run_id, workflow=workflow)

    assert load_checkpoint(store, legacy_ref).metadata.schema_version == "1.0"
    assert resumed.report.status == "ok"
    assert resumed.report.nodes == []


@pytest.mark.parametrize(
    ("wrong_kind", "wrong_media_type", "wrong_schema"),
    [
        (
            "other.checkpoint",
            "application/json",
            SchemaInfo(
                name="polisyos.scientist.checkpoint.CheckpointArtifact",
                version="1.3",
            ),
        ),
        (
            "scientist.checkpoint",
            "application/vnd.other+json",
            SchemaInfo(
                name="polisyos.scientist.checkpoint.CheckpointArtifact",
                version="1.3",
            ),
        ),
        (
            "scientist.checkpoint",
            "application/json",
            SchemaInfo(name="other.CheckpointArtifact", version="1.3"),
        ),
        (
            "scientist.checkpoint",
            "application/json",
            SchemaInfo(
                name="polisyos.scientist.checkpoint.CheckpointArtifact",
                version="9.0",
            ),
        ),
        ("scientist.checkpoint", "application/json", None),
    ],
    ids=["kind", "media-type", "schema-name", "schema-version", "missing-schema"],
)
def test_resume_rejects_same_checkpoint_bytes_with_wrong_owner_before_state_restore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    wrong_kind: str,
    wrong_media_type: str,
    wrong_schema: SchemaInfo | None,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_wrong_checkpoint_owner"
    workflow = _workflow("scientist.node_cached_counter@1.0.0")
    state = ExperimentState(run_id=run_id)
    created = create_checkpoint(
        store,
        run_id=run_id,
        state=state.model_dump(mode="python", by_alias=True, exclude_none=False),
        sequence_number=0,
        completed_node_alias="start",
        completed_node_id="scientist.node_cached_counter@1.0.0",
        completed_nodes=["start"],
        completed_node_status_contract=COMPLETED_NODE_STATUS_CONTRACT,
        workflow_id=workflow.workflow_id,
        workflow_fingerprint=compute_workflow_fingerprint(workflow),
        fsm_phase="EXECUTE",
        cache_entry_refs=[],
    )
    checkpoint_bytes = store.get_bytes(created.checkpoint_ref)
    wrong_ref = store.put_bytes(
        checkpoint_bytes,
        PutOptions(
            kind=wrong_kind,
            media_type=wrong_media_type,
            schema=wrong_schema,
            canon=CanonInfo(forbid_floats=False),
        ),
        return_selected_profile=True,
    )
    assert wrong_ref.artifact_id == created.checkpoint_ref.artifact_id
    assert store.get_bytes(wrong_ref) == checkpoint_bytes
    assert wrong_ref.manifest_profile_sha256 is not None
    update_checkpoint_head(
        tmp_path / "runs" / run_id,
        run_id=run_id,
        checkpoint_ref=wrong_ref,
        sequence_number=0,
        node_alias="start",
        writer_pid=123,
        writer_hostname="localhost",
    )

    state_restore_attempts: list[object] = []
    original_model_validate = ExperimentState.model_validate

    def _track_state_restore(
        cls: type[ExperimentState],
        value: Any,
        **kwargs: Any,
    ) -> ExperimentState:
        state_restore_attempts.append(value)
        return original_model_validate(value, **kwargs)

    monkeypatch.setattr(
        ExperimentState,
        "model_validate",
        classmethod(_track_state_restore),
    )

    with pytest.raises(CheckpointCorruptedError, match="checkpoint artifact payload is invalid"):
        resume_from_checkpoint(store, run_id, workflow=workflow)

    assert state_restore_attempts == []


def test_resume_refuses_status_blind_checkpoint_completed_nodes(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_resume_status_not_established"
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

    with pytest.raises(
        CheckpointStatusNotEstablishedError,
        match="checkpoint_completed_node_status_not_established",
    ):
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


def test_incremental_checkpoint_rejects_cross_tenant_base(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    base_state = ExperimentState(run_id="R_incremental_scope", params={"step": 1})
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
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
            tenant_id="tenant-a",
            cell_id="cell-a",
        )
    next_state = base_state.model_copy(deep=True)
    next_state.params["step"] = 2
    with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-a"):
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
            tenant_id="tenant-b",
            cell_id="cell-a",
            previous_state=base_state.model_dump(mode="python", by_alias=True, exclude_none=False),
            previous_checkpoint_ref=base.checkpoint_ref,
            previous_chain_depth=base.chain_depth,
        )

    with pytest.raises(CheckpointCorruptedError, match="chain scope mismatch"):
        materialize_checkpoint_state(store, incremental.checkpoint_ref)


def test_compute_workflow_fingerprint_accepts_finite_nested_workflow_numbers() -> None:
    workflow = WorkflowSpec(
        workflow_id="wf_nested_numeric_params",
        nodes=[
            NodeInvocation(
                alias="start",
                node_id="scientist.node_noop@1.0.0",
                params={
                    "conditional_transport_request": {
                        "resource_policy": {
                            "limits": {"max_fraction": 0.75},
                            "budget": {"max_elapsed_seconds": 90.25},
                        }
                    }
                },
            )
        ],
    )
    before = workflow.model_dump(mode="python", by_alias=True, exclude_none=False)
    fingerprint = compute_workflow_fingerprint(workflow)

    assert isinstance(  # noqa: S101
        workflow.nodes[0].params["conditional_transport_request"]["resource_policy"]["limits"][
            "max_fraction"
        ],
        float,
    )
    assert len(fingerprint) == 64  # noqa: S101
    assert compute_workflow_fingerprint(workflow.model_copy(deep=True)) == fingerprint  # noqa: S101
    assert workflow.model_dump(mode="python", by_alias=True, exclude_none=False) == before  # noqa: S101

    changed = WorkflowSpec.model_validate(before)
    changed.nodes[0].params["conditional_transport_request"]["resource_policy"]["budget"][
        "max_elapsed_seconds"
    ] = 90.5
    assert compute_workflow_fingerprint(changed) != fingerprint  # noqa: S101


def test_compute_workflow_fingerprint_preserves_existing_float_free_bytes() -> None:
    workflow = WorkflowSpec(
        workflow_id="wf_checkpoint",
        required_binds=["run_id"],
        nodes=[NodeInvocation(alias="start", node_id="scientist.node_noop@1.0.0")],
    )

    assert (  # noqa: S101
        compute_workflow_fingerprint(workflow)
        == "9b03fb7cbd50f192ee7108f7b6e7882ca9dd737112473060191d258a396ccf98"
    )


@pytest.mark.parametrize(
    "bad_value",
    [float("nan"), float("inf"), float("-inf"), object()],
    ids=["nan", "positive-infinity", "negative-infinity", "unsupported-object"],
)
def test_compute_workflow_fingerprint_refuses_nonfinite_or_malformed_nested_values_without_mutation(
    bad_value: object,
) -> None:
    workflow = WorkflowSpec(
        workflow_id="wf_malformed_nested_value",
        nodes=[
            NodeInvocation(
                alias="start",
                node_id="scientist.node_noop@1.0.0",
                params={"resource_budget": {"limit": bad_value}},
            )
        ],
    )
    before = workflow.model_dump(mode="python", by_alias=True, exclude_none=False)

    with pytest.raises(ValueError, match=r"NaN/Inf forbidden|Unsupported type for canonical JSON"):
        compute_workflow_fingerprint(workflow)

    assert workflow.model_dump(mode="python", by_alias=True, exclude_none=False) == before  # noqa: S101
