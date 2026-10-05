from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import pytest

from polisyos.core.artifacts.backends.config import ArtifactStoreConfig
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    _build_resume_workflow_spec,
    resolve_latest_checkpoint,
    restore_checkpoint_hook_from_runtime_metadata,
    serialize_checkpoint_hook_runtime_metadata,
)
from polisyos.scientist.orchestration.engine.idempotency import (
    NodeCacheEntry,
    NodeResultCache,
)
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.runner.distributed_tier import (
    _persist_cache_entries,
    build_distributed_execution_result,
    merge_and_checkpoint_tier,
    project_distributed_node_outcomes,
)
from polisyos.scientist.orchestration.engine.runner.serialization import (
    NativeNodeOutcomeBatch,
    deserialize_state,
    serialize_outcome,
    serialize_state,
)
from polisyos.scientist.orchestration.engine.runner.state_merge import (
    TierOutcomeAdmissionError,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state,
    mutation_journal_for_state,
)
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
        result_bytes_by_alias={
            "policy": serialize_outcome(NodeOutcome(status="ok", state=result_state))
        },
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
    cached_entry = NodeCacheEntry.model_validate(
        from_canonical_bytes(store.get_bytes(result.cache_entry_refs["policy"].artifact_id))
    )
    assert cached_entry.outcome_payload is not None
    assert cached_entry.outcome_payload["status"] == "ok"

    resolved = resolve_latest_checkpoint(store, run_id)
    assert resolved is not None
    _, checkpoint = resolved
    assert checkpoint.metadata.completed_nodes == ["policy"]
    assert checkpoint.metadata.completed_node_status_contract == "native_node_outcome_v1"
    assert len(checkpoint.metadata.cache_entry_refs) == 1


class TierStatusNode:
    def __init__(self, alias: str) -> None:
        self._spec = NodeSpec(
            metadata=_meta(f"scientist.node_tier_{alias}@1.0.0", f"Tier {alias}"),
            state_writes=[f"params.{alias}"],
        )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx, state) -> NodeOutcome:
        del ctx
        return NodeOutcome(status="ok", state=state)


class _TierCheckpointRecorder:
    def __init__(self, delegate: CASCheckpointHook | None = None) -> None:
        self._delegate = delegate
        self.tier_calls: list[dict[str, object]] = []
        self.node_calls: list[dict[str, object]] = []

    def on_tier_complete(self, **kwargs):
        self.tier_calls.append(kwargs)
        if self._delegate is not None:
            return self._delegate.on_tier_complete(**kwargs)
        return None

    def on_node_complete(self, **kwargs):
        self.node_calls.append(kwargs)
        return None


