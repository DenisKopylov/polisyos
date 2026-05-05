from __future__ import annotations

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.recourse_manifold import (
    ActionChannel,
    ActionDomain,
    CouplingCost,
    EquivalenceMode,
    InterventionCostManifold,
    InterventionProgram,
    OptimalRecourseInterventionBundle,
    OptimalRecourseInterventionQuery,
    PrimitiveAction,
    PrimitiveCost,
    RecourseReadinessCap,
    RecourseRecoverabilityStatus,
    RecourseSemantics,
    RecourseSolverStatus,
    RecourseSuccessMode,
    build_feasibility_certificate,
    build_recourse_proof_bundle,
    load_feasibility_certificate,
    load_intervention_cost_manifold,
    load_optimal_recourse_query,
    load_recourse_bundle,
    load_recourse_proof_bundle,
    persist_feasibility_certificate,
    persist_intervention_cost_manifold,
    persist_optimal_recourse_query,
    persist_recourse_bundle,
    persist_recourse_proof_bundle,
    render_recourse_query,
)


def _minimal_manifold() -> InterventionCostManifold:
    return InterventionCostManifold(
        scm_ref="scm:demo",
        factual_unit_ref="unit:1",
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        mutable_nodes=("education", "income"),
        immutable_nodes=("age",),
        action_channels=(
            ActionChannel(
                node="education",
                channel="certificate_course",
                prerequisite_refs=("prereq:education_course_eligible",),
            ),
            ActionChannel(node="income", channel="salary_raise"),
        ),
        prerequisite_refs=("prereq:education_course_eligible",),
        domains=(
            ActionDomain(
                node="education",
                kind="discrete",
                values=("bachelor", "master", "phd"),
            ),
            ActionDomain(
                node="income",
                kind="interval",
                lower=0.0,
                upper=1_000_000.0,
            ),
        ),
        primitive_costs=(
            PrimitiveCost(node="education", cost_kind="constant", base_cost=5.0),
            PrimitiveCost(node="income", cost_kind="linear", base_cost=1.0, slope=0.001),
        ),
        coupling_costs=(CouplingCost(kind="budget", nodes=("income", "education"), limit=1_000.0),),
        equivalence_mode=EquivalenceMode.SAME_COUNTERFACTUAL_DISTRIBUTION,
    )


def _query(manifold_ref) -> OptimalRecourseInterventionQuery:
    return OptimalRecourseInterventionQuery(
        factual_unit_ref="unit:1",
        target_outcome="loan_approval",
        target_value=1,
        threshold_tau=0.75,
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        success_mode=RecourseSuccessMode.POINT_PROBABILITY,
        intervention_cost_manifold_ref=manifold_ref,
        mutable_nodes=("education", "income"),
        immutable_nodes=("age",),
        support_budget=2,
    )


def test_manifold_rejects_mutable_immutable_overlap() -> None:
    with pytest.raises(ValueError, match="overlap"):
        InterventionCostManifold(
            scm_ref="scm:bad",
            factual_unit_ref="unit:1",
            semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
            mutable_nodes=("age",),
            immutable_nodes=("age",),
            action_channels=(ActionChannel(node="age", channel="chan"),),
            domains=(ActionDomain(node="age", kind="discrete", values=("18",)),),
            primitive_costs=(PrimitiveCost(node="age", cost_kind="constant", base_cost=1.0),),
        )


def test_manifold_rejects_missing_channel_for_mutable_node() -> None:
    with pytest.raises(ValueError, match="action_channels missing"):
        InterventionCostManifold(
            scm_ref="scm:bad",
            factual_unit_ref="unit:1",
            semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
            mutable_nodes=("income",),
            action_channels=(),
            domains=(ActionDomain(node="income", kind="interval", lower=0.0, upper=1.0),),
            primitive_costs=(PrimitiveCost(node="income", cost_kind="constant", base_cost=1.0),),
        )


def test_query_rejects_bounded_point_probability_combo() -> None:
    _minimal_manifold()
    from polisyos.ir.refs import InterventionCostManifoldRef

    manifold_ref = InterventionCostManifoldRef(
        artifact_id="sha256:" + "a" * 64,
        kind="ir.intervention_cost_manifold",
        media_type="application/json",
    )
    with pytest.raises(ValueError, match="bounded_recourse"):
        OptimalRecourseInterventionQuery(
            factual_unit_ref="unit:1",
            target_outcome="loan_approval",
            threshold_tau=0.5,
            semantics=RecourseSemantics.BOUNDED_RECOURSE,
            success_mode=RecourseSuccessMode.POINT_PROBABILITY,
            intervention_cost_manifold_ref=manifold_ref,
            mutable_nodes=("education",),
        )


