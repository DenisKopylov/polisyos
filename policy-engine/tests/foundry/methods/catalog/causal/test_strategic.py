from __future__ import annotations

import hashlib
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.policy_learning import OptimalPolicyLearner
from polisyos.foundry.methods.catalog.causal.dtr import QLearningDTR
from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.foundry.methods.catalog.causal.strategic import (
    PerformativeLoopSpec,
    analyze_performative_loop,
    evaluate_strategic_hook,
    solve_strategic_response,
    strategic_result_summary,
)
from polisyos.foundry.methods.catalog.policy.frontier import MeanFieldEquilibriumEstimator
from polisyos.ir.analytics.abstraction import (
    AbstractionCertificate,
    AbstractionPreservationType,
    FiniteStateAbstractionMapRef,
)
from polisyos.ir.analytics.causal_queries import InterventionSpec
from polisyos.ir.analytics.strategic import (
    FiniteStrategicPayoffTable,
    MeanFieldSolveInput,
    PerformativeInstabilityReason,
    PerformativeLoopAnalysisScope,
    PerformativeLoopProofFamily,
    PerformativeLoopRecommendedAction,
    PerformativeLoopStabilityStatus,
    StrategicGameClass,
    StrategicFallbackMode,
    StrategicSCM,
    StrategicSolutionConcept,
    load_strategic_component_bounds_summary,
    load_strategic_decomposition_certificate,
    load_mean_field_equilibrium_certificate,
    load_mean_field_mass_conservation_report,
    load_mean_field_solver_residual_report,
    persist_strategic_solve_artifacts,
)
from polisyos.ir.refs import ArtifactRefModel
from polisyos.scientist.governance.passes.strategic_response_pass import _bundle_summary
from polisyos.scientist.kernel.budgets import ComputeBudget


def _artifact_id(ch: str) -> str:
    return f"sha256:{hashlib.sha256(ch.encode('utf-8')).hexdigest()}"


