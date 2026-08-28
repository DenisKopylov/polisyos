from __future__ import annotations

import importlib.util
import json
from datetime import date, timedelta

import numpy as np
import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.foundry.data_plane import materialize_method_contract
from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod
from polisyos.foundry.methods.catalog.causal.did import StandardDifferenceInDifferences
from polisyos.foundry.methods.catalog.causal.g_computation import ParametricGFormula
from polisyos.foundry.methods.catalog.causal.interference import NetworkAIPWEstimator
from polisyos.foundry.methods.catalog.causal.measurement_error import (
    MeasurementErrorEstimator,
    identify_with_proxy,
)
from polisyos.foundry.methods.catalog.econometrics.panel import PanelDataEstimator
from polisyos.foundry.methods.catalog.microsim.static import StaticMicrosimEstimator
from polisyos.foundry.methods.catalog.ml.survival import SurvivalAnalysisEstimator
from polisyos.foundry.methods.catalog.network.analysis import (
    MultiplexNetworkEstimator,
    NetworkDiffusionEstimator,
)
from polisyos.foundry.methods.catalog.optimization.io_model import LeontiefInputOutput
from polisyos.foundry.methods.catalog.sensitivity.specification import (
    SpecificationCurveEstimator,
)
from polisyos.ir.analytics.backtest import load_backtest_report
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.model_layer.types import TimeFrequency
from polisyos.ir.observation.bundles import (
    DYNAMIC_TREATMENT_TARGET,
    MULTIPLEX_NETWORK_TARGET,
    NETWORK_ANALYSIS_TARGET,
    NETWORK_DATA_TARGET,
    PANEL_ECONOMETRIC_TARGET,
    PANEL_OBSERVATIONAL_TARGET,
    PROXY_MEASUREMENT_TARGET,
    SURVEY_MICRODATA_TARGET,
    SURVIVAL_DATA_TARGET,
    CausalPanelBundleManifest,
    ContractCompatibilityTarget,
    DTRTreatmentSequenceBundleManifest,
    MicrosimSurveyContractBundle,
)
from polisyos.ir.observation.contract_compilers import (
    BoundsEstimationCompileSpec,
    DynamicTreatmentCompileSpec,
    FirmEventRecord,
    FirmEvents,
    FirmPanelRow,
    FirmPanels,
    GraphArtifacts,
    GraphBipartiteEdge,
    GraphEdge,
    HistoricalValidationCompileSpec,
    HistoricalValidationPlanCompiler,
    LeontiefIOCompileSpec,
    NetworkCausalCompileSpec,
    NetworkContractCompileSpec,
    ObservationContractCompilerSuite,
    ObservationContractLoadError,
    PanelEconometricCompileSpec,
    PanelObservationalCompileSpec,
    ProxyMap,
    ProxyMeasurementCompileSpec,
    RegionSectorFlowRow,
    RegionSectorPanels,
    SparseDenseBridge,
    SpecificationCurveCompileSpec,
    SpecificationCurveSourceSpec,
    SurveyMicroDataCompileSpec,
    SurvivalCompileSpec,
    load_json_bundle,
    load_npz_payload,
    load_parquet_rows,
    write_json_bundle,
    write_npz_payload,
    write_parquet_rows,
)
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    MultiplexGraphLayerId,
    ObservationFamily,
    ObservationPanel,
    ObservationRecord,
    SourceConfidenceTier,
)
from polisyos.scientist.governance.backtest_matrix import BacktestKind, BacktestMatrixRunner

