"""Space-time DSCM contracts and finite-element SPDE g-computation.

This module implements the first narrow Track 3.4 extension for controlled
diffusion-reaction systems: field-valued nodes, operator edges, space-time
interventions, an identification certificate, and a NumPy finite-element
g-computation estimator for one-dimensional meshes.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from enum import StrEnum
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
from polisyos.foundry.methods.catalog.causal._common import (
    build_failure_report,
    build_success_report,
    wrap_causal_output,
)
from polisyos.ir.analytics.causal import CausalMethod, EstimationStatus
from polisyos.ir.analytics.phase4_dynamics import (
    SpaceTimeCausalCertificate,
    build_space_time_causal_certificate,
    persist_space_time_causal_certificate,
)
from polisyos.ir.refs import SpaceTimeCausalCertificateRef


class SpaceTimePathSpace(StrEnum):
    """Supported field-path semantics for ST-DSCM nodes."""

    CADLAG_L2 = "D([0,T],L2(Omega))"
    CONTINUOUS_L2 = "C([0,T],L2(Omega))"


class SPDEGenerator(StrEnum):
    """Supported structural generator families for the first ST-DSCM lane."""

    DIFFUSION = "diffusion"
    ADVECTION_DIFFUSION = "advection_diffusion"
    DIFFUSION_REACTION = "diffusion_reaction"
    TREATMENT_ASSIGNMENT = "treatment_assignment"


class SpaceTimeInterventionType(StrEnum):
    """Policy intervention families supported by the ST-DSCM contract."""

    PERFECT_FIELD = "perfect_field"
    DYNAMIC_POLICY = "dynamic_policy"
    STOCHASTIC_POLICY = "stochastic_policy"
    SOFT_MECHANISM = "soft_mechanism"
    FORCING = "forcing"


class SpaceTimeIdentificationStatus(StrEnum):
    """Identification/runtime status for controlled diffusion-reaction queries."""

    IDENTIFIED_G_COMPUTATION = "identified_g_computation"
    IDENTIFIED_IPW = "identified_ipw"
    MODEL_EXTRAPOLATION = "model_extrapolation"
    BLOCKED = "blocked"


class SpaceTimeMeshSpec(BaseModel):
    """Finite-element mesh metadata for a space-time domain."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: Literal["finite_element"] = "finite_element"
    basis: Literal["piecewise_linear"] = "piecewise_linear"
    max_edge: float | None = Field(default=None, gt=0.0)
    n_nodes: int | None = Field(default=None, ge=3)


class SpaceTimeDomain(BaseModel):
    """Space-time domain for field-valued DSCM nodes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    geometry: str | None = None
    crs: str = Field(default="cartesian", min_length=1)
    time_start: float = 0.0
    time_end: float = Field(gt=0.0)
    time_unit: str = Field(default="unit", min_length=1)
    boundary: dict[str, Literal["neumann", "dirichlet", "periodic"]] = Field(default_factory=dict)
    mesh: SpaceTimeMeshSpec = Field(default_factory=SpaceTimeMeshSpec)

    @model_validator(mode="after")
    def _validate_time_horizon(self) -> SpaceTimeDomain:
        if self.time_end <= self.time_start:
            raise ValueError("time_end must be greater than time_start")
        return self


class OperatorEdge(BaseModel):
    """Operator-valued causal edge between field nodes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    operator: str = Field(min_length=1)
    edge_type: Literal["operator"] = "operator"
    delayed: bool = False
    kernel_ref: str | None = None
    attenuation_threshold: float | None = Field(default=None, ge=0.0)


class SPDEMechanism(BaseModel):
    """Structural mechanism for a field node."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["SPDE", "treatment_assignment"] = "SPDE"
    generator: SPDEGenerator
    reaction: str | None = None
    noise: str = Field(default="projected_white", min_length=1)
    parents: tuple[str, ...] = ()
    operators: tuple[OperatorEdge, ...] = ()
    measurement_model: str | None = None


class FieldNode(BaseModel):
    """DSCM node whose values are whole spatial field paths."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    path_space: SpaceTimePathSpace = SpaceTimePathSpace.CADLAG_L2
    mechanism: SPDEMechanism


class SpaceTimeSupport(BaseModel):
    """Region-time support for an intervention or split."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    region: str | None = None
    region_bounds: tuple[float, float] | None = None
    interval: tuple[float, float]

    @model_validator(mode="after")
    def _validate_support(self) -> SpaceTimeSupport:
        start, end = self.interval
        if end < start:
            raise ValueError("support interval end must be >= start")
        if self.region_bounds is not None:
            left, right = self.region_bounds
            if right < left:
                raise ValueError("region_bounds right must be >= left")
        return self


class SpaceTimeIntervention(BaseModel):
    """Intervention object for field-valued DSCMs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    type: SpaceTimeInterventionType
    target: str = Field(min_length=1)
    support: SpaceTimeSupport | None = None
    value: float | None = None
    policy_ref: str | None = None
    mechanism_replacement: str | None = None


class SpaceTimeSplit(BaseModel):
    """Projection of a field trajectory onto a region-time block."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node: str = Field(min_length=1)
    support: SpaceTimeSupport

    @property
    def projection_key(self) -> str:
        region = self.support.region or str(self.support.region_bounds)
        return f"P[{self.node};{region};{self.support.interval}]"


class SpaceTimeIdentificationCertificate(BaseModel):
    """Sufficient-condition certificate for ST-DSCM identification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    theorem_family: Literal["controlled_diffusion_reaction_st_dscm_v1"] = (
        "controlled_diffusion_reaction_st_dscm_v1"
    )
    status: SpaceTimeIdentificationStatus
    adjustment_fields: tuple[str, ...] = ()
    assumptions: dict[str, Literal["pass", "fail", "not_applicable"]]
    g_computation_allowed: bool
    ipw_allowed: bool
    stochastic_policy_absolutely_continuous: bool
    path_space_support: Literal[
        "on_support",
        "deterministic_singular_for_ipw",
        "model_extrapolation",
        "blocked",
    ]
    caveats: tuple[str, ...] = ()

    @property
    def identified(self) -> bool:
        return self.status is not SpaceTimeIdentificationStatus.BLOCKED

    @model_validator(mode="after")
    def _validate_certificate(self) -> SpaceTimeIdentificationCertificate:
        if self.ipw_allowed and not self.stochastic_policy_absolutely_continuous:
            raise ValueError("ipw_allowed requires stochastic_policy_absolutely_continuous")
        if self.status is SpaceTimeIdentificationStatus.IDENTIFIED_IPW and not self.ipw_allowed:
            raise ValueError("IDENTIFIED_IPW requires ipw_allowed")
        if self.status is SpaceTimeIdentificationStatus.BLOCKED and self.identified:
            raise ValueError("blocked certificates cannot be identified")
        return self


