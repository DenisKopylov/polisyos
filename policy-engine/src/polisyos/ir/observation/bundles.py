"""Declare bundle manifests that connect observation evidence to runtime contracts.

Bundle models are the compiler output layer above raw observations and family
policy. They describe which persisted payload was materialized, which Foundry
or Scientist protocol it satisfies, and which lineage/governance metadata must
travel with the artifact before readiness and execution stages consume it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, model_validator

from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.observation.contracts import (
    IdentificationMode,
    MultiplexGraphLayerId,
    ObservationFamily,
    SourceConfidenceTier,
    StrategicResponseChannel,
)

if TYPE_CHECKING:
    from datetime import date

    from polisyos.ir.analytics.context import ContextProfile
    from polisyos.ir.analytics.privacy_transportability import DPUtilityManifest
    from polisyos.ir.analytics.transportability import SNode
    from polisyos.ir.model_layer.types import TimeFrequency
    from polisyos.ir.observation.governance import GovernancePassAliasRegistry
else:
    from datetime import date

    from polisyos.ir.analytics.context import ContextProfile
    from polisyos.ir.analytics.privacy_transportability import DPUtilityManifest
    from polisyos.ir.analytics.transportability import SNode
    from polisyos.ir.model_layer.types import TimeFrequency
    from polisyos.ir.observation.governance import GovernancePassAliasRegistry

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"

SURVEY_MICRODATA_CONTRACT_ID = "foundry.microsim.survey_micro_data.v1"
NETWORK_CAUSAL_DATA_CONTRACT_ID = "foundry.causal.network_causal_data.v1"
PANEL_OBSERVATIONAL_DATA_CONTRACT_ID = "foundry.causal.panel_observational_data.v1"
PROXY_MEASUREMENT_DATA_CONTRACT_ID = "foundry.causal.proxy_measurement_data.v1"
DYNAMIC_TREATMENT_DATA_CONTRACT_ID = "foundry.causal.dynamic_treatment_data.v1"
PANEL_DATA_CONTRACT_ID = "foundry.econometrics.panel_data.v1"
SURVIVAL_DATA_CONTRACT_ID = "foundry.ml.survival_data.v1"


class ContractCompatibilityTarget(KernelModel):
    """Identifier of a downstream contract that an observation bundle targets."""

    contract_id: str = Field(..., min_length=1, max_length=200)
    contract_fqn: str = Field(..., min_length=1, max_length=255)


class BundleLineageRef(KernelModel):
    """Lineage edge from a bundle back to an upstream observation artifact."""

    source_artifact: str = Field(..., min_length=1, max_length=200)
    source_family: ObservationFamily | None = None
    source_confidence_tier: SourceConfidenceTier = SourceConfidenceTier.VALIDATED
    notes: list[str] = Field(default_factory=list)


class RequiredArraySpec(KernelModel):
    """Manifest entry describing a required dense array payload."""

    name: str = Field(..., min_length=1, max_length=120)
    axes: list[str] = Field(..., min_length=1)
    dtype: str | None = Field(None, max_length=64)
    description: str | None = Field(None, max_length=255)
    required: bool = True


class RequiredColumnSpec(KernelModel):
    """Manifest entry describing a required tabular column."""

    name: str = Field(..., min_length=1, max_length=120)
    dtype: str | None = Field(None, max_length=64)
    nullable: bool = False
    description: str | None = Field(None, max_length=255)


class BundleAxisSemantic(KernelModel):
    """Human-readable meaning attached to one bundle axis."""

    axis: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1, max_length=255)


class ObservationContractRoute(KernelModel):
    """Route from an observation family and identification mode to a contract target."""

    family: ObservationFamily
    identification_mode: IdentificationMode
    target_contract: ContractCompatibilityTarget
    notes: list[str] = Field(default_factory=list)


class ObservationContractArtifact(KernelModel):
    """Manifest entry describing one compiled observation artifact."""

    compiler_id: str = Field(..., min_length=1, max_length=120)
    artifact_name: str = Field(..., min_length=1, max_length=200)
    target_contract: ContractCompatibilityTarget | None = None
    status: Literal["compiled", "blocked", "skipped"] = "compiled"
    lineage: list[BundleLineageRef] = Field(default_factory=list)
    blocking_reason: str | None = Field(None, max_length=255)
    notes: list[str] = Field(default_factory=list)


class BoundsChannelSpec(KernelModel):
    """Bounds-estimation policy for one observation family."""

    family: ObservationFamily
    bound_strategy: str = Field(..., min_length=1, max_length=120)
    fallback_reason: str = Field(..., min_length=1, max_length=120)
    notes: list[str] = Field(default_factory=list)


class ProxyChannelSpec(KernelModel):
    """Proxy-identification contract for one latent measurement pathway."""

    family: ObservationFamily
    proxy_variable: str = Field(..., min_length=1, max_length=120)
    latent_variable: str = Field(..., min_length=1, max_length=120)
    treatment_variable: str | None = Field(default=None, min_length=1, max_length=120)
    outcome_variable: str | None = Field(default=None, min_length=1, max_length=120)
    target_contract: ContractCompatibilityTarget
    verification_method: str = Field(default="identify_with_proxy", min_length=1, max_length=120)
    notes: list[str] = Field(default_factory=list)


class SpecificationCurveSource(KernelModel):
    """One source-combination entry inside a specification-curve bundle."""

    source_combination_id: str = Field(..., min_length=1, max_length=120)
    included_families: list[ObservationFamily] = Field(..., min_length=1)
    sensitivity_axes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class StrategicResponseSpec(KernelModel):
    """Expectation that a policy intervention may trigger strategic adaptation."""

    intervention_kind: str = Field(..., min_length=1, max_length=120)
    channels: list[StrategicResponseChannel] = Field(..., min_length=1)
    hook_fqn: str = Field(
        default="polisyos.foundry.methods.catalog.causal.strategic.evaluate_strategic_hook",
        min_length=1,
        max_length=255,
    )
    strategic_response_expected: bool = True
    notes: list[str] = Field(default_factory=list)


class TransportabilityCheckSpec(KernelModel):
    """Request to assess transportability between two regimes or contexts."""

    check_id: str = Field(..., min_length=1, max_length=120)
    family: ObservationFamily | None = None
    treatment: str = Field(..., min_length=1, max_length=120)
    outcome: str = Field(..., min_length=1, max_length=120)
    source_regime_id: str | None = Field(default=None, min_length=1, max_length=120)
    target_regime_id: str | None = Field(default=None, min_length=1, max_length=120)
    schema_regime_id: str | None = Field(default=None, min_length=1, max_length=120)
    period_start: date | None = None
    period_end: date | None = None
    time_grain: TimeFrequency | None = None
    source_context: ContextProfile | None = None
    target_context: ContextProfile | None = None
    explicit_s_nodes: list[SNode] = Field(default_factory=list)
    dp_utility_manifest: DPUtilityManifest | None = None
    notes: list[str] = Field(default_factory=list)


class CounterfactualCheckSpec(KernelModel):
    """Request to evaluate a counterfactual query before execution."""

    query_id: str = Field(..., min_length=1, max_length=120)
    family: ObservationFamily | None = None
    query: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_query(self) -> CounterfactualCheckSpec:
        if not self.query:
            raise ValueError("query must be non-empty")
        return self


class InterferenceLossTargetSpec(KernelModel):
    """Observed spillover target used by interference-aware calibration losses."""

    spec_id: str = Field(..., min_length=1, max_length=120)
    family: ObservationFamily
    graph_layer: MultiplexGraphLayerId
    predicted_metric_path: str = Field(..., min_length=1, max_length=255)
    observed_spillover: list[float] = Field(..., min_length=1)
    adjacency: list[list[float]] = Field(..., min_length=1)
    trust_weight: list[float] = Field(default_factory=list)
    coverage_estimate: list[float] = Field(default_factory=list)
    censoring_mask: list[bool] = Field(default_factory=list)
    lag_days_estimate: list[int] = Field(default_factory=list)
    shock_mask: list[bool] = Field(default_factory=list)
    schema_regime_id: list[str] = Field(default_factory=list)
    loss_kind: Literal["mse", "huber"] = "mse"
    huber_delta: float = Field(default=1.0, gt=0.0)
    normalization: Literal["row", "global", "none"] = "row"
    areal_support: bool = False
    scale_id: str | None = Field(default=None, min_length=1, max_length=120)
    zoning_id: str | None = Field(default=None, min_length=1, max_length=120)
    aggregation_rule: (
        Literal["sum", "mean", "population_weighted_mean", "rate", "custom"] | None
    ) = None
    weight_spec: str | None = Field(default=None, min_length=1, max_length=120)
    candidate_partition_ids: list[str] = Field(default_factory=list)
    measurement_error_bounded: bool | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_topology(self) -> InterferenceLossTargetSpec:
        node_count = len(self.adjacency)
        if any(len(row) != node_count for row in self.adjacency):
            raise ValueError("adjacency must be square")
        if len(self.observed_spillover) != node_count:
            raise ValueError("observed_spillover length must match adjacency size")
        for field_name in (
            "trust_weight",
            "coverage_estimate",
            "censoring_mask",
            "lag_days_estimate",
            "shock_mask",
            "schema_regime_id",
        ):
            values = getattr(self, field_name)
            if values and len(values) != node_count:
                raise ValueError(f"{field_name} length must match adjacency size when provided")
        normalized_partition_ids = [value.strip() for value in self.candidate_partition_ids]
        if any(not value for value in normalized_partition_ids):
            raise ValueError("candidate_partition_ids must contain non-empty strings")
        if len(set(normalized_partition_ids)) != len(normalized_partition_ids):
            raise ValueError("candidate_partition_ids must be unique")
        if self.areal_support and self.scale_id is None and self.zoning_id is not None:
            raise ValueError("scale_id must be set when zoning_id is provided for areal_support")
        return self


class LessonRegistrySeedEntry(KernelModel):
    """Seed record used to publish lesson cards from observation failures."""

    summary: str = Field(..., min_length=1, max_length=255)
    failure_type: str = Field(..., min_length=1, max_length=120)
    stage_name: str = Field(..., min_length=1, max_length=120)
    fidelity_level: int = Field(..., ge=0)
    tags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CalibrationTargetBundleManifest(KernelModel):
    """Declare calibration tensors, axis semantics, and provenance lineage.

    The manifest declares the downstream contract, required tensors, axis
    meanings, and observation-family lineage for the NPZ payload consumed by
    Foundry calibration.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["calibration_target_bundle_v1.npz"] = "calibration_target_bundle_v1.npz"
    contract_target: ContractCompatibilityTarget
    required_arrays: list[RequiredArraySpec] = Field(..., min_length=1)
    axis_semantics: list[BundleAxisSemantic] = Field(..., min_length=1)
    observation_families: list[ObservationFamily] = Field(..., min_length=1)
    lineage: list[BundleLineageRef] = Field(default_factory=list)


