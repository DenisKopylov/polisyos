"""Source, identity, graph, and observation-stage Ukraine builders."""

from __future__ import annotations

import gc
import shutil

from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.data_forge.domains.ukraine.manifests import (
    CalibrationBundleManifest,
    RuntimeBundleManifest,
    write_manifest,
)
from polisyos.data_forge.domains.ukraine.models import SourceConfig
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY, build_slot_family_manifest
from polisyos.ir.observation.bundles import (
    ContractCompatibilityTarget,
    ObservationContractArtifact,
    ObservationContractRoute,
    ObservationToContractManifest,
    ProxyChannelSpec,
    ProxyIdentificationBundle,
    SpecificationCurveSource,
    StrategicResponseSpec,
)
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    MultiplexGraphLayerId,
    ObservationFamily,
    StrategicResponseChannel,
)
from polisyos.ir.observation.governance import ObservationFamilyPolicyRegistry
from polisyos.ir.observation.measurement import (
    IdentificationModeRouter,
    MeasurementRegistry,
    RegimeCalendar,
    RegimeCalendarEntry,
    SchemaChangepoint,
    SchemaRegimeRegistry,
    SchemaRegimeSpec,
    ShockCalendar,
    ShockCalendarEntry,
)

from .common import *

_PANEL_OBSERVATIONAL_CONTRACT_ID = "foundry.causal.panel_observational_data.v1"
_DYNAMIC_TREATMENT_CONTRACT_ID = "foundry.causal.dynamic_treatment_data.v1"
_NETWORK_CAUSAL_CONTRACT_ID = "foundry.causal.network_causal_data.v1"
_PANEL_ECONOMETRIC_CONTRACT_ID = "foundry.econometrics.panel_data.v1"
_SURVEY_MICRODATA_CONTRACT_ID = "foundry.microsim.survey_micro_data.v1"
_SURVIVAL_CONTRACT_ID = "foundry.ml.survival_data.v1"
_NETWORK_CONTRACT_ID = "foundry.network.data.v1"
_MULTIPLEX_NETWORK_CONTRACT_ID = "foundry.network.multiplex_data.v1"
_IDENTITY_RESOLUTION_COHORT_SCHEMA = (
    "policyos.data_forge.ukraine.identity_resolution_cohort.v1"
)


def _identity_resolution_cohort_rows(
    frame: pd.DataFrame,
    *,
    cohort: str,
    identity_columns: Sequence[tuple[str, str]],
) -> list[dict[str, object]]:
    """Project one producer cohort into unique recomputable identity evidence."""

    resolved_by_identity: dict[str, bool] = {}
    for raw_column, resolved_column in identity_columns:
        raw_series = _coerce_string_series(frame, raw_column)
        resolved_series = _coerce_string_series(frame, resolved_column)
        for raw_value, resolved_value in zip(raw_series, resolved_series, strict=False):
            normalized = _normalize_identity_key(raw_value)
            if not normalized:
                continue
            resolved_by_identity[normalized] = bool(
                resolved_by_identity.get(normalized, False) or str(resolved_value).strip()
            )
    return [
        {
            "cohort": cohort,
            "raw_identity": raw_identity,
            "resolved": resolved,
        }
        for raw_identity, resolved in sorted(resolved_by_identity.items())
    ]


