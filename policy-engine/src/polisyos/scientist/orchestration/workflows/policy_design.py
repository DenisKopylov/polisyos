"""Verified policy-design workflow DAG with legal sourcing and hierarchical search.

The spec expands a policy request into verified legal/source packs, generates
candidate policies, runs hierarchical search, blocks non-identified
counterfactuals before simulation, and packages the translated champion policy.
"""

from __future__ import annotations

from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


def policy_design_workflow_spec() -> WorkflowSpec:
    """Build the Scientist policy-design workflow with C6c extensions.

    Adds legal-source verification, hierarchical policy search, causal
    readiness, and counterfactual gating before simulation so that the chosen
    policy candidate is both executable and governance-ready.

    Returns:
        `WorkflowSpec` for `scientist_policy_design`, including the champion
        search path and final policy-output bundle assembly.
    """

    return WorkflowSpec(
        workflow_id="scientist_policy_design",
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
                alias="build_literature_prior",
                node_id="scientist.node_build_literature_prior@1.0.0",
                depends_on=["start"],
            ),
            NodeInvocation(
                alias="reconcile_causal_graph",
                node_id="scientist.node_reconcile_causal_graph@1.0.0",
                depends_on=["build_literature_prior"],
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
                alias="assemble_legal_candidate_pack",
                node_id="scientist.node_assemble_legal_candidate_pack@1.0.0",
                depends_on=["plan_policy_request"],
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
                alias="run_hierarchical_policy_search",
                node_id="scientist.node_run_hierarchical_policy_search@1.0.0",
                depends_on=[
                    "formalize_verified_policy",
                    "run_data_plane_gate",
                    "run_preflight",
                    "reconcile_causal_graph",
                ],
            ),
            NodeInvocation(
                alias="compile_foundry",
                node_id="scientist.node_compile_foundry@1.0.0",
                depends_on=[
                    "run_hierarchical_policy_search",
                    "run_data_plane_gate",
                    "run_preflight",
                ],
            ),
            NodeInvocation(
                alias="compile_cross_graph_evidence",
                node_id="scientist.node_compile_cross_graph_evidence@1.0.0",
                depends_on=["run_hierarchical_policy_search", "reconcile_causal_graph"],
            ),
            NodeInvocation(
                alias="run_causal_readiness",
                node_id="scientist.node_run_causal_readiness@1.0.0",
                depends_on=["compile_cross_graph_evidence", "reconcile_causal_graph"],
            ),
            NodeInvocation(
                alias="resolve_parameters",
                node_id="scientist.node_resolve_parameters@1.0.0",
                depends_on=[
                    "compile_foundry",
                    "compile_cross_graph_evidence",
                    "bind_foundry_inputs",
                    "run_data_plane_gate",
                    "reconcile_causal_graph",
                ],
            ),
            NodeInvocation(
                alias="counterfactual_identification_gate",
                node_id="scientist.node_counterfactual_identification_gate@1.0.0",
                depends_on=["run_causal_readiness", "resolve_parameters"],
            ),
            NodeInvocation(
                alias="run_simulation",
                node_id="scientist.node_run_simulation@1.0.1",
                depends_on=[
                    "compile_foundry",
                    "bind_foundry_inputs",
                    "run_data_plane_gate",
                    "resolve_parameters",
                    "counterfactual_identification_gate",
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
                alias="propagate_welfare",
                node_id="scientist.node_propagate_welfare@1.0.0",
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
                    "run_causal_readiness",
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
                    "run_causal_readiness",
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
                alias="run_policy_blueprint_runtime",
                node_id="scientist.node_run_policy_blueprint_runtime@1.0.0",
                depends_on=[
                    "run_governance",
                    "run_causal_evaluation",
                    "run_distributional_analysis",
                    "propagate_uncertainty",
                ],
            ),
            NodeInvocation(
                alias="run_policy_translation",
                node_id="scientist.node_run_policy_translation@1.0.0",
                depends_on=["run_policy_blueprint_runtime"],
            ),
            NodeInvocation(
                alias="run_translator_compliance",
                node_id="scientist.node_run_translator_compliance@1.0.0",
                depends_on=["run_policy_translation"],
            ),
            NodeInvocation(
                alias="build_policy_output_bundle",
                node_id="scientist.node_build_policy_output_bundle@1.0.0",
                depends_on=[
                    "run_policy_blueprint_runtime",
                    "run_policy_translation",
                    "run_translator_compliance",
                    "build_verified_policy_report",
                ],
            ),
            NodeInvocation(
                alias="build_decision_packet",
                node_id="scientist.node_build_decision_packet@1.5.0",
                depends_on=[
                    "build_verified_policy_report",
                    "build_policy_output_bundle",
                    "run_metric_validation",
                    "propagate_welfare",
                ],
            ),
        ],
        notes=[
            "Policy-design workflow adds a typed policy output bundle before the decision packet.",
            "C6c adds hierarchical policy search, causal readiness, and counterfactual gating before simulation.",
            "Existing scientist_default and scientist_policy_verified workflows remain unchanged.",
        ],
    )


__all__ = ["policy_design_workflow_spec"]