class SPDEEstimatorSpec(BaseModel):
    """Runtime configuration for the FEM SPDE g-computation estimator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["fem_spde_g_computation"] = "fem_spde_g_computation"
    fit: Literal["least_squares", "known_coefficients"] = "least_squares"
    solver: Literal["implicit_euler", "explicit_euler"] = "implicit_euler"
    simulations: int = Field(default=0, ge=0)
    mesh_sensitivity: bool = False
    timestep_sensitivity: bool = False


class SpaceTimeDSCM(BaseModel):
    """Minimal ST-DSCM model spec for controlled diffusion-reaction systems."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: SpaceTimeDomain
    nodes: tuple[FieldNode, ...]
    operator_edges: tuple[OperatorEdge, ...] = ()
    interventions: tuple[SpaceTimeIntervention, ...] = ()
    estimator: SPDEEstimatorSpec = Field(default_factory=SPDEEstimatorSpec)

    @model_validator(mode="after")
    def _validate_graph_references(self) -> SpaceTimeDSCM:
        node_ids = {node.id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("field node ids must be unique")
        for edge in self.operator_edges:
            if edge.source not in node_ids or edge.target not in node_ids:
                raise ValueError("operator_edges must reference declared nodes")
        for intervention in self.interventions:
            if intervention.target not in node_ids:
                raise ValueError("interventions must target declared nodes")
        return self


class SpaceTimeFieldData(BaseModel):
    """Observed or simulated fields on a regular time by one-dimensional space grid."""

    contract_id: ClassVar[str] = "foundry.causal.space_time_field_data.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    outcome_field: Any
    treatment_field: Any
    time_grid: Any
    space_grid: Any
    confounder_field: Any | None = None
    baseline_treatment_field: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "outcome_field",
        "treatment_field",
        "confounder_field",
        "baseline_treatment_field",
        mode="before",
    )
    @classmethod
    def _coerce_field(cls, value: Any) -> Any:
        if value is None:
            return None
        array = np.asarray(value, dtype=float)
        if array.ndim != 2:
            raise ValueError("field arrays must have shape (n_times, n_space)")
        if not np.isfinite(array).all():
            raise ValueError("field arrays must contain only finite values")
        return array

    @field_validator("time_grid", "space_grid", mode="before")
    @classmethod
    def _coerce_grid(cls, value: Any) -> Any:
        array = np.asarray(value, dtype=float).reshape(-1)
        if array.ndim != 1:
            raise ValueError("grids must be one-dimensional")
        if array.shape[0] < 2:
            raise ValueError("grids must contain at least two points")
        if not np.isfinite(array).all():
            raise ValueError("grids must contain only finite values")
        if not np.all(np.diff(array) > 0.0):
            raise ValueError("grids must be strictly increasing")
        return array

    @model_validator(mode="after")
    def _validate_shapes(self) -> SpaceTimeFieldData:
        expected = (self.time_grid.shape[0], self.space_grid.shape[0])
        if self.space_grid.shape[0] < 3:
            raise ValueError("space_grid must contain at least three nodes for FEM diffusion")
        for field_name in (
            "outcome_field",
            "treatment_field",
            "confounder_field",
            "baseline_treatment_field",
        ):
            value = getattr(self, field_name)
            if value is not None and value.shape != expected:
                raise ValueError(f"{field_name} shape {value.shape} does not match {expected}")
        return self

    @field_serializer(
        "outcome_field",
        "treatment_field",
        "time_grid",
        "space_grid",
        "confounder_field",
        "baseline_treatment_field",
        mode="plain",
        when_used="json",
    )
    def _serialize_numpy(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @property
    def n_times(self) -> int:
        return int(self.time_grid.shape[0])

    @property
    def n_space(self) -> int:
        return int(self.space_grid.shape[0])

    @property
    def sample_size(self) -> int:
        return int(self.n_times * self.n_space)


class FittedSPDEParameters(BaseModel):
    """Linear diffusion-response coefficients used by the estimator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kappa: float = Field(ge=0.0)
    treatment_effect: float
    confounder_effect: float = 0.0
    intercept: float = 0.0
    reaction_rate: float = 0.0
    carrying_capacity: float = Field(default=1.0, gt=0.0)
    residual_scale: float = Field(default=0.0, ge=0.0)
    fit_source: Literal["least_squares", "known_coefficients", "hybrid"] = "least_squares"


class SpaceTimeSPDEGComputationResult(BaseModel):
    """Estimator output payload for space-time policy effects."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    policy_effect_region_time_average: float
    fitted_coefficients: FittedSPDEParameters
    identification_certificate: SpaceTimeIdentificationCertificate
    space_time_causal_certificate: SpaceTimeCausalCertificate
    space_time_causal_certificate_ref: SpaceTimeCausalCertificateRef | None = None
    positivity_report: dict[str, Any]
    green_kernel_summary: dict[str, Any]
    spillover_impulse_response: dict[str, list[float]]
    effect_surface: list[list[float]]
    baseline_surface: list[list[float]]
    policy_surface: list[list[float]]
    ipw_result: dict[str, Any] | None = None
    doubly_robust_estimate: float | None = None
    convergence_diagnostics: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


def _space_time_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec("report", SlotType.SCALAR, Unit("report", "json")),
            SlotSpec("envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
            SlotSpec("warnings", SlotType.SCALAR, Unit("warning", "list")),
            SlotSpec("result", SlotType.SCALAR, Unit("result", "json")),
            SlotSpec("spde_estimator", SlotType.SCALAR, Unit("result", "json")),
            SlotSpec("identification_certificate", SlotType.SCALAR, Unit("certificate", "json")),
            SlotSpec("positivity_report", SlotType.SCALAR, Unit("diagnostic", "json")),
            SlotSpec("effect_surface", SlotType.MATRIX, Unit("effect", "value")),
            SlotSpec("spillover_impulse_response", SlotType.SCALAR, Unit("effect", "json")),
            SlotSpec("green_kernel_summary", SlotType.SCALAR, Unit("kernel", "json")),
            SlotSpec("convergence_diagnostics", SlotType.SCALAR, Unit("diagnostic", "json")),
            SlotSpec("ipw_result", SlotType.SCALAR, Unit("result", "json")),
        }
    )


def build_piecewise_linear_fem_matrices(space_grid: Any) -> tuple[np.ndarray, np.ndarray]:
    """Build 1D piecewise-linear FEM mass and stiffness matrices."""

    x = np.asarray(space_grid, dtype=float).reshape(-1)
    if x.ndim != 1 or x.shape[0] < 3:
        raise ValueError("space_grid must be one-dimensional with at least three nodes")
    if not np.all(np.diff(x) > 0.0):
        raise ValueError("space_grid must be strictly increasing")

    n = x.shape[0]
    mass = np.zeros((n, n), dtype=float)
    stiffness = np.zeros((n, n), dtype=float)
    for index, h in enumerate(np.diff(x)):
        local_mass = (h / 6.0) * np.array([[2.0, 1.0], [1.0, 2.0]], dtype=float)
        local_stiffness = (1.0 / h) * np.array([[1.0, -1.0], [-1.0, 1.0]], dtype=float)
        slc = np.ix_([index, index + 1], [index, index + 1])
        mass[slc] += local_mass
        stiffness[slc] += local_stiffness
    return mass, stiffness


def _space_quadrature_weights(space_grid: np.ndarray) -> np.ndarray:
    weights = np.empty(space_grid.shape[0], dtype=float)
    weights[0] = 0.5 * (space_grid[1] - space_grid[0])
    weights[-1] = 0.5 * (space_grid[-1] - space_grid[-2])
    if space_grid.shape[0] > 2:
        weights[1:-1] = 0.5 * (space_grid[2:] - space_grid[:-2])
    return weights


def _projected_laplacian(field: np.ndarray, mass: np.ndarray, stiffness: np.ndarray) -> np.ndarray:
    """Return the FEM projection of the spatial Laplacian for each time row."""

    projected = np.empty_like(field, dtype=float)
    for index, row in enumerate(field):
        projected[index] = np.linalg.solve(mass, -(stiffness @ row))
    return projected