def test_distributed_tier_preserves_status_and_publishes_one_successful_frontier(
    tmp_path: Path,
) -> None:
    run_id = "R_distributed_tier_status"
    store = FileSystemCAS(tmp_path)
    registry = NodeRegistry()
    for alias in ("ok", "skip", "fail"):
        registry.register(TierStatusNode(alias))
    workflow = WorkflowSpec(
        workflow_id="wf_distributed_tier_status",
        required_binds=["run_id"],
        error_policy="continue",
        nodes=[
            NodeInvocation(
                alias=alias,
                node_id=ComponentId.parse(f"scientist.node_tier_{alias}@1.0.0"),
            )
            for alias in ("ok", "skip", "fail")
        ],
    )
    base_state = ExperimentState(run_id=run_id)
    cache = NodeResultCache(store, run_id=base_state.run_id)
    ok_state = base_state.model_copy(deep=True)
    ok_state.params["ok"] = True
    skipped_state = base_state.model_copy(deep=True)
    skipped_state.params["skip"] = True
    failed_state = base_state.model_copy(deep=True)
    failed_state.params["fail"] = True
    checkpoint_hook = CASCheckpointHook(
        store=store,
        run_dir=tmp_path / "runs" / run_id,
        checkpoint_policy="strict",
    )
    recorder = _TierCheckpointRecorder(checkpoint_hook)

    result = merge_and_checkpoint_tier(
        workflow=workflow,
        tier_aliases=["ok", "skip", "fail"],
        invocations={inv.alias: inv for inv in workflow.nodes},
        result_bytes_by_alias={
            "ok": serialize_outcome(NodeOutcome(status="ok", state=ok_state)),
            "skip": serialize_outcome(NodeOutcome(status="skip", state=skipped_state)),
            "fail": serialize_outcome(
                NodeOutcome(
                    status="fail",
                    state=failed_state,
                    error=NodeError(code="node.test_failure", message="expected test failure"),
                )
            ),
        },
        base_state_bytes=serialize_state(base_state),
        registry=registry,
        checkpoint_hook=recorder,
        cache=cache,
        completed_nodes=[],
        workflow_fingerprint="b" * 64,
        conflict_policy=MergeConflictPolicy.ERROR,
        logger=logging.getLogger("test.distributed_tier.status"),
    )

    merged = deserialize_state(result.state_bytes)
    assert merged.params == {"ok": True}
    assert result.completed_nodes == ["ok"]
    assert set(result.cache_entry_refs) == {"ok"}
    cached_entry = NodeCacheEntry.model_validate(
        from_canonical_bytes(store.get_bytes(result.cache_entry_refs["ok"].artifact_id))
    )
    assert cached_entry.outcome_payload is not None
    assert cached_entry.outcome_payload["status"] == "ok"
    assert {alias: outcome.status for alias, outcome in result.node_outcomes.items()} == {
        "ok": "ok",
        "skip": "skip",
        "fail": "fail",
    }
    assert len(recorder.tier_calls) == 1
    assert recorder.node_calls == []
    assert recorder.tier_calls[0]["alias"] == "ok"
    assert recorder.tier_calls[0]["completed_nodes"] == ["ok"]
    checkpoint_state = recorder.tier_calls[0]["state"]
    assert checkpoint_state.params == {"ok": True}
    resolved = resolve_latest_checkpoint(store, run_id)
    assert resolved is not None
    _, checkpoint = resolved
    assert checkpoint.metadata.completed_nodes == ["ok"]
    assert checkpoint.metadata.completed_node_status_contract == "native_node_outcome_v1"
    assert checkpoint.state["params"] == {"ok": True}
    resumed_workflow = _build_resume_workflow_spec(
        workflow,
        completed_nodes=checkpoint.metadata.completed_nodes,
    )
    assert {invocation.alias for invocation in resumed_workflow.nodes} == {"skip", "fail"}


def test_distributed_fail_fast_rolls_back_before_checkpoint_or_cache() -> None:
    registry = NodeRegistry()
    for alias in ("ok", "fail"):
        registry.register(TierStatusNode(alias))
    workflow = WorkflowSpec(
        workflow_id="wf_distributed_tier_fail_fast",
        required_binds=["run_id"],
        error_policy="fail_fast",
        nodes=[
            NodeInvocation(
                alias=alias,
                node_id=ComponentId.parse(f"scientist.node_tier_{alias}@1.0.0"),
            )
            for alias in ("ok", "fail")
        ],
    )
    base_state = ExperimentState(run_id="R_distributed_tier_fail_fast")
    ok_state = base_state.model_copy(deep=True)
    ok_state.params["ok"] = True
    fail_state = base_state.model_copy(deep=True)
    fail_state.params["fail"] = True
    recorder = _TierCheckpointRecorder()

    result = merge_and_checkpoint_tier(
        workflow=workflow,
        tier_aliases=["ok", "fail"],
        invocations={inv.alias: inv for inv in workflow.nodes},
        result_bytes_by_alias={
            "ok": serialize_outcome(NodeOutcome(status="ok", state=ok_state)),
            "fail": serialize_outcome(
                NodeOutcome(
                    status="fail",
                    state=fail_state,
                    error=NodeError(code="node.test_failure", message="expected test failure"),
                )
            ),
        },
        base_state_bytes=serialize_state(base_state),
        registry=registry,
        checkpoint_hook=recorder,
        cache=None,
        completed_nodes=["before"],
        workflow_fingerprint="c" * 64,
        conflict_policy=MergeConflictPolicy.ERROR,
        logger=logging.getLogger("test.distributed_tier.fail_fast"),
    )

    assert deserialize_state(result.state_bytes) == base_state
    assert result.completed_nodes == ["before"]
    assert result.should_abort is True
    assert {alias: outcome.status for alias, outcome in result.node_outcomes.items()} == {
        "ok": "ok",
        "fail": "fail",
    }
    assert recorder.tier_calls == []
    assert recorder.node_calls == []


