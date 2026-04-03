"""Public store segments module API."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.fabric.fact_writer import write_fact_segment
from polisyos.ir.fact_log import Fact, FactSegmentManifest
from polisyos.ir.kernel.base import ID_PATTERN

from .errors import WorldSegmentError

logger = get_logger(__name__)

SEGMENTS_INDEX_NAME = "_segments.jsonl"

_ID_RE = re.compile(ID_PATTERN)


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
    """Write world fact segment helper."""
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
) -> None:
    """Append world segment index helper."""
    try:
        index_path = fact_log_root / "world" / SEGMENTS_INDEX_NAME
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with index_path.open("a", encoding="utf-8") as f:
            f.write(manifest.model_dump_json() + "\n")
    except Exception as exc:  # pragma: no cover - defensive
        raise WorldSegmentError(f"failed to append world segment index: {exc}") from exc


def load_world_fact_manifests(fact_log_root: Path) -> list[FactSegmentManifest]:
    """Load world fact manifests."""
    index_path = fact_log_root / "world" / SEGMENTS_INDEX_NAME
    if not index_path.exists():
        return []
    manifests: list[FactSegmentManifest] = []
    with index_path.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                manifests.append(FactSegmentManifest.model_validate_json(raw))
            except Exception as exc:
                logger.warning("Skipping invalid world fact manifest: %s", exc)
    return manifests


def persist_fact_segment_manifest(
    manifest: FactSegmentManifest, store: FileSystemCAS
) -> ArtifactRef:
    """Persist fact segment manifest helper."""
    ref = store.put_json(
        manifest.model_dump(),
        opts=PutOptions(
            kind="ir.fact_segment_manifest",
            media_type="application/json",
            schema=SchemaInfo(name="ir.fact_segment_manifest", version="1.0"),
        ),
    )
    return ArtifactRef.model_validate(ref.model_dump())


__all__ = [
    "SEGMENTS_INDEX_NAME",
    "append_world_segment_index",
    "load_world_fact_manifests",
    "persist_fact_segment_manifest",
    "write_world_fact_segment",
]
