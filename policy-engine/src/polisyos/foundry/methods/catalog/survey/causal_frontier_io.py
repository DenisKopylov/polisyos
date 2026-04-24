"""I/O helpers for causal-frontier small-area estimation bundles."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from polisyos.foundry.methods.catalog.survey.protocols import SAEResult

type Path = Any
_Path = __import__("pathlib", fromlist=("Path",)).Path

_REQUIRED_AREA_COLUMNS = ("area_id", "direct_estimate", "direct_variance")
_REQUIRED_EDGE_COLUMNS = ("src_area_id", "dst_area_id")
_RESERVED_AREA_COLUMNS = {
    "area_id",
    "direct_estimate",
    "direct_variance",
    "sample_size",
    "regime_id",
    "policy_indicator",
}


def load_causal_frontier_bundle(
    bundle_dir: str | Path,
    *,
    covariate_columns: list[str] | None = None,
    add_intercept: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the Phase 2 causal-frontier bundle contract from one directory."""
    bundle_path = _Path(bundle_dir).expanduser().resolve()
    if not bundle_path.exists():
        raise FileNotFoundError(f"bundle_dir does not exist: {bundle_path}")
    if not bundle_path.is_dir():
        raise ValueError(f"bundle_dir must be a directory: {bundle_path}")

    areas_path = bundle_path / "areas.parquet"
    edges_path = bundle_path / "edges.parquet"
    exposure_path = bundle_path / "exposure.parquet"
    metadata_path = bundle_path / "metadata.json"

    if not areas_path.exists():
        raise FileNotFoundError(f"missing bundle file: {areas_path}")
    if not edges_path.exists():
        raise FileNotFoundError(f"missing bundle file: {edges_path}")

    areas = pd.read_parquet(areas_path)
    edges = pd.read_parquet(edges_path)
    exposure = pd.read_parquet(exposure_path) if exposure_path.exists() else None
    metadata = (
        json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    )
    if not isinstance(metadata, dict):
        raise ValueError("metadata.json must contain a JSON object")

    state, resolved_metadata = build_causal_frontier_state_from_frames(
        areas=areas,
        edges=edges,
        exposure=exposure,
        metadata=metadata,
        covariate_columns=covariate_columns,
        add_intercept=add_intercept,
    )
    resolved_metadata["bundle_dir"] = str(bundle_path)
    resolved_metadata["bundle_contract_files"] = {
        "areas": str(areas_path),
        "edges": str(edges_path),
        "exposure": str(exposure_path) if exposure_path.exists() else None,
        "metadata": str(metadata_path) if metadata_path.exists() else None,
    }
    return state, resolved_metadata


