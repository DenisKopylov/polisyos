from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.checkpoint import CASCheckpointHook, resolve_latest_checkpoint
from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.runner.distributed_tier import merge_and_checkpoint_tier
from polisyos.scientist.orchestration.engine.runner.serialization import deserialize_state, serialize_state
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_merge import MergeConflictPolicy
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


def _meta(raw: str, name: str) -> ComponentMetadata:
    return ComponentMetadata(
        component_id=ComponentId.parse(raw),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name=name,
        description=f"{name} test node",
        tags=["test"],
        capabilities=Capability.SCIENTIST_NODE,
    )


def _artifact_ref(name: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + hashlib.sha256(name.encode()).hexdigest(),
        kind="test",
        media_type="application/json",
    )


class PolicyOutputNode:
    _spec = NodeSpec(
        metadata=_meta("scientist.node_policy_output@1.0.0", "PolicyOutput"),
        state_reads=[],
        state_writes=["policy_output_bundle_ref"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx, state) -> NodeOutcome:
        return NodeOutcome(status="ok", state=state)


def test_merge_and_checkpoint_tier_persists_cache_entry_and_non_default_write(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_distributed_tier"
    run_dir = tmp_path / "runs" / run_id
    hook = CASCheckpointHook(store=store, run_dir=run_dir, checkpoint_policy="strict")
    cache = NodeResultCache(store, run_id=run_id)

    registry = NodeRegistry()
    registry.register(PolicyOutputNode())

    workflow = WorkflowSpec(
        workflow_id="wf_distributed_tier",
        required_binds=["run_id"],
        error_policy="fail_fast",
        nodes=[
            NodeInvocation(
                alias="policy",
                node_id=ComponentId.parse("scientist.node_policy_output@1.0.0"),
            )
        ],
    )
    invocations = {inv.alias: inv for inv in workflow.nodes}

    base_state = ExperimentState(run_id=run_id)
    result_state = base_state.model_copy(deep=True)
    result_state.policy_output_bundle_ref = _artifact_ref("policy-output")

    result = merge_and_checkpoint_tier(
        workflow=workflow,
        tier_aliases=["policy"],
        invocations=invocations,
        result_bytes_by_alias={"policy": serialize_state(result_state)},
        base_state_bytes=serialize_state(base_state),
        registry=registry,
        checkpoint_hook=hook,
        cache=cache,
        completed_nodes=[],
        workflow_fingerprint="a" * 64,
        conflict_policy=MergeConflictPolicy.ERROR,
        logger=logging.getLogger("test.distributed_tier"),
    )

    merged = deserialize_state(result.state_bytes)
    assert merged.policy_output_bundle_ref == result_state.policy_output_bundle_ref
    assert merged.last_checkpoint_ref is not None
    assert result.completed_nodes == ["policy"]
    assert "policy" in result.cache_entry_refs
    assert result.cache_entry_refs["policy"].kind == "scientist.node_cache_entry"

    resolved = resolve_latest_checkpoint(store, run_id)
    assert resolved is not None
    _, checkpoint = resolved
    assert checkpoint.metadata.completed_nodes == ["policy"]
    assert len(checkpoint.metadata.cache_entry_refs) == 1