class MicrosimSurveyContractBundle(KernelModel):
    """Bundle carrying survey-microdata payloads for microsimulation methods."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["microsim_survey_contract_v1.json"] = "microsim_survey_contract_v1.json"
    contract_target: ContractCompatibilityTarget
    required_fields: list[str] = Field(..., min_length=1)
    observation_families: list[ObservationFamily] = Field(..., min_length=1)
    contract_payload: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class NetworkContractBundle(KernelModel):
    """Bundle carrying graph structures for network-oriented runtime contracts."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["network_contract_bundle_v1.json"] = "network_contract_bundle_v1.json"
    contract_targets: list[ContractCompatibilityTarget] = Field(..., min_length=1)
    graph_layers: list[MultiplexGraphLayerId] = Field(..., min_length=1)
    alignment_keys: list[str] = Field(default_factory=lambda: ["agent_id", "cell_id", "period_id"])
    source_artifacts: list[str] = Field(..., min_length=1)
    node_order: list[str] = Field(default_factory=list)
    node_index_map: dict[str, int] = Field(default_factory=dict)
    sparse_edges: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    slice_settings: dict[str, Any] = Field(default_factory=dict)
    low_rank_factors: dict[str, dict[str, list[list[float]]]] = Field(default_factory=dict)
    contract_payloads: dict[str, dict[str, Any]] = Field(default_factory=dict)