def _artifact_ref(artifact_id: str, *, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel.model_validate(
        {
            "artifact_id": _artifact_id(artifact_id),
            "kind": kind,
            "media_type": "application/json",
        }
    )


def _strategic_contract(*, equilibrium_concept: str = "stackelberg", max_sim_runs: float = 16.0) -> StrategicSCM:
    return StrategicSCM(
        base_graph_ref=_artifact_ref("graph", kind="ir.causal_graph_model"),
        strategic_agents=("leader", "follower"),
        utility_refs={
            "leader": _artifact_ref("leader-payoff", kind="ir.strategic_payoff_table"),
            "follower": _artifact_ref("follower-payoff", kind="ir.strategic_payoff_table"),
        },
        policy_rule_ref=_artifact_ref("policy", kind="ir.policy_recommendation"),
        equilibrium_concept=equilibrium_concept,
        compute_budget=ComputeBudget(
            max_llm_calls=0.0,
            max_sim_runs=max_sim_runs,
            max_wall_time_s=30.0,
        ),
    )


def _payoff_tables() -> dict[str, FiniteStrategicPayoffTable]:
    action_spaces = {
        "leader": ("low", "high"),
        "follower": ("stay", "switch"),
    }
    return {
        "leader": FiniteStrategicPayoffTable(
            agent="leader",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs={
                "leader=low|follower=stay": 1.0,
                "leader=low|follower=switch": 0.0,
                "leader=high|follower=stay": 2.0,
                "leader=high|follower=switch": 3.0,
            },
        ),
        "follower": FiniteStrategicPayoffTable(
            agent="follower",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs={
                "leader=low|follower=stay": 2.0,
                "leader=low|follower=switch": 1.0,
                "leader=high|follower=stay": 0.0,
                "leader=high|follower=switch": 3.0,
            },
        ),
    }


def _best_response_tables() -> dict[str, FiniteStrategicPayoffTable]:
    action_spaces = {
        "leader": ("left", "right"),
        "follower": ("up", "down"),
    }
    leader = {
        "leader=left|follower=up": 1.0,
        "leader=left|follower=down": 0.0,
        "leader=right|follower=up": 0.0,
        "leader=right|follower=down": 1.0,
    }
    follower = {
        "leader=left|follower=up": 1.0,
        "leader=left|follower=down": 0.0,
        "leader=right|follower=up": 0.0,
        "leader=right|follower=down": 1.0,
    }
    return {
        "leader": FiniteStrategicPayoffTable(
            agent="leader",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs=leader,
        ),
        "follower": FiniteStrategicPayoffTable(
            agent="follower",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs=follower,
        ),
    }


def _best_response_tables_noninvariant() -> dict[str, FiniteStrategicPayoffTable]:
    action_spaces = {
        "leader": ("left", "right"),
        "follower": ("up", "down"),
    }
    leader = {
        "leader=left|follower=up": 1.0,
        "leader=left|follower=down": 0.0,
        "leader=right|follower=up": 0.0,
        "leader=right|follower=down": 2.0,
    }
    follower = {
        "leader=left|follower=up": 1.0,
        "leader=left|follower=down": 0.0,
        "leader=right|follower=up": 0.0,
        "leader=right|follower=down": 2.0,
    }
    return {
        "leader": FiniteStrategicPayoffTable(
            agent="leader",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs=leader,
        ),
        "follower": FiniteStrategicPayoffTable(
            agent="follower",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs=follower,
        ),
    }


def _large_micro_tables() -> dict[str, FiniteStrategicPayoffTable]:
    action_spaces = {
        "leader": ("a0", "a1", "a2"),
        "follower": ("b0", "b1", "b2"),
    }
    leader_payoffs: dict[str, float] = {}
    follower_payoffs: dict[str, float] = {}
    for i, leader_action in enumerate(action_spaces["leader"]):
        for j, follower_action in enumerate(action_spaces["follower"]):
            key = f"leader={leader_action}|follower={follower_action}"
            leader_payoffs[key] = float(i + j)
            follower_payoffs[key] = float((2 * i) - j)
    return {
        "leader": FiniteStrategicPayoffTable(
            agent="leader",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs=leader_payoffs,
        ),
        "follower": FiniteStrategicPayoffTable(
            agent="follower",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs=follower_payoffs,
        ),
    }


def _macro_tables() -> dict[str, FiniteStrategicPayoffTable]:
    action_spaces = {
        "leader": ("coarse_low", "coarse_high"),
        "follower": ("stay", "switch"),
    }
    return {
        "leader": FiniteStrategicPayoffTable(
            agent="leader",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs={
                "leader=coarse_low|follower=stay": 0.5,
                "leader=coarse_low|follower=switch": 0.0,
                "leader=coarse_high|follower=stay": 1.0,
                "leader=coarse_high|follower=switch": 2.0,
            },
        ),
        "follower": FiniteStrategicPayoffTable(
            agent="follower",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs={
                "leader=coarse_low|follower=stay": 1.0,
                "leader=coarse_low|follower=switch": 0.0,
                "leader=coarse_high|follower=stay": 0.0,
                "leader=coarse_high|follower=switch": 2.0,
            },
        ),
    }


def _exact_certificate() -> AbstractionCertificate:
    return AbstractionCertificate(
        micro_graph_ref=_artifact_ref("micro-graph", kind="ir.causal_graph_model"),
        macro_graph_ref=_artifact_ref("macro-graph", kind="ir.causal_graph_model"),
        abstraction_map_ref=FiniteStateAbstractionMapRef.model_validate(
            {
                "artifact_id": _artifact_id("m"),
                "kind": "ir.finite_state_abstraction_map",
                "media_type": "application/json",
            }
        ),
        preservation_type=AbstractionPreservationType.EXACT,
        preserved_queries=("observational", "interventional"),
        error_bound=None,
    )


def _approximate_certificate(*, transfer_scope: str = "regret") -> AbstractionCertificate:
    return AbstractionCertificate(
        micro_graph_ref=_artifact_ref("micro-graph", kind="ir.causal_graph_model"),
        macro_graph_ref=_artifact_ref("macro-graph", kind="ir.causal_graph_model"),
        abstraction_map_ref=FiniteStateAbstractionMapRef.model_validate(
            {
                "artifact_id": _artifact_id("m"),
                "kind": "ir.finite_state_abstraction_map",
                "media_type": "application/json",
            }
        ),
        preservation_type=AbstractionPreservationType.APPROXIMATE,
        preserved_queries=("policy_value:macro", "regret:epsilon"),
        error_bound=0.2,
        metadata={
            "abstraction_family": "type_mean_affine",
            "allowed_intervention_family": "type_symmetric",
            "intervention_family_verified": True,
            "proof_obligations_satisfied": ["mean_closure", "controlled_mean_residual"],
            "non_preserved_queries": ["unit_level_equilibrium_selection"],
            "estimand_error_bounds": {
                "policy_value:macro": 0.2,
                "regret:epsilon": 0.2,
            },
            "diagnostics": {"macro_partition_residual": 0.0},
            "strategic_transfer_scope": transfer_scope,
        },
    )


def _policy_value_only_certificate() -> AbstractionCertificate:
    return AbstractionCertificate(
        micro_graph_ref=_artifact_ref("micro-graph", kind="ir.causal_graph_model"),
        macro_graph_ref=_artifact_ref("macro-graph", kind="ir.causal_graph_model"),
        abstraction_map_ref=FiniteStateAbstractionMapRef.model_validate(
            {
                "artifact_id": _artifact_id("m"),
                "kind": "ir.finite_state_abstraction_map",
                "media_type": "application/json",
            }
        ),
        preservation_type=AbstractionPreservationType.POLICY_VALUE_ONLY,
        preserved_queries=("policy_value:macro",),
        error_bound=0.2,
    )


def _continuous_policy_value_certificate() -> AbstractionCertificate:
    return AbstractionCertificate(
        micro_graph_ref=_artifact_ref("micro-graph", kind="ir.causal_graph_model"),
        macro_graph_ref=_artifact_ref("macro-graph", kind="ir.causal_graph_model"),
        abstraction_map_ref=FiniteStateAbstractionMapRef.model_validate(
            {
                "artifact_id": _artifact_id("m"),
                "kind": "ir.finite_state_abstraction_map",
                "media_type": "application/json",
            }
        ),
        preservation_type=AbstractionPreservationType.POLICY_VALUE_ONLY,
        preserved_queries=("policy_value:macro",),
        error_bound=0.2,
        metadata={
            "abstraction_family": "continuous_linear_gaussian",
            "error_bound_spec": {
                "scope": {
                    "query_family": "policy_value",
                    "interventions": "hard_or_soft_declared_scope",
                    "action_domain": "compact_box",
                },
                "state_metric": "weighted_l1",
                "distribution_metric": "wasserstein_1",
                "value_lipschitz_constant": 1.25,
                "global_state_bound": 0.11,
                "recommendation_margin_required": 0.4,
                "gain_matrix_spectral_radius": 0.45,
                "tightness_status": "exact_on_linear_gaussian",
            },
        },
    )


def _mean_field_contract() -> StrategicSCM:
    return StrategicSCM(
        base_graph_ref=_artifact_ref("mfg-graph", kind="ir.causal_graph_model"),
        strategic_agents=("population", "regulator"),
        utility_refs={
            "population": _artifact_ref("mfg-pop", kind="ir.strategic_payoff_table"),
            "regulator": _artifact_ref("mfg-reg", kind="ir.strategic_payoff_table"),
        },
        policy_rule_ref=_artifact_ref("mfg-policy", kind="ir.policy_recommendation"),
        equilibrium_descriptor={
            "game_class": StrategicGameClass.ANONYMOUS_AGGREGATIVE.value,
            "solution_concept": StrategicSolutionConcept.EPSILON_NASH.value,
            "existence_assumptions": (
                "bounded_strategy_space",
                "compact_population_response",
            ),
            "approximation_epsilon": 0.05,
        },
        compute_budget=ComputeBudget(
            max_llm_calls=0.0,
            max_sim_runs=16.0,
            max_wall_time_s=30.0,
        ),
    )


def _mean_field_inputs(
    *,
    positivity_status: str = "verified",
    uniqueness_status: str = "unique",
    selection_rule: str = "none",
    max_iter: int = 200,
    tol: float = 1.0e-8,
) -> dict[str, object]:
    identification: dict[str, object] = {
        "graph_semantics": "sigma_separation",
        "positivity_status": positivity_status,
        "selection_rule": selection_rule,
    }
    if positivity_status != "failed":
        identification["identified_estimands"] = ("welfare",)
    return {
        "reward_matrix": (
            (1.2, 0.9),
            (1.0, 1.1),
            (0.8, 1.3),
        ),
        "transition_tensor": (
            (
                (0.7, 0.2, 0.1),
                (0.2, 0.7, 0.1),
                (0.1, 0.3, 0.6),
            ),
            (
                (0.6, 0.3, 0.1),
                (0.1, 0.7, 0.2),
                (0.1, 0.2, 0.7),
            ),
        ),
        "congestion_costs": (0.1, 0.2, 0.15),
        "intervention_spec": InterventionSpec(type="shifted", shift=0.1).model_dump(mode="json"),
        "intervention_spec_ref": _artifact_ref(
            "mfg-intervention", kind="ir.intervention_certificate"
        ).model_dump(mode="json"),
        "baseline_policy_ref": _artifact_ref(
            "mfg-policy", kind="ir.policy_recommendation"
        ).model_dump(mode="json"),
        "mean_field_model_class": "second_order",
        "well_posedness": {
            "scm_solvability_ref": _artifact_ref("mfg-proof", kind="ir.proof_bundle").model_dump(mode="json"),
            "monotonicity_type": "lasry_lions",
            "convexity_verified": True,
            "regularity_scope": "discrete_anonymous_aggregative",
            "uniqueness_status": uniqueness_status,
        },
        "identification": identification,
        "stability": {
            "bound_type": "ergodic_exponential",
            "constant_C": 1.0,
            "decay_rate": 0.2,
            "metric": "W1",
        },
        "macro_simulation_config": {
            "population_measure_snapshot_ref": _artifact_ref(
                "mfg-pop-snapshot", kind="ir.population_measure_snapshot"
            ).model_dump(mode="json"),
            "coefficient_field_ref": _artifact_ref(
                "mfg-coeff", kind="ir.coefficient_field_estimate"
            ).model_dump(mode="json"),
            "runtime_mode": "replay",
            "numerics_scheme": "semi_implicit_finite_difference",
            "fixed_point_method": "forward_backward_sweep",
            "time_horizon": 4.0,
            "time_steps": 16,
            "state_grid_shape": (8, 4),
        },
        "discount": 0.9,
        "temperature": 0.4,
        "max_iter": max_iter,
        "tol": tol,
        "metadata": {"test_case": "stage_6_4_mfg"},
    }


def _make_dtr_data(
    n_units: int = 120,
    n_periods: int = 2,
    seed: int = 11,
) -> DynamicTreatmentData:
    rng = np.random.default_rng(seed)
    covariates = np.zeros((n_units, n_periods, 1), dtype=float)
    treatments = np.zeros((n_units, n_periods), dtype=int)
    covariates[:, 0, 0] = rng.standard_normal(n_units)
    for t in range(n_periods):
        treatments[:, t] = rng.integers(0, 2, size=n_units)
        if t < n_periods - 1:
            covariates[:, t + 1, 0] = (
                0.35 * covariates[:, t, 0] + 0.45 * treatments[:, t] + rng.normal(0.0, 0.3, n_units)
            )
    outcome = 1.8 * treatments.sum(axis=1) + covariates[:, 0, 0] + rng.normal(0.0, 0.4, n_units)
    return DynamicTreatmentData(
        outcome=outcome,
        treatment_sequence=treatments,
        covariate_sequence=covariates,
    )


def test_stackelberg_solver_selects_expected_leader_optimum() -> None:
    result = solve_strategic_response(
        _strategic_contract(equilibrium_concept="stackelberg"),
        _payoff_tables(),
        baseline_policy_value=5.0,
    )

    assert result.fallback_mode is StrategicFallbackMode.EXACT_EQUILIBRIUM
    assert result.selected_equilibrium == {"leader": "high", "follower": "switch"}
    assert result.performative_shift == 3.0
    assert result.post_adaptation_policy_value == 8.0


def test_best_response_fixed_point_exposes_multiplicity() -> None:
    result = solve_strategic_response(
        _strategic_contract(equilibrium_concept="best_response_fixed_point"),
        _best_response_tables(),
        baseline_policy_value=0.5,
    )

    assert result.fallback_mode is StrategicFallbackMode.EXACT_EQUILIBRIUM
    assert len(result.equilibrium_profiles) == 2
    assert result.multiplicity_note == "multiple_best_response_fixed_points"
    assert result.equilibrium_selection_dependence == "best_response_tie_breaking"


def test_solver_uses_bounds_when_exact_equilibrium_is_research_blocked() -> None:
    result = solve_strategic_response(
        _strategic_contract(equilibrium_concept="nash", max_sim_runs=16.0),
        _payoff_tables(),
        baseline_policy_value=10.0,
    )

    assert result.fallback_mode is StrategicFallbackMode.STRATEGIC_BOUNDS
    assert result.bounds is not None
    assert result.bounds == (10.5, 13.0)


def test_analyze_performative_loop_certifies_stateful_lipschitz_convergence() -> None:
    certificate = analyze_performative_loop(
        PerformativeLoopSpec(
            proof_family=PerformativeLoopProofFamily.STATEFUL_LIPSCHITZ,
            analysis_scope=PerformativeLoopAnalysisScope.ITERATED_LOOP,
            l_theta=0.4,
            l_s=0.2,
            l_psi=0.5,
            initial_distance_upper=1.0,
            delta_target=0.01,
        )
    )

    assert certificate.stability_status is PerformativeLoopStabilityStatus.CERTIFIED_CONVERGENT
    assert certificate.contraction_upper_bound == 0.4
    assert certificate.recommended_action is PerformativeLoopRecommendedAction.ALLOW_AUTO_ITERATION
    assert certificate.iterations_to_delta_bound == 6


def test_analyze_performative_loop_uses_local_instability_witness() -> None:
    certificate = analyze_performative_loop(
        PerformativeLoopSpec(
            proof_family=PerformativeLoopProofFamily.STATEFUL_LIPSCHITZ,
            analysis_scope=PerformativeLoopAnalysisScope.ITERATED_LOOP,
            l_theta=0.4,
            l_s=0.9,
            l_psi=0.5,
            local_spectral_radius_estimate=1.12,
            simulation_horizon=12,
        )
    )

    assert certificate.stability_status is PerformativeLoopStabilityStatus.CERTIFIED_UNSTABLE
    assert certificate.reason_code is PerformativeInstabilityReason.LOCAL_SPECTRAL_RADIUS_GT_ONE
    assert certificate.recommended_action is PerformativeLoopRecommendedAction.BLOCK_AUTO_ITERATION


def test_solver_exposes_performative_loop_summary_from_contract_metadata() -> None:
    contract = _strategic_contract().model_copy(
        update={
            "metadata": {
                "performative_loop_spec": PerformativeLoopSpec(
                    proof_family=PerformativeLoopProofFamily.RRM_PARAMETRIC,
                    analysis_scope=PerformativeLoopAnalysisScope.ITERATED_LOOP,
                    beta=2.0,
                    gamma=4.0,
                    epsilon=0.5,
                ).model_dump(mode="json")
            }
        }
    )

    result = solve_strategic_response(
        contract,
        _payoff_tables(),
        baseline_policy_value=5.0,
    )
    summary = strategic_result_summary(result)

    assert result.performative_loop_certificate is not None
    assert summary["performative_loop"]["stability_status"] == "certified_convergent"
    assert summary["performative_loop"]["recommended_action"] == "allow_auto_iteration"
    assert summary["decomposition_status"] == "exact"
    assert summary["causal_component_value"] == pytest.approx(5.0)
    assert summary["strategic_component_value"] == pytest.approx(3.0)


def test_best_response_fixed_point_summary_is_selector_invariant_when_equilibria_share_payoff() -> None:
    result = solve_strategic_response(
        _strategic_contract(equilibrium_concept="best_response_fixed_point"),
        _best_response_tables(),
        baseline_policy_value=2.0,
    )

    summary = strategic_result_summary(result)

    assert summary["decomposition_status"] == "selector_invariant"
    assert summary["causal_component_value"] == pytest.approx(2.0)
    assert summary["strategic_component_value"] == pytest.approx(1.0)


def test_best_response_fixed_point_summary_is_bounded_when_equilibria_change_payoff() -> None:
    result = solve_strategic_response(
        _strategic_contract(equilibrium_concept="best_response_fixed_point"),
        _best_response_tables_noninvariant(),
        baseline_policy_value=2.0,
    )

    summary = strategic_result_summary(result)

    assert summary["decomposition_status"] == "bounded"
    assert summary["causal_component_bounds"] == pytest.approx([2.0, 2.0])
    assert summary["strategic_component_bounds"] == pytest.approx([1.0, 2.0])


def test_macro_abstracted_fallback_requires_exact_certificate() -> None:
    result = solve_strategic_response(
        _strategic_contract(equilibrium_concept="stackelberg", max_sim_runs=4.0),
        _large_micro_tables(),
        baseline_policy_value=1.0,
        macro_payoff_tables=_macro_tables(),
    )

    assert result.fallback_mode is StrategicFallbackMode.BLOCKED
    assert result.blocked_reason == "macro_abstracted_requires_exact_abstraction_certificate"


def test_macro_abstracted_fallback_works_with_exact_certificate() -> None:
    result = solve_strategic_response(
        _strategic_contract(equilibrium_concept="stackelberg", max_sim_runs=4.0),
        _large_micro_tables(),
        baseline_policy_value=1.0,
        abstraction_certificate=_exact_certificate(),
        macro_payoff_tables=_macro_tables(),
    )

    assert result.fallback_mode is StrategicFallbackMode.MACRO_ABSTRACTED
    assert result.selected_equilibrium == {"leader": "coarse_high", "follower": "switch"}
    assert result.post_adaptation_policy_value == 3.0
    assert result.closure_summary["abstraction_map_ref"] == _artifact_id("m")
    assert result.closure_summary["abstraction_transfer_scope"] == "equilibrium"


def test_anonymous_aggregative_runtime_requires_mean_field_payload_even_with_macro_certificate() -> None:
    contract = StrategicSCM(
        base_graph_ref=_artifact_ref("graph", kind="ir.causal_graph_model"),
        strategic_agents=("leader", "follower"),
        utility_refs={
            "leader": _artifact_ref("leader-payoff", kind="ir.strategic_payoff_table"),
            "follower": _artifact_ref("follower-payoff", kind="ir.strategic_payoff_table"),
        },
        policy_rule_ref=_artifact_ref("policy", kind="ir.policy_recommendation"),
        equilibrium_concept="epsilon_nash_anonymous",
        compute_budget=ComputeBudget(
            max_llm_calls=0.0,
            max_sim_runs=4.0,
            max_wall_time_s=30.0,
        ),
    )

    result = solve_strategic_response(
        contract,
        _large_micro_tables(),
        baseline_policy_value=1.0,
        abstraction_certificate=_approximate_certificate(),
        macro_payoff_tables=_macro_tables(),
    )

    assert result.fallback_mode is StrategicFallbackMode.BLOCKED
    assert result.blocked_reason == "missing_mean_field_game_payload"


def test_anonymous_aggregative_runtime_does_not_silent_fallback_to_policy_value_macro_mode() -> None:
    contract = StrategicSCM(
        base_graph_ref=_artifact_ref("graph", kind="ir.causal_graph_model"),
        strategic_agents=("leader", "follower"),
        utility_refs={
            "leader": _artifact_ref("leader-payoff", kind="ir.strategic_payoff_table"),
            "follower": _artifact_ref("follower-payoff", kind="ir.strategic_payoff_table"),
        },
        policy_rule_ref=_artifact_ref("policy", kind="ir.policy_recommendation"),
        equilibrium_concept="epsilon_nash_anonymous",
        compute_budget=ComputeBudget(
            max_llm_calls=0.0,
            max_sim_runs=4.0,
            max_wall_time_s=30.0,
        ),
    )

    result = solve_strategic_response(
        contract,
        _large_micro_tables(),
        baseline_policy_value=1.0,
        abstraction_certificate=_policy_value_only_certificate(),
        macro_payoff_tables=_macro_tables(),
    )

    assert result.fallback_mode is StrategicFallbackMode.BLOCKED
    assert result.blocked_reason == "missing_mean_field_game_payload"


def test_anonymous_aggregative_runtime_blocks_before_macro_error_bound_projection_without_mfg_payload() -> None:
    contract = StrategicSCM(
        base_graph_ref=_artifact_ref("graph", kind="ir.causal_graph_model"),
        strategic_agents=("leader", "follower"),
        utility_refs={
            "leader": _artifact_ref("leader-payoff", kind="ir.strategic_payoff_table"),
            "follower": _artifact_ref("follower-payoff", kind="ir.strategic_payoff_table"),
        },
        policy_rule_ref=_artifact_ref("policy", kind="ir.policy_recommendation"),
        equilibrium_concept="epsilon_nash_anonymous",
        compute_budget=ComputeBudget(
            max_llm_calls=0.0,
            max_sim_runs=4.0,
            max_wall_time_s=30.0,
        ),
    )

    result = solve_strategic_response(
        contract,
        _large_micro_tables(),
        baseline_policy_value=1.0,
        abstraction_certificate=_continuous_policy_value_certificate(),
        macro_payoff_tables=_macro_tables(),
    )

    assert result.fallback_mode is StrategicFallbackMode.BLOCKED
    assert result.blocked_reason == "missing_mean_field_game_payload"


def test_anonymous_aggregative_runtime_blocks_before_macro_transfer_scope_checks_without_mfg_payload() -> None:
    result = solve_strategic_response(
        StrategicSCM(
            base_graph_ref=_artifact_ref("graph", kind="ir.causal_graph_model"),
            strategic_agents=("leader", "follower"),
            utility_refs={
                "leader": _artifact_ref("leader-payoff", kind="ir.strategic_payoff_table"),
                "follower": _artifact_ref("follower-payoff", kind="ir.strategic_payoff_table"),
            },
            policy_rule_ref=_artifact_ref("policy", kind="ir.policy_recommendation"),
            equilibrium_concept="epsilon_nash_anonymous",
            compute_budget=ComputeBudget(
                max_llm_calls=0.0,
                max_sim_runs=4.0,
                max_wall_time_s=30.0,
            ),
        ),
        _large_micro_tables(),
        baseline_policy_value=1.0,
        abstraction_certificate=_approximate_certificate(transfer_scope="unsupported"),
        macro_payoff_tables=_macro_tables(),
    )

    assert result.fallback_mode is StrategicFallbackMode.BLOCKED
    assert result.blocked_reason == "missing_mean_field_game_payload"


def test_anonymous_aggregative_runtime_blocks_before_macro_query_scope_checks_without_mfg_payload() -> None:
    result = solve_strategic_response(
        StrategicSCM(
            base_graph_ref=_artifact_ref("graph", kind="ir.causal_graph_model"),
            strategic_agents=("leader", "follower"),
            utility_refs={
                "leader": _artifact_ref("leader-payoff", kind="ir.strategic_payoff_table"),
                "follower": _artifact_ref("follower-payoff", kind="ir.strategic_payoff_table"),
            },
            policy_rule_ref=_artifact_ref("policy", kind="ir.policy_recommendation"),
            equilibrium_concept="epsilon_nash_anonymous",
            compute_budget=ComputeBudget(
                max_llm_calls=0.0,
                max_sim_runs=4.0,
                max_wall_time_s=30.0,
            ),
        ),
        _large_micro_tables(),
        baseline_policy_value=1.0,
        abstraction_certificate=AbstractionCertificate.model_validate(
            _approximate_certificate().model_dump(mode="json")
            | {
                "preserved_queries": ("policy_value:macro", "mean_potential_outcome:type_mean"),
                "metadata": (
                    _approximate_certificate().metadata
                    | {
                        "estimand_error_bounds": {
                            "policy_value:macro": 0.2,
                            "mean_potential_outcome:type_mean": 0.1,
                        }
                    }
                ),
            }
        ),
        macro_payoff_tables=_macro_tables(),
    )

    assert result.fallback_mode is StrategicFallbackMode.BLOCKED
    assert result.blocked_reason == "missing_mean_field_game_payload"


def test_solver_blocks_game_classes_marked_blocked_by_admissibility_registry() -> None:
    contract = StrategicSCM(
        base_graph_ref=_artifact_ref("graph", kind="ir.causal_graph_model"),
        strategic_agents=("leader", "follower"),
        utility_refs={
            "leader": _artifact_ref("leader-payoff", kind="ir.strategic_payoff_table"),
            "follower": _artifact_ref("follower-payoff", kind="ir.strategic_payoff_table"),
        },
        policy_rule_ref=_artifact_ref("policy", kind="ir.policy_recommendation"),
        equilibrium_descriptor={
            "game_class": StrategicGameClass.STACKELBERG_COMPLEX.value,
            "solution_concept": StrategicSolutionConcept.STACKELBERG_OPTIMISTIC.value,
            "existence_assumptions": (
                "multi_follower_commitment",
                "follower_equilibrium_selection_rule",
            ),
        },
        compute_budget=ComputeBudget(
            max_llm_calls=0.0,
            max_sim_runs=16.0,
            max_wall_time_s=30.0,
        ),
    )

    result = solve_strategic_response(
        contract,
        _payoff_tables(),
        baseline_policy_value=5.0,
    )

    assert result.fallback_mode is StrategicFallbackMode.BLOCKED
    assert result.blocked_reason == "strategic_game_class_default_blocked"


def test_mean_field_runtime_routes_anonymous_aggregative_contracts_to_mfg_solver() -> None:
    result = solve_strategic_response(
        _mean_field_contract(),
        {},
        baseline_policy_value=2.0,
        mean_field_inputs=_mean_field_inputs(),
    )

    assert result.fallback_mode is StrategicFallbackMode.EXACT_EQUILIBRIUM
    assert result.selected_equilibrium is None
    assert result.equilibrium_profiles == ()
    assert result.performative_shift is not None
    assert result.post_adaptation_policy_value is not None
    assert result.mfg_equilibrium_certificate is not None
    assert result.mfg_macro_simulation_config is not None
    assert result.closure_summary["runtime_branch"] == "mean_field_equilibrium"
    assert result.mfg_equilibrium_certificate.metadata["runtime_branch"] == (
        "policy.agent_sim.mean_field_equilibrium@1.0.0"
    )
    assert result.mfg_solver_residual_report is not None
    assert result.mfg_solver_residual_report.within_tolerance is True
    assert result.mfg_mass_conservation_report is not None
    assert result.mfg_mass_conservation_report.within_tolerance is True


def test_mean_field_runtime_persists_loadable_certificate_with_numerics_evidence(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "mfg-runtime")
    contract = _mean_field_contract()
    result = solve_strategic_response(
        contract,
        {},
        baseline_policy_value=2.0,
        mean_field_inputs=_mean_field_inputs(),
    )

    bundle, _ = persist_strategic_solve_artifacts(
        store,
        causal_component_ref=_artifact_ref("mfg-causal-report", kind="ir.causal_effect_report"),
        result=result,
        equilibrium_concept=contract.equilibrium_concept,
        equilibrium_descriptor=contract.equilibrium_descriptor,
        baseline_policy_value=2.0,
        mfg_equilibrium_certificate=result.mfg_equilibrium_certificate,
        mfg_macro_simulation_config=result.mfg_macro_simulation_config,
        mfg_solver_residual_report=result.mfg_solver_residual_report,
        mfg_mass_conservation_report=result.mfg_mass_conservation_report,
    )

    assert bundle.mfg_equilibrium_ref is not None
    loaded_certificate = load_mean_field_equilibrium_certificate(
        store,
        bundle.mfg_equilibrium_ref,
    )
    assert loaded_certificate.provenance is not None
    assert loaded_certificate.provenance.numerics_config_ref is not None
    assert loaded_certificate.equilibrium_solution is not None
    assert loaded_certificate.equilibrium_solution.solver_residual_ref is not None
    assert loaded_certificate.equilibrium_solution.mass_conservation_ref is not None
    solver_report = load_mean_field_solver_residual_report(
        store,
        loaded_certificate.equilibrium_solution.solver_residual_ref,
    )
    mass_report = load_mean_field_mass_conservation_report(
        store,
        loaded_certificate.equilibrium_solution.mass_conservation_ref,
    )
    assert solver_report.within_tolerance is True
    assert mass_report.within_tolerance is True
    governance_summary = _bundle_summary(store, bundle)
    assert governance_summary["mfg_has_solver_residual"] is True
    assert governance_summary["mfg_has_mass_conservation"] is True


def test_mean_field_runtime_requires_explicit_payload_for_supported_descriptor() -> None:
    result = solve_strategic_response(
        _mean_field_contract(),
        {},
        baseline_policy_value=2.0,
    )

    assert result.fallback_mode is StrategicFallbackMode.BLOCKED
    assert result.blocked_reason == "missing_mean_field_game_payload"


def test_mean_field_runtime_blocks_nonunique_equilibrium_without_selection_rule() -> None:
    result = solve_strategic_response(
        _mean_field_contract(),
        {},
        baseline_policy_value=2.0,
        mean_field_inputs=_mean_field_inputs(
            uniqueness_status="multiple",
            selection_rule="none",
        ),
    )

    assert result.fallback_mode is StrategicFallbackMode.BLOCKED
    assert result.blocked_reason == "mean_field_selection_rule_required"


def test_mean_field_runtime_blocks_failed_positivity_and_non_convergence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    positivity_failed = solve_strategic_response(
        _mean_field_contract(),
        {},
        baseline_policy_value=2.0,
        mean_field_inputs=_mean_field_inputs(positivity_status="failed"),
    )

    assert positivity_failed.fallback_mode is StrategicFallbackMode.BLOCKED
    assert positivity_failed.blocked_reason == "mean_field_positivity_failed"

    monkeypatch.setattr(
        MeanFieldEquilibriumEstimator,
        "pure_step",
        staticmethod(
            lambda state, params: {
                "result": {
                    "stationary_distribution": [1.0, 0.0, 0.0],
                    "policy_matrix": [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]],
                    "value_function": [0.0, 0.0, 0.0],
                    "mean_value": 0.0,
                    "converged": False,
                    "iterations": 200,
                }
            }
        ),
    )

    non_converged = solve_strategic_response(
        _mean_field_contract(),
        {},
        baseline_policy_value=2.0,
        mean_field_inputs=_mean_field_inputs(),
    )

    assert non_converged.fallback_mode is StrategicFallbackMode.BLOCKED
    assert non_converged.blocked_reason == "mean_field_solver_nonconvergent"

    monkeypatch.setattr(
        MeanFieldEquilibriumEstimator,
        "pure_step",
        staticmethod(
            lambda state, params: {
                "result": {
                    "stationary_distribution": [1.2, -0.2, 0.0],
                    "policy_matrix": [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]],
                    "value_function": [0.0, 0.0, 0.0],
                    "mean_value": 0.0,
                    "converged": True,
                    "iterations": 2,
                }
            }
        ),
    )

    diagnostics_failed = solve_strategic_response(
        _mean_field_contract(),
        {},
        baseline_policy_value=2.0,
        mean_field_inputs=_mean_field_inputs(),
    )

    assert diagnostics_failed.fallback_mode is StrategicFallbackMode.BLOCKED
    assert diagnostics_failed.blocked_reason == "mean_field_solution_diagnostics_failed"


