"""Joint simulation horizon controller over existing Foundry engines.

This module owns the N5 orchestration seam: it maps bound N2 intervention atoms
and a composed WorldModelRecord into individual, pairwise, and joint simulation
runs. It does not promote simulation output into world evidence and does not
implement a parallel simulator beside Foundry engines.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Literal, Protocol
from uuid import uuid4

import numpy as np
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)

from polisyos.core.artifacts.manifest import ArtifactRef, input_ref_from_artifact_ref
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.foundry.execute.executor import (
    apply_state_delta,
    execute_program_graph,
    new_method_execution_capture,
    persist_method_execution_capture,
    put_state_snapshot,
)
from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.catalog.causal.protocols import NCMQueryData
from polisyos.foundry.methods.catalog.simulation import (
    ensure_simulation_methods_registered,
)
from polisyos.foundry.methods.exceptions import MethodExecutionAbortError
from polisyos.foundry.methods.selection.registry import MethodRegistry
from polisyos.ir.analytics.ncm import NCMSpec  # Pydantic validates at runtime.
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.design_axes.coupling_composition import (
    BoundaryCouplingKind,
    CouplingGraph,
    CouplingRegimeClassification,
    classify_coupling,
)
from polisyos.runtime.quality.intervention_atom_binding import (
    InterventionAtomBinding,
)
from polisyos.runtime.quality.world_model_record import (
    WorldModelRecord,
    consume_world_model_record_for_simulation,
    resolve_intervention_atom_world_binding,
)
from polisyos.scientist.orchestration.engine.budget import BudgetExhaustedError
from polisyos.scientist.orchestration.engine.producer_budget import (
    ProducerBudgetObservation,
    ProducerBudgetObserver,
    ProducerBudgetSourceError,
)

JOINT_SIMULATION_HORIZON_V1_SCHEMA_VERSION = "policyos.runtime.joint_simulation_horizon.v1"
JOINT_SIMULATION_HORIZON_STATE_CONSUMPTION_SCHEMA_VERSION = (
    "policyos.runtime.joint_simulation_horizon.v2"
)
JOINT_SIMULATION_HORIZON_REPLICATION_UNCERTAINTY_SCHEMA_VERSION = (
    "policyos.runtime.joint_simulation_horizon.v3"
)
JOINT_SIMULATION_HORIZON_PAIRED_INTERACTION_UNCERTAINTY_SCHEMA_VERSION = (
    "policyos.runtime.joint_simulation_horizon.v4"
)
JOINT_SIMULATION_HORIZON_SCHEMA_VERSION = (
    JOINT_SIMULATION_HORIZON_PAIRED_INTERACTION_UNCERTAINTY_SCHEMA_VERSION
)
_JOINT_SIMULATION_HORIZON_SCHEMA_VERSIONS = frozenset(
    {
        JOINT_SIMULATION_HORIZON_V1_SCHEMA_VERSION,
        JOINT_SIMULATION_HORIZON_STATE_CONSUMPTION_SCHEMA_VERSION,
        JOINT_SIMULATION_HORIZON_REPLICATION_UNCERTAINTY_SCHEMA_VERSION,
        JOINT_SIMULATION_HORIZON_PAIRED_INTERACTION_UNCERTAINTY_SCHEMA_VERSION,
    }
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


class _CoupledSourceTimeTrace(_StrictModel):
    """Candidate-only projection of times emitted by the existing coupled producer."""

    schema_version: Literal["policyos.runtime.coupled_source_time_trace.candidate.v1"] = (
        "policyos.runtime.coupled_source_time_trace.candidate.v1"
    )
    initial_time_source: Literal["CoupledRuntimeState.time"] = "CoupledRuntimeState.time"
    transition_time_source: Literal["coupled/time"] = "coupled/time"
    corroborating_transition_time_source: Literal["queue/time"] = "queue/time"
    initial_coordinate: float
    transition_coordinates: tuple[float, ...]
    unit_status: Literal["not_established"] = "not_established"
    origin_status: Literal["not_established"] = "not_established"
    horizon_relation_status: Literal["not_established"] = "not_established"


_REPLICATION_ENGINE_STATE_CANON_SPEC = CanonSpec(
    forbid_floats=False,
    forbid_nan_inf=True,
)


def _replication_engine_state_canonical_bytes(value: object) -> bytes:
    """Encode one engine state without Python's cross-type equality coercions."""

    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValueError("replication_engine_state_not_canonical_json")
    try:
        return to_canonical_bytes(value, _REPLICATION_ENGINE_STATE_CANON_SPEC)
    except (TypeError, ValueError) as exc:
        raise ValueError("replication_engine_state_not_canonical_json") from exc


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


class PreparedJointSimulationConfiguration(_StrictModel):
    """Actual owner-prepared controller values, with no deferred defaults.

    All nested policy/settings values are required. This is candidate execution
    input data, not an authority receipt or a native-validator attestation.
    """

    schema_version: Literal["joint_simulation.prepared_configuration.v1"] = (
        "joint_simulation.prepared_configuration.v1"
    )
    policy: JointSimulationControllerPolicy
    runtime_settings: _RuntimeSettings


def prepare_joint_simulation_configuration(
    *,
    policy: JointSimulationControllerPolicy | None = None,
) -> PreparedJointSimulationConfiguration:
    """Prepare the real typed values once through the constructor's owner.

    The actual constructor consumes this frozen object. Changed model defaults,
    validators or factories therefore change prepared values, not an opaque
    identity token. No WMR, context, simulation or artifact is produced here.
    """
    if policy is not None and type(policy) is not JointSimulationControllerPolicy:
        raise TypeError("policy must be a JointSimulationControllerPolicy")
    return PreparedJointSimulationConfiguration(
        policy=policy if policy is not None else JointSimulationControllerPolicy(),
        runtime_settings=_RuntimeSettings(),
    )


def read_joint_simulation_configuration(
    controller: JointSimulationHorizonController,
) -> PreparedJointSimulationConfiguration:
    """Read the actual consumer's whole prepared quantity and live aliases.

    Future fields of the prepared schema remain included by construction. The
    two existing convenience aliases are read from the actual receiver, rather
    than trusting that the descriptor's values were consumed unchanged.
    """
    if type(controller) is not JointSimulationHorizonController:
        raise ValueError("n5_prepared_configuration_not_consumed")
    prepared = controller._prepared_configuration
    if type(prepared) is not PreparedJointSimulationConfiguration:
        raise TypeError("n5_prepared_configuration_untyped")
    if (
        type(controller.policy) is not JointSimulationControllerPolicy
        or type(controller._settings) is not _RuntimeSettings
    ):
        raise ValueError("n5_prepared_configuration_not_consumed")
    return prepared.model_copy(
        update={
            "policy": controller.policy,
            "runtime_settings": controller._settings,
        }
    )


def require_prepared_joint_simulation_configuration(
    controller: JointSimulationHorizonController,
    prepared: PreparedJointSimulationConfiguration,
) -> None:
    """Require the real constructed consumer to use the complete prepared values."""
    from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes

    if type(prepared) is not PreparedJointSimulationConfiguration:
        raise TypeError("n5_prepared_configuration_untyped")
    if type(controller) is not JointSimulationHorizonController:
        raise ValueError("n5_prepared_configuration_not_consumed")
    actual = read_joint_simulation_configuration(controller)
    if exact_n5_content_bytes(actual) != exact_n5_content_bytes(prepared):
        raise ValueError("n5_prepared_configuration_not_consumed")


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
        if (self.end - self.start) % self.step:
            raise ValueError("horizon_end_not_on_step_grid")
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
    system_dynamics_state_overrides_by_atom: dict[str, dict[str, Any]] = Field(default_factory=dict)
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
    candidate_intent: Literal["n4_unique_parent_source_members.v1"] | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    member_basis: Literal["hypothetical_all_unique_n4_source_members"] | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    source_candidate_relationship: Literal["alternatives"] | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    composition_status: Literal["not_established"] | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    composition_limitation_code: (
        Literal["n4_source_candidates_are_alternatives_not_authored_compound_design"] | None
    ) = Field(default=None, exclude_if=lambda value: value is None)
    child_to_parent_refinement_status: Literal["not_established"] | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    child_to_parent_refinement_limitation_code: (
        Literal["child_to_parent_refinement_rule_not_established"] | None
    ) = Field(default=None, exclude_if=lambda value: value is None)

    @field_validator("intervention_atoms")
    @classmethod
    def _atoms_required(
        cls,
        value: tuple[InterventionAtomBinding, ...],
    ) -> tuple[InterventionAtomBinding, ...]:
        if not value:
            raise ValueError("intervention_atoms_missing")
        return value

    @model_validator(mode="after")
    def _candidate_diagnostic_scope_is_complete(self) -> JointSimulationRequest:
        fields = (
            self.candidate_intent,
            self.member_basis,
            self.source_candidate_relationship,
            self.composition_status,
            self.composition_limitation_code,
            self.child_to_parent_refinement_status,
            self.child_to_parent_refinement_limitation_code,
        )
        if not any(value is not None for value in fields):
            return self
        if (
            any(value is None for value in fields)
            or self.candidate_intent != "n4_unique_parent_source_members.v1"
            or self.member_basis != "hypothetical_all_unique_n4_source_members"
            or self.source_candidate_relationship != "alternatives"
            or self.composition_status != "not_established"
            or self.composition_limitation_code
            != "n4_source_candidates_are_alternatives_not_authored_compound_design"
            or self.child_to_parent_refinement_status != "not_established"
            or self.child_to_parent_refinement_limitation_code
            != "child_to_parent_refinement_rule_not_established"
            or self.coupling_graph is not None
        ):
            raise ValueError("joint_simulation_candidate_diagnostic_scope_invalid")
        return self


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