def test_status_blind_state_frontier_keeps_state_but_cannot_publish_cache_or_status(
    tmp_path: Path,
) -> None:
    run_id = "R_distributed_tier_status_blind"
    store = FileSystemCAS(tmp_path)
    hook = CASCheckpointHook(
        store=store,
        run_dir=tmp_path / "runs" / run_id,
        checkpoint_policy="strict",
    )
    cache = NodeResultCache(store, run_id=run_id)
    registry = NodeRegistry()
    registry.register(TierStatusNode("legacy"))
    workflow = WorkflowSpec(
        workflow_id="wf_distributed_tier_status_blind",
        required_binds=["run_id"],
        error_policy="continue",
        nodes=[
            NodeInvocation(
                alias="legacy",
                node_id=ComponentId.parse("scientist.node_tier_legacy@1.0.0"),
            )
        ],
    )
    base_state = ExperimentState(run_id=run_id)
    worker_state = branch_state(base_state, write_paths=["params.legacy"]).state
    worker_state.params["legacy"] = True
    journal = mutation_journal_for_state(worker_state)
    assert journal is not None and journal.operations
    wire_worker_state = ExperimentState.model_validate(
        worker_state.model_dump(mode="python", by_alias=True, exclude_none=False)
    )
    assert type(wire_worker_state) is ExperimentState

    result = merge_and_checkpoint_tier(
        workflow=workflow,
        tier_aliases=["legacy"],
        invocations={inv.alias: inv for inv in workflow.nodes},
        result_bytes_by_alias={"legacy": serialize_state(wire_worker_state)},
        base_state_bytes=serialize_state(base_state),
        registry=registry,
        checkpoint_hook=hook,
        cache=cache,
        completed_nodes=[],
        workflow_fingerprint="d" * 64,
        conflict_policy=MergeConflictPolicy.ERROR,
        logger=logging.getLogger("test.distributed_tier.status_blind"),
        result_format="state",
    )

    assert deserialize_state(result.state_bytes).params == {"legacy": True}
    assert result.completed_nodes == ["legacy"]
    assert result.node_outcomes == {}
    assert result.cache_entry_refs == {}
    assert cache.size == 0
    resolved = resolve_latest_checkpoint(store, run_id)
    assert resolved is not None
    _, checkpoint = resolved
    assert checkpoint.metadata.completed_nodes == ["legacy"]
    assert checkpoint.metadata.completed_node_status_contract is None
    assert checkpoint.metadata.cache_entry_refs == []


def test_empty_status_blind_checkpoint_establishes_contract_after_native_success(
    tmp_path: Path,
) -> None:
    run_id = "R_distributed_tier_empty_status_blind"
    store = FileSystemCAS(tmp_path / "cas")
    store_config = ArtifactStoreConfig(
        backend="filesystem", root=str(tmp_path / "cas")
    )
    initial_hook = CASCheckpointHook(
        store=store,
        run_dir=tmp_path / "runs" / run_id,
        store_config=store_config,
        checkpoint_policy="strict",
        initial_status_contract_established=False,
    )
    metadata = serialize_checkpoint_hook_runtime_metadata(initial_hook)
    assert metadata is not None
    assert metadata["completed_nodes"] == []
    assert metadata["completed_node_status_contract"] is None
    hook = restore_checkpoint_hook_from_runtime_metadata(metadata)
    assert hook is not None

    registry = NodeRegistry()
    registry.register(TierStatusNode("native"))
    workflow = WorkflowSpec(
        workflow_id="wf_distributed_tier_empty_status_blind",
        required_binds=["run_id"],
        error_policy="continue",
        nodes=[
            NodeInvocation(
                alias="native",
                node_id=ComponentId.parse("scientist.node_tier_native@1.0.0"),
            )
        ],
    )
    base_state = ExperimentState(run_id=run_id)
    native_state = base_state.model_copy(deep=True)
    native_state.params["native"] = True

    result = merge_and_checkpoint_tier(
        workflow=workflow,
        tier_aliases=["native"],
        invocations={inv.alias: inv for inv in workflow.nodes},
        result_bytes_by_alias={
            "native": serialize_outcome(NodeOutcome(status="ok", state=native_state))
        },
        base_state_bytes=serialize_state(base_state),
        registry=registry,
        checkpoint_hook=hook,
        cache=None,
        completed_nodes=[],
        workflow_fingerprint="f" * 64,
        conflict_policy=MergeConflictPolicy.ERROR,
        logger=logging.getLogger("test.distributed_tier.empty_status_blind"),
    )

    assert deserialize_state(result.state_bytes).params == {"native": True}
    resolved = resolve_latest_checkpoint(
        store, run_id, run_dir=tmp_path / "runs" / run_id
    )
    assert resolved is not None
    _, checkpoint = resolved
    assert checkpoint.metadata.completed_nodes == ["native"]
    assert checkpoint.metadata.completed_node_status_contract == "native_node_outcome_v1"


