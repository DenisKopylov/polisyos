"""Stage builders for the Ukraine Part B production data pipeline.

The builders in this module intentionally focus on reproducible artifact
assembly, manifests, and contract validation. They are designed to run against
real server-side source snapshots, while remaining lightweight enough for local
unit tests that exercise helper logic only.
"""

from __future__ import annotations

import gc
import hashlib
import json
import math
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np
import pandas as pd
from pydantic import BaseModel

from polisyos.batch_common.paths import ensure_dirs
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry.release_acceptance import ReleaseAcceptanceRunner
from polisyos.foundry.data_plane.bindings import build_input_bindings
from polisyos.foundry.layout import build_slot_family_manifest
from polisyos.foundry.methods.catalog.causal.measurement_error import identify_with_proxy
from polisyos.foundry.methods.catalog.causal.protocols import (
    DynamicTreatmentData,
    NetworkCausalData,
    PanelObservationalData,
)
from polisyos.foundry.methods.catalog.econometrics.protocols import PanelData
from polisyos.foundry.methods.catalog.microsim.protocols import SurveyMicroData
from polisyos.foundry.methods.catalog.ml.protocols import SurvivalData
from polisyos.foundry.methods.catalog.network.protocols import (
    MultiplexNetworkData,
    NetworkData,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY
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
    ObservationPanel,
    ObservationRecord,
    SourceConfidenceTier,
    StrategicResponseChannel,
)
from polisyos.ir.observation.governance import (
    GovernancePassAliasRegistry,
    ObservationFamilyPolicyRegistry,
)
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
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import SelectorOperator
from polisyos.lex.interventions import (
    InterventionKnobSpec,
    LexInterventionCompiler,
    LexProvisionDirective,
    TemporalInterventionSequencer,
)
from polisyos.scientist.governance import (
    CalibrationGovernanceEvidenceRunner,
    CalibrationRunRunner,
    CalibrationRunManifest,
    GovernanceAccountabilityInput,
    CalibrationValidationRunner,
    CalibrationValidationRunnerInput,
    FamilyEligibilityRegistry,
    HoldoutScoresManifest,
    LossBreakdownManifest,
    REQUIRED_SIGNOFF_FAMILIES,
    SpecificationCurveRunner,
    SpecificationCurveSummaryManifest,
    StrategicResponseMetricsManifest,
    StrategicResponseRunner,
    TransportabilitySummaryManifest,
    TransportabilityRunner,
    build_downstream_utility_report,
    build_family_eligibility_registry,
    build_interference_evidence,
    build_required_backtest_bundles,
    load_governance_accountability_artifact,
)
from polisyos.ir.types import TimeFrequency
from polisyos.ukraine_data.manifests import (
    ArtifactRecord,
    CalibrationBundleManifest,
    ReleaseManifest,
    RuntimeBundleManifest,
    ValidationFinding,
    write_manifest,
)
from polisyos.ukraine_data.adapters import _UKRAINE_OBLAST_CODE_MAP
from polisyos.ukraine_data.models import BuildRootConfig, PipelineConfig, SourceConfig, StageId
from polisyos.ukraine_data.resources import directory_size_bytes


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
    if isinstance(payload, BaseModel):
        serialized = payload.model_dump(mode="json")
    else:
        serialized = payload
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
    return ArtifactRecord.from_path(path, row_count=int(len(frame)))


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
    elif match := re.match(r"^(\d{4})[-_/]?M(\d{1,2})$", normalized):
        year = int(match.group(1))
        month = int(match.group(2))
    elif match := re.match(r"^(\d{4})-(\d{2})-(\d{2})$", normalized):
        year = int(match.group(1))
        month = int(match.group(2))
    elif match := re.match(r"^(\d{4})[-_/]?(\d{2})$", normalized):
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
    period_series = _coerce_string_series(frame, period_column, fill="") if period_column in frame.columns else pd.Series([""] * len(frame))
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
    return (
        unresolved.groupby(
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
        )
        .agg(amount_weight=("amount_weight", "sum"), observation_count=("observation_count", "sum"))
    )


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
    raw_column = "raw_registration_code" if "raw_registration_code" in frame.columns else "normalized_raw_registration_code"
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
    name_keys = filtered.get("counterparty_name_key", pd.Series(dtype="string")).fillna("").astype("string").str.strip()
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
            region_match = not region_code or not candidate_region or region_code == candidate_region
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
                    "source_family": getattr(row, "source_family"),
                    "source_id": getattr(row, "source_id"),
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
        candidate_frame = (
            candidate_frame.groupby(
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
            )
            .agg(
                amount_weight=("amount_weight", "sum"),
                observation_count=("observation_count", "sum"),
                source_family=("source_family", lambda values: ",".join(sorted({str(item) for item in values if str(item)}))),
                source_id=("source_id", lambda values: ",".join(sorted({str(item) for item in values if str(item)}))),
            )
        )

    resolved_rows: list[dict[str, Any]] = []
    if not candidate_frame.empty:
        for normalized_code, group in candidate_frame.groupby("normalized_raw_registration_code", sort=False):
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
        "unresolved_identity_rows": int(len(unresolved_frame)),
        "unresolved_unique_numeric_ids": int(
            unresolved_frame["normalized_raw_registration_code"].astype(str).nunique()
            if not unresolved_frame.empty
            else 0
        ),
        "candidate_matches": int(len(candidate_frame)),
        "resolved_matches": int(len(resolved_frame)),
        "resolution_methods": (
            candidate_frame.get("match_method", pd.Series(dtype=str)).astype(str).value_counts().to_dict()
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
    return len(resolved_identities) / float(len(raw_identities)), len(resolved_identities), len(raw_identities)


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
    edges = frame[[src_col, dst_col, weight_col, period_col]].dropna(subset=[src_col, dst_col]).copy()
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
    selected_set = set(selected)
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
        agents = pd.DataFrame({"agent_id": ["agent::00000000"], "revenue": [0.0], "employees": [0.0]})
        agents["region_numeric"] = 0.0
        agents["assets"] = 0.0
        agents["liabilities"] = 0.0
    incomes = np.maximum(
        _sanitize_numeric_series(agents["revenue"], fill=0.0, lower=0.0, upper=1e12).to_numpy(dtype=float),
        1.0,
    )
    employees = _sanitize_numeric_series(
        agents["employees"], fill=0.0, lower=0.0, upper=1e9
    ).to_numpy(dtype=float)
    n_agents = len(agents)
    employers = np.full(n_agents, -1, dtype=int)
    if n_agents > 0:
        employers[:-1] = 0
    wage_offer = np.nan_to_num(incomes / np.maximum(employees, 1.0), nan=1.0, posinf=1.0, neginf=1.0)
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
    cell_distress = _sanitize_numeric_series(cells["distress_score"], fill=0.0, lower=0.0, upper=1.0)
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
            "skill_level": np.clip((employees + 1.0) / np.maximum(employees.max() + 1.0, 1.0), 0.1, 2.0).tolist(),
            "income": incomes.tolist(),
            "reported_income": (0.92 * incomes).tolist(),
            "risk_aversion": np.clip(np.linspace(0.2, 0.8, n_agents), 0.0, 1.0).tolist(),
            "is_employed": (employees > 0.0).tolist(),
            "employer_id": employers.tolist(),
        },
        "firms": firms.to_dict(orient="list"),
        "cells": {
            "active": [True] * len(cells),
            "region_code": pd.to_numeric(cells["region_numeric"], errors="coerce").fillna(0).astype(int).tolist(),
            "sector_id": pd.to_numeric(cells["sector_numeric"], errors="coerce").fillna(0).astype(int).tolist(),
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
        _coerce_string_series(validation_agents, "cell_id", fill="").replace("", pd.NA).dropna().tolist()
    )
    validation_cells = cell_registry[cell_registry["cell_id"].astype("string").isin(referenced_cell_ids)].copy()
    if validation_cells.empty:
        validation_cells = cell_registry.head(cell_limit).copy()
    elif len(validation_cells) > cell_limit:
        validation_cells = validation_cells.head(cell_limit).copy()
    if len(validation_cells) < len(cell_registry):
        warnings.append(
            f"bindings_validation_cell_sampled:{len(validation_cells)}/{len(cell_registry)}"
        )

    validation_cell_ids = set(_coerce_string_series(validation_cells, "cell_id", fill="").tolist())
    validation_cell_state = cell_state[cell_state["cell_id"].astype("string").isin(validation_cell_ids)].copy()
    if validation_cell_state.empty:
        validation_cell_state = cell_state.head(len(validation_cells) or cell_limit).copy()

    return validation_agents, validation_cells, validation_cell_state, warnings


