"""Curated metric -> source bindings used by FastLane resolution."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterable
from fnmatch import fnmatchcase
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.common.logger import get_logger
from polisyos.fabric.io.atomic import atomic_write_text

logger = get_logger(__name__)


class SourceBinding(BaseModel):
    """Single curated binding for one metric/source pair."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_id: str = Field(..., min_length=1)
    connector_id: str = Field(..., min_length=1)
    dataset_id: str = Field(..., min_length=1)
    profile_id: str | None = None
    geography_patterns: list[str] = Field(default_factory=lambda: ["*"])
    granularity: list[str] = Field(default_factory=list)
    priority: int = Field(default=100, ge=0)
    trust: float = Field(default=0.5, ge=0.0, le=1.0)
    filters_template: dict[str, list[str]] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("geography_patterns", mode="before")
    @classmethod
    def _normalize_geo_patterns(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return ["*"]
        normalized = [str(item).strip().upper() for item in value if str(item).strip()]
        return normalized or ["*"]

    @field_validator("granularity", "tags", "aliases", mode="before")
    @classmethod
    def _normalize_string_list(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        result: list[str] = []
        for item in value:
            normalized = str(item).strip().lower()
            if normalized:
                result.append(normalized)
        return result

    def matches_geography(self, geography: str | None) -> bool:
        if geography is None:
            return True
        normalized_geo = geography.strip().upper()
        if not normalized_geo:
            return True
        return any(fnmatchcase(normalized_geo, pattern) for pattern in self.geography_patterns)


class SourceBindingCollection(BaseModel):
    """Source binding collection public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    generated_at: str | None = None
    generated_by: str | None = None
    bindings: list[SourceBinding] = Field(default_factory=list)


class SourceBindingRegistry:
    """In-memory registry loaded from curated JSON bindings."""

    DEFAULT_FILENAME = "source_bindings.json"

    def __init__(
        self,
        curated_dir: Path,
        filename: str = DEFAULT_FILENAME,
        *,
        strict: bool = True,
    ) -> None:
        self.curated_dir = curated_dir
        self.bindings_path = curated_dir / filename
        self._strict = strict
        self._bindings: list[SourceBinding] = []
        self._by_metric: dict[str, list[SourceBinding]] = {}
        self._raw_size_bytes = 0
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        if not self.bindings_path.exists():
            logger.warning("No source bindings file found at %s", self.bindings_path)
            return
        raw = self.bindings_path.read_text(encoding="utf-8")
        self._raw_size_bytes = len(raw.encode("utf-8"))
        try:
            collection = SourceBindingCollection.model_validate_json(raw)
        except Exception as exc:
            if self._strict:
                raise ValueError(
                    f"Invalid source bindings file '{self.bindings_path}': {exc}"
                ) from exc
            logger.warning("Invalid source bindings file '%s': %s", self.bindings_path, exc)
            return

        bindings = sorted(
            collection.bindings,
            key=lambda item: (
                item.metric_id,
                item.priority,
                -item.trust,
                item.connector_id,
                item.dataset_id,
            ),
        )
        by_metric: dict[str, list[SourceBinding]] = {}
        for binding in bindings:
            by_metric.setdefault(binding.metric_id, []).append(binding)
        with self._lock:
            self._bindings = bindings
            self._by_metric = by_metric
        logger.info(
            "Loaded %s source bindings from %s",
            len(bindings),
            self.bindings_path,
        )

    def all_bindings(self) -> list[SourceBinding]:
        with self._lock:
            return list(self._bindings)

    def list_metric_ids(self) -> list[str]:
        with self._lock:
            return sorted(self._by_metric)

    def bindings_for_metric(
        self, metric_id: str, *, geography: str | None = None
    ) -> list[SourceBinding]:
        with self._lock:
            bindings = list(self._by_metric.get(metric_id, []))
        if geography is None:
            return bindings
        return [binding for binding in bindings if binding.matches_geography(geography)]

    def search(
        self,
        metric_query: str,
        *,
        geography: str | None = None,
        limit: int = 50,
    ) -> list[SourceBinding]:
        query = metric_query.strip().lower()
        if not query:
            return []

        result: list[SourceBinding] = []
        seen: set[tuple[str, str, str]] = set()

        def _append(bindings: Iterable[SourceBinding]) -> None:
            for binding in bindings:
                key = (binding.metric_id, binding.connector_id, binding.dataset_id)
                if key in seen:
                    continue
                if geography is not None and not binding.matches_geography(geography):
                    continue
                seen.add(key)
                result.append(binding)
                if len(result) >= limit:
                    return

        # Exact metric ID.
        _append(self.bindings_for_metric(query, geography=geography))
        if len(result) >= limit:
            return result[:limit]

        # Wildcard metric matches.
        for metric_id in self.list_metric_ids():
            if fnmatchcase(metric_id.lower(), query):
                _append(self.bindings_for_metric(metric_id, geography=geography))
            if len(result) >= limit:
                return result[:limit]

        # Alias/tag substring fallback.
        for binding in self.all_bindings():
            if query in binding.metric_id.lower():
                _append([binding])
                if len(result) >= limit:
                    return result[:limit]
                continue
            searchable = " ".join([*binding.aliases, *binding.tags]).lower()
            if query in searchable:
                _append([binding])
            if len(result) >= limit:
                return result[:limit]

        return result[:limit]

    def upsert(self, binding: SourceBinding) -> None:
        """Insert or replace a binding in memory."""
        key = (binding.metric_id, binding.connector_id, binding.dataset_id)
        with self._lock:
            retained = [
                item
                for item in self._bindings
                if (item.metric_id, item.connector_id, item.dataset_id) != key
            ]
            retained.append(binding)
            self._bindings = sorted(
                retained,
                key=lambda item: (
                    item.metric_id,
                    item.priority,
                    -item.trust,
                    item.connector_id,
                    item.dataset_id,
                ),
            )
            by_metric: dict[str, list[SourceBinding]] = {}
            for item in self._bindings:
                by_metric.setdefault(item.metric_id, []).append(item)
            self._by_metric = by_metric

    def persist(self) -> None:
        """Persist in-memory registry to JSON file."""
        with self._lock:
            payload = SourceBindingCollection(bindings=list(self._bindings)).model_dump(mode="json")
        encoded = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
        self.bindings_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.bindings_path, encoded)
        with self._lock:
            self._raw_size_bytes = len(encoded.encode("utf-8"))

    def stats(self) -> dict[str, int]:
        with self._lock:
            sources = {item.connector_id for item in self._bindings}
            return {
                "docs_total": len(self._bindings),
                "size_bytes": self._raw_size_bytes,
                "indexed_sources": len(sources),
            }