def test_skip_with_mutation_proof_is_not_admitted_as_successful_cache_or_frontier(
    tmp_path: Path,
) -> None:
    run_id = "R_distributed_tier_skip_mutation"
    store = FileSystemCAS(tmp_path)
    cache = NodeResultCache(store, run_id=run_id)
    registry = NodeRegistry()
    registry.register(TierStatusNode("skip"))
    workflow = WorkflowSpec(
        workflow_id="wf_distributed_tier_skip_mutation",
        required_binds=["run_id"],
        error_policy="continue",
        nodes=[
            NodeInvocation(
                alias="skip",
                node_id=ComponentId.parse("scientist.node_tier_skip@1.0.0"),
            )
        ],
    )
    base_state = ExperimentState(run_id=run_id)
    skipped_state = branch_state(base_state, write_paths=["params.skip"]).state
    skipped_state.params["skip"] = True
    journal = mutation_journal_for_state(skipped_state)
    assert journal is not None and journal.operations
    invocation = workflow.nodes[0]
    skip_outcome = NodeOutcome(status="skip", state=skipped_state)
    cache_refs = _persist_cache_entries(
        tier_aliases=["skip"],
        invocations={"skip": invocation},
        registry=registry,
        node_outcomes={"skip": skip_outcome},
        status_evidence=NativeNodeOutcomeBatch(outcomes={"skip": skip_outcome}),
        base_state=base_state,
        cache=cache,
        logger=logging.getLogger("test.distributed_tier.skip_mutation_cache"),
    )
    assert cache_refs == {}
    assert cache.size == 0

    wire_skipped_state = ExperimentState.model_validate(
        skipped_state.model_dump(mode="python", by_alias=True, exclude_none=False)
    )
    assert type(wire_skipped_state) is ExperimentState

    result = merge_and_checkpoint_tier(
        workflow=workflow,
        tier_aliases=["skip"],
        invocations={inv.alias: inv for inv in workflow.nodes},
        result_bytes_by_alias={
            "skip": serialize_outcome(NodeOutcome(status="skip", state=wire_skipped_state))
        },
        base_state_bytes=serialize_state(base_state),
        registry=registry,
        checkpoint_hook=None,
        cache=cache,
        completed_nodes=[],
        workflow_fingerprint="e" * 64,
        conflict_policy=MergeConflictPolicy.ERROR,
        logger=logging.getLogger("test.distributed_tier.skip_mutation"),
    )

    assert deserialize_state(result.state_bytes) == base_state
    assert result.completed_nodes == []
    assert result.cache_entry_refs == {}
    assert cache.size == 0
    assert result.node_outcomes["skip"].status == "skip"


