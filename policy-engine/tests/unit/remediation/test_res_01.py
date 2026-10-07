from __future__ import annotations

import logging
import os
import socket
from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    CheckpointCorruptedError,
    CheckpointStatusNotEstablishedError,
    WorkflowMismatchError,
    compute_workflow_fingerprint,
    create_checkpoint,
    resolve_latest_checkpoint,
    resume_from_checkpoint,
    update_checkpoint_head,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


def _journaled_outcome(run_id: str, marker: str) -> NodeOutcome:
    branched = branch_state(
        ExperimentState(run_id=run_id),
        write_paths=("params.marker",),
    )
    branched.state.params["marker"] = marker
    return NodeOutcome(status="ok", state=branched.state)


def test_cache_seed_deduplicates_exact_refs_and_does_not_mark_failed_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_res_01_seed"
    writer = NodeResultCache(store, run_id=run_id)
    entry_ref = writer.put(
        "a" * 64,
        node_id="scientist.node_res_seed@1.0.0",
        outcome=_journaled_outcome(run_id, "A"),
    )
    missing_ref = entry_ref.model_copy(
        update={"artifact_id": "sha256:" + "f" * 64},
    )

    reads = 0
    original_get_bytes = store.get_bytes

    def counted_get_bytes(artifact_id):
        nonlocal reads
        reads += 1
        return original_get_bytes(artifact_id)

    monkeypatch.setattr(store, "get_bytes", counted_get_bytes)
    restored = NodeResultCache(store, run_id=run_id).seed_from_entry_refs(
        [entry_ref] * 100 + [missing_ref] * 2,
    )

    assert restored == 1
    assert reads == 3

    replay = NodeResultCache(store, run_id=run_id)
    assert replay.seed_from_entry_refs([missing_ref]) == 0
    assert not replay.has("a" * 64)


def test_cache_seed_does_not_mix_different_content_under_same_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_res_01_conflict"
    key = "b" * 64
    first = NodeResultCache(store, run_id=run_id).put(
        key,
        node_id="scientist.node_res_seed@1.0.0",
        outcome=_journaled_outcome(run_id, "first"),
    )
    second = NodeResultCache(store, run_id=run_id).put(
        key,
        node_id="scientist.node_res_seed@1.0.0",
        outcome=_journaled_outcome(run_id, "second"),
    )

    reads: list[str] = []
    original_get_bytes = store.get_bytes

    def counted_get_bytes(artifact_id):
        reads.append(
            str(artifact_id.artifact_id if isinstance(artifact_id, ArtifactRef) else artifact_id)
        )
        return original_get_bytes(artifact_id)

    monkeypatch.setattr(store, "get_bytes", counted_get_bytes)
    replay = NodeResultCache(store, run_id=run_id)
    assert replay.seed_from_entry_refs([first, second]) == 1
    assert str(first.artifact_id) in reads
    assert str(second.artifact_id) in reads
    loaded = replay.get(key)
    assert loaded is not None
    assert loaded.state.params["marker"] == "first"