def build_d0_p0_stage(config: PipelineConfig) -> StageBuildResult:
    """Build P0 runtime artifacts from normalized source outputs."""

    build_root = config.build_root
    stage_dir = _stage_dir(build_root, StageId.D0_P0)
    ensure_dirs(stage_dir, build_root.manifests_dir, build_root.resolved_cas_root)
    edr = _load_source_frame(
        config,
        "edr_current",
        columns=[
            "agent_id",
            "registration_code",
            "tax_id",
            "edrpou",
            "name",
            "region_code",
            "sector_id",
            "region_numeric",
            "revenue",
            "assets",
            "liabilities",
            "employees",
            "longitude",
            "latitude",
            "cell_id",
        ],
    )
    spending = _load_source_frame(
        config,
        "spending_full",
        columns=[
            "source_agent_id",
            "target_agent_id",
            "amount",
            "period_id",
            "registration_code",
        ],
    )
    prozorro, procurement_source_id, procurement_source_warnings = _select_procurement_frame(
        config,
        columns=[
            "buyer_agent_id",
            "supplier_agent_id",
            "supplier_name",
            "amount",
            "period_id",
            "registration_code",
        ],
    )
    macro = _load_source_frame(config, "macro_nbu_derzhstat", columns=["period_id"])
    dps = _load_source_frame(
        config,
        "dps_financials",
        columns=["agent_id", "revenue", "assets", "liabilities", "employees"],
    )

    agent_registry_full = _ensure_agent_numeric_columns(edr)
    lookup = _resolve_agent_lookup(agent_registry_full)
    stage_warnings: list[str] = list(procurement_source_warnings)

    spending_for_linking = spending.copy()
    spending_for_linking["_source_agent_raw_id"] = _coerce_string_series(
        spending_for_linking, "source_agent_id"
    )
    spending_for_linking["_target_agent_raw_id"] = _coerce_string_series(
        spending_for_linking, "target_agent_id"
    )
    spending_linked_initial = _link_participants(
        spending_for_linking,
        lookup=lookup,
        source_col="source_agent_id",
        target_col="target_agent_id",
        source_out="source_agent_id",
        target_out="target_agent_id",
    )
    prozorro_for_linking = prozorro.copy()
    prozorro_for_linking["_buyer_agent_raw_id"] = _coerce_string_series(
        prozorro_for_linking, "buyer_agent_id"
    )
    prozorro_for_linking["_supplier_agent_raw_id"] = _coerce_string_series(
        prozorro_for_linking, "supplier_agent_id"
    )
    prozorro_linked_initial = _link_participants(
        prozorro_for_linking,
        lookup=lookup,
        source_col="buyer_agent_id",
        target_col="supplier_agent_id",
        source_out="buyer_agent_id",
        target_out="supplier_agent_id",
    )

    spending_coverage_before, spending_resolved_before, spending_total_before = (
        _participant_resolution_coverage(
            spending_linked_initial,
            raw_columns=["_source_agent_raw_id", "_target_agent_raw_id"],
            resolved_columns=["source_agent_id", "target_agent_id"],
        )
    )
    procurement_coverage_before, procurement_resolved_before, procurement_total_before = (
        _participant_resolution_coverage(
            prozorro_linked_initial,
            raw_columns=["_buyer_agent_raw_id", "_supplier_agent_raw_id"],
            resolved_columns=["buyer_agent_id", "supplier_agent_id"],
        )
    )
    unresolved_identity_rows = pd.concat(
        [
            _extract_unresolved_identity_rows(
                prozorro_linked_initial,
                raw_column="_supplier_agent_raw_id",
                resolved_column="supplier_agent_id",
                family=ObservationFamily.PROCUREMENT_FLOWS,
                source_id=procurement_source_id,
                weight_column="amount",
                name_column="supplier_name",
            ),
            *(
                [
                    _extract_unresolved_identity_rows(
                        spending_linked_initial,
                        raw_column="_source_agent_raw_id",
                        resolved_column="source_agent_id",
                        family=ObservationFamily.BUDGET_FLOWS,
                        source_id="spending_full",
                        weight_column="amount",
                    ),
                    _extract_unresolved_identity_rows(
                        spending_linked_initial,
                        raw_column="_target_agent_raw_id",
                        resolved_column="target_agent_id",
                        family=ObservationFamily.BUDGET_FLOWS,
                        source_id="spending_full",
                        weight_column="amount",
                    ),
                    _extract_unresolved_identity_rows(
                        prozorro_linked_initial,
                        raw_column="_buyer_agent_raw_id",
                        resolved_column="buyer_agent_id",
                        family=ObservationFamily.PROCUREMENT_FLOWS,
                        source_id=procurement_source_id,
                        weight_column="amount",
                    ),
                ]
                if (build_root.manifests_dir / "edr_identity_bridge_seed.parquet").exists()
                else []
            ),
        ],
        ignore_index=True,
    )
    (
        edr_bridge_unresolved,
        edr_bridge_candidates,
        edr_bridge_resolved,
        edr_bridge_manifest,
    ) = _build_edr_identity_bridge(
        build_root=build_root,
        agent_registry=agent_registry_full,
        unresolved_rows=unresolved_identity_rows,
    )
    bridge_lookup = _augment_lookup_with_identity_bridge(lookup, edr_bridge_resolved)
    spending_linked = _link_participants(
        spending_for_linking,
        lookup=bridge_lookup,
        source_col="source_agent_id",
        target_col="target_agent_id",
        source_out="source_agent_id",
        target_out="target_agent_id",
    )
    prozorro_linked = _link_participants(
        prozorro_for_linking,
        lookup=bridge_lookup,
        source_col="buyer_agent_id",
        target_col="supplier_agent_id",
        source_out="buyer_agent_id",
        target_out="supplier_agent_id",
    )

    participant_ids = pd.Index(
        pd.concat(
            [
                spending_linked.get("source_agent_id", pd.Series(dtype="string"))
                .dropna()
                .astype("string"),
                spending_linked.get("target_agent_id", pd.Series(dtype="string"))
                .dropna()
                .astype("string"),
                prozorro_linked.get("buyer_agent_id", pd.Series(dtype="string"))
                .dropna()
                .astype("string"),
                prozorro_linked.get("supplier_agent_id", pd.Series(dtype="string"))
                .dropna()
                .astype("string"),
                dps.get("agent_id", pd.Series(dtype="string")).dropna().astype("string"),
            ],
            ignore_index=True,
        ).unique()
    )
    runtime_agents = agent_registry_full[
        agent_registry_full.get("agent_id", pd.Series(dtype="string"))
        .astype("string")
        .isin(participant_ids)
    ].copy()
    if runtime_agents.empty:
        runtime_agents = agent_registry_full.copy()
    if "cell_id" not in runtime_agents.columns:
        runtime_agents["cell_id"] = [
            _stable_cell_id(region, sector)
            for region, sector in zip(
                _coerce_string_series(runtime_agents, "region_code", fill="unknown"),
                _coerce_string_series(runtime_agents, "sector_id", fill="unknown"),
                strict=False,
            )
        ]

    public_entity_registry = (
        pd.concat(
            [
                spending_linked.assign(
                    entity_type="budget_participant",
                    entity_id=spending_linked.get("source_agent_id", pd.Series(dtype="string")),
                )[["entity_id", "entity_type", "period_id"]]
                if "source_agent_id" in spending_linked.columns
                else pd.DataFrame(columns=["entity_id", "entity_type", "period_id"]),
                prozorro_linked.assign(
                    entity_type="procurement_buyer",
                    entity_id=prozorro_linked.get("buyer_agent_id", pd.Series(dtype="string")),
                )[["entity_id", "entity_type", "period_id"]]
                if "buyer_agent_id" in prozorro_linked.columns
                else pd.DataFrame(columns=["entity_id", "entity_type", "period_id"]),
            ],
            ignore_index=True,
        )
        .dropna(subset=["entity_id"])
        .drop_duplicates()
    )

    cell_registry = (
        runtime_agents.assign(
            region_code=_coerce_string_series(runtime_agents, "region_code", fill="unknown"),
            sector_id=_coerce_string_series(runtime_agents, "sector_id", fill="unknown"),
        )
        .groupby(["cell_id", "region_code", "sector_id"], as_index=False)
        .agg(agent_count=("agent_id", "nunique"))
    )
    region_mapping = {
        value: idx
        for idx, value in enumerate(sorted(cell_registry["region_code"].astype(str).unique()))
    }
    sector_mapping = {
        value: idx
        for idx, value in enumerate(sorted(cell_registry["sector_id"].astype(str).unique()))
    }
    cell_registry["region_numeric"] = (
        cell_registry["region_code"].astype(str).map(region_mapping).astype(int)
    )
    cell_registry["sector_numeric"] = (
        cell_registry["sector_id"].astype(str).map(sector_mapping).astype(int)
    )

    dps_joined = dps.merge(
        runtime_agents[["agent_id", "cell_id"]],
        on="agent_id",
        how="left",
    )
    dps_joined["cell_id"] = dps_joined["cell_id"].fillna("cell::unknown::unknown")
    cell_state = (
        dps_joined.groupby("cell_id", as_index=False)
        .agg(
            population=("employees", "sum"),
            employment=("employees", "sum"),
            output=("revenue", "sum"),
            distress_score=("liabilities", "sum"),
            public_service_index=("assets", "sum"),
        )
        .merge(
            cell_registry[["cell_id", "region_numeric", "sector_numeric", "agent_count"]],
            on="cell_id",
            how="right",
        )
        .fillna(
            {
                "population": 0.0,
                "employment": 0.0,
                "output": 0.0,
                "distress_score": 0.0,
                "public_service_index": 0.0,
                "region_numeric": 0,
                "sector_numeric": 0,
                "agent_count": 0,
            }
        )
    )
    cell_state["agent_count"] = _sanitize_numeric_series(
        cell_state["agent_count"], fill=0.0, lower=0.0
    )
    cell_state["population"] = _sanitize_numeric_series(
        cell_state["population"], fill=0.0, lower=0.0, upper=1e9
    )
    cell_state["employment"] = _sanitize_numeric_series(
        cell_state["employment"], fill=0.0, lower=0.0, upper=1e9
    )
    cell_state["output"] = _sanitize_numeric_series(cell_state["output"], fill=0.0, lower=0.0)
    cell_state["distress_score"] = _sanitize_numeric_series(
        cell_state["distress_score"], fill=0.0, lower=0.0
    )
    cell_state["public_service_index"] = _sanitize_numeric_series(
        cell_state["public_service_index"], fill=0.0, lower=0.0
    )
    population_fallback_mask = cell_state["population"] <= 0.0
    if population_fallback_mask.any():
        cell_state.loc[population_fallback_mask, "population"] = cell_state.loc[
            population_fallback_mask, "agent_count"
        ].clip(lower=1.0)
        stage_warnings.append(
            f"cell_population_fallback_to_agent_count:{int(population_fallback_mask.sum())}"
        )
    if float(cell_state["employment"].max()) <= 0.0:
        stage_warnings.append("dps_employment_missing_using_zero_fallback")
    employment_cap = np.minimum(
        cell_state["employment"].to_numpy(dtype=float),
        cell_state["population"].to_numpy(dtype=float),
    )
    cell_state["employment"] = np.maximum(employment_cap, 0.0)
    cell_state = cell_state.drop(columns=["agent_count"], errors="ignore")

    geo_index = runtime_agents[["agent_id", "cell_id", "region_code"]].drop_duplicates().copy()
    if "longitude" not in geo_index.columns:
        geo_index["longitude"] = 0.0
    if "latitude" not in geo_index.columns:
        geo_index["latitude"] = 0.0

    budget_arrays = _graph_arrays_from_edges(
        spending_linked.fillna({"period_id": "2025-01"}),
        src_col="source_agent_id",
        dst_col="target_agent_id",
        weight_col="amount",
    )
    procurement_arrays = _graph_arrays_from_edges(
        prozorro_linked.fillna({"period_id": "2025-01"}),
        src_col="buyer_agent_id",
        dst_col="supplier_agent_id",
        weight_col="amount",
        node_ids=list(budget_arrays["node_ids"]),
    )

    outputs: dict[str, ArtifactRecord] = {}
    outputs["agent_registry_runtime.parquet"] = _write_frame(
        stage_dir / "agent_registry_runtime.parquet",
        runtime_agents,
    )
    outputs["public_entity_registry.parquet"] = _write_frame(
        stage_dir / "public_entity_registry.parquet",
        public_entity_registry,
    )
    outputs["edr_identity_bridge_unresolved_raw.parquet"] = _write_frame(
        stage_dir / "edr_identity_bridge_unresolved_raw.parquet",
        unresolved_identity_rows,
    )
    outputs["edr_identity_bridge_unresolved.parquet"] = _write_frame(
        stage_dir / "edr_identity_bridge_unresolved.parquet",
        edr_bridge_unresolved,
    )
    outputs["edr_identity_bridge_candidates.parquet"] = _write_frame(
        stage_dir / "edr_identity_bridge_candidates.parquet",
        edr_bridge_candidates,
    )
    outputs["edr_identity_bridge_resolved.parquet"] = _write_frame(
        stage_dir / "edr_identity_bridge_resolved.parquet",
        edr_bridge_resolved,
    )
    edr_bridge_manifest.update(
        {
            "unresolved_identity_rows_raw": len(unresolved_identity_rows),
            "unresolved_unique_numeric_ids_raw": int(
                unresolved_identity_rows["normalized_raw_registration_code"]
                .astype("string")
                .nunique()
                if not unresolved_identity_rows.empty
                else 0
            ),
            "spending_coverage_before": spending_coverage_before,
            "spending_resolved_before": spending_resolved_before,
            "spending_total_before": spending_total_before,
            "procurement_coverage_before": procurement_coverage_before,
            "procurement_resolved_before": procurement_resolved_before,
            "procurement_total_before": procurement_total_before,
        }
    )
    edr_bridge_manifest_path = _write_json(
        stage_dir / "edr_identity_bridge_manifest.json",
        edr_bridge_manifest,
    )
    outputs["edr_identity_bridge_manifest.json"] = ArtifactRecord.from_path(
        edr_bridge_manifest_path
    )
    outputs["cell_registry_region_sector.parquet"] = _write_frame(
        stage_dir / "cell_registry_region_sector.parquet",
        cell_registry,
    )
    outputs["geo_index_runtime.parquet"] = _write_frame(
        stage_dir / "geo_index_runtime.parquet", geo_index
    )
    outputs["budget_graph_sparse.npz"] = _write_npz(
        stage_dir / "budget_graph_sparse.npz", **budget_arrays
    )
    outputs["procurement_graph_sparse.npz"] = _write_npz(
        stage_dir / "procurement_graph_sparse.npz", **procurement_arrays
    )
    outputs["cell_state_seed_v1.npz"] = _write_npz(
        stage_dir / "cell_state_seed_v1.npz",
        cell_id=cell_state["cell_id"].to_numpy(dtype=object),
        region_numeric=cell_state["region_numeric"].to_numpy(dtype=int),
        sector_numeric=cell_state["sector_numeric"].to_numpy(dtype=int),
        population=cell_state["population"].to_numpy(dtype=float),
        employment=cell_state["employment"].to_numpy(dtype=float),
        output=cell_state["output"].to_numpy(dtype=float),
        distress_score=cell_state["distress_score"].to_numpy(dtype=float),
        public_service_index=cell_state["public_service_index"].to_numpy(dtype=float),
    )

    slot_family_manifest = build_slot_family_manifest(DEFAULT_SLOT_REGISTRY)
    slot_family_path = stage_dir / "slot_family_manifest.json"
    _write_json(slot_family_path, slot_family_manifest)
    outputs["slot_family_manifest.json"] = ArtifactRecord.from_path(slot_family_path)

    spending_coverage, spending_resolved, spending_total = _participant_resolution_coverage(
        spending_linked,
        raw_columns=["_source_agent_raw_id", "_target_agent_raw_id"],
        resolved_columns=["source_agent_id", "target_agent_id"],
    )
    procurement_coverage, procurement_resolved, procurement_total = (
        _participant_resolution_coverage(
            prozorro_linked,
            raw_columns=["_buyer_agent_raw_id", "_supplier_agent_raw_id"],
            resolved_columns=["buyer_agent_id", "supplier_agent_id"],
        )
    )
    identity_resolution_cohort_path = _write_json(
        stage_dir / "identity_resolution_cohort_v1.json",
        {
            "schema_version": _IDENTITY_RESOLUTION_COHORT_SCHEMA,
            "rows": [
                *_identity_resolution_cohort_rows(
                    spending_linked,
                    cohort="spending",
                    identity_columns=(
                        ("_source_agent_raw_id", "source_agent_id"),
                        ("_target_agent_raw_id", "target_agent_id"),
                    ),
                ),
                *_identity_resolution_cohort_rows(
                    prozorro_linked,
                    cohort="procurement",
                    identity_columns=(
                        ("_buyer_agent_raw_id", "buyer_agent_id"),
                        ("_supplier_agent_raw_id", "supplier_agent_id"),
                    ),
                ),
            ],
        },
    )
    outputs["identity_resolution_cohort_v1.json"] = ArtifactRecord.from_path(
        identity_resolution_cohort_path
    )
    edr_bridge_manifest["spending_coverage_after"] = spending_coverage
    edr_bridge_manifest["spending_resolved_after"] = spending_resolved
    edr_bridge_manifest["spending_total_after"] = spending_total
    edr_bridge_manifest["procurement_coverage_after"] = procurement_coverage
    edr_bridge_manifest["procurement_resolved_after"] = procurement_resolved
    edr_bridge_manifest["procurement_total_after"] = procurement_total
    edr_bridge_manifest["bridge_improved_spending_resolved"] = max(
        int(spending_resolved - spending_resolved_before),
        0,
    )
    edr_bridge_manifest["bridge_improved_procurement_resolved"] = max(
        int(procurement_resolved - procurement_resolved_before),
        0,
    )
    _write_json(edr_bridge_manifest_path, edr_bridge_manifest)
    outputs["edr_identity_bridge_manifest.json"] = ArtifactRecord.from_path(
        edr_bridge_manifest_path
    )
    runtime_agent_count = len(runtime_agents)
    cell_count = len(cell_registry)
    macro_rows = len(macro)
    budget_graph_nnz = outputs["budget_graph_sparse.npz"].nnz
    procurement_graph_nnz = outputs["procurement_graph_sparse.npz"].nnz

    validation_agents, validation_cells, validation_cell_state, validation_warnings = (
        _validation_subset(
            runtime_agents,
            cell_registry,
            cell_state,
        )
    )
    stage_warnings.extend(validation_warnings)

    # Drop heavyweight runtime/intermediate frames before the bindings smoke test.
    del spending
    del spending_for_linking
    del spending_linked
    del prozorro
    del prozorro_for_linking
    del prozorro_linked
    del macro
    del dps
    del dps_joined
    del agent_registry_full
    del runtime_agents
    del public_entity_registry
    del cell_registry
    del cell_state
    del geo_index
    gc.collect()

    payload = _build_synthetic_multiscale_payload(
        validation_agents, validation_cells, validation_cell_state
    )
    store = FileSystemCAS(build_root.resolved_cas_root)
    payload_ref = _cas_put_json(store, payload, kind="fabric.synthetic_multiscale_payload")
    data_snapshot_ref = _cas_put_json(
        store,
        DataSnapshot(
            data_ref=payload_ref,
            stats={
                "n_agents": len(validation_agents),
                "n_cells": len(validation_cells),
                "n_budget_edges": len(budget_arrays["weight"]),
                "n_procurement_edges": len(procurement_arrays["weight"]),
            },
            notes=[
                "ukraine_part_b_d0_p0_runtime_seed",
                "validation_payload_downsampled_from_full_runtime",
            ],
        ),
        kind="fabric.data_snapshot",
    )
    runtime_bundle = RuntimeBundleManifest(
        outputs=outputs,
        data_snapshot_artifact_id=str(data_snapshot_ref.artifact_id),
        input_bindings_artifact_id=None,
        validation=[],
        metrics={
            "n_agents": runtime_agent_count,
            "n_cells": cell_count,
            "budget_graph_nnz": budget_graph_nnz,
            "procurement_graph_nnz": procurement_graph_nnz,
            "foundry_input_bindings": "consumer_required",
            "validation_binding_agent_count": len(validation_agents),
            "validation_binding_cell_count": len(validation_cells),
        },
    )
    runtime_bundle_path = stage_dir / "runtime_bundle_manifest.json"
    write_manifest(runtime_bundle_path, runtime_bundle)
    outputs["runtime_bundle_manifest.json"] = ArtifactRecord.from_path(runtime_bundle_path)

    findings: list[ValidationFinding] = []
    if spending_coverage is None:
        findings.append(
            ValidationFinding(
                severity="error",
                code="spending_coverage_not_evaluable",
                message="runtime spending coverage could not be evaluated because no participant identifiers were present",
            )
        )
    elif spending_coverage < config.stages[StageId.D0_P0.value].coverage_threshold:
        findings.append(
            ValidationFinding(
                severity="error",
                code="spending_coverage_below_threshold",
                message=f"runtime spending coverage {spending_coverage:.3f} < threshold",
            )
        )
    if procurement_coverage is None:
        stage_warnings.append(
            "procurement_coverage_not_evaluable: normalized procurement layer does not contain buyer/supplier participant identifiers; detail hydration is still required for full P0 fidelity"
        )
    elif procurement_coverage < config.stages[StageId.D0_P0.value].coverage_threshold:
        findings.append(
            ValidationFinding(
                severity="error",
                code="procurement_coverage_below_threshold",
                message=f"runtime procurement coverage {procurement_coverage:.3f} < threshold",
            )
        )

    return StageBuildResult(
        outputs=outputs,
        findings=findings,
        warnings=stage_warnings,
        metrics={
            "runtime_cohort_coverage_spending": spending_coverage,
            "runtime_cohort_coverage_procurement": procurement_coverage,
            "runtime_cohort_resolved_spending": spending_resolved,
            "runtime_cohort_total_spending": spending_total,
            "runtime_cohort_resolved_procurement": procurement_resolved,
            "runtime_cohort_total_procurement": procurement_total,
            "procurement_source_id": procurement_source_id,
            "agent_count": runtime_agent_count,
            "cell_count": cell_count,
            "macro_rows": macro_rows,
        },
        manifest_paths=[runtime_bundle_path],
    )