def _as_field_like(value: Any, *, shape: tuple[int, int], name: str) -> np.ndarray:
    if value is None:
        raise ValueError(f"{name} is required")
    array = np.asarray(value, dtype=float)
    if array.ndim == 0:
        array = np.full(shape, float(array), dtype=float)
    if array.ndim == 1:
        if array.shape[0] == shape[0]:
            array = np.repeat(array[:, None], shape[1], axis=1)
        elif array.shape[0] == shape[1]:
            array = np.repeat(array[None, :], shape[0], axis=0)
    if array.shape != shape:
        raise ValueError(f"{name} shape {array.shape} does not match {shape}")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _mask_from_bounds(grid: np.ndarray, bounds: Any | None) -> np.ndarray:
    if bounds is None:
        return np.ones(grid.shape[0], dtype=bool)
    if isinstance(bounds, np.ndarray) and bounds.dtype == bool:
        if bounds.shape[0] != grid.shape[0]:
            raise ValueError("boolean mask length does not match grid")
        return bounds
    if isinstance(bounds, (list, tuple)) and len(bounds) == grid.shape[0]:
        mask = np.asarray(bounds)
        if mask.dtype == bool:
            return mask
    left, right = tuple(float(item) for item in bounds)
    if right < left:
        raise ValueError("bounds upper endpoint must be >= lower endpoint")
    return (grid >= left) & (grid <= right)


def _time_mask_from_window(time_grid: np.ndarray, window: Any | None) -> np.ndarray:
    if window is None:
        return np.ones(time_grid.shape[0], dtype=bool)
    start, end = tuple(float(item) for item in window)
    if end < start:
        raise ValueError("time_window end must be >= start")
    return (time_grid >= start) & (time_grid <= end)


def _region_time_average(
    field: np.ndarray,
    *,
    time_grid: np.ndarray,
    space_grid: np.ndarray,
    region_mask: np.ndarray,
    time_mask: np.ndarray,
) -> float:
    sub = np.asarray(field, dtype=float)[np.ix_(time_mask, region_mask)]
    times = time_grid[time_mask]
    spaces = space_grid[region_mask]
    if sub.size == 0:
        raise ValueError("region-time functional selected no cells")
    if times.shape[0] < 2 or spaces.shape[0] < 2:
        return float(np.mean(sub))
    space_integral = np.trapezoid(sub, spaces, axis=1)
    total_integral = float(np.trapezoid(space_integral, times))
    measure = float((times[-1] - times[0]) * (spaces[-1] - spaces[0]))
    if measure <= 0.0:
        return float(np.mean(sub))
    return total_integral / measure


def _fit_linear_diffusion_response(
    data: SpaceTimeFieldData,
    *,
    mass: np.ndarray,
    stiffness: np.ndarray,
    params: Mapping[str, Any],
) -> FittedSPDEParameters:
    coefficients = (
        dict(params.get("coefficients", {}))
        if isinstance(params.get("coefficients"), Mapping)
        else {}
    )
    has_known = any(
        key in coefficients
        for key in (
            "kappa",
            "treatment_effect",
            "confounder_effect",
            "intercept",
            "reaction_rate",
            "carrying_capacity",
        )
    )
    carrying_capacity = float(
        coefficients.get("carrying_capacity", params.get("carrying_capacity", 1.0))
    )
    fit_reaction = bool(params.get("fit_reaction", False))

    y = np.asarray(data.outcome_field, dtype=float)
    a = np.asarray(data.treatment_field, dtype=float)
    l = (
        np.zeros_like(y)
        if data.confounder_field is None
        else np.asarray(data.confounder_field, dtype=float)
    )
    dt = np.diff(np.asarray(data.time_grid, dtype=float))
    dy_dt = (y[1:] - y[:-1]) / dt[:, None]
    laplacian = _projected_laplacian(y[:-1], mass, stiffness)

    columns = [laplacian.reshape(-1), a[:-1].reshape(-1), l[:-1].reshape(-1), np.ones(dy_dt.size)]
    if fit_reaction:
        reaction_basis = y[:-1] * (1.0 - y[:-1] / carrying_capacity)
        columns.append(reaction_basis.reshape(-1))
    design = np.column_stack(columns)
    target = dy_dt.reshape(-1)
    solved, *_ = np.linalg.lstsq(design, target, rcond=None)

    fitted = {
        "kappa": max(float(solved[0]), 0.0),
        "treatment_effect": float(solved[1]),
        "confounder_effect": float(solved[2]),
        "intercept": float(solved[3]),
        "reaction_rate": float(solved[4]) if fit_reaction else 0.0,
        "carrying_capacity": carrying_capacity,
    }
    merged = {
        **fitted,
        **{key: float(value) for key, value in coefficients.items() if key in fitted},
    }

    prediction = design @ np.array(
        [
            merged["kappa"],
            merged["treatment_effect"],
            merged["confounder_effect"],
            merged["intercept"],
            *([merged["reaction_rate"]] if fit_reaction else []),
        ],
        dtype=float,
    )
    residual_scale = float(np.std(target - prediction)) if target.size > design.shape[1] else 0.0
    fit_source: Literal["least_squares", "known_coefficients", "hybrid"]
    if not has_known:
        fit_source = "least_squares"
    elif len(coefficients) >= 4:
        fit_source = "known_coefficients"
    else:
        fit_source = "hybrid"
    return FittedSPDEParameters(
        kappa=merged["kappa"],
        treatment_effect=merged["treatment_effect"],
        confounder_effect=merged["confounder_effect"],
        intercept=merged["intercept"],
        reaction_rate=merged["reaction_rate"],
        carrying_capacity=merged["carrying_capacity"],
        residual_scale=residual_scale,
        fit_source=fit_source,
    )


def simulate_linear_diffusion_response(
    *,
    time_grid: Any,
    space_grid: Any,
    treatment_field: Any,
    confounder_field: Any | None = None,
    initial_field: Any | None = None,
    kappa: float = 0.05,
    treatment_effect: float = 1.0,
    confounder_effect: float = 0.0,
    intercept: float = 0.0,
    reaction_rate: float = 0.0,
    carrying_capacity: float = 1.0,
    solver: Literal["implicit_euler", "explicit_euler"] = "implicit_euler",
) -> np.ndarray:
    """Simulate the mean field of a controlled diffusion-reaction SPDE."""

    t = np.asarray(time_grid, dtype=float).reshape(-1)
    x = np.asarray(space_grid, dtype=float).reshape(-1)
    shape = (t.shape[0], x.shape[0])
    treatment = _as_field_like(treatment_field, shape=shape, name="treatment_field")
    confounder = (
        np.zeros(shape, dtype=float)
        if confounder_field is None
        else _as_field_like(confounder_field, shape=shape, name="confounder_field")
    )
    initial = (
        np.zeros(x.shape[0], dtype=float)
        if initial_field is None
        else np.asarray(initial_field, dtype=float).reshape(-1)
    )
    if initial.shape[0] != x.shape[0]:
        raise ValueError("initial_field length must match space_grid")

    mass, stiffness = build_piecewise_linear_fem_matrices(x)
    path = np.empty(shape, dtype=float)
    path[0] = initial
    for index, step in enumerate(np.diff(t), start=1):
        previous = path[index - 1]
        force = (
            treatment_effect * treatment[index - 1]
            + confounder_effect * confounder[index - 1]
            + intercept
        )
        if reaction_rate:
            force = force + reaction_rate * previous * (1.0 - previous / carrying_capacity)
        if solver == "explicit_euler":
            laplacian = np.linalg.solve(mass, -(stiffness @ previous))
            path[index] = previous + step * (kappa * laplacian + force)
        else:
            lhs = mass + step * kappa * stiffness
            rhs = mass @ previous + step * (mass @ force)
            path[index] = np.linalg.solve(lhs, rhs)
    return path


