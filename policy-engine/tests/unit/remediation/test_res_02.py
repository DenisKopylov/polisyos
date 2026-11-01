"""Regression witnesses for RES-02 tier frontier and checkpoint semantics."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.nodes.builtins.causal.resolve_parameters import ResolveParametersNode
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    CheckpointError,
    CheckpointWriteResult,
    resolve_latest_checkpoint,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


def _ref(
    tag: str, *, kind: str = "scientist.node_cache_entry", selected: bool = False
) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{hashlib.sha256(tag.encode('utf-8')).hexdigest()}",
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=(
            f"sha256:{hashlib.sha256((tag + '-profile').encode('utf-8')).hexdigest()}"
            if selected
            else None
        ),
    )


def _context(*, audit: Any | None = None) -> ExecutionContext:
    store = MagicMock()
    run = MagicMock()
    run.trace_path = None
    run.finalize.return_value = _ref("f", kind="scientist.run")
    return ExecutionContext(store=store, run=run, logger=MagicMock(), audit=audit)


def _node(*, node_id: str, write_path: str) -> MagicMock:
    node = MagicMock()
    node.spec.state_writes = [write_path]
    node.spec.state_reads = []
    node.spec.node_id = node_id
    return node


class _RecordingCheckpointHook:
    def __init__(self) -> None:
        self.node_calls: list[dict[str, Any]] = []
        self.tier_calls: list[dict[str, Any]] = []

    async def on_node_complete_async(self, **kwargs: Any) -> None:
        self.node_calls.append(kwargs)

    async def on_tier_complete_async(self, **kwargs: Any) -> None:
        self.tier_calls.append(kwargs)


class _AsyncOnlyLegacyCheckpointHook:
    def __init__(self) -> None:
        self.node_calls: list[dict[str, Any]] = []
        self._sequence = 0

    async def on_node_complete_async(self, **kwargs: Any) -> CheckpointWriteResult:
        self.node_calls.append(kwargs)
        result = CheckpointWriteResult(
            checkpoint_ref=_ref(str(9 + self._sequence), kind="scientist.checkpoint"),
            sequence_number=self._sequence,
            duration_ms=1,
            snapshot_mode="full",
        )
        self._sequence += 1
        return result


class _RecordingAudit:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def append(self, **kwargs: Any) -> None:
        self.entries.append(kwargs)


def _executor(
    workflow: WorkflowSpec,
    outcomes: dict[str, NodeOutcome],
    cache_refs: dict[str, ArtifactRef | None],
    hook: Any,
    *,
    audit: Any | None = None,
) -> AsyncWorkflowExecutor:
    ctx = _context(audit=audit)
    registry = MagicMock(spec=NodeRegistry)

    def _get_node(node_id: object) -> MagicMock:
        label = str(node_id).split("@", 1)[0].rsplit(".", 1)[-1]
        return _node(node_id=str(node_id), write_path=f"params.{label.removeprefix('node_')}")

    registry.get.side_effect = _get_node
    executor = AsyncWorkflowExecutor(ctx, registry, checkpoint_hook=hook, max_parallelism=2)

    async def _persist_workflow_spec(
        workflow_spec: WorkflowSpec, *, return_selected_profile: bool = False
    ) -> ArtifactRef:
        return _ref("a", kind="scientist.workflow_spec", selected=return_selected_profile)

    async def _persist_state(
        state: ExperimentState, *, return_selected_profile: bool = False
    ) -> ArtifactRef:
        return _ref("b", kind="scientist.experiment_state", selected=return_selected_profile)

    async def _persist_report(report: Any) -> ArtifactRef:
        return _ref("c", kind="scientist.workflow_report", selected=True)

    async def _put_workflow_artifact(
        obj: object, opts: Any, *, canon_spec: Any = None, return_selected_profile: bool = False
    ) -> ArtifactRef:
        return _ref("finalization", kind=opts.kind, selected=return_selected_profile)

    async def _execute_node(
        alias: str,
        inv: NodeInvocation,
        state: ExperimentState,
        workflow_spec: WorkflowSpec,
        *,
        tier_index: int = 0,
    ) -> tuple[NodeOutcome, int, bool, ArtifactRef | None]:
        del inv, workflow_spec, tier_index
        return outcomes[alias], 1, False, cache_refs.get(alias)

    executor._persist_workflow_spec = _persist_workflow_spec  # type: ignore[method-assign]
    executor._persist_state = _persist_state  # type: ignore[method-assign]
    executor._persist_report = _persist_report  # type: ignore[method-assign]
    executor._put_workflow_artifact = _put_workflow_artifact  # type: ignore[method-assign]
    executor._execute_node = _execute_node  # type: ignore[method-assign]
    return executor


def _workflow(*aliases: str, error_policy: str = "fail_fast") -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="res_02_regression",
        error_policy=error_policy,
        nodes=[
            NodeInvocation(
                alias=alias,
                node_id=ComponentId.parse(f"scientist.node_{alias}@1.0.0"),
            )
            for alias in aliases
        ],
    )


def test_single_skip_is_not_added_to_checkpoint_completed_set() -> None:
    state = ExperimentState(run_id="res-02-single-skip")
    hook = _RecordingCheckpointHook()
    workflow = WorkflowSpec(
        workflow_id="res_02_single_skip",
        nodes=[
            NodeInvocation(
                alias="skipped",
                node_id=ComponentId.parse("scientist.node_skipped@1.0.0"),
            ),
            NodeInvocation(
                alias="after",
                node_id=ComponentId.parse("scientist.node_after@1.0.0"),
                depends_on=["skipped"],
            ),
        ],
    )
    outcomes = {
        "skipped": NodeOutcome(status="skip", state=state),
        "after": NodeOutcome(
            status="ok",
            state=state.model_copy(update={"params": {"after": True}}),
        ),
    }
    executor = _executor(workflow, outcomes, {"after": _ref("d")}, hook)

    result = asyncio.run(executor.execute(workflow, state))

    assert result.report.status == "ok"
    assert [call["completed_nodes"] for call in hook.node_calls] == [["after"]]


def test_independent_neighbor_does_not_promote_parallel_skip_to_completed() -> None:
    state = ExperimentState(run_id="res-02-parallel-skip")
    hook = _RecordingCheckpointHook()
    workflow = WorkflowSpec(
        workflow_id="res_02_parallel_skip",
        nodes=[
            NodeInvocation(
                alias="skipped",
                node_id=ComponentId.parse("scientist.node_skipped@1.0.0"),
            ),
            NodeInvocation(
                alias="independent",
                node_id=ComponentId.parse("scientist.node_independent@1.0.0"),
            ),
            NodeInvocation(
                alias="after",
                node_id=ComponentId.parse("scientist.node_after@1.0.0"),
                depends_on=["skipped", "independent"],
            ),
        ],
    )
    outcomes = {
        "skipped": NodeOutcome(status="skip", state=state),
        "independent": NodeOutcome(
            status="ok",
            state=state.model_copy(update={"params": {"independent": True}}),
        ),
        "after": NodeOutcome(
            status="ok",
            state=state.model_copy(
                update={"params": {"independent": True, "after": True}},
            ),
        ),
    }
    executor = _executor(
        workflow,
        outcomes,
        {"independent": _ref("parallel-independent"), "after": _ref("parallel-after")},
        hook,
    )

    result = asyncio.run(executor.execute(workflow, state))

    assert result.report.status == "ok"
    assert hook.tier_calls[0]["completed_nodes"] == ["independent"]
    assert hook.node_calls[0]["completed_nodes"] == ["independent", "after"]
    assert all(
        "skipped" not in call["completed_nodes"] for call in [*hook.tier_calls, *hook.node_calls]
    )
    assert result.state.params == {"independent": True, "after": True}


def test_parallel_tier_publishes_one_checkpoint_with_full_completed_set_and_cache_refs() -> None:
    state = ExperimentState(run_id="res-02-tier-atomic")
    left = state.model_copy(update={"params": {"left": 1}})
    right = state.model_copy(update={"params": {"right": 2}})
    hook = _RecordingCheckpointHook()
    workflow = _workflow("left", "right")
    executor = _executor(
        workflow,
        {
            "left": NodeOutcome(status="ok", state=left, artifacts=[_ref("e")]),
            "right": NodeOutcome(status="ok", state=right, artifacts=[_ref("f")]),
        },
        {"left": _ref("1"), "right": _ref("2")},
        hook,
    )

    result = asyncio.run(executor.execute(workflow, state))

    assert result.report.status == "ok"
    assert result.state.params == {"left": 1, "right": 2}
    assert len(hook.tier_calls) == 1
    assert hook.tier_calls[0]["completed_nodes"] == ["left", "right"]
    assert hook.tier_calls[0]["cache_entry_refs"] == [_ref("1"), _ref("2")]
    assert hook.node_calls == []


def test_fail_fast_discards_parallel_tier_without_checkpoint_but_keeps_output_record() -> None:
    state = ExperimentState(run_id="res-02-tier-rollback")
    hook = _RecordingCheckpointHook()
    workflow = _workflow("left", "right")
    output = _ref("3", kind="scientist.output")
    executor = _executor(
        workflow,
        {
            "left": NodeOutcome(
                status="ok",
                state=state.model_copy(update={"params": {"left": 1}}),
                artifacts=[output],
            ),
            "right": NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="node.expected", message="expected failure"),
            ),
        },
        {"left": _ref("4"), "right": None},
        hook,
    )

    result = asyncio.run(executor.execute(workflow, state))

    assert result.report.status == "fail"
    assert result.state.params == {}
    assert hook.tier_calls == []
    assert result.report.nodes[0].artifacts == [output]


def test_continue_checkpoints_successes_and_preserves_their_outputs() -> None:
    state = ExperimentState(run_id="res-02-tier-continue")
    hook = _RecordingCheckpointHook()
    workflow = _workflow("left", "right", error_policy="continue")
    output = _ref("5", kind="scientist.output")
    executor = _executor(
        workflow,
        {
            "left": NodeOutcome(
                status="ok",
                state=state.model_copy(update={"params": {"left": 1}}),
                artifacts=[output],
            ),
            "right": NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="node.expected", message="expected failure"),
            ),
        },
        {"left": _ref("6"), "right": None},
        hook,
    )

    result = asyncio.run(executor.execute(workflow, state))

    assert result.report.status == "fail"
    assert result.state.params == {"left": 1}
    assert len(hook.tier_calls) == 1
    assert hook.tier_calls[0]["completed_nodes"] == ["left"]
    assert hook.tier_calls[0]["cache_entry_refs"] == [_ref("6")]
    assert result.report.nodes[0].artifacts == [output]


def test_serial_tier_supports_async_only_node_checkpoint_hook() -> None:
    state = ExperimentState(run_id="res-02-async-only-legacy")
    hook = _AsyncOnlyLegacyCheckpointHook()
    audit = _RecordingAudit()
    workflow = _workflow("solo")
    executor = _executor(
        workflow,
        {
            "solo": NodeOutcome(
                status="ok",
                state=state.model_copy(update={"params": {"solo": 1}}),
            ),
        },
        {"solo": _ref("7")},
        hook,
        audit=audit,
    )

    result = asyncio.run(executor.execute(workflow, state))

    assert result.report.status == "ok"
    assert result.state.params == {"solo": 1}
    assert [call["alias"] for call in hook.node_calls] == ["solo"]
    assert [call["completed_nodes"] for call in hook.node_calls] == [["solo"]]
    assert [call["cache_entry_ref"] for call in hook.node_calls] == [_ref("7")]
    checkpoint_entries = [
        entry for entry in audit.entries if entry["action"] == "CHECKPOINT_CREATED"
    ]
    assert checkpoint_entries
    assert all("tier_atomic" not in entry["metadata"] for entry in checkpoint_entries)


def test_parallel_tier_without_checkpoint_hook_still_executes() -> None:
    state = ExperimentState(run_id="res-02-no-hook")
    workflow = _workflow("left", "right")
    executor = _executor(
        workflow,
        {
            "left": NodeOutcome(
                status="ok",
                state=state.model_copy(update={"params": {"left": 1}}),
            ),
            "right": NodeOutcome(
                status="ok",
                state=state.model_copy(update={"params": {"right": 2}}),
            ),
        },
        {"left": _ref("7"), "right": _ref("8")},
        None,
    )

    result = asyncio.run(executor.execute(workflow, state))

    assert result.report.status == "ok"
    assert result.state.params == {"left": 1, "right": 2}


def test_multi_node_tier_rejects_node_only_hook_before_node_execution() -> None:
    state = ExperimentState(run_id="res-02-node-only-hook-refused")
    hook = _AsyncOnlyLegacyCheckpointHook()
    workflow = _workflow("left", "right")
    executor = _executor(
        workflow,
        {
            "left": NodeOutcome(
                status="ok",
                state=state.model_copy(update={"params": {"left": 1}}),
            ),
            "right": NodeOutcome(
                status="ok",
                state=state.model_copy(update={"params": {"right": 2}}),
            ),
        },
        {"left": _ref("9"), "right": _ref("10")},
        hook,
    )
    executed: list[str] = []
    execute_node = executor._execute_node

    async def _record_execution(alias: str, *args: Any, **kwargs: Any) -> Any:
        executed.append(alias)
        return await execute_node(alias, *args, **kwargs)

    executor._execute_node = _record_execution  # type: ignore[method-assign]

    with pytest.raises(CheckpointError, match="parallel_tier_requires_atomic_checkpoint_hook"):
        asyncio.run(executor.execute(workflow, state))

    assert executed == []
    assert hook.node_calls == []


def test_real_rollback_retains_output_bytes_without_selecting_them(tmp_path: Path) -> None:
    """An independent artifact survives rollback without becoming a run output."""
    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run_id = "R_res02_rollback_output"
    run = RunContext.start(store, bundle, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("res02.rollback"))
    events: list[tuple[Any, ExperimentState]] = []

    class Compensation:
        def on_tier_rollback(self, *, event: Any, restored_state: ExperimentState) -> None:
            events.append((event, restored_state))

    class Node:
        def __init__(self, alias: str) -> None:
            self.alias = alias
            self.spec = NodeSpec(
                metadata=ComponentMetadata(
                    component_id=ComponentId.parse(f"scientist.res02_{alias}@1.0.0"),
                    kind=ComponentKind.SCIENTIST_NODE,
                    abi_targets={"world_abi": "1.x"},
                    display_name=f"RES02 {alias}",
                    description="Real rollback output boundary",
                    capabilities=Capability.SCIENTIST_NODE,
                ),
                state_reads=[],
                state_writes=["artifacts_index.left"] if alias == "left" else [f"params.{alias}"],
            )

        def execute(self, context: ExecutionContext, state: ExperimentState) -> NodeOutcome:
            if self.alias == "prior":
                state.params["prior"] = 1
                return NodeOutcome(status="ok", state=state)
            if self.alias == "right":
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(code="res02.expected", message="fail"),
                )
            ref = context.store.put_bytes(
                b"real useful left output",
                PutOptions(kind="test.res02.output", media_type="application/octet-stream"),
                return_selected_profile=True,
            )
            state.artifacts_index["left"] = ref
            return NodeOutcome(status="ok", state=state, artifacts=[ref])

    registry = NodeRegistry()
    nodes = [Node(alias) for alias in ("prior", "left", "right")]
    for node in nodes:
        registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="res02_real_output_rollback",
        error_policy="fail_fast",
        nodes=[
            NodeInvocation(
                alias=node.alias,
                node_id=node.spec.metadata.component_id,
                depends_on=[] if node.alias == "prior" else ["prior"],
            )
            for node in nodes
        ],
    )
    hook = CASCheckpointHook(store=store, run_dir=Path(store.root) / "runs" / run_id)
    result = asyncio.run(
        AsyncWorkflowExecutor(
            ctx, registry, checkpoint_hook=hook, compensation_hook=Compensation(), max_parallelism=2
        ).execute(workflow, ExperimentState(run_id=run_id, inputs={"registry_bundle_ref": bundle}))
    )
    assert result.report.status == "fail"
    left = next(record for record in result.report.nodes if record.alias == "left")
    assert left.status == "ok" and len(left.artifacts) == 1
    output = left.artifacts[0]
    assert FileSystemCAS(store.root).get_bytes(output) == b"real useful left output"
    assert "left" not in result.state.artifacts_index
    assert output not in run.run_manifest.outputs
    assert len(events) == 1
    assert events[0][0].completed_before_tier == ("prior",)
    assert events[0][1].params == {"prior": 1}
    _, checkpoint = resolve_latest_checkpoint(FileSystemCAS(store.root), run_id)
    assert checkpoint.metadata.completed_nodes == ["prior"]
    assert checkpoint.state["params"] == {"prior": 1}


@pytest.mark.parametrize("with_neighbor", [False, True])
def test_real_required_graph_consumer_and_optional_consumer_after_skip(
    tmp_path: Path, with_neighbor: bool
) -> None:
    """A skipped producer leaves the actual graph consumer unready at either width."""
    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run_id = f"R_res02_graph_skip_{with_neighbor}"
    run = RunContext.start(store, bundle, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("res02.skip"))

    class Node:
        def __init__(self, alias: str) -> None:
            self.alias = alias
            self.calls = 0
            self.spec = NodeSpec(
                metadata=ComponentMetadata(
                    component_id=ComponentId.parse(f"scientist.res02_skip_{alias}@1.0.0"),
                    kind=ComponentKind.SCIENTIST_NODE,
                    abi_targets={"world_abi": "1.x"},
                    display_name=f"RES02 {alias}",
                    description="Declared optional graph consumer or skipped producer",
                    capabilities=Capability.SCIENTIST_NODE,
                ),
                state_reads=[],
                state_writes=[f"params.{alias}"],
            )

        def execute(self, _ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
            self.calls += 1
            if self.alias == "producer":
                return NodeOutcome(status="skip", state=state)
            state.params[self.alias] = True
            return NodeOutcome(status="ok", state=state)

    producer, optional, neighbor = (Node(alias) for alias in ("producer", "optional", "neighbor"))
    required = ResolveParametersNode()
    registry = NodeRegistry()
    for node in (producer, optional, neighbor, required):
        registry.register(node)
    invocations = [NodeInvocation(alias="producer", node_id=producer.spec.metadata.component_id)]
    if with_neighbor:
        invocations.append(
            NodeInvocation(alias="neighbor", node_id=neighbor.spec.metadata.component_id)
        )
    invocations.extend(
        [
            NodeInvocation(
                alias="required",
                node_id=required.spec.metadata.component_id,
                depends_on=["producer"],
            ),
            NodeInvocation(
                alias="optional",
                node_id=optional.spec.metadata.component_id,
                depends_on=["producer"],
            ),
        ]
    )
    workflow = WorkflowSpec(workflow_id="res02_graph_skip", nodes=invocations)
    hook = CASCheckpointHook(store=store, run_dir=Path(store.root) / "runs" / run_id)
    state = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": bundle},
        params={
            "target_context": {
                "context_id": "us-2025",
                "countries": ["US"],
                "publication_year": 2025,
            },
            "required_parameters": ["fiscal_multiplier"],
        },
    )
    result = asyncio.run(
        AsyncWorkflowExecutor(ctx, registry, checkpoint_hook=hook, max_parallelism=2).execute(
            workflow, state
        )
    )
    records = {record.alias: record for record in result.report.nodes}
    assert records["producer"].status == "skip"
    assert records["required"].status == "skip"
    assert records["required"].skip_blocker is not None
    assert records["optional"].status == "ok" and optional.calls == 1
    assert "phase15_runtime_ready" not in result.state.params
    _, checkpoint = resolve_latest_checkpoint(FileSystemCAS(store.root), run_id)
    assert "producer" not in checkpoint.metadata.completed_nodes
    assert "required" not in checkpoint.metadata.completed_nodes
    assert "optional" in checkpoint.metadata.completed_nodes
    assert ("neighbor" in checkpoint.metadata.completed_nodes) is with_neighbor