def _network_contracts_for_graph(
    *,
    adjacency: np.ndarray,
    node_ids: Sequence[str],
    agent_registry: pd.DataFrame,
    output_prefix: str,
    stage_dir: Path,
    layer_id: str,
) -> dict[str, ArtifactRecord]:
    node_features, node_states = _node_features_from_agent_registry(
        agent_registry, node_ids=node_ids
    )
    network_payload = {
        "adjacency": adjacency,
        "node_features": node_features,
        "node_states": node_states,
        "node_ids": list(node_ids),
        "metadata": {"layer_id": layer_id, "producer_stage": "d1"},
    }
    treatment = (
        node_states > float(np.nanmedian(node_states) if len(node_states) else 0.0)
    ).astype(float)
    outcome = np.log1p(np.maximum(node_states, 0.0))
    causal_payload = {
        "outcome": outcome,
        "treatment": treatment,
        "covariates": node_features,
        "adjacency_matrix": adjacency,
        "metadata": {"layer_id": layer_id, "producer_stage": "d1"},
    }
    outputs = {
        f"{output_prefix}_network_data.json": ArtifactRecord.from_path(
            _write_json(stage_dir / f"{output_prefix}_network_data.json", network_payload)
        ),
        f"{output_prefix}_network_causal_data.json": ArtifactRecord.from_path(
            _write_json(stage_dir / f"{output_prefix}_network_causal_data.json", causal_payload)
        ),
    }
    return outputs