class NetworkCausalContractBundle(KernelModel):
    """Manifest and payload wrapper for interference-aware network causal inputs.

    Network causal estimators consume ``contract_payload`` according to
    ``contract_target`` while readiness and governance layers inspect
    ``supported_layers`` and ``interference_required`` to enforce SUTVA-related
    guardrails.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["network_causal_contract_bundle_v1.json"] = (
        "network_causal_contract_bundle_v1.json"
    )
    contract_target: ContractCompatibilityTarget
    supported_layers: list[MultiplexGraphLayerId] = Field(..., min_length=1)
    exposure_fields: list[str] = Field(
        default_factory=lambda: [
            "adjacency_matrix",
            "cluster_id",
            "coordinates",
            "bipartite_edges",
        ]
    )
    interference_required: bool = True
    contract_payload: dict[str, Any] = Field(default_factory=dict)


class CausalPanelBundleManifest(KernelModel):
    """Describe a compiled panel table that satisfies a causal estimator contract.

    Use ``required_columns`` and ``contract_target`` as the schema handshake,
    ``lineage`` to preserve observation provenance, and ``contract_payload`` for
    estimator-specific materialized data.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["causal_panel_bundle_monthly.parquet"] = (
        "causal_panel_bundle_monthly.parquet"
    )
    contract_target: ContractCompatibilityTarget
    required_columns: list[RequiredColumnSpec] = Field(..., min_length=1)
    lineage: list[BundleLineageRef] = Field(default_factory=list)
    table_rows: list[dict[str, Any]] = Field(default_factory=list)
    contract_payload: dict[str, Any] = Field(default_factory=dict)