def test_proof_bundle_caps_readiness_by_status() -> None:
    from polisyos.ir.refs import OptimalRecourseInterventionQueryRef

    query_ref = OptimalRecourseInterventionQueryRef(
        artifact_id="sha256:" + "b" * 64,
        kind="ir.optimal_recourse_intervention_query",
        media_type="application/json",
    )
    identified = build_recourse_proof_bundle(
        query_ref=query_ref,
        scm_ref="scm:demo",
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        success_mode=RecourseSuccessMode.POINT_PROBABILITY,
        recoverability_status=RecourseRecoverabilityStatus.IDENTIFIED,
        mutable_nodes=("education",),
    )
    assert identified.readiness_cap is RecourseReadinessCap.ESTIMATION_READY

    bounded = build_recourse_proof_bundle(
        query_ref=query_ref,
        scm_ref="scm:demo",
        semantics=RecourseSemantics.BOUNDED_RECOURSE,
        success_mode=RecourseSuccessMode.LOWER_IDENTIFICATION_BOUND,
        recoverability_status=RecourseRecoverabilityStatus.BOUNDED,
        mutable_nodes=("education",),
    )
    assert bounded.readiness_cap is RecourseReadinessCap.BOUNDS_READY

    nonrec = build_recourse_proof_bundle(
        query_ref=query_ref,
        scm_ref="scm:demo",
        semantics=RecourseSemantics.INTERVENTIONAL_SUBPOPULATION,
        success_mode=RecourseSuccessMode.LOWER_CONFIDENCE_BOUND,
        recoverability_status=RecourseRecoverabilityStatus.NONRECOVERABLE,
        mutable_nodes=("education",),
    )
    assert nonrec.readiness_cap is RecourseReadinessCap.PROOF_ONLY


def test_proof_bundle_rejects_bounded_point_probability_combo() -> None:
    from polisyos.ir.refs import OptimalRecourseInterventionQueryRef

    query_ref = OptimalRecourseInterventionQueryRef(
        artifact_id="sha256:" + "1" * 64,
        kind="ir.optimal_recourse_intervention_query",
        media_type="application/json",
    )
    with pytest.raises(ValueError, match="lower-bound success_mode"):
        build_recourse_proof_bundle(
            query_ref=query_ref,
            scm_ref="scm:demo",
            semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
            success_mode=RecourseSuccessMode.POINT_PROBABILITY,
            recoverability_status=RecourseRecoverabilityStatus.BOUNDED,
            mutable_nodes=("education",),
        )


def test_feasibility_certificate_flags_immutable_violation() -> None:
    manifold = _minimal_manifold()
    action = InterventionProgram(
        actions=(
            PrimitiveAction(node="age", target_value=21),
            PrimitiveAction(node="education", target_value="master"),
        )
    )
    cert = build_feasibility_certificate(
        action=action,
        factual_unit_ref="unit:1",
        scm_ref="scm:demo",
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        manifold=manifold,
        achieved_success_value=0.9,
        threshold_tau=0.75,
        success_measure=RecourseSuccessMode.POINT_PROBABILITY,
        structural_consistency_ok=True,
        optimality_status="exact",
    )
    assert cert.mutable_support_ok is False
    assert "age" in cert.immutable_violations
    assert cert.threshold_met is True


def test_feasibility_certificate_flags_out_of_domain_value() -> None:
    manifold = _minimal_manifold()
    action = InterventionProgram(
        actions=(PrimitiveAction(node="education", target_value="kindergarten"),)
    )
    cert = build_feasibility_certificate(
        action=action,
        factual_unit_ref="unit:1",
        scm_ref="scm:demo",
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        manifold=manifold,
        achieved_success_value=0.1,
        threshold_tau=0.75,
        success_measure=RecourseSuccessMode.POINT_PROBABILITY,
        structural_consistency_ok=True,
        optimality_status="heuristic",
    )
    assert cert.domain_constraints_ok is False
    assert cert.threshold_met is False


def test_feasibility_certificate_flags_missing_prerequisites() -> None:
    manifold = InterventionCostManifold(
        scm_ref="scm:demo",
        factual_unit_ref="unit:1",
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        mutable_nodes=("education",),
        action_channels=(
            ActionChannel(
                node="education",
                channel="certificate_course",
                prerequisite_refs=("prereq:education_course_eligible",),
            ),
        ),
        domains=(
            ActionDomain(
                node="education",
                kind="discrete",
                values=("master",),
            ),
        ),
        primitive_costs=(PrimitiveCost(node="education", cost_kind="constant", base_cost=5.0),),
        prerequisite_refs=(),
    )
    action = InterventionProgram(
        actions=(PrimitiveAction(node="education", target_value="master"),),
        metadata={"satisfied_prerequisite_refs": ()},
    )
    cert = build_feasibility_certificate(
        action=action,
        factual_unit_ref="unit:1",
        scm_ref="scm:demo",
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        manifold=manifold,
        achieved_success_value=0.8,
        threshold_tau=0.75,
        success_measure=RecourseSuccessMode.POINT_PROBABILITY,
        structural_consistency_ok=True,
        optimality_status="exact",
    )
    assert cert.prerequisite_constraints_ok is False