_FOUNDRY_METHOD_TARGETS: dict[str, ContractCompatibilityTarget] = {
    "dynamic_treatment_data": DYNAMIC_TREATMENT_TARGET,
    "multiplex_network_data": MULTIPLEX_NETWORK_TARGET,
    "network_causal_data": NETWORK_DATA_TARGET,
    "network_data": NETWORK_ANALYSIS_TARGET,
    "panel_econometric_data": PANEL_ECONOMETRIC_TARGET,
    "panel_observational_data": PANEL_OBSERVATIONAL_TARGET,
    "proxy_measurement_data": PROXY_MEASUREMENT_TARGET,
    "survey_micro_data": SURVEY_MICRODATA_TARGET,
    "survival_data": SURVIVAL_DATA_TARGET,
}


def _materialize_artifact(artifact):
    return materialize_method_contract(
        contract_target=_FOUNDRY_METHOD_TARGETS[artifact.artifact_key],
        contract_payload=artifact.contract,
    )


def _period(month: int) -> tuple[date, date]:
    start = date(2024, month, 1)
    end = date(2024, month, 28)
    return start, end


def _observation_panel(n_units: int = 20, n_periods: int = 4) -> ObservationPanel:
    records: list[ObservationRecord] = []
    for unit_idx in range(n_units):
        unit_id = f"hh_{unit_idx:02d}"
        base_cov = 20.0 + unit_idx
        for period_idx in range(n_periods):
            period_start, period_end = _period(period_idx + 1)
            treated = 1.0 if unit_idx % 2 == 0 and period_idx >= 1 else 0.0
            income = 1000.0 + 25.0 * unit_idx + 15.0 * period_idx
            outcome = 5.0 + 0.4 * unit_idx + 0.7 * period_idx + 1.5 * treated
            weight = 1.0 + unit_idx / 100.0
            proxy = max(0.0, min(1.0, treated + (0.2 if unit_idx % 5 == 0 else 0.0)))
            metrics = {
                "income": income,
                "weight": weight,
                "outcome_score": outcome,
                "treatment": treated,
                "cov_a": base_cov,
                "cov_b": base_cov * 0.1 + period_idx,
                "instrument": float(unit_idx % 2),
                "selected": 0.0 if unit_idx == n_units - 1 else 1.0,
                "miv_proxy": float(unit_idx % 4),
                "treatment_proxy": proxy,
                "validation_true_treatment": treated,
                "validation_proxy": proxy,
            }
            for metric_id, value in metrics.items():
                records.append(
                    ObservationRecord(
                        observation_id=f"obs_{unit_id}_{metric_id}_{period_idx}",
                        family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
                        time_grain=TimeFrequency.MONTH,
                        period_start=period_start,
                        period_end=period_end,
                        entity_scope=EntityScope.HOUSEHOLD,
                        entity_id=unit_id,
                        metric_id=metric_id,
                        observed_value=value,
                        unit="value",
                        coverage_estimate=0.95,
                        measurement_bias_flag=False,
                        censoring_mask=False,
                        trust_weight=0.9,
                        lag_days_estimate=2,
                        source_id="synthetic_household_panel",
                        source_version="2024.1",
                        regime_id="wartime_2024",
                        shock_mask=False,
                        schema_regime_id="synthetic_schema_v1",
                        identification_mode=IdentificationMode.POINT_IDENTIFIED,
                        source_confidence_tier=SourceConfidenceTier.VALIDATED,
                    )
                )
    return ObservationPanel(
        panel_id="synthetic_household_panel",
        family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
        time_grain=TimeFrequency.MONTH,
        records=records,
    )