class BacktestPlanBundle(KernelModel):
    """Bundle of neutral historical-validation payloads and frozen observations."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["backtest_plan_bundle.json"] = "backtest_plan_bundle.json"
    contract_target: ContractCompatibilityTarget
    required_fields: list[str] = Field(..., min_length=1)
    holdout_windows: list[str] = Field(default_factory=list)
    plans: list[dict[str, Any]] = Field(default_factory=list)
    historical_payloads: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ObservationToContractManifest(KernelModel):
    """Index of compiled observation artifacts and their contract routes.

    This manifest is the high-level handshake between observation evidence and
    downstream contracts: it records what was compiled, where it routes, and
    which lineage edges were preserved.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["observation_to_contract_manifest.json"] = (
        "observation_to_contract_manifest.json"
    )
    routes: list[ObservationContractRoute] = Field(..., min_length=1)
    artifacts: list[ObservationContractArtifact] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_families(self) -> ObservationToContractManifest:
        seen = [
            (route.family, route.identification_mode, route.target_contract.contract_id)
            for route in self.routes
        ]
        if len(set(seen)) != len(seen):
            raise ValueError("routes must contain unique family/mode/target combinations")
        return self


class BoundsEstimationBundle(KernelModel):
    """Declare available bounds strategies and fallback reasons by observation family.

    Bounds runners read ``channels`` to choose estimator families, while
    readiness checks can surface ``fallback_reason`` when a family drops from
    point identification to bounds-only execution.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["bounds_estimation_bundle_v1.json"] = "bounds_estimation_bundle_v1.json"
    channels: list[BoundsChannelSpec] = Field(..., min_length=1)
    available_estimators: list[str] = Field(
        default_factory=lambda: ["manski_bounds", "balke_pearl_bounds"]
    )
    contract_payload: dict[str, Any] = Field(default_factory=dict)


class ProxyIdentificationBundle(KernelModel):
    """Package proxy-identification channels and the compiler payload they target.

    This bundle bridges latent-variable observation families to
    ``ProxyMeasurementData``-style contracts and is consumed by proxy readiness
    checks before proxy-based estimators run.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["proxy_identification_bundle_v1.json"] = (
        "proxy_identification_bundle_v1.json"
    )
    contract_target: ContractCompatibilityTarget
    proxy_channels: list[ProxyChannelSpec] = Field(..., min_length=1)
    contract_payload: dict[str, Any] = Field(default_factory=dict)
    proxy_map: dict[str, str] = Field(default_factory=dict)


