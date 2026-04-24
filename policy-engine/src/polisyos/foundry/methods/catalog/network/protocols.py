"""Define network input/output contracts for graph and multiplex estimators."""

from __future__ import annotations

from enum import Enum
from typing import Any, ClassVar, Literal

import numpy as np
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from polisyos.ir.analytics.network_embedding import (
    EmbeddingFidelityAction,
    EmbeddingFidelityStatus,
    NetworkEmbeddingFidelityCertificate,
)


def _to_numpy(value: Any) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value
    return np.asarray(value)


class NetworkData(BaseModel):
    """Carry a weighted adjacency matrix, optional node states, and node labels."""

    contract_id: ClassVar[str] = "foundry.network.data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    adjacency: Any
    node_features: Any | None = None
    node_states: Any | None = None
    node_ids: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("adjacency", "node_features", "node_states", mode="before")
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> NetworkData:
        if not isinstance(self.adjacency, np.ndarray) or self.adjacency.ndim != 2:
            raise ValueError("adjacency must be a 2D numpy array")
        n_nodes = self.adjacency.shape[0]
        if self.adjacency.shape[1] != n_nodes:
            raise ValueError("adjacency must be square")
        if self.node_features is not None:
            if not isinstance(self.node_features, np.ndarray) or self.node_features.ndim != 2:
                raise ValueError("node_features must be a 2D numpy array")
            if self.node_features.shape[0] != n_nodes:
                raise ValueError("node_features rows must match node count")
        if self.node_states is not None:
            if not isinstance(self.node_states, np.ndarray) or self.node_states.ndim != 1:
                raise ValueError("node_states must be a 1D numpy array")
            if self.node_states.shape[0] != n_nodes:
                raise ValueError("node_states length must match node count")
        if self.node_ids is not None and len(self.node_ids) != n_nodes:
            raise ValueError("node_ids length must match node count")
        return self

    @field_serializer("adjacency", "node_features", "node_states", mode="plain", when_used="json")
    def _serialize_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class MultiplexNetworkData(BaseModel):
    """Carry aligned adjacency layers and optional node states for multiplex graph methods."""

    contract_id: ClassVar[str] = "foundry.network.multiplex_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    adjacency_layers: Any
    node_features: Any | None = None
    node_ids: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("adjacency_layers", "node_features", mode="before")
    @classmethod
    def _coerce_layer_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @model_validator(mode="after")
    def _validate_layers(self) -> MultiplexNetworkData:
        if not isinstance(self.adjacency_layers, np.ndarray) or self.adjacency_layers.ndim != 3:
            raise ValueError("adjacency_layers must be a 3D numpy array")
        n_layers, n_nodes, n_nodes_2 = self.adjacency_layers.shape
        if n_layers < 2 or n_nodes != n_nodes_2:
            raise ValueError("adjacency_layers must have shape (n_layers>=2, n_nodes, n_nodes)")
        if self.node_features is not None:
            if not isinstance(self.node_features, np.ndarray) or self.node_features.ndim != 2:
                raise ValueError("node_features must be a 2D numpy array")
            if self.node_features.shape[0] != n_nodes:
                raise ValueError("node_features rows must match node count")
        if self.node_ids is not None and len(self.node_ids) != n_nodes:
            raise ValueError("node_ids length must match node count")
        return self

    @field_serializer("adjacency_layers", "node_features", mode="plain", when_used="json")
    def _serialize_layer_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class IntervalEstimate(BaseModel):
    """Point estimate with uncertainty metadata for a network estimand."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    estimate: float | None = None
    std_error: float | None = None
    ci_level: float = 0.95
    ci_lower: float | None = None
    ci_upper: float | None = None
    p_value: float | None = None
    units: str = "outcome-units per 1-unit change in peer mean"
    method: str = "2SLS"


class BoundEstimate(BaseModel):
    """Outer, sharp, or sensitivity bounds for partially identified effects."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lower: float | None = None
    upper: float | None = None
    assumptions: list[str] = Field(default_factory=list)
    bound_type: Literal["sharp", "outer", "sensitivity"] = "outer"