def _graph_artifacts(n_units: int = 20) -> GraphArtifacts:
    node_ids = [f"hh_{unit_idx:02d}" for unit_idx in range(n_units)]
    budget_edges = []
    procurement_edges = []
    for unit_idx, node_id in enumerate(node_ids):
        next_node = node_ids[(unit_idx + 1) % n_units]
        prev_node = node_ids[(unit_idx - 1) % n_units]
        budget_edges.append(GraphEdge(src_id=node_id, dst_id=next_node, weight=1.0))
        procurement_edges.append(GraphEdge(src_id=node_id, dst_id=prev_node, weight=0.5))
    return GraphArtifacts(
        artifact_id="synthetic_graph_artifact",
        node_ids=node_ids,
        layer_edges={
            MultiplexGraphLayerId.BUDGET: budget_edges,
            MultiplexGraphLayerId.PROCUREMENT: procurement_edges,
        },
        node_features={
            node_id: {
                "feature_a": float(idx),
                "feature_b": float(idx % 3),
            }
            for idx, node_id in enumerate(node_ids)
        },
        node_states={node_id: float(idx % 2) for idx, node_id in enumerate(node_ids)},
        cluster_ids={node_id: idx % 4 for idx, node_id in enumerate(node_ids)},
        coordinates={node_id: (float(idx), float(idx % 5)) for idx, node_id in enumerate(node_ids)},
        bipartite_edges=[
            GraphBipartiteEdge(
                treatment_node_id=node_ids[idx],
                outcome_node_id=node_ids[(idx + 2) % n_units],
            )
            for idx in range(n_units)
        ],
    )


def _firm_panels(n_firms: int = 20, n_periods: int = 4) -> FirmPanels:
    rows: list[FirmPanelRow] = []
    for firm_idx in range(n_firms):
        firm_id = f"firm_{firm_idx:02d}"
        for period_idx in range(n_periods):
            period_start, period_end = _period(period_idx + 1)
            rows.append(
                FirmPanelRow(
                    firm_id=firm_id,
                    period_start=period_start,
                    period_end=period_end,
                    metrics={
                        "sales": 100.0 + 4.0 * firm_idx + 3.0 * period_idx,
                        "capital": 50.0 + 2.0 * firm_idx,
                        "leverage": 0.2 + 0.01 * period_idx + 0.005 * firm_idx,
                        "instrument_z": float((firm_idx + period_idx) % 2),
                    },
                )
            )
    return FirmPanels(panel_id="synthetic_firm_panels", rows=rows)


def _firm_events(n_firms: int = 20) -> FirmEvents:
    records: list[FirmEventRecord] = []
    for firm_idx in range(n_firms):
        entry_date = date(2024, 1, 1)
        if firm_idx < n_firms // 2:
            records.append(
                FirmEventRecord(
                    firm_id=f"firm_{firm_idx:02d}",
                    entry_date=entry_date,
                    exit_date=entry_date + timedelta(days=120 + firm_idx),
                )
            )
        else:
            records.append(
                FirmEventRecord(
                    firm_id=f"firm_{firm_idx:02d}",
                    entry_date=entry_date,
                    censor_date=entry_date + timedelta(days=180 + firm_idx),
                )
            )
    return FirmEvents(event_set_id="synthetic_firm_events", records=records)


def _region_sector_panels() -> RegionSectorPanels:
    rows = [
        RegionSectorFlowRow(
            from_region_code="UA-30",
            from_sector_id="agro",
            to_region_code="UA-30",
            to_sector_id="agro",
            technical_coefficient=0.2,
            final_demand=50.0,
            value_added=30.0,
        ),
        RegionSectorFlowRow(
            from_region_code="UA-30",
            from_sector_id="agro",
            to_region_code="UA-46",
            to_sector_id="industry",
            technical_coefficient=0.1,
            final_demand=20.0,
            value_added=10.0,
        ),
        RegionSectorFlowRow(
            from_region_code="UA-46",
            from_sector_id="industry",
            to_region_code="UA-30",
            to_sector_id="agro",
            technical_coefficient=0.15,
            final_demand=25.0,
            value_added=15.0,
        ),
        RegionSectorFlowRow(
            from_region_code="UA-46",
            from_sector_id="industry",
            to_region_code="UA-46",
            to_sector_id="industry",
            technical_coefficient=0.25,
            final_demand=40.0,
            value_added=20.0,
        ),
    ]
    return RegionSectorPanels(panel_id="synthetic_region_sector_panels", rows=rows)


