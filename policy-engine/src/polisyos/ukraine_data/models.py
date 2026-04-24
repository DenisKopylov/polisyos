"""Typed configuration models for the Ukraine Part B build stack."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    ObservationFamily,
    SourceConfidenceTier,
)
from polisyos.ir.types import TimeFrequency


class StageId(str, Enum):
    """Stable stage identifiers used by the Ukraine data orchestrator."""

    BOOTSTRAP_SERVER = "bootstrap_server"
    VALIDATE_PART_A = "validate_part_a"
    D0_P0 = "d0_p0"
    D1 = "d1"
    D2 = "d2"
    D3 = "d3"
    D4 = "d4"
    D5 = "d5"
    FULL = "full"
    RELEASE = "release"


class ResourceBudget(BaseModel):
    """Resource hints recorded in manifests and used by schedulers."""

    model_config = ConfigDict(extra="forbid")

    max_workers: int = Field(default=1, ge=1)
    memory_gib: float | None = Field(default=None, gt=0.0)
    disk_gib: float | None = Field(default=None, gt=0.0)
    time_budget_s: float | None = Field(default=None, gt=0.0)


class ArtifactRetentionPolicy(BaseModel):
    """Retention toggles for raw, normalized, and intermediate outputs."""

    model_config = ConfigDict(extra="forbid")

    keep_raw: bool = True
    keep_normalized: bool = True
    keep_runtime_intermediates: bool = True
    keep_calibration_intermediates: bool = True
    compress_raw: bool = False


class CountRange(BaseModel):
    """Expected inclusive count range for runtime validation."""

    model_config = ConfigDict(extra="forbid")

    min_count: int = Field(..., ge=0)
    max_count: int = Field(..., ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> CountRange:
        if self.max_count < self.min_count:
            raise ValueError("max_count must be >= min_count")
        return self


class ServerConfig(BaseModel):
    """Target server information and server-only execution guard settings."""

    model_config = ConfigDict(extra="forbid")

    host: str = "204.168.164.187"
    user: str = "root"
    port: int = Field(default=22, ge=1, le=65535)
    workdir: Path = Path("/srv/polisyos/repo/policy-engine")
    storage_root: Path = Path("/srv/polisyos/ukraine-data")
    cas_root: Path = Path("/srv/polisyos/.polisyos/cas")
    python_bin: str = "python3"
    uv_bin: str = "uv"
    server_marker_env: str = "POLISYOS_SERVER_EXECUTION"
    require_server_for_build: bool = True
    bootstrap_packages: list[str] = Field(
        default_factory=lambda: [
            "build-essential",
            "curl",
            "gdal-bin",
            "git",
            "jq",
            "logrotate",
            "osmium-tool",
            "p7zip-full",
            "python3",
            "python3-dev",
            "python3-pip",
            "python3-venv",
            "rsync",
            "tmux",
        ]
    )
    bootstrap_extras: list[str] = Field(default_factory=lambda: ["runtime", "ml", "research"])

    @property
    def ssh_target(self) -> str:
        return f"{self.user}@{self.host}"

    @property
    def env_path(self) -> Path:
        return self.storage_root / "env.sh"


class BuildRootConfig(BaseModel):
    """Filesystem layout for raw, normalized, runtime, and release artifacts."""

    model_config = ConfigDict(extra="forbid")

    root: Path = Path("production_data/ukraine_part_b")
    cas_root: Path | None = None

    @property
    def raw_dir(self) -> Path:
        return self.root / "raw"

    @property
    def normalized_dir(self) -> Path:
        return self.root / "normalized"

    @property
    def runtime_dir(self) -> Path:
        return self.root / "runtime"

    @property
    def calibration_dir(self) -> Path:
        return self.root / "calibration"

    @property
    def bundles_dir(self) -> Path:
        return self.root / "bundles"

    @property
    def manifests_dir(self) -> Path:
        return self.root / "manifests"

    @property
    def tmp_dir(self) -> Path:
        return self.root / "tmp"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def metrics_prom_path(self) -> Path:
        return self.manifests_dir / "metrics.prom"

    @property
    def stage_metrics_path(self) -> Path:
        return self.manifests_dir / "stage_metrics.json"

    @property
    def resource_usage_path(self) -> Path:
        return self.manifests_dir / "resource_usage.jsonl"

    @property
    def part_a_gate_manifest_path(self) -> Path:
        return self.manifests_dir / "part_a_gate_manifest.json"

    @property
    def capability_manifest_path(self) -> Path:
        return self.manifests_dir / "server_capability_manifest.json"

    @property
    def resolved_cas_root(self) -> Path:
        return self.cas_root or (self.root / ".cas")


class StageConfig(BaseModel):
    """Static stage requirements, resource budgets, and validation thresholds."""

    model_config = ConfigDict(extra="forbid")

    stage_id: StageId
    server_only: bool = True
    required_sources: list[str] = Field(default_factory=list)
    required_previous_stages: list[StageId] = Field(default_factory=list)
    output_artifacts: list[str] = Field(default_factory=list)
    coverage_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    final_signoff_waived_families: list[ObservationFamily] = Field(default_factory=list)
    expected_agent_count: CountRange | None = None
    expected_cell_count: CountRange | None = None
    resource_budget: ResourceBudget = Field(default_factory=ResourceBudget)
    notes: list[str] = Field(default_factory=list)


class SourceConfig(BaseModel):
    """Per-source adapter configuration and normalized observation metadata."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., min_length=1, max_length=120)
    display_name: str = Field(..., min_length=1, max_length=255)
    stage_id: StageId
    adapter_id: str = Field(default="tabular", min_length=1, max_length=120)
    required: bool = True
    endpoint: str | None = None
    local_path: Path | None = None
    raw_format: str = Field(default="parquet", min_length=1, max_length=32)
    normalized_artifact: str = Field(..., min_length=1, max_length=255)
    required_columns: list[str] = Field(default_factory=list)
    column_map: dict[str, str] = Field(default_factory=dict)
    identity_columns: list[str] = Field(default_factory=list)
    metric_columns: list[str] = Field(default_factory=list)
    observation_family: ObservationFamily | None = None
    entity_scope: EntityScope | None = None
    time_grain: TimeFrequency = TimeFrequency.MONTH
    period_column: str = "period_id"
    period_start_column: str | None = None
    period_end_column: str | None = None
    entity_id_column: str | None = "agent_id"
    cell_id_column: str | None = "cell_id"
    region_code_column: str | None = "region_code"
    sector_id_column: str | None = "sector_id"
    source_version: str = "1.0"
    regime_id: str = "regime_a"
    schema_regime_id: str = "ukraine_schema_v1"
    source_confidence_tier: SourceConfidenceTier = SourceConfidenceTier.VALIDATED
    coverage_estimate: float = Field(default=0.95, ge=0.0, le=1.0)
    trust_weight: float = Field(default=0.9, ge=0.0)
    identification_mode: IdentificationMode = IdentificationMode.POINT_IDENTIFIED
    optional_reason: str | None = None

    @property
    def manifest_name(self) -> str:
        return f"{self.source_id}_normalized_artifact_manifest.json"