class DTRTreatmentSequenceBundleManifest(KernelModel):
    """Describe the tensor payload required by sequential/DTR estimators.

    ``TemporalDTRTask`` may reference this manifest directly, so axis semantics
    and required-array declarations must be complete enough for deterministic
    reconstruction of treatment, covariate, and outcome tensors.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["dtr_treatment_sequence_bundle_v1.npz"] = (
        "dtr_treatment_sequence_bundle_v1.npz"
    )
    contract_target: ContractCompatibilityTarget
    required_arrays: list[RequiredArraySpec] = Field(..., min_length=1)
    axis_semantics: list[BundleAxisSemantic] = Field(..., min_length=1)
    lineage: list[BundleLineageRef] = Field(default_factory=list)
    contract_payload: dict[str, Any] = Field(default_factory=dict)


class PanelEconometricBundleManifest(KernelModel):
    """Describe panel-econometric tables consumed by fixed-effects/IV estimators."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["panel_econometric_bundle_v1.parquet"] = (
        "panel_econometric_bundle_v1.parquet"
    )
    contract_target: ContractCompatibilityTarget
    required_columns: list[RequiredColumnSpec] = Field(..., min_length=1)
    lineage: list[BundleLineageRef] = Field(default_factory=list)
    table_rows: list[dict[str, Any]] = Field(default_factory=list)
    contract_payload: dict[str, Any] = Field(default_factory=dict)


class SurvivalDataBundleManifest(KernelModel):
    """Describe survival-analysis tables consumed by hazard or duration models."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["survival_data_bundle_v1.parquet"] = "survival_data_bundle_v1.parquet"
    contract_target: ContractCompatibilityTarget
    required_columns: list[RequiredColumnSpec] = Field(..., min_length=1)
    lineage: list[BundleLineageRef] = Field(default_factory=list)
    table_rows: list[dict[str, Any]] = Field(default_factory=list)
    contract_payload: dict[str, Any] = Field(default_factory=dict)


class AgentFactorEmbeddingsBundleManifest(KernelModel):
    """Describe latent agent-factor arrays and embedding method provenance."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["agent_factor_embeddings_v1.npz"] = "agent_factor_embeddings_v1.npz"
    required_arrays: list[RequiredArraySpec] = Field(..., min_length=1)
    axis_semantics: list[BundleAxisSemantic] = Field(..., min_length=1)
    lineage: list[BundleLineageRef] = Field(default_factory=list)
    embedding_method: str = Field(..., min_length=1, max_length=120)
    contract_payload: dict[str, Any] = Field(default_factory=dict)


class CellPrototypeEmbeddingsBundleManifest(KernelModel):
    """Describe prototype-cell embedding arrays and clustering provenance."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["cell_prototype_embeddings_v1.npz"] = "cell_prototype_embeddings_v1.npz"
    required_arrays: list[RequiredArraySpec] = Field(..., min_length=1)
    axis_semantics: list[BundleAxisSemantic] = Field(..., min_length=1)
    lineage: list[BundleLineageRef] = Field(default_factory=list)
    clustering_method: str = Field(..., min_length=1, max_length=120)
    contract_payload: dict[str, Any] = Field(default_factory=dict)


class BilevelProblemBundle(KernelModel):
    """Persist an optimization-ready bilevel problem snapshot and result summary."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["bilevel_problem_bundle_v1.json"] = "bilevel_problem_bundle_v1.json"
    optimization_target: str = Field(
        default="optimization.bilevel.bilevel@1.1.0", min_length=1, max_length=120
    )
    knob_names: list[str] = Field(..., min_length=1)
    c_upper: list[float] = Field(..., min_length=1)
    c_lower: list[float] = Field(..., min_length=1)
    A_upper: list[list[float]] = Field(..., min_length=1)
    b_upper: list[float] = Field(..., min_length=1)
    A_lower: list[list[float]] = Field(..., min_length=1)
    b_lower: list[float] = Field(..., min_length=1)
    tie_break: str | None = Field(default=None, min_length=1, max_length=64)
    ambiguity_mode: str = Field(default="auto", min_length=1, max_length=64)
    delta_near_opt: float = Field(default=0.0, ge=0.0)
    certificate_mode: str = Field(default="residual_or_bounds", min_length=1, max_length=64)
    result_summary: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class HeckmanCorrectionBundle(KernelModel):
    """Describe selection-correction tables and payloads for Heckman estimators."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["heckman_correction_bundle_v1.parquet"] = (
        "heckman_correction_bundle_v1.parquet"
    )
    contract_target: ContractCompatibilityTarget
    required_columns: list[RequiredColumnSpec] = Field(..., min_length=1)
    lineage: list[BundleLineageRef] = Field(default_factory=list)
    table_rows: list[dict[str, Any]] = Field(default_factory=list)
    contract_payload: dict[str, Any] = Field(default_factory=dict)


class SurvivalHazardBundle(KernelModel):
    """Describe hazard-model tables and payloads for survival estimators."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["survival_hazard_bundle_v1.parquet"] = (
        "survival_hazard_bundle_v1.parquet"
    )
    contract_target: ContractCompatibilityTarget
    required_columns: list[RequiredColumnSpec] = Field(..., min_length=1)
    lineage: list[BundleLineageRef] = Field(default_factory=list)
    table_rows: list[dict[str, Any]] = Field(default_factory=list)
    contract_payload: dict[str, Any] = Field(default_factory=dict)


