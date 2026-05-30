from __future__ import annotations

import pytest
from polisyos.foundry.methods.catalog.causal.recourse_manifold import (
    PlannerOptions,
    best_first_support_search,
    branch_and_bound_over_supports,
    build_discrete_atlas,
    exact_graph_search,
    optimal_recourse_intervention,
    program_cost,
)
from polisyos.ir.analytics.recourse_manifold import (
    ActionChannel,
    ActionDomain,
    CouplingCost,
    InterventionCostManifold,
    InterventionProgram,
    OptimalRecourseInterventionQuery,
    PrimitiveAction,
    PrimitiveCost,
    RecourseReadinessCap,
    RecourseRecoverabilityStatus,
    RecourseSemantics,
    RecourseSolverStatus,
)
from polisyos.ir.registry.refs import (
    InterventionCostManifoldRef,
    OptimalRecourseInterventionQueryRef,
)


def _threshold_scm(
    scores: dict[tuple[str, object], float], *, status=RecourseRecoverabilityStatus.IDENTIFIED
):
    """Build a mock SCM adapter whose success functional sums per-atom scores."""

    class _Mock:
        def identify_success_functional(self, query):
            return status, None, ["id_algorithm:success"]

        def success_value(self, query, action):
            total = 0.0
            for step in action.actions:
                key = (step.node, step.target_value)
                total += scores.get(key, 0.0)
            return total

        def canonicalise(self, manifold, action):
            return action

        def replay_structural_consistency(self, action):
            return True

    return _Mock()


def _discrete_manifold() -> InterventionCostManifold:
    return InterventionCostManifold(
        scm_ref="scm:demo",
        factual_unit_ref="unit:1",
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        mutable_nodes=("education", "income"),
        immutable_nodes=("age",),
        action_channels=(
            ActionChannel(node="education", channel="course"),
            ActionChannel(node="income", channel="raise"),
        ),
        domains=(
            ActionDomain(node="education", kind="discrete", values=("bachelor", "master")),
            ActionDomain(node="income", kind="discrete", values=("50k", "100k")),
        ),
        primitive_costs=(
            PrimitiveCost(node="education", cost_kind="constant", base_cost=2.0),
            PrimitiveCost(node="income", cost_kind="constant", base_cost=1.0),
        ),
    )


def _interval_manifold(*, income_cost: PrimitiveCost) -> InterventionCostManifold:
    return InterventionCostManifold(
        scm_ref="scm:demo",
        factual_unit_ref="unit:1",
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        mutable_nodes=("income",),
        immutable_nodes=("age",),
        action_channels=(ActionChannel(node="income", channel="raise"),),
        domains=(ActionDomain(node="income", kind="interval", lower=0.0, upper=100.0),),
        primitive_costs=(income_cost,),
    )


def _mixed_interval_manifold() -> InterventionCostManifold:
    return InterventionCostManifold(
        scm_ref="scm:demo",
        factual_unit_ref="unit:1",
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        mutable_nodes=("education", "income"),
        immutable_nodes=("age",),
        action_channels=(
            ActionChannel(node="education", channel="course"),
            ActionChannel(node="income", channel="raise"),
        ),
        domains=(
            ActionDomain(node="education", kind="discrete", values=("master",)),
            ActionDomain(node="income", kind="interval", lower=0.0, upper=100.0),
        ),
        primitive_costs=(
            PrimitiveCost(node="education", cost_kind="constant", base_cost=1.0),
            PrimitiveCost(
                node="income",
                cost_kind="tabular",
                base_cost=0.2,
                table={"100.0": 0.6},
            ),
        ),
    )


def _query(manifold_ref) -> OptimalRecourseInterventionQuery:
    return OptimalRecourseInterventionQuery(
        factual_unit_ref="unit:1",
        target_outcome="loan_approval",
        threshold_tau=0.75,
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        intervention_cost_manifold_ref=manifold_ref,
        mutable_nodes=("education", "income"),
        immutable_nodes=("age",),
        support_budget=2,
    )


def _refs():
    manifold_ref = InterventionCostManifoldRef(
        artifact_id="sha256:" + "a" * 64,
        kind="ir.intervention_cost_manifold",
        media_type="application/json",
    )
    query_ref = OptimalRecourseInterventionQueryRef(
        artifact_id="sha256:" + "b" * 64,
        kind="ir.optimal_recourse_intervention_query",
        media_type="application/json",
    )
    return manifold_ref, query_ref


def test_build_discrete_atlas_enumerates_all_atoms() -> None:
    manifold = _discrete_manifold()
    atlas = build_discrete_atlas(manifold)
    atoms = {(atom.node, atom.target_value) for atom in atlas.atoms}
    assert atoms == {
        ("education", "bachelor"),
        ("education", "master"),
        ("income", "50k"),
        ("income", "100k"),
    }
    assert atlas.is_finite_discrete is True