class PipelineConfig(BaseModel):
    """Top-level configuration bundle for the Ukraine data build stack."""

    model_config = ConfigDict(extra="forbid")

    server: ServerConfig = Field(default_factory=ServerConfig)
    build_root: BuildRootConfig = Field(default_factory=BuildRootConfig)
    retention: ArtifactRetentionPolicy = Field(default_factory=ArtifactRetentionPolicy)
    stages: dict[str, StageConfig]
    sources: dict[str, SourceConfig]

    @model_validator(mode="after")
    def validate_pipeline(self) -> PipelineConfig:
        for key, stage in self.stages.items():
            if key != stage.stage_id.value:
                raise ValueError(f"stage key mismatch: {key!r} != {stage.stage_id.value!r}")
        for key, source in self.sources.items():
            if key != source.source_id:
                raise ValueError(f"source key mismatch: {key!r} != {source.source_id!r}")
        return self


def _default_stage_configs() -> dict[str, StageConfig]:
    return {
        StageId.D0_P0.value: StageConfig(
            stage_id=StageId.D0_P0,
            required_sources=[
                "edr_current",
                "spending_full",
                "spending_contracts_procurement_proxy",
                "prozorro_full",
                "macro_nbu_derzhstat",
                "dps_financials",
            ],
            output_artifacts=[
                "agent_registry_runtime.parquet",
                "public_entity_registry.parquet",
                "cell_registry_region_sector.parquet",
                "cell_state_seed_v1.npz",
                "budget_graph_sparse.npz",
                "procurement_graph_sparse.npz",
                "edr_identity_bridge_unresolved.parquet",
                "edr_identity_bridge_candidates.parquet",
                "edr_identity_bridge_resolved.parquet",
                "edr_identity_bridge_manifest.json",
                "geo_index_runtime.parquet",
                "slot_family_manifest.json",
                "runtime_bundle_manifest.json",
            ],
            expected_agent_count=CountRange(min_count=1, max_count=10_000_000),
            expected_cell_count=CountRange(min_count=1, max_count=500_000),
            resource_budget=ResourceBudget(max_workers=4, memory_gib=24.0, time_budget_s=14_400.0),
        ),
        StageId.D1.value: StageConfig(
            stage_id=StageId.D1,
            required_previous_stages=[StageId.D0_P0],
            required_sources=[
                "dps_tax_risk",
                "customs_trade",
                "customs_vehicles",
                "employment_service",
                "license_registry",
                "budget_managers",
                "nszu_payments",
                "yedebo",
                "yedessb",
                "road_characteristics",
                "osm_exact",
                "spatial_exogenous",
            ],
            output_artifacts=[
                "trade_graph_sparse.npz",
                "distress_graph_sparse.npz",
                "public_service_graph_sparse.npz",
                "trade_network_data.json",
                "trade_network_causal_data.json",
                "distress_network_data.json",
                "distress_network_causal_data.json",
                "public_service_network_data.json",
                "public_service_network_causal_data.json",
                "multiplex_graph_manifest.json",
                "proxy_identification_bundle_v1.json",
            ],
            resource_budget=ResourceBudget(max_workers=6, memory_gib=28.0, time_budget_s=28_800.0),
        ),
        StageId.D2.value: StageConfig(
            stage_id=StageId.D2,
            required_previous_stages=[StageId.D1],
            output_artifacts=[
                "observation_panel_monthly.parquet",
                "observation_panel_annual.parquet",
                "measurement_registry.json",
                "schema_regime_registry.json",
                "identification_mode_registry.json",
                "regime_calendar.json",
                "shock_calendar.json",
                "changepoint_registry.json",
                "calibration_splits.json",
                "negative_control_panel.parquet",
                "jax_calibration_bundle_v1.npz",
                "calibration_dictionary.json",
                "causal_panel_bundle_monthly.parquet",
                "panel_econometric_bundle_v1.parquet",
                "survival_data_bundle_v1.parquet",
                "dtr_treatment_sequence_bundle_v1.npz",
                "specification_curve_input_v1.json",
                "leontief_io_bundle_v1.json",
                "backtest_plan_bundle.json",
                "network_contract_bundle_v1.json",
                "network_causal_contract_bundle_v1.json",
                "bounds_estimation_bundle_v1.json",
                "governance_pass_mapping_v1.json",
                "strategic_response_specs_v1.json",
                "observation_to_contract_manifest.json",
            ],
            resource_budget=ResourceBudget(max_workers=6, memory_gib=28.0, time_budget_s=28_800.0),
        ),
        StageId.D3.value: StageConfig(
            stage_id=StageId.D3,
            required_previous_stages=[StageId.D2],
            required_sources=[
                "household_microdata",
                "labor_force_microdata",
                "pfu_debt",
                "wage_arrears",
                "distress_events",
                "logistics_mobility_displacement",
                "land_cadastre",
            ],
            output_artifacts=[
                "microsim_survey_contract_v1.json",
                "corrected_firm_panels.parquet",
                "survival_hazard_estimates.parquet",
                "calibrated_household_cells.parquet",
                "labor_validation_panel.parquet",
                "labor_market_corrected_panel.parquet",
                "labor_bias_validation.json",
                "lesson_registry_seed_v1.json",
                "logistics_mobility_displacement_skipped_source_manifest.json",
                "land_cadastre_skipped_source_manifest.json",
            ],
            resource_budget=ResourceBudget(max_workers=4, memory_gib=28.0, time_budget_s=21_600.0),
        ),
        StageId.D4.value: StageConfig(
            stage_id=StageId.D4,
            required_previous_stages=[StageId.D3],
            final_signoff_waived_families=[
                ObservationFamily.PROCUREMENT_FLOWS,
                ObservationFamily.DISTRESS_ENFORCEMENT,
            ],
            output_artifacts=[
                "calibration_run_manifest.json",
                "family_eligibility_registry.json",
                "loss_breakdown.json",
                "holdout_scores.json",
                "shock_scenario_scores.json",
                "calibration_leaderboard.json",
                "transportability_results.json",
                "strategic_response_metrics.json",
                "specification_curve_summary.json",
                "foundry_seed_state_v1.npz",
                "replay_artifacts.json",
                "governance_report_v1.json",
                "lesson_registry_d4.json",
            ],
            resource_budget=ResourceBudget(max_workers=16, memory_gib=28.0, time_budget_s=7_200.0),
            notes=[
                "Current policy cycle treats procurement proxy and distress proxy families as diagnostic-only waivers for final sign-off.",
                "Remaining exact-signoff uplift is focused on EDR identity bridge and labor-market evidence.",
            ],
        ),
        StageId.D5.value: StageConfig(
            stage_id=StageId.D5,
            required_previous_stages=[StageId.D4],
            output_artifacts=[
                "agent_embedding_32d.npz",
                "cell_prototype_embeddings.npz",
                "graph_compression_bundle.json",
                "lex_intervention_map.json",
                "intervention_knob_dictionary.json",
                "temporal_intervention_sequences.json",
                "policy_scenario_templates.json",
                "provision_to_program_crosswalk.parquet",
                "runtime_bundle_v1/",
                "calibration_bundle_v1/",
                "method_contract_bundle_v1/",
                "governance_report_v1/",
                "intervention_bundle_v1/",
                "embedding_bundle_v1/",
                "release_acceptance_report.json",
                "release_manifest_v1.json",
            ],
            resource_budget=ResourceBudget(max_workers=8, memory_gib=28.0, time_budget_s=14_400.0),
        ),
    }


