"""Write and index world fact segments that bridge emission and materialization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.fabric.fact_writer import write_fact_segment
from polisyos.fabric.io.atomic import append_text_locked, atomic_write_text, file_lock
from polisyos.fabric.observability import FABRIC_TRACE_NAMES
from polisyos.fabric.temporal import parse_datetime_utc
from polisyos.fabric.world.providers import resolve_world_observability
from polisyos.ir.fact_log import Fact, FactSegmentManifest
from polisyos.ir.kernel.base import ID_PATTERN

if TYPE_CHECKING:
    from collections.abc import Iterable

    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer

from .errors import WorldSegmentError

logger = get_logger(__name__)

SEGMENTS_INDEX_NAME = "_segments.jsonl"
SEGMENTS_INDEX_LOCK_NAME = "_segments.lock"

_ID_RE = re.compile(ID_PATTERN)


@dataclass(frozen=True)
class WorldSegmentGCReport:
    """Outcome of world segment retention and garbage collection."""

    retained_segment_ids: tuple[str, ...]
    deleted_segment_ids: tuple[str, ...]
    dry_run: bool = False


def _segment_manifest_sidecar_path(manifest: FactSegmentManifest) -> Path:
    segment_path = Path(manifest.path)
    return segment_path.with_name(f"{segment_path.stem}_manifest.json")


def _write_world_fact_index(
    fact_log_root: Path,
    manifests: Iterable[FactSegmentManifest],
) -> list[FactSegmentManifest]:
    manifest_list = list(manifests)
    index_path = fact_log_root / "world" / SEGMENTS_INDEX_NAME
    lock_path = fact_log_root / "world" / SEGMENTS_INDEX_LOCK_NAME
    payload = "".join(manifest.model_dump_json() + "\n" for manifest in manifest_list)
    with file_lock(lock_path):
        atomic_write_text(index_path, payload)
    return manifest_list


def _normalize_segment_name(segment_name: str) -> str:
    value = segment_name.strip().lower()
    value = re.sub(r"[^a-z0-9_.-]+", "_", value)
    value = value.strip("_-. ")
    if not value:
        value = "segment"
    if not re.match(r"^[a-z]", value):
        value = f"seg_{value}"
    if _ID_RE.fullmatch(value) is None:
        value = re.sub(r"[^a-z0-9_.-]+", "_", value)
        if not value or _ID_RE.fullmatch(value) is None:
            value = "segment"
    return value


def _dedup_facts(facts: Iterable[Fact]) -> list[Fact]:
    seen: set[str] = set()
    deduped: list[Fact] = []
    for fact in facts:
        if fact.fact_id in seen:
            continue
        seen.add(fact.fact_id)
        deduped.append(fact)
    return deduped


def write_world_fact_segment(
    facts: list[Fact],
    *,
    fact_log_root: Path,
    segment_name: str,
) -> FactSegmentManifest:
    """Write one deduplicated world fact segment under the fact-log `world/` lane."""
    try:
        segment_dir = fact_log_root / "world"
        normalized = _normalize_segment_name(segment_name)
        deduped = _dedup_facts(facts)
        return write_fact_segment(
            deduped,
            segment_dir=segment_dir,
            segment_name=normalized,
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise WorldSegmentError(f"failed to write world fact segment: {exc}") from exc


def append_world_segment_index(
    manifest: FactSegmentManifest,
    *,
    fact_log_root: Path,
    tracer: PolicyOSTracer | None = None,
    metrics: MetricsRegistry | None = None,
) -> None:
    """Append a segment manifest to the world fact-log index consumed by materializers."""
    resolved = resolve_world_observability(tracer=tracer, metrics=metrics)
    try:
        with resolved.tracer.start_as_current_span(
            FABRIC_TRACE_NAMES["segment_append"],
            attributes={
                "world.segment_id": manifest.segment_id,
                "world.row_count": manifest.row_count,
            },
        ):
            index_path = fact_log_root / "world" / SEGMENTS_INDEX_NAME
            lock_path = fact_log_root / "world" / SEGMENTS_INDEX_LOCK_NAME
            append_text_locked(
                index_path,
                manifest.model_dump_json() + "\n",
                lock_path=lock_path,
            )
            if getattr(resolved.metrics, "set_fabric_segment_count", None):
                try:
                    manifests = load_world_fact_manifests(fact_log_root)
                except Exception:
                    manifests = []
                tenant_id = ""
                if isinstance(manifest.stats, dict):
                    tenant_id = str(manifest.stats.get("tenant_id", "") or "").strip()
                if tenant_id:
                    count = sum(
                        1
                        for item in manifests
                        if isinstance(item.stats, dict)
                        and str(item.stats.get("tenant_id", "") or "").strip() == tenant_id
                    )
                    resolved.metrics.set_fabric_segment_count(float(count), tenant_id=tenant_id)
                else:
                    resolved.metrics.set_fabric_segment_count(float(len(manifests)))
    except Exception as exc:  # pragma: no cover - defensive
        raise WorldSegmentError(f"failed to append world segment index: {exc}") from exc


def load_world_fact_manifests(fact_log_root: Path) -> list[FactSegmentManifest]:
    """Load world fact manifests."""
    index_path = fact_log_root / "world" / SEGMENTS_INDEX_NAME
    if not index_path.exists():
        return []
    manifests: list[FactSegmentManifest] = []
    lock_path = fact_log_root / "world" / SEGMENTS_INDEX_LOCK_NAME
    with file_lock(lock_path), index_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                manifests.append(FactSegmentManifest.model_validate_json(raw))
            except Exception as exc:
                logger.error(
                    "Invalid world fact manifest index entry",
                    index_path=str(index_path),
                    line_number=line_number,
                    error=str(exc),
                )
                raise WorldSegmentError(
                    f"invalid world segment index entry at {index_path}:{line_number}: {exc}"
                ) from exc
    return manifests


def vacuum_world_segment_index(fact_log_root: Path) -> list[FactSegmentManifest]:
    """Rewrite the segment index so it only references unique, existing segments."""

    manifests = load_world_fact_manifests(fact_log_root)
    deduped: dict[str, FactSegmentManifest] = {}
    for manifest in manifests:
        if not Path(manifest.path).exists():
            logger.warning(
                "Dropping missing world segment from index during vacuum",
                segment_id=manifest.segment_id,
                path=manifest.path,
            )
            continue
        deduped[manifest.segment_id] = manifest
    return _write_world_fact_index(fact_log_root, deduped.values())


def gc_world_segments(
    fact_log_root: Path,
    *,
    applied_segment_ids: Iterable[str] = (),
    retain_latest: int = 0,
    retain_since: str | None = None,
    retain_segment_ids: Iterable[str] = (),
    dry_run: bool = False,
) -> WorldSegmentGCReport:
    """Delete expired applied segments while preserving retained or unapplied ones."""

    manifests = load_world_fact_manifests(fact_log_root)
    applied_ids = {str(segment_id) for segment_id in applied_segment_ids}
    explicit_retain = {str(segment_id) for segment_id in retain_segment_ids}
    keep_since_dt = (
        parse_datetime_utc(retain_since, what="retain_since") if retain_since is not None else None
    )

    retained: list[FactSegmentManifest] = []
    deleted_ids: list[str] = []
    latest_ids = {manifest.segment_id for manifest in manifests[-max(retain_latest, 0) :]}

    for manifest in manifests:
        keep = False
        if manifest.segment_id not in applied_ids:
            keep = True
        if manifest.segment_id in explicit_retain or manifest.segment_id in latest_ids:
            keep = True
        if keep_since_dt is not None:
            if manifest.time_end is None:
                keep = True
            else:
                try:
                    keep = (
                        parse_datetime_utc(manifest.time_end, what="world segment time_end")
                        >= keep_since_dt
                    ) or keep
                except Exception:
                    keep = True

        if keep:
            retained.append(manifest)
            continue

        deleted_ids.append(manifest.segment_id)
        if dry_run:
            continue
        for path in (Path(manifest.path), _segment_manifest_sidecar_path(manifest)):
            try:
                if path.exists():
                    path.unlink()
            except OSError as exc:
                logger.warning(
                    "Failed to delete world segment artifact during GC",
                    segment_id=manifest.segment_id,
                    path=str(path),
                    error=str(exc),
                )
                retained.append(manifest)
                deleted_ids.pop()
                break

    if not dry_run:
        retained = _write_world_fact_index(fact_log_root, retained)

    return WorldSegmentGCReport(
        retained_segment_ids=tuple(manifest.segment_id for manifest in retained),
        deleted_segment_ids=tuple(deleted_ids),
        dry_run=dry_run,
    )


def persist_fact_segment_manifest(
    manifest: FactSegmentManifest,
    store: ArtifactStore,
) -> ArtifactRef:
    """Persist a segment manifest artifact so downstream stages can reference the batch."""
    ref = store.put_json(
        manifest.model_dump(),
        opts=ArtifactWriteOptions(
            kind="ir.fact_segment_manifest",
            media_type="application/json",
            schema=SchemaInfo(name="ir.fact_segment_manifest", version="1.0"),
        ),
    )
    return ArtifactRef.model_validate(ref.model_dump())


__all__ = [
    "SEGMENTS_INDEX_LOCK_NAME",
    "SEGMENTS_INDEX_NAME",
    "WorldSegmentGCReport",
    "append_world_segment_index",
    "gc_world_segments",
    "load_world_fact_manifests",
    "persist_fact_segment_manifest",
    "vacuum_world_segment_index",
    "write_world_fact_segment",
]
