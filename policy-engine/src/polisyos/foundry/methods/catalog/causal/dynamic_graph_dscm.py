"""Dynamic graph DSCM catalog entry.

This module implements a compact, auditable v1 of the Dynamic Graph Dynamic
Structural Causal Model (DG-DSCM).  The estimator is intentionally conservative:
it separates the graph-to-outcome and outcome-to-graph local mechanisms, reports
when panel fallback semantics are being used, and exposes the identification
warnings needed before downstream policy simulation treats the fitted feedback
loop as causal.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
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

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog._phase1_artifacts import resolve_artifact_store
from polisyos.ir.analytics.dynamic_regime import (
    TemporalIdentificationCertificate,
    TemporalIdentificationTheoremFamily,
    TemporalInterventionSemantics,
    TemporalLawObject,
    TemporalObservabilityRegime,
    TemporalTargetFunctional,
)
from polisyos.ir.analytics.local_independence import (
    EliminabilityCheck,
    IndependentCensoringCheck,
    IntensityModelRequirement,
    LocalIndependenceEdge,
    LocalIndependenceGraphicalChecks,
    LocalIndependenceGraphSpec,
    LocalIndependenceIdentificationSpec,
    LocalIndependenceRuntimeRequirements,
    LocalIndependenceTarget,
    LocalIndependenceWeightingCertificate,
    TreatmentIntensityInterventionSpec,
)
from polisyos.ir.analytics.phase4_dynamics import (
    TemporalGraphCausalCertificate,
    build_temporal_graph_causal_certificate,
    persist_temporal_graph_causal_certificate,
)
from polisyos.ir.refs import TemporalGraphCausalCertificateRef

_METHOD_ID = "causal.dynamic_graph.dscm"
_TRACK_ID = "causal.3.4.continuous_time_dscm"
_EPS = 1.0e-9
_DEFAULT_EVENT_PRIORITY = {
    "edge_dissolution": 0,
    "edge_formation": 1,
    "edge": 2,
    "policy": 3,
    "covariate": 4,
    "outcome": 5,
    "censoring": 6,
}

FeedbackStatus = Literal[
    "full_feedback",
    "A_to_Y_only",
    "Y_to_A_only",
    "no_feedback",
    "unidentified",
]


class DynamicGraphEvent(BaseModel):
    """One event-log row for edge, outcome, policy, or observation updates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    time: float
    event_type: Literal[
        "edge",
        "edge_formation",
        "edge_dissolution",
        "outcome",
        "policy",
        "covariate",
        "censoring",
    ]
    i: int = Field(ge=0)
    j: int | None = Field(default=None, ge=0)
    value: float = 1.0
    mark: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DynamicGraphDSCMData(BaseModel):
    """Observed history for DG-DSCM fitting.

    Preferred production input is an event log.  The v1 estimator also accepts
    panel graph snapshots and node outcomes, which are treated as the explicit
    panel fallback described by the catalog contract.
    """

    contract_id: ClassVar[str] = "foundry.causal.dynamic_graph_dscm_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    edge_states: Any | None = None
    node_outcomes: Any | None = None
    policy: Any | None = None
    covariates: Any | None = None
    observation: Any | None = None
    event_log: tuple[DynamicGraphEvent, ...] = ()
    initial_edges: Any | None = None
    initial_outcomes: Any | None = None
    node_ids: Any | None = None
    time_index: Any | None = None
    directed: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "edge_states",
        "node_outcomes",
        "policy",
        "covariates",
        "observation",
        "initial_edges",
        "initial_outcomes",
        "node_ids",
        "time_index",
        mode="before",
    )
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return np.asarray(value)

    @field_validator("event_log", mode="before")
    @classmethod
    def _coerce_event_log(cls, value: Any) -> tuple[DynamicGraphEvent, ...]:
        if value in (None, (), []):
            return ()
        if not isinstance(value, (tuple, list)):
            raise ValueError("event_log must be a list/tuple of event rows")
        return tuple(
            item if isinstance(item, DynamicGraphEvent) else DynamicGraphEvent.model_validate(item)
            for item in value
        )

    @model_validator(mode="after")
    def _validate_dynamic_graph_data(self) -> DynamicGraphDSCMData:
        if self.edge_states is None and not self.event_log:
            raise ValueError("DG-DSCM data requires edge_states or event_log")

        if self.edge_states is not None:
            edge_states = np.asarray(self.edge_states, dtype=float)
            if edge_states.ndim != 3:
                raise ValueError("edge_states must be a 3D array: (n_periods, n_units, n_units)")
            if edge_states.shape[1] != edge_states.shape[2]:
                raise ValueError("edge_states must contain square adjacency snapshots")
            if edge_states.shape[0] < 2:
                raise ValueError("edge_states must contain at least two time points")
            if not np.isfinite(edge_states).all():
                raise ValueError("edge_states contains non-finite values")
            if not np.isin(edge_states, [0.0, 1.0]).all():
                raise ValueError("edge_states must be binary (0/1)")
            self.edge_states = edge_states

        if self.node_outcomes is not None:
            outcomes = np.asarray(self.node_outcomes, dtype=float)
            if outcomes.ndim != 2:
                raise ValueError("node_outcomes must be a 2D array")
            if not np.isfinite(outcomes).all():
                raise ValueError("node_outcomes contains non-finite values")
            if self.edge_states is not None:
                n_periods, n_units, _ = self.edge_states.shape
                if outcomes.shape == (n_periods, n_units):
                    outcomes = outcomes.T
                if outcomes.shape != (n_units, n_periods):
                    raise ValueError(
                        "node_outcomes must be (n_units, n_periods) or "
                        "(n_periods, n_units) aligned with edge_states"
                    )
            self.node_outcomes = outcomes

        if self.policy is not None:
            policy = np.asarray(self.policy, dtype=float)
            if policy.ndim != 2:
                raise ValueError("policy must be a 2D array")
            if not np.isfinite(policy).all():
                raise ValueError("policy contains non-finite values")
            self.policy = policy

        if self.covariates is not None:
            covariates = np.asarray(self.covariates, dtype=float)
            if covariates.ndim not in (2, 3):
                raise ValueError("covariates must be a 2D or 3D array")
            if not np.isfinite(covariates).all():
                raise ValueError("covariates contains non-finite values")
            self.covariates = covariates

        if self.observation is not None:
            observation = np.asarray(self.observation, dtype=float)
            if observation.ndim != 2:
                raise ValueError("observation must be a 2D array")
            if not np.isfinite(observation).all():
                raise ValueError("observation contains non-finite values")
            self.observation = observation

        if self.initial_edges is not None:
            initial_edges = np.asarray(self.initial_edges, dtype=float)
            if initial_edges.ndim != 2 or initial_edges.shape[0] != initial_edges.shape[1]:
                raise ValueError("initial_edges must be a square 2D array")
            if not np.isin(initial_edges, [0.0, 1.0]).all():
                raise ValueError("initial_edges must be binary (0/1)")
            self.initial_edges = initial_edges

        if self.initial_outcomes is not None:
            initial_outcomes = np.asarray(self.initial_outcomes, dtype=float)
            if initial_outcomes.ndim != 1:
                raise ValueError("initial_outcomes must be a 1D array")
            if not np.isfinite(initial_outcomes).all():
                raise ValueError("initial_outcomes contains non-finite values")
            self.initial_outcomes = initial_outcomes

        if self.time_index is not None:
            time_index = np.asarray(self.time_index, dtype=float)
            if time_index.ndim != 1:
                raise ValueError("time_index must be a 1D array")
            if self.edge_states is not None and time_index.shape[0] != self.edge_states.shape[0]:
                raise ValueError("time_index length must match edge_states n_periods")
            if np.any(np.diff(time_index) <= 0.0):
                raise ValueError("time_index must be strictly increasing")
            self.time_index = time_index

        return self

    @field_serializer(
        "edge_states",
        "node_outcomes",
        "policy",
        "covariates",
        "observation",
        "initial_edges",
        "initial_outcomes",
        "node_ids",
        "time_index",
        mode="plain",
        when_used="json",
    )
    def _serialize_numpy(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @property
    def n_units(self) -> int:
        if self.edge_states is not None:
            return int(self.edge_states.shape[1])
        if self.node_outcomes is not None:
            return int(self.node_outcomes.shape[0])
        if self.initial_edges is not None:
            return int(self.initial_edges.shape[0])
        if self.initial_outcomes is not None:
            return int(self.initial_outcomes.shape[0])
        if self.node_ids is not None:
            return int(np.asarray(self.node_ids).shape[0])
        if self.event_log:
            max_id = max(
                max(event.i, -1 if event.j is None else event.j) for event in self.event_log
            )
            return int(max_id + 1)
        raise ValueError("Could not infer n_units")


class LocalDependenceEdgeResult(BaseModel):
    """One fitted local-dependence edge in the DG-DSCM output graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    present: bool
    estimate: float | None = None
    p_value: float | None = None
    interpretation: str
    mechanism: str
    test: str


class DynamicGraphDSCMResult(BaseModel):
    """DG-DSCM fitted result and identification surface."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    schema_version: str = "1.0"
    method_id: str = _METHOD_ID
    track: str = _TRACK_ID
    processes: dict[str, Any]
    feedback_status: FeedbackStatus
    local_dependence_graph: dict[str, LocalDependenceEdgeResult]
    interventions: tuple[dict[str, Any], ...]
    estimator_api: dict[str, Any]
    mechanism_estimates: dict[str, Any]
    causal_effect_curves: dict[str, tuple[float, ...]]
    loop_effect: float | None = None
    uncertainty_intervals: dict[str, Any]
    diagnostics: dict[str, Any]
    fallback_used: bool
    identification_warnings: tuple[str, ...] = ()
    local_independence_certificate: LocalIndependenceWeightingCertificate | None = None
    temporal_identification_certificate: TemporalIdentificationCertificate | None = None
    temporal_graph_causal_certificate: TemporalGraphCausalCertificate | None = None
    temporal_graph_causal_certificate_ref: TemporalGraphCausalCertificateRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("causal_effect_curves", mode="before")
    @classmethod
    def _coerce_curves(cls, value: Any) -> dict[str, tuple[float, ...]]:
        if not isinstance(value, Mapping):
            raise ValueError("causal_effect_curves must be a mapping")
        return {
            str(key): tuple(float(item) for item in np.asarray(series, dtype=float).ravel())
            for key, series in value.items()
        }


def _dynamic_graph_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                name="result",
                slot_type=SlotType.SCALAR,
                unit=Unit("report", "json"),
                description="DynamicGraphDSCMResult with feedback diagnostics and effect curves.",
            )
        }
    )


