from __future__ import annotations

import logging
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    ArtifactIntegrityError,
    ArtifactRef,
    ProducerInfo,
    PutOptions,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    CheckpointCorruptedError,
    CheckpointWriteResult,
    WorkflowMismatchError,
    compute_workflow_fingerprint,
    resolve_latest_checkpoint,
    resume_from_checkpoint,
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

    def counted_get_bytes(artifact_ref: ArtifactRef):
        nonlocal reads
        reads += 1
        return original_get_bytes(artifact_ref)

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

    reads: list[ArtifactRef] = []
    original_get_bytes = store.get_bytes

    def counted_get_bytes(artifact_ref: ArtifactRef):
        reads.append(artifact_ref)
        return original_get_bytes(artifact_ref)

    monkeypatch.setattr(store, "get_bytes", counted_get_bytes)
    replay = NodeResultCache(store, run_id=run_id)
    assert replay.seed_from_entry_refs([first, second]) == 1
    assert reads == [first, second]
    loaded = replay.get(key)
    assert loaded is not None
    assert loaded.state.params["marker"] == "first"


@pytest.mark.parametrize(
    "mismatch_field",
    ["artifact_id", "kind", "media_type", "manifest_profile_sha256"],
)
def test_cache_load_rejects_altered_ref_identity_without_admission_or_eviction(
    tmp_path: Path,
    mismatch_field: str,
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

    if mismatch_field == "manifest_profile_sha256":
        entry_bytes = store.get_bytes(entry_ref)
        entry_manifest = store.get_manifest(entry_ref)
        foreign_producer = ProducerInfo(
            component="tests.res_01.foreign_cache_epoch",
            version="1.0.0",
        )
        altered_ref = store.put_bytes(
            entry_bytes,
            PutOptions(
                kind=entry_ref.kind,
                media_type=entry_ref.media_type,
                schema=entry_manifest.artifact_schema,
                producer=foreign_producer,
            ),
            return_selected_profile=True,
        )
        assert altered_ref.artifact_id == entry_ref.artifact_id
        assert altered_ref.kind == entry_ref.kind
        assert altered_ref.media_type == entry_ref.media_type
        assert altered_ref.manifest_profile_sha256 is not None
        assert altered_ref.manifest_profile_sha256 != entry_ref.manifest_profile_sha256
        assert store.get_bytes(altered_ref) == entry_bytes
        assert store.get_manifest(altered_ref).producer == foreign_producer
    elif mismatch_field == "artifact_id":
        altered_ref = entry_ref.model_copy(
            update={"artifact_id": "sha256:" + "f" * 64},
        )
    else:
        altered_ref = entry_ref.model_copy(
            update={
                "kind": "scientist.other_cache_entry"
                if mismatch_field == "kind"
                else entry_ref.kind,
                "media_type": "text/plain"
                if mismatch_field == "media_type"
                else entry_ref.media_type,
            }
        )
    assert altered_ref != entry_ref

    fresh = NodeResultCache(store, run_id=run_id)
    if mismatch_field == "artifact_id":
        with pytest.raises(FileNotFoundError):
            fresh.load_entry(altered_ref)
    elif mismatch_field == "manifest_profile_sha256":
        with pytest.raises(ValueError, match="cache_custody: immutable_epoch_mismatch"):
            fresh.load_entry(altered_ref)
    else:
        with pytest.raises(
            ArtifactIntegrityError,
            match="Artifact reference type does not match selected manifest",
        ):
            fresh.load_entry(altered_ref)
    assert fresh.size == 0
    assert not fresh.has(key)
    assert fresh.get(key) is None

    replay = NodeResultCache(store, run_id=run_id)
    assert replay.load_entry(entry_ref) is True
    if mismatch_field == "artifact_id":
        with pytest.raises(FileNotFoundError):
            replay.load_entry(altered_ref)
    elif mismatch_field == "manifest_profile_sha256":
        with pytest.raises(ValueError, match="cache_custody: immutable_epoch_mismatch"):
            replay.load_entry(altered_ref)
    else:
        with pytest.raises(
            ArtifactIntegrityError,
            match="Artifact reference type does not match selected manifest",
        ):
            replay.load_entry(altered_ref)
    preserved = replay.get(key)
    assert preserved is not None
    assert preserved.state.params["marker"] == "identity"

    reopened = NodeResultCache(store, run_id=run_id)
    assert reopened.load_entry(entry_ref) is True
    reloaded = reopened.get(key)
    assert reloaded is not None
    assert reloaded.state.params["marker"] == "identity"


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
    return ExecutionContext(store=store, run=run, logger=logging.getLogger("res_01")), bundle.bundle_ref


def _write_known_successful_frontier_checkpoint(
    store: FileSystemCAS,
    *,
    run_dir: Path,
    state: ExperimentState,
    completed_node_alias: str,
    completed_node_id: str,
    completed_nodes: list[str],
    workflow: WorkflowSpec,
) -> CheckpointWriteResult:
    """Persist a successful test frontier through the canonical checkpoint hook."""
    hook = CASCheckpointHook(store=store, run_dir=run_dir)
    # These fixtures represent prior nodes whose native outcomes were successful.
    hook.mark_completed_node_status_established(prior_completed_nodes=[])
    result = hook.on_node_complete(
        state=state,
        alias=completed_node_alias,
        node_id=completed_node_id,
        completed_nodes=completed_nodes,
        workflow_id=workflow.workflow_id,
        workflow_fingerprint=compute_workflow_fingerprint(workflow),
        cache_entry_ref=None,
    )
    assert result is not None
    return result


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
    state = ExperimentState(
        run_id=run_id,
        params={"a": 1, "b": 2},
    )
    _write_known_successful_frontier_checkpoint(
        store,
        run_dir=tmp_path / "runs" / run_id,
        state=state,
        completed_node_alias="b",
        completed_node_id="scientist.node_res_b@1.0.0",
        completed_nodes=["a", "b"],
        workflow=workflow,
    )

    ctx, bundle_ref = _context(store, run_id)
    del ctx
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
    state = ExperimentState(run_id=run_id, params={"a": 1})
    _write_known_successful_frontier_checkpoint(
        store,
        run_dir=tmp_path / "runs" / run_id,
        state=state,
        completed_node_alias="b",
        completed_node_id="scientist.node_res_b@1.0.0",
        completed_nodes=["a", "b"],
        workflow=workflow,
    )

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
    state = ExperimentState(run_id=run_id, params={"a": 1})
    _write_known_successful_frontier_checkpoint(
        store,
        run_dir=tmp_path / "runs" / run_id,
        state=state,
        completed_node_alias="b",
        completed_node_id="scientist.node_res_b@1.0.0",
        completed_nodes=["a", "b"],
        workflow=workflow,
    )

    ctx, bundle_ref = _context(store, run_id)
    del ctx
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
    state = ExperimentState(run_id=run_id)
    _write_known_successful_frontier_checkpoint(
        store,
        run_dir=tmp_path / "runs" / run_id,
        state=state,
        completed_node_alias="a",
        completed_node_id="scientist.node_res_a@1.0.0",
        completed_nodes=["a"],
        workflow=workflow,
    )
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
