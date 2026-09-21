"""Canonical domain I/O helpers for Ukraine stage builders.

The helpers in this module own the serialization and source-selection boundary
for the Ukraine builders.  JSON keeps the legacy deterministic serializer,
while JSON publication uses the Data Forge kernel's atomic text writer.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from pydantic import BaseModel

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.data_forge.domains.ukraine.manifests import ArtifactRecord
from polisyos.data_forge.domains.ukraine.models import BuildRootConfig, PipelineConfig, StageId
from polisyos.data_forge.kernel.io import atomic_write_bytes, atomic_write_text, ensure_dirs

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.core.artifacts.manifest import ArtifactRef


def _json_default(value: object) -> object:
    """Convert domain values to the legacy JSON-compatible representation."""
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


def _write_json(path: Path, payload: object) -> Path:
    """Write a deterministic domain JSON document atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    text = json.dumps(
        serialized,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        default=_json_default,
    )
    return atomic_write_text(path, text)


def _write_protocol_json(path: Path, payload: BaseModel) -> ArtifactRecord:
    """Write a protocol model and return its content-addressed artifact record."""
    _write_json(path, payload)
    return ArtifactRecord.from_path(path)


def _write_frame(path: Path, frame: pd.DataFrame) -> ArtifactRecord:
    """Write a Parquet frame using the established domain profile."""
    ensure_dirs(path.parent)
    frame.to_parquet(path, index=False)
    return ArtifactRecord.from_path(path, row_count=len(frame))


def _write_npz(path: Path, **arrays: object) -> ArtifactRecord:
    """Write a compressed NumPy artifact and record its non-zero count."""
    buffer = BytesIO()
    np.savez_compressed(buffer, **arrays)
    atomic_write_bytes(path, buffer.getvalue())
    nnz = None
    if "weight" in arrays:
        weight = np.asarray(arrays["weight"])
        nnz = int(np.count_nonzero(weight))
    elif "adjacency" in arrays:
        adjacency = np.asarray(arrays["adjacency"])
        nnz = int(np.count_nonzero(adjacency))
    return ArtifactRecord.from_path(path, nnz=nnz)


def _manifest_path(build_root: BuildRootConfig, name: str) -> Path:
    """Resolve a build manifest path."""
    return build_root.manifests_dir / name


def _stage_dir(build_root: BuildRootConfig, stage_id: StageId) -> Path:
    """Resolve the canonical output directory for a stage."""
    if stage_id in {StageId.D0_P0, StageId.D1}:
        return build_root.runtime_dir / stage_id.value
    if stage_id in {StageId.D2, StageId.D3, StageId.D4}:
        return build_root.calibration_dir / stage_id.value
    return build_root.bundles_dir / stage_id.value


def _read_parquet_frame(path: Path, *, columns: Sequence[str] | None = None) -> pd.DataFrame:
    """Read a Parquet frame, selecting only available requested columns."""
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
    """Read numeric Parquet statistics in batches when the native backend allows it."""
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
    """Return the size of direct files in a bundle directory in GiB."""
    total_bytes = sum(item.stat().st_size for item in path.iterdir() if item.is_file())
    return total_bytes / (1024**3)


def _load_source_frame(
    config: PipelineConfig,
    source_id: str,
    *,
    columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Load one required normalized source artifact."""
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
    """Load one optional normalized source artifact when configured and present."""
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
    """Select the preferred procurement source and preserve diagnostics."""
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


def _cas_put_json(store: FileSystemCAS, payload: object, *, kind: str) -> ArtifactRef:
    """Persist JSON through the existing CAS canonicalization contract."""
    return store.put_json(
        payload,
        PutOptions(kind=kind, media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )


__all__ = ()