class SobolDiagnosticsBundle(KernelModel):
    """Persist Sobol indices and target/specification axes for sensitivity diagnostics."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["sobol_diagnostics_bundle_v1.json"] = "sobol_diagnostics_bundle_v1.json"
    target_names: list[str] = Field(..., min_length=1)
    source_combination_ids: list[str] = Field(..., min_length=1)
    first_order_indices: list[list[float]] = Field(..., min_length=1)
    variance: list[float] = Field(..., min_length=1)
    notes: list[str] = Field(default_factory=list)


class SpecificationCurveDiagnosticsBundle(KernelModel):
    """Persist sorted estimates and stability metrics for specification-curve review."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["specification_curve_diagnostics_v1.json"] = (
        "specification_curve_diagnostics_v1.json"
    )
    specification_ids: list[str] = Field(..., min_length=1)
    sorted_estimates: list[float] = Field(..., min_length=1)
    share_significant: float = Field(..., ge=0.0, le=1.0)
    sign_consistency: float = Field(..., ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


class SpecificationCurveBundle(KernelModel):
    """Persist source combinations and estimates for specification-curve analysis.

    Scientist robustness tooling reads this bundle to rank specification choices,
    recompute curve diagnostics, and preserve the observation-family mix behind
    each estimate.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["specification_curve_input_v1.json"] = (
        "specification_curve_input_v1.json"
    )
    source_specifications: list[SpecificationCurveSource] = Field(..., min_length=1)
    specification_ids: list[str] = Field(default_factory=list)
    estimates: list[float] = Field(default_factory=list)
    standard_errors: list[float] = Field(default_factory=list)
    contract_payload: dict[str, Any] = Field(default_factory=dict)


class LeontiefIOBundle(KernelModel):
    """Input bundle for Leontief input-output analysis and optimization."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["leontief_io_bundle_v1.json"] = "leontief_io_bundle_v1.json"
    regions: list[str] = Field(..., min_length=1)
    sectors: list[str] = Field(..., min_length=1)
    required_tables: list[str] = Field(
        default_factory=lambda: ["technical_coefficients", "final_demand", "value_added"]
    )
    optimization_target: str = Field(default="optimization.io_leontief", min_length=1)
    technical_coefficients: list[list[float]] = Field(default_factory=list)
    final_demand: list[float] = Field(default_factory=list)
    value_added: list[float] = Field(default_factory=list)
    sector_names: list[str] = Field(default_factory=list)
    region_index_map: dict[str, int] = Field(default_factory=dict)
    sector_index_map: dict[str, int] = Field(default_factory=dict)
    contract_payload: dict[str, Any] = Field(default_factory=dict)


class StrategicResponseSpecsBundle(KernelModel):
    """Bundle intervention-level strategic-response expectations for readiness checks."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["strategic_response_specs_v1.json"] = "strategic_response_specs_v1.json"
    expectations: list[StrategicResponseSpec] = Field(..., min_length=1)


class TransportabilityCheckBundle(KernelModel):
    """Bundle of transportability checks queued for readiness validation."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["transportability_check_bundle_v1.json"] = (
        "transportability_check_bundle_v1.json"
    )
    checks: list[TransportabilityCheckSpec] = Field(..., min_length=1)