def test_evaluate_hook_emits_summary_only_even_with_runtime_refs() -> None:
    params = {
        "strategic_scm": _strategic_contract().model_dump(mode="json"),
        "strategic_payoff_tables": {
            agent: table.model_dump(mode="json") for agent, table in _payoff_tables().items()
        },
        "strategic_runtime_refs": {
            "causal_component_ref": _artifact_ref("causal", kind="ir.causal_effect_report").model_dump(mode="json"),
            "strategic_closure_ref": _artifact_ref("closure", kind="ir.strategic_closure_summary").model_dump(mode="json"),
            "equilibrium_set_ref": _artifact_ref("eqset", kind="ir.equilibrium_set_summary").model_dump(mode="json"),
            "post_adaptation_policy_value_ref": _artifact_ref(
                "value", kind="ir.post_adaptation_policy_value_summary"
            ).model_dump(mode="json"),
            "selected_equilibrium_ref": _artifact_ref("selected", kind="ir.equilibrium_summary").model_dump(mode="json"),
            "performative_shift_ref": _artifact_ref("shift", kind="ir.performative_shift_summary").model_dump(mode="json"),
        },
    }

    summary, warnings, bundle = evaluate_strategic_hook(params=params, baseline_policy_value=2.0)

    assert warnings == ()
    assert summary is not None
    assert summary["fallback_mode"] == StrategicFallbackMode.EXACT_EQUILIBRIUM.value
    assert summary["decomposition_status"] == "exact"
    assert bundle is None