def test_program_cost_rejects_immutable_support() -> None:
    manifold = _discrete_manifold()
    action = InterventionProgram(actions=(PrimitiveAction(node="age", target_value=30),))
    assert program_cost(action, manifold) == float("inf")


def test_program_cost_respects_budget() -> None:
    manifold = InterventionCostManifold(
        scm_ref="scm:demo",
        factual_unit_ref="unit:1",
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        mutable_nodes=("education", "income"),
        action_channels=(
            ActionChannel(node="education", channel="course"),
            ActionChannel(node="income", channel="raise"),
        ),
        domains=(
            ActionDomain(node="education", kind="discrete", values=("master",)),
            ActionDomain(node="income", kind="discrete", values=("100k",)),
        ),
        primitive_costs=(
            PrimitiveCost(node="education", cost_kind="constant", base_cost=5.0),
            PrimitiveCost(node="income", cost_kind="constant", base_cost=5.0),
        ),
        coupling_costs=(CouplingCost(kind="budget", nodes=("education", "income"), limit=6.0),),
    )
    cheap = InterventionProgram(actions=(PrimitiveAction(node="education", target_value="master"),))
    too_expensive = InterventionProgram(
        actions=(
            PrimitiveAction(node="education", target_value="master"),
            PrimitiveAction(node="income", target_value="100k"),
        )
    )
    assert program_cost(cheap, manifold) == 5.0
    assert program_cost(too_expensive, manifold) == float("inf")


def test_public_solver_aliases_are_callable() -> None:
    assert callable(branch_and_bound_over_supports)
    assert callable(best_first_support_search)


def test_exact_graph_search_finds_cheapest_satisfying_program() -> None:
    manifold = _discrete_manifold()
    manifold_ref, query_ref = _refs()
    query = _query(manifold_ref)
    scm = _threshold_scm(
        {
            ("education", "master"): 0.6,
            ("education", "bachelor"): 0.1,
            ("income", "100k"): 0.3,
            ("income", "50k"): 0.1,
        }
    )
    atlas = build_discrete_atlas(manifold)
    result = exact_graph_search(
        query=query,
        manifold=manifold,
        atlas=atlas,
        scm=scm,
        options=PlannerOptions(support_budget=2),
    )
    assert result is not None
    action, cost, success, explored = result
    assert success >= query.threshold_tau
    assert set(action.support) == {"education", "income"}
    assert cost == pytest.approx(3.0)
    assert explored >= 1


def test_exact_graph_search_returns_none_when_budget_too_tight() -> None:
    manifold = _discrete_manifold()
    manifold_ref, query_ref = _refs()
    query = OptimalRecourseInterventionQuery(
        factual_unit_ref="unit:1",
        target_outcome="loan_approval",
        threshold_tau=0.9,
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        intervention_cost_manifold_ref=manifold_ref,
        mutable_nodes=("education", "income"),
        immutable_nodes=("age",),
        support_budget=1,
    )
    scm = _threshold_scm(
        {
            ("education", "master"): 0.5,
            ("income", "100k"): 0.4,
        }
    )
    atlas = build_discrete_atlas(manifold)
    result = exact_graph_search(
        query=query,
        manifold=manifold,
        atlas=atlas,
        scm=scm,
        options=PlannerOptions(support_budget=1),
    )
    assert result is None


def test_optimal_recourse_blocks_when_nonrecoverable() -> None:
    manifold = _discrete_manifold()
    manifold_ref, query_ref = _refs()
    query = _query(manifold_ref)
    scm = _threshold_scm({}, status=RecourseRecoverabilityStatus.NONRECOVERABLE)
    proof, bundle, cert = optimal_recourse_intervention(
        query=query, query_ref=query_ref, manifold=manifold, scm=scm
    )
    assert proof.recoverability_status is RecourseRecoverabilityStatus.NONRECOVERABLE
    assert proof.readiness_cap is RecourseReadinessCap.PROOF_ONLY
    assert bundle.solver_status is RecourseSolverStatus.BLOCKED_NONRECOVERABLE
    assert bundle.blocked_reason == "nonrecoverable_success_functional"
    assert cert is None


def test_optimal_recourse_blocks_when_no_feasible_action_exists() -> None:
    manifold = _discrete_manifold()
    manifold_ref, query_ref = _refs()
    query = OptimalRecourseInterventionQuery(
        factual_unit_ref="unit:1",
        target_outcome="loan_approval",
        threshold_tau=0.99,
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        intervention_cost_manifold_ref=manifold_ref,
        mutable_nodes=("education", "income"),
        immutable_nodes=("age",),
        support_budget=2,
    )
    scm = _threshold_scm(
        {
            ("education", "master"): 0.5,
            ("income", "100k"): 0.4,
        }
    )
    proof, bundle, cert = optimal_recourse_intervention(
        query=query, query_ref=query_ref, manifold=manifold, scm=scm
    )
    assert proof.recoverability_status is RecourseRecoverabilityStatus.IDENTIFIED
    assert bundle.solver_status is RecourseSolverStatus.BLOCKED_INFEASIBLE
    assert cert is None


