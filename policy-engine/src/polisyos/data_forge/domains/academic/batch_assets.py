"""Academic batch-stage asset contracts for Data Forge Phase 2."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from polisyos.data_forge.kernel._base import DataForgeModel
from polisyos.data_forge.kernel.artifacts import RetentionClass
from polisyos.data_forge.kernel.pipeline import AssetGroup, AssetKey, AssetSpec

AcademicBatchRunProfile = Literal[
    "prod_full",
    "publish_readiness",
    "graph_only",
    "extraction_only",
]

ACADEMIC_BATCH_STAGE_ID_PATTERN = r"^[a-z][a-z0-9_]*$"
ACADEMIC_BATCH_STAGE_ORDER: tuple[str, ...] = (
    "topic_select",
    "demand_harvest",
    "doc_normalize",
    "harvest",
    "parse",
    "resolve_extract",
    "claim_extract",
    "context_extract",
    "mechanism_extract",
    "resolve_finalize",
    "numeric_extract",
    "merge_dedup",
    "claim_adjudicate",
    "conflict_resolve",
    "graph_load",
    "edge_synthesize",
    "graph_index",
    "transport_score",
    "benchmark",
    "embed",
    "qc",
    "publish",
)

ACADEMIC_BATCH_STAGE_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "topic_select": (),
    "demand_harvest": ("topic_select",),
    "doc_normalize": ("topic_select",),
    "harvest": ("topic_select", "demand_harvest"),
    "parse": ("harvest",),
    "resolve_extract": ("parse", "doc_normalize"),
    "claim_extract": ("resolve_extract",),
    "context_extract": ("resolve_extract",),
    "mechanism_extract": ("resolve_extract",),
    "resolve_finalize": (
        "claim_extract",
        "context_extract",
        "mechanism_extract",
    ),
    "numeric_extract": ("resolve_finalize",),
    "merge_dedup": ("parse", "resolve_finalize", "numeric_extract"),
    "claim_adjudicate": ("merge_dedup",),
    "conflict_resolve": ("claim_adjudicate",),
    "graph_load": ("conflict_resolve", "merge_dedup"),
    "edge_synthesize": ("graph_load",),
    "graph_index": ("edge_synthesize",),
    "transport_score": ("graph_index",),
    "benchmark": ("transport_score",),
    "embed": ("merge_dedup",),
    "qc": ("benchmark", "embed", "transport_score"),
    "publish": ("qc",),
}

_RUN_PROFILE_TARGETS: dict[AcademicBatchRunProfile, tuple[str, ...]] = {
    "prod_full": ACADEMIC_BATCH_STAGE_ORDER,
    "publish_readiness": ("publish",),
    "graph_only": ("graph_index",),
    "extraction_only": (
        "claim_extract",
        "context_extract",
        "mechanism_extract",
        "resolve_finalize",
    ),
}


def _artifact_globs_for_stage(stage_id: str) -> tuple[str, ...]:
    if stage_id == "benchmark":
        return ("benchmark_report.json",)
    if stage_id == "qc":
        return ("qc_report.json",)
    if stage_id == "publish":
        return ("publish/manifest.json", "publish/academic_pipeline_readiness.json")
    if stage_id == "graph_load":
        return ("graph/scholar_knowledge.duckdb",)
    return (f"{stage_id}/**/*", f"manifests/{stage_id}.json")


class AcademicBatchStageSpec(DataForgeModel):
    """Declarative target for one migrated academic batch stage."""

    stage_id: str = Field(pattern=ACADEMIC_BATCH_STAGE_ID_PATTERN)
    asset_key: AssetKey
    deps: tuple[str, ...] = Field(default_factory=tuple)
    schema_id: str = Field(min_length=1)
    artifact_globs: tuple[str, ...] = Field(default_factory=tuple)
    publish_blocking: bool = True
    read_api_surface: bool = False

    @model_validator(mode="after")
    def _stage_key_matches_id(self) -> AcademicBatchStageSpec:
        expected = AssetKey.from_parts("academic", "batch", self.stage_id)
        if self.asset_key != expected:
            raise ValueError(f"stage {self.stage_id} must use asset key {expected}")
        return self

    def dependency_asset_keys(self) -> tuple[AssetKey, ...]:
        """Return Data Forge asset keys for this stage's dependencies."""
        return tuple(AssetKey.from_parts("academic", "batch", dep) for dep in self.deps)

    def asset_spec(self, *, owner: str = "team-data-forge") -> AssetSpec:
        """Return the asset spec that represents this academic batch stage."""
        return AssetSpec(
            key=self.asset_key,
            deps=self.dependency_asset_keys(),
            owner=owner,
            schema_id=self.schema_id,
            retention=RetentionClass.HOT if self.read_api_surface else RetentionClass.WARM,
        )


