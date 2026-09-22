"""Integration tests for retry in WorkflowExecutor."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.run.context import RunContext
from polisyos.core.run.manifest import RunManifest
from polisyos.core.trace.record import TraceRecord
from polisyos.core.trace.sink import JsonlTraceSink
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


def _make_durable_ctx(tmp_path):
    """Build a real run context for reading back retry trace records."""
    store = MagicMock()
    store.put_json.return_value = ArtifactRef(
        artifact_id=_FAKE_SHA,
        kind="test",
        media_type="application/json",
    )
    store.put_bytes.return_value = ArtifactRef(
        artifact_id=_FAKE_SHA,
        kind="trace",
        media_type="application/jsonl",
    )
    trace_path = tmp_path / "trace.jsonl"
    run = RunContext(
        store=store,
        trace=JsonlTraceSink(trace_path),
        run_manifest=RunManifest(
            run_id="retry-test-terminal",
            registry_bundle=ArtifactRef(
                artifact_id=_FAKE_SHA,
                kind="registry",
                media_type="application/json",
            ),
        ),
        _trace_path=trace_path,
    )
    return ExecutionContext(store=store, run=run, logger=MagicMock()), trace_path


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

    def test_terminal_raised_retry_preserves_only_spend_in_final_result(self, tmp_path):
        """Terminal retry keeps failed cost/history, not ordinary failed writes."""
        state = ExperimentState(
            run_id="retry-test-terminal",
            params={"keep": "baseline"},
            budgets={"prior_spent_usd": Decimal("1.00")},
        )
        node = MagicMock()
        node.spec.state_reads = []
        node.spec.state_writes = [
            "params.counter",
            "params.attempt_history",
            "budgets",
        ]
        node.spec.node_id = "test.costed_failure@1.0.0"
        calls = {"n": 0}

        def _execute(_ctx, attempt_state):
            calls["n"] += 1
            attempt_state.params["counter"] = int(
                attempt_state.params.get("counter", 0)
            ) + 1
            attempt_state.params.setdefault("attempt_history", []).append(calls["n"])
            attempt_state.budgets["run_spent_usd"] = attempt_state.budgets.get(
                "run_spent_usd",
                Decimal("0"),
            ) + Decimal("0.25")
            raise RuntimeError("terminal after an attempt-side effect")

        node.execute.side_effect = _execute
        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node
        workflow = WorkflowSpec(
            workflow_id="test_retry_terminal_spend",
            nodes=[
                NodeInvocation(
                    alias="costed_failure",
                    node_id="test.costed_failure@1.0.0",
                    retry=RetryPolicy(
                        max_retries=1,
                        backoff_base_s=0.1,
                        backoff_factor=1.0,
                        jitter="none",
                    ),
                ),
            ],
        )
        context, trace_path = _make_durable_ctx(tmp_path)

        with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
            result = WorkflowExecutor(context, registry).execute(workflow, state)

        assert result.report.status == "fail"
        assert result.report.nodes[0].status == "fail"
        assert calls["n"] == 2
        assert result.state.params == {"keep": "baseline"}
        assert result.state.budgets["prior_spent_usd"] == Decimal("1.00")
        assert result.state.budgets["run_spent_usd"] == Decimal("0.50")
        assert state.params == {"keep": "baseline"}
        assert state.budgets == {"prior_spent_usd": Decimal("1.00")}

        records = [
            TraceRecord.model_validate_json(line)
            for line in trace_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        retry_events = [record for record in records if record.event == "NODE_RETRY"]
        dead_letter_events = [
            record for record in records if record.event == "NODE_DEAD_LETTER"
        ]
        assert len(retry_events) == 1
        assert retry_events[0].metrics["attempt"] == 1
        assert retry_events[0].metrics["failed_cost_usd"] == 0.25
        assert len(dead_letter_events) == 1
        assert dead_letter_events[0].metrics["attempts"] == 2
        assert dead_letter_events[0].metrics["failed_cost_usd"] == 0.5

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
