"""Regression witnesses for the bounded EXE-02 readiness schedule."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.engine.state_merge import (
    StateReplayIncompatible,
    merge_parallel_outcomes,
)
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


def _ref(tag: str, *, kind: str = "scientist.test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + tag * 64,
        kind=kind,
        media_type="application/json",
    )


def _node_spec(
    node_id: str,
    *,
    state_reads: tuple[str, ...] = (),
    state_writes: tuple[str, ...] = (),
) -> NodeSpec:
    return NodeSpec(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse(node_id),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name="EXE-02 test node",
            description="Deterministic readiness scheduling witness",
            tags=["test"],
            capabilities=Capability.SCIENTIST_NODE,
        ),
        state_reads=list(state_reads),
        state_writes=list(state_writes),
        produces=[],
    )


def _context() -> ExecutionContext:
    store = MagicMock()
    run = MagicMock()
    run.trace_path = None
    run.finalize.return_value = _ref("f", kind="scientist.run")
    return ExecutionContext(store=store, run=run, logger=MagicMock())


def _executor(
    nodes: dict[str, MagicMock],
    execute_node,
) -> AsyncWorkflowExecutor:
    registry = MagicMock(spec=NodeRegistry)
    registry.get.side_effect = lambda node_id: nodes[str(node_id)]
    executor = AsyncWorkflowExecutor(_context(), registry, max_parallelism=2)

    async def _persist_workflow_spec(workflow: WorkflowSpec) -> ArtifactRef:
        del workflow
        return _ref("a", kind="scientist.workflow_spec")

    async def _persist_state(state: ExperimentState) -> ArtifactRef:
        del state
        return _ref("b", kind="scientist.experiment_state")

    async def _persist_report(report) -> ArtifactRef:
        del report
        return _ref("c", kind="scientist.workflow_report")

    executor._persist_workflow_spec = _persist_workflow_spec  # type: ignore[method-assign]
    executor._persist_state = _persist_state  # type: ignore[method-assign]
    executor._persist_report = _persist_report  # type: ignore[method-assign]
    executor._execute_node = execute_node  # type: ignore[method-assign]
    return executor


def _nodes(*, overlap: bool = False) -> dict[str, MagicMock]:
    a_id = "scientist.exe_a@1.0.0"
    b_id = "scientist.exe_b@1.0.0"
    c_id = "scientist.exe_c@1.0.0"
    a = MagicMock()
    a.spec = _node_spec(
        a_id,
        state_writes=("params.a", "params.c_input") if not overlap else ("params.a",),
    )
    b = MagicMock()
    b.spec = _node_spec(
        b_id,
        state_writes=("params.c_input" if overlap else "params.b",),
    )
    c = MagicMock()
    c.spec = _node_spec(c_id, state_reads=("params.c_input",), state_writes=("params.result",))
    return {a_id: a, b_id: b, c_id: c}


def _workflow(*, c_depends_on: list[str]) -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="exe_02_readiness",
        error_policy="continue",
        nodes=[
            NodeInvocation(alias="a", node_id=ComponentId.parse("scientist.exe_a@1.0.0")),
            NodeInvocation(alias="b", node_id=ComponentId.parse("scientist.exe_b@1.0.0")),
            NodeInvocation(
                alias="c",
                node_id=ComponentId.parse("scientist.exe_c@1.0.0"),
                depends_on=c_depends_on,
            ),
        ],
    )


async def _run_witness(
    *,
    overlap: bool,
    c_depends_on: list[str],
) -> tuple[asyncio.Task, asyncio.Event, asyncio.Event, asyncio.Event, list[str], list[str]]:
    started: list[str] = []
    c_inputs: list[str | None] = []
    b_started = asyncio.Event()
    b_release = asyncio.Event()
    c_started = asyncio.Event()
    b_finished = asyncio.Event()
    state = ExperimentState(run_id="exe-02-witness")

    async def _execute_node(alias, invocation, node_state, workflow, *, tier_index=0):
        del invocation, workflow, tier_index
        started.append(alias)
        if alias == "a":
            node_state.params["a"] = "done"
            if not overlap:
                node_state.params["c_input"] = "from-a"
        elif alias == "b":
            b_started.set()
            await b_release.wait()
            if overlap:
                node_state.params["c_input"] = "from-b"
            else:
                node_state.params["b"] = "done"
            b_finished.set()
        else:
            c_started.set()
            c_inputs.append(node_state.params.get("c_input"))
            node_state.params["result"] = "from-c"
        return NodeOutcome(status="ok", state=node_state), 1, False, None

    executor = _executor(_nodes(overlap=overlap), _execute_node)
    task = asyncio.create_task(
        executor.execute(_workflow(c_depends_on=c_depends_on), state)
    )
    await asyncio.wait_for(b_started.wait(), timeout=1)
    return task, b_release, c_started, b_finished, started, c_inputs


def test_readiness_launch_baseline_is_not_execution_input() -> None:
    """A node mutation cannot alter the snapshot used for delta ownership."""
    source = ExperimentState(run_id="exe-02-baseline")

    baseline, execution_input = AsyncWorkflowExecutor._readiness_launch_pair(source)
    execution_input.params["a"] = "done"

    assert source.params == {}
    assert baseline.params == {}
    assert execution_input.params == {"a": "done"}


def test_readiness_launch_pair_isolates_nested_mutable_state() -> None:
    """Nested execution-input mutation cannot leak into source or baseline."""
    source = ExperimentState(
        run_id="exe-02-nested-alias",
        params={"nested": {"x": "old"}},
    )

    baseline, execution_input = AsyncWorkflowExecutor._readiness_launch_pair(source)
    execution_input.params["nested"]["x"] = "new"

    assert source.params["nested"] == {"x": "old"}
    assert baseline.params["nested"] == {"x": "old"}


def test_readiness_rejects_journal_operation_outside_declared_paths() -> None:
    """A branch journal cannot smuggle an undeclared state operation."""
    baseline = ExperimentState(run_id="exe-02-journal-boundary")
    returned = branch_state(
        baseline,
        write_paths=("params.allowed", "params.unauthorized"),
    ).state
    returned.params["allowed"] = "ok"
    returned.params["unauthorized"] = "bad"

    with pytest.raises(StateReplayIncompatible) as error:
        AsyncWorkflowExecutor._prepare_readiness_outcome(
            NodeOutcome(status="ok", state=returned),
            baseline,
            ["params.allowed"],
        )

    assert error.value.path == "params.unauthorized"


def test_readiness_rebases_stale_returned_snapshot_to_declared_delta() -> None:
    """A returned stale sibling snapshot cannot overwrite a committed write."""
    baseline = ExperimentState(run_id="exe-02-returned", params={"a": "old"})
    returned = ExperimentState(
        run_id="exe-02-returned",
        params={"a": "old", "b": "done"},
    )
    raw_journal = AsyncWorkflowExecutor._readiness_synthetic_journal(
        baseline,
        returned,
        ["params.b"],
    )
    raw_replay = merge_parallel_outcomes(
        baseline,
        {"b": NodeOutcome(status="ok", state=returned)},
        {"b": ["params.b"]},
        mutation_journals={"b": raw_journal},
    )
    assert raw_replay.state.model_dump(mode="python") == returned.model_dump(mode="python")

    prepared, journal = AsyncWorkflowExecutor._prepare_readiness_outcome(
        NodeOutcome(status="ok", state=returned),
        baseline,
        ["params.b"],
    )

    assert journal is not None
    assert [operation.path for operation in journal.operations] == ["params.b"]
    merged = merge_parallel_outcomes(
        ExperimentState(run_id="exe-02-returned", params={"a": "done"}),
        {"b": prepared},
        {"b": ["params.b"]},
        mutation_journals={"b": journal},
    )
    assert merged.state.params == {"a": "done", "b": "done"}


def test_readiness_rejects_undeclared_returned_snapshot_write() -> None:
    """Unjournaled state outside the declared paths fails closed."""
    with pytest.raises(StateReplayIncompatible) as error:
        AsyncWorkflowExecutor._prepare_readiness_outcome(
            NodeOutcome(
                status="ok",
                state=ExperimentState(
                    run_id="exe-02-undeclared",
                    params={"a": "done", "c_input": "from-a"},
                ),
            ),
            ExperimentState(run_id="exe-02-undeclared"),
            ["params.c_input"],
        )

    assert error.value.path == "params.a"


@pytest.mark.asyncio
async def test_independent_successor_starts_before_slow_sibling() -> None:
    """C observes committed A while independent slow B is still running."""
    task, release_b, c_started, b_finished, started, c_inputs = await _run_witness(
        overlap=False,
        c_depends_on=["a"],
    )

    await asyncio.wait_for(c_started.wait(), timeout=1)
    assert c_inputs == ["from-a"]
    assert started[:2] == ["a", "b"]
    assert not b_finished.is_set()
    assert not task.done()

    release_b.set()
    result = await task
    assert result.report.status == "ok"
    assert [record.alias for record in result.report.nodes] == ["a", "b", "c"]
    assert result.state.params == {
        "a": "done",
        "c_input": "from-a",
        "result": "from-c",
        "b": "done",
    }


@pytest.mark.asyncio
async def test_unordered_read_write_overlap_keeps_tier_barrier() -> None:
    """An unordered B write overlapping C's read must not be reordered."""
    task, release_b, c_started, _b_finished, _started, _c_inputs = await _run_witness(
        overlap=True,
        c_depends_on=["a"],
    )

    await asyncio.sleep(0)
    assert not c_started.is_set()
    release_b.set()
    result = await task
    assert result.report.status == "ok"
    assert c_started.is_set()


@pytest.mark.asyncio
async def test_declared_dependency_keeps_successor_after_b_and_overlap() -> None:
    """A real B→C edge remains a join even when the paths overlap."""
    task, release_b, c_started, _b_finished, _started, _c_inputs = await _run_witness(
        overlap=True,
        c_depends_on=["a", "b"],
    )

    await asyncio.sleep(0)
    assert not c_started.is_set()
    release_b.set()
    result = await task
    assert result.report.status == "ok"
    assert c_started.is_set()
