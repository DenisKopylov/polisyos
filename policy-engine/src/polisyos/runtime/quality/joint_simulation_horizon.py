"""Joint simulation horizon controller over existing Foundry engines.

This module owns the N5 orchestration seam: it maps bound N2 intervention atoms
and a composed WorldModelRecord into individual, pairwise, and joint simulation
runs. It does not promote simulation output into world evidence and does not
implement a parallel simulator beside Foundry engines.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal, Protocol

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator

from polisyos.foundry.execute._internal.snapshots import _flatten_state
from polisyos.foundry.execute.executor import (
    apply_state_delta,
    execute_program_graph,
)
from polisyos.foundry.methods import SlotType
from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.catalog.causal.protocols import NCMQueryData
from polisyos.foundry.methods.catalog.simulation import (
    StockFlowSystemDynamicsEstimator,
    ensure_simulation_methods_registered,
)
from polisyos.foundry.methods.components.io import validate_value_for_slot
from polisyos.foundry.methods.selection.registry import MethodRegistry
from polisyos.ir.analytics.ncm import NCMSpec  # noqa: TC001 - Pydantic validates at runtime.
from polisyos.pdc import gy_content_hash, gy_recorded_content_hash
from polisyos.runtime.quality.design_axes.coupling_composition import (
    BoundaryCouplingKind,
    CouplingGraph,
    CouplingRegimeClassification,
    classify_coupling,
)
from polisyos.runtime.quality.intervention_atom_binding import (  # noqa: TC001
    InterventionAtomBinding,
)
from polisyos.runtime.quality.world_model_record import (
    WorldModelRecord,
    consume_world_model_record_for_simulation,
    resolve_intervention_atom_world_binding,
)

if TYPE_CHECKING:
    from polisyos.runtime.quality.intervention_atom_binding import CausalAssignmentProjection

JOINT_SIMULATION_HORIZON_SCHEMA_VERSION = "policyos.runtime.joint_simulation_horizon.v1"
JOINT_SIMULATION_HORIZON_STATE_CONSUMPTION_SCHEMA_VERSION = (
    "policyos.runtime.joint_simulation_horizon.v2"
)
WORLD_STATE_CONSUMPTION_AUTHORITY_LIMITATIONS = (
    "exec_plan_provenance_not_established",
    "horizon_time_alignment_not_established",
)

EngineKind = Literal[
    "program_graph",
    "ncm_parallel_worlds",
    "coupled_des_abm",
    "system_dynamics",
    "method_registry_estimator",
]
RunLevel = Literal["individual", "pairwise", "joint"]
EngineDecisionKind = Literal["selected", "unsupported", "rejected"]
TemporalCapability = Literal["static", "multi_period", "unsupported"]
ControllerAuthorityScope = Literal["production", "contract_testing"]
EquilibriumSemantics = Literal[
    "none",
    "static_SCM",
    "dynamic_SCM",
    "time_unrolled_SCM",
    "equilibrium_SCM",
    "game_model",
    "agent_based_model",
    "unsupported",
]
CouplingSupportStatus = Literal["supported", "unsupported", "not_applicable"]
EngineOutputShape = Literal[
    "static_point",
    "time_series_trajectory",
    "program_state_trajectory",
    "scalar_final_value",
    "unsupported",
]
SimulationCalibrationStatus = Literal[
    "content_bound_run_receipt",
    "unsupported_coupling_gated",
    "no_run",
]

_SEMANTICS_BY_OUTPUT_SHAPE: dict[EngineOutputShape, frozenset[EquilibriumSemantics]] = {
    "static_point": frozenset({"none", "static_SCM"}),
    "time_series_trajectory": frozenset(
        {"dynamic_SCM", "time_unrolled_SCM", "equilibrium_SCM", "agent_based_model"}
    ),
    "program_state_trajectory": frozenset({"dynamic_SCM", "time_unrolled_SCM", "equilibrium_SCM"}),
    "scalar_final_value": frozenset({"none"}),
    "unsupported": frozenset(),
}
_OUTPUT_SHAPE_VALUES = frozenset(_SEMANTICS_BY_OUTPUT_SHAPE)
_SYSTEM_WIDE_COUPLING_REGIMES = frozenset({"hierarchically_coupled", "entangled"})
_COUPLING_ENGINES_BY_KIND: dict[BoundaryCouplingKind, frozenset[EngineKind]] = {
    "independent": frozenset(
        {
            "program_graph",
            "ncm_parallel_worlds",
            "coupled_des_abm",
            "system_dynamics",
            "method_registry_estimator",
        }
    ),
    "sequential": frozenset({"program_graph", "system_dynamics", "method_registry_estimator"}),
    "shared_resource": frozenset({"coupled_des_abm", "system_dynamics"}),
    "feedback": frozenset({"coupled_des_abm", "system_dynamics"}),
    "unknown": frozenset(),
}


class JointSimulationControllerError(ValueError):
    """Fail-closed error raised before a simulation can claim K_sim output."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class ProofReceiptError(ValueError):
    """Raised when a simulation receipt is not content-bound to the run payload."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class _StrictModel(BaseModel):
    """Strict immutable base model for N5 public artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)


class _MethodSignatureLike(Protocol):
    """Structural slice of registry signatures needed for output-shape resolution."""

    @property
    def output_slot_names(self) -> frozenset[str]:
        """Return declared output slot names."""

    @property
    def input_slot_names(self) -> frozenset[str]:
        """Return declared input slot names."""


class JointSimulationControllerPolicy(_StrictModel):
    """Safe public N5 policy.

    Production exposes no knob to bypass the coupling gate, force support for an
    unbacked engine, or trust a declared equilibrium label. Mutation switches
    live only behind ``JointSimulationHorizonController.for_contract_testing``.
    """


class _RuntimeSettings(_StrictModel):
    """Internal N5 settings, with unsafe switches only for contract probes."""

    authority_scope: ControllerAuthorityScope = "production"
    disable_coupling_gate: bool = False
    trust_declared_equilibrium_semantics: bool = False
    trust_method_tags_for_semantics: bool = False
    force_run_receipt_for_no_trajectories: bool = False
    shrink_world_credal_state: bool = False
    fabricate_interaction_terms: bool = False


class HorizonSpec(_StrictModel):
    """Discrete valid-time horizon requested from the selected engine."""

    start: int = Field(ge=0)
    end: int = Field(ge=0)
    step: int = Field(default=1, ge=1)
    valid_time_role: str = "valid_time"
    transaction_time_role: str = "transaction_time"
    scenario_branch_policy: str = "hold_world_record_constant"

    @model_validator(mode="after")
    def _validate_bounds(self) -> HorizonSpec:
        if self.end < self.start:
            raise ValueError("horizon_end_before_start")
        return self

    def steps(self) -> tuple[int, ...]:
        """Return inclusive horizon steps."""

        return tuple(range(self.start, self.end + 1, self.step))


class EnginePlan(_StrictModel):
    """Requested engine contour plus engine-specific eligibility inputs."""

    engine_kind: EngineKind
    objective_ref: str = Field(..., min_length=1)
    declared_equilibrium_semantics: EquilibriumSemantics | None = None
    eligibility_conditions: tuple[str, ...] = ()
    ncm_spec: NCMSpec | None = None
    variable_map: dict[str, str] = Field(default_factory=dict)
    coupled_state: dict[str, Any] = Field(default_factory=dict)
    coupled_params: dict[str, Any] = Field(default_factory=dict)
    system_dynamics_state: dict[str, Any] = Field(default_factory=dict)
    system_dynamics_params: dict[str, Any] = Field(default_factory=dict)
    system_dynamics_state_overrides_by_atom: dict[str, dict[str, Any]] = Field(
        default_factory=dict
    )
    program_graph_ref: Any | None = Field(default=None, exclude=True)
    exec_plan_ref: Any | None = Field(default=None, exclude=True)
    program_store: Any | None = Field(default=None, exclude=True)
    program_base_state: Any | None = Field(default=None, exclude=True)
    program_base_ref: Any | None = Field(default=None, exclude=True)
    mechanism_registry: Any | None = Field(default=None, exclude=True)
    slot_registry: Any | None = Field(default=None, exclude=True)
    merge_registry: Any | None = Field(default=None, exclude=True)
    selector_field_registry: Any | None = Field(default=None, exclude=True)
    constraint_registry: Any | None = Field(default=None, exclude=True)
    program_graph_acyclic: bool = True
    program_parameter_overrides_by_atom: dict[str, dict[str, dict[str, Any]]] = Field(
        default_factory=dict
    )
    method_fqn: str | None = None


class JointSimulationRequest(_StrictModel):
    """Controller input matching the GY-N0 seam contract."""

    world_model_record_ref: str = Field(..., min_length=1)
    world_model_record: WorldModelRecord
    intervention_atoms: tuple[InterventionAtomBinding, ...]
    selected_outcomes: tuple[str, ...] = Field(min_length=1)
    horizon: HorizonSpec
    engine_plan: tuple[EnginePlan, ...] = Field(min_length=1)
    baseline_state: dict[str, float] = Field(default_factory=dict)
    evidence_state: dict[str, float] | None = None
    comparator_refs: tuple[str, ...] = ()
    coupling_graph: CouplingGraph | None = None
    budget_ref: str | None = None
    seed: int = 0
    replications: int = Field(default=1, ge=1)
    world_credal_state_before: dict[str, Any] = Field(default_factory=dict)

    @field_validator("intervention_atoms")
    @classmethod
    def _atoms_required(
        cls,
        value: tuple[InterventionAtomBinding, ...],
    ) -> tuple[InterventionAtomBinding, ...]:
        if not value:
            raise ValueError("intervention_atoms_missing")
        return value


class EngineDecision(_StrictModel):
    """Registry-derived engine eligibility and selection decision."""

    engine_kind: EngineKind
    objective_ref: str
    decision: EngineDecisionKind
    method_fqn: str | None = None
    equilibrium_semantics: EquilibriumSemantics
    temporal_capability: TemporalCapability = "unsupported"
    output_shape: EngineOutputShape = "unsupported"
    reason: str
    blockers: tuple[str, ...] = ()
    eligibility_source: str = "method_registry"


class JointSimulationApplicability(_StrictModel):
    """Typed pre-run applicability decision for one exact N5 request."""

    status: Literal["eligible", "ineligible", "not_established"]
    request_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    engine_decisions: tuple[EngineDecision, ...] = ()
    blockers: tuple[str, ...] = ()


class TrajectoryPoint(_StrictModel):
    """One horizon point emitted by a real engine run."""

    step: int
    outcomes: dict[str, float]
    effect: dict[str, float]
    engine_state: dict[str, Any] = Field(default_factory=dict)


class SimulationTrajectory(_StrictModel):
    """Individual, pairwise, or joint trajectory for a concrete atom subset."""

    run_level: RunLevel
    atom_ids: tuple[str, ...]
    engine_kind: EngineKind
    method_fqn: str
    objective_ref: str
    points: tuple[TrajectoryPoint, ...]
    diagnostics: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _InteractionCoverage:
    """Request-wide scope census with observed and complete evidence separated."""

    by_scope: Mapping[tuple[str, tuple[str, ...]], SimulationTrajectory]
    complete_scopes: frozenset[tuple[str, tuple[str, ...]]]
    issues: tuple[str, ...]
    expected_steps: tuple[int, ...]


def _higher_order_residuals(
    request: JointSimulationRequest,
    coverage: _InteractionCoverage,
) -> dict[str, dict[int, float]]:
    """Return joint residuals after individual and pairwise effects.

    Pairwise zero is not a proof of global additivity.  For a joint run with
    three or more atoms, this residual keeps the higher-order component visible
    without enumerating any additional powerset of interventions.
    """

    atom_ids = tuple(atom.intervention_id for atom in request.intervention_atoms)
    if len(atom_ids) < 3:
        return {}
    scope_index = coverage.by_scope
    if coverage.issues:
        return {}
    individual = {
        atom_id: scope_index.get(("individual", (atom_id,)))
        for atom_id in atom_ids
    }
    pairwise = {
        tuple(pair): scope_index.get(("pairwise", tuple(pair)))
        for pair in itertools.combinations(atom_ids, 2)
    }
    joint = scope_index.get(("joint", atom_ids))
    if joint is None or any(item is None for item in (*individual.values(), *pairwise.values())):
        return {}
    residuals: dict[str, dict[int, float]] = {}
    for outcome in request.selected_outcomes:
        by_step: dict[int, float] = {}
        joint_points = {point.step: point for point in joint.points}
        individual_points = {
            atom_id: {point.step: point for point in trajectory.points}
            for atom_id, trajectory in individual.items()
            if trajectory is not None
        }
        pairwise_points = {
            pair: {point.step: point for point in trajectory.points}
            for pair, trajectory in pairwise.items()
            if trajectory is not None
        }
        for step in coverage.expected_steps:
            pair_interaction_sum = 0.0
            individual_sum = sum(
                individual_points[atom_id][step].effect[outcome]
                for atom_id in atom_ids
            )
            for pair in pairwise:
                pair_effect = pairwise_points[pair][step].effect[outcome]
                pair_interaction_sum += pair_effect - sum(
                    individual_points[atom_id][step].effect[outcome]
                    for atom_id in pair
                )
            by_step[step] = float(
                joint_points[step].effect[outcome]
                - individual_sum
                - pair_interaction_sum
            )
        residuals[outcome] = by_step
    return residuals


def _checked_interaction_orders(
    request: JointSimulationRequest,
    coverage: _InteractionCoverage,
) -> tuple[int, ...]:
    """Return interaction orders fully backed by the executed trajectory set."""
    atom_ids = tuple(atom.intervention_id for atom in request.intervention_atoms)
    complete_scopes = coverage.complete_scopes
    checked: list[int] = []
    complete_individuals = all(
        ("individual", (atom_id,)) in complete_scopes for atom_id in atom_ids
    )
    if complete_individuals:
        checked.append(1)
    complete_pairs = all(
        ("pairwise", tuple(pair)) in complete_scopes for pair in itertools.combinations(atom_ids, 2)
    )
    if len(atom_ids) >= 2 and complete_individuals and complete_pairs:
        checked.append(2)
    if (
        len(atom_ids) == 3
        and complete_individuals
        and complete_pairs
        and ("joint", atom_ids) in complete_scopes
    ):
        checked.append(3)
    return tuple(checked)