def test_persist_strategic_solve_artifacts_auto_persists_exact_decomposition_artifacts(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "strategic-exact")
    contract = _strategic_contract()
    result = solve_strategic_response(
        contract,
        _payoff_tables(),
        baseline_policy_value=2.0,
    )

    bundle, _ = persist_strategic_solve_artifacts(
        store,
        causal_component_ref=_artifact_ref("causal-report", kind="ir.causal_effect_report"),
        result=result,
        equilibrium_concept=contract.equilibrium_concept,
        equilibrium_descriptor=contract.equilibrium_descriptor,
        baseline_policy_value=2.0,
    )

    assert bundle.decomposition_status.value == "exact"
    assert bundle.decomposition_certificate_ref is not None
    assert bundle.anchor_equilibrium_ref is not None
    certificate = load_strategic_decomposition_certificate(
        store,
        bundle.decomposition_certificate_ref,
    )
    assert certificate.decomposition_status.value == "exact"
    assert certificate.cross_world_anchor_defined is True


def test_persist_strategic_solve_artifacts_auto_persists_bounded_component_artifacts(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "strategic-bounded")
    contract = _strategic_contract(equilibrium_concept="best_response_fixed_point")
    result = solve_strategic_response(
        contract,
        _best_response_tables_noninvariant(),
        baseline_policy_value=2.0,
    )

    bundle, _ = persist_strategic_solve_artifacts(
        store,
        causal_component_ref=_artifact_ref("causal-report-bounded", kind="ir.causal_effect_report"),
        result=result,
        equilibrium_concept=contract.equilibrium_concept,
        equilibrium_descriptor=contract.equilibrium_descriptor,
        baseline_policy_value=2.0,
    )

    assert bundle.decomposition_status.value == "bounded"
    assert bundle.causal_component_bounds_ref is not None
    assert bundle.strategic_component_bounds_ref is not None
    causal_bounds = load_strategic_component_bounds_summary(
        store,
        bundle.causal_component_bounds_ref,
    )
    strategic_bounds = load_strategic_component_bounds_summary(
        store,
        bundle.strategic_component_bounds_ref,
    )
    assert causal_bounds.lower_bound == pytest.approx(2.0)
    assert causal_bounds.upper_bound == pytest.approx(2.0)
    assert strategic_bounds.lower_bound == pytest.approx(1.0)
    assert strategic_bounds.upper_bound == pytest.approx(2.0)


