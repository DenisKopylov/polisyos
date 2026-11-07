"""Tests for sub-workflow nesting (workflow-as-node)."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run import RunContext
from polisyos.core.run.manifest import RunManifest
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import (
    WorkflowExecutionResult,
    WorkflowExecutor,
    WorkflowReport,
)
from polisyos.scientist.orchestration.engine.protocol import (
    InputAwareNodeSpec,
    NodeError,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.sub_workflow import (
    StateMapping,
    SubWorkflowConfig,
    SubWorkflowNode,
)
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_FAKE_SHA = "sha256:" + "ab" * 32


def _make_ctx(tmp_path: Path, *, depth=0):
    """Build an unadmitted context only for refusals before any child dispatch."""
    store = FileSystemCAS(tmp_path / "cas")
    run = MagicMock()
    run.trace_path = None
    run.finalize.return_value = ArtifactRef(
        artifact_id=_FAKE_SHA,
        kind="run",
        media_type="application/json",
    )
    return ExecutionContext(store=store, run=run, logger=MagicMock(), depth=depth)


def _make_mock_node(*, ok=True, state_writes: tuple[str, ...] = ()):
    node = MagicMock()
    node.spec = NodeSpec(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse("test.node@1.0.0"),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name="Sub-workflow test child",
            description="A child with exactly declared state writes",
            capabilities=Capability.SCIENTIST_NODE,
        ),
        state_writes=list(state_writes),
    )

    if ok:

        def _execute(ctx, state):
            return NodeOutcome(status="ok", state=state, events=[], artifacts=[])

        node.execute = MagicMock(side_effect=_execute)
    else:

        def _execute_fail(ctx, state):
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="test.fail", message="fail", details={}),
            )

        node.execute = MagicMock(side_effect=_execute_fail)
    return node


def _make_registry(node):
    registry = NodeRegistry()
    registry.register(node)
    return registry


def _run_sub_workflow(
    node: SubWorkflowNode, state: ExperimentState, tmp_path: Path, *, depth: int = 0
) -> WorkflowExecutionResult:
    """Dispatch the composite through its real outer engine and separate child owner."""
    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(store, bundle, run_id=state.run_id)
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.sub_workflow"),
        depth=depth,
    )
    workflow = WorkflowSpec(
        workflow_id="parent_sub_workflow",
        nodes=[NodeInvocation(alias="child", node_id=node.spec.metadata.component_id)],
    )
    return WorkflowExecutor(ctx, _make_registry(node)).execute(workflow, state)


def _assert_completed_child_visible_after_refusal(
    result: WorkflowExecutionResult, tmp_path: Path, *, child_status: str
) -> None:
    """Read the failed parent's actual report without promoting its child evidence."""
    store = FileSystemCAS(tmp_path / "cas")
    report_ref = result.state.reports_index["workflow_report"]
    assert store.verify(report_ref).ok
    report = WorkflowReport.model_validate(from_canonical_bytes(store.get_bytes(report_ref)))
    assert report.run_id == result.state.run_id
    assert report.workflow_id == "parent_sub_workflow"
    assert report.status == "fail"
    assert report.nodes[0].status == "fail"
    child_refs = [ref for ref in report.nodes[0].artifacts if ref.kind == "core.run_manifest"]
    assert len(child_refs) == 1
    assert store.verify(child_refs[0]).ok
    child_manifest = RunManifest.model_validate(
        from_canonical_bytes(store.get_bytes(child_refs[0]))
    )
    assert child_manifest.status == child_status
    assert child_manifest.parent_run_id == result.state.run_id
    assert result.run_ref is not None
    assert store.verify(result.run_ref).ok
    parent_manifest = RunManifest.model_validate(
        from_canonical_bytes(store.get_bytes(result.run_ref))
    )
    assert parent_manifest.run_id == result.state.run_id
    assert parent_manifest.status == "fail"
    assert report_ref in parent_manifest.outputs
    assert child_manifest.run_id != parent_manifest.run_id
    assert child_refs[0] not in parent_manifest.outputs


