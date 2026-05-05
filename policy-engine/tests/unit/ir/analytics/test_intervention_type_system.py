from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.estimand import (
    DistributionDomain,
    DistributionRef,
    EdgeInterventionAssignment,
    EdgeInterventionNode,
    EstimandAST,
    ModifiedTreatmentPolicyNode,
)
from polisyos.ir.analytics.interventions import (
    CompositeIntervention,
    ConditionalIntervention,
    ConditionalPolicy,
    EdgeAssignment,
    EdgeIntervention,
    InterferenceIntervention,
    InterferencePolicySpec,
    InterventionCompositionStatus,
    InterventionIdentificationStatus,
    InterventionQuery,
    ModifiedTreatmentPolicySpec,
    MTPIntervention,
    NodeIntervention,
    PathIntervention,
    ProofKernelInterventionType,
    QueryTarget,
    StochasticIntervention,
    StochasticPolicySpec,
    TransportIntervention,
    VariableAssignment,
    build_intervention_certificate,
    certificate_for_typecheck_failure,
    check_intervention_composition,
    identification_plan_for_intervention,
    load_intervention_certificate,
    load_intervention_query,
    natural_dependencies,
    persist_intervention_certificate,
    persist_intervention_query,
    proof_bundle_from_intervention_certificate,
    render_intervention_query,
)


def _target() -> QueryTarget:
    return QueryTarget(outcome_variables=("Y",))


def _node(variable: str = "A", value: int = 1) -> NodeIntervention:
    return NodeIntervention(assignments=(VariableAssignment(variable=variable, value=value),))


def test_intervention_language_covers_stage_13_1_minimum_types() -> None:
    base_node = _node()
    expressions = (
        base_node,
        ConditionalIntervention(
            assignments=(ConditionalPolicy(target="A", policy_expr="g(W)", history_vars=("W",)),)
        ),
        StochasticIntervention(
            policies=(
                StochasticPolicySpec(
                    target="A",
                    distribution_expr="pi(a|W)",
                    conditioning_vars=("W",),
                ),
            )
        ),
        MTPIntervention(
            policies=(
                ModifiedTreatmentPolicySpec(
                    target="A",
                    policy_expr="A+1",
                    natural_treatment="A",
                    covariates=("W",),
                ),
            )
        ),
        EdgeIntervention(assignments=(EdgeAssignment(source="A", target="M", value=1),)),
        PathIntervention(active_paths=(("A", "M", "Y"),), natural_value_vars=("M",)),
        TransportIntervention(
            source_domain="source",
            target_domain="target",
            selection_nodes=("S_A",),
            base_intervention=base_node,
        ),
        InterferenceIntervention(
            policies=(
                InterferencePolicySpec(
                    target="A_i",
                    policy_expr="pi_i(E_i)",
                    exposure_vars=("E_i",),
                ),
            ),
            exposure_map_ref="artifact:exposure-map",
            fallback_mode="clustered",
        ),
    )

    seen = {identification_plan_for_intervention(expr).intervention_type for expr in expressions}

    assert seen == {
        ProofKernelInterventionType.NODE,
        ProofKernelInterventionType.CONDITIONAL,
        ProofKernelInterventionType.STOCHASTIC,
        ProofKernelInterventionType.MTP,
        ProofKernelInterventionType.EDGE,
        ProofKernelInterventionType.PATH,
        ProofKernelInterventionType.TRANSPORT,
        ProofKernelInterventionType.INTERFERENCE,
    }
    assert natural_dependencies(expressions[3]) == ("A", "W")
    assert natural_dependencies(expressions[5]) == ("M",)


def test_mtp_after_node_assignment_is_blocked_by_natdeps() -> None:
    intervention = CompositeIntervention(
        steps=(
            _node("A", 1),
            MTPIntervention(
                policies=(
                    ModifiedTreatmentPolicySpec(
                        target="A",
                        policy_expr="A+delta",
                        natural_treatment="A",
                        covariates=("W",),
                    ),
                )
            ),
        )
    )
    query = InterventionQuery(target=_target(), intervention=intervention)

    certificate = certificate_for_typecheck_failure(query)
    proof_bundle = proof_bundle_from_intervention_certificate(certificate)

    assert (
        certificate.identification_status is InterventionIdentificationStatus.BLOCKED_BY_TYPECHECK
    )
    assert certificate.composition_check is not None
    assert certificate.composition_check.status is InterventionCompositionStatus.BLOCKED
    assert certificate.negative_certificate is not None
    assert certificate.negative_certificate["blocking_type"] == "intervention_typecheck"
    assert proof_bundle.proof_status == "non_identified"
    assert proof_bundle.metadata["intervention_type"] == "composite"


