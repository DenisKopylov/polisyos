from __future__ import annotations

import importlib

import pytest

from polisyos.ir.observation.bundles import (
    AgentFactorEmbeddingsBundleManifest,
    BACKTEST_PLAN_TARGET,
    BilevelProblemBundle,
    DYNAMIC_TREATMENT_TARGET,
    LESSON_CARD_TARGET,
    MULTIPLEX_NETWORK_TARGET,
    NETWORK_ANALYSIS_TARGET,
    PANEL_ECONOMETRIC_TARGET,
    PANEL_OBSERVATIONAL_TARGET,
    PROXY_MEASUREMENT_TARGET,
    SURVEY_MICRODATA_TARGET,
    SURVIVAL_DATA_TARGET,
    BacktestPlanBundle,
    BoundsEstimationBundle,
    BundleAxisSemantic,
    BundleLineageRef,
    CalibrationTargetBundleManifest,
    CausalPanelBundleManifest,
    CellPrototypeEmbeddingsBundleManifest,
    CounterfactualCheckBundle,
    ContractCompatibilityTarget,
    DTRTreatmentSequenceBundleManifest,
    GovernancePassMappingBundle,
    HeckmanCorrectionBundle,
    InterferenceLossSpecBundle,
    LeontiefIOBundle,
    LessonRegistrySeedBundle,
    MicrosimSurveyContractBundle,
    NetworkCausalContractBundle,
    NetworkContractBundle,
    ObservationToContractManifest,
    PanelEconometricBundleManifest,
    ProxyIdentificationBundle,
    RequiredArraySpec,
    RequiredColumnSpec,
    SECTION_15_7_BUNDLE_MODELS,
    SobolDiagnosticsBundle,
    SpecificationCurveBundle,
    SpecificationCurveDiagnosticsBundle,
    TransportabilityCheckBundle,
    StrategicResponseSpecsBundle,
    SurvivalDataBundleManifest,
    SurvivalHazardBundle,
)
from polisyos.ir.observation.contracts import (
    IdentificationMode,
    MultiplexGraphLayerId,
    ObservationFamily,
    StrategicResponseChannel,
)
from polisyos.ir.observation.governance import DEFAULT_GOVERNANCE_PASS_ALIAS_REGISTRY


EXPECTED_ARTIFACTS = {
    "calibration_target_bundle_v1.npz",
    "microsim_survey_contract_v1.json",
    "network_contract_bundle_v1.json",
    "network_causal_contract_bundle_v1.json",
    "causal_panel_bundle_monthly.parquet",
    "backtest_plan_bundle.json",
    "observation_to_contract_manifest.json",
    "bounds_estimation_bundle_v1.json",
    "proxy_identification_bundle_v1.json",
    "dtr_treatment_sequence_bundle_v1.npz",
    "panel_econometric_bundle_v1.parquet",
    "survival_data_bundle_v1.parquet",
    "agent_factor_embeddings_v1.npz",
    "cell_prototype_embeddings_v1.npz",
    "bilevel_problem_bundle_v1.json",
    "heckman_correction_bundle_v1.parquet",
    "survival_hazard_bundle_v1.parquet",
    "sobol_diagnostics_bundle_v1.json",
    "specification_curve_diagnostics_v1.json",
    "specification_curve_input_v1.json",
    "leontief_io_bundle_v1.json",
    "strategic_response_specs_v1.json",
    "transportability_check_bundle_v1.json",
    "counterfactual_check_bundle_v1.json",
    "interference_loss_spec_bundle_v1.json",
    "governance_pass_mapping_v1.json",
    "lesson_registry_seed_v1.json",
}


def _measurement_target() -> ContractCompatibilityTarget:
    return ContractCompatibilityTarget(
        contract_id="foundry.calibration.measurement_aware_target.v1",
        contract_fqn="polisyos.foundry.calibration.measurement.MeasurementAwareTarget",
    )


