"""Per-source catalog module contracts for the Data Forge mirror."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel
from polisyos.data_forge.kernel.artifacts import RetentionClass
from polisyos.data_forge.kernel.pipeline import AssetGroup, AssetKey, AssetSpec

CatalogExecutionTier = Literal["catalog", "fetchable", "transport_ready"]
CatalogRunLane = Literal["catalog", "empirical", "enrichment"]
CatalogRunProfile = Literal[
    "prod_full",
    "prod_core_blocking",
    "catalog_refresh",
    "preflight_core",
    "observations_backfill",
]

SOURCE_ID_PATTERN = r"^[a-z][a-z0-9_]*$"


class CatalogSourceAssetKeys(DataForgeModel):
    """Stable per-source asset keys for a catalog source module."""

    raw: AssetKey
    normalized: AssetKey
    observations: AssetKey | None = None
    readiness: AssetKey


class CatalogSourceModuleSpec(DataForgeModel):
    """Declarative catalog source module split target."""

    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    family: str = Field(min_length=1)
    wave: str = Field(min_length=1, max_length=8)
    connector_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    execution_tier: CatalogExecutionTier = "catalog"
    run_lane: CatalogRunLane = "catalog"
    publish_blocking: bool = False
    update_frequency: str = Field(default="", min_length=0)
    metrics_required: bool = False
    seed_from: str | None = Field(default=None, pattern=SOURCE_ID_PATTERN)

    @property
    def emits_observations(self) -> bool:
        """Return whether this source should own empirical observation assets."""
        return (
            self.execution_tier in {"fetchable", "transport_ready"} and self.run_lane == "empirical"
        )

    def included_in_run_profile(self, profile: CatalogRunProfile) -> bool:
        """Return whether this source module participates in a run profile."""
        if profile == "prod_full":
            return True
        if profile == "prod_core_blocking":
            return self.publish_blocking
        if profile == "catalog_refresh":
            return self.run_lane in {"catalog", "enrichment"}
        if profile == "preflight_core":
            return self.publish_blocking and self.run_lane == "empirical"
        if profile == "observations_backfill":
            return self.execution_tier == "transport_ready" and self.run_lane == "empirical"
        return False

    def asset_keys(self) -> CatalogSourceAssetKeys:
        """Return stable per-source asset keys."""
        observations = (
            AssetKey.from_parts("catalog", "sources", self.source_id, "observations")
            if self.emits_observations
            else None
        )
        return CatalogSourceAssetKeys(
            raw=AssetKey.from_parts("catalog", "sources", self.source_id, "raw"),
            normalized=AssetKey.from_parts("catalog", "sources", self.source_id, "normalized"),
            observations=observations,
            readiness=AssetKey.from_parts("catalog", "sources", self.source_id, "readiness"),
        )

    def asset_specs(self, *, owner: str = "team-data-forge") -> tuple[AssetSpec, ...]:
        """Return per-source asset specs that can replace a legacy god-file slice."""
        keys = self.asset_keys()
        specs = [
            AssetSpec(
                key=keys.raw,
                owner=owner,
                schema_id=f"catalog.sources.{self.source_id}.raw",
                retention=RetentionClass.WARM,
            ),
            AssetSpec(
                key=keys.normalized,
                deps=(keys.raw,),
                owner=owner,
                schema_id=f"catalog.sources.{self.source_id}.normalized",
                retention=RetentionClass.WARM,
            ),
        ]
        readiness_deps = [keys.normalized]
        if keys.observations is not None:
            specs.append(
                AssetSpec(
                    key=keys.observations,
                    deps=(keys.normalized,),
                    owner=owner,
                    schema_id=f"catalog.sources.{self.source_id}.observations",
                    retention=RetentionClass.WARM,
                )
            )
            readiness_deps = [keys.observations]
        specs.append(
            AssetSpec(
                key=keys.readiness,
                deps=tuple(readiness_deps),
                owner=owner,
                schema_id=f"catalog.sources.{self.source_id}.readiness",
                retention=RetentionClass.HOT,
            )
        )
        return tuple(specs)


class CatalogSourceModulePlan(DataForgeModel):
    """Selected per-source module with the asset specs it owns."""

    source: CatalogSourceModuleSpec
    asset_specs: tuple[AssetSpec, ...]


CORE_CATALOG_SOURCE_MODULES: tuple[CatalogSourceModuleSpec, ...] = (
    CatalogSourceModuleSpec(
        source_id="oecd",
        family="sdmx",
        wave="A",
        connector_id="sdmx.source",
        profile_id="oecd_sdmx",
        execution_tier="transport_ready",
        run_lane="empirical",
        publish_blocking=True,
        update_frequency="quarterly",
        metrics_required=True,
    ),
    CatalogSourceModuleSpec(
        source_id="eurostat",
        family="sdmx",
        wave="A",
        connector_id="eurostat.data",
        profile_id="eurostat_public",
        execution_tier="transport_ready",
        run_lane="empirical",
        publish_blocking=True,
        update_frequency="monthly",
        metrics_required=True,
    ),
    CatalogSourceModuleSpec(
        source_id="worldbank",
        family="worldbank",
        wave="B",
        connector_id="worldbank.wdi",
        profile_id="worldbank_wdi",
        execution_tier="transport_ready",
        run_lane="empirical",
        publish_blocking=True,
        update_frequency="annual",
        metrics_required=True,
    ),
    CatalogSourceModuleSpec(
        source_id="wvs",
        family="wvs",
        wave="B",
        connector_id="wvs.wave7",
        profile_id="wvs_wave7",
        execution_tier="transport_ready",
        run_lane="empirical",
        publish_blocking=True,
        update_frequency="wave",
        metrics_required=True,
    ),
    CatalogSourceModuleSpec(
        source_id="ukons",
        family="ukons",
        wave="B",
        connector_id="ukons.datasets",
        profile_id="ukons_public",
        execution_tier="catalog",
        run_lane="catalog",
        update_frequency="monthly",
    ),
    CatalogSourceModuleSpec(
        source_id="data_gov_ua_broad",
        family="ckan",
        wave="C",
        connector_id="ckan.resource",
        profile_id="data_gov_ua",
        execution_tier="catalog",
        run_lane="catalog",
        update_frequency="irregular",
    ),
    CatalogSourceModuleSpec(
        source_id="data_gov_ua_exec",
        family="ckan",
        wave="C",
        connector_id="ckan.resource",
        profile_id="data_gov_ua",
        execution_tier="fetchable",
        run_lane="empirical",
        publish_blocking=True,
        update_frequency="irregular",
        metrics_required=True,
        seed_from="data_gov_ua_broad",
    ),
)


def select_catalog_source_modules(
    modules: tuple[CatalogSourceModuleSpec, ...] = CORE_CATALOG_SOURCE_MODULES,
    *,
    wave: str | None = None,
    run_profile: CatalogRunProfile = "prod_full",
) -> tuple[CatalogSourceModuleSpec, ...]:
    """Select source modules and include any seed dependencies."""
    selected = [
        module
        for module in modules
        if (wave is None or module.wave.upper() == wave.upper())
        and module.included_in_run_profile(run_profile)
    ]
    return _with_seed_dependencies(modules, selected)


def plan_catalog_source_modules(
    modules: tuple[CatalogSourceModuleSpec, ...] = CORE_CATALOG_SOURCE_MODULES,
    *,
    wave: str | None = None,
    run_profile: CatalogRunProfile = "prod_full",
) -> tuple[CatalogSourceModulePlan, ...]:
    """Return source module plans for selected catalog sources."""
    return tuple(
        CatalogSourceModulePlan(source=module, asset_specs=module.asset_specs())
        for module in select_catalog_source_modules(
            modules,
            wave=wave,
            run_profile=run_profile,
        )
    )


def build_catalog_source_asset_group(
    modules: tuple[CatalogSourceModuleSpec, ...] = CORE_CATALOG_SOURCE_MODULES,
    *,
    name: str = "catalog_sources",
    wave: str | None = None,
    run_profile: CatalogRunProfile = "prod_full",
) -> AssetGroup:
    """Build a per-source asset group from selected catalog modules."""
    specs = tuple(
        spec
        for plan in plan_catalog_source_modules(
            modules,
            wave=wave,
            run_profile=run_profile,
        )
        for spec in plan.asset_specs
    )
    return AssetGroup.from_specs(name, specs)


def _with_seed_dependencies(
    modules: tuple[CatalogSourceModuleSpec, ...],
    selected: list[CatalogSourceModuleSpec],
) -> tuple[CatalogSourceModuleSpec, ...]:
    selected_ids = {module.source_id for module in selected}
    by_id = {module.source_id: module for module in modules}
    queue = list(selected)
    while queue:
        module = queue.pop()
        if not module.seed_from or module.seed_from in selected_ids:
            continue
        seed_module = by_id.get(module.seed_from)
        if seed_module is None:
            continue
        selected_ids.add(seed_module.source_id)
        queue.append(seed_module)
    return tuple(module for module in modules if module.source_id in selected_ids)


__all__ = [
    "CORE_CATALOG_SOURCE_MODULES",
    "CatalogExecutionTier",
    "CatalogRunLane",
    "CatalogRunProfile",
    "CatalogSourceAssetKeys",
    "CatalogSourceModulePlan",
    "CatalogSourceModuleSpec",
    "build_catalog_source_asset_group",
    "plan_catalog_source_modules",
    "select_catalog_source_modules",
]
