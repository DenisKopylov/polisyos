from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.abstraction import (
    AbstractionCertificate,
    AbstractionPreservationType,
    FiniteStateAbstractionMap,
    VariableStateAbstraction,
    load_abstraction_certificate,
    load_finite_state_abstraction_map,
    persist_abstraction_certificate,
    persist_finite_state_abstraction_map,
    verify_finite_state_exact_abstraction,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.distributional import (
    CohortDimension,
    CouplingDiagnostics,
    DiscreteDistributionSummary,
    DistributionBin,
    DistributionalEffectBundle,
    DistributionalJustification,
    DistributionalReport,
    ImpactDirection,
    MetricUnit,
    WinnersLosersTable,
    load_distributional_effect_bundle,
    load_distributional_report,
    persist_discrete_distribution_summary,
    persist_distributional_effect_bundle,
    persist_distributional_report,
)
from polisyos.ir.analytics.dynamic_regime import RuntimeSupportStatus
from polisyos.ir.analytics.strategic import (
    FiniteStrategicPayoffTable,
    StrategicFallbackMode,
    StrategicResponseBundle,
    StrategicSCM,
    load_strategic_payoff_table,
    load_strategic_response_bundle,
    load_strategic_scm,
    persist_strategic_payoff_table,
    persist_strategic_response_bundle,
    persist_strategic_scm,
)
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
)
from polisyos.ir.refs import ArtifactRefModel
from polisyos.scientist.kernel.budgets import ComputeBudget


def _artifact_id(ch: str) -> str:
    return f"sha256:{ch * 64}"


def _artifact_ref(ch: str, *, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=_artifact_id(ch),
        kind=kind,
        media_type="application/json",
    )


def _distribution_summary(outcome_name: str) -> DiscreteDistributionSummary:
    return DiscreteDistributionSummary(
        outcome_name=outcome_name,
        sample_size=10,
        total_weight=10.0,
        weighting_mode="uniform",
        mean_value=2.0,
        min_value=1.0,
        max_value=3.0,
        bins=[
            DistributionBin(
                index=0,
                lower_edge=0.0,
                upper_edge=2.0,
                midpoint=1.0,
                probability=0.4,
                sample_count=4,
            ),
            DistributionBin(
                index=1,
                lower_edge=2.0,
                upper_edge=4.0,
                midpoint=3.0,
                probability=0.6,
                sample_count=6,
            ),
        ],
    )


def test_distributional_effect_bundle_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    baseline_ref = persist_discrete_distribution_summary(store, _distribution_summary("income"))
    counterfactual_ref = persist_discrete_distribution_summary(store, _distribution_summary("income"))
    quantile_ref = persist_discrete_distribution_summary(store, _distribution_summary("quantile_proxy"))
    tail_ref = persist_discrete_distribution_summary(store, _distribution_summary("tail_proxy"))

    bundle = DistributionalEffectBundle(
        outcome_name="income",
        justification=DistributionalJustification.SCENARIO,
        baseline_distribution_ref=baseline_ref,
        counterfactual_distribution_ref=counterfactual_ref,
        coupling_ref=None,
        coupling_diagnostics=CouplingDiagnostics(
            mass_conservation_error=0.0,
            support_mismatch_note=None,
            regularization_strength=0.05,
            sinkhorn_iterations=12,
            convergence_delta=1e-8,
            weighting_mode="uniform",
            identifiability_assumptions=["scenario_level_ot_coupling"],
        ),
        wasserstein_distance=0.5,
        quantile_shift_ref=quantile_ref,
        tail_risk_delta_ref=tail_ref,
        subgroup_distribution_refs=[],
        causal_assumptions=["distributional_estimand_not_proof_kernel_identified"],
        readiness_cap="simulation_ready",
    )

    bundle_ref = persist_distributional_effect_bundle(store, bundle)
    loaded = load_distributional_effect_bundle(store, bundle_ref)

    assert loaded == bundle
    assert loaded.justification is DistributionalJustification.SCENARIO


def test_distributional_validation_rejects_non_finite_metrics() -> None:
    with pytest.raises(ValidationError, match="mass_conservation_error"):
        CouplingDiagnostics(
            mass_conservation_error=float("inf"),
            weighting_mode="uniform",
            identifiability_assumptions=[],
        )


