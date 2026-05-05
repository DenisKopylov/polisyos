"""Catalog source registry contracts for Data Forge Phase 3."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel

from .source_modules import (
    CatalogExecutionTier,
    CatalogHistoryPolicy,
    CatalogRunLane,
    CatalogRunProfile,
    CatalogSourceModuleSpec,
)


class CatalogSourceRegistryEntry(DataForgeModel):
    """One source entry from the catalog source registry."""

    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    family: str = Field(min_length=1)
    wave: str = Field(min_length=1, max_length=8)
    endpoint: str = Field(min_length=1)
    enabled: bool = True
    connector_id: str = Field(min_length=1)
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
        )


class CatalogSourceRegistrySpec(DataForgeModel):
    """Validated source registry contract used by Data Forge catalog planning."""

    version: int = Field(ge=1)
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
        selected = [
            source
            for source in self.sources
            if source.enabled
            and (wave is None or source.wave.upper() == wave.upper())
            and source.included_in_run_profile(run_profile)
        ]
        return self._with_seed_dependencies(selected)

    def to_module_specs(self) -> tuple[CatalogSourceModuleSpec, ...]:
        """Return source-module specs for all registry entries."""
        return tuple(source.to_module_spec() for source in self.sources)

    def _with_seed_dependencies(
        self,
        selected: list[CatalogSourceRegistryEntry],
    ) -> tuple[CatalogSourceRegistryEntry, ...]:
        selected_ids = {source.source_id for source in selected}
        by_id = {source.source_id: source for source in self.sources if source.enabled}
        queue = list(selected)
        while queue:
            source = queue.pop()
            if not source.seed_from or source.seed_from in selected_ids:
                continue
            seed = by_id.get(source.seed_from)
            if seed is None:
                continue
            selected_ids.add(seed.source_id)
            queue.append(seed)
        return tuple(
            source for source in self.sources if source.enabled and source.source_id in selected_ids
        )


def default_catalog_source_registry_path() -> Path:
    """Return the checked-in Data Forge source registry file."""
    return Path(__file__).with_name("source_registry.yaml")


def load_catalog_source_registry(path: str | Path | None = None) -> CatalogSourceRegistrySpec:
    """Load a source registry file through the Data Forge canonical registry."""
    import yaml

    registry_path = Path(path) if path is not None else default_catalog_source_registry_path()
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"source registry must be a mapping: {registry_path}")
    raw_sources = payload.get("sources", [])
    if not isinstance(raw_sources, list):
        raise ValueError(f"source registry 'sources' must be a list: {registry_path}")
    return CatalogSourceRegistrySpec(
        version=int(payload.get("version", 1)),
        sources=tuple(
            _entry_from_mapping(row)
            for row in raw_sources
            if isinstance(row, dict) and str(row.get("name") or "").strip()
        ),
    )


def catalog_source_modules_from_registry(
    registry: CatalogSourceRegistrySpec,
) -> tuple[CatalogSourceModuleSpec, ...]:
    """Convert a Data Forge registry contract into source-module specs."""
    return registry.to_module_specs()


def _entry_from_mapping(row: dict[str, Any]) -> CatalogSourceRegistryEntry:
    execution_tier = _execution_tier(row.get("execution_tier"))
    run_lane = _run_lane(row.get("run_lane"), execution_tier)
    return CatalogSourceRegistryEntry(
        source_id=str(row.get("name") or "").strip(),
        family=str(row.get("family") or "").strip(),
        wave=str(row.get("wave") or "").strip().upper(),
        endpoint=str(row.get("endpoint") or "").strip(),
        enabled=bool(row.get("enabled", True)),
        connector_id=str(row.get("connector_id") or "").strip(),
        profile_id=str(row.get("profile_id") or "").strip(),
        execution_tier=execution_tier,
        run_lane=run_lane,
        publish_blocking=bool(row.get("publish_blocking", execution_tier != "catalog")),
        update_frequency=str(row.get("update_frequency") or "").strip(),
        metrics_required=bool(row.get("metrics_required", False)),
        history_policy=_history_policy(row.get("history_policy")),
        default_lookback_days=_int_or_none(row.get("default_lookback_days")),
        max_rows_per_snapshot=_int_or_none(row.get("max_rows_per_snapshot")),
        max_bytes_per_snapshot=_int_or_none(row.get("max_bytes_per_snapshot")),
        allow_manual_backfill=bool(row.get("allow_manual_backfill", False)),
        seed_from=_optional_str(row.get("seed_from")),
        require_curated_resources=bool(row.get("require_curated_resources", False)),
        agency_prefix=str(row.get("agency_prefix") or "").strip(),
        agency_allowlist=_string_tuple(row.get("agency_allowlist")),
        exclude_agencies=_string_tuple(row.get("exclude_agencies")),
        format_allowlist=_upper_string_tuple(row.get("format_allowlist")),
        format_denylist=_upper_string_tuple(row.get("format_denylist")),
        keyword_allowlist=_lower_string_tuple(row.get("keyword_allowlist")),
        keyword_denylist=_lower_string_tuple(row.get("keyword_denylist")),
    )


def _execution_tier(value: object) -> CatalogExecutionTier:
    tier = str(value or "catalog").strip() or "catalog"
    if tier in {"catalog", "fetchable", "transport_ready"}:
        return tier
    raise ValueError(f"invalid catalog execution_tier: {tier}")


def _run_lane(value: object, execution_tier: CatalogExecutionTier) -> CatalogRunLane:
    lane = str(value or "").strip() or ("catalog" if execution_tier == "catalog" else "empirical")
    if lane in {"catalog", "empirical", "enrichment"}:
        return lane
    raise ValueError(f"invalid catalog run_lane: {lane}")


def _history_policy(value: object) -> CatalogHistoryPolicy:
    policy = str(value or "full_snapshot").strip() or "full_snapshot"
    if policy in {"full_snapshot", "rolling_window"}:
        return policy
    raise ValueError(f"invalid catalog history_policy: {policy}")


def _optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _upper_string_tuple(value: object) -> tuple[str, ...]:
    return tuple(item.upper() for item in _string_tuple(value))


def _lower_string_tuple(value: object) -> tuple[str, ...]:
    return tuple(item.lower() for item in _string_tuple(value))


__all__ = [
    "CatalogSourceRegistryEntry",
    "CatalogSourceRegistrySpec",
    "catalog_source_modules_from_registry",
    "default_catalog_source_registry_path",
    "load_catalog_source_registry",
]
