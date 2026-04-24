from __future__ import annotations

from polisyos.scientist.workflows.policy_verified import policy_verified_workflow_spec


def test_policy_verified_workflow_contains_source_verification_path() -> None:
    spec = policy_verified_workflow_spec()
    by_alias = {node.alias: node for node in spec.nodes}

    assert spec.workflow_id == "scientist_policy_verified"
    assert "plan_policy_request" in by_alias
    assert "assemble_legal_candidate_pack" in by_alias
    assert "expand_legal_source_pack" in by_alias
    assert "run_source_verification" in by_alias
    assert "run_source_gap_review" in by_alias
    assert "draft_policy_options" in by_alias
    assert "formalize_verified_policy" in by_alias
    assert "build_verified_policy_report" in by_alias
    assert "build_decision_packet" in by_alias
    assert "compile_cross_graph_evidence" in by_alias["assemble_legal_candidate_pack"].depends_on
    assert by_alias["run_source_verification"].depends_on == ["expand_legal_source_pack"]
    assert by_alias["run_source_gap_review"].depends_on == ["run_source_verification"]
    assert by_alias["draft_policy_options"].depends_on == ["run_source_gap_review"]
    assert "build_verified_policy_report" in by_alias["build_decision_packet"].depends_on


def test_policy_verified_workflow_formalizes_before_foundry_compile() -> None:
    spec = policy_verified_workflow_spec()
    by_alias = {node.alias: node for node in spec.nodes}
    aliases_in_order = [node.alias for node in spec.nodes]

    assert "formalize_verified_policy" in by_alias["compile_foundry"].depends_on
    assert "run_data_plane_gate" in by_alias["compile_foundry"].depends_on
    assert "run_normative_arbitration" in by_alias["run_governance"].depends_on
    assert aliases_in_order.index("run_source_verification") < aliases_in_order.index(
        "draft_policy_options"
    )
    assert aliases_in_order.index("draft_policy_options") < aliases_in_order.index(
        "formalize_verified_policy"
    )
    assert aliases_in_order.index("build_verified_policy_report") < aliases_in_order.index(
        "build_decision_packet"
    )