def _extract_dynamic_graph_data(state: Any) -> DynamicGraphDSCMData:
    if isinstance(state, DynamicGraphDSCMData):
        return state
    if isinstance(state, Mapping):
        return DynamicGraphDSCMData.model_validate(dict(state))
    raise TypeError(f"Expected DynamicGraphDSCMData or mapping, got {type(state).__name__}")


def _normal_two_sided_pvalue(z_score: float) -> float:
    if not math.isfinite(z_score):
        return 1.0
    return float(math.erfc(abs(z_score) / math.sqrt(2.0)))


def _as_time_major_outcomes(data: DynamicGraphDSCMData, n_periods: int, n_units: int) -> np.ndarray:
    if data.node_outcomes is None:
        if data.initial_outcomes is not None:
            initial = np.asarray(data.initial_outcomes, dtype=float)
            return np.tile(initial, (n_periods, 1))
        return np.zeros((n_periods, n_units), dtype=float)
    outcomes = np.asarray(data.node_outcomes, dtype=float)
    if outcomes.shape == (n_periods, n_units):
        return outcomes
    if outcomes.shape == (n_units, n_periods):
        return outcomes.T
    raise ValueError("node_outcomes cannot be aligned to edge_states")


def _as_time_major_policy(data: DynamicGraphDSCMData, n_periods: int, n_units: int) -> np.ndarray:
    if data.policy is None:
        return np.zeros((n_periods, n_units), dtype=float)
    policy = np.asarray(data.policy, dtype=float)
    if policy.shape == (n_periods, n_units):
        return policy
    if policy.shape == (n_units, n_periods):
        return policy.T
    raise ValueError("policy must align as (n_units, n_periods) or (n_periods, n_units)")


def _as_time_major_observation(
    data: DynamicGraphDSCMData,
    n_periods: int,
    n_units: int,
) -> np.ndarray | None:
    if data.observation is None:
        return None
    observation = np.asarray(data.observation, dtype=float)
    if observation.shape == (n_periods, n_units):
        return observation
    if observation.shape == (n_units, n_periods):
        return observation.T
    raise ValueError("observation must align as (n_units, n_periods) or (n_periods, n_units)")


def _as_time_major_covariates(
    data: DynamicGraphDSCMData,
    n_periods: int,
    n_units: int,
) -> np.ndarray | None:
    if data.covariates is None:
        return None
    covariates = np.asarray(data.covariates, dtype=float)
    if covariates.ndim == 2:
        if covariates.shape[0] != n_units:
            raise ValueError("2D covariates first dimension must match n_units")
        return np.repeat(covariates[np.newaxis, :, :], n_periods, axis=0)
    if covariates.shape[0] == n_periods and covariates.shape[1] == n_units:
        return covariates
    if covariates.shape[0] == n_units and covariates.shape[1] == n_periods:
        return np.transpose(covariates, (1, 0, 2))
    raise ValueError("3D covariates must align with n_units and n_periods")


def _event_priority(event: DynamicGraphEvent, rule: Any) -> int:
    if isinstance(rule, Mapping):
        return int(rule.get(event.event_type, _DEFAULT_EVENT_PRIORITY[event.event_type]))
    if isinstance(rule, (tuple, list)):
        order = {str(name): index for index, name in enumerate(rule)}
        return int(order.get(event.event_type, _DEFAULT_EVENT_PRIORITY[event.event_type]))
    return _DEFAULT_EVENT_PRIORITY[event.event_type]


def _reconstruct_from_event_log(
    data: DynamicGraphDSCMData,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None, np.ndarray, str]:
    n_units = data.n_units
    event_times = sorted({float(event.time) for event in data.event_log})
    if not event_times:
        raise ValueError("event_log must contain at least one event")
    horizon_start = float(data.metadata.get("horizon_start", min(0.0, event_times[0])))
    if horizon_start in event_times:
        time_grid = np.asarray(event_times, dtype=float)
    else:
        time_grid = np.asarray([horizon_start, *event_times], dtype=float)

    n_periods = int(time_grid.shape[0])
    edges = np.zeros((n_periods, n_units, n_units), dtype=float)
    outcomes = np.zeros((n_periods, n_units), dtype=float)
    policy = np.zeros((n_periods, n_units), dtype=float)
    covariate_events = [event for event in data.event_log if event.event_type == "covariate"]
    covariates = (
        _as_time_major_covariates(data, n_periods, n_units)
        if data.covariates is not None
        else (
            np.zeros((n_periods, n_units, 1), dtype=float)
            if covariate_events
            else None
        )
    )

    if data.initial_edges is not None:
        edges[0] = np.asarray(data.initial_edges, dtype=float)
    if data.initial_outcomes is not None:
        outcomes[0] = np.asarray(data.initial_outcomes, dtype=float)
    if data.node_outcomes is not None:
        outcomes = _as_time_major_outcomes(data, n_periods, n_units)
    if data.policy is not None:
        policy = _as_time_major_policy(data, n_periods, n_units)

    events_by_time: dict[float, list[DynamicGraphEvent]] = {}
    for event in data.event_log:
        events_by_time.setdefault(float(event.time), []).append(event)

    priority_rule = data.metadata.get("event_priority_rule")
    for index in range(1, n_periods):
        edges[index] = edges[index - 1]
        outcomes[index] = outcomes[index - 1]
        policy[index] = policy[index - 1]
        if covariates is not None:
            covariates[index] = covariates[index - 1]
        events_at_time = sorted(
            events_by_time.get(float(time_grid[index]), []),
            key=lambda item: _event_priority(item, priority_rule),
        )
        for event in events_at_time:
            if event.event_type in {"edge", "edge_formation", "edge_dissolution"}:
                if event.j is None:
                    raise ValueError("edge events require j")
                edge_value = 0.0 if event.event_type == "edge_dissolution" else float(event.value)
                edges[index, event.i, event.j] = 1.0 if edge_value >= 0.5 else 0.0
                if not data.directed:
                    edges[index, event.j, event.i] = edges[index, event.i, event.j]
            elif event.event_type == "outcome":
                outcomes[index, event.i] = float(event.value)
            elif event.event_type == "policy":
                policy[index, event.i] = float(event.value)
            elif event.event_type == "covariate" and covariates is not None:
                feature_index = int(event.metadata.get("feature_index", 0))
                if feature_index >= covariates.shape[2]:
                    expanded = np.zeros((n_periods, n_units, feature_index + 1), dtype=float)
                    expanded[:, :, : covariates.shape[2]] = covariates
                    covariates = expanded
                covariates[index, event.i, feature_index] = float(event.value)

    data_source = (
        "hybrid"
        if any(
            item is not None
            for item in (data.edge_states, data.node_outcomes, data.policy, data.covariates)
        )
        else "event_log"
    )
    return edges, outcomes, policy, covariates, time_grid, data_source