def _interaction_coverage(
    request: JointSimulationRequest,
    trajectories: Sequence[SimulationTrajectory],
) -> _InteractionCoverage:
    """Index valid requested scopes and report incomplete horizons separately."""

    atom_ids = tuple(atom.intervention_id for atom in request.intervention_atoms)
    expected_steps = request.horizon.steps()
    expected = {
        (level, tuple(atom.intervention_id for atom in subset))
        for level, subset in _atom_subsets(request.intervention_atoms)
    }
    observed: dict[tuple[str, tuple[str, ...]], list[SimulationTrajectory]] = {}
    for trajectory in trajectories:
        key = (trajectory.run_level, tuple(trajectory.atom_ids))
        observed.setdefault(key, []).append(trajectory)

    issues: list[str] = []
    if len(set(atom_ids)) != len(atom_ids):
        issues.append("requested_atom_ids_not_unique")
    index: dict[tuple[str, tuple[str, ...]], SimulationTrajectory] = {}
    complete_scopes: set[tuple[str, tuple[str, ...]]] = set()
    for key in sorted(expected):
        matches = observed.get(key, [])
        if len(matches) != 1:
            issues.append(
                "trajectory_missing:" + key[0] + ":" + ",".join(key[1])
                if not matches
                else "trajectory_duplicate:" + key[0] + ":" + ",".join(key[1])
            )
            continue
        trajectory = matches[0]
        point_steps = tuple(point.step for point in trajectory.points)
        if len(point_steps) != len(set(point_steps)):
            issues.append("horizon_incomplete:" + key[0] + ":" + ",".join(key[1]))
            continue
        horizon_complete = point_steps == expected_steps
        valid_points = True
        for point in trajectory.points:
            for outcome in request.selected_outcomes:
                if outcome not in point.outcomes or outcome not in point.effect:
                    valid_points = False
                    break
                try:
                    finite = np.isfinite(float(point.outcomes[outcome])) and np.isfinite(
                        float(point.effect[outcome])
                    )
                except (TypeError, ValueError, OverflowError):
                    finite = False
                if not finite:
                    valid_points = False
                    break
            if not valid_points:
                break
        if not valid_points:
            issues.append("selected_outcome_incomplete:" + key[0] + ":" + ",".join(key[1]))
            continue
        index[key] = trajectory
        if horizon_complete:
            complete_scopes.add(key)
        else:
            expected_set = set(expected_steps)
            if any(step not in expected_set for step in point_steps):
                coverage_kind = "overlong"
            elif point_steps == expected_steps[: len(point_steps)]:
                coverage_kind = "short"
            elif set(point_steps) == expected_set:
                coverage_kind = "reordered"
            elif point_steps and point_steps == expected_steps[-len(point_steps) :]:
                coverage_kind = "suffix_only"
            else:
                coverage_kind = "missing_internal"
            issues.append(
                "horizon_incomplete:"
                + coverage_kind
                + ":"
                + key[0]
                + ":"
                + ",".join(key[1])
            )
    for key in observed.keys() - expected:
        issues.append("trajectory_scope_unrequested:" + key[0] + ":" + ",".join(key[1]))
    return _InteractionCoverage(
        by_scope=index,
        complete_scopes=frozenset(complete_scopes),
        issues=tuple(sorted(issues)),
        expected_steps=tuple(expected_steps),
    )


def _replication_seeds(request: JointSimulationRequest) -> tuple[int, ...]:
    """Derive one deterministic, distinct seed for every requested replicate."""

    return tuple(int(request.seed) + index for index in range(int(request.replications)))


def _effective_evidence_state(
    request: JointSimulationRequest,
) -> tuple[dict[str, float], Literal["explicit_evidence_state", "legacy_baseline_state_compat"]]:
    """Resolve the exact NCM input and preserve whether compatibility fallback applied."""

    if request.evidence_state is None:
        return request.baseline_state, "legacy_baseline_state_compat"
    return request.evidence_state, "explicit_evidence_state"


def _physical_run_ref(
    request: JointSimulationRequest,
    plan: EnginePlan,
    decision: EngineDecision,
    subset: Sequence[InterventionAtomBinding],
) -> str:
    """Content-bind the physical run specification used by role reuse."""

    evidence_state, evidence_source = _effective_evidence_state(request)
    runtime_refs = {
        name: str(getattr(plan, name))
        for name in ("program_graph_ref", "exec_plan_ref", "program_base_ref")
        if getattr(plan, name) is not None
    }
    payload = {
        "world_model_record_ref": request.world_model_record_ref,
        "world_model_record_content_hash": request.world_model_record.content_hash,
        "engine_kind": decision.engine_kind,
        "method_fqn": decision.method_fqn,
        "objective_ref": plan.objective_ref,
        "horizon": request.horizon.model_dump(mode="json"),
        "selected_outcomes": list(request.selected_outcomes),
        "seed": int(request.seed),
        "replications": int(request.replications),
        "replication_seeds": list(_replication_seeds(request)),
        "baseline_state": _json_ready(request.baseline_state),
        "comparator_refs": list(request.comparator_refs),
        "evidence_state": _json_ready(evidence_state),
        "evidence_source": evidence_source,
        "plan": plan.model_dump(mode="json"),
        "program_base_state_content_hash": (
            None
            if plan.program_base_state is None
            else _program_base_state_content_hash(plan.program_base_state)
        ),
        "runtime_refs": runtime_refs,
        "atoms": sorted(
            (atom.model_dump(mode="json") for atom in subset),
            key=lambda atom: (str(atom["content_hash"]), str(atom["intervention_id"])),
        ),
    }
    return gy_content_hash(payload)


def _program_base_state_content_hash(state: object) -> str:
    """Hash a base state using the typed leaf projection used by CAS snapshots."""

    try:
        leaves = {
            path: {
                "dtype": np.asarray(value).dtype.str,
                "shape": list(np.asarray(value).shape),
                "bytes_hex": np.ascontiguousarray(value).tobytes(order="C").hex(),
            }
            for path, value in _flatten_state(state)
        }
    except (TypeError, ValueError, OverflowError) as exc:
        raise JointSimulationControllerError(
            "program_graph_state_fingerprint_unavailable",
            type(state).__name__,
        ) from exc
    return gy_recorded_content_hash(leaves)


def _aggregate_replicated_trajectory(
    trajectories: Sequence[SimulationTrajectory],
    seeds: Sequence[int],
    physical_run_ref: str,
) -> SimulationTrajectory:
    """Average equal-shaped replicate trajectories while preserving diagnostics."""

    if not trajectories:
        raise JointSimulationControllerError("simulation_replications_missing")
    first = trajectories[0]
    if any(
        trajectory.atom_ids != first.atom_ids
        or trajectory.engine_kind != first.engine_kind
        or trajectory.method_fqn != first.method_fqn
        or len(trajectory.points) != len(first.points)
        for trajectory in trajectories[1:]
    ):
        raise JointSimulationControllerError("simulation_replication_shape_mismatch")

    points: list[TrajectoryPoint] = []
    for point_index, first_point in enumerate(first.points):
        replicated_points = [trajectory.points[point_index] for trajectory in trajectories]
        if any(point.step != first_point.step for point in replicated_points):
            raise JointSimulationControllerError("simulation_replication_step_mismatch")
        outcomes = {
            outcome: _required_finite_scalar(
                [point.outcomes[outcome] for point in replicated_points],
                field=f"outcome:{outcome}",
                missing_code="simulation_output_missing",
                malformed_code="simulation_output_non_numeric",
                non_finite_code="simulation_output_non_finite",
                allow_array_mean=True,
            )
            for outcome in first_point.outcomes
        }
        effects = {
            outcome: _required_finite_scalar(
                [point.effect[outcome] for point in replicated_points],
                field=f"effect:{outcome}",
                missing_code="simulation_output_missing",
                malformed_code="simulation_output_non_numeric",
                non_finite_code="simulation_output_non_finite",
                allow_array_mean=True,
            )
            for outcome in first_point.effect
        }
        points.append(
            TrajectoryPoint(
                step=first_point.step,
                outcomes=outcomes,
                effect=effects,
                engine_state={
                    **dict(_json_ready(first_point.engine_state)),
                    "replication_count": len(replicated_points),
                    "replication_seeds": list(seeds),
                    "replication_engine_states": [
                        _json_ready(point.engine_state) for point in replicated_points
                    ],
                },
            )
        )
    diagnostics = {
        **first.diagnostics,
        "requested_replications": len(seeds),
        "actual_replications": len(trajectories),
        "replication_seeds": list(seeds),
        "physical_run_ref": physical_run_ref,
    }
    return first.model_copy(update={"points": tuple(points), "diagnostics": diagnostics})


_ENGINE_PLAN_RUNTIME_HANDLES = frozenset(
    {
        "program_store",
        "mechanism_registry",
        "slot_registry",
        "merge_registry",
        "selector_field_registry",
        "constraint_registry",
    }
)


def _snapshot_engine_plan(plan: EnginePlan) -> EnginePlan:
    """Copy semantic plan inputs while retaining process-owned handles by identity."""

    snapshot = plan.model_copy()
    for name in EnginePlan.model_fields:
        if name in _ENGINE_PLAN_RUNTIME_HANDLES:
            continue
        object.__setattr__(snapshot, name, deepcopy(getattr(plan, name)))
    return snapshot


def _snapshot_joint_simulation_request(
    request: JointSimulationRequest,
) -> JointSimulationRequest:
    """Copy request semantics without recursively copying plan runtime handles."""

    snapshot = request.model_copy()
    for name in JointSimulationRequest.model_fields:
        value = getattr(request, name)
        if name == "engine_plan":
            copied = tuple(_snapshot_engine_plan(plan) for plan in value)
        else:
            copied = deepcopy(value)
        object.__setattr__(snapshot, name, copied)
    return snapshot


def _contains_invalid_original_numeric_element(value: object) -> bool:
    """Detect disallowed original elements before NumPy can coerce them."""

    pending: list[object] = [value]
    visited: set[int] = set()
    while pending:
        item = pending.pop()
        if item is None or isinstance(
            item,
            (str, bytes, bytearray, bool, np.bool_, complex, np.complexfloating),
        ):
            return True
        if isinstance(item, np.ndarray):
            if item.dtype.kind in {"b", "U", "S", "c"} or np.iscomplexobj(item):
                return True
            if item.dtype.kind == "O" and id(item) not in visited:
                visited.add(id(item))
                pending.extend(item.flat)
            continue
        if isinstance(item, Mapping):
            identity = id(item)
            if identity not in visited:
                visited.add(identity)
                pending.extend(item.values())
            continue
        if isinstance(item, Sequence):
            identity = id(item)
            if identity not in visited:
                visited.add(identity)
                pending.extend(item)
    return False


