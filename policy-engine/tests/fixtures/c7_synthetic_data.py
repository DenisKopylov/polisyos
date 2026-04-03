from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import DataSnapshot, EvidenceBundle, EvidenceBundleRef
from polisyos.foundry.methods.catalog.ml.protocols import SurvivalData
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
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
    LeontiefIOCompileSpec,
    NetworkCausalCompileSpec,
    NetworkContractCompileSpec,
    ObservationContractCompilerSuite,
    PanelEconometricCompileSpec,
    PanelObservationalCompileSpec,
    ProxyMap,
    ProxyMeasurementCompileSpec,
    RegionSectorFlowRow,
    RegionSectorPanels,
    SpecificationCurveCompileSpec,
    SpecificationCurveInput,
    SpecificationCurveSourceSpec,
    SurveyMicroDataCompileSpec,
    SurvivalCompileSpec,
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
from polisyos.ir.types import TimeFrequency
from polisyos.scientist.compute.advanced_methods import C7AdvancedInputs

SEED = 20260328
N_AGENTS = 1000
N_FIRMS = 150
N_CELLS = 50
N_HOUSEHOLD_CELLS = 250
N_PERIODS = 4


@dataclass(frozen=True)
class C7SyntheticFixture:
    parquet_paths: dict[str, Path]
    parquet_rows: dict[str, list[dict[str, Any]]]
    normalized_payload: dict[str, Any]
    observation_panel: ObservationPanel
    graph_artifacts: GraphArtifacts
    firm_panels: FirmPanels
    firm_events: FirmEvents
    region_sector_panels: RegionSectorPanels
    proxy_map: ProxyMap
    specs: dict[str, object]
    survival_contract: SurvivalData
    specification_curve_input: SpecificationCurveInput
    advanced_inputs: C7AdvancedInputs


def _period_bounds(index: int) -> tuple[date, date]:
    start = date(2024, index + 1, 1)
    if index + 1 == 2:
        end = date(2024, index + 1, 29)
    elif index + 1 in {1, 3}:
        end = date(2024, index + 1, 31)
    else:
        end = date(2024, index + 1, 30)
    return start, end


def _period_id(index: int) -> str:
    return f"2024-{index + 1:02d}"