def _materialize_history(
    data: DynamicGraphDSCMData,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None, np.ndarray, str]:
    if data.edge_states is None:
        return _reconstruct_from_event_log(data)
    edges = np.asarray(data.edge_states, dtype=float)
    n_periods, n_units, _ = edges.shape
    outcomes = _as_time_major_outcomes(data, n_periods, n_units)
    policy = _as_time_major_policy(data, n_periods, n_units)
    covariates = _as_time_major_covariates(data, n_periods, n_units)
    time_grid = (
        np.asarray(data.time_index, dtype=float)
        if data.time_index is not None
        else np.arange(n_periods, dtype=float)
    )
    return edges, outcomes, policy, covariates, time_grid, "hybrid" if data.event_log else "panel"


def _pair_indices(n_units: int, directed: bool) -> list[tuple[int, int]]:
    if directed:
        return [(i, j) for i in range(n_units) for j in range(n_units) if i != j]
    return [(i, j) for i in range(n_units) for j in range(i + 1, n_units)]


def _network_exposure(edges: np.ndarray, outcomes: np.ndarray) -> np.ndarray:
    degree = edges.sum(axis=1)
    exposure = edges @ outcomes
    return np.divide(exposure, degree, out=np.zeros_like(exposure), where=degree > _EPS)


def _shared_neighbors(edges: np.ndarray, i: int, j: int) -> float:
    return float(np.dot(edges[i], edges[j]))


def _covariate_signal(covariates: np.ndarray | None, t_index: int, n_units: int) -> np.ndarray:
    if covariates is None:
        return np.zeros(n_units, dtype=float)
    values = np.asarray(covariates[t_index], dtype=float)
    if values.ndim == 1:
        return values
    return values.mean(axis=1)


def _edge_feature_names() -> tuple[str, ...]:
    return (
        "outcome_similarity",
        "outcome_difference",
        "sender_degree",
        "receiver_degree",
        "reciprocity",
        "shared_neighbors",
        "policy_sender",
        "policy_receiver",
        "policy_difference",
        "sender_covariate",
        "receiver_covariate",
        "covariate_distance",
    )


def _edge_feature_row(
    *,
    current_edges: np.ndarray,
    current_outcomes: np.ndarray,
    current_policy: np.ndarray,
    current_covariate: np.ndarray,
    i: int,
    j: int,
    directed: bool,
) -> list[float]:
    degree = current_edges.sum(axis=1)
    y_std = float(np.std(current_outcomes))
    scale = y_std if y_std > _EPS else 1.0
    outcome_difference = abs(float(current_outcomes[i] - current_outcomes[j])) / scale
    policy_difference = abs(float(current_policy[i] - current_policy[j]))
    covariate_difference = abs(float(current_covariate[i] - current_covariate[j]))
    return [
        -outcome_difference,
        outcome_difference,
        float(degree[i]),
        float(degree[j]),
        float(current_edges[j, i]) if directed else 0.0,
        _shared_neighbors(current_edges, i, j),
        float(current_policy[i]),
        float(current_policy[j]),
        policy_difference,
        float(current_covariate[i]),
        float(current_covariate[j]),
        covariate_difference,
    ]


def _fit_linear_model(
    response: np.ndarray,
    predictors: np.ndarray,
    names: tuple[str, ...],
) -> dict[str, Any]:
    y = np.asarray(response, dtype=float).ravel()
    x = np.asarray(predictors, dtype=float)
    if x.ndim == 1:
        x = x.reshape(-1, 1)
    if x.shape[0] != y.shape[0]:
        raise ValueError("predictor row count must match response length")

    finite = np.isfinite(y) & np.isfinite(x).all(axis=1)
    y = y[finite]
    x = x[finite]
    n_obs = int(y.shape[0])
    n_predictors = int(x.shape[1])
    if n_obs <= n_predictors + 1 or float(np.var(y)) <= _EPS:
        zero = dict.fromkeys(names, 0.0)
        ones = dict.fromkeys(names, 1.0)
        return {
            "n_obs": n_obs,
            "intercept": float(np.mean(y)) if n_obs else 0.0,
            "coefficients": zero,
            "standard_errors": zero,
            "p_values": ones,
            "residual_variance": 0.0,
            "residual_mean": 0.0,
            "fitted": tuple(float(np.mean(y)) for _ in range(n_obs)),
            "response_mean": float(np.mean(y)) if n_obs else 0.0,
        }

    design = np.column_stack([np.ones(n_obs, dtype=float), x])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    fitted = design @ beta
    residual = y - fitted
    dof = max(n_obs - design.shape[1], 1)
    residual_variance = float(np.sum(residual**2) / dof)
    xtx_inv = np.linalg.pinv(design.T @ design)
    se = np.sqrt(np.maximum(np.diag(xtx_inv) * residual_variance, 0.0))
    p_values: dict[str, float] = {}
    coefficients: dict[str, float] = {}
    standard_errors: dict[str, float] = {}
    for offset, name in enumerate(names, start=1):
        coefficient = float(beta[offset])
        stderr = float(se[offset])
        z_score = coefficient / stderr if stderr > _EPS else 0.0
        coefficients[name] = coefficient
        standard_errors[name] = stderr
        p_values[name] = _normal_two_sided_pvalue(z_score)

    return {
        "n_obs": n_obs,
        "intercept": float(beta[0]),
        "coefficients": coefficients,
        "standard_errors": standard_errors,
        "p_values": p_values,
        "residual_variance": residual_variance,
        "residual_mean": float(np.mean(residual)),
        "fitted": tuple(float(item) for item in fitted.tolist()),
        "response_mean": float(np.mean(y)),
    }


def _fit_outcome_mechanism(
    edges: np.ndarray,
    outcomes: np.ndarray,
    policy: np.ndarray,
    covariates: np.ndarray | None,
    time_grid: np.ndarray,
) -> dict[str, Any]:
    response: list[float] = []
    rows: list[list[float]] = []
    for t_index in range(edges.shape[0] - 1):
        dt = max(float(time_grid[t_index + 1] - time_grid[t_index]), _EPS)
        exposure = _network_exposure(edges[t_index], outcomes[t_index])
        degree = edges[t_index].sum(axis=1)
        covariate = _covariate_signal(covariates, t_index, edges.shape[1])
        for unit in range(edges.shape[1]):
            response.append(float((outcomes[t_index + 1, unit] - outcomes[t_index, unit]) / dt))
            rows.append(
                [
                    float(exposure[unit]),
                    float(outcomes[t_index, unit]),
                    float(degree[unit]),
                    float(policy[t_index, unit]),
                    float(covariate[unit]),
                ]
            )
    names = ("network_exposure", "own_lag_outcome", "degree", "policy", "covariate")
    return _fit_linear_model(np.asarray(response), np.asarray(rows), names)


def _fit_edge_mechanisms(
    edges: np.ndarray,
    outcomes: np.ndarray,
    policy: np.ndarray,
    covariates: np.ndarray | None,
    directed: bool,
) -> dict[str, Any]:
    pairs = _pair_indices(edges.shape[1], directed)
    formation_y: list[float] = []
    formation_x: list[list[float]] = []
    dissolution_y: list[float] = []
    dissolution_x: list[list[float]] = []

    for t_index in range(edges.shape[0] - 1):
        current_edges = edges[t_index]
        next_edges = edges[t_index + 1]
        current_covariate = _covariate_signal(covariates, t_index, edges.shape[1])
        for i, j in pairs:
            row = _edge_feature_row(
                current_edges=current_edges,
                current_outcomes=outcomes[t_index],
                current_policy=policy[t_index],
                current_covariate=current_covariate,
                i=i,
                j=j,
                directed=directed,
            )
            if current_edges[i, j] < 0.5:
                formation_y.append(float(next_edges[i, j] >= 0.5))
                formation_x.append(row)
            else:
                dissolution_y.append(float(next_edges[i, j] < 0.5))
                dissolution_x.append(row)

    names = _edge_feature_names()
    formation = _fit_linear_model(np.asarray(formation_y), np.asarray(formation_x), names)
    dissolution = _fit_linear_model(np.asarray(dissolution_y), np.asarray(dissolution_x), names)
    return {"formation": formation, "dissolution": dissolution}