# ---------------------------------------------------------------------------
# Config model
# ---------------------------------------------------------------------------


class TestStateMappingModel:
    def test_basic(self) -> None:
        m = StateMapping(source_path="params.x", target_path="params.y")
        assert m.source_path == "params.x"

    def test_extra_forbidden(self) -> None:
        with pytest.raises(ValidationError):
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
        with pytest.raises(ValidationError):
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
    def test_repeated_optional_source_has_one_rule_and_two_mappings(self) -> None:
        cfg = SubWorkflowConfig(
            workflow=WorkflowSpec(workflow_id="child", nodes=[]),
            input_mappings=[
                StateMapping(source_path="params.value", target_path="params.left"),
                StateMapping(source_path="params.value", target_path="params.right"),
            ],
        )
        spec = SubWorkflowNode(cfg, _make_registry(_make_mock_node())).spec
        assert isinstance(spec, InputAwareNodeSpec)
        assert spec.state_reads == ["params.value"]
        assert len(spec.input_rules) == 1
        assert spec.input_rules[0].availability == "optional"
        assert spec.input_rules[0].allow_null

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
    def test_direct_execution_without_child_owner_refuses_before_producer(
        self, tmp_path: Path
    ) -> None:
        child = _make_mock_node()
        node = SubWorkflowNode(
            SubWorkflowConfig(
                workflow=WorkflowSpec(
                    workflow_id="unadmitted_child",
                    nodes=[NodeInvocation(alias="step", node_id=child.spec.metadata.component_id)],
                )
            ),
            _make_registry(child),
        )
        state = ExperimentState(run_id="unadmitted_parent", params={"original": "kept"})

        outcome = node.execute(_make_ctx(tmp_path), state)

        assert outcome.status == "fail"
        assert outcome.error is not None
        assert outcome.error.code == "sub_workflow.owner_not_established"
        assert outcome.state is state
        assert state.params == {"original": "kept"}
        child.execute.assert_not_called()

    def test_trivial_child_workflow(self, tmp_path: Path) -> None:
        """Empty child workflow completes successfully."""
        child_wf = WorkflowSpec(workflow_id="child_empty", nodes=[])
        cfg = SubWorkflowConfig(workflow=child_wf)
        task_node = _make_mock_node()
        registry = _make_registry(task_node)

        node = SubWorkflowNode(cfg, registry)
        state = ExperimentState(run_id="r1")
        result = _run_sub_workflow(node, state, tmp_path)
        outcome = result.report.nodes[0]
        assert outcome.status == "ok"

    def test_child_with_single_node(self, tmp_path: Path, caplog) -> None:
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
        caplog.set_level(logging.INFO)
        result = _run_sub_workflow(node, state, tmp_path)
        outcome = result.report.nodes[0]
        assert outcome.status == "ok"
        assert "Sub-workflow 'sub_workflow' completed" in caplog.text

    def test_child_run_id_deterministic(self, tmp_path: Path) -> None:
        """Equivalent parent/dispatch identities select the same child run identity."""
        child_wf = WorkflowSpec(workflow_id="child_det", nodes=[])
        cfg = SubWorkflowConfig(workflow=child_wf)
        node = SubWorkflowNode(cfg, _make_registry(_make_mock_node()), alias="my_child")
        state = ExperimentState(run_id="parent_run")
        child_ids = []
        for directory in (tmp_path / "first", tmp_path / "second"):
            result = _run_sub_workflow(node, state, directory)
            outcome = result.report.nodes[0]
            assert outcome.status == "ok", outcome.error
            child_refs = [ref for ref in outcome.artifacts if ref.kind == "core.run_manifest"]
            assert len(child_refs) == 1
            fresh_store = FileSystemCAS(directory / "cas")
            assert fresh_store.verify(child_refs[0]).ok
            child_manifest = RunManifest.model_validate(
                from_canonical_bytes(fresh_store.get_bytes(child_refs[0]))
            )
            assert child_manifest.parent_run_id == state.run_id
            child_ids.append(child_manifest.run_id)
        assert child_ids[0] == child_ids[1]