class ReplicationSample(_StrictModel):
    """One seed-bound selected-engine point before replication aggregation."""

    seed: int
    engine_state: dict[str, Any]
    outcomes: dict[str, float]
    effects: dict[str, float]

    @field_validator("seed", mode="before")
    @classmethod
    def _strict_seed(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("replication_sample_seed_invalid")
        return value

    @field_validator("engine_state", mode="before")
    @classmethod
    def _engine_state_mapping(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            raise ValueError("replication_sample_engine_state_invalid")
        try:
            _replication_engine_state_canonical_bytes(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("replication_sample_engine_state_not_canonical_json") from exc
        return value

    @field_validator("outcomes", "effects", mode="before")
    @classmethod
    def _finite_real_samples(cls, value: object) -> object:
        if not isinstance(value, Mapping) or not value:
            raise ValueError("replication_sample_mapping_missing")
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("replication_sample_key_invalid")
            if isinstance(item, bool) or not isinstance(item, int | float):
                raise ValueError("replication_sample_value_not_real")
            if not math.isfinite(float(item)):
                raise ValueError("replication_sample_value_non_finite")
        return value


class ReplicationSamplingSummary(_StrictModel):
    """Recomputable selected-model Monte Carlo sampling summary for one point."""

    status: Literal["estimated", "standard_error_not_estimated"]
    replicate_count: int = Field(ge=1)
    seeds: tuple[int, ...] = Field(min_length=1)
    samples: tuple[ReplicationSample, ...] = Field(min_length=1)
    outcomes_standard_error: dict[str, float | None]
    effects_standard_error: dict[str, float | None]

    @field_validator("replicate_count", mode="before")
    @classmethod
    def _strict_replicate_count(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("replication_count_invalid")
        return value

    @field_validator("seeds", mode="before")
    @classmethod
    def _strict_distinct_seed_values(cls, value: object) -> object:
        if not isinstance(value, list | tuple) or not value:
            raise ValueError("replication_seeds_missing")
        if any(isinstance(seed, bool) or not isinstance(seed, int) for seed in value):
            raise ValueError("replication_seed_not_integer")
        if len(set(value)) != len(value):
            raise ValueError("replication_seed_duplicate")
        return value

    @field_validator("outcomes_standard_error", "effects_standard_error", mode="before")
    @classmethod
    def _finite_nonnegative_standard_errors(cls, value: object) -> object:
        if not isinstance(value, Mapping) or not value:
            raise ValueError("replication_standard_error_mapping_missing")
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("replication_standard_error_key_invalid")
            if item is None:
                continue
            if isinstance(item, bool) or not isinstance(item, int | float):
                raise ValueError("replication_standard_error_not_real")
            if not math.isfinite(float(item)) or float(item) < 0.0:
                raise ValueError("replication_standard_error_invalid")
        return value

    @model_validator(mode="after")
    def _recompute_sampling_error(self) -> ReplicationSamplingSummary:
        if self.replicate_count != len(self.seeds) or len(self.samples) != self.replicate_count:
            raise ValueError("replication_summary_denominator_mismatch")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("replication_seed_duplicate")
        if tuple(sample.seed for sample in self.samples) != self.seeds:
            raise ValueError("replication_sample_seed_binding_mismatch")
        outcome_keys = set(self.samples[0].outcomes)
        effect_keys = set(self.samples[0].effects)
        if any(
            set(sample.outcomes) != outcome_keys or set(sample.effects) != effect_keys
            for sample in self.samples[1:]
        ):
            raise ValueError("replication_sample_key_mismatch")
        if set(self.outcomes_standard_error) != outcome_keys:
            raise ValueError("replication_outcome_error_key_mismatch")
        if set(self.effects_standard_error) != effect_keys:
            raise ValueError("replication_effect_error_key_mismatch")
        expected_status = (
            "standard_error_not_estimated" if self.replicate_count == 1 else "estimated"
        )
        if self.status != expected_status:
            raise ValueError("replication_sampling_status_mismatch")
        for sample_map, errors in (
            ("outcomes", self.outcomes_standard_error),
            ("effects", self.effects_standard_error),
        ):
            for key, reported in errors.items():
                values = [float(getattr(sample, sample_map)[key]) for sample in self.samples]
                expected = _sample_standard_error(values)
                if expected is None:
                    if reported is not None:
                        raise ValueError("replication_single_draw_error_must_be_unestimated")
                elif reported is None or not math.isclose(
                    float(reported), expected, rel_tol=1e-12, abs_tol=1e-12
                ):
                    raise ValueError("replication_standard_error_recomputation_mismatch")
        return self


def _sample_standard_error(values: Sequence[float]) -> float | None:
    """Return the sample standard error, or None when one draw cannot estimate it."""

    if len(values) < 2:
        return None
    return float(np.std(np.asarray(values, dtype=float), ddof=1) / math.sqrt(len(values)))


def _validate_trajectory_sampling(trajectory: SimulationTrajectory) -> None:
    """Reconcile every point's typed summary with the complete replicate set."""

    diagnostics = trajectory.diagnostics
    requested = diagnostics.get("requested_replications")
    actual = diagnostics.get("actual_replications")
    seeds = diagnostics.get("replication_seeds")
    if (
        isinstance(requested, bool)
        or not isinstance(requested, int)
        or isinstance(actual, bool)
        or not isinstance(actual, int)
        or not isinstance(seeds, list | tuple)
        or requested < 1
        or requested != actual
        or actual != len(seeds)
        or any(isinstance(seed, bool) or not isinstance(seed, int) for seed in seeds)
        or len(set(seeds)) != len(seeds)
    ):
        raise ValueError("replication_diagnostics_denominator_invalid")
    for point in trajectory.points:
        summary = point.replication_sampling
        if summary is None:
            raise ValueError("replication_sampling_summary_missing")
        if summary.replicate_count != actual or summary.seeds != tuple(seeds):
            raise ValueError("replication_summary_diagnostics_mismatch")
        sidecar_count = point.engine_state.get("replication_count")
        sidecar_seeds = point.engine_state.get("replication_seeds")
        sidecar_states = point.engine_state.get("replication_engine_states")
        if (
            isinstance(sidecar_count, bool)
            or not isinstance(sidecar_count, int)
            or sidecar_count != actual
            or not isinstance(sidecar_seeds, list | tuple)
            or any(isinstance(seed, bool) or not isinstance(seed, int) for seed in sidecar_seeds)
            or tuple(sidecar_seeds) != tuple(seeds)
            or not isinstance(sidecar_states, list)
            or len(sidecar_states) != actual
            or any(not isinstance(state, Mapping) for state in sidecar_states)
        ):
            raise ValueError("replication_engine_state_denominator_mismatch")
        try:
            sidecar_state_bytes = tuple(
                _replication_engine_state_canonical_bytes(state) for state in sidecar_states
            )
            sample_state_bytes = tuple(
                _replication_engine_state_canonical_bytes(sample.engine_state)
                for sample in summary.samples
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("replication_engine_state_not_canonical_json") from exc
        if sidecar_state_bytes != sample_state_bytes:
            raise ValueError("replication_engine_state_binding_mismatch")
        sample_outcome_keys = set(summary.samples[0].outcomes)
        sample_effect_keys = set(summary.samples[0].effects)
        if sample_outcome_keys != set(point.outcomes) or sample_effect_keys != set(point.effect):
            raise ValueError("replication_summary_output_keys_mismatch")
        for metric, aggregated in (
            ("outcomes", point.outcomes),
            ("effects", point.effect),
        ):
            for key, reported in aggregated.items():
                observed = [float(getattr(sample, metric)[key]) for sample in summary.samples]
                mean = float(np.mean(np.asarray(observed, dtype=float)))
                if not math.isfinite(float(reported)) or not math.isclose(
                    float(reported), mean, rel_tol=1e-12, abs_tol=1e-12
                ):
                    raise ValueError("replication_mean_recomputation_mismatch")


def _replication_summary_for_points(
    replicated_points: Sequence[TrajectoryPoint], seeds: Sequence[int]
) -> ReplicationSamplingSummary:
    """Build a recomputable summary from complete, same-shaped engine outputs."""

    if not replicated_points or len(replicated_points) != len(seeds):
        raise JointSimulationControllerError("simulation_replication_denominator_mismatch")
    if len(set(seeds)) != len(seeds):
        raise JointSimulationControllerError("simulation_replication_seed_duplicate")
    outcome_keys = set(replicated_points[0].outcomes)
    effect_keys = set(replicated_points[0].effect)
    for point in replicated_points:
        if set(point.outcomes) != outcome_keys or set(point.effect) != effect_keys:
            raise JointSimulationControllerError("simulation_replication_output_key_mismatch")
        for values in (point.outcomes, point.effect):
            if any(not math.isfinite(float(value)) for value in values.values()):
                raise JointSimulationControllerError("simulation_replication_output_non_finite")
    samples = tuple(
        ReplicationSample(
            seed=seed,
            engine_state=dict(_json_ready(point.engine_state)),
            outcomes={key: float(point.outcomes[key]) for key in point.outcomes},
            effects={key: float(point.effect[key]) for key in point.effect},
        )
        for point, seed in zip(replicated_points, seeds, strict=True)
    )
    return ReplicationSamplingSummary(
        status="standard_error_not_estimated" if len(samples) == 1 else "estimated",
        replicate_count=len(samples),
        seeds=tuple(seeds),
        samples=samples,
        outcomes_standard_error={
            key: _sample_standard_error([float(sample.outcomes[key]) for sample in samples])
            for key in outcome_keys
        },
        effects_standard_error={
            key: _sample_standard_error([float(sample.effects[key]) for sample in samples])
            for key in effect_keys
        },
    )


class TrajectoryPoint(_StrictModel):
    """One horizon point emitted by a real engine run."""

    step: int
    outcomes: dict[str, float]
    effect: dict[str, float]
    replication_sampling: ReplicationSamplingSummary | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
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
    """Return joint residuals after individual and pairwise effects."""

    return _higher_order_residuals_from_fields(
        atom_ids=tuple(atom.intervention_id for atom in request.intervention_atoms),
        selected_outcomes=request.selected_outcomes,
        coverage=coverage,
    )


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
    pairs = tuple(itertools.combinations(atom_ids, 2))
    complete_pairs = bool(pairs) and all(
        ("pairwise", tuple(pair)) in complete_scopes for pair in pairs
    )
    if complete_individuals and complete_pairs:
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
    return _interaction_coverage_for_fields(
        atom_ids=atom_ids,
        selected_outcomes=request.selected_outcomes,
        expected_steps=request.horizon.steps(),
        trajectories=trajectories,
    )


def _interaction_coverage_for_fields(
    *,
    atom_ids: Sequence[str],
    selected_outcomes: Sequence[str],
    expected_steps: Sequence[int],
    trajectories: Sequence[SimulationTrajectory],
) -> _InteractionCoverage:
    """Recompute requested scope coverage from typed trajectory objects."""

    normalized_atoms = tuple(atom_ids)
    steps = tuple(expected_steps)
    expected = {
        (level, tuple(atom_id for atom_id in subset))
        for level, subset in _atom_subsets_from_ids(normalized_atoms)
    }
    observed: dict[tuple[str, tuple[str, ...]], list[SimulationTrajectory]] = {}
    for trajectory in trajectories:
        key = (trajectory.run_level, tuple(trajectory.atom_ids))
        observed.setdefault(key, []).append(trajectory)

    issues: list[str] = []
    if len(set(normalized_atoms)) != len(normalized_atoms):
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
        horizon_complete = set(point_steps) == set(steps)
        valid_points = True
        for point in trajectory.points:
            for outcome in selected_outcomes:
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
            issues.append("horizon_incomplete:" + key[0] + ":" + ",".join(key[1]))
    for key in observed.keys() - expected:
        issues.append("trajectory_scope_unrequested:" + key[0] + ":" + ",".join(key[1]))
    return _InteractionCoverage(
        by_scope=index,
        complete_scopes=frozenset(complete_scopes),
        issues=tuple(sorted(issues)),
        expected_steps=steps,
    )


def _atom_subsets_from_ids(
    atom_ids: Sequence[str],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return exactly the individual, pairwise, and all-joint scopes for the request."""

    normalized = tuple(atom_ids)
    return tuple(
        [("individual", (atom_id,)) for atom_id in normalized]
        + [("pairwise", pair) for pair in itertools.combinations(normalized, 2)]
        + [("joint", normalized)]
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
        "evidence_state": _json_ready(evidence_state),
        "evidence_source": evidence_source,
        "plan": plan.model_dump(mode="json"),
        "runtime_refs": runtime_refs,
        "atoms": [atom.model_dump(mode="json") for atom in subset],
    }
    return gy_content_hash(payload)


def _aggregate_replicated_trajectory(
    trajectories: Sequence[SimulationTrajectory],
    seeds: Sequence[int],
    physical_run_ref: str,
) -> SimulationTrajectory:
    """Average equal-shaped replicate trajectories while preserving diagnostics."""

    if not trajectories:
        raise JointSimulationControllerError("simulation_replications_missing")
    first = trajectories[0]
    if len(trajectories) != len(seeds) or len(set(seeds)) != len(seeds):
        raise JointSimulationControllerError("simulation_replication_denominator_mismatch")
    if any(
        trajectory.run_level != first.run_level
        or trajectory.atom_ids != first.atom_ids
        or trajectory.engine_kind != first.engine_kind
        or trajectory.method_fqn != first.method_fqn
        or trajectory.objective_ref != first.objective_ref
        or len(trajectory.points) != len(first.points)
        for trajectory in trajectories[1:]
    ):
        raise JointSimulationControllerError("simulation_replication_shape_mismatch")

    points: list[TrajectoryPoint] = []
    for point_index, first_point in enumerate(first.points):
        replicated_points = [trajectory.points[point_index] for trajectory in trajectories]
        if any(point.step != first_point.step for point in replicated_points):
            raise JointSimulationControllerError("simulation_replication_step_mismatch")
        if any(
            set(point.outcomes) != set(first_point.outcomes)
            or set(point.effect) != set(first_point.effect)
            for point in replicated_points[1:]
        ):
            raise JointSimulationControllerError("simulation_replication_output_key_mismatch")
        for point in replicated_points:
            if any(
                not math.isfinite(float(value))
                for values in (point.outcomes, point.effect)
                for value in values.values()
            ):
                raise JointSimulationControllerError("simulation_replication_output_non_finite")
        outcomes = {
            outcome: float(np.mean([point.outcomes[outcome] for point in replicated_points]))
            for outcome in first_point.outcomes
        }
        effects = {
            outcome: float(np.mean([point.effect[outcome] for point in replicated_points]))
            for outcome in first_point.effect
        }
        sampling = _replication_summary_for_points(replicated_points, seeds)
        points.append(
            TrajectoryPoint(
                step=first_point.step,
                outcomes=outcomes,
                effect=effects,
                replication_sampling=sampling,
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
    if any("method_execution_sources" in trajectory.diagnostics for trajectory in trajectories):
        diagnostics["replication_method_execution_sources"] = [
            trajectory.diagnostics.get("method_execution_sources", [])
            for trajectory in trajectories
        ]
    return first.model_copy(update={"points": tuple(points), "diagnostics": diagnostics})


class PhysicalSimulationWorkObservation(_StrictModel):
    """One observed physical invocation, separately from money and scientific proof."""

    schema_version: Literal["policyos.runtime.physical_simulation_work.v1"] = (
        "policyos.runtime.physical_simulation_work.v1"
    )
    invocation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    event_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    physical_spec_ref: str = Field(pattern=r"^[a-f0-9]{64}$")
    effective_seed: int = Field(strict=True)
    status: Literal["completed", "failed"]
    started_at: datetime
    completed_at: datetime
    duration_seconds: float = Field(ge=0.0, allow_inf_nan=False)
    work_units: Literal[1] = 1
    work_unit: Literal["physical_simulation_invocation"] = "physical_simulation_invocation"
    observation_basis: Literal["in_process_call_boundary"] = "in_process_call_boundary"
    scientific_authenticity: Literal["not_established"] = "not_established"
    usd_cost: None = None
    usd_cost_status: Literal["not_established"] = "not_established"
    budget_status: Literal["current_owner_checked", "not_established"]
    budget_source_basis_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    error_type: str | None = None

    @model_validator(mode="after")
    def _work_observation_binding(self) -> PhysicalSimulationWorkObservation:
        if (self.budget_status == "current_owner_checked") != (
            self.budget_source_basis_digest is not None
        ):
            raise ValueError("physical_work_budget_source_mismatch")
        if (self.status == "failed") != (self.error_type is not None):
            raise ValueError("physical_work_error_binding_mismatch")
        return self


class _PhysicalRunOutput(list[SimulationTrajectory]):
    """Invocation-local capture; repeated roles reference one shared event/basis set."""

    def __init__(
        self,
        trajectories: Sequence[SimulationTrajectory],
        observations: Sequence[PhysicalSimulationWorkObservation],
        budget_observations: Sequence[ProducerBudgetObservation],
    ) -> None:
        super().__init__(trajectories)
        self.observations = tuple(observations)
        self.budget_observations = tuple(budget_observations)


class _PhysicalWorkInterruptedError(JointSimulationControllerError):
    """Retain actual completed roles and work facts across a bounded interruption."""

    def __init__(
        self,
        code: str,
        trajectories: Sequence[SimulationTrajectory],
        observations: Sequence[PhysicalSimulationWorkObservation],
        budget_observations: Sequence[ProducerBudgetObservation],
        *,
        budget_refusal_basis: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.trajectories = tuple(trajectories)
        self.observations = tuple(observations)
        self.budget_observations = tuple(budget_observations)
        self.budget_refusal_basis = budget_refusal_basis


def _run_cached_replicates(
    request: JointSimulationRequest,
    plan: EnginePlan,
    decision: EngineDecision,
    run_once: Callable[[RunLevel, tuple[InterventionAtomBinding, ...], int], SimulationTrajectory],
    *,
    producer_budget_observer: ProducerBudgetObserver | None = None,
) -> list[SimulationTrajectory]:
    """Admit each physical seed once; role projections do not create new work.

    The budget read is current at the actual call boundary. The work unit is a
    physical invocation and does not establish a USD price or numerical producer
    authenticity. An interruption retains only fully completed role trajectories.
    """
    if producer_budget_observer is not None and (
        type(producer_budget_observer) is not ProducerBudgetObserver
        or "admit" in vars(producer_budget_observer)
        or "observe" in vars(producer_budget_observer)
    ):
        raise JointSimulationControllerError("n5_budget_observer_not_canonical")
    cache: dict[str, SimulationTrajectory] = {}
    output: list[SimulationTrajectory] = []
    observations: list[PhysicalSimulationWorkObservation] = []
    budget_bases: dict[str, ProducerBudgetObservation] = {}
    invocation_id = uuid4().hex
    seeds = _replication_seeds(request)
    for run_level, raw_subset in _atom_subsets(request.intervention_atoms):
        subset = tuple(raw_subset)
        physical_ref = _physical_run_ref(request, plan, decision, subset)
        reused = physical_ref in cache
        if not reused:
            replicated: list[SimulationTrajectory] = []
            physical_observations: list[PhysicalSimulationWorkObservation] = []
            for seed in seeds:
                budget_observation = None
                if producer_budget_observer is not None:
                    try:
                        budget_observation = producer_budget_observer.admit()
                    except (BudgetExhaustedError, ProducerBudgetSourceError) as exc:
                        last_checked = producer_budget_observer.last_checked
                        if last_checked is not None:
                            budget_bases[last_checked.source_basis_digest] = last_checked
                        exhausted = isinstance(exc, BudgetExhaustedError)
                        status = (
                            "configured_limit_only"
                            if producer_budget_observer.configured_limit_usd == 0
                            else "current_owner_checked"
                            if exhausted
                            else "last_checked_not_current"
                        )
                        raise _PhysicalWorkInterruptedError(
                            "n5_current_budget_exhausted"
                            if exhausted
                            else "n5_current_budget_source_not_established",
                            output,
                            observations,
                            tuple(budget_bases.values()),
                            budget_refusal_basis={
                                "status": status,
                                "configured_limit_usd": str(
                                    producer_budget_observer.configured_limit_usd
                                ),
                                "last_checked_observation_ref": (
                                    last_checked.source_basis_digest
                                    if last_checked is not None
                                    else None
                                ),
                            },
                        ) from exc
                    budget_bases[budget_observation.source_basis_digest] = budget_observation
                started_monotonic = perf_counter()
                started_at = datetime.now(UTC)
                error: Exception | None = None
                try:
                    trajectory = run_once(run_level, subset, seed)
                except Exception as exc:
                    error = exc
                work = PhysicalSimulationWorkObservation(
                    invocation_id=invocation_id,
                    event_id=uuid4().hex,
                    physical_spec_ref=physical_ref,
                    effective_seed=seed,
                    status="completed" if error is None else "failed",
                    started_at=started_at,
                    completed_at=datetime.now(UTC),
                    duration_seconds=max(0.0, perf_counter() - started_monotonic),
                    budget_status=(
                        "current_owner_checked"
                        if budget_observation is not None
                        else "not_established"
                    ),
                    budget_source_basis_digest=(
                        budget_observation.source_basis_digest
                        if budget_observation is not None
                        else None
                    ),
                    error_type=type(error).__name__ if error is not None else None,
                )
                observations.append(work)
                physical_observations.append(work)
                if error is not None:
                    raise _PhysicalWorkInterruptedError(
                        "n5_physical_work_failed",
                        output,
                        observations,
                        tuple(budget_bases.values()),
                    ) from error
                replicated.append(trajectory)
            aggregate = _aggregate_replicated_trajectory(replicated, seeds, physical_ref)
            cache[physical_ref] = aggregate.model_copy(
                update={
                    "diagnostics": {
                        **aggregate.diagnostics,
                        "physical_work_event_ids": [
                            item.event_id for item in physical_observations
                        ],
                    }
                }
            )
        cached = cache[physical_ref]
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
    return _PhysicalRunOutput(output, observations, tuple(budget_bases.values()))


class InteractionTerm(_StrictModel):
    """Real paired interaction term computed from actual shared-seed trajectories."""

    atom_ids: tuple[str, str]
    outcome: str
    by_step: dict[int, float]
    replication_sampling_by_step: dict[int, ReplicationSamplingSummary] = Field(
        default_factory=dict
    )
    formula: Literal["joint_effect_minus_sum_individual_effects"] = (
        "joint_effect_minus_sum_individual_effects"
    )

    @model_validator(mode="after")
    def _recompute_paired_interaction_means(self) -> InteractionTerm:
        if set(self.replication_sampling_by_step) - set(self.by_step):
            raise ValueError("interaction_sampling_step_not_in_mean_map")
        for step, summary in self.replication_sampling_by_step.items():
            if set(summary.effects_standard_error) != {"derived_effect"}:
                raise ValueError("interaction_sampling_effect_key_invalid")
            values = [sample.effects["derived_effect"] for sample in summary.samples]
            mean = float(np.mean(np.asarray(values, dtype=float)))
            if not math.isclose(mean, self.by_step[step], rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("interaction_mean_recomputation_mismatch")
        return self


class FeedbackClassification(_StrictModel):
    """Feedback/shared-resource posture from S5 plus numeric interaction evidence."""

    numeric_interaction: Literal["none", "additive", "non_additive", "unsupported"]
    numeric_interaction_basis: Literal[
        "finite_checked_model_point_estimate_only", "not_established"
    ] = "not_established"
    interaction_sampling_status: Literal[
        "estimated", "standard_error_not_estimated", "not_established"
    ] = "not_established"
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
        "policyos.runtime.joint_simulation_horizon.v3",
        "policyos.runtime.joint_simulation_horizon.v4",
    ] = JOINT_SIMULATION_HORIZON_SCHEMA_VERSION
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
        "policyos.runtime.joint_simulation_horizon.v3",
        "policyos.runtime.joint_simulation_horizon.v4",
    ] = JOINT_SIMULATION_HORIZON_SCHEMA_VERSION
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
    higher_order_residual_sampling: dict[str, dict[int, ReplicationSamplingSummary]] = Field(
        default_factory=dict
    )
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

    @property
    def physical_work_observations(self) -> tuple[PhysicalSimulationWorkObservation, ...]:
        """Reconcile persisted work/event references, not a self-reported count."""
        raw = self.diagnostics.get("physical_work_observations")
        if raw is None:
            return ()
        if type(raw) is not list:
            raise ValueError("n5_physical_work_observations_not_a_sequence")
        observations = tuple(PhysicalSimulationWorkObservation.model_validate(item) for item in raw)
        ids = [item.event_id for item in observations]
        if len(ids) != len(set(ids)):
            raise ValueError("n5_physical_work_observation_duplicate")
        if self.diagnostics.get("physical_work_units") != len(observations):
            raise ValueError("n5_physical_work_unit_count_mismatch")
        if self.diagnostics.get("physical_work_unit") != "physical_simulation_invocation":
            raise ValueError("n5_physical_work_unit_invalid")
        if self.diagnostics.get("physical_work_usd_cost_status") != "not_established":
            raise ValueError("n5_physical_work_usd_not_established")
        bases = self.diagnostics.get("producer_budget_observations", {})
        if type(bases) is not dict:
            raise ValueError("n5_producer_budget_basis_set_invalid")
        for ref, basis in bases.items():
            parsed_basis = ProducerBudgetObservation.model_validate(basis)
            if ref != parsed_basis.source_basis_digest:
                raise ValueError("n5_producer_budget_basis_ref_mismatch")
        known = {item.event_id: item for item in observations}
        calls: set[tuple[str, str, int]] = set()
        for item in observations:
            call = (item.invocation_id, item.physical_spec_ref, item.effective_seed)
            if call in calls:
                raise ValueError("n5_physical_work_call_duplicate")
            calls.add(call)
            if item.budget_source_basis_digest is not None and (
                item.budget_source_basis_digest not in bases
            ):
                raise ValueError("n5_physical_work_budget_source_missing")
        if self.diagnostics.get("physical_work_capture_status") != "observed":
            if observations or bases:
                raise ValueError("n5_unknown_capture_cannot_claim_observations")
            return ()
        for trajectory in self.trajectories:
            physical_ref = trajectory.diagnostics.get("physical_run_ref")
            event_refs = trajectory.diagnostics.get("physical_work_event_ids", ())
            expected_seeds = tuple(trajectory.diagnostics.get("replication_seeds", ()))
            actual_seeds = []
            for ref in event_refs:
                parsed = known.get(ref)
                if parsed is None or parsed.status != "completed":
                    raise ValueError("n5_physical_work_trajectory_binding_mismatch")
                if parsed.physical_spec_ref != physical_ref:
                    raise ValueError("n5_physical_work_spec_binding_mismatch")
                actual_seeds.append(parsed.effective_seed)
            if tuple(actual_seeds) != expected_seeds:
                raise ValueError("n5_physical_work_replication_binding_mismatch")
        return observations

    @model_validator(mode="after")
    def _versioned_state_consumption(self) -> JointSimulationResult:
        if "physical_work_observations" in self.diagnostics:
            _ = self.physical_work_observations
        if self.receipt.schema_version != self.schema_version:
            raise ValueError("joint_simulation_receipt_schema_mismatch")
        if self.schema_version == JOINT_SIMULATION_HORIZON_V1_SCHEMA_VERSION:
            if "state_consumption" in self.model_fields_set:
                raise ValueError("joint_simulation_v1_cannot_claim_state_consumption")
        elif self.schema_version == JOINT_SIMULATION_HORIZON_STATE_CONSUMPTION_SCHEMA_VERSION:
            if self.state_consumption is None:
                raise ValueError("joint_simulation_v2_state_consumption_missing")
        elif self.schema_version in {
            JOINT_SIMULATION_HORIZON_REPLICATION_UNCERTAINTY_SCHEMA_VERSION,
            JOINT_SIMULATION_HORIZON_PAIRED_INTERACTION_UNCERTAINTY_SCHEMA_VERSION,
        }:
            requested = self.diagnostics.get("requested_replications")
            seeds = self.diagnostics.get("replication_seeds")
            if (
                isinstance(requested, bool)
                or not isinstance(requested, int)
                or requested < 1
                or not isinstance(seeds, list | tuple)
                or len(seeds) != requested
                or any(isinstance(seed, bool) or not isinstance(seed, int) for seed in seeds)
                or len(set(seeds)) != len(seeds)
            ):
                raise ValueError("replication_request_diagnostics_invalid")
            for trajectory in self.trajectories:
                _validate_trajectory_sampling(trajectory)
                if (
                    trajectory.diagnostics.get("requested_replications") != requested
                    or trajectory.diagnostics.get("actual_replications") != requested
                    or trajectory.diagnostics.get("replication_seeds") != list(seeds)
                ):
                    raise ValueError("replication_trajectory_request_mismatch")
            if self.schema_version == (
                JOINT_SIMULATION_HORIZON_PAIRED_INTERACTION_UNCERTAINTY_SCHEMA_VERSION
            ):
                (
                    expected_terms,
                    expected_residual_means,
                    expected_residual_sampling,
                    sampling_issues,
                    evidence_issues,
                ) = _recompute_result_interaction_sampling(self)
                if [term.model_dump(mode="json") for term in self.interaction_terms] != [
                    term.model_dump(mode="json") for term in expected_terms
                ]:
                    raise ValueError("interaction_sampling_source_recomputation_mismatch")
                if self.higher_order_residuals != expected_residual_means:
                    raise ValueError("higher_order_residual_mean_recomputation_mismatch")
                if self.higher_order_residual_sampling != expected_residual_sampling:
                    raise ValueError("higher_order_sampling_source_recomputation_mismatch")
                if self.feedback_classification.higher_order_residuals != expected_residual_means:
                    raise ValueError("feedback_higher_order_residual_binding_mismatch")
                if (
                    tuple(self.diagnostics.get("interaction_sampling_issues", ()))
                    != sampling_issues
                ):
                    raise ValueError("interaction_sampling_issue_recomputation_mismatch")
                if (
                    tuple(self.diagnostics.get("interaction_evidence_issues", ()))
                    != evidence_issues
                ):
                    raise ValueError("interaction_evidence_issue_recomputation_mismatch")
                expected_status = _interaction_sampling_status(
                    expected_terms,
                    expected_residual_sampling,
                    (*sampling_issues, *evidence_issues),
                    no_interactions_applicable=len(self.atom_ids) < 2,
                )
                if self.feedback_classification.interaction_sampling_status != expected_status:
                    raise ValueError("interaction_sampling_status_recomputation_mismatch")
                if self.feedback_classification.numeric_interaction_basis != (
                    "finite_checked_model_point_estimate_only"
                    if expected_status == "estimated"
                    else "not_established"
                ):
                    raise ValueError("interaction_point_estimate_basis_mismatch")
                expected_numeric = _numeric_interaction_classification(
                    interaction_terms=expected_terms,
                    higher_order_residuals=expected_residual_means,
                    higher_order_residual_sampling=expected_residual_sampling,
                    sampling_status=expected_status,
                    sampling_issues=(*sampling_issues, *evidence_issues),
                    interaction_evidence_issues=evidence_issues,
                    aggregate_order_three_plus=len(self.atom_ids) >= 4,
                    interaction_required=len(self.atom_ids) >= 2,
                )
                if self.feedback_classification.numeric_interaction != expected_numeric:
                    raise ValueError("numeric_interaction_classification_recomputation_mismatch")
                expected_basis = (
                    "finite_checked_model_point_estimate_only"
                    if expected_status == "estimated"
                    else "not_established"
                )
                if self.feedback_classification.numeric_interaction_basis != expected_basis:
                    raise ValueError("interaction_point_estimate_basis_mismatch")
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
    schema_version = payload_dict.get("schema_version", JOINT_SIMULATION_HORIZON_SCHEMA_VERSION)
    if schema_version not in _JOINT_SIMULATION_HORIZON_SCHEMA_VERSIONS:
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

    if result.schema_version not in {
        JOINT_SIMULATION_HORIZON_V1_SCHEMA_VERSION,
        JOINT_SIMULATION_HORIZON_REPLICATION_UNCERTAINTY_SCHEMA_VERSION,
        JOINT_SIMULATION_HORIZON_PAIRED_INTERACTION_UNCERTAINTY_SCHEMA_VERSION,
    }:
        raise ProofReceiptError("state_consumption_requires_unbound_engine_result")
    verify_simulation_receipt(result.receipt, result.content_bound_payload())
    if result.world_model_record_content_hash != consumption.world_model_record_content_hash:
        raise ProofReceiptError("state_consumption_world_mismatch")
    if (
        not any(
            item.engine_kind == "program_graph" and item.decision == "selected"
            for item in result.engine_decisions
        )
        or not result.trajectories
    ):
        raise ProofReceiptError("state_consumption_program_run_missing")
    payload = deepcopy(result.content_bound_payload())
    if result.schema_version == JOINT_SIMULATION_HORIZON_V1_SCHEMA_VERSION:
        payload["schema_version"] = JOINT_SIMULATION_HORIZON_STATE_CONSUMPTION_SCHEMA_VERSION
    elif result.schema_version == JOINT_SIMULATION_HORIZON_REPLICATION_UNCERTAINTY_SCHEMA_VERSION:
        payload["schema_version"] = JOINT_SIMULATION_HORIZON_REPLICATION_UNCERTAINTY_SCHEMA_VERSION
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


class JointSimulationHorizonController:
    """Thin N5 controller over registry-selected Foundry joint engines."""

    def __init__(
        self,
        *,
        method_registry: MethodRegistry | None = None,
        policy: JointSimulationControllerPolicy | None = None,
        producer_budget_observer: ProducerBudgetObserver | None = None,
        _prepared_configuration: PreparedJointSimulationConfiguration | None = None,
    ) -> None:
        if policy is not None and not isinstance(policy, JointSimulationControllerPolicy):
            raise TypeError("policy must be a JointSimulationControllerPolicy")
        self._registry = (
            method_registry if method_registry is not None else MethodRegistry.get_instance()
        )
        prepared = _prepared_configuration
        if prepared is None:
            prepared = prepare_joint_simulation_configuration(policy=policy)
        elif type(prepared) is not PreparedJointSimulationConfiguration:
            raise TypeError("n5_prepared_configuration_untyped")
        elif policy is not None and policy is not prepared.policy:
            raise ValueError("n5_prepared_policy_conflict")
        self._prepared_configuration = prepared
        self.policy = prepared.policy
        if producer_budget_observer is not None and (
            type(producer_budget_observer) is not ProducerBudgetObserver
        ):
            raise TypeError("n5_budget_observer_not_canonical")
        self._producer_budget_observer = producer_budget_observer
        self._settings = prepared.runtime_settings
        self._last_n5_implementation_capture: object | None = None

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

        self._last_n5_implementation_capture = None
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
        higher_order_residual_sampling: dict[str, dict[int, ReplicationSamplingSummary]] = {}
        checked_interaction_orders: tuple[int, ...] = ()
        interaction_evidence_issues: tuple[str, ...] = ()
        interaction_sampling_issues: tuple[str, ...] = ()
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
            "effect_basis": "outcome_minus_request_baseline_state",
            "effect_basis_status": "not_established",
            "physical_time_basis_status": (
                "not_established"
                if decision.temporal_capability == "multi_period"
                else "not_applicable"
            ),
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
                try:
                    produced = runner(request, selected_plan, decision)
                    trajectories = tuple(produced)
                    if type(produced) is _PhysicalRunOutput:
                        diagnostics["physical_work_capture_status"] = "observed"
                        diagnostics["physical_work_observations"] = [
                            item.model_dump(mode="json") for item in produced.observations
                        ]
                        diagnostics["producer_budget_observations"] = {
                            item.source_basis_digest: item.model_dump(mode="json")
                            for item in produced.budget_observations
                        }
                except _PhysicalWorkInterruptedError as exc:
                    trajectories = exc.trajectories
                    diagnostics["physical_work_capture_status"] = "observed"
                    diagnostics["physical_work_interruption"] = exc.code
                    diagnostics["physical_work_observations"] = [
                        item.model_dump(mode="json") for item in exc.observations
                    ]
                    diagnostics["producer_budget_observations"] = {
                        item.source_basis_digest: item.model_dump(mode="json")
                        for item in exc.budget_observations
                    }
                    if exc.budget_refusal_basis is not None:
                        diagnostics["budget_interruption_basis"] = exc.budget_refusal_basis
                diagnostics["engine_run_claimed"] = bool(trajectories)
                if trajectories:
                    self._validate_selected_trajectories(
                        request=request,
                        plan=selected_plan,
                        decision=decision,
                        trajectories=trajectories,
                    )
        else:
            unsupported_decisions = tuple(item for item in decisions if item.decision != "selected")
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

        work_events = tuple(
            PhysicalSimulationWorkObservation.model_validate(raw)
            for raw in diagnostics.get("physical_work_observations", ())
        )
        diagnostics.setdefault("physical_work_capture_status", "not_established")
        diagnostics.setdefault("physical_work_observations", [])
        diagnostics.setdefault("producer_budget_observations", {})
        diagnostics["physical_work_units"] = len(work_events)
        diagnostics["physical_work_unit"] = "physical_simulation_invocation"
        diagnostics["physical_work_usd_cost_status"] = "not_established"
        diagnostics["budget_admission_status"] = (
            "current_owner_checked"
            if self._producer_budget_observer is not None
            and "physical_work_interruption" not in diagnostics
            and work_events
            else "not_established"
        )
        if trajectories:
            marginal_effects = _marginal_effects(trajectories)
            coverage = _interaction_coverage(
                request,
                trajectories,
            )
            interaction_evidence_issues = coverage.issues
            pair_sampling_issues: list[str] = []
            replication_seeds = _replication_seeds(request)
            interaction_terms = tuple(
                _interaction_terms(
                    request,
                    coverage,
                    replication_seeds=replication_seeds,
                    sampling_issues=pair_sampling_issues,
                )
            )
            higher_order_residuals = _higher_order_residuals(request, coverage)
            higher_order_residual_sampling, residual_sampling_issues = (
                _higher_order_residual_sampling(
                    request,
                    coverage,
                    replication_seeds=replication_seeds,
                )
            )
            interaction_sampling_issues = tuple(
                sorted(
                    set(
                        pair_sampling_issues
                        + list(residual_sampling_issues)
                        + (["interaction_evidence_incomplete"] if coverage.issues else [])
                    )
                )
            )
            diagnostics["interaction_sampling_issues"] = list(interaction_sampling_issues)
            checked_interaction_orders = _checked_interaction_orders(
                request,
                coverage,
            )
            diagnostics["checked_interaction_orders"] = list(checked_interaction_orders)
            diagnostics["interaction_evidence_issues"] = list(interaction_evidence_issues)
            if self._settings.fabricate_interaction_terms:
                interaction_terms = _contract_testing_fabricated_interactions(interaction_terms)
        else:
            empty_coverage = _interaction_coverage(request, trajectories)
            interaction_evidence_issues = empty_coverage.issues
            interaction_sampling_issues = (
                ("interaction_evidence_incomplete",) if empty_coverage.issues else ()
            )
            diagnostics["interaction_sampling_issues"] = list(interaction_sampling_issues)
            diagnostics["interaction_evidence_issues"] = list(interaction_evidence_issues)

        feedback = _feedback_classification(
            request=request,
            interaction_terms=interaction_terms,
            higher_order_residuals=higher_order_residuals,
            checked_interaction_orders=checked_interaction_orders,
            unsupported=decision.decision != "selected",
            coupling_support=coupling_support,
            decision_blockers=tuple(blocker for item in decisions for blocker in item.blockers),
            interaction_evidence_issues=interaction_evidence_issues,
            aggregate_order_three_plus=len(request.intervention_atoms) >= 4,
            higher_order_residual_sampling=higher_order_residual_sampling,
            interaction_sampling_status=_interaction_sampling_status(
                interaction_terms,
                higher_order_residual_sampling,
                (*interaction_sampling_issues, *interaction_evidence_issues),
                no_interactions_applicable=len(request.intervention_atoms) < 2,
            ),
            interaction_sampling_issues=interaction_sampling_issues,
        )
        authority_blockers = ["simulation_only_k_sim_not_world_evidence"]
        if "physical_work_interruption" in diagnostics:
            authority_blockers.append(str(diagnostics["physical_work_interruption"]))
        if trajectories:
            authority_blockers.append("simulation_effect_basis_not_established")
            if decision.temporal_capability == "multi_period":
                authority_blockers.append("horizon_time_alignment_not_established")
        if interaction_evidence_issues:
            authority_blockers.append("interaction_evidence_incomplete")
        point_sampling_statuses = {
            point.replication_sampling.status
            for trajectory in trajectories
            for point in trajectory.points
            if point.replication_sampling is not None
        }
        if "standard_error_not_estimated" in point_sampling_statuses:
            authority_blockers.append("standard_error_not_estimated")
        if feedback.interaction_sampling_status == "not_established":
            authority_blockers.append("interaction_sampling_not_established")
        elif feedback.interaction_sampling_status == "standard_error_not_estimated":
            if "standard_error_not_estimated" not in authority_blockers:
                authority_blockers.append("standard_error_not_estimated")
            authority_blockers.append("interaction_sampling_not_established")
        if _sampling_variation_observed(interaction_terms, higher_order_residual_sampling):
            authority_blockers.append("interaction_sampling_variation_observed")
        if feedback.numeric_interaction == "unsupported":
            authority_blockers.append("interaction_numeric_classification_unsupported")
        value_packet = {
            "world_model_record_ref": request.world_model_record_ref,
            "world_model_record_content_hash": request.world_model_record.content_hash,
            "atom_ids": [atom.intervention_id for atom in request.intervention_atoms],
            "grounding_method_refs": [
                item.method_fqn for item in decisions if item.method_fqn is not None
            ],
            "comparator_refs_status": "not_established",
            "effect_basis": "outcome_minus_request_baseline_state",
            "effect_basis_status": (
                "not_established" if trajectories else "not_applicable_no_trajectory"
            ),
            "physical_time_basis_status": (
                "not_established"
                if decision.temporal_capability == "multi_period"
                else "not_applicable"
            ),
            "authority_blockers": authority_blockers,
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
            "higher_order_residuals": _json_ready(higher_order_residuals),
            "higher_order_residual_sampling": _json_ready(higher_order_residual_sampling),
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
        requested_steps = request.horizon.steps()
        requires_multi_period = len(requested_steps) > 1
        fallback_plan = request.engine_plan[0]
        for plan in request.engine_plan:
            selector = selectors.get(plan.engine_kind, self._select_registry_method_engine)
            decision = selector(plan)
            decision = self._resolve_engine_semantics(plan, decision)
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
            if (
                decision.decision == "selected"
                and requires_multi_period
                and decision.temporal_capability != "multi_period"
            ):
                reason = (
                    "static_engine_cannot_ground_dynamic_horizon"
                    if decision.temporal_capability == "static"
                    else "engine_temporal_capability_unavailable"
                )
                blocker = (
                    "static_engine_temporal_capability"
                    if decision.temporal_capability == "static"
                    else "engine_temporal_capability_unsupported"
                )
                decision = _unsupported(plan, reason, (blocker,))
            if decision.decision == "selected":
                try:
                    _validate_atom_composition(plan, request.intervention_atoms)
                except JointSimulationControllerError as exc:
                    decision = _unsupported(plan, exc.code, (exc.code,))
            decisions.append(decision)
            if decision.decision == "selected":
                return _SelectedEngine(decision=decision, plan=plan, decisions=tuple(decisions))
        return _SelectedEngine(
            decision=decisions[0],
            plan=fallback_plan,
            decisions=tuple(decisions),
        )

    def validate_selected_result(
        self, *, request: JointSimulationRequest, result: JointSimulationResult
    ) -> None:
        """Recompute the selected physical-plan binding for a produced N5 result.

        This is a candidate-only consistency check against the actual request and
        the same engine-selection and physical-ref owners used by ``run``. It
        does not establish scientific truth or authenticate a foreign producer.
        """
        if type(request) is not JointSimulationRequest or type(result) is not JointSimulationResult:
            raise JointSimulationControllerError("selected_plan_execution_binding_missing")
        try:
            actual = result.model_dump(mode="json", exclude={"receipt"})
            payload = result.content_bound_payload()
            if not payload:
                # Freshly decoded nested results have no private payload cache.
                # Reconstruct and verify their complete serialized projection.
                payload = actual
            verify_simulation_receipt(result.receipt, payload)
            if gy_content_hash(payload) != gy_content_hash(actual):
                raise ValueError("result_model_receipt_payload_mismatch")
            if (
                result.world_model_record_ref != request.world_model_record_ref
                or result.world_model_record_content_hash != request.world_model_record.content_hash
                or result.atom_ids
                != tuple(atom.intervention_id for atom in request.intervention_atoms)
                or result.selected_outcomes != request.selected_outcomes
                or result.horizon != request.horizon
                or result.diagnostics.get("requested_replications") != request.replications
                or result.diagnostics.get("replication_seeds") != list(_replication_seeds(request))
                or not result.trajectories
            ):
                raise ValueError("result_request_binding_mismatch")
            selected = self._select_engine(request)
            if (
                selected.decision.decision != "selected"
                or selected.decisions != result.engine_decisions
                or result.receipt.engine_kind != selected.decision.engine_kind
            ):
                raise ValueError("selected_engine_owner_mismatch")
            self._validate_selected_trajectories(
                request=request,
                plan=selected.plan,
                decision=selected.decision,
                trajectories=result.trajectories,
            )
            for trajectory in result.trajectories:
                for point in trajectory.points:
                    for outcome in request.selected_outcomes:
                        expected = _effect_for_outcome(request, outcome, point.outcomes[outcome])
                        if not math.isclose(
                            point.effect[outcome], expected, rel_tol=1e-12, abs_tol=1e-12
                        ):
                            raise ValueError("selected_effect_basis_mismatch")
                    if point.replication_sampling is not None:
                        for sample in point.replication_sampling.samples:
                            for outcome in request.selected_outcomes:
                                expected = _effect_for_outcome(
                                    request, outcome, sample.outcomes[outcome]
                                )
                                if not math.isclose(
                                    sample.effects[outcome], expected, rel_tol=1e-12, abs_tol=1e-12
                                ):
                                    raise ValueError("selected_sample_effect_basis_mismatch")
        except (
            ProofReceiptError,
            JointSimulationControllerError,
            TypeError,
            ValueError,
            KeyError,
        ) as exc:
            raise JointSimulationControllerError(
                "selected_plan_execution_binding_missing", str(exc)
            ) from exc

    def _validate_selected_trajectories(
        self,
        *,
        request: JointSimulationRequest,
        plan: EnginePlan,
        decision: EngineDecision,
        trajectories: Sequence[SimulationTrajectory],
    ) -> None:
        """Require every emitted trajectory to bind to the executed plan."""

        atoms_by_id = {atom.intervention_id: atom for atom in request.intervention_atoms}
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
        if temporal == "static" and conditions & {
            "multi_period",
            "dynamic_horizon",
            "dynamic_scm",
        }:
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

        def run_once(
            run_level: RunLevel,
            subset: tuple[InterventionAtomBinding, ...],
            replication_seed: int,
        ) -> SimulationTrajectory:
            current_state = plan.program_base_state
            last_state_source_ref = plan.program_base_ref
            points: list[TrajectoryPoint] = []
            state_delta_refs: list[str] = []
            metrics_refs: list[str] = []
            method_execution_capture = new_method_execution_capture(
                plan.program_store,
                program_ref=plan.program_graph_ref,
                exec_plan_ref=plan.exec_plan_ref,
            )
            method_execution_steps: list[dict[str, Any]] = []
            for step in request.horizon.steps():
                prestate_ref = plan.program_base_ref
                if method_execution_capture is not None:
                    prestate_inputs = (
                        [
                            input_ref_from_artifact_ref(
                                last_state_source_ref,
                                role="horizon_prestate_source",
                            )
                        ]
                        if isinstance(last_state_source_ref, ArtifactRef)
                        and last_state_source_ref.manifest_profile_sha256 is not None
                        else []
                    )
                    prestate_ref = put_state_snapshot(
                        plan.program_store,
                        state=current_state,
                        step=step,
                        inputs=prestate_inputs,
                        return_selected_profile=True,
                    )
                first_occurrence_index = (
                    len(method_execution_capture.occurrences)
                    if method_execution_capture is not None
                    else 0
                )
                try:
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
                        seed=int(replication_seed) + int(step),
                        base_ref=prestate_ref,
                        parameter_overrides=_program_parameter_overrides(subset, plan),
                        return_selected_profile=method_execution_capture is not None,
                        method_execution_capture=method_execution_capture,
                        method_input_state_source_ref=prestate_ref
                        if method_execution_capture is not None
                        else None,
                        finalize_method_execution_capture=method_execution_capture is None,
                    )
                except MethodExecutionAbortError as exc:
                    if method_execution_capture is not None:
                        bundle_ref = (
                            exc.method_execution_bundle_ref
                            or persist_method_execution_capture(
                                plan.program_store,
                                method_execution_capture,
                            )
                        )
                        invocation_id = (
                            f"graph-invocation.{method_execution_capture.invocation_count:06d}"
                        )
                        current_invocation_occurrences = [
                            item
                            for item in method_execution_capture.occurrences
                            if item.invocation_id == invocation_id
                        ]
                        method_execution_steps.append(
                            {
                                "step": step,
                                "source_status": "failed",
                                "prestate_ref": prestate_ref.model_dump(mode="json"),
                                "occurrence_ids": [
                                    item.occurrence_id for item in current_invocation_occurrences
                                ],
                            }
                        )
                        exception_occurrences = [
                            {
                                "occurrence_id": item.occurrence_id,
                                "invocation_id": item.invocation_id,
                                "node_id": item.node_id,
                                "status": "skipped" if item.status == "planned" else item.status,
                            }
                            for item in method_execution_capture.occurrences
                        ]
                        binding_set_payload = (
                            method_execution_capture.method_metric_binding_set_ref.model_dump(
                                mode="json"
                            )
                        )
                        exc.method_metric_horizon_capture = {
                            "step": step,
                            "status": "failed",
                            "method_metric_binding_set_ref": binding_set_payload,
                            "method_execution_bundle_ref": bundle_ref.model_dump(mode="json"),
                            "invocation_id": invocation_id,
                            "occurrences": exception_occurrences,
                            "method_execution_sources": method_execution_steps,
                        }
                    raise
                occurrence_rows = (
                    method_execution_capture.occurrences[first_occurrence_index:]
                    if method_execution_capture is not None
                    else []
                )
                method_execution_steps.append(
                    {
                        "step": step,
                        "prestate_ref": prestate_ref.model_dump(mode="json")
                        if method_execution_capture is not None
                        else None,
                        "state_delta_ref": artifacts.state_delta_ref.model_dump(mode="json"),
                        "metrics_ref": artifacts.metrics_ref.model_dump(mode="json"),
                        "occurrence_ids": [item.occurrence_id for item in occurrence_rows],
                    }
                )
                current_state = apply_state_delta(
                    plan.program_store,
                    base_state=current_state,
                    state_delta_ref=artifacts.state_delta_ref,
                    slot_registry=plan.slot_registry,
                    merge_registry=plan.merge_registry,
                )
                last_state_source_ref = artifacts.state_delta_ref
                state_delta_payload = artifacts.state_delta_ref.model_dump(mode="json")
                metrics_payload = artifacts.metrics_ref.model_dump(mode="json")
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
                            outcome: _effect_for_outcome(request, outcome, outcomes[outcome])
                            for outcome in request.selected_outcomes
                        },
                        engine_state={
                            "state_delta_ref": state_delta_refs[-1],
                            "metrics_ref_produced": True,
                            "state_delta_artifact_ref": state_delta_payload,
                            "metrics_artifact_ref": metrics_payload,
                        },
                    )
                )
            method_execution_bundle_ref = None
            binding_set_ref = None
            if method_execution_capture is not None:
                method_execution_bundle_ref = persist_method_execution_capture(
                    plan.program_store,
                    method_execution_capture,
                )
                binding_set_ref = method_execution_capture.method_metric_binding_set_ref
                binding_set_payload = binding_set_ref.model_dump(mode="json")
                bundle_payload = method_execution_bundle_ref.model_dump(mode="json")
                occurrences_by_id = {
                    item.occurrence_id: item for item in method_execution_capture.occurrences
                }
                for point, source in zip(points, method_execution_steps, strict=True):
                    occurrence_rows = []
                    for occurrence_id in source["occurrence_ids"]:
                        occurrence = occurrences_by_id[occurrence_id]
                        occurrence_rows.append(
                            {
                                "occurrence_id": occurrence.occurrence_id,
                                "invocation_id": occurrence.invocation_id,
                                "node_id": occurrence.node_id,
                                "status": "skipped"
                                if occurrence.status == "planned"
                                else occurrence.status,
                            }
                        )
                    point.engine_state["method_execution"] = {
                        "status": "captured",
                        "method_metric_binding_set_ref": binding_set_payload,
                        "method_execution_bundle_ref": bundle_payload,
                        "prestate_ref": source["prestate_ref"],
                        "occurrences": occurrence_rows,
                    }
                    source["method_metric_binding_set_ref"] = binding_set_payload
                    source["method_execution_bundle_ref"] = bundle_payload
                    source["occurrences"] = occurrence_rows
            return SimulationTrajectory(
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
                    "method_execution_sources": method_execution_steps,
                    "method_execution_capture_status": "captured"
                    if method_execution_capture is not None
                    else "not_requested",
                    "requested_step_dispatch_status": "matched",
                    "time_alignment_status": "not_established",
                },
            )

        return _run_cached_replicates(
            request,
            plan,
            decision,
            run_once,
            producer_budget_observer=self._producer_budget_observer,
        )

    def _run_ncm_horizon(
        self,
        request: JointSimulationRequest,
        plan: EnginePlan,
        decision: EngineDecision,
    ) -> list[SimulationTrajectory]:
        if plan.ncm_spec is None or decision.method_fqn is None:
            return []
        method = self._registry.get(decision.method_fqn)
        # Capture and execute the same concrete selected callable. A later
        # registry replacement cannot redirect this already prepared call.
        selected_step = method.pure_step

        from polisyos.runtime.quality.n5_execution_basis import N5ImplementationCapture

        capture = N5ImplementationCapture(
            method=method,
            request=request,
            controller=self,
            method_fqn=decision.method_fqn,
        )

        def run_once(
            run_level: RunLevel,
            subset: tuple[InterventionAtomBinding, ...],
            replication_seed: int,
        ) -> SimulationTrajectory:
            with capture.observe_numerical_call():
                intervention = _ncm_intervention(subset, plan)
                evidence_state, _ = _effective_evidence_state(request)
                evidence = {
                    _engine_variable(variable, plan): float(value)
                    for variable, value in evidence_state.items()
                }
                step = request.horizon.start
                output = selected_step(
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
                    step=step,
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

        with capture:
            trajectories = _run_cached_replicates(
                request,
                plan,
                decision,
                run_once,
                producer_budget_observer=self._producer_budget_observer,
            )
        capture.bind_trajectories(trajectories)
        self._last_n5_implementation_capture = capture
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

        def run_once(
            run_level: RunLevel,
            subset: tuple[InterventionAtomBinding, ...],
            replication_seed: int,
        ) -> SimulationTrajectory:
            params = _coupled_params_for_subset(plan, subset)
            params["n_steps"] = max(1, len(request.horizon.steps()) - 1)
            params["seed"] = int(replication_seed)
            time_alignment = _method_step_parameter_diagnostics(
                method,
                params,
                request.horizon.step,
                parameter_name="delta_a_max",
            )
            if "initial_queue_length" not in params:
                declared_default = _declared_parameter_default(
                    method,
                    "initial_queue_length",
                )
                if declared_default is not _MISSING_OUTCOME:
                    params["initial_queue_length"] = deepcopy(declared_default)
            initial_queue_length = params.get("initial_queue_length", _MISSING_OUTCOME)
            _selected_outcome_value(
                initial_queue_length,
                outcome="final_queue_length",
                engine_kind="coupled_des_abm",
            )
            output = method.pure_step(plan.coupled_state, params)
            result = _engine_result(output, engine_kind="coupled_des_abm")
            requested_steps = request.horizon.steps()
            raw_queue = result.get("queue_length_trajectory", _MISSING_OUTCOME)
            if raw_queue is _MISSING_OUTCOME and len(requested_steps) > 1:
                raise JointSimulationControllerError(
                    "coupled_outcome_missing",
                    "queue_length_trajectory",
                )
            if isinstance(raw_queue, Mapping | str | bytes | bytearray):
                raise JointSimulationControllerError(
                    "coupled_outcome_non_numeric",
                    "queue_length_trajectory",
                )
            if raw_queue is _MISSING_OUTCOME:
                queue_rows: Sequence[Any] = ()
            else:
                try:
                    queue_length = len(raw_queue)
                except TypeError as exc:
                    raise JointSimulationControllerError(
                        "coupled_outcome_non_numeric",
                        "queue_length_trajectory",
                    ) from exc
                required_transitions = max(0, len(requested_steps) - 1)
                if queue_length > required_transitions:
                    raise JointSimulationControllerError(
                        "coupled_trajectory_exceeds_horizon",
                        f"{queue_length}>{required_transitions}",
                    )
                queue_rows = raw_queue
            source_time_trace, source_time_trace_status, source_time_trace_reason = (
                _coupled_source_time_trace(result, queue_rows)
            )
            covered_count = min(len(requested_steps), 1 + len(queue_rows))
            points: list[TrajectoryPoint] = []
            for index, step in enumerate(requested_steps[:covered_count]):
                outcomes = _coupled_outcomes(
                    result,
                    request.selected_outcomes,
                    index,
                    initial_queue_length=initial_queue_length,
                    horizon_length=len(requested_steps),
                )
                points.append(
                    TrajectoryPoint(
                        step=step,
                        outcomes=outcomes,
                        effect={
                            outcome: _effect_for_outcome(request, outcome, outcomes[outcome])
                            for outcome in request.selected_outcomes
                        },
                        engine_state={
                            "coupled_summary": result.get("summary", {}),
                            "queue_length": outcomes.get("final_queue_length"),
                        },
                    )
                )
            return SimulationTrajectory(
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
                    "coverage_status": (
                        "complete" if covered_count == len(requested_steps) else "partial"
                    ),
                    "covered_steps": requested_steps[:covered_count],
                    "requested_steps": requested_steps,
                    "hold_last": False,
                    "source_time_trace": source_time_trace,
                    "source_time_trace_status": source_time_trace_status,
                    "source_time_trace_reason": source_time_trace_reason,
                    **time_alignment,
                },
            )

        return _run_cached_replicates(
            request,
            plan,
            decision,
            run_once,
            producer_budget_observer=self._producer_budget_observer,
        )

    def _run_system_dynamics_horizon(
        self,
        request: JointSimulationRequest,
        plan: EnginePlan,
        decision: EngineDecision,
    ) -> list[SimulationTrajectory]:
        if decision.method_fqn is None:
            return []
        method = self._registry.get(decision.method_fqn)

        def run_once(
            run_level: RunLevel,
            subset: tuple[InterventionAtomBinding, ...],
            replication_seed: int,
        ) -> SimulationTrajectory:
            state = _system_dynamics_state_for_subset(plan, subset)
            params = {
                **plan.system_dynamics_params,
                "n_steps": max(1, len(request.horizon.steps()) - 1),
            }
            params.setdefault("dt", float(request.horizon.step))
            params["seed"] = int(replication_seed)
            time_alignment = _method_step_parameter_diagnostics(
                method,
                params,
                request.horizon.step,
                parameter_name="dt",
            )
            output = method.pure_step(state, params)
            result = _engine_result(output, engine_kind="system_dynamics")
            raw_trajectory = result.get("trajectory", _MISSING_OUTCOME)
            if raw_trajectory is _MISSING_OUTCOME:
                raise JointSimulationControllerError(
                    "system_dynamics_trajectory_missing",
                    decision.method_fqn,
                )
            if isinstance(raw_trajectory, Mapping | str | bytes | bytearray):
                raise JointSimulationControllerError(
                    "system_dynamics_trajectory_malformed",
                    decision.method_fqn,
                )
            try:
                trajectory_length = len(raw_trajectory)
            except TypeError as exc:
                raise JointSimulationControllerError(
                    "system_dynamics_trajectory_malformed",
                    decision.method_fqn,
                ) from exc
            requested_steps = request.horizon.steps()
            covered_count = min(trajectory_length, len(requested_steps))
            if covered_count == 0:
                raise JointSimulationControllerError(
                    "trajectory_coverage_incomplete",
                    decision.method_fqn,
                )
            points: list[TrajectoryPoint] = []
            for index, step in enumerate(requested_steps[:covered_count]):
                stock_values = raw_trajectory[index]
                outcomes = _system_dynamics_outcomes(
                    result,
                    stock_values,
                    request.selected_outcomes,
                    plan,
                    horizon_length=len(requested_steps),
                )
                points.append(
                    TrajectoryPoint(
                        step=step,
                        outcomes=outcomes,
                        effect={
                            outcome: _effect_for_outcome(request, outcome, outcomes[outcome])
                            for outcome in request.selected_outcomes
                        },
                        engine_state={
                            "stock_values": _json_ready(stock_values),
                            "mass_balance": result.get("mass_balance"),
                        },
                    )
                )
            return SimulationTrajectory(
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
                    "coverage_status": (
                        "complete" if covered_count == len(requested_steps) else "partial"
                    ),
                    "covered_steps": requested_steps[:covered_count],
                    "requested_steps": requested_steps,
                    "hold_last": False,
                    **time_alignment,
                },
            )

        return _run_cached_replicates(
            request,
            plan,
            decision,
            run_once,
            producer_budget_observer=self._producer_budget_observer,
        )

    def _run_registry_method_horizon(
        self,
        request: JointSimulationRequest,
        plan: EnginePlan,
        decision: EngineDecision,
    ) -> list[SimulationTrajectory]:
        if decision.method_fqn is None:
            return []
        method = self._registry.get(decision.method_fqn)

        def run_once(
            run_level: RunLevel,
            subset: tuple[InterventionAtomBinding, ...],
            replication_seed: int,
        ) -> SimulationTrajectory:
            state = _method_state_for_subset(plan, subset)
            params = {
                **plan.system_dynamics_params,
                "n_steps": max(1, len(request.horizon.steps()) - 1),
            }
            params.setdefault("dt", float(request.horizon.step))
            params["seed"] = int(replication_seed)
            time_alignment = _method_step_parameter_diagnostics(
                method,
                params,
                request.horizon.step,
                parameter_name="dt",
            )
            output = method.pure_step(state, params)
            result = _engine_result(output, engine_kind="method_registry_estimator")
            raw_trajectory = result.get("trajectory")
            if raw_trajectory is None or isinstance(
                raw_trajectory, Mapping | str | bytes | bytearray
            ):
                raise JointSimulationControllerError(
                    "method_registry_temporal_output_missing",
                    decision.method_fqn,
                )
            try:
                trajectory_length = len(raw_trajectory)
            except TypeError as exc:
                raise JointSimulationControllerError(
                    "trajectory_coverage_incomplete",
                    decision.method_fqn,
                ) from exc
            requested_steps = request.horizon.steps()
            covered_count = min(trajectory_length, len(requested_steps))
            if covered_count == 0:
                raise JointSimulationControllerError(
                    "trajectory_coverage_incomplete",
                    decision.method_fqn,
                )
            points: list[TrajectoryPoint] = []
            for index, step in enumerate(requested_steps[:covered_count]):
                state_values = raw_trajectory[index]
                outcomes = _system_dynamics_outcomes(
                    result,
                    state_values,
                    request.selected_outcomes,
                    plan,
                    horizon_length=len(requested_steps),
                )
                points.append(
                    TrajectoryPoint(
                        step=step,
                        outcomes=outcomes,
                        effect={
                            outcome: _effect_for_outcome(request, outcome, outcomes[outcome])
                            for outcome in request.selected_outcomes
                        },
                        engine_state={
                            "stock_values": _json_ready(state_values),
                            "mass_balance": result.get("mass_balance"),
                        },
                    )
                )
            return SimulationTrajectory(
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
                    "coverage_status": (
                        "complete" if covered_count == len(requested_steps) else "partial"
                    ),
                    "covered_steps": requested_steps[:covered_count],
                    "requested_steps": requested_steps,
                    "hold_last": False,
                    **time_alignment,
                },
            )

        return _run_cached_replicates(
            request,
            plan,
            decision,
            run_once,
            producer_budget_observer=self._producer_budget_observer,
        )


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
        dict.fromkeys(blocker for support in supports for blocker in support.blockers)
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
    classes = tuple(sorted({row.coupling_kind for row in classification.boundary_classifications}))
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


def _temporal_capability_for_output_shape(
    output_shape: EngineOutputShape,
) -> TemporalCapability:
    if output_shape == "static_point":
        return "static"
    if output_shape in {"time_series_trajectory", "program_state_trajectory"}:
        return "multi_period"
    return "unsupported"


def _declared_entry_semantics(
    assumptions: Mapping[str, Any],
) -> EquilibriumSemantics | None:
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


def _default_semantics_for_output_shape(
    output_shape: EngineOutputShape,
) -> EquilibriumSemantics:
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


def _validate_atom_composition(
    plan: EnginePlan,
    atoms: Sequence[InterventionAtomBinding],
) -> None:
    """Resolve the selected plan's complete write set before any producer runs."""
    if plan.engine_kind == "ncm_parallel_worlds":
        _ncm_intervention(atoms, plan)
    elif plan.engine_kind == "coupled_des_abm":
        _coupled_params_for_subset(plan, atoms)
    elif plan.engine_kind == "system_dynamics":
        _system_dynamics_state_for_subset(plan, atoms)
    elif plan.engine_kind == "program_graph":
        _program_parameter_overrides(atoms, plan)
    elif plan.engine_kind == "method_registry_estimator":
        _method_state_for_subset(plan, atoms)


def _causal_assignment_writes(
    atoms: Sequence[InterventionAtomBinding],
    plan: EnginePlan,
    *,
    engine_kind: EngineKind,
    dotted_paths: bool,
) -> dict[tuple[str, ...], float]:
    """Resolve simultaneous direct effects without arrival-order semantics."""
    prefix = _outcome_error_prefix(engine_kind)
    writes: list[tuple[tuple[str, ...], Any, str]] = []
    for atom in atoms:
        for assignment in atom.causal_do_expr.assignments:
            if assignment.value is None:
                raise JointSimulationControllerError(
                    f"value_expr_intervention_not_supported_by_{prefix}_controller",
                    assignment.variable,
                )
            try:
                value = float(assignment.value)
            except (TypeError, ValueError, OverflowError) as exc:
                raise JointSimulationControllerError(
                    "intervention_assignment_non_numeric",
                    assignment.variable,
                ) from exc
            if not np.isfinite(value):
                raise JointSimulationControllerError(
                    "intervention_assignment_non_finite",
                    assignment.variable,
                )
            target = _engine_variable(assignment.variable, plan)
            path = tuple(target.split(".")) if dotted_paths else (target,)
            writes.append((path, value, atom.intervention_id))
    return _resolve_assignment_writes(writes)


def _nested_mapping_writes(
    value: object,
    path: tuple[str, ...],
    source_id: str,
) -> list[tuple[tuple[str, ...], Any, str]]:
    """Flatten nested state overrides to their actual leaf write paths."""
    if isinstance(value, Mapping) and value:
        return [
            write
            for key, item in value.items()
            for write in _nested_mapping_writes(item, (*path, str(key)), source_id)
        ]
    if isinstance(value, np.ndarray) and value.ndim > 0 and value.size:
        return [
            write
            for index, item in enumerate(value)
            for write in _nested_mapping_writes(item, (*path, str(index)), source_id)
        ]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray) and value:
        return [
            write
            for index, item in enumerate(value)
            for write in _nested_mapping_writes(item, (*path, str(index)), source_id)
        ]
    return [(path, value, source_id)]


def _resolve_assignment_writes(
    writes: Sequence[tuple[tuple[str, ...], Any, str]],
) -> dict[tuple[str, ...], Any]:
    """Merge identical writes and reject conflicting or overlapping targets."""
    resolved: dict[tuple[str, ...], tuple[Any, set[str]]] = {}
    for path, value, source_id in writes:
        for prior_path, (prior_value, prior_sources) in resolved.items():
            exact = prior_path == path
            overlap = (len(prior_path) < len(path) and path[: len(prior_path)] == prior_path) or (
                len(path) < len(prior_path) and prior_path[: len(path)] == path
            )
            if exact and _same_assignment_value(prior_value, value):
                prior_sources.add(source_id)
                break
            if exact or overlap:
                sources = ",".join(sorted((*prior_sources, source_id)))
                target = ".".join(path)
                raise JointSimulationControllerError(
                    "intervention_assignment_conflict",
                    f"{target} is assigned incompatibly by {sources}",
                )
        else:
            resolved[path] = (deepcopy(value), {source_id})
    return {path: value for path, (value, _) in sorted(resolved.items())}


def _same_assignment_value(left: object, right: object) -> bool:
    """Compare assignment values without Python's cross-type numeric equality."""
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        if len(left) != len(right):
            return False
        unmatched = list(right.items())
        for key, value in left.items():
            for index, (other_key, other_value) in enumerate(unmatched):
                if _same_assignment_value(key, other_key):
                    if not _same_assignment_value(value, other_value):
                        return False
                    del unmatched[index]
                    break
            else:
                return False
        return not unmatched
    if isinstance(left, np.ndarray) and isinstance(right, np.ndarray):
        if left.dtype != right.dtype or left.shape != right.shape:
            return False
        if left.dtype.hasobject:
            return all(
                _same_assignment_value(left[index], right[index])
                for index in np.ndindex(left.shape)
            )
        return bool(np.array_equal(left, right))
    if (
        isinstance(left, Sequence)
        and isinstance(right, Sequence)
        and not isinstance(left, str | bytes | bytearray)
        and not isinstance(right, str | bytes | bytearray)
    ):
        return len(left) == len(right) and all(
            _same_assignment_value(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    try:
        result = left == right
        return bool(result) if not isinstance(result, np.ndarray) else bool(result.all())
    except (TypeError, ValueError):
        return False


def _outcome_error_prefix(engine_kind: EngineKind) -> str:
    if engine_kind == "ncm_parallel_worlds":
        return "ncm"
    if engine_kind == "coupled_des_abm":
        return "coupled"
    if engine_kind == "system_dynamics":
        return "system_dynamics"
    if engine_kind == "method_registry_estimator":
        return "method_registry"
    return "program_graph"


def _engine_result(output: object, *, engine_kind: EngineKind) -> Mapping[str, Any]:
    """Require the registered method's typed result envelope before projection."""
    prefix = _outcome_error_prefix(engine_kind)
    if not isinstance(output, Mapping):
        raise JointSimulationControllerError(f"{prefix}_result_malformed")
    result = output.get("result", _MISSING_OUTCOME)
    if result is _MISSING_OUTCOME:
        raise JointSimulationControllerError(f"{prefix}_result_missing")
    if not isinstance(result, Mapping):
        raise JointSimulationControllerError(f"{prefix}_result_malformed")
    return result


def _declared_parameter_default(method: object, parameter_name: str) -> object:
    """Read one method-contract default without inventing an adapter fallback."""
    signature = getattr(method, "signature", None)
    parameters = getattr(signature, "parameters", ())
    if not isinstance(parameters, Sequence) or isinstance(parameters, str | bytes):
        return _MISSING_OUTCOME
    for parameter in parameters:
        if getattr(parameter, "name", None) == parameter_name:
            return getattr(parameter, "default", _MISSING_OUTCOME)
    return _MISSING_OUTCOME


def _method_step_parameter_diagnostics(
    method: object,
    parameters: Mapping[str, Any],
    requested_step: int,
    *,
    parameter_name: str,
) -> dict[str, object]:
    """Report adapter parameter equality without claiming emitted-time alignment.

    This comparison describes only the step supplied to the selected method. It does
    not establish what time any returned trajectory row represents.
    """
    signature = getattr(method, "signature", None)
    declared_parameters = getattr(signature, "parameters", ())
    declares_step = isinstance(declared_parameters, Sequence) and any(
        getattr(parameter, "name", None) == parameter_name for parameter in declared_parameters
    )
    effective_step = parameters.get(
        parameter_name,
        _declared_parameter_default(method, parameter_name),
    )
    parsed_step: float | None = None
    if not isinstance(effective_step, bool):
        try:
            candidate = float(effective_step)
        except (TypeError, ValueError, OverflowError):
            pass
        else:
            if np.isfinite(candidate) and candidate > 0:
                parsed_step = candidate
    aligned: bool | None = None
    if declares_step and parsed_step is not None:
        aligned = bool(
            np.isclose(
                parsed_step,
                float(requested_step),
                rtol=0.0,
                atol=1e-12,
            )
        )
    return {
        "requested_time_step": requested_step,
        "method_time_step_parameter": parameter_name,
        "effective_method_time_step": parsed_step,
        "declared_step_parameter_matches_request": aligned,
        "time_alignment_status": "not_established",
    }


def _finite_source_coordinate(value: object) -> float | None:
    """Return a finite coordinate only from a Python or NumPy real scalar."""
    if isinstance(value, bool | np.bool_ | np.ndarray):
        return None
    if not isinstance(value, int | float | np.integer | np.floating):
        return None
    try:
        raw = np.asarray(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if raw.ndim != 0 or raw.dtype.kind not in "iuf":
        return None
    try:
        coordinate = float(raw.item())
    except (TypeError, ValueError, OverflowError):
        return None
    return coordinate if math.isfinite(coordinate) else None


def _coupled_source_time_trace(
    result: Mapping[str, Any],
    queue_rows: Sequence[Any],
) -> tuple[dict[str, object] | None, str, str]:
    """Project actual coupled metrics without inferring units or horizon alignment."""
    raw_initial = result.get("coupled_initial_time", _MISSING_OUTCOME)
    if raw_initial is _MISSING_OUTCOME:
        return None, "not_established", "initial_source_time_missing"
    initial_coordinate = _finite_source_coordinate(raw_initial)
    if initial_coordinate is None:
        return None, "not_established", "initial_source_time_malformed"

    raw_metrics = result.get("metrics", _MISSING_OUTCOME)
    if raw_metrics is _MISSING_OUTCOME:
        return None, "not_established", "source_metrics_missing"
    if not isinstance(raw_metrics, Sequence) or isinstance(raw_metrics, str | bytes | bytearray):
        return None, "not_established", "source_metrics_malformed"
    if len(raw_metrics) != len(queue_rows):
        return None, "not_established", "source_metrics_queue_row_count_mismatch"

    transition_coordinates: list[float] = []
    for index, row in enumerate(raw_metrics):
        if not isinstance(row, Mapping):
            return None, "not_established", f"source_metric_row_malformed:{index}"
        raw_transition = row.get("coupled/time", _MISSING_OUTCOME)
        if raw_transition is _MISSING_OUTCOME:
            return None, "not_established", f"transition_source_time_missing:{index}"
        transition = _finite_source_coordinate(raw_transition)
        if transition is None:
            return None, "not_established", f"transition_source_time_malformed:{index}"
        raw_queue_time = row.get("queue/time", _MISSING_OUTCOME)
        if raw_queue_time is _MISSING_OUTCOME:
            return None, "not_established", f"queue_source_time_missing:{index}"
        queue_time = _finite_source_coordinate(raw_queue_time)
        if queue_time is None:
            return None, "not_established", f"queue_source_time_malformed:{index}"
        if not math.isclose(transition, queue_time, rel_tol=0.0, abs_tol=1e-12):
            return (
                None,
                "not_established",
                f"coupled_queue_source_time_disagreement:{index}",
            )

        metric_queue = _finite_source_coordinate(row.get("queue/queue_length", _MISSING_OUTCOME))
        returned_queue = _finite_source_coordinate(queue_rows[index])
        if metric_queue is None or returned_queue is None:
            return None, "not_established", f"queue_source_value_malformed:{index}"
        if not math.isclose(metric_queue, returned_queue, rel_tol=0.0, abs_tol=1e-12):
            return None, "not_established", f"queue_source_value_disagreement:{index}"
        transition_coordinates.append(transition)

    trace = _CoupledSourceTimeTrace(
        initial_coordinate=initial_coordinate,
        transition_coordinates=tuple(transition_coordinates),
    )
    return (
        trace.model_dump(mode="json"),
        "observed_candidate",
        "physical_unit_origin_and_horizon_relation_not_established",
    )


def _selected_outcome_value(
    value: object,
    *,
    outcome: str,
    engine_kind: EngineKind,
) -> float:
    """Return one real finite selected scalar or a typed missing/invalid refusal."""
    prefix = _outcome_error_prefix(engine_kind)
    if value is _MISSING_OUTCOME:
        raise JointSimulationControllerError(f"{prefix}_outcome_missing", outcome)
    try:
        raw = np.asarray(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise JointSimulationControllerError(f"{prefix}_outcome_non_numeric", outcome) from exc
    if raw.size == 0:
        raise JointSimulationControllerError(f"{prefix}_outcome_missing", outcome)
    if raw.dtype.kind not in "iuf":
        raise JointSimulationControllerError(f"{prefix}_outcome_non_numeric", outcome)
    try:
        numeric = raw.astype(float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise JointSimulationControllerError(f"{prefix}_outcome_non_numeric", outcome) from exc
    if not np.isfinite(numeric).all():
        raise JointSimulationControllerError(f"{prefix}_outcome_non_finite", outcome)
    value_mean = float(np.mean(numeric))
    if not np.isfinite(value_mean):
        raise JointSimulationControllerError(f"{prefix}_outcome_non_finite", outcome)
    return value_mean


_MISSING_OUTCOME = object()


def _ncm_intervention(
    atoms: Sequence[InterventionAtomBinding],
    plan: EnginePlan,
) -> dict[str, float]:
    writes = _causal_assignment_writes(
        atoms,
        plan,
        engine_kind="ncm_parallel_worlds",
        dotted_paths=False,
    )
    return {path[0]: float(value) for path, value in writes.items()}


def _program_parameter_overrides(
    atoms: Sequence[InterventionAtomBinding],
    plan: EnginePlan,
) -> dict[str, dict[str, Any]] | None:
    writes: list[tuple[tuple[str, ...], Any, str]] = []
    for atom in atoms:
        atom_overrides = plan.program_parameter_overrides_by_atom.get(atom.intervention_id, {})
        for node_id, values in atom_overrides.items():
            if not isinstance(values, Mapping):
                raise JointSimulationControllerError(
                    "program_parameter_override_malformed",
                    str(node_id),
                )
            writes.extend(
                ((str(node_id), str(parameter)), value, atom.intervention_id)
                for parameter, value in values.items()
            )
    resolved = _resolve_assignment_writes(writes)
    overrides: dict[str, dict[str, Any]] = {}
    for path, value in resolved.items():
        node_id, parameter = path
        overrides.setdefault(node_id, {})[parameter] = deepcopy(value)
    return overrides or None


def _coupled_params_for_subset(
    plan: EnginePlan,
    atoms: Sequence[InterventionAtomBinding],
) -> dict[str, Any]:
    params = deepcopy(plan.coupled_params)
    writes = _causal_assignment_writes(
        atoms,
        plan,
        engine_kind="coupled_des_abm",
        dotted_paths=False,
    )
    for path, value in writes.items():
        params[path[0]] = float(value)
    return params


def _coupled_queue_value(
    result: Mapping[str, Any],
    index: int,
    *,
    initial_queue_length: object,
) -> float:
    """Resolve the actual initial state or emitted post-transition queue row."""
    if index == 0:
        return _selected_outcome_value(
            initial_queue_length,
            outcome="final_queue_length",
            engine_kind="coupled_des_abm",
        )
    queue = result.get("queue_length_trajectory", _MISSING_OUTCOME)
    if queue is _MISSING_OUTCOME or isinstance(queue, Mapping | str | bytes | bytearray):
        raise JointSimulationControllerError("coupled_outcome_missing", "final_queue_length")
    try:
        queue_length = len(queue)
    except TypeError as exc:
        raise JointSimulationControllerError(
            "coupled_outcome_non_numeric", "final_queue_length"
        ) from exc
    trajectory_index = index - 1
    if trajectory_index >= queue_length:
        raise JointSimulationControllerError("coupled_outcome_missing", "final_queue_length")
    return _selected_outcome_value(
        queue[trajectory_index],
        outcome="final_queue_length",
        engine_kind="coupled_des_abm",
    )


def _coupled_outcomes(
    result: Mapping[str, Any],
    selected_outcomes: Sequence[str],
    index: int,
    *,
    initial_queue_length: object,
    horizon_length: int,
) -> dict[str, float]:
    outcomes: dict[str, float] = {}
    for outcome in selected_outcomes:
        if outcome == "final_queue_length":
            outcomes[outcome] = _coupled_queue_value(
                result,
                index,
                initial_queue_length=initial_queue_length,
            )
        else:
            if horizon_length > 1 and index < horizon_length - 1:
                raise JointSimulationControllerError(
                    "coupled_temporal_outcome_series_missing",
                    outcome,
                )
            value = result.get(outcome, _MISSING_OUTCOME)
            outcomes[outcome] = _selected_outcome_value(
                value,
                outcome=outcome,
                engine_kind="coupled_des_abm",
            )
    return outcomes


def _method_state_for_subset(
    plan: EnginePlan,
    atoms: Sequence[InterventionAtomBinding],
) -> dict[str, Any]:
    if plan.system_dynamics_state:
        return _system_dynamics_state_for_subset(plan, atoms)
    if plan.coupled_state:
        state = deepcopy(plan.coupled_state)
        writes = _causal_assignment_writes(
            atoms,
            plan,
            engine_kind="method_registry_estimator",
            dotted_paths=True,
        )
        for path, value in writes.items():
            target = ".".join(path)
            try:
                _state_path_value(state, target)
                _assign_path_value(state, target, float(value))
                written = _state_path_value(state, target)
                if float(written) != float(value):
                    raise ValueError("method_registry_assignment_not_applied")
            except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
                raise JointSimulationControllerError(
                    "method_registry_intervention_binding_missing",
                    target,
                ) from exc
        return state
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
        try:
            value = _state_path_value(state, path)
        except (AttributeError, KeyError, IndexError, TypeError) as exc:
            raise JointSimulationControllerError(
                "program_graph_outcome_missing",
                path,
            ) from exc
        outcomes[outcome] = _selected_outcome_value(
            value,
            outcome=outcome,
            engine_kind="program_graph",
        )
    return outcomes


def _state_path_value(state: object, path: str) -> object:
    value = state
    for part in path.split("."):
        if isinstance(value, Mapping):
            value = value[part]
        elif isinstance(value, list | tuple | np.ndarray):
            value = value[int(part)]
        else:
            value = getattr(value, part)
    return value


def _engine_variable(variable: str, plan: EnginePlan) -> str:
    return plan.variable_map.get(variable, variable)


def _ncm_outcomes(
    output: object,
    selected_outcomes: Sequence[str],
    plan: EnginePlan,
) -> dict[str, float]:
    if not isinstance(output, Mapping):
        raise JointSimulationControllerError("ncm_result_malformed")
    payload = output.get("counterfactual_result")
    if not isinstance(payload, Mapping):
        raise JointSimulationControllerError("ncm_world_summaries_missing")
    summaries = payload.get("world_summaries")
    if (
        not isinstance(summaries, Sequence)
        or isinstance(summaries, str | bytes | bytearray)
        or not summaries
        or not isinstance(summaries[0], Mapping)
    ):
        raise JointSimulationControllerError("ncm_world_summaries_missing")
    summary = summaries[0]
    outcomes: dict[str, float] = {}
    for outcome in selected_outcomes:
        engine_outcome = _engine_variable(outcome, plan)
        stats = summary.get(engine_outcome)
        if not isinstance(stats, Mapping) or "mean" not in stats:
            raise JointSimulationControllerError("ncm_outcome_missing", engine_outcome)
        outcomes[outcome] = _selected_outcome_value(
            stats["mean"],
            outcome=engine_outcome,
            engine_kind="ncm_parallel_worlds",
        )
    return outcomes


def _system_dynamics_state_for_subset(
    plan: EnginePlan,
    atoms: Sequence[InterventionAtomBinding],
) -> dict[str, Any]:
    writes = [
        write
        for atom in atoms
        for key, value in plan.system_dynamics_state_overrides_by_atom.get(
            atom.intervention_id, {}
        ).items()
        for write in _nested_mapping_writes(value, (str(key),), atom.intervention_id)
    ]
    direct_writes = _causal_assignment_writes(
        atoms,
        plan,
        engine_kind=plan.engine_kind,
        dotted_paths=True,
    )
    writes.extend((path, value, "direct_effect") for path, value in direct_writes.items())
    _resolve_assignment_writes(writes)

    state = deepcopy(plan.system_dynamics_state)
    for atom in sorted(atoms, key=lambda item: item.intervention_id):
        _merge_mapping(
            state,
            plan.system_dynamics_state_overrides_by_atom.get(atom.intervention_id, {}),
        )
    for path, value in direct_writes.items():
        target = ".".join(path)
        if target not in state and "." not in target:
            raise JointSimulationControllerError(
                "system_dynamics_intervention_binding_missing",
                target,
            )
        try:
            _assign_path_value(state, target, float(value))
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
            raise JointSimulationControllerError(
                "system_dynamics_intervention_binding_missing",
                target,
            ) from exc
    return state


def _system_dynamics_outcomes(
    result: Mapping[str, Any],
    stock_values: object,
    selected_outcomes: Sequence[str],
    plan: EnginePlan,
    *,
    horizon_length: int,
) -> dict[str, float]:
    prefix = _outcome_error_prefix(plan.engine_kind)
    try:
        stocks = np.asarray(stock_values)
    except (TypeError, ValueError, OverflowError) as exc:
        raise JointSimulationControllerError(
            f"{prefix}_outcome_non_numeric",
            "trajectory",
        ) from exc
    if stocks.dtype.kind not in "iuf":
        raise JointSimulationControllerError(
            f"{prefix}_outcome_non_numeric",
            "trajectory",
        )
    if stocks.ndim != 1:
        raise JointSimulationControllerError(
            f"{prefix}_outcome_non_numeric",
            "trajectory",
        )
    outcomes: dict[str, float] = {}
    for outcome in selected_outcomes:
        target = _engine_variable(outcome, plan)
        if target == "mass_balance":
            value = result.get("mass_balance", _MISSING_OUTCOME)
            selected_value = _selected_outcome_value(
                value,
                outcome=outcome,
                engine_kind=plan.engine_kind,
            )
            if horizon_length > 1:
                raise JointSimulationControllerError(
                    f"{prefix}_temporal_outcome_series_missing",
                    outcome,
                )
            outcomes[outcome] = selected_value
            continue
        index = _stock_index(target)
        if index is None:
            value = result.get(target, _MISSING_OUTCOME)
            selected_value = _selected_outcome_value(
                value,
                outcome=outcome,
                engine_kind=plan.engine_kind,
            )
            if horizon_length > 1:
                raise JointSimulationControllerError(
                    f"{prefix}_temporal_outcome_series_missing",
                    outcome,
                )
            outcomes[outcome] = selected_value
            continue
        if index < 0 or index >= stocks.shape[0]:
            raise JointSimulationControllerError(
                f"{prefix}_outcome_missing",
                outcome,
            )
        outcomes[outcome] = _selected_outcome_value(
            stocks[index],
            outcome=outcome,
            engine_kind=plan.engine_kind,
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
    value = float(request.baseline_state[outcome])
    if not np.isfinite(value):
        raise JointSimulationControllerError(
            "baseline_state_nonfinite_for_outcome",
            outcome,
        )
    return value


def _effect_for_outcome(
    request: JointSimulationRequest,
    outcome: str,
    value: float,
) -> float:
    """Compute an effect only against the request's explicit comparator."""

    return float(value) - _baseline_value(request, outcome)


_DERIVED_INTERACTION_SAMPLE_KEY = "derived_effect"


def _scope_samples_by_seed(
    point: TrajectoryPoint,
) -> dict[int, ReplicationSample] | None:
    summary = point.replication_sampling
    if summary is None:
        return None
    return {sample.seed: sample for sample in summary.samples}


def _paired_replication_summary(
    *,
    sample_maps: Mapping[str, Mapping[int, ReplicationSample] | None],
    expected_seeds: Sequence[int],
    outcome: str,
    base_scope: str,
    value_for_seed: Callable[[Mapping[str, ReplicationSample]], float],
) -> ReplicationSamplingSummary | None:
    """Summarize a derived effect only when every selected scope shares all seeds."""

    seeds = tuple(expected_seeds)
    if not seeds or base_scope not in sample_maps:
        return None
    if any(samples is None or set(samples) != set(seeds) for samples in sample_maps.values()):
        return None
    typed_maps = {scope: samples for scope, samples in sample_maps.items() if samples is not None}
    derived_samples: list[ReplicationSample] = []
    for seed in seeds:
        source_samples = {scope: samples[seed] for scope, samples in typed_maps.items()}
        if any(outcome not in sample.outcomes for sample in source_samples.values()):
            return None
        value = float(value_for_seed(source_samples))
        if not math.isfinite(value):
            return None
        base_sample = source_samples[base_scope]
        derived_samples.append(
            ReplicationSample(
                seed=seed,
                engine_state={
                    "source_scope_engine_states": {
                        scope: sample.engine_state for scope, sample in source_samples.items()
                    }
                },
                outcomes={outcome: float(base_sample.outcomes[outcome])},
                effects={_DERIVED_INTERACTION_SAMPLE_KEY: value},
            )
        )
    values = [sample.effects[_DERIVED_INTERACTION_SAMPLE_KEY] for sample in derived_samples]
    outcome_values = [sample.outcomes[outcome] for sample in derived_samples]
    standard_error = _sample_standard_error(values)
    outcome_standard_error = _sample_standard_error(outcome_values)
    return ReplicationSamplingSummary(
        status="standard_error_not_estimated" if len(seeds) == 1 else "estimated",
        replicate_count=len(seeds),
        seeds=seeds,
        samples=tuple(derived_samples),
        outcomes_standard_error={outcome: outcome_standard_error},
        effects_standard_error={_DERIVED_INTERACTION_SAMPLE_KEY: standard_error},
    )


def _interaction_terms(
    request: JointSimulationRequest,
    coverage: _InteractionCoverage,
    *,
    replication_seeds: Sequence[int] | None = None,
    sampling_issues: list[str] | None = None,
) -> list[InteractionTerm]:
    """Build pairwise means and recomputable shared-seed effect samples."""

    return _interaction_terms_from_fields(
        atom_ids=tuple(atom.intervention_id for atom in request.intervention_atoms),
        selected_outcomes=request.selected_outcomes,
        coverage=coverage,
        replication_seeds=replication_seeds,
        sampling_issues=sampling_issues,
    )


def _interaction_terms_from_fields(
    *,
    atom_ids: Sequence[str],
    selected_outcomes: Sequence[str],
    coverage: _InteractionCoverage,
    replication_seeds: Sequence[int] | None,
    sampling_issues: list[str] | None = None,
) -> list[InteractionTerm]:
    normalized_atoms = tuple(atom_ids)
    scope_index = coverage.by_scope
    terms: list[InteractionTerm] = []
    for pair in itertools.combinations(normalized_atoms, 2):
        trajectory = scope_index.get(("pairwise", tuple(pair)))
        left = scope_index.get(("individual", (pair[0],)))
        right = scope_index.get(("individual", (pair[1],)))
        if trajectory is None or left is None or right is None:
            continue
        left_by_step = {point.step: point for point in left.points}
        right_by_step = {point.step: point for point in right.points}
        pair_by_step = {point.step: point for point in trajectory.points}
        for outcome in selected_outcomes:
            by_step: dict[int, float] = {}
            sampling_by_step: dict[int, ReplicationSamplingSummary] = {}
            for step in coverage.expected_steps:
                if (
                    step not in pair_by_step
                    or step not in left_by_step
                    or step not in right_by_step
                ):
                    continue
                by_step[step] = float(
                    pair_by_step[step].effect[outcome]
                    - left_by_step[step].effect[outcome]
                    - right_by_step[step].effect[outcome]
                )
                if replication_seeds is not None:
                    sample_maps = {
                        "pairwise": _scope_samples_by_seed(pair_by_step[step]),
                        "individual_left": _scope_samples_by_seed(left_by_step[step]),
                        "individual_right": _scope_samples_by_seed(right_by_step[step]),
                    }
                    summary = _paired_replication_summary(
                        sample_maps=sample_maps,
                        expected_seeds=replication_seeds,
                        outcome=outcome,
                        base_scope="pairwise",
                        value_for_seed=lambda samples, selected_outcome=outcome: (
                            samples["pairwise"].effects[selected_outcome]
                            - samples["individual_left"].effects[selected_outcome]
                            - samples["individual_right"].effects[selected_outcome]
                        ),
                    )
                    if summary is not None:
                        sampling_by_step[step] = summary
                    elif sampling_issues is not None:
                        sampling_issues.append(
                            f"pairwise_sampling_not_established:{outcome}:{step}:" + ",".join(pair)
                        )
            if by_step:
                terms.append(
                    InteractionTerm(
                        atom_ids=pair,
                        outcome=outcome,
                        by_step=by_step,
                        replication_sampling_by_step=sampling_by_step,
                    )
                )
    return terms


def _higher_order_residuals_from_fields(
    *,
    atom_ids: Sequence[str],
    selected_outcomes: Sequence[str],
    coverage: _InteractionCoverage,
) -> dict[str, dict[int, float]]:
    """Compute aggregate order-three-plus residual means from selected scopes."""

    normalized_atoms = tuple(atom_ids)
    if len(normalized_atoms) < 3 or coverage.issues:
        return {}
    individual = {
        atom_id: coverage.by_scope.get(("individual", (atom_id,))) for atom_id in normalized_atoms
    }
    pairs = tuple(itertools.combinations(normalized_atoms, 2))
    pairwise = {pair: coverage.by_scope.get(("pairwise", pair)) for pair in pairs}
    joint = coverage.by_scope.get(("joint", normalized_atoms))
    if joint is None or any(item is None for item in (*individual.values(), *pairwise.values())):
        return {}
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
    residuals: dict[str, dict[int, float]] = {}
    for outcome in selected_outcomes:
        by_step: dict[int, float] = {}
        for step in coverage.expected_steps:
            individual_sum = sum(
                individual_points[atom_id][step].effect[outcome] for atom_id in normalized_atoms
            )
            pair_interaction_sum = sum(
                pairwise_points[pair][step].effect[outcome]
                - sum(individual_points[atom_id][step].effect[outcome] for atom_id in pair)
                for pair in pairs
            )
            by_step[step] = float(
                joint_points[step].effect[outcome] - individual_sum - pair_interaction_sum
            )
        residuals[outcome] = by_step
    return residuals


def _higher_order_residual_sampling(
    request: JointSimulationRequest,
    coverage: _InteractionCoverage,
    *,
    replication_seeds: Sequence[int],
) -> tuple[dict[str, dict[int, ReplicationSamplingSummary]], tuple[str, ...]]:
    """Pair every selected higher-order residual by actual common replicate seed."""

    return _higher_order_residual_sampling_from_fields(
        atom_ids=tuple(atom.intervention_id for atom in request.intervention_atoms),
        selected_outcomes=request.selected_outcomes,
        coverage=coverage,
        replication_seeds=replication_seeds,
    )


def _higher_order_residual_sampling_from_fields(
    *,
    atom_ids: Sequence[str],
    selected_outcomes: Sequence[str],
    coverage: _InteractionCoverage,
    replication_seeds: Sequence[int],
) -> tuple[dict[str, dict[int, ReplicationSamplingSummary]], tuple[str, ...]]:
    """Recompute aggregate order-three-plus replicate vectors from common seeds."""

    normalized_atoms = tuple(atom_ids)
    if len(normalized_atoms) < 3:
        return {}, ()
    if coverage.issues:
        return {}, ("interaction_evidence_incomplete",)
    individual = {
        atom_id: coverage.by_scope.get(("individual", (atom_id,))) for atom_id in normalized_atoms
    }
    pairs = tuple(itertools.combinations(normalized_atoms, 2))
    pairwise = {pair: coverage.by_scope.get(("pairwise", pair)) for pair in pairs}
    joint = coverage.by_scope.get(("joint", normalized_atoms))
    if joint is None or any(item is None for item in (*individual.values(), *pairwise.values())):
        return {}, ("interaction_evidence_incomplete",)
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
    output: dict[str, dict[int, ReplicationSamplingSummary]] = {}
    issues: list[str] = []
    for outcome in selected_outcomes:
        by_step: dict[int, ReplicationSamplingSummary] = {}
        for step in coverage.expected_steps:
            scopes: dict[str, dict[int, ReplicationSample] | None] = {
                "joint": _scope_samples_by_seed(joint_points[step])
            }
            for atom_id in normalized_atoms:
                scopes[f"individual:{atom_id}"] = _scope_samples_by_seed(
                    individual_points[atom_id][step]
                )
            for pair in pairs:
                scopes[f"pairwise:{pair[0]},{pair[1]}"] = _scope_samples_by_seed(
                    pairwise_points[pair][step]
                )

            def residual_for_seed(
                samples: Mapping[str, ReplicationSample],
                selected_outcome: str = outcome,
            ) -> float:
                individual_sum = sum(
                    samples[f"individual:{atom_id}"].effects[selected_outcome]
                    for atom_id in normalized_atoms
                )
                pair_interaction_sum = sum(
                    samples[f"pairwise:{pair[0]},{pair[1]}"].effects[selected_outcome]
                    - samples[f"individual:{pair[0]}"].effects[selected_outcome]
                    - samples[f"individual:{pair[1]}"].effects[selected_outcome]
                    for pair in pairs
                )
                return float(
                    samples["joint"].effects[selected_outcome]
                    - individual_sum
                    - pair_interaction_sum
                )

            summary = _paired_replication_summary(
                sample_maps=scopes,
                expected_seeds=replication_seeds,
                outcome=outcome,
                base_scope="joint",
                value_for_seed=residual_for_seed,
            )
            if summary is None:
                issues.append(f"higher_order_sampling_not_established:{outcome}:{step}")
            else:
                by_step[step] = summary
        if by_step:
            output[outcome] = by_step
    return output, tuple(sorted(set(issues)))


def _interaction_sampling_status(
    interaction_terms: (
        Mapping[tuple[tuple[str, ...], str], Mapping[int, ReplicationSamplingSummary]]
        | Sequence[InteractionTerm]
    ),
    residual_sampling: Mapping[str, Mapping[int, ReplicationSamplingSummary]],
    sampling_issues: Sequence[str],
    *,
    no_interactions_applicable: bool = False,
) -> Literal["estimated", "standard_error_not_estimated", "not_established"]:
    summaries: list[ReplicationSamplingSummary] = []
    if isinstance(interaction_terms, Mapping):
        summaries.extend(
            summary for by_step in interaction_terms.values() for summary in by_step.values()
        )
    else:
        summaries.extend(
            summary
            for term in interaction_terms
            for summary in term.replication_sampling_by_step.values()
        )
    summaries.extend(
        summary for by_step in residual_sampling.values() for summary in by_step.values()
    )
    if sampling_issues:
        return "not_established"
    if not summaries:
        return "estimated" if no_interactions_applicable else "not_established"
    if any(
        summary.status == "standard_error_not_estimated"
        or any(value is None for value in summary.effects_standard_error.values())
        for summary in summaries
    ):
        return "standard_error_not_estimated"
    return "estimated"


def _sampling_variation_observed(
    interaction_terms: Sequence[InteractionTerm],
    residual_sampling: Mapping[str, Mapping[int, ReplicationSamplingSummary]],
) -> bool:
    summaries = [
        summary
        for term in interaction_terms
        for summary in term.replication_sampling_by_step.values()
    ] + [summary for by_step in residual_sampling.values() for summary in by_step.values()]
    return any(
        value is not None and float(value) > 0.0
        for summary in summaries
        for value in summary.effects_standard_error.values()
    )


def _recompute_result_interaction_sampling(
    result: JointSimulationResult,
) -> tuple[
    tuple[InteractionTerm, ...],
    dict[str, dict[int, float]],
    dict[str, dict[int, ReplicationSamplingSummary]],
    tuple[str, ...],
    tuple[str, ...],
]:
    """Recompute pair and residual draws from the persisted trajectory objects."""

    coverage = _interaction_coverage_for_fields(
        atom_ids=result.atom_ids,
        selected_outcomes=result.selected_outcomes,
        expected_steps=result.horizon.steps(),
        trajectories=result.trajectories,
    )
    seeds = tuple(int(seed) for seed in result.diagnostics.get("replication_seeds", ()))
    sampling_issues: list[str] = []
    expected_terms = tuple(
        _interaction_terms_from_fields(
            atom_ids=result.atom_ids,
            selected_outcomes=result.selected_outcomes,
            coverage=coverage,
            replication_seeds=seeds,
            sampling_issues=sampling_issues,
        )
    )
    expected_residuals = _higher_order_residuals_from_fields(
        atom_ids=result.atom_ids,
        selected_outcomes=result.selected_outcomes,
        coverage=coverage,
    )
    expected_residual_sampling: dict[str, dict[int, ReplicationSamplingSummary]] = {}
    if len(result.atom_ids) >= 3 and not coverage.issues:
        # Reconstructing the request is unnecessary: this generic helper consumes only the
        # declared atom/outcome/scope set and the common seed denominator.
        expected_residual_sampling, residual_issues = _higher_order_residual_sampling_from_fields(
            atom_ids=result.atom_ids,
            selected_outcomes=result.selected_outcomes,
            coverage=coverage,
            replication_seeds=seeds,
        )
        sampling_issues.extend(residual_issues)
    if coverage.issues:
        sampling_issues.append("interaction_evidence_incomplete")
    return (
        expected_terms,
        expected_residuals,
        expected_residual_sampling,
        tuple(sorted(set(sampling_issues))),
        coverage.issues,
    )


def _numeric_interaction_classification(
    *,
    interaction_terms: Sequence[InteractionTerm],
    higher_order_residuals: Mapping[str, Mapping[int, float]],
    higher_order_residual_sampling: Mapping[str, Mapping[int, ReplicationSamplingSummary]],
    sampling_status: Literal["estimated", "standard_error_not_estimated", "not_established"],
    sampling_issues: Sequence[str],
    interaction_evidence_issues: Sequence[str],
    aggregate_order_three_plus: bool,
    interaction_required: bool = True,
) -> Literal["none", "additive", "non_additive", "unsupported"]:
    """Classify only a finite selected-model estimate with complete paired uncertainty."""

    if not interaction_required and sampling_status == "estimated" and not sampling_issues:
        return "none"
    if (
        sampling_status != "estimated"
        or sampling_issues
        or _sampling_variation_observed(interaction_terms, higher_order_residual_sampling)
    ):
        return "unsupported"
    any_nonzero = any(
        abs(value) > 1e-12 for term in interaction_terms for value in term.by_step.values()
    ) or any(
        abs(value) > 1e-12
        for by_step in higher_order_residuals.values()
        for value in by_step.values()
    )
    if any_nonzero:
        return "non_additive"
    if interaction_evidence_issues or aggregate_order_three_plus:
        return "unsupported"
    return "additive"


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
    higher_order_residual_sampling: Mapping[str, Mapping[int, ReplicationSamplingSummary]] = {},
    interaction_sampling_status: Literal[
        "estimated", "standard_error_not_estimated", "not_established"
    ] = "not_established",
    interaction_sampling_issues: Sequence[str] = (),
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
    sampling_issues = tuple(
        sorted(set(interaction_sampling_issues) | set(interaction_evidence_issues))
    )
    basis: Literal["finite_checked_model_point_estimate_only", "not_established"] = (
        "finite_checked_model_point_estimate_only"
        if interaction_sampling_status == "estimated" and not sampling_issues
        else "not_established"
    )
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
            numeric_interaction_basis="not_established",
            interaction_sampling_status=interaction_sampling_status,
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
    numeric_interaction = _numeric_interaction_classification(
        interaction_terms=interaction_terms,
        higher_order_residuals=higher_order_residuals,
        higher_order_residual_sampling=higher_order_residual_sampling,
        sampling_status=interaction_sampling_status,
        sampling_issues=sampling_issues,
        interaction_evidence_issues=interaction_evidence_issues,
        aggregate_order_three_plus=aggregate_order_three_plus,
        interaction_required=len(request.intervention_atoms) >= 2,
    )
    evidence_limitations: list[str] = []
    if interaction_evidence_issues:
        evidence_limitations.append("interaction_evidence_incomplete")
    if interaction_sampling_issues or interaction_sampling_status != "estimated":
        evidence_limitations.append("interaction_sampling_not_established")
    if _sampling_variation_observed(interaction_terms, higher_order_residual_sampling):
        evidence_limitations.append("interaction_sampling_variation_observed")
    if aggregate_order_three_plus:
        evidence_limitations.append("aggregate_order_3_plus_not_identified")
    return FeedbackClassification(
        numeric_interaction=numeric_interaction,
        numeric_interaction_basis=basis,
        interaction_sampling_status=interaction_sampling_status,
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
    "JOINT_SIMULATION_HORIZON_PAIRED_INTERACTION_UNCERTAINTY_SCHEMA_VERSION",
    "JOINT_SIMULATION_HORIZON_REPLICATION_UNCERTAINTY_SCHEMA_VERSION",
    "JOINT_SIMULATION_HORIZON_SCHEMA_VERSION",
    "JOINT_SIMULATION_HORIZON_STATE_CONSUMPTION_SCHEMA_VERSION",
    "JOINT_SIMULATION_HORIZON_V1_SCHEMA_VERSION",
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
    "ReplicationSample",
    "ReplicationSamplingSummary",
    "SimulationProofReceipt",
    "SimulationTrajectory",
    "TrajectoryPoint",
    "build_content_bound_simulation_receipt",
    "verify_simulation_receipt",
]
