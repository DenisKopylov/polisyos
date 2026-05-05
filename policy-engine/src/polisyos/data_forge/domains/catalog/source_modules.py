"""Per-source catalog module contracts for the Data Forge catalog migration."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel
from polisyos.data_forge.kernel.artifacts import RetentionClass
from polisyos.data_forge.kernel.pipeline import AssetGroup, AssetKey, AssetSpec

CatalogExecutionTier = Literal["catalog", "fetchable", "transport_ready"]
CatalogHistoryPolicy = Literal["full_snapshot", "rolling_window"]
CatalogRunLane = Literal["catalog", "empirical", "enrichment"]
CatalogRunProfile = Literal[
    "prod_full",
    "prod_core_blocking",
    "rest_backfill",
    "catalog_refresh",
    "preflight_core",
    "observations_backfill",
]
CatalogSourceStage = Literal["harvest", "normalize", "observations", "publish"]

SOURCE_ID_PATTERN = r"^[a-z][a-z0-9_]*$"


class CatalogSourceAssetKeys(DataForgeModel):
    """Stable per-source asset keys for a catalog source module."""

    raw: AssetKey
    normalized: AssetKey
    observations: AssetKey | None = None
    readiness: AssetKey


class CatalogSourceStageContract(DataForgeModel):
    """Artifact-path contract for one source-owned pipeline stage."""

    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    stage: CatalogSourceStage
    asset_key: AssetKey
    deps: tuple[AssetKey, ...] = Field(default_factory=tuple)
    schema_id: str = Field(min_length=1)
    artifact_globs: tuple[str, ...] = Field(default_factory=tuple)
    legacy_stage: str = Field(min_length=1)


class CatalogSourceModuleSpec(DataForgeModel):
    """Declarative catalog source module split target."""

    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    family: str = Field(min_length=1)
    wave: str = Field(min_length=1, max_length=8)
    connector_id: str = Field(min_length=1)
    profile_id: str = Field(default="", min_length=0)
    endpoint: str = Field(default="", min_length=0)
    enabled: bool = True
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
    seed_from: str | None = Field(default=None, pattern=SOURCE_ID_PATTERN)
    require_curated_resources: bool = False

    @property
    def emits_observations(self) -> bool:
        """Return whether this source owns empirical observation assets."""
        return (
            self.execution_tier in {"fetchable", "transport_ready"} and self.run_lane == "empirical"
        )

    def included_in_run_profile(self, profile: CatalogRunProfile) -> bool:
        """Return whether this source module participates in a run profile."""
        if not self.enabled:
            return False
        if profile == "prod_full":
            return True
        if profile == "prod_core_blocking":
            return self.publish_blocking
        if profile == "rest_backfill":
            return self.allow_manual_backfill
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

    def stage_contracts(self) -> tuple[CatalogSourceStageContract, ...]:
        """Return harvest/normalize/observation/publish contracts for this source."""
        keys = self.asset_keys()
        contracts = [
            CatalogSourceStageContract(
                source_id=self.source_id,
                stage="harvest",
                asset_key=keys.raw,
                schema_id=f"catalog.sources.{self.source_id}.raw",
                artifact_globs=(
                    f"raw/{self.source_id}/**/*",
                    f"raw/{self.source_id}/manifest.json",
                ),
                legacy_stage="harvest",
            ),
            CatalogSourceStageContract(
                source_id=self.source_id,
                stage="normalize",
                asset_key=keys.normalized,
                deps=(keys.raw,),
                schema_id=f"catalog.sources.{self.source_id}.normalized",
                artifact_globs=(f"normalized/{self.source_id}.jsonl",),
                legacy_stage="normalize",
            ),
        ]
        readiness_deps = [keys.normalized]
        if keys.observations is not None:
            contracts.append(
                CatalogSourceStageContract(
                    source_id=self.source_id,
                    stage="observations",
                    asset_key=keys.observations,
                    deps=(keys.normalized,),
                    schema_id=f"catalog.sources.{self.source_id}.observations",
                    artifact_globs=(
                        "graph/dataset_catalog.duckdb",
                        "manifests/core_sources_ingest.json",
                    ),
                    legacy_stage="core_sources_ingest",
                )
            )
            readiness_deps = [keys.observations]
        contracts.append(
            CatalogSourceStageContract(
                source_id=self.source_id,
                stage="publish",
                asset_key=keys.readiness,
                deps=tuple(readiness_deps),
                schema_id=f"catalog.sources.{self.source_id}.readiness",
                artifact_globs=("publish/consumer_readiness.json", "publish/manifest.json"),
                legacy_stage="publish",
            )
        )
        return tuple(contracts)

    def asset_specs(self, *, owner: str = "team-data-forge") -> tuple[AssetSpec, ...]:
        """Return per-source asset specs that replace a legacy god-file slice."""
        retention_by_stage: dict[CatalogSourceStage, RetentionClass] = {
            "harvest": RetentionClass.WARM,
            "normalize": RetentionClass.WARM,
            "observations": RetentionClass.WARM,
            "publish": RetentionClass.HOT,
        }
        return tuple(
            AssetSpec(
                key=contract.asset_key,
                deps=contract.deps,
                owner=owner,
                schema_id=contract.schema_id,
                retention=retention_by_stage[contract.stage],
            )
            for contract in self.stage_contracts()
        )


class CatalogSourceModulePlan(DataForgeModel):
    """Selected per-source module with the asset specs it owns."""

    source: CatalogSourceModuleSpec
    asset_specs: tuple[AssetSpec, ...]
    stage_contracts: tuple[CatalogSourceStageContract, ...]


def select_catalog_source_modules(
    modules: tuple[CatalogSourceModuleSpec, ...] | None = None,
    *,
    wave: str | None = None,
    run_profile: CatalogRunProfile = "prod_full",
) -> tuple[CatalogSourceModuleSpec, ...]:
    """Select source modules and include any seed dependencies."""
    selected_modules = modules or CORE_CATALOG_SOURCE_MODULES
    selected = [
        module
        for module in selected_modules
        if (wave is None or module.wave.upper() == wave.upper())
        and module.included_in_run_profile(run_profile)
    ]
    return _with_seed_dependencies(selected_modules, selected)


def plan_catalog_source_modules(
    modules: tuple[CatalogSourceModuleSpec, ...] | None = None,
    *,
    wave: str | None = None,
    run_profile: CatalogRunProfile = "prod_full",
) -> tuple[CatalogSourceModulePlan, ...]:
    """Return source module plans for selected catalog sources."""
    return tuple(
        CatalogSourceModulePlan(
            source=module,
            asset_specs=module.asset_specs(),
            stage_contracts=module.stage_contracts(),
        )
        for module in select_catalog_source_modules(
            modules,
            wave=wave,
            run_profile=run_profile,
        )
    )


def plan_catalog_source_stage_contracts(
    modules: tuple[CatalogSourceModuleSpec, ...] | None = None,
    *,
    wave: str | None = None,
    run_profile: CatalogRunProfile = "prod_full",
) -> tuple[CatalogSourceStageContract, ...]:
    """Return selected source stage contracts in source-module order."""
    return tuple(
        contract
        for plan in plan_catalog_source_modules(
            modules,
            wave=wave,
            run_profile=run_profile,
        )
        for contract in plan.stage_contracts
    )


def build_catalog_source_asset_group(
    modules: tuple[CatalogSourceModuleSpec, ...] | None = None,
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


from .sources import ALL_CATALOG_SOURCE_MODULES as CORE_CATALOG_SOURCE_MODULES  # noqa: E402

__all__ = [
    "CORE_CATALOG_SOURCE_MODULES",
    "CatalogExecutionTier",
    "CatalogHistoryPolicy",
    "CatalogRunLane",
    "CatalogRunProfile",
    "CatalogSourceAssetKeys",
    "CatalogSourceModulePlan",
    "CatalogSourceModuleSpec",
    "CatalogSourceStage",
    "CatalogSourceStageContract",
    "build_catalog_source_asset_group",
    "plan_catalog_source_modules",
    "plan_catalog_source_stage_contracts",
    "select_catalog_source_modules",
]