def _required_finite_scalar(
    value: object,
    *,
    field: str,
    missing_code: str,
    malformed_code: str,
    non_finite_code: str,
    allow_array_mean: bool = False,
) -> float:
    """Project a required producer value to one finite scalar or refuse it."""

    if value is None:
        raise JointSimulationControllerError(missing_code, field)
    if isinstance(value, (str, bytes, bytearray, bool, np.bool_)):
        raise JointSimulationControllerError(malformed_code, field)
    try:
        if _contains_invalid_original_numeric_element(value):
            raise TypeError("output contains a disallowed original element")
        raw_array = np.asarray(value)
        if raw_array.dtype.kind in {"b", "U", "S", "c"} or np.iscomplexobj(raw_array):
            raise TypeError("output is not a real numeric value")
        if raw_array.dtype.kind == "O" and any(
            item is None
            or isinstance(item, (str, bytes, bytearray, bool, np.bool_, complex))
            for item in raw_array.flat
        ):
            raise TypeError("object output contains non-numeric values")
        array = np.asarray(value, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise JointSimulationControllerError(malformed_code, field) from exc
    if array.size == 0 or (array.shape != () and not allow_array_mean):
        raise JointSimulationControllerError(malformed_code, field)
    if not bool(np.isfinite(array).all()):
        raise JointSimulationControllerError(non_finite_code, field)
    try:
        projected = float(array.item()) if array.shape == () else float(np.mean(array))
    except (TypeError, ValueError, OverflowError) as exc:
        raise JointSimulationControllerError(malformed_code, field) from exc
    if not np.isfinite(projected):
        raise JointSimulationControllerError(non_finite_code, field)
    return projected


def _validate_finite_tree(value: object, *, field: str) -> None:
    """Reject non-finite numeric metadata before it reaches a receipt payload."""

    if value is None or isinstance(value, (str, bytes, bool)):
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _validate_finite_tree(item, field=f"{field}.{key}")
        return
    if isinstance(value, Sequence):
        for index, item in enumerate(value):
            _validate_finite_tree(item, field=f"{field}[{index}]")
        return
    if isinstance(value, np.ndarray):
        _required_finite_scalar(
            value,
            field=field,
            missing_code="simulation_output_missing",
            malformed_code="simulation_output_non_numeric",
            non_finite_code="simulation_output_non_finite",
            allow_array_mean=True,
        )
        return
    if isinstance(value, (int, float, np.number)):
        _required_finite_scalar(
            value,
            field=field,
            missing_code="simulation_output_missing",
            malformed_code="simulation_output_non_numeric",
            non_finite_code="simulation_output_non_finite",
        )


def _validate_finite_trajectory(trajectory: SimulationTrajectory) -> SimulationTrajectory:
    """Apply the same finite-output contract to every registered adapter."""

    for point_index, point in enumerate(trajectory.points):
        for channel, values in (("outcome", point.outcomes), ("effect", point.effect)):
            for key, value in values.items():
                _required_finite_scalar(
                    value,
                    field=f"{channel}:{key}@{point.step}",
                    missing_code="simulation_output_missing",
                    malformed_code="simulation_output_non_numeric",
                    non_finite_code="simulation_output_non_finite",
                )
        _validate_finite_tree(point.engine_state, field=f"engine_state[{point_index}]")
    _validate_finite_tree(trajectory.diagnostics, field="trajectory_diagnostics")
    return trajectory


def _run_or_reuse_physical_spec(
    cache: dict[str, SimulationTrajectory],
    request: JointSimulationRequest,
    plan: EnginePlan,
    decision: EngineDecision,
    run_level: RunLevel,
    subset: tuple[InterventionAtomBinding, ...],
    run_once: Callable[
        [
            JointSimulationRequest,
            EnginePlan,
            EngineDecision,
            RunLevel,
            tuple[InterventionAtomBinding, ...],
            int,
        ],
        SimulationTrajectory,
    ],
) -> tuple[str, SimulationTrajectory, bool]:
    """Execute or reuse one physical spec in the caller-owned invocation cache."""

    physical_ref = _physical_run_ref(request, plan, decision, subset)
    cached = cache.get(physical_ref)
    if cached is not None:
        return physical_ref, cached, True
    seeds = _replication_seeds(request)
    replicated = tuple(
        _validate_finite_trajectory(
            run_once(
                _snapshot_joint_simulation_request(request),
                _snapshot_engine_plan(plan),
                decision.model_copy(deep=True),
                run_level,
                tuple(atom.model_copy(deep=True) for atom in subset),
                seed,
            )
        )
        for seed in seeds
    )
    aggregate = _validate_finite_trajectory(
        _aggregate_replicated_trajectory(replicated, seeds, physical_ref)
    )
    cache[physical_ref] = aggregate
    return physical_ref, aggregate, False


def _run_cached_replicates(
    request: JointSimulationRequest,
    plan: EnginePlan,
    decision: EngineDecision,
    run_once: Callable[
        [
            JointSimulationRequest,
            EnginePlan,
            EngineDecision,
            RunLevel,
            tuple[InterventionAtomBinding, ...],
            int,
        ],
        SimulationTrajectory,
    ],
) -> list[SimulationTrajectory]:
    """Run each physical specification once and project it to all requested roles."""

    # Freeze the key basis once; mutable nested request payloads cannot change
    # identity halfway through an invocation's execution loop.
    selected_plan_index = next(
        (index for index, candidate in enumerate(request.engine_plan) if candidate is plan),
        None,
    )
    cache_request = _snapshot_joint_simulation_request(request)
    cache_plan = (
        cache_request.engine_plan[selected_plan_index]
        if selected_plan_index is not None
        else _snapshot_engine_plan(plan)
    )
    cache_decision = decision.model_copy(deep=True)
    cache: dict[str, SimulationTrajectory] = {}
    output: list[SimulationTrajectory] = []
    for run_level, raw_subset in _atom_subsets(cache_request.intervention_atoms):
        subset = tuple(raw_subset)
        physical_ref, cached, reused = _run_or_reuse_physical_spec(
            cache,
            cache_request,
            cache_plan,
            cache_decision,
            run_level,
            subset,
            run_once,
        )
        output.append(
            cached.model_copy(
                update={
                    "run_level": run_level,
                    "atom_ids": tuple(atom.intervention_id for atom in subset),
                    "diagnostics": {
                        **cached.diagnostics,
                        "physical_run_ref": physical_ref,
                        "physical_run_reused": reused,
                        "role": run_level,
                    },
                }
            )
        )
    return output


class InteractionTerm(_StrictModel):
    """Real interaction term computed from actual trajectories."""

    atom_ids: tuple[str, str]
    outcome: str
    by_step: dict[int, float]
    formula: Literal["joint_effect_minus_sum_individual_effects"] = (
        "joint_effect_minus_sum_individual_effects"
    )


class FeedbackClassification(_StrictModel):
    """Feedback/shared-resource posture from S5 plus numeric interaction evidence."""

    numeric_interaction: Literal["none", "additive", "non_additive", "unsupported"]
    higher_order_residuals: dict[str, dict[int, float]] = Field(default_factory=dict)
    checked_interaction_orders: tuple[int, ...] = ()
    coupling_classes: tuple[BoundaryCouplingKind, ...] = ()
    coupling_regime: str | None = None
    coupling_gate_verdict: str | None = None
    coupling_classification_ref: str | None = None
    engine_supported: bool = True
    support_status: CouplingSupportStatus = "not_applicable"
    support_blockers: tuple[str, ...] = ()
    feedback: bool = False
    shared_resource: bool = False
    general_equilibrium: bool = False
    limitations: tuple[str, ...] = ()


class SimulationProofReceipt(_StrictModel):
    """Content-bound K_sim proof/calibration receipt for a real simulation run."""

    schema_version: Literal[
        "policyos.runtime.joint_simulation_horizon.v1",
        "policyos.runtime.joint_simulation_horizon.v2",
    ] = (
        JOINT_SIMULATION_HORIZON_SCHEMA_VERSION
    )
    receipt_id: str = Field(..., pattern=r"^joint_sim_receipt_[a-f0-9]{16}$")
    engine_kind: str = Field(..., min_length=1)
    payload_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    trajectory_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    metrics_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    diagnostics_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    diagnostics_attached: bool
    trajectory_count: int = Field(ge=0)
    uncertainty_kind: Literal["K_sim"] = "K_sim"
    authoritative_for: tuple[Literal["simulation_numerical_uncertainty"], ...] = ()
    may_not_use_for: tuple[Literal["world_credal_state_shrinkage", "promotion"], ...] = (
        "world_credal_state_shrinkage",
        "promotion",
    )
    calibration_status: SimulationCalibrationStatus = "content_bound_run_receipt"


class WorldStateConsumptionRecord(_StrictModel):
    """Exact WMR state and controlled plan consumed by one candidate N5 run."""

    world_model_record_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    input_bindings_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    bound_state_snapshot_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    state_blob_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    state_slot_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    selected_slot_paths: tuple[str, ...] = Field(min_length=1)
    program_graph_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    exec_plan_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    exec_plan_manifest_profile_sha256: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    exec_plan_provenance: Literal["not_established"] = "not_established"
    horizon_time_alignment: Literal["not_established"] = "not_established"

    @property
    def authority_limitations(self) -> tuple[str, str]:
        """Return the two limitations that N8 must retain as candidate facts."""

        return WORLD_STATE_CONSUMPTION_AUTHORITY_LIMITATIONS


class JointSimulationResult(_StrictModel):
    """N5 output artifact consumed by value gating, VOI, audit, and dashboards."""

    schema_version: Literal[
        "policyos.runtime.joint_simulation_horizon.v1",
        "policyos.runtime.joint_simulation_horizon.v2",
    ] = (
        JOINT_SIMULATION_HORIZON_SCHEMA_VERSION
    )
    world_model_record_ref: str
    world_model_record_content_hash: str
    atom_ids: tuple[str, ...]
    selected_outcomes: tuple[str, ...]
    horizon: HorizonSpec
    engine_decisions: tuple[EngineDecision, ...]
    equilibrium_semantics: dict[str, EquilibriumSemantics]
    trajectories: tuple[SimulationTrajectory, ...]
    marginal_effects: dict[str, dict[int, dict[str, float]]]
    interaction_terms: tuple[InteractionTerm, ...]
    feedback_classification: FeedbackClassification
    higher_order_residuals: dict[str, dict[int, float]] = Field(default_factory=dict)
    uncertainty_kind: Literal["K_sim"] = "K_sim"
    world_credal_state_before: dict[str, Any] = Field(default_factory=dict)
    world_credal_state_after: dict[str, Any] = Field(default_factory=dict)
    acquisition_requests: tuple[dict[str, Any], ...] = ()
    refinement_decisions: tuple[dict[str, Any], ...] = ()
    promotion_ready_value_packet: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    state_consumption: WorldStateConsumptionRecord | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    receipt: SimulationProofReceipt

    _content_payload: dict[str, Any] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def _versioned_state_consumption(self) -> JointSimulationResult:
        if self.receipt.schema_version != self.schema_version:
            raise ValueError("joint_simulation_receipt_schema_mismatch")
        if self.schema_version == JOINT_SIMULATION_HORIZON_SCHEMA_VERSION:
            if "state_consumption" in self.model_fields_set:
                raise ValueError("joint_simulation_v1_cannot_claim_state_consumption")
        elif self.state_consumption is None:
            raise ValueError("joint_simulation_v2_state_consumption_missing")
        return self

    def content_bound_payload(self) -> dict[str, Any]:
        """Return the exact payload that the receipt must content-bind."""

        return dict(self._content_payload)

    def trajectory_for(self, run_level: RunLevel, atom_ids: Sequence[str]) -> SimulationTrajectory:
        """Return the trajectory for ``run_level`` and an exact atom-id set."""

        normalized = tuple(atom_ids)
        for trajectory in self.trajectories:
            if trajectory.run_level == run_level and trajectory.atom_ids == normalized:
                return trajectory
        raise KeyError(f"trajectory_not_found:{run_level}:{','.join(normalized)}")


@dataclass(frozen=True, slots=True)
class _SelectedEngine:
    """Selected engine plan plus all attempted eligibility decisions."""

    decision: EngineDecision
    plan: EnginePlan
    decisions: tuple[EngineDecision, ...]


def _typed_execution_payload(value: object) -> object:
    """Project every typed execution input, refusing opaque or omitted values."""

    if isinstance(value, Enum):
        return {
            "type": f"{type(value).__module__}.{type(value).__qualname__}",
            "value": _typed_execution_payload(value.value),
        }
    if isinstance(value, BaseModel):
        payload: dict[str, object] = {}
        for name, field in type(value).model_fields.items():
            item = getattr(value, name)
            if field.exclude and item is not None:
                raise ValueError(f"excluded_execution_input_not_bindable:{name}")
            payload[name] = _typed_execution_payload(item)
        for name in type(value).model_computed_fields:
            payload[f"computed:{name}"] = _typed_execution_payload(getattr(value, name))
        private_values = getattr(value, "__pydantic_private__", None) or {}
        if any(item is not None for item in private_values.values()):
            raise ValueError("private_execution_input_not_bindable")
        return {
            "type": f"{type(value).__module__}.{type(value).__qualname__}",
            "fields": payload,
        }
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise TypeError("execution_input_mapping_key_not_string")
        return {
            "type": "mapping",
            "items": {key: _typed_execution_payload(item) for key, item in value.items()},
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return {
            "type": "sequence",
            "items": [_typed_execution_payload(item) for item in value],
        }
    if type(value) is Decimal:
        if not value.is_finite():
            raise ValueError("execution_input_non_finite")
        return {"type": "decimal.Decimal", "value": str(value)}
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        if not np.isfinite(value):
            raise ValueError("execution_input_non_finite")
        return value
    raise TypeError(f"execution_input_not_json_bindable:{type(value).__name__}")


def _joint_simulation_request_digest(
    request: JointSimulationRequest,
) -> str | None:
    """Hash all typed request inputs, including fields omitted from wire dumps."""

    try:
        return gy_recorded_content_hash(_typed_execution_payload(request))
    except Exception:
        return None


@dataclass(frozen=True, slots=True)
class _RequestApplicabilityEvaluation:
    """One N5 preflight plus its private selected-plan execution handle."""

    assessment: JointSimulationApplicability
    selected: _SelectedEngine
    world_input: Any


@dataclass(frozen=True, slots=True)
class _CouplingSupportDecision:
    """Engine support decision for the already-classified S5 coupling graph."""

    classification: CouplingRegimeClassification | None
    support_status: CouplingSupportStatus
    blockers: tuple[str, ...]
    coupling_classes: tuple[BoundaryCouplingKind, ...]
    general_equilibrium: bool
    gate_blocked: bool = False

    @property
    def engine_supported(self) -> bool:
        """Return whether the selected engine can ground the classified coupling."""

        return self.support_status != "unsupported"


def build_content_bound_simulation_receipt(
    *,
    engine_kind: str,
    payload: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
) -> SimulationProofReceipt:
    """Build a deterministic receipt over real trajectory, metrics, and diagnostics."""

    payload_dict = _json_ready(payload)
    schema_version = payload_dict.get(
        "schema_version", JOINT_SIMULATION_HORIZON_SCHEMA_VERSION
    )
    if schema_version not in {
        JOINT_SIMULATION_HORIZON_SCHEMA_VERSION,
        JOINT_SIMULATION_HORIZON_STATE_CONSUMPTION_SCHEMA_VERSION,
    }:
        raise ProofReceiptError("receipt_schema_version_unsupported")
    diagnostics_dict = _json_ready(diagnostics)
    trajectory_hash = gy_content_hash(
        payload_dict.get("trajectory", payload_dict.get("trajectories", ()))
    )
    trajectory_count = _trajectory_count(payload_dict)
    if diagnostics_dict.get("engine_run_claimed") is True and trajectory_count == 0:
        raise ProofReceiptError("receipt_engine_run_missing")
    if trajectory_count == 0:
        calibration_status: SimulationCalibrationStatus = (
            "unsupported_coupling_gated"
            if diagnostics_dict.get(
                "coupling_gate_blocked",
                diagnostics_dict.get("coupling_support_status") == "unsupported",
            )
            else "no_run"
        )
        authoritative_for: tuple[Literal["simulation_numerical_uncertainty"], ...] = ()
    else:
        calibration_status = "content_bound_run_receipt"
        authoritative_for = ("simulation_numerical_uncertainty",)
    metrics_hash = gy_content_hash(
        payload_dict.get("metrics", payload_dict.get("engine_decisions", ()))
    )
    diagnostics_hash = gy_content_hash(diagnostics_dict)
    payload_hash = gy_content_hash(
        {
            "payload": payload_dict,
            "diagnostics": diagnostics_dict,
            "trajectory_hash": trajectory_hash,
            "metrics_hash": metrics_hash,
            "diagnostics_hash": diagnostics_hash,
        }
    )
    return SimulationProofReceipt(
        schema_version=schema_version,
        receipt_id=f"joint_sim_receipt_{payload_hash.removeprefix('sha256:')[:16]}",
        engine_kind=engine_kind,
        payload_hash=payload_hash,
        trajectory_hash=trajectory_hash,
        metrics_hash=metrics_hash,
        diagnostics_hash=diagnostics_hash,
        diagnostics_attached=bool(diagnostics_dict),
        trajectory_count=trajectory_count,
        authoritative_for=authoritative_for,
        calibration_status=calibration_status,
    )


def bind_world_state_consumption(
    result: JointSimulationResult,
    consumption: WorldStateConsumptionRecord,
) -> JointSimulationResult:
    """Content-bind the state actually installed into the candidate N5 plan."""

    if result.schema_version != JOINT_SIMULATION_HORIZON_SCHEMA_VERSION:
        raise ProofReceiptError("state_consumption_requires_v1_engine_result")
    verify_simulation_receipt(result.receipt, result.content_bound_payload())
    if result.world_model_record_content_hash != consumption.world_model_record_content_hash:
        raise ProofReceiptError("state_consumption_world_mismatch")
    if not any(
        item.engine_kind == "program_graph" and item.decision == "selected"
        for item in result.engine_decisions
    ) or not result.trajectories:
        raise ProofReceiptError("state_consumption_program_run_missing")
    payload = deepcopy(result.content_bound_payload())
    payload["schema_version"] = JOINT_SIMULATION_HORIZON_STATE_CONSUMPTION_SCHEMA_VERSION
    payload["state_consumption"] = consumption.model_dump(mode="json", exclude_none=True)
    packet = dict(payload["promotion_ready_value_packet"])
    packet["authority_blockers"] = list(
        dict.fromkeys((*packet.get("authority_blockers", ()), *consumption.authority_limitations))
    )
    payload["promotion_ready_value_packet"] = packet
    receipt = build_content_bound_simulation_receipt(
        engine_kind=result.receipt.engine_kind,
        payload=payload,
        diagnostics=payload["diagnostics"],
    )
    bound = JointSimulationResult.model_validate(
        {**payload, "receipt": receipt.model_dump(mode="json")}
    )
    bound._content_payload = payload
    verify_simulation_receipt(bound.receipt, bound.content_bound_payload())
    return bound


def verify_simulation_receipt(
    receipt: SimulationProofReceipt,
    payload: Mapping[str, Any],
) -> None:
    """Recompute and verify a simulation receipt against a real run payload."""

    diagnostics = payload.get("diagnostics", {}) if isinstance(payload, Mapping) else {}
    trajectories = payload.get("trajectories", ()) if isinstance(payload, Mapping) else ()
    trajectory_count = _trajectory_count(payload) if isinstance(payload, Mapping) else 0
    if receipt.calibration_status == "content_bound_run_receipt" and trajectory_count == 0:
        raise ProofReceiptError("receipt_engine_run_missing")
    if receipt.calibration_status != "content_bound_run_receipt" and trajectory_count != 0:
        raise ProofReceiptError("receipt_no_run_has_trajectories")
    if (
        isinstance(diagnostics, Mapping)
        and diagnostics.get("engine_run_claimed") is True
        and (
            not isinstance(trajectories, Sequence)
            or isinstance(trajectories, str | bytes | bytearray)
            or not trajectories
        )
    ):
        raise ProofReceiptError("receipt_engine_run_missing")
    expected = build_content_bound_simulation_receipt(
        engine_kind=receipt.engine_kind,
        payload=payload,
        diagnostics=diagnostics if isinstance(diagnostics, Mapping) else {},
    )
    if receipt != expected:
        raise ProofReceiptError(
            "receipt_content_mismatch",
            f"{receipt.receipt_id} does not bind to the supplied simulation payload",
        )
    if not receipt.diagnostics_attached:
        raise ProofReceiptError("receipt_diagnostics_missing")


def _trajectory_count(payload: Mapping[str, Any]) -> int:
    raw = payload.get("trajectories", payload.get("trajectory", ()))
    if isinstance(raw, Sequence) and not isinstance(raw, str | bytes | bytearray):
        return len(raw)
    return 0


def _simulation_value_packet(
    request: JointSimulationRequest,
    decisions: Sequence[EngineDecision],
    *,
    interaction_evidence_issues: Sequence[str] = (),
) -> dict[str, Any]:
    """Build the canonical purpose-limited packet for the N5 producer/readers."""

    authority_blockers = ["simulation_only_k_sim_not_world_evidence"]
    if interaction_evidence_issues:
        authority_blockers.append("interaction_evidence_incomplete")
    return {
        "world_model_record_ref": request.world_model_record_ref,
        "world_model_record_content_hash": request.world_model_record.content_hash,
        "atom_ids": [atom.intervention_id for atom in request.intervention_atoms],
        "grounding_method_refs": [
            item.method_fqn for item in decisions if item.method_fqn is not None
        ],
        "comparator_refs_status": "not_established",
        "authority_blockers": authority_blockers,
        "uncertainty_kind": "K_sim",
    }


class JointSimulationHorizonController:
    """Thin N5 controller over registry-selected Foundry joint engines."""

    def __init__(
        self,
        *,
        method_registry: MethodRegistry | None = None,
        policy: JointSimulationControllerPolicy | None = None,
    ) -> None:
        if policy is not None and not isinstance(policy, JointSimulationControllerPolicy):
            raise TypeError("policy must be a JointSimulationControllerPolicy")
        self._registry = method_registry or MethodRegistry.get_instance()
        self.policy = policy or JointSimulationControllerPolicy()
        self._settings = _RuntimeSettings()

    @classmethod
    def for_contract_testing(
        cls,
        *,
        method_registry: MethodRegistry | None = None,
        disable_coupling_gate: bool = False,
        trust_declared_equilibrium_semantics: bool = False,
        trust_method_tags_for_semantics: bool = False,
        force_run_receipt_for_no_trajectories: bool = False,
        shrink_world_credal_state: bool = False,
        fabricate_interaction_terms: bool = False,
    ) -> JointSimulationHorizonController:
        """Return a non-authoritative N5 controller for mutation probes."""

        controller = cls(method_registry=method_registry)
        controller._settings = _RuntimeSettings(
            authority_scope="contract_testing",
            disable_coupling_gate=disable_coupling_gate,
            trust_declared_equilibrium_semantics=trust_declared_equilibrium_semantics,
            trust_method_tags_for_semantics=trust_method_tags_for_semantics,
            force_run_receipt_for_no_trajectories=force_run_receipt_for_no_trajectories,
            shrink_world_credal_state=shrink_world_credal_state,
            fabricate_interaction_terms=fabricate_interaction_terms,
        )
        return controller

    def assess_applicability(
        self,
        request: JointSimulationRequest,
    ) -> JointSimulationApplicability:
        """Assess an exact request with N5's owner checks, without running an engine."""

        request_digest = _joint_simulation_request_digest(request)
        if request_digest is None:
            return JointSimulationApplicability(
                status="not_established",
                blockers=("n5_request_digest_not_established",),
            )
        try:
            return self._assess_request(
                request,
                request_digest=request_digest,
            ).assessment
        except JointSimulationControllerError as exc:
            return JointSimulationApplicability(
                status=(
                    "ineligible"
                    if exc.code == "intervention_assignment_conflict"
                    else "not_established"
                ),
                request_digest=request_digest,
                blockers=(exc.code,),
            )

    def _assess_request(
        self,
        request: JointSimulationRequest,
        *,
        request_digest: str | None = None,
    ) -> _RequestApplicabilityEvaluation:
        """Run the shared N5 pre-execution checks and retain their selection."""

        self._validate_world_model_record(request)
        world_input = consume_world_model_record_for_simulation(
            request.world_model_record
        )
        for atom in request.intervention_atoms:
            resolve_intervention_atom_world_binding(atom, request.world_model_record)
        _validate_atom_assignment_compatibility(request)
        selected = self._select_engine(request)
        if (
            selected.decision.decision == "selected"
            and selected.decision.engine_kind == "ncm_parallel_worlds"
        ):
            try:
                _ncm_intervention(request.intervention_atoms, selected.plan)
            except JointSimulationControllerError as exc:
                return _RequestApplicabilityEvaluation(
                    assessment=JointSimulationApplicability(
                        status="ineligible",
                        request_digest=request_digest,
                        engine_decisions=selected.decisions,
                        blockers=(exc.code,),
                    ),
                    selected=selected,
                    world_input=world_input,
                )
        blockers = ()
        status: Literal["eligible", "ineligible"] = "eligible"
        if selected.decision.decision != "selected":
            status = "ineligible"
            blockers = tuple(
                dict.fromkeys(
                    reason
                    for item in selected.decisions
                    if item.decision != "selected"
                    for reason in (item.reason, *item.blockers)
                )
            ) or ("n5_no_engine_selected",)
        return _RequestApplicabilityEvaluation(
            assessment=JointSimulationApplicability(
                status=status,
                request_digest=request_digest,
                engine_decisions=selected.decisions,
                blockers=blockers,
            ),
            selected=selected,
            world_input=world_input,
        )

    def run(
        self,
        request: JointSimulationRequest,
        *,
        expected_applicability: JointSimulationApplicability | None = None,
    ) -> JointSimulationResult:
        """Run individual, pairwise, and joint horizons or fail closed."""

        request_digest = (
            _joint_simulation_request_digest(request)
            if expected_applicability is not None
            else None
        )
        if expected_applicability is not None and request_digest is None:
            raise JointSimulationControllerError(
                "joint_simulation_request_digest_not_established"
            )
        evaluation = self._assess_request(
            request,
            request_digest=request_digest,
        )
        if expected_applicability is not None and (
            expected_applicability.model_dump(mode="json")
            != evaluation.assessment.model_dump(mode="json")
            or expected_applicability.status != "eligible"
        ):
            raise JointSimulationControllerError(
                "joint_simulation_applicability_changed_before_run"
            )
        world_input = evaluation.world_input
        selected = evaluation.selected
        decision = selected.decision
        selected_plan = selected.plan
        decisions = selected.decisions
        coupling_support = _resolve_coupling_support(
            request=request,
            engine_kind=decision.engine_kind,
            gate_disabled=self._settings.disable_coupling_gate,
        )
        if decision.decision == "selected" and not coupling_support.engine_supported:
            decision = _unsupported(
                selected_plan,
                "coupling_composition_gate_unsupported",
                coupling_support.blockers,
            )
            decisions = (*decisions[:-1], decision)
        if decision.decision != "selected":
            coupling_support = _aggregate_no_run_coupling_support(
                request=request,
                decisions=decisions,
                gate_disabled=self._settings.disable_coupling_gate,
            )
        equilibrium = {decision.objective_ref: decision.equilibrium_semantics}
        trajectories: tuple[SimulationTrajectory, ...] = ()
        marginal_effects: dict[str, dict[int, dict[str, float]]] = {}
        interaction_terms: tuple[InteractionTerm, ...] = ()
        higher_order_residuals: dict[str, dict[int, float]] = {}
        checked_interaction_orders: tuple[int, ...] = ()
        interaction_evidence_issues: tuple[str, ...] = ()
        diagnostics: dict[str, Any] = {
            "world_model_record_id": request.world_model_record.world_model_record_id,
            "world_model_record_content_hash": request.world_model_record.content_hash,
            "world_input_ref": world_input.world_model_record_id,
            "horizon_loop_iterations": (
                len(request.horizon.steps())
                if decision.temporal_capability == "multi_period"
                else 1
            ),
            "temporal_capability": decision.temporal_capability,
            "unsupported_objectives": [],
            "unsupported_reasons": [],
            "controller_authority_scope": self._settings.authority_scope,
            "coupling_gate_disabled": self._settings.disable_coupling_gate,
            "coupling_support_status": coupling_support.support_status,
            "coupling_support_blockers": list(coupling_support.blockers),
            "coupling_gate_blocked": coupling_support.gate_blocked,
            "comparator_refs": list(request.comparator_refs),
            "comparator_refs_status": "not_established",
            "evidence_source": (
                "explicit_evidence_state"
                if request.evidence_state is not None
                else "legacy_baseline_state_compat"
            ),
            "requested_replications": int(request.replications),
            "replication_seeds": list(_replication_seeds(request)),
            "checked_interaction_orders": [],
            "engine_run_claimed": False,
        }

        if decision.decision == "selected":
            runner = self._engine_runners().get(decision.engine_kind)
            if runner is None:
                diagnostics["unsupported_objectives"].append(decision.objective_ref)
            else:
                trajectories = tuple(runner(request, selected_plan, decision))
                diagnostics["engine_run_claimed"] = bool(trajectories)
                if trajectories:
                    self._validate_selected_trajectories(
                        request=request,
                        plan=selected_plan,
                        decision=decision,
                        trajectories=trajectories,
                    )
        else:
            unsupported_decisions = tuple(
                item for item in decisions if item.decision != "selected"
            )
            diagnostics["unsupported_objectives"].extend(
                item.objective_ref for item in unsupported_decisions
            )
            diagnostics["unsupported_reasons"].extend(
                {
                    "objective_ref": item.objective_ref,
                    "reason": item.reason,
                    "blockers": list(item.blockers),
                }
                for item in unsupported_decisions
            )

        if trajectories:
            marginal_effects = _marginal_effects(trajectories)
            coverage = _interaction_coverage(
                request,
                trajectories,
            )
            interaction_evidence_issues = coverage.issues
            interaction_terms = tuple(
                _interaction_terms(request, coverage)
            )
            higher_order_residuals = _higher_order_residuals(
                request,
                coverage,
            )
            checked_interaction_orders = _checked_interaction_orders(
                request,
                coverage,
            )
            diagnostics["checked_interaction_orders"] = list(checked_interaction_orders)
            diagnostics["interaction_evidence_issues"] = list(interaction_evidence_issues)
            if self._settings.fabricate_interaction_terms:
                interaction_terms = _contract_testing_fabricated_interactions(interaction_terms)
        elif decision.decision == "selected":
            interaction_evidence_issues = ("trajectories_missing",)
            diagnostics["interaction_evidence_issues"] = list(interaction_evidence_issues)

        feedback = _feedback_classification(
            request=request,
            interaction_terms=interaction_terms,
            higher_order_residuals=higher_order_residuals,
            checked_interaction_orders=checked_interaction_orders,
            unsupported=decision.decision != "selected",
            coupling_support=coupling_support,
            decision_blockers=tuple(
                blocker for item in decisions for blocker in item.blockers
            ),
            interaction_evidence_issues=interaction_evidence_issues,
            aggregate_order_three_plus=len(request.intervention_atoms) >= 4,
        )
        value_packet = _simulation_value_packet(
            request, decisions, interaction_evidence_issues=interaction_evidence_issues
        )
        world_credal_state_after = _json_ready(request.world_credal_state_before)
        if self._settings.shrink_world_credal_state:
            world_credal_state_after = _contract_testing_shrunk_credal_state(
                request.world_credal_state_before
            )
        result_without_receipt = {
            "schema_version": JOINT_SIMULATION_HORIZON_SCHEMA_VERSION,
            "world_model_record_ref": request.world_model_record_ref,
            "world_model_record_content_hash": request.world_model_record.content_hash,
            "atom_ids": [atom.intervention_id for atom in request.intervention_atoms],
            "selected_outcomes": list(request.selected_outcomes),
            "horizon": request.horizon.model_dump(mode="json"),
            "engine_decisions": [item.model_dump(mode="json") for item in decisions],
            "equilibrium_semantics": equilibrium,
            "trajectories": [item.model_dump(mode="json") for item in trajectories],
            "marginal_effects": _json_ready(marginal_effects),
            "interaction_terms": [item.model_dump(mode="json") for item in interaction_terms],
            "higher_order_residuals": _json_ready(higher_order_residuals),
            "feedback_classification": feedback.model_dump(mode="json"),
            "uncertainty_kind": "K_sim",
            "world_credal_state_before": _json_ready(request.world_credal_state_before),
            "world_credal_state_after": world_credal_state_after,
            "acquisition_requests": [],
            "refinement_decisions": [],
            "promotion_ready_value_packet": _json_ready(value_packet),
            "diagnostics": _json_ready(diagnostics),
        }
        receipt = build_content_bound_simulation_receipt(
            engine_kind=decision.engine_kind,
            payload=result_without_receipt,
            diagnostics=diagnostics,
        )
        if self._settings.force_run_receipt_for_no_trajectories and not trajectories:
            receipt = receipt.model_copy(
                update={
                    "calibration_status": "content_bound_run_receipt",
                    "authoritative_for": ("simulation_numerical_uncertainty",),
                }
            )
        result = JointSimulationResult(**result_without_receipt, receipt=receipt)
        result._content_payload = result_without_receipt
        verify_simulation_receipt(result.receipt, result.content_bound_payload())
        return result

    def _validate_world_model_record(self, request: JointSimulationRequest) -> None:
        ref = request.world_model_record_ref
        if "pending" in ref.lower():
            raise JointSimulationControllerError(
                "world_model_record_ref_pending",
                "N5 requires the composed WorldModelRecord, not a pending placeholder",
            )
        accepted = {
            request.world_model_record.world_model_record_id,
            request.world_model_record.content_hash,
        }
        if ref not in accepted:
            raise JointSimulationControllerError(
                "world_model_record_ref_unresolved",
                f"{ref} does not resolve to the composed WorldModelRecord",
            )

    def _select_engine(self, request: JointSimulationRequest) -> _SelectedEngine:
        selectors = self._engine_selectors(request.world_model_record)
        decisions: list[EngineDecision] = []
        fallback_plan = request.engine_plan[0]
        for plan in request.engine_plan:
            selector = selectors.get(plan.engine_kind, self._select_registry_method_engine)
            decision = selector(plan)
            decision = self._resolve_engine_semantics(plan, decision)
            if decision.decision == "selected":
                input_issue = self._registered_system_dynamics_input_issue(request, plan, decision)
                if input_issue is not None:
                    decision = _unsupported(
                        plan,
                        "engine_input_contract_failed",
                        (input_issue,),
                    )
            if decision.decision == "selected":
                execution_conflict = _execution_assignment_conflict(request, plan)
                if execution_conflict is not None:
                    decision = _unsupported(
                        plan,
                        "engine_intervention_assignment_conflict",
                        (f"engine_variable_conflict:{execution_conflict}",),
                    )
            if (
                decision.decision == "selected"
                and decision.temporal_capability == "static"
                and len(request.horizon.steps()) > 1
            ):
                decision = _unsupported(
                    plan,
                    "static_engine_cannot_ground_dynamic_horizon",
                    ("static_engine_temporal_capability",),
                )
            if decision.decision == "selected":
                coupling_support = _resolve_coupling_support(
                    request=request,
                    engine_kind=decision.engine_kind,
                    gate_disabled=self._settings.disable_coupling_gate,
                )
                if not coupling_support.engine_supported:
                    decision = _unsupported(
                        plan,
                        "coupling_composition_gate_unsupported",
                        coupling_support.blockers,
                    )
            decisions.append(decision)
            if decision.decision == "selected":
                return _SelectedEngine(decision=decision, plan=plan, decisions=tuple(decisions))
        return _SelectedEngine(
            decision=decisions[0],
            plan=fallback_plan,
            decisions=tuple(decisions),
        )

    def _registered_system_dynamics_input_issue(
        self,
        request: JointSimulationRequest,
        plan: EnginePlan,
        decision: EngineDecision,
    ) -> str | None:
        """Validate effective numeric state against the registered input slots.

        Every physical subset must satisfy the same declared shapes before
        selection. This does not establish units, time-grid meaning, or input
        constraints absent from the registered signature.
        """

        if decision.engine_kind != "system_dynamics" and not (
            decision.engine_kind == "method_registry_estimator" and plan.system_dynamics_state
        ):
            return None
        entry = self._registry.get_entry(decision.method_fqn or "")
        if entry is None:
            return "registered_input_signature_missing"
        try:
            for _run_level, subset in _atom_subsets(request.intervention_atoms):
                state = _system_dynamics_state_for_subset(plan, subset)
                dimensions: dict[object, int] = {}
                for slot in sorted(entry.signature.input_slots, key=lambda item: item.name):
                    if slot.name not in state:
                        return f"registered_input_missing:{slot.name}"
                    value = state[slot.name]
                    if slot.slot_type is SlotType.SCALAR and slot.contract_id is None:
                        value = _required_finite_scalar(
                            value,
                            field=slot.name,
                            missing_code="registered_input_missing",
                            malformed_code="registered_input_non_numeric",
                            non_finite_code="registered_input_non_finite",
                        )
                    elif slot.shape or slot.slot_type in {SlotType.VECTOR, SlotType.MATRIX}:
                        if _contains_invalid_original_numeric_element(value):
                            return f"registered_input_non_numeric:{slot.name}"
                        value = np.asarray(value, dtype=float)
                        if not np.all(np.isfinite(value)):
                            return f"registered_input_non_finite:{slot.name}"
                    validate_value_for_slot(
                        slot,
                        value,
                        method_fqn=entry.signature.fqn,
                        label="input",
                    )
                    for axis, dimension in enumerate(slot.shape):
                        if dimension is None or isinstance(dimension, int):
                            continue
                        size = int(value.shape[axis])
                        if dimension in dimensions and dimensions[dimension] != size:
                            return f"registered_input_dimension_mismatch:{slot.name}:{dimension}"
                        dimensions[dimension] = size
        except Exception as exc:
            return f"registered_input_validation_failed:{type(exc).__name__}:{exc}"
        return None

    def _validate_selected_trajectories(
        self,
        *,
        request: JointSimulationRequest,
        plan: EnginePlan,
        decision: EngineDecision,
        trajectories: Sequence[SimulationTrajectory],
    ) -> None:
        """Require every emitted trajectory to bind to the executed plan."""

        atoms_by_id = {
            atom.intervention_id: atom for atom in request.intervention_atoms
        }
        for trajectory in trajectories:
            if (
                trajectory.engine_kind != decision.engine_kind
                or trajectory.method_fqn != decision.method_fqn
                or trajectory.objective_ref != plan.objective_ref
            ):
                raise JointSimulationControllerError(
                    "selected_trajectory_binding_mismatch",
                    "trajectory identity does not match the selected engine plan",
                )
            try:
                subset = tuple(atoms_by_id[atom_id] for atom_id in trajectory.atom_ids)
            except KeyError as exc:
                raise JointSimulationControllerError(
                    "selected_trajectory_binding_mismatch",
                    f"unknown intervention atom: {exc.args[0]}",
                ) from exc
            physical_run_ref = trajectory.diagnostics.get("physical_run_ref")
            expected_ref = _physical_run_ref(request, plan, decision, subset)
            if physical_run_ref != expected_ref:
                raise JointSimulationControllerError(
                    "selected_plan_execution_binding_missing",
                    "trajectory is not content-bound to the executed selected plan",
                )

    def _engine_selectors(
        self,
        record: WorldModelRecord,
    ) -> Mapping[EngineKind, Any]:
        return {
            "program_graph": self._select_program_graph_engine,
            "ncm_parallel_worlds": self._select_ncm_engine,
            "coupled_des_abm": lambda plan: self._select_coupled_engine(plan, record),
            "system_dynamics": self._select_system_dynamics_engine,
            "method_registry_estimator": self._select_registry_method_engine,
        }

    def _engine_runners(self) -> Mapping[EngineKind, Any]:
        return {
            "program_graph": self._run_program_graph_horizon,
            "ncm_parallel_worlds": self._run_ncm_horizon,
            "coupled_des_abm": self._run_coupled_horizon,
            "system_dynamics": self._run_system_dynamics_horizon,
            "method_registry_estimator": self._run_registry_method_horizon,
        }

    def _resolve_engine_semantics(
        self,
        plan: EnginePlan,
        decision: EngineDecision,
    ) -> EngineDecision:
        if decision.decision != "selected":
            return decision
        declared = plan.declared_equilibrium_semantics
        if declared is None:
            return decision
        if (
            self._settings.authority_scope == "contract_testing"
            and self._settings.trust_declared_equilibrium_semantics
        ):
            return decision.model_copy(update={"equilibrium_semantics": declared})
        supported = _SEMANTICS_BY_OUTPUT_SHAPE.get(decision.output_shape, frozenset())
        if declared in supported:
            return decision.model_copy(update={"equilibrium_semantics": declared})
        return _unsupported(
            plan,
            "equilibrium_semantics_not_backed_by_engine",
            (
                f"declared_semantics_unbacked:{declared}",
                f"output_shape:{decision.output_shape}",
            ),
        )

    def _select_program_graph_engine(self, plan: EnginePlan) -> EngineDecision:
        conditions = {item.strip().casefold() for item in plan.eligibility_conditions}
        if "cyclic" in conditions or not plan.program_graph_acyclic:
            return _unsupported(
                plan,
                "engine_eligibility_failed",
                ("cyclic_program_graph_rejected",),
            )
        required = (
            plan.program_store,
            plan.program_graph_ref,
            plan.exec_plan_ref,
            plan.program_base_state,
            plan.mechanism_registry,
            plan.slot_registry,
            plan.merge_registry,
        )
        if any(item is None for item in required):
            return _unsupported(
                plan,
                "program_graph_runtime_binding_missing",
                ("program_graph_runtime_binding_missing",),
            )
        return EngineDecision(
            engine_kind=plan.engine_kind,
            objective_ref=plan.objective_ref,
            decision="selected",
            method_fqn="foundry.execute.program_graph",
            equilibrium_semantics="dynamic_SCM",
            temporal_capability="multi_period",
            output_shape="program_state_trajectory",
            reason="engine_eligibility_satisfied",
            eligibility_source="program_graph_runtime_contract",
        )

    def _select_ncm_engine(self, plan: EnginePlan) -> EngineDecision:
        ensure_causal_methods_registered(self._registry)
        if plan.ncm_spec is None:
            return _unsupported(plan, "ncm_spec_missing")
        if not plan.ncm_spec.is_acyclic:
            return _unsupported(plan, "engine_eligibility_failed", ("cyclic_ncm_rejected",))
        method_fqn = self._registry_method_fqn(
            tags={"ncm"},
            input_slot="ncm_query_data",
            output_slot="counterfactual_result",
        )
        if method_fqn is None:
            return _unsupported(plan, "engine_registry_candidate_missing")
        return EngineDecision(
            engine_kind=plan.engine_kind,
            objective_ref=plan.objective_ref,
            decision="selected",
            method_fqn=method_fqn,
            equilibrium_semantics="static_SCM",
            temporal_capability="static",
            output_shape="static_point",
            reason="engine_eligibility_satisfied",
        )

    def _select_coupled_engine(
        self,
        plan: EnginePlan,
        record: WorldModelRecord,
    ) -> EngineDecision:
        ensure_simulation_methods_registered(self._registry)
        method_fqn = self._registry_method_fqn(
            tags={"coupled", "agent-based", "discrete-event"},
            input_slot="initial_income",
            output_slot="result",
        )
        if method_fqn is None:
            return _unsupported(plan, "engine_registry_candidate_missing")
        entry = self._registry.get_entry(method_fqn)
        assumptions = dict(entry.metadata.assumptions) if entry is not None else {}
        supported_domains = _csv_set(assumptions.get("joint_simulation_policy_domains"))
        required_structure = _csv_set(assumptions.get("joint_simulation_required_structure"))
        conditions = {item.strip().casefold() for item in plan.eligibility_conditions}
        if supported_domains and record.policy_domain.casefold() not in supported_domains:
            return _unsupported(plan, "engine_eligibility_failed", ("policy_domain_mismatch",))
        if required_structure and not required_structure.issubset(conditions):
            return _unsupported(plan, "engine_eligibility_failed", ("required_structure_missing",))
        return EngineDecision(
            engine_kind=plan.engine_kind,
            objective_ref=plan.objective_ref,
            decision="selected",
            method_fqn=method_fqn,
            equilibrium_semantics="agent_based_model",
            temporal_capability="multi_period",
            output_shape="time_series_trajectory",
            reason="engine_eligibility_satisfied",
        )

    def _select_system_dynamics_engine(self, plan: EnginePlan) -> EngineDecision:
        ensure_simulation_methods_registered(self._registry)
        method_fqn = self._registry_method_fqn(
            tags={"system-dynamics", "stock-flow"},
            input_slot="initial_stocks",
            output_slot="result",
        )
        if method_fqn is None:
            return _unsupported(plan, "engine_registry_candidate_missing")
        if "initial_stocks" not in plan.system_dynamics_state:
            return _unsupported(
                plan,
                "system_dynamics_state_missing",
                ("initial_stocks_missing",),
            )
        if "flow_matrix" not in plan.system_dynamics_state:
            return _unsupported(
                plan,
                "system_dynamics_state_missing",
                ("flow_matrix_missing",),
            )
        return EngineDecision(
            engine_kind=plan.engine_kind,
            objective_ref=plan.objective_ref,
            decision="selected",
            method_fqn=method_fqn,
            equilibrium_semantics="dynamic_SCM",
            temporal_capability="multi_period",
            output_shape="time_series_trajectory",
            reason="engine_eligibility_satisfied",
        )

    def _select_registry_method_engine(self, plan: EnginePlan) -> EngineDecision:
        ensure_causal_methods_registered(self._registry)
        ensure_simulation_methods_registered(self._registry)
        if plan.method_fqn is None:
            return _unsupported(plan, "method_registry_fqn_missing")
        entry = self._registry.get_entry(plan.method_fqn)
        if entry is None:
            return _unsupported(
                plan,
                "engine_registry_candidate_missing",
                ("method_fqn_not_registered",),
            )
        if self._settings.trust_method_tags_for_semantics:
            temporal = _entry_temporal_capability_from_tags(
                entry.metadata.assumptions,
                entry.metadata.tags,
            )
            semantics = _entry_equilibrium_semantics_from_tags(
                entry.metadata.assumptions,
                entry.metadata.tags,
                temporal,
            )
            output_shape: EngineOutputShape = "time_series_trajectory"
        else:
            output_shape = _entry_output_shape(entry.metadata.assumptions, entry.signature)
            declared = plan.declared_equilibrium_semantics or _declared_entry_semantics(
                entry.metadata.assumptions
            )
            if declared is not None and declared not in _SEMANTICS_BY_OUTPUT_SHAPE[output_shape]:
                return _unsupported(
                    plan,
                    "method_output_shape_does_not_back_semantics",
                    (
                        f"output_shape:{output_shape}",
                        f"declared_semantics_unbacked:{declared}",
                    ),
                )
            if output_shape == "unsupported":
                return _unsupported(
                    plan,
                    "method_output_shape_does_not_back_semantics",
                    ("method_output_shape_missing",),
                )
            temporal = _temporal_capability_for_output_shape(output_shape)
            semantics = declared or _default_semantics_for_output_shape(output_shape)
        if temporal == "unsupported":
            return _unsupported(
                plan,
                "method_output_shape_does_not_back_semantics",
                (f"output_shape:{output_shape}",),
            )
        if temporal == "multi_period" and "result" in entry.signature.output_slot_names:
            required_inputs = set(entry.signature.input_slot_names)
            state_keys = set(plan.system_dynamics_state) | set(plan.coupled_state)
            missing = required_inputs - state_keys
            if missing:
                return _unsupported(
                    plan,
                    "method_registry_state_missing",
                    tuple(f"missing_input_slot:{item}" for item in sorted(missing)),
                )
        return EngineDecision(
            engine_kind=plan.engine_kind,
            objective_ref=plan.objective_ref,
            decision="selected",
            method_fqn=plan.method_fqn,
            equilibrium_semantics=semantics,
            temporal_capability=temporal,
            output_shape=output_shape,
            reason="engine_eligibility_satisfied",
            eligibility_source="method_registry_output_shape_contract",
        )

    def _registry_method_fqn(
        self,
        *,
        tags: set[str],
        input_slot: str,
        output_slot: str,
    ) -> str | None:
        for signature in self._registry.query(tags=tags):
            if (
                input_slot in signature.input_slot_names
                and output_slot in signature.output_slot_names
            ):
                return signature.fqn
        return None

    def _run_program_graph_horizon(
        self,
        request: JointSimulationRequest,
        plan: EnginePlan,
        decision: EngineDecision,
    ) -> list[SimulationTrajectory]:
        if decision.method_fqn is None:
            return []

        def run_once(
            run_request: JointSimulationRequest,
            run_plan: EnginePlan,
            run_decision: EngineDecision,
            run_level: RunLevel,
            subset: tuple[InterventionAtomBinding, ...],
            replication_seed: int,
        ) -> SimulationTrajectory:
            method_fqn = _selected_method_fqn(run_decision)
            current_state = run_plan.program_base_state
            points: list[TrajectoryPoint] = []
            state_delta_refs: list[str] = []
            metrics_refs: list[str] = []
            for step in run_request.horizon.steps():
                artifacts = execute_program_graph(
                    run_plan.program_store,
                    program_ref=run_plan.program_graph_ref,
                    exec_plan_ref=run_plan.exec_plan_ref,
                    base_state=current_state,
                    mechanism_registry=run_plan.mechanism_registry,
                    slot_registry=run_plan.slot_registry,
                    merge_registry=run_plan.merge_registry,
                    selector_field_registry=run_plan.selector_field_registry,
                    constraint_registry=run_plan.constraint_registry,
                    step=step,
                    seed=int(replication_seed) + int(step),
                    base_ref=run_plan.program_base_ref,
                    parameter_overrides=_program_parameter_overrides(subset, run_plan),
                )
                current_state = apply_state_delta(
                    run_plan.program_store,
                    base_state=current_state,
                    state_delta_ref=artifacts.state_delta_ref,
                    slot_registry=run_plan.slot_registry,
                    merge_registry=run_plan.merge_registry,
                )
                state_delta_refs.append(str(artifacts.state_delta_ref.artifact_id))
                metrics_refs.append(str(artifacts.metrics_ref.artifact_id))
                outcomes = _program_graph_outcomes(
                    current_state,
                    run_request.selected_outcomes,
                    run_plan,
                )
                points.append(
                    TrajectoryPoint(
                        step=step,
                        outcomes=outcomes,
                        effect={
                            outcome: _effect_for_outcome(
                                run_request, outcome, outcomes[outcome]
                            )
                            for outcome in run_request.selected_outcomes
                        },
                        engine_state={
                            "state_delta_ref": state_delta_refs[-1],
                            "metrics_ref_produced": True,
                        },
                    )
                )
            return SimulationTrajectory(
                run_level=run_level,
                atom_ids=tuple(atom.intervention_id for atom in subset),
                engine_kind=run_decision.engine_kind,
                method_fqn=method_fqn,
                objective_ref=run_plan.objective_ref,
                points=tuple(points),
                diagnostics={
                    "engine": "execute_program_graph",
                    "horizon_loop": True,
                    "state_delta_refs": state_delta_refs,
                    "metrics_ref_count": len(metrics_refs),
                },
            )

        return _run_cached_replicates(request, plan, decision, run_once)

    def _run_ncm_horizon(
        self,
        request: JointSimulationRequest,
        plan: EnginePlan,
        decision: EngineDecision,
    ) -> list[SimulationTrajectory]:
        if plan.ncm_spec is None or decision.method_fqn is None:
            return []

        def run_once(
            run_request: JointSimulationRequest,
            run_plan: EnginePlan,
            run_decision: EngineDecision,
            run_level: RunLevel,
            subset: tuple[InterventionAtomBinding, ...],
            replication_seed: int,
        ) -> SimulationTrajectory:
            method_fqn = _selected_method_fqn(run_decision)
            return _ncm_run_once(
                run_request,
                run_plan,
                run_decision,
                self._registry.get(method_fqn).pure_step,
                run_level,
                subset,
                replication_seed,
            )

        return _run_cached_replicates(request, plan, decision, run_once)

    def _run_coupled_horizon(
        self,
        request: JointSimulationRequest,
        plan: EnginePlan,
        decision: EngineDecision,
    ) -> list[SimulationTrajectory]:
        if decision.method_fqn is None:
            return []

        def run_once(
            run_request: JointSimulationRequest,
            run_plan: EnginePlan,
            run_decision: EngineDecision,
            run_level: RunLevel,
            subset: tuple[InterventionAtomBinding, ...],
            replication_seed: int,
        ) -> SimulationTrajectory:
            method_fqn = _selected_method_fqn(run_decision)
            method = self._registry.get(method_fqn)
            params = _coupled_params_for_subset(run_plan, subset)
            requested_steps = run_request.horizon.steps()
            params["n_steps"] = max(1, len(requested_steps) - 1)
            params["seed"] = int(replication_seed)
            output = method.pure_step(run_plan.coupled_state, params)
            if not isinstance(output, Mapping):
                raise JointSimulationControllerError(
                    "coupled_simulation_result_missing"
                    if output is None
                    else "coupled_simulation_result_malformed"
                )
            raw_result = output.get("result")
            if raw_result is None:
                raise JointSimulationControllerError("coupled_simulation_result_missing")
            if not isinstance(raw_result, Mapping):
                raise JointSimulationControllerError("coupled_simulation_result_malformed")
            if not raw_result:
                raise JointSimulationControllerError("coupled_simulation_result_missing")
            result = {
                **raw_result,
                "initial_queue_length": _required_finite_scalar(
                    params.get("initial_queue_length", 0.0),
                    field="initial_queue_length",
                    missing_code="coupled_queue_trajectory_incomplete",
                    malformed_code="coupled_queue_trajectory_non_numeric",
                    non_finite_code="coupled_queue_trajectory_non_finite",
                ),
            }
            points: list[TrajectoryPoint] = []
            terminal_index = len(requested_steps) - 1
            for index, step in enumerate(requested_steps):
                outcomes = _coupled_outcomes(
                    result,
                    run_request.selected_outcomes,
                    index,
                    terminal_index=terminal_index,
                )
                effects = {
                    outcome: _effect_for_outcome(run_request, outcome, value)
                    for outcome, value in outcomes.items()
                }
                queue_value = _coupled_queue_value(result, index)
                points.append(
                    TrajectoryPoint(
                        step=step,
                        outcomes=outcomes,
                        effect=effects,
                        engine_state={
                            "coupled_summary": result.get("summary", {}),
                            "queue_length": queue_value,
                        },
                    )
                )
            return SimulationTrajectory(
                run_level=run_level,
                atom_ids=tuple(atom.intervention_id for atom in subset),
                engine_kind=run_decision.engine_kind,
                method_fqn=run_decision.method_fqn,
                objective_ref=run_plan.objective_ref,
                points=tuple(points),
                diagnostics={
                    "engine": "CoupledPolicySimulationEstimator",
                    "horizon_loop": True,
                    "temporal_capability": "multi_period",
                },
            )

        return _run_cached_replicates(request, plan, decision, run_once)

    def _run_system_dynamics_horizon(
        self,
        request: JointSimulationRequest,
        plan: EnginePlan,
        decision: EngineDecision,
    ) -> list[SimulationTrajectory]:
        if decision.method_fqn is None:
            return []

        def run_once(
            run_request: JointSimulationRequest,
            run_plan: EnginePlan,
            run_decision: EngineDecision,
            run_level: RunLevel,
            subset: tuple[InterventionAtomBinding, ...],
            replication_seed: int,
        ) -> SimulationTrajectory:
            method_fqn = _selected_method_fqn(run_decision)
            method = self._registry.get(method_fqn)
            state = _system_dynamics_state_for_subset(run_plan, subset)
            params = {
                **run_plan.system_dynamics_params,
                "n_steps": max(1, len(run_request.horizon.steps()) - 1),
            }
            params.setdefault("dt", float(run_request.horizon.step))
            params["seed"] = int(replication_seed)
            output = method.pure_step(state, params)
            if not isinstance(output, Mapping):
                raise JointSimulationControllerError(
                    "system_dynamics_result_missing",
                    method_fqn,
                )
            result = output.get("result", {})
            if not isinstance(result, Mapping):
                raise JointSimulationControllerError(
                    "system_dynamics_result_missing",
                    method_fqn,
                )
            stock_trajectory = result.get("trajectory", [])
            if (
                stock_trajectory is None
                or isinstance(stock_trajectory, Mapping | str | bytes | bytearray)
            ):
                raise JointSimulationControllerError(
                    "system_dynamics_trajectory_missing",
                    method_fqn,
                )
            requested_steps = run_request.horizon.steps()
            is_stock_flow_owner = method is StockFlowSystemDynamicsEstimator
            terminal_scalar_fields = (
                frozenset({"mass_balance", "final_stocks"})
                if is_stock_flow_owner
                else frozenset()
            )
            terminal_index = len(requested_steps) - 1
            try:
                trajectory_length = len(stock_trajectory)
            except TypeError as exc:
                raise JointSimulationControllerError(
                    "system_dynamics_trajectory_missing",
                    method_fqn,
                ) from exc
            if trajectory_length == 0:
                raise JointSimulationControllerError(
                    "system_dynamics_trajectory_missing",
                    method_fqn,
                )
            unrequested_points = max(0, trajectory_length - len(requested_steps))
            if unrequested_points and not (
                len(requested_steps) == 1 and unrequested_points == 1
            ):
                raise JointSimulationControllerError(
                    "system_dynamics_trajectory_overlong",
                    f"expected {len(requested_steps)}, received {trajectory_length}",
                )
            covered_count = min(trajectory_length, len(requested_steps))
            points: list[TrajectoryPoint] = []
            for index, step in enumerate(requested_steps[:covered_count]):
                stock_values = stock_trajectory[index]
                outcomes = _system_dynamics_outcomes(
                    result,
                    stock_values,
                    run_request.selected_outcomes,
                    run_plan,
                    point_is_terminal=index == terminal_index,
                    terminal_scalar_fields=terminal_scalar_fields,
                )
                points.append(
                    TrajectoryPoint(
                        step=step,
                        outcomes=outcomes,
                        effect={
                            outcome: _effect_for_outcome(
                                run_request, outcome, outcomes[outcome]
                            )
                            for outcome in outcomes
                        },
                        engine_state={
                            "stock_values": _json_ready(stock_values),
                        },
                    )
                )
            return SimulationTrajectory(
                run_level=run_level,
                atom_ids=tuple(atom.intervention_id for atom in subset),
                engine_kind=run_decision.engine_kind,
                method_fqn=method_fqn,
                objective_ref=run_plan.objective_ref,
                points=tuple(points),
                diagnostics={
                    "engine": "StockFlowSystemDynamicsEstimator",
                    "horizon_loop": True,
                    "temporal_capability": "multi_period",
                    "unrequested_output_points": unrequested_points,
                    "producer_time_grid_binding": "not_established",
                },
            )

        return _run_cached_replicates(request, plan, decision, run_once)

    def _run_registry_method_horizon(
        self,
        request: JointSimulationRequest,
        plan: EnginePlan,
        decision: EngineDecision,
    ) -> list[SimulationTrajectory]:
        if decision.method_fqn is None:
            return []

        def run_once(
            run_request: JointSimulationRequest,
            run_plan: EnginePlan,
            run_decision: EngineDecision,
            run_level: RunLevel,
            subset: tuple[InterventionAtomBinding, ...],
            replication_seed: int,
        ) -> SimulationTrajectory:
            method_fqn = _selected_method_fqn(run_decision)
            method = self._registry.get(method_fqn)
            state = _method_state_for_subset(run_plan, subset)
            params = {
                **run_plan.system_dynamics_params,
                "n_steps": max(1, len(run_request.horizon.steps()) - 1),
            }
            params.setdefault("dt", float(run_request.horizon.step))
            params["seed"] = int(replication_seed)
            output = method.pure_step(state, params)
            if not isinstance(output, Mapping):
                raise JointSimulationControllerError(
                    "method_registry_result_missing",
                    method_fqn,
                )
            result = output.get("result", {})
            if not isinstance(result, Mapping):
                raise JointSimulationControllerError(
                    "method_registry_result_missing",
                    method_fqn,
                )
            raw_trajectory = result.get("trajectory")
            if raw_trajectory is None or isinstance(
                raw_trajectory,
                Mapping | str | bytes | bytearray,
            ):
                raise JointSimulationControllerError(
                    "method_registry_temporal_output_missing",
                    method_fqn,
                )
            try:
                trajectory_length = len(raw_trajectory)
            except TypeError as exc:
                raise JointSimulationControllerError(
                    "trajectory_coverage_incomplete",
                    method_fqn,
                ) from exc
            requested_steps = run_request.horizon.steps()
            covered_count = min(trajectory_length, len(requested_steps))
            if covered_count == 0:
                raise JointSimulationControllerError(
                    "trajectory_coverage_incomplete",
                    method_fqn,
                )
            if trajectory_length > len(requested_steps):
                raise JointSimulationControllerError(
                    "method_registry_trajectory_overlong",
                    f"expected {len(requested_steps)}, received {trajectory_length}",
                )
            points: list[TrajectoryPoint] = []
            for index, step in enumerate(requested_steps[:covered_count]):
                state_values = raw_trajectory[index]
                outcomes = _system_dynamics_outcomes(
                    result,
                    state_values,
                    run_request.selected_outcomes,
                    run_plan,
                )
                points.append(
                    TrajectoryPoint(
                        step=step,
                        outcomes=outcomes,
                        effect={
                            outcome: _effect_for_outcome(
                                run_request, outcome, outcomes[outcome]
                            )
                            for outcome in run_request.selected_outcomes
                        },
                        engine_state={
                            "stock_values": _json_ready(state_values),
                        },
                    )
                )
            return SimulationTrajectory(
                run_level=run_level,
                atom_ids=tuple(atom.intervention_id for atom in subset),
                engine_kind=run_decision.engine_kind,
                method_fqn=method_fqn,
                objective_ref=run_plan.objective_ref,
                points=tuple(points),
                diagnostics={
                    "engine": method_fqn,
                    "horizon_loop": True,
                    "temporal_capability": "multi_period",
                    "coverage_status": (
                        "complete" if covered_count == len(requested_steps) else "partial"
                    ),
                    "covered_steps": requested_steps[:covered_count],
                    "requested_steps": requested_steps,
                    "hold_last": False,
                    "producer_time_grid_binding": "not_established",
                },
            )

        return _run_cached_replicates(request, plan, decision, run_once)


def _unsupported(
    plan: EnginePlan,
    reason: str,
    blockers: Sequence[str] | None = None,
) -> EngineDecision:
    return EngineDecision(
        engine_kind=plan.engine_kind,
        objective_ref=plan.objective_ref,
        decision="unsupported",
        equilibrium_semantics="unsupported",
        temporal_capability="unsupported",
        reason=reason,
        blockers=tuple(blockers or (reason,)),
    )


def _selected_method_fqn(decision: EngineDecision) -> str:
    """Require the registry identity carried by the engine decision snapshot."""

    if decision.method_fqn is None:
        raise JointSimulationControllerError("simulation_engine_method_binding_missing")
    return decision.method_fqn


def _resolve_coupling_support(
    *,
    request: JointSimulationRequest,
    engine_kind: EngineKind,
    gate_disabled: bool = False,
) -> _CouplingSupportDecision:
    if request.coupling_graph is None:
        return _CouplingSupportDecision(
            classification=None,
            support_status="not_applicable",
            blockers=(),
            coupling_classes=(),
            general_equilibrium=False,
            gate_blocked=False,
        )
    classification = classify_coupling(request.coupling_graph)
    classes = _coupling_classes(classification)
    general_equilibrium = classification.coupling_regime in _SYSTEM_WIDE_COUPLING_REGIMES
    blockers = _coupling_support_blockers(
        engine_kind=engine_kind,
        classes=classes,
        general_equilibrium=general_equilibrium,
    )
    if blockers and not gate_disabled:
        status: CouplingSupportStatus = "unsupported"
    else:
        status = "supported"
    return _CouplingSupportDecision(
        classification=classification,
        support_status=status,
        blockers=blockers,
        coupling_classes=classes,
        general_equilibrium=general_equilibrium,
        gate_blocked=bool(blockers) and not gate_disabled,
    )


def _aggregate_no_run_coupling_support(
    *,
    request: JointSimulationRequest,
    decisions: Sequence[EngineDecision],
    gate_disabled: bool = False,
) -> _CouplingSupportDecision:
    """Build a fail-closed coupling posture when no candidate was selected."""

    supports = tuple(
        _resolve_coupling_support(
            request=request,
            engine_kind=decision.engine_kind,
            gate_disabled=gate_disabled,
        )
        for decision in decisions
    )
    reference = supports[0] if supports else None
    coupling_blockers = tuple(
        dict.fromkeys(
            blocker
            for support in supports
            for blocker in support.blockers
        )
    )
    blockers = (*coupling_blockers, "all_engine_candidates_rejected")
    gate_blocked = any(support.gate_blocked for support in supports)
    support_status: CouplingSupportStatus = (
        "unsupported"
        if gate_blocked
        else ("not_applicable" if reference is None else reference.support_status)
    )
    return _CouplingSupportDecision(
        classification=None if reference is None else reference.classification,
        support_status=support_status,
        blockers=blockers,
        coupling_classes=() if reference is None else reference.coupling_classes,
        general_equilibrium=False if reference is None else reference.general_equilibrium,
        gate_blocked=gate_blocked,
    )


def _coupling_classes(
    classification: CouplingRegimeClassification,
) -> tuple[BoundaryCouplingKind, ...]:
    classes = tuple(
        sorted(
            {
                row.coupling_kind
                for row in classification.boundary_classifications
            }
        )
    )
    if classes:
        return classes
    if classification.coupling_regime == "modular":
        return ("independent",)
    return ("unknown",)


def _coupling_support_blockers(
    *,
    engine_kind: EngineKind,
    classes: Sequence[BoundaryCouplingKind],
    general_equilibrium: bool,
) -> tuple[str, ...]:
    blockers: list[str] = []
    for coupling_class in classes:
        supported_engines = _COUPLING_ENGINES_BY_KIND.get(coupling_class, frozenset())
        if engine_kind not in supported_engines:
            blockers.append(f"unsupported_coupling_class:{coupling_class}")
    if general_equilibrium:
        blockers.append("general_equilibrium_coupling_not_grounded_by_available_engine")
    return tuple(dict.fromkeys(blockers))


def _entry_output_shape(
    assumptions: Mapping[str, Any],
    signature: _MethodSignatureLike,
) -> EngineOutputShape:
    declared = str(assumptions.get("joint_simulation_output_shape", "")).casefold()
    if declared in _OUTPUT_SHAPE_VALUES:
        return declared  # type: ignore[return-value]
    output_slots = {str(item) for item in getattr(signature, "output_slot_names", frozenset())}
    if "counterfactual_result" in output_slots:
        return "static_point"
    return "unsupported"


def _temporal_capability_for_output_shape(output_shape: EngineOutputShape) -> TemporalCapability:
    if output_shape == "static_point":
        return "static"
    if output_shape in {"time_series_trajectory", "program_state_trajectory"}:
        return "multi_period"
    return "unsupported"


def _declared_entry_semantics(assumptions: Mapping[str, Any]) -> EquilibriumSemantics | None:
    declared = str(assumptions.get("joint_simulation_equilibrium_semantics", ""))
    if declared in {
        "none",
        "static_SCM",
        "dynamic_SCM",
        "time_unrolled_SCM",
        "equilibrium_SCM",
        "game_model",
        "agent_based_model",
        "unsupported",
    }:
        return declared  # type: ignore[return-value]
    return None


def _default_semantics_for_output_shape(output_shape: EngineOutputShape) -> EquilibriumSemantics:
    if output_shape == "static_point":
        return "static_SCM"
    if output_shape in {"time_series_trajectory", "program_state_trajectory"}:
        return "dynamic_SCM"
    return "unsupported"


def _entry_temporal_capability_from_tags(
    assumptions: Mapping[str, Any],
    tags: frozenset[str],
) -> TemporalCapability:
    declared = str(assumptions.get("joint_simulation_temporal_capability", "")).casefold()
    normalized_tags = {str(item).casefold() for item in tags}
    if "ncm" in normalized_tags or "static-aging" in normalized_tags:
        return "static"
    if normalized_tags & {
        "system-dynamics",
        "stock-flow",
        "discrete-event",
        "agent-based",
        "dynamic",
        "time-series",
        "coupled",
    }:
        return "multi_period"
    if declared in {"static", "multi_period"}:
        return "unsupported"
    return "unsupported"


def _entry_equilibrium_semantics_from_tags(
    assumptions: Mapping[str, Any],
    tags: frozenset[str],
    temporal: TemporalCapability,
) -> EquilibriumSemantics:
    declared = str(assumptions.get("joint_simulation_equilibrium_semantics", ""))
    normalized_tags = {str(item).casefold() for item in tags}
    if declared in {
        "none",
        "static_SCM",
        "dynamic_SCM",
        "time_unrolled_SCM",
        "equilibrium_SCM",
        "game_model",
        "agent_based_model",
        "unsupported",
    }:
        return declared  # type: ignore[return-value]
    if "ncm" in normalized_tags:
        return "static_SCM"
    if normalized_tags & {"agent-based", "discrete-event", "coupled"}:
        return "agent_based_model"
    if normalized_tags & {"system-dynamics", "stock-flow", "dynamic", "time-series"}:
        return "dynamic_SCM"
    if temporal == "static":
        return "static_SCM"
    if temporal == "multi_period":
        return "dynamic_SCM"
    return "unsupported"


def _atom_subsets(
    atoms: Sequence[InterventionAtomBinding],
) -> list[tuple[RunLevel, tuple[InterventionAtomBinding, ...]]]:
    subsets: list[tuple[RunLevel, tuple[InterventionAtomBinding, ...]]] = []
    for atom in atoms:
        subsets.append(("individual", (atom,)))
    for pair in itertools.combinations(atoms, 2):
        subsets.append(("pairwise", tuple(pair)))
    subsets.append(("joint", tuple(atoms)))
    return subsets


def _validate_atom_assignment_compatibility(request: JointSimulationRequest) -> None:
    """Refuse ambiguous direct writes before any singleton or joint run starts.

    ``JointSimulationRequest`` has no per-atom dependency declaration, so tuple
    position is not promoted into sequential execution semantics here.
    """

    writes: dict[str, tuple[str, float | None]] = {}
    for atom in request.intervention_atoms:
        for assignment in atom.causal_do_expr.assignments:
            binding = request.world_model_record.slot_binding(assignment.variable)
            if binding is None:
                binding = next(
                    (
                        candidate
                        for slot_id in atom.target_world_slots
                        if (candidate := request.world_model_record.slot_binding(slot_id))
                        is not None
                        and candidate.state_path == assignment.variable
                    ),
                    None,
                )
            target = (
                "state_path:" + binding.state_path
                if binding is not None and binding.state_path
                else "world_slot:" + assignment.variable
            )
            value = _numeric_assignment_value(assignment)

            previous = writes.get(target)
            if previous is not None:
                previous_atom, previous_value = previous
                if value is None or previous_value is None or value != previous_value:
                    raise JointSimulationControllerError(
                        "intervention_assignment_conflict",
                        (
                            f"{target} is assigned incompatibly by "
                            f"{previous_atom!r} and {atom.intervention_id!r}"
                        ),
                    )
            else:
                writes[target] = (atom.intervention_id, value)


def _execution_assignment_conflict(
    request: JointSimulationRequest,
    plan: EnginePlan,
) -> str | None:
    """Refuse conflicting raw writes before the first physical run.

    Compatible overrides must have the same content-bound typed value; this
    does not infer equivalence from a method's later coercion or imply an atom
    sequence. State-path prefixes also conflict across atoms because replacing
    a container and editing its child have no declared unordered merge law.
    """

    writes: list[tuple[tuple[str, ...], str, str | None]] = []
    for atom in request.intervention_atoms:
        atom_writes: list[tuple[tuple[str, ...], object, bool]] = []
        for assignment in atom.causal_do_expr.assignments:
            target = _engine_variable(assignment.variable, plan)
            value = _numeric_assignment_value(assignment)
            atom_writes.append((("engine_state", *target.split(".")), value, value is not None))
        if plan.engine_kind == "program_graph":
            for node_id, values in plan.program_parameter_overrides_by_atom.get(
                atom.intervention_id, {}
            ).items():
                atom_writes.extend(
                    (("program_parameter", str(node_id), str(name)), value, True)
                    for name, value in values.items()
                )
        if plan.engine_kind == "system_dynamics" or (
            plan.engine_kind == "method_registry_estimator" and plan.system_dynamics_state
        ):
            atom_writes.extend(
                (("engine_state", *path), value, True)
                for path, value in _state_override_writes(
                    plan.system_dynamics_state_overrides_by_atom.get(atom.intervention_id, {})
                )
            )
        for target, value, established in atom_writes:
            identity = (
                gy_recorded_content_hash(_typed_execution_payload(value)) if established else None
            )
            for previous_target, previous_atom, previous_identity in writes:
                if previous_atom == atom.intervention_id:
                    continue
                shared_prefix = min(len(target), len(previous_target))
                if target[:shared_prefix] != previous_target[:shared_prefix]:
                    continue
                if target != previous_target or identity is None or identity != previous_identity:
                    variable = ".".join(target[1:])
                    return (
                        f"program_parameter:{variable}"
                        if target[0] == "program_parameter"
                        else variable
                    )
            writes.append((target, atom.intervention_id, identity))
    return None


def _state_override_writes(
    values: Mapping[str, Any],
    prefix: tuple[str, ...] = (),
) -> list[tuple[tuple[str, ...], object]]:
    """Enumerate the leaf writes of the existing recursive mapping merge."""

    writes: list[tuple[tuple[str, ...], object]] = []
    for name, value in values.items():
        path = (*prefix, str(name))
        if isinstance(value, Mapping) and value:
            writes.extend(_state_override_writes(value, path))
        else:
            writes.append((path, value))
    return writes


def _numeric_assignment_value(assignment: CausalAssignmentProjection) -> float | None:
    if assignment.value is None or assignment.value_expr is not None:
        return None
    try:
        numeric_value = float(assignment.value)
    except (TypeError, ValueError, OverflowError):
        return None
    return numeric_value if np.isfinite(numeric_value) else None


def _ncm_intervention(
    atoms: Sequence[InterventionAtomBinding],
    plan: EnginePlan,
) -> dict[str, float]:
    intervention: dict[str, float] = {}
    for atom in atoms:
        for assignment in atom.causal_do_expr.assignments:
            variable = _engine_variable(assignment.variable, plan)
            if assignment.value is None:
                raise JointSimulationControllerError(
                    "value_expr_intervention_not_supported_by_ncm_controller",
                    assignment.variable,
                )
            value = float(assignment.value)
            previous = intervention.get(variable)
            if previous is not None and previous != value:
                raise JointSimulationControllerError(
                    "ncm_intervention_conflict",
                    variable,
                )
            intervention[variable] = value
    return intervention


def _program_parameter_overrides(
    atoms: Sequence[InterventionAtomBinding],
    plan: EnginePlan,
) -> dict[str, dict[str, Any]] | None:
    overrides: dict[str, dict[str, Any]] = {}
    for atom in atoms:
        atom_overrides = plan.program_parameter_overrides_by_atom.get(atom.intervention_id, {})
        for node_id, values in atom_overrides.items():
            overrides.setdefault(str(node_id), {}).update(dict(values))
    return overrides or None


def _coupled_params_for_subset(
    plan: EnginePlan,
    atoms: Sequence[InterventionAtomBinding],
) -> dict[str, Any]:
    params = deepcopy(plan.coupled_params)
    for atom in atoms:
        for assignment in atom.causal_do_expr.assignments:
            if assignment.value is None:
                raise JointSimulationControllerError(
                    "value_expr_intervention_not_supported_by_coupled_controller",
                    assignment.variable,
                )
            target = _engine_variable(assignment.variable, plan)
            params[target] = float(assignment.value)
    return params


def _coupled_queue_value(result: Mapping[str, Any], index: int) -> float:
    if index == 0:
        value = result.get("initial_queue_length")
    else:
        queue = result.get("queue_length_trajectory")
        if queue is None:
            value = None
        elif (
            not isinstance(queue, Sequence | np.ndarray)
            or isinstance(queue, str | bytes | bytearray)
            or (isinstance(queue, np.ndarray) and queue.ndim != 1)
        ):
            raise JointSimulationControllerError(
                "coupled_queue_trajectory_non_numeric", f"queue_length@{index}"
            )
        elif index - 1 >= len(queue):
            value = None
        else:
            value = queue[index - 1]
    return _required_finite_scalar(
        value,
        field=f"queue_length@{index}",
        missing_code="coupled_queue_trajectory_incomplete",
        malformed_code="coupled_queue_trajectory_non_numeric",
        non_finite_code="coupled_queue_trajectory_non_finite",
    )


def _coupled_outcomes(
    result: Mapping[str, Any],
    selected_outcomes: Sequence[str],
    index: int,
    *,
    terminal_index: int,
) -> dict[str, float]:
    outcomes: dict[str, float] = {}
    for outcome in selected_outcomes:
        if outcome == "final_queue_length":
            outcomes[outcome] = _coupled_queue_value(result, index)
        else:
            if index != terminal_index:
                continue
            value = result.get(outcome)
            if value is None:
                raise JointSimulationControllerError(
                    "coupled_outcome_binding_missing",
                    outcome,
                )
            outcomes[outcome] = _required_finite_scalar(
                value,
                field=outcome,
                missing_code="coupled_outcome_binding_missing",
                malformed_code="coupled_outcome_non_numeric",
                non_finite_code="coupled_outcome_non_finite",
                allow_array_mean=True,
            )
    return outcomes


def _method_state_for_subset(
    plan: EnginePlan,
    atoms: Sequence[InterventionAtomBinding],
) -> dict[str, Any]:
    if plan.system_dynamics_state:
        return _system_dynamics_state_for_subset(plan, atoms)
    if plan.coupled_state:
        return deepcopy(plan.coupled_state)
    raise JointSimulationControllerError(
        "method_registry_state_missing",
        plan.method_fqn or plan.engine_kind,
    )


def _program_graph_outcomes(
    state: object,
    selected_outcomes: Sequence[str],
    plan: EnginePlan,
) -> dict[str, float]:
    outcomes: dict[str, float] = {}
    for outcome in selected_outcomes:
        path = plan.variable_map.get(outcome, outcome)
        outcomes[outcome] = _state_path_scalar(state, path)
    return outcomes


def _state_path_scalar(state: object, path: str) -> float:
    value = state
    try:
        for part in path.split("."):
            value = value[part] if isinstance(value, Mapping) else getattr(value, part)
    except (AttributeError, IndexError, KeyError, TypeError) as exc:
        raise JointSimulationControllerError(
            "program_graph_outcome_binding_missing",
            path,
        ) from exc
    return _required_finite_scalar(
        value,
        field=path,
        missing_code="program_graph_outcome_binding_missing",
        malformed_code="program_graph_outcome_non_numeric",
        non_finite_code="program_graph_outcome_non_finite",
        allow_array_mean=True,
    )


def _engine_variable(variable: str, plan: EnginePlan) -> str:
    return plan.variable_map.get(variable, variable)


def _ncm_outcomes(
    output: Mapping[str, Any],
    selected_outcomes: Sequence[str],
    plan: EnginePlan,
) -> dict[str, float]:
    if output is None:
        raise JointSimulationControllerError("ncm_world_summaries_missing")
    if not isinstance(output, Mapping):
        raise JointSimulationControllerError("ncm_world_summaries_malformed")
    payload = output.get("counterfactual_result")
    if payload is None:
        raise JointSimulationControllerError("ncm_world_summaries_missing")
    if not isinstance(payload, Mapping):
        raise JointSimulationControllerError("ncm_world_summaries_malformed")
    summaries = payload.get("world_summaries")
    if summaries is None:
        raise JointSimulationControllerError("ncm_world_summaries_missing")
    if (
        not isinstance(summaries, Sequence)
        or isinstance(summaries, str | bytes | bytearray)
    ):
        raise JointSimulationControllerError("ncm_world_summaries_malformed")
    if not summaries:
        raise JointSimulationControllerError("ncm_world_summaries_missing")
    if not isinstance(summaries[0], Mapping):
        raise JointSimulationControllerError("ncm_world_summaries_malformed")
    summary = summaries[0]
    outcomes: dict[str, float] = {}
    for outcome in selected_outcomes:
        engine_outcome = _engine_variable(outcome, plan)
        stats = summary.get(engine_outcome)
        if stats is None:
            raise JointSimulationControllerError("ncm_outcome_missing", engine_outcome)
        if not isinstance(stats, Mapping):
            raise JointSimulationControllerError("ncm_outcome_malformed", engine_outcome)
        if "mean" not in stats:
            raise JointSimulationControllerError("ncm_outcome_missing", engine_outcome)
        outcomes[outcome] = _required_finite_scalar(
            stats["mean"],
            field=engine_outcome,
            missing_code="ncm_outcome_missing",
            malformed_code="ncm_outcome_non_numeric",
            non_finite_code="ncm_outcome_non_finite",
        )
    return outcomes


def _ncm_run_once(
    request: JointSimulationRequest,
    plan: EnginePlan,
    decision: EngineDecision,
    pure_step: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]],
    run_level: RunLevel,
    subset: tuple[InterventionAtomBinding, ...],
    replication_seed: int,
) -> SimulationTrajectory:
    """Run one registered NCM query through the adapter's canonical projection."""

    if plan.ncm_spec is None or decision.method_fqn is None:
        raise JointSimulationControllerError("ncm_engine_binding_missing")
    intervention = _ncm_intervention(subset, plan)
    evidence_state, _ = _effective_evidence_state(request)
    evidence = {
        _engine_variable(variable, plan): float(value)
        for variable, value in evidence_state.items()
    }
    output = pure_step(
        {
            "ncm_query_data": NCMQueryData(
                ncm_spec=plan.ncm_spec,
                evidence=evidence,
                interventions=[intervention],
                query_vars=[
                    _engine_variable(outcome, plan)
                    for outcome in request.selected_outcomes
                ],
                n_samples=1,
            )
        },
        {"__seed__": int(replication_seed)},
    )
    outcomes = _ncm_outcomes(output, request.selected_outcomes, plan)
    point = TrajectoryPoint(
        step=request.horizon.start,
        outcomes=outcomes,
        effect={
            outcome: _effect_for_outcome(request, outcome, outcomes[outcome])
            for outcome in request.selected_outcomes
        },
        engine_state={"intervention": dict(intervention)},
    )
    return SimulationTrajectory(
        run_level=run_level,
        atom_ids=tuple(atom.intervention_id for atom in subset),
        engine_kind=decision.engine_kind,
        method_fqn=decision.method_fqn,
        objective_ref=plan.objective_ref,
        points=(point,),
        diagnostics={
            "engine": "NCMEngineMethod",
            "horizon_loop": False,
            "temporal_capability": "static",
        },
    )