@pytest.mark.parametrize(
    ("field", "value"),
    [("kind", "scientist.other_cache_entry"), ("media_type", "text/plain")],
)
def test_cache_seed_revalidates_full_ref_identity(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_res_01_ref_identity"
    key = "d" * 64
    cache = NodeResultCache(store, run_id=run_id)
    entry_ref = cache.put(
        key,
        node_id="scientist.node_res_seed@1.0.0",
        outcome=_journaled_outcome(run_id, "identity"),
    )

    replay = NodeResultCache(store, run_id=run_id)
    assert replay.load_entry(entry_ref) is True
    altered_ref = entry_ref.model_copy(update={field: value})
    with pytest.raises(
        ValueError, match="Artifact reference type does not match selected manifest"
    ):
        replay.load_entry(altered_ref)
    assert replay.get(key) is not None


def _meta(raw: str, name: str) -> ComponentMetadata:
    return ComponentMetadata(
        component_id=ComponentId.parse(raw),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name=name,
        description=f"{name} RES-01 test node",
        tags=["test", "res-01"],
        capabilities=Capability.SCIENTIST_NODE,
    )


class _ResumeNode:
    _spec: NodeSpec

    def __init__(self, *, node_id: str, name: str, read_path: str | None = None) -> None:
        self.invocations = 0
        self._spec = NodeSpec(
            metadata=_meta(node_id, name),
            state_reads=[read_path] if read_path is not None else [],
            state_writes=["params." + name.lower()],
        )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def _finish(self, state: ExperimentState) -> NodeOutcome:
        updated = state.model_copy(deep=True)
        updated.params[self._spec.metadata.display_name.lower()] = self.invocations
        return NodeOutcome(status="ok", state=updated)

    def execute(self, _ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.invocations += 1
        return self._finish(state)


class _FailOnceNode(_ResumeNode):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.fail_once = True

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        del ctx
        self.invocations += 1
        if self.fail_once:
            self.fail_once = False
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="res_01.stop", message="intentional RES-01 stop"),
            )
        return self._finish(state)


def _resume_workflow() -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="wf_res_01_resume",
        required_binds=["run_id"],
        error_policy="fail_fast",
        nodes=[
            NodeInvocation(
                alias="a",
                node_id=ComponentId.parse("scientist.node_res_a@1.0.0"),
            ),
            NodeInvocation(
                alias="b",
                node_id=ComponentId.parse("scientist.node_res_b@1.0.0"),
                depends_on=["a"],
            ),
            NodeInvocation(
                alias="c",
                node_id=ComponentId.parse("scientist.node_res_c@1.0.0"),
                depends_on=["b"],
            ),
        ],
    )


def _resume_registry() -> NodeRegistry:
    registry = NodeRegistry()
    registry.register(
        _ResumeNode(
            node_id="scientist.node_res_a@1.0.0",
            name="A",
        )
    )
    registry.register(
        _FailOnceNode(
            node_id="scientist.node_res_b@1.0.0",
            name="B",
            read_path="params.a",
        )
    )
    registry.register(
        _FailOnceNode(
            node_id="scientist.node_res_c@1.0.0",
            name="C",
            read_path="params.b",
        )
    )
    return registry


def _context(store: FileSystemCAS, run_id: str) -> tuple[ExecutionContext, object]:
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id=run_id)
    return ExecutionContext(
        store=store, run=run, logger=logging.getLogger("res_01")
    ), bundle.bundle_ref


def _native_completed_checkpoint(
    store: FileSystemCAS,
    *,
    run_id: str,
    workflow: WorkflowSpec,
    through: str = "b",
    missing_param: str | None = None,
):
    """Produce completion evidence through the actual executor, then inject missing state."""
    producer = _resume_registry()
    if through == "b":
        producer.get(ComponentId.parse("scientist.node_res_b@1.0.0")).fail_once = False
    ctx, bundle_ref = _context(store, run_id)
    hook = CASCheckpointHook(store=store, run_dir=Path(store.root) / "runs" / run_id)
    first = WorkflowExecutor(ctx, producer, checkpoint_hook=hook).execute(
        workflow, ExperimentState(run_id=run_id, inputs={"registry_bundle_ref": bundle_ref})
    )
    assert first.report.status == "fail"
    resolved = resolve_latest_checkpoint(store, run_id)
    assert resolved is not None
    head, checkpoint = resolved
    assert checkpoint.metadata.completed_nodes == (["a", "b"] if through == "b" else ["a"])
    assert checkpoint.metadata.completed_node_status_contract == "native_node_outcome_v1"
    assert checkpoint.state is not None
    if missing_param is not None:
        state = ExperimentState.model_validate(checkpoint.state)
        del state.params[missing_param]
        created = create_checkpoint(
            store,
            run_id=run_id,
            state=state.model_dump(mode="python", by_alias=True, exclude_none=False),
            sequence_number=head.sequence_number + 1,
            completed_node_alias=through,
            completed_node_id=str(workflow.nodes[1 if through == "b" else 0].node_id),
            completed_nodes=list(checkpoint.metadata.completed_nodes),
            completed_node_status_contract=checkpoint.metadata.completed_node_status_contract,
            workflow_id=checkpoint.metadata.workflow_id,
            workflow_fingerprint=checkpoint.metadata.workflow_fingerprint,
            origin_workflow_fingerprint=checkpoint.metadata.origin_workflow_fingerprint,
            fsm_phase="EXECUTE",
            cache_entry_refs=[],
        )
        update_checkpoint_head(
            Path(store.root) / "runs" / run_id,
            run_id=run_id,
            checkpoint_ref=created.checkpoint_ref,
            sequence_number=head.sequence_number + 1,
            node_alias=through,
            writer_pid=os.getpid(),
            writer_hostname=socket.gethostname(),
        )
    return bundle_ref


