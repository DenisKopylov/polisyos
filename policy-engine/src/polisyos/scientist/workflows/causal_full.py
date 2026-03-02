from __future__ import annotations

from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec


def causal_full_workflow_spec() -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="scientist_causal_full",
        error_policy="continue",
        required_binds=[
            "run_id",
            "inputs.trinity_bundle_ref",
            "inputs.registry_bundle_ref",
        ],
        nodes=[
            NodeInvocation(alias="start", node_id="scientist.node_noop@1.0.0"),
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
                alias="ready_to_run",
                node_id="scientist.node_ready_to_run@1.0.0",
                depends_on=["run_preflight"],
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
                alias="link_trinity",
                node_id="scientist.node_link_trinity@1.0.0",
                depends_on=["start"],
            ),
            NodeInvocation(
                alias="compile_foundry",
                node_id="scientist.node_compile_foundry@1.0.0",
                depends_on=["link_trinity", "run_data_plane_gate", "ready_to_run"],
            ),
            NodeInvocation(
                alias="resolve_parameters",
                node_id="scientist.node_resolve_parameters@1.0.0",
                depends_on=[
                    "compile_foundry",
                    "bind_foundry_inputs",
                    "run_data_plane_gate",
                    "reconcile_causal_graph",
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
                alias="run_causal_evaluation",
                node_id="scientist.node_run_causal_evaluation@1.2.0",
                depends_on=["build_data_snapshot"],
            ),
            NodeInvocation(
                alias="run_causal_queries",
                node_id="scientist.node_run_causal_queries@1.0.0",
                depends_on=["run_causal_evaluation"],
            ),
            NodeInvocation(
                alias="run_causal_ensemble",
                node_id="scientist.node_run_causal_ensemble@1.0.0",
                depends_on=["run_causal_queries"],
            ),
            NodeInvocation(
                alias="run_abm_consistency",
                node_id="scientist.node_run_abm_consistency@1.0.0",
                depends_on=["run_causal_ensemble"],
            ),
            NodeInvocation(
                alias="run_transportability",
                node_id="scientist.node_run_transportability@1.0.0",
                depends_on=["run_abm_consistency", "reconcile_causal_graph"],
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
                alias="run_governance",
                node_id="scientist.node_run_governance@1.1.0",
                depends_on=[
                    "propagate_uncertainty",
                    "run_distributional_analysis",
                    "run_causal_evaluation",
                    "run_causal_ensemble",
                    "run_abm_consistency",
                    "reconcile_causal_graph",
                    "run_transportability",
                ],
            ),
            NodeInvocation(
                alias="run_evaluator",
                node_id="scientist.node_run_evaluator@1.0.0",
                depends_on=["run_governance"],
            ),
            NodeInvocation(
                alias="build_decision_packet",
                node_id="scientist.node_build_decision_packet@1.4.0",
                depends_on=["run_governance", "run_causal_evaluation", "run_evaluator"],
            ),
        ],
        notes=[
            "Phase 9 full workflow includes literature prior build + graph reconciliation.",
            "scientist_default remains unchanged for backward compatibility.",
            "Reconciliation diagnostics and needs_expert_review are propagated via state.params.",
        ],
    )


__all__ = ["causal_full_workflow_spec"]