def simulate_reaction_diffusion_response(
    *,
    time_grid: Any,
    space_grid: Any,
    treatment_field: Any,
    confounder_field: Any | None = None,
    initial_field: Any | None = None,
    kappa: float = 0.05,
    treatment_effect: float = 1.0,
    confounder_effect: float = 0.0,
    growth_rate: float = 0.2,
    carrying_capacity: float = 1.0,
    intercept: float = 0.0,
    solver: Literal["implicit_euler", "explicit_euler"] = "implicit_euler",
) -> np.ndarray:
    """Simulate a logistic reaction-diffusion response under a treatment field."""

    return simulate_linear_diffusion_response(
        time_grid=time_grid,
        space_grid=space_grid,
        treatment_field=treatment_field,
        confounder_field=confounder_field,
        initial_field=initial_field,
        kappa=kappa,
        treatment_effect=treatment_effect,
        confounder_effect=confounder_effect,
        intercept=intercept,
        reaction_rate=growth_rate,
        carrying_capacity=carrying_capacity,
        solver=solver,
    )


def _materialize_policy_fields(
    data: SpaceTimeFieldData,
    params: Mapping[str, Any],
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    shape = (data.n_times, data.n_space)
    if "baseline_policy_field" in params:
        baseline = _as_field_like(
            params.get("baseline_policy_field"), shape=shape, name="baseline_policy_field"
        )
    elif data.baseline_treatment_field is not None:
        baseline = np.asarray(data.baseline_treatment_field, dtype=float)
    elif bool(params.get("baseline_is_observed", False)):
        baseline = np.asarray(data.treatment_field, dtype=float)
    else:
        baseline = np.zeros(shape, dtype=float)

    if "policy_field" in params:
        policy = _as_field_like(params.get("policy_field"), shape=shape, name="policy_field")
        metadata = {"policy_source": "policy_field"}
        return policy, baseline, metadata

    policy = baseline.copy()
    source_region_mask = _mask_from_bounds(
        np.asarray(data.space_grid, dtype=float),
        params.get("intervention_region_bounds"),
    )
    pulse_interval = params.get("intervention_interval", params.get("pulse_interval"))
    if pulse_interval is None:
        raise ValueError("policy_field or intervention_interval must be provided")
    time_mask = _time_mask_from_window(np.asarray(data.time_grid, dtype=float), pulse_interval)
    value = float(params.get("intervention_value", params.get("pulse_value", 1.0)))
    policy[np.ix_(time_mask, source_region_mask)] = value
    return (
        policy,
        baseline,
        {
            "policy_source": "rectangular_pulse",
            "intervention_value": value,
            "source_region_nodes": int(np.sum(source_region_mask)),
            "intervention_time_points": int(np.sum(time_mask)),
        },
    )


def build_space_time_identification_certificate(
    data: SpaceTimeFieldData,
    policy_field: np.ndarray,
    *,
    params: Mapping[str, Any] | None = None,
) -> SpaceTimeIdentificationCertificate:
    """Build a sufficient-condition certificate for ST-DSCM g-computation."""

    resolved = dict(params or {})
    adjustment_fields = tuple(str(item) for item in resolved.get("adjustment_fields", ()))
    requires_adjustment = bool(adjustment_fields)
    observed_adjustment = not requires_adjustment or data.confounder_field is not None
    stochastic_ac = bool(resolved.get("policy_absolute_continuity", False))
    deterministic_policy = str(resolved.get("policy_mode", "deterministic")) == "deterministic"

    observed_treatment = np.asarray(data.treatment_field, dtype=float)
    obs_min = float(np.min(observed_treatment))
    obs_max = float(np.max(observed_treatment))
    outside_support = (policy_field < obs_min - 1.0e-9) | (policy_field > obs_max + 1.0e-9)
    extrapolation_fraction = float(np.mean(outside_support))

    assumptions: dict[str, Literal["pass", "fail", "not_applicable"]] = {
        "well_posed_mild_solution": "pass",
        "consistency": "pass" if bool(resolved.get("consistency", True)) else "fail",
        "no_anticipation": "pass" if bool(resolved.get("no_anticipation", True)) else "fail",
        "no_information_drift": "pass"
        if bool(resolved.get("no_information_drift", True))
        else "fail",
        "path_space_positivity": "pass"
        if stochastic_ac and extrapolation_fraction == 0.0
        else ("not_applicable" if deterministic_policy else "fail"),
        "adjustment_set_observed": "pass" if observed_adjustment else "fail",
        "measurement_support": "pass" if data.n_times >= 2 and data.n_space >= 3 else "fail",
    }
    caveats: list[str] = []
    if deterministic_policy:
        caveats.append("deterministic_field_interventions_are_singular_for_ipw")
    if extrapolation_fraction > 0.0:
        caveats.append("policy_field_leaves_observed_treatment_range")
    if not observed_adjustment:
        caveats.append("declared_adjustment_fields_missing_from_payload")

    hard_fail = any(
        assumptions[key] == "fail"
        for key in (
            "consistency",
            "no_anticipation",
            "no_information_drift",
            "adjustment_set_observed",
            "measurement_support",
        )
    )
    ipw_allowed = stochastic_ac and extrapolation_fraction == 0.0 and not hard_fail
    g_allowed = not hard_fail
    if hard_fail:
        status = SpaceTimeIdentificationStatus.BLOCKED
        path_support: Literal[
            "on_support",
            "deterministic_singular_for_ipw",
            "model_extrapolation",
            "blocked",
        ] = "blocked"
    elif extrapolation_fraction > 0.0:
        status = SpaceTimeIdentificationStatus.MODEL_EXTRAPOLATION
        path_support = "model_extrapolation"
    elif ipw_allowed:
        status = SpaceTimeIdentificationStatus.IDENTIFIED_IPW
        path_support = "on_support"
    else:
        status = SpaceTimeIdentificationStatus.IDENTIFIED_G_COMPUTATION
        path_support = "deterministic_singular_for_ipw" if deterministic_policy else "on_support"

    return SpaceTimeIdentificationCertificate(
        status=status,
        adjustment_fields=adjustment_fields,
        assumptions=assumptions,
        g_computation_allowed=g_allowed,
        ipw_allowed=ipw_allowed,
        stochastic_policy_absolutely_continuous=stochastic_ac,
        path_space_support=path_support,
        caveats=tuple(caveats),
    )


def _build_positivity_report(
    data: SpaceTimeFieldData,
    policy: np.ndarray,
    baseline: np.ndarray,
    certificate: SpaceTimeIdentificationCertificate,
) -> dict[str, Any]:
    observed = np.asarray(data.treatment_field, dtype=float)
    obs_min = float(np.min(observed))
    obs_max = float(np.max(observed))
    outside_policy = (policy < obs_min - 1.0e-9) | (policy > obs_max + 1.0e-9)
    outside_baseline = (baseline < obs_min - 1.0e-9) | (baseline > obs_max + 1.0e-9)
    overlap_margin = np.minimum(policy - obs_min, obs_max - policy)
    return {
        "observed_treatment_min": obs_min,
        "observed_treatment_max": obs_max,
        "policy_min": float(np.min(policy)),
        "policy_max": float(np.max(policy)),
        "baseline_min": float(np.min(baseline)),
        "baseline_max": float(np.max(baseline)),
        "policy_outside_observed_range_fraction": float(np.mean(outside_policy)),
        "baseline_outside_observed_range_fraction": float(np.mean(outside_baseline)),
        "minimum_policy_overlap_margin": float(np.min(overlap_margin)),
        "support_heatmap": outside_policy.astype(int).tolist(),
        "ipw_allowed": bool(certificate.ipw_allowed),
        "g_computation_allowed": bool(certificate.g_computation_allowed),
        "path_space_support": certificate.path_space_support,
    }


def _as_drift_field(value: Any, *, fallback: np.ndarray, name: str) -> np.ndarray:
    if value is None:
        return fallback
    array = np.asarray(value, dtype=float)
    if array.shape == fallback.shape:
        return array
    if array.shape == (fallback.shape[0] + 1, fallback.shape[1]):
        return array[:-1]
    if array.ndim == 0:
        return np.full_like(fallback, float(array), dtype=float)
    raise ValueError(f"{name} must be scalar, (n_times-1,n_space), or (n_times,n_space)")


def estimate_space_time_treatment_density_process(
    data: SpaceTimeFieldData,
    policy_field: np.ndarray,
    *,
    params: Mapping[str, Any],
    region_mask: np.ndarray,
    time_mask: np.ndarray,
) -> dict[str, Any]:
    """Approximate a continuous-time treatment density process on the FEM grid."""

    sigma = float(params.get("treatment_diffusion_scale", params.get("sigma_A", 1.0)))
    if sigma <= 0.0:
        raise ValueError("treatment_diffusion_scale must be positive for IPW")
    time_grid = np.asarray(data.time_grid, dtype=float)
    space_grid = np.asarray(data.space_grid, dtype=float)
    treatment = np.asarray(data.treatment_field, dtype=float)
    dt = np.diff(time_grid)
    if not np.all(dt > 0.0):
        raise ValueError("time_grid must be strictly increasing for IPW")

    observed_drift = np.diff(treatment, axis=0) / dt[:, None]
    policy_drift_from_field = np.diff(policy_field, axis=0) / dt[:, None]
    factual_drift = _as_drift_field(
        params.get("factual_treatment_drift_field"),
        fallback=observed_drift,
        name="factual_treatment_drift_field",
    )
    policy_drift = _as_drift_field(
        params.get("policy_treatment_drift_field"),
        fallback=policy_drift_from_field,
        name="policy_treatment_drift_field",
    )
    increments = np.diff(treatment, axis=0)
    d_w = (increments - factual_drift * dt[:, None]) / sigma
    h = (policy_drift - factual_drift) / sigma
    spatial_weights = _space_quadrature_weights(space_grid)
    log_terms = np.sum(
        spatial_weights[None, :] * (h * d_w - 0.5 * h * h * dt[:, None]),
        axis=1,
    )
    log_density_process = np.cumsum(log_terms)
    clipped_log_density = np.clip(log_density_process, -50.0, 50.0)
    density_process = np.exp(clipped_log_density)
    observed_functional = _region_time_average(
        np.asarray(data.outcome_field, dtype=float),
        time_grid=time_grid,
        space_grid=space_grid,
        region_mask=region_mask,
        time_mask=time_mask,
    )
    final_density = float(density_process[-1]) if density_process.size else 1.0
    return {
        "status": "computed",
        "semantics": "discrete_girsanov_approximation",
        "estimate": float(final_density * observed_functional),
        "observed_functional": float(observed_functional),
        "final_density": final_density,
        "log_density": float(log_density_process[-1]) if log_density_process.size else 0.0,
        "density_process": [float(value) for value in density_process.tolist()],
        "effective_sample_size": 1.0,
        "diagnostics": {
            "single_path_ipw_is_diagnostic": True,
            "treatment_diffusion_scale": sigma,
            "max_abs_h": float(np.max(np.abs(h))) if h.size else 0.0,
        },
    }


def _outcome_residual_diagnostics(
    data: SpaceTimeFieldData,
    fitted: FittedSPDEParameters,
    *,
    mass: np.ndarray,
    stiffness: np.ndarray,
) -> dict[str, Any]:
    y = np.asarray(data.outcome_field, dtype=float)
    a = np.asarray(data.treatment_field, dtype=float)
    l = (
        np.zeros_like(y)
        if data.confounder_field is None
        else np.asarray(data.confounder_field, dtype=float)
    )
    dt = np.diff(np.asarray(data.time_grid, dtype=float))
    dy_dt = (y[1:] - y[:-1]) / dt[:, None]
    laplacian = _projected_laplacian(y[:-1], mass, stiffness)
    predicted = (
        fitted.kappa * laplacian
        + fitted.treatment_effect * a[:-1]
        + fitted.confounder_effect * l[:-1]
        + fitted.intercept
    )
    if fitted.reaction_rate:
        predicted = predicted + fitted.reaction_rate * y[:-1] * (
            1.0 - y[:-1] / fitted.carrying_capacity
        )
    residual = dy_dt - predicted
    flat = residual.reshape(-1)
    lag1 = 0.0
    if flat.shape[0] > 1 and np.std(flat[:-1]) > 0.0 and np.std(flat[1:]) > 0.0:
        lag1 = float(np.corrcoef(flat[:-1], flat[1:])[0, 1])
    cumulative = np.cumsum(np.mean(residual, axis=1))
    return {
        "outcome_residual_mean": float(np.mean(flat)) if flat.size else 0.0,
        "outcome_residual_std": float(np.std(flat)) if flat.size else 0.0,
        "outcome_residual_lag1_correlation": lag1,
        "max_abs_cumulative_mean_residual": float(np.max(np.abs(cumulative)))
        if cumulative.size
        else 0.0,
        "martingale_residual_proxy": "mean_increment_residual_should_be_near_zero",
    }


def _stride_indices(length: int, *, stride: int, min_points: int) -> np.ndarray:
    if length < min_points:
        return np.arange(length, dtype=int)
    indices = np.arange(0, length, max(int(stride), 1), dtype=int)
    if indices[-1] != length - 1:
        indices = np.append(indices, length - 1)
    if indices.shape[0] < min_points:
        indices = np.unique(np.linspace(0, length - 1, min_points, dtype=int))
    return indices


def _coarsened_policy_effect(
    data: SpaceTimeFieldData,
    *,
    policy: np.ndarray,
    baseline: np.ndarray,
    fitted: FittedSPDEParameters,
    params: Mapping[str, Any],
    solver: Literal["implicit_euler", "explicit_euler"],
    time_stride: int = 1,
    space_stride: int = 1,
) -> float:
    time_indices = _stride_indices(data.n_times, stride=time_stride, min_points=2)
    space_indices = _stride_indices(data.n_space, stride=space_stride, min_points=3)
    time_grid = np.asarray(data.time_grid, dtype=float)[time_indices]
    space_grid = np.asarray(data.space_grid, dtype=float)[space_indices]
    baseline_subset = baseline[np.ix_(time_indices, space_indices)]
    policy_subset = policy[np.ix_(time_indices, space_indices)]
    confounder_subset = (
        None
        if data.confounder_field is None
        else np.asarray(data.confounder_field, dtype=float)[np.ix_(time_indices, space_indices)]
    )
    initial_subset = np.asarray(data.outcome_field, dtype=float)[0, space_indices]
    baseline_surface = simulate_linear_diffusion_response(
        time_grid=time_grid,
        space_grid=space_grid,
        treatment_field=baseline_subset,
        confounder_field=confounder_subset,
        initial_field=initial_subset,
        kappa=fitted.kappa,
        treatment_effect=fitted.treatment_effect,
        confounder_effect=fitted.confounder_effect,
        intercept=fitted.intercept,
        reaction_rate=fitted.reaction_rate,
        carrying_capacity=fitted.carrying_capacity,
        solver=solver,
    )
    policy_surface = simulate_linear_diffusion_response(
        time_grid=time_grid,
        space_grid=space_grid,
        treatment_field=policy_subset,
        confounder_field=confounder_subset,
        initial_field=initial_subset,
        kappa=fitted.kappa,
        treatment_effect=fitted.treatment_effect,
        confounder_effect=fitted.confounder_effect,
        intercept=fitted.intercept,
        reaction_rate=fitted.reaction_rate,
        carrying_capacity=fitted.carrying_capacity,
        solver=solver,
    )
    target_mask = _mask_from_bounds(space_grid, params.get("outcome_region_bounds"))
    time_window = _time_mask_from_window(time_grid, params.get("time_window"))
    return _region_time_average(
        policy_surface - baseline_surface,
        time_grid=time_grid,
        space_grid=space_grid,
        region_mask=target_mask,
        time_mask=time_window,
    )


def _effect_convergence_diagnostics(
    data: SpaceTimeFieldData,
    *,
    policy: np.ndarray,
    baseline: np.ndarray,
    fitted: FittedSPDEParameters,
    params: Mapping[str, Any],
    solver: Literal["implicit_euler", "explicit_euler"],
    full_effect: float,
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {
        "full_effect": float(full_effect),
        "full_mesh_nodes": int(data.n_space),
        "full_time_points": int(data.n_times),
        "checks": {},
    }
    checks: dict[str, Any] = {}
    if data.n_space >= 5:
        mesh_effect = _coarsened_policy_effect(
            data,
            policy=policy,
            baseline=baseline,
            fitted=fitted,
            params=params,
            solver=solver,
            space_stride=2,
        )
        checks["mesh_stride_2"] = {
            "effect": mesh_effect,
            "absolute_difference_from_full": float(abs(mesh_effect - full_effect)),
            "mesh_nodes": int(_stride_indices(data.n_space, stride=2, min_points=3).shape[0]),
        }
    else:
        checks["mesh_stride_2"] = {"status": "not_enough_space_nodes"}
    if data.n_times >= 4:
        timestep_effect = _coarsened_policy_effect(
            data,
            policy=policy,
            baseline=baseline,
            fitted=fitted,
            params=params,
            solver=solver,
            time_stride=2,
        )
        checks["time_stride_2"] = {
            "effect": timestep_effect,
            "absolute_difference_from_full": float(abs(timestep_effect - full_effect)),
            "time_points": int(_stride_indices(data.n_times, stride=2, min_points=2).shape[0]),
        }
    else:
        checks["time_stride_2"] = {"status": "not_enough_time_points"}
    both_available = data.n_space >= 5 and data.n_times >= 4
    if both_available:
        joint_effect = _coarsened_policy_effect(
            data,
            policy=policy,
            baseline=baseline,
            fitted=fitted,
            params=params,
            solver=solver,
            time_stride=2,
            space_stride=2,
        )
        checks["mesh_and_time_stride_2"] = {
            "effect": joint_effect,
            "absolute_difference_from_full": float(abs(joint_effect - full_effect)),
        }
    diagnostics["checks"] = checks
    diagnostics["interpretation"] = (
        "Mesh and time-step sensitivity are finite-grid reruns of the same controlled SPDE "
        "functional; small differences support, but do not prove, continuum stability."
    )
    return diagnostics


def _spillover_impulse_response(
    effect_surface: np.ndarray,
    *,
    time_grid: np.ndarray,
    source_time: float,
    target_mask: np.ndarray,
    lags: tuple[float, ...],
) -> dict[str, list[float]]:
    values: list[float] = []
    materialized_lags: list[float] = []
    for lag in lags:
        target_time = source_time + float(lag)
        if target_time < time_grid[0] or target_time > time_grid[-1]:
            continue
        idx = int(np.argmin(np.abs(time_grid - target_time)))
        values.append(float(np.mean(effect_surface[idx, target_mask])))
        materialized_lags.append(float(time_grid[idx] - source_time))
    return {"lags": materialized_lags, "values": values}


def _green_kernel_summary(
    effect_surface: np.ndarray,
    *,
    time_grid: np.ndarray,
    space_grid: np.ndarray,
    source_mask: np.ndarray,
    target_mask: np.ndarray,
    intervention_time_mask: np.ndarray,
    treatment_effect: float,
) -> dict[str, Any]:
    if not np.any(intervention_time_mask) or not np.any(source_mask) or not np.any(target_mask):
        return {
            "kernel_family": "finite_element_diffusion_response",
            "status": "empty_support",
            "max_abs_effect": 0.0,
        }
    first_time = float(time_grid[np.where(intervention_time_mask)[0][0]])
    peak_index = int(np.argmax(np.max(np.abs(effect_surface[:, target_mask]), axis=1)))
    source_width = (
        float(space_grid[source_mask][-1] - space_grid[source_mask][0])
        if np.sum(source_mask) > 1
        else 0.0
    )
    target_width = (
        float(space_grid[target_mask][-1] - space_grid[target_mask][0])
        if np.sum(target_mask) > 1
        else 0.0
    )
    return {
        "kernel_family": "finite_element_diffusion_response",
        "semantics": "operator_support_not_binary_adjacency",
        "source_width": source_width,
        "target_width": target_width,
        "first_intervention_time": first_time,
        "peak_target_time": float(time_grid[peak_index]),
        "peak_target_mean_effect": float(np.mean(effect_surface[peak_index, target_mask])),
        "max_abs_effect": float(np.max(np.abs(effect_surface[:, target_mask]))),
        "treatment_effect_coefficient": float(treatment_effect),
    }


def estimate_space_time_spde_g_computation(
    data: SpaceTimeFieldData | Mapping[str, Any],
    params: Mapping[str, Any],
) -> SpaceTimeSPDEGComputationResult:
    """Estimate a controlled diffusion-reaction policy effect by FEM g-computation."""

    field_data = (
        data if isinstance(data, SpaceTimeFieldData) else SpaceTimeFieldData.model_validate(data)
    )
    policy, baseline, policy_metadata = _materialize_policy_fields(field_data, params)
    mass, stiffness = build_piecewise_linear_fem_matrices(field_data.space_grid)
    fitted = _fit_linear_diffusion_response(
        field_data, mass=mass, stiffness=stiffness, params=params
    )
    certificate = build_space_time_identification_certificate(field_data, policy, params=params)
    if not certificate.g_computation_allowed:
        raise ValueError("space-time identification certificate blocks g-computation")

    confounder = field_data.confounder_field
    initial = field_data.outcome_field[0]
    solver_name = str(params.get("solver", "implicit_euler"))
    if solver_name not in {"implicit_euler", "explicit_euler"}:
        raise ValueError("solver must be implicit_euler or explicit_euler")
    solver: Literal["implicit_euler", "explicit_euler"] = (
        "explicit_euler" if solver_name == "explicit_euler" else "implicit_euler"
    )
    baseline_surface = simulate_linear_diffusion_response(
        time_grid=field_data.time_grid,
        space_grid=field_data.space_grid,
        treatment_field=baseline,
        confounder_field=confounder,
        initial_field=initial,
        kappa=fitted.kappa,
        treatment_effect=fitted.treatment_effect,
        confounder_effect=fitted.confounder_effect,
        intercept=fitted.intercept,
        reaction_rate=fitted.reaction_rate,
        carrying_capacity=fitted.carrying_capacity,
        solver=solver,
    )
    policy_surface = simulate_linear_diffusion_response(
        time_grid=field_data.time_grid,
        space_grid=field_data.space_grid,
        treatment_field=policy,
        confounder_field=confounder,
        initial_field=initial,
        kappa=fitted.kappa,
        treatment_effect=fitted.treatment_effect,
        confounder_effect=fitted.confounder_effect,
        intercept=fitted.intercept,
        reaction_rate=fitted.reaction_rate,
        carrying_capacity=fitted.carrying_capacity,
        solver=solver,
    )
    effect_surface = policy_surface - baseline_surface

    space_grid = np.asarray(field_data.space_grid, dtype=float)
    time_grid = np.asarray(field_data.time_grid, dtype=float)
    target_mask = _mask_from_bounds(space_grid, params.get("outcome_region_bounds"))
    source_mask = _mask_from_bounds(space_grid, params.get("intervention_region_bounds"))
    time_window = _time_mask_from_window(time_grid, params.get("time_window"))
    intervention_window = params.get("intervention_interval", params.get("pulse_interval"))
    intervention_time_mask = (
        _time_mask_from_window(time_grid, intervention_window)
        if intervention_window is not None
        else np.any(np.abs(policy - baseline) > 1.0e-12, axis=1)
    )
    source_time = (
        float(time_grid[np.where(intervention_time_mask)[0][0]])
        if np.any(intervention_time_mask)
        else float(time_grid[0])
    )
    lags = tuple(float(item) for item in params.get("impulse_lags", (0.0,)))
    irf = _spillover_impulse_response(
        effect_surface,
        time_grid=time_grid,
        source_time=source_time,
        target_mask=target_mask,
        lags=lags,
    )
    effect = _region_time_average(
        effect_surface,
        time_grid=time_grid,
        space_grid=space_grid,
        region_mask=target_mask,
        time_mask=time_window,
    )
    policy_value = _region_time_average(
        policy_surface,
        time_grid=time_grid,
        space_grid=space_grid,
        region_mask=target_mask,
        time_mask=time_window,
    )
    baseline_value = _region_time_average(
        baseline_surface,
        time_grid=time_grid,
        space_grid=space_grid,
        region_mask=target_mask,
        time_mask=time_window,
    )
    positivity = _build_positivity_report(field_data, policy, baseline, certificate)
    green_summary = _green_kernel_summary(
        effect_surface,
        time_grid=time_grid,
        space_grid=space_grid,
        source_mask=source_mask,
        target_mask=target_mask,
        intervention_time_mask=intervention_time_mask,
        treatment_effect=fitted.treatment_effect,
    )
    residual_diagnostics = _outcome_residual_diagnostics(
        field_data,
        fitted,
        mass=mass,
        stiffness=stiffness,
    )
    ipw_result: dict[str, Any] | None = None
    doubly_robust_estimate: float | None = None
    if bool(params.get("compute_ipw", False)):
        if certificate.ipw_allowed:
            ipw_result = estimate_space_time_treatment_density_process(
                field_data,
                policy,
                params=params,
                region_mask=target_mask,
                time_mask=time_window,
            )
        else:
            ipw_result = {
                "status": "not_applicable",
                "reason": "target_policy_is_not_absolutely_continuous_or_fails_path_space_positivity",
                "ipw_allowed": False,
            }
    if bool(params.get("compute_dr", False)):
        if ipw_result is None and certificate.ipw_allowed:
            ipw_result = estimate_space_time_treatment_density_process(
                field_data,
                policy,
                params=params,
                region_mask=target_mask,
                time_mask=time_window,
            )
        if ipw_result is not None and ipw_result.get("status") == "computed":
            factual_surface = simulate_linear_diffusion_response(
                time_grid=field_data.time_grid,
                space_grid=field_data.space_grid,
                treatment_field=field_data.treatment_field,
                confounder_field=confounder,
                initial_field=initial,
                kappa=fitted.kappa,
                treatment_effect=fitted.treatment_effect,
                confounder_effect=fitted.confounder_effect,
                intercept=fitted.intercept,
                reaction_rate=fitted.reaction_rate,
                carrying_capacity=fitted.carrying_capacity,
                solver=solver,
            )
            factual_model_value = _region_time_average(
                factual_surface,
                time_grid=time_grid,
                space_grid=space_grid,
                region_mask=target_mask,
                time_mask=time_window,
            )
            observed_value = _region_time_average(
                np.asarray(field_data.outcome_field, dtype=float),
                time_grid=time_grid,
                space_grid=space_grid,
                region_mask=target_mask,
                time_mask=time_window,
            )
            dr_policy_value = policy_value + float(ipw_result["final_density"]) * (
                observed_value - factual_model_value
            )
            doubly_robust_estimate = float(dr_policy_value - baseline_value)
            ipw_result["doubly_robust_augmented"] = True
            ipw_result["factual_model_functional"] = float(factual_model_value)
            ipw_result["baseline_model_functional"] = float(baseline_value)
        elif ipw_result is None:
            ipw_result = {
                "status": "not_applicable",
                "reason": "doubly_robust_requires_absolute_continuity_for_the_ipw_component",
                "ipw_allowed": bool(certificate.ipw_allowed),
            }
    convergence_diagnostics: dict[str, Any] = {}
    if bool(
        params.get("compute_convergence", False)
        or params.get("mesh_sensitivity", False)
        or params.get("timestep_sensitivity", False)
    ):
        convergence_diagnostics = _effect_convergence_diagnostics(
            field_data,
            policy=policy,
            baseline=baseline,
            fitted=fitted,
            params=params,
            solver=solver,
            full_effect=effect,
        )
    diagnostics = {
        "mesh_nodes": int(field_data.n_space),
        "time_points": int(field_data.n_times),
        "solver": solver,
        "mass_matrix_trace": float(np.trace(mass)),
        "stiffness_matrix_trace": float(np.trace(stiffness)),
        "policy_metadata": policy_metadata,
        "target_region_nodes": int(np.sum(target_mask)),
        "source_region_nodes": int(np.sum(source_mask)),
        "residual_scale": float(fitted.residual_scale),
        "policy_functional": float(policy_value),
        "baseline_functional": float(baseline_value),
        "outcome_residual_diagnostics": residual_diagnostics,
    }
    space_time_certificate = build_space_time_causal_certificate(
        certificate,
        metadata={
            "method_id": "causal.space_time.spde_g_computation",
            "sample_size": field_data.sample_size,
        },
    )
    artifact_store = resolve_artifact_store({}, params)
    space_time_certificate_ref = (
        persist_space_time_causal_certificate(artifact_store, space_time_certificate)
        if artifact_store is not None
        else None
    )

    return SpaceTimeSPDEGComputationResult(
        policy_effect_region_time_average=effect,
        fitted_coefficients=fitted,
        identification_certificate=certificate,
        space_time_causal_certificate=space_time_certificate,
        space_time_causal_certificate_ref=space_time_certificate_ref,
        positivity_report=positivity,
        green_kernel_summary=green_summary,
        spillover_impulse_response=irf,
        effect_surface=effect_surface.tolist(),
        baseline_surface=baseline_surface.tolist(),
        policy_surface=policy_surface.tolist(),
        ipw_result=ipw_result,
        doubly_robust_estimate=doubly_robust_estimate,
        convergence_diagnostics=convergence_diagnostics,
        diagnostics=diagnostics,
    )


def _failure_payload(reason: str, *, sample_size: int = 0) -> dict[str, Any]:
    report = build_failure_report(
        method=CausalMethod.ST_DSCM_SPDE,
        status=EstimationStatus.INPUT_INVALID,
        reason=reason,
        estimand="E[integral_BxJ(Y^policy)]",
        sample_size=sample_size,
        n_treated=0,
        n_control=0,
        pre_periods=0,
        post_periods=0,
        assumptions={},
    )
    return wrap_causal_output(report, warnings=[reason])


@foundry_method(
    namespace="causal.space_time",
    version="1.0.0",
    tags={"causal", "space-time", "dscm", "spde", "g-computation", "spillover"},
)
class SpaceTimeSPDEGComputation:
    """Estimate ST-DSCM policy effects through finite-element SPDE g-computation."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="fem_spde_g_computation",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="outcome_field",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("outcome", "field"),
                    shape=("n_times", "n_space"),
                ),
                SlotSpec(
                    name="treatment_field",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("treatment", "field"),
                    shape=("n_times", "n_space"),
                ),
                SlotSpec(
                    name="time_grid",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("time", "index"),
                    shape=("n_times",),
                ),
                SlotSpec(
                    name="space_grid",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("space", "coordinate"),
                    shape=("n_space",),
                ),
            }
        ),
        output_slots=_space_time_output_slots(),
        parameters=(
            ParameterSpec(name="policy_field", default=None),
            ParameterSpec(name="baseline_policy_field", default=None),
            ParameterSpec(name="intervention_region_bounds", default=None),
            ParameterSpec(name="intervention_interval", default=None),
            ParameterSpec(name="intervention_value", default=1.0),
            ParameterSpec(name="outcome_region_bounds", default=None),
            ParameterSpec(name="time_window", default=None),
            ParameterSpec(name="impulse_lags", default=(0.0,)),
            ParameterSpec(name="solver", default="implicit_euler"),
            ParameterSpec(name="coefficients", default={}),
            ParameterSpec(name="fit_reaction", default=False),
            ParameterSpec(name="carrying_capacity", default=1.0),
            ParameterSpec(name="compute_convergence", default=False),
            ParameterSpec(name="mesh_sensitivity", default=False),
            ParameterSpec(name="timestep_sensitivity", default=False),
            ParameterSpec(name="compute_ipw", default=False),
            ParameterSpec(name="compute_dr", default=False),
            ParameterSpec(name="policy_mode", default="deterministic"),
            ParameterSpec(name="policy_absolute_continuity", default=False),
            ParameterSpec(name="treatment_diffusion_scale", default=1.0),
            ParameterSpec(name="factual_treatment_drift_field", default=None),
            ParameterSpec(name="policy_treatment_drift_field", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N3,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Space-time Dynamic Structural Causal Model estimator for controlled "
            "diffusion-reaction systems. Fields remain continuum objects in the "
            "causal contract; FEM mesh and time steps are numerical approximations."
        ),
        tags=frozenset({"causal", "space-time", "dscm", "spde", "g-computation", "spillover"}),
        citations=(
            "Lindgren, F., Rue, H. & Lindstrom, J. (2011). An explicit link between Gaussian fields and GMRFs.",
            "Robins, J.M. (1986). A new approach to causal inference in mortality studies.",
            "Boeken, P. & Mooij, J.M. (2024). Dynamic structural causal models.",
        ),
        equations={
            "projected_spde": "M dxi_t = (-kappa K xi_t + M f_theta(xi_t,L_t,t) + B A_t) dt",
            "g_computation": "psi_hat(pi;B,J) = average_{B,J} E_hat[Y^pi(s,t)]",
            "operator_spillover": "A(R,I) -> Y(B,J) through the FEM Green response, not binary adjacency",
        },
        assumptions={
            "well_posed_mild_solution": "Generators and reactions define unique mild solutions.",
            "consistency": "Observed outcome field equals the potential field under observed treatment.",
            "no_anticipation": "Structural equations are adapted to observed field history.",
            "no_information_drift": "Treatment has no extra information about future potential outcome fields.",
            "path_space_positivity": "IPW only when target policy law is absolutely continuous with the factual law.",
            "measurement_support": "Observed fields or measurement model identify the FEM approximation.",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Continuous space-time policy spillovers where diffusion-reaction dynamics "
            "are the scientific structural model and discrete lag panels are not the estimand."
        ),
        when_not_to_use=(
            "Arbitrary space-time systems without a defended SPDE mechanism, missing adjustment "
            "fields, or deterministic policies treated as if IPW were valid."
        ),
        typical_min_obs=200,
        output_interpretation=(
            "Region-time policy effect, effect surface, spillover impulse response, "
            "identification certificate, and positivity report for a controlled SPDE."
        ),
    )

    @staticmethod
    def pure_step(
        state: SpaceTimeFieldData | Mapping[str, Any], params: Mapping[str, Any]
    ) -> dict[str, Any]:
        sample_size = 0
        try:
            data = (
                state
                if isinstance(state, SpaceTimeFieldData)
                else SpaceTimeFieldData.model_validate(state)
            )
            sample_size = data.sample_size
            result = estimate_space_time_spde_g_computation(data, params)
            n_treated = int(np.sum(np.asarray(data.treatment_field, dtype=float) > 0.0))
            report = build_success_report(
                method=CausalMethod.ST_DSCM_SPDE,
                estimand="E[integral_BxJ(Y^policy)]",
                point_estimate=result.policy_effect_region_time_average,
                confidence_interval=(
                    result.policy_effect_region_time_average
                    - 1.96
                    * result.fitted_coefficients.residual_scale
                    / math.sqrt(max(sample_size, 1)),
                    result.policy_effect_region_time_average
                    + 1.96
                    * result.fitted_coefficients.residual_scale
                    / math.sqrt(max(sample_size, 1)),
                ),
                inference_method="fem_spde_g_computation",
                sample_size=sample_size,
                n_treated=n_treated,
                n_control=max(sample_size - n_treated, 0),
                pre_periods=0,
                post_periods=data.n_times,
                assumptions=SpaceTimeSPDEGComputation.metadata.assumptions,
                metadata={
                    "identification_status": result.identification_certificate.status.value,
                    "path_space_support": result.identification_certificate.path_space_support,
                    "has_convergence_diagnostics": bool(result.convergence_diagnostics),
                    "has_ipw_result": result.ipw_result is not None,
                },
                sutva_assumed=False,
                sutva_violation_risk="low",
            )
            extras = {
                "result": result.model_dump(mode="json"),
                "spde_estimator": result.model_dump(mode="json"),
                "identification_certificate": result.identification_certificate.model_dump(
                    mode="json"
                ),
                "space_time_causal_certificate": result.space_time_causal_certificate.model_dump(
                    mode="json"
                ),
                "space_time_causal_certificate_ref": (
                    None
                    if result.space_time_causal_certificate_ref is None
                    else result.space_time_causal_certificate_ref.model_dump(mode="json")
                ),
                "positivity_report": result.positivity_report,
                "effect_surface": result.effect_surface,
                "spillover_impulse_response": result.spillover_impulse_response,
                "green_kernel_summary": result.green_kernel_summary,
                "convergence_diagnostics": result.convergence_diagnostics,
                "ipw_result": result.ipw_result,
                "doubly_robust_estimate": result.doubly_robust_estimate,
            }
            return wrap_causal_output(report, extras=extras)
        except Exception as exc:
            return _failure_payload(str(exc), sample_size=sample_size)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> SpaceTimeFieldData:
        if isinstance(fallback_state, SpaceTimeFieldData):
            return fallback_state
        payload: dict[str, Any] = {}
        if isinstance(fallback_state, Mapping):
            payload.update(dict(fallback_state))
        payload.update({key: value for key, value in bound_inputs.items()})
        return SpaceTimeFieldData.model_validate(payload)


__all__ = [
    "FieldNode",
    "FittedSPDEParameters",
    "OperatorEdge",
    "SPDEEstimatorSpec",
    "SPDEGenerator",
    "SPDEMechanism",
    "SpaceTimeDSCM",
    "SpaceTimeDomain",
    "SpaceTimeFieldData",
    "SpaceTimeIdentificationCertificate",
    "SpaceTimeIdentificationStatus",
    "SpaceTimeIntervention",
    "SpaceTimeInterventionType",
    "SpaceTimeMeshSpec",
    "SpaceTimePathSpace",
    "SpaceTimeSPDEGComputation",
    "SpaceTimeSPDEGComputationResult",
    "SpaceTimeSplit",
    "SpaceTimeSupport",
    "build_piecewise_linear_fem_matrices",
    "build_space_time_identification_certificate",
    "estimate_space_time_spde_g_computation",
    "estimate_space_time_treatment_density_process",
    "simulate_linear_diffusion_response",
    "simulate_reaction_diffusion_response",
]
