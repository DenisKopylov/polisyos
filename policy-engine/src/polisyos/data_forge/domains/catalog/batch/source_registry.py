"""Batch-facing source registry projection from the canonical catalog owner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from polisyos.data_forge.domains.catalog.registry import (
    CatalogSourceRegistryEntry,
    load_catalog_source_registry,
)
from polisyos.data_forge.domains.catalog.selection import (
    select_catalog_sources,
    source_included_in_run_profile,
)

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """Batch compatibility projection for one canonical catalog source."""

    name: str
    family: str
    wave: str
    endpoint: str
    enabled: bool = True
    connector_id: str = ""
    profile_id: str = ""
    execution_tier: str = "catalog"
    run_lane: str = "catalog"
    publish_blocking: bool = False
    update_frequency: str = ""
    metrics_required: bool = False
    history_policy: str = "full_snapshot"
    default_lookback_days: int | None = None
    max_rows_per_snapshot: int | None = None
    max_bytes_per_snapshot: int | None = None
    allow_manual_backfill: bool = False
    agency_prefix: str = ""
    agency_allowlist: tuple[str, ...] = ()
    exclude_agencies: tuple[str, ...] = ()
    seed_from: str = ""
    format_allowlist: tuple[str, ...] = ()
    format_denylist: tuple[str, ...] = ()
    keyword_allowlist: tuple[str, ...] = ()
    keyword_denylist: tuple[str, ...] = ()
    require_curated_resources: bool = False

    @property
    def source_id(self) -> str:
        """Expose the canonical source identity to shared selection policy."""
        return self.name

    def included_in_run_profile(self, profile: str) -> bool:
        """Return whether this source participates in a validated run profile."""
        return source_included_in_run_profile(self, profile)


@dataclass(frozen=True, slots=True)
class SourceRegistry:
    """Batch in-memory view selected by the canonical catalog policy."""

    version: int
    sources: tuple[SourceSpec, ...] = field(default_factory=tuple)

    def enabled_sources(
        self,
        *,
        wave: str | None = None,
        run_profile: str = "prod_full",
    ) -> list[SourceSpec]:
        """Return canonical wave/profile selection with fail-closed seed closure."""
        return list(select_catalog_sources(self.sources, wave=wave, run_profile=run_profile))


def load_source_registry(path: Path | str) -> SourceRegistry:
    """Load through the canonical typed registry and project into the batch view."""
    registry = load_catalog_source_registry(path)
    return SourceRegistry(
        version=registry.version,
        sources=tuple(_batch_source_spec(source) for source in registry.sources),
    )


def _batch_source_spec(source: CatalogSourceRegistryEntry) -> SourceSpec:
    """Map the canonical source identity into the legacy batch field name."""
    payload = source.model_dump()
    payload["name"] = payload.pop("source_id")
    payload["seed_from"] = payload["seed_from"] or ""
    return SourceSpec(**payload)


__all__ = ["SourceRegistry", "SourceSpec", "load_source_registry"]