def test_distributional_effect_bundle_rejects_nan_wasserstein(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    baseline_ref = persist_discrete_distribution_summary(store, _distribution_summary("income"))
    counterfactual_ref = persist_discrete_distribution_summary(store, _distribution_summary("income"))

    with pytest.raises(ValidationError, match="wasserstein_distance"):
        DistributionalEffectBundle(
            outcome_name="income",
            justification=DistributionalJustification.SCENARIO,
            baseline_distribution_ref=baseline_ref,
            counterfactual_distribution_ref=counterfactual_ref,
            coupling_ref=None,
            coupling_diagnostics=CouplingDiagnostics(
                mass_conservation_error=0.0,
                weighting_mode="uniform",
                identifiability_assumptions=[],
            ),
            wasserstein_distance=float("nan"),
            quantile_shift_ref=None,
            tail_risk_delta_ref=None,
            subgroup_distribution_refs=[],
            causal_assumptions=[],
        )


def test_legacy_distributional_report_round_trip_unchanged(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    with pytest.raises(ValidationError):
        DistributionalReport(
            breakdowns=[],
            winners_losers=WinnersLosersTable(),
        )

    # Keep the legacy contract strict: one valid breakdown is still required.
    from polisyos.ir.analytics.distributional import CohortImpact, DimensionBreakdown

    valid_report = DistributionalReport(
        breakdowns=[
            DimensionBreakdown(
                dimension=CohortDimension.CUSTOM,
                dimension_label="Custom",
                primary_metric="income_delta",
                primary_metric_unit=MetricUnit.ABSOLUTE,
                cohorts=[
                    CohortImpact(
                        cohort_id="a",
                        cohort_label="A",
                        population_share=0.5,
                        metric_values={"income": 1.0},
                        metric_deltas={"income_delta": 0.2},
                        impact_direction=ImpactDirection.POSITIVE,
                    ),
                    CohortImpact(
                        cohort_id="b",
                        cohort_label="B",
                        population_share=0.5,
                        metric_values={"income": 1.0},
                        metric_deltas={"income_delta": -0.2},
                        impact_direction=ImpactDirection.NEGATIVE,
                    ),
                ],
            )
        ],
        winners_losers=WinnersLosersTable(),
        methodology="agent_aggregation",
    )

    report_ref = persist_distributional_report(store, valid_report)
    loaded = load_distributional_report(store, report_ref)

    assert loaded == valid_report


def _payoff_table(agent: str) -> FiniteStrategicPayoffTable:
    return FiniteStrategicPayoffTable(
        agent=agent,
        strategic_agents=("leader", "follower"),
        action_spaces={
            "leader": ("invest", "hold"),
            "follower": ("comply", "resist"),
        },
        payoffs={
            "leader=invest|follower=comply": 5.0 if agent == "leader" else 4.0,
            "leader=invest|follower=resist": 1.0 if agent == "leader" else 0.0,
            "leader=hold|follower=comply": 3.0 if agent == "leader" else 1.0,
            "leader=hold|follower=resist": 2.0 if agent == "leader" else 2.0,
        },
    )


def _finite_state_scm(*, macro: bool, mismatch: bool = False) -> StructuralCausalModelSpec:
    x_name = "X" if macro else "X_m"
    y_name = "Y" if macro else "Y_m"
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=[x_name, y_name],
        edges=[CausalEdge(src=x_name, dst=y_name)],
    )
    y_conditional = [
        {"when": {x_name: "0"}, "distribution": {"low": 1.0, "high": 0.0}},
        {
            "when": {x_name: "1"},
            "distribution": {"low": 0.0 if not mismatch else 1.0, "high": 1.0 if not mismatch else 0.0},
        },
    ]
    return StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable=x_name,
                parents=[],
                family=MechanismFamily.EMPIRICAL,
                family_params={
                    "state_space": ["0", "1"],
                    "distribution": {"0": 0.5, "1": 0.5},
                },
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable=y_name,
                parents=[x_name],
                family=MechanismFamily.EMPIRICAL,
                family_params={
                    "state_space": ["low", "high"],
                    "conditional_distribution": y_conditional,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
    )


def test_strategic_ir_contracts_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "strategic")
    leader_table_ref = persist_strategic_payoff_table(store, _payoff_table("leader"))
    follower_table_ref = persist_strategic_payoff_table(store, _payoff_table("follower"))
    contract = StrategicSCM(
        base_graph_ref=_artifact_ref("a", kind="ir.causal_graph_model"),
        strategic_agents=("leader", "follower"),
        utility_refs={
            "leader": leader_table_ref,
            "follower": follower_table_ref,
        },
        policy_rule_ref=_artifact_ref("b", kind="ir.policy_recommendation"),
        equilibrium_concept="stackelberg",
        compute_budget=ComputeBudget(max_llm_calls=0.0, max_sim_runs=16.0, max_wall_time_s=30.0),
    )
    contract_ref = persist_strategic_scm(store, contract)

    bundle = StrategicResponseBundle(
        causal_component_ref=_artifact_ref("c", kind="ir.causal_effect_report"),
        strategic_closure_ref=_artifact_ref("d", kind="ir.strategic_closure_summary"),
        equilibrium_selection_dependence="deterministic",
        equilibrium_set_ref=_artifact_ref("e", kind="ir.equilibrium_set_summary"),
        selected_equilibrium_ref=_artifact_ref("f", kind="ir.equilibrium_summary"),
        multiplicity_note=None,
        performative_shift_ref=_artifact_ref("1", kind="ir.performative_shift_summary"),
        post_adaptation_policy_value_ref=_artifact_ref(
            "2",
            kind="ir.post_adaptation_policy_value_summary",
        ),
        fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
    )
    bundle_ref = persist_strategic_response_bundle(store, bundle)

    assert load_strategic_payoff_table(store, leader_table_ref) == _payoff_table("leader")
    assert load_strategic_scm(store, contract_ref) == contract
    assert load_strategic_response_bundle(store, bundle_ref) == bundle


