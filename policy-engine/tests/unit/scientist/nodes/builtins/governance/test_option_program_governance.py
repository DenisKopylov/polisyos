"""Governance preserves gate decisions while exposing an unproved program join."""

from __future__ import annotations

import logging

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.governance.report import load_governance_report_artifact
from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


@pytest.mark.parametrize("workflow_id", ["scientist_policy_verified", "scientist_default"])
def test_actual_governance_report_preserves_human_gate_and_names_unproved_join(
    tmp_path, workflow_id: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    state = ExperimentState(
        run_id="synthetic-option-program-governance",
        params={"workflow_id": workflow_id, "require_human_gate": True},
    )
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=state.run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    node = RunGovernanceNode()
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="synthetic_option_program_governance",
        nodes=[NodeInvocation(alias="governance", node_id=node.spec.metadata.component_id)],
    )
    result = WorkflowExecutor(ctx, registry).execute(workflow, state)
    assert result.report.nodes[0].status == "ok"
    report_ref = result.state.reports_index["governance_report_ref"]
    report = load_governance_report_artifact(store, report_ref)
    assert report.verdict == "human_gate"
    has_limitation = any(
        issue.get("code") == "option_program_correspondence_not_established"
        and issue.get("status") == "not_established"
        for issue in report.issues
    )
    assert has_limitation is (workflow_id == "scientist_policy_verified")