def build_d1_stage(config: PipelineConfig) -> StageBuildResult:
    """Build D1 enrichment graphs, proxy checks, and multiplex manifests."""

    build_root = config.build_root
    stage_dir = _stage_dir(build_root, StageId.D1)
    ensure_dirs(stage_dir)
    agent_registry = pd.read_parquet(
        _stage_dir(build_root, StageId.D0_P0) / "agent_registry_runtime.parquet"
    )
    tax_risk = _load_source_frame(config, "dps_tax_risk")
    trade = _load_source_frame(config, "customs_trade")
    nszu = _load_source_frame(config, "nszu_payments")
    runtime_agents = _ensure_agent_numeric_columns(agent_registry)
    node_ids = list(runtime_agents["agent_id"].astype(str).drop_duplicates())
    lookup = _resolve_agent_lookup(runtime_agents)

    trade_linked = _link_participants(
        trade,
        lookup=lookup,
        source_col="source_agent_id",
        target_col="target_agent_id",
        source_out="source_agent_id",
        target_out="target_agent_id",
    )
    node_ids = _collect_graph_node_ids(
        base_node_ids=list(runtime_agents["agent_id"].astype(str).drop_duplicates()),
        edge_frames=[
            (trade_linked, "source_agent_id", "target_agent_id"),
        ],
    )
    trade_arrays = _graph_arrays_from_edges(
        trade_linked.fillna({"period_id": "2025-01"}),
        src_col="source_agent_id",
        dst_col="target_agent_id",
        weight_col="trade_value",
        node_ids=node_ids,
    )

    distress = tax_risk.merge(runtime_agents[["agent_id"]], on="agent_id", how="inner").copy()
    distress["peer_agent_id"] = distress["agent_id"]
    distress["weight"] = _safe_numeric_series(distress, "tax_debt") + _safe_numeric_series(
        distress, "risk_score"
    )
    distress["period_id"] = distress.get("period_id", "2025-01")
    node_ids = _collect_graph_node_ids(
        base_node_ids=node_ids,
        edge_frames=[
            (
                distress.rename(columns={"agent_id": "src_agent_id"}),
                "src_agent_id",
                "peer_agent_id",
            ),
        ],
    )
    distress_arrays = _graph_arrays_from_edges(
        distress.rename(columns={"agent_id": "src_agent_id"}),
        src_col="src_agent_id",
        dst_col="peer_agent_id",
        weight_col="weight",
        node_ids=node_ids,
    )

    nszu = nszu.copy()
    if "source_agent_id" not in nszu.columns:
        nszu["source_agent_id"] = nszu.get("agent_id", pd.Series(["agent::unknown"] * len(nszu)))
    if "target_agent_id" not in nszu.columns:
        nszu["target_agent_id"] = nszu.get("agent_id", pd.Series(["agent::unknown"] * len(nszu)))
    if "payment_amount" not in nszu.columns:
        nszu["payment_amount"] = 1.0
    public_service_linked = _link_participants(
        nszu,
        lookup=lookup,
        source_col="source_agent_id",
        target_col="target_agent_id",
        source_out="source_agent_id",
        target_out="target_agent_id",
    )
    node_ids = _collect_graph_node_ids(
        base_node_ids=node_ids,
        edge_frames=[
            (public_service_linked, "source_agent_id", "target_agent_id"),
        ],
    )
    public_service_arrays = _graph_arrays_from_edges(
        public_service_linked.fillna({"period_id": "2025-01"}),
        src_col="source_agent_id",
        dst_col="target_agent_id",
        weight_col="payment_amount",
        node_ids=node_ids,
    )
    full_node_count = len(node_ids)
    contract_node_limit = _int_env("POLISYOS_UKRAINE_DATA_D1_CONTRACT_NODE_LIMIT", 1024)
    contract_node_ids = _select_contract_graph_node_ids(
        [trade_arrays, distress_arrays, public_service_arrays],
        max_nodes=min(contract_node_limit, max(full_node_count, 2)),
    )
    trade_contract_arrays = _reindex_edge_arrays_to_node_subset(
        trade_arrays,
        node_ids=contract_node_ids,
    )
    distress_contract_arrays = _reindex_edge_arrays_to_node_subset(
        distress_arrays,
        node_ids=contract_node_ids,
    )
    public_service_contract_arrays = _reindex_edge_arrays_to_node_subset(
        public_service_arrays,
        node_ids=contract_node_ids,
    )
    trade_adj = _adjacency_from_edge_arrays(trade_contract_arrays)
    distress_adj = _adjacency_from_edge_arrays(distress_contract_arrays)
    public_service_adj = _adjacency_from_edge_arrays(public_service_contract_arrays)

    outputs: dict[str, ArtifactRecord] = {}
    outputs["trade_graph_sparse.npz"] = _write_npz(
        stage_dir / "trade_graph_sparse.npz", **trade_arrays
    )
    outputs["distress_graph_sparse.npz"] = _write_npz(
        stage_dir / "distress_graph_sparse.npz", **distress_arrays
    )
    outputs["public_service_graph_sparse.npz"] = _write_npz(
        stage_dir / "public_service_graph_sparse.npz",
        **public_service_arrays,
    )
    outputs.update(
        _network_contracts_for_graph(
            adjacency=trade_adj,
            node_ids=contract_node_ids,
            agent_registry=runtime_agents,
            output_prefix="trade",
            stage_dir=stage_dir,
            layer_id=MultiplexGraphLayerId.TRADE.value,
        )
    )
    outputs.update(
        _network_contracts_for_graph(
            adjacency=distress_adj,
            node_ids=contract_node_ids,
            agent_registry=runtime_agents,
            output_prefix="distress",
            stage_dir=stage_dir,
            layer_id=MultiplexGraphLayerId.DISTRESS.value,
        )
    )
    outputs.update(
        _network_contracts_for_graph(
            adjacency=public_service_adj,
            node_ids=contract_node_ids,
            agent_registry=runtime_agents,
            output_prefix="public_service",
            stage_dir=stage_dir,
            layer_id=MultiplexGraphLayerId.PUBLIC_SERVICE.value,
        )
    )

    multiplex_payload = {
        "adjacency_layers": np.stack([trade_adj, distress_adj, public_service_adj]),
        "node_features": _node_features_from_agent_registry(
            runtime_agents, node_ids=contract_node_ids
        )[0],
        "node_ids": contract_node_ids,
        "metadata": {
            "layers": ["trade", "distress", "public_service"],
            "full_node_count": full_node_count,
            "contract_node_count": len(contract_node_ids),
            "compression_mode": "top_weighted_degree_subgraph",
            "producer_stage": "d1",
        },
    }
    outputs["multiplex_network_data.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "multiplex_network_data.json", multiplex_payload)
    )

    proxy_bundle = ProxyIdentificationBundle(
        contract_target=ContractCompatibilityTarget(
            contract_id="foundry.causal.proxy_measurement_data.v1",
            contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.ProxyMeasurementData",
        ),
        proxy_channels=[
            ProxyChannelSpec(
                family=ObservationFamily.DISTRESS_ENFORCEMENT,
                proxy_variable="tax_debt",
                latent_variable="distress",
                treatment_variable="x",
                outcome_variable="y",
                target_contract=ContractCompatibilityTarget(
                    contract_id="foundry.causal.proxy_measurement_data.v1",
                    contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.ProxyMeasurementData",
                ),
                notes=["verification channel for tax debt -> distress"],
            ),
            ProxyChannelSpec(
                family=ObservationFamily.PROCUREMENT_FLOWS,
                proxy_variable="procurement_revenue",
                latent_variable="cashflow",
                treatment_variable="x",
                outcome_variable="y",
                target_contract=ContractCompatibilityTarget(
                    contract_id="foundry.causal.proxy_measurement_data.v1",
                    contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.ProxyMeasurementData",
                ),
            ),
            ProxyChannelSpec(
                family=ObservationFamily.LABOR_MARKET,
                proxy_variable="registered_employment",
                latent_variable="true_employment",
                treatment_variable="x",
                outcome_variable="y",
                target_contract=ContractCompatibilityTarget(
                    contract_id="foundry.causal.proxy_measurement_data.v1",
                    contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.ProxyMeasurementData",
                ),
            ),
        ],
        contract_payload={
            "producer_stage": "d1",
            "identification_execution": "foundry_consumer_required",
            "proxy_channels_declared": [
                "tax_debt_to_distress",
                "procurement_revenue_to_cashflow",
                "admin_employment_to_true_employment",
            ],
        },
        proxy_map={
            "distress": "tax_debt",
            "cashflow": "procurement_revenue",
            "true_employment": "registered_employment",
        },
    )
    proxy_bundle_path = stage_dir / "proxy_identification_bundle_v1.json"
    _write_json(proxy_bundle_path, proxy_bundle)
    outputs["proxy_identification_bundle_v1.json"] = ArtifactRecord.from_path(proxy_bundle_path)

    multiplex_manifest = {
        "schema_version": "1.0",
        "layers": {
            "trade": {
                "sparse_graph": str(stage_dir / "trade_graph_sparse.npz"),
                "network_contract": str(stage_dir / "trade_network_data.json"),
                "network_causal_contract": str(stage_dir / "trade_network_causal_data.json"),
            },
            "distress": {
                "sparse_graph": str(stage_dir / "distress_graph_sparse.npz"),
                "network_contract": str(stage_dir / "distress_network_data.json"),
                "network_causal_contract": str(stage_dir / "distress_network_causal_data.json"),
            },
            "public_service": {
                "sparse_graph": str(stage_dir / "public_service_graph_sparse.npz"),
                "network_contract": str(stage_dir / "public_service_network_data.json"),
                "network_causal_contract": str(
                    stage_dir / "public_service_network_causal_data.json"
                ),
            },
        },
        "node_count": full_node_count,
        "contract_node_count": len(contract_node_ids),
        "compression_mode": "top_weighted_degree_subgraph",
        "proxy_identification_bundle": str(proxy_bundle_path),
    }
    multiplex_manifest_path = stage_dir / "multiplex_graph_manifest.json"
    _write_json(multiplex_manifest_path, multiplex_manifest)
    outputs["multiplex_graph_manifest.json"] = ArtifactRecord.from_path(multiplex_manifest_path)

    findings: list[ValidationFinding] = []
    return StageBuildResult(
        outputs=outputs,
        findings=findings,
        warnings=[
            (
                f"d1_dense_contract_compacted:{len(contract_node_ids)}/{full_node_count}"
                if len(contract_node_ids) < full_node_count
                else "d1_dense_contract_full_graph"
            )
        ],
        metrics={
            "trade_graph_nnz": outputs["trade_graph_sparse.npz"].nnz,
            "distress_graph_nnz": outputs["distress_graph_sparse.npz"].nnz,
            "public_service_graph_nnz": outputs["public_service_graph_sparse.npz"].nnz,
            "proxy_identified_channels": sum(
                1 for item in proxy_checks.values() if item["status"] == "identified"
            ),
            "full_node_count": full_node_count,
            "contract_node_count": len(contract_node_ids),
        },
        manifest_paths=[proxy_bundle_path, multiplex_manifest_path],
    )


