from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.strategic import (
    PerformativeLoopSpec,
    persist_strategic_solve_artifacts,
    solve_strategic_response,
)
from polisyos.ir.analytics.abstraction import (
    AbstractionCertificate,
    AbstractionPreservationType,
    FiniteStateAbstractionMap,
    VariableStateAbstraction,
    abstraction_error_bound_spec,
    abstraction_recommendation_margin_required,
    load_abstraction_certificate,
    load_finite_state_abstraction_map,
    persist_abstraction_certificate,
    persist_finite_state_abstraction_map,
    verify_finite_state_exact_abstraction,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_queries import InterventionSpec
from polisyos.ir.analytics.distributional import (
    CausalAssumptionCard,
    CohortDimension,
    CouplingDiagnostics,
    DiscreteDistributionSummary,
    DistributionalBoundUniformity,
    DistributionalCouplingStatus,
    DistributionalEffectBundle,
    DistributionalJustification,
    DistributionalProofArtifact,
    DistributionalProofTarget,
    DistributionalReport,
    DistributionBin,
    ImpactDirection,
    MetricUnit,
    OrdinalPovertyEstimate,
    OrdinalPovertyReport,
    WinnersLosersTable,
    load_causal_assumption_card,
    load_distributional_effect_bundle,
    load_distributional_proof_artifact,
    load_distributional_report,
    load_ordinal_poverty_report,
    persist_causal_assumption_card,
    persist_discrete_distribution_summary,
    persist_distributional_effect_bundle,
    persist_distributional_proof_artifact,
    persist_distributional_report,
    persist_ordinal_poverty_report,
)
from polisyos.ir.analytics.dynamic_regime import RuntimeSupportStatus
from polisyos.ir.analytics.strategic import (
    FiniteStrategicPayoffTable,
    MeanFieldEquilibriumCertificate,
    MeanFieldMacroSimulationConfig,
    PerformativeLoopAnalysisScope,
    PerformativeLoopProofFamily,
    PerformativeLoopStabilityStatus,
    StrategicAdmissibilityRecord,
    StrategicDecompositionStatus,
    StrategicEquilibriumConcept,
    StrategicEquilibriumDescriptor,
    StrategicFallbackMode,
    StrategicGameClass,
    StrategicResponseBundle,
    StrategicSCM,
    StrategicSolutionConcept,
    StrategicTractabilityClass,
    compile_intervention_spec_to_mean_field_perturbation,
    load_mean_field_equilibrium_certificate,
    load_mean_field_macro_simulation_config,
    load_mean_field_perturbation_spec,
    load_performative_shift_summary,
    load_strategic_decomposition_certificate,
    load_strategic_payoff_table,
    load_strategic_response_bundle,
    load_strategic_scm,
    persist_mean_field_equilibrium_certificate,
    persist_mean_field_macro_simulation_config,
    persist_mean_field_perturbation_spec,
    persist_strategic_payoff_table,
    persist_strategic_response_bundle,
    persist_strategic_scm,
    strategic_admissibility_record_for,
    strategic_admissibility_records,
)
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
)
from polisyos.ir.registry.refs import ArtifactRefModel, EstimandASTRef, ProofBundleRef
from polisyos.scientist.orchestration.kernel.budgets import ComputeBudget


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


def _ordinal_poverty_estimate() -> OrdinalPovertyEstimate:
    return OrdinalPovertyEstimate(
        headcount_h=0.5,
        ordinal_intensity_a=0.4,
        ordinal_adjusted_headcount_q=0.2,
        af_m0_baseline=0.18,
        beta=1.0,
        k_threshold=2 / 3,
        n_agents=10,
        n_dimensions=3,
        n_poor=5,
        dimension_weights=(1 / 3, 1 / 3, 1 / 3),
        deprivation_cutoffs=(2, 2, 1),
        dimension_names=("health", "education", "housing"),
        threshold_weights_basis="equal",
        dimension_contributions={"available": True},
        cutoff_diagnostics={"recoding_invariance_bound": 0.0},
        poor_mask=(1, 1, 0, 0, 1, 0, 1, 0, 1, 0),
        breadth_scores=(1.0, 2 / 3, 1 / 3, 0.0, 2 / 3, 0.0, 1.0, 0.0, 2 / 3, 0.0),
        severity_scores=(0.6, 0.3, 0.1, 0.0, 0.4, 0.0, 0.7, 0.0, 0.5, 0.0),
        censored_scores=(0.6, 0.3, 0.0, 0.0, 0.4, 0.0, 0.7, 0.0, 0.5, 0.0),
    )


def test_distributional_effect_bundle_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    baseline_ref = persist_discrete_distribution_summary(store, _distribution_summary("income"))
    counterfactual_ref = persist_discrete_distribution_summary(
        store, _distribution_summary("income")
    )
    quantile_ref = persist_discrete_distribution_summary(
        store, _distribution_summary("quantile_proxy")
    )
    tail_ref = persist_discrete_distribution_summary(store, _distribution_summary("tail_proxy"))
    ordinal_ref = persist_ordinal_poverty_report(
        store,
        OrdinalPovertyReport(
            baseline=_ordinal_poverty_estimate(),
            counterfactual=_ordinal_poverty_estimate().model_copy(
                update={
                    "headcount_h": 0.4,
                    "ordinal_intensity_a": 0.35,
                    "ordinal_adjusted_headcount_q": 0.14,
                    "af_m0_baseline": 0.15,
                    "n_poor": 4,
                }
            ),
            source_simulation_ref="sha256:" + "f" * 64,
        ),
    )

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
        ordinal_poverty_ref=ordinal_ref,
        subgroup_distribution_refs=[],
        causal_assumptions=["distributional_estimand_not_proof_kernel_identified"],
        readiness_cap="simulation_ready",
    )

    bundle_ref = persist_distributional_effect_bundle(store, bundle)
    loaded = load_distributional_effect_bundle(store, bundle_ref)

    assert loaded == bundle
    assert loaded.justification is DistributionalJustification.SCENARIO
    assert loaded.marginal_justification is DistributionalJustification.SCENARIO
    assert loaded.marginal_law_justification is DistributionalJustification.SCENARIO
    assert loaded.coupling_justification is None
    assert loaded.distributional_query_kind == "interventional_law"
    assert loaded.distributional_bounds_refs == []
    assert loaded.marginal_law_proof_ref is None
    assert loaded.ordinal_poverty_ref == ordinal_ref