def _system_dynamics_state_for_subset(
    plan: EnginePlan,
    atoms: Sequence[InterventionAtomBinding],
) -> dict[str, Any]:
    state = deepcopy(plan.system_dynamics_state)
    for atom in atoms:
        _merge_mapping(
            state,
            plan.system_dynamics_state_overrides_by_atom.get(atom.intervention_id, {}),
        )
        for assignment in atom.causal_do_expr.assignments:
            if assignment.value is None:
                raise JointSimulationControllerError(
                    "value_expr_intervention_not_supported_by_system_dynamics_controller",
                    assignment.variable,
                )
            target = _engine_variable(assignment.variable, plan)
            if target not in state and "." not in target:
                raise JointSimulationControllerError(
                    "system_dynamics_intervention_binding_missing",
                    assignment.variable,
                )
            _assign_path_value(state, target, float(assignment.value))
    return state


def _system_dynamics_outcomes(
    result: Mapping[str, Any],
    stock_values: object,
    selected_outcomes: Sequence[str],
    plan: EnginePlan,
    *,
    point_is_terminal: bool = False,
    terminal_scalar_fields: frozenset[str] = frozenset(),
) -> dict[str, float]:
    _required_finite_scalar(
        stock_values,
        field="stock_trajectory_point",
        missing_code="system_dynamics_trajectory_missing",
        malformed_code="system_dynamics_trajectory_non_numeric",
        non_finite_code="system_dynamics_trajectory_non_finite",
        allow_array_mean=True,
    )
    try:
        stocks = np.asarray(stock_values, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise JointSimulationControllerError(
            "system_dynamics_trajectory_non_numeric",
        ) from exc
    if not np.isfinite(stocks).all():
        raise JointSimulationControllerError(
            "system_dynamics_trajectory_non_finite",
        )
    outcomes: dict[str, float] = {}
    for outcome in selected_outcomes:
        target = _engine_variable(outcome, plan)
        if target == "final_stocks":
            raise JointSimulationControllerError(
                "system_dynamics_outcome_binding_ambiguous",
                "select one indexed terminal stock",
            )
        if target == "mass_balance":
            if target not in terminal_scalar_fields:
                raise JointSimulationControllerError(
                    "system_dynamics_scalar_result_unbound",
                    outcome,
                )
            if not point_is_terminal:
                continue
            mass_balance = result.get("mass_balance")
            if mass_balance is None:
                raise JointSimulationControllerError(
                    "system_dynamics_mass_balance_missing",
                    outcome,
                )
            outcomes[outcome] = _required_finite_scalar(
                mass_balance,
                field=outcome,
                missing_code="system_dynamics_mass_balance_missing",
                malformed_code="system_dynamics_mass_balance_non_numeric",
                non_finite_code="system_dynamics_mass_balance_non_finite",
            )
            continue
        if target.startswith("final_stocks."):
            if "final_stocks" not in terminal_scalar_fields:
                raise JointSimulationControllerError(
                    "system_dynamics_scalar_result_unbound",
                    outcome,
                )
            if not point_is_terminal:
                continue
            index = _stock_index(target)
            final_stocks = result.get("final_stocks")
            if index is None or final_stocks is None:
                raise JointSimulationControllerError(
                    "system_dynamics_outcome_binding_missing",
                    outcome,
                )
            _required_finite_scalar(
                final_stocks,
                field="final_stocks",
                missing_code="system_dynamics_outcome_binding_missing",
                malformed_code="system_dynamics_outcome_non_numeric",
                non_finite_code="system_dynamics_outcome_non_finite",
                allow_array_mean=True,
            )
            try:
                final_values = np.asarray(final_stocks, dtype=float)
                final_value = final_values[index]
            except (IndexError, TypeError, ValueError, OverflowError) as exc:
                raise JointSimulationControllerError(
                    "system_dynamics_outcome_non_numeric",
                    outcome,
                ) from exc
            outcomes[outcome] = _required_finite_scalar(
                final_value,
                field=outcome,
                missing_code="system_dynamics_outcome_binding_missing",
                malformed_code="system_dynamics_outcome_non_numeric",
                non_finite_code="system_dynamics_outcome_non_finite",
            )
            continue
        index = _stock_index(target)
        if index is None:
            if target not in terminal_scalar_fields:
                raise JointSimulationControllerError(
                    "system_dynamics_scalar_result_unbound",
                    outcome,
                )
            if not point_is_terminal:
                continue
            outcomes[outcome] = _required_finite_scalar(
                result.get(target),
                field=outcome,
                missing_code="system_dynamics_outcome_binding_missing",
                malformed_code="system_dynamics_outcome_non_numeric",
                non_finite_code="system_dynamics_outcome_non_finite",
                allow_array_mean=True,
            )
            continue
        try:
            value = stocks[index]
        except IndexError as exc:
            raise JointSimulationControllerError(
                "system_dynamics_outcome_binding_missing",
                outcome,
            ) from exc
        outcomes[outcome] = _required_finite_scalar(
            value,
            field=outcome,
            missing_code="system_dynamics_outcome_binding_missing",
            malformed_code="system_dynamics_outcome_non_numeric",
            non_finite_code="system_dynamics_outcome_non_finite",
        )
    return outcomes


def _stock_index(target: str) -> int | None:
    if target.isdigit():
        return int(target)
    for prefix in ("stock:", "stock.", "stocks.", "initial_stocks.", "final_stocks."):
        if target.startswith(prefix):
            suffix = target.removeprefix(prefix)
            return int(suffix) if suffix.isdigit() else None
    return None


def _merge_mapping(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, Mapping) and isinstance(target.get(key), dict):
            _merge_mapping(target[key], value)
        else:
            target[str(key)] = deepcopy(value)


def _assign_path_value(state: dict[str, Any], path: str, value: float) -> None:
    parts = path.split(".")
    current: Any = state
    for part in parts[:-1]:
        if isinstance(current, Mapping):
            if part not in current:
                raise JointSimulationControllerError(
                    "system_dynamics_intervention_binding_missing",
                    path,
                )
            current = current[part]
        elif isinstance(current, list | np.ndarray):
            current = current[int(part)]
        else:
            current = getattr(current, part)
    last = parts[-1]
    if isinstance(current, dict):
        current[last] = value
    elif isinstance(current, list | np.ndarray):
        current[int(last)] = value
    else:
        setattr(current, last, value)


def _marginal_effects(
    trajectories: Sequence[SimulationTrajectory],
) -> dict[str, dict[int, dict[str, float]]]:
    out: dict[str, dict[int, dict[str, float]]] = {}
    for trajectory in trajectories:
        if trajectory.run_level != "individual":
            continue
        atom_id = trajectory.atom_ids[0]
        out[atom_id] = {point.step: dict(point.effect) for point in trajectory.points}
    return out


def _baseline_value(request: JointSimulationRequest, outcome: str) -> float:
    """Resolve an explicit finite comparator value for one selected outcome."""

    if outcome not in request.baseline_state:
        raise JointSimulationControllerError(
            "baseline_state_missing_for_outcome",
            outcome,
        )
    return _required_finite_scalar(
        request.baseline_state[outcome],
        field=outcome,
        missing_code="baseline_state_missing_for_outcome",
        malformed_code="baseline_state_non_numeric_for_outcome",
        non_finite_code="baseline_state_nonfinite_for_outcome",
    )


def _effect_for_outcome(
    request: JointSimulationRequest,
    outcome: str,
    value: float,
) -> float:
    """Compute an effect only against the request's explicit comparator."""

    return float(value) - _baseline_value(request, outcome)


def _interaction_terms(
    request: JointSimulationRequest,
    coverage: _InteractionCoverage,
) -> list[InteractionTerm]:
    atom_ids = tuple(atom.intervention_id for atom in request.intervention_atoms)
    scope_index = coverage.by_scope
    terms: list[InteractionTerm] = []
    for pair in itertools.combinations(atom_ids, 2):
        trajectory = scope_index.get(("pairwise", tuple(pair)))
        left = scope_index.get(("individual", (pair[0],)))
        right = scope_index.get(("individual", (pair[1],)))
        if trajectory is None or left is None or right is None:
            continue
        left_by_step = {point.step: point for point in left.points}
        right_by_step = {point.step: point for point in right.points}
        pair_by_step = {point.step: point for point in trajectory.points}
        for outcome in request.selected_outcomes:
            by_step: dict[int, float] = {}
            for step in coverage.expected_steps:
                if (
                    step not in pair_by_step
                    or step not in left_by_step
                    or step not in right_by_step
                ):
                    continue
                by_step[step] = (
                    pair_by_step[step].effect[outcome]
                    - left_by_step[step].effect[outcome]
                    - right_by_step[step].effect[outcome]
                )
            if not by_step:
                continue
            terms.append(
                InteractionTerm(
                    atom_ids=pair,
                    outcome=outcome,
                    by_step=by_step,
                )
            )
    return terms


def _feedback_classification(
    *,
    request: JointSimulationRequest,
    interaction_terms: Sequence[InteractionTerm],
    higher_order_residuals: Mapping[str, Mapping[int, float]],
    checked_interaction_orders: Sequence[int],
    unsupported: bool,
    coupling_support: _CouplingSupportDecision,
    decision_blockers: Sequence[str] = (),
    interaction_evidence_issues: Sequence[str] = (),
    aggregate_order_three_plus: bool = False,
) -> FeedbackClassification:
    classification = coupling_support.classification
    coupling_verdict = None
    coupling_ref = None
    feedback = False
    shared = False
    limitations: list[str] = []
    if classification is not None:
        coupling_verdict = classification.composition_disposition
        coupling_ref = classification.classification_ref
        feedback = classification.feedback_intensity in {"weak", "medium", "high"}
        shared = "shared_resource" in coupling_support.coupling_classes
        if feedback:
            limitations.append("requires_system_dynamics")
        if shared:
            limitations.append("requires_capacity_aggregation")
        if coupling_support.general_equilibrium:
            limitations.append("general_equilibrium_limitation")
        limitations.extend(coupling_support.blockers)
    if unsupported:
        refusal_limitations = tuple(
            dict.fromkeys(
                (
                    *limitations,
                    *(str(blocker) for blocker in decision_blockers),
                )
            )
        )
        return FeedbackClassification(
            numeric_interaction="unsupported",
            higher_order_residuals={
                str(outcome): {int(step): float(value) for step, value in by_step.items()}
                for outcome, by_step in higher_order_residuals.items()
            },
            checked_interaction_orders=tuple(int(order) for order in checked_interaction_orders),
            coupling_classes=coupling_support.coupling_classes,
            coupling_regime=classification.coupling_regime if classification is not None else None,
            coupling_gate_verdict=coupling_verdict,
            coupling_classification_ref=coupling_ref,
            engine_supported=coupling_support.engine_supported,
            support_status=coupling_support.support_status,
            support_blockers=coupling_support.blockers,
            feedback=feedback,
            shared_resource=shared,
            general_equilibrium=coupling_support.general_equilibrium,
            limitations=("eligible_joint_engine_missing", *refusal_limitations),
        )
    any_nonzero = any(
        abs(value) > 1e-12 for term in interaction_terms for value in term.by_step.values()
    ) or any(
        abs(value) > 1e-12
        for by_step in higher_order_residuals.values()
        for value in by_step.values()
    )
    if any_nonzero:
        numeric_interaction: Literal["none", "additive", "non_additive", "unsupported"] = (
            "non_additive"
        )
    elif interaction_evidence_issues or aggregate_order_three_plus:
        numeric_interaction = "unsupported"
    else:
        numeric_interaction = "additive"
    evidence_limitations: list[str] = []
    if interaction_evidence_issues:
        evidence_limitations.append("interaction_evidence_incomplete")
    if aggregate_order_three_plus:
        evidence_limitations.append("aggregate_order_3_plus_not_identified")
    return FeedbackClassification(
        numeric_interaction=numeric_interaction,
        higher_order_residuals={
            str(outcome): {int(step): float(value) for step, value in by_step.items()}
            for outcome, by_step in higher_order_residuals.items()
        },
        checked_interaction_orders=tuple(int(order) for order in checked_interaction_orders),
        coupling_classes=coupling_support.coupling_classes,
        coupling_regime=classification.coupling_regime if classification is not None else None,
        coupling_gate_verdict=coupling_verdict,
        coupling_classification_ref=coupling_ref,
        engine_supported=coupling_support.engine_supported,
        support_status=coupling_support.support_status,
        support_blockers=coupling_support.blockers,
        feedback=feedback,
        shared_resource=shared,
        general_equilibrium=coupling_support.general_equilibrium,
        limitations=tuple(dict.fromkeys((*limitations, *evidence_limitations))),
    )


def _contract_testing_fabricated_interactions(
    interaction_terms: Sequence[InteractionTerm],
) -> tuple[InteractionTerm, ...]:
    if not interaction_terms:
        return tuple(interaction_terms)
    first = interaction_terms[0]
    by_step = dict(first.by_step)
    if by_step:
        step = sorted(by_step)[0]
        by_step[step] = float(by_step[step]) + 1.0
    fabricated = first.model_copy(update={"by_step": by_step})
    return (fabricated, *tuple(interaction_terms[1:]))


def _contract_testing_shrunk_credal_state(state: Mapping[str, Any]) -> dict[str, Any]:
    if not state:
        return {"__contract_testing_k_sim_shrink__": {"low": 0.45, "high": 0.55}}
    shrunk = _json_ready(state)
    if isinstance(shrunk, dict):
        for key, value in list(shrunk.items()):
            if isinstance(value, Mapping) and {"low", "high"}.issubset(value):
                low = float(value["low"])
                high = float(value["high"])
                center = (low + high) / 2.0
                width = max((high - low) / 4.0, 0.0)
                shrunk[key] = {
                    **dict(value),
                    "low": center - width,
                    "high": center + width,
                    "source": "K_sim_contract_mutation",
                }
                return shrunk
        first_key = next(iter(shrunk))
        shrunk[first_key] = {"source": "K_sim_contract_mutation", "narrowed": True}
    return shrunk if isinstance(shrunk, dict) else {"value": shrunk}


def _csv_set(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        raw = value.split(",")
    elif isinstance(value, Sequence):
        raw = [str(item) for item in value]
    else:
        raw = [str(value)]
    return {item.strip().casefold() for item in raw if item.strip()}


def _json_ready(value: object) -> Any:  # noqa: ANN401
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_ready(item) for item in value]
    return value


__all__ = [
    "EngineDecision",
    "EnginePlan",
    "FeedbackClassification",
    "HorizonSpec",
    "InteractionTerm",
    "JointSimulationApplicability",
    "JointSimulationControllerError",
    "JointSimulationControllerPolicy",
    "JointSimulationHorizonController",
    "JointSimulationRequest",
    "JointSimulationResult",
    "ProofReceiptError",
    "SimulationProofReceipt",
    "SimulationTrajectory",
    "TrajectoryPoint",
    "build_content_bound_simulation_receipt",
    "verify_simulation_receipt",
]