class AcademicBatchStagePlan(DataForgeModel):
    """Selected academic batch stage and the asset specs it contributes."""

    stage: AcademicBatchStageSpec
    asset_specs: tuple[AssetSpec, ...]


CORE_ACADEMIC_BATCH_STAGES: tuple[AcademicBatchStageSpec, ...] = tuple(
    AcademicBatchStageSpec(
        stage_id=stage_id,
        asset_key=AssetKey.from_parts("academic", "batch", stage_id),
        deps=ACADEMIC_BATCH_STAGE_DEPENDENCIES[stage_id],
        schema_id=f"academic.batch.{stage_id}",
        artifact_globs=_artifact_globs_for_stage(stage_id),
        publish_blocking=stage_id
        in {
            "resolve_finalize",
            "merge_dedup",
            "graph_load",
            "graph_index",
            "benchmark",
            "qc",
            "publish",
        },
        read_api_surface=stage_id in {"benchmark", "qc", "publish"},
    )
    for stage_id in ACADEMIC_BATCH_STAGE_ORDER
)


def select_academic_batch_stages(
    stages: tuple[AcademicBatchStageSpec, ...] = CORE_ACADEMIC_BATCH_STAGES,
    *,
    run_profile: AcademicBatchRunProfile = "prod_full",
) -> tuple[AcademicBatchStageSpec, ...]:
    """Select academic stages for a run profile, including upstream dependencies."""
    selected_ids = _dependency_closure(_RUN_PROFILE_TARGETS[run_profile])
    return tuple(stage for stage in stages if stage.stage_id in selected_ids)


def plan_academic_batch_stages(
    stages: tuple[AcademicBatchStageSpec, ...] = CORE_ACADEMIC_BATCH_STAGES,
    *,
    run_profile: AcademicBatchRunProfile = "prod_full",
) -> tuple[AcademicBatchStagePlan, ...]:
    """Return academic batch-stage plans for a run profile."""
    return tuple(
        AcademicBatchStagePlan(
            stage=stage,
            asset_specs=(
                stage.asset_spec(
                    owner=(
                        "team-scientist"
                        if stage.stage_id == "claim_adjudicate"
                        else "team-data-forge"
                    )
                ),
            ),
        )
        for stage in select_academic_batch_stages(stages, run_profile=run_profile)
    )


def build_academic_batch_asset_group(
    stages: tuple[AcademicBatchStageSpec, ...] = CORE_ACADEMIC_BATCH_STAGES,
    *,
    name: str = "academic_batch",
    run_profile: AcademicBatchRunProfile = "prod_full",
) -> AssetGroup:
    """Build the detailed academic batch asset group for the selected profile."""
    specs = tuple(
        spec
        for plan in plan_academic_batch_stages(stages, run_profile=run_profile)
        for spec in plan.asset_specs
    )
    return AssetGroup.from_specs(name, specs)


def _dependency_closure(target_ids: tuple[str, ...]) -> frozenset[str]:
    selected = set(target_ids)
    queue = list(target_ids)
    while queue:
        stage_id = queue.pop()
        for dep in ACADEMIC_BATCH_STAGE_DEPENDENCIES[stage_id]:
            if dep in selected:
                continue
            selected.add(dep)
            queue.append(dep)
    return frozenset(selected)


__all__ = [
    "ACADEMIC_BATCH_STAGE_DEPENDENCIES",
    "ACADEMIC_BATCH_STAGE_ID_PATTERN",
    "ACADEMIC_BATCH_STAGE_ORDER",
    "CORE_ACADEMIC_BATCH_STAGES",
    "AcademicBatchRunProfile",
    "AcademicBatchStagePlan",
    "AcademicBatchStageSpec",
    "build_academic_batch_asset_group",
    "plan_academic_batch_stages",
    "select_academic_batch_stages",
]
