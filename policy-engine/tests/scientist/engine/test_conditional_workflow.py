"""Integration tests for conditional nodes in both sync and async executors."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.engine.condition import NodeCondition
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.executor import WorkflowExecutor
from polisyos.scientist.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.engine.registry import NodeRegistry
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec

_FAKE_SHA = "sha256:" + "ab" * 32


def _make_ctx():
    store = MagicMock()
    store.put_json.return_value = ArtifactRef(
        artifact_id=_FAKE_SHA,
        kind="test",
        media_type="application/json",
    )
    run = MagicMock()
    run.trace_path = None
    run.finalize.return_value = ArtifactRef(
        artifact_id=_FAKE_SHA,
        kind="run",
        media_type="application/json",
    )
    return ExecutionContext(store=store, run=run, logger=MagicMock())


def _make_mock_node(*, node_id="test.node@1.0.0", state_writes=None):
    node = MagicMock()
    node.spec = MagicMock(spec=NodeSpec)
    node.spec.state_reads = []
    node.spec.state_writes = state_writes or []
    node.spec.node_id = node_id
    return node


def _ok_outcome(state: ExperimentState) -> NodeOutcome:
    return NodeOutcome(status="ok", state=state, events=[], artifacts=[])


# ---------------------------------------------------------------------------
# Sync executor tests
# ---------------------------------------------------------------------------


class TestSyncConditionalNodes:
    def test_condition_true_runs_node(self) -> None:
        """Node with condition=true runs normally."""
        state = ExperimentState(run_id="r1", params={"enabled": True})
        node = _make_mock_node()
        node.execute.return_value = _ok_outcome(state)

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_cond_true",
            nodes=[
                NodeInvocation(
                    alias="step_a",
                    node_id="test.node@1.0.0",
                    condition=NodeCondition(expr="params.enabled == true"),
                ),
            ],
        )

        ctx = _make_ctx()
        result = WorkflowExecutor(ctx, registry).execute(workflow, state)
        assert result.report.status == "ok"
        assert result.report.nodes[0].status == "ok"

    def test_condition_false_skips_node(self) -> None:
        """Node with condition=false and on_false=skip is skipped."""
        state = ExperimentState(run_id="r2", params={"enabled": False})
        node = _make_mock_node()

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_cond_false",
            nodes=[
                NodeInvocation(
                    alias="step_a",
                    node_id="test.node@1.0.0",
                    condition=NodeCondition(expr="params.enabled == true"),
                ),
            ],
        )

        ctx = _make_ctx()
        result = WorkflowExecutor(ctx, registry).execute(workflow, state)
        assert result.report.status == "ok"  # skip is not a failure
        assert result.report.nodes[0].status == "skip"
        assert result.report.nodes[0].skip_reason == "condition_false"
        node.execute.assert_not_called()

    def test_condition_false_fail_fails_node(self) -> None:
        """Node with on_false=fail is failed."""
        state = ExperimentState(run_id="r3", params={"enabled": False})
        node = _make_mock_node()

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_cond_fail",
            nodes=[
                NodeInvocation(
                    alias="step_a",
                    node_id="test.node@1.0.0",
                    condition=NodeCondition(expr="params.enabled == true", on_false="fail"),
                ),
            ],
        )

        ctx = _make_ctx()
        result = WorkflowExecutor(ctx, registry).execute(workflow, state)
        assert result.report.status == "fail"
        assert result.report.nodes[0].status == "fail"
        assert result.report.nodes[0].error is not None
        assert result.report.nodes[0].error.code == "node.condition_false"

    def test_condition_skip_does_not_block_downstream(self) -> None:
        """Condition-skipped node does NOT block downstream."""
        state = ExperimentState(run_id="r4", params={"skip_this": True})
        node = _make_mock_node()
        node.execute.return_value = _ok_outcome(state)

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_skip_no_block",
            nodes=[
                NodeInvocation(
                    alias="step_a",
                    node_id="test.node@1.0.0",
                    condition=NodeCondition(expr="params.skip_this == false"),
                ),
                NodeInvocation(
                    alias="step_b",
                    node_id="test.node@1.0.0",
                    depends_on=["step_a"],
                ),
            ],
        )

        ctx = _make_ctx()
        result = WorkflowExecutor(ctx, registry).execute(workflow, state)
        assert result.report.nodes[0].status == "skip"
        assert result.report.nodes[0].skip_reason == "condition_false"
        # step_b should still run
        assert result.report.nodes[1].status == "ok"

    def test_condition_fail_blocks_downstream(self) -> None:
        """Condition-failed node DOES block downstream."""
        state = ExperimentState(run_id="r5", params={"x": False})
        node = _make_mock_node()
        node.execute.return_value = _ok_outcome(state)

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_fail_blocks",
            nodes=[
                NodeInvocation(
                    alias="step_a",
                    node_id="test.node@1.0.0",
                    condition=NodeCondition(expr="params.x == true", on_false="fail"),
                ),
                NodeInvocation(
                    alias="step_b",
                    node_id="test.node@1.0.0",
                    depends_on=["step_a"],
                ),
            ],
            error_policy="continue",
        )

        ctx = _make_ctx()
        result = WorkflowExecutor(ctx, registry).execute(workflow, state)
        assert result.report.nodes[0].status == "fail"
        assert result.report.nodes[1].status == "skip"
        assert result.report.nodes[1].skip_reason == "upstream_failed"

    def test_branching_pattern(self) -> None:
        """If/else branching: one path runs, other skipped, merge runs."""
        state = ExperimentState(run_id="r6", params={"transport_required": True})
        node = _make_mock_node()
        node.execute.return_value = _ok_outcome(state)

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_branching",
            nodes=[
                NodeInvocation(
                    alias="path_a",
                    node_id="test.node@1.0.0",
                    condition=NodeCondition(expr="params.transport_required == true"),
                ),
                NodeInvocation(
                    alias="path_b",
                    node_id="test.node@1.0.0",
                    condition=NodeCondition(expr="params.transport_required != true"),
                ),
                NodeInvocation(
                    alias="merge",
                    node_id="test.node@1.0.0",
                    depends_on=["path_a", "path_b"],
                ),
            ],
        )

        ctx = _make_ctx()
        result = WorkflowExecutor(ctx, registry).execute(workflow, state)
        records = {r.alias: r for r in result.report.nodes}
        assert records["path_a"].status == "ok"
        assert records["path_b"].status == "skip"
        assert records["path_b"].skip_reason == "condition_false"
        assert records["merge"].status == "ok"  # NOT blocked by condition_skipped path_b

    def test_no_condition_unchanged_behavior(self) -> None:
        """Nodes without conditions run as before."""
        state = ExperimentState(run_id="r7")
        node = _make_mock_node()
        node.execute.return_value = _ok_outcome(state)

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_no_cond",
            nodes=[
                NodeInvocation(alias="step_a", node_id="test.node@1.0.0"),
                NodeInvocation(alias="step_b", node_id="test.node@1.0.0", depends_on=["step_a"]),
            ],
        )

        ctx = _make_ctx()
        result = WorkflowExecutor(ctx, registry).execute(workflow, state)
        assert result.report.status == "ok"
        assert all(r.status == "ok" for r in result.report.nodes)

    def test_condition_syntax_error_treated_as_false(self) -> None:
        """Malformed condition expression defaults to condition=False."""
        state = ExperimentState(run_id="r8")
        node = _make_mock_node()

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_syntax_err",
            nodes=[
                NodeInvocation(
                    alias="step_a",
                    node_id="test.node@1.0.0",
                    condition=NodeCondition(expr="!!! invalid !!!"),
                ),
            ],
        )

        ctx = _make_ctx()
        result = WorkflowExecutor(ctx, registry).execute(workflow, state)
        assert result.report.nodes[0].status == "skip"

    def test_is_set_condition(self) -> None:
        """Unary is_set condition works."""
        state = ExperimentState(run_id="r9", execution_profile="research")
        node = _make_mock_node()
        node.execute.return_value = _ok_outcome(state)

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_is_set",
            nodes=[
                NodeInvocation(
                    alias="step_a",
                    node_id="test.node@1.0.0",
                    condition=NodeCondition(expr="execution_profile is_set"),
                ),
            ],
        )

        ctx = _make_ctx()
        result = WorkflowExecutor(ctx, registry).execute(workflow, state)
        assert result.report.nodes[0].status == "ok"


# ---------------------------------------------------------------------------
# Async executor tests
# ---------------------------------------------------------------------------


class TestAsyncConditionalNodes:
    @pytest.mark.asyncio
    async def test_condition_skip_in_tier(self) -> None:
        """Conditional skip in async tier filtering."""
        state = ExperimentState(run_id="async-r1", params={"enabled": False})
        node = _make_mock_node()
        node.execute.return_value = _ok_outcome(state)

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_async_cond",
            nodes=[
                NodeInvocation(
                    alias="step_a",
                    node_id="test.node@1.0.0",
                    condition=NodeCondition(expr="params.enabled == true"),
                ),
                NodeInvocation(alias="step_b", node_id="test.node@1.0.0"),
            ],
        )

        ctx = _make_ctx()
        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        records = {r.alias: r for r in result.report.nodes}
        assert records["step_a"].status == "skip"
        assert records["step_a"].skip_reason == "condition_false"
        assert records["step_b"].status == "ok"

    @pytest.mark.asyncio
    async def test_branching_in_parallel_tier(self) -> None:
        """Branching works in parallel tier — one path skipped, merge runs."""
        state = ExperimentState(run_id="async-r2", params={"mode": "a"})
        node = _make_mock_node()
        node.execute.return_value = _ok_outcome(state)

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_async_branch",
            nodes=[
                NodeInvocation(
                    alias="path_a",
                    node_id="test.node@1.0.0",
                    condition=NodeCondition(expr='params.mode == "a"'),
                ),
                NodeInvocation(
                    alias="path_b",
                    node_id="test.node@1.0.0",
                    condition=NodeCondition(expr='params.mode == "b"'),
                ),
                NodeInvocation(
                    alias="merge",
                    node_id="test.node@1.0.0",
                    depends_on=["path_a", "path_b"],
                ),
            ],
        )

        ctx = _make_ctx()
        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        records = {r.alias: r for r in result.report.nodes}
        assert records["path_a"].status == "ok"
        assert records["path_b"].status == "skip"
        assert records["merge"].status == "ok"

    @pytest.mark.asyncio
    async def test_condition_fail_triggers_abort_fail_fast(self) -> None:
        """Condition on_false=fail with fail_fast aborts remaining tiers."""
        state = ExperimentState(run_id="async-r3", params={"gate": False})
        node = _make_mock_node()
        node.execute.return_value = _ok_outcome(state)

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_async_abort",
            error_policy="fail_fast",
            nodes=[
                NodeInvocation(
                    alias="gate_node",
                    node_id="test.node@1.0.0",
                    condition=NodeCondition(expr="params.gate == true", on_false="fail"),
                ),
                NodeInvocation(
                    alias="after_gate",
                    node_id="test.node@1.0.0",
                    depends_on=["gate_node"],
                ),
            ],
        )

        ctx = _make_ctx()
        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        records = {r.alias: r for r in result.report.nodes}
        assert records["gate_node"].status == "fail"
        assert records["after_gate"].status == "skip"
        assert result.report.status == "fail"
