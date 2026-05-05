"""Stage builders for the Ukraine Part B production data pipeline.

The builders in this module intentionally focus on reproducible artifact
assembly, manifests, and contract validation. They are designed to run against
real server-side source snapshots, while remaining lightweight enough for local
unit tests that exercise helper logic only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from pydantic import BaseModel

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.data_forge.domains.ukraine.adapters import _UKRAINE_OBLAST_CODE_MAP
from polisyos.data_forge.domains.ukraine.manifests import (
    ArtifactRecord,
    ValidationFinding,
)
from polisyos.data_forge.domains.ukraine.models import (
    BuildRootConfig,
    PipelineConfig,
    StageId,
)
from polisyos.data_forge.kernel.io import ensure_dirs
from polisyos.ir.observation.contracts import (
    ObservationFamily,
)
from polisyos.ir.types import TimeFrequency

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


def _clip_value(value: float, *, lower: float, upper: float) -> float:
    return float(min(max(value, lower), upper))


MONTHLY_END_MONTH = {
    1: 31,
    2: 28,
    3: 31,
    4: 30,
    5: 31,
    6: 30,
    7: 31,
    8: 31,
    9: 30,
    10: 31,
    11: 30,
    12: 31,
}

OBSERVATION_FRAME_COLUMNS = [
    "observation_id",
    "family",
    "time_grain",
    "period_start",
    "period_end",
    "entity_scope",
    "entity_id",
    "cell_id",
    "region_code",
    "sector_id",
    "metric_id",
    "observed_value",
    "unit",
    "coverage_estimate",
    "measurement_bias_flag",
    "censoring_mask",
    "trust_weight",
    "lag_days_estimate",
    "source_id",
    "source_version",
    "regime_id",
    "shock_mask",
    "schema_regime_id",
    "identification_mode",
    "source_confidence_tier",
    "proxy_source_id",
]


@dataclass(frozen=True)
class ScheduledTask:
    """One heavyweight task scheduled under a memory budget."""

    task_id: str
    memory_gib_hint: float
    run: Callable[[], dict[str, Any]]


@dataclass
class StageBuildResult:
    """Structured stage output returned to the orchestrator."""

    outputs: dict[str, ArtifactRecord] = field(default_factory=dict)
    findings: list[ValidationFinding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    manifest_paths: list[Path] = field(default_factory=list)


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


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return str(value)


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    path.write_text(
        json.dumps(serialized, ensure_ascii=True, indent=2, sort_keys=True, default=_json_default),
        encoding="utf-8",
    )
    return path


def _write_protocol_json(path: Path, payload: BaseModel) -> ArtifactRecord:
    _write_json(path, payload)
    return ArtifactRecord.from_path(path)


def _write_frame(path: Path, frame: pd.DataFrame) -> ArtifactRecord:
    ensure_dirs(path.parent)
    frame.to_parquet(path, index=False)
    return ArtifactRecord.from_path(path, row_count=len(frame))


def _write_npz(path: Path, **arrays: Any) -> ArtifactRecord:
    ensure_dirs(path.parent)
    np.savez_compressed(path, **arrays)
    nnz = None
    if "weight" in arrays:
        weight = np.asarray(arrays["weight"])
        nnz = int(np.count_nonzero(weight))
    elif "adjacency" in arrays:
        adjacency = np.asarray(arrays["adjacency"])
        nnz = int(np.count_nonzero(adjacency))
    return ArtifactRecord.from_path(path, nnz=nnz)


def _manifest_path(build_root: BuildRootConfig, name: str) -> Path:
    return build_root.manifests_dir / name


def _stage_dir(build_root: BuildRootConfig, stage_id: StageId) -> Path:
    if stage_id in {StageId.D0_P0, StageId.D1}:
        return build_root.runtime_dir / stage_id.value
    if stage_id in {StageId.D2, StageId.D3, StageId.D4}:
        return build_root.calibration_dir / stage_id.value
    return build_root.bundles_dir / stage_id.value


def _read_parquet_frame(path: Path, *, columns: Sequence[str] | None = None) -> pd.DataFrame:
    if not columns:
        return pd.read_parquet(path)
    try:
        import pyarrow.parquet as pq

        available = set(pq.ParquetFile(path).schema.names)
    except Exception:
        available = set()
    selected = [column for column in columns if not available or column in available]
    if not selected:
        return pd.read_parquet(path)
    return pd.read_parquet(path, columns=selected)


def _stream_parquet_numeric_column_stats(
    path: Path,
    column: str,
    *,
    head_limit: int = 256,
) -> tuple[float, np.ndarray]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        parquet_file = pq.ParquetFile(path)
        available = set(parquet_file.schema.names)
        if column not in available:
            return 0.0, np.asarray([], dtype=float)

        head_values: list[float] = []
        abs_sum = 0.0
        value_count = 0
        for batch in parquet_file.iter_batches(batch_size=100_000, columns=[column]):
            frame = pa.Table.from_batches([batch]).to_pandas()
            if column not in frame.columns:
                continue
            series = pd.to_numeric(frame[column], errors="coerce").dropna()
            if series.empty:
                continue
            if len(head_values) < head_limit:
                remaining = head_limit - len(head_values)
                head_values.extend(series.head(remaining).tolist())
            abs_sum += float(series.abs().sum())
            value_count += int(series.shape[0])
            del frame
        mean_abs = abs_sum / value_count if value_count else 0.0
        return mean_abs, np.asarray(head_values, dtype=float)
    except Exception:
        frame = _read_parquet_frame(path, columns=[column])
        if column not in frame.columns or frame.empty:
            return 0.0, np.asarray([], dtype=float)
        series = pd.to_numeric(frame[column], errors="coerce").dropna()
        mean_abs = float(series.abs().mean()) if not series.empty else 0.0
        return mean_abs, np.asarray(series.head(head_limit), dtype=float)


def _directory_file_size_gib(path: Path) -> float:
    total_bytes = sum(item.stat().st_size for item in path.iterdir() if item.is_file())
    return total_bytes / (1024**3)


def _load_source_frame(
    config: PipelineConfig,
    source_id: str,
    *,
    columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    source = config.sources[source_id]
    path = config.build_root.normalized_dir / source_id / source.normalized_artifact
    if not path.exists():
        raise FileNotFoundError(f"missing normalized artifact for {source_id}: {path}")
    return _read_parquet_frame(path, columns=columns)


def _load_optional_source_frame(
    config: PipelineConfig,
    source_id: str,
    *,
    columns: Sequence[str] | None = None,
) -> pd.DataFrame | None:
    source = config.sources.get(source_id)
    if source is None:
        return None
    path = config.build_root.normalized_dir / source_id / source.normalized_artifact
    if not path.exists():
        return None
    return _read_parquet_frame(path, columns=columns)


def _select_procurement_frame(
    config: PipelineConfig,
    *,
    columns: Sequence[str] | None = None,
) -> tuple[pd.DataFrame, str, list[str]]:
    warnings: list[str] = []
    spending_proxy = _load_optional_source_frame(
        config,
        "spending_contracts_procurement_proxy",
        columns=columns,
    )
    if spending_proxy is not None and not spending_proxy.empty:
        warnings.append("procurement_source_selected:spending_contracts_procurement_proxy")
        return spending_proxy, "spending_contracts_procurement_proxy", warnings
    if spending_proxy is not None and spending_proxy.empty:
        warnings.append("procurement_source_empty:spending_contracts_procurement_proxy")
    warnings.append("procurement_source_selected:prozorro_full")
    return _load_source_frame(config, "prozorro_full", columns=columns), "prozorro_full", warnings


def _period_to_dates(period_value: object, time_grain: TimeFrequency) -> tuple[date, date]:
    text = str(period_value).strip()
    normalized = text.upper()
    year = 2025
    month = 1
    quarter_from_text: int | None = None

    if re.match(r"^\d{4}$", normalized):
        year = int(normalized[:4])
    elif match := re.match(r"^(\d{4})[-_/]?Q([1-4])$", normalized):
        year = int(match.group(1))
        quarter_from_text = int(match.group(2))
        month = (quarter_from_text - 1) * 3 + 1
    elif (
        (match := re.match(r"^(\d{4})[-_/]?M(\d{1,2})$", normalized))
        or (match := re.match(r"^(\d{4})-(\d{2})-(\d{2})$", normalized))
        or (match := re.match(r"^(\d{4})[-_/]?(\d{2})$", normalized))
    ):
        year = int(match.group(1))
        month = int(match.group(2))
    month = max(1, min(12, month))

    if time_grain == TimeFrequency.YEAR:
        start = date(year, 1, 1)
        return start, date(year, 12, 31)
    if time_grain == TimeFrequency.QUARTER:
        quarter = quarter_from_text or max(1, min(4, ((month - 1) // 3) + 1))
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2
        return date(year, start_month, 1), date(year, end_month, MONTHLY_END_MONTH[end_month])
    start = date(year, month, 1)
    return start, date(year, month, MONTHLY_END_MONTH[month])


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


def _normalize_identity_key(value: object) -> str:
    text = str(value).strip().lower()
    return "".join(ch for ch in text if ch.isalnum())


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


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, value)


def _resolve_agent_lookup(agent_registry: pd.DataFrame) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for key in ("agent_id", "registration_code", "tax_id", "edrpou"):
        if key not in agent_registry.columns or "agent_id" not in agent_registry.columns:
            continue
        subset = agent_registry[[key, "agent_id"]].dropna()
        for raw_key, agent_id in subset.itertuples(index=False):
            normalized = _normalize_identity_key(raw_key)
            if not normalized:
                continue
            value = str(agent_id)
            lookup[normalized] = value
            if normalized.isdigit():
                if len(normalized) <= 8:
                    lookup.setdefault(normalized.zfill(8), value)
                if len(normalized) <= 10:
                    lookup.setdefault(normalized.zfill(10), value)
    return lookup


def _resolve_agent_id(value: object, lookup: dict[str, str]) -> str | None:
    text = str(value).strip()
    if not text:
        return None
    direct = lookup.get(_normalize_identity_key(text))
    if direct:
        return direct
    normalized = _normalize_identity_key(text)
    if normalized.isdigit():
        for width in (8, 10):
            direct = lookup.get(normalized.zfill(width))
            if direct:
                return direct
    if text.startswith("agent::"):
        return text
    return None


def _normalize_name_key(value: object) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    replacements = {
        "ТОВАРИСТВО З ОБМЕЖЕНОЮ ВІДПОВІДАЛЬНІСТЮ": "ТОВ",
        "ПРИВАТНЕ ПІДПРИЄМСТВО": "ПП",
        "ФІЗИЧНА ОСОБА ПІДПРИЄМЕЦЬ": "ФОП",
        "ФІЗИЧНА ОСОБА-ПІДПРИЄМЕЦЬ": "ФОП",
        "КОМУНАЛЬНЕ НЕКОМЕРЦІЙНЕ ПІДПРИЄМСТВО": "КНП",
        "КОМУНАЛЬНЕ ПІДПРИЄМСТВО": "КП",
        "ДЕРЖАВНЕ ПІДПРИЄМСТВО": "ДП",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = re.sub(r"[\"'`«»“”„]+", " ", text)
    text = re.sub(r"[^0-9A-ZА-ЯІЇЄҐ ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _build_unique_name_lookup(
    agent_registry: pd.DataFrame,
    *,
    allowed_name_keys: set[str] | None = None,
) -> dict[str, dict[str, str]]:
    if "name" not in agent_registry.columns or "agent_id" not in agent_registry.columns:
        return {}
    frame = agent_registry[["agent_id", "registration_code", "region_code", "name"]].copy()
    frame["name_key"] = frame["name"].map(_normalize_name_key)
    frame = frame.dropna(subset=["name_key", "agent_id"])
    if allowed_name_keys is not None:
        normalized_keys = {str(item).strip() for item in allowed_name_keys if str(item).strip()}
        if not normalized_keys:
            return {}
        frame = frame[frame["name_key"].astype("string").isin(normalized_keys)]
    if frame.empty:
        return {}
    lookup: dict[str, dict[str, str]] = {}
    for name_key, group in frame.groupby("name_key", sort=False):
        unique_agents = group["agent_id"].astype(str).dropna().unique().tolist()
        if len(unique_agents) != 1:
            continue
        row = group.iloc[0]
        lookup[str(name_key)] = {
            "agent_id": str(unique_agents[0]),
            "registration_code": str(row.get("registration_code") or "").strip(),
            "region_code": str(row.get("region_code") or "").strip(),
            "name": str(row.get("name") or "").strip(),
        }
    return lookup


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


def _extract_unresolved_identity_rows(
    frame: pd.DataFrame,
    *,
    raw_column: str,
    resolved_column: str,
    family: ObservationFamily,
    source_id: str,
    weight_column: str | None = None,
    name_column: str | None = None,
    region_column: str | None = None,
    period_column: str = "period_id",
) -> pd.DataFrame:
    if raw_column not in frame.columns:
        return pd.DataFrame(
            columns=[
                "raw_registration_code",
                "normalized_raw_registration_code",
                "source_family",
                "source_id",
                "counterparty_name",
                "counterparty_name_key",
                "region_code",
                "period_id",
                "amount_weight",
                "observation_count",
            ]
        )

    raw_series = _coerce_string_series(frame, raw_column)
    resolved_series = _coerce_string_series(frame, resolved_column)
    period_series = (
        _coerce_string_series(frame, period_column, fill="")
        if period_column in frame.columns
        else pd.Series([""] * len(frame))
    )
    weight_series = (
        pd.to_numeric(frame[weight_column], errors="coerce").fillna(1.0)
        if weight_column and weight_column in frame.columns
        else pd.Series([1.0] * len(frame), index=frame.index, dtype=float)
    )
    name_series = (
        _coerce_string_series(frame, name_column, fill="")
        if name_column and name_column in frame.columns
        else pd.Series([""] * len(frame), index=frame.index, dtype="string")
    )
    region_series = (
        _coerce_string_series(frame, region_column, fill="")
        if region_column and region_column in frame.columns
        else pd.Series([""] * len(frame), index=frame.index, dtype="string")
    )

    rows: list[dict[str, Any]] = []
    for raw_value, resolved_value, period_id, weight, counterparty_name, region_code in zip(
        raw_series,
        resolved_series,
        period_series,
        weight_series,
        name_series,
        region_series,
        strict=False,
    ):
        normalized = _normalize_identity_key(raw_value)
        if not normalized or str(resolved_value).strip():
            continue
        rows.append(
            {
                "raw_registration_code": str(raw_value).strip(),
                "normalized_raw_registration_code": normalized,
                "source_family": family.value,
                "source_id": source_id,
                "counterparty_name": str(counterparty_name).strip() or None,
                "counterparty_name_key": _normalize_name_key(counterparty_name),
                "region_code": str(region_code).strip() or None,
                "period_id": str(period_id).strip() or None,
                "amount_weight": float(max(float(weight), 0.0)),
                "observation_count": 1,
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "raw_registration_code",
                "normalized_raw_registration_code",
                "source_family",
                "source_id",
                "counterparty_name",
                "counterparty_name_key",
                "region_code",
                "period_id",
                "amount_weight",
                "observation_count",
            ]
        )
    unresolved = pd.DataFrame.from_records(rows)
    return unresolved.groupby(
        [
            "raw_registration_code",
            "normalized_raw_registration_code",
            "source_family",
            "source_id",
            "counterparty_name",
            "counterparty_name_key",
            "region_code",
            "period_id",
        ],
        dropna=False,
        as_index=False,
    ).agg(amount_weight=("amount_weight", "sum"), observation_count=("observation_count", "sum"))


def _build_identity_bridge_seed_lookup(build_root: BuildRootConfig) -> pd.DataFrame:
    seed_path = build_root.manifests_dir / "edr_identity_bridge_seed.parquet"
    if not seed_path.exists():
        return pd.DataFrame(
            columns=[
                "normalized_raw_registration_code",
                "agent_id",
                "match_method",
                "match_confidence",
            ]
        )
    frame = _read_parquet_frame(seed_path)
    if frame.empty:
        return frame
    raw_column = (
        "raw_registration_code"
        if "raw_registration_code" in frame.columns
        else "normalized_raw_registration_code"
    )
    frame["normalized_raw_registration_code"] = frame[raw_column].map(_normalize_identity_key)
    frame = frame.dropna(subset=["normalized_raw_registration_code", "agent_id"]).copy()
    if "match_method" not in frame.columns:
        frame["match_method"] = "manual_seed"
    if "match_confidence" not in frame.columns:
        frame["match_confidence"] = 1.0
    return frame[
        [
            "normalized_raw_registration_code",
            "agent_id",
            "match_method",
            "match_confidence",
        ]
    ].drop_duplicates()


def _filter_identity_bridge_inputs(
    unresolved_rows: pd.DataFrame,
    seed_frame: pd.DataFrame,
) -> pd.DataFrame:
    if unresolved_rows.empty:
        return unresolved_rows.copy()
    filtered = unresolved_rows.copy()
    name_keys = (
        filtered.get("counterparty_name_key", pd.Series(dtype="string"))
        .fillna("")
        .astype("string")
        .str.strip()
    )
    has_name = name_keys.ne("")
    if seed_frame.empty:
        return filtered.loc[has_name].copy()
    seeded_codes = set(seed_frame["normalized_raw_registration_code"].astype("string"))
    normalized_codes = (
        filtered.get("normalized_raw_registration_code", pd.Series(dtype="string"))
        .fillna("")
        .astype("string")
        .str.strip()
    )
    has_seed = normalized_codes.isin(seeded_codes)
    return filtered.loc[has_name | has_seed].copy()


def _build_edr_identity_bridge(
    *,
    build_root: BuildRootConfig,
    agent_registry: pd.DataFrame,
    unresolved_rows: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    seed_frame = _build_identity_bridge_seed_lookup(build_root)
    unresolved_frame = _filter_identity_bridge_inputs(unresolved_rows, seed_frame)
    requested_name_keys = {
        str(value).strip()
        for value in unresolved_frame.get("counterparty_name_key", pd.Series(dtype="string"))
        .fillna("")
        .astype("string")
        .tolist()
        if str(value).strip()
    }
    unique_name_lookup = _build_unique_name_lookup(
        agent_registry,
        allowed_name_keys=requested_name_keys,
    )

    candidate_rows: list[dict[str, Any]] = []
    for row in unresolved_frame.itertuples(index=False):
        normalized_code = str(getattr(row, "normalized_raw_registration_code", "") or "").strip()
        if not normalized_code:
            continue
        name_key = str(getattr(row, "counterparty_name_key", "") or "").strip()
        region_code = str(getattr(row, "region_code", "") or "").strip()
        weight = float(getattr(row, "amount_weight", 0.0) or 0.0)
        observations = int(getattr(row, "observation_count", 0) or 0)
        if name_key and name_key in unique_name_lookup:
            candidate = unique_name_lookup[name_key]
            candidate_region = str(candidate.get("region_code") or "").strip()
            region_match = (
                not region_code or not candidate_region or region_code == candidate_region
            )
            confidence = 0.93 if region_match else 0.72
            candidate_rows.append(
                {
                    "normalized_raw_registration_code": normalized_code,
                    "candidate_agent_id": candidate["agent_id"],
                    "candidate_registration_code": candidate.get("registration_code") or None,
                    "candidate_name": candidate.get("name") or None,
                    "match_method": "edr_unique_name_exact",
                    "match_confidence": confidence,
                    "amount_weight": weight,
                    "observation_count": observations,
                    "source_family": row.source_family,
                    "source_id": row.source_id,
                    "region_match": region_match,
                }
            )

    if not seed_frame.empty:
        for row in seed_frame.itertuples(index=False):
            candidate_rows.append(
                {
                    "normalized_raw_registration_code": str(row.normalized_raw_registration_code),
                    "candidate_agent_id": str(row.agent_id),
                    "candidate_registration_code": None,
                    "candidate_name": None,
                    "match_method": str(row.match_method),
                    "match_confidence": float(row.match_confidence),
                    "amount_weight": 0.0,
                    "observation_count": 0,
                    "source_family": "manual",
                    "source_id": "edr_identity_bridge_seed",
                    "region_match": True,
                }
            )

    candidate_frame = pd.DataFrame.from_records(candidate_rows)
    if candidate_frame.empty:
        candidate_frame = pd.DataFrame(
            columns=[
                "normalized_raw_registration_code",
                "candidate_agent_id",
                "candidate_registration_code",
                "candidate_name",
                "match_method",
                "match_confidence",
                "amount_weight",
                "observation_count",
                "source_family",
                "source_id",
                "region_match",
            ]
        )
    else:
        candidate_frame = candidate_frame.groupby(
            [
                "normalized_raw_registration_code",
                "candidate_agent_id",
                "candidate_registration_code",
                "candidate_name",
                "match_method",
                "match_confidence",
                "region_match",
            ],
            dropna=False,
            as_index=False,
        ).agg(
            amount_weight=("amount_weight", "sum"),
            observation_count=("observation_count", "sum"),
            source_family=(
                "source_family",
                lambda values: ",".join(sorted({str(item) for item in values if str(item)})),
            ),
            source_id=(
                "source_id",
                lambda values: ",".join(sorted({str(item) for item in values if str(item)})),
            ),
        )

    resolved_rows: list[dict[str, Any]] = []
    if not candidate_frame.empty:
        for normalized_code, group in candidate_frame.groupby(
            "normalized_raw_registration_code", sort=False
        ):
            unique_candidates = group["candidate_agent_id"].astype(str).dropna().unique().tolist()
            best = group.sort_values(
                ["match_confidence", "amount_weight", "observation_count"],
                ascending=[False, False, False],
            ).iloc[0]
            if len(unique_candidates) == 1 and float(best["match_confidence"]) >= 0.90:
                resolved_rows.append(
                    {
                        "normalized_raw_registration_code": normalized_code,
                        "agent_id": str(best["candidate_agent_id"]),
                        "match_method": str(best["match_method"]),
                        "match_confidence": float(best["match_confidence"]),
                        "candidate_registration_code": best.get("candidate_registration_code"),
                        "candidate_name": best.get("candidate_name"),
                        "amount_weight": float(best["amount_weight"]),
                        "observation_count": int(best["observation_count"]),
                    }
                )
    resolved_frame = pd.DataFrame.from_records(resolved_rows)
    if resolved_frame.empty:
        resolved_frame = pd.DataFrame(
            columns=[
                "normalized_raw_registration_code",
                "agent_id",
                "match_method",
                "match_confidence",
                "candidate_registration_code",
                "candidate_name",
                "amount_weight",
                "observation_count",
            ]
        )

    manifest = {
        "schema_version": "1.0",
        "manual_seed_applied": not seed_frame.empty,
        "unresolved_identity_rows": len(unresolved_frame),
        "unresolved_unique_numeric_ids": int(
            unresolved_frame["normalized_raw_registration_code"].astype(str).nunique()
            if not unresolved_frame.empty
            else 0
        ),
        "candidate_matches": len(candidate_frame),
        "resolved_matches": len(resolved_frame),
        "resolution_methods": (
            candidate_frame.get("match_method", pd.Series(dtype=str))
            .astype(str)
            .value_counts()
            .to_dict()
            if not candidate_frame.empty
            else {}
        ),
    }
    return unresolved_frame, candidate_frame, resolved_frame, manifest


def _augment_lookup_with_identity_bridge(
    lookup: dict[str, str],
    bridge_resolved: pd.DataFrame,
) -> dict[str, str]:
    augmented = dict(lookup)
    if bridge_resolved.empty:
        return augmented
    for row in bridge_resolved.itertuples(index=False):
        normalized = _normalize_identity_key(getattr(row, "normalized_raw_registration_code", None))
        agent_id = str(getattr(row, "agent_id", "") or "").strip()
        if normalized and agent_id:
            augmented[normalized] = agent_id
            if normalized.isdigit():
                if len(normalized) <= 8:
                    augmented.setdefault(normalized.zfill(8), agent_id)
                if len(normalized) <= 10:
                    augmented.setdefault(normalized.zfill(10), agent_id)
    return augmented


def _participant_resolution_coverage(
    frame: pd.DataFrame,
    *,
    raw_columns: Sequence[str],
    resolved_columns: Sequence[str],
) -> tuple[float | None, int, int]:
    raw_identities: set[str] = set()
    resolved_identities: set[str] = set()
    for raw_column, resolved_column in zip(raw_columns, resolved_columns, strict=True):
        raw_series = _coerce_string_series(frame, raw_column)
        resolved_series = _coerce_string_series(frame, resolved_column)
        for raw_value, resolved_value in zip(raw_series, resolved_series, strict=False):
            normalized = _normalize_identity_key(raw_value)
            if not normalized:
                continue
            raw_identities.add(normalized)
            if str(resolved_value).strip():
                resolved_identities.add(normalized)
    if not raw_identities:
        return None, 0, 0
    return (
        len(resolved_identities) / float(len(raw_identities)),
        len(resolved_identities),
        len(raw_identities),
    )


def _link_participants(
    frame: pd.DataFrame,
    *,
    lookup: dict[str, str],
    source_col: str,
    target_col: str,
    source_out: str,
    target_out: str,
) -> pd.DataFrame:
    linked = frame.copy()
    if source_col in linked.columns:
        linked[source_out] = linked[source_col].map(lambda value: _resolve_agent_id(value, lookup))
    if target_col in linked.columns:
        linked[target_out] = linked[target_col].map(lambda value: _resolve_agent_id(value, lookup))
    return linked


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
    edges = (
        frame[[src_col, dst_col, weight_col, period_col]].dropna(subset=[src_col, dst_col]).copy()
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


def _build_synthetic_multiscale_payload(
    agent_registry_runtime: pd.DataFrame,
    cell_registry: pd.DataFrame,
    cell_state: pd.DataFrame,
) -> dict[str, Any]:
    agents = _ensure_agent_numeric_columns(agent_registry_runtime)
    if agents.empty:
        agents = pd.DataFrame(
            {"agent_id": ["agent::00000000"], "revenue": [0.0], "employees": [0.0]}
        )
        agents["region_numeric"] = 0.0
        agents["assets"] = 0.0
        agents["liabilities"] = 0.0
    incomes = np.maximum(
        _sanitize_numeric_series(agents["revenue"], fill=0.0, lower=0.0, upper=1e12).to_numpy(
            dtype=float
        ),
        1.0,
    )
    employees = _sanitize_numeric_series(
        agents["employees"], fill=0.0, lower=0.0, upper=1e9
    ).to_numpy(dtype=float)
    n_agents = len(agents)
    employers = np.full(n_agents, -1, dtype=int)
    if n_agents > 0:
        employers[:-1] = 0
    wage_offer = np.nan_to_num(
        incomes / np.maximum(employees, 1.0), nan=1.0, posinf=1.0, neginf=1.0
    )
    firms = pd.DataFrame(
        {
            "labor_count": [float(max(1.0, employees.sum()))],
            "wage_offer": [float(np.nanmean(wage_offer))],
        }
    )
    cells = cell_state.copy()
    if cells.empty:
        cells = pd.DataFrame(
            {
                "cell_id": ["cell::0::0"],
                "region_numeric": [0],
                "sector_numeric": [0],
                "population": [1.0],
                "employment": [0.0],
                "output": [0.0],
                "distress_score": [0.0],
                "public_service_index": [0.0],
            }
        )
    cell_population = _sanitize_numeric_series(cells["population"], fill=1.0, lower=0.0, upper=1e9)
    cell_employment = _sanitize_numeric_series(cells["employment"], fill=0.0, lower=0.0, upper=1e9)
    cell_output = _sanitize_numeric_series(cells["output"], fill=0.0, lower=0.0)
    cell_distress = _sanitize_numeric_series(
        cells["distress_score"], fill=0.0, lower=0.0, upper=1.0
    )
    cell_public_service = _sanitize_numeric_series(
        cells["public_service_index"], fill=0.0, lower=0.0, upper=1.0
    )
    household_cells = cells.head(max(1, min(32, len(cells)))).copy()
    household_population = _sanitize_numeric_series(
        household_cells["population"], fill=1.0, lower=0.0, upper=1e9
    )
    household_output = _sanitize_numeric_series(household_cells["output"], fill=0.0, lower=0.0)
    household_distress = _sanitize_numeric_series(
        household_cells["distress_score"], fill=0.0, lower=0.0, upper=1.0
    )
    household_public_service = _sanitize_numeric_series(
        household_cells["public_service_index"], fill=0.0, lower=0.0, upper=1.0
    )
    household_cells["household_count"] = np.maximum(
        np.ceil(household_population / 3.0),
        1.0,
    )
    household_cells["disposable_income"] = np.maximum(
        household_output / np.maximum(household_cells["household_count"], 1.0),
        1.0,
    )
    household_cells["poverty_rate"] = household_distress
    household_cells["transfer_intensity"] = household_public_service
    payload = {
        "agents": {
            "age": [30.0 + (idx % 25) for idx in range(n_agents)],
            "skill_level": np.clip(
                (employees + 1.0) / np.maximum(employees.max() + 1.0, 1.0), 0.1, 2.0
            ).tolist(),
            "income": incomes.tolist(),
            "reported_income": (0.92 * incomes).tolist(),
            "risk_aversion": np.clip(np.linspace(0.2, 0.8, n_agents), 0.0, 1.0).tolist(),
            "is_employed": (employees > 0.0).tolist(),
            "employer_id": employers.tolist(),
        },
        "firms": firms.to_dict(orient="list"),
        "cells": {
            "active": [True] * len(cells),
            "region_code": pd.to_numeric(cells["region_numeric"], errors="coerce")
            .fillna(0)
            .astype(int)
            .tolist(),
            "sector_id": pd.to_numeric(cells["sector_numeric"], errors="coerce")
            .fillna(0)
            .astype(int)
            .tolist(),
            "population": cell_population.tolist(),
            "employment": cell_employment.tolist(),
            "output": cell_output.tolist(),
            "distress_score": cell_distress.tolist(),
            "public_service_index": cell_public_service.tolist(),
        },
        "household_cells": {
            "active": [True] * len(household_cells),
            "cell_id": list(range(len(household_cells))),
            "household_count": household_cells["household_count"].astype(float).tolist(),
            "disposable_income": household_cells["disposable_income"].astype(float).tolist(),
            "poverty_rate": household_cells["poverty_rate"].astype(float).tolist(),
            "transfer_intensity": household_cells["transfer_intensity"].astype(float).tolist(),
        },
    }
    return payload


def _validation_subset(
    runtime_agents: pd.DataFrame,
    cell_registry: pd.DataFrame,
    cell_state: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    agent_limit = _int_env("POLISYOS_UKRAINE_DATA_BINDINGS_AGENT_LIMIT", 1024)
    cell_limit = _int_env("POLISYOS_UKRAINE_DATA_BINDINGS_CELL_LIMIT", 256)
    warnings: list[str] = []

    validation_agents = runtime_agents.head(agent_limit).copy()
    if len(validation_agents) < len(runtime_agents):
        warnings.append(
            f"bindings_validation_agent_sampled:{len(validation_agents)}/{len(runtime_agents)}"
        )

    referenced_cell_ids = set(
        _coerce_string_series(validation_agents, "cell_id", fill="")
        .replace("", pd.NA)
        .dropna()
        .tolist()
    )
    validation_cells = cell_registry[
        cell_registry["cell_id"].astype("string").isin(referenced_cell_ids)
    ].copy()
    if validation_cells.empty:
        validation_cells = cell_registry.head(cell_limit).copy()
    elif len(validation_cells) > cell_limit:
        validation_cells = validation_cells.head(cell_limit).copy()
    if len(validation_cells) < len(cell_registry):
        warnings.append(
            f"bindings_validation_cell_sampled:{len(validation_cells)}/{len(cell_registry)}"
        )

    validation_cell_ids = set(_coerce_string_series(validation_cells, "cell_id", fill="").tolist())
    validation_cell_state = cell_state[
        cell_state["cell_id"].astype("string").isin(validation_cell_ids)
    ].copy()
    if validation_cell_state.empty:
        validation_cell_state = cell_state.head(len(validation_cells) or cell_limit).copy()

    return validation_agents, validation_cells, validation_cell_state, warnings


def _cas_put_json(store: FileSystemCAS, payload: Any, *, kind: str):
    return store.put_json(
        payload,
        PutOptions(kind=kind, media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )


__all__ = tuple(name for name in globals() if not name.startswith("__"))