def _coefficient_interval(model: Mapping[str, Any], coefficient_name: str) -> tuple[float, float]:
    coefficients = model.get("coefficients", {})
    standard_errors = model.get("standard_errors", {})
    estimate = float(coefficients.get(coefficient_name, 0.0))
    se = float(standard_errors.get(coefficient_name, 0.0))
    return (float(estimate - 1.96 * se), float(estimate + 1.96 * se))


def _status_from_tests(
    *,
    outcome_model: Mapping[str, Any],
    edge_models: Mapping[str, Any],
    alpha: float,
    min_effect_size: float,
    force_unidentified: bool,
) -> tuple[FeedbackStatus, bool, bool]:
    if force_unidentified:
        return "unidentified", False, False

    a_to_y_beta = float(outcome_model["coefficients"].get("network_exposure", 0.0))
    a_to_y_p = float(outcome_model["p_values"].get("network_exposure", 1.0))
    a_to_y = a_to_y_p <= alpha and abs(a_to_y_beta) >= min_effect_size

    formation = edge_models["formation"]
    dissolution = edge_models["dissolution"]
    formation_beta = float(formation["coefficients"].get("outcome_similarity", 0.0))
    formation_p = float(formation["p_values"].get("outcome_similarity", 1.0))
    dissolution_beta = float(dissolution["coefficients"].get("outcome_difference", 0.0))
    dissolution_p = float(dissolution["p_values"].get("outcome_difference", 1.0))
    y_to_a = (
        (formation_p <= alpha and abs(formation_beta) >= min_effect_size)
        or (dissolution_p <= alpha and abs(dissolution_beta) >= min_effect_size)
    )

    if a_to_y and y_to_a:
        return "full_feedback", True, True
    if a_to_y:
        return "A_to_Y_only", True, False
    if y_to_a:
        return "Y_to_A_only", False, True
    return "no_feedback", False, False


def _edge_transition_probability(
    model: Mapping[str, Any],
    row: list[float],
    *,
    multiplier: float,
    block_y_to_a: bool,
) -> float:
    names = _edge_feature_names()
    value = float(model.get("intercept", 0.0))
    coefficients = model.get("coefficients", {})
    for name, feature in zip(names, row, strict=True):
        if block_y_to_a and name in {"outcome_similarity", "outcome_difference"}:
            continue
        value += float(coefficients.get(name, 0.0)) * float(feature)
    return float(np.clip(value * multiplier, 0.0, 1.0))