# ---------------------------------------------------------------------------
# State mapping
# ---------------------------------------------------------------------------


class TestStateMapping:
    @pytest.mark.parametrize(
        ("parent_params", "expected"),
        [
            ({}, {}),
            ({"rows": [{"value": None}]}, {}),
            ({"rows": [{"value": 0}]}, {"value": 0}),
            ({"rows": [{"value": False}]}, {"value": False}),
        ],
        ids=["missing", "null", "zero", "false"],
    )
    def test_optional_indexed_input_reaches_real_child_without_truthiness_collapse(
        self, tmp_path: Path, parent_params: dict, expected: dict
    ) -> None:
        """The real child executor receives values under the declared skip contract."""
        observed: list[dict] = []

        def _execute(ctx, state):
            observed.append(dict(state.params))
            return NodeOutcome(status="ok", state=state)

        child = _make_mock_node()
        child.execute.side_effect = _execute
        node = SubWorkflowNode(
            SubWorkflowConfig(
                workflow=WorkflowSpec(
                    workflow_id="child_optional_indexed",
                    nodes=[NodeInvocation(alias="observe", node_id="test.node@1.0.0")],
                ),
                input_mappings=[
                    StateMapping(source_path="params.rows.0.value", target_path="params.value")
                ],
            ),
            _make_registry(child),
        )

        result = _run_sub_workflow(
            node,
            ExperimentState(run_id="parent_optional_indexed", params=parent_params),
            tmp_path,
        )

        outcome = result.report.nodes[0]
        assert outcome.status == "ok"
        assert observed == [expected]
        if expected:
            assert type(observed[0]["value"]) is type(expected["value"])

    def test_input_mapping(self, tmp_path: Path) -> None:
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
        result = _run_sub_workflow(node, state, tmp_path)
        outcome = result.report.nodes[0]
        assert outcome.status == "ok"

    def test_output_mapping(self, tmp_path: Path) -> None:
        """Child params are mapped back to parent state."""

        # Create a node that writes to child state
        def _execute(ctx, state):
            state.params["result"] = "computed_value"
            return NodeOutcome(status="ok", state=state, events=[], artifacts=[])

        task_node = _make_mock_node(state_writes=("params.result",))
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
        result = _run_sub_workflow(node, state, tmp_path)
        outcome = result.report.nodes[0]
        assert outcome.status == "ok"
        assert result.state.params.get("child_result") == "computed_value"


# ---------------------------------------------------------------------------
# Depth enforcement
# ---------------------------------------------------------------------------