def _source(
    *,
    source_id: str,
    display_name: str,
    stage_id: StageId,
    normalized_artifact: str,
    required_columns: list[str],
    observation_family: ObservationFamily | None = None,
    entity_scope: EntityScope | None = None,
    identity_columns: list[str] | None = None,
    metric_columns: list[str] | None = None,
    required: bool = True,
    optional_reason: str | None = None,
    identification_mode: IdentificationMode = IdentificationMode.POINT_IDENTIFIED,
) -> SourceConfig:
    return SourceConfig(
        source_id=source_id,
        display_name=display_name,
        stage_id=stage_id,
        normalized_artifact=normalized_artifact,
        required_columns=required_columns,
        observation_family=observation_family,
        entity_scope=entity_scope,
        identity_columns=list(identity_columns or []),
        metric_columns=list(metric_columns or []),
        required=required,
        optional_reason=optional_reason,
        identification_mode=identification_mode,
    )


def _default_source_configs() -> dict[str, SourceConfig]:
    sources = [
        _source(
            source_id="edr_current",
            display_name="ЄДР current dump",
            stage_id=StageId.D0_P0,
            normalized_artifact="agent_registry_full.parquet",
            required_columns=["agent_id", "registration_code", "region_code", "sector_id"],
        ),
        _source(
            source_id="spending_full",
            display_name="Spending.gov.ua full horizon",
            stage_id=StageId.D0_P0,
            normalized_artifact="budget_flows_monthly_sparse.parquet",
            required_columns=[
                "source_agent_id",
                "target_agent_id",
                "amount",
                "period_id",
                "registration_code",
            ],
            observation_family=ObservationFamily.BUDGET_FLOWS,
            entity_scope=EntityScope.AGENT,
            identity_columns=["source_agent_id", "target_agent_id", "registration_code"],
            metric_columns=["amount"],
            identification_mode=IdentificationMode.INTERFERENCE_AWARE,
        ),
        _source(
            source_id="spending_contracts_procurement_proxy",
            display_name="Spending.gov.ua contracts procurement proxy",
            stage_id=StageId.D0_P0,
            normalized_artifact="procurement_contracts_monthly.parquet",
            required_columns=[
                "buyer_agent_id",
                "supplier_agent_id",
                "amount",
                "period_id",
                "registration_code",
            ],
            observation_family=ObservationFamily.PROCUREMENT_FLOWS,
            entity_scope=EntityScope.AGENT,
            identity_columns=["buyer_agent_id", "supplier_agent_id", "registration_code"],
            metric_columns=["amount"],
            required=False,
            optional_reason="Official Spending contracts procurement proxy used when exact Prozorro contract details are unavailable.",
            identification_mode=IdentificationMode.INTERFERENCE_AWARE,
        ),
        _source(
            source_id="prozorro_full",
            display_name="Prozorro full horizon",
            stage_id=StageId.D0_P0,
            normalized_artifact="procurement_contracts_monthly.parquet",
            required_columns=[
                "buyer_agent_id",
                "supplier_agent_id",
                "amount",
                "period_id",
                "registration_code",
            ],
            observation_family=ObservationFamily.PROCUREMENT_FLOWS,
            entity_scope=EntityScope.AGENT,
            identity_columns=["buyer_agent_id", "supplier_agent_id", "registration_code"],
            metric_columns=["amount"],
            identification_mode=IdentificationMode.INTERFERENCE_AWARE,
        ),
        _source(
            source_id="macro_nbu_derzhstat",
            display_name="НБУ + Держстат macro panels",
            stage_id=StageId.D0_P0,
            normalized_artifact="macro_panel_monthly.parquet",
            required_columns=["period_id", "metric_id", "observed_value", "region_code"],
            observation_family=ObservationFamily.MACRO_STATE,
            entity_scope=EntityScope.REGION,
            metric_columns=["observed_value"],
        ),
        _source(
            source_id="dps_financials",
            display_name="DPS financial statements",
            stage_id=StageId.D0_P0,
            normalized_artifact="firm_fundamentals_annual.parquet",
            required_columns=[
                "agent_id",
                "period_id",
                "revenue",
                "assets",
                "liabilities",
                "employees",
            ],
            observation_family=ObservationFamily.FIRM_FUNDAMENTALS,
            entity_scope=EntityScope.FIRM,
            identity_columns=["agent_id", "registration_code"],
            metric_columns=["revenue", "assets", "liabilities", "employees"],
        ),
        _source(
            source_id="dps_tax_risk",
            display_name="DPS tax/risk layer",
            stage_id=StageId.D1,
            normalized_artifact="compliance_distress_signals_monthly.parquet",
            required_columns=["agent_id", "period_id", "tax_debt", "risk_score"],
            observation_family=ObservationFamily.DISTRESS_ENFORCEMENT,
            entity_scope=EntityScope.FIRM,
            identity_columns=["agent_id", "registration_code"],
            metric_columns=["tax_debt", "risk_score"],
            identification_mode=IdentificationMode.PROXY_IDENTIFIED,
        ),
        _source(
            source_id="customs_trade",
            display_name="Customs trade exposure",
            stage_id=StageId.D1,
            normalized_artifact="trade_exposure_monthly.parquet",
            required_columns=["source_agent_id", "target_agent_id", "trade_value", "period_id"],
            observation_family=ObservationFamily.TRADE_EXPOSURE,
            entity_scope=EntityScope.AGENT,
            identity_columns=["source_agent_id", "target_agent_id", "registration_code"],
            metric_columns=["trade_value"],
            identification_mode=IdentificationMode.INTERFERENCE_AWARE,
        ),
        _source(
            source_id="customs_vehicles",
            display_name="Customs commercial vehicles",
            stage_id=StageId.D1,
            normalized_artifact="logistics_friction_monthly.parquet",
            required_columns=["agent_id", "period_id", "vehicle_delay_hours", "queue_length"],
            observation_family=ObservationFamily.LOGISTICS_FRICTION,
            entity_scope=EntityScope.AGENT,
            identity_columns=["agent_id", "registration_code"],
            metric_columns=["vehicle_delay_hours", "queue_length"],
            identification_mode=IdentificationMode.PROXY_IDENTIFIED,
        ),
        _source(
            source_id="employment_service",
            display_name="Employment service",
            stage_id=StageId.D1,
            normalized_artifact="labor_market_panel_monthly.parquet",
            required_columns=["agent_id", "period_id", "employment_count", "vacancies"],
            observation_family=ObservationFamily.LABOR_MARKET,
            entity_scope=EntityScope.AGENT,
            identity_columns=["agent_id", "registration_code"],
            metric_columns=["employment_count", "vacancies"],
            identification_mode=IdentificationMode.PROXY_IDENTIFIED,
        ),
        _source(
            source_id="license_registry",
            display_name="License registry",
            stage_id=StageId.D1,
            normalized_artifact="regulated_activity_flags.parquet",
            required_columns=["agent_id", "period_id", "license_flag"],
            observation_family=ObservationFamily.FIRM_FUNDAMENTALS,
            entity_scope=EntityScope.FIRM,
            identity_columns=["agent_id", "registration_code"],
            metric_columns=["license_flag"],
        ),
        _source(
            source_id="budget_managers",
            display_name="Budget managers and recipients registry",
            stage_id=StageId.D1,
            normalized_artifact="public_budget_manager_registry.parquet",
            required_columns=["agent_id", "period_id", "is_budget_manager"],
            observation_family=ObservationFamily.PUBLIC_SERVICE_DOMAIN_FLOWS,
            entity_scope=EntityScope.AGENT,
            identity_columns=["agent_id", "registration_code"],
            metric_columns=["is_budget_manager"],
        ),
        _source(
            source_id="nszu_payments",
            display_name="NSZU payments",
            stage_id=StageId.D1,
            normalized_artifact="public_service_observation_panel_monthly.parquet",
            required_columns=["source_agent_id", "target_agent_id", "payment_amount", "period_id"],
            observation_family=ObservationFamily.PUBLIC_SERVICE_DOMAIN_FLOWS,
            entity_scope=EntityScope.AGENT,
            identity_columns=["source_agent_id", "target_agent_id", "registration_code"],
            metric_columns=["payment_amount"],
        ),
        _source(
            source_id="yedebo",
            display_name="ЄДЕБО / education",
            stage_id=StageId.D1,
            normalized_artifact="education_entity_registry.parquet",
            required_columns=["agent_id", "period_id", "student_count", "capacity"],
            observation_family=ObservationFamily.EDUCATION_HUMAN_CAPITAL_SUPPLY,
            entity_scope=EntityScope.AGENT,
            identity_columns=["agent_id", "registration_code"],
            metric_columns=["student_count", "capacity"],
        ),
        _source(
            source_id="yedessb",
            display_name="ЄДЕССБ / construction",
            stage_id=StageId.D1,
            normalized_artifact="construction_activity_panel_monthly.parquet",
            required_columns=["agent_id", "period_id", "permit_count", "project_area"],
            observation_family=ObservationFamily.CONSTRUCTION_CAPITAL_FORMATION,
            entity_scope=EntityScope.AGENT,
            identity_columns=["agent_id", "registration_code"],
            metric_columns=["permit_count", "project_area"],
        ),
        _source(
            source_id="road_characteristics",
            display_name="Road characteristics",
            stage_id=StageId.D1,
            normalized_artifact="road_accessibility_cell_panel.parquet",
            required_columns=["cell_id", "period_id", "road_access_index", "travel_time_minutes"],
            observation_family=ObservationFamily.LOGISTICS_FRICTION,
            entity_scope=EntityScope.CELL,
            metric_columns=["road_access_index", "travel_time_minutes"],
            identification_mode=IdentificationMode.PROXY_IDENTIFIED,
        ),
        _source(
            source_id="osm_exact",
            display_name="OSM exact geo enrichment",
            stage_id=StageId.D1,
            normalized_artifact="geo_enrichment_exact.parquet",
            required_columns=["cell_id", "period_id", "amenity_density", "road_density"],
            observation_family=ObservationFamily.SPATIAL_RASTER_EXOGENOUS,
            entity_scope=EntityScope.CELL,
            metric_columns=["amenity_density", "road_density"],
        ),
        _source(
            source_id="spatial_exogenous",
            display_name="Raster and exogenous layers",
            stage_id=StageId.D1,
            normalized_artifact="spatial_cell_exogenous_monthly.parquet",
            required_columns=["cell_id", "period_id", "night_lights", "population_density"],
            observation_family=ObservationFamily.SPATIAL_RASTER_EXOGENOUS,
            entity_scope=EntityScope.CELL,
            metric_columns=["night_lights", "population_density"],
        ),
        _source(
            source_id="household_microdata",
            display_name="Household microdata",
            stage_id=StageId.D3,
            normalized_artifact="household_synthetic_targets.parquet",
            required_columns=["household_id", "cell_id", "period_id", "income", "weight"],
            observation_family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
            entity_scope=EntityScope.HOUSEHOLD,
            metric_columns=["income", "weight"],
        ),
        _source(
            source_id="labor_force_microdata",
            display_name="Labor-force microdata",
            stage_id=StageId.D3,
            normalized_artifact="labor_force_micro_targets.parquet",
            required_columns=["household_id", "cell_id", "period_id", "participation_rate"],
            observation_family=ObservationFamily.LABOR_MARKET,
            entity_scope=EntityScope.HOUSEHOLD,
            metric_columns=["participation_rate"],
            identification_mode=IdentificationMode.PROXY_IDENTIFIED,
        ),
        _source(
            source_id="pfu_debt",
            display_name="PFU debt",
            stage_id=StageId.D3,
            normalized_artifact="arrears_panel_monthly.parquet",
            required_columns=["agent_id", "period_id", "arrears_amount"],
            observation_family=ObservationFamily.DISTRESS_ENFORCEMENT,
            entity_scope=EntityScope.AGENT,
            identity_columns=["agent_id", "registration_code"],
            metric_columns=["arrears_amount"],
        ),
        _source(
            source_id="wage_arrears",
            display_name="Wage arrears",
            stage_id=StageId.D3,
            normalized_artifact="wage_arrears_panel_monthly.parquet",
            required_columns=["agent_id", "period_id", "wage_arrears_amount"],
            observation_family=ObservationFamily.DISTRESS_ENFORCEMENT,
            entity_scope=EntityScope.AGENT,
            identity_columns=["agent_id", "registration_code"],
            metric_columns=["wage_arrears_amount"],
        ),
        _source(
            source_id="distress_events",
            display_name="Enforcement, debtor, bankruptcy, and court layers",
            stage_id=StageId.D3,
            normalized_artifact="distress_events_panel_monthly.parquet",
            required_columns=["agent_id", "period_id", "event_count", "event_flag"],
            observation_family=ObservationFamily.DISTRESS_ENFORCEMENT,
            entity_scope=EntityScope.AGENT,
            identity_columns=["agent_id", "registration_code"],
            metric_columns=["event_count", "event_flag"],
        ),
        _source(
            source_id="logistics_mobility_displacement",
            display_name="Logistics, mobility, displacement layers",
            stage_id=StageId.D3,
            normalized_artifact="transport_pressure_monthly.parquet",
            required_columns=["cell_id", "period_id", "mobility_pressure"],
            observation_family=ObservationFamily.LOGISTICS_FRICTION,
            entity_scope=EntityScope.CELL,
            metric_columns=["mobility_pressure"],
            required=False,
            optional_reason="Exploratory optional D3 connector.",
            identification_mode=IdentificationMode.PROXY_IDENTIFIED,
        ),
        _source(
            source_id="land_cadastre",
            display_name="Land cadastre baseline",
            stage_id=StageId.D3,
            normalized_artifact="land_use_proxy_baseline.parquet",
            required_columns=["cell_id", "period_id", "land_use_proxy"],
            observation_family=ObservationFamily.CONSTRUCTION_CAPITAL_FORMATION,
            entity_scope=EntityScope.CELL,
            metric_columns=["land_use_proxy"],
            required=False,
            optional_reason="Exploratory optional land-use proxy connector.",
        ),
    ]
    return {source.source_id: source for source in sources}


def build_default_pipeline_config(root: Path | None = None) -> PipelineConfig:
    """Construct the default Ukraine Part B pipeline config."""

    build_root = BuildRootConfig(root=root or BuildRootConfig().root)
    return PipelineConfig(
        build_root=build_root,
        stages=_default_stage_configs(),
        sources=_default_source_configs(),
    )


__all__ = [
    "ArtifactRetentionPolicy",
    "BuildRootConfig",
    "CountRange",
    "PipelineConfig",
    "ResourceBudget",
    "ServerConfig",
    "SourceConfig",
    "StageConfig",
    "StageId",
    "build_default_pipeline_config",
]