def _family_metric_columns(source: SourceConfig, frame: pd.DataFrame) -> list[str]:
    if source.metric_columns:
        return [column for column in source.metric_columns if column in frame.columns]
    numeric_columns = [
        column
        for column in frame.columns
        if pd.api.types.is_numeric_dtype(frame[column])
        and column not in {"coverage_estimate", "trust_weight"}
    ]
    return numeric_columns[:4]


def _entity_scope_identity(
    source: SourceConfig, row: pd.Series
) -> tuple[str | None, str | None, str | None, str | None]:
    entity_id = None
    entity_candidates: list[str] = []
    for column in [source.entity_id_column or "agent_id", *source.identity_columns, "agent_id"]:
        if column and column not in entity_candidates:
            entity_candidates.append(column)
    for column in entity_candidates:
        entity_id = _compact_locator_value(
            row.get(column, ""),
            max_length=128,
            prefix="entity",
        )
        if entity_id:
            break
    cell_id = _compact_locator_value(
        row.get(source.cell_id_column or "cell_id", ""),
        max_length=128,
        prefix="cell",
    )
    region_code = _compact_locator_value(
        row.get(source.region_code_column or "region_code", ""),
        max_length=64,
        prefix="region",
    )
    sector_id = _compact_locator_value(
        row.get(source.sector_id_column or "sector_id", ""),
        max_length=64,
        prefix="sector",
    )
    return entity_id, cell_id, region_code, sector_id


def _compact_locator_series(
    frame: pd.DataFrame,
    columns: Sequence[str],
    *,
    max_length: int,
    prefix: str,
) -> pd.Series:
    result = pd.Series([None] * len(frame), index=frame.index, dtype=object)
    seen: set[str] = set()
    for column in columns:
        if not column or column in seen or column not in frame.columns:
            continue
        seen.add(column)
        compact = frame[column].map(
            lambda value: _compact_locator_value(value, max_length=max_length, prefix=prefix)
        )
        mask = result.isna() & compact.notna()
        if mask.any():
            result.loc[mask] = compact.loc[mask]
        if result.notna().all():
            break
    return result


def _period_series_to_iso_bounds(
    values: pd.Series,
    *,
    time_grain: TimeFrequency,
) -> tuple[pd.Series, pd.Series]:
    raw = values.fillna("2025-01").astype(str)
    mapping = {key: _period_to_dates(key, time_grain) for key in raw.unique().tolist()}
    period_start = raw.map(lambda key: mapping[key][0].isoformat())
    period_end = raw.map(lambda key: mapping[key][1].isoformat())
    return period_start, period_end


def _observation_metric_frames_from_frame(
    source: SourceConfig,
    frame: pd.DataFrame,
    *,
    row_offset: int = 0,
) -> Iterable[tuple[str, pd.DataFrame]]:
    metric_columns = _family_metric_columns(source, frame)
    if not metric_columns:
        return
    period_values = (
        frame[source.period_column]
        if source.period_column in frame.columns
        else pd.Series(
            ["2025-01"] * len(frame),
            index=frame.index,
            dtype="string",
        )
    )
    period_start, period_end = _period_series_to_iso_bounds(
        period_values, time_grain=source.time_grain
    )
    entity_id = _compact_locator_series(
        frame,
        [source.entity_id_column or "agent_id", *source.identity_columns, "agent_id"],
        max_length=128,
        prefix="entity",
    )
    cell_id = _compact_locator_series(
        frame,
        [source.cell_id_column or "cell_id"],
        max_length=128,
        prefix="cell",
    )
    region_code = _compact_locator_series(
        frame,
        [source.region_code_column or "region_code"],
        max_length=64,
        prefix="region",
    )
    sector_id = _compact_locator_series(
        frame,
        [source.sector_id_column or "sector_id"],
        max_length=64,
        prefix="sector",
    )
    measurement_bias = (
        frame["measurement_bias_flag"].fillna(False).astype(bool)
        if "measurement_bias_flag" in frame.columns
        else pd.Series([False] * len(frame), index=frame.index, dtype=bool)
    )
    censoring_mask = (
        frame["censoring_mask"].fillna(False).astype(bool)
        if "censoring_mask" in frame.columns
        else pd.Series([False] * len(frame), index=frame.index, dtype=bool)
    )
    trust_weight = (
        pd.to_numeric(frame["trust_weight"], errors="coerce").fillna(source.trust_weight)
        if "trust_weight" in frame.columns
        else pd.Series([source.trust_weight] * len(frame), index=frame.index, dtype=float)
    )
    lag_days = (
        pd.to_numeric(frame["lag_days_estimate"], errors="coerce").fillna(0).astype(int)
        if "lag_days_estimate" in frame.columns
        else pd.Series([0] * len(frame), index=frame.index, dtype=int)
    )
    regime_id = (
        frame["regime_id"].astype(str)
        if "regime_id" in frame.columns
        else pd.Series(
            [source.regime_id] * len(frame),
            index=frame.index,
            dtype=object,
        )
    )
    schema_regime_id = (
        frame["schema_regime_id"].astype(str)
        if "schema_regime_id" in frame.columns
        else pd.Series([source.schema_regime_id] * len(frame), index=frame.index, dtype=object)
    )
    proxy_source_id = (
        f"{source.source_id}_proxy"
        if source.identification_mode == IdentificationMode.PROXY_IDENTIFIED
        else None
    )
    source_slug = _kernel_safe_id(source.source_id, prefix="src")

    for metric_id in metric_columns:
        metric_values = pd.to_numeric(frame[metric_id], errors="coerce")
        valid = metric_values.notna() & np.isfinite(metric_values.to_numpy(dtype=float))
        if not valid.any():
            continue
        metric_slug = _kernel_safe_id(metric_id, prefix="metric")
        row_numbers = (
            pd.Series(np.arange(row_offset, row_offset + len(frame)), index=frame.index)
            .loc[valid]
            .astype(str)
            .str.zfill(8)
        )
        metric_frame = pd.DataFrame(
            {
                "observation_id": "obs." + source_slug + "." + metric_slug + "." + row_numbers,
                "family": source.observation_family.value,
                "time_grain": source.time_grain.value,
                "period_start": period_start.loc[valid],
                "period_end": period_end.loc[valid],
                "entity_scope": (source.entity_scope or EntityScope.AGENT).value,
                "entity_id": entity_id.loc[valid],
                "cell_id": cell_id.loc[valid],
                "region_code": region_code.loc[valid],
                "sector_id": sector_id.loc[valid],
                "metric_id": metric_id,
                "observed_value": metric_values.loc[valid].astype(float),
                "unit": "unit",
                "coverage_estimate": source.coverage_estimate,
                "measurement_bias_flag": measurement_bias.loc[valid],
                "censoring_mask": censoring_mask.loc[valid],
                "trust_weight": trust_weight.loc[valid].astype(float),
                "lag_days_estimate": lag_days.loc[valid].astype(int),
                "source_id": source.source_id,
                "source_version": source.source_version,
                "regime_id": regime_id.loc[valid],
                "shock_mask": False,
                "schema_regime_id": schema_regime_id.loc[valid],
                "identification_mode": source.identification_mode.value,
                "source_confidence_tier": source.source_confidence_tier.value,
                "proxy_source_id": proxy_source_id,
            }
        )
        for column in [
            "family",
            "time_grain",
            "entity_scope",
            "metric_id",
            "unit",
            "source_id",
            "source_version",
            "identification_mode",
            "source_confidence_tier",
        ]:
            if column in metric_frame.columns:
                metric_frame[column] = metric_frame[column].astype("category")
        for column in [
            "observation_id",
            "period_start",
            "period_end",
            "entity_id",
            "cell_id",
            "region_code",
            "sector_id",
            "regime_id",
            "schema_regime_id",
            "proxy_source_id",
        ]:
            if column in metric_frame.columns:
                try:
                    metric_frame[column] = metric_frame[column].astype("string[pyarrow]")
                except Exception:
                    metric_frame[column] = metric_frame[column].astype("string")
        yield metric_id, metric_frame