def test_resume_preserves_origin_fingerprint_across_two_stops(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    workflow = _resume_workflow()
    registry = _resume_registry()
    run_id = "R_res_01_double_resume"
    ctx, bundle_ref = _context(store, run_id)
    state = ExperimentState(run_id=run_id, inputs={"registry_bundle_ref": bundle_ref})
    hook = CASCheckpointHook(store=store, run_dir=tmp_path / "runs" / run_id)

    first = WorkflowExecutor(ctx, registry, checkpoint_hook=hook).execute(workflow, state)
    assert first.report.status == "fail"
    assert [record.alias for record in first.report.nodes] == ["a", "b"]
    first_checkpoint = resolve_latest_checkpoint(store, run_id)
    assert first_checkpoint is not None
    original_fingerprint = compute_workflow_fingerprint(workflow)
    assert first_checkpoint[1].metadata.workflow_fingerprint == original_fingerprint
    assert first_checkpoint[1].metadata.origin_workflow_fingerprint == original_fingerprint

    second = resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=registry,
        registry_bundle_ref=bundle_ref,
    )
    assert second.report.status == "fail"
    assert [record.alias for record in second.report.nodes] == ["b", "c"]
    second_checkpoint = resolve_latest_checkpoint(store, run_id)
    assert second_checkpoint is not None
    assert second_checkpoint[1].metadata.origin_workflow_fingerprint == original_fingerprint

    third = resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=registry,
        registry_bundle_ref=bundle_ref,
    )
    assert third.report.status == "ok"
    assert [record.alias for record in third.report.nodes] == ["c"]
    assert registry.get(ComponentId.parse("scientist.node_res_a@1.0.0")).invocations == 1
    assert registry.get(ComponentId.parse("scientist.node_res_b@1.0.0")).invocations == 2
    assert registry.get(ComponentId.parse("scientist.node_res_c@1.0.0")).invocations == 2


def test_full_valid_state_resumes_without_unnecessary_cache_seed(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    workflow = _resume_workflow()
    registry = _resume_registry()
    registry.get(ComponentId.parse("scientist.node_res_c@1.0.0")).fail_once = False
    run_id = "R_res_01_full_state"
    bundle_ref = _native_completed_checkpoint(store, run_id=run_id, workflow=workflow)
    resumed = resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=registry,
        registry_bundle_ref=bundle_ref,
    )

    assert resumed.report.status == "ok"
    assert [record.alias for record in resumed.report.nodes] == ["c"]