class TestDepthEnforcement:
    def test_negative_depth_is_rejected(self, tmp_path: Path) -> None:
        child_wf = WorkflowSpec(workflow_id="child_negative_depth", nodes=[])
        cfg = SubWorkflowConfig(workflow=child_wf, max_depth=2)
        node = SubWorkflowNode(cfg, _make_registry(_make_mock_node()))

        outcome = node.execute(_make_ctx(tmp_path, depth=-1), ExperimentState(run_id="r_neg"))
        assert outcome.status == "fail"
        assert outcome.error is not None
        assert outcome.error.code == "sub_workflow.invalid_depth"

    def test_max_depth_exceeded(self, tmp_path: Path) -> None:
        child_wf = WorkflowSpec(workflow_id="child_depth", nodes=[])
        cfg = SubWorkflowConfig(workflow=child_wf, max_depth=2)
        node = SubWorkflowNode(cfg, _make_registry(_make_mock_node()))

        state = ExperimentState(run_id="r5")
        # Context already at depth 2, max_depth=2 → fail
        outcome = node.execute(_make_ctx(tmp_path, depth=2), state)
        assert outcome.status == "fail"
        assert outcome.error is not None
        assert "max_depth" in outcome.error.code

    def test_depth_within_limit(self, tmp_path: Path) -> None:
        child_wf = WorkflowSpec(workflow_id="child_ok", nodes=[])
        cfg = SubWorkflowConfig(workflow=child_wf, max_depth=3)
        node = SubWorkflowNode(cfg, _make_registry(_make_mock_node()))

        state = ExperimentState(run_id="r6")
        # depth=1, max_depth=3 → 1+1=2 <= 3, ok
        result = _run_sub_workflow(node, state, tmp_path, depth=1)
        outcome = result.report.nodes[0]
        assert outcome.status == "ok"

    def test_managed_depth_exceeded_refuses_before_child_producer(self, tmp_path: Path) -> None:
        child = _make_mock_node()
        node = SubWorkflowNode(
            SubWorkflowConfig(
                workflow=WorkflowSpec(
                    workflow_id="managed_depth_refused",
                    nodes=[NodeInvocation(alias="step", node_id=child.spec.metadata.component_id)],
                ),
                max_depth=2,
            ),
            _make_registry(child),
        )

        result = _run_sub_workflow(
            node, ExperimentState(run_id="managed_depth_parent"), tmp_path, depth=2
        )

        outcome = result.report.nodes[0]
        assert outcome.status == "fail"
        assert outcome.error is not None
        assert outcome.error.code == "sub_workflow.max_depth"
        assert not any(ref.kind == "core.run_manifest" for ref in outcome.artifacts)
        child.execute.assert_not_called()

    def test_depth_at_boundary(self, tmp_path: Path) -> None:
        child_wf = WorkflowSpec(workflow_id="child_boundary", nodes=[])
        cfg = SubWorkflowConfig(workflow=child_wf, max_depth=2)
        node = SubWorkflowNode(cfg, _make_registry(_make_mock_node()))

        state = ExperimentState(run_id="r7")
        # depth=1, max_depth=2 → 1+1=2 <= 2, ok
        result = _run_sub_workflow(node, state, tmp_path, depth=1)
        outcome = result.report.nodes[0]
        assert outcome.status == "ok"


# ---------------------------------------------------------------------------
# Child failure propagation
# ---------------------------------------------------------------------------