class CounterfactualCheckBundle(KernelModel):
    """Bundle of counterfactual queries queued for readiness validation."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["counterfactual_check_bundle_v1.json"] = (
        "counterfactual_check_bundle_v1.json"
    )
    queries: list[CounterfactualCheckSpec] = Field(..., min_length=1)


class InterferenceLossSpecBundle(KernelModel):
    """Bundle of interference-loss targets for measurement-aware calibration."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["interference_loss_spec_bundle_v1.json"] = (
        "interference_loss_spec_bundle_v1.json"
    )
    specs: list[InterferenceLossTargetSpec] = Field(..., min_length=1)


class GovernancePassMappingBundle(KernelModel):
    """Persist resolved family-to-pass routing together with alias metadata.

    Bundles the concrete pass mapping with the alias registry that resolves
    canonical IR pass ids to the runtime pass names available in Scientist.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["governance_pass_mapping_v1.json"] = "governance_pass_mapping_v1.json"
    family_passes: dict[str, list[str]] = Field(..., min_length=1)
    alias_registry: GovernancePassAliasRegistry


class LessonRegistrySeedBundle(KernelModel):
    """Bundle of lesson-card seeds emitted from observation-layer governance."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["lesson_registry_seed_v1.json"] = "lesson_registry_seed_v1.json"
    contract_target: ContractCompatibilityTarget
    seed_entries: list[LessonRegistrySeedEntry] = Field(..., min_length=1)


SURVEY_MICRODATA_TARGET = ContractCompatibilityTarget(
    contract_id=SURVEY_MICRODATA_CONTRACT_ID,
    contract_fqn="polisyos.foundry.methods.catalog.microsim.protocols.SurveyMicroData",
)
NETWORK_DATA_TARGET = ContractCompatibilityTarget(
    contract_id=NETWORK_CAUSAL_DATA_CONTRACT_ID,
    contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.NetworkCausalData",
)
NETWORK_ANALYSIS_TARGET = ContractCompatibilityTarget(
    contract_id="foundry.network.data.v1",
    contract_fqn="polisyos.foundry.methods.catalog.network.protocols.NetworkData",
)
MULTIPLEX_NETWORK_TARGET = ContractCompatibilityTarget(
    contract_id="foundry.network.multiplex_data.v1",
    contract_fqn="polisyos.foundry.methods.catalog.network.protocols.MultiplexNetworkData",
)
PANEL_OBSERVATIONAL_TARGET = ContractCompatibilityTarget(
    contract_id=PANEL_OBSERVATIONAL_DATA_CONTRACT_ID,
    contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.PanelObservationalData",
)
PROXY_MEASUREMENT_TARGET = ContractCompatibilityTarget(
    contract_id=PROXY_MEASUREMENT_DATA_CONTRACT_ID,
    contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.ProxyMeasurementData",
)
DYNAMIC_TREATMENT_TARGET = ContractCompatibilityTarget(
    contract_id=DYNAMIC_TREATMENT_DATA_CONTRACT_ID,
    contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.DynamicTreatmentData",
)
PANEL_ECONOMETRIC_TARGET = ContractCompatibilityTarget(
    contract_id=PANEL_DATA_CONTRACT_ID,
    contract_fqn="polisyos.foundry.methods.catalog.econometrics.protocols.PanelData",
)
SURVIVAL_DATA_TARGET = ContractCompatibilityTarget(
    contract_id=SURVIVAL_DATA_CONTRACT_ID,
    contract_fqn="polisyos.foundry.methods.catalog.ml.protocols.SurvivalData",
)
BACKTEST_PLAN_TARGET = ContractCompatibilityTarget(
    contract_id="scientist.backtesting.historical_validation_plan.v1",
    contract_fqn="polisyos.scientist.methods.backtesting.plan.HistoricalValidationPlan",
)
LESSON_CARD_TARGET = ContractCompatibilityTarget(
    contract_id="scientist.search.lesson_card.v1",
    contract_fqn="polisyos.scientist.methods.search.lessons.LessonCard",
)