def test_resume_rejects_missing_state_written_by_completed_node(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    workflow = _resume_workflow()
    registry = _resume_registry()
    run_id = "R_res_01_missing_state"
    _native_completed_checkpoint(store, run_id=run_id, workflow=workflow, missing_param="b")

    with pytest.raises(CheckpointCorruptedError, match=r"params\.b"):
        resume_from_checkpoint(
            store,
            run_id,
            workflow=workflow,
            registry=registry,
        )
    assert registry.get(ComponentId.parse("scientist.node_res_c@1.0.0")).invocations == 0


def test_allow_replay_rebuilds_completed_nodes_for_missing_state(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    workflow = _resume_workflow()
    registry = _resume_registry()
    registry.get(ComponentId.parse("scientist.node_res_b@1.0.0")).fail_once = False
    registry.get(ComponentId.parse("scientist.node_res_c@1.0.0")).fail_once = False
    run_id = "R_res_01_allow_replay"
    bundle_ref = _native_completed_checkpoint(
        store, run_id=run_id, workflow=workflow, missing_param="b"
    )
    resumed = resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=registry,
        registry_bundle_ref=bundle_ref,
        resume_strategy="allow_replay",
    )

    assert resumed.report.status == "ok"
    assert [record.alias for record in resumed.report.nodes] == ["a", "b", "c"]


def test_changed_functional_input_remains_incompatible_with_checkpoint(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    workflow = _resume_workflow().model_copy(
        update={
            "nodes": [
                _resume_workflow().nodes[0].model_copy(update={"params": {"mode": "v1"}}),
                *_resume_workflow().nodes[1:],
            ]
        }
    )
    run_id = "R_res_01_changed_input"
    _native_completed_checkpoint(store, run_id=run_id, workflow=workflow, through="a")
    changed = workflow.model_copy(
        update={
            "nodes": [
                workflow.nodes[0].model_copy(update={"params": {"mode": "v2"}}),
                *workflow.nodes[1:],
            ]
        }
    )
    with pytest.raises(WorkflowMismatchError):
        resume_from_checkpoint(store, run_id, workflow=changed, registry=_resume_registry())


def test_duplicate_cache_ref_is_not_independent_coverage(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    writer = NodeResultCache(store, run_id="R_res_01_duplicate")
    entry = writer.put(
        "c" * 64,
        node_id="scientist.node_res_a@1.0.0",
        outcome=_journaled_outcome("R_res_01_duplicate", "A"),
    )
    replay = NodeResultCache(store, run_id="R_res_01_duplicate")
    assert replay.seed_from_entry_refs([entry, entry]) == 1
    assert replay.size == 1
    assert replay.seed_from_entry_refs([]) == 0


def test_constructed_completion_without_native_status_is_refused(tmp_path: Path) -> None:
    """The old state-only frontier cannot assert native completion on behalf of a producer."""
    store = FileSystemCAS(tmp_path)
    workflow = _resume_workflow()
    run_id = "R_res_01_unestablished_completion"
    state = ExperimentState(run_id=run_id, params={"a": 1, "b": 2})
    created = create_checkpoint(
        store,
        run_id=run_id,
        state=state.model_dump(mode="python", by_alias=True, exclude_none=False),
        sequence_number=1,
        completed_node_alias="b",
        completed_node_id="scientist.node_res_b@1.0.0",
        completed_nodes=["a", "b"],
        workflow_id=workflow.workflow_id,
        workflow_fingerprint=compute_workflow_fingerprint(workflow),
        fsm_phase="EXECUTE",
        cache_entry_refs=[],
    )
    update_checkpoint_head(
        tmp_path / "runs" / run_id,
        run_id=run_id,
        checkpoint_ref=created.checkpoint_ref,
        sequence_number=1,
        node_alias="b",
        writer_pid=os.getpid(),
        writer_hostname=socket.gethostname(),
    )
    consumer = _resume_registry()
    with pytest.raises(
        CheckpointStatusNotEstablishedError,
        match="checkpoint_completed_node_status_not_established",
    ):
        resume_from_checkpoint(store, run_id, workflow=workflow, registry=consumer)
    assert all(consumer.get(invocation.node_id).invocations == 0 for invocation in workflow.nodes)