def test_optimal_recourse_returns_exact_solution_and_feasibility_certificate() -> None:
    manifold = _discrete_manifold()
    manifold_ref, query_ref = _refs()
    query = _query(manifold_ref)
    scm = _threshold_scm(
        {
            ("education", "master"): 0.8,
            ("education", "bachelor"): 0.1,
            ("income", "100k"): 0.3,
            ("income", "50k"): 0.1,
        }
    )
    proof, bundle, cert = optimal_recourse_intervention(
        query=query, query_ref=query_ref, manifold=manifold, scm=scm
    )
    assert proof.recoverability_status is RecourseRecoverabilityStatus.IDENTIFIED
    assert bundle.solver_status is RecourseSolverStatus.EXACT
    assert bundle.readiness_cap is RecourseReadinessCap.ESTIMATION_READY
    assert bundle.achieved_cost == pytest.approx(2.0)
    assert bundle.achieved_success_value >= query.threshold_tau
    assert cert is not None
    assert cert.mutable_support_ok is True
    assert cert.domain_constraints_ok is True
    assert cert.structural_consistency_ok is True
    assert cert.threshold_met is True


def test_optimal_recourse_uses_interval_branch_for_convex_manifold() -> None:
    manifold = _interval_manifold(
        income_cost=PrimitiveCost(
            node="income",
            cost_kind="linear",
            base_cost=0.0,
            slope=0.01,
        )
    )
    manifold_ref, query_ref = _refs()
    query = OptimalRecourseInterventionQuery(
        factual_unit_ref="unit:1",
        target_outcome="loan_approval",
        threshold_tau=0.61,
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        intervention_cost_manifold_ref=manifold_ref,
        mutable_nodes=("income",),
        immutable_nodes=("age",),
        support_budget=1,
    )

    class _IntervalSCM:
        def identify_success_functional(self, query):
            return RecourseRecoverabilityStatus.IDENTIFIED, None, ["id_algorithm:success"]

        def success_value(self, query, action):
            if not action.actions:
                return 0.0
            return float(action.actions[0].target_value) / 100.0

        def canonicalise(self, manifold, action):
            return action

        def replay_structural_consistency(self, action):
            return True

    proof, bundle, cert = optimal_recourse_intervention(
        query=query,
        query_ref=query_ref,
        manifold=manifold,
        scm=_IntervalSCM(),
        options=PlannerOptions(interval_grid_size=9, support_budget=1),
    )

    assert proof.recoverability_status is RecourseRecoverabilityStatus.IDENTIFIED
    assert bundle.solver_status is RecourseSolverStatus.EPSILON_OPTIMAL
    assert bundle.readiness_cap is RecourseReadinessCap.ESTIMATION_READY
    assert bundle.action.support == ("income",)
    assert float(bundle.action.actions[0].target_value) == pytest.approx(62.5)
    assert bundle.achieved_cost == pytest.approx(0.625)
    assert cert is not None
    assert cert.optimality_status == "epsilon_optimal"
    assert cert.threshold_met is True


def test_optimal_recourse_uses_heuristic_branch_for_mixed_interval_manifold() -> None:
    manifold = _mixed_interval_manifold()
    manifold_ref, query_ref = _refs()
    query = OptimalRecourseInterventionQuery(
        factual_unit_ref="unit:1",
        target_outcome="loan_approval",
        threshold_tau=0.7,
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        intervention_cost_manifold_ref=manifold_ref,
        mutable_nodes=("education", "income"),
        immutable_nodes=("age",),
        support_budget=2,
    )

    class _MixedSCM:
        def identify_success_functional(self, query):
            return RecourseRecoverabilityStatus.IDENTIFIED, None, ["id_algorithm:success"]

        def success_value(self, query, action):
            total = 0.0
            for step in action.actions:
                if step.node == "education" and step.target_value == "master":
                    total += 0.35
                elif step.node == "income":
                    total += float(step.target_value) / 100.0 * 0.4
            return total

        def canonicalise(self, manifold, action):
            return action

        def replay_structural_consistency(self, action):
            return True

    proof, bundle, cert = optimal_recourse_intervention(
        query=query,
        query_ref=query_ref,
        manifold=manifold,
        scm=_MixedSCM(),
        options=PlannerOptions(
            interval_grid_size=9, heuristic_interval_grid_size=5, support_budget=2
        ),
    )

    assert proof.recoverability_status is RecourseRecoverabilityStatus.IDENTIFIED
    assert bundle.solver_status is RecourseSolverStatus.HEURISTIC
    assert set(bundle.action.support) == {"education", "income"}
    assert float(
        next(step.target_value for step in bundle.action.actions if step.node == "income")
    ) == pytest.approx(100.0)
    assert bundle.achieved_success_value >= query.threshold_tau
    assert cert is not None
    assert cert.optimality_status == "heuristic"
    assert cert.threshold_met is True