SECTION_15_7_BUNDLE_MODELS: dict[str, type[KernelModel]] = {
    "calibration_target_bundle_v1.npz": CalibrationTargetBundleManifest,
    "microsim_survey_contract_v1.json": MicrosimSurveyContractBundle,
    "network_contract_bundle_v1.json": NetworkContractBundle,
    "network_causal_contract_bundle_v1.json": NetworkCausalContractBundle,
    "causal_panel_bundle_monthly.parquet": CausalPanelBundleManifest,
    "backtest_plan_bundle.json": BacktestPlanBundle,
    "observation_to_contract_manifest.json": ObservationToContractManifest,
    "bounds_estimation_bundle_v1.json": BoundsEstimationBundle,
    "proxy_identification_bundle_v1.json": ProxyIdentificationBundle,
    "dtr_treatment_sequence_bundle_v1.npz": DTRTreatmentSequenceBundleManifest,
    "panel_econometric_bundle_v1.parquet": PanelEconometricBundleManifest,
    "survival_data_bundle_v1.parquet": SurvivalDataBundleManifest,
    "agent_factor_embeddings_v1.npz": AgentFactorEmbeddingsBundleManifest,
    "cell_prototype_embeddings_v1.npz": CellPrototypeEmbeddingsBundleManifest,
    "bilevel_problem_bundle_v1.json": BilevelProblemBundle,
    "heckman_correction_bundle_v1.parquet": HeckmanCorrectionBundle,
    "survival_hazard_bundle_v1.parquet": SurvivalHazardBundle,
    "sobol_diagnostics_bundle_v1.json": SobolDiagnosticsBundle,
    "specification_curve_diagnostics_v1.json": SpecificationCurveDiagnosticsBundle,
    "specification_curve_input_v1.json": SpecificationCurveBundle,
    "leontief_io_bundle_v1.json": LeontiefIOBundle,
    "strategic_response_specs_v1.json": StrategicResponseSpecsBundle,
    "transportability_check_bundle_v1.json": TransportabilityCheckBundle,
    "counterfactual_check_bundle_v1.json": CounterfactualCheckBundle,
    "interference_loss_spec_bundle_v1.json": InterferenceLossSpecBundle,
    "governance_pass_mapping_v1.json": GovernancePassMappingBundle,
    "lesson_registry_seed_v1.json": LessonRegistrySeedBundle,
}

__all__ = [
    "BACKTEST_PLAN_TARGET",
    "DYNAMIC_TREATMENT_TARGET",
    "LESSON_CARD_TARGET",
    "MULTIPLEX_NETWORK_TARGET",
    "NETWORK_ANALYSIS_TARGET",
    "NETWORK_DATA_TARGET",
    "PANEL_ECONOMETRIC_TARGET",
    "PANEL_OBSERVATIONAL_TARGET",
    "PROXY_MEASUREMENT_TARGET",
    "SECTION_15_7_BUNDLE_MODELS",
    "SURVEY_MICRODATA_TARGET",
    "SURVIVAL_DATA_TARGET",
    "AgentFactorEmbeddingsBundleManifest",
    "BilevelProblemBundle",
    "BoundsChannelSpec",
    "BoundsEstimationBundle",
    "BundleAxisSemantic",
    "BundleLineageRef",
    "CalibrationTargetBundleManifest",
    "CausalPanelBundleManifest",
    "CellPrototypeEmbeddingsBundleManifest",
    "ContractCompatibilityTarget",
    "CounterfactualCheckBundle",
    "CounterfactualCheckSpec",
    "DTRTreatmentSequenceBundleManifest",
    "GovernancePassMappingBundle",
    "HeckmanCorrectionBundle",
    "InterferenceLossSpecBundle",
    "InterferenceLossTargetSpec",
    "LeontiefIOBundle",
    "LessonRegistrySeedBundle",
    "LessonRegistrySeedEntry",
    "MicrosimSurveyContractBundle",
    "NetworkCausalContractBundle",
    "NetworkContractBundle",
    "ObservationContractArtifact",
    "ObservationContractRoute",
    "ObservationToContractManifest",
    "PanelEconometricBundleManifest",
    "ProxyChannelSpec",
    "ProxyIdentificationBundle",
    "RequiredArraySpec",
    "RequiredColumnSpec",
    "SobolDiagnosticsBundle",
    "SpecificationCurveBundle",
    "SpecificationCurveDiagnosticsBundle",
    "SpecificationCurveSource",
    "StrategicResponseSpec",
    "StrategicResponseSpecsBundle",
    "SurvivalDataBundleManifest",
    "SurvivalHazardBundle",
    "TransportabilityCheckBundle",
    "TransportabilityCheckSpec",
]