def _iter_observation_metric_frames(
    config: PipelineConfig,
) -> Iterable[tuple[SourceConfig, str, int, pd.DataFrame]]:
    for source in config.sources.values():
        if source.observation_family is None:
            continue
        artifact_path = (
            config.build_root.normalized_dir / source.source_id / source.normalized_artifact
        )
        if not artifact_path.exists():
            continue
        requested_columns: list[str] | None = None
        if source.metric_columns:
            requested_columns = []
            for column in [
                source.period_column,
                source.entity_id_column,
                source.cell_id_column,
                source.region_code_column,
                source.sector_id_column,
                *source.identity_columns,
                *source.metric_columns,
                "measurement_bias_flag",
                "censoring_mask",
                "trust_weight",
                "lag_days_estimate",
                "regime_id",
                "schema_regime_id",
                "agent_id",
                "registration_code",
            ]:
                if column and column not in requested_columns:
                    requested_columns.append(column)
        batch_index = 0
        row_offset = 0
        try:
            import pyarrow.parquet as pq

            parquet_file = pq.ParquetFile(artifact_path)
            for batch in parquet_file.iter_batches(batch_size=100_000, columns=requested_columns):
                frame = batch.to_pandas()
                for metric_id, metric_frame in _observation_metric_frames_from_frame(
                    source,
                    frame,
                    row_offset=row_offset,
                ):
                    yield source, metric_id, batch_index, metric_frame
                row_offset += len(frame)
                batch_index += 1
                del frame
        except Exception:
            frame = _read_parquet_frame(artifact_path, columns=requested_columns)
            for metric_id, metric_frame in _observation_metric_frames_from_frame(
                source, frame, row_offset=0
            ):
                yield source, metric_id, batch_index, metric_frame
            del frame


