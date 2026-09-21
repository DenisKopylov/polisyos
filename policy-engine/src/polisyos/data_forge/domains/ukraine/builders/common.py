"""Stage builders for the Ukraine Part B production data pipeline.

The builders in this module intentionally focus on reproducible artifact
assembly, manifests, and contract validation. They are designed to run against
real server-side source snapshots, while remaining lightweight enough for local
unit tests that exercise helper logic only.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from polisyos.data_forge.domains.ukraine.adapters import _UKRAINE_OBLAST_CODE_MAP
from polisyos.ir.model_layer import types as _model_layer_types

from . import observation as _observation
from .contracts import StageBuildResult as _StageBuildResult

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


StageBuildResult = _StageBuildResult
TimeFrequency = _model_layer_types.TimeFrequency
MONTHLY_END_MONTH = _observation.MONTHLY_END_MONTH
OBSERVATION_FRAME_COLUMNS = _observation.OBSERVATION_FRAME_COLUMNS
_period_to_dates = _observation._period_to_dates


def _clip_value(value: float, *, lower: float, upper: float) -> float:
    return float(min(max(value, lower), upper))


@dataclass(frozen=True)
class ScheduledTask:
    """One heavyweight task scheduled under a memory budget."""

    task_id: str
    memory_gib_hint: float
    run: Callable[[], dict[str, Any]]


class MemoryAwareScheduler:
    """Budget-aware task scheduler for CPX62-oriented workloads.

    The implementation is intentionally conservative: tasks are executed in a
    deterministic order and only when their memory hint fits the configured
    ceiling. The scheduler still provides the accounting hooks that a later
    concurrent executor can reuse without changing stage builder interfaces.
    """

    def __init__(self, *, max_workers: int, memory_budget_gib: float) -> None:
        self.max_workers = max(1, int(max_workers))
        self.memory_budget_gib = max(0.1, float(memory_budget_gib))

    def run(self, tasks: Sequence[ScheduledTask]) -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}
        for task in tasks:
            if task.memory_gib_hint > self.memory_budget_gib:
                raise ValueError(
                    f"task {task.task_id!r} requests {task.memory_gib_hint:.2f} GiB "
                    f"but scheduler budget is {self.memory_budget_gib:.2f} GiB"
                )
            results[task.task_id] = task.run()
        return results


def _stable_cell_id(region_code: object, sector_id: object) -> str:
    return f"cell::{str(region_code).strip()}::{str(sector_id).strip()}"


def _safe_numeric_series(frame: pd.DataFrame, column: str, *, fill: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series([fill] * len(frame), index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(fill)


def _coerce_string_series(frame: pd.DataFrame, column: str, *, fill: str = "") -> pd.Series:
    if column not in frame.columns:
        return pd.Series([fill] * len(frame), index=frame.index, dtype="string")
    return frame[column].fillna(fill).astype("string")


def _compact_locator_value(value: object, *, max_length: int, prefix: str) -> str | None:
    text = str(value).strip()
    if not text:
        return None
    if len(text) <= max_length:
        return text
    compact = _kernel_safe_id(text, prefix=prefix)
    if len(compact) <= max_length:
        return compact
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:24]
    fallback = f"{prefix}.{digest}"
    return fallback[:max_length]


def _kernel_safe_id(*parts: object, prefix: str = "id") -> str:
    cleaned_parts: list[str] = []
    for part in parts:
        text = str(part).strip().lower()
        if not text:
            continue
        text = re.sub(r"[^a-z0-9_.-]+", "-", text)
        text = re.sub(r"[_.-]{2,}", "-", text)
        text = text.strip("._-")
        if text:
            cleaned_parts.append(text)
    identifier = ".".join(cleaned_parts)
    if not identifier:
        return prefix
    if not identifier[0].isalpha():
        return f"{prefix}.{identifier}"
    return identifier


def _normalize_region_code_value(value: object) -> str:
    raw_text = str(value or "").strip()
    text = raw_text.lower().replace("область", "").replace('"', "")
    text = " ".join(text.split())
    if any(char.isalpha() for char in raw_text):
        direct = _UKRAINE_OBLAST_CODE_MAP.get(text)
        if direct is not None:
            return direct
        for key, code in _UKRAINE_OBLAST_CODE_MAP.items():
            if key in text:
                return code
            stem = key.replace("м. ", "").rstrip()
            if len(stem) > 4 and stem[:-2] in text:
                return code
    digits = "".join(ch for ch in raw_text if ch.isdigit())
    if len(digits) >= 2:
        return digits[:2]
    if len(digits) == 1:
        return digits.zfill(2)
    return "00"


def _regime_for_period_id(period_id: object) -> tuple[str, str]:
    text = str(period_id or "").strip()
    try:
        year = int(text[:4])
    except Exception:
        return "regime_c", "ukraine_schema_v2"
    if year <= 2021:
        return "regime_a", "ukraine_schema_v1"
    if year <= 2023:
        return "regime_b", "ukraine_schema_v2"
    return "regime_c", "ukraine_schema_v2"


def _collect_graph_node_ids(
    *,
    base_node_ids: Sequence[str] | None = None,
    edge_frames: Sequence[tuple[pd.DataFrame, str, str]] = (),
) -> list[str]:
    node_ids: set[str] = set()
    for node_id in base_node_ids or ():
        text = str(node_id).strip()
        if text:
            node_ids.add(text)
    for frame, source_col, target_col in edge_frames:
        for column in (source_col, target_col):
            if column not in frame.columns:
                continue
            for value in _coerce_string_series(frame, column):
                text = str(value).strip()
                if text:
                    node_ids.add(text)
    return sorted(node_ids)


def _graph_arrays_from_edges(
    frame: pd.DataFrame,
    *,
    src_col: str,
    dst_col: str,
    weight_col: str,
    period_col: str = "period_id",
    node_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    if period_col not in frame.columns:
        frame = frame.copy()
        frame[period_col] = pd.Series(pd.NA, index=frame.index, dtype="string")
    period_start, period_end = _observation._period_series_to_iso_bounds(
        frame[period_col],
        time_grain=TimeFrequency.MONTH,
    )
    valid_period_mask = period_start.notna() & period_end.notna()
    edges = (
        frame.loc[valid_period_mask, [src_col, dst_col, weight_col, period_col]]
        .dropna(subset=[src_col, dst_col])
        .copy()
    )
    edges[src_col] = edges[src_col].astype(str)
    edges[dst_col] = edges[dst_col].astype(str)
    edges[weight_col] = pd.to_numeric(edges[weight_col], errors="coerce").fillna(0.0)
    if node_ids is None:
        node_ids = sorted(set(edges[src_col]).union(set(edges[dst_col])))
    index_map = {node_id: index for index, node_id in enumerate(node_ids)}
    src_index = edges[src_col].map(index_map).to_numpy(dtype=int)
    dst_index = edges[dst_col].map(index_map).to_numpy(dtype=int)
    return {
        "node_ids": np.asarray(list(node_ids), dtype=object),
        "src_ids": edges[src_col].to_numpy(dtype=object),
        "dst_ids": edges[dst_col].to_numpy(dtype=object),
        "src_index": src_index,
        "dst_index": dst_index,
        "weight": edges[weight_col].to_numpy(dtype=float),
        "period_id": edges[period_col].astype(str).to_numpy(dtype=object),
    }


def _adjacency_from_edge_arrays(arrays: dict[str, Any]) -> np.ndarray:
    node_ids = np.asarray(arrays["node_ids"], dtype=object)
    adjacency = np.zeros((len(node_ids), len(node_ids)), dtype=float)
    src_index = np.asarray(arrays["src_index"], dtype=int)
    dst_index = np.asarray(arrays["dst_index"], dtype=int)
    weight = np.asarray(arrays["weight"], dtype=float)
    for src, dst, w in zip(src_index, dst_index, weight, strict=False):
        adjacency[src, dst] += float(w)
    return adjacency


def _edge_weight_by_node(arrays: dict[str, Any]) -> dict[str, float]:
    node_ids = np.asarray(arrays["node_ids"], dtype=object)
    if len(node_ids) == 0:
        return {}
    src_index = np.asarray(arrays["src_index"], dtype=int)
    dst_index = np.asarray(arrays["dst_index"], dtype=int)
    weight = np.abs(np.asarray(arrays["weight"], dtype=float))
    src_degree = np.bincount(src_index, weights=weight, minlength=len(node_ids))
    dst_degree = np.bincount(dst_index, weights=weight, minlength=len(node_ids))
    degree = src_degree + dst_degree
    return {
        str(node_id): float(score)
        for node_id, score in zip(node_ids.tolist(), degree.tolist(), strict=False)
        if float(score) > 0.0
    }


def _select_contract_graph_node_ids(
    array_layers: Sequence[dict[str, Any]],
    *,
    max_nodes: int,
) -> list[str]:
    score_by_node: dict[str, float] = {}
    for arrays in array_layers:
        for node_id, score in _edge_weight_by_node(arrays).items():
            score_by_node[node_id] = score_by_node.get(node_id, 0.0) + float(score)
    ranked = sorted(score_by_node.items(), key=lambda item: (-item[1], item[0]))
    selected = [node_id for node_id, _ in ranked[:max_nodes]]
    if len(selected) >= 2:
        return selected

    for arrays in array_layers:
        for node_id in np.asarray(arrays["node_ids"], dtype=object).tolist():
            text = str(node_id)
            if text in selected:
                continue
            selected.append(text)
            if len(selected) >= 2:
                return selected
    return selected


def _reindex_edge_arrays_to_node_subset(
    arrays: dict[str, Any],
    *,
    node_ids: Sequence[str],
) -> dict[str, Any]:
    selected = [str(node_id) for node_id in node_ids]
    set(selected)
    src_ids = np.asarray(arrays["src_ids"], dtype=object).astype(str)
    dst_ids = np.asarray(arrays["dst_ids"], dtype=object).astype(str)
    weight = np.asarray(arrays["weight"], dtype=float)
    period_id = np.asarray(arrays["period_id"], dtype=object)
    mask = np.isin(src_ids, selected) & np.isin(dst_ids, selected)
    index_map = {node_id: index for index, node_id in enumerate(selected)}
    filtered_src_ids = src_ids[mask]
    filtered_dst_ids = dst_ids[mask]
    return {
        "node_ids": np.asarray(selected, dtype=object),
        "src_ids": filtered_src_ids.astype(object),
        "dst_ids": filtered_dst_ids.astype(object),
        "src_index": np.asarray([index_map[node_id] for node_id in filtered_src_ids], dtype=int),
        "dst_index": np.asarray([index_map[node_id] for node_id in filtered_dst_ids], dtype=int),
        "weight": weight[mask],
        "period_id": period_id[mask],
    }


def _node_features_from_agent_registry(
    agent_registry: pd.DataFrame,
    *,
    node_ids: Sequence[str],
) -> tuple[np.ndarray, np.ndarray]:
    frame = agent_registry.copy()
    if "agent_id" not in frame.columns:
        frame["agent_id"] = [f"agent::{idx:08d}" for idx in range(len(frame))]
    frame = frame.drop_duplicates("agent_id").set_index("agent_id")
    revenue = pd.to_numeric(frame.get("revenue", 0.0), errors="coerce").fillna(0.0)
    employees = pd.to_numeric(frame.get("employees", 0.0), errors="coerce").fillna(0.0)
    assets = pd.to_numeric(frame.get("assets", 0.0), errors="coerce").fillna(0.0)
    region = pd.to_numeric(frame.get("region_numeric", 0.0), errors="coerce").fillna(0.0)
    features = []
    states = []
    for node_id in node_ids:
        if node_id in frame.index:
            features.append(
                [
                    float(revenue.get(node_id, 0.0)),
                    float(employees.get(node_id, 0.0)),
                    float(assets.get(node_id, 0.0)),
                    float(region.get(node_id, 0.0)),
                ]
            )
            states.append(float(revenue.get(node_id, 0.0)))
        else:
            features.append([0.0, 0.0, 0.0, 0.0])
            states.append(0.0)
    return np.asarray(features, dtype=float), np.asarray(states, dtype=float)


def _ensure_agent_numeric_columns(agent_registry: pd.DataFrame) -> pd.DataFrame:
    frame = agent_registry.copy()
    if "region_numeric" not in frame.columns:
        region_codes = _coerce_string_series(frame, "region_code", fill="0")
        mapping = {value: index for index, value in enumerate(sorted(region_codes.unique()))}
        frame["region_numeric"] = region_codes.map(mapping).astype(float)
    for column in ("revenue", "assets", "liabilities", "employees"):
        if column not in frame.columns:
            frame[column] = 0.0
        frame[column] = _sanitize_numeric_series(frame[column], fill=0.0, lower=0.0)
    return frame


def _sanitize_numeric_series(
    values: pd.Series | Sequence[Any],
    *,
    fill: float,
    lower: float | None = None,
    upper: float | None = None,
) -> pd.Series:
    base = values if isinstance(values, pd.Series) else pd.Series(values)
    series = pd.to_numeric(base, errors="coerce")
    series = series.replace([np.inf, -np.inf], np.nan).fillna(fill).astype(float)
    if lower is not None:
        series = series.clip(lower=lower)
    if upper is not None:
        series = series.clip(upper=upper)
    return series

_IO_COMPAT_NAMES = frozenset({
    "_cas_put_json",
    "_directory_file_size_gib",
    "_json_default",
    "_load_optional_source_frame",
    "_load_source_frame",
    "_manifest_path",
    "_read_parquet_frame",
    "_select_procurement_frame",
    "_stage_dir",
    "_stream_parquet_numeric_column_stats",
    "_write_frame",
    "_write_json",
    "_write_npz",
    "_write_protocol_json",
})
_BINDINGS_COMPAT_NAMES = frozenset({
    "_augment_lookup_with_identity_bridge",
    "_build_edr_identity_bridge",
    "_build_synthetic_multiscale_payload",
    "_build_unique_name_lookup",
    "_extract_unresolved_identity_rows",
    "_filter_identity_bridge_inputs",
    "_int_env",
    "_link_participants",
    "_normalize_identity_key",
    "_normalize_name_key",
    "_participant_resolution_coverage",
    "_resolve_agent_id",
    "_resolve_agent_lookup",
    "_validation_subset",
})


def __getattr__(name: str) -> Any:
    """Resolve moved private helpers for legacy internal imports."""
    if name in _IO_COMPAT_NAMES:
        from . import io as _io

        return getattr(_io, name)
    if name in _BINDINGS_COMPAT_NAMES:
        from . import bindings_validation as _bindings_validation

        return getattr(_bindings_validation, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = (
    "MONTHLY_END_MONTH",
    "OBSERVATION_FRAME_COLUMNS",
    "MemoryAwareScheduler",
    "ScheduledTask",
    "StageBuildResult",
)