def _suite_specs() -> dict[str, object]:
    return {
        "survey_spec": SurveyMicroDataCompileSpec(
            spec_id="c7_survey",
            income_metric_id="income",
            weight_metric_id="weight",
            feature_metric_ids=["cov_a", "cov_b"],
            entity_scope=EntityScope.AGENT,
        ),
        "network_spec": NetworkContractCompileSpec(
            spec_id="c7_network",
            primary_layer=MultiplexGraphLayerId.BUDGET,
            layer_order=[MultiplexGraphLayerId.BUDGET, MultiplexGraphLayerId.PROCUREMENT],
            node_feature_names=["feature_a", "feature_b"],
            low_rank_rank=3,
        ),
        "network_causal_spec": NetworkCausalCompileSpec(
            spec_id="c7_network_causal",
            outcome_metric_id="outcome_score",
            treatment_metric_id="treatment",
            covariate_metric_ids=["cov_a", "cov_b"],
            treatment_threshold=0.5,
            structure_layer=MultiplexGraphLayerId.PROCUREMENT,
        ),
        "panel_spec": PanelObservationalCompileSpec(
            spec_id="c7_panel",
            outcome_metric_id="outcome_score",
            treatment_metric_id="treatment",
            covariate_metric_ids=["cov_a", "cov_b"],
            explicit_time_treatment=1,
        ),
        "dynamic_treatment_spec": DynamicTreatmentCompileSpec(
            spec_id="c7_dynamic_treatment",
            outcome_metric_id="outcome_score",
            treatment_metric_id="treatment",
            covariate_metric_ids=["cov_a", "cov_b"],
        ),
        "survival_spec": SurvivalCompileSpec(
            spec_id="c7_survival",
            feature_metric_ids=["sales", "capital", "leverage"],
        ),
        "panel_econometric_spec": PanelEconometricCompileSpec(
            spec_id="c7_panel_econ",
            dependent_metric_id="sales",
            exog_metric_ids=["capital", "leverage"],
            instrument_metric_ids=["instrument_z"],
        ),
        "bounds_spec": BoundsEstimationCompileSpec(
            spec_id="c7_bounds",
            outcome_metric_id="outcome_score",
            treatment_metric_id="treatment",
            instrument_metric_id="instrument",
            selected_metric_id="selected",
            miv_proxy_metric_id="miv_proxy",
        ),
        "proxy_spec": ProxyMeasurementCompileSpec(
            spec_id="c7_proxy",
            outcome_metric_id="outcome_score",
            treatment_proxy_metric_id="treatment_proxy",
            covariate_metric_ids=["cov_a"],
            validation_true_treatment_metric_id="validation_true_treatment",
            validation_proxy_metric_id="validation_proxy",
            error_rate_bound=0.1,
        ),
        "historical_validation_spec": HistoricalValidationCompileSpec(
            spec_id="c7_backtest",
            metric_ids=["outcome_score"],
            intervention_date="2024-02-01",
            pre_intervention_periods=1,
            post_intervention_periods=3,
        ),
        "specification_curve_spec": SpecificationCurveCompileSpec(
            spec_id="c7_spec_curve",
            source_specifications=[
                SpecificationCurveSourceSpec(
                    source_combination_id="survey_only",
                    included_metric_ids=["outcome_score"],
                    included_families=[ObservationFamily.HOUSEHOLD_DISTRIBUTION],
                    sensitivity_axes=["baseline"],
                ),
                SpecificationCurveSourceSpec(
                    source_combination_id="survey_plus_income",
                    included_metric_ids=["outcome_score", "income"],
                    included_families=[ObservationFamily.HOUSEHOLD_DISTRIBUTION],
                    sensitivity_axes=["income_plus_outcome"],
                ),
                SpecificationCurveSourceSpec(
                    source_combination_id="survey_plus_network",
                    included_metric_ids=["outcome_score", "cov_a", "cov_b"],
                    included_families=[ObservationFamily.HOUSEHOLD_DISTRIBUTION],
                    sensitivity_axes=["network_covariates"],
                ),
            ],
        ),
        "leontief_spec": LeontiefIOCompileSpec(spec_id="c7_leontief"),
    }


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
        proxy_map_id="c7_proxy_map",
        mapping={"c": "c_star"},
        measurement_model="estimated",
        graph=graph,
    )