def _proxy_map() -> ProxyMap:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["c", "c_star", "x", "y"],
        edges=[
            CausalEdge(src="c", dst="x"),
            CausalEdge(src="c", dst="y"),
            CausalEdge(src="c", dst="c_star"),
            CausalEdge(src="x", dst="y"),
        ],
    )
    return ProxyMap(
        proxy_map_id="synthetic_proxy_map",
        mapping={"c": "c_star"},
        measurement_model="estimated",
        graph=graph,
    )


def _suite_specs() -> dict[str, object]:
    return {
        "survey_spec": SurveyMicroDataCompileSpec(
            spec_id="survey_spec",
            income_metric_id="income",
            weight_metric_id="weight",
            feature_metric_ids=["cov_a", "cov_b"],
        ),
        "network_spec": NetworkContractCompileSpec(
            spec_id="network_spec",
            primary_layer=MultiplexGraphLayerId.BUDGET,
            layer_order=[MultiplexGraphLayerId.BUDGET, MultiplexGraphLayerId.PROCUREMENT],
            node_feature_names=["feature_a", "feature_b"],
            low_rank_rank=2,
        ),
        "network_causal_spec": NetworkCausalCompileSpec(
            spec_id="network_causal_spec",
            outcome_metric_id="outcome_score",
            treatment_metric_id="treatment",
            covariate_metric_ids=["cov_a", "cov_b"],
            treatment_threshold=0.5,
            structure_layer=MultiplexGraphLayerId.PROCUREMENT,
        ),
        "panel_spec": PanelObservationalCompileSpec(
            spec_id="panel_spec",
            outcome_metric_id="outcome_score",
            treatment_metric_id="treatment",
            covariate_metric_ids=["cov_a", "cov_b"],
            explicit_time_treatment=1,
        ),
        "dynamic_treatment_spec": DynamicTreatmentCompileSpec(
            spec_id="dynamic_treatment_spec",
            outcome_metric_id="outcome_score",
            treatment_metric_id="treatment",
            covariate_metric_ids=["cov_a", "cov_b"],
        ),
        "survival_spec": SurvivalCompileSpec(
            spec_id="survival_spec",
            feature_metric_ids=["sales", "capital", "leverage"],
        ),
        "panel_econometric_spec": PanelEconometricCompileSpec(
            spec_id="panel_econometric_spec",
            dependent_metric_id="sales",
            exog_metric_ids=["capital", "leverage"],
            instrument_metric_ids=["instrument_z"],
        ),
        "bounds_spec": BoundsEstimationCompileSpec(
            spec_id="bounds_spec",
            outcome_metric_id="outcome_score",
            treatment_metric_id="treatment",
            instrument_metric_id="instrument",
            selected_metric_id="selected",
            miv_proxy_metric_id="miv_proxy",
        ),
        "proxy_spec": ProxyMeasurementCompileSpec(
            spec_id="proxy_spec",
            outcome_metric_id="outcome_score",
            treatment_proxy_metric_id="treatment_proxy",
            covariate_metric_ids=["cov_a"],
            validation_true_treatment_metric_id="validation_true_treatment",
            validation_proxy_metric_id="validation_proxy",
            error_rate_bound=0.1,
        ),
        "historical_validation_spec": HistoricalValidationCompileSpec(
            spec_id="historical_validation_spec",
            metric_ids=["outcome_score"],
            intervention_date="2024-02-01",
            pre_intervention_periods=1,
            post_intervention_periods=3,
        ),
        "specification_curve_spec": SpecificationCurveCompileSpec(
            spec_id="spec_curve_spec",
            source_specifications=[
                SpecificationCurveSourceSpec(
                    source_combination_id="spec_a",
                    included_metric_ids=["outcome_score"],
                    included_families=[ObservationFamily.HOUSEHOLD_DISTRIBUTION],
                    sensitivity_axes=["baseline"],
                ),
                SpecificationCurveSourceSpec(
                    source_combination_id="spec_b",
                    included_metric_ids=["outcome_score", "income"],
                    included_families=[ObservationFamily.HOUSEHOLD_DISTRIBUTION],
                    sensitivity_axes=["income_plus_outcome"],
                ),
            ],
        ),
        "leontief_spec": LeontiefIOCompileSpec(spec_id="leontief_spec"),
    }