def test_feasibility_certificate_accepts_action_scoped_prerequisites() -> None:
    manifold = InterventionCostManifold(
        scm_ref="scm:demo",
        factual_unit_ref="unit:1",
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        mutable_nodes=("education",),
        action_channels=(
            ActionChannel(
                node="education",
                channel="certificate_course",
                prerequisite_refs=("prereq:education_course_eligible",),
            ),
        ),
        domains=(
            ActionDomain(
                node="education",
                kind="discrete",
                values=("master",),
            ),
        ),
        primitive_costs=(PrimitiveCost(node="education", cost_kind="constant", base_cost=5.0),),
        prerequisite_refs=(),
    )
    action = InterventionProgram(
        actions=(PrimitiveAction(node="education", target_value="master"),),
        metadata={"satisfied_prerequisite_refs": ("prereq:education_course_eligible",)},
    )
    cert = build_feasibility_certificate(
        action=action,
        factual_unit_ref="unit:1",
        scm_ref="scm:demo",
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        manifold=manifold,
        achieved_success_value=0.8,
        threshold_tau=0.75,
        success_measure=RecourseSuccessMode.POINT_PROBABILITY,
        structural_consistency_ok=True,
        optimality_status="exact",
    )
    assert cert.prerequisite_constraints_ok is True


def test_recourse_bundle_blocks_when_solver_status_blocked() -> None:
    from polisyos.ir.refs import (
        OptimalRecourseInterventionQueryRef,
        RecourseProofBundleRef,
    )

    query_ref = OptimalRecourseInterventionQueryRef(
        artifact_id="sha256:" + "c" * 64,
        kind="ir.optimal_recourse_intervention_query",
        media_type="application/json",
    )
    proof_ref = RecourseProofBundleRef(
        artifact_id="sha256:" + "d" * 64,
        kind="ir.recourse_proof_bundle",
        media_type="application/json",
    )
    with pytest.raises(ValueError, match="blocked_reason"):
        OptimalRecourseInterventionBundle(
            query_ref=query_ref,
            proof_ref=proof_ref,
            action=InterventionProgram(actions=()),
            achieved_cost=0.0,
            achieved_success_value=0.0,
            feasibility_certificate_ref=None,
            solver_status=RecourseSolverStatus.BLOCKED_NONRECOVERABLE,
            readiness_cap=RecourseReadinessCap.PROOF_ONLY,
        )


def test_render_recourse_query_is_stable() -> None:
    from polisyos.ir.refs import InterventionCostManifoldRef

    manifold_ref = InterventionCostManifoldRef(
        artifact_id="sha256:" + "e" * 64,
        kind="ir.intervention_cost_manifold",
        media_type="application/json",
    )
    q = _query(manifold_ref)
    rendered = render_recourse_query(q)
    assert rendered.startswith("recourse[counterfactual_unit|point_probability]:")
    assert "loan_approval" in rendered
    assert "0.75" in rendered
    assert "education" in rendered
    assert "income" in rendered


def test_contracts_roundtrip_through_cas(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    manifold = _minimal_manifold()
    manifold_ref = persist_intervention_cost_manifold(store, manifold)
    assert manifold_ref.kind == "ir.intervention_cost_manifold"

    query = _query(manifold_ref)
    query_ref = persist_optimal_recourse_query(store, query)
    assert query_ref.kind == "ir.optimal_recourse_intervention_query"

    proof = build_recourse_proof_bundle(
        query_ref=query_ref,
        scm_ref="scm:demo",
        semantics=query.semantics,
        success_mode=query.success_mode,
        recoverability_status=RecourseRecoverabilityStatus.IDENTIFIED,
        mutable_nodes=query.mutable_nodes,
        immutable_nodes=query.immutable_nodes,
    )
    proof_ref = persist_recourse_proof_bundle(store, proof)
    assert proof_ref.kind == "ir.recourse_proof_bundle"

    action = InterventionProgram(
        actions=(PrimitiveAction(node="education", target_value="master"),)
    )
    cert = build_feasibility_certificate(
        action=action,
        factual_unit_ref="unit:1",
        scm_ref="scm:demo",
        semantics=query.semantics,
        manifold=manifold,
        achieved_success_value=0.9,
        threshold_tau=query.threshold_tau,
        success_measure=query.success_mode,
        structural_consistency_ok=True,
        optimality_status="exact",
        optimality_gap=0.0,
        recoverability_ref=proof_ref,
    )
    cert_ref = persist_feasibility_certificate(store, cert)
    assert cert_ref.kind == "ir.recourse_feasibility_certificate"

    bundle = OptimalRecourseInterventionBundle(
        query_ref=query_ref,
        proof_ref=proof_ref,
        action=action,
        achieved_cost=5.0,
        achieved_success_value=0.9,
        feasibility_certificate_ref=cert_ref,
        solver_status=RecourseSolverStatus.EXACT,
        readiness_cap=proof.readiness_cap,
        candidate_supports_explored=3,
    )
    bundle_ref = persist_recourse_bundle(store, bundle)
    assert bundle_ref.kind == "ir.optimal_recourse_intervention_bundle"

    assert load_intervention_cost_manifold(store, manifold_ref) == manifold
    assert load_optimal_recourse_query(store, query_ref) == query
    assert load_recourse_proof_bundle(store, proof_ref) == proof
    assert load_feasibility_certificate(store, cert_ref) == cert
    assert load_recourse_bundle(store, bundle_ref) == bundle
