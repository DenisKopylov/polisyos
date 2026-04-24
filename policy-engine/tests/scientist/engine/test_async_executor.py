"""Tests for polisyos.scientist.engine.async_executor — AsyncWorkflowExecutor."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.engine.registry import NodeRegistry
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec

_FAKE_SHA = "sha256:" + "ab" * 32


def _make_ctx(*, metrics=None):
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
    return ExecutionContext(
        store=store,
        run=run,
        logger=MagicMock(),
        metrics=metrics,
    )


def _make_mock_node(*, node_id="test.node@1.0.0", state_writes=None):
    node = MagicMock()
    node.spec = MagicMock(spec=NodeSpec)
    node.spec.state_reads = []
    node.spec.state_writes = state_writes or []
    node.spec.node_id = node_id
    return node


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAsyncWorkflowExecutor:
    @pytest.mark.asyncio
    async def test_simple_linear_dag(self):
        """A→B→C — same result as sync."""
        state = ExperimentState(run_id="async-test-001")

        node = _make_mock_node()
        node.execute.return_value = NodeOutcome(
            status="ok",
            state=state,
            events=[],
            artifacts=[],
        )

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_linear",
            nodes=[
                NodeInvocation(alias="step_a", node_id="test.node@1.0.0"),
                NodeInvocation(alias="step_b", node_id="test.node@1.0.0", depends_on=["step_a"]),
                NodeInvocation(alias="step_c", node_id="test.node@1.0.0", depends_on=["step_b"]),
            ],
        )

        ctx = _make_ctx()
        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        assert result.report.status == "ok"
        assert len(result.report.nodes) == 3
        assert all(r.status == "ok" for r in result.report.nodes)

    @pytest.mark.asyncio
    async def test_parallel_tier(self):
        """A→(B,C)→D — B and C run in parallel."""
        state = ExperimentState(run_id="async-test-002")

        call_order = []

        def _make_execute(alias):
            def _execute(ctx, st):
                call_order.append(alias)
                return NodeOutcome(status="ok", state=st, events=[], artifacts=[])

            return _execute

        def _get_node(node_id):
            alias = str(node_id).split("@")[0].split(".")[-1]
            node = _make_mock_node(node_id=str(node_id))
            node.execute.side_effect = _make_execute(alias)
            return node

        registry = MagicMock(spec=NodeRegistry)
        registry.get.side_effect = _get_node

        workflow = WorkflowSpec(
            workflow_id="test_parallel",
            nodes=[
                NodeInvocation(alias="a", node_id="test.a@1.0.0"),
                NodeInvocation(alias="b", node_id="test.b@1.0.0", depends_on=["a"]),
                NodeInvocation(alias="c", node_id="test.c@1.0.0", depends_on=["a"]),
                NodeInvocation(alias="d", node_id="test.d@1.0.0", depends_on=["b", "c"]),
            ],
        )

        ctx = _make_ctx()
        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        assert result.report.status == "ok"
        assert len(result.report.nodes) == 4

        # A must be first, D must be last, B and C in middle (any order)
        aliases = [r.alias for r in result.report.nodes]
        assert aliases[0] == "a"
        assert set(aliases[1:3]) == {"b", "c"}
        assert aliases[3] == "d"

    @pytest.mark.asyncio
    async def test_failed_node_blocks_downstream(self):
        """A→B→C — if B fails, C should be skipped."""
        state = ExperimentState(run_id="async-test-003")

        def _get_node(node_id):
            alias = str(node_id).split("@")[0].split(".")[-1]
            node = _make_mock_node(node_id=str(node_id))
            if alias == "b":
                node.execute.return_value = NodeOutcome(
                    status="fail",
                    state=state,
                    events=[],
                    artifacts=[],
                    error=NodeError(code="node.exception", message="b failed"),
                )
            else:
                node.execute.return_value = NodeOutcome(
                    status="ok",
                    state=state,
                    events=[],
                    artifacts=[],
                )
            return node

        registry = MagicMock(spec=NodeRegistry)
        registry.get.side_effect = _get_node

        workflow = WorkflowSpec(
            workflow_id="test_fail",
            nodes=[
                NodeInvocation(alias="a", node_id="test.a@1.0.0"),
                NodeInvocation(alias="b", node_id="test.b@1.0.0", depends_on=["a"]),
                NodeInvocation(alias="c", node_id="test.c@1.0.0", depends_on=["b"]),
            ],
        )

        ctx = _make_ctx()
        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        assert result.report.status == "fail"
        statuses = {r.alias: r.status for r in result.report.nodes}
        assert statuses["a"] == "ok"
        assert statuses["b"] == "fail"
        assert statuses["c"] == "skip"

    @pytest.mark.asyncio
    async def test_max_parallelism_one_degrades_to_sequential(self):
        """max_parallelism=1 → nodes execute sequentially even in parallel tier."""
        state = ExperimentState(run_id="async-test-004")

        order = []

        def _get_node(node_id):
            alias = str(node_id).split("@")[0].split(".")[-1]
            node = _make_mock_node(node_id=str(node_id))

            def _execute(ctx, st):
                order.append(alias)
                return NodeOutcome(status="ok", state=st, events=[], artifacts=[])

            node.execute.side_effect = _execute
            return node

        registry = MagicMock(spec=NodeRegistry)
        registry.get.side_effect = _get_node

        workflow = WorkflowSpec(
            workflow_id="test_seq",
            nodes=[
                NodeInvocation(alias="a", node_id="test.a@1.0.0"),
                NodeInvocation(alias="b", node_id="test.b@1.0.0"),
                NodeInvocation(alias="c", node_id="test.c@1.0.0"),
            ],
        )

        ctx = _make_ctx()
        executor = AsyncWorkflowExecutor(ctx, registry, max_parallelism=1)
        result = await executor.execute(workflow, state)

        assert result.report.status == "ok"
        assert len(order) == 3

    @pytest.mark.asyncio
    async def test_metrics_tier_completed_called(self):
        """Verify record_tier_completed is called for each tier."""
        state = ExperimentState(run_id="async-test-005")

        node = _make_mock_node()
        node.execute.return_value = NodeOutcome(
            status="ok",
            state=state,
            events=[],
            artifacts=[],
        )

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        metrics = MagicMock()
        ctx = _make_ctx(metrics=metrics)

        workflow = WorkflowSpec(
            workflow_id="test_metrics",
            nodes=[
                NodeInvocation(alias="a", node_id="test.node@1.0.0"),
                NodeInvocation(alias="b", node_id="test.node@1.0.0", depends_on=["a"]),
            ],
        )

        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        assert result.report.status == "ok"
        assert metrics.record_tier_completed.call_count == 2
        assert metrics.record_workflow_completed.call_count == 1

    @pytest.mark.asyncio
    async def test_async_executor_persists_via_async_artifact_store_adapter(self, monkeypatch):
        state = ExperimentState(run_id="async-test-persist")
        node = _make_mock_node()
        node.execute.return_value = NodeOutcome(
            status="ok",
            state=state,
            events=[],
            artifacts=[],
        )

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node
        workflow = WorkflowSpec(
            workflow_id="test_async_persist",
            nodes=[NodeInvocation(alias="a", node_id="test.node@1.0.0")],
        )

        seen_kinds: list[str] = []
        original_put_json = AsyncArtifactStoreAdapter.put_json

        async def _tracked_put_json(self, obj, opts, canon_spec=None):
            seen_kinds.append(str(getattr(opts, "kind", "")))
            return await original_put_json(self, obj, opts, canon_spec=canon_spec)

        monkeypatch.setattr(AsyncArtifactStoreAdapter, "put_json", _tracked_put_json)

        ctx = _make_ctx()
        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        assert result.report.status == "ok"
        assert seen_kinds[:3] == [
            "scientist.workflow_spec",
            "scientist.experiment_state",
            "scientist.workflow_report",
        ]

    @pytest.mark.asyncio
    async def test_no_metrics_no_crash(self):
        """When metrics is None, async executor should not crash."""
        state = ExperimentState(run_id="async-test-006")

        node = _make_mock_node()
        node.execute.return_value = NodeOutcome(
            status="ok",
            state=state,
            events=[],
            artifacts=[],
        )

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        ctx = _make_ctx(metrics=None)
        workflow = WorkflowSpec(
            workflow_id="test_no_metrics",
            nodes=[NodeInvocation(alias="a", node_id="test.node@1.0.0")],
        )

        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)
        assert result.report.status == "ok"