def test_policy_composition_and_edge_lifting_are_recorded_as_reductions() -> None:
    policy_combo = CompositeIntervention(
        steps=(
            ConditionalIntervention(
                assignments=(
                    ConditionalPolicy(target="A", policy_expr="g(W)", history_vars=("W",)),
                )
            ),
            StochasticIntervention(
                policies=(
                    StochasticPolicySpec(
                        target="A",
                        distribution_expr="pi(a|W)",
                        conditioning_vars=("W",),
                    ),
                )
            ),
        )
    )
    edge_combo = CompositeIntervention(
        steps=(
            _node("A", 1),
            EdgeIntervention(assignments=(EdgeAssignment(source="A", target="Y", value=1),)),
        )
    )

    policy_check = check_intervention_composition(policy_combo)
    edge_check = check_intervention_composition(edge_combo)

    assert policy_check.well_typed is True
    assert "POLICY_COMPOSITION_REPLACE_MECHANISM" in {
        reduction.rule_name for reduction in policy_check.reduction_chain
    }
    assert edge_check.well_typed is True
    assert "LIFT_NODE_TO_EDGE" in {reduction.rule_name for reduction in edge_check.reduction_chain}


def test_transport_must_be_outermost_and_interference_requires_reduction() -> None:
    bad_transport = CompositeIntervention(
        steps=(
            TransportIntervention(source_domain="s", target_domain="t"),
            _node("A", 1),
        )
    )
    clustered_interference = CompositeIntervention(
        steps=(
            _node("ClusterA", 1),
            InterferenceIntervention(
                policies=(
                    InterferencePolicySpec(
                        target="A_i",
                        policy_expr="pi_i(E_i)",
                        exposure_vars=("E_i",),
                    ),
                ),
                exposure_map_ref="artifact:exposure-map",
                fallback_mode="clustered",
            ),
        )
    )
    edge_interference = CompositeIntervention(
        steps=(
            EdgeIntervention(assignments=(EdgeAssignment(source="A", target="Y", value=1),)),
            InterferenceIntervention(
                policies=(InterferencePolicySpec(target="A_i", policy_expr="pi_i(E_i)"),),
                exposure_map_ref="artifact:exposure-map",
                fallback_mode="clustered",
            ),
        )
    )

    assert check_intervention_composition(bad_transport).well_typed is False
    clustered = check_intervention_composition(clustered_interference)
    assert clustered.well_typed is True
    assert "INTERFERENCE_CLUSTER_REDUCTION" in {
        reduction.rule_name for reduction in clustered.reduction_chain
    }
    assert check_intervention_composition(edge_interference).well_typed is False


def test_certificate_persists_and_embeds_in_proof_bundle(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    dist = DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Y",),
        intervention_set=("A",),
        dataset_ref="observed",
    )
    estimand = EstimandAST(
        query_str="P(Y|do(A))",
        root=dist,
        treatment="A",
        outcome="Y",
        all_variables=("A", "Y"),
    )
    query = InterventionQuery(target=_target(), intervention=_node("A", 1))
    certificate = build_intervention_certificate(
        query=query,
        identification_status=InterventionIdentificationStatus.IDENTIFIED,
        estimand_ast=estimand,
        required_distributions=(dist,),
    )

    query_ref = persist_intervention_query(store, query)
    ref = persist_intervention_certificate(store, certificate)
    restored_query = load_intervention_query(store, query_ref)
    restored = load_intervention_certificate(store, ref)
    proof_bundle = proof_bundle_from_intervention_certificate(restored, query_ref="query:typed")

    assert restored_query == query
    assert restored == certificate
    assert query_ref.kind == "ir.intervention_query"
    assert ref.kind == "ir.intervention_certificate"
    assert proof_bundle.proof_status == "identified"
    assert proof_bundle.query_ref == "query:typed"
    assert proof_bundle.metadata["query_kind"] == "intervention"
    target_payload = proof_bundle.metadata["intervention_certificate"]["query"]["target"]
    assert target_payload["outcome_variables"] == ["Y"]
    assert render_intervention_query(query) == "expectation:Y <- do(A=1)"


def test_estimand_ast_supports_edge_and_mtp_nodes() -> None:
    inner = DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Y",),
        conditioning=("A",),
        dataset_ref="inner_ds",
    )
    edge_node = EdgeInterventionNode(
        assignments=(EdgeInterventionAssignment(source="A", target="Y", value_expr="1"),),
        inner_node=inner,
        dataset_ref="edge_ds",
    )
    mtp_node = ModifiedTreatmentPolicyNode(
        treatment_var="A",
        policy_expr="A+delta",
        natural_treatment_var="A",
        covariates=("W",),
        inner_node=edge_node,
        dataset_ref="mtp_ds",
    )
    ast = EstimandAST(
        query_str="MTP(A+delta)",
        root=mtp_node,
        treatment="A",
        outcome="Y",
        all_variables=("A", "W", "Y"),
    )

    assert "MTP" in ast.to_latex()
    assert "edge_ds" in ast.required_datasets()
    assert "inner_ds" in ast.required_datasets()
    assert "mtp_ds" in ast.required_datasets()
    assert ast.normalize().root.node_type == "modified_treatment_policy"  # type: ignore[union-attr]
