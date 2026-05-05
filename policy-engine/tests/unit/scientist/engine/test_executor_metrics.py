"""Tests for metrics integration in WorkflowExecutor."""

from __future__ import annotations

from unittest.mock import MagicMock

from polisyos.scientist.engine.metrics_protocol import NoopEngineMetrics

# ---------------------------------------------------------------------------
# Recording mock metrics → run simple workflow → verify calls
# ---------------------------------------------------------------------------


class TestExecutorMetricsCalls:
    """Verify the executor calls metrics methods at the right points."""

    def _make_mock_metrics(self):
        m = MagicMock(spec=NoopEngineMetrics)
        m.record_node_started = MagicMock()
        m.record_node_completed = MagicMock()
        m.record_tier_completed = MagicMock()
        m.record_workflow_completed = MagicMock()
        return m

    def _build_minimal_executor(self, metrics):
        """Build a WorkflowExecutor with mocked context that uses given metrics."""
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.scientist.engine.context import ExecutionContext
        from polisyos.scientist.engine.executor import WorkflowExecutor
        from polisyos.scientist.engine.protocol import NodeOutcome
        from polisyos.scientist.engine.registry import NodeRegistry
        from polisyos.scientist.engine.state import ExperimentState
        from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec

        _fake_sha = "sha256:" + "ab" * 32

        store = MagicMock()
        store.put_json.return_value = ArtifactRef(
            artifact_id=_fake_sha,
            kind="test",
            media_type="application/json",
        )

        run = MagicMock()
        run.emit = MagicMock()
        run.add_input = MagicMock()
        run.add_output = MagicMock()
        run.trace_path = None
        run.finalize = MagicMock(
            return_value=ArtifactRef(
                artifact_id=_fake_sha,
                kind="run",
                media_type="application/json",
            )
        )

        logger = MagicMock()

        ctx = ExecutionContext(
            store=store,
            run=run,
            logger=logger,
            metrics=metrics,
        )

        state = ExperimentState(run_id="test-run-001")

        # Create a mock node
        mock_node = MagicMock()
        mock_node.spec.state_reads = []
        mock_node.spec.state_writes = []
        mock_node.spec.node_id = "test.node@1.0.0"
        mock_outcome = NodeOutcome(status="ok", state=state, events=[], artifacts=[])
        mock_node.execute.return_value = mock_outcome

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = mock_node

        workflow = WorkflowSpec(
            workflow_id="test_wf",
            nodes=[
                NodeInvocation(alias="step_a", node_id="test.node@1.0.0"),
                NodeInvocation(alias="step_b", node_id="test.node@1.0.0", depends_on=["step_a"]),
            ],
        )

        executor = WorkflowExecutor(ctx, registry)
        return executor, workflow, state

    def test_node_started_called_per_node(self):
        metrics = self._make_mock_metrics()
        executor, workflow, state = self._build_minimal_executor(metrics)
        executor.execute(workflow, state)
        assert metrics.record_node_started.call_count == 2

    def test_node_completed_called_per_node(self):
        metrics = self._make_mock_metrics()
        executor, workflow, state = self._build_minimal_executor(metrics)
        executor.execute(workflow, state)
        assert metrics.record_node_completed.call_count == 2

    def test_node_completed_kwargs(self):
        metrics = self._make_mock_metrics()
        executor, workflow, state = self._build_minimal_executor(metrics)
        executor.execute(workflow, state)
        call_kwargs = metrics.record_node_completed.call_args_list[0][1]
        assert call_kwargs["alias"] == "step_a"
        assert call_kwargs["workflow_id"] == "test_wf"
        assert call_kwargs["status"] == "ok"
        assert call_kwargs["cache_hit"] is False
        assert call_kwargs["retry_count"] == 0
        assert isinstance(call_kwargs["duration_ms"], int)

    def test_workflow_completed_called_once(self):
        metrics = self._make_mock_metrics()
        executor, workflow, state = self._build_minimal_executor(metrics)
        executor.execute(workflow, state)
        assert metrics.record_workflow_completed.call_count == 1

    def test_workflow_completed_kwargs(self):
        metrics = self._make_mock_metrics()
        executor, workflow, state = self._build_minimal_executor(metrics)
        executor.execute(workflow, state)
        call_kwargs = metrics.record_workflow_completed.call_args[1]
        assert call_kwargs["workflow_id"] == "test_wf"
        assert call_kwargs["status"] == "ok"
        assert call_kwargs["node_count"] == 2
        assert isinstance(call_kwargs["duration_ms"], int)

    def test_no_metrics_no_crash(self):
        """When metrics is None, executor should not crash."""
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.scientist.engine.context import ExecutionContext
        from polisyos.scientist.engine.executor import WorkflowExecutor
        from polisyos.scientist.engine.protocol import NodeOutcome
        from polisyos.scientist.engine.registry import NodeRegistry
        from polisyos.scientist.engine.state import ExperimentState
        from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec

        _fake_sha = "sha256:" + "ab" * 32
        store = MagicMock()
        store.put_json.return_value = ArtifactRef(
            artifact_id=_fake_sha,
            kind="test",
            media_type="application/json",
        )
        run = MagicMock()
        run.trace_path = None
        run.finalize.return_value = ArtifactRef(
            artifact_id=_fake_sha,
            kind="run",
            media_type="application/json",
        )

        ctx = ExecutionContext(store=store, run=run, logger=MagicMock(), metrics=None)
        state = ExperimentState(run_id="test-run-002")

        mock_node = MagicMock()
        mock_node.spec.state_reads = []
        mock_node.spec.state_writes = []
        mock_node.spec.node_id = "test.node@1.0.0"
        mock_node.execute.return_value = NodeOutcome(
            status="ok",
            state=state,
            events=[],
            artifacts=[],
        )

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = mock_node

        workflow = WorkflowSpec(
            workflow_id="wf",
            nodes=[NodeInvocation(alias="step_a", node_id="test.node@1.0.0")],
        )

        executor = WorkflowExecutor(ctx, registry)
        result = executor.execute(workflow, state)
        assert result.report.status == "ok"

    def test_failed_node_records_fail_status(self):
        metrics = self._make_mock_metrics()

        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.scientist.engine.context import ExecutionContext
        from polisyos.scientist.engine.executor import WorkflowExecutor
        from polisyos.scientist.engine.registry import NodeRegistry
        from polisyos.scientist.engine.state import ExperimentState
        from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec

        _fake_sha = "sha256:" + "ab" * 32
        store = MagicMock()
        store.put_json.return_value = ArtifactRef(
            artifact_id=_fake_sha,
            kind="test",
            media_type="application/json",
        )
        run = MagicMock()
        run.trace_path = None
        run.finalize.return_value = ArtifactRef(
            artifact_id=_fake_sha,
            kind="run",
            media_type="application/json",
        )

        ctx = ExecutionContext(store=store, run=run, logger=MagicMock(), metrics=metrics)
        state = ExperimentState(run_id="test-run-003")

        mock_node = MagicMock()
        mock_node.spec.state_reads = []
        mock_node.spec.state_writes = []
        mock_node.spec.node_id = "test.fail@1.0.0"
        mock_node.execute.side_effect = RuntimeError("boom")

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = mock_node

        workflow = WorkflowSpec(
            workflow_id="wf_fail",
            nodes=[NodeInvocation(alias="failing_node", node_id="test.fail@1.0.0")],
        )

        executor = WorkflowExecutor(ctx, registry)
        result = executor.execute(workflow, state)

        assert metrics.record_node_completed.call_count == 1
        call_kwargs = metrics.record_node_completed.call_args[1]
        assert call_kwargs["status"] == "fail"
        assert call_kwargs["alias"] == "failing_node"

        assert metrics.record_workflow_completed.call_count == 1
        wf_kwargs = metrics.record_workflow_completed.call_args[1]
        assert wf_kwargs["status"] == "fail"
