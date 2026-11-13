"""Integration tests for retry in WorkflowExecutor."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.core.trace.record import TraceRecord
from polisyos.scientist.orchestration.engine import retry as retry_module
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.retry import RetryPolicy
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


class _FixtureNode:
    """Supply real component metadata around a test-owned retry callback."""

    def __init__(self, node_id, execute, *, write_paths=()):
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse(node_id),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Retry integration fixture",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_writes=list(write_paths),
        )
        self._execute = execute

    def execute(self, ctx, state):
        return self._execute(ctx, state)


def _make_ctx(tmp_path, *, run_id, metrics=None):
    context, _trace_path = _make_durable_ctx(tmp_path, run_id=run_id, metrics=metrics)
    return context


def _make_durable_ctx(tmp_path, *, run_id="retry-test-terminal", metrics=None):
    """Build a real run context for reading back retry trace records."""
    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store, return_selected_profile=True)
    run = RunContext.start(
        store=store,
        registry_bundle=bundle.bundle_ref,
        run_id=run_id,
        run_dir=tmp_path / "run",
    )
    return ExecutionContext(
        store=store, run=run, logger=MagicMock(), metrics=metrics
    ), run.trace_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRetryIntegration:
    def test_node_with_retry_succeeds_after_failure(self, tmp_path):
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

        node = _FixtureNode("test.flaky@1.0.0", _flaky_execute)

        registry = NodeRegistry()
        registry.register(node)

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

        ctx = _make_ctx(tmp_path, run_id=state.run_id)
        with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
            executor = WorkflowExecutor(ctx, registry)
            result = executor.execute(workflow, state)

        assert result.report.status == "ok"
        assert call_count["n"] == 3

    def test_node_with_retry_exhausted(self, tmp_path):
        state = ExperimentState(run_id="retry-test-002")

        node = _FixtureNode(
            "test.always_fail@1.0.0",
            lambda _ctx, attempt_state: NodeOutcome(
                status="fail",
                state=attempt_state,
                error=NodeError(code="node.exception", message="always fails"),
            ),
        )

        registry = NodeRegistry()
        registry.register(node)

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

        ctx = _make_ctx(tmp_path, run_id=state.run_id)
        with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
            executor = WorkflowExecutor(ctx, registry)
            result = executor.execute(workflow, state)

        assert result.report.status == "fail"
        assert result.report.nodes[0].status == "fail"

    @pytest.mark.parametrize("failure_mode", ["raise", "return"])
    def test_terminal_raised_retry_preserves_only_spend_in_final_result(
        self,
        tmp_path,
        failure_mode,
    ):
        """Terminal raised and returned failures keep cost, not ordinary writes."""
        state = ExperimentState(
            run_id="retry-test-terminal",
            params={"keep": "baseline"},
            budgets={"prior_spent_usd": Decimal("1.00")},
        )
        from polisyos.scientist.orchestration.engine.state_branching import snapshot_state

        rows = [{"value": "baseline"}]
        state.params["config"] = {"left": rows, "right": rows}
        sibling = snapshot_state(state)
        write_paths = [
            "params.counter",
            "params.attempt_history",
            "params.config",
            "budgets",
        ]
        calls = {"n": 0}

        def _execute(_ctx, attempt_state):
            calls["n"] += 1
            attempt_state.params["counter"] = int(attempt_state.params.get("counter", 0)) + 1
            attempt_state.params.setdefault("attempt_history", []).append(calls["n"])
            assert attempt_state.params["config"]["left"] is attempt_state.params["config"]["right"]
            assert attempt_state.params["config"]["left"] == [{"value": "baseline"}]
            attempt_state.params["config"]["left"][0]["value"] = "uncommitted"
            attempt_state.budgets["run_spent_usd"] = attempt_state.budgets.get(
                "run_spent_usd",
                Decimal("0"),
            ) + Decimal("0.25")
            if failure_mode == "raise":
                raise RuntimeError("terminal after an attempt-side effect")
            return NodeOutcome(
                status="fail",
                state=attempt_state,
                events=[],
                artifacts=[],
                error=NodeError(
                    code="node.exception",
                    message="terminal after an attempt-side effect",
                ),
            )

        class CostedFailureNode:
            spec = NodeSpec(
                metadata=ComponentMetadata(
                    component_id=ComponentId.parse("test.costed_failure@1.0.0"),
                    kind=ComponentKind.SCIENTIST_NODE,
                    abi_targets={"world_abi": "1.x"},
                    display_name="Retry terminal fixture",
                    capabilities=Capability.SCIENTIST_NODE,
                ),
                state_writes=write_paths,
            )

            def execute(self, ctx, attempt_state):
                return _execute(ctx, attempt_state)

        registry = NodeRegistry()
        registry.register(CostedFailureNode())
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
        expected_params = {
            "keep": "baseline",
            "config": {"left": [{"value": "baseline"}], "right": [{"value": "baseline"}]},
        }
        assert result.state.params == expected_params
        assert result.state.params["config"]["left"] is result.state.params["config"]["right"]
        assert result.state.budgets["prior_spent_usd"] == Decimal("1.00")
        assert result.state.budgets["run_spent_usd"] == Decimal("0.50")
        assert state.params == expected_params
        assert state.budgets == {"prior_spent_usd": Decimal("1.00")}
        assert sibling.params == expected_params
        assert sibling.params["config"]["left"] is sibling.params["config"]["right"]
        assert sibling.params["config"]["left"] is not rows
        assert sibling.budgets == {"prior_spent_usd": Decimal("1.00")}

        records = [
            TraceRecord.model_validate_json(line)
            for line in trace_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        retry_events = [record for record in records if record.event == "NODE_RETRY"]
        dead_letter_events = [record for record in records if record.event == "NODE_DEAD_LETTER"]
        assert len(retry_events) == 1
        assert retry_events[0].metrics["attempt"] == 1
        assert retry_events[0].metrics["failed_cost_usd"] == 0.25
        if failure_mode == "raise":
            assert len(dead_letter_events) == 1
            assert dead_letter_events[0].metrics["attempts"] == 2
            assert dead_letter_events[0].metrics["failed_cost_usd"] == 0.5
        else:
            assert dead_letter_events == []

    @pytest.mark.skipif(
        retry_module._timeout_worker_start_method() != "fork",
        reason="blocking fixture node needs native fork; macOS spawn admits only two canonical nodes",
    )
    def test_node_with_timeout(self, tmp_path):
        import time as _time

        state = ExperimentState(run_id="retry-test-003")

        calls = []

        def slow_execute(_ctx, attempt_state):
            calls.append("work")
            _time.sleep(5)
            return NodeOutcome(status="ok", state=attempt_state)

        node = _FixtureNode("test.slow@1.0.0", slow_execute)

        registry = NodeRegistry()
        registry.register(node)

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

        ctx = _make_ctx(tmp_path, run_id=state.run_id)
        executor = WorkflowExecutor(ctx, registry)
        result = executor.execute(workflow, state)

        assert result.report.status == "fail"
        assert result.report.nodes[0].error is not None
        assert result.report.nodes[0].error.code == "node.timeout"

    def test_node_retry_events_in_trace(self, tmp_path):
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

        node = _FixtureNode("test.retry_once@1.0.0", _execute)

        registry = NodeRegistry()
        registry.register(node)

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

        ctx = _make_ctx(tmp_path, run_id=state.run_id)
        with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
            executor = WorkflowExecutor(ctx, registry)
            result = executor.execute(workflow, state)

        assert result.report.status == "ok"

        records = [
            TraceRecord.model_validate_json(line)
            for line in ctx.run.trace_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        retry_events = [record for record in records if record.event == "NODE_RETRY"]
        assert len(retry_events) == 1

    def test_no_retry_field_backward_compat(self, tmp_path):
        """NodeInvocation with no retry field should work (default None → RetryPolicy())."""
        state = ExperimentState(run_id="retry-test-005")

        node = _FixtureNode(
            "test.simple@1.0.0",
            lambda _ctx, attempt_state: NodeOutcome(status="ok", state=attempt_state),
        )

        registry = NodeRegistry()
        registry.register(node)

        workflow = WorkflowSpec(
            workflow_id="test_no_retry",
            nodes=[
                NodeInvocation(alias="simple", node_id="test.simple@1.0.0"),
            ],
        )

        ctx = _make_ctx(tmp_path, run_id=state.run_id)
        executor = WorkflowExecutor(ctx, registry)
        result = executor.execute(workflow, state)
        assert result.report.status == "ok"