def _assert_primary_payload(output: dict[str, object]) -> None:
    assert any(
        key in output for key in ("result", "report", "bounds_report", "status", "output_vector")
    )


def test_sparse_dense_bridge_materializes_small_subgraph_and_guards_large_dense() -> None:
    graph = _graph_artifacts()
    bridge = SparseDenseBridge()

    adjacency, node_order, _ = bridge.materialize_layer(
        graph,
        layer_id=MultiplexGraphLayerId.BUDGET,
        materialize_node_ids=["hh_00", "hh_01", "hh_02"],
        max_bytes=10_000,
    )

    assert adjacency.shape == (3, 3)
    assert node_order == ["hh_00", "hh_01", "hh_02"]
    assert float(adjacency[0, 1]) == 1.0

    with pytest.raises(MemoryError, match="dense materialization"):
        bridge.materialize_layer(
            graph,
            layer_id=MultiplexGraphLayerId.BUDGET,
            max_bytes=1,
        )


def test_survival_compiler_sets_right_censoring_flags() -> None:
    compiler_suite = ObservationContractCompilerSuite()
    artifact = compiler_suite.survival.compile(
        _firm_events(),
        _firm_panels(),
        _suite_specs()["survival_spec"],  # type: ignore[arg-type]
    )

    contract = _materialize_artifact(artifact)
    assert contract.events.shape[0] == 20
    assert int(np.sum(contract.events == 0)) == 10
    assert int(np.sum(contract.events == 1)) == 10


