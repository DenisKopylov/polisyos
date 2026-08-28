"""Release-bundle and intervention payload builders for Ukraine."""

from __future__ import annotations

import shutil

from polisyos.data_forge.domains.ukraine.manifests import (
    D5ReleaseContentRef,
    D5ReleaseHandoffRequest,
    D5ReleaseProducerFacts,
    ReleaseManifest,
    write_manifest,
)
from polisyos.data_forge.domains.ukraine.resources import directory_size_bytes

from .common import *


def _build_embedding_matrix(frame: pd.DataFrame, n_components: int) -> np.ndarray:
    numeric = frame.select_dtypes(include=["number"]).fillna(0.0)
    if numeric.empty:
        base = np.ones((max(1, len(frame)), 1), dtype=float)
    else:
        base = numeric.to_numpy(dtype=float)
    centered = base - base.mean(axis=0, keepdims=True)
    u, s, _ = np.linalg.svd(centered, full_matrices=False)
    embedding = u[:, : min(n_components, u.shape[1])] * s[: min(n_components, len(s))]
    if embedding.shape[1] < n_components:
        padding = np.zeros((embedding.shape[0], n_components - embedding.shape[1]), dtype=float)
        embedding = np.concatenate([embedding, padding], axis=1)
    return embedding


def _load_npz_artifact(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with np.load(path, allow_pickle=True) as loaded:
        return {key: loaded[key] for key in loaded.files}


def _stable_bucket_id(value: str, *, bucket_count: int = 64) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"bucket::{int(digest[:12], 16) % bucket_count:03d}"


def _bundle_content_records(bundle_dir: Path) -> dict[str, ArtifactRecord]:
    records: dict[str, ArtifactRecord] = {}
    for item in sorted(bundle_dir.iterdir(), key=lambda path: path.name):
        if not item.is_file():
            continue
        records[item.name] = ArtifactRecord.from_path(item)
    return records


def _safe_first(values: pd.Series, default: str) -> str:
    cleaned = values.dropna().astype(str).str.strip()
    cleaned = cleaned.loc[cleaned != ""]
    if cleaned.empty:
        return default
    return str(cleaned.iloc[0])


def _build_agent_embeddings(
    runtime_agents: pd.DataFrame,
    *,
    graph_layers: dict[str, dict[str, Any]],
) -> tuple[np.ndarray, pd.DataFrame]:
    frame = _ensure_agent_numeric_columns(runtime_agents)
    if "agent_id" not in frame.columns:
        frame["agent_id"] = [f"agent::{idx:08d}" for idx in range(len(frame))]
    for layer_name, arrays in graph_layers.items():
        degree_map = _edge_weight_by_node(arrays) if arrays else {}
        frame[f"{layer_name}_degree"] = (
            frame["agent_id"].astype(str).map(degree_map).fillna(0.0).astype(float)
        )
    if "cell_id" in frame.columns:
        cell_sizes = frame.groupby("cell_id")["agent_id"].transform("count").astype(float)
        frame["cell_population_proxy"] = cell_sizes
    else:
        frame["cell_population_proxy"] = 1.0
    embedding = _build_embedding_matrix(frame, 32)
    return embedding, frame


def _build_cell_embeddings(
    cell_registry: pd.DataFrame,
    *,
    calibrated_households: pd.DataFrame | None = None,
) -> tuple[np.ndarray, pd.DataFrame]:
    frame = cell_registry.copy()
    if "region_numeric" not in frame.columns:
        region_codes = _coerce_string_series(frame, "region_code", fill="0")
        region_map = {value: index for index, value in enumerate(sorted(region_codes.unique()))}
        frame["region_numeric"] = region_codes.map(region_map).astype(float)
    if "sector_numeric" not in frame.columns:
        sector_codes = _coerce_string_series(frame, "sector_id", fill="unknown")
        sector_map = {value: index for index, value in enumerate(sorted(sector_codes.unique()))}
        frame["sector_numeric"] = sector_codes.map(sector_map).astype(float)
    if (
        calibrated_households is not None
        and not calibrated_households.empty
        and "cell_id" in calibrated_households.columns
    ):
        household_features = calibrated_households.copy()
        household_features = household_features.groupby("cell_id", as_index=False).mean(
            numeric_only=True
        )
        frame = frame.merge(household_features, on="cell_id", how="left", suffixes=("", "_hh"))
    for column in frame.columns:
        if column == "cell_id":
            continue
        if frame[column].dtype == object:
            continue
        frame[column] = _sanitize_numeric_series(frame[column], fill=0.0)
    embedding = _build_embedding_matrix(frame, 16)
    return embedding, frame


def _build_graph_compression_bundle(
    runtime_agents: pd.DataFrame,
    *,
    graph_layers: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if "agent_id" not in runtime_agents.columns:
        runtime_agents = runtime_agents.copy()
        runtime_agents["agent_id"] = [f"agent::{idx:08d}" for idx in range(len(runtime_agents))]
    if "cell_id" in runtime_agents.columns:
        group_map = {
            str(agent_id): str(cell_id)
            for agent_id, cell_id in runtime_agents[["agent_id", "cell_id"]].itertuples(index=False)
            if str(cell_id).strip()
        }
    else:
        group_map = {}

    layer_payloads: list[dict[str, Any]] = []
    degree_preservation_scores: list[float] = []
    weight_errors: list[float] = []
    overlap_scores: list[float] = []
    for layer_name, arrays in graph_layers.items():
        if not arrays:
            continue
        src_ids = np.asarray(
            arrays.get("src_ids", np.asarray([], dtype=object)), dtype=object
        ).astype(str)
        dst_ids = np.asarray(
            arrays.get("dst_ids", np.asarray([], dtype=object)), dtype=object
        ).astype(str)
        weights = np.asarray(arrays.get("weight", np.asarray([], dtype=float)), dtype=float)
        if len(src_ids) == 0:
            continue
        grouped = pd.DataFrame(
            {
                "src_group": [group_map.get(src, _stable_bucket_id(src)) for src in src_ids],
                "dst_group": [group_map.get(dst, _stable_bucket_id(dst)) for dst in dst_ids],
                "weight": weights,
            }
        )
        compressed = grouped.groupby(["src_group", "dst_group"], as_index=False)["weight"].sum()
        original_group_degree = (
            (
                grouped.groupby("src_group")["weight"].sum().abs()
                + grouped.groupby("dst_group")["weight"].sum().abs()
            )
            .groupby(level=0)
            .sum()
        )
        compressed_group_degree = (
            (
                compressed.groupby("src_group")["weight"].sum().abs()
                + compressed.groupby("dst_group")["weight"].sum().abs()
            )
            .groupby(level=0)
            .sum()
        )
        all_groups = sorted(
            set(original_group_degree.index).union(set(compressed_group_degree.index))
        )
        original_vector = np.asarray(
            [float(original_group_degree.get(group, 0.0)) for group in all_groups], dtype=float
        )
        compressed_vector = np.asarray(
            [float(compressed_group_degree.get(group, 0.0)) for group in all_groups], dtype=float
        )
        total_degree = max(float(np.abs(original_vector).sum()), 1e-9)
        degree_preservation = max(
            0.0,
            1.0 - float(np.abs(original_vector - compressed_vector).sum() / total_degree),
        )
        total_original_weight = max(float(np.abs(weights).sum()), 1e-9)
        total_compressed_weight = float(np.abs(compressed["weight"].to_numpy(dtype=float)).sum())
        weight_error = float(
            abs(total_original_weight - total_compressed_weight) / total_original_weight
        )
        top_original = set(
            grouped.groupby("src_group")["weight"]
            .sum()
            .abs()
            .sort_values(ascending=False)
            .head(10)
            .index.tolist()
        )
        top_compressed = set(
            compressed.groupby("src_group")["weight"]
            .sum()
            .abs()
            .sort_values(ascending=False)
            .head(10)
            .index.tolist()
        )
        neighborhood_overlap = (
            float(len(top_original & top_compressed) / max(len(top_original | top_compressed), 1))
            if top_original or top_compressed
            else 1.0
        )
        degree_preservation_scores.append(degree_preservation)
        weight_errors.append(weight_error)
        overlap_scores.append(neighborhood_overlap)
        layer_payloads.append(
            {
                "layer_id": layer_name,
                "coarsening_strategy": "cell_aware_sparse_coarsening",
                "n_original_edges": len(weights),
                "n_compressed_edges": len(compressed),
                "n_supernodes": len(all_groups),
                "degree_preservation_score": degree_preservation,
                "edge_weight_reconstruction_error": weight_error,
                "neighborhood_overlap_stability": neighborhood_overlap,
            }
        )
    aggregate_degree = (
        float(np.mean(degree_preservation_scores)) if degree_preservation_scores else 1.0
    )
    aggregate_weight_error = float(np.mean(weight_errors)) if weight_errors else 0.0
    aggregate_overlap = float(np.mean(overlap_scores)) if overlap_scores else 1.0
    return {
        "schema_version": "1.0",
        "method": "deterministic_spectral_factor_with_cell_coarsening",
        "layers": layer_payloads,
        "fidelity_metrics": {
            "degree_preservation_score": aggregate_degree,
            "edge_weight_reconstruction_error": aggregate_weight_error,
            "neighborhood_overlap_stability": aggregate_overlap,
            "downstream_policy_response_stability": {
                "status": "not_established",
                "reason": "requires the absent D5 downstream bridge and consumer",
            },
        },
    }


def _build_d5_release_handoff_request(
    *,
    cell_registry: pd.DataFrame,
    graph_compression_bundle: dict[str, Any],
    content_refs: dict[str, ArtifactRecord],
    release_root: Path,
) -> D5ReleaseHandoffRequest:
    """Build the strict, non-authoritative D5 producer handoff contract."""

    return D5ReleaseHandoffRequest(
        declared_release_root=str(release_root),
        producer_facts=D5ReleaseProducerFacts(
            primary_region_id=_safe_first(
                cell_registry.get("region_code", pd.Series(dtype=str)), "00"
            ),
            primary_sector_id=_safe_first(
                cell_registry.get("sector_id", pd.Series(dtype=str)), "unknown"
            ),
            graph_compression_degree_preservation_score=graph_compression_bundle[
                "fidelity_metrics"
            ]["degree_preservation_score"],
            graph_compression_edge_weight_reconstruction_error=graph_compression_bundle[
                "fidelity_metrics"
            ]["edge_weight_reconstruction_error"],
        ),
        content_refs={
            name: D5ReleaseContentRef.from_artifact_record(record)
            for name, record in sorted(content_refs.items())
        },
    )


def build_d5_stage(config: PipelineConfig) -> StageBuildResult:
    """Build D5 producer artifacts and a neutral downstream handoff request."""

    build_root = config.build_root
    stage_dir = _stage_dir(build_root, StageId.D5)
    ensure_dirs(stage_dir)
    runtime_stage = _stage_dir(build_root, StageId.D0_P0)
    d1_stage = _stage_dir(build_root, StageId.D1)
    calibration_stage = _stage_dir(build_root, StageId.D2)
    d3_stage = _stage_dir(build_root, StageId.D3)
    d4_stage = _stage_dir(build_root, StageId.D4)
    runtime_agents = pd.read_parquet(runtime_stage / "agent_registry_runtime.parquet")
    cell_registry = pd.read_parquet(runtime_stage / "cell_registry_region_sector.parquet")
    calibrated_household_cells = None
    calibrated_household_cells_path = d3_stage / "calibrated_household_cells.parquet"
    if calibrated_household_cells_path.exists():
        calibrated_household_cells = pd.read_parquet(calibrated_household_cells_path)
    graph_layers = {
        "budget": _load_npz_artifact(runtime_stage / "budget_graph_sparse.npz"),
        "procurement": _load_npz_artifact(runtime_stage / "procurement_graph_sparse.npz"),
        "trade": _load_npz_artifact(d1_stage / "trade_graph_sparse.npz"),
        "distress": _load_npz_artifact(d1_stage / "distress_graph_sparse.npz"),
        "public_service": _load_npz_artifact(d1_stage / "public_service_graph_sparse.npz"),
    }

    outputs: dict[str, ArtifactRecord] = {}
    agent_embedding, enriched_agent_frame = _build_agent_embeddings(
        runtime_agents,
        graph_layers=graph_layers,
    )
    outputs["agent_embedding_32d.npz"] = _write_npz(
        stage_dir / "agent_embedding_32d.npz",
        agent_id=enriched_agent_frame.get(
            "agent_id",
            pd.Series([f"agent::{idx:08d}" for idx in range(len(enriched_agent_frame))]),
        ).to_numpy(dtype=object),
        embedding=agent_embedding,
    )
    cell_embedding, enriched_cell_frame = _build_cell_embeddings(
        cell_registry,
        calibrated_households=calibrated_household_cells,
    )
    outputs["cell_prototype_embeddings.npz"] = _write_npz(
        stage_dir / "cell_prototype_embeddings.npz",
        cell_id=enriched_cell_frame["cell_id"].to_numpy(dtype=object),
        embedding=cell_embedding,
    )
    graph_compression_bundle = _build_graph_compression_bundle(
        runtime_agents,
        graph_layers=graph_layers,
    )
    outputs["graph_compression_bundle.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "graph_compression_bundle.json", graph_compression_bundle)
    )
    handoff_content_refs = {
        "cell_registry": ArtifactRecord.from_path(
            runtime_stage / "cell_registry_region_sector.parquet"
        ),
        "d4_governance_request": ArtifactRecord.from_path(
            d4_stage / "d4_governance_request.json"
        ),
        "graph_compression_bundle": outputs["graph_compression_bundle.json"],
    }
    handoff_request = _build_d5_release_handoff_request(
        cell_registry=cell_registry,
        graph_compression_bundle=graph_compression_bundle,
        content_refs=handoff_content_refs,
        release_root=stage_dir,
    )
    outputs["d5_release_handoff_request.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "d5_release_handoff_request.json", handoff_request)
    )

    release_dirs = {
        "runtime_bundle_v1": stage_dir / "runtime_bundle_v1",
        "calibration_bundle_v1": stage_dir / "calibration_bundle_v1",
        "method_contract_bundle_v1": stage_dir / "method_contract_bundle_v1",
        "embedding_bundle_v1": stage_dir / "embedding_bundle_v1",
    }
    for directory in release_dirs.values():
        ensure_dirs(directory)

    copy_plan = {
        "runtime_bundle_v1": [
            runtime_stage / "runtime_bundle_manifest.json",
            runtime_stage / "slot_family_manifest.json",
            runtime_stage / "agent_registry_runtime.parquet",
            runtime_stage / "cell_registry_region_sector.parquet",
            runtime_stage / "geo_index_runtime.parquet",
        ],
        "calibration_bundle_v1": [
            calibration_stage / "calibration_bundle_manifest.json",
            calibration_stage / "observation_panel_monthly.parquet",
            calibration_stage / "observation_panel_annual.parquet",
        ],
        "method_contract_bundle_v1": [
            calibration_stage / "observation_to_contract_manifest.json",
            calibration_stage / "network_contract_bundle_v1.json",
            calibration_stage / "network_causal_contract_bundle_v1.json",
            calibration_stage / "bounds_estimation_bundle_v1.json",
            calibration_stage / "backtest_plan_bundle.json",
        ],
        "embedding_bundle_v1": [
            stage_dir / "agent_embedding_32d.npz",
            stage_dir / "cell_prototype_embeddings.npz",
            stage_dir / "graph_compression_bundle.json",
        ],
    }
    for bundle_name, sources in copy_plan.items():
        for source_path in sources:
            if source_path.exists():
                shutil.copy2(source_path, release_dirs[bundle_name] / source_path.name)

    bundle_records = {
        bundle_name: ArtifactRecord(path=str(path), size_bytes=directory_size_bytes(path))
        for bundle_name, path in release_dirs.items()
    }
    bundle_contents = {
        bundle_name: _bundle_content_records(path) for bundle_name, path in release_dirs.items()
    }
    release_manifest = ReleaseManifest(
        bundles=bundle_records,
        bundle_contents=bundle_contents,
        evidence_refs={
            **handoff_content_refs,
            "d5_release_handoff_request": outputs["d5_release_handoff_request.json"],
        },
        metrics={
            "runtime_bundle_size_gib": _directory_file_size_gib(release_dirs["runtime_bundle_v1"]),
            "calibration_bundle_size_gib": _directory_file_size_gib(
                release_dirs["calibration_bundle_v1"]
            ),
            "contract_bundle_size_gib": _directory_file_size_gib(
                release_dirs["method_contract_bundle_v1"]
            ),
            "compression_degree_preservation_score": graph_compression_bundle["fidelity_metrics"][
                "degree_preservation_score"
            ],
            "compression_edge_weight_reconstruction_error": graph_compression_bundle[
                "fidelity_metrics"
            ]["edge_weight_reconstruction_error"],
            "compression_neighborhood_overlap_stability": graph_compression_bundle[
                "fidelity_metrics"
            ]["neighborhood_overlap_stability"],
        },
        validation=[],
        lineage={
            "authority_purpose": "producer_bundle_inventory",
            "capability_state": "bridge_missing",
            "consumer_state": "consumer_missing",
            "may_not_use_for": [
                "legal_intervention_compilation",
                "governance_admissibility",
                "release_acceptance",
                "publication",
            ],
            "runtime_manifest": str(runtime_stage / "runtime_bundle_manifest.json"),
            "calibration_manifest": str(calibration_stage / "calibration_bundle_manifest.json"),
            "d4_governance_request": str(d4_stage / "d4_governance_request.json"),
        },
    )
    release_manifest_path = stage_dir / "release_manifest_v1.json"
    findings: list[ValidationFinding] = [
        ValidationFinding(
            severity="warning",
            code="downstream_release_authority_not_established",
            message=(
                "D5 produced a bundle inventory only; Lex compilation, Foundry acceptance, "
                "and publication remain unavailable until a downstream bridge consumes the handoff."
            ),
        )
    ]
    if float(graph_compression_bundle["fidelity_metrics"]["degree_preservation_score"]) < 0.85:
        findings.append(
            ValidationFinding(
                severity="error",
                code="compression_degree_preservation_below_threshold",
                message="graph compression degree preservation fell below the minimum release threshold",
            )
        )
    if (
        float(graph_compression_bundle["fidelity_metrics"]["edge_weight_reconstruction_error"])
        > 0.15
    ):
        findings.append(
            ValidationFinding(
                severity="error",
                code="compression_edge_weight_error_above_threshold",
                message="graph compression edge-weight reconstruction error exceeds the release threshold",
            )
        )
    release_manifest = release_manifest.model_copy(
        update={
            "validation": findings,
        }
    )
    write_manifest(release_manifest_path, release_manifest)
    outputs["release_manifest_v1.json"] = ArtifactRecord.from_path(release_manifest_path)
    for bundle_name, record in bundle_records.items():
        outputs[f"{bundle_name}/"] = record

    if float(release_manifest.metrics["runtime_bundle_size_gib"]) >= 25.0:
        findings.append(
            ValidationFinding(
                severity="warning",
                code="runtime_bundle_size_budget_exceeded",
                message="runtime bundle size exceeds 25 GiB target budget",
            )
        )
    return StageBuildResult(
        outputs=outputs,
        findings=findings,
        metrics=release_manifest.metrics,
        manifest_paths=[release_manifest_path],
    )


__all__ = tuple(name for name in globals() if not name.startswith("__"))