def _simulate_expected_path(
    *,
    initial_edges: np.ndarray,
    initial_outcomes: np.ndarray,
    time_grid: np.ndarray,
    policy: np.ndarray,
    covariates: np.ndarray | None,
    outcome_model: Mapping[str, Any],
    edge_models: Mapping[str, Any],
    directed: bool,
    intervention: Mapping[str, Any],
    block_a_to_y: bool = False,
    block_y_to_a: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    n_periods = int(time_grid.shape[0])
    n_units = int(initial_outcomes.shape[0])
    pairs = _pair_indices(n_units, directed)
    edges_path = np.zeros((n_periods, n_units, n_units), dtype=float)
    outcomes_path = np.zeros((n_periods, n_units), dtype=float)
    edges_path[0] = initial_edges.astype(float)
    outcomes_path[0] = initial_outcomes.astype(float)

    formation_multiplier = float(intervention.get("formation_multiplier", 1.0))
    dissolution_multiplier = float(intervention.get("dissolution_multiplier", 1.0))
    outcome_shift = float(intervention.get("outcome_shift", 0.0))
    policy_shift = float(intervention.get("policy_shift", 0.0))

    outcome_coeffs = outcome_model.get("coefficients", {})
    for t_index in range(n_periods - 1):
        current_edges = edges_path[t_index]
        current_outcomes = outcomes_path[t_index]
        degree = current_edges.sum(axis=1)
        exposure = _network_exposure(current_edges, current_outcomes)
        covariate = _covariate_signal(covariates, t_index, n_units)
        dt = max(float(time_grid[t_index + 1] - time_grid[t_index]), _EPS)

        drift = np.full(n_units, float(outcome_model.get("intercept", 0.0)))
        if not block_a_to_y:
            drift += float(outcome_coeffs.get("network_exposure", 0.0)) * exposure
        drift += float(outcome_coeffs.get("own_lag_outcome", 0.0)) * current_outcomes
        drift += float(outcome_coeffs.get("degree", 0.0)) * degree
        drift += float(outcome_coeffs.get("policy", 0.0)) * (policy[t_index] + policy_shift)
        drift += float(outcome_coeffs.get("covariate", 0.0)) * covariate
        drift += outcome_shift
        outcomes_path[t_index + 1] = current_outcomes + dt * drift

        next_edges = current_edges.copy()
        for i, j in pairs:
            row = _edge_feature_row(
                current_edges=current_edges,
                current_outcomes=current_outcomes,
                current_policy=policy[t_index] + policy_shift,
                current_covariate=covariate,
                i=i,
                j=j,
                directed=directed,
            )
            if current_edges[i, j] < 0.5:
                probability = _edge_transition_probability(
                    edge_models["formation"],
                    row,
                    multiplier=formation_multiplier,
                    block_y_to_a=block_y_to_a,
                )
                next_edges[i, j] = current_edges[i, j] + (1.0 - current_edges[i, j]) * probability
            else:
                probability = _edge_transition_probability(
                    edge_models["dissolution"],
                    row,
                    multiplier=dissolution_multiplier,
                    block_y_to_a=block_y_to_a,
                )
                next_edges[i, j] = current_edges[i, j] * (1.0 - probability)
            if not directed:
                next_edges[j, i] = next_edges[i, j]
        np.fill_diagonal(next_edges, 0.0)
        edges_path[t_index + 1] = np.clip(next_edges, 0.0, 1.0)

    return edges_path, outcomes_path


def _causal_effect_curves(
    *,
    edges: np.ndarray,
    outcomes: np.ndarray,
    policy: np.ndarray,
    covariates: np.ndarray | None,
    time_grid: np.ndarray,
    outcome_model: Mapping[str, Any],
    edge_models: Mapping[str, Any],
    directed: bool,
    intervention: Mapping[str, Any],
) -> tuple[dict[str, np.ndarray], float]:
    baseline_edges, baseline_outcomes = _simulate_expected_path(
        initial_edges=edges[0],
        initial_outcomes=outcomes[0],
        time_grid=time_grid,
        policy=policy,
        covariates=covariates,
        outcome_model=outcome_model,
        edge_models=edge_models,
        directed=directed,
        intervention={},
    )
    full_edges, full_outcomes = _simulate_expected_path(
        initial_edges=edges[0],
        initial_outcomes=outcomes[0],
        time_grid=time_grid,
        policy=policy,
        covariates=covariates,
        outcome_model=outcome_model,
        edge_models=edge_models,
        directed=directed,
        intervention=intervention,
    )
    blocked_y_to_a_edges, blocked_y_to_a_outcomes = _simulate_expected_path(
        initial_edges=edges[0],
        initial_outcomes=outcomes[0],
        time_grid=time_grid,
        policy=policy,
        covariates=covariates,
        outcome_model=outcome_model,
        edge_models=edge_models,
        directed=directed,
        intervention=intervention,
        block_y_to_a=True,
    )
    blocked_a_to_y_edges, blocked_a_to_y_outcomes = _simulate_expected_path(
        initial_edges=edges[0],
        initial_outcomes=outcomes[0],
        time_grid=time_grid,
        policy=policy,
        covariates=covariates,
        outcome_model=outcome_model,
        edge_models=edge_models,
        directed=directed,
        intervention=intervention,
        block_a_to_y=True,
    )

    full_outcome_effect = full_outcomes.mean(axis=1) - baseline_outcomes.mean(axis=1)
    blocked_y_to_a_effect = (
        blocked_y_to_a_outcomes.mean(axis=1) - baseline_outcomes.mean(axis=1)
    )
    blocked_a_to_y_effect = (
        blocked_a_to_y_outcomes.mean(axis=1) - baseline_outcomes.mean(axis=1)
    )
    full_density_effect = full_edges.mean(axis=(1, 2)) - baseline_edges.mean(axis=(1, 2))
    curves = {
        "observed_mean_outcome": outcomes.mean(axis=1),
        "observed_edge_density": edges.mean(axis=(1, 2)),
        "full_mean_outcome_effect": full_outcome_effect,
        "full_edge_density_effect": full_density_effect,
        "blocked_Y_to_A_mean_outcome_effect": blocked_y_to_a_effect,
        "blocked_A_to_Y_mean_outcome_effect": blocked_a_to_y_effect,
        "loop_mean_outcome_effect": full_outcome_effect
        - blocked_y_to_a_effect
        - blocked_a_to_y_effect,
    }
    loop_effect = float(
        full_outcome_effect[-1] - blocked_y_to_a_effect[-1] - blocked_a_to_y_effect[-1]
    )
    return curves, loop_effect


def _build_identification_warnings(
    *,
    data: DynamicGraphDSCMData,
    data_source: str,
    edges: np.ndarray,
    outcomes: np.ndarray,
    outcome_model: Mapping[str, Any],
    edge_models: Mapping[str, Any],
) -> tuple[str, ...]:
    warnings: list[str] = []
    if data_source == "panel":
        warnings.append(
            "panel_fallback_used: exact within-interval ordering is not observed; "
            "feedback direction relies on the panel transition model."
        )
    if data_source == "hybrid":
        warnings.append(
            "hybrid_data_used: exact edge or outcome events are combined with panel-aligned "
            "state histories; unmatched within-interval ordering remains model-based."
        )
    if data.event_log and any(len([event for event in data.event_log if event.time == t]) > 1 for t in {event.time for event in data.event_log}):
        if "event_priority_rule" not in data.metadata:
            warnings.append(
                "simultaneous_events_default_priority: same-time event ordering used the "
                "DG-DSCM default priority rule."
            )
    if data_source in {"panel", "hybrid"} and edges.shape[0] > 1:
        edge_changed = np.any(np.abs(np.diff(edges, axis=0)) > _EPS, axis=(1, 2))
        outcome_changed = np.any(np.abs(np.diff(outcomes, axis=0)) > _EPS, axis=1)
        if bool(np.any(edge_changed & outcome_changed)):
            warnings.append(
                "within_interval_ordering_unobserved: edge and outcome states both change "
                "between at least one pair of snapshots."
            )
    if data.metadata.get("unobserved_homophily") is True:
        warnings.append(
            "unobserved_homophily_declared: latent similarity may drive both ties and outcomes."
        )
    if data.metadata.get("partial_graph_observation") is True:
        warnings.append(
            "partial_graph_observation_declared: missing edges can mimic dissolution or suppress exposure."
        )
    if float(np.var(_network_exposure(edges[0], outcomes[0]))) <= _EPS:
        warnings.append("low_initial_exposure_variation: A_to_Y positivity may be weak.")
    if int(edge_models["formation"]["n_obs"]) == 0:
        warnings.append("no_formation_risk_set: Y_to_A formation mechanism is not estimable.")
    if int(edge_models["dissolution"]["n_obs"]) == 0:
        warnings.append("no_dissolution_risk_set: Y_to_A dissolution mechanism is not estimable.")
    if int(outcome_model["n_obs"]) <= 8:
        warnings.append("small_outcome_risk_set: outcome mechanism estimates are unstable.")
    edge_density = edges.mean(axis=(1, 2))
    if float(edge_density.min()) <= _EPS or float(edge_density.max()) >= 1.0 - _EPS:
        warnings.append(
            "edge_positivity_boundary: observed graph density touches an empty or saturated support boundary."
        )
    return tuple(dict.fromkeys(warnings))


def _time_aggregation_sensitivity(
    *,
    edges: np.ndarray,
    outcomes: np.ndarray,
    policy: np.ndarray,
    covariates: np.ndarray | None,
    time_grid: np.ndarray,
) -> dict[str, Any]:
    if edges.shape[0] < 5:
        return {"checked": False, "reason": "need_at_least_five_time_points"}
    indices = np.arange(0, edges.shape[0], 2, dtype=int)
    if indices[-1] != edges.shape[0] - 1:
        indices = np.append(indices, edges.shape[0] - 1)
    coarse = _fit_outcome_mechanism(
        edges[indices],
        outcomes[indices],
        policy[indices],
        None if covariates is None else covariates[indices],
        time_grid[indices],
    )
    fine = _fit_outcome_mechanism(edges, outcomes, policy, covariates, time_grid)
    fine_beta = float(fine["coefficients"].get("network_exposure", 0.0))
    coarse_beta = float(coarse["coefficients"].get("network_exposure", 0.0))
    return {
        "checked": True,
        "fine_A_to_Y": fine_beta,
        "coarse_A_to_Y": coarse_beta,
        "sign_flip": bool(np.sign(fine_beta) != np.sign(coarse_beta) and abs(fine_beta) > _EPS),
    }


def _build_local_independence_certificate(
    *,
    feedback_status: FeedbackStatus,
    time_grid: np.ndarray,
    warnings: tuple[str, ...],
    a_to_y_present: bool,
    y_to_a_present: bool,
    p_to_y_present: bool,
    p_to_a_present: bool,
    x_to_y_present: bool,
    x_to_a_present: bool,
) -> LocalIndependenceWeightingCertificate:
    identified = feedback_status != "unidentified"
    edges = []
    if a_to_y_present:
        edges.append(LocalIndependenceEdge(src="A", dst="Y"))
    if y_to_a_present:
        edges.append(LocalIndependenceEdge(src="Y", dst="A"))
    if p_to_y_present:
        edges.append(LocalIndependenceEdge(src="P", dst="Y"))
    if p_to_a_present:
        edges.append(LocalIndependenceEdge(src="P", dst="A"))
    if x_to_y_present:
        edges.append(LocalIndependenceEdge(src="X", dst="Y"))
    if x_to_a_present:
        edges.append(LocalIndependenceEdge(src="X", dst="A"))
    horizon_start = float(time_grid[0])
    horizon_end = float(time_grid[-1])
    return LocalIndependenceWeightingCertificate(
        verification_status="identified" if identified else "oracle_needed",
        target=LocalIndependenceTarget(
            functional="dynamic_graph_feedback_loop_effect",
            outcome_process="Y",
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            time_scale="observed_time",
        ),
        graph=LocalIndependenceGraphSpec(
            process_family="event_log",
            representation="LIG_or_muDMG",
            separation_criterion="delta_or_mu",
            nodes=("A", "Y", "X", "P", "R"),
            edges=tuple(edges),
            notes=("DG-DSCM local-dependence projection over graph and node processes.",),
        ),
        treatment_intervention=TreatmentIntensityInterventionSpec(
            node="A",
            predictable_wrt=("F_t_minus",),
            bound_note="Edge interventions replace formation/dissolution intensities.",
        ),
        identification=LocalIndependenceIdentificationSpec(
            theorem_reference=(
                "Dynamic Structural Causal Models",
                "Causal identification for continuous-time stochastic processes",
                "Local-independence graphs for marked point processes",
            ),
            weight_components=("W_edge_formation", "W_edge_dissolution", "W_outcome"),
            formula_hint="E_do(q)[h(H_T)] = E_obs[W_T(q) h(H_T)]",
            decensoring_map_used=False,
        ),
        graphical_checks=LocalIndependenceGraphicalChecks(
            independent_censoring=IndependentCensoringCheck(
                checked=identified,
                criterion="graph_structure" if identified else "unknown",
                statement="Observation/censoring process is assumed ignorable given F_{t-}.",
                conditioning_set=("F_t_minus",),
            ),
            eliminability=EliminabilityCheck(
                checked=identified,
                target_node="Y",
                eliminate_set=(),
                elimination_sequence=(),
            ),
        ),
        runtime_requirements=LocalIndependenceRuntimeRequirements(
            needed_intensity_models=(
                IntensityModelRequirement(
                    process="A_formation",
                    conditioning=("A(t-)", "Y(t-)", "X(t-)", "P(t-)"),
                    estimation="relational_event_or_panel_transition",
                ),
                IntensityModelRequirement(
                    process="A_dissolution",
                    conditioning=("A(t-)", "Y(t-)", "X(t-)", "P(t-)"),
                    estimation="relational_event_or_panel_transition",
                ),
                IntensityModelRequirement(
                    process="Y",
                    conditioning=("A(t-)", "Y(t-)", "X(t-)", "P(t-)"),
                    estimation="drift_or_counting_intensity",
                ),
            ),
            data_contract=DynamicGraphDSCMData.contract_id,
            positivity_assumed=True,
            diagnostics_required=True,
        ),
        assumptions=(
            "complete_ordered_history_or_declared_panel_fallback",
            "causal_validity_local_mechanism_modularity",
            "continuous_time_sequential_exchangeability",
            "positivity_or_absolute_continuity",
            "sufficient_history_state",
            "faithfulness_for_feedback_discovery",
        ),
        proof_trace=(
            "factorize trajectory law into edge formation, edge dissolution, outcome, policy, covariate, and observation mechanisms",
            "identify A(t-) to Y(t) through the outcome local characteristic",
            "identify Y(t-) to A(t) through edge formation/dissolution local characteristics",
            "replace targeted local characteristics to compute stochastic interventions",
        ),
        metadata={"warnings": list(warnings), "feedback_status": feedback_status},
    )


def _build_temporal_identification_certificate(
    warnings: tuple[str, ...],
) -> TemporalIdentificationCertificate:
    return TemporalIdentificationCertificate(
        theorem_family=TemporalIdentificationTheoremFamily.LOCAL_INDEPENDENCE_WEIGHTING_V1,
        identified_functionals=(
            TemporalTargetFunctional.EFFECT_PATH,
            TemporalTargetFunctional.INTEGRAL_EFFECT,
        ),
        intervention_semantics=TemporalInterventionSemantics.INTENSITY_REPLACEMENT,
        observability_regime=TemporalObservabilityRegime.OBSERVED_FILTRATION,
        law_object=TemporalLawObject.INTENSITY_COMPENSATOR,
        assumptions=(
            "observed_filtration_contains_edge_outcome_policy_covariate_history",
            "interventions_replace_local_intensities_or_drifts",
            "absolute_continuity_for_stochastic_intervention_laws",
        ),
        notes={
            "method_id": _METHOD_ID,
            "track": _TRACK_ID,
            "warnings": list(warnings),
        },
    )


def _process_declarations(*, directed: bool, outcome_family: str) -> dict[str, Any]:
    return {
        "A": {
            "type": "graph_edge_state",
            "index": ["i", "j"],
            "state_space": "binary",
            "directed": bool(directed),
            "mechanisms": {
                "formation": "counting_intensity",
                "dissolution": "counting_intensity",
            },
        },
        "Y": {
            "type": "node_outcome",
            "index": ["i"],
            "family": outcome_family,
        },
        "X": {
            "type": "node_covariate",
            "index": ["i"],
            "time_varying": True,
            "optional": True,
        },
        "P": {
            "type": "policy_or_treatment",
            "index": ["i"],
            "assignment": "randomized | observational | stochastic_policy",
            "optional": True,
        },
        "R": {
            "type": "observation_or_censoring",
            "index": ["i"],
            "optional": True,
        },
    }


def _intervention_api(intervention: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    return (
        {
            "id": "edge_intensity_shift",
            "target": "A",
            "type": "intensity_shift",
            "formation_multiplier": float(intervention.get("formation_multiplier", 1.0)),
            "dissolution_multiplier": float(intervention.get("dissolution_multiplier", 1.0)),
        },
        {
            "id": "node_outcome_shift",
            "target": "Y",
            "type": "drift_shift",
            "outcome_shift": float(intervention.get("outcome_shift", 0.0)),
        },
        {
            "id": "policy_shift",
            "target": "P",
            "type": "stochastic_policy_or_exposure_shift",
            "policy_shift": float(intervention.get("policy_shift", 0.0)),
        },
        {
            "id": "block_feedback",
            "target": "model",
            "type": "edge_deletion_in_local_dependence_graph",
            "remove": ["Y_to_A", "A_to_Y"],
        },
    )


def _estimator_api(
    *,
    params: Mapping[str, Any],
    data_source: str,
) -> dict[str, Any]:
    edge_family = str(
        params.get(
            "edge_model_family",
            "relational_event" if data_source == "event_log" else "panel_transition",
        )
    )
    outcome_family = str(params.get("outcome_model_family", "sde_drift"))
    effect_method = str(params.get("causal_effect_method", "g_computation"))
    return {
        "edge_model": {
            "family": edge_family,
            "mechanisms": ["formation", "dissolution"],
            "implemented_backend": "numpy_linear_hazard_proxy",
        },
        "outcome_model": {
            "family": outcome_family,
            "implemented_backend": "numpy_linear_drift_proxy",
        },
        "adjustment": {
            "history": str(params.get("history", "user_defined")),
            "latent_actor_effects": bool(params.get("latent_actor_effects", False)),
            "cross_fitting": bool(params.get("cross_fitting", False)),
        },
        "causal_effect": {
            "method": effect_method,
            "simulation_replicates": int(params.get("simulation_replicates", 1000)),
            "implemented_backend": "deterministic_expected_path_g_computation",
        },
        "diagnostics": {
            "martingale_residuals": True,
            "feedback_tests": True,
            "positivity": True,
            "time_aggregation_sensitivity": True,
            "latent_homophily_sensitivity": True,
        },
    }


def estimate_dynamic_graph_dscm(
    data: DynamicGraphDSCMData | Mapping[str, Any],
    params: Mapping[str, Any] | None = None,
) -> DynamicGraphDSCMResult:
    """Fit the DG-DSCM v1 local mechanisms and return feedback diagnostics."""

    dynamic_data = _extract_dynamic_graph_data(data)
    params = dict(params or {})
    alpha = float(params.get("alpha", 0.05))
    min_effect_size = float(params.get("min_effect_size", 1.0e-8))
    intervention = dict(params.get("intervention", {}))

    edges, outcomes, policy, covariates, time_grid, data_source = _materialize_history(
        dynamic_data
    )
    outcome_model = _fit_outcome_mechanism(edges, outcomes, policy, covariates, time_grid)
    edge_models = _fit_edge_mechanisms(
        edges,
        outcomes,
        policy,
        covariates,
        bool(dynamic_data.directed),
    )
    warnings = _build_identification_warnings(
        data=dynamic_data,
        data_source=data_source,
        edges=edges,
        outcomes=outcomes,
        outcome_model=outcome_model,
        edge_models=edge_models,
    )
    force_unidentified = bool(dynamic_data.metadata.get("unobserved_homophily", False)) and bool(
        params.get("block_when_unobserved_homophily", False)
    )
    feedback_status, a_to_y_present, y_to_a_present = _status_from_tests(
        outcome_model=outcome_model,
        edge_models=edge_models,
        alpha=alpha,
        min_effect_size=min_effect_size,
        force_unidentified=force_unidentified,
    )

    curves, loop_effect = _causal_effect_curves(
        edges=edges,
        outcomes=outcomes,
        policy=policy,
        covariates=covariates,
        time_grid=time_grid,
        outcome_model=outcome_model,
        edge_models=edge_models,
        directed=bool(dynamic_data.directed),
        intervention=intervention,
    )
    if feedback_status != "full_feedback":
        loop_effect_value: float | None = None
    else:
        loop_effect_value = loop_effect

    formation = edge_models["formation"]
    dissolution = edge_models["dissolution"]
    p_to_a_estimate = max(
        abs(float(formation["coefficients"].get("policy_difference", 0.0))),
        abs(float(dissolution["coefficients"].get("policy_difference", 0.0))),
        abs(float(formation["coefficients"].get("policy_sender", 0.0))),
        abs(float(dissolution["coefficients"].get("policy_sender", 0.0))),
    )
    p_to_a_p_value = min(
        float(formation["p_values"].get("policy_difference", 1.0)),
        float(dissolution["p_values"].get("policy_difference", 1.0)),
        float(formation["p_values"].get("policy_sender", 1.0)),
        float(dissolution["p_values"].get("policy_sender", 1.0)),
    )
    x_to_a_estimate = max(
        abs(float(formation["coefficients"].get("covariate_distance", 0.0))),
        abs(float(dissolution["coefficients"].get("covariate_distance", 0.0))),
        abs(float(formation["coefficients"].get("sender_covariate", 0.0))),
        abs(float(dissolution["coefficients"].get("sender_covariate", 0.0))),
    )
    x_to_a_p_value = min(
        float(formation["p_values"].get("covariate_distance", 1.0)),
        float(dissolution["p_values"].get("covariate_distance", 1.0)),
        float(formation["p_values"].get("sender_covariate", 1.0)),
        float(dissolution["p_values"].get("sender_covariate", 1.0)),
    )
    p_to_y_present = float(outcome_model["p_values"].get("policy", 1.0)) <= alpha
    p_to_a_present = p_to_a_p_value <= alpha and p_to_a_estimate >= min_effect_size
    x_to_y_present = float(outcome_model["p_values"].get("covariate", 1.0)) <= alpha
    x_to_a_present = x_to_a_p_value <= alpha and x_to_a_estimate >= min_effect_size
    local_dependence_graph = {
        "A_to_Y": LocalDependenceEdgeResult(
            present=a_to_y_present,
            estimate=float(outcome_model["coefficients"].get("network_exposure", 0.0)),
            p_value=float(outcome_model["p_values"].get("network_exposure", 1.0)),
            interpretation="network influence / interference",
            mechanism="outcome_drift_or_intensity",
            test="conditional_linear_local_dependence_proxy",
        ),
        "Y_to_A": LocalDependenceEdgeResult(
            present=y_to_a_present,
            estimate=float(
                max(
                    abs(float(formation["coefficients"].get("outcome_similarity", 0.0))),
                    abs(float(dissolution["coefficients"].get("outcome_difference", 0.0))),
                )
            ),
            p_value=float(
                min(
                    float(formation["p_values"].get("outcome_similarity", 1.0)),
                    float(dissolution["p_values"].get("outcome_difference", 1.0)),
                )
            ),
            interpretation="selection / outcome-driven rewiring",
            mechanism="edge_formation_dissolution_intensities",
            test="conditional_linear_local_dependence_proxy",
        ),
        "P_to_Y": LocalDependenceEdgeResult(
            present=p_to_y_present,
            estimate=float(outcome_model["coefficients"].get("policy", 0.0)),
            p_value=float(outcome_model["p_values"].get("policy", 1.0)),
            interpretation="policy exposure affects node outcomes",
            mechanism="outcome_drift_or_intensity",
            test="conditional_linear_local_dependence_proxy",
        ),
        "P_to_A": LocalDependenceEdgeResult(
            present=p_to_a_present,
            estimate=p_to_a_estimate,
            p_value=p_to_a_p_value,
            interpretation="policy exposure affects future tie formation or dissolution",
            mechanism="edge_formation_dissolution_intensities",
            test="conditional_linear_local_dependence_proxy",
        ),
        "X_to_A": LocalDependenceEdgeResult(
            present=x_to_a_present,
            estimate=x_to_a_estimate,
            p_value=x_to_a_p_value,
            interpretation="covariate history affects future tie formation or dissolution",
            mechanism="edge_formation_dissolution_intensities",
            test="conditional_linear_local_dependence_proxy",
        ),
        "X_to_Y": LocalDependenceEdgeResult(
            present=x_to_y_present,
            estimate=float(outcome_model["coefficients"].get("covariate", 0.0)),
            p_value=float(outcome_model["p_values"].get("covariate", 1.0)),
            interpretation="covariate history affects node outcomes",
            mechanism="outcome_drift_or_intensity",
            test="conditional_linear_local_dependence_proxy",
        ),
    }

    uncertainty_intervals = {
        "A_to_Y": _coefficient_interval(outcome_model, "network_exposure"),
        "Y_to_A_formation": _coefficient_interval(formation, "outcome_similarity"),
        "Y_to_A_dissolution": _coefficient_interval(dissolution, "outcome_difference"),
        "P_to_Y": _coefficient_interval(outcome_model, "policy"),
        "P_to_A": (
            min(
                _coefficient_interval(formation, "policy_difference")[0],
                _coefficient_interval(dissolution, "policy_difference")[0],
            ),
            max(
                _coefficient_interval(formation, "policy_difference")[1],
                _coefficient_interval(dissolution, "policy_difference")[1],
            ),
        ),
        "X_to_Y": _coefficient_interval(outcome_model, "covariate"),
        "X_to_A": (
            min(
                _coefficient_interval(formation, "covariate_distance")[0],
                _coefficient_interval(dissolution, "covariate_distance")[0],
            ),
            max(
                _coefficient_interval(formation, "covariate_distance")[1],
                _coefficient_interval(dissolution, "covariate_distance")[1],
            ),
        ),
        "confidence_level": 0.95,
    }
    diagnostics = {
        "data_source": data_source,
        "alpha": alpha,
        "outcome_family": str(params.get("outcome_family", "continuous")),
        "outcome_model_n_obs": int(outcome_model["n_obs"]),
        "formation_risk_set_n_obs": int(formation["n_obs"]),
        "dissolution_risk_set_n_obs": int(dissolution["n_obs"]),
        "observation_process": {
            "declared": dynamic_data.observation is not None
            or any(event.event_type == "censoring" for event in dynamic_data.event_log),
            "censoring_event_count": int(
                sum(event.event_type == "censoring" for event in dynamic_data.event_log)
            ),
        },
        "positivity": {
            "edge_density_min": float(edges.mean(axis=(1, 2)).min()),
            "edge_density_max": float(edges.mean(axis=(1, 2)).max()),
            "network_exposure_variance": float(np.var(_network_exposure(edges[0], outcomes[0]))),
        },
        "martingale_residuals": {
            "outcome_residual_variance": float(outcome_model["residual_variance"]),
            "outcome_residual_mean": float(outcome_model["residual_mean"]),
            "formation_residual_variance": float(formation["residual_variance"]),
            "formation_residual_mean": float(formation["residual_mean"]),
            "dissolution_residual_variance": float(dissolution["residual_variance"]),
            "dissolution_residual_mean": float(dissolution["residual_mean"]),
        },
        "feedback_tests": {
            "A_to_Y_p_value": float(outcome_model["p_values"].get("network_exposure", 1.0)),
            "Y_to_A_formation_p_value": float(
                formation["p_values"].get("outcome_similarity", 1.0)
            ),
            "Y_to_A_dissolution_p_value": float(
                dissolution["p_values"].get("outcome_difference", 1.0)
            ),
        },
        "time_aggregation_sensitivity": _time_aggregation_sensitivity(
            edges=edges,
            outcomes=outcomes,
            policy=policy,
            covariates=covariates,
            time_grid=time_grid,
        ),
        "latent_homophily_sensitivity": {
            "mode": "actor_latent_effect_placeholder",
            "reported": True,
            "warning": "Use actor latent effects or external randomization before treating feedback as nonparametrically separated.",
        },
    }
    fallback_used = bool(data_source in {"panel", "hybrid"} or feedback_status != "full_feedback")
    fallback_reason = (
        "panel_transition_fallback"
        if data_source == "panel"
        else (
            "hybrid_ordering_fallback"
            if data_source == "hybrid"
            else ("no_bidirectional_feedback_fallback" if feedback_status != "full_feedback" else "none")
        )
    )
    local_independence_certificate = _build_local_independence_certificate(
        feedback_status=feedback_status,
        time_grid=time_grid,
        warnings=warnings,
        a_to_y_present=a_to_y_present,
        y_to_a_present=y_to_a_present,
        p_to_y_present=p_to_y_present,
        p_to_a_present=p_to_a_present,
        x_to_y_present=x_to_y_present,
        x_to_a_present=x_to_a_present,
    )
    temporal_certificate = _build_temporal_identification_certificate(warnings)
    temporal_graph_certificate = build_temporal_graph_causal_certificate(
        temporal_identification_certificate=temporal_certificate,
        local_independence_certificate=local_independence_certificate,
        warnings=warnings,
        metadata={"method_id": _METHOD_ID, "track": _TRACK_ID},
    )
    artifact_store = resolve_artifact_store({}, params)
    temporal_graph_certificate_ref = (
        persist_temporal_graph_causal_certificate(
            artifact_store,
            temporal_graph_certificate,
        )
        if artifact_store is not None
        else None
    )
    return DynamicGraphDSCMResult(
        processes=_process_declarations(
            directed=bool(dynamic_data.directed),
            outcome_family=str(params.get("outcome_family", "continuous")),
        ),
        feedback_status=feedback_status,
        local_dependence_graph=local_dependence_graph,
        interventions=_intervention_api(intervention),
        estimator_api=_estimator_api(params=params, data_source=data_source),
        mechanism_estimates={
            "edge_model": {
                "family": (
                    "relational_event_linear_hazard_proxy"
                    if data_source == "event_log"
                    else "panel_transition_linear_probability"
                ),
                "formation": {
                    key: value
                    for key, value in formation.items()
                    if key not in {"fitted"}
                },
                "dissolution": {
                    key: value
                    for key, value in dissolution.items()
                    if key not in {"fitted"}
                },
            },
            "outcome_model": {
                "family": "continuous_drift_linear_proxy",
                **{key: value for key, value in outcome_model.items() if key not in {"fitted"}},
            },
            "policy_model": {
                "family": "observed_or_zero_policy_process",
                "observational_policy_estimated": bool(np.any(np.abs(policy) > _EPS)),
            },
        },
        causal_effect_curves=curves,
        loop_effect=loop_effect_value,
        uncertainty_intervals=uncertainty_intervals,
        diagnostics=diagnostics,
        fallback_used=fallback_used,
        identification_warnings=warnings,
        local_independence_certificate=local_independence_certificate,
        temporal_identification_certificate=temporal_certificate,
        temporal_graph_causal_certificate=temporal_graph_certificate,
        temporal_graph_causal_certificate_ref=temporal_graph_certificate_ref,
        metadata={
            "time_grid": [float(item) for item in time_grid.tolist()],
            "n_units": int(edges.shape[1]),
            "n_periods": int(edges.shape[0]),
            "intervention": intervention,
            "fallback_reason": fallback_reason,
        },
    )


@foundry_method(
    namespace="causal.dynamic_graph",
    version="1.0.0",
    tags={
        "causal",
        "network",
        "time-series",
        "structural",
        "estimation",
        "diagnostics",
        "dynamic-graph",
        "dscm",
    },
)
class DynamicGraphDSCM:
    """Dynamic graph DSCM estimator for outcome-structure feedback."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "pydantic")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="dscm",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="dynamic_graph_data",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("contract", "json"),
                    contract_id=DynamicGraphDSCMData.contract_id,
                    description="Event-log or panel dynamic graph history for DG-DSCM.",
                )
            }
        ),
        output_slots=_dynamic_graph_output_slots(),
        parameters=(
            ParameterSpec(
                name="alpha",
                default=0.05,
                bounds=(0.0, 1.0),
                description="Directional local-dependence test level.",
            ),
            ParameterSpec(
                name="min_effect_size",
                default=1.0e-8,
                bounds=(0.0, None),
                description="Smallest absolute coefficient considered a present mechanism.",
            ),
            ParameterSpec(
                name="simulation_replicates",
                default=1000,
                bounds=(1, 100000),
                description="Declared simulation replicate budget for downstream stochastic runs.",
            ),
            ParameterSpec(
                name="intervention",
                default={},
                description=(
                    "Optional stochastic intervention with formation_multiplier, "
                    "dissolution_multiplier, outcome_shift, or policy_shift."
                ),
            ),
            ParameterSpec(
                name="edge_model_family",
                default="auto",
                description="Declared edge model family: relational_event, poisson_quadrature, cox, or panel_transition.",
            ),
            ParameterSpec(
                name="outcome_model_family",
                default="sde_drift",
                description="Declared outcome model family: sde_drift, counting_intensity, survival, or panel_transition.",
            ),
            ParameterSpec(
                name="causal_effect_method",
                default="g_computation",
                description="Causal effect engine: g_computation, likelihood_ratio_weighting, or doubly_robust_panel_fallback.",
            ),
            ParameterSpec(
                name="history",
                default="user_defined",
                description="Adjustment history mode: user_defined or learned_state.",
            ),
            ParameterSpec(
                name="latent_actor_effects",
                default=False,
                description="Declare whether actor latent effects are included in sensitivity modeling.",
            ),
            ParameterSpec(
                name="block_when_unobserved_homophily",
                default=False,
                description="Return unidentified when input metadata declares unobserved homophily.",
            ),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Dynamic Graph Dynamic Structural Causal Model. Fits separate local "
            "mechanisms for edge formation, edge dissolution, and node outcomes; "
            "tests A(t-) to Y(t) and Y(t-) to A(t); simulates stochastic "
            "counterfactuals by replacing local characteristics."
        ),
        tags=frozenset(
            {
                "causal",
                "network",
                "time-series",
                "structural",
                "estimation",
                "diagnostics",
                "dynamic-graph",
                "dscm",
            }
        ),
        citations=(
            "Boeken & Mooij (2024). Dynamic Structural Causal Models.",
            "Didelez (2008). Graphical models for marked point processes based on local independence.",
            "Mogensen & Hansen (continuous-time local independence and intervention weighting).",
            "Hudgens & Halloran (2008). Toward causal inference with interference.",
            "Krivitsky & Handcock (2014). A separable model for dynamic networks.",
        ),
        equations={
            "edge_formation": "lambda^+_ij(t) = (1 - A_ij(t-)) exp(mu + theta S_ij(t-) + beta_YA Phi_ij(t-))",
            "edge_dissolution": "lambda^-_ij(t) = A_ij(t-) exp(mu + theta S_ij(t-) + beta_YA Phi_ij(t-))",
            "outcome_drift": "dY_i(t) = b_i(t,F_{t-}) dt + sigma_i(t,F_{t-}) dB_i(t) + dJ_i(t)",
            "feedback": "feedback exists when beta_A_to_Y != 0 and beta_Y_to_A != 0",
        },
        assumptions={
            "complete_ordered_history": (
                "Edge, outcome, policy, covariate, and observation histories are ordered, "
                "or panel fallback semantics are explicitly disclosed."
            ),
            "causal_validity_modularity": (
                "Replacing an edge, outcome, or policy local mechanism changes other "
                "mechanisms only through their inputs."
            ),
            "continuous_time_exchangeability": (
                "No unobserved process jointly drives future edge and outcome changes "
                "after conditioning on the observed filtration."
            ),
            "positivity": "Evaluated intervention trajectories have support or absolute continuity.",
            "sufficient_history": "Predictable features use only F_{t-} history.",
            "faithfulness": "Feedback discovery assumes no exact cancellation of local dependence.",
        },
        identifiable_target={
            "method_id": _METHOD_ID,
            "track": _TRACK_ID,
            "estimands": (
                "structure_to_outcome_effect",
                "outcome_to_structure_effect",
                "dynamic_feedback_loop_effect",
                "policy_effect_under_stochastic_graph_intervention",
            ),
        },
        coverage_contract={
            "supports": {
                "graph_process": True,
                "node_outcome_process": True,
                "edge_formation_dissolution": True,
                "continuous_time": True,
                "panel_fallback": True,
                "stochastic_interventions": True,
            },
            "outputs": (
                "processes",
                "local_dependence_graph",
                "feedback_status",
                "interventions",
                "estimator_api",
                "mechanism_estimates",
                "causal_effect_curves",
                "loop_effect",
                "uncertainty_intervals",
                "diagnostics",
                "identification_warnings",
            ),
        },
        diagnostic_contract={
            "feedback_tests": True,
            "martingale_residuals": True,
            "positivity": True,
            "time_aggregation_sensitivity": True,
            "latent_homophily_sensitivity": True,
        },
        when_to_use=(
            "Use when node outcomes and network ties co-evolve, policies may alter ties "
            "or outcomes, and a fixed exposure mapping is not credible."
        ),
        when_not_to_use=(
            "Do not treat estimates as identified when unobserved homophily, coarse panels, "
            "partial graph observation, or instantaneous reflection cannot be ruled out."
        ),
        typical_min_obs=100,
        output_interpretation=(
            "feedback_status reports whether A_to_Y, Y_to_A, both, neither, or an "
            "unidentified case is supported. loop_effect is only populated for full feedback."
        ),
    )

    @staticmethod
    def pure_step(
        state: DynamicGraphDSCMData | Mapping[str, Any],
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        result = estimate_dynamic_graph_dscm(state, params)
        return {"result": result}

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> DynamicGraphDSCMData:
        if isinstance(fallback_state, DynamicGraphDSCMData):
            return fallback_state
        payload: dict[str, Any] = {}
        if isinstance(fallback_state, Mapping):
            payload.update(dict(fallback_state))
        payload.update({key: value for key, value in bound_inputs.items()})
        if "dynamic_graph_data" in payload and len(payload) == 1:
            return _extract_dynamic_graph_data(payload["dynamic_graph_data"])
        return DynamicGraphDSCMData.model_validate(payload)


__all__ = [
    "DynamicGraphDSCM",
    "DynamicGraphDSCMData",
    "DynamicGraphDSCMResult",
    "DynamicGraphEvent",
    "LocalDependenceEdgeResult",
    "estimate_dynamic_graph_dscm",
]
