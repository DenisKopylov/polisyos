"""Catalog source registry contracts for Data Forge Phase 3."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import ConfigDict, Field, model_validator

from polisyos.data_forge.kernel._base import DataForgeModel

from .selection import select_catalog_sources
from .source_modules import (
    CatalogExecutionTier,
    CatalogHistoryPolicy,
    CatalogRunLane,
    CatalogRunProfile,
    CatalogSourceModuleSpec,
)


class CatalogSourceRegistryEntry(DataForgeModel):
    """One source entry from the catalog source registry."""

    model_config = ConfigDict(strict=True)

    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    family: str = Field(min_length=1)
    wave: str = Field(min_length=1, max_length=8)
    endpoint: str = Field(min_length=1)
    enabled: bool = True
    connector_id: str = Field(default="", min_length=0)
    profile_id: str = Field(default="", min_length=0)
    execution_tier: CatalogExecutionTier = "catalog"
    run_lane: CatalogRunLane = "catalog"
    publish_blocking: bool = False
    update_frequency: str = Field(default="", min_length=0)
    metrics_required: bool = False
    history_policy: CatalogHistoryPolicy = "full_snapshot"
    default_lookback_days: int | None = Field(default=None, ge=0)
    max_rows_per_snapshot: int | None = Field(default=None, ge=0)
    max_bytes_per_snapshot: int | None = Field(default=None, ge=0)
    allow_manual_backfill: bool = False
    seed_from: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")
    require_curated_resources: bool = False
    agency_prefix: str = Field(default="", min_length=0)
    agency_allowlist: tuple[str, ...] = Field(default_factory=tuple)
    exclude_agencies: tuple[str, ...] = Field(default_factory=tuple)
    format_allowlist: tuple[str, ...] = Field(default_factory=tuple)
    format_denylist: tuple[str, ...] = Field(default_factory=tuple)
    keyword_allowlist: tuple[str, ...] = Field(default_factory=tuple)
    keyword_denylist: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="before")
    @classmethod
    def _apply_execution_tier_defaults(cls, value: object) -> object:
        """Preserve the batch registry's dependent defaults for omitted fields."""
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        execution_tier = normalized.get("execution_tier", "catalog")
        normalized.setdefault(
            "run_lane",
            "catalog" if execution_tier == "catalog" else "empirical",
        )
        normalized.setdefault("publish_blocking", execution_tier != "catalog")
        return normalized

    @model_validator(mode="after")
    def _policy_fields_are_consistent(self) -> Self:
        """Keep the existing batch registry's cross-field policy constraints."""
        if self.run_lane == "enrichment" and self.publish_blocking:
            raise ValueError("enrichment sources cannot be publish-blocking")
        if self.allow_manual_backfill and self.history_policy != "rolling_window":
            raise ValueError("manual backfill requires rolling_window history policy")
        if self.default_lookback_days is not None and self.history_policy != "rolling_window":
            raise ValueError("default_lookback_days requires rolling_window history policy")
        return self

    def included_in_run_profile(self, profile: CatalogRunProfile) -> bool:
        """Return whether this source participates in a Data Forge run profile."""
        return self.to_module_spec().included_in_run_profile(profile)

    def to_module_spec(self) -> CatalogSourceModuleSpec:
        """Convert a registry entry into a source-module contract."""
        return CatalogSourceModuleSpec(
            source_id=self.source_id,
            family=self.family,
            wave=self.wave,
            connector_id=self.connector_id,
            profile_id=self.profile_id,
            endpoint=self.endpoint,
            enabled=self.enabled,
            execution_tier=self.execution_tier,
            run_lane=self.run_lane,
            publish_blocking=self.publish_blocking,
            update_frequency=self.update_frequency,
            metrics_required=self.metrics_required,
            history_policy=self.history_policy,
            default_lookback_days=self.default_lookback_days,
            max_rows_per_snapshot=self.max_rows_per_snapshot,
            max_bytes_per_snapshot=self.max_bytes_per_snapshot,
            allow_manual_backfill=self.allow_manual_backfill,
            seed_from=self.seed_from,
            require_curated_resources=self.require_curated_resources,
            agency_prefix=self.agency_prefix,
            agency_allowlist=self.agency_allowlist,
            exclude_agencies=self.exclude_agencies,
            format_allowlist=self.format_allowlist,
            format_denylist=self.format_denylist,
            keyword_allowlist=self.keyword_allowlist,
            keyword_denylist=self.keyword_denylist,
        )


