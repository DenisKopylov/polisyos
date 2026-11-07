"""Canonical causal workflow DAG for graph reconciliation, simulation, and governance.

The spec starts from Trinity/registry inputs, materializes data and literature
priors, reconciles the causal graph, runs readiness and transport checks, then
emits a decision packet after evaluator and governance stages.
"""

from __future__ import annotations

from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

CAUSAL_FULL_TRANSPORT_NODE_TIMEOUT_S = 120.0
CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM = "transport_candidate_resource_policy"


def _transport_work_estimator_snapshot() -> dict[str, object]:
    """Freeze the method-owned PAG work estimator identity without requiring its backend."""

    try:
        from polisyos.foundry.methods.catalog.causal.pag_member_family import (
            PAGWorkEstimateError,
            pag_member_work_algorithm_identity,
            pag_member_work_estimator_source_sha256,
        )
    except ImportError:
        return {
            "status": "unavailable",
            "reason_code": "pinned_backend_identity_unavailable",
        }

    try:
        identity = pag_member_work_algorithm_identity()
        source_sha256 = pag_member_work_estimator_source_sha256()
    except PAGWorkEstimateError as exc:
        return {
            "status": "unavailable",
            "reason_code": exc.code,
        }

    return {
        "status": "available",
        "algorithm_identity": identity.model_dump(mode="json"),
        "estimator_source_sha256": source_sha256,
    }


def causal_full_transport_resource_policy_snapshot() -> dict[str, object]:
    """Return the code-owned per-node resource profile frozen in WorkflowSpec."""

    return {
        "work_estimator": _transport_work_estimator_snapshot(),
        "schema_version": "1.0",
        "policy_id": "transport-candidate.standard.v1",
        "policy_revision": "g528-conditional-transport-resources.v2",
        "selection_identity": "transport-candidate.standard.v1",
        "supported_profiles": [
            {
                "profile_id": "transport.conditional.resolved_graph",
                "profile_revision": "1",
            },
            {
                "profile_id": "pag.no_selection.finite_member_sensitivity",
                "profile_revision": "1",
            },
        ],
        "limits": {
            "node_timeout_s": CAUSAL_FULL_TRANSPORT_NODE_TIMEOUT_S,
            "max_proposals": 64,
            "max_members": 64,
            "max_evaluations": 64,
            "max_oracle_operations": 64,
            "max_estimated_dsep_queries": 8192,
            "max_expanded_graph_element_query_units": 524288,
            "max_elapsed_seconds": 75.0,
            "max_output_bytes": 65536,
            "max_diagnostic_bytes": 262144,
        },
        "limit_units": {
            "node_timeout_s": "seconds",
            "max_proposals": "count",
            "max_members": "count",
            "max_evaluations": "count",
            "max_oracle_operations": "count",
            "max_estimated_dsep_queries": "d_separation_query_count",
            "max_expanded_graph_element_query_units": "expanded_graph_element_query_units",
            "max_elapsed_seconds": "seconds",
            "max_output_bytes": "bytes",
            "max_diagnostic_bytes": "bytes",
        },
    }


def causal_full_workflow_spec() -> WorkflowSpec:
    """Build the canonical end-to-end causal workflow spec.

    The workflow links literature-prior assembly, graph reconciliation,
    readiness checks, Foundry compilation, simulation, causal evaluation, and
    governance into one reproducible DAG used by ``run_experiment``.

    Returns:
        `WorkflowSpec` with required Trinity/registry binds and ordered node
        aliases for the `scientist_causal_full` DAG.
    """

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
                alias="compile_cross_graph_evidence",
                node_id="scientist.node_compile_cross_graph_evidence@1.0.0",
                depends_on=["compile_foundry", "reconcile_causal_graph"],
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
                alias="run_causal_evaluation",
                node_id="scientist.node_run_causal_evaluation@2.0.0",
                depends_on=["build_data_snapshot", "bind_foundry_inputs"],
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
                params={
                    CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM: causal_full_transport_resource_policy_snapshot()
                },
                depends_on=["run_abm_consistency", "reconcile_causal_graph"],
                timeout_s=CAUSAL_FULL_TRANSPORT_NODE_TIMEOUT_S,
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
                alias="run_normative_arbitration",
                node_id="scientist.node_run_normative_arbitration@1.0.0",
                depends_on=[
                    "propagate_uncertainty",
                    "run_distributional_analysis",
                    "run_causal_evaluation",
                    "run_transportability",
                    "run_causal_readiness",
                ],
            ),
            NodeInvocation(
                alias="run_governance",
                node_id="scientist.node_run_governance@1.2.0",
                depends_on=[
                    "propagate_uncertainty",
                    "run_distributional_analysis",
                    "run_causal_evaluation",
                    "run_causal_ensemble",
                    "run_abm_consistency",
                    "reconcile_causal_graph",
                    "run_transportability",
                    "run_causal_readiness",
                    "run_normative_arbitration",
                    "run_metric_validation",
                    "propagate_welfare",
                ],
            ),
            NodeInvocation(
                alias="run_evaluator",
                node_id="scientist.node_run_evaluator@1.0.0",
                depends_on=["run_governance"],
            ),
            # Evaluation changes the full governance pass context; reissue on that basis.
            NodeInvocation(
                alias="refresh_governance",
                node_id="scientist.node_run_governance@1.2.0",
                params={"replay_previous_gate_decision": True},
                depends_on=["run_evaluator"],
            ),
            NodeInvocation(
                alias="build_decision_packet",
                node_id="scientist.node_build_decision_packet@1.5.0",
                depends_on=[
                    "refresh_governance",
                    "run_causal_evaluation",
                    "run_evaluator",
                    "run_metric_validation",
                    "propagate_welfare",
                ],
            ),
        ],
        notes=[
            "Phase 9 full workflow includes literature prior build + graph reconciliation.",
            "scientist_default remains unchanged for backward compatibility.",
            "Cross-graph evidence profile is compiled before parameter resolution and governance.",
            "Causal readiness checks run after graph/evidence assembly and feed downstream governance.",
            "Reconciliation diagnostics and needs_expert_review are propagated via state.params.",
        ],
    )


__all__ = ["causal_full_workflow_spec"]