class TestChildFailure:
    def test_child_node_failure_propagates(self, tmp_path: Path) -> None:
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
        result = _run_sub_workflow(node, state, tmp_path)
        outcome = result.report.nodes[0]
        assert outcome.status == "fail"
        assert outcome.error is not None

    def test_child_failure_does_not_apply_output_mappings(self, tmp_path: Path) -> None:
        """Failed child workflows must not partially mutate the parent state."""

        def _execute_fail_after_write(ctx, state):
            state.params["result"] = "should_not_leak"
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="test.fail", message="fail", details={}),
            )

        failing_node = _make_mock_node(state_writes=("params.result",))
        failing_node.execute.side_effect = _execute_fail_after_write
        child_wf = WorkflowSpec(
            workflow_id="child_fail_after_write",
            nodes=[NodeInvocation(alias="bad_step", node_id="test.node@1.0.0")],
        )
        cfg = SubWorkflowConfig(
            workflow=child_wf,
            output_mappings=[
                StateMapping(source_path="params.result", target_path="params.child_result"),
            ],
        )
        registry = _make_registry(failing_node)
        node = SubWorkflowNode(cfg, registry)
        state = ExperimentState(run_id="r8b", params={"existing": "kept"})

        result = _run_sub_workflow(node, state, tmp_path)
        outcome = result.report.nodes[0]

        assert outcome.status == "fail"
        assert outcome.error is not None
        assert outcome.error.code == "sub_workflow.child_failed"
        assert result.state.params == {"existing": "kept"}
        _assert_completed_child_visible_after_refusal(result, tmp_path, child_status="fail")

    def test_invalid_output_mapping_retains_child_evidence_without_parent_mutation(
        self, tmp_path: Path
    ) -> None:
        def _execute(ctx, state):
            state.params["result"] = "computed"
            return NodeOutcome(status="ok", state=state)

        child = _make_mock_node(state_writes=("params.result",))
        child.execute.side_effect = _execute
        node = SubWorkflowNode(
            SubWorkflowConfig(
                workflow=WorkflowSpec(
                    workflow_id="child_invalid_mapping",
                    nodes=[
                        NodeInvocation(alias="compute", node_id=child.spec.metadata.component_id)
                    ],
                ),
                output_mappings=[StateMapping(source_path="params.result", target_path="params")],
            ),
            _make_registry(child),
        )

        result = _run_sub_workflow(
            node, ExperimentState(run_id="invalid_mapping_parent", params={"kept": True}), tmp_path
        )

        outcome = result.report.nodes[0]
        assert outcome.status == "fail"
        assert outcome.error is not None
        assert outcome.error.code == "sub_workflow.invalid_output_mapping"
        assert result.state.params == {"kept": True}
        _assert_completed_child_visible_after_refusal(result, tmp_path, child_status="ok")

    def test_overlapping_output_mappings_fail_atomically(self, tmp_path: Path) -> None:
        """Overlapping output targets must fail before any parent mutation is applied."""

        def _execute(ctx, state):
            state.params["summary"] = "value"
            state.params["detail"] = {"nested": True}
            return NodeOutcome(status="ok", state=state, events=[], artifacts=[])

        task_node = _make_mock_node(state_writes=("params.summary", "params.detail"))
        task_node.execute.side_effect = _execute
        child_wf = WorkflowSpec(
            workflow_id="child_conflict",
            nodes=[NodeInvocation(alias="compute", node_id="test.node@1.0.0")],
        )
        cfg = SubWorkflowConfig(
            workflow=child_wf,
            output_mappings=[
                StateMapping(source_path="params.summary", target_path="params.result"),
                StateMapping(source_path="params.detail", target_path="params.result.detail"),
            ],
        )
        registry = _make_registry(task_node)
        node = SubWorkflowNode(cfg, registry)
        state = ExperimentState(run_id="r8c", params={"existing": "kept"})

        result = _run_sub_workflow(node, state, tmp_path)
        outcome = result.report.nodes[0]

        assert outcome.status == "fail"
        assert outcome.error is not None
        assert outcome.error.code == "sub_workflow.output_conflict"
        assert result.state.params == {"existing": "kept"}
        _assert_completed_child_visible_after_refusal(result, tmp_path, child_status="ok")


# ---------------------------------------------------------------------------
# Error policy override
# ---------------------------------------------------------------------------


class TestErrorPolicyOverride:
    def test_override_to_continue(self, tmp_path: Path) -> None:
        """error_policy_override='continue' makes child not fail-fast."""
        # One failing node and one succeeding node
        call_count = 0

        def _execute(ctx, state):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return NodeOutcome(
                    status="fail",
                    state=state,
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
        _run_sub_workflow(node, state, tmp_path)
        # With continue policy, step_b still runs even after step_a fails
        assert task_node.execute.call_count == 2


# ---------------------------------------------------------------------------
# Nested sub-workflows (depth=2)
# ---------------------------------------------------------------------------


class TestNestedSubWorkflows:
    def test_two_level_nesting(self, tmp_path: Path) -> None:
        """A sub-workflow containing another sub-workflow."""
        inner_wf = WorkflowSpec(workflow_id="inner", nodes=[])
        inner_cfg = SubWorkflowConfig(workflow=inner_wf, max_depth=3)

        # The "inner" node is a SubWorkflowNode itself
        inner_node = SubWorkflowNode(
            inner_cfg,
            _make_registry(_make_mock_node()),
            alias="inner",
        )

        registry = _make_registry(inner_node)

        outer_wf = WorkflowSpec(
            workflow_id="outer",
            nodes=[NodeInvocation(alias="nested", node_id=inner_node.spec.metadata.component_id)],
        )
        outer_cfg = SubWorkflowConfig(workflow=outer_wf, max_depth=3)
        outer_node = SubWorkflowNode(outer_cfg, registry, alias="outer")

        state = ExperimentState(run_id="r10")
        result = _run_sub_workflow(outer_node, state, tmp_path)
        outcome = result.report.nodes[0]
        assert outcome.status == "ok", outcome.error