def build_c7_synthetic_fixture(tmp_path: Path) -> C7SyntheticFixture:
    rng = np.random.default_rng(SEED)
    period_ids = [_period_id(index) for index in range(N_PERIODS)]
    cell_indices = np.arange(N_CELLS, dtype=int)
    household_cell_indices = np.arange(N_HOUSEHOLD_CELLS, dtype=int)
    firm_indices = np.arange(N_FIRMS, dtype=int)
    agent_indices = np.arange(N_AGENTS, dtype=int)

    household_cell_to_cell = household_cell_indices % N_CELLS
    firm_to_cell = firm_indices % N_CELLS
    agent_household_cell = agent_indices % N_HOUSEHOLD_CELLS
    agent_cell = household_cell_to_cell[agent_household_cell]
    agent_employer = np.where(agent_indices % 11 == 0, -1, agent_indices % N_FIRMS)
    base_income = 900.0 + 15.0 * (agent_indices % 37)
    base_risk = 0.2 + 0.6 * ((agent_indices % 19) / 18.0)
    base_skill = 0.8 + 0.5 * ((agent_indices % 23) / 22.0)

    agent_panel_rows: list[dict[str, Any]] = []
    observation_records: list[ObservationRecord] = []
    for period_index, period_id in enumerate(period_ids):
        period_start, period_end = _period_bounds(period_index)
        treated_mask = ((agent_indices + period_index) % 4 == 0).astype(float)
        seasonal = 1.0 + 0.03 * period_index
        incomes = base_income * seasonal + 25.0 * treated_mask + rng.normal(0.0, 8.0, size=N_AGENTS)
        employment_score = np.where(agent_employer >= 0, 0.75, 0.2) + 0.05 * period_index
        consumption = incomes * (0.72 + 0.05 * base_risk)
        distress_signal = 0.15 + 0.01 * agent_cell + 0.03 * period_index + 0.2 * (agent_employer < 0)
        network_exposure = 0.1 + 0.005 * (agent_indices % 31) + 0.02 * treated_mask
        outcome_score = (
            4.0
            + 0.015 * incomes
            + 0.8 * treated_mask
            - 0.5 * distress_signal
            + rng.normal(0.0, 0.05, size=N_AGENTS)
        )
        cov_a = 10.0 + 0.02 * incomes
        cov_b = 2.0 + 0.03 * (agent_indices % 17) + 0.2 * period_index
        instrument = (agent_indices % 2).astype(float)
        selected = np.where((agent_indices + period_index) % 29 == 0, 0.0, 1.0)
        miv_proxy = (agent_indices % 5).astype(float)
        treatment_proxy = np.clip(treated_mask + 0.1 * ((agent_indices % 7) == 0), 0.0, 1.0)
        weights = 1.0 + (agent_indices % 13) / 100.0
        for idx in range(N_AGENTS):
            row = {
                "agent_id": f"agent_{idx:04d}",
                "period_id": period_id,
                "household_cell_id": int(agent_household_cell[idx]),
                "cell_id": f"cell_{int(agent_cell[idx]):02d}",
                "employer_id": int(agent_employer[idx]),
                "income": float(incomes[idx]),
                "employment_score": float(employment_score[idx]),
                "consumption": float(consumption[idx]),
                "distress_signal": float(distress_signal[idx]),
                "network_exposure": float(network_exposure[idx]),
                "outcome_score": float(outcome_score[idx]),
                "treatment": float(treated_mask[idx]),
                "cov_a": float(cov_a[idx]),
                "cov_b": float(cov_b[idx]),
                "instrument": float(instrument[idx]),
                "selected": float(selected[idx]),
                "miv_proxy": float(miv_proxy[idx]),
                "treatment_proxy": float(treatment_proxy[idx]),
                "validation_true_treatment": float(treated_mask[idx]),
                "validation_proxy": float(treatment_proxy[idx]),
                "weight": float(weights[idx]),
            }
            agent_panel_rows.append(row)
            for metric_id in (
                "income",
                "weight",
                "outcome_score",
                "treatment",
                "cov_a",
                "cov_b",
                "instrument",
                "selected",
                "miv_proxy",
                "treatment_proxy",
                "validation_true_treatment",
                "validation_proxy",
            ):
                observation_records.append(
                    ObservationRecord(
                        observation_id=f"obs_{row['agent_id']}_{metric_id}_{period_id}",
                        family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
                        time_grain=TimeFrequency.MONTH,
                        period_start=period_start,
                        period_end=period_end,
                        entity_scope=EntityScope.AGENT,
                        entity_id=row["agent_id"],
                        metric_id=metric_id,
                        observed_value=float(row[metric_id]),
                        unit="value",
                        coverage_estimate=0.95,
                        measurement_bias_flag=False,
                        censoring_mask=False,
                        trust_weight=0.9,
                        lag_days_estimate=2,
                        source_id="synthetic_agent_panel",
                        source_version="2026.03",
                        regime_id="wartime_2024",
                        shock_mask=period_index == 1,
                        schema_regime_id="synthetic_c7_schema_v1",
                        identification_mode=(
                            IdentificationMode.PROXY_IDENTIFIED
                            if metric_id in {"treatment_proxy", "validation_proxy"}
                            else IdentificationMode.POINT_IDENTIFIED
                        ),
                        proxy_source_id=(
                            "synthetic_treatment_proxy"
                            if metric_id in {"treatment_proxy", "validation_proxy"}
                            else None
                        ),
                        source_confidence_tier=SourceConfidenceTier.VALIDATED,
                    )
                )

    firm_panel_rows: list[dict[str, Any]] = []
    firm_panel_models: list[FirmPanelRow] = []
    firm_event_records: list[FirmEventRecord] = []
    for firm_idx in range(N_FIRMS):
        entry_date = date(2024, 1, 1)
        exit_period = None
        if firm_idx % 5 == 0:
            exit_period = 2
        elif firm_idx % 7 == 0:
            exit_period = 3
        for period_index, period_id in enumerate(period_ids):
            if exit_period is not None and period_index > exit_period:
                continue
            period_start, period_end = _period_bounds(period_index)
            employment = 18.0 + (firm_idx % 9) + period_index
            wage_bill = 500.0 + 30.0 * employment
            output = 1200.0 + 12.0 * firm_idx + 40.0 * period_index
            sales = output * (0.85 + 0.02 * (firm_idx % 4))
            capital = 600.0 + 9.0 * firm_idx
            leverage = 0.2 + 0.01 * (firm_idx % 6) + 0.01 * period_index
            credit_stress = 0.1 + 0.05 * (firm_idx % 5)
            prior_distress = 0.05 + 0.02 * max(period_index - 1, 0)
            cell_distress = 0.08 + 0.01 * firm_to_cell[firm_idx]
            row = {
                "firm_id": f"firm_{firm_idx:03d}",
                "period_id": period_id,
                "cell_id": f"cell_{int(firm_to_cell[firm_idx]):02d}",
                "output": float(output),
                "sales": float(sales),
                "capital": float(capital),
                "leverage": float(leverage),
                "instrument_z": float((firm_idx + period_index) % 2),
                "employment": float(employment),
                "wage_bill": float(wage_bill),
                "cell_distress": float(cell_distress),
                "credit_stress": float(credit_stress),
                "prior_distress": float(prior_distress),
            }
            firm_panel_rows.append(row)
            firm_panel_models.append(
                FirmPanelRow(
                    firm_id=row["firm_id"],
                    period_start=period_start,
                    period_end=period_end,
                    metrics={
                        "sales": row["sales"],
                        "capital": row["capital"],
                        "leverage": row["leverage"],
                        "instrument_z": row["instrument_z"],
                        "output": row["output"],
                        "employment": row["employment"],
                        "wage_bill": row["wage_bill"],
                        "cell_distress": row["cell_distress"],
                        "credit_stress": row["credit_stress"],
                        "prior_distress": row["prior_distress"],
                    },
                )
            )
        if exit_period is not None:
            _, exit_date = _period_bounds(exit_period)
            firm_event_records.append(
                FirmEventRecord(
                    firm_id=f"firm_{firm_idx:03d}",
                    entry_date=entry_date,
                    exit_date=exit_date,
                )
            )
        else:
            firm_event_records.append(
                FirmEventRecord(
                    firm_id=f"firm_{firm_idx:03d}",
                    entry_date=entry_date,
                    censor_date=date(2024, 5, 31),
                )
            )

    latest_agent_rows = {
        row["agent_id"]: row for row in agent_panel_rows if row["period_id"] == period_ids[-1]
    }
    cell_rows = []
    for cell_idx in cell_indices:
        agent_mask = agent_cell == cell_idx
        population = float(np.sum(agent_mask))
        employment = float(np.sum((agent_mask) & (agent_employer >= 0)))
        output = 2000.0 + 110.0 * cell_idx
        cell_rows.append(
            {
                "cell_id": f"cell_{cell_idx:02d}",
                "region_code": int(1 + cell_idx // 10),
                "sector_id": int(1 + cell_idx % 5),
                "population": population,
                "employment": employment,
                "output": output,
                "distress_score": 0.08 + 0.01 * cell_idx,
                "public_service_index": 0.9 - 0.002 * cell_idx,
            }
        )

    household_cell_rows = []
    for hh_idx in household_cell_indices:
        member_mask = agent_household_cell == hh_idx
        member_ids = agent_indices[member_mask]
        last_incomes = [latest_agent_rows[f"agent_{member_id:04d}"]["income"] for member_id in member_ids]
        household_cell_rows.append(
            {
                "household_cell_id": int(hh_idx),
                "cell_id": f"cell_{int(household_cell_to_cell[hh_idx]):02d}",
                "household_count": float(max(member_mask.sum(), 1)),
                "disposable_income": float(np.mean(last_incomes) if last_incomes else 0.0),
                "poverty_rate": 0.12 + 0.001 * hh_idx,
                "transfer_intensity": 0.25 + 0.0005 * hh_idx,
            }
        )

    network_edge_rows = []
    node_ids = [f"agent_{idx:04d}" for idx in agent_indices]
    budget_edges: list[GraphEdge] = []
    procurement_edges: list[GraphEdge] = []
    for idx, node_id in enumerate(node_ids):
        budget_dst = node_ids[(idx + 1) % N_AGENTS]
        procurement_dst = node_ids[(idx + 7) % N_AGENTS]
        budget_weight = 1.0 + (idx % 5) / 10.0
        procurement_weight = 0.6 + (idx % 3) / 10.0
        budget_edges.append(GraphEdge(src_id=node_id, dst_id=budget_dst, weight=budget_weight))
        procurement_edges.append(GraphEdge(src_id=node_id, dst_id=procurement_dst, weight=procurement_weight))
        network_edge_rows.append(
            {
                "src_id": node_id,
                "dst_id": budget_dst,
                "layer_id": MultiplexGraphLayerId.BUDGET.value,
                "weight": budget_weight,
            }
        )
        network_edge_rows.append(
            {
                "src_id": node_id,
                "dst_id": procurement_dst,
                "layer_id": MultiplexGraphLayerId.PROCUREMENT.value,
                "weight": procurement_weight,
            }
        )
    graph_artifacts = GraphArtifacts(
        artifact_id="c7_graph",
        node_ids=node_ids,
        layer_edges={
            MultiplexGraphLayerId.BUDGET: budget_edges,
            MultiplexGraphLayerId.PROCUREMENT: procurement_edges,
        },
        node_features={
            node_id: {
                "feature_a": float(latest_agent_rows[node_id]["income"]) / 1000.0,
                "feature_b": float(latest_agent_rows[node_id]["network_exposure"]),
            }
            for node_id in node_ids
        },
        node_states={node_id: float(latest_agent_rows[node_id]["treatment"]) for node_id in node_ids},
        cluster_ids={node_id: int(agent_cell[idx] % 8) for idx, node_id in enumerate(node_ids)},
        coordinates={
            node_id: (
                float(agent_cell[idx]),
                float(agent_household_cell[idx] % 5),
            )
            for idx, node_id in enumerate(node_ids)
        },
        bipartite_edges=[
            GraphBipartiteEdge(
                treatment_node_id=node_ids[idx],
                outcome_node_id=node_ids[(idx + 13) % N_AGENTS],
            )
            for idx in range(N_AGENTS)
        ],
    )

    observation_panel = ObservationPanel(
        panel_id="c7_synthetic_household_panel",
        family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
        time_grain=TimeFrequency.MONTH,
        records=observation_records,
    )
    firm_panels = FirmPanels(panel_id="c7_synthetic_firm_panels", rows=firm_panel_models)
    firm_events = FirmEvents(event_set_id="c7_synthetic_firm_events", records=firm_event_records)
    region_sector_panels = RegionSectorPanels(
        panel_id="c7_region_sector",
        rows=[
            RegionSectorFlowRow(
                from_region_code="UA-30",
                from_sector_id="agro",
                to_region_code="UA-30",
                to_sector_id="agro",
                technical_coefficient=0.20,
                final_demand=50.0,
                value_added=30.0,
            ),
            RegionSectorFlowRow(
                from_region_code="UA-30",
                from_sector_id="agro",
                to_region_code="UA-46",
                to_sector_id="industry",
                technical_coefficient=0.10,
                final_demand=22.0,
                value_added=10.0,
            ),
            RegionSectorFlowRow(
                from_region_code="UA-46",
                from_sector_id="industry",
                to_region_code="UA-30",
                to_sector_id="agro",
                technical_coefficient=0.12,
                final_demand=26.0,
                value_added=14.0,
            ),
            RegionSectorFlowRow(
                from_region_code="UA-46",
                from_sector_id="industry",
                to_region_code="UA-46",
                to_sector_id="industry",
                technical_coefficient=0.24,
                final_demand=40.0,
                value_added=20.0,
            ),
        ],
    )
    specs = _suite_specs()
    suite = ObservationContractCompilerSuite()
    survival_artifact = suite.survival.compile(
        firm_events,
        firm_panels,
        specs["survival_spec"],  # type: ignore[arg-type]
    )
    spec_artifact = suite.specification_curve.compile(
        observation_panel,
        specs["specification_curve_spec"],  # type: ignore[arg-type]
    )

    latest_agent_numeric = np.arange(N_AGENTS, dtype=int)
    normalized_payload = {
        "agents": {
            "age": (20 + latest_agent_numeric % 45).tolist(),
            "skill_level": base_skill.tolist(),
            "income": [latest_agent_rows[f"agent_{idx:04d}"]["income"] for idx in latest_agent_numeric],
            "reported_income": [
                0.92 * latest_agent_rows[f"agent_{idx:04d}"]["income"] for idx in latest_agent_numeric
            ],
            "risk_aversion": base_risk.tolist(),
            "is_employed": (agent_employer >= 0).tolist(),
            "employer_id": agent_employer.astype(int).tolist(),
            "household_cell_id": agent_household_cell.astype(int).tolist(),
        },
        "firms": {
            "active": [True] * N_FIRMS,
            "firm_id": firm_indices.astype(int).tolist(),
            "cell_id": firm_to_cell.astype(int).tolist(),
            "firm_type_id": (1 + firm_indices % 4).astype(int).tolist(),
            "sector_id": (1 + firm_indices % 5).astype(int).tolist(),
            "labor_count": (15.0 + firm_indices % 9).tolist(),
            "cash": (500.0 + 8.0 * firm_indices).tolist(),
            "inventory": (30.0 + firm_indices % 11).tolist(),
            "productivity": (1.0 + 0.01 * (firm_indices % 17)).tolist(),
            "wage_offer": (35.0 + 0.2 * (firm_indices % 13)).tolist(),
        },
        "cells": {
            "active": [True] * N_CELLS,
            "region_code": [row["region_code"] for row in cell_rows],
            "sector_id": [row["sector_id"] for row in cell_rows],
            "population": [row["population"] for row in cell_rows],
            "employment": [row["employment"] for row in cell_rows],
            "output": [row["output"] for row in cell_rows],
            "distress_score": [row["distress_score"] for row in cell_rows],
            "public_service_index": [row["public_service_index"] for row in cell_rows],
        },
        "household_cells": {
            "active": [True] * N_HOUSEHOLD_CELLS,
            "cell_id": [int(household_cell_to_cell[idx]) for idx in household_cell_indices],
            "household_count": [row["household_count"] for row in household_cell_rows],
            "disposable_income": [row["disposable_income"] for row in household_cell_rows],
            "poverty_rate": [row["poverty_rate"] for row in household_cell_rows],
            "transfer_intensity": [row["transfer_intensity"] for row in household_cell_rows],
        },
    }

    sobol_targets = {
        "fit_rmse": {
            "outputs_a": np.linspace(0.2, 1.0, 24),
            "outputs_b": np.linspace(0.3, 1.1, 24),
            "mixed_outputs": np.vstack(
                [
                    np.linspace(0.25, 1.05, 24),
                    np.linspace(0.28, 1.08, 24),
                    np.linspace(0.35, 1.15, 24),
                ]
            ),
            "source_combination_ids": ["survey_only", "survey_plus_income", "survey_plus_network"],
        },
        "coverage_gap": {
            "outputs_a": np.linspace(1.0, 2.0, 24),
            "outputs_b": np.linspace(1.1, 2.1, 24),
            "mixed_outputs": np.vstack(
                [
                    np.linspace(1.02, 2.02, 24),
                    np.linspace(1.08, 2.08, 24),
                    np.linspace(1.15, 2.15, 24),
                ]
            ),
            "source_combination_ids": ["survey_only", "survey_plus_income", "survey_plus_network"],
        },
    }
    survival_row_metadata = [
        {
            "firm_id": row["firm_id"],
            "period_id": period_ids[-1],
            "event": row["event"],
        }
        for row in survival_artifact.bundle.table_rows
    ]
    advanced_inputs = C7AdvancedInputs(
        agent_panel_rows=agent_panel_rows,
        firm_panel_rows=firm_panel_rows,
        cell_rows=cell_rows,
        household_cell_rows=household_cell_rows,
        survival_contract=survival_artifact.contract,
        survival_row_metadata=survival_row_metadata,
        specification_curve_input=spec_artifact.contract,
        sobol_targets=sobol_targets,
        intervention_knobs={
            "tax_rate": 0.12,
            "credit_support": 0.35,
            "procurement_multiplier": 0.18,
            "transfer_floor": 0.22,
        },
        calibration_cut_period=period_ids[-2],
        seed=SEED,
    )

    parquet_rows = {
        "agent_panel": agent_panel_rows,
        "firm_panel": firm_panel_rows,
        "cell_panel": cell_rows,
        "household_cell_panel": household_cell_rows,
        "network_edges": network_edge_rows,
    }
    parquet_paths = {}
    out_dir = tmp_path / "c7_synthetic_sources"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in parquet_rows.items():
        path = write_parquet_rows(rows, out_dir / f"{name}.parquet")
        parquet_paths[name] = path

    return C7SyntheticFixture(
        parquet_paths=parquet_paths,
        parquet_rows=parquet_rows,
        normalized_payload=normalized_payload,
        observation_panel=observation_panel,
        graph_artifacts=graph_artifacts,
        firm_panels=firm_panels,
        firm_events=firm_events,
        region_sector_panels=region_sector_panels,
        proxy_map=_proxy_map(),
        specs=specs,
        survival_contract=survival_artifact.contract,
        specification_curve_input=spec_artifact.contract,
        advanced_inputs=advanced_inputs,
    )


def persist_c7_synthetic_snapshot(
    store: FileSystemCAS,
    *,
    fixture: C7SyntheticFixture,
) -> tuple[dict[str, ArtifactRef], ArtifactRef, ArtifactRef]:
    source_refs: dict[str, ArtifactRef] = {}
    for name, path in fixture.parquet_paths.items():
        source_refs[name] = store.put_bytes(
            path.read_bytes(),
            PutOptions(
                kind=f"fabric.synthetic_source.{name}",
                media_type="application/parquet",
                schema=SchemaInfo(name=f"c7.synthetic.{name}", version="1.0"),
            ),
        )
    payload_ref = store.put_json(
        fixture.normalized_payload,
        PutOptions(
            kind="fabric.synthetic_multiscale_payload",
            media_type="application/json",
            schema=SchemaInfo(name="c7.synthetic.multiscale_payload", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    evidence_ref = store.put_json(
        EvidenceBundle(
            sources=list(source_refs.values()),
            notes=["c7.synthetic.sources", f"files={len(source_refs)}"],
        ),
        PutOptions(
            kind="fabric.evidence_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.EvidenceBundle", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    snapshot_ref = store.put_json(
        DataSnapshot(
            data_ref=payload_ref,
            evidence_ref=EvidenceBundleRef(artifact_id=evidence_ref.artifact_id),
            stats={
                "agent_count": N_AGENTS,
                "firm_count": N_FIRMS,
                "cell_count": N_CELLS,
                "household_cell_count": N_HOUSEHOLD_CELLS,
                "data_shape": "synthetic_multiscale",
            },
            notes=["c7.synthetic.data_snapshot"],
        ),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return source_refs, payload_ref, snapshot_ref


def expected_compile_all_artifact_keys() -> set[str]:
    return {
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
    }


__all__ = [
    "C7SyntheticFixture",
    "N_AGENTS",
    "N_CELLS",
    "N_FIRMS",
    "N_HOUSEHOLD_CELLS",
    "N_PERIODS",
    "SEED",
    "build_c7_synthetic_fixture",
    "expected_compile_all_artifact_keys",
    "persist_c7_synthetic_snapshot",
]
