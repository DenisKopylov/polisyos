"""Data-state substrate lift over real L1/L4/L5 production data.

This bridge owns the S1 orchestration boundary only. L1 DCAT remains the
coverage/availability authority, L5 remains the trust/identification/schema
authority, Data Forge owns snapshot binding evidence, Foundry owns
``GlobalState`` materialization, S0 owns substrate registration, and N3 owns
the ``WorldModelRecord`` lifecycle.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, InputRef, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import DataTrust, ValueOuterSet
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.registry import build_default_registry_bundle
from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.data_forge.kernel.pipeline.manifests import write_publish_manifest
from polisyos.data_forge.kernel.snapshot import finalize_snapshot
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.substrate_registry import (
    L5CatalogAuthority,
    SubstrateRegistryError,
    build_substrate_registry_from_existing_catalogs,
    default_substrate_catalog_paths,
    load_l5_catalog_authority,
    persist_substrate_registry,
)
from polisyos.runtime.quality.world_model_record import (
    BranchMode,
    FabricWorldRef,
    SkgCausalPriorRef,
    WorldModelBuildResult,
    WorldModelLimitations,
    WorldModelRecordError,
    WorldModelSimulationInput,
    build_world_model_record,
    consume_world_model_record_for_simulation,
)

DATA_STATE_SUBSTRATE_SCHEMA_VERSION = "policyos.runtime.data_state_substrate.v1"
DEFAULT_L4_SNAPSHOT_ID = "ukraine_server_support_20260410"
DEFAULT_DATA_STATE_PERIOD_START = "2021-12"
DEFAULT_DATA_STATE_PERIOD_END = "2023-07"
DEFAULT_DATA_STATE_VARIABLES = ("avg_income", "employment_rate", "tax_revenue")
DEFAULT_DATA_STATE_FAMILIES = (
    "budget_flows",
    "firm_fundamentals",
    "household_distribution",
    "distress_enforcement",
)
_ACADEMIC_SKG_DB = Path(
    "production_data/policyos_academic_runtime_slim_20260411T112032Z/"
    "academic/graph/scholar_knowledge.duckdb"
)


class DataStateSubstrateError(ValueError):
    """Fail-closed error raised when S1 would fabricate data or authority."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class _StrictModel(BaseModel):
    """Strict immutable base for data-state substrate DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class L1VariableAvailability(_StrictModel):
    """L1 DCAT coverage decision for one required canonical variable."""

    variable_id: str = Field(..., min_length=1)
    status: Literal["available", "unavailable"]
    dataset_count: int = Field(..., ge=0)
    metric_binding_count: int = Field(..., ge=0)
    observation_count: int = Field(..., ge=0)
    coverage_ref: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _status_matches_owner_counts(self) -> L1VariableAvailability:
        count = self.dataset_count + self.metric_binding_count + self.observation_count
        if self.status == "unavailable" and count != 0:
            raise ValueError("l1_unavailable_counts_nonzero")
        if self.status == "available" and count == 0:
            raise ValueError("l1_available_counts_empty")
        return self


class L5FamilyAuthority(_StrictModel):
    """L5 trust/identification cap for one bound observation family."""

    family_id: str = Field(..., min_length=1)
    coverage_score: float = Field(..., ge=0.0, le=1.0)
    trust_tier: str = Field(..., min_length=1)
    trust_cap: float = Field(..., ge=0.0, le=1.0)
    trust_multiplier: float = Field(..., ge=0.0, le=1.0)
    min_coverage: float | None = Field(None, ge=0.0, le=1.0)
    max_coverage: float | None = Field(None, ge=0.0, le=1.0)
    promotion_floor: float = Field(..., ge=0.0, le=1.0)
    identification_mode: str = Field(..., min_length=1)
    value_authority: Literal["point", "bounds", "proxy_bounds", "limited"]
    measurement_registry_ref: str = Field(..., min_length=1)
    identification_registry_ref: str = Field(..., min_length=1)


class L5FamilyBindingProfile(_StrictModel):
    """Combined L5 family authority and schema-regime decision for S1."""

    schema_version: str = DATA_STATE_SUBSTRATE_SCHEMA_VERSION
    period_start: str = Field(..., min_length=1)
    period_end: str = Field(..., min_length=1)
    schema_regime_status: Literal[
        "single_regime",
        "boundary_buffer_flagged",
        "spans_changepoint_flagged",
    ]
    regime_ids: tuple[str, ...]
    changepoint_id: str | None = None
    changepoint_period: str | None = None
    boundary_buffer_periods: int = Field(..., ge=0)
    families: tuple[L5FamilyAuthority, ...]

    @field_validator("families", "regime_ids")
    @classmethod
    def _not_empty(cls, value: tuple[Any, ...]) -> tuple[Any, ...]:
        if not value:
            raise ValueError("l5_binding_profile_empty")
        return value

    def family_authority(self, family_id: str) -> L5FamilyAuthority:
        """Return the L5 authority row for ``family_id``."""

        for family in self.families:
            if family.family_id == family_id:
                return family
        raise DataStateSubstrateError("l5_family_unidentified", family_id)


@dataclass(frozen=True)
class DataStateMaterializationResult:
    """CAS and Data Forge artifacts emitted before N3 binds the world."""

    data_snapshot_ref: ArtifactRef
    data_forge_snapshot_binding_path: Path
    data_snapshot_stats: dict[str, Any]
    l1_availability: tuple[L1VariableAvailability, ...]
    l5_profile: L5FamilyBindingProfile
    payload_content_hash: str
    snapshot_id: str


@dataclass(frozen=True)
class ProductionDataStateWorldBuildResult:
    """End-to-end S1 world build result with the N3/Foundry outputs."""

    materialization: DataStateMaterializationResult
    world_model: WorldModelBuildResult
    simulation_input: WorldModelSimulationInput
    model_spec: ModelSpec
    registry_bundle_ref: ArtifactRef
    substrate_registry_ref: ArtifactRef

    @property
    def data_snapshot_stats(self) -> dict[str, Any]:
        """Return materialization stats for probe assertions."""

        return self.materialization.data_snapshot_stats


@dataclass(frozen=True)
class _DataStatePaths:
    """Canonical real-data paths consumed by S1."""

    l1_dcat_path: Path
    agent_registry_full: Path
    firm_fundamentals_annual: Path
    budget_flows_monthly_sparse: Path
    corrected_firm_panels: Path
    calibrated_household_cells: Path


def l1_dcat_variable_availability(
    repo_root: Path,
    variable_id: str,
    *,
    overlay_path: Path | None = None,
) -> L1VariableAvailability:
    """Resolve required-vs-available status from the L1 DCAT DuckDB catalog."""

    variable = variable_id.strip()
    if not variable:
        raise DataStateSubstrateError("l1_variable_empty")
    dcat_path = default_substrate_catalog_paths(repo_root).l1_dcat_path
    if not dcat_path.exists():
        raise DataStateSubstrateError("l1_dcat_missing", dcat_path.as_posix())

    selected_overlay = overlay_path or (
        data_forge_read_api.catalog.default_acquisition_overlay_path(repo_root)
    )
    con = data_forge_read_api.catalog.open_catalog_read_session(
        dcat_path,
        overlay_path=selected_overlay,
    )
    try:
        metric_binding_count = int(
            con.execute(
                "SELECT count(*) FROM ds_metric_bindings WHERE metric_id = ?",
                [variable],
            ).fetchone()[0]
            or 0
        )
        observation_count = int(
            con.execute(
                "SELECT count(*) FROM ds_observations WHERE canonical_var = ?",
                [variable],
            ).fetchone()[0]
            or 0
        )
        dataset_count = int(
            con.execute(
                "SELECT count(*) FROM ds_datasets WHERE list_contains(polisyos_metrics, ?)",
                [variable],
            ).fetchone()[0]
            or 0
        )
    finally:
        con.close()

    return L1VariableAvailability(
        variable_id=variable,
        status=(
            "available"
            if metric_binding_count > 0 or observation_count > 0 or dataset_count > 0
            else "unavailable"
        ),
        dataset_count=dataset_count,
        metric_binding_count=metric_binding_count,
        observation_count=observation_count,
        coverage_ref=(
            f"repo://production_data/datasets_full_phase3full_20260327_183054/"
            f"dataset_catalog.duckdb#variable/{variable}"
        ),
    )


def build_l5_family_binding_profile(
    repo_root: Path,
    *,
    families: Sequence[str],
    period_start: str,
    period_end: str,
) -> L5FamilyBindingProfile:
    """Build the L5 honesty profile for bound data-state families."""

    l5 = load_l5_catalog_authority(default_substrate_catalog_paths(repo_root))
    resolved_families: list[L5FamilyAuthority] = []
    for family_id in families:
        family = str(family_id).strip()
        if not family:
            raise DataStateSubstrateError("l5_family_empty")
        if family not in l5.coverage_rules or family not in l5.identification_modes:
            raise DataStateSubstrateError("l5_family_unidentified", family)
        tier = l5.expected_trust_tier(family)
        mode = l5.identification_modes[family]
        resolved_families.append(
            L5FamilyAuthority(
                family_id=family,
                coverage_score=float(l5.coverage_rules[family]),
                trust_tier=tier.tier,
                trust_cap=tier.trust_cap,
                trust_multiplier=tier.trust_multiplier,
                min_coverage=tier.min_coverage,
                max_coverage=tier.max_coverage,
                promotion_floor=l5.minimum_positive_coverage_floor(default=1.0),
                identification_mode=mode,
                value_authority=_value_authority_for_identification(mode),
                measurement_registry_ref=f"{l5.measurement_registry_ref}#/coverage_rules/{family}",
                identification_registry_ref=f"{l5.identification_mode_registry_ref}#/{family}",
            )
        )
    regime = _schema_regime_decision(
        l5,
        period_start=period_start,
        period_end=period_end,
    )
    return L5FamilyBindingProfile(
        period_start=period_start,
        period_end=period_end,
        families=tuple(resolved_families),
        **regime,
    )


def materialize_l4_data_state_snapshot(
    store: FileSystemCAS,
    *,
    repo_root: Path,
    workspace_dir: Path,
    agent_limit: int | None = 1024,
    required_l1_variables: Sequence[str] = DEFAULT_DATA_STATE_VARIABLES,
    families: Sequence[str] = DEFAULT_DATA_STATE_FAMILIES,
    period_start: str = DEFAULT_DATA_STATE_PERIOD_START,
    period_end: str = DEFAULT_DATA_STATE_PERIOD_END,
) -> DataStateMaterializationResult:
    """Persist a real L4 data-state ``DataSnapshot`` and Data Forge binding.

    ``agent_limit`` may be ``None`` for a full local materialization, but probe
    runs should pass a representative bound so the same production binding path
    remains cheap enough for targeted verification.
    """

    if agent_limit is not None and agent_limit <= 0:
        raise DataStateSubstrateError("production_data_state_empty")
    root = repo_root.resolve()
    paths = _default_data_state_paths(root)
    _require_paths(paths)
    availability = tuple(
        l1_dcat_variable_availability(root, variable)
        for variable in required_l1_variables
    )
    unavailable = [item.variable_id for item in availability if item.status == "unavailable"]
    if unavailable:
        raise DataStateSubstrateError("l1_variable_unavailable", ",".join(unavailable))
    l5_profile = build_l5_family_binding_profile(
        root,
        families=families,
        period_start=period_start,
        period_end=period_end,
    )
    substrate_registry = build_substrate_registry_from_existing_catalogs(root)
    world_preimage_ref = _world_preimage_ref(
        substrate_version_id=substrate_registry.substrate_version_id,
        agent_limit=agent_limit,
        required_l1_variables=required_l1_variables,
        families=families,
        period_start=period_start,
        period_end=period_end,
        branch_mode=BranchMode.OBSERVED.value,
    )

    payload, stats = _project_real_l4_payload(
        paths,
        agent_limit=agent_limit,
        l5_profile=l5_profile,
        world_model_record_ref=world_preimage_ref,
    )
    bound_agent_count = int(stats.get("bound_agent_count") or 0)
    if bound_agent_count <= 0:
        raise DataStateSubstrateError("production_data_state_empty")

    profile_hash = gy_content_hash(l5_profile.model_dump(mode="json"))
    payload_with_meta = {
        **payload,
        "_policyos_data_state": {
            "schema_version": DATA_STATE_SUBSTRATE_SCHEMA_VERSION,
            "source_mode": "real_l4_representative_slice"
            if agent_limit is not None
            else "real_l4_full_projection",
            "l1_availability": [item.model_dump(mode="json") for item in availability],
            "l5_profile": l5_profile.model_dump(mode="json"),
            "l5_profile_hash": profile_hash,
            "world_preimage_ref": world_preimage_ref,
            "source_paths": _relative_source_paths(paths, root),
            "stats": stats,
        },
    }
    payload_ref = store.put_json(
        payload_with_meta,
        PutOptions(
            kind="fabric.production_data_state_payload",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.runtime.quality.DataStatePayload",
                version=DATA_STATE_SUBSTRATE_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    payload_content_hash = str(payload_ref.artifact_id)
    snapshot_id = _snapshot_id(agent_limit=agent_limit, payload_hash=payload_content_hash)
    data_snapshot = DataSnapshot(
        data_ref=payload_ref,
        stats={
            "snapshot_id": snapshot_id,
            "source_mode": str(payload_with_meta["_policyos_data_state"]["source_mode"]),
            "bound_agent_count": bound_agent_count,
            "l4_total_rows.agent_registry_full": int(
                stats["l4_total_rows"]["agent_registry_full"]
            ),
            "l4_total_rows.budget_flows_monthly_sparse": int(
                stats["l4_total_rows"]["budget_flows_monthly_sparse"]
            ),
            "l5_profile_hash": profile_hash,
            "world_preimage_ref": world_preimage_ref,
        },
        notes=[
            "gy_s1_real_l4_data_state",
            "data_forge_snapshot_binding:finalize_snapshot",
            "foundry_binding_owner:polisyos.foundry.data_plane.bindings.build_input_bindings",
            f"schema_regime_status:{l5_profile.schema_regime_status}",
        ],
    )
    data_snapshot_ref = store.put_json(
        data_snapshot,
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=[InputRef(artifact_id=payload_ref.artifact_id, role="payload.real_l4")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    binding_path = _write_data_forge_snapshot_binding(
        workspace_dir=workspace_dir,
        snapshot_id=snapshot_id,
        payload=payload_with_meta,
        payload_content_hash=payload_content_hash,
    )
    stats = {
        **stats,
        "source_mode": data_snapshot.stats["source_mode"],
        "payload_content_hash": payload_content_hash,
        "snapshot_id": snapshot_id,
        "l5_profile_hash": profile_hash,
        "world_preimage_ref": world_preimage_ref,
    }
    return DataStateMaterializationResult(
        data_snapshot_ref=data_snapshot_ref,
        data_forge_snapshot_binding_path=binding_path,
        data_snapshot_stats=stats,
        l1_availability=availability,
        l5_profile=l5_profile,
        payload_content_hash=payload_content_hash,
        snapshot_id=snapshot_id,
    )


def build_production_data_state_world_model_record(
    store: FileSystemCAS,
    *,
    repo_root: Path,
    workspace_dir: Path,
    agent_limit: int | None = 1024,
    required_l1_variables: Sequence[str] = DEFAULT_DATA_STATE_VARIABLES,
    required_substrate_families: Sequence[str] = DEFAULT_DATA_STATE_FAMILIES,
    period_start: str = DEFAULT_DATA_STATE_PERIOD_START,
    period_end: str = DEFAULT_DATA_STATE_PERIOD_END,
) -> ProductionDataStateWorldBuildResult:
    """Build an N3 ``WorldModelRecord`` over the real S1 data-state substrate."""

    try:
        materialized = materialize_l4_data_state_snapshot(
            store,
            repo_root=repo_root,
            workspace_dir=workspace_dir,
            agent_limit=agent_limit,
            required_l1_variables=required_l1_variables,
            families=DEFAULT_DATA_STATE_FAMILIES,
            period_start=period_start,
            period_end=period_end,
        )
        registry = build_substrate_registry_from_existing_catalogs(repo_root)
        substrate_registry_ref = persist_substrate_registry(store, registry)
        registry_bundle = build_default_registry_bundle(store)
        model_spec = ModelSpec(
            model_id="model_ua_real_l4_data_state",
            data_snapshot_ref=str(materialized.data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry_bundle.bundle_ref.artifact_id),
            calibrated=True,
            calibration_ref=materialized.data_snapshot_stats["l5_profile_hash"],
            notes=[
                "gy_s1_real_l4_data_state",
                f"schema_regime_status:{materialized.l5_profile.schema_regime_status}",
            ],
        )
        fabric_root = _write_fabric_world_snapshot(
            workspace_dir=workspace_dir,
            snapshot_id=materialized.snapshot_id,
            payload_hash=materialized.payload_content_hash,
            stats=materialized.data_snapshot_stats,
        )
        skg_ref = _production_skg_ref(repo_root, snapshot_id=materialized.snapshot_id)
        limitations = WorldModelLimitations(
            unavailable_data=tuple(
                f"l1:{item.variable_id}"
                for item in materialized.l1_availability
                if item.status == "unavailable"
            ),
            calibration_envelope_status=(
                "near_boundary"
                if materialized.l5_profile.schema_regime_status != "single_regime"
                else "inside"
            ),
            unresolved_conflicts=(
                (f"schema_regime:{materialized.l5_profile.schema_regime_status}",)
                if materialized.l5_profile.schema_regime_status != "single_regime"
                else ()
            ),
        )
        world_model = build_world_model_record(
            store,
            fabric_world_ref=FabricWorldRef(
                snapshot_root=str(fabric_root),
                snapshot_id=materialized.snapshot_id,
                branch="observed",
                as_of_valid_time="2026-05-01T00:00:00+00:00",
                as_of_tx_time="2026-05-01T00:00:00+00:00",
                world_query_policy="gy_s1_real_data_state_non_empty",
                provenance_manifest_ref=f"cas://{materialized.payload_content_hash}",
            ),
            data_forge_snapshot_binding_path=materialized.data_forge_snapshot_binding_path,
            data_snapshot_ref=materialized.data_snapshot_ref,
            model_spec=model_spec,
            skg_causal_prior_ref=skg_ref,
            substrate_registry=registry,
            substrate_registry_artifact_ref=substrate_registry_ref,
            region_or_jurisdiction="UA",
            population_scope="ukraine_real_l4_representative_firms",
            policy_domain="fiscal_credit",
            valid_time_scope=f"{period_start}/{period_end}",
            tx_time_scope="2026-05-01T00:00:00+00:00",
            resolution="firm_month",
            branch_mode=BranchMode.OBSERVED,
            policy_slot_ids=(
                "agents.income",
                "agents.reported_income",
                "agents.skill_level",
                "agents.risk_aversion",
                "agents.is_employed",
                "agents.employer_id",
                "firms.labor_count",
                "firms.wage_offer",
                "cells.output",
                "cells.employment",
                "cells.distress_score",
                "household_cells.disposable_income",
                "household_cells.transfer_intensity",
                "household_cells.value_outer_set",
                "government.balance",
                "global.tax_rate",
            ),
            producer_ref=(
                "polisyos.runtime.quality.data_state_substrate."
                "build_production_data_state_world_model_record"
            ),
            data_forge_role="domain",
            required_substrate_families=required_substrate_families,
            limitations=limitations,
        )
    except (WorldModelRecordError, SubstrateRegistryError) as exc:
        code = getattr(exc, "code", type(exc).__name__)
        raise DataStateSubstrateError(str(code), str(exc)) from exc
    return ProductionDataStateWorldBuildResult(
        materialization=materialized,
        world_model=world_model,
        simulation_input=consume_world_model_record_for_simulation(world_model.record),
        model_spec=model_spec,
        registry_bundle_ref=registry_bundle.bundle_ref,
        substrate_registry_ref=substrate_registry_ref,
    )


def _project_real_l4_payload(
    paths: _DataStatePaths,
    *,
    agent_limit: int | None,
    l5_profile: L5FamilyBindingProfile,
    world_model_record_ref: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    import duckdb

    params: list[object] = [agent_limit]
    query = """
        WITH latest_firm AS (
            SELECT
                agent_id,
                registration_code,
                period_id,
                revenue,
                assets,
                liabilities,
                employees,
                row_number() OVER (
                    PARTITION BY agent_id
                    ORDER BY
                        period_id DESC,
                        source_snapshot_id DESC,
                        record_hash,
                        registration_code,
                        revenue,
                        assets,
                        liabilities,
                        employees
                ) AS rn
            FROM read_parquet(?)
            WHERE revenue IS NOT NULL AND revenue > 0
        ),
        distress AS (
            SELECT
                agent_id,
                avg(CAST(corrected_exit_bias AS DOUBLE)) AS distress_score,
                max(period_id) AS distress_period_id
            FROM read_parquet(?)
            GROUP BY agent_id
        ),
        agent_registry_conflicts AS (
            SELECT
                agent_id,
                count(*) AS registry_row_count,
                count(DISTINCT COALESCE(CAST(region_code AS VARCHAR), '__NULL__'))
                    AS region_value_count,
                count(DISTINCT COALESCE(CAST(sector_id AS VARCHAR), '__NULL__'))
                    AS sector_value_count
            FROM read_parquet(?)
            GROUP BY agent_id
        ),
        agent_registry_ranked AS (
            SELECT
                agent_id,
                registration_code,
                region_code,
                sector_id,
                row_number() OVER (
                    PARTITION BY agent_id
                    ORDER BY
                        period_id DESC,
                        source_snapshot_id DESC,
                        record_hash,
                        registration_code,
                        region_code,
                        sector_id,
                        agent_id
                ) AS registry_rn
            FROM read_parquet(?)
            WHERE agent_id IS NOT NULL
        ),
        agent_registry AS (
            SELECT
                r.agent_id,
                CASE
                    WHEN c.region_value_count > 1 THEN 'ambiguous_region'
                    ELSE COALESCE(CAST(r.region_code AS VARCHAR), 'unknown_region')
                END AS region_code,
                CASE
                    WHEN c.sector_value_count > 1 THEN 'ambiguous_sector'
                    ELSE COALESCE(CAST(r.sector_id AS VARCHAR), 'unknown_sector')
                END AS sector_id,
                c.registry_row_count,
                c.region_value_count,
                c.sector_value_count
            FROM agent_registry_ranked r
            JOIN agent_registry_conflicts c USING (agent_id)
            WHERE r.registry_rn = 1
        ),
        firm_registry AS (
            SELECT
                f.agent_id,
                f.registration_code,
                a.region_code,
                a.sector_id,
                f.period_id,
                f.revenue,
                f.assets,
                f.liabilities,
                f.employees,
                a.registry_row_count,
                a.region_value_count,
                a.sector_value_count
            FROM latest_firm f
            JOIN agent_registry a USING (agent_id)
            WHERE f.rn = 1
        ),
        sample_population AS (
            SELECT
                *,
                md5(
                    COALESCE(CAST(region_code AS VARCHAR), '')
                    || ':'
                    || COALESCE(CAST(registration_code AS VARCHAR), '')
                    || ':'
                    || COALESCE(CAST(agent_id AS VARCHAR), '')
                ) AS sample_key,
                row_number() OVER (
                    PARTITION BY region_code
                    ORDER BY
                        md5(
                            COALESCE(CAST(region_code AS VARCHAR), '')
                            || ':'
                            || COALESCE(CAST(registration_code AS VARCHAR), '')
                            || ':'
                            || COALESCE(CAST(agent_id AS VARCHAR), '')
                        ),
                        registration_code,
                        agent_id
                ) AS stratum_rank,
                count(*) OVER (PARTITION BY region_code) AS stratum_population
            FROM firm_registry
        ),
        ranked_sample AS (
            SELECT
                *,
                row_number() OVER (
                    ORDER BY stratum_rank, region_code, sample_key, registration_code, agent_id
                ) AS representative_rank
            FROM sample_population
        ),
        firm_sample AS (
            SELECT *
            FROM ranked_sample
            ORDER BY representative_rank
            LIMIT COALESCE(CAST(? AS BIGINT), 9223372036854775807)
        )
        SELECT
            f.agent_id,
            f.registration_code,
            CAST(f.region_code AS VARCHAR) AS region_code,
            CAST(f.sector_id AS VARCHAR) AS sector_id,
            CAST(f.revenue AS DOUBLE) AS revenue,
            CAST(f.assets AS DOUBLE) AS assets,
            CAST(f.liabilities AS DOUBLE) AS liabilities,
            CAST(f.employees AS DOUBLE) AS employees,
            CAST(COALESCE(d.distress_score, 0.0) AS DOUBLE) AS distress_score,
            f.period_id,
            d.distress_period_id,
            f.registry_row_count,
            f.region_value_count,
            f.sector_value_count,
            f.sample_key,
            f.stratum_rank,
            f.stratum_population,
            f.representative_rank
        FROM firm_sample f
        LEFT JOIN distress d USING (agent_id)
        ORDER BY f.representative_rank, f.registration_code, f.agent_id
    """
    con = duckdb.connect(database=":memory:")
    try:
        rows = con.execute(
            query,
            [
                str(paths.firm_fundamentals_annual),
                str(paths.corrected_firm_panels),
                str(paths.agent_registry_full),
                str(paths.agent_registry_full),
                *params,
            ],
        ).fetchall()
        agent_total = int(
            con.execute(
                "SELECT count(*) FROM read_parquet(?)",
                [str(paths.agent_registry_full)],
            ).fetchone()[0]
            or 0
        )
        firm_total = int(
            con.execute(
                "SELECT count(*) FROM read_parquet(?)",
                [str(paths.firm_fundamentals_annual)],
            ).fetchone()[0]
            or 0
        )
        distress_total = int(
            con.execute(
                "SELECT count(*) FROM read_parquet(?)",
                [str(paths.corrected_firm_panels)],
            ).fetchone()[0]
            or 0
        )
        budget_total = int(
            con.execute(
                "SELECT count(*) FROM read_parquet(?)",
                [str(paths.budget_flows_monthly_sparse)],
            ).fetchone()[0]
            or 0
        )
        budget_slice = con.execute(
            """
            SELECT
                count(*) AS row_count,
                COALESCE(sum(CAST(amount AS DOUBLE)), 0.0) AS amount_sum
            FROM (
                SELECT amount
                FROM read_parquet(?)
                LIMIT 100000
            )
            """,
            [str(paths.budget_flows_monthly_sparse)],
        ).fetchone()
        household_rows = con.execute(
            """
            SELECT
                cell_id,
                region_code,
                household_income_mean,
                household_weight_sum,
                measurement_bias_flag,
                trust_weight,
                market_income_mean,
                total_expenditure_mean
            FROM read_parquet(?)
            ORDER BY period_id DESC, region_code, cell_id
            LIMIT 100
            """,
            [str(paths.calibrated_household_cells)],
        ).fetchall()
    finally:
        con.close()
    if not rows:
        return {}, {
            "bound_agent_count": 0,
            "l4_total_rows": {
                "agent_registry_full": 0,
                "firm_fundamentals_annual": 0,
                "corrected_firm_panels": 0,
                "budget_flows_monthly_sparse": 0,
            },
        }
    return _payload_from_rows(
        rows=rows,
        household_rows=household_rows,
        l5_profile=l5_profile,
        world_model_record_ref=world_model_record_ref,
        budget_slice_count=int(budget_slice[0] or 0),
        budget_slice_amount_sum=float(budget_slice[1] or 0.0),
        totals={
            "agent_registry_full": agent_total,
            "firm_fundamentals_annual": firm_total,
            "corrected_firm_panels": distress_total,
            "budget_flows_monthly_sparse": budget_total,
        },
    )


def _payload_from_rows(
    *,
    rows: Sequence[Sequence[Any]],
    household_rows: Sequence[Sequence[Any]],
    l5_profile: L5FamilyBindingProfile,
    world_model_record_ref: str,
    budget_slice_count: int,
    budget_slice_amount_sum: float,
    totals: Mapping[str, int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    sector_ids = sorted({str(row[3] or "unknown") for row in rows})
    sector_index = {sector: idx for idx, sector in enumerate(sector_ids)}
    cell_keys = sorted({(str(row[2] or "0"), str(row[3] or "unknown")) for row in rows})
    cell_index = {key: idx for idx, key in enumerate(cell_keys)}

    income: list[float] = []
    reported_income: list[float] = []
    skill_level: list[float] = []
    risk_aversion: list[float] = []
    is_employed: list[bool] = []
    employer_id: list[int] = []
    household_cell_id: list[int] = []
    firms_labor_count: list[float] = []
    firms_wage_offer: list[float] = []
    firms_active: list[bool] = []
    firms_firm_id: list[int] = []
    firms_cell_id: list[int] = []
    firms_type_id: list[int] = []
    cell_accumulators = {
        key: {"count": 0.0, "employment": 0.0, "output": 0.0, "distress": []}
        for key in cell_keys
    }
    for idx, row in enumerate(rows):
        (
            _agent_id,
            _registration_code,
            region_code,
            sector_id,
            revenue,
            assets,
            liabilities,
            employees,
            distress_score,
            _period_id,
            _distress_period_id,
            _registry_row_count,
            _region_value_count,
            _sector_value_count,
            _sample_key,
            _stratum_rank,
            _stratum_population,
            _representative_rank,
        ) = row
        revenue_f = max(0.0, float(revenue or 0.0))
        employees_f = max(0.0, float(employees or 0.0))
        assets_f = max(0.0, float(assets or 0.0))
        liabilities_f = max(0.0, float(liabilities or 0.0))
        sector = str(sector_id or "unknown")
        key = (str(region_code or "0"), sector)
        cell_id = cell_index[key]
        income.append(revenue_f)
        reported_income.append(revenue_f)
        skill_level.append(max(1.0, min(10.0, employees_f + 1.0)))
        risk_aversion.append(max(0.1, min(0.9, liabilities_f / max(assets_f, 1.0))))
        is_employed.append(employees_f > 0.0)
        employer_id.append(idx)
        household_cell_id.append(-1)
        firms_labor_count.append(employees_f)
        firms_wage_offer.append(revenue_f / max(employees_f, 1.0) / 12.0)
        firms_active.append(True)
        firms_firm_id.append(idx)
        firms_cell_id.append(cell_id)
        firms_type_id.append(sector_index[sector])
        acc = cell_accumulators[key]
        acc["count"] = float(acc["count"]) + 1.0
        acc["employment"] = float(acc["employment"]) + employees_f
        acc["output"] = float(acc["output"]) + revenue_f
        acc["distress"].append(float(distress_score or 0.0))

    cell_region_code = [_region_numeric(key[0]) for key in cell_keys]
    cell_sector_id = [sector_index[key[1]] for key in cell_keys]
    cell_population = [float(cell_accumulators[key]["count"]) for key in cell_keys]
    cell_employment = [float(cell_accumulators[key]["employment"]) for key in cell_keys]
    cell_output = [float(cell_accumulators[key]["output"]) for key in cell_keys]
    cell_distress = [
        _mean_or_zero(cell_accumulators[key]["distress"])
        for key in cell_keys
    ]

    household_authority = l5_profile.family_authority("household_distribution")
    household_payload = _household_payload(
        household_rows,
        household_authority,
        l5_profile=l5_profile,
        world_model_record_ref=world_model_record_ref,
    )
    household_value_set = household_payload.get("value_outer_set", {})
    household_interval_widths = [
        max(0.0, float(width))
        for coordinate, width in zip(
            household_value_set.get("coordinates", ()),
            household_value_set.get("width", ()),
            strict=False,
        )
        if str(coordinate).startswith("household_cells.disposable_income[")
    ]
    payload = {
        "agents": {
            "income": income,
            "reported_income": reported_income,
            "skill_level": skill_level,
            "risk_aversion": risk_aversion,
            "is_employed": is_employed,
            "employer_id": employer_id,
            "household_cell_id": household_cell_id,
        },
        "firms": {
            "active": firms_active,
            "firm_id": firms_firm_id,
            "cell_id": firms_cell_id,
            "firm_type_id": firms_type_id,
            "labor_count": firms_labor_count,
            "wage_offer": firms_wage_offer,
        },
        "cells": {
            "active": [True for _ in cell_keys],
            "region_code": cell_region_code,
            "sector_id": cell_sector_id,
            "population": cell_population,
            "employment": cell_employment,
            "output": cell_output,
            "distress_score": cell_distress,
            "public_service_index": [1.0 for _ in cell_keys],
            "firm_count": cell_population,
        },
        "government_balance": budget_slice_amount_sum,
        "tax_rate": 0.0,
    }
    if household_payload:
        payload["household_cells"] = household_payload
    stats = {
        "bound_agent_count": len(rows),
        "bound_firm_count": len(rows),
        "bound_cell_count": len(cell_keys),
        "bound_household_cell_count": len(household_payload.get("cell_id", ())),
        "agent_registry_resolution_strategy": (
            "canonical_latest_record_then_ambiguous_region_sector_for_conflicts"
        ),
        "selected_agent_registry_duplicate_count": sum(
            1 for row in rows if int(row[11] or 0) > 1
        ),
        "selected_agent_registry_inconsistent_count": sum(
            1
            for row in rows
            if int(row[12] or 0) > 1 or int(row[13] or 0) > 1
        ),
        "ambiguous_region_agent_count": sum(
            1 for row in rows if str(row[2] or "") == "ambiguous_region"
        ),
        "ambiguous_sector_agent_count": sum(
            1 for row in rows if str(row[3] or "") == "ambiguous_sector"
        ),
        "sample_strategy": "deterministic_region_stratified_hash",
        "sample_stratification": "region_code",
        "bound_region_count": len({str(row[2] or "unknown_region") for row in rows}),
        "bound_sector_count": len(sector_ids),
        "household_identification_mode": household_authority.identification_mode,
        "household_value_authority": household_authority.value_authority,
        "household_trust_tier": household_authority.trust_tier,
        "household_trust_cap": household_authority.trust_cap,
        "household_proxy_bound_count": sum(
            1 for width in household_interval_widths if width > 0.0
        ),
        "household_point_tight_count": sum(
            1 for width in household_interval_widths if width == 0.0
        ),
        "household_disposable_income_interval_width_sum": round(
            sum(household_interval_widths),
            6,
        ),
        "budget_slice_row_count": budget_slice_count,
        "budget_slice_amount_sum": round(float(budget_slice_amount_sum), 6),
        "l4_total_rows": dict(totals),
        "d3_bias_corrected_sources": [
            "corrected_firm_panels.parquet",
            "calibrated_household_cells.parquet",
        ],
    }
    return payload, stats


def _household_payload(
    rows: Sequence[Sequence[Any]],
    authority: L5FamilyAuthority,
    *,
    l5_profile: L5FamilyBindingProfile,
    world_model_record_ref: str,
) -> dict[str, Any]:
    if not rows:
        return {}
    point_authority = authority.value_authority == "point"

    household_count: list[float] = []
    disposable_income: list[float] = []
    income_interval_lower: list[float] = []
    income_interval_upper: list[float] = []
    poverty_rate: list[float] = []
    poverty_interval_lower: list[float] = []
    poverty_interval_upper: list[float] = []
    transfer_intensity: list[float] = []
    transfer_interval_lower: list[float] = []
    transfer_interval_upper: list[float] = []
    for row in rows:
        income = max(0.0, float(row[2] or 0.0))
        weight = max(0.0, float(row[3] or 0.0))
        biased = bool(row[4])
        trust_weight = _clamp(float(row[5] or 0.0), 0.0, 1.0)
        market_income = max(0.0, float(row[6] or income))
        expenditure = max(0.0, float(row[7] or income))
        effective_trust = min(trust_weight, authority.trust_cap)
        uncertainty = max(0.0, 1.0 - effective_trust)

        if point_authority:
            income_lower = income_upper = income
            poverty_lower = poverty_upper = 1.0 if biased else 0.0
            transfer = _clamp(1.0 - trust_weight, 0.0, 1.0)
            transfer_lower = transfer_upper = transfer
        else:
            candidate_values = [income, market_income, expenditure]
            d3_lower = min(candidate_values)
            d3_upper = max(candidate_values)
            margin = max(
                income * uncertainty * 0.25,
                income * (0.05 if biased else 0.0),
                1.0 if income > 0.0 else 0.0,
            )
            income_lower = max(0.0, min(d3_lower, income - margin))
            income_upper = max(income_lower, d3_upper, income + margin)

            poverty = 1.0 if biased else 0.0
            poverty_margin = max(0.02, uncertainty * 0.25, 0.10 if biased else 0.0)
            poverty_lower = _clamp(poverty - poverty_margin, 0.0, 1.0)
            poverty_upper = max(poverty_lower, _clamp(poverty + poverty_margin, 0.0, 1.0))

            transfer = _clamp(1.0 - trust_weight, 0.0, 1.0)
            transfer_margin = max(0.02, uncertainty * 0.5)
            transfer_lower = _clamp(transfer - transfer_margin, 0.0, 1.0)
            transfer_upper = max(
                transfer_lower,
                _clamp(transfer + transfer_margin, 0.0, 1.0),
            )

        household_count.append(weight)
        disposable_income.append(income)
        income_interval_lower.append(income_lower)
        income_interval_upper.append(income_upper)
        poverty_rate.append(1.0 if biased else 0.0)
        poverty_interval_lower.append(poverty_lower)
        poverty_interval_upper.append(poverty_upper)
        transfer = _clamp(1.0 - trust_weight, 0.0, 1.0)
        transfer_intensity.append(transfer)
        transfer_interval_lower.append(transfer_lower)
        transfer_interval_upper.append(transfer_upper)

    coordinates: list[str] = []
    lower: list[float] = []
    upper: list[float] = []
    for idx in range(len(rows)):
        coordinates.extend(
            [
                f"household_cells.disposable_income[{idx}]",
                f"household_cells.poverty_rate[{idx}]",
                f"household_cells.transfer_intensity[{idx}]",
            ]
        )
        lower.extend(
            [
                income_interval_lower[idx],
                poverty_interval_lower[idx],
                transfer_interval_lower[idx],
            ]
        )
        upper.extend(
            [
                income_interval_upper[idx],
                poverty_interval_upper[idx],
                transfer_interval_upper[idx],
            ]
        )

    regime_scope = (
        l5_profile.regime_ids[0]
        if l5_profile.schema_regime_status == "single_regime" and l5_profile.regime_ids
        else f"{l5_profile.schema_regime_status}:{'|'.join(l5_profile.regime_ids)}"
    )
    value_outer_set = ValueOuterSet.interval_box(
        coordinates=tuple(coordinates),
        lower=tuple(lower),
        upper=tuple(upper),
        identification_mode=authority.identification_mode,
        assumptions=(
            "d3_bias_corrected_household_cells",
            f"l5_identification_mode:{authority.identification_mode}",
            f"schema_regime_status:{l5_profile.schema_regime_status}",
        ),
        assumption_status="externally_supported",
        calibration_scope={
            "population": "ukraine_household_cells",
            "regime": regime_scope,
            "measurement": authority.family_id,
        },
        data_trust=DataTrust(
            tier=authority.trust_tier,
            trust_cap=authority.trust_cap,
            trust_multiplier=authority.trust_multiplier,
            min_coverage=authority.min_coverage,
            max_coverage=authority.max_coverage,
            promotion_floor=authority.promotion_floor,
            authority_ref=authority.measurement_registry_ref,
        ),
        world_model_record_ref=world_model_record_ref,
        epoch=regime_scope,
        representation_status="certified",
    )

    return {
        "active": [True for _ in rows],
        "cell_id": [idx for idx, _row in enumerate(rows)],
        "household_count": household_count,
        "disposable_income": disposable_income,
        "poverty_rate": poverty_rate,
        "transfer_intensity": transfer_intensity,
        "value_outer_set": value_outer_set.model_dump(mode="json"),
    }


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _write_data_forge_snapshot_binding(
    *,
    workspace_dir: Path,
    snapshot_id: str,
    payload: Mapping[str, Any],
    payload_content_hash: str,
) -> Path:
    snapshot_root = workspace_dir / snapshot_id
    pipeline_root = snapshot_root / "ukraine"
    artifact_path = pipeline_root / "data_state_payload.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_publish_manifest(
        manifest_path=pipeline_root / "publish" / "manifest.json",
        pipeline="ukraine",
        artifacts=(artifact_path,),
        published_at="2026-05-01T00:00:00+00:00",
        extra={
            "corpus_id": "ukraine-real-l4-data-state",
            "builder_revision": (
                "polisyos.runtime.quality.data_state_substrate."
                "materialize_l4_data_state_snapshot"
            ),
            "lineage_refs": [
                payload_content_hash,
                "repo://production_data/canonical/local_data_20260501/"
                "ukraine_server_support_20260410/normalized_corpus",
                "repo://production_data/datasets_full_phase3full_20260327_183054/"
                "dataset_catalog.duckdb",
            ],
            "claim_requirement_bindings": [
                {
                    "claim_id": "gy-s1-real-l4-data-state",
                    "requirement_id": "gy-s1-l1-l4-l5-data-state",
                    "requirement_kind": "production_data_state",
                    "authority_level": "closeout",
                    "time_role": "observation_time",
                }
            ],
        },
    )
    finalize_snapshot(
        snapshot_root,
        update_latest_symlink=False,
        pipelines=("ukraine",),
    )
    return snapshot_root / "data_forge_snapshot_binding.json"


def _write_fabric_world_snapshot(
    *,
    workspace_dir: Path,
    snapshot_id: str,
    payload_hash: str,
    stats: Mapping[str, Any],
) -> Path:
    from polisyos.fabric.io.db import SimulationDB
    from polisyos.fabric.world import ensure_world_schema
    from polisyos.fabric.world.store import create_world_snapshot

    snapshot_root = workspace_dir / "fabric-world"
    db_path = workspace_dir / "fabric-world.duckdb"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with SimulationDB(db_path=str(db_path)) as db:
        ensure_world_schema(db)
        node_id = f"world.data_state.{snapshot_id}"
        fact_ids = (
            f"fact:{snapshot_id}:bound_agent_count",
            f"fact:{snapshot_id}:payload_hash",
        )
        db.conn.execute(
            "DELETE FROM world.world_facts WHERE fact_id IN (?, ?)",
            list(fact_ids),
        )
        db.conn.execute("DELETE FROM world.world_nodes WHERE node_id = ?", [node_id])
        db.conn.execute(
            """
            INSERT INTO world.world_nodes (node_id, kind, label, artifact_id)
            VALUES (?, 'data_state', 'GY-S1 real L4 data-state substrate', ?)
            """,
            [node_id, payload_hash],
        )
        db.conn.execute(
            """
            INSERT INTO world.world_facts (
                fact_id,
                schema_version,
                subject_id,
                predicate_id,
                object_value,
                target_id,
                valid_time,
                tx_time,
                provenance_json,
                trust_json,
                legal_json,
                segment_id
            )
            VALUES
                (?, '1.0', ?, 'data_state.bound_agent_count', ?, NULL,
                 '2026-05-01T00:00:00Z', '2026-05-01T00:00:00Z', ?, NULL, NULL, ?),
                (?, '1.0', ?, 'data_state.payload_hash', ?, NULL,
                 '2026-05-01T00:00:00Z', '2026-05-01T00:00:00Z', ?, NULL, NULL, ?)
            """,
            [
                fact_ids[0],
                node_id,
                str(stats.get("bound_agent_count") or 0),
                json.dumps({"producer": "data_state_substrate"}, sort_keys=True),
                f"seg:{snapshot_id}:count",
                fact_ids[1],
                node_id,
                payload_hash,
                json.dumps({"producer": "data_state_substrate"}, sort_keys=True),
                f"seg:{snapshot_id}:hash",
            ],
        )
        create_world_snapshot(
            db,
            snapshot_root=snapshot_root,
            snapshot_id=snapshot_id,
            branch_name="observed",
            as_of_valid_time="2026-05-01T00:00:00+00:00",
            as_of_tx_time="2026-05-01T00:00:00+00:00",
            provenance={
                "producer": (
                    "polisyos.runtime.quality.data_state_substrate."
                    "_write_fabric_world_snapshot"
                ),
                "payload_hash": payload_hash,
            },
        )
    return snapshot_root


def _production_skg_ref(repo_root: Path, *, snapshot_id: str) -> SkgCausalPriorRef:
    from polisyos.data_forge.read_api.academic import SKGQuery

    db_path = repo_root / _ACADEMIC_SKG_DB
    if not db_path.exists():
        raise DataStateSubstrateError("skg_prior_ref_unresolved", db_path.as_posix())
    query = SKGQuery(db_path=db_path, index_dir=db_path.parent / "index")
    try:
        version_id = query.latest_skg_version_id()
        snapshot_ref = query.skg_snapshot_ref(version_id=version_id)
    finally:
        query.close()
    if snapshot_ref is None:
        raise DataStateSubstrateError("skg_prior_ref_unresolved", "missing SKG snapshot ref")
    return SkgCausalPriorRef(
        skg_snapshot_ref=snapshot_ref,
        skg_version_id=str(version_id),
        source_data_snapshot_id=snapshot_id,
        edge_prior_refs=("skg-edge://gy-s1-forward-hook",),
        transport_score_refs=("skg-transport://gy-s1-forward-hook",),
        query_trace_refs=("g2-skg-query-trace://gy-s1-forward-hook",),
    )


def _schema_regime_decision(
    l5: L5CatalogAuthority,
    *,
    period_start: str,
    period_end: str,
) -> dict[str, Any]:
    start_month = _month_ordinal(period_start)
    end_month = _month_ordinal(period_end)
    if start_month > end_month:
        raise DataStateSubstrateError("schema_regime_period_order_invalid")
    v1 = l5.schema_regimes.get("ukraine_schema_v1")
    v2 = l5.schema_regimes.get("ukraine_schema_v2")
    if v1 is None or v2 is None:
        raise DataStateSubstrateError("l5_schema_regime_missing")
    changepoint_month = _month_ordinal(v2.effective_start or "2022-02")
    boundary_buffer = max(v1.boundary_buffer_periods or 0, v2.boundary_buffer_periods or 0)
    if start_month < changepoint_month <= end_month:
        status = "spans_changepoint_flagged"
        regime_ids = ("ukraine_schema_v1", "ukraine_schema_v2")
    elif (
        abs(start_month - changepoint_month) <= boundary_buffer
        or abs(end_month - changepoint_month) <= boundary_buffer
    ):
        status = "boundary_buffer_flagged"
        regime_ids = (
            ("ukraine_schema_v1",)
            if end_month < changepoint_month
            else ("ukraine_schema_v2",)
        )
    else:
        status = "single_regime"
        regime_ids = (
            ("ukraine_schema_v1",)
            if end_month < changepoint_month
            else ("ukraine_schema_v2",)
        )
    return {
        "schema_regime_status": status,
        "regime_ids": regime_ids,
        "changepoint_id": "schema.2022_02_wartime",
        "changepoint_period": "2022-02",
        "boundary_buffer_periods": boundary_buffer,
    }


def _default_data_state_paths(repo_root: Path) -> _DataStatePaths:
    base = (
        repo_root
        / "production_data/canonical/local_data_20260501/"
        "ukraine_server_support_20260410"
    )
    normalized = base / "normalized_corpus/normalized"
    d3 = base / "runtime_calibration_internals/calibration/d3"
    l1 = default_substrate_catalog_paths(repo_root).l1_dcat_path
    return _DataStatePaths(
        l1_dcat_path=l1,
        agent_registry_full=normalized / "edr_current/agent_registry_full.parquet",
        firm_fundamentals_annual=(
            normalized / "dps_financials/firm_fundamentals_annual.parquet"
        ),
        budget_flows_monthly_sparse=(
            normalized / "spending_full/budget_flows_monthly_sparse.parquet"
        ),
        corrected_firm_panels=d3 / "corrected_firm_panels.parquet",
        calibrated_household_cells=d3 / "calibrated_household_cells.parquet",
    )


def _require_paths(paths: _DataStatePaths) -> None:
    for path in (
        paths.l1_dcat_path,
        paths.agent_registry_full,
        paths.firm_fundamentals_annual,
        paths.budget_flows_monthly_sparse,
        paths.corrected_firm_panels,
        paths.calibrated_household_cells,
    ):
        if not path.exists():
            raise DataStateSubstrateError("production_data_path_missing", path.as_posix())


def _relative_source_paths(paths: _DataStatePaths, root: Path) -> dict[str, str]:
    return {
        key: path.relative_to(root).as_posix()
        for key, path in {
            "l1_dcat_path": paths.l1_dcat_path,
            "agent_registry_full": paths.agent_registry_full,
            "firm_fundamentals_annual": paths.firm_fundamentals_annual,
            "budget_flows_monthly_sparse": paths.budget_flows_monthly_sparse,
            "corrected_firm_panels": paths.corrected_firm_panels,
            "calibrated_household_cells": paths.calibrated_household_cells,
        }.items()
    }


def _world_preimage_ref(
    *,
    substrate_version_id: str,
    agent_limit: int | None,
    required_l1_variables: Sequence[str],
    families: Sequence[str],
    period_start: str,
    period_end: str,
    branch_mode: str,
) -> str:
    preimage = {
        "schema_version": DATA_STATE_SUBSTRATE_SCHEMA_VERSION,
        "world_identity_kind": "gy-n3-world-preimage",
        "substrate_version_id": substrate_version_id,
        "slice": {
            "agent_limit": "full" if agent_limit is None else int(agent_limit),
            "sample_strategy": "deterministic_region_stratified_hash",
        },
        "required_l1_variables": tuple(sorted(str(item) for item in required_l1_variables)),
        "families": tuple(sorted(str(item) for item in families)),
        "period_start": period_start,
        "period_end": period_end,
        "branch_mode": branch_mode,
    }
    return f"gy-n3:world-preimage:{gy_content_hash(preimage)}"


def _snapshot_id(*, agent_limit: int | None, payload_hash: str) -> str:
    prefix = "gy-s1-l4-data-state"
    limit = "full" if agent_limit is None else str(agent_limit)
    suffix = payload_hash.removeprefix("sha256:")[:16]
    return f"{prefix}-{limit}-{suffix}"


def _value_authority_for_identification(
    mode: str,
) -> Literal["point", "bounds", "proxy_bounds", "limited"]:
    if mode == "point_identified":
        return "point"
    if mode == "proxy_identified":
        return "proxy_bounds"
    if mode in {"partially_identified", "bounds_only"}:
        return "bounds"
    return "limited"


def _month_ordinal(period: str) -> int:
    parts = period.split("-")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise DataStateSubstrateError("schema_regime_period_invalid", period)
    return int(parts[0]) * 12 + int(parts[1])


def _region_numeric(value: str) -> int:
    digits = "".join(char for char in value if char.isdigit())
    return int(digits or 0)


def _mean_or_zero(values: object) -> float:
    if not isinstance(values, list) or not values:
        return 0.0
    return float(sum(float(value) for value in values) / len(values))


__all__ = [
    "DATA_STATE_SUBSTRATE_SCHEMA_VERSION",
    "DataStateMaterializationResult",
    "DataStateSubstrateError",
    "L1VariableAvailability",
    "L5FamilyAuthority",
    "L5FamilyBindingProfile",
    "ProductionDataStateWorldBuildResult",
    "build_l5_family_binding_profile",
    "build_production_data_state_world_model_record",
    "l1_dcat_variable_availability",
    "materialize_l4_data_state_snapshot",
]