def test_distributed_report_retains_native_fail_and_success_statuses() -> None:
    registry = NodeRegistry()
    for alias in ("ok", "fail"):
        registry.register(TierStatusNode(alias))
    workflow = WorkflowSpec(
        workflow_id="wf_distributed_status_report",
        required_binds=["run_id"],
        error_policy="continue",
        nodes=[
            NodeInvocation(
                alias=alias,
                node_id=ComponentId.parse(f"scientist.node_tier_{alias}@1.0.0"),
            )
            for alias in ("ok", "fail")
        ],
    )
    base_state = ExperimentState(run_id="R_distributed_status_report")
    base_state.params["large_payload"] = "x" * 50_000
    failed_state = base_state.model_copy(deep=True)
    failed_state.params["fail"] = True
    ok_state = base_state.model_copy(deep=True)
    ok_state.params["ok"] = True

    outcome_bytes_by_alias = {
        "ok": serialize_outcome(NodeOutcome(status="ok", state=ok_state)),
        "fail": serialize_outcome(
            NodeOutcome(
                status="fail",
                state=failed_state,
                error=NodeError(code="node.test_failure", message="expected"),
            )
        ),
    }
    node_reports_by_alias = project_distributed_node_outcomes(
        workflow=workflow,
        tier_aliases=["ok", "fail"],
        outcome_bytes_by_alias=outcome_bytes_by_alias,
    )
    compact_report_bytes = json.dumps(node_reports_by_alias, sort_keys=True).encode()
    assert len(outcome_bytes_by_alias["ok"]) > 50_000
    assert len(compact_report_bytes) < 2_048
    assert "large_payload" not in compact_report_bytes.decode()

    result = build_distributed_execution_result(
        workflow=workflow,
        run_id=base_state.run_id,
        state_bytes=serialize_state(base_state),
        node_reports_by_alias=node_reports_by_alias,
    )

    assert result.report.status == "fail"
    assert {node.alias: node.status for node in result.report.nodes} == {
        "ok": "ok",
        "fail": "fail",
    }


def test_outcome_for_later_workflow_alias_is_refused_before_merge_or_checkpoint(
    tmp_path: Path,
) -> None:
    run_id = "R_distributed_tier_unrequested_alias"
    store = FileSystemCAS(tmp_path)
    hook = CASCheckpointHook(
        store=store,
        run_dir=tmp_path / "runs" / run_id,
        checkpoint_policy="strict",
    )
    cache = NodeResultCache(store, run_id=run_id)
    registry = NodeRegistry()
    registry.register(TierStatusNode("current"))
    registry.register(TierStatusNode("later"))
    workflow = WorkflowSpec(
        workflow_id="wf_distributed_tier_unrequested_alias",
        required_binds=["run_id"],
        error_policy="continue",
        nodes=[
            NodeInvocation(
                alias="current",
                node_id=ComponentId.parse("scientist.node_tier_current@1.0.0"),
            ),
            NodeInvocation(
                alias="later",
                node_id=ComponentId.parse("scientist.node_tier_later@1.0.0"),
                depends_on=["current"],
            ),
        ],
    )
    base_state = ExperimentState(run_id=run_id)
    current_state = base_state.model_copy(deep=True)
    current_state.params["current"] = True
    later_state = base_state.model_copy(deep=True)
    later_state.params["later"] = True
    result_bytes = {
        "current": serialize_outcome(NodeOutcome(status="ok", state=current_state)),
        "later": serialize_outcome(NodeOutcome(status="ok", state=later_state)),
    }

    with pytest.raises(
        TierOutcomeAdmissionError,
        match="distributed_tier_result_alias_outside_requested_tier",
    ) as captured:
        merge_and_checkpoint_tier(
            workflow=workflow,
            tier_aliases=["current"],
            invocations={inv.alias: inv for inv in workflow.nodes},
            result_bytes_by_alias=result_bytes,
            base_state_bytes=serialize_state(base_state),
            registry=registry,
            checkpoint_hook=hook,
            cache=cache,
            completed_nodes=[],
            workflow_fingerprint="a" * 64,
            conflict_policy=MergeConflictPolicy.ERROR,
            logger=logging.getLogger("test.distributed_tier.unrequested_alias"),
        )

    assert captured.value.unexpected_aliases == ("later",)
    assert base_state.params == {}
    assert cache.size == 0
    assert resolve_latest_checkpoint(store, run_id) is None

    with pytest.raises(TierOutcomeAdmissionError):
        project_distributed_node_outcomes(
            workflow=workflow,
            tier_aliases=["current"],
            outcome_bytes_by_alias=result_bytes,
        )