class IdentificationDiagnostics(BaseModel):
    """Diagnostics describing whether the peer-effect decomposition is identified."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    identification_status: Literal[
        "identified",
        "weakly_identified",
        "partially_identified",
        "not_identified",
    ]
    strategy_used: Literal[
        "topology_iv",
        "external_iv",
        "panel",
        "control_function",
        "leave_own_out",
        "randomization",
        "graphical_reconstruction",
        "partial_id",
    ]
    rank_condition_ok: bool
    weak_iv_flag: bool = False
    kp_rk_f: float | None = None
    ar_p_value: float | None = None
    overid_p_value: float | None = None
    network_observability_rate: float | None = None
    component_count: int | None = None
    density: float | None = None
    intransitivity_index: float | None = None
    mobility_variation: float | None = None
    spectral_radius_W: float | None = None
    blocking_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)


class PeerEffectDecomposition(BaseModel):
    """Structured output for Manski-style peer-effect decomposition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_class: Literal[
        "linear_in_means",
        "dynamic_contagion",
        "potential_outcomes_network",
    ]
    estimand_scale: Literal[
        "outcome_units",
        "standardized",
        "log_odds",
        "hazard_ratio",
        "risk_difference",
    ]
    endogenous_effect: IntervalEstimate | None = None
    contextual_effect: IntervalEstimate | None = None
    correlated_effect_proxy: IntervalEstimate | None = None
    direct_effect: IntervalEstimate | None = None
    spillover_effect: IntervalEstimate | None = None
    total_peer_effect: IntervalEstimate | None = None
    reduced_form_peer_multiplier: IntervalEstimate | None = None
    contagion_effect: IntervalEstimate | None = None
    infectiousness_effect: IntervalEstimate | None = None
    endogenous_bounds: BoundEstimate | None = None
    contextual_bounds: BoundEstimate | None = None
    diagnostics: IdentificationDiagnostics
    assumptions: list[str] = Field(default_factory=list)
    testable_implications: list[str] = Field(default_factory=list)
    data_requirements_met: dict[str, bool] = Field(default_factory=dict)
    robustness_checks_run: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class MissingnessAssessmentScope(str, Enum):
    """Scope of the network missingness target."""

    FINITE_POPULATION = "finite_population"
    SUPERPOPULATION = "superpopulation"


class NetworkEstimandTarget(str, Enum):
    """Target object for a network estimand under missingness."""

    REALIZED_GRAPH = "realized_graph"
    EXPECTED_UNDER_MODEL = "expected_under_model"
    POSTERIOR_PREDICTIVE = "posterior_predictive"


class NetworkIdentificationStatus(str, Enum):
    """Identification status for one network estimand."""

    POINT_IDENTIFIED = "point_identified"
    SET_IDENTIFIED = "set_identified"
    MODEL_DEPENDENT = "model_dependent"
    NOT_IDENTIFIED = "not_identified"


class NetworkMissingnessRisk(str, Enum):
    """Global risk tier induced by partial observability."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"


class EstimandAssessment(BaseModel):
    """Machine-readable identification assessment for one network estimand."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    target: NetworkEstimandTarget
    identification_status: NetworkIdentificationStatus
    assumptions_required: tuple[str, ...] = ()
    estimator: str | None = None
    estimate: Any | None = None
    std_error: float | None = None
    identification_region: Any | None = None
    sensitivity_region: dict[str, Any] | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    algorithm: str = ""
    complexity: str = ""


class MissingnessAssessment(BaseModel):
    """Identification-aware assessment of network missingness risk."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: MissingnessAssessmentScope
    observed_graph_summary: dict[str, Any] = Field(default_factory=dict)
    assumptions: tuple[str, ...] = ()
    missingness_hypotheses: tuple[dict[str, Any], ...] = ()
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    estimands: dict[str, EstimandAssessment] = Field(default_factory=dict)
    global_risk: NetworkMissingnessRisk = NetworkMissingnessRisk.MODERATE
    recommendations: tuple[str, ...] = ()


class FormationEvent(BaseModel):
    """One observed dyadic revision for strategic network-formation estimators."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    i: int = Field(ge=0)
    j: int = Field(ge=0)
    next_state: int = Field(ge=0, le=1)
    prev_state: int | None = Field(default=None, ge=0, le=1)
    timestamp: str | None = None
    common_neighbors: int | None = Field(default=None, ge=0)
    degree_sum: int | None = Field(default=None, ge=0)
    dyad_covariates: tuple[float, ...] = ()

    @field_validator("dyad_covariates", mode="before")
    @classmethod
    def _coerce_covariates(cls, value: Any) -> tuple[float, ...]:
        if value is None:
            return ()
        if isinstance(value, np.ndarray):
            value = value.tolist()
        return tuple(float(entry) for entry in value)

    @model_validator(mode="after")
    def _validate_event(self) -> FormationEvent:
        if self.i == self.j:
            raise ValueError("formation events must reference distinct nodes")
        for entry in self.dyad_covariates:
            if not np.isfinite(entry):
                raise ValueError("formation event covariates must be finite")
        return self