def _sample_payloads() -> list[object]:
    lineage = [
        BundleLineageRef(
            source_artifact="observation_panel_monthly.parquet",
            source_family=ObservationFamily.BUDGET_FLOWS,
        )
    ]
    return [
        CalibrationTargetBundleManifest(
            contract_target=_measurement_target(),
            required_arrays=[
                RequiredArraySpec(name="targets", axes=["observation"], dtype="float32"),
                RequiredArraySpec(name="trust_weight", axes=["observation"], dtype="float32"),
            ],
            axis_semantics=[
                BundleAxisSemantic(axis="observation", description="Aligned observation axis")
            ],
            observation_families=[ObservationFamily.BUDGET_FLOWS],
            lineage=lineage,
        ),
        MicrosimSurveyContractBundle(
            contract_target=SURVEY_MICRODATA_TARGET,
            required_fields=["market_income", "weights", "household_ids"],
            observation_families=[
                ObservationFamily.HOUSEHOLD_DISTRIBUTION,
                ObservationFamily.LABOR_MARKET,
            ],
        ),
        NetworkContractBundle(
            contract_targets=[NETWORK_ANALYSIS_TARGET, MULTIPLEX_NETWORK_TARGET],
            graph_layers=[MultiplexGraphLayerId.BUDGET, MultiplexGraphLayerId.PROCUREMENT],
            source_artifacts=["budget_graph_sparse.npz", "procurement_graph_sparse.npz"],
        ),
        NetworkCausalContractBundle(
            contract_target=ContractCompatibilityTarget(
                contract_id="foundry.causal.network_causal_data.v1",
                contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.NetworkCausalData",
            ),
            supported_layers=[MultiplexGraphLayerId.PROCUREMENT],
        ),
        CausalPanelBundleManifest(
            contract_target=PANEL_OBSERVATIONAL_TARGET,
            required_columns=[
                RequiredColumnSpec(name="unit_id", dtype="string"),
                RequiredColumnSpec(name="period_id", dtype="string"),
                RequiredColumnSpec(name="treatment", dtype="float"),
                RequiredColumnSpec(name="outcome", dtype="float"),
            ],
            lineage=lineage,
        ),
        BacktestPlanBundle(
            contract_target=BACKTEST_PLAN_TARGET,
            required_fields=["historical_data_ref", "ground_truth_outcomes", "target_metrics"],
            holdout_windows=["2023-01:2023-06"],
        ),
        ObservationToContractManifest(
            routes=[
                {
                    "family": ObservationFamily.BUDGET_FLOWS,
                    "identification_mode": IdentificationMode.POINT_IDENTIFIED,
                    "target_contract": PANEL_OBSERVATIONAL_TARGET,
                },
                {
                    "family": ObservationFamily.HOUSEHOLD_DISTRIBUTION,
                    "identification_mode": IdentificationMode.PROXY_IDENTIFIED,
                    "target_contract": SURVEY_MICRODATA_TARGET,
                },
            ]
        ),
        BoundsEstimationBundle(
            channels=[
                {
                    "family": ObservationFamily.DISTRESS_ENFORCEMENT,
                    "bound_strategy": "manski_bounds",
                    "fallback_reason": "coverage_gap",
                }
            ]
        ),
        ProxyIdentificationBundle(
            contract_target=PROXY_MEASUREMENT_TARGET,
            proxy_channels=[
                {
                    "family": ObservationFamily.LABOR_MARKET,
                    "proxy_variable": "administrative_employment",
                    "latent_variable": "true_employment",
                    "target_contract": PROXY_MEASUREMENT_TARGET,
                }
            ],
        ),
        DTRTreatmentSequenceBundleManifest(
            contract_target=DYNAMIC_TREATMENT_TARGET,
            required_arrays=[
                RequiredArraySpec(name="outcome", axes=["unit"], dtype="float32"),
                RequiredArraySpec(name="treatment_sequence", axes=["unit", "period"], dtype="int8"),
            ],
            axis_semantics=[
                BundleAxisSemantic(axis="unit", description="Treatment unit axis"),
                BundleAxisSemantic(axis="period", description="Temporal policy sequence axis"),
            ],
            lineage=lineage,
        ),
        PanelEconometricBundleManifest(
            contract_target=PANEL_ECONOMETRIC_TARGET,
            required_columns=[
                RequiredColumnSpec(name="dependent", dtype="float"),
                RequiredColumnSpec(name="entity_ids", dtype="string"),
                RequiredColumnSpec(name="time_ids", dtype="string"),
            ],
            lineage=lineage,
        ),
        SurvivalDataBundleManifest(
            contract_target=SURVIVAL_DATA_TARGET,
            required_columns=[
                RequiredColumnSpec(name="features", dtype="array"),
                RequiredColumnSpec(name="durations", dtype="float"),
                RequiredColumnSpec(name="events", dtype="int"),
            ],
            lineage=lineage,
        ),
        AgentFactorEmbeddingsBundleManifest(
            required_arrays=[
                RequiredArraySpec(name="agent_ids", axes=["agent"], dtype="string"),
                RequiredArraySpec(name="embeddings", axes=["agent", "factor"], dtype="float32"),
                RequiredArraySpec(name="factor_loadings", axes=["variable", "factor"], dtype="float32"),
                RequiredArraySpec(name="explained_variance_ratio", axes=["factor"], dtype="float32"),
            ],
            axis_semantics=[
                BundleAxisSemantic(axis="agent", description="Unique agent embedding axis"),
                BundleAxisSemantic(axis="factor", description="Latent factor axis"),
                BundleAxisSemantic(axis="variable", description="Observed feature axis"),
            ],
            lineage=lineage,
            embedding_method="econometrics.factor.principal_components@1.0.0",
        ),
        CellPrototypeEmbeddingsBundleManifest(
            required_arrays=[
                RequiredArraySpec(name="cell_ids", axes=["cell"], dtype="string"),
                RequiredArraySpec(name="labels", axes=["cell"], dtype="int64"),
                RequiredArraySpec(name="prototype_centers", axes=["prototype", "feature"], dtype="float32"),
            ],
            axis_semantics=[
                BundleAxisSemantic(axis="cell", description="Observed cell axis"),
                BundleAxisSemantic(axis="prototype", description="Cluster centroid axis"),
                BundleAxisSemantic(axis="feature", description="Cell feature axis"),
            ],
            lineage=lineage,
            clustering_method="ml.clustering.kmeans@1.0.0",
        ),
        BilevelProblemBundle(
            knob_names=["tax_rate", "credit_support"],
            c_upper=[1.1, 1.3],
            c_lower=[0.6, 0.8],
            A_upper=[[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]],
            b_upper=[1.0, 1.0, 1.2],
            A_lower=[[1.0, 0.0], [0.0, 1.0]],
            b_lower=[1.0, 1.0],
            result_summary={"upper_feasible": True, "lower_feasible": True, "n_vars": 2},
        ),
        HeckmanCorrectionBundle(
            contract_target=ContractCompatibilityTarget(
                contract_id="econometrics.selection.heckman@1.0.0",
                contract_fqn="polisyos.foundry.methods.catalog.econometrics.selection.HeckmanSelectionEstimator",
            ),
            required_columns=[
                RequiredColumnSpec(name="firm_id", dtype="string"),
                RequiredColumnSpec(name="period_id", dtype="string"),
                RequiredColumnSpec(name="selected", dtype="int"),
                RequiredColumnSpec(name="corrected_log_output", dtype="float"),
                RequiredColumnSpec(name="corrected_output", dtype="float"),
            ],
            lineage=lineage,
        ),
        SurvivalHazardBundle(
            contract_target=ContractCompatibilityTarget(
                contract_id="foundry.ml.survival_result.v1",
                contract_fqn="polisyos.foundry.methods.catalog.ml.protocols.SurvivalResult",
            ),
            required_columns=[
                RequiredColumnSpec(name="firm_id", dtype="string"),
                RequiredColumnSpec(name="period_id", dtype="string"),
                RequiredColumnSpec(name="risk_score", dtype="float"),
                RequiredColumnSpec(name="event", dtype="int"),
            ],
            lineage=lineage,
        ),
        SobolDiagnosticsBundle(
            target_names=["fit_rmse", "coverage_gap"],
            source_combination_ids=["survey_only", "survey_plus_network"],
            first_order_indices=[[0.3, 0.2], [0.4, 0.1]],
            variance=[1.2, 0.8],
        ),
        SpecificationCurveDiagnosticsBundle(
            specification_ids=["spec_a", "spec_b", "spec_c"],
            sorted_estimates=[0.1, 0.2, 0.25],
            share_significant=2.0 / 3.0,
            sign_consistency=1.0,
        ),
        SpecificationCurveBundle(
            source_specifications=[
                {
                    "source_combination_id": "spec_a",
                    "included_families": [ObservationFamily.BUDGET_FLOWS],
                    "sensitivity_axes": ["winsorization"],
                }
            ]
        ),
        LeontiefIOBundle(
            regions=["UA-30"],
            sectors=["agro", "industry"],
        ),
        StrategicResponseSpecsBundle(
            expectations=[
                {
                    "intervention_kind": "procurement_threshold_change",
                    "channels": [StrategicResponseChannel.PROCUREMENT_CHANNEL],
                }
            ]
        ),
        TransportabilityCheckBundle(
            checks=[
                {
                    "check_id": "transport_procurement",
                    "family": ObservationFamily.PROCUREMENT_FLOWS,
                    "treatment": "tender_threshold",
                    "outcome": "supplier_entry",
                    "source_regime_id": "peacetime",
                    "target_regime_id": "wartime",
                    "time_grain": "M",
                    "source_context": {"context_id": "PL"},
                    "target_context": {"context_id": "UA"},
                    "explicit_s_nodes": [
                        {
                            "target_variable": "supplier_entry",
                            "context_dimension": "procurement_regime",
                            "source_value": 0.0,
                            "target_value": 1.0,
                            "delta": 1.0,
                            "severity": "high",
                        }
                    ],
                }
            ]
        ),
        CounterfactualCheckBundle(
            queries=[
                {
                    "query_id": "cf_budget",
                    "family": ObservationFamily.BUDGET_FLOWS,
                    "query": {
                        "outcome": "welfare",
                        "intervention": {"tax_rate": 1.0},
                        "conditioning": ["employment"],
                    },
                }
            ]
        ),
        InterferenceLossSpecBundle(
            specs=[
                {
                    "spec_id": "spillover_procurement",
                    "family": ObservationFamily.PROCUREMENT_FLOWS,
                    "graph_layer": MultiplexGraphLayerId.PROCUREMENT,
                    "predicted_metric_path": "metrics.procurement_spillover",
                    "observed_spillover": [0.2, 0.4],
                    "adjacency": [[0.0, 1.0], [1.0, 0.0]],
                    "trust_weight": [1.0, 0.8],
                    "coverage_estimate": [1.0, 1.0],
                }
            ]
        ),
        GovernancePassMappingBundle(
            family_passes={
                ObservationFamily.BUDGET_FLOWS.value: ["sutva_check", "freshness", "equity"]
            },
            alias_registry=DEFAULT_GOVERNANCE_PASS_ALIAS_REGISTRY,
        ),
        LessonRegistrySeedBundle(
            contract_target=LESSON_CARD_TARGET,
            seed_entries=[
                {
                    "summary": "Bounds-first fallback for censored distress observations.",
                    "failure_type": "censoring",
                    "stage_name": "calibration",
                    "fidelity_level": 0,
                }
            ],
        ),
    ]