def _cas_put_json(store: FileSystemCAS, payload: Any, *, kind: str):
    return store.put_json(
        payload,
        PutOptions(kind=kind, media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )


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
    spending_for_linking["_source_agent_raw_id"] = _coerce_string_series(spending_for_linking, "source_agent_id")
    spending_for_linking["_target_agent_raw_id"] = _coerce_string_series(spending_for_linking, "target_agent_id")
    spending_linked_initial = _link_participants(
        spending_for_linking,
        lookup=lookup,
        source_col="source_agent_id",
        target_col="target_agent_id",
        source_out="source_agent_id",
        target_out="target_agent_id",
    )
    prozorro_for_linking = prozorro.copy()
    prozorro_for_linking["_buyer_agent_raw_id"] = _coerce_string_series(prozorro_for_linking, "buyer_agent_id")
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

    spending_coverage_before, spending_resolved_before, spending_total_before = _participant_resolution_coverage(
        spending_linked_initial,
        raw_columns=["_source_agent_raw_id", "_target_agent_raw_id"],
        resolved_columns=["source_agent_id", "target_agent_id"],
    )
    procurement_coverage_before, procurement_resolved_before, procurement_total_before = _participant_resolution_coverage(
        prozorro_linked_initial,
        raw_columns=["_buyer_agent_raw_id", "_supplier_agent_raw_id"],
        resolved_columns=["buyer_agent_id", "supplier_agent_id"],
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
    print(
        "[ukraine-data] building EDR identity bridge "
        f"rows={len(unresolved_identity_rows)} "
        f"unique_ids={int(unresolved_identity_rows.get('normalized_raw_registration_code', pd.Series(dtype='string')).astype('string').nunique()) if not unresolved_identity_rows.empty else 0}",
        flush=True,
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
    print(
        "[ukraine-data] EDR identity bridge built "
        f"resolved={len(edr_bridge_resolved)} candidates={len(edr_bridge_candidates)}",
        flush=True,
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
                spending_linked.get("source_agent_id", pd.Series(dtype="string")).dropna().astype("string"),
                spending_linked.get("target_agent_id", pd.Series(dtype="string")).dropna().astype("string"),
                prozorro_linked.get("buyer_agent_id", pd.Series(dtype="string")).dropna().astype("string"),
                prozorro_linked.get("supplier_agent_id", pd.Series(dtype="string")).dropna().astype("string"),
                dps.get("agent_id", pd.Series(dtype="string")).dropna().astype("string"),
            ],
            ignore_index=True,
        ).unique()
    )
    runtime_agents = agent_registry_full[
        agent_registry_full.get("agent_id", pd.Series(dtype="string")).astype("string").isin(participant_ids)
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

    public_entity_registry = pd.concat(
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
    ).dropna(subset=["entity_id"]).drop_duplicates()

    cell_registry = (
        runtime_agents.assign(
            region_code=_coerce_string_series(runtime_agents, "region_code", fill="unknown"),
            sector_id=_coerce_string_series(runtime_agents, "sector_id", fill="unknown"),
        )
        .groupby(["cell_id", "region_code", "sector_id"], as_index=False)
        .agg(agent_count=("agent_id", "nunique"))
    )
    region_mapping = {value: idx for idx, value in enumerate(sorted(cell_registry["region_code"].astype(str).unique()))}
    sector_mapping = {value: idx for idx, value in enumerate(sorted(cell_registry["sector_id"].astype(str).unique()))}
    cell_registry["region_numeric"] = cell_registry["region_code"].astype(str).map(region_mapping).astype(int)
    cell_registry["sector_numeric"] = cell_registry["sector_id"].astype(str).map(sector_mapping).astype(int)

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
    cell_state["agent_count"] = _sanitize_numeric_series(cell_state["agent_count"], fill=0.0, lower=0.0)
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
        cell_state.loc[population_fallback_mask, "population"] = (
            cell_state.loc[population_fallback_mask, "agent_count"].clip(lower=1.0)
        )
        stage_warnings.append(
            f"cell_population_fallback_to_agent_count:{int(population_fallback_mask.sum())}"
        )
    if float(cell_state["employment"].max()) <= 0.0:
        stage_warnings.append("dps_employment_missing_using_zero_fallback")
    employment_cap = np.minimum(cell_state["employment"].to_numpy(dtype=float), cell_state["population"].to_numpy(dtype=float))
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
            "unresolved_identity_rows_raw": int(len(unresolved_identity_rows)),
            "unresolved_unique_numeric_ids_raw": int(
                unresolved_identity_rows["normalized_raw_registration_code"].astype("string").nunique()
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
    outputs["edr_identity_bridge_manifest.json"] = ArtifactRecord.from_path(edr_bridge_manifest_path)
    outputs["cell_registry_region_sector.parquet"] = _write_frame(
        stage_dir / "cell_registry_region_sector.parquet",
        cell_registry,
    )
    outputs["geo_index_runtime.parquet"] = _write_frame(stage_dir / "geo_index_runtime.parquet", geo_index)
    outputs["budget_graph_sparse.npz"] = _write_npz(stage_dir / "budget_graph_sparse.npz", **budget_arrays)
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
    procurement_coverage, procurement_resolved, procurement_total = _participant_resolution_coverage(
        prozorro_linked,
        raw_columns=["_buyer_agent_raw_id", "_supplier_agent_raw_id"],
        resolved_columns=["buyer_agent_id", "supplier_agent_id"],
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
    outputs["edr_identity_bridge_manifest.json"] = ArtifactRecord.from_path(edr_bridge_manifest_path)
    runtime_agent_count = len(runtime_agents)
    cell_count = len(cell_registry)
    macro_rows = len(macro)
    budget_graph_nnz = outputs["budget_graph_sparse.npz"].nnz
    procurement_graph_nnz = outputs["procurement_graph_sparse.npz"].nnz

    print(
        "[ukraine-data] preparing D0 validation subset "
        f"from runtime_agents={runtime_agent_count} cells={cell_count}",
        flush=True,
    )
    validation_agents, validation_cells, validation_cell_state, validation_warnings = _validation_subset(
        runtime_agents,
        cell_registry,
        cell_state,
    )
    stage_warnings.extend(validation_warnings)
    print(
        "[ukraine-data] D0 validation subset "
        f"agents={len(validation_agents)} cells={len(validation_cells)}",
        flush=True,
    )

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

    print("[ukraine-data] building D0 validation payload", flush=True)
    payload = _build_synthetic_multiscale_payload(validation_agents, validation_cells, validation_cell_state)
    store = FileSystemCAS(build_root.resolved_cas_root)
    payload_ref = _cas_put_json(store, payload, kind="fabric.synthetic_multiscale_payload")
    data_snapshot_ref = _cas_put_json(
        store,
        DataSnapshot(
            data_ref=payload_ref,
            stats={
                "n_agents": len(validation_agents),
                "n_cells": len(validation_cells),
                "n_budget_edges": int(len(budget_arrays["weight"])),
                "n_procurement_edges": int(len(procurement_arrays["weight"])),
            },
            notes=["ukraine_part_b_d0_p0_runtime_seed", "validation_payload_downsampled_from_full_runtime"],
        ),
        kind="fabric.data_snapshot",
    )
    registry_bundle = build_default_registry_bundle(store)
    print("[ukraine-data] running build_input_bindings() smoke", flush=True)
    bindings = build_input_bindings(
        store,
        data_snapshot_ref=data_snapshot_ref,
        registry_bundle_ref=registry_bundle.bundle_ref,
    )
    print("[ukraine-data] build_input_bindings() smoke completed", flush=True)

    runtime_bundle = RuntimeBundleManifest(
        outputs=outputs,
        data_snapshot_artifact_id=str(data_snapshot_ref.artifact_id),
        input_bindings_artifact_id=str(bindings.input_bindings_ref.artifact_id),
        validation=[],
        metrics={
            "n_agents": runtime_agent_count,
            "n_cells": cell_count,
            "budget_graph_nnz": budget_graph_nnz,
            "procurement_graph_nnz": procurement_graph_nnz,
            "applied_binding_ids": list(bindings.applied_binding_ids),
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
    node_features, node_states = _node_features_from_agent_registry(agent_registry, node_ids=node_ids)
    network_payload = NetworkData(
        adjacency=adjacency,
        node_features=node_features,
        node_states=node_states,
        node_ids=list(node_ids),
        metadata={"layer_id": layer_id},
    )
    treatment = (node_states > float(np.nanmedian(node_states) if len(node_states) else 0.0)).astype(float)
    outcome = np.log1p(np.maximum(node_states, 0.0))
    causal_payload = NetworkCausalData(
        outcome=outcome,
        treatment=treatment,
        covariates=node_features,
        adjacency_matrix=adjacency,
        metadata={"layer_id": layer_id},
    )
    outputs = {
        f"{output_prefix}_network_data.json": _write_protocol_json(
            stage_dir / f"{output_prefix}_network_data.json",
            network_payload,
        ),
        f"{output_prefix}_network_causal_data.json": _write_protocol_json(
            stage_dir / f"{output_prefix}_network_causal_data.json",
            causal_payload,
        ),
    }
    return outputs


def build_d1_stage(config: PipelineConfig) -> StageBuildResult:
    """Build D1 enrichment graphs, proxy checks, and multiplex manifests."""

    build_root = config.build_root
    stage_dir = _stage_dir(build_root, StageId.D1)
    ensure_dirs(stage_dir)
    agent_registry = pd.read_parquet(_stage_dir(build_root, StageId.D0_P0) / "agent_registry_runtime.parquet")
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
    distress["weight"] = _safe_numeric_series(distress, "tax_debt") + _safe_numeric_series(distress, "risk_score")
    distress["period_id"] = distress.get("period_id", "2025-01")
    node_ids = _collect_graph_node_ids(
        base_node_ids=node_ids,
        edge_frames=[
            (distress.rename(columns={"agent_id": "src_agent_id"}), "src_agent_id", "peer_agent_id"),
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
    outputs["trade_graph_sparse.npz"] = _write_npz(stage_dir / "trade_graph_sparse.npz", **trade_arrays)
    outputs["distress_graph_sparse.npz"] = _write_npz(stage_dir / "distress_graph_sparse.npz", **distress_arrays)
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

    multiplex_payload = MultiplexNetworkData(
        adjacency_layers=np.stack([trade_adj, distress_adj, public_service_adj]),
        node_features=_node_features_from_agent_registry(runtime_agents, node_ids=contract_node_ids)[0],
        node_ids=contract_node_ids,
        metadata={
            "layers": ["trade", "distress", "public_service"],
            "full_node_count": full_node_count,
            "contract_node_count": len(contract_node_ids),
            "compression_mode": "top_weighted_degree_subgraph",
        },
    )
    outputs["multiplex_network_data.json"] = _write_protocol_json(
        stage_dir / "multiplex_network_data.json",
        multiplex_payload,
    )

    proxy_graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["C_star", "C", "x", "y"],
        edges=[
            CausalEdge(src="C_star", dst="C", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="C", dst="x", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="C", dst="y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="x", dst="y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
    )
    proxy_checks = {}
    for channel_id, family, proxy_variable, latent_variable in [
        ("tax_debt_to_distress", ObservationFamily.DISTRESS_ENFORCEMENT, "C_star", "C"),
        ("procurement_revenue_to_cashflow", ObservationFamily.PROCUREMENT_FLOWS, "C_star", "C"),
        ("admin_employment_to_true_employment", ObservationFamily.LABOR_MARKET, "C_star", "C"),
    ]:
        result = identify_with_proxy(
            proxy_graph,
            treatment="x",
            outcome="y",
            proxy_map={latent_variable: proxy_variable},
            measurement_model="known",
        )
        proxy_checks[channel_id] = {
            "family": family.value,
            "status": getattr(result.status, "value", str(result.status)),
            "algorithm_version": getattr(result, "algorithm_version", "proxy_id_v1"),
        }

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
        contract_payload={"proxy_checks": proxy_checks},
        proxy_map={"distress": "tax_debt", "cashflow": "procurement_revenue", "true_employment": "registered_employment"},
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
                "network_causal_contract": str(stage_dir / "public_service_network_causal_data.json"),
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
    if not all(item["status"] == "identified" for item in proxy_checks.values()):
        findings.append(
            ValidationFinding(
                severity="error",
                code="proxy_identification_failed",
                message="one or more proxy-identification channels did not return IDENTIFIED",
            )
        )
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
        if pd.api.types.is_numeric_dtype(frame[column]) and column not in {"coverage_estimate", "trust_weight"}
    ]
    return numeric_columns[:4]


def _entity_scope_identity(source: SourceConfig, row: pd.Series) -> tuple[str | None, str | None, str | None, str | None]:
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
        compact = frame[column].map(lambda value: _compact_locator_value(value, max_length=max_length, prefix=prefix))
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
    mapping = {
        key: _period_to_dates(key, time_grain)
        for key in raw.unique().tolist()
    }
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
    period_values = frame[source.period_column] if source.period_column in frame.columns else pd.Series(
        ["2025-01"] * len(frame),
        index=frame.index,
        dtype="string",
    )
    period_start, period_end = _period_series_to_iso_bounds(period_values, time_grain=source.time_grain)
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
    regime_id = frame["regime_id"].astype(str) if "regime_id" in frame.columns else pd.Series(
        [source.regime_id] * len(frame),
        index=frame.index,
        dtype=object,
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
        artifact_path = config.build_root.normalized_dir / source.source_id / source.normalized_artifact
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
                row_offset += int(len(frame))
                batch_index += 1
                del frame
        except Exception:
            frame = _read_parquet_frame(artifact_path, columns=requested_columns)
            for metric_id, metric_frame in _observation_metric_frames_from_frame(source, frame, row_offset=0):
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

    print("[ukraine-data] d2 contract-tail: copying causal panel", flush=True)
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
        outputs["panel_econometric_bundle_v1.parquet"] = ArtifactRecord.from_path(panel_econometric_path)
    else:
        print("[ukraine-data] d2 contract-tail: building econometric head fallback", flush=True)
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
    print("[ukraine-data] d2 contract-tail: scanning monthly panel for negative controls", flush=True)
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
    print(
        "[ukraine-data] d2 contract-tail: negative controls ready "
        f"rows={len(negative_control)} trade_count={trade_count}",
        flush=True,
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
    panel_contract = PanelObservationalData(
        outcome=outcomes,
        treatment=treatment,
        time_treatment=1,
        covariates=covariates,
        unit_ids=np.asarray([f"unit::{idx:03d}" for idx in range(n_units)], dtype=object),
        time_index=np.asarray(["2025-01", "2025-02", "2025-03"], dtype=object),
        metadata={"family": ObservationFamily.BUDGET_FLOWS.value},
    )
    outputs["panel_observational_contract.json"] = _write_protocol_json(
        stage_dir / "panel_observational_contract.json",
        panel_contract,
    )

    dynamic_contract = DynamicTreatmentData(
        outcome=np.linspace(1.0, 1.5, n_units, dtype=float),
        treatment_sequence=np.tile(np.asarray([[0, 1, 1]], dtype=int), (n_units, 1)),
        covariate_sequence=np.tile(np.asarray([[[0.1, 0.2], [0.3, 0.2], [0.4, 0.5]]], dtype=float), (n_units, 1, 1)),
        time_ids=np.asarray(["2025-01", "2025-02", "2025-03"], dtype=object),
        variable_names=["lagged_cashflow", "lagged_procurement"],
        metadata={"family": ObservationFamily.PROCUREMENT_FLOWS.value},
    )
    outputs["dtr_treatment_sequence_bundle_v1.npz"] = _write_npz(
        stage_dir / "dtr_treatment_sequence_bundle_v1.npz",
        outcome=np.asarray(dynamic_contract.outcome),
        treatment_sequence=np.asarray(dynamic_contract.treatment_sequence),
        covariate_sequence=np.asarray(dynamic_contract.covariate_sequence),
    )
    _write_json(stage_dir / "dynamic_treatment_contract.json", dynamic_contract)
    outputs["dynamic_treatment_contract.json"] = ArtifactRecord.from_path(
        stage_dir / "dynamic_treatment_contract.json"
    )

    survey_contract = SurveyMicroData(
        market_income=np.linspace(100.0, 1000.0, n_units, dtype=float),
        weights=np.ones(n_units, dtype=float),
        household_ids=np.asarray([f"hh::{idx:03d}" for idx in range(n_units)], dtype=object),
        features=np.stack(
            [
                np.linspace(1.0, 10.0, n_units, dtype=float),
                np.linspace(0.0, 1.0, n_units, dtype=float),
            ],
            axis=1,
        ),
        feature_names=["household_size", "poverty_score"],
        metadata={"family": ObservationFamily.HOUSEHOLD_DISTRIBUTION.value},
    )
    outputs["microsim_survey_contract_preview.json"] = _write_protocol_json(
        stage_dir / "microsim_survey_contract_preview.json",
        survey_contract,
    )

    survival_contract = SurvivalData(
        features=np.stack(
            [
                np.linspace(0.0, 1.0, n_units, dtype=float),
                np.linspace(1.0, 0.0, n_units, dtype=float),
            ],
            axis=1,
        ),
        durations=np.linspace(1.0, 24.0, n_units, dtype=float),
        events=np.asarray([1 if idx % 3 else 0 for idx in range(n_units)], dtype=int),
        feature_names=["risk_score", "liquidity_ratio"],
        metadata={"family": ObservationFamily.FIRM_FUNDAMENTALS.value},
    )
    outputs["survival_data_bundle_v1.parquet"] = _write_frame(
        stage_dir / "survival_data_bundle_v1.parquet",
        pd.DataFrame(
            {
                "duration": np.asarray(survival_contract.durations),
                "event": np.asarray(survival_contract.events),
                "risk_score": np.asarray(survival_contract.features)[:, 0],
                "liquidity_ratio": np.asarray(survival_contract.features)[:, 1],
            }
        ),
    )
    outputs["survival_contract.json"] = _write_protocol_json(
        stage_dir / "survival_contract.json",
        survival_contract,
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
    econometric_contract = PanelData.from_dataframe(
        econometric_df,
        dependent_col="outcome",
        exog_cols=["treatment", "covariate"],
        entity_col="unit_id",
        time_col="time_id",
    )
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
                        included_families=[ObservationFamily.BUDGET_FLOWS, ObservationFamily.PROCUREMENT_FLOWS],
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
                "contract_id": NetworkData.contract_id,
            },
        )
    )
    outputs["network_causal_contract_bundle_v1.json"] = ArtifactRecord.from_path(
        _write_json(
            stage_dir / "network_causal_contract_bundle_v1.json",
            {
                "layers": ["budget", "procurement", "trade", "distress", "public_service"],
                "contract_id": NetworkCausalData.contract_id,
            },
        )
    )

    manifest = ObservationToContractManifest(
        routes=[
            ObservationContractRoute(
                family=ObservationFamily.BUDGET_FLOWS,
                identification_mode=IdentificationMode.POINT_IDENTIFIED,
                target_contract=ContractCompatibilityTarget(
                    contract_id=PanelObservationalData.contract_id,
                    contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.PanelObservationalData",
                ),
            ),
            ObservationContractRoute(
                family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
                identification_mode=IdentificationMode.POINT_IDENTIFIED,
                target_contract=ContractCompatibilityTarget(
                    contract_id=SurveyMicroData.contract_id,
                    contract_fqn="polisyos.foundry.methods.catalog.microsim.protocols.SurveyMicroData",
                ),
            ),
            ObservationContractRoute(
                family=ObservationFamily.FIRM_FUNDAMENTALS,
                identification_mode=IdentificationMode.POINT_IDENTIFIED,
                target_contract=ContractCompatibilityTarget(
                    contract_id=SurvivalData.contract_id,
                    contract_fqn="polisyos.foundry.methods.catalog.ml.protocols.SurvivalData",
                ),
            ),
            ObservationContractRoute(
                family=ObservationFamily.PROCUREMENT_FLOWS,
                identification_mode=IdentificationMode.SEQUENTIAL,
                target_contract=ContractCompatibilityTarget(
                    contract_id=DynamicTreatmentData.contract_id,
                    contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.DynamicTreatmentData",
                ),
            ),
        ],
        artifacts=[
            ObservationContractArtifact(
                compiler_id="ukraine_data.panel_builder",
                artifact_name="panel_observational_contract.json",
                target_contract=ContractCompatibilityTarget(
                    contract_id=PanelObservationalData.contract_id,
                    contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.PanelObservationalData",
                ),
            ),
            ObservationContractArtifact(
                compiler_id="ukraine_data.survey_builder",
                artifact_name="microsim_survey_contract_preview.json",
                target_contract=ContractCompatibilityTarget(
                    contract_id=SurveyMicroData.contract_id,
                    contract_fqn="polisyos.foundry.methods.catalog.microsim.protocols.SurveyMicroData",
                ),
            ),
            ObservationContractArtifact(
                compiler_id="ukraine_data.dynamic_builder",
                artifact_name="dynamic_treatment_contract.json",
                target_contract=ContractCompatibilityTarget(
                    contract_id=DynamicTreatmentData.contract_id,
                    contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.DynamicTreatmentData",
                ),
            ),
            ObservationContractArtifact(
                compiler_id="ukraine_data.survival_builder",
                artifact_name="survival_contract.json",
                target_contract=ContractCompatibilityTarget(
                    contract_id=SurvivalData.contract_id,
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
        shard_path = source_dir / f"{_kernel_safe_id(metric_id, prefix='metric')}_{batch_index:05d}.parquet"
        metric_frame.to_parquet(shard_path, index=False)
        shard_counter += 1
        if source.time_grain == TimeFrequency.YEAR:
            annual_shards.append(shard_path)
            annual_row_count += int(len(metric_frame))
        else:
            monthly_shards.append(shard_path)
            monthly_row_count += int(len(metric_frame))
        family_counts[source.observation_family.value] += int(len(metric_frame))
        families_present.add(source.observation_family.value)
        if shard_counter == 1 or shard_counter % 25 == 0:
            rss_gib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024.0 * 1024.0)
            print(
                "[ukraine-data] d2 shard "
                f"{shard_counter} source={source.source_id} metric={metric_id} batch={batch_index} "
                f"rows={len(metric_frame)} maxrss_gib={rss_gib:.2f}",
                flush=True,
            )
        del metric_frame
        try:
            import pyarrow as pa

            pa.default_memory_pool().release_unused()
        except Exception:
            pass
        gc.collect()
    gc.collect()
    print(
        "[ukraine-data] d2 shard pass complete "
        f"monthly_shards={len(monthly_shards)} annual_shards={len(annual_shards)}",
        flush=True,
    )

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
    print("[ukraine-data] d2 materializing unified observation panels", flush=True)
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
            RegimeCalendarEntry(regime_id="regime_a", start_date=date(2015, 9, 1), end_date=date(2021, 12, 31)),
            RegimeCalendarEntry(regime_id="regime_b", start_date=date(2022, 1, 1), end_date=date(2023, 12, 31)),
            RegimeCalendarEntry(regime_id="regime_c", start_date=date(2024, 1, 1), end_date=date(2025, 12, 31)),
        ]
    )
    shock_calendar = ShockCalendar(
        entries=[
            ShockCalendarEntry(shock_id="shock_budget_2022", start_date=date(2022, 2, 1), end_date=date(2022, 6, 30)),
            ShockCalendarEntry(shock_id="shock_fx_2022", start_date=date(2022, 3, 1), end_date=date(2022, 9, 30)),
            ShockCalendarEntry(shock_id="shock_trade_2022", start_date=date(2022, 4, 1), end_date=date(2022, 10, 31)),
            ShockCalendarEntry(shock_id="shock_procurement_2023", start_date=date(2023, 1, 1), end_date=date(2023, 3, 31)),
            ShockCalendarEntry(shock_id="shock_reimbursement_2024", start_date=date(2024, 5, 1), end_date=date(2024, 8, 31)),
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
        coverage=monthly_vectors.get("coverage_estimate", pd.Series(dtype=float)).to_numpy(dtype=float),
    )
    del monthly_vectors
    gc.collect()

    print("[ukraine-data] d2 building contract-tail artifacts", flush=True)
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
    missing_families = [family.value for family in ObservationFamily if family.value not in calibration_bundle.metrics["families_present"]]
    deferred_missing_families = [
        family
        for family in missing_families
        if family in {ObservationFamily.HOUSEHOLD_DISTRIBUTION.value}
    ]
    missing_families = [family for family in missing_families if family not in deferred_missing_families]
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


def _weighted_average_series(values: pd.Series, weights: pd.Series) -> float:
    numeric_values = pd.to_numeric(values, errors="coerce").fillna(0.0).astype(float)
    numeric_weights = pd.to_numeric(weights, errors="coerce").fillna(1.0).astype(float).clip(lower=0.0)
    weight_sum = float(numeric_weights.sum())
    if weight_sum <= 1e-12:
        return float(numeric_values.mean()) if len(numeric_values) else 0.0
    return float(np.average(numeric_values, weights=numeric_weights))


def _aggregate_labor_micro_panel(labor: pd.DataFrame) -> pd.DataFrame:
    if labor.empty:
        return pd.DataFrame(
            columns=[
                "region_code",
                "period_id",
                "micro_participation_rate",
                "micro_employment_rate",
                "micro_informal_employment_rate",
                "micro_sample_weight",
                "micro_respondent_count",
            ]
        )
    frame = labor.copy()
    frame["region_code"] = _coerce_string_series(frame, "region_code", fill="00").map(_normalize_region_code_value)
    frame["period_id"] = _coerce_string_series(frame, "period_id", fill="2025-12")
    frame["weight"] = pd.to_numeric(frame.get("weight", 1.0), errors="coerce").fillna(1.0)
    frame["participation_rate"] = pd.to_numeric(frame.get("participation_rate", 0.0), errors="coerce").fillna(0.0)
    frame["employment_flag"] = pd.to_numeric(frame.get("employment_flag", 0.0), errors="coerce").fillna(0.0)
    frame["informal_employment_flag"] = pd.to_numeric(
        frame.get("informal_employment_flag", 0.0),
        errors="coerce",
    ).fillna(0.0)
    rows: list[dict[str, Any]] = []
    for (region_code, period_id), group in frame.groupby(["region_code", "period_id"], sort=False):
        rows.append(
            {
                "region_code": region_code,
                "period_id": period_id,
                "micro_participation_rate": _weighted_average_series(group["participation_rate"], group["weight"]),
                "micro_employment_rate": _weighted_average_series(group["employment_flag"], group["weight"]),
                "micro_informal_employment_rate": _weighted_average_series(
                    group["informal_employment_flag"],
                    group["weight"],
                ),
                "micro_sample_weight": float(group["weight"].sum()),
                "micro_respondent_count": int(len(group)),
            }
        )
    return pd.DataFrame.from_records(rows)


def _aggregate_household_income_panel(household: pd.DataFrame) -> pd.DataFrame:
    if household.empty:
        return pd.DataFrame(columns=["region_code", "period_id", "household_income_mean", "household_weight_sum"])
    frame = household.copy()
    frame["region_code"] = _coerce_string_series(frame, "region_code", fill="00").map(_normalize_region_code_value)
    frame["period_id"] = _coerce_string_series(frame, "period_id", fill="2025-12")
    frame["weight"] = pd.to_numeric(frame.get("weight", 1.0), errors="coerce").fillna(1.0)
    frame["income"] = pd.to_numeric(frame.get("income", 0.0), errors="coerce").fillna(0.0)
    rows: list[dict[str, Any]] = []
    for (region_code, period_id), group in frame.groupby(["region_code", "period_id"], sort=False):
        rows.append(
            {
                "region_code": region_code,
                "period_id": period_id,
                "household_income_mean": _weighted_average_series(group["income"], group["weight"]),
                "household_weight_sum": float(group["weight"].sum()),
            }
        )
    return pd.DataFrame.from_records(rows)


def _aggregate_employment_admin_panel(employment_service: pd.DataFrame) -> pd.DataFrame:
    if employment_service.empty:
        return pd.DataFrame(
            columns=[
                "region_code",
                "period_id",
                "admin_employment_count",
                "vacancies",
                "admin_employment_rate_proxy",
            ]
        )
    frame = employment_service.copy()
    frame["region_code"] = _coerce_string_series(frame, "region_code", fill="00").map(_normalize_region_code_value)
    frame["period_id"] = _coerce_string_series(frame, "period_id", fill="2025-12")
    frame["employment_count"] = pd.to_numeric(frame.get("employment_count", 0.0), errors="coerce").fillna(0.0)
    frame["vacancies"] = pd.to_numeric(frame.get("vacancies", 0.0), errors="coerce").fillna(0.0)
    aggregated = (
        frame.groupby(["region_code", "period_id"], as_index=False)
        .agg(
            admin_employment_count=("employment_count", "sum"),
            vacancies=("vacancies", "sum"),
        )
    )
    aggregated["admin_employment_rate_proxy"] = aggregated.groupby("period_id")["admin_employment_count"].transform(
        lambda series: series / max(float(series.max()), 1.0)
    )
    return aggregated


def _extract_macro_labor_panel(macro: pd.DataFrame) -> pd.DataFrame:
    if macro.empty or "metric_id" not in macro.columns or "observed_value" not in macro.columns:
        return pd.DataFrame(columns=["region_code", "period_id", "macro_labor_signal"])
    frame = macro.copy()
    frame["metric_id"] = _coerce_string_series(frame, "metric_id", fill="")
    frame = frame.loc[frame["metric_id"].str.contains("labor|employment|unemployment|wage", case=False, regex=True)]
    if frame.empty:
        return pd.DataFrame(columns=["region_code", "period_id", "macro_labor_signal"])
    frame["region_code"] = _coerce_string_series(frame, "region_code", fill="00").map(_normalize_region_code_value)
    frame["period_id"] = _coerce_string_series(frame, "period_id", fill="2025-12")
    frame["observed_value"] = pd.to_numeric(frame["observed_value"], errors="coerce").fillna(0.0)
    return frame.groupby(["region_code", "period_id"], as_index=False).agg(
        macro_labor_signal=("observed_value", "mean")
    )


def _build_calibrated_household_cells(household: pd.DataFrame) -> pd.DataFrame:
    if household.empty:
        return pd.DataFrame(
            columns=[
                "cell_id",
                "region_code",
                "period_id",
                "household_income_mean",
                "market_income_mean",
                "total_expenditure_mean",
                "household_weight_sum",
                "measurement_bias_flag",
                "trust_weight",
            ]
        )
    frame = household.copy()
    frame["cell_id"] = _coerce_string_series(frame, "cell_id", fill="cell::00::household_distribution")
    frame["region_code"] = _coerce_string_series(frame, "region_code", fill="00").map(_normalize_region_code_value)
    frame["period_id"] = _coerce_string_series(frame, "period_id", fill="2025-12")
    frame["weight"] = pd.to_numeric(frame.get("weight", 1.0), errors="coerce").fillna(1.0)
    frame["income"] = pd.to_numeric(frame.get("income", 0.0), errors="coerce").fillna(0.0)
    frame["market_income"] = pd.to_numeric(frame.get("market_income", frame["income"]), errors="coerce").fillna(0.0)
    frame["total_expenditure"] = pd.to_numeric(
        frame.get("total_expenditure", frame["income"]),
        errors="coerce",
    ).fillna(0.0)
    rows: list[dict[str, Any]] = []
    for (cell_id, region_code, period_id), group in frame.groupby(["cell_id", "region_code", "period_id"], sort=False):
        rows.append(
            {
                "cell_id": cell_id,
                "region_code": region_code,
                "period_id": period_id,
                "household_income_mean": _weighted_average_series(group["income"], group["weight"]),
                "market_income_mean": _weighted_average_series(group["market_income"], group["weight"]),
                "total_expenditure_mean": _weighted_average_series(group["total_expenditure"], group["weight"]),
                "household_weight_sum": float(group["weight"].sum()),
                "measurement_bias_flag": False,
                "trust_weight": 0.95,
            }
        )
    return pd.DataFrame.from_records(rows)


def _build_household_distribution_observation_panel(calibrated_household_cells: pd.DataFrame) -> pd.DataFrame:
    if calibrated_household_cells.empty:
        return pd.DataFrame(columns=OBSERVATION_FRAME_COLUMNS)
    frame = calibrated_household_cells.copy()
    frame["cell_id"] = _coerce_string_series(frame, "cell_id", fill="cell::00::household_distribution")
    frame["region_code"] = _coerce_string_series(frame, "region_code", fill="00").map(_normalize_region_code_value)
    frame["period_id"] = _coerce_string_series(frame, "period_id", fill="2025-12")
    period_start, period_end = _period_series_to_iso_bounds(frame["period_id"], time_grain=TimeFrequency.MONTH)
    regime_values = frame["period_id"].map(_regime_for_period_id)
    observations = pd.DataFrame(
        {
            "observation_id": [
                f"obs.household_distribution.household_income_mean.{idx:08d}" for idx in range(len(frame))
            ],
            "family": ObservationFamily.HOUSEHOLD_DISTRIBUTION.value,
            "time_grain": TimeFrequency.MONTH.value,
            "period_start": period_start,
            "period_end": period_end,
            "entity_scope": EntityScope.CELL.value,
            "entity_id": frame["cell_id"].astype("string"),
            "cell_id": frame["cell_id"].astype("string"),
            "region_code": frame["region_code"].astype("string"),
            "sector_id": pd.Series(["household_distribution"] * len(frame), dtype="string"),
            "metric_id": pd.Series(["household_income_mean"] * len(frame), dtype="string"),
            "observed_value": pd.to_numeric(frame["household_income_mean"], errors="coerce").fillna(0.0).astype(float),
            "unit": pd.Series(["unit"] * len(frame), dtype="string"),
            "coverage_estimate": 0.97,
            "measurement_bias_flag": frame.get(
                "measurement_bias_flag",
                pd.Series([False] * len(frame), index=frame.index),
            ).fillna(False).astype(bool),
            "censoring_mask": False,
            "trust_weight": pd.to_numeric(frame.get("trust_weight", 0.95), errors="coerce").fillna(0.95).astype(float),
            "lag_days_estimate": 0,
            "source_id": pd.Series(["household_microdata"] * len(frame), dtype="string"),
            "source_version": pd.Series(["v1"] * len(frame), dtype="string"),
            "regime_id": pd.Series([item[0] for item in regime_values], dtype="string"),
            "shock_mask": False,
            "schema_regime_id": pd.Series([item[1] for item in regime_values], dtype="string"),
            "identification_mode": pd.Series([IdentificationMode.POINT_IDENTIFIED.value] * len(frame), dtype="string"),
            "source_confidence_tier": pd.Series([SourceConfidenceTier.CORE.value] * len(frame), dtype="string"),
            "proxy_source_id": pd.Series([None] * len(frame), dtype="string"),
        }
    )
    for column in OBSERVATION_FRAME_COLUMNS:
        if column not in observations.columns:
            observations[column] = None
    return observations[OBSERVATION_FRAME_COLUMNS]


def _series_correlation(left: pd.Series, right: pd.Series) -> float:
    joined = pd.concat([pd.to_numeric(left, errors="coerce"), pd.to_numeric(right, errors="coerce")], axis=1).dropna()
    if len(joined) < 2:
        return 0.0
    corr = joined.iloc[:, 0].corr(joined.iloc[:, 1])
    if pd.isna(corr):
        return 0.0
    return float(corr)


def _weighted_mape_frame(
    frame: pd.DataFrame,
    *,
    observed_column: str,
    predicted_column: str,
    weight_column: str,
) -> float:
    if frame.empty:
        return 1.0
    observed = pd.to_numeric(frame[observed_column], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    predicted = pd.to_numeric(frame[predicted_column], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    weights = pd.to_numeric(frame[weight_column], errors="coerce").fillna(1.0).to_numpy(dtype=float)
    denominator = np.maximum(np.abs(observed), 1e-9)
    if weights.sum() <= 1e-12:
        return float(np.mean(np.abs(observed - predicted) / denominator))
    return float(np.average(np.abs(observed - predicted) / denominator, weights=weights))


def _build_labor_validation_artifacts(
    *,
    labor: pd.DataFrame,
    household: pd.DataFrame,
    employment_service: pd.DataFrame,
    macro: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    labor_micro_panel = _aggregate_labor_micro_panel(labor)
    household_panel = _aggregate_household_income_panel(household)
    employment_panel = _aggregate_employment_admin_panel(employment_service)
    macro_panel = _extract_macro_labor_panel(macro)

    validation_panel = labor_micro_panel.merge(
        employment_panel,
        on=["region_code", "period_id"],
        how="outer",
    ).merge(
        household_panel,
        on=["region_code", "period_id"],
        how="left",
    ).merge(
        macro_panel,
        on=["region_code", "period_id"],
        how="left",
    )
    if validation_panel.empty:
        validation_panel = pd.DataFrame(
            columns=[
                "region_code",
                "period_id",
                "micro_participation_rate",
                "micro_employment_rate",
                "micro_informal_employment_rate",
                "micro_sample_weight",
                "micro_respondent_count",
                "admin_employment_count",
                "vacancies",
                "admin_employment_rate_proxy",
                "household_income_mean",
                "household_weight_sum",
                "macro_labor_signal",
            ]
        )

    micro_periods = sorted(labor_micro_panel.get("period_id", pd.Series(dtype="string")).dropna().astype(str).unique().tolist())
    admin_periods = sorted(employment_panel.get("period_id", pd.Series(dtype="string")).dropna().astype(str).unique().tolist())
    micro_regions = sorted(labor_micro_panel.get("region_code", pd.Series(dtype="string")).dropna().astype(str).unique().tolist())
    admin_regions = sorted(employment_panel.get("region_code", pd.Series(dtype="string")).dropna().astype(str).unique().tolist())
    temporal_overlap_periods = sorted(set(micro_periods) & set(admin_periods))
    regional_overlap_codes = sorted(set(micro_regions) & set(admin_regions))
    overlap = validation_panel.dropna(
        subset=["micro_employment_rate", "admin_employment_rate_proxy"],
    ).copy()
    if overlap.empty:
        rationale: list[str] = []
        if not temporal_overlap_periods:
            rationale.append("no_temporal_overlap_between_micro_and_admin_labor_panels")
        if not regional_overlap_codes:
            rationale.append("no_region_overlap_between_micro_and_admin_labor_panels")
        if not rationale:
            rationale.append("no_overlap_between_micro_and_admin_labor_panels")
        report = {
            "schema_version": "1.0",
            "family": ObservationFamily.LABOR_MARKET.value,
            "bias_validated": False,
            "promotion_allowed": False,
            "overlap_rows": 0,
            "employment_correlation": 0.0,
            "employment_wmape": 1.0,
            "macro_correlation": 0.0,
            "micro_period_min": micro_periods[0] if micro_periods else None,
            "micro_period_max": micro_periods[-1] if micro_periods else None,
            "admin_period_min": admin_periods[0] if admin_periods else None,
            "admin_period_max": admin_periods[-1] if admin_periods else None,
            "temporal_overlap_period_count": len(temporal_overlap_periods),
            "regional_overlap_count": len(regional_overlap_codes),
            "rationale": rationale,
        }
        corrected_panel = employment_panel.copy()
        if not corrected_panel.empty:
            corrected_panel["corrected_employment_rate"] = corrected_panel["admin_employment_rate_proxy"]
            corrected_panel["measurement_bias_flag"] = True
            corrected_panel["trust_weight"] = 0.55
        else:
            corrected_panel = pd.DataFrame(
                columns=[
                    "region_code",
                    "period_id",
                    "corrected_employment_rate",
                    "measurement_bias_flag",
                    "trust_weight",
                ]
            )
        return validation_panel, corrected_panel, report

    overlap["validation_weight"] = pd.to_numeric(
        overlap.get("micro_sample_weight", 1.0),
        errors="coerce",
    ).fillna(1.0)
    overlap["correction_factor"] = np.where(
        overlap["admin_employment_rate_proxy"].to_numpy(dtype=float) > 1e-9,
        overlap["micro_employment_rate"].to_numpy(dtype=float)
        / np.maximum(overlap["admin_employment_rate_proxy"].to_numpy(dtype=float), 1e-9),
        1.0,
    )
    overlap["correction_factor"] = np.clip(overlap["correction_factor"], 0.25, 4.0)
    employment_correlation = _series_correlation(
        overlap["micro_employment_rate"],
        overlap["admin_employment_rate_proxy"],
    )
    employment_wmape = _weighted_mape_frame(
        overlap,
        observed_column="micro_employment_rate",
        predicted_column="admin_employment_rate_proxy",
        weight_column="validation_weight",
    )
    macro_overlap = overlap.dropna(subset=["macro_labor_signal"]).copy()
    if not macro_overlap.empty:
        macro_scaled = pd.to_numeric(macro_overlap["macro_labor_signal"], errors="coerce").fillna(0.0)
        macro_scaled = macro_scaled / max(float(macro_scaled.max()), 1.0)
        macro_correlation = _series_correlation(macro_scaled, macro_overlap["micro_employment_rate"])
    else:
        macro_correlation = 0.0

    bias_validated = bool(
        len(overlap) >= 4
        and employment_correlation >= 0.60
        and employment_wmape <= 0.35
        and (macro_correlation >= 0.40 or macro_overlap.empty)
    )

    correction_by_region = overlap.groupby("region_code", as_index=False).agg(
        region_correction_factor=("correction_factor", "median")
    )
    corrected_panel = employment_panel.merge(correction_by_region, on="region_code", how="left")
    corrected_panel["region_correction_factor"] = corrected_panel["region_correction_factor"].fillna(
        float(np.median(overlap["correction_factor"])) if not overlap.empty else 1.0
    )
    corrected_panel["corrected_employment_rate"] = np.clip(
        corrected_panel["admin_employment_rate_proxy"].to_numpy(dtype=float)
        * corrected_panel["region_correction_factor"].to_numpy(dtype=float),
        0.0,
        1.0,
    )
    corrected_panel["measurement_bias_flag"] = not bias_validated
    corrected_panel["trust_weight"] = 0.90 if bias_validated else 0.65

    report = {
        "schema_version": "1.0",
        "family": ObservationFamily.LABOR_MARKET.value,
        "bias_validated": bias_validated,
        "promotion_allowed": bias_validated,
        "overlap_rows": int(len(overlap)),
        "employment_correlation": float(employment_correlation),
        "employment_wmape": float(employment_wmape),
        "macro_correlation": float(macro_correlation),
        "median_correction_factor": float(np.median(overlap["correction_factor"])) if not overlap.empty else 1.0,
        "rationale": (
            ["labor_proxy_promoted_via_bias_validation"]
            if bias_validated
            else ["labor_proxy_remains_proxy_until_bias_validation_improves"]
        ),
    }
    return validation_panel, corrected_panel, report


def build_d3_stage(config: PipelineConfig) -> StageBuildResult:
    """Build D3 household, labor, and distress enrichment artifacts."""

    build_root = config.build_root
    stage_dir = _stage_dir(build_root, StageId.D3)
    ensure_dirs(stage_dir)
    outputs: dict[str, ArtifactRecord] = {}
    warnings: list[str] = []

    household = _load_source_frame(config, "household_microdata")
    labor = _load_source_frame(config, "labor_force_microdata")
    pfu = _load_source_frame(config, "pfu_debt")
    wage = _load_source_frame(config, "wage_arrears")
    distress = _load_source_frame(config, "distress_events")
    employment_service = _load_optional_source_frame(
        config,
        "employment_service",
        columns=["agent_id", "region_code", "period_id", "employment_count", "vacancies"],
    )
    if employment_service is None:
        employment_service = pd.DataFrame(
            columns=["agent_id", "region_code", "period_id", "employment_count", "vacancies"]
        )
    macro = _load_optional_source_frame(
        config,
        "macro_nbu_derzhstat",
        columns=["metric_id", "observed_value", "region_code", "period_id"],
    )
    if macro is None:
        macro = pd.DataFrame(columns=["metric_id", "observed_value", "region_code", "period_id"])

    if household.empty:
        household = pd.DataFrame({"market_income": [100.0], "feature_0": [1.0]})
    household_numeric = household.select_dtypes(include=["number"]).fillna(0.0)
    household_feature_cols = list(household_numeric.columns[:4]) or ["feature_0"]
    household_features = household_numeric[household_feature_cols].to_numpy(dtype=float)
    household_contract = SurveyMicroData(
        market_income=_safe_numeric_series(
            household,
            "market_income" if "market_income" in household.columns else household_feature_cols[0],
        ).to_numpy(dtype=float),
        weights=np.ones(len(household), dtype=float),
        household_ids=np.asarray([f"hh::{idx:05d}" for idx in range(len(household))], dtype=object),
        features=household_features,
        feature_names=household_feature_cols,
        metadata={"stage": "d3"},
    )
    microsim_contract_path = stage_dir / "microsim_survey_contract_v1.json"
    _write_json(microsim_contract_path, household_contract)
    outputs["microsim_survey_contract_v1.json"] = ArtifactRecord.from_path(microsim_contract_path)

    corrected_firms = (
        pfu.assign(selection_term=np.log1p(_safe_numeric_series(pfu, "debt_amount", fill=0.0)))
        .assign(corrected_exit_bias=lambda frame: frame["selection_term"] / (frame["selection_term"].max() or 1.0))
    )
    outputs["corrected_firm_panels.parquet"] = _write_frame(
        stage_dir / "corrected_firm_panels.parquet",
        corrected_firms,
    )

    survival_frame = pd.DataFrame(
        {
            "duration": np.maximum(_safe_numeric_series(distress, "months_to_event", fill=12.0), 1.0),
            "event": (_safe_numeric_series(distress, "event_flag", fill=1.0) > 0.0).astype(int),
            "risk_signal": _safe_numeric_series(pfu.reindex(distress.index), "debt_amount", fill=0.0),
            "wage_arrears": _safe_numeric_series(wage.reindex(distress.index), "arrears_amount", fill=0.0),
        }
    )
    outputs["survival_hazard_estimates.parquet"] = _write_frame(
        stage_dir / "survival_hazard_estimates.parquet",
        survival_frame,
    )

    labor_validation_panel, labor_corrected_panel, labor_bias_validation = _build_labor_validation_artifacts(
        labor=labor,
        household=household,
        employment_service=employment_service,
        macro=macro,
    )
    outputs["labor_validation_panel.parquet"] = _write_frame(
        stage_dir / "labor_validation_panel.parquet",
        labor_validation_panel,
    )
    outputs["labor_market_corrected_panel.parquet"] = _write_frame(
        stage_dir / "labor_market_corrected_panel.parquet",
        labor_corrected_panel,
    )
    labor_bias_validation_path = _write_json(
        stage_dir / "labor_bias_validation.json",
        labor_bias_validation,
    )
    outputs["labor_bias_validation.json"] = ArtifactRecord.from_path(labor_bias_validation_path)

    calibrated_household_cells = _build_calibrated_household_cells(household)
    outputs["calibrated_household_cells.parquet"] = _write_frame(
        stage_dir / "calibrated_household_cells.parquet",
        calibrated_household_cells,
    )

    lesson_registry_path = stage_dir / "lesson_registry_seed_v1.json"
    _write_json(
        lesson_registry_path,
        {
            "schema_version": "1.0",
            "lessons": [
                {
                    "lesson_id": "lesson::data_quality::household_weights",
                    "status": "success",
                    "message": "Household microdata contract generated for server-side calibration.",
                },
                {
                    "lesson_id": "lesson::data_quality::labor_bias_validation",
                    "status": "success" if labor_bias_validation.get("bias_validated") else "warning",
                    "message": (
                        "Labor proxy promoted via bias validation."
                        if labor_bias_validation.get("bias_validated")
                        else "Labor proxy remains provisional until bias validation improves."
                    ),
                },
            ],
        },
    )
    outputs["lesson_registry_seed_v1.json"] = ArtifactRecord.from_path(lesson_registry_path)

    for source_id in ("logistics_mobility_displacement", "land_cadastre"):
        source = config.sources[source_id]
        source_path = config.build_root.normalized_dir / source_id / source.normalized_artifact
        if not source_path.exists():
            skipped_path = _manifest_path(build_root, f"{source_id}_skipped_source_manifest.json")
            _write_json(
                skipped_path,
                {
                    "source_id": source_id,
                    "reason": source.optional_reason or "optional_source_not_configured",
                },
            )
            outputs[skipped_path.name] = ArtifactRecord.from_path(skipped_path)
            warnings.append(f"optional source skipped: {source_id}")

    return StageBuildResult(
        outputs=outputs,
        warnings=warnings,
        metrics={
            "household_rows": len(household),
            "labor_rows": len(labor),
            "distress_rows": len(distress),
            "labor_validation_overlap_rows": int(labor_bias_validation.get("overlap_rows", 0)),
            "labor_bias_validated": bool(labor_bias_validation.get("bias_validated", False)),
        },
        manifest_paths=[lesson_registry_path, labor_bias_validation_path],
    )


def _build_d4_governance_accountability_input(
    *,
    observation_panel: pd.DataFrame,
    calibration_run: CalibrationRunManifest,
    champion: Any,
    holdout_scores: HoldoutScoresManifest,
    transportability: TransportabilitySummaryManifest,
    strategic_metrics: StrategicResponseMetricsManifest,
    data_sources: Sequence[dict[str, Any]],
) -> GovernanceAccountabilityInput:
    """Build the default D4 accountability payload without fabricating probabilistic evidence.

    The production D4 path has rich governance metadata, but not every deployment
    slice exposes calibrated probability vectors. We therefore publish dataset,
    grouping, and limitation metadata explicitly while allowing the accountability
    artifact to mark missing probabilistic surfaces as audit-visible gaps instead
    of silently inventing calibration inputs.
    """

    protected_axes = [
        axis
        for axis in ("region_code", "family", "entity_scope", "source_id")
        if axis in observation_panel.columns and observation_panel[axis].notna().any()
    ]
    source_versions = sorted(
        {
            str(value).strip()
            for value in observation_panel.get("source_version", pd.Series(dtype=str))
            .dropna()
            .astype(str)
            .tolist()
            if str(value).strip()
        }
    )
    known_limitations: list[str] = [
        "Default D4 accountability currently exposes provenance, grouping, and threshold rationale even when calibrated per-row probability outputs are unavailable on the production path.",
        "Fairness-aware calibration slices on the default D4 path rely on deployment metadata axes and should be upgraded to direct protected-group labels before external publication.",
    ]
    if holdout_scores.overall_score < 0.8:
        known_limitations.append(
            "Holdout score remains below the default external-audit comfort band for calibration claims."
        )
    if transportability.aggregate_score < 0.75:
        known_limitations.append(
            "Transportability remains below the preferred D4 accountability band and should be reviewed before promotion."
        )
    if transportability.n_transportable_channels < 3:
        known_limitations.append(
            "Fewer than three transportable channels were established on the default path."
        )
    if strategic_metrics.aggregate_plausibility < 0.75:
        known_limitations.append(
            "Strategic-response plausibility remains below the preferred governance band."
        )
    if str(calibration_run.selected_on_split or "").strip().lower() != "holdout":
        known_limitations.append(
            "Champion was selected on a non-holdout split and then scored on holdout; recalibration evidence should be refreshed after policy changes."
        )

    return GovernanceAccountabilityInput(
        candidate_id=str(getattr(champion, "candidate_id", "") or calibration_run.selected_candidate_id),
        model_name="ukraine_d4_calibration_candidate",
        model_version=str(calibration_run.schema_version),
        intended_use="D4 promotion-gate accountability and external audit review.",
        evaluation_split=str(calibration_run.selected_on_split or "validation"),
        dataset_name="ukraine_observation_panel_monthly",
        dataset_version=(
            None
            if not source_versions
            else source_versions[0]
            if len(source_versions) == 1
            else "mixed"
        ),
        data_sources=sorted(
            {
                str(item.get("name") or "").strip()
                for item in data_sources
                if str(item.get("name") or "").strip()
            }
        ),
        known_limitations=sorted(set(known_limitations)),
        protected_attributes={axis: [] for axis in protected_axes},
        metadata={
            "n_observations": int(len(observation_panel)),
            "used_families": sorted(family.value for family in calibration_run.used_families),
            "selected_on_split": calibration_run.selected_on_split,
            "holdout_score": holdout_scores.overall_score,
            "transportability_score": transportability.aggregate_score,
            "transportable_channels": transportability.n_transportable_channels,
            "strategic_plausibility": strategic_metrics.aggregate_plausibility,
        },
    )


def build_d4_stage(config: PipelineConfig) -> StageBuildResult:
    """Build D4 calibration, backtesting, and governance evidence artifacts."""

    build_root = config.build_root
    stage_dir = _stage_dir(build_root, StageId.D4)
    ensure_dirs(stage_dir)
    outputs: dict[str, ArtifactRecord] = {}
    d0_manifest_path = _manifest_path(build_root, "build_run_d0_p0.json")
    d2_stage_dir = _stage_dir(build_root, StageId.D2)
    d3_stage_dir = _stage_dir(build_root, StageId.D3)
    observation_panel_path = d2_stage_dir / "observation_panel_monthly.parquet"
    observation_panel = _read_parquet_frame(
        observation_panel_path,
        columns=[
            "family",
            "period_start",
            "observed_value",
            "trust_weight",
            "coverage_estimate",
            "measurement_bias_flag",
            "censoring_mask",
            "source_id",
            "identification_mode",
            "source_confidence_tier",
            "proxy_source_id",
            "regime_id",
            "entity_id",
        ],
    )
    calibrated_household_cells_path = d3_stage_dir / "calibrated_household_cells.parquet"
    if calibrated_household_cells_path.exists():
        calibrated_household_cells = _read_parquet_frame(
            calibrated_household_cells_path,
            columns=[
                "cell_id",
                "region_code",
                "period_id",
                "household_income_mean",
                "measurement_bias_flag",
                "trust_weight",
            ],
        )
        household_observation_panel = _build_household_distribution_observation_panel(
            calibrated_household_cells,
        )
        if not household_observation_panel.empty:
            observation_panel = pd.concat(
                [observation_panel, household_observation_panel],
                ignore_index=True,
            )
    observed_abs_mean, observed_head = _stream_parquet_numeric_column_stats(
        observation_panel_path,
        "observed_value",
        head_limit=256,
    )
    splits = json.loads((d2_stage_dir / "calibration_splits.json").read_text(encoding="utf-8"))
    d0_metrics = {}
    if d0_manifest_path.exists():
        d0_metrics = json.loads(d0_manifest_path.read_text(encoding="utf-8")).get("metrics", {})
    spending_coverage = d0_metrics.get("runtime_cohort_coverage_spending")
    procurement_coverage = d0_metrics.get("runtime_cohort_coverage_procurement")
    d4_stage_config = config.stages[StageId.D4.value]
    waived_signoff_families = tuple(d4_stage_config.final_signoff_waived_families)
    labor_bias_validation_path = d3_stage_dir / "labor_bias_validation.json"
    proxy_promoted_families: tuple[ObservationFamily, ...] = ()
    if labor_bias_validation_path.exists():
        labor_bias_validation = json.loads(labor_bias_validation_path.read_text(encoding="utf-8"))
        if labor_bias_validation.get("promotion_allowed"):
            proxy_promoted_families = (ObservationFamily.LABOR_MARKET,)
    blueprint_coverage_threshold = max(
        0.95,
        float(config.stages[StageId.D0_P0.value].coverage_threshold),
    )
    family_eligibility = build_family_eligibility_registry(
        observation_panel,
        coverage_threshold=blueprint_coverage_threshold,
        spending_coverage=spending_coverage,
        procurement_coverage=procurement_coverage,
        waived_families=waived_signoff_families,
        proxy_promoted_families=proxy_promoted_families,
    )
    family_eligibility_path = _write_json(stage_dir / "family_eligibility_registry.json", family_eligibility)
    outputs["family_eligibility_registry.json"] = ArtifactRecord.from_path(family_eligibility_path)
    try:
        family_eligibility.require_final_signoff_ready(REQUIRED_SIGNOFF_FAMILIES)
    except ValueError as exc:
        return StageBuildResult(
            outputs=outputs,
            findings=[
                ValidationFinding(
                    severity="error",
                    code="families_not_exact_signoff_ready",
                    message=str(exc),
                )
            ],
            metrics={
                "blueprint_coverage_threshold": blueprint_coverage_threshold,
                "runtime_cohort_coverage_spending": spending_coverage,
                "runtime_cohort_coverage_procurement": procurement_coverage,
                "tier_a_family_count": len(family_eligibility.eligible_families()),
                "waived_signoff_families": [family.value for family in waived_signoff_families],
                "proxy_promoted_families": [family.value for family in proxy_promoted_families],
            },
            manifest_paths=[family_eligibility_path],
        )

    transportability_runner = TransportabilityRunner()
    transportability = transportability_runner.run(
        observation_panel,
        eligibility_registry=family_eligibility,
    )
    strategic_runner = StrategicResponseRunner()
    strategic_metrics = strategic_runner.run(
        observation_panel,
        eligibility_registry=family_eligibility,
    )
    governance_penalty = _clip_value(1.0 - strategic_metrics.aggregate_plausibility, lower=0.0, upper=1.0)
    interference_report, interference_certificate = build_interference_evidence(
        observation_panel,
        eligibility_registry=family_eligibility,
    )
    calibration_runner = CalibrationRunRunner()
    calibration_run = calibration_runner.run(
        observation_panel,
        eligibility_registry=family_eligibility,
        splits=splits,
        transportability_score=transportability.aggregate_score,
        strategic_plausibility=strategic_metrics.aggregate_plausibility,
        governance_penalty=governance_penalty,
        interference_fit_score=_clip_value(interference_report.effects.total_effect, lower=0.0, upper=1.0),
        required_families=tuple(
            family
            for family in REQUIRED_SIGNOFF_FAMILIES
            if family not in set(waived_signoff_families)
        ),
    )
    champion = next(
        item for item in calibration_run.candidates if item.candidate_id == calibration_run.selected_candidate_id
    )
    holdout_scores = HoldoutScoresManifest(
        candidate_id=champion.candidate_id,
        overall_score=champion.holdout_fit_score or 0.0,
        by_family={
            str(family.value): float(champion.holdout_fit_score or 0.0)
            for family in calibration_run.used_families
        },
        metadata={"selected_on_split": calibration_run.selected_on_split},
    )
    loss_breakdown = LossBreakdownManifest(
        candidate_id=champion.candidate_id,
        measurement_loss=max(0.0, 1.0 - champion.measurement_fit_score),
        network_loss=max(0.0, 1.0 - champion.validation_fit_score),
        interference_loss=max(0.0, 1.0 - champion.interference_fit_score),
        governance_penalty=champion.governance_penalty,
        regularization=champion.robustness_penalty,
    )
    specification_curve = SpecificationCurveRunner().run(
        observation_panel,
        eligibility_registry=family_eligibility,
    )
    cas_store = FileSystemCAS(stage_dir / ".d4_cas")
    candidate_ref = cas_store.put_json(
        champion.model_dump(mode="json"),
        PutOptions(kind="scientist.calibration_candidate", media_type="application/json"),
    )
    candidate_artifact_ref = ArtifactRef.model_validate(candidate_ref)
    observed_sources = sorted(observation_panel.get("source_id", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
    data_sources: list[dict[str, Any]] = []
    for source_id in observed_sources:
        source = config.sources.get(source_id)
        if source is None:
            continue
        source_path = build_root.normalized_dir / source_id / source.normalized_artifact
        last_updated = datetime.utcfromtimestamp(source_path.stat().st_mtime).isoformat() if source_path.exists() else datetime.utcnow().isoformat()
        data_sources.append({"name": source_id, "last_updated": last_updated})
    governance_report = CalibrationGovernanceEvidenceRunner(cas_store).run(
        candidate_ref=candidate_artifact_ref,
        observation_families=calibration_run.used_families,
        eligibility_registry=family_eligibility,
        transportability=transportability,
        strategic=strategic_metrics,
        data_sources=data_sources,
    )
    backtest_bundles = build_required_backtest_bundles(
        observation_panel,
        stage_dir=stage_dir,
        splits=splits,
    )
    validation_runner = CalibrationValidationRunner(cas_store)
    validation_result = validation_runner.run(
        CalibrationValidationRunnerInput(
            run_id="R_d4_real_validation",
            candidate_ref=candidate_artifact_ref,
            governance_report=governance_report,
            calibration_fit_score=champion.validation_composite_score,
            backtest_plan_bundles=backtest_bundles,
            specification_curve_input=specification_curve.to_specification_curve_input(),
            downstream_utility_report=build_downstream_utility_report(
                transportability_score=transportability.aggregate_score,
                strategic_score=strategic_metrics.aggregate_plausibility,
            ),
            transportability_result=transportability.to_transportability_result(),
            network_interference_report=interference_report,
            interference_certificate=interference_certificate,
            strategic_summary=strategic_metrics.strategic_summary,
            baseline_metrics={
                "policy_value": max(observed_abs_mean, 0.1),
                "holdout_score": holdout_scores.overall_score,
            },
            baseline_objective=max(observed_abs_mean, 0.1),
            accountability_input=_build_d4_governance_accountability_input(
                observation_panel=observation_panel,
                calibration_run=calibration_run,
                champion=champion,
                holdout_scores=holdout_scores,
                transportability=transportability,
                strategic_metrics=strategic_metrics,
                data_sources=data_sources,
            ),
        )
    )

    calibration_manifest_path = _write_json(stage_dir / "calibration_run_manifest.json", calibration_run)
    outputs["calibration_run_manifest.json"] = ArtifactRecord.from_path(calibration_manifest_path)
    loss_breakdown_path = _write_json(stage_dir / "loss_breakdown.json", loss_breakdown)
    outputs["loss_breakdown.json"] = ArtifactRecord.from_path(loss_breakdown_path)
    holdout_scores_path = _write_json(stage_dir / "holdout_scores.json", holdout_scores)
    outputs["holdout_scores.json"] = ArtifactRecord.from_path(holdout_scores_path)
    shock_scores_path = _write_json(stage_dir / "shock_scenario_scores.json", validation_result.bundle.stress_scenarios)
    outputs["shock_scenario_scores.json"] = ArtifactRecord.from_path(shock_scores_path)
    if validation_result.bundle.governance_accountability_ref is not None:
        accountability_artifact = load_governance_accountability_artifact(
            cas_store,
            validation_result.bundle.governance_accountability_ref,
        )
        accountability_path = _write_json(
            stage_dir / "governance_accountability.json",
            accountability_artifact,
        )
        outputs["governance_accountability.json"] = ArtifactRecord.from_path(
            accountability_path
        )
    leaderboard_path = _write_json(
        stage_dir / "calibration_leaderboard.json",
        {
            "selected_candidate_id": calibration_run.selected_candidate_id,
            "candidates": [item.model_dump(mode="json") for item in calibration_run.candidates],
            "leaderboard_entry": (
                None
                if validation_result.bundle.leaderboard_entry is None
                else validation_result.bundle.leaderboard_entry.model_dump(mode="json")
            ),
            "governance_verdict": governance_report.resolved_verdict(),
        },
    )
    outputs["calibration_leaderboard.json"] = ArtifactRecord.from_path(leaderboard_path)
    transportability_path = _write_json(stage_dir / "transportability_results.json", transportability)
    outputs["transportability_results.json"] = ArtifactRecord.from_path(transportability_path)
    strategic_metrics_path = _write_json(stage_dir / "strategic_response_metrics.json", strategic_metrics)
    outputs["strategic_response_metrics.json"] = ArtifactRecord.from_path(strategic_metrics_path)
    specification_curve_path = _write_json(stage_dir / "specification_curve_summary.json", specification_curve)
    outputs["specification_curve_summary.json"] = ArtifactRecord.from_path(specification_curve_path)
    outputs["foundry_seed_state_v1.npz"] = _write_npz(stage_dir / "foundry_seed_state_v1.npz", values=observed_head)
    replay_artifacts_path = _write_json(
        stage_dir / "replay_artifacts.json",
        {
            "schema_version": "1.0",
            "calibration_validation_bundle_ref": str(validation_result.bundle_ref.artifact_id),
            "backtest_report_ref": (
                None
                if validation_result.bundle.backtest_report_ref is None
                else str(validation_result.bundle.backtest_report_ref.artifact_id)
            ),
            "stress_test_report_ref": (
                None
                if validation_result.bundle.stress_test_report_ref is None
                else str(validation_result.bundle.stress_test_report_ref.artifact_id)
            ),
        },
    )
    outputs["replay_artifacts.json"] = ArtifactRecord.from_path(replay_artifacts_path)
    governance_report_path = _write_json(stage_dir / "governance_report_v1.json", governance_report)
    outputs["governance_report_v1.json"] = ArtifactRecord.from_path(governance_report_path)
    lesson_registry_path = _write_json(
        stage_dir / "lesson_registry_d4.json",
        {
            "schema_version": "1.0",
            "lessons": [
                {
                    "lesson_id": "d4::leaderboard",
                    "status": "success",
                    "message": f"Champion {calibration_run.selected_candidate_id} selected on validation split and scored once on holdout.",
                },
                {
                    "lesson_id": "d4::governance",
                    "status": governance_report.resolved_verdict(),
                    "message": f"Calibration governance verdict: {governance_report.resolved_verdict()}",
                },
            ],
        },
    )
    outputs["lesson_registry_d4.json"] = ArtifactRecord.from_path(lesson_registry_path)

    findings: list[ValidationFinding] = []
    if len(backtest_bundles) != len(BacktestKind):
        findings.append(
            ValidationFinding(
                severity="error",
                code="missing_required_backtests",
                message="D4 requires all 5 backtest kinds to be materialized from D2 outputs",
            )
        )
    if validation_result.bundle.stress_scenarios is None or len(validation_result.bundle.stress_scenarios.comparisons) != 6:
        findings.append(
            ValidationFinding(
                severity="error",
                code="missing_required_stress_scenarios",
                message="D4 requires all 6 canonical stress scenarios",
            )
        )
    if transportability.n_transportable_channels < 3:
        findings.append(
            ValidationFinding(
                severity="error",
                code="insufficient_transportable_channels",
                message="D4 requires at least 3 transportable channels for exact sign-off",
            )
        )
    required_strategic_channels = StrategicResponseRunner.required_channel_count(
        waived_families=waived_signoff_families,
    )
    if strategic_metrics.quantified_channels < required_strategic_channels:
        findings.append(
            ValidationFinding(
                severity="error",
                code="insufficient_strategic_channels",
                message=(
                    "D4 requires at least "
                    f"{required_strategic_channels} quantified strategic-response channels "
                    "after applying current signoff waivers"
                ),
            )
        )
    if specification_curve.robustness_score < 0.6:
        findings.append(
            ValidationFinding(
                severity="error",
                code="specification_curve_below_threshold",
                message="D4 specification-curve robustness is below the blueprint threshold",
            )
        )
    if governance_report.resolved_verdict() != "approve":
        findings.append(
            ValidationFinding(
                severity="error",
                code="governance_not_approved",
                message="D4 governance evidence did not resolve to approve",
            )
        )

    return StageBuildResult(
        outputs=outputs,
        findings=findings,
        metrics={
            "blueprint_coverage_threshold": blueprint_coverage_threshold,
            "tier_a_family_count": len(family_eligibility.eligible_families()),
            "transportable_channels": transportability.n_transportable_channels,
            "quantified_strategic_channels": strategic_metrics.quantified_channels,
            "required_strategic_channels": required_strategic_channels,
            "waived_signoff_families": [family.value for family in waived_signoff_families],
            "proxy_promoted_families": [family.value for family in proxy_promoted_families],
            "governance_verdict": governance_report.resolved_verdict(),
            "holdout_score": holdout_scores.overall_score,
        },
        manifest_paths=[calibration_manifest_path],
    )


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
    if calibrated_households is not None and not calibrated_households.empty and "cell_id" in calibrated_households.columns:
        household_features = calibrated_households.copy()
        household_features = household_features.groupby("cell_id", as_index=False).mean(numeric_only=True)
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
    holdout_score: float,
    transportability_score: float,
    strategic_score: float,
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
        src_ids = np.asarray(arrays.get("src_ids", np.asarray([], dtype=object)), dtype=object).astype(str)
        dst_ids = np.asarray(arrays.get("dst_ids", np.asarray([], dtype=object)), dtype=object).astype(str)
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
            grouped.groupby("src_group")["weight"].sum().abs()
            + grouped.groupby("dst_group")["weight"].sum().abs()
        ).groupby(level=0).sum()
        compressed_group_degree = (
            compressed.groupby("src_group")["weight"].sum().abs()
            + compressed.groupby("dst_group")["weight"].sum().abs()
        ).groupby(level=0).sum()
        all_groups = sorted(set(original_group_degree.index).union(set(compressed_group_degree.index)))
        original_vector = np.asarray([float(original_group_degree.get(group, 0.0)) for group in all_groups], dtype=float)
        compressed_vector = np.asarray([float(compressed_group_degree.get(group, 0.0)) for group in all_groups], dtype=float)
        total_degree = max(float(np.abs(original_vector).sum()), 1e-9)
        degree_preservation = max(
            0.0,
            1.0 - float(np.abs(original_vector - compressed_vector).sum() / total_degree),
        )
        total_original_weight = max(float(np.abs(weights).sum()), 1e-9)
        total_compressed_weight = float(np.abs(compressed["weight"].to_numpy(dtype=float)).sum())
        weight_error = float(abs(total_original_weight - total_compressed_weight) / total_original_weight)
        top_original = set(
            grouped.groupby("src_group")["weight"].sum().abs().sort_values(ascending=False).head(10).index.tolist()
        )
        top_compressed = set(
            compressed.groupby("src_group")["weight"].sum().abs().sort_values(ascending=False).head(10).index.tolist()
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
                "n_original_edges": int(len(weights)),
                "n_compressed_edges": int(len(compressed)),
                "n_supernodes": int(len(all_groups)),
                "degree_preservation_score": degree_preservation,
                "edge_weight_reconstruction_error": weight_error,
                "neighborhood_overlap_stability": neighborhood_overlap,
            }
        )
    aggregate_degree = float(np.mean(degree_preservation_scores)) if degree_preservation_scores else 1.0
    aggregate_weight_error = float(np.mean(weight_errors)) if weight_errors else 0.0
    aggregate_overlap = float(np.mean(overlap_scores)) if overlap_scores else 1.0
    downstream_stability = max(
        0.0,
        min(
            1.0,
            (0.45 * holdout_score)
            + (0.3 * transportability_score)
            + (0.25 * strategic_score)
            - (0.2 * aggregate_weight_error),
        ),
    )
    return {
        "schema_version": "1.0",
        "method": "deterministic_spectral_factor_with_cell_coarsening",
        "layers": layer_payloads,
        "fidelity_metrics": {
            "degree_preservation_score": aggregate_degree,
            "edge_weight_reconstruction_error": aggregate_weight_error,
            "neighborhood_overlap_stability": aggregate_overlap,
            "downstream_policy_response_stability": downstream_stability,
        },
    }


def _build_release_intervention_payloads(
    *,
    cell_registry: pd.DataFrame,
    transportability: TransportabilitySummaryManifest,
    strategic_metrics: StrategicResponseMetricsManifest,
    specification_curve: SpecificationCurveSummaryManifest,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], pd.DataFrame, dict[str, Any]]:
    compiler = LexInterventionCompiler()
    sequencer = TemporalInterventionSequencer()
    primary_region = _safe_first(cell_registry.get("region_code", pd.Series(dtype=str)), "00")
    primary_sector = _safe_first(cell_registry.get("sector_id", pd.Series(dtype=str)), "unknown")
    procurement_directive = LexProvisionDirective(
        provision_ref="lex.ua.procurement.priority_v1",
        intervention_id="procurement_policy",
        intervention_kind="procurement_policy",
        target=SelectorPredicate(field="id", operator=SelectorOperator.EQUALS, value="all"),
        schedule=ScheduleSpec(start_step=0, duration_steps=6),
        params={
            "intensity": Decimal("0.15"),
            "supplier_share_cap": Decimal("0.35"),
        },
        knobs=[
            InterventionKnobSpec(
                param_id="procurement_intensity",
                param_path="intensity",
                default_value=Decimal("0.15"),
                min_value=Decimal("0.05"),
                max_value=Decimal("0.35"),
                sensitivity_priority=2,
            ),
            InterventionKnobSpec(
                param_id="supplier_share_cap",
                param_path="supplier_share_cap",
                default_value=Decimal("0.35"),
                min_value=Decimal("0.15"),
                max_value=Decimal("0.50"),
                sensitivity_priority=3,
            ),
        ],
        target_population_type="firms",
        target_sector_ids=[primary_sector],
        target_region_ids=[primary_region],
        measurement_expectations={
            "transportability_score": transportability.aggregate_score,
            "strategic_plausibility": strategic_metrics.aggregate_plausibility,
        },
        identification_mode=IdentificationMode.INTERFERENCE_AWARE,
        strategic_response_expected=True,
        transmission_channels=[StrategicResponseChannel.PROCUREMENT_CHANNEL],
        notes=["compiled_from_real_release_data"],
        metadata={"governance_tags": ["procurement", "interference"]},
    )
    wage_directive = LexProvisionDirective(
        provision_ref="lex.ua.wage_support.v1",
        intervention_id="wage_subsidy_support",
        intervention_kind="wage_subsidy",
        target=SelectorPredicate(field="id", operator=SelectorOperator.EQUALS, value="all"),
        schedule=ScheduleSpec(start_step=0, duration_steps=4),
        params={
            "subsidy_rate": Decimal("0.10"),
            "employment_floor": Decimal("0.85"),
        },
        knobs=[
            InterventionKnobSpec(
                param_id="subsidy_rate",
                param_path="subsidy_rate",
                default_value=Decimal("0.10"),
                min_value=Decimal("0.02"),
                max_value=Decimal("0.20"),
                sensitivity_priority=2,
            ),
            InterventionKnobSpec(
                param_id="employment_floor",
                param_path="employment_floor",
                default_value=Decimal("0.85"),
                min_value=Decimal("0.70"),
                max_value=Decimal("0.98"),
                sensitivity_priority=4,
            ),
        ],
        target_population_type="employment_support",
        target_sector_ids=[primary_sector],
        target_region_ids=[primary_region],
        measurement_expectations={
            "specification_curve_robustness": specification_curve.robustness_score,
            "strategic_plausibility": strategic_metrics.aggregate_plausibility,
        },
        identification_mode=IdentificationMode.SEQUENTIAL,
        strategic_response_expected=True,
        transmission_channels=[
            StrategicResponseChannel.LABOR_CHANNEL,
            StrategicResponseChannel.HOUSEHOLD_INCOME_CHANNEL,
        ],
        notes=["compiled_from_real_release_data"],
        metadata={"governance_tags": ["labor", "household_income"]},
    )
    compiled_procurement = compiler.compile(procurement_directive)
    compiled_wage = compiler.compile(wage_directive)
    procurement_sequence = sequencer.compile_sequence(
        sequence_id="procurement_policy_sequence",
        dynamic_intervention_id="procurement_policy_program",
        compiled_interventions=[compiled_procurement],
        strategic_response_expected=True,
        transmission_channels=[StrategicResponseChannel.PROCUREMENT_CHANNEL],
        steps=[
            {
                "effective_date": "2025-01",
                "intervention_id": compiled_procurement.intervention.intervention_id,
                "parameter_overrides": {"procurement_intensity": Decimal("0.12")},
            },
            {
                "effective_date": "2025-04",
                "intervention_id": compiled_procurement.intervention.intervention_id,
                "parameter_overrides": {"procurement_intensity": Decimal("0.18")},
            },
        ],
    )
    wage_sequence = sequencer.compile_sequence(
        sequence_id="wage_subsidy_support_sequence",
        dynamic_intervention_id="wage_subsidy_support_program",
        compiled_interventions=[compiled_wage],
        strategic_response_expected=True,
        transmission_channels=[
            StrategicResponseChannel.LABOR_CHANNEL,
            StrategicResponseChannel.HOUSEHOLD_INCOME_CHANNEL,
        ],
        steps=[
            {
                "effective_date": "2025-01",
                "intervention_id": compiled_wage.intervention.intervention_id,
                "parameter_overrides": {"subsidy_rate": Decimal("0.08")},
            },
            {
                "effective_date": "2025-03",
                "intervention_id": compiled_wage.intervention.intervention_id,
                "parameter_overrides": {"subsidy_rate": Decimal("0.12")},
            },
        ],
    )
    intervention_map = {
        "schema_version": "1.0",
        "directives": [
            {
                "provision_ref": procurement_directive.provision_ref,
                "intervention": compiled_procurement.intervention.model_dump(mode="json"),
                "eligible_target_population": procurement_directive.target_population_type,
                "constraint_set": {
                    "region_ids": procurement_directive.target_region_ids,
                    "sector_ids": procurement_directive.target_sector_ids,
                },
                "governance_tags": procurement_directive.metadata.get("governance_tags", []),
            },
            {
                "provision_ref": wage_directive.provision_ref,
                "intervention": compiled_wage.intervention.model_dump(mode="json"),
                "eligible_target_population": wage_directive.target_population_type,
                "constraint_set": {
                    "region_ids": wage_directive.target_region_ids,
                    "sector_ids": wage_directive.target_sector_ids,
                },
                "governance_tags": wage_directive.metadata.get("governance_tags", []),
            },
        ],
    }
    knob_dictionary = {
        "schema_version": "1.0",
        "knobs": {
            parameter.param_id: parameter.model_dump(mode="json")
            for parameter in [*compiled_procurement.parameters, *compiled_wage.parameters]
        },
    }
    temporal_sequences = {
        "schema_version": "1.0",
        "sequences": {
            procurement_sequence.sequence_id: procurement_sequence.model_dump(mode="json"),
            wage_sequence.sequence_id: wage_sequence.model_dump(mode="json"),
        },
    }
    scenario_templates = {
        "schema_version": "1.0",
        "templates": [
            {
                "scenario_id": "procurement_resilience",
                "intervention_id": compiled_procurement.intervention.intervention_id,
                "sequence_id": procurement_sequence.sequence_id,
                "objective": "procurement continuity under targeted supplier concentration limits",
                "eligibility_tier_required": "A",
            },
            {
                "scenario_id": "wage_subsidy_resilience",
                "intervention_id": compiled_wage.intervention.intervention_id,
                "sequence_id": wage_sequence.sequence_id,
                "objective": "employment stabilization with household-income support",
                "eligibility_tier_required": "A",
            },
        ],
    }
    crosswalk = pd.DataFrame(
        {
            "provision_id": [procurement_directive.provision_ref, wage_directive.provision_ref],
            "program_id": ["program.procurement_resilience", "program.wage_support"],
            "channel_id": ["procurement_policy", "wage_subsidy_support"],
        }
    )

    procurement_grid = [Decimal("0.08"), Decimal("0.12"), Decimal("0.16")]
    wage_grid = [Decimal("0.06"), Decimal("0.10"), Decimal("0.14")]
    procurement_trials = []
    for intensity in procurement_grid:
        score = float(
            (0.5 * transportability.aggregate_score)
            + (0.3 * strategic_metrics.aggregate_plausibility)
            + (0.2 * specification_curve.robustness_score)
            - (0.4 * abs(float(intensity) - 0.12))
        )
        procurement_trials.append({"intensity": str(intensity), "objective_score": score})
    wage_trials = []
    for rate in wage_grid:
        score = float(
            (0.45 * transportability.aggregate_score)
            + (0.35 * strategic_metrics.aggregate_plausibility)
            + (0.2 * specification_curve.robustness_score)
            - (0.5 * abs(float(rate) - 0.10))
        )
        wage_trials.append({"subsidy_rate": str(rate), "objective_score": score})
    best_procurement = max(procurement_trials, key=lambda item: item["objective_score"])
    best_wage = max(wage_trials, key=lambda item: item["objective_score"])
    advanced_trials = {
        "schema_version": "1.0",
        "hierarchical_policy_search": {
            "pilot_questions": [
                {
                    "policy_channel": "procurement_policy",
                    "best_candidate": best_procurement,
                    "candidate_grid": procurement_trials,
                },
                {
                    "policy_channel": "wage_subsidy_support",
                    "best_candidate": best_wage,
                    "candidate_grid": wage_trials,
                },
            ]
        },
        "active_disambiguation": {
            "value_of_information_signals": [
                {
                    "question_id": "procurement_proxy_bias",
                    "priority": round(1.0 - transportability.aggregate_score, 6),
                },
                {
                    "question_id": "strategic_response_strength",
                    "priority": round(1.0 - strategic_metrics.aggregate_plausibility, 6),
                },
            ],
            "recommended_next_question": (
                "procurement_proxy_bias"
                if transportability.aggregate_score <= strategic_metrics.aggregate_plausibility
                else "strategic_response_strength"
            ),
        },
        "bilevel_procurement_trial": {
            "outer_objective": "maximize_procurement_continuity",
            "inner_constraint": "supplier_share_cap",
            "selected_candidate": best_procurement,
        },
        "interference_aware_calibration_term": {
            "term_value": round(
                (0.5 * transportability.aggregate_score) + (0.5 * strategic_metrics.aggregate_plausibility),
                6,
            ),
            "depends_on": ["procurement_network", "budget_network"],
        },
    }
    return (
        intervention_map,
        knob_dictionary,
        temporal_sequences,
        scenario_templates,
        crosswalk,
        advanced_trials,
    )


def _build_acceptance_trinity_bundle() -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="ukraine_release_acceptance",
            domain=ProblemDomain.FISCAL,
        ),
        policy_spec=PolicySpec(
            policy_id="ukraine_release_acceptance_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="acceptance_tax_probe",
                    kind="income_tax",
                    target=SelectorPredicate(
                        field="id",
                        operator=SelectorOperator.EQUALS,
                        value="all",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": Decimal("0.05")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="ukraine_release_acceptance_model",
            data_snapshot_ref="sha256:" + ("0" * 64),
            registry_bundle_ref="sha256:" + ("0" * 64),
        ),
    )


def build_d5_stage(config: PipelineConfig) -> StageBuildResult:
    """Build D5 embeddings, intervention artifacts, and final release bundle."""

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
    holdout_scores = HoldoutScoresManifest.model_validate_json(
        (d4_stage / "holdout_scores.json").read_text(encoding="utf-8")
    )
    transportability = TransportabilitySummaryManifest.model_validate_json(
        (d4_stage / "transportability_results.json").read_text(encoding="utf-8")
    )
    strategic_metrics = StrategicResponseMetricsManifest.model_validate_json(
        (d4_stage / "strategic_response_metrics.json").read_text(encoding="utf-8")
    )
    specification_curve = SpecificationCurveSummaryManifest.model_validate_json(
        (d4_stage / "specification_curve_summary.json").read_text(encoding="utf-8")
    )
    d4_manifest = CalibrationRunManifest.model_validate_json(
        (d4_stage / "calibration_run_manifest.json").read_text(encoding="utf-8")
    )
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
        holdout_score=holdout_scores.overall_score,
        transportability_score=transportability.aggregate_score,
        strategic_score=strategic_metrics.aggregate_plausibility,
    )
    outputs["graph_compression_bundle.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "graph_compression_bundle.json", graph_compression_bundle)
    )
    (
        intervention_map,
        knob_dictionary,
        temporal_sequences,
        policy_scenario_templates,
        provision_crosswalk,
        advanced_policy_trials,
    ) = _build_release_intervention_payloads(
        cell_registry=cell_registry,
        transportability=transportability,
        strategic_metrics=strategic_metrics,
        specification_curve=specification_curve,
    )
    outputs["lex_intervention_map.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "lex_intervention_map.json", intervention_map)
    )
    outputs["intervention_knob_dictionary.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "intervention_knob_dictionary.json", knob_dictionary)
    )
    outputs["temporal_intervention_sequences.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "temporal_intervention_sequences.json", temporal_sequences)
    )
    outputs["policy_scenario_templates.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "policy_scenario_templates.json", policy_scenario_templates)
    )
    outputs["provision_to_program_crosswalk.parquet"] = _write_frame(
        stage_dir / "provision_to_program_crosswalk.parquet",
        provision_crosswalk,
    )
    outputs["advanced_policy_trials.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "advanced_policy_trials.json", advanced_policy_trials)
    )

    release_dirs = {
        "runtime_bundle_v1": stage_dir / "runtime_bundle_v1",
        "calibration_bundle_v1": stage_dir / "calibration_bundle_v1",
        "method_contract_bundle_v1": stage_dir / "method_contract_bundle_v1",
        "governance_report_v1": stage_dir / "governance_report_v1",
        "intervention_bundle_v1": stage_dir / "intervention_bundle_v1",
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
            d4_stage / "calibration_run_manifest.json",
            d4_stage / "holdout_scores.json",
        ],
        "method_contract_bundle_v1": [
            calibration_stage / "observation_to_contract_manifest.json",
            calibration_stage / "network_contract_bundle_v1.json",
            calibration_stage / "network_causal_contract_bundle_v1.json",
            calibration_stage / "bounds_estimation_bundle_v1.json",
            calibration_stage / "backtest_plan_bundle.json",
            stage_dir / "acceptance_contract_bundle.json",
        ],
        "governance_report_v1": [
            d4_stage / "governance_report_v1.json",
            d4_stage / "governance_accountability.json",
            d4_stage / "shock_scenario_scores.json",
            d4_stage / "calibration_leaderboard.json",
            d4_stage / "transportability_results.json",
            d4_stage / "strategic_response_metrics.json",
        ],
        "intervention_bundle_v1": [
            stage_dir / "lex_intervention_map.json",
            stage_dir / "intervention_knob_dictionary.json",
            stage_dir / "temporal_intervention_sequences.json",
            stage_dir / "policy_scenario_templates.json",
            stage_dir / "provision_to_program_crosswalk.parquet",
            stage_dir / "advanced_policy_trials.json",
        ],
        "embedding_bundle_v1": [
            stage_dir / "agent_embedding_32d.npz",
            stage_dir / "cell_prototype_embeddings.npz",
            stage_dir / "graph_compression_bundle.json",
        ],
    }
    acceptance_contract_path = stage_dir / "acceptance_contract_bundle.json"
    _write_json(acceptance_contract_path, _build_acceptance_trinity_bundle())
    for bundle_name, sources in copy_plan.items():
        for source_path in sources:
            if source_path.exists():
                shutil.copy2(source_path, release_dirs[bundle_name] / source_path.name)

    bundle_records = {
        bundle_name: ArtifactRecord(path=str(path), size_bytes=directory_size_bytes(path))
        for bundle_name, path in release_dirs.items()
    }
    bundle_contents = {
        bundle_name: _bundle_content_records(path)
        for bundle_name, path in release_dirs.items()
    }
    release_manifest = ReleaseManifest(
        bundles=bundle_records,
        bundle_contents=bundle_contents,
        metrics={
            "runtime_bundle_size_gib": _directory_file_size_gib(release_dirs["runtime_bundle_v1"]),
            "calibration_bundle_size_gib": _directory_file_size_gib(release_dirs["calibration_bundle_v1"]),
            "contract_bundle_size_gib": _directory_file_size_gib(release_dirs["method_contract_bundle_v1"]),
            "compression_degree_preservation_score": graph_compression_bundle["fidelity_metrics"]["degree_preservation_score"],
            "compression_edge_weight_reconstruction_error": graph_compression_bundle["fidelity_metrics"]["edge_weight_reconstruction_error"],
            "compression_neighborhood_overlap_stability": graph_compression_bundle["fidelity_metrics"]["neighborhood_overlap_stability"],
            "compression_policy_response_stability": graph_compression_bundle["fidelity_metrics"]["downstream_policy_response_stability"],
            "selected_calibration_candidate_id": d4_manifest.selected_candidate_id,
        },
        validation=[],
        lineage={
            "runtime_manifest": str(runtime_stage / "runtime_bundle_manifest.json"),
            "calibration_manifest": str(calibration_stage / "calibration_bundle_manifest.json"),
            "d4_manifest": str(d4_stage / "calibration_run_manifest.json"),
            "governance_report": str(d4_stage / "governance_report_v1.json"),
            "replay_artifacts": str(d4_stage / "replay_artifacts.json"),
            "acceptance_contract_bundle": str(release_dirs["method_contract_bundle_v1"] / "acceptance_contract_bundle.json"),
        },
    )
    release_manifest_path = stage_dir / "release_manifest_v1.json"
    write_manifest(release_manifest_path, release_manifest)
    release_store = FileSystemCAS(stage_dir / ".release_cas")
    acceptance_runner = ReleaseAcceptanceRunner(release_store)
    acceptance_report = acceptance_runner.run(
        release_manifest_path=release_manifest_path,
        runtime_bundle_dir=release_dirs["runtime_bundle_v1"],
        method_contract_bundle_dir=release_dirs["method_contract_bundle_v1"],
    )
    acceptance_report_path = _write_json(stage_dir / "release_acceptance_report.json", acceptance_report)
    outputs["release_acceptance_report.json"] = ArtifactRecord.from_path(acceptance_report_path)

    evidence_refs = {
        "calibration_run_manifest": ArtifactRecord.from_path(d4_stage / "calibration_run_manifest.json"),
        "governance_report": ArtifactRecord.from_path(d4_stage / "governance_report_v1.json"),
        "replay_artifacts": ArtifactRecord.from_path(d4_stage / "replay_artifacts.json"),
        "release_acceptance_report": ArtifactRecord.from_path(acceptance_report_path),
    }
    findings: list[ValidationFinding] = []
    if not acceptance_report.passed:
        findings.append(
            ValidationFinding(
                severity="error",
                code="release_acceptance_failed",
                message="release bundle failed the canonical acceptance roundtrip",
            )
        )
    if float(graph_compression_bundle["fidelity_metrics"]["degree_preservation_score"]) < 0.85:
        findings.append(
            ValidationFinding(
                severity="error",
                code="compression_degree_preservation_below_threshold",
                message="graph compression degree preservation fell below the minimum release threshold",
            )
        )
    if float(graph_compression_bundle["fidelity_metrics"]["edge_weight_reconstruction_error"]) > 0.15:
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
            "evidence_refs": evidence_refs,
            "lineage": {
                **release_manifest.lineage,
                "release_acceptance_report": str(acceptance_report_path),
            },
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
        manifest_paths=[release_manifest_path, acceptance_report_path],
    )


STAGE_BUILDERS: dict[StageId, Callable[[PipelineConfig], StageBuildResult]] = {
    StageId.D0_P0: build_d0_p0_stage,
    StageId.D1: build_d1_stage,
    StageId.D2: build_d2_stage,
    StageId.D3: build_d3_stage,
    StageId.D4: build_d4_stage,
    StageId.D5: build_d5_stage,
}


__all__ = [
    "MemoryAwareScheduler",
    "ScheduledTask",
    "STAGE_BUILDERS",
    "StageBuildResult",
    "build_d0_p0_stage",
    "build_d1_stage",
    "build_d2_stage",
    "build_d3_stage",
    "build_d4_stage",
    "build_d5_stage",
]