def build_causal_frontier_state_from_records(
    *,
    areas: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    exposure: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    covariate_columns: list[str] | None = None,
    add_intercept: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Materialize estimator inputs from inline DTO-style records."""
    areas_frame = pd.DataFrame(_expand_area_records(areas))
    edges_frame = pd.DataFrame(edges)
    exposure_frame = None if exposure is None else pd.DataFrame(exposure)
    return build_causal_frontier_state_from_frames(
        areas=areas_frame,
        edges=edges_frame,
        exposure=exposure_frame,
        metadata=metadata or {},
        covariate_columns=covariate_columns,
        add_intercept=add_intercept,
    )


def build_causal_frontier_state_from_frames(
    *,
    areas: pd.DataFrame,
    edges: pd.DataFrame,
    exposure: pd.DataFrame | None,
    metadata: dict[str, Any],
    covariate_columns: list[str] | None,
    add_intercept: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Normalize tabular bundle inputs into one estimator state payload."""
    areas_frame = areas.copy()
    edges_frame = edges.copy()

    _require_columns(areas_frame, _REQUIRED_AREA_COLUMNS, label="areas")
    _require_columns(edges_frame, _REQUIRED_EDGE_COLUMNS, label="edges")

    areas_frame["area_id"] = areas_frame["area_id"].astype(str)
    if areas_frame["area_id"].duplicated().any():
        raise ValueError("areas.area_id must be unique")

    if "policy_indicator" not in areas_frame.columns:
        areas_frame["policy_indicator"] = 0.0
    areas_frame["policy_indicator"] = pd.to_numeric(
        areas_frame["policy_indicator"], errors="coerce"
    ).fillna(0.0)
    areas_frame["direct_estimate"] = pd.to_numeric(
        areas_frame["direct_estimate"],
        errors="coerce",
    )
    areas_frame["direct_variance"] = pd.to_numeric(
        areas_frame["direct_variance"],
        errors="coerce",
    )
    if not np.all(np.isfinite(areas_frame["direct_estimate"].to_numpy(dtype=float))):
        raise ValueError("areas.direct_estimate must be finite")
    if not np.all(np.isfinite(areas_frame["direct_variance"].to_numpy(dtype=float))):
        raise ValueError("areas.direct_variance must be finite")
    if np.any(areas_frame["direct_variance"].to_numpy(dtype=float) <= 0.0):
        raise ValueError("areas.direct_variance must be strictly positive")

    area_ids = areas_frame["area_id"].tolist()
    area_lookup = {area_id: idx for idx, area_id in enumerate(area_ids)}
    covariates_used = _resolve_covariate_columns(
        areas_frame,
        covariate_columns=covariate_columns,
        add_intercept=add_intercept,
    )
    design_columns: list[np.ndarray] = []
    if add_intercept:
        design_columns.append(np.ones(len(area_ids), dtype=float))
    for column in covariates_used:
        if column == "intercept":
            continue
        design_columns.append(
            pd.to_numeric(areas_frame[column], errors="coerce").to_numpy(dtype=float)
        )
    if not design_columns:
        raise ValueError("causal-frontier SAE requires at least one covariate column or intercept")
    x_covariates = np.column_stack(design_columns)
    if not np.all(np.isfinite(x_covariates)):
        raise ValueError("covariate columns must be finite numeric values")

    weights = np.zeros((len(area_ids), len(area_ids)), dtype=float)
    frontier_edges: list[tuple[str, str, bool]] = []
    edges_frame["src_area_id"] = edges_frame["src_area_id"].astype(str)
    edges_frame["dst_area_id"] = edges_frame["dst_area_id"].astype(str)
    if "weight" not in edges_frame.columns:
        edges_frame["weight"] = 1.0
    if "frontier_flag" not in edges_frame.columns:
        edges_frame["frontier_flag"] = False

    for edge in edges_frame.to_dict(orient="records"):
        src = str(edge["src_area_id"])
        dst = str(edge["dst_area_id"])
        if src not in area_lookup or dst not in area_lookup:
            raise ValueError(f"edge references unknown area ids: {(src, dst)!r}")
        src_idx = area_lookup[src]
        dst_idx = area_lookup[dst]
        if src_idx == dst_idx:
            continue
        weight = float(edge.get("weight", 1.0))
        if not np.isfinite(weight) or weight < 0.0:
            raise ValueError("edges.weight must be finite and non-negative")
        weights[src_idx, dst_idx] = max(weights[src_idx, dst_idx], weight)
        weights[dst_idx, src_idx] = max(weights[dst_idx, src_idx], weight)
        frontier_edges.append((src, dst, bool(edge.get("frontier_flag", False))))

    spillover_exposure = None
    exposure_versions: list[str] = []
    if exposure is not None and not exposure.empty:
        if "area_id" not in exposure.columns:
            raise ValueError("exposure.area_id column is required when exposure.parquet is present")
        if "spillover_exposure" in exposure.columns:
            exposure_frame = exposure.copy()
            exposure_frame["area_id"] = exposure_frame["area_id"].astype(str)
            spillover_map = {
                str(row["area_id"]): float(row["spillover_exposure"])
                for row in exposure_frame.to_dict(orient="records")
                if row.get("spillover_exposure") is not None
            }
            spillover_exposure = np.asarray(
                [float(spillover_map.get(area_id, 0.0)) for area_id in area_ids],
                dtype=float,
            )
            if not np.all(np.isfinite(spillover_exposure)):
                raise ValueError("exposure.spillover_exposure must be finite")
        if "exposure_mapping_version" in exposure.columns:
            exposure_versions = sorted(
                {
                    str(value)
                    for value in exposure["exposure_mapping_version"].dropna().astype(str).tolist()
                }
            )

    frontier_sources = sorted(
        {
            str(value)
            for value in edges_frame.get("frontier_source", pd.Series(dtype=object))
            .dropna()
            .astype(str)
            .tolist()
        }
    )
    frontier_types = sorted(
        {
            str(value)
            for value in edges_frame.get("frontier_type", pd.Series(dtype=object))
            .dropna()
            .astype(str)
            .tolist()
        }
    )
    adjacency_types = sorted(
        {
            str(value)
            for value in edges_frame.get("adjacency_type", pd.Series(dtype=object))
            .dropna()
            .astype(str)
            .tolist()
        }
    )
    state = {
        "area_ids": area_ids,
        "y_direct": areas_frame["direct_estimate"].to_numpy(dtype=float),
        "sampling_var": areas_frame["direct_variance"].to_numpy(dtype=float),
        "policy_indicator": areas_frame["policy_indicator"].to_numpy(dtype=float),
        "X": x_covariates,
        "graph": {
            "graph_id": str(metadata.get("graph_id", "causal_frontier_bundle_graph")),
            "family": str(metadata.get("graph_family", "CAR")),
            "W": weights.tolist(),
            "metadata": {
                "adjacency_types": adjacency_types,
            },
        },
        "frontier_edges": frontier_edges,
    }
    if spillover_exposure is not None:
        state["spillover_exposure"] = spillover_exposure

    resolved_metadata = dict(metadata)
    resolved_metadata["covariate_columns_used"] = covariates_used
    resolved_metadata["adjacency_types"] = adjacency_types
    resolved_metadata["frontier_sources"] = frontier_sources
    resolved_metadata["frontier_types"] = frontier_types
    resolved_metadata["exposure_mapping_versions"] = exposure_versions
    resolved_metadata["n_areas"] = len(area_ids)
    resolved_metadata["spillover_term_included"] = spillover_exposure is not None
    resolved_metadata["frontier_semantics"] = metadata.get("frontier_semantics")
    return state, resolved_metadata


def result_to_estimates_frame(result: SAEResult) -> pd.DataFrame:
    """Convert one `SAEResult` into the output `sae_estimates.parquet` contract."""
    statistics = result.statistics
    estimates = list(map(float, statistics.get("estimates", [])))
    theta_sd = list(map(float, statistics.get("theta_sd", [])))
    mse = list(map(float, statistics.get("mse", [])))
    component_ids = list(map(int, statistics.get("component_ids", [])))
    borrow_strength_neighbors = list(map(int, statistics.get("borrow_strength_neighbors", [])))
    area_ids = statistics.get("area_ids") or [f"area_{idx}" for idx in range(len(estimates))]
    return pd.DataFrame(
        {
            "area_id": [str(value) for value in area_ids],
            "theta_mean": estimates,
            "theta_sd": theta_sd,
            "mse": mse,
            "component_id": component_ids,
            "borrow_strength_neighbors": borrow_strength_neighbors,
        }
    )


def write_output_bundle(
    output_dir: str | Path,
    *,
    estimates: pd.DataFrame,
    diagnostics: dict[str, Any],
    governance_artifact: dict[str, Any],
) -> dict[str, str]:
    """Persist output bundle files following the Phase 2 contract layout."""
    output_path = _Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    estimates_path = output_path / "sae_estimates.parquet"
    diagnostics_path = output_path / "causal_diagnostics.json"
    governance_path = output_path / "governance_artifact.json"

    estimates.to_parquet(estimates_path, index=False)
    diagnostics_path.write_text(
        json.dumps(diagnostics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    governance_path.write_text(
        json.dumps(governance_artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "sae_estimates": str(estimates_path),
        "causal_diagnostics": str(diagnostics_path),
        "governance_artifact": str(governance_path),
    }


def _expand_area_records(areas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for area in areas:
        row = dict(area)
        covariates = row.pop("covariates", {}) or {}
        if not isinstance(covariates, dict):
            raise ValueError("area covariates must be a JSON object")
        for key, value in covariates.items():
            row[str(key)] = value
        rows.append(row)
    return rows


def _resolve_covariate_columns(
    areas: pd.DataFrame,
    *,
    covariate_columns: list[str] | None,
    add_intercept: bool,
) -> list[str]:
    if covariate_columns is not None:
        missing = [column for column in covariate_columns if column not in areas.columns]
        if missing:
            raise ValueError(f"unknown covariate columns: {missing}")
        resolved = list(covariate_columns)
    else:
        resolved = [
            column
            for column in areas.columns
            if column not in _RESERVED_AREA_COLUMNS and pd.api.types.is_numeric_dtype(areas[column])
        ]
    if add_intercept:
        return ["intercept", *resolved]
    return resolved


def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...], *, label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


__all__ = [
    "build_causal_frontier_state_from_frames",
    "build_causal_frontier_state_from_records",
    "load_causal_frontier_bundle",
    "result_to_estimates_frame",
    "write_output_bundle",
]