def test_every_section_15_7_artifact_has_a_schema_model() -> None:
    assert set(SECTION_15_7_BUNDLE_MODELS) == EXPECTED_ARTIFACTS


def test_bundle_models_validate_sample_payloads() -> None:
    for model in _sample_payloads():
        assert model.artifact_name in EXPECTED_ARTIFACTS


@pytest.mark.parametrize(
    ("target", "expected_contract_id"),
    [
        (SURVEY_MICRODATA_TARGET, "foundry.microsim.survey_micro_data.v1"),
        (PANEL_ECONOMETRIC_TARGET, "foundry.econometrics.panel_data.v1"),
        (SURVIVAL_DATA_TARGET, "foundry.ml.survival_data.v1"),
        (PANEL_OBSERVATIONAL_TARGET, "foundry.causal.panel_observational_data.v1"),
        (PROXY_MEASUREMENT_TARGET, "foundry.causal.proxy_measurement_data.v1"),
        (DYNAMIC_TREATMENT_TARGET, "foundry.causal.dynamic_treatment_data.v1"),
        (BACKTEST_PLAN_TARGET, "scientist.backtesting.historical_validation_plan.v1"),
        (LESSON_CARD_TARGET, "scientist.search.lesson_card.v1"),
    ],
)
def test_target_contract_fqns_resolve_where_applicable(
    target: ContractCompatibilityTarget,
    expected_contract_id: str,
) -> None:
    module_name, attr_name = target.contract_fqn.rsplit(".", 1)
    resolved = getattr(importlib.import_module(module_name), attr_name)

    assert target.contract_id == expected_contract_id
    if hasattr(resolved, "contract_id"):
        assert target.contract_id == getattr(resolved, "contract_id")
