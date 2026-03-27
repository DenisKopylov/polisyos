from __future__ import annotations

import hashlib

import numpy as np

from polisyos.foundry.methods.catalog.causal.dtr import QLearningDTR
from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
from polisyos.foundry.methods.catalog.causal.strategic import (
    build_strategic_response_bundle,
    evaluate_strategic_hook,
    solve_strategic_response,
)
from polisyos.ir.analytics.abstraction import (
    AbstractionCertificate,
    AbstractionPreservationType,
    FiniteStateAbstractionMapRef,
)
from polisyos.ir.analytics.strategic import (
    FiniteStrategicPayoffTable,
    StrategicFallbackMode,
    StrategicSCM,
)
from polisyos.ir.refs import ArtifactRefModel
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


def test_evaluate_hook_builds_bundle_with_disclosure_fields() -> None:
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
    assert bundle is not None
    assert str(bundle.causal_component_ref.artifact_id) == _artifact_id("causal")
    assert str(bundle.strategic_closure_ref.artifact_id) == _artifact_id("closure")
    assert bundle.fallback_mode is StrategicFallbackMode.EXACT_EQUILIBRIUM


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
