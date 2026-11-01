"""Regression witnesses for the bounded EXE-02 readiness schedule."""

from __future__ import annotations

import asyncio
import tempfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
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


class _TemporaryFileSystemCAS(FileSystemCAS):
    """Provide the selected-profile writer required by terminal finalization."""

    def __init__(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory(prefix="exe-02-test-")
        super().__init__(Path(self._temporary_directory.name) / "cas")


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
    store = _TemporaryFileSystemCAS()
    run = MagicMock()
    run.trace_path = None
    run.finalize.return_value = _ref("f", kind="scientist.run")
    return ExecutionContext(store=store, run=run, logger=MagicMock())


def _executor(
    nodes: dict[str, MagicMock],
    execute_node,
    *,
    checkpoint_hook=None,
) -> AsyncWorkflowExecutor:
    registry = MagicMock(spec=NodeRegistry)
    registry.get.side_effect = lambda node_id: nodes[str(node_id)]
    executor = AsyncWorkflowExecutor(
        _context(),
        registry,
        checkpoint_hook=checkpoint_hook,
        max_parallelism=2,
    )

    async def _persist_workflow_spec(
        workflow: WorkflowSpec,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        del workflow
        assert return_selected_profile is True
        return _ref("a", kind="scientist.workflow_spec")

    async def _persist_state(
        state: ExperimentState,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        del state
        del return_selected_profile
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
    fail_a: bool = False,
    checkpoint_hook=None,
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
        if alias == "a" and fail_a:
            return (
                NodeOutcome(
                    status="fail",
                    state=node_state,
                    error=NodeError(code="node.exe_02_expected", message="A failed"),
                ),
                1,
                False,
                None,
            )
        return NodeOutcome(status="ok", state=node_state), 1, False, None

    executor = _executor(
        _nodes(overlap=overlap),
        _execute_node,
        checkpoint_hook=checkpoint_hook,
    )
    task = asyncio.create_task(executor.execute(_workflow(c_depends_on=c_depends_on), state))
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
async def test_failed_predecessor_blocks_successor_and_keeps_independent_sibling() -> None:
    """A failure blocks C without cancelling independent slow B."""
    task, release_b, c_started, b_finished, started, _c_inputs = await _run_witness(
        overlap=False,
        c_depends_on=["a"],
        fail_a=True,
    )

    await asyncio.sleep(0)
    c_started_before_b = c_started.is_set()
    b_finished_before_release = b_finished.is_set()
    release_b.set()
    result = await task

    assert not c_started_before_b
    assert not b_finished_before_release
    assert result.report.status == "fail"
    assert started == ["a", "b"]
    assert [record.alias for record in result.report.nodes] == ["a", "b", "c"]
    assert [record.status for record in result.report.nodes] == ["fail", "ok", "skip"]
    assert result.state.params == {"b": "done"}


@pytest.mark.asyncio
async def test_checkpoint_hook_preserves_tier_wide_successor_barrier() -> None:
    """A semantic tier hook keeps the established tier schedule."""

    class _NoopCheckpointHook:
        def on_tier_complete(self, **_kwargs):
            return None

    task, release_b, c_started, b_finished, started, _c_inputs = await _run_witness(
        overlap=False,
        c_depends_on=["a"],
        checkpoint_hook=_NoopCheckpointHook(),
    )

    await asyncio.sleep(0)
    c_started_before_b = c_started.is_set()
    b_finished_before_release = b_finished.is_set()
    release_b.set()
    result = await task

    assert not c_started_before_b
    assert not b_finished_before_release
    assert result.report.status == "ok"
    assert c_started.is_set()
    assert started == ["a", "b", "c"]
    assert [record.alias for record in result.report.nodes] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_readiness_preserves_node_bindings_seed_and_record_order() -> None:
    """The schedule observes each original method binding exactly once."""
    nodes = _nodes()
    binding_by_alias = {
        "a": {"method": "fit", "seed": 41, "repeats": 2},
        "b": {"method": "validate", "seed": 41, "repeats": 2},
        "c": {"method": "publish", "seed": 41, "repeats": 2},
    }
    observed: dict[str, tuple[dict[str, object], dict[str, object]]] = {}

    async def _execute_node(alias, invocation, node_state, workflow, *, tier_index=0):
        del workflow, tier_index
        observed[alias] = (
            dict(invocation.params),
            {
                "seed": node_state.params["seed"],
                "repeat_count": node_state.params["repeat_count"],
                "input_ref": node_state.inputs["fixture"],
            },
        )
        node_state.params[alias] = "done"
        return NodeOutcome(status="ok", state=node_state), 1, False, None

    workflow = WorkflowSpec(
        workflow_id="exe_02_preserved_invocation_bindings",
        error_policy="continue",
        nodes=[
            NodeInvocation(
                alias=alias,
                node_id=ComponentId.parse(f"scientist.exe_{alias}@1.0.0"),
                params=params,
                depends_on=["a"] if alias == "c" else [],
            )
            for alias, params in binding_by_alias.items()
        ],
    )
    input_ref = _ref("e")
    state = ExperimentState(
        run_id="exe-02-bindings",
        inputs={"fixture": input_ref},
        params={"seed": 41, "repeat_count": 2},
    )
    result = await _executor(nodes, _execute_node).execute(workflow, state)

    assert observed == {
        alias: (params, {"seed": 41, "repeat_count": 2, "input_ref": input_ref})
        for alias, params in binding_by_alias.items()
    }
    assert result.report.status == "ok"
    assert [record.alias for record in result.report.nodes] == ["a", "b", "c"]


def _container_nodes(
    left_segment: str,
    right_segment: str,
    *,
    target_suffix: str | None = None,
) -> dict[str, MagicMock]:
    a_id = "scientist.exe_container_a@1.0.0"
    b_id = "scientist.exe_container_b@1.0.0"
    c_id = "scientist.exe_container_c@1.0.0"
    a = MagicMock()
    a.spec = _node_spec(
        a_id,
        state_writes=(
            f"params.items.{left_segment}{'.' + target_suffix if target_suffix else ''}",
            "params.c_input",
        ),
    )
    b = MagicMock()
    b.spec = _node_spec(
        b_id,
        state_writes=(
            f"params.items.{right_segment}{'.' + target_suffix if target_suffix else ''}",
        ),
    )
    c = MagicMock()
    c.spec = _node_spec(
        c_id,
        state_reads=("params.c_input",),
        state_writes=("params.result",),
    )
    return {a_id: a, b_id: b, c_id: c}


async def _run_container_witness(
    *,
    container: object,
    left_segment: str,
    right_segment: str,
    unjournaled: bool = False,
    touch_slots: bool = False,
    target_suffix: str | None = None,
    alias_items: bool = False,
    checkpoint_hook=None,
) -> tuple[asyncio.Task, asyncio.Event, asyncio.Event, asyncio.Event, list[str], list[object]]:
    """Run real executor branching over a list or mapping with a held sibling."""
    nodes = _container_nodes(
        left_segment,
        right_segment,
        target_suffix=target_suffix,
    )
    started: list[str] = []
    c_observed: list[object] = []
    b_started = asyncio.Event()
    b_release = asyncio.Event()
    b_finished = asyncio.Event()
    c_started = asyncio.Event()
    state = ExperimentState(run_id="exe-02-container", params={"items": container})
    if alias_items:
        assert isinstance(state.params["items"], list)
        shared = {"value": "initial"}
        state.params["items"] = [shared, shared]
        assert state.params["items"][0] is state.params["items"][1]
    left_index = int(left_segment) if isinstance(container, list) else left_segment
    right_index = int(right_segment) if isinstance(container, list) else right_segment

    async def _execute_node(alias, invocation, input_state, workflow, *, tier_index=0):
        del workflow, tier_index
        node = nodes[str(invocation.node_id)]
        node_state = branch_state(
            input_state,
            write_paths=node.spec.state_writes,
        ).state
        started.append(alias)
        if alias == "a":
            if touch_slots and node_state.params["items"] is not None:
                if target_suffix is None:
                    node_state.params["items"][left_index] = "from-a"
                else:
                    node_state.params["items"][left_index][target_suffix] = "from-a"
            node_state.params["c_input"] = "from-a"
        elif alias == "b":
            b_started.set()
            await b_release.wait()
            if touch_slots and node_state.params["items"] is not None:
                if target_suffix is None:
                    node_state.params["items"][right_index] = "from-b"
                else:
                    node_state.params["items"][right_index][target_suffix] = "from-b"
            b_finished.set()
        else:
            c_started.set()
            c_observed.append(
                (
                    deepcopy(node_state.params["items"]),
                    node_state.params.get("c_input"),
                )
            )
            node_state.params["result"] = "from-c"

        if unjournaled:
            node_state = ExperimentState.model_validate(node_state.model_dump(mode="python"))
        return NodeOutcome(status="ok", state=node_state), 1, False, None

    executor = _executor(
        nodes,
        _execute_node,
        checkpoint_hook=checkpoint_hook,
    )
    workflow = WorkflowSpec(
        workflow_id="exe_02_container_alias",
        error_policy="continue",
        nodes=[
            NodeInvocation(
                alias="a",
                node_id=ComponentId.parse("scientist.exe_container_a@1.0.0"),
            ),
            NodeInvocation(
                alias="b",
                node_id=ComponentId.parse("scientist.exe_container_b@1.0.0"),
            ),
            NodeInvocation(
                alias="c",
                node_id=ComponentId.parse("scientist.exe_container_c@1.0.0"),
                depends_on=["a"],
            ),
        ],
    )
    task = asyncio.create_task(executor.execute(workflow, state))
    await asyncio.wait_for(b_started.wait(), timeout=1)
    return task, b_release, c_started, b_finished, started, c_observed


@pytest.mark.parametrize("alias_segment", ["00", "+0", "-1"])
@pytest.mark.parametrize("unjournaled", [False, True])
@pytest.mark.asyncio
async def test_one_element_list_alias_cannot_release_successor_before_conflict_resolution(
    alias_segment: str,
    unjournaled: bool,
) -> None:
    """Equivalent list indexes cannot release a successor from a stale state."""
    task, release_b, c_started, b_finished, _started, c_observed = await _run_container_witness(
        container=["initial"],
        left_segment="0",
        right_segment=alias_segment,
        unjournaled=unjournaled,
        touch_slots=True,
    )

    await asyncio.sleep(0)
    c_started_before_b = c_started.is_set()
    b_finished_before_release = b_finished.is_set()
    release_b.set()
    result = await task

    assert not c_started_before_b
    assert not b_finished_before_release
    assert not c_started.is_set()
    assert result.report.status == "fail"
    assert result.state.params["items"] == ["initial"]
    assert [record.status for record in result.report.nodes] == ["fail", "fail", "skip"]
    assert [record.error.code if record.error else None for record in result.report.nodes] == [
        "node.parallel_merge_conflict",
        "node.parallel_merge_conflict",
        None,
    ]
    assert c_observed == []
    assert [record.alias for record in result.report.nodes] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_unresolved_container_shape_keeps_existing_tier_barrier() -> None:
    """A declared list path is not admitted when the current parent is unknown."""
    task, release_b, c_started, b_finished, _started, c_observed = await _run_container_witness(
        container=None,
        left_segment="0",
        right_segment="1",
    )

    await asyncio.sleep(0)
    c_started_before_b = c_started.is_set()
    b_finished_before_release = b_finished.is_set()
    release_b.set()
    result = await task

    assert not c_started_before_b
    assert not b_finished_before_release
    assert result.report.status == "ok"
    assert c_started.is_set()
    assert [record.alias for record in result.report.nodes] == ["a", "b", "c"]
    assert c_observed == [(None, "from-a")]


@pytest.mark.asyncio
async def test_same_mutable_object_in_two_list_slots_is_not_admitted_as_disjoint() -> None:
    """Distinct indices do not prove distinct targets when the elements alias."""
    task, release_b, c_started, b_finished, started, c_observed = await _run_container_witness(
        container=[{"value": "initial"}, {"value": "initial"}],
        left_segment="0",
        right_segment="1",
        target_suffix="value",
        alias_items=True,
        touch_slots=True,
    )

    await asyncio.sleep(0)
    c_started_before_b = c_started.is_set()
    b_finished_before_release = b_finished.is_set()
    release_b.set()
    result = await task

    assert not c_started_before_b
    assert not b_finished_before_release
    assert result.report.status == "fail"
    assert not c_started.is_set()
    assert b_finished.is_set()
    assert started == ["a", "b"]
    assert [record.status for record in result.report.nodes] == ["fail", "fail", "skip"]
    assert [record.error.code if record.error else None for record in result.report.nodes] == [
        "node.parallel_merge_conflict",
        "node.parallel_merge_conflict",
        None,
    ]
    assert c_observed == []


@pytest.mark.asyncio
async def test_cross_parent_shared_mapping_alias_is_not_admitted_as_disjoint() -> None:
    """Different declared parents that resolve to one object retain the tier barrier."""
    a_id = "scientist.exe_cross_parent_a@1.0.0"
    b_id = "scientist.exe_cross_parent_b@1.0.0"
    c_id = "scientist.exe_cross_parent_c@1.0.0"
    nodes: dict[str, MagicMock] = {}
    for node_id, reads, writes in (
        (a_id, (), ("params.left.items.0.value", "params.c_input")),
        (b_id, (), ("params.right.items.0.value",)),
        (c_id, ("params.c_input",), ("params.result",)),
    ):
        node = MagicMock()
        node.spec = _node_spec(node_id, state_reads=reads, state_writes=writes)
        nodes[node_id] = node

    shared = {"items": [{"value": "initial"}]}
    state = ExperimentState(run_id="exe-02-cross-parent-alias")
    state.params["left"] = shared
    state.params["right"] = shared
    assert state.params["left"] is state.params["right"]
    started: list[str] = []
    c_observed: list[object] = []
    b_started = asyncio.Event()
    b_release = asyncio.Event()
    b_finished = asyncio.Event()
    c_started = asyncio.Event()

    async def _execute_node(alias, invocation, input_state, workflow, *, tier_index=0):
        del workflow, tier_index
        node = nodes[str(invocation.node_id)]
        node_state = branch_state(input_state, write_paths=node.spec.state_writes).state
        started.append(alias)
        if alias == "a":
            node_state.params["left"]["items"][0]["value"] = "from-a"
            node_state.params["c_input"] = "from-a"
        elif alias == "b":
            b_started.set()
            await b_release.wait()
            node_state.params["right"]["items"][0]["value"] = "from-b"
            b_finished.set()
        else:
            c_started.set()
            c_observed.append(
                (
                    node_state.params["left"]["items"][0]["value"],
                    node_state.params["right"]["items"][0]["value"],
                    node_state.params.get("c_input"),
                )
            )
            node_state.params["result"] = "from-c"
        return NodeOutcome(status="ok", state=node_state), 1, False, None

    workflow = WorkflowSpec(
        workflow_id="exe_02_cross_parent_alias",
        error_policy="continue",
        nodes=[
            NodeInvocation(alias="a", node_id=ComponentId.parse(a_id)),
            NodeInvocation(alias="b", node_id=ComponentId.parse(b_id)),
            NodeInvocation(
                alias="c",
                node_id=ComponentId.parse(c_id),
                depends_on=["a"],
            ),
        ],
    )
    task = asyncio.create_task(_executor(nodes, _execute_node).execute(workflow, state))
    await asyncio.wait_for(b_started.wait(), timeout=1)
    await asyncio.sleep(0)
    c_started_before_b = c_started.is_set()
    b_finished_before_release = b_finished.is_set()
    b_release.set()
    result = await task

    assert not c_started_before_b
    assert not b_finished_before_release
    assert b_finished.is_set()
    assert result.report.status == "fail"
    assert started == ["a", "b"]
    assert [record.status for record in result.report.nodes] == ["fail", "fail", "skip"]
    assert [record.error.code if record.error else None for record in result.report.nodes] == [
        "node.parallel_merge_conflict",
        "node.parallel_merge_conflict",
        None,
    ]
    assert c_observed == []


@pytest.mark.parametrize(
    ("container", "left_segment", "right_segment"),
    [
        ({"0": 0, "00": 0}, "0", "00"),
        (["initial-zero", "initial-one"], "0", "1"),
    ],
)
@pytest.mark.asyncio
async def test_proven_disjoint_container_targets_keep_early_successor_release(
    container: list[object] | dict[str, object],
    left_segment: str,
    right_segment: str,
) -> None:
    """Exact dict keys and stable distinct list slots retain useful readiness."""
    task, release_b, c_started, b_finished, _started, c_observed = await _run_container_witness(
        container=container,
        left_segment=left_segment,
        right_segment=right_segment,
        touch_slots=True,
    )

    try:
        await asyncio.wait_for(c_started.wait(), timeout=1)
        c_released_before_b = True
    except TimeoutError:
        c_released_before_b = False
    b_was_still_running = not b_finished.is_set()
    c_observed_before_release = list(c_observed)
    release_b.set()
    result = await task

    assert c_released_before_b
    left_index = int(left_segment) if isinstance(container, list) else left_segment
    right_index = int(right_segment) if isinstance(container, list) else right_segment
    expected_after_a = deepcopy(container)
    expected_after_a[left_index] = "from-a"
    expected_final = deepcopy(container)
    expected_final[left_index] = "from-a"
    expected_final[right_index] = "from-b"
    assert c_observed_before_release == [(expected_after_a, "from-a")]
    assert b_was_still_running

    assert result.report.status == "ok"
    assert [record.alias for record in result.report.nodes] == ["a", "b", "c"]
    final_items = result.state.params["items"]
    assert final_items == expected_final


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