def test_evaluate_hook_reads_mean_field_game_payload() -> None:
    params = {
        "strategic_scm": _mean_field_contract().model_dump(mode="json"),
        "mean_field_game": MeanFieldSolveInput.model_validate(
            _mean_field_inputs()
        ).model_dump(mode="json"),
    }

    summary, warnings, bundle = evaluate_strategic_hook(
        params=params,
        baseline_policy_value=2.0,
    )

    assert warnings == ()
    assert bundle is None
    assert summary is not None
    assert summary["fallback_mode"] == StrategicFallbackMode.EXACT_EQUILIBRIUM.value
    assert summary["mfg_equilibrium"]["mean_field_model_class"] == "second_order"


def test_dtr_integration_emits_strategic_metadata() -> None:
    result = QLearningDTR.pure_step(
        _make_dtr_data(),
        {
            "n_bootstrap": 20,
            "strategic_scm": _strategic_contract().model_dump(mode="json"),
            "strategic_payoff_tables": {
                agent: table.model_dump(mode="json") for agent, table in _payoff_tables().items()
            },
        },
    )

    summary = result["dtr_result"].metadata["strategic_response"]
    assert summary["fallback_mode"] == StrategicFallbackMode.EXACT_EQUILIBRIUM.value
    assert result["report"].metadata["strategic_response_present"] is True
    assert result["strategic_response_summary"]["selected_equilibrium"] == {
        "leader": "high",
        "follower": "switch",
    }
    assert "strategic_response_bundle" not in result