class CatalogSourceRegistrySpec(DataForgeModel):
    """Validated source registry contract used by Data Forge catalog planning."""

    model_config = ConfigDict(strict=True)

    version: int = Field(default=1, ge=1)
    sources: tuple[CatalogSourceRegistryEntry, ...] = Field(default_factory=tuple)

    def source_by_id(self, source_id: str) -> CatalogSourceRegistryEntry | None:
        """Return a source entry by id."""
        for source in self.sources:
            if source.source_id == source_id:
                return source
        return None

    def enabled_sources(
        self,
        *,
        wave: str | None = None,
        run_profile: CatalogRunProfile = "prod_full",
    ) -> tuple[CatalogSourceRegistryEntry, ...]:
        """Return selected registry entries with seed dependencies expanded."""
        return select_catalog_sources(self.sources, wave=wave, run_profile=run_profile)

    def to_module_specs(self) -> tuple[CatalogSourceModuleSpec, ...]:
        """Return source-module specs for all registry entries."""
        return tuple(source.to_module_spec() for source in self.sources)


def default_catalog_source_registry_path() -> Path:
    """Return the checked-in Data Forge source registry file."""
    return Path(__file__).with_name("source_registry.yaml")


def load_catalog_source_registry(path: str | Path | None = None) -> CatalogSourceRegistrySpec:
    """Load a source registry file through the Data Forge canonical registry."""
    registry_path = Path(path) if path is not None else default_catalog_source_registry_path()
    return _load_catalog_source_registry(registry_path)


@lru_cache(maxsize=1)
def _default_catalog_source_registry_view() -> CatalogSourceRegistrySpec:
    """Cache the checked-in registry for static compatibility views."""
    return _load_catalog_source_registry(default_catalog_source_registry_path())


def _load_catalog_source_registry(registry_path: Path) -> CatalogSourceRegistrySpec:
    """Parse one YAML registry through strict Pydantic source contracts."""
    import yaml

    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError(f"source registry must be a mapping: {registry_path}")
    raw_sources = payload.get("sources", [])
    if not isinstance(raw_sources, list):
        raise ValueError(f"source registry 'sources' must be a list: {registry_path}")

    normalized_sources: list[dict[str, object]] = []
    for index, row in enumerate(raw_sources):
        if not isinstance(row, dict):
            raise ValueError(f"source registry row {index} must be a mapping: {registry_path}")
        normalized_row: dict[str, object] = {}
        for key, value in row.items():
            normalized_key = "source_id" if key == "name" else key
            if normalized_key in normalized_row:
                raise ValueError(
                    f"source registry row {index} repeats source identity: {registry_path}"
                )
            normalized_row[normalized_key] = _normalize_yaml_sequences(value)
        normalized_sources.append(normalized_row)

    normalized_payload = {key: _normalize_yaml_sequences(value) for key, value in payload.items()}
    normalized_payload["sources"] = tuple(normalized_sources)
    registry = CatalogSourceRegistrySpec.model_validate(normalized_payload, strict=True)
    source_ids = tuple(entry.source_id for entry in registry.sources)
    if len(source_ids) != len(set(source_ids)):
        raise ValueError(f"source registry contains duplicate source names: {registry_path}")
    return registry


def catalog_source_modules_from_registry(
    registry: CatalogSourceRegistrySpec,
) -> tuple[CatalogSourceModuleSpec, ...]:
    """Convert a Data Forge registry contract into source-module specs."""
    return registry.to_module_specs()


def _catalog_source_module(source_id: str) -> CatalogSourceModuleSpec:
    """Return one compatibility-view module from the canonical YAML source."""
    source = _default_catalog_source_registry_view().source_by_id(source_id)
    if source is None:
        raise ValueError(f"catalog source is not registered: {source_id}")
    return source.to_module_spec()


def _normalize_yaml_sequences(value: object) -> object:
    """Represent YAML arrays as tuples while retaining every scalar type."""
    if isinstance(value, list):
        return tuple(_normalize_yaml_sequences(item) for item in value)
    if isinstance(value, dict):
        return {key: _normalize_yaml_sequences(item) for key, item in value.items()}
    return value


__all__ = [
    "CatalogSourceRegistryEntry",
    "CatalogSourceRegistrySpec",
    "catalog_source_modules_from_registry",
    "default_catalog_source_registry_path",
    "load_catalog_source_registry",
]