def test_compilers_round_trip_deterministic_bundles(tmp_path) -> None:
    suite = ObservationContractCompilerSuite()
    panel = _observation_panel()
    graph = _graph_artifacts()
    firm_panels = _firm_panels()
    firm_events = _firm_events()
    region_sector_panels = _region_sector_panels()
    proxy_map = _proxy_map()
    specs = _suite_specs()

    survey_artifact = suite.survey.compile(panel, specs["survey_spec"])  # type: ignore[arg-type]
    network_artifacts = suite.network.compile(graph, specs["network_spec"])  # type: ignore[arg-type]
    network_causal_artifact = suite.network_causal.compile(
        panel,
        graph,
        specs["network_causal_spec"],  # type: ignore[arg-type]
    )
    dynamic_artifact = suite.dynamic.compile(panel, specs["dynamic_treatment_spec"])  # type: ignore[arg-type]
    panel_artifact = suite.panel.compile(panel, specs["panel_spec"])  # type: ignore[arg-type]
    survival_artifact = suite.survival.compile(firm_events, firm_panels, specs["survival_spec"])  # type: ignore[arg-type]
    panel_econometric_artifact = suite.panel_econometric.compile(
        firm_panels,
        specs["panel_econometric_spec"],  # type: ignore[arg-type]
    )
    spec_artifact = suite.specification_curve.compile(panel, specs["specification_curve_spec"])  # type: ignore[arg-type]
    leontief_artifact = suite.leontief.compile(region_sector_panels, specs["leontief_spec"])  # type: ignore[arg-type]
    proxy_artifact = suite.proxy.compile(panel, proxy_map, specs["proxy_spec"])  # type: ignore[arg-type]

    survey_path = write_json_bundle(survey_artifact.bundle, tmp_path / "survey.json")
    loaded_survey = load_json_bundle(survey_path, MicrosimSurveyContractBundle)
    assert (
        loaded_survey.contract_payload["market_income"]
        == survey_artifact.bundle.contract_payload["market_income"]
    )

    spec_path = write_json_bundle(spec_artifact.bundle, tmp_path / "specification.json")
    loaded_spec = load_json_bundle(spec_path, type(spec_artifact.bundle))
    assert loaded_spec.specification_ids == spec_artifact.bundle.specification_ids

    npz_path = write_npz_payload(
        dynamic_artifact.bundle.contract_payload, tmp_path / "dynamic_treatment.npz"
    )
    loaded_npz = load_npz_payload(npz_path)
    assert loaded_npz["treatment_sequence"].shape == (20, 4)

    panel_path = write_parquet_rows(panel_artifact.bundle.table_rows, tmp_path / "panel.parquet")
    loaded_panel_rows = load_parquet_rows(panel_path)
    assert len(loaded_panel_rows) == 80

    survival_path = write_parquet_rows(
        survival_artifact.bundle.table_rows, tmp_path / "survival.parquet"
    )
    loaded_survival_rows = load_parquet_rows(survival_path)
    assert len(loaded_survival_rows) == 20

    assert isinstance(panel_artifact.bundle, CausalPanelBundleManifest)
    assert isinstance(dynamic_artifact.bundle, DTRTreatmentSequenceBundleManifest)
    assert proxy_artifact.bundle.proxy_map == {"c": "c_star"}
    assert leontief_artifact.bundle.contract_payload["sector_names"]

    for artifact in (
        survey_artifact,
        network_artifacts["network_data"],
        network_artifacts["multiplex_network_data"],
        network_causal_artifact,
        dynamic_artifact,
        panel_artifact,
        survival_artifact,
        panel_econometric_artifact,
        proxy_artifact,
    ):
        assert isinstance(artifact.contract, dict)
        materialized = _materialize_artifact(artifact)
        assert materialized.model_dump(mode="json") == artifact.contract
        rematerialized = materialize_method_contract(
            contract_target=_FOUNDRY_METHOD_TARGETS[artifact.artifact_key],
            contract_payload=materialized.model_dump(mode="json"),
        )
        assert rematerialized.model_dump(mode="json") == artifact.contract


def test_load_npz_payload_raises_on_malformed_json_scalar(tmp_path) -> None:
    npz_path = tmp_path / "broken_payload.npz"
    np.savez(npz_path, metadata=np.asarray('{"broken":', dtype="<U16"))

    with pytest.raises(
        ObservationContractLoadError, match="failed to parse JSON-encoded scalar payload"
    ):
        load_npz_payload(npz_path)


def test_proxy_map_rejects_duplicate_targets() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["latent_a", "latent_b", "proxy"],
        edges=[CausalEdge(src="latent_a", dst="proxy"), CausalEdge(src="latent_b", dst="proxy")],
    )

    with pytest.raises(ValidationError, match="duplicate proxy_map.mapping value"):
        ProxyMap(
            proxy_map_id="duplicate_proxy_targets",
            mapping={"latent_a": "proxy", "latent_b": "proxy"},
            measurement_model="estimated",
            graph=graph,
        )


def test_network_causal_compiler_shapes() -> None:
    suite = ObservationContractCompilerSuite()
    artifact = suite.network_causal.compile(
        _observation_panel(),
        _graph_artifacts(),
        _suite_specs()["network_causal_spec"],  # type: ignore[arg-type]
    )

    contract = _materialize_artifact(artifact)
    assert contract.adjacency_matrix.shape == (20, 20)
    assert contract.cluster_id.shape == (20,)
    assert contract.coordinates.shape == (20, 2)
    assert contract.bipartite_edges.shape[1] == 2


