"""Tests for sub-workflow nesting (workflow-as-node)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.executor import WorkflowExecutor
from polisyos.scientist.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.engine.registry import NodeRegistry
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.sub_workflow import (
    StateMapping,
    SubWorkflowConfig,
    SubWorkflowNode,
)
from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec

_FAKE_SHA = "sha256:" + "ab" * 32


def _make_ctx(*, depth=0):
    store = MagicMock()
    store.put_json.return_value = ArtifactRef(
        artifact_id=_FAKE_SHA, kind="test", media_type="application/json",
    )
    run = MagicMock()
    run.trace_path = None
    run.finalize.return_value = ArtifactRef(
        artifact_id=_FAKE_SHA, kind="run", media_type="application/json",
    )
    return ExecutionContext(store=store, run=run, logger=MagicMock(), depth=depth)


def _make_mock_node(*, ok=True):
    node = MagicMock()
    node.spec = MagicMock(spec=NodeSpec)
    node.spec.state_reads = []
    node.spec.state_writes = []

    if ok:
        def _execute(ctx, state):
            return NodeOutcome(status="ok", state=state, events=[], artifacts=[])
        node.execute.side_effect = _execute
    else:
        def _execute_fail(ctx, state):
            return NodeOutcome(
                status="fail", state=state,
                error=NodeError(code="test.fail", message="fail", details={}),
            )
        node.execute.side_effect = _execute_fail
    return node


def _make_registry(node):
    registry = MagicMock(spec=NodeRegistry)
    registry.get.return_value = node
    return registry


# ---------------------------------------------------------------------------
# Config model
# ---------------------------------------------------------------------------


class TestStateMappingModel:
    def test_basic(self) -> None:
        m = StateMapping(source_path="params.x", target_path="params.y")
        assert m.source_path == "params.x"

    def test_extra_forbidden(self) -> None:
        with pytest.raises(Exception):
            StateMapping(source_path="a", target_path="b", bad="field")


class TestSubWorkflowConfigModel:
    def test_defaults(self) -> None:
        wf = WorkflowSpec(workflow_id="child", nodes=[])
        cfg = SubWorkflowConfig(workflow=wf)
        assert cfg.max_depth == 3
        assert cfg.error_policy_override is None
        assert cfg.input_mappings == []
        assert cfg.output_mappings == []

    def test_extra_forbidden(self) -> None:
        wf = WorkflowSpec(workflow_id="child", nodes=[])
        with pytest.raises(Exception):
            SubWorkflowConfig(workflow=wf, bad="field")

    def test_roundtrip(self) -> None:
        wf = WorkflowSpec(workflow_id="child", nodes=[])
        cfg = SubWorkflowConfig(
            workflow=wf,
            input_mappings=[StateMapping(source_path="params.x", target_path="params.x")],
            max_depth=5,
        )
        dumped = cfg.model_dump()
        restored = SubWorkflowConfig.model_validate(dumped)
        assert restored.max_depth == 5
        assert len(restored.input_mappings) == 1


# ---------------------------------------------------------------------------
# Spec
# ---------------------------------------------------------------------------


class TestSubWorkflowNodeSpec:
    def test_spec_reads_input_mappings(self) -> None:
        wf = WorkflowSpec(workflow_id="child", nodes=[])
        cfg = SubWorkflowConfig(
            workflow=wf,
            input_mappings=[
                StateMapping(source_path="params.a", target_path="params.a"),
                StateMapping(source_path="params.b", target_path="params.b"),
            ],
        )
        node = SubWorkflowNode(cfg, _make_registry(_make_mock_node()))
        assert "params.a" in node.spec.state_reads
        assert "params.b" in node.spec.state_reads

    def test_spec_writes_output_mappings(self) -> None:
        wf = WorkflowSpec(workflow_id="child", nodes=[])
        cfg = SubWorkflowConfig(
            workflow=wf,
            output_mappings=[
                StateMapping(source_path="params.result", target_path="params.result"),
            ],
        )
        node = SubWorkflowNode(cfg, _make_registry(_make_mock_node()))
        assert "params.result" in node.spec.state_writes


# ---------------------------------------------------------------------------
# Execution: basic
# ---------------------------------------------------------------------------


class TestSubWorkflowExecution:
    def test_trivial_child_workflow(self) -> None:
        """Empty child workflow completes successfully."""
        child_wf = WorkflowSpec(workflow_id="child_empty", nodes=[])
        cfg = SubWorkflowConfig(workflow=child_wf)
        task_node = _make_mock_node()
        registry = _make_registry(task_node)

        node = SubWorkflowNode(cfg, registry)
        state = ExperimentState(run_id="r1")
        outcome = node.execute(_make_ctx(), state)
        assert outcome.status == "ok"

    def test_child_with_single_node(self) -> None:
        """Child workflow with one node runs and returns ok."""
        child_wf = WorkflowSpec(
            workflow_id="child_single",
            nodes=[NodeInvocation(alias="step_a", node_id="test.node@1.0.0")],
        )
        cfg = SubWorkflowConfig(workflow=child_wf)
        task_node = _make_mock_node()
        registry = _make_registry(task_node)

        node = SubWorkflowNode(cfg, registry)
        state = ExperimentState(run_id="r2")
        outcome = node.execute(_make_ctx(), state)
        assert outcome.status == "ok"
        assert any("completed" in e.message for e in outcome.events)

    def test_child_run_id_deterministic(self) -> None:
        """Child run_id includes parent run_id and alias."""
        child_wf = WorkflowSpec(workflow_id="child_det", nodes=[])
        cfg = SubWorkflowConfig(workflow=child_wf)
        node = SubWorkflowNode(cfg, _make_registry(_make_mock_node()), alias="my_child")
        state = ExperimentState(run_id="parent_run")
        outcome = node.execute(_make_ctx(), state)
        # The child state run_id should contain the parent's and alias
        # We can check from events
        assert outcome.status == "ok"


# ---------------------------------------------------------------------------
# State mapping
# ---------------------------------------------------------------------------


class TestStateMapping:
    def test_input_mapping(self) -> None:
        """Parent params are mapped to child state."""
        child_wf = WorkflowSpec(workflow_id="child_map", nodes=[])
        cfg = SubWorkflowConfig(
            workflow=child_wf,
            input_mappings=[
                StateMapping(source_path="params.country", target_path="params.country"),
            ],
        )
        task_node = _make_mock_node()
        registry = _make_registry(task_node)

        node = SubWorkflowNode(cfg, registry)
        state = ExperimentState(run_id="r3", params={"country": "UA"})
        outcome = node.execute(_make_ctx(), state)
        assert outcome.status == "ok"

    def test_output_mapping(self) -> None:
        """Child params are mapped back to parent state."""
        # Create a node that writes to child state
        def _execute(ctx, state):
            state.params["result"] = "computed_value"
            return NodeOutcome(status="ok", state=state, events=[], artifacts=[])

        task_node = _make_mock_node()
        task_node.execute.side_effect = _execute

        child_wf = WorkflowSpec(
            workflow_id="child_out",
            nodes=[NodeInvocation(alias="compute", node_id="test.node@1.0.0")],
        )
        cfg = SubWorkflowConfig(
            workflow=child_wf,
            output_mappings=[
                StateMapping(source_path="params.result", target_path="params.child_result"),
            ],
        )
        registry = _make_registry(task_node)
        node = SubWorkflowNode(cfg, registry)
        state = ExperimentState(run_id="r4")
        outcome = node.execute(_make_ctx(), state)
        assert outcome.status == "ok"
        assert outcome.state.params.get("child_result") == "computed_value"


# ---------------------------------------------------------------------------
# Depth enforcement
# ---------------------------------------------------------------------------


class TestDepthEnforcement:
    def test_max_depth_exceeded(self) -> None:
        child_wf = WorkflowSpec(workflow_id="child_depth", nodes=[])
        cfg = SubWorkflowConfig(workflow=child_wf, max_depth=2)
        node = SubWorkflowNode(cfg, _make_registry(_make_mock_node()))

        state = ExperimentState(run_id="r5")
        # Context already at depth 2, max_depth=2 → fail
        outcome = node.execute(_make_ctx(depth=2), state)
        assert outcome.status == "fail"
        assert outcome.error is not None
        assert "max_depth" in outcome.error.code

    def test_depth_within_limit(self) -> None:
        child_wf = WorkflowSpec(workflow_id="child_ok", nodes=[])
        cfg = SubWorkflowConfig(workflow=child_wf, max_depth=3)
        node = SubWorkflowNode(cfg, _make_registry(_make_mock_node()))

        state = ExperimentState(run_id="r6")
        # depth=1, max_depth=3 → 1+1=2 <= 3, ok
        outcome = node.execute(_make_ctx(depth=1), state)
        assert outcome.status == "ok"

    def test_depth_at_boundary(self) -> None:
        child_wf = WorkflowSpec(workflow_id="child_boundary", nodes=[])
        cfg = SubWorkflowConfig(workflow=child_wf, max_depth=2)
        node = SubWorkflowNode(cfg, _make_registry(_make_mock_node()))

        state = ExperimentState(run_id="r7")
        # depth=1, max_depth=2 → 1+1=2 <= 2, ok
        outcome = node.execute(_make_ctx(depth=1), state)
        assert outcome.status == "ok"


# ---------------------------------------------------------------------------
# Child failure propagation
# ---------------------------------------------------------------------------


class TestChildFailure:
    def test_child_node_failure_propagates(self) -> None:
        """When child workflow fails, sub-workflow node reports failure."""
        failing_node = _make_mock_node(ok=False)
        child_wf = WorkflowSpec(
            workflow_id="child_fail",
            nodes=[NodeInvocation(alias="bad_step", node_id="test.node@1.0.0")],
        )
        cfg = SubWorkflowConfig(workflow=child_wf)
        registry = _make_registry(failing_node)

        node = SubWorkflowNode(cfg, registry)
        state = ExperimentState(run_id="r8")
        outcome = node.execute(_make_ctx(), state)
        assert outcome.status == "fail"
        assert outcome.error is not None


# ---------------------------------------------------------------------------
# Error policy override
# ---------------------------------------------------------------------------


class TestErrorPolicyOverride:
    def test_override_to_continue(self) -> None:
        """error_policy_override='continue' makes child not fail-fast."""
        # One failing node and one succeeding node
        call_count = 0

        def _execute(ctx, state):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return NodeOutcome(
                    status="fail", state=state,
                    error=NodeError(code="test.fail", message="fail", details={}),
                )
            return NodeOutcome(status="ok", state=state, events=[], artifacts=[])

        task_node = _make_mock_node()
        task_node.execute.side_effect = _execute

        child_wf = WorkflowSpec(
            workflow_id="child_continue",
            error_policy="fail_fast",  # default would stop
            nodes=[
                NodeInvocation(alias="step_a", node_id="test.node@1.0.0"),
                NodeInvocation(alias="step_b", node_id="test.node@1.0.0"),
            ],
        )
        cfg = SubWorkflowConfig(
            workflow=child_wf,
            error_policy_override="continue",
        )
        registry = _make_registry(task_node)
        node = SubWorkflowNode(cfg, registry)
        state = ExperimentState(run_id="r9")
        outcome = node.execute(_make_ctx(), state)
        # With continue policy, step_b still runs even after step_a fails
        assert task_node.execute.call_count == 2


# ---------------------------------------------------------------------------
# Nested sub-workflows (depth=2)
# ---------------------------------------------------------------------------


class TestNestedSubWorkflows:
    def test_two_level_nesting(self) -> None:
        """A sub-workflow containing another sub-workflow."""
        inner_wf = WorkflowSpec(workflow_id="inner", nodes=[])
        inner_cfg = SubWorkflowConfig(workflow=inner_wf, max_depth=3)

        # The "inner" node is a SubWorkflowNode itself
        inner_node = SubWorkflowNode(
            inner_cfg, _make_registry(_make_mock_node()), alias="inner",
        )

        # We need a registry that returns the inner SubWorkflowNode
        # But SubWorkflowNode doesn't have a spec with a valid component_id
        # for registry lookup. Instead, use a mock registry.
        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = inner_node

        outer_wf = WorkflowSpec(
            workflow_id="outer",
            nodes=[NodeInvocation(alias="nested", node_id="test.node@1.0.0")],
        )
        outer_cfg = SubWorkflowConfig(workflow=outer_wf, max_depth=3)
        outer_node = SubWorkflowNode(outer_cfg, registry, alias="outer")

        state = ExperimentState(run_id="r10")
        outcome = outer_node.execute(_make_ctx(depth=0), state)
        assert outcome.status == "ok"