def test_policy_learning_integration_emits_summary_without_bundle(monkeypatch) -> None:
    class _FakeCausalForestDML:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def fit(self, y, t, X=None, W=None) -> None:
            self._n_obs = len(y)

        def effect(self, X):
            return np.linspace(0.1, 1.0, num=X.shape[0], dtype=float)

    class _FakePolicyTree:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs
            self.tree_ = SimpleNamespace(
                children_left=np.array([-1], dtype=int),
                children_right=np.array([-1], dtype=int),
                feature=np.array([-2], dtype=int),
                threshold=np.array([-2.0], dtype=float),
                value=np.array([[[1.0]]], dtype=float),
            )

        def fit(self, X, cate_estimates) -> None:
            self._n_obs = X.shape[0]

        def predict(self, X):
            return np.ones(X.shape[0], dtype=int)

        def apply(self, X):
            return np.zeros(X.shape[0], dtype=int)

    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.causal.policy_learning.require_econml",
        lambda: None,
    )
    dml_module = ModuleType("econml.dml")
    dml_module.CausalForestDML = _FakeCausalForestDML
    policy_module = ModuleType("econml.policy")
    policy_module.PolicyTree = _FakePolicyTree
    monkeypatch.setitem(sys.modules, "econml.dml", dml_module)
    monkeypatch.setitem(sys.modules, "econml.policy", policy_module)

    n_obs = 60
    x = np.linspace(-1.0, 1.0, num=n_obs, dtype=float).reshape(n_obs, 1)
    treatment = np.tile(np.array([0, 1], dtype=int), n_obs // 2)
    outcome = 0.5 + 0.8 * treatment + x[:, 0]
    state = HTEObservationalData(
        outcome=outcome,
        treatment=treatment,
        covariates=x,
        feature_names=["feature_0"],
    )

    result = OptimalPolicyLearner.pure_step(
        state,
        {
            "cate_n_estimators": 20,
            "max_depth": 2,
            "min_samples_leaf": 10,
            "budget_fraction": 0.5,
            "strategic_scm": _strategic_contract().model_dump(mode="json"),
            "strategic_payoff_tables": {
                agent: table.model_dump(mode="json") for agent, table in _payoff_tables().items()
            },
        },
    )

    assert result["report"].metadata["strategic_response_present"] is True
    assert result["policy_recommendation"].metadata["strategic_response"]["fallback_mode"] == (
        StrategicFallbackMode.EXACT_EQUILIBRIUM.value
    )
    assert "strategic_response_summary" in result
    assert "strategic_response_bundle" not in result