def test_historical_validation_bundle_runs_through_scientist_matrix(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    historical_ref = store.put_json(
        {"outcome_score": [5.2, 6.65, 7.35, 8.05]},
        PutOptions(kind="test.historical_data", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    compilation = HistoricalValidationPlanCompiler().compile(
        _observation_panel(n_units=2, n_periods=4),
        HistoricalValidationCompileSpec(
            spec_id="neutral_backtest_plan",
            metric_ids=["outcome_score"],
            intervention_date="2024-02-01",
            pre_intervention_periods=1,
            post_intervention_periods=3,
            historical_data_ref=str(historical_ref.artifact_id),
        ),
    )

    plan_payload = compilation.bundle.plans[0]
    assert isinstance(plan_payload, dict)
    assert "prediction_source" not in plan_payload

    result = BacktestMatrixRunner(store).run(
        {BacktestKind.HOUSEHOLD: compilation.bundle}
    )
    household = next(item for item in result.kind_results if item.kind is BacktestKind.HOUSEHOLD)
    assert household.status == "ok"
    assert household.n_plans == 1
    assert result.backtest_report_ref is not None

    report = load_backtest_report(store, result.backtest_report_ref)
    assert report.n_scenarios == 1
    assert report.scenarios[0].metadata["prediction_source_requested"] == "naive"
    assert report.scenarios[0].metadata["prediction_source_effective"] == "naive"


def test_compile_all_and_downstream_methods_accept_compiled_contracts(tmp_path) -> None:
    suite = ObservationContractCompilerSuite()
    panel = _observation_panel()
    graph = _graph_artifacts()
    firm_panels = _firm_panels()
    firm_events = _firm_events()
    region_sector_panels = _region_sector_panels()
    proxy_map = _proxy_map()
    specs = _suite_specs()

    result = suite.compile_all(
        observation_panel=panel,
        graph_artifacts=graph,
        firm_events=firm_events,
        firm_panels=firm_panels,
        region_sector_panels=region_sector_panels,
        proxy_map=proxy_map,
        survey_spec=specs["survey_spec"],  # type: ignore[arg-type]
        network_spec=specs["network_spec"],  # type: ignore[arg-type]
        network_causal_spec=specs["network_causal_spec"],  # type: ignore[arg-type]
        panel_spec=specs["panel_spec"],  # type: ignore[arg-type]
        dynamic_treatment_spec=specs["dynamic_treatment_spec"],  # type: ignore[arg-type]
        survival_spec=specs["survival_spec"],  # type: ignore[arg-type]
        panel_econometric_spec=specs["panel_econometric_spec"],  # type: ignore[arg-type]
        bounds_spec=specs["bounds_spec"],  # type: ignore[arg-type]
        proxy_spec=specs["proxy_spec"],  # type: ignore[arg-type]
        historical_validation_spec=specs["historical_validation_spec"],  # type: ignore[arg-type]
        specification_curve_spec=specs["specification_curve_spec"],  # type: ignore[arg-type]
        leontief_spec=specs["leontief_spec"],  # type: ignore[arg-type]
    )

    assert {
        "survey_micro_data",
        "network_data",
        "multiplex_network_data",
        "network_causal_data",
        "panel_observational_data",
        "dynamic_treatment_data",
        "survival_data",
        "panel_econometric_data",
        "bounds_estimation_input",
        "proxy_measurement_data",
        "specification_curve_input",
        "leontief_io_input",
    } <= set(result.artifacts)
    assert result.backtest is not None
    assert any(
        item.artifact_name == "backtest_plan_bundle.json" for item in result.manifest.artifacts
    )

    survey_contract = _materialize_artifact(result.artifacts["survey_micro_data"])
    network_contract = _materialize_artifact(result.artifacts["network_data"])
    multiplex_contract = _materialize_artifact(result.artifacts["multiplex_network_data"])
    network_causal_contract = _materialize_artifact(result.artifacts["network_causal_data"])
    panel_contract = _materialize_artifact(result.artifacts["panel_observational_data"])
    dynamic_contract = _materialize_artifact(result.artifacts["dynamic_treatment_data"])
    survival_contract = _materialize_artifact(result.artifacts["survival_data"])
    panel_econometric_contract = _materialize_artifact(
        result.artifacts["panel_econometric_data"]
    )
    proxy_contract = _materialize_artifact(result.artifacts["proxy_measurement_data"])

    microsim_out = StaticMicrosimEstimator.pure_step(survey_contract, {})
    network_out = NetworkDiffusionEstimator.pure_step(network_contract, {})
    multiplex_out = MultiplexNetworkEstimator.pure_step(
        multiplex_contract, {}
    )
    network_causal_out = NetworkAIPWEstimator.pure_step(
        network_causal_contract,
        {"n_bootstrap": 10, "confidence_level": 0.9},
    )
    panel_out = StandardDifferenceInDifferences.pure_step(
        panel_contract,
        {},
    )
    dynamic_out = ParametricGFormula.pure_step(
        dynamic_contract,
        {"n_monte_carlo": 100, "n_bootstrap": 20},
    )
    survival_out = None
    if importlib.util.find_spec("lifelines") is not None:
        survival_out = SurvivalAnalysisEstimator.pure_step(
            survival_contract, {}
        )
    econometric_out = None
    if importlib.util.find_spec("linearmodels") is not None:
        econometric_out = PanelDataEstimator.pure_step(
            panel_econometric_contract,
            {"model": "fixed_effects"},
        )
    bounds_out = BoundsEngineMethod.pure_step(
        result.artifacts["bounds_estimation_input"].contract,
        {"has_iv": True, "has_selection": True, "use_auto_bounds": False},
    )
    proxy_payload = proxy_contract.model_dump(mode="python")
    proxy_out = MeasurementErrorEstimator.pure_step(
        proxy_payload,
        {"method": "bounds", "error_rate_bound": 0.1},
    )
    id_result = identify_with_proxy(
        proxy_map.graph,
        treatment="x",
        outcome="y",
        proxy_map=dict(proxy_map.mapping),
        measurement_model=proxy_map.measurement_model,
    )
    spec_out = SpecificationCurveEstimator.pure_step(
        result.artifacts["specification_curve_input"].contract,
        {},
    )
    leontief_out = LeontiefInputOutput.pure_step(result.artifacts["leontief_io_input"].contract, {})

    historical_path = tmp_path / "historical_data.json"
    backtest_series = result.backtest.historical_payloads["historical_validation_spec"]["series"]
    historical_path.write_text(json.dumps(backtest_series), encoding="utf-8")
    backtest_plan_payload = {
        **result.backtest.plans[0],
        "historical_data_path": str(historical_path),
        "historical_data_ref": None,
    }
    backtest_bundle = result.backtest.bundle.model_copy(
        update={"plans": [backtest_plan_payload]}
    )
    backtest_store = FileSystemCAS(tmp_path / ".cas")
    backtest_matrix = BacktestMatrixRunner(backtest_store).run(
        {BacktestKind.HOUSEHOLD: backtest_bundle}
    )
    assert backtest_matrix.backtest_report_ref is not None
    backtest_report = load_backtest_report(
        backtest_store,
        backtest_matrix.backtest_report_ref,
    )

    _assert_primary_payload(microsim_out)
    _assert_primary_payload(network_out)
    _assert_primary_payload(multiplex_out)
    _assert_primary_payload(network_causal_out)
    _assert_primary_payload(panel_out)
    _assert_primary_payload(dynamic_out)
    if survival_out is not None:
        _assert_primary_payload(survival_out)
    else:
        assert survival_contract.events.shape[0] == 20
    if econometric_out is not None:
        _assert_primary_payload(econometric_out)
    else:
        assert panel_econometric_contract.n_obs == 80
    _assert_primary_payload(bounds_out)
    _assert_primary_payload(proxy_out)
    assert getattr(id_result, "status", None) is not None
    _assert_primary_payload(spec_out)
    _assert_primary_payload(leontief_out)
    assert backtest_report.n_scenarios == 1