def test_strategic_scm_marks_nash_as_runtime_blocked() -> None:
    contract = StrategicSCM(
        base_graph_ref=_artifact_ref("a", kind="ir.causal_graph_model"),
        strategic_agents=("leader", "follower"),
        utility_refs={
            "leader": _artifact_ref("b", kind="ir.strategic_payoff_table"),
            "follower": _artifact_ref("c", kind="ir.strategic_payoff_table"),
        },
        policy_rule_ref=_artifact_ref("d", kind="ir.policy_recommendation"),
        equilibrium_concept="nash",
        compute_budget=ComputeBudget(max_llm_calls=0.0, max_sim_runs=16.0, max_wall_time_s=30.0),
    )

    assert contract.runtime_support_status is RuntimeSupportStatus.BLOCKED_RESEARCH
    assert contract.runtime_eligible is False


def test_abstraction_contracts_round_trip_and_exact_verification(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "abstraction")
    abstraction_map = FiniteStateAbstractionMap(
        variable_maps=(
            VariableStateAbstraction(
                micro_variable="X_m",
                macro_variable="X",
                state_map={"0": "0", "1": "1"},
            ),
            VariableStateAbstraction(
                micro_variable="Y_m",
                macro_variable="Y",
                state_map={"low": "low", "high": "high"},
            ),
        )
    )
    map_ref = persist_finite_state_abstraction_map(store, abstraction_map)
    certificate = AbstractionCertificate(
        micro_graph_ref=_artifact_ref("a", kind="ir.causal_graph_model"),
        macro_graph_ref=_artifact_ref("b", kind="ir.causal_graph_model"),
        abstraction_map_ref=map_ref,
        preservation_type=AbstractionPreservationType.EXACT,
        preserved_queries=("observational", "interventional"),
        error_bound=None,
    )
    cert_ref = persist_abstraction_certificate(store, certificate)

    assert load_finite_state_abstraction_map(store, map_ref) == abstraction_map
    assert load_abstraction_certificate(store, cert_ref) == certificate

    exact = verify_finite_state_exact_abstraction(
        _finite_state_scm(macro=False),
        _finite_state_scm(macro=True),
        abstraction_map,
        micro_graph_ref=_artifact_ref("c", kind="ir.causal_graph_model"),
        macro_graph_ref=_artifact_ref("d", kind="ir.causal_graph_model"),
        abstraction_map_ref=map_ref,
    )
    invalid = verify_finite_state_exact_abstraction(
        _finite_state_scm(macro=False),
        _finite_state_scm(macro=True, mismatch=True),
        abstraction_map,
        micro_graph_ref=_artifact_ref("e", kind="ir.causal_graph_model"),
        macro_graph_ref=_artifact_ref("f", kind="ir.causal_graph_model"),
        abstraction_map_ref=map_ref,
    )

    assert exact.preservation_type is AbstractionPreservationType.EXACT
    assert invalid.preservation_type is AbstractionPreservationType.INVALID
    assert invalid.error_bound is None
