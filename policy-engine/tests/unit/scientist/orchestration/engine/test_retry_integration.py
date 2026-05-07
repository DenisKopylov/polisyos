"""Integration tests for retry in WorkflowExecutor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.retry import RetryPolicy
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRetryIntegration:
    def test_node_with_retry_succeeds_after_failure(self):
        state = ExperimentState(run_id="retry-test-001")

        call_count = {"n": 0}

        def _flaky_execute(ctx, st):
            call_count["n"] += 1
            if call_count["n"] < 3:
                return NodeOutcome(
                    status="fail",
                    state=st,
                    events=[],
                    artifacts=[],
                    error=NodeError(code="node.exception", message="transient"),
                )
            return NodeOutcome(status="ok", state=st, events=[], artifacts=[])

        node = MagicMock()
        node.spec.state_reads = []
        node.spec.state_writes = []
        node.spec.node_id = "test.flaky@1.0.0"
        node.execute.side_effect = _flaky_execute

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_retry_wf",
            nodes=[
                NodeInvocation(
                    alias="flaky_node",
                    node_id="test.flaky@1.0.0",
                    retry=RetryPolicy(max_retries=3, backoff_base_s=0.1, backoff_factor=1.0),
                ),
            ],
        )

        ctx = _make_ctx()
        with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
            executor = WorkflowExecutor(ctx, registry)
            result = executor.execute(workflow, state)

        assert result.report.status == "ok"
        assert call_count["n"] == 3

    def test_node_with_retry_exhausted(self):
        state = ExperimentState(run_id="retry-test-002")

        node = MagicMock()
        node.spec.state_reads = []
        node.spec.state_writes = []
        node.spec.node_id = "test.always_fail@1.0.0"
        node.execute.return_value = NodeOutcome(
            status="fail",
            state=state,
            events=[],
            artifacts=[],
            error=NodeError(code="node.exception", message="always fails"),
        )

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_retry_exhausted",
            nodes=[
                NodeInvocation(
                    alias="always_fail",
                    node_id="test.always_fail@1.0.0",
                    retry=RetryPolicy(max_retries=2, backoff_base_s=0.1, backoff_factor=1.0),
                ),
            ],
        )

        ctx = _make_ctx()
        with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
            executor = WorkflowExecutor(ctx, registry)
            result = executor.execute(workflow, state)

        assert result.report.status == "fail"
        assert result.report.nodes[0].status == "fail"

    def test_node_with_timeout(self):
        import time as _time

        state = ExperimentState(run_id="retry-test-003")

        node = MagicMock()
        node.spec.state_reads = []
        node.spec.state_writes = []
        node.spec.node_id = "test.slow@1.0.0"
        node.execute.side_effect = lambda ctx, st: (
            _time.sleep(5),
            NodeOutcome(status="ok", state=st, events=[], artifacts=[]),
        )[1]

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_timeout_wf",
            nodes=[
                NodeInvocation(
                    alias="slow_node",
                    node_id="test.slow@1.0.0",
                    timeout_s=1.0,
                ),
            ],
        )

        ctx = _make_ctx()
        executor = WorkflowExecutor(ctx, registry)
        result = executor.execute(workflow, state)

        assert result.report.status == "fail"
        assert result.report.nodes[0].error is not None
        assert result.report.nodes[0].error.code == "node.timeout"

    def test_node_retry_events_in_trace(self):
        state = ExperimentState(run_id="retry-test-004")

        call_count = {"n": 0}

        def _execute(ctx, st):
            call_count["n"] += 1
            if call_count["n"] < 2:
                return NodeOutcome(
                    status="fail",
                    state=st,
                    events=[],
                    artifacts=[],
                    error=NodeError(code="node.exception", message="once"),
                )
            return NodeOutcome(status="ok", state=st, events=[], artifacts=[])

        node = MagicMock()
        node.spec.state_reads = []
        node.spec.state_writes = []
        node.spec.node_id = "test.retry_once@1.0.0"
        node.execute.side_effect = _execute

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_retry_events",
            nodes=[
                NodeInvocation(
                    alias="retry_node",
                    node_id="test.retry_once@1.0.0",
                    retry=RetryPolicy(max_retries=2, backoff_base_s=0.1, backoff_factor=1.0),
                ),
            ],
        )

        ctx = _make_ctx()
        with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
            executor = WorkflowExecutor(ctx, registry)
            result = executor.execute(workflow, state)

        assert result.report.status == "ok"

        # Check NODE_RETRY events
        retry_events = [
            c for c in ctx.run.emit.call_args_list if len(c[0]) >= 2 and c[0][1] == "NODE_RETRY"
        ]
        assert len(retry_events) == 1

    def test_no_retry_field_backward_compat(self):
        """NodeInvocation with no retry field should work (default None → RetryPolicy())."""
        state = ExperimentState(run_id="retry-test-005")

        node = MagicMock()
        node.spec.state_reads = []
        node.spec.state_writes = []
        node.spec.node_id = "test.simple@1.0.0"
        node.execute.return_value = NodeOutcome(
            status="ok",
            state=state,
            events=[],
            artifacts=[],
        )

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_no_retry",
            nodes=[
                NodeInvocation(alias="simple", node_id="test.simple@1.0.0"),
            ],
        )

        ctx = _make_ctx()
        executor = WorkflowExecutor(ctx, registry)
        result = executor.execute(workflow, state)
        assert result.report.status == "ok"
