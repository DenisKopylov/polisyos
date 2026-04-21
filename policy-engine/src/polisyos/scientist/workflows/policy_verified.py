"""Workflow spec for verified-answer generation without hierarchical policy search."""
from __future__ import annotations

from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec


def policy_verified_workflow_spec() -> WorkflowSpec:
    """Build the `scientist_policy_verified` workflow spec.

    The DAG assumes registry input and either research intent or a policy
    question in `params`, verifies legal/source support before drafting,
    formalizes the selected option into Trinity, then runs simulation,
    arbitration, governance, and verified-report packaging.

    Returns:
        `WorkflowSpec` for the legacy verified-policy path that does not run
        hierarchical champion search.
    """
    return WorkflowSpec(
        workflow_id="scientist_policy_verified",
        error_policy="continue",
        required_binds=[
            "run_id",
            "inputs.registry_bundle_ref",
        ],
        nodes=[
            NodeInvocation(alias="start", node_id="scientist.node_noop@1.0.0"),
            NodeInvocation(
                alias="plan_policy_request",
                node_id="scientist.node_plan_policy_request@1.0.0",
                depends_on=["start"],
            ),
            NodeInvocation(
                alias="build_data_snapshot",
                node_id="scientist.node_build_data_snapshot@1.0.0",
                depends_on=["start"],
            ),
            NodeInvocation(
                alias="build_execution_plan",
                node_id="scientist.node_build_execution_plan@1.0.0",
                depends_on=["start"],
            ),
            NodeInvocation(
                alias="build_method_catalog_snapshot",
                node_id="scientist.node_build_method_catalog_snapshot@1.0.0",
                depends_on=["build_execution_plan"],
            ),
            NodeInvocation(
                alias="run_preflight",
                node_id="scientist.node_run_preflight@1.0.0",
                depends_on=["build_execution_plan", "build_method_catalog_snapshot"],
            ),
            NodeInvocation(
                alias="compile_cross_graph_evidence",
                node_id="scientist.node_compile_cross_graph_evidence@1.0.0",
                depends_on=["plan_policy_request"],
            ),
            NodeInvocation(
                alias="assemble_legal_candidate_pack",
                node_id="scientist.node_assemble_legal_candidate_pack@1.0.0",
                depends_on=["plan_policy_request", "compile_cross_graph_evidence"],
            ),
            NodeInvocation(
                alias="expand_legal_source_pack",
                node_id="scientist.node_expand_legal_source_pack@1.0.0",
                depends_on=["assemble_legal_candidate_pack"],
            ),
            NodeInvocation(
                alias="run_source_verification",
                node_id="scientist.node_run_source_verification@1.0.0",
                depends_on=["expand_legal_source_pack"],
            ),
            NodeInvocation(
                alias="run_source_gap_review",
                node_id="scientist.node_run_source_gap_review@1.0.0",
                depends_on=["run_source_verification"],
            ),
            NodeInvocation(
                alias="draft_policy_options",
                node_id="scientist.node_draft_policy_options@1.0.0",
                depends_on=["run_source_gap_review"],
            ),
            NodeInvocation(
                alias="formalize_verified_policy",
                node_id="scientist.node_formalize_verified_policy@1.0.0",
                depends_on=["draft_policy_options"],
            ),
            NodeInvocation(
                alias="bind_foundry_inputs",
                node_id="scientist.node_bind_foundry_inputs@1.0.0",
                depends_on=["build_data_snapshot"],
            ),
            NodeInvocation(
                alias="run_data_plane_gate",
                node_id="scientist.node_run_data_plane_gate@1.0.0",
                depends_on=["bind_foundry_inputs"],
            ),
            NodeInvocation(
                alias="compile_foundry",
                node_id="scientist.node_compile_foundry@1.0.0",
                depends_on=["formalize_verified_policy", "run_data_plane_gate", "run_preflight"],
            ),
            NodeInvocation(
                alias="resolve_parameters",
                node_id="scientist.node_resolve_parameters@1.0.0",
                depends_on=[
                    "compile_foundry",
                    "compile_cross_graph_evidence",
                    "bind_foundry_inputs",
                    "run_data_plane_gate",
                ],
            ),
            NodeInvocation(
                alias="run_simulation",
                node_id="scientist.node_run_simulation@1.0.1",
                depends_on=[
                    "compile_foundry",
                    "bind_foundry_inputs",
                    "run_data_plane_gate",
                    "resolve_parameters",
                ],
            ),
            NodeInvocation(
                alias="run_metric_validation",
                node_id="scientist.node_run_metric_validation@1.0.0",
                depends_on=["run_simulation"],
            ),
            NodeInvocation(
                alias="legal_check",
                node_id="scientist.node_legal_check@1.0.1",
                depends_on=["run_simulation"],
            ),
            NodeInvocation(
                alias="run_distributional_analysis",
                node_id="scientist.node_run_distributional_analysis@1.0.0",
                depends_on=["run_simulation"],
            ),
            NodeInvocation(
                alias="propagate_uncertainty",
                node_id="scientist.node_propagate_uncertainty@1.0.0",
                depends_on=["run_simulation"],
            ),
            NodeInvocation(
                alias="run_causal_evaluation",
                node_id="scientist.node_run_causal_evaluation@1.2.0",
                depends_on=["build_data_snapshot"],
            ),
            NodeInvocation(
                alias="run_normative_arbitration",
                node_id="scientist.node_run_normative_arbitration@1.0.0",
                depends_on=[
                    "legal_check",
                    "propagate_uncertainty",
                    "run_distributional_analysis",
                    "run_causal_evaluation",
                ],
            ),
            NodeInvocation(
                alias="run_governance",
                node_id="scientist.node_run_governance@1.2.0",
                depends_on=[
                    "legal_check",
                    "propagate_uncertainty",
                    "run_distributional_analysis",
                    "run_causal_evaluation",
                    "run_normative_arbitration",
                ],
            ),
            NodeInvocation(
                alias="build_verified_policy_report",
                node_id="scientist.node_build_verified_policy_report@1.0.0",
                depends_on=[
                    "run_governance",
                    "run_source_gap_review",
                    "draft_policy_options",
                    "run_simulation",
                    "run_causal_evaluation",
                    "run_distributional_analysis",
                    "propagate_uncertainty",
                ],
            ),
            NodeInvocation(
                alias="build_decision_packet",
                node_id="scientist.node_build_decision_packet@1.5.0",
                depends_on=[
                    "run_governance",
                    "run_causal_evaluation",
                    "build_verified_policy_report",
                    "run_metric_validation",
                ],
            ),
        ],
        notes=[
            "Scientist production workflow uses lex graph for recall and source verification for final trust.",
            "Verified-only legal basis is produced before drafting and formalization.",
            "Workflow is additive and leaves scientist_default and scientist_causal_full unchanged.",
        ],
    )


__all__ = ["policy_verified_workflow_spec"]
