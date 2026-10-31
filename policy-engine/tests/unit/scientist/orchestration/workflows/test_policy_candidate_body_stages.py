"""Real policy workflows select restricted candidate inputs before assessment."""

from __future__ import annotations

import pytest

from polisyos.scientist.nodes.builtins import builtin_nodes
from polisyos.scientist.orchestration.workflows.policy_design import policy_design_workflow_spec
from polisyos.scientist.orchestration.workflows.policy_verified import policy_verified_workflow_spec


def test_selected_candidate_and_body_are_registered_as_production_builtins() -> None:
    components = {str(node.spec.metadata.component_id) for node in builtin_nodes()}
    assert "scientist.node_select_policy_candidate@1.0.0" in components
    assert "scientist.node_build_verified_policy_body@1.0.0" in components


@pytest.mark.parametrize("workflow", [policy_verified_workflow_spec, policy_design_workflow_spec])
def test_selected_candidate_and_body_precede_governance_assessment(workflow) -> None:
    nodes = {node.alias: node for node in workflow().nodes}
    assert (
        str(nodes["select_policy_candidate"].node_id)
        == "scientist.node_select_policy_candidate@1.0.0"
    )
    assert (
        str(nodes["build_verified_policy_body"].node_id)
        == "scientist.node_build_verified_policy_body@1.0.0"
    )
    assert {"select_policy_candidate", "build_verified_policy_body"} <= set(
        nodes["run_governance"].depends_on
    )
    assert {
        "draft_policy_options",
        "run_source_gap_review",
        "run_simulation",
        "run_causal_evaluation",
    } <= set(nodes["build_verified_policy_body"].depends_on)


@pytest.mark.parametrize("workflow", [policy_verified_workflow_spec, policy_design_workflow_spec])
def test_workflow_notes_preserve_unverified_source_and_program_limitations(workflow) -> None:
    notes = workflow().notes
    assert (
        "Independent legal claim verification is not established; source interpretations remain candidates."
        in notes
    )
    assert "Selected policy option correspondence to the final program is not established." in notes
