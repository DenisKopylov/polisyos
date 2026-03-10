from __future__ import annotations

from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec


def default_workflow_spec() -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="scientist_default",
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
                alias="legal_check",
                node_id="scientist.node_legal_check@1.0.1",
                depends_on=["run_simulation"],
            ),
            NodeInvocation(
                alias="run_causal_evaluation",
                node_id="scientist.node_run_causal_evaluation@1.2.0",
                depends_on=["build_data_snapshot"],
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
                    "legal_check",
                    "propagate_uncertainty",
                    "run_distributional_analysis",
                    "run_causal_evaluation",
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
            "E1.8 default workflow spec (engine DAG)",
            "ExecutionPlan/preflight pipeline is mandatory before compile stage.",
            "P8 data-plane: bind_foundry_inputs + pre-simulation run_data_plane_gate.",
            "LegalCheckNode executes after simulation and may skip when legal context is unavailable.",
            "Decision packet is generated after governance, evaluation, and uncertainty propagation.",
        ],
    )


__all__ = ["default_workflow_spec"]