def test_ordinal_poverty_report_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    baseline = _ordinal_poverty_estimate()
    counterfactual = baseline.model_copy(
        update={
            "headcount_h": 0.3,
            "ordinal_intensity_a": 0.32,
            "ordinal_adjusted_headcount_q": 0.096,
            "af_m0_baseline": 0.12,
            "n_poor": 3,
        }
    )
    report = OrdinalPovertyReport(
        baseline=baseline,
        counterfactual=counterfactual,
        source_simulation_ref="sha256:" + "e" * 64,
        metadata={"run_id": "R_test"},
    )

    ref = persist_ordinal_poverty_report(store, report)
    loaded = load_ordinal_poverty_report(store, ref)

    assert loaded == report
    assert loaded.deltas["headcount_h"] == pytest.approx(-0.2)
    assert loaded.deltas["ordinal_adjusted_headcount_q"] == pytest.approx(-0.104)


def test_distributional_effect_bundle_uses_weakest_link_semantics(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    baseline_ref = persist_discrete_distribution_summary(store, _distribution_summary("income"))
    counterfactual_ref = persist_discrete_distribution_summary(
        store, _distribution_summary("income")
    )

    bundle = DistributionalEffectBundle(
        outcome_name="income",
        distributional_query_kind="interventional_law",
        justification=DistributionalJustification.IDENTIFIED,
        marginal_justification=DistributionalJustification.IDENTIFIED,
        marginal_law_justification=DistributionalJustification.IDENTIFIED,
        coupling_justification=DistributionalJustification.SCENARIO,
        baseline_distribution_ref=baseline_ref,
        counterfactual_distribution_ref=counterfactual_ref,
        coupling_ref=baseline_ref,
        coupling_diagnostics=CouplingDiagnostics(
            mass_conservation_error=0.0,
            weighting_mode="uniform",
            identifiability_assumptions=["scenario_level_ot_coupling"],
        ),
        distributional_proof_ref=_artifact_ref("d", kind="ir.distributional_proof_artifact"),
        causal_assumptions=["scenario_level_ot_coupling"],
    )

    assert bundle.justification is DistributionalJustification.SCENARIO
    assert bundle.marginal_justification is DistributionalJustification.IDENTIFIED
    assert bundle.marginal_law_justification is DistributionalJustification.IDENTIFIED
    assert bundle.coupling_justification is DistributionalJustification.SCENARIO


def test_distributional_effect_bundle_rejects_identified_without_proof(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    baseline_ref = persist_discrete_distribution_summary(store, _distribution_summary("income"))
    counterfactual_ref = persist_discrete_distribution_summary(
        store, _distribution_summary("income")
    )

    with pytest.raises(ValidationError, match="distributional_proof_ref"):
        DistributionalEffectBundle(
            outcome_name="income",
            justification=DistributionalJustification.IDENTIFIED,
            marginal_justification=DistributionalJustification.IDENTIFIED,
            marginal_law_justification=DistributionalJustification.IDENTIFIED,
            baseline_distribution_ref=baseline_ref,
            counterfactual_distribution_ref=counterfactual_ref,
            coupling_diagnostics=CouplingDiagnostics(
                mass_conservation_error=0.0,
                weighting_mode="uniform",
                identifiability_assumptions=[],
            ),
        )


def test_distributional_proof_artifact_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    card = CausalAssumptionCard(
        scope="marginal",
        status="identified_needed",
        theorem_family="id_backdoor",
        assumption_type="consistency",
        description="Consistency links observed and potential outcomes.",
        testable=False,
    )
    card_ref = persist_causal_assumption_card(store, card)

    artifact = DistributionalProofArtifact(
        base_proof_ref=ProofBundleRef.model_validate(
            _artifact_ref("a", kind="ir.proof_bundle").model_dump()
        ),
        estimand_ast_ref=EstimandASTRef.model_validate(
            _artifact_ref("b", kind="ir.estimand_ast").model_dump()
        ),
        target=DistributionalProofTarget.CDF,
        bound_uniformity=DistributionalBoundUniformity.IDENTIFIED,
        coupling_status=DistributionalCouplingStatus.NOT_USED,
        theorem_family="id_backdoor",
        assumption_card_refs=[card_ref],
        metadata={"distributional_query_kind": "interventional_law"},
    )

    artifact_ref = persist_distributional_proof_artifact(store, artifact)
    loaded_artifact = load_distributional_proof_artifact(store, artifact_ref)
    loaded_card = load_causal_assumption_card(store, card_ref)

    assert loaded_artifact == artifact
    assert loaded_artifact.target is DistributionalProofTarget.CDF
    assert loaded_artifact.bound_uniformity is DistributionalBoundUniformity.IDENTIFIED
    assert loaded_card == card


def test_distributional_proof_artifact_rejects_primary_quantile_claim() -> None:
    with pytest.raises(ValidationError, match="derived distributional targets"):
        DistributionalProofArtifact(
            base_proof_ref=ProofBundleRef.model_validate(
                _artifact_ref("a", kind="ir.proof_bundle").model_dump()
            ),
            target=DistributionalProofTarget.QUANTILE,
            bound_uniformity=DistributionalBoundUniformity.IDENTIFIED,
            coupling_status=DistributionalCouplingStatus.NOT_USED,
            theorem_family="id_backdoor",
        )


def test_distributional_proof_artifact_rejects_empty_marginal_claim() -> None:
    with pytest.raises(ValidationError, match="proof or curve refs"):
        DistributionalProofArtifact(
            target=DistributionalProofTarget.CDF,
            bound_uniformity=DistributionalBoundUniformity.NOT_APPLICABLE,
            coupling_status=DistributionalCouplingStatus.NOT_USED,
            theorem_family="distribution_law_scenario",
        )


def test_distributional_proof_artifact_rejects_pointwise_only_derived_bounds() -> None:
    with pytest.raises(ValidationError, match="pointwise-only"):
        DistributionalProofArtifact(
            base_proof_ref=ProofBundleRef.model_validate(
                _artifact_ref("a", kind="ir.proof_bundle").model_dump()
            ),
            target=DistributionalProofTarget.EXPECTED_SHORTFALL,
            derived_from_target=DistributionalProofTarget.CDF,
            bound_uniformity=DistributionalBoundUniformity.POINTWISE_ONLY,
            bounded_curve_ref=_artifact_ref("c", kind="ir.distributional_bounds_bundle"),
            coupling_status=DistributionalCouplingStatus.NOT_USED,
            theorem_family="makarov_bounds",
        )


def test_distributional_effect_bundle_requires_bounds_refs_for_bounded_justification(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    baseline_ref = persist_discrete_distribution_summary(store, _distribution_summary("income"))
    counterfactual_ref = persist_discrete_distribution_summary(
        store, _distribution_summary("income")
    )

    with pytest.raises(ValidationError, match="distributional_bounds_refs"):
        DistributionalEffectBundle(
            outcome_name="income",
            justification=DistributionalJustification.BOUNDED,
            marginal_justification=DistributionalJustification.BOUNDED,
            marginal_law_justification=DistributionalJustification.BOUNDED,
            baseline_distribution_ref=baseline_ref,
            counterfactual_distribution_ref=counterfactual_ref,
            coupling_diagnostics=CouplingDiagnostics(
                mass_conservation_error=0.0,
                weighting_mode="uniform",
                identifiability_assumptions=[],
            ),
        )


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
    counterfactual_ref = persist_discrete_distribution_summary(
        store, _distribution_summary("income")
    )

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
            "leader=hold|follower=resist": 2.0,
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
            "distribution": {
                "low": 0.0 if not mismatch else 1.0,
                "high": 1.0 if not mismatch else 0.0,
            },
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
        decomposition_status=StrategicDecompositionStatus.EXACT,
        decomposition_certificate_ref=_artifact_ref(
            "3",
            kind="ir.strategic_decomposition_certificate",
        ),
        anchor_equilibrium_ref=_artifact_ref(
            "4",
            kind="ir.equilibrium_selection_summary",
        ),
        fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
    )
    bundle_ref = persist_strategic_response_bundle(store, bundle)

    assert load_strategic_payoff_table(store, leader_table_ref) == _payoff_table("leader")
    assert load_strategic_scm(store, contract_ref) == contract
    assert load_strategic_response_bundle(store, bundle_ref) == bundle


def test_mean_field_equilibrium_certificate_round_trip_and_exact_bundle_support(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "mfg")
    perturbation = compile_intervention_spec_to_mean_field_perturbation(
        InterventionSpec(type="stochastic", distribution="eligibility_kernel_v2"),
        source_intervention_ref=_artifact_ref("b", kind="ir.intervention_certificate"),
        baseline_policy_ref=_artifact_ref("a", kind="ir.policy_recommendation"),
    )
    perturbation_ref = persist_mean_field_perturbation_spec(store, perturbation)
    numerics_config = MeanFieldMacroSimulationConfig(
        population_measure_snapshot_ref=_artifact_ref("c", kind="ir.population_measure_snapshot"),
        coefficient_field_ref=_artifact_ref("d", kind="ir.coefficient_field_estimate"),
        policy_kernel_ref=_artifact_ref("e", kind="ir.policy_kernel_estimate"),
        numerics_scheme="semi_implicit_finite_difference",
        fixed_point_method="forward_backward_sweep",
        runtime_mode="replay",
        time_horizon=12.0,
        time_steps=120,
        state_grid_shape=(64, 32),
    )
    numerics_config_ref = persist_mean_field_macro_simulation_config(store, numerics_config)
    certificate = MeanFieldEquilibriumCertificate(
        intervention_kind="distributional",
        baseline_policy_ref=_artifact_ref("a", kind="ir.policy_recommendation"),
        intervention_spec_ref=perturbation_ref,
        mean_field_model_class="second_order",
        well_posedness={
            "scm_solvability_ref": _artifact_ref("f", kind="ir.proof_bundle"),
            "monotonicity_type": "lasry_lions",
            "convexity_verified": True,
            "regularity_scope": "Lipschitz_in_measure",
            "uniqueness_status": "local_stable_branch",
        },
        identification={
            "graph_semantics": "sigma_separation",
            "positivity_status": "verified",
            "selection_rule": "stable_branch",
            "identified_estimands": ("welfare", "fiscal_cost"),
        },
        equilibrium_solution={
            "hjb_solution_ref": _artifact_ref("1", kind="ir.hjb_solution"),
            "fp_solution_ref": _artifact_ref("2", kind="ir.fp_solution"),
            "solver_residual_ref": _artifact_ref("3", kind="ir.solver_residual"),
            "mass_conservation_ref": _artifact_ref("6", kind="ir.mass_conservation_report"),
        },
        stability={
            "bound_type": "ergodic_exponential",
            "constant_C": 1.0,
            "decay_rate": 0.2,
            "metric": "W1",
        },
        provenance={
            "data_snapshot_ref": _artifact_ref("4", kind="ir.data_snapshot"),
            "calibration_bundle_ref": _artifact_ref("5", kind="ir.calibration_bundle"),
            "numerics_config_ref": numerics_config_ref,
        },
    )

    certificate_ref = persist_mean_field_equilibrium_certificate(store, certificate)
    loaded_certificate = load_mean_field_equilibrium_certificate(store, certificate_ref)
    loaded_perturbation = load_mean_field_perturbation_spec(store, perturbation_ref)
    loaded_numerics_config = load_mean_field_macro_simulation_config(store, numerics_config_ref)

    bundle = StrategicResponseBundle(
        causal_component_ref=_artifact_ref("5", kind="ir.causal_effect_report"),
        strategic_closure_ref=_artifact_ref("6", kind="ir.strategic_closure_summary"),
        equilibrium_selection_dependence="mfg_stable_branch",
        equilibrium_set_ref=_artifact_ref("7", kind="ir.equilibrium_set_summary"),
        mfg_equilibrium_ref=certificate_ref,
        post_adaptation_policy_value_ref=_artifact_ref(
            "8",
            kind="ir.post_adaptation_policy_value_summary",
        ),
        decomposition_status=StrategicDecompositionStatus.EXACT,
        decomposition_certificate_ref=_artifact_ref(
            "9",
            kind="ir.strategic_decomposition_certificate",
        ),
        anchor_equilibrium_ref=_artifact_ref("a", kind="ir.equilibrium_selection_summary"),
        fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
    )

    bundle_ref = persist_strategic_response_bundle(store, bundle)
    loaded_bundle = load_strategic_response_bundle(store, bundle_ref)

    assert loaded_certificate.model_dump(mode="json") == certificate.model_dump(mode="json")
    assert loaded_perturbation == perturbation
    assert loaded_numerics_config == numerics_config
    assert loaded_certificate.mean_field_model_class.value == "second_order"
    assert loaded_certificate.identification.selection_rule.value == "stable_branch"
    assert loaded_perturbation.intervention_kind.value == "distributional"
    assert loaded_numerics_config.numerics_scheme.value == "semi_implicit_finite_difference"
    assert loaded_bundle == bundle
    assert loaded_bundle.mfg_equilibrium_ref == certificate_ref


def test_mean_field_perturbation_compiler_maps_policy_interventions() -> None:
    atomic = compile_intervention_spec_to_mean_field_perturbation(
        InterventionSpec(type="atomic", value=65.0)
    )
    truncated = compile_intervention_spec_to_mean_field_perturbation(
        InterventionSpec(type="truncated", bounds=(0.0, 1.0))
    )
    stochastic = compile_intervention_spec_to_mean_field_perturbation(
        InterventionSpec(type="stochastic", distribution="benefit_assignment_kernel")
    )

    assert atomic.intervention_kind.value == "coefficient"
    assert [channel.value for channel in atomic.representative_agent_channels] == [
        "running_cost",
        "terminal_payoff",
    ]
    assert truncated.intervention_kind.value == "mixed"
    assert [channel.value for channel in truncated.population_channels] == [
        "policy_kernel",
        "initial_distribution",
    ]
    assert stochastic.intervention_kind.value == "distributional"
    assert stochastic.policy_kernel_overlap_required is True


def test_strategic_response_bundle_rejects_discrete_and_mfg_equilibria_together() -> None:
    with pytest.raises(ValidationError):
        StrategicResponseBundle(
            causal_component_ref=_artifact_ref("a", kind="ir.causal_effect_report"),
            strategic_closure_ref=_artifact_ref("b", kind="ir.strategic_closure_summary"),
            equilibrium_selection_dependence="deterministic",
            equilibrium_set_ref=_artifact_ref("c", kind="ir.equilibrium_set_summary"),
            selected_equilibrium_ref=_artifact_ref("d", kind="ir.equilibrium_summary"),
            mfg_equilibrium_ref=_artifact_ref("e", kind="ir.mean_field_equilibrium_certificate"),
            post_adaptation_policy_value_ref=_artifact_ref(
                "f", kind="ir.post_adaptation_policy_value_summary"
            ),
            decomposition_status=StrategicDecompositionStatus.EXACT,
            decomposition_certificate_ref=_artifact_ref(
                "1", kind="ir.strategic_decomposition_certificate"
            ),
            fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
        )


def test_persist_strategic_solve_artifacts_can_attach_mfg_numerics_config(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "strategic-mfg-bundle")
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
    result = solve_strategic_response(
        contract,
        {"leader": _payoff_table("leader"), "follower": _payoff_table("follower")},
        baseline_policy_value=10.0,
    )
    perturbation_ref = persist_mean_field_perturbation_spec(
        store,
        compile_intervention_spec_to_mean_field_perturbation(
            InterventionSpec(type="shifted", shift=1.0),
            source_intervention_ref=_artifact_ref("c", kind="ir.intervention_certificate"),
            baseline_policy_ref=_artifact_ref("b", kind="ir.policy_recommendation"),
        ),
    )

    bundle, bundle_ref = persist_strategic_solve_artifacts(
        store,
        causal_component_ref=_artifact_ref("d", kind="ir.causal_effect_report"),
        result=result,
        equilibrium_concept=contract.equilibrium_concept,
        equilibrium_descriptor=contract.equilibrium_descriptor,
        baseline_policy_value=10.0,
        mfg_equilibrium_certificate=MeanFieldEquilibriumCertificate(
            intervention_kind="coefficient",
            baseline_policy_ref=_artifact_ref("b", kind="ir.policy_recommendation"),
            intervention_spec_ref=perturbation_ref,
            mean_field_model_class="second_order",
            well_posedness={
                "scm_solvability_ref": _artifact_ref("e", kind="ir.proof_bundle"),
                "monotonicity_type": "lasry_lions",
                "convexity_verified": True,
                "regularity_scope": "Lipschitz_in_measure",
                "uniqueness_status": "unique",
            },
            identification={
                "graph_semantics": "sigma_separation",
                "positivity_status": "verified",
                "selection_rule": "none",
                "identified_estimands": ("welfare",),
            },
            equilibrium_solution={
                "solver_residual_ref": _artifact_ref("f", kind="ir.solver_residual"),
                "mass_conservation_ref": _artifact_ref("1", kind="ir.mass_conservation_report"),
            },
        ),
        mfg_macro_simulation_config=MeanFieldMacroSimulationConfig(
            population_measure_snapshot_ref=_artifact_ref(
                "2", kind="ir.population_measure_snapshot"
            ),
            coefficient_field_ref=_artifact_ref("3", kind="ir.coefficient_field_estimate"),
            numerics_scheme="semi_implicit_finite_difference",
            fixed_point_method="forward_backward_sweep",
            runtime_mode="replay",
            time_horizon=6.0,
            time_steps=48,
            state_grid_shape=(24, 12),
        ),
    )

    loaded_bundle = load_strategic_response_bundle(store, bundle_ref)
    assert bundle.mfg_equilibrium_ref is not None
    assert loaded_bundle.mfg_equilibrium_ref is not None
    loaded_certificate = load_mean_field_equilibrium_certificate(
        store, loaded_bundle.mfg_equilibrium_ref
    )
    assert loaded_certificate.provenance is not None
    assert loaded_certificate.provenance.numerics_config_ref is not None


def test_persist_strategic_solve_artifacts_keeps_loop_certificate_without_point_shift(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "strategic-loop")
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
        equilibrium_concept="nash",
        compute_budget=ComputeBudget(max_llm_calls=0.0, max_sim_runs=16.0, max_wall_time_s=30.0),
    )
    result = solve_strategic_response(
        contract,
        {"leader": _payoff_table("leader"), "follower": _payoff_table("follower")},
        baseline_policy_value=10.0,
        performative_loop_spec=PerformativeLoopSpec(
            proof_family=PerformativeLoopProofFamily.RRM_PARAMETRIC,
            analysis_scope=PerformativeLoopAnalysisScope.ITERATED_LOOP,
            beta=3.0,
            gamma=2.0,
            epsilon=1.0,
        ),
    )

    bundle, _ = persist_strategic_solve_artifacts(
        store,
        causal_component_ref=_artifact_ref("c", kind="ir.causal_effect_report"),
        result=result,
        equilibrium_concept=contract.equilibrium_concept,
        equilibrium_descriptor=contract.equilibrium_descriptor,
        baseline_policy_value=10.0,
    )

    assert bundle.performative_shift_ref is not None
    shift_summary = load_performative_shift_summary(store, bundle.performative_shift_ref)
    assert shift_summary.performative_shift is None
    assert shift_summary.analysis_scope is PerformativeLoopAnalysisScope.ITERATED_LOOP
    assert shift_summary.stability_status is PerformativeLoopStabilityStatus.UNCERTIFIED


def test_persist_strategic_solve_artifacts_defaults_to_exact_decomposition_artifacts(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "strategic-decomposition")
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
    result = solve_strategic_response(
        contract,
        {"leader": _payoff_table("leader"), "follower": _payoff_table("follower")},
        baseline_policy_value=10.0,
    )

    bundle, _ = persist_strategic_solve_artifacts(
        store,
        causal_component_ref=_artifact_ref("c", kind="ir.causal_effect_report"),
        result=result,
        equilibrium_concept=contract.equilibrium_concept,
        equilibrium_descriptor=contract.equilibrium_descriptor,
        baseline_policy_value=10.0,
    )

    assert bundle.decomposition_status is StrategicDecompositionStatus.EXACT
    assert bundle.decomposition_certificate_ref is not None
    assert bundle.anchor_equilibrium_ref is not None
    certificate = load_strategic_decomposition_certificate(
        store,
        bundle.decomposition_certificate_ref,
    )
    assert certificate.decomposition_status is StrategicDecompositionStatus.EXACT
    assert certificate.cross_world_anchor_defined is True


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

    assert contract.equilibrium_descriptor == StrategicEquilibriumDescriptor(
        game_class=StrategicGameClass.NORMAL_FORM_GENERAL_SUM,
        solution_concept=StrategicSolutionConcept.MIXED_NASH,
        tractability_class=StrategicTractabilityClass.PPAD,
        existence_theorem="finite_mixed_nash_exists",
        existence_assumptions=("finite_game",),
        uniqueness_assumptions=(),
        approximation_epsilon=None,
        tie_breaking_rule=None,
        default_fallback_mode=StrategicFallbackMode.STRATEGIC_BOUNDS,
    )
    assert contract.runtime_support_status is RuntimeSupportStatus.BLOCKED_RESEARCH
    assert contract.runtime_eligible is False


def test_strategic_scm_normalizes_stackelberg_to_descriptor() -> None:
    contract = StrategicSCM(
        base_graph_ref=_artifact_ref("a", kind="ir.causal_graph_model"),
        strategic_agents=("leader", "follower"),
        utility_refs={
            "leader": _artifact_ref("b", kind="ir.strategic_payoff_table"),
            "follower": _artifact_ref("c", kind="ir.strategic_payoff_table"),
        },
        policy_rule_ref=_artifact_ref("d", kind="ir.policy_recommendation"),
        equilibrium_concept="stackelberg",
        compute_budget=ComputeBudget(max_llm_calls=0.0, max_sim_runs=16.0, max_wall_time_s=30.0),
    )

    assert contract.equilibrium_descriptor == StrategicEquilibriumDescriptor(
        game_class=StrategicGameClass.STACKELBERG_SINGLE_FOLLOWER,
        solution_concept=StrategicSolutionConcept.STACKELBERG_OPTIMISTIC,
        tractability_class=StrategicTractabilityClass.P,
        existence_theorem="single_follower_stackelberg_commitment_exists",
        existence_assumptions=("finite_action_space", "single_follower"),
        uniqueness_assumptions=(),
        approximation_epsilon=None,
        tie_breaking_rule="optimistic_leader_favorable",
        default_fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
    )
    assert contract.default_fallback_mode is StrategicFallbackMode.EXACT_EQUILIBRIUM
    assert contract.allowed_macro_preservation_types == (AbstractionPreservationType.EXACT,)


def test_strategic_scm_accepts_descriptor_only_for_anonymous_games() -> None:
    contract = StrategicSCM(
        base_graph_ref=_artifact_ref("a", kind="ir.causal_graph_model"),
        strategic_agents=("population", "regulator"),
        utility_refs={
            "population": _artifact_ref("b", kind="ir.strategic_payoff_table"),
            "regulator": _artifact_ref("c", kind="ir.strategic_payoff_table"),
        },
        policy_rule_ref=_artifact_ref("d", kind="ir.policy_recommendation"),
        equilibrium_descriptor={
            "game_class": "anonymous_aggregative",
            "solution_concept": "epsilon_nash",
            "existence_assumptions": ("bounded_strategy_space", "compact_population_response"),
            "approximation_epsilon": 0.05,
        },
        compute_budget=ComputeBudget(max_llm_calls=0.0, max_sim_runs=16.0, max_wall_time_s=30.0),
    )

    assert contract.equilibrium_concept is StrategicEquilibriumConcept.EPSILON_NASH_ANONYMOUS
    assert contract.equilibrium_descriptor == StrategicEquilibriumDescriptor(
        game_class=StrategicGameClass.ANONYMOUS_AGGREGATIVE,
        solution_concept=StrategicSolutionConcept.EPSILON_NASH,
        tractability_class=StrategicTractabilityClass.POLY_EPSILON,
        existence_theorem="anonymous_game_ptas_or_macro_limit",
        existence_assumptions=("bounded_strategy_space", "compact_population_response"),
        uniqueness_assumptions=(),
        approximation_epsilon=0.05,
        tie_breaking_rule=None,
        default_fallback_mode=StrategicFallbackMode.MACRO_ABSTRACTED,
    )
    assert contract.runtime_support_status is RuntimeSupportStatus.SUPPORTED
    assert contract.allowed_macro_preservation_types == (
        AbstractionPreservationType.EXACT,
        AbstractionPreservationType.APPROXIMATE,
        AbstractionPreservationType.POLICY_VALUE_ONLY,
    )


def test_strategic_admissibility_registry_exposes_stage_6_1_first_wave() -> None:
    records = strategic_admissibility_records()
    assert records
    assert all(isinstance(record, StrategicAdmissibilityRecord) for record in records)

    aliases = {alias for record in records for alias in record.equilibrium_concept_aliases}
    assert {
        StrategicEquilibriumConcept.MINIMAX_ZERO_SUM,
        StrategicEquilibriumConcept.MIXED_NASH_FINITE_GENERAL_SUM,
        StrategicEquilibriumConcept.STACKELBERG_SINGLE_FOLLOWER_OPTIMISTIC,
        StrategicEquilibriumConcept.STACKELBERG_SINGLE_FOLLOWER_PESSIMISTIC,
        StrategicEquilibriumConcept.PURE_NASH_POTENTIAL,
        StrategicEquilibriumConcept.VARIATIONAL_EQUILIBRIUM_MONOTONE,
        StrategicEquilibriumConcept.GNE_JOINTLY_CONVEX,
        StrategicEquilibriumConcept.EPSILON_NASH_ANONYMOUS,
    }.issubset(aliases)

    mixed = strategic_admissibility_record_for(
        game_class=StrategicGameClass.NORMAL_FORM_GENERAL_SUM,
        solution_concept=StrategicSolutionConcept.MIXED_NASH,
    )
    assert mixed.existence_theorem == "finite_mixed_nash_exists"
    assert mixed.tractability_class is StrategicTractabilityClass.PPAD
    assert mixed.default_fallback_mode is StrategicFallbackMode.STRATEGIC_BOUNDS


def test_strategic_scm_rejects_descriptor_missing_existence_assumptions() -> None:
    with pytest.raises(ValidationError, match="existence_assumptions"):
        StrategicSCM(
            base_graph_ref=_artifact_ref("a", kind="ir.causal_graph_model"),
            strategic_agents=("leader", "follower"),
            utility_refs={
                "leader": _artifact_ref("b", kind="ir.strategic_payoff_table"),
                "follower": _artifact_ref("c", kind="ir.strategic_payoff_table"),
            },
            policy_rule_ref=_artifact_ref("d", kind="ir.policy_recommendation"),
            equilibrium_descriptor={
                "game_class": "zero_sum",
                "solution_concept": "minimax",
            },
        )


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


def test_abstraction_certificate_accepts_approximate_type_mean_transport_contract(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "abstraction-approximate")
    map_ref = persist_finite_state_abstraction_map(
        store,
        FiniteStateAbstractionMap(
            variable_maps=(
                VariableStateAbstraction(
                    micro_variable="Y_m",
                    macro_variable="Y_bar",
                    state_map={"low": "low", "high": "high"},
                ),
            )
        ),
    )

    certificate = AbstractionCertificate(
        micro_graph_ref=_artifact_ref("a", kind="ir.causal_graph_model"),
        macro_graph_ref=_artifact_ref("b", kind="ir.causal_graph_model"),
        abstraction_map_ref=map_ref,
        preservation_type=AbstractionPreservationType.APPROXIMATE,
        preserved_queries=(
            "mean_potential_outcome:type_mean",
            "ate:type_mean",
            "policy_value:weighted_type_mean",
        ),
        error_bound=0.05,
        metadata={
            "abstraction_family": "type_mean_affine",
            "allowed_intervention_family": "type_symmetric",
            "intervention_family_verified": True,
            "proof_obligations_satisfied": [
                "within_type_exchangeability",
                "mean_closure",
                "admissible_omega_map",
                "controlled_mean_residual",
            ],
            "estimand_error_bounds": {
                "mean_potential_outcome:type_mean": 0.03,
                "ate:type_mean": 0.05,
                "policy_value:weighted_type_mean": 0.02,
            },
            "diagnostics": {
                "within_type_dispersion": {"max": 0.1},
                "partition_residual": None,
            },
            "non_preserved_queries": [
                "unit_level_potential_outcome",
                "within_type_quantile_effect",
                "tail_risk",
            ],
        },
    )

    assert certificate.preservation_type is AbstractionPreservationType.APPROXIMATE
    assert certificate.error_bound == 0.05


def test_abstraction_certificate_rejects_approximate_without_query_bounds(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "abstraction-approximate-invalid")
    map_ref = persist_finite_state_abstraction_map(
        store,
        FiniteStateAbstractionMap(
            variable_maps=(
                VariableStateAbstraction(
                    micro_variable="Y_m",
                    macro_variable="Y_bar",
                    state_map={"low": "low", "high": "high"},
                ),
            )
        ),
    )

    with pytest.raises(ValidationError, match="estimand_error_bounds"):
        AbstractionCertificate(
            micro_graph_ref=_artifact_ref("a", kind="ir.causal_graph_model"),
            macro_graph_ref=_artifact_ref("b", kind="ir.causal_graph_model"),
            abstraction_map_ref=map_ref,
            preservation_type=AbstractionPreservationType.APPROXIMATE,
            preserved_queries=(
                "mean_potential_outcome:type_mean",
                "ate:type_mean",
            ),
            error_bound=0.05,
            metadata={
                "abstraction_family": "type_mean_affine",
                "allowed_intervention_family": "type_symmetric",
                "intervention_family_verified": True,
                "proof_obligations_satisfied": ["mean_closure"],
                "estimand_error_bounds": {
                    "mean_potential_outcome:type_mean": 0.03,
                },
                "diagnostics": {"within_type_dispersion": {"max": 0.1}},
                "non_preserved_queries": ["unit_level_potential_outcome"],
            },
        )


def test_abstraction_certificate_policy_value_only_is_single_query_contract(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "abstraction-policy-value")
    map_ref = persist_finite_state_abstraction_map(
        store,
        FiniteStateAbstractionMap(
            variable_maps=(
                VariableStateAbstraction(
                    micro_variable="Y_m",
                    macro_variable="Y_bar",
                    state_map={"low": "low", "high": "high"},
                ),
            )
        ),
    )

    certificate = AbstractionCertificate(
        micro_graph_ref=_artifact_ref("a", kind="ir.causal_graph_model"),
        macro_graph_ref=_artifact_ref("b", kind="ir.causal_graph_model"),
        abstraction_map_ref=map_ref,
        preservation_type=AbstractionPreservationType.POLICY_VALUE_ONLY,
        preserved_queries=("policy_value:weighted_type_mean",),
        error_bound=0.02,
    )

    assert certificate.preserved_queries == ("policy_value:weighted_type_mean",)

    with pytest.raises(ValidationError, match="exactly one preserved policy-value query"):
        AbstractionCertificate(
            micro_graph_ref=_artifact_ref("c", kind="ir.causal_graph_model"),
            macro_graph_ref=_artifact_ref("d", kind="ir.causal_graph_model"),
            abstraction_map_ref=map_ref,
            preservation_type=AbstractionPreservationType.POLICY_VALUE_ONLY,
            preserved_queries=("policy_value:weighted_type_mean", "ate:type_mean"),
            error_bound=0.02,
        )


def test_abstraction_certificate_rejects_unverified_intervention_family(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "abstraction-intervention-family")
    map_ref = persist_finite_state_abstraction_map(
        store,
        FiniteStateAbstractionMap(
            variable_maps=(
                VariableStateAbstraction(
                    micro_variable="Y_m",
                    macro_variable="Y_bar",
                    state_map={"low": "low", "high": "high"},
                ),
            )
        ),
    )

    with pytest.raises(ValidationError, match="intervention_family_verified"):
        AbstractionCertificate(
            micro_graph_ref=_artifact_ref("a", kind="ir.causal_graph_model"),
            macro_graph_ref=_artifact_ref("b", kind="ir.causal_graph_model"),
            abstraction_map_ref=map_ref,
            preservation_type=AbstractionPreservationType.APPROXIMATE,
            preserved_queries=(
                "mean_potential_outcome:type_mean",
                "ate:type_mean",
            ),
            error_bound=0.05,
            metadata={
                "abstraction_family": "type_mean_affine",
                "allowed_intervention_family": "type_symmetric",
                "proof_obligations_satisfied": ["mean_closure"],
                "estimand_error_bounds": {
                    "mean_potential_outcome:type_mean": 0.03,
                    "ate:type_mean": 0.05,
                },
                "diagnostics": {"within_type_dispersion": {"max": 0.1}},
                "non_preserved_queries": ["unit_level_potential_outcome"],
            },
        )


def test_abstraction_certificate_accepts_continuous_linear_gaussian_error_bound_spec(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "abstraction-continuous-linear-gaussian")
    map_ref = persist_finite_state_abstraction_map(
        store,
        FiniteStateAbstractionMap(
            variable_maps=(
                VariableStateAbstraction(
                    micro_variable="X_m",
                    macro_variable="Z",
                    state_map={"low": "low", "high": "high"},
                ),
            )
        ),
    )

    certificate = AbstractionCertificate(
        micro_graph_ref=_artifact_ref("a", kind="ir.causal_graph_model"),
        macro_graph_ref=_artifact_ref("b", kind="ir.causal_graph_model"),
        abstraction_map_ref=map_ref,
        preservation_type=AbstractionPreservationType.APPROXIMATE,
        preserved_queries=("policy_value:planner_welfare", "policy_rank:top2"),
        error_bound=0.12,
        metadata={
            "abstraction_family": "continuous_linear_gaussian",
            "allowed_intervention_family": "hard_or_soft_declared_scope",
            "intervention_family_verified": True,
            "proof_obligations_satisfied": [
                "local_defect_certified",
                "gain_matrix_contracting",
                "value_lipschitz_bound",
            ],
            "estimand_error_bounds": {
                "policy_value:planner_welfare": 0.12,
                "policy_rank:top2": 0.12,
            },
            "diagnostics": {
                "global_state_bound": 0.08,
                "wasserstein_bound": 0.06,
            },
            "non_preserved_queries": ["unit_level_counterfactual"],
            "error_bound_spec": {
                "scope": {
                    "query_family": "policy_value",
                    "interventions": "hard_or_soft_declared_scope",
                    "action_domain": "compact_box",
                },
                "state_metric": "weighted_l1",
                "distribution_metric": "wasserstein_1",
                "value_lipschitz_constant": 1.5,
                "global_state_bound": 0.08,
                "recommendation_margin_required": 0.24,
                "gain_matrix_spectral_radius": 0.35,
                "tightness_status": "exact_on_linear_gaussian",
                "computation_artifact_ref": "sha256:continuous-proof",
                "local_defect_artifact_ref": "sha256:defect-proof",
            },
        },
    )

    assert abstraction_error_bound_spec(certificate) == {
        "scope": {
            "query_family": "policy_value",
            "interventions": "hard_or_soft_declared_scope",
            "action_domain": "compact_box",
        },
        "state_metric": "weighted_l1",
        "distribution_metric": "wasserstein_1",
        "value_lipschitz_constant": 1.5,
        "global_state_bound": 0.08,
        "recommendation_margin_required": 0.24,
        "gain_matrix_spectral_radius": 0.35,
        "tightness_status": "exact_on_linear_gaussian",
        "computation_artifact_ref": "sha256:continuous-proof",
        "local_defect_artifact_ref": "sha256:defect-proof",
    }
    assert abstraction_recommendation_margin_required(certificate) == 0.24


def test_abstraction_certificate_rejects_continuous_error_bound_spec_below_margin(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "abstraction-continuous-invalid")
    map_ref = persist_finite_state_abstraction_map(
        store,
        FiniteStateAbstractionMap(
            variable_maps=(
                VariableStateAbstraction(
                    micro_variable="X_m",
                    macro_variable="Z",
                    state_map={"low": "low", "high": "high"},
                ),
            )
        ),
    )

    with pytest.raises(ValidationError, match="recommendation_margin_required"):
        AbstractionCertificate(
            micro_graph_ref=_artifact_ref("c", kind="ir.causal_graph_model"),
            macro_graph_ref=_artifact_ref("d", kind="ir.causal_graph_model"),
            abstraction_map_ref=map_ref,
            preservation_type=AbstractionPreservationType.APPROXIMATE,
            preserved_queries=("policy_value:planner_welfare", "policy_rank:top2"),
            error_bound=0.12,
            metadata={
                "abstraction_family": "continuous_lipschitz_dag",
                "allowed_intervention_family": "hard_or_soft_declared_scope",
                "intervention_family_verified": True,
                "proof_obligations_satisfied": [
                    "local_defect_certified",
                    "gain_matrix_contracting",
                    "value_lipschitz_bound",
                ],
                "estimand_error_bounds": {
                    "policy_value:planner_welfare": 0.12,
                    "policy_rank:top2": 0.12,
                },
                "diagnostics": {"global_state_bound": 0.08},
                "non_preserved_queries": ["unit_level_counterfactual"],
                "error_bound_spec": {
                    "scope": {
                        "query_family": "policy_value",
                        "interventions": "hard_or_soft_declared_scope",
                        "action_domain": "compact_box",
                    },
                    "state_metric": "weighted_l1",
                    "distribution_metric": "wasserstein_1",
                    "value_lipschitz_constant": 1.5,
                    "global_state_bound": 0.08,
                    "recommendation_margin_required": 0.20,
                    "gain_matrix_spectral_radius": 0.35,
                    "tightness_status": "upper_bound_only",
                },
            },
        )


def test_abstraction_certificate_rejects_continuous_policy_value_only_without_spec(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "abstraction-continuous-policy-only-invalid")
    map_ref = persist_finite_state_abstraction_map(
        store,
        FiniteStateAbstractionMap(
            variable_maps=(
                VariableStateAbstraction(
                    micro_variable="X_m",
                    macro_variable="Z",
                    state_map={"low": "low", "high": "high"},
                ),
            )
        ),
    )

    with pytest.raises(ValidationError, match="continuous policy_value_only"):
        AbstractionCertificate(
            micro_graph_ref=_artifact_ref("e", kind="ir.causal_graph_model"),
            macro_graph_ref=_artifact_ref("f", kind="ir.causal_graph_model"),
            abstraction_map_ref=map_ref,
            preservation_type=AbstractionPreservationType.POLICY_VALUE_ONLY,
            preserved_queries=("policy_value:planner_welfare",),
            error_bound=0.08,
            metadata={"abstraction_family": "continuous_linear_gaussian"},
        )