class StrategicNetworkFormationData(BaseModel):
    """Input contract for strategic network-formation estimation."""

    contract_id: ClassVar[str] = "foundry.network.strategic_formation_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    adjacency: Any
    dyad_features: Any | None = None
    node_features: Any | None = None
    initial_adjacency: Any | None = None
    policy_shock: Any | None = None
    holdout_mask: Any | None = None
    adjacency_snapshots: Any | None = None
    formation_events: tuple[FormationEvent, ...] = ()
    node_ids: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "adjacency",
        "dyad_features",
        "node_features",
        "initial_adjacency",
        "adjacency_snapshots",
        mode="before",
    )
    @classmethod
    def _coerce_numpy_fields(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @field_validator("policy_shock", mode="before")
    @classmethod
    def _coerce_policy_shock(cls, value: Any) -> Any:
        if value is None:
            return None
        arr = _to_numpy(value)
        if isinstance(arr, np.ndarray) and arr.ndim == 2:
            return arr[:, :, None]
        return arr

    @field_validator("holdout_mask", mode="before")
    @classmethod
    def _coerce_holdout_mask(cls, value: Any) -> Any:
        if value is None:
            return None
        return np.asarray(value, dtype=bool)

    @model_validator(mode="after")
    def _validate_shapes(self) -> StrategicNetworkFormationData:
        if not isinstance(self.adjacency, np.ndarray) or self.adjacency.ndim != 2:
            raise ValueError("adjacency must be a 2D numpy array")
        n_nodes = self.adjacency.shape[0]
        if self.adjacency.shape[1] != n_nodes:
            raise ValueError("adjacency must be square")
        if not np.isfinite(self.adjacency).all():
            raise ValueError("adjacency must be finite")
        if self.dyad_features is not None:
            if not isinstance(self.dyad_features, np.ndarray) or self.dyad_features.ndim != 3:
                raise ValueError("dyad_features must be a 3D numpy array")
            if self.dyad_features.shape[0] != n_nodes or self.dyad_features.shape[1] != n_nodes:
                raise ValueError("dyad_features first two dimensions must match node count")
            if not np.isfinite(self.dyad_features).all():
                raise ValueError("dyad_features must be finite")
        if self.node_features is not None:
            if not isinstance(self.node_features, np.ndarray) or self.node_features.ndim != 2:
                raise ValueError("node_features must be a 2D numpy array")
            if self.node_features.shape[0] != n_nodes:
                raise ValueError("node_features rows must match node count")
            if not np.isfinite(self.node_features).all():
                raise ValueError("node_features must be finite")
        if self.initial_adjacency is not None:
            if (
                not isinstance(self.initial_adjacency, np.ndarray)
                or self.initial_adjacency.ndim != 2
            ):
                raise ValueError("initial_adjacency must be a 2D numpy array")
            if self.initial_adjacency.shape != self.adjacency.shape:
                raise ValueError("initial_adjacency must match adjacency shape")
            if not np.isfinite(self.initial_adjacency).all():
                raise ValueError("initial_adjacency must be finite")
        if self.policy_shock is not None:
            if not isinstance(self.policy_shock, np.ndarray) or self.policy_shock.ndim != 3:
                raise ValueError("policy_shock must be a 3D numpy array")
            if self.policy_shock.shape[0] != n_nodes or self.policy_shock.shape[1] != n_nodes:
                raise ValueError("policy_shock first two dimensions must match node count")
            if not np.isfinite(self.policy_shock).all():
                raise ValueError("policy_shock must be finite")
            if (
                self.dyad_features is not None
                and self.policy_shock.shape[2] != self.dyad_features.shape[2]
            ):
                raise ValueError("policy_shock width must match dyad_features width")
        if self.holdout_mask is not None:
            if not isinstance(self.holdout_mask, np.ndarray) or self.holdout_mask.ndim != 2:
                raise ValueError("holdout_mask must be a 2D numpy array")
            if self.holdout_mask.shape != self.adjacency.shape:
                raise ValueError("holdout_mask must match adjacency shape")
        if self.adjacency_snapshots is not None:
            if (
                not isinstance(self.adjacency_snapshots, np.ndarray)
                or self.adjacency_snapshots.ndim != 3
            ):
                raise ValueError("adjacency_snapshots must be a 3D numpy array")
            if self.adjacency_snapshots.shape[0] < 2:
                raise ValueError("adjacency_snapshots must contain at least two snapshots")
            if self.adjacency_snapshots.shape[1:] != self.adjacency.shape:
                raise ValueError("adjacency_snapshots must align with adjacency shape")
            if not np.isfinite(self.adjacency_snapshots).all():
                raise ValueError("adjacency_snapshots must be finite")
        if self.node_ids is not None and len(self.node_ids) != n_nodes:
            raise ValueError("node_ids length must match node count")
        event_covariate_widths = {
            len(event.dyad_covariates) for event in self.formation_events if event.dyad_covariates
        }
        if len(event_covariate_widths) > 1:
            raise ValueError("formation event dyad_covariates must use a consistent width")
        for event in self.formation_events:
            if event.i >= n_nodes or event.j >= n_nodes:
                raise ValueError("formation event indices must be within node range")
        return self

    @field_serializer(
        "adjacency",
        "dyad_features",
        "node_features",
        "initial_adjacency",
        "policy_shock",
        "holdout_mask",
        "adjacency_snapshots",
        mode="plain",
        when_used="json",
    )
    def _serialize_array_fields(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


class NetworkFormationIdentifiedSet(BaseModel):
    """Coarse identified-set disclosure for pairwise-stability fallbacks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    parameter_bounds: dict[str, tuple[float, float]] = Field(default_factory=dict)
    grid_size: int = Field(default=0, ge=0)
    feasible_share: float = Field(default=0.0, ge=0.0, le=1.0)
    violation_threshold: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def _validate_bounds(self) -> NetworkFormationIdentifiedSet:
        for key, interval in self.parameter_bounds.items():
            lo, hi = interval
            if not np.isfinite(lo) or not np.isfinite(hi):
                raise ValueError(f"parameter_bounds.{key} must be finite")
            if lo > hi:
                raise ValueError(f"parameter_bounds.{key} lower must be <= upper")
        return self


class NetworkFormationScenarioMoments(BaseModel):
    """Aggregate moments for one simulated network regime or scenario."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    density: float = Field(ge=0.0, le=1.0)
    mean_degree: float = Field(ge=0.0)
    clustering: float = Field(ge=0.0, le=1.0)
    reachability_share: float = Field(ge=0.0, le=1.0)
    largest_component_share: float = Field(ge=0.0, le=1.0)


class NetworkFormationPredictiveCheck(BaseModel):
    """Observed-vs-simulated posterior-predictive check for one graph statistic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statistic: str
    observed: float
    simulated_mean: float
    q05: float
    q95: float
    passed: bool


class NetworkFormationValidationSummary(BaseModel):
    """Posterior-predictive, held-out, and temporal-stability diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    posterior_predictive_checks: tuple[NetworkFormationPredictiveCheck, ...] = ()
    heldout_log_loss: float | None = None
    temporal_parameter_drift: float | None = None
    overall_passed: bool = False
    warnings: tuple[str, ...] = ()


class NetworkFormationUncertaintySummary(BaseModel):
    """Parameter and scenario uncertainty carried by the formation estimator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: Literal[
        "asymptotic_normal",
        "parametric_bootstrap",
        "bootstrap_refit",
    ]
    draw_count: int = Field(default=0, ge=0)
    parameter_intervals: dict[str, IntervalEstimate] = Field(default_factory=dict)
    scenario_effect_intervals: dict[str, IntervalEstimate] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()


class NetworkFormationCounterfactualSummary(BaseModel):
    """Distributional summary of a policy shock on strategic network formation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_name: str = "policy_shock"
    baseline: NetworkFormationScenarioMoments
    counterfactual: NetworkFormationScenarioMoments
    effects: dict[str, IntervalEstimate] = Field(default_factory=dict)
    simulation_draws: int = Field(default=0, ge=0)
    warnings: tuple[str, ...] = ()


class NetworkFormationDiagnostic(BaseModel):
    """Typed identifiability and fallback diagnostics for strategic formation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_class: str
    strategy_used: Literal[
        "event_history_mle",
        "stationary_mcmc_mle",
        "stationary_pseudolikelihood",
        "moment_inequality_fallback",
        "blocked",
    ]
    identification_status: Literal[
        "point_identified",
        "weakly_identified",
        "partially_identified",
        "blocked",
    ]
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    density: float = Field(ge=0.0, le=1.0)
    clustering: float = Field(ge=0.0, le=1.0)
    event_history_available: bool = False
    event_history_used: bool = False
    observed_events: int = Field(default=0, ge=0)
    observed_dyads: int = Field(default=0, ge=0)
    dyad_feature_dimension: int = Field(default=0, ge=0)
    dyad_feature_support: float = Field(default=0.0, ge=0.0, le=1.0)
    node_heterogeneity_present: bool = False
    design_rank: int | None = Field(default=None, ge=0)
    design_condition_number: float | None = Field(default=None, ge=0.0)
    degeneracy_risk: Literal["low", "moderate", "high"]
    fit_converged: bool = False
    policy_counterfactual_ready: bool = False
    parameter_estimates: dict[str, float] = Field(default_factory=dict)
    standard_errors: dict[str, float] = Field(default_factory=dict)
    fit_statistics: dict[str, float] = Field(default_factory=dict)
    identified_set: NetworkFormationIdentifiedSet | None = None
    uncertainty_summary: NetworkFormationUncertaintySummary | None = None
    validation_summary: NetworkFormationValidationSummary | None = None
    counterfactual_summary: NetworkFormationCounterfactualSummary | None = None
    warm_start_used: bool = False
    fallback_reason: str | None = None

    @model_validator(mode="after")
    def _validate_diagnostic(self) -> NetworkFormationDiagnostic:
        if not self.model_class:
            raise ValueError("model_class must be non-empty")
        for bucket_name, bucket in (
            ("parameter_estimates", self.parameter_estimates),
            ("standard_errors", self.standard_errors),
            ("fit_statistics", self.fit_statistics),
        ):
            for key, value in bucket.items():
                if not np.isfinite(value):
                    raise ValueError(f"{bucket_name}.{key} must be finite")
        if self.identification_status == "partially_identified" and self.identified_set is None:
            raise ValueError(
                "identified_set is required when identification_status=partially_identified"
            )
        if self.identification_status == "blocked" and self.fallback_reason is None:
            raise ValueError("fallback_reason is required when identification_status=blocked")
        if self.strategy_used == "blocked" and self.identification_status != "blocked":
            raise ValueError("blocked strategy requires blocked identification status")
        return self


class NetworkResult(BaseModel):
    """Store graph metrics, node scores/labels, trajectories, and method metadata."""

    contract_id: ClassVar[str] = "foundry.network.result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    method_name: str
    metrics: dict[str, float] = Field(default_factory=dict)
    node_scores: Any | None = None
    labels: Any | None = None
    state_trajectories: Any | None = None
    peer_effect_decomposition: PeerEffectDecomposition | None = None
    missingness_assessment: MissingnessAssessment | None = None
    formation_diagnostic: NetworkFormationDiagnostic | None = None
    embedding_fidelity_certificate: NetworkEmbeddingFidelityCertificate | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("node_scores", "labels", "state_trajectories", mode="before")
    @classmethod
    def _coerce_result_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @field_serializer("node_scores", "labels", "state_trajectories", mode="plain", when_used="json")
    def _serialize_result_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


from .generative_protocols import (
    DiffusionNullResult,
    EdgeListNetworkData,
    ERGMResult,
    SBMStratificationResult,
)

__all__ = [
    "BoundEstimate",
    "DiffusionNullResult",
    "ERGMResult",
    "EdgeListNetworkData",
    "EmbeddingFidelityAction",
    "EmbeddingFidelityStatus",
    "EstimandAssessment",
    "FormationEvent",
    "IdentificationDiagnostics",
    "IntervalEstimate",
    "MissingnessAssessment",
    "MissingnessAssessmentScope",
    "MultiplexNetworkData",
    "NetworkData",
    "NetworkEmbeddingFidelityCertificate",
    "NetworkEstimandTarget",
    "NetworkFormationCounterfactualSummary",
    "NetworkFormationDiagnostic",
    "NetworkFormationIdentifiedSet",
    "NetworkFormationPredictiveCheck",
    "NetworkFormationScenarioMoments",
    "NetworkFormationUncertaintySummary",
    "NetworkFormationValidationSummary",
    "NetworkIdentificationStatus",
    "NetworkMissingnessRisk",
    "NetworkResult",
    "PeerEffectDecomposition",
    "SBMStratificationResult",
    "StrategicNetworkFormationData",
]
