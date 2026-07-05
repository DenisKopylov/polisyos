"""Joint simulation horizon controller over existing Foundry engines.

This module owns the N5 orchestration seam: it maps bound N2 intervention atoms
and a composed WorldModelRecord into individual, pairwise, and joint simulation
runs. It does not promote simulation output into world evidence and does not
implement a parallel simulator beside Foundry engines.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator

from polisyos.foundry.execute.executor import (
    apply_state_delta,
    execute_program_graph,
)
from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.catalog.causal.protocols import NCMQueryData
from polisyos.foundry.methods.catalog.simulation import ensure_simulation_methods_registered
from polisyos.foundry.methods.selection.registry import MethodRegistry
from polisyos.ir.analytics.ncm import NCMSpec  # noqa: TC001 - Pydantic validates at runtime.
from polisyos.pdc import gy_content_hash
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

JOINT_SIMULATION_HORIZON_SCHEMA_VERSION = "policyos.runtime.joint_simulation_horizon.v1"

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

    schema_version: Literal["policyos.runtime.joint_simulation_horizon.v1"] = (
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


class JointSimulationResult(_StrictModel):
    """N5 output artifact consumed by value gating, VOI, audit, and dashboards."""

    schema_version: Literal["policyos.runtime.joint_simulation_horizon.v1"] = (
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
    uncertainty_kind: Literal["K_sim"] = "K_sim"
    world_credal_state_before: dict[str, Any] = Field(default_factory=dict)
    world_credal_state_after: dict[str, Any] = Field(default_factory=dict)
    acquisition_requests: tuple[dict[str, Any], ...] = ()
    refinement_decisions: tuple[dict[str, Any], ...] = ()
    promotion_ready_value_packet: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    receipt: SimulationProofReceipt

    _content_payload: dict[str, Any] = PrivateAttr(default_factory=dict)

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


@dataclass(frozen=True, slots=True)
class _CouplingSupportDecision:
    """Engine support decision for the already-classified S5 coupling graph."""

    classification: CouplingRegimeClassification | None
    support_status: CouplingSupportStatus
    blockers: tuple[str, ...]
    coupling_classes: tuple[BoundaryCouplingKind, ...]
    general_equilibrium: bool

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
            if diagnostics_dict.get("coupling_support_status") == "unsupported"
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

    def run(self, request: JointSimulationRequest) -> JointSimulationResult:
        """Run individual, pairwise, and joint horizons or fail closed."""

        self._validate_world_model_record(request)
        world_input = consume_world_model_record_for_simulation(request.world_model_record)
        for atom in request.intervention_atoms:
            resolve_intervention_atom_world_binding(atom, request.world_model_record)

        selected = self._select_engine(request)
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
        equilibrium = {decision.objective_ref: decision.equilibrium_semantics}
        trajectories: tuple[SimulationTrajectory, ...] = ()
        marginal_effects: dict[str, dict[int, dict[str, float]]] = {}
        interaction_terms: tuple[InteractionTerm, ...] = ()
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
            "controller_authority_scope": self._settings.authority_scope,
            "coupling_gate_disabled": self._settings.disable_coupling_gate,
            "coupling_support_status": coupling_support.support_status,
            "coupling_support_blockers": list(coupling_support.blockers),
            "engine_run_claimed": False,
        }

        if decision.decision == "selected":
            runner = self._engine_runners().get(decision.engine_kind)
            if runner is None:
                diagnostics["unsupported_objectives"].append(decision.objective_ref)
            else:
                trajectories = tuple(runner(request, selected_plan, decision))
                diagnostics["engine_run_claimed"] = bool(trajectories)
        else:
            diagnostics["unsupported_objectives"].append(decision.objective_ref)

        if trajectories:
            marginal_effects = _marginal_effects(trajectories)
            interaction_terms = tuple(_interaction_terms(trajectories, request.selected_outcomes))
            if self._settings.fabricate_interaction_terms:
                interaction_terms = _contract_testing_fabricated_interactions(interaction_terms)

        feedback = _feedback_classification(
            request=request,
            interaction_terms=interaction_terms,
            unsupported=decision.decision != "selected",
            coupling_support=coupling_support,
        )
        value_packet = {
            "world_model_record_ref": request.world_model_record_ref,
            "world_model_record_content_hash": request.world_model_record.content_hash,
            "atom_ids": [atom.intervention_id for atom in request.intervention_atoms],
            "grounding_method_refs": [
                item.method_fqn for item in decisions if item.method_fqn is not None
            ],
            "authority_blockers": ["simulation_only_k_sim_not_world_evidence"],
            "uncertainty_kind": "K_sim",
        }
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
            decisions.append(decision)
            if decision.decision == "selected":
                return _SelectedEngine(decision=decision, plan=plan, decisions=tuple(decisions))
        return _SelectedEngine(
            decision=decisions[0],
            plan=fallback_plan,
            decisions=tuple(decisions),
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
        conditions = {item.strip().casefold() for item in plan.eligibility_conditions}
        if conditions & {"multi_period", "dynamic_horizon", "dynamic_scm"}:
            return _unsupported(
                plan,
                "static_engine_cannot_ground_dynamic_horizon",
                ("static_engine_temporal_capability",),
            )
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
        conditions = {item.strip().casefold() for item in plan.eligibility_conditions}
        if temporal == "static" and conditions & {"multi_period", "dynamic_horizon", "dynamic_scm"}:
            return _unsupported(
                plan,
                "static_engine_cannot_ground_dynamic_horizon",
                ("static_engine_temporal_capability",),
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
        atoms = tuple(request.intervention_atoms)
        trajectories: list[SimulationTrajectory] = []
        for run_level, subset in _atom_subsets(atoms):
            current_state = plan.program_base_state
            points: list[TrajectoryPoint] = []
            state_delta_refs: list[str] = []
            metrics_refs: list[str] = []
            for step in request.horizon.steps():
                artifacts = execute_program_graph(
                    plan.program_store,
                    program_ref=plan.program_graph_ref,
                    exec_plan_ref=plan.exec_plan_ref,
                    base_state=current_state,
                    mechanism_registry=plan.mechanism_registry,
                    slot_registry=plan.slot_registry,
                    merge_registry=plan.merge_registry,
                    selector_field_registry=plan.selector_field_registry,
                    constraint_registry=plan.constraint_registry,
                    step=step,
                    seed=int(request.seed) + int(step),
                    base_ref=plan.program_base_ref,
                    parameter_overrides=_program_parameter_overrides(subset, plan),
                )
                current_state = apply_state_delta(
                    plan.program_store,
                    base_state=current_state,
                    state_delta_ref=artifacts.state_delta_ref,
                    slot_registry=plan.slot_registry,
                    merge_registry=plan.merge_registry,
                )
                state_delta_refs.append(str(artifacts.state_delta_ref.artifact_id))
                metrics_refs.append(str(artifacts.metrics_ref.artifact_id))
                outcomes = _program_graph_outcomes(
                    current_state,
                    request.selected_outcomes,
                    plan,
                )
                points.append(
                    TrajectoryPoint(
                        step=step,
                        outcomes=outcomes,
                        effect={
                            outcome: float(outcomes[outcome])
                            - float(request.baseline_state.get(outcome, 0.0))
                            for outcome in request.selected_outcomes
                        },
                        engine_state={
                            "state_delta_ref": state_delta_refs[-1],
                            "metrics_ref_produced": True,
                        },
                    )
                )
            trajectories.append(
                SimulationTrajectory(
                    run_level=run_level,
                    atom_ids=tuple(atom.intervention_id for atom in subset),
                    engine_kind=decision.engine_kind,
                    method_fqn=decision.method_fqn,
                    objective_ref=plan.objective_ref,
                    points=tuple(points),
                    diagnostics={
                        "engine": "execute_program_graph",
                        "horizon_loop": True,
                        "state_delta_refs": state_delta_refs,
                        "metrics_ref_count": len(metrics_refs),
                    },
                )
            )
        return trajectories

    def _run_ncm_horizon(
        self,
        request: JointSimulationRequest,
        plan: EnginePlan,
        decision: EngineDecision,
    ) -> list[SimulationTrajectory]:
        if plan.ncm_spec is None or decision.method_fqn is None:
            return []
        method = self._registry.get(decision.method_fqn)
        atoms = tuple(request.intervention_atoms)
        trajectories: list[SimulationTrajectory] = []
        for run_level, subset in _atom_subsets(atoms):
            intervention = _ncm_intervention(subset, plan)
            points: list[TrajectoryPoint] = []
            evidence = {
                _engine_variable(variable, plan): float(value)
                for variable, value in request.baseline_state.items()
            }
            step = request.horizon.start
            output = method.pure_step(
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
                {"__seed__": int(request.seed)},
            )
            outcomes = _ncm_outcomes(output, request.selected_outcomes, plan)
            points.append(
                TrajectoryPoint(
                    step=step,
                    outcomes=outcomes,
                    effect={
                        outcome: float(outcomes[outcome])
                        - float(request.baseline_state.get(outcome, 0.0))
                        for outcome in request.selected_outcomes
                    },
                    engine_state={"intervention": dict(intervention)},
                )
            )
            trajectories.append(
                SimulationTrajectory(
                    run_level=run_level,
                    atom_ids=tuple(atom.intervention_id for atom in subset),
                    engine_kind=decision.engine_kind,
                    method_fqn=decision.method_fqn,
                    objective_ref=plan.objective_ref,
                    points=tuple(points),
                    diagnostics={
                        "engine": "NCMEngineMethod",
                        "horizon_loop": False,
                        "temporal_capability": "static",
                    },
                )
            )
        return trajectories

    def _run_coupled_horizon(
        self,
        request: JointSimulationRequest,
        plan: EnginePlan,
        decision: EngineDecision,
    ) -> list[SimulationTrajectory]:
        if decision.method_fqn is None:
            return []
        method = self._registry.get(decision.method_fqn)
        atoms = tuple(request.intervention_atoms)
        trajectories: list[SimulationTrajectory] = []
        for run_level, subset in _atom_subsets(atoms):
            params = _coupled_params_for_subset(plan, subset)
            params["n_steps"] = max(1, len(request.horizon.steps()) - 1)
            params.setdefault("seed", int(request.seed))
            output = method.pure_step(plan.coupled_state, params)
            result = output.get("result", {})
            points: list[TrajectoryPoint] = []
            for index, step in enumerate(request.horizon.steps()):
                outcomes = _coupled_outcomes(result, request.selected_outcomes, index)
                points.append(
                    TrajectoryPoint(
                        step=step,
                        outcomes=outcomes,
                        effect={
                            outcome: float(outcomes[outcome])
                            - float(request.baseline_state.get(outcome, 0.0))
                            for outcome in request.selected_outcomes
                        },
                        engine_state={
                            "coupled_summary": result.get("summary", {}),
                            "queue_length": _coupled_queue_value(result, index),
                        },
                    )
                )
            trajectories.append(
                SimulationTrajectory(
                    run_level=run_level,
                    atom_ids=tuple(atom.intervention_id for atom in subset),
                    engine_kind=decision.engine_kind,
                    method_fqn=decision.method_fqn,
                    objective_ref=plan.objective_ref,
                    points=tuple(points),
                    diagnostics={
                        "engine": "CoupledPolicySimulationEstimator",
                        "horizon_loop": True,
                        "temporal_capability": "multi_period",
                    },
                )
            )
        return trajectories

    def _run_system_dynamics_horizon(
        self,
        request: JointSimulationRequest,
        plan: EnginePlan,
        decision: EngineDecision,
    ) -> list[SimulationTrajectory]:
        if decision.method_fqn is None:
            return []
        method = self._registry.get(decision.method_fqn)
        atoms = tuple(request.intervention_atoms)
        trajectories: list[SimulationTrajectory] = []
        for run_level, subset in _atom_subsets(atoms):
            state = _system_dynamics_state_for_subset(plan, subset)
            params = {
                **plan.system_dynamics_params,
                "n_steps": max(1, len(request.horizon.steps()) - 1),
            }
            params.setdefault("dt", float(request.horizon.step))
            output = method.pure_step(state, params)
            result = output.get("result", {})
            stock_trajectory = result.get("trajectory", [])
            points: list[TrajectoryPoint] = []
            for index, step in enumerate(request.horizon.steps()):
                stock_values = (
                    stock_trajectory[index]
                    if index < len(stock_trajectory)
                    else result.get("final_stocks", [])
                )
                outcomes = _system_dynamics_outcomes(
                    result,
                    stock_values,
                    request.selected_outcomes,
                    plan,
                )
                points.append(
                    TrajectoryPoint(
                        step=step,
                        outcomes=outcomes,
                        effect={
                            outcome: float(outcomes[outcome])
                            - float(request.baseline_state.get(outcome, 0.0))
                            for outcome in request.selected_outcomes
                        },
                        engine_state={
                            "stock_values": _json_ready(stock_values),
                            "mass_balance": result.get("mass_balance"),
                        },
                    )
                )
            trajectories.append(
                SimulationTrajectory(
                    run_level=run_level,
                    atom_ids=tuple(atom.intervention_id for atom in subset),
                    engine_kind=decision.engine_kind,
                    method_fqn=decision.method_fqn,
                    objective_ref=plan.objective_ref,
                    points=tuple(points),
                    diagnostics={
                        "engine": "StockFlowSystemDynamicsEstimator",
                        "horizon_loop": True,
                        "temporal_capability": "multi_period",
                    },
                )
            )
        return trajectories

    def _run_registry_method_horizon(
        self,
        request: JointSimulationRequest,
        plan: EnginePlan,
        decision: EngineDecision,
    ) -> list[SimulationTrajectory]:
        if decision.method_fqn is None:
            return []
        method = self._registry.get(decision.method_fqn)
        atoms = tuple(request.intervention_atoms)
        trajectories: list[SimulationTrajectory] = []
        for run_level, subset in _atom_subsets(atoms):
            state = _method_state_for_subset(plan, subset)
            params = {
                **plan.system_dynamics_params,
                "n_steps": max(1, len(request.horizon.steps()) - 1),
            }
            params.setdefault("dt", float(request.horizon.step))
            output = method.pure_step(state, params)
            result = output.get("result", {})
            raw_trajectory = result.get("trajectory")
            if raw_trajectory is None:
                raise JointSimulationControllerError(
                    "method_registry_temporal_output_missing",
                    decision.method_fqn,
                )
            points: list[TrajectoryPoint] = []
            for index, step in enumerate(request.horizon.steps()):
                state_values = (
                    raw_trajectory[index]
                    if index < len(raw_trajectory)
                    else result.get("final_stocks", raw_trajectory[-1])
                )
                outcomes = _system_dynamics_outcomes(
                    result,
                    state_values,
                    request.selected_outcomes,
                    plan,
                )
                points.append(
                    TrajectoryPoint(
                        step=step,
                        outcomes=outcomes,
                        effect={
                            outcome: float(outcomes[outcome])
                            - float(request.baseline_state.get(outcome, 0.0))
                            for outcome in request.selected_outcomes
                        },
                        engine_state={
                            "stock_values": _json_ready(state_values),
                            "mass_balance": result.get("mass_balance"),
                        },
                    )
                )
            trajectories.append(
                SimulationTrajectory(
                    run_level=run_level,
                    atom_ids=tuple(atom.intervention_id for atom in subset),
                    engine_kind=decision.engine_kind,
                    method_fqn=decision.method_fqn,
                    objective_ref=plan.objective_ref,
                    points=tuple(points),
                    diagnostics={
                        "engine": decision.method_fqn,
                        "horizon_loop": True,
                        "temporal_capability": "multi_period",
                    },
                )
            )
        return trajectories


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
            intervention[variable] = float(assignment.value)
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
    queue = result.get("queue_length_trajectory", [])
    if index < len(queue):
        return float(queue[index])
    return float(result.get("final_queue_length", 0.0))


def _coupled_outcomes(
    result: Mapping[str, Any],
    selected_outcomes: Sequence[str],
    index: int,
) -> dict[str, float]:
    outcomes: dict[str, float] = {}
    for outcome in selected_outcomes:
        if outcome == "final_queue_length":
            outcomes[outcome] = _coupled_queue_value(result, index)
        else:
            value = result.get(outcome)
            if value is None:
                raise JointSimulationControllerError(
                    "coupled_outcome_binding_missing",
                    outcome,
                )
            outcomes[outcome] = float(np.asarray(value, dtype=float).mean())
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
    for part in path.split("."):
        value = value[part] if isinstance(value, Mapping) else getattr(value, part)
    arr = np.asarray(value)
    if arr.shape == ():
        return float(arr.item())
    return float(np.mean(arr.astype(float)))


def _engine_variable(variable: str, plan: EnginePlan) -> str:
    return plan.variable_map.get(variable, variable)


def _ncm_outcomes(
    output: Mapping[str, Any],
    selected_outcomes: Sequence[str],
    plan: EnginePlan,
) -> dict[str, float]:
    payload = output.get("counterfactual_result", {})
    summaries = payload.get("world_summaries", [])
    summary = summaries[0] if summaries else {}
    outcomes: dict[str, float] = {}
    for outcome in selected_outcomes:
        engine_outcome = _engine_variable(outcome, plan)
        stats = summary.get(engine_outcome, {})
        outcomes[outcome] = float(stats.get("mean", 0.0))
    return outcomes


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
) -> dict[str, float]:
    stocks = np.asarray(stock_values, dtype=float)
    outcomes: dict[str, float] = {}
    for outcome in selected_outcomes:
        target = _engine_variable(outcome, plan)
        if target == "mass_balance":
            outcomes[outcome] = float(result.get("mass_balance", 0.0))
            continue
        index = _stock_index(target)
        if index is None:
            value = result.get(target)
            if value is None:
                raise JointSimulationControllerError(
                    "system_dynamics_outcome_binding_missing",
                    outcome,
                )
            outcomes[outcome] = float(np.asarray(value, dtype=float).mean())
            continue
        outcomes[outcome] = float(stocks[index])
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


def _interaction_terms(
    trajectories: Sequence[SimulationTrajectory],
    selected_outcomes: Sequence[str],
) -> list[InteractionTerm]:
    individual = {
        trajectory.atom_ids[0]: trajectory
        for trajectory in trajectories
        if trajectory.run_level == "individual" and len(trajectory.atom_ids) == 1
    }
    pairwise = [trajectory for trajectory in trajectories if trajectory.run_level == "pairwise"]
    terms: list[InteractionTerm] = []
    for trajectory in pairwise:
        if len(trajectory.atom_ids) != 2:
            continue
        left = individual[trajectory.atom_ids[0]]
        right = individual[trajectory.atom_ids[1]]
        left_by_step = {point.step: point for point in left.points}
        right_by_step = {point.step: point for point in right.points}
        for outcome in selected_outcomes:
            by_step: dict[int, float] = {}
            for point in trajectory.points:
                by_step[point.step] = (
                    point.effect[outcome]
                    - left_by_step[point.step].effect[outcome]
                    - right_by_step[point.step].effect[outcome]
                )
            terms.append(
                InteractionTerm(
                    atom_ids=(trajectory.atom_ids[0], trajectory.atom_ids[1]),
                    outcome=outcome,
                    by_step=by_step,
                )
            )
    return terms


def _feedback_classification(
    *,
    request: JointSimulationRequest,
    interaction_terms: Sequence[InteractionTerm],
    unsupported: bool,
    coupling_support: _CouplingSupportDecision,
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
        return FeedbackClassification(
            numeric_interaction="unsupported",
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
            limitations=("eligible_joint_engine_missing", *limitations),
        )
    any_nonzero = any(
        abs(value) > 1e-12 for term in interaction_terms for value in term.by_step.values()
    )
    return FeedbackClassification(
        numeric_interaction="non_additive" if any_nonzero else "additive",
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
        limitations=tuple(limitations),
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