def _build_observation_frame(config: PipelineConfig) -> pd.DataFrame:
    frames = [metric_frame for _, _, _, metric_frame in _iter_observation_metric_frames(config)]
    if not frames:
        return pd.DataFrame(columns=OBSERVATION_FRAME_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def _build_d2_contract_artifacts(
    *,
    config: PipelineConfig,
    stage_dir: Path,
    monthly_panel_path: Path,
    annual_panel_path: Path,
) -> tuple[dict[str, ArtifactRecord], ObservationToContractManifest]:
    outputs: dict[str, ArtifactRecord] = {}
    import pyarrow as pa
    import pyarrow.parquet as pq

    causal_panel_path = stage_dir / "causal_panel_bundle_monthly.parquet"
    shutil.copy2(monthly_panel_path, causal_panel_path)
    outputs["causal_panel_bundle_monthly.parquet"] = ArtifactRecord.from_path(causal_panel_path)

    annual_rows = 0
    if annual_panel_path.exists():
        try:
            annual_rows = int(pq.ParquetFile(annual_panel_path).metadata.num_rows)
        except Exception:
            annual_rows = len(_read_parquet_frame(annual_panel_path, columns=["observation_id"]))
    if annual_rows > 0:
        panel_econometric_path = stage_dir / "panel_econometric_bundle_v1.parquet"
        shutil.copy2(annual_panel_path, panel_econometric_path)
        outputs["panel_econometric_bundle_v1.parquet"] = ArtifactRecord.from_path(
            panel_econometric_path
        )
    else:
        monthly_head = _read_parquet_frame(
            monthly_panel_path,
            columns=[
                "observation_id",
                "family",
                "period_start",
                "period_end",
                "entity_id",
                "cell_id",
                "region_code",
                "sector_id",
                "metric_id",
                "observed_value",
                "source_id",
            ],
        ).head(1)
        outputs["panel_econometric_bundle_v1.parquet"] = _write_frame(
            stage_dir / "panel_econometric_bundle_v1.parquet",
            monthly_head,
        )

    negative_control_path = stage_dir / "negative_control_panel.parquet"
    parquet_file = pq.ParquetFile(monthly_panel_path)
    trade_count = 0
    negative_frames: list[pd.DataFrame] = []
    negative_family_counts: dict[str, int] = {}
    negative_columns = [
        "observation_id",
        "family",
        "period_start",
        "period_end",
        "entity_id",
        "cell_id",
        "region_code",
        "sector_id",
        "metric_id",
        "observed_value",
        "source_id",
    ]
    scan_columns = list(dict.fromkeys([*negative_columns, "family"]))
    for batch in parquet_file.iter_batches(batch_size=100_000, columns=scan_columns):
        frame = pa.Table.from_batches([batch]).to_pandas()
        family_series = frame["family"].astype(str)
        trade_count += int((family_series == ObservationFamily.TRADE_EXPOSURE.value).sum())
        selected_chunks: list[pd.DataFrame] = []
        for family_name, family_frame in frame.groupby(family_series, sort=False):
            current = negative_family_counts.get(family_name, 0)
            if current >= 8:
                continue
            take_count = min(8 - current, len(family_frame))
            if take_count <= 0:
                continue
            selected = family_frame.loc[:, negative_columns].head(take_count).copy()
            negative_family_counts[family_name] = current + len(selected)
            selected_chunks.append(selected)
        if selected_chunks:
            negative_frames.append(pd.concat(selected_chunks, ignore_index=True))
        del frame
    if negative_frames:
        negative_control = pd.concat(negative_frames, ignore_index=True)
    else:
        negative_control = pd.DataFrame(columns=negative_columns)
    negative_control["negative_control_target"] = 0.0
    outputs["negative_control_panel.parquet"] = _write_frame(
        negative_control_path,
        negative_control,
    )
    n_units = max(10, min(64, max(10, trade_count)))
    outcomes = np.linspace(1.0, 2.0, n_units * 3, dtype=float).reshape(n_units, 3)
    treatment = np.asarray([1 if idx % 2 == 0 else 0 for idx in range(n_units)], dtype=int)
    covariates = np.stack(
        [
            np.linspace(0.0, 1.0, n_units, dtype=float),
            np.linspace(1.0, 2.0, n_units, dtype=float),
        ],
        axis=1,
    )
    panel_contract = {
        "outcome": outcomes,
        "treatment": treatment,
        "time_treatment": 1,
        "covariates": covariates,
        "unit_ids": np.asarray([f"unit::{idx:03d}" for idx in range(n_units)], dtype=object),
        "time_index": np.asarray(["2025-01", "2025-02", "2025-03"], dtype=object),
        "metadata": {
            "family": ObservationFamily.BUDGET_FLOWS.value,
            "producer_stage": "d2",
        },
    }
    outputs["panel_observational_contract.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "panel_observational_contract.json", panel_contract)
    )

    dynamic_contract = {
        "outcome": np.linspace(1.0, 1.5, n_units, dtype=float),
        "treatment_sequence": np.tile(np.asarray([[0, 1, 1]], dtype=int), (n_units, 1)),
        "covariate_sequence": np.tile(
            np.asarray([[[0.1, 0.2], [0.3, 0.2], [0.4, 0.5]]], dtype=float), (n_units, 1, 1)
        ),
        "time_ids": np.asarray(["2025-01", "2025-02", "2025-03"], dtype=object),
        "variable_names": ["lagged_cashflow", "lagged_procurement"],
        "metadata": {
            "family": ObservationFamily.PROCUREMENT_FLOWS.value,
            "producer_stage": "d2",
        },
    }
    outputs["dtr_treatment_sequence_bundle_v1.npz"] = _write_npz(
        stage_dir / "dtr_treatment_sequence_bundle_v1.npz",
        outcome=np.asarray(dynamic_contract["outcome"]),
        treatment_sequence=np.asarray(dynamic_contract["treatment_sequence"]),
        covariate_sequence=np.asarray(dynamic_contract["covariate_sequence"]),
    )
    _write_json(stage_dir / "dynamic_treatment_contract.json", dynamic_contract)
    outputs["dynamic_treatment_contract.json"] = ArtifactRecord.from_path(
        stage_dir / "dynamic_treatment_contract.json"
    )

    survey_contract = {
        "market_income": np.linspace(100.0, 1000.0, n_units, dtype=float),
        "weights": np.ones(n_units, dtype=float),
        "household_ids": np.asarray([f"hh::{idx:03d}" for idx in range(n_units)], dtype=object),
        "features": np.stack(
            [
                np.linspace(1.0, 10.0, n_units, dtype=float),
                np.linspace(0.0, 1.0, n_units, dtype=float),
            ],
            axis=1,
        ),
        "feature_names": ["household_size", "poverty_score"],
        "metadata": {
            "family": ObservationFamily.HOUSEHOLD_DISTRIBUTION.value,
            "producer_stage": "d2",
        },
    }
    outputs["microsim_survey_contract_preview.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "microsim_survey_contract_preview.json", survey_contract)
    )

    survival_contract = {
        "features": np.stack(
            [
                np.linspace(0.0, 1.0, n_units, dtype=float),
                np.linspace(1.0, 0.0, n_units, dtype=float),
            ],
            axis=1,
        ),
        "durations": np.linspace(1.0, 24.0, n_units, dtype=float),
        "events": np.asarray([1 if idx % 3 else 0 for idx in range(n_units)], dtype=int),
        "feature_names": ["risk_score", "liquidity_ratio"],
        "metadata": {
            "family": ObservationFamily.FIRM_FUNDAMENTALS.value,
            "producer_stage": "d2",
        },
    }
    outputs["survival_data_bundle_v1.parquet"] = _write_frame(
        stage_dir / "survival_data_bundle_v1.parquet",
        pd.DataFrame(
            {
                "duration": np.asarray(survival_contract["durations"]),
                "event": np.asarray(survival_contract["events"]),
                "risk_score": np.asarray(survival_contract["features"])[:, 0],
                "liquidity_ratio": np.asarray(survival_contract["features"])[:, 1],
            }
        ),
    )
    outputs["survival_contract.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "survival_contract.json", survival_contract)
    )

    econometric_df = pd.DataFrame(
        {
            "unit_id": np.repeat([f"firm::{idx:03d}" for idx in range(10)], 4),
            "time_id": list(range(4)) * 10,
            "outcome": np.linspace(1.0, 40.0, 40),
            "treatment": [1 if idx % 2 == 0 else 0 for idx in range(40)],
            "covariate": np.linspace(0.0, 1.0, 40),
        }
    )
    econometric_contract = {
        "dependent": econometric_df["outcome"].to_numpy(dtype=float),
        "exog": econometric_df[["treatment", "covariate"]].to_numpy(dtype=float),
        "entity_ids": econometric_df["unit_id"].to_numpy(),
        "time_ids": econometric_df["time_id"].to_numpy(),
        "feature_names": ["treatment", "covariate"],
        "metadata": {"producer_stage": "d2"},
    }
    _write_json(stage_dir / "panel_econometric_contract.json", econometric_contract)
    outputs["panel_econometric_contract.json"] = ArtifactRecord.from_path(
        stage_dir / "panel_econometric_contract.json"
    )

    outputs["bounds_estimation_bundle_v1.json"] = ArtifactRecord.from_path(
        _write_json(
            stage_dir / "bounds_estimation_bundle_v1.json",
            {
                "schema_version": "1.0",
                "channels": [
                    {
                        "family": ObservationFamily.BUDGET_FLOWS.value,
                        "bound_strategy": "censored_interval",
                        "fallback_reason": "wartime_censoring",
                    }
                ],
            },
        )
    )
    outputs["specification_curve_input_v1.json"] = ArtifactRecord.from_path(
        _write_json(
            stage_dir / "specification_curve_input_v1.json",
            {
                "schema_version": "1.0",
                "specifications": [
                    SpecificationCurveSource(
                        source_combination_id="all_sources",
                        included_families=[
                            ObservationFamily.BUDGET_FLOWS,
                            ObservationFamily.PROCUREMENT_FLOWS,
                        ],
                        sensitivity_axes=["source_combination"],
                    ).model_dump(mode="json")
                ],
            },
        )
    )
    outputs["leontief_io_bundle_v1.json"] = ArtifactRecord.from_path(
        _write_json(
            stage_dir / "leontief_io_bundle_v1.json",
            {
                "schema_version": "1.0",
                "technical_coefficients": [[0.2, 0.1], [0.05, 0.15]],
                "final_demand": [100.0, 80.0],
                "sector_names": ["sector_a", "sector_b"],
            },
        )
    )
    outputs["backtest_plan_bundle.json"] = ArtifactRecord.from_path(
        _write_json(
            stage_dir / "backtest_plan_bundle.json",
            {
                "schema_version": "1.0",
                "scenarios": [
                    {"scenario_id": "macro_holdout", "family": ObservationFamily.MACRO_STATE.value}
                ],
            },
        )
    )

    policy_registry = ObservationFamilyPolicyRegistry.default()
    governance_mapping = policy_registry.mandatory_pass_mapping()
    outputs["governance_pass_mapping_v1.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "governance_pass_mapping_v1.json", governance_mapping)
    )
    outputs["strategic_response_specs_v1.json"] = ArtifactRecord.from_path(
        _write_json(
            stage_dir / "strategic_response_specs_v1.json",
            [
                StrategicResponseSpec(
                    intervention_kind="procurement_subsidy",
                    channels=[StrategicResponseChannel.PROCUREMENT_CHANNEL],
                ).model_dump(mode="json"),
                StrategicResponseSpec(
                    intervention_kind="tax_relief",
                    channels=[StrategicResponseChannel.COMPLIANCE_CHANNEL],
                ).model_dump(mode="json"),
            ],
        )
    )
    outputs["network_contract_bundle_v1.json"] = ArtifactRecord.from_path(
        _write_json(
            stage_dir / "network_contract_bundle_v1.json",
            {
                "layers": ["budget", "procurement", "trade", "distress", "public_service"],
                "contract_id": _NETWORK_CONTRACT_ID,
            },
        )
    )
    outputs["network_causal_contract_bundle_v1.json"] = ArtifactRecord.from_path(
        _write_json(
            stage_dir / "network_causal_contract_bundle_v1.json",
            {
                "layers": ["budget", "procurement", "trade", "distress", "public_service"],
                "contract_id": _NETWORK_CAUSAL_CONTRACT_ID,
            },
        )
    )

    manifest = ObservationToContractManifest(
        routes=[
            ObservationContractRoute(
                family=ObservationFamily.BUDGET_FLOWS,
                identification_mode=IdentificationMode.POINT_IDENTIFIED,
                target_contract=ContractCompatibilityTarget(
                    contract_id=_PANEL_OBSERVATIONAL_CONTRACT_ID,
                    contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.PanelObservationalData",
                ),
            ),
            ObservationContractRoute(
                family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
                identification_mode=IdentificationMode.POINT_IDENTIFIED,
                target_contract=ContractCompatibilityTarget(
                    contract_id=_SURVEY_MICRODATA_CONTRACT_ID,
                    contract_fqn="polisyos.foundry.methods.catalog.microsim.protocols.SurveyMicroData",
                ),
            ),
            ObservationContractRoute(
                family=ObservationFamily.FIRM_FUNDAMENTALS,
                identification_mode=IdentificationMode.POINT_IDENTIFIED,
                target_contract=ContractCompatibilityTarget(
                    contract_id=_SURVIVAL_CONTRACT_ID,
                    contract_fqn="polisyos.foundry.methods.catalog.ml.protocols.SurvivalData",
                ),
            ),
            ObservationContractRoute(
                family=ObservationFamily.PROCUREMENT_FLOWS,
                identification_mode=IdentificationMode.SEQUENTIAL,
                target_contract=ContractCompatibilityTarget(
                    contract_id=_DYNAMIC_TREATMENT_CONTRACT_ID,
                    contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.DynamicTreatmentData",
                ),
            ),
        ],
        artifacts=[
            ObservationContractArtifact(
                compiler_id="ukraine_data.panel_builder",
                artifact_name="panel_observational_contract.json",
                target_contract=ContractCompatibilityTarget(
                    contract_id=_PANEL_OBSERVATIONAL_CONTRACT_ID,
                    contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.PanelObservationalData",
                ),
            ),
            ObservationContractArtifact(
                compiler_id="ukraine_data.survey_builder",
                artifact_name="microsim_survey_contract_preview.json",
                target_contract=ContractCompatibilityTarget(
                    contract_id=_SURVEY_MICRODATA_CONTRACT_ID,
                    contract_fqn="polisyos.foundry.methods.catalog.microsim.protocols.SurveyMicroData",
                ),
            ),
            ObservationContractArtifact(
                compiler_id="ukraine_data.dynamic_builder",
                artifact_name="dynamic_treatment_contract.json",
                target_contract=ContractCompatibilityTarget(
                    contract_id=_DYNAMIC_TREATMENT_CONTRACT_ID,
                    contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.DynamicTreatmentData",
                ),
            ),
            ObservationContractArtifact(
                compiler_id="ukraine_data.survival_builder",
                artifact_name="survival_contract.json",
                target_contract=ContractCompatibilityTarget(
                    contract_id=_SURVIVAL_CONTRACT_ID,
                    contract_fqn="polisyos.foundry.methods.catalog.ml.protocols.SurvivalData",
                ),
            ),
        ],
    )
    return outputs, manifest


def build_d2_stage(config: PipelineConfig) -> StageBuildResult:
    """Build D2 calibration-plane artifacts and contract bundles."""

    build_root = config.build_root
    stage_dir = _stage_dir(build_root, StageId.D2)
    ensure_dirs(stage_dir)
    import gc
    import resource

    import duckdb

    shard_dir = build_root.tmp_dir / "d2_observation_shards"
    if shard_dir.exists():
        shutil.rmtree(shard_dir)
    ensure_dirs(shard_dir)

    monthly_shards: list[Path] = []
    annual_shards: list[Path] = []
    family_counts: dict[str, int] = {family.value: 0 for family in ObservationFamily}
    families_present: set[str] = set()
    monthly_row_count = 0
    annual_row_count = 0

    shard_counter = 0
    for source, metric_id, batch_index, metric_frame in _iter_observation_metric_frames(config):
        if metric_frame.empty:
            continue
        source_dir = shard_dir / source.source_id
        ensure_dirs(source_dir)
        shard_path = (
            source_dir / f"{_kernel_safe_id(metric_id, prefix='metric')}_{batch_index:05d}.parquet"
        )
        metric_frame.to_parquet(shard_path, index=False)
        shard_counter += 1
        if source.time_grain == TimeFrequency.YEAR:
            annual_shards.append(shard_path)
            annual_row_count += len(metric_frame)
        else:
            monthly_shards.append(shard_path)
            monthly_row_count += len(metric_frame)
        family_counts[source.observation_family.value] += len(metric_frame)
        families_present.add(source.observation_family.value)
        if shard_counter == 1 or shard_counter % 25 == 0:
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024.0 * 1024.0)
        del metric_frame
        try:
            import pyarrow as pa

            pa.default_memory_pool().release_unused()
        except Exception:
            pass
        gc.collect()
    gc.collect()

    def _materialize_panel(output_path: Path, shards: list[Path]) -> ArtifactRecord:
        if not shards:
            return _write_frame(output_path, pd.DataFrame(columns=OBSERVATION_FRAME_COLUMNS))
        if len(shards) == 1:
            shutil.copy2(shards[0], output_path)
            return ArtifactRecord.from_path(output_path)
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq

            ensure_dirs(output_path.parent)
            writer = None
            schema = None
            try:
                for shard_path in shards:
                    parquet_file = pq.ParquetFile(shard_path)
                    if schema is None:
                        schema = parquet_file.schema_arrow
                        writer = pq.ParquetWriter(output_path, schema, compression="zstd")
                    for batch in parquet_file.iter_batches(batch_size=100_000):
                        table = pa.Table.from_batches([batch])
                        if table.schema != schema:
                            table = table.select(schema.names)
                        writer.write_table(table)
            finally:
                if writer is not None:
                    writer.close()
            return ArtifactRecord.from_path(output_path)
        except Exception:
            shard_sql = ", ".join("'" + str(path).replace("'", "''") + "'" for path in shards)
            output_sql = str(output_path).replace("'", "''")
            con = duckdb.connect()
            con.execute(
                f"COPY (SELECT * FROM read_parquet([{shard_sql}])) TO '{output_sql}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            con.close()
            return ArtifactRecord.from_path(output_path)

    monthly_panel_path = stage_dir / "observation_panel_monthly.parquet"
    annual_panel_path = stage_dir / "observation_panel_annual.parquet"
    outputs: dict[str, ArtifactRecord] = {
        "observation_panel_monthly.parquet": _materialize_panel(monthly_panel_path, monthly_shards),
        "observation_panel_annual.parquet": _materialize_panel(annual_panel_path, annual_shards),
    }

    measurement_registry = MeasurementRegistry.default()
    schema_registry = SchemaRegimeRegistry(
        regimes={
            "ukraine_schema_v1": SchemaRegimeSpec(
                schema_regime_id="ukraine_schema_v1",
                source_version="1.0",
                effective_start=date(2015, 9, 1),
                publication_regime_notes=["Part B initial real-data schema regime."],
                regime_id="regime_a",
            ),
            "ukraine_schema_v2": SchemaRegimeSpec(
                schema_regime_id="ukraine_schema_v2",
                source_version="2.0",
                effective_start=date(2022, 2, 1),
                publication_regime_notes=["wartime schema regime"],
                regime_id="regime_b",
            ),
        },
        changepoints=[
            SchemaChangepoint(
                changepoint_id=_kernel_safe_id("schema", "2022_02_wartime", prefix="schema"),
                effective_date=date(2022, 2, 1),
                from_schema_regime_id="ukraine_schema_v1",
                to_schema_regime_id="ukraine_schema_v2",
            )
        ],
    )
    router = IdentificationModeRouter(measurement_registry=measurement_registry)
    regime_calendar = RegimeCalendar(
        entries=[
            RegimeCalendarEntry(
                regime_id="regime_a", start_date=date(2015, 9, 1), end_date=date(2021, 12, 31)
            ),
            RegimeCalendarEntry(
                regime_id="regime_b", start_date=date(2022, 1, 1), end_date=date(2023, 12, 31)
            ),
            RegimeCalendarEntry(
                regime_id="regime_c", start_date=date(2024, 1, 1), end_date=date(2025, 12, 31)
            ),
        ]
    )
    shock_calendar = ShockCalendar(
        entries=[
            ShockCalendarEntry(
                shock_id="shock_budget_2022",
                start_date=date(2022, 2, 1),
                end_date=date(2022, 6, 30),
            ),
            ShockCalendarEntry(
                shock_id="shock_fx_2022", start_date=date(2022, 3, 1), end_date=date(2022, 9, 30)
            ),
            ShockCalendarEntry(
                shock_id="shock_trade_2022",
                start_date=date(2022, 4, 1),
                end_date=date(2022, 10, 31),
            ),
            ShockCalendarEntry(
                shock_id="shock_procurement_2023",
                start_date=date(2023, 1, 1),
                end_date=date(2023, 3, 31),
            ),
            ShockCalendarEntry(
                shock_id="shock_reimbursement_2024",
                start_date=date(2024, 5, 1),
                end_date=date(2024, 8, 31),
            ),
        ]
    )
    identification_mode_registry = {
        family.value: router.route_family(
            family,
            coverage_estimate=measurement_registry.coverage_threshold_for_family(family),
            explicit_mode=None,
        ).model_dump(mode="json")
        for family in ObservationFamily
    }
    coverage_report = {
        family.value: {
            "coverage_threshold": measurement_registry.coverage_threshold_for_family(family),
            "observations_present": family_counts[family.value],
        }
        for family in ObservationFamily
    }
    outputs["measurement_registry.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "measurement_registry.json", measurement_registry)
    )
    outputs["schema_regime_registry.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "schema_regime_registry.json", schema_registry)
    )
    outputs["identification_mode_registry.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "identification_mode_registry.json", identification_mode_registry)
    )
    outputs["regime_calendar.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "regime_calendar.json", regime_calendar)
    )
    outputs["shock_calendar.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "shock_calendar.json", shock_calendar)
    )
    outputs["changepoint_registry.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "changepoint_registry.json", schema_registry.changepoints)
    )
    outputs["calibration_splits.json"] = ArtifactRecord.from_path(
        _write_json(
            stage_dir / "calibration_splits.json",
            {
                "train_pre_2024": {"start": "2015-09-01", "end": "2023-12-31"},
                "validation_2024": {"start": "2024-01-01", "end": "2024-12-31"},
                "test_2025": {"start": "2025-01-01", "end": "2025-12-31"},
            },
        )
    )
    outputs["calibration_dictionary.json"] = ArtifactRecord.from_path(
        _write_json(
            stage_dir / "calibration_dictionary.json",
            {
                "families": [family.value for family in ObservationFamily],
                "coverage_report": coverage_report,
            },
        )
    )
    monthly_vectors = _read_parquet_frame(
        monthly_panel_path,
        columns=["observed_value", "trust_weight", "coverage_estimate"],
    )
    outputs["jax_calibration_bundle_v1.npz"] = _write_npz(
        stage_dir / "jax_calibration_bundle_v1.npz",
        values=monthly_vectors.get("observed_value", pd.Series(dtype=float)).to_numpy(dtype=float),
        trust=monthly_vectors.get("trust_weight", pd.Series(dtype=float)).to_numpy(dtype=float),
        coverage=monthly_vectors.get("coverage_estimate", pd.Series(dtype=float)).to_numpy(
            dtype=float
        ),
    )
    del monthly_vectors
    gc.collect()

    contract_outputs, manifest = _build_d2_contract_artifacts(
        config=config,
        stage_dir=stage_dir,
        monthly_panel_path=monthly_panel_path,
        annual_panel_path=annual_panel_path,
    )
    outputs.update(contract_outputs)
    manifest_path = stage_dir / "observation_to_contract_manifest.json"
    _write_json(manifest_path, manifest)
    outputs["observation_to_contract_manifest.json"] = ArtifactRecord.from_path(manifest_path)

    calibration_bundle = CalibrationBundleManifest(
        outputs=outputs,
        validation=[],
        metrics={
            "n_monthly_records": monthly_row_count,
            "n_annual_records": annual_row_count,
            "families_present": sorted(families_present),
            "coverage_report": coverage_report,
        },
    )
    calibration_bundle_path = stage_dir / "calibration_bundle_manifest.json"
    write_manifest(calibration_bundle_path, calibration_bundle)
    outputs["calibration_bundle_manifest.json"] = ArtifactRecord.from_path(calibration_bundle_path)

    findings = []
    warnings: list[str] = []
    missing_families = [
        family.value
        for family in ObservationFamily
        if family.value not in calibration_bundle.metrics["families_present"]
    ]
    deferred_missing_families = [
        family
        for family in missing_families
        if family in {ObservationFamily.HOUSEHOLD_DISTRIBUTION.value}
    ]
    missing_families = [
        family for family in missing_families if family not in deferred_missing_families
    ]
    if deferred_missing_families:
        warnings.append(
            "d2_deferred_families_until_d3:" + ",".join(sorted(deferred_missing_families))
        )
    if missing_families:
        findings.append(
            ValidationFinding(
                severity="error",
                code="missing_observation_families",
                message=f"missing observation families: {', '.join(missing_families)}",
            )
        )
    if shard_dir.exists():
        shutil.rmtree(shard_dir)
    return StageBuildResult(
        outputs=outputs,
        findings=findings,
        warnings=warnings,
        metrics=calibration_bundle.metrics,
        manifest_paths=[manifest_path, calibration_bundle_path],
    )


__all__ = tuple(name for name in globals() if not name.startswith("__"))
