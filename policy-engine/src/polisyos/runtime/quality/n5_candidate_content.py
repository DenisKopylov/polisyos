"""Bridge native candidate N5 calls to persisted, limited content observations.

This is producer observation, not independent verification or protected-use
permission. Historical receipts remain readable without a process-session token.
Current candidate retention additionally compares the declared numerical image
and actual selected callable; unresolved closure remains an explicit limitation.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import types
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key
from polisyos.runtime.quality.n5_execution_basis import (
    GENERIC_FOUNDRY_CALL_NORMALIZATION,
    N5ControlledCallCaptureV3,
    N5ExecutionContentWitnessV3,
    N5ProductionImage,
    _require_n5_json_wire_domain,
    capture_n5_production_image,
    exact_n5_content_bytes,
    exact_n5_content_hash,
    snapshot_foundry_call_value,
    snapshot_foundry_mechanism_call,
    snapshot_n5_callable_content_v3,
)
from polisyos.runtime.quality.n5_execution_profile import (
    N5BackendObservation,
    N5NativeExecutionProfile,
    N5ProfileSetting,
    bind_n5_backend_observation,
    observe_n5_native_execution_profile,
    reconcile_recorded_n5_profile_content,
    reconcile_recorded_n5_profile_current_bytes,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from polisyos.core.artifacts import CoreJSONArtifactStore
    from polisyos.runtime.quality.joint_simulation_horizon import (
        EngineDecision,
        EnginePlan,
        JointSimulationHorizonController,
        JointSimulationRequest,
        JointSimulationResult,
        PreparedJointSimulationConfiguration,
    )
    from polisyos.runtime.quality.model_input_requirements import ProgramGraphInputPreflight
    from polisyos.runtime.quality.n5_replay_appointment import N5BlindReplayLaunchSpecV2
    from polisyos.runtime.quality.n5_replay_execution import (
        N5OriginalPreflight,
        N5OriginalProducerAction,
        N5ReplayPreflight,
    )
    from polisyos.scientist.orchestration.engine import ProducerBudgetObserver

CONTENT_OBSERVATION_KEY = "candidate_n5_execution_content_observation"
_ResultT = TypeVar("_ResultT")
_ACTIVE: ContextVar[CandidateN5ContentRun | None] = ContextVar(
    "policyos_candidate_n5_content_run", default=None
)
CANDIDATE_CONTENT_RESIDUALS = (
    "full_readset_completeness_not_established",
    "transient_global_cell_registry_substitution_not_established",
    "generated_code_provenance_not_established",
    "loaded_code_to_file_bytes_association_not_independently_reconciled",
    "interpreter_and_os_integrity_not_established",
    "protected_reuse_not_established",
)


class CandidateN5Completion(BaseModel):
    """Physical-plan denominator and actual fully completed work identities."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    planned_units: tuple[tuple[str, int], ...]
    completed_units: tuple[tuple[str, int], ...]
    failed_units: tuple[tuple[str, int], ...] = ()
    interruption_reason: str | None = None
    status: Literal["recomputed", "not_established"]

    @model_validator(mode="after")
    def _complete_plan(self) -> Self:
        expected = bool(self.planned_units) and (
            len(set(self.planned_units)) == len(self.planned_units)
            and len(set(self.completed_units)) == len(self.completed_units)
            and set(self.planned_units) == set(self.completed_units)
            and not self.failed_units
            and self.interruption_reason is None
        )
        if (self.status == "recomputed") != expected:
            raise ValueError("candidate_n5_completion_status_mismatch")
        return self


class CandidateN5ContentObservation(BaseModel):
    """A result-bound observation with no production or publication authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["CandidateN5ContentObservation@1.0"] = (
        "CandidateN5ContentObservation@1.0"
    )
    authority_purpose: Literal["candidate_declared_numerical_basis_only"] = (
        "candidate_declared_numerical_basis_only"
    )
    input_ref_identity: tuple[str, str, str, str | None]
    method_fqn: str = Field(min_length=1)
    witness: N5ExecutionContentWitnessV3
    execution_profile: N5NativeExecutionProfile
    profile_stability: Literal["recomputed", "not_established"]
    source_image_stability: Literal["recomputed", "not_established"]
    consumed_configuration: dict[str, object]
    completion: CandidateN5Completion
    result_without_observation_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    closure_residual_profile: Literal["candidate-n5-declared-basis-residuals/1"] = (
        "candidate-n5-declared-basis-residuals/1"
    )
    closure_residuals: tuple[str, ...] = CANDIDATE_CONTENT_RESIDUALS
    independent_verification: Literal["not_established"] = "not_established"
    protected_use_allowed: Literal[False] = False
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _bound_content(self) -> Self:
        if self.closure_residuals != CANDIDATE_CONTENT_RESIDUALS:
            raise ValueError("candidate_n5_content_residual_profile_mismatch")
        if self.content_hash != exact_n5_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("candidate_n5_content_observation_hash_mismatch")
        return self


class GenericProgramGraphCallObservation(BaseModel):
    """Bound call and producer-observed state from the selected Foundry graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    plan_index: int = Field(ge=0, strict=True)
    node_id: str = Field(min_length=1)
    callable_receiver_hex: str | None = Field(default=None, max_length=131072)
    key_hex: str | None = Field(default=None, max_length=131072)
    target_mask_hex: str | None = Field(default=None, max_length=131072)
    state_ref: ArtifactRef | None = None
    receiver_stable: bool = False
    state_matches_base: bool = False
    status: Literal["returned", "raised", "not_established"]
    reason_codes: tuple[str, ...] = ()


class GenericProgramGraphStepObservation(BaseModel):
    """One physical unit's selected graph step and complete node denominator."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    physical_spec_ref: str = Field(pattern=r"^[0-9a-f]{64}$")
    replication_seed: int = Field(strict=True)
    step: int = Field(ge=0, strict=True)
    effective_seed: int = Field(strict=True)
    base_state_ref: ArtifactRef | None = None
    planned_nodes: tuple[tuple[str, str, str | None], ...]
    completed_nodes: tuple[tuple[int, str, Literal["succeeded", "skipped", "failed"]], ...]
    calls: tuple[GenericProgramGraphCallObservation, ...]
    graph_finished: bool
    predicate_provenance: Literal["recomputed", "not_established"]
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _complete_step(self) -> Self:
        if (self.predicate_provenance == "recomputed") == bool(self.reason_codes):
            raise ValueError("generic_program_graph_step_predicate_mismatch")
        if self.predicate_provenance == "recomputed":
            if (
                not self.graph_finished
                or self.base_state_ref is None
                or self.base_state_ref.kind != "foundry.state_snapshot"
                or self.base_state_ref.media_type != "application/json"
                or self.base_state_ref.manifest_profile_sha256 is None
                or any(
                    not (
                        (kind == "mechanism" and op_kind is None)
                        or (
                            kind == "op"
                            and op_kind
                            in {"make_mask", "apply_mechanism", "merge_state", "check_constraints"}
                        )
                    )
                    for _, kind, op_kind in self.planned_nodes
                )
                or tuple((index, name) for index, (name, _, _) in enumerate(self.planned_nodes))
                != tuple((index, name) for index, name, _ in self.completed_nodes)
                or any(status == "failed" for _, _, status in self.completed_nodes)
                or any(
                    call.status != "returned"
                    or call.callable_receiver_hex is None
                    or call.key_hex is None
                    or call.target_mask_hex is None
                    or not call.receiver_stable
                    or call.state_ref is None
                    or call.state_ref.kind != "foundry.state_snapshot"
                    or call.state_ref.media_type != "application/json"
                    or call.state_ref.manifest_profile_sha256 is None
                    or call.reason_codes
                    for call in self.calls
                )
            ):
                raise ValueError("generic_program_graph_step_not_complete")
            expected_calls = tuple(
                (index, name)
                for (index, name, status), (_, kind, op_kind) in zip(
                    self.completed_nodes, self.planned_nodes, strict=True
                )
                if status == "succeeded"
                and (kind == "mechanism" or (kind == "op" and op_kind == "apply_mechanism"))
            )
            if tuple((call.plan_index, call.node_id) for call in self.calls) != expected_calls:
                raise ValueError("generic_program_graph_step_call_census_mismatch")
        return self


class GenericProgramGraphContentObservationV1(BaseModel):
    """Actual generic graph trace; no current-use or protected authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["GenericProgramGraphContentObservation@1.0"] = (
        "GenericProgramGraphContentObservation@1.0"
    )
    authority_purpose: Literal["candidate_declared_numerical_basis_only"] = (
        "candidate_declared_numerical_basis_only"
    )
    call_normalization_profile: Literal[
        "foundry-bound-call-content/1",
        "foundry-bound-call-content/2",
        "foundry-bound-call-content/3",
    ]
    input_ref_identity: tuple[str, str, str, str | None]
    semantic_successor_ref: ArtifactRef
    source_image: N5ProductionImage
    execution_profile: N5NativeExecutionProfile
    profile_stability: Literal["recomputed", "not_established"]
    source_image_stability: Literal["recomputed", "not_established"]
    consumed_configuration: dict[str, object]
    completion: CandidateN5Completion
    steps: tuple[GenericProgramGraphStepObservation, ...]
    predicate_provenance: Literal["recomputed", "not_established"]
    reason_codes: tuple[str, ...] = ()
    result_without_observation_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    closure_residuals: tuple[str, ...] = CANDIDATE_CONTENT_RESIDUALS
    independent_verification: Literal["not_established"] = "not_established"
    protected_use_allowed: Literal[False] = False
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _bound_content(self) -> Self:
        if (
            self.semantic_successor_ref.kind != "runtime.quality.model_input_successor_selection"
            or self.semantic_successor_ref.media_type != "application/json"
            or self.semantic_successor_ref.manifest_profile_sha256 is None
            or self.closure_residuals != CANDIDATE_CONTENT_RESIDUALS
            or (self.predicate_provenance == "recomputed") == bool(self.reason_codes)
            or self.content_hash
            != exact_n5_content_hash(self.model_dump(mode="json", exclude={"content_hash"}))
        ):
            raise ValueError("generic_program_graph_content_observation_invalid")
        if self.predicate_provenance == "recomputed" and (
            self.completion.status != "recomputed"
            or self.profile_stability != "recomputed"
            or self.source_image_stability != "recomputed"
            or self.source_image.provenance != "recomputed"
            or self.execution_profile.profile_identity_predicate != "recomputed"
            or not self.steps
            or any(step.predicate_provenance != "recomputed" for step in self.steps)
        ):
            raise ValueError("generic_program_graph_content_incomplete")
        return self


class GenericProgramGraphContentObservationV2(GenericProgramGraphContentObservationV1):
    """A generic trace bound to the producer's versioned numerical intent."""

    schema_version: Literal["GenericProgramGraphContentObservation@2.0"] = (
        "GenericProgramGraphContentObservation@2.0"
    )
    numerical_intent_profile: Literal["generic_program_graph_declared_numerical_v2"]
    numerical_intent_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class GenericProgramGraphMethodCallObservation(BaseModel):
    """Actual mapped NumPy call content, separate from legacy mechanism calls."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    plan_index: int = Field(ge=0, strict=True)
    node_id: str = Field(min_length=1)
    call_content_hex: str | None = Field(default=None, max_length=262144)
    stable: bool = False
    status: Literal["returned", "raised", "not_established"]
    reason_codes: tuple[str, ...] = ()


class GenericProgramGraphMethodStepObservation(GenericProgramGraphStepObservation):
    """One supported independent mapped-method step with its complete denominator."""

    calls: tuple[GenericProgramGraphMethodCallObservation, ...]
    mechanism_calls: tuple[GenericProgramGraphCallObservation, ...]

    @model_validator(mode="after")
    def _complete_step(self) -> Self:
        if (self.predicate_provenance == "recomputed") == bool(self.reason_codes):
            raise ValueError("generic_program_graph_step_predicate_mismatch")
        if self.predicate_provenance == "recomputed":
            expected = tuple(
                (index, name)
                for index, (name, kind, _) in enumerate(self.planned_nodes)
                if kind == "method"
            )
            expected_mechanisms = tuple(
                (index, name)
                for index, (name, kind, op) in enumerate(self.planned_nodes)
                if kind == "op" and op == "apply_mechanism"
            )
            if (
                not self.graph_finished
                or self.base_state_ref is None
                or self.base_state_ref.kind != "foundry.state_snapshot"
                or self.base_state_ref.media_type != "application/json"
                or self.base_state_ref.manifest_profile_sha256 is None
                or any(
                    not (
                        kind == "method"
                        or (
                            kind == "op"
                            and op
                            in {"make_mask", "apply_mechanism", "merge_state", "check_constraints"}
                        )
                    )
                    for _, kind, op in self.planned_nodes
                )
                or tuple((i, name) for i, (name, _, _) in enumerate(self.planned_nodes))
                != tuple((i, name) for i, name, _ in self.completed_nodes)
                or any(status != "succeeded" for _, _, status in self.completed_nodes)
                or not expected
                or len(expected_mechanisms) != 1
                or tuple((call.plan_index, call.node_id) for call in self.mechanism_calls)
                != expected_mechanisms
                or any(
                    call.status != "returned"
                    or call.callable_receiver_hex is None
                    or call.key_hex is None
                    or call.target_mask_hex is None
                    or not call.receiver_stable
                    or call.state_ref is None
                    or call.state_ref.kind != "foundry.state_snapshot"
                    or call.state_ref.media_type != "application/json"
                    or call.state_ref.manifest_profile_sha256 is None
                    or call.reason_codes
                    for call in self.mechanism_calls
                )
                or tuple((call.plan_index, call.node_id) for call in self.calls) != expected
                or any(
                    call.status != "returned"
                    or not call.stable
                    or call.call_content_hex is None
                    or call.reason_codes
                    for call in self.calls
                )
            ):
                raise ValueError("generic_program_graph_method_step_not_complete")
        return self


class GenericProgramGraphContentObservationV3(GenericProgramGraphContentObservationV1):
    """Versioned physical method-call observation; no old V2 meaning is changed."""

    schema_version: Literal["GenericProgramGraphContentObservation@3.0"] = (
        "GenericProgramGraphContentObservation@3.0"
    )
    numerical_intent_profile: Literal["generic_program_graph_mapped_numpy_methods_v3"]
    numerical_intent_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    steps: tuple[GenericProgramGraphMethodStepObservation, ...]


def _product_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _native_profile(
    configuration: PreparedJointSimulationConfiguration,
    *,
    numerical_callable: object | None = None,
) -> N5NativeExecutionProfile:
    """Observe the actual native backend, never a requested backend label."""
    try:
        import jax

        backend = N5BackendObservation(
            backend_name=jax.default_backend(),
            backend_version=jax.__version__,
            device_platforms=tuple(sorted({device.platform for device in jax.devices()})),
            x64_enabled=bool(jax.config.jax_enable_x64),
            numerical_policy=(
                N5ProfileSetting(
                    name="jax_default_matmul_precision",
                    value=jax.config.jax_default_matmul_precision,
                ),
                N5ProfileSetting(
                    name="jax_default_prng_impl", value=jax.config.jax_default_prng_impl
                ),
                *(
                    N5ProfileSetting(name=name, value=os.environ.get(name))
                    for name in (
                        "OMP_NUM_THREADS",
                        "OPENBLAS_NUM_THREADS",
                        "MKL_NUM_THREADS",
                        "XLA_FLAGS",
                    )
                ),
            ),
            observation_provenance="recomputed",
        )
    except (ImportError, OSError, RuntimeError, TypeError, ValueError):
        backend = N5BackendObservation(
            backend_name="unobserved",
            observation_provenance="not_established",
            reason_codes=("native_backend_observation_not_established",),
        )
    # Backend initialization may load providers; observe those before the call.
    profile = observe_n5_native_execution_profile(
        first_party_root=_product_root() / "src" / "polisyos",
        entrypoint_module_names=tuple(
            name
            for name in ("__main__", "__mp_main__")
            if name in sys.modules
            and (
                type(numerical_callable) is not types.FunctionType
                or numerical_callable.__module__ != name
            )
        ),
        declared_settings={
            "prepared_configuration_hash": exact_n5_content_hash(
                configuration.model_dump(mode="python")
            )
        },
    )
    return bind_n5_backend_observation(profile, backend)


def _prepared_image_descriptor(
    configuration: PreparedJointSimulationConfiguration,
) -> dict[str, object]:
    # The observation binds the complete post-call native profile separately.
    # Source identity binds the configuration actually present before execution;
    # no circular reference or ambient module census enters this source image.
    return {
        "configuration_schema": configuration.schema_version,
        "configuration_hash": exact_n5_content_hash(configuration.model_dump(mode="json")),
        "authority_scope": "candidate_observation_only",
    }


def _planned_units(
    request: JointSimulationRequest, plan: EnginePlan, decision: EngineDecision
) -> tuple[tuple[str, int], ...]:
    from polisyos.runtime.quality.joint_simulation_horizon import (
        _atom_subsets,
        _physical_run_ref,
        _physical_spec_digest,
        _replication_seeds,
    )

    specs = {
        _physical_spec_digest(_physical_run_ref(request, plan, decision, subset))
        for _role, subset in _atom_subsets(request.intervention_atoms)
    }
    if request.comparator_profile is not None:
        specs.add(_physical_spec_digest(_physical_run_ref(request, plan, decision, ())))
    return tuple(sorted((spec, seed) for spec in specs for seed in _replication_seeds(request)))


def _numerical_intent(
    request: JointSimulationRequest,
    plan: EnginePlan,
    decision: EngineDecision,
    configuration: PreparedJointSimulationConfiguration,
) -> dict[str, object]:
    """Use the same concrete consumed projection at production and source replay."""
    return {
        "plan": plan,
        "method_fqn": decision.method_fqn,
        "horizon": request.horizon,
        "atoms": request.intervention_atoms,
        "selected_outcomes": request.selected_outcomes,
        "baseline_state": request.baseline_state,
        "evidence_state": request.evidence_state,
        "seed": request.seed,
        "replications": request.replications,
        "comparator_profile": request.comparator_profile,
        "prepared_configuration": configuration,
    }


def _completion(
    result: JointSimulationResult, planned: tuple[tuple[str, int], ...]
) -> CandidateN5Completion:
    observations = result.physical_work_observations
    completed = tuple(
        sorted(
            (item.physical_spec_ref, item.effective_seed)
            for item in observations
            if item.status == "completed"
        )
    )
    failed = tuple(
        sorted(
            (item.physical_spec_ref, item.effective_seed)
            for item in observations
            if item.status != "completed"
        )
    )
    interruption = result.diagnostics.get("physical_work_interruption")
    if interruption is not None and type(interruption) is not str:
        raise ValueError("candidate_n5_completion_interruption_invalid")
    full = (
        bool(planned)
        and not failed
        and interruption is None
        and (
            len(set(planned)) == len(planned)
            and len(set(completed)) == len(completed)
            and set(planned) == set(completed)
        )
    )
    return CandidateN5Completion(
        planned_units=planned,
        completed_units=completed,
        failed_units=failed,
        interruption_reason=interruption,
        status="recomputed" if full else "not_established",
    )


class CandidateN5ContentRun:
    """One native producer operation; its mutable recorder never crosses CAS."""

    def __init__(
        self,
        *,
        controller: JointSimulationHorizonController,
        request: JointSimulationRequest,
        input_ref: ArtifactRef,
        replay_preflight: N5ReplayPreflight | N5OriginalPreflight | None = None,
    ) -> None:
        if replay_preflight is not None:
            from polisyos.runtime.quality.n5_replay_execution import (
                N5OriginalPreflight,
                N5ReplayPreflight,
            )

            if type(replay_preflight) not in {N5ReplayPreflight, N5OriginalPreflight}:
                raise ValueError("candidate_n5_replay_preflight_not_canonical")
        self.controller = controller
        self.request = request
        self.input_ref = input_ref
        self.capture: N5ControlledCallCaptureV3 | None = None
        self.method_fqn: str | None = None
        self.planned_units: tuple[tuple[str, int], ...] = ()
        self.profile: N5NativeExecutionProfile | None = None
        self.selected_callable: object | None = None
        self.configuration: PreparedJointSimulationConfiguration | None = None
        self.production_image: N5ProductionImage | None = None
        self._replay_preflight = replay_preflight
        self._preflight_passed = replay_preflight is None

    def prepare(
        self,
        plan: EnginePlan,
        decision: EngineDecision,
    ) -> None:
        """Bind the actual selected plan before its first numerical call."""
        if self.capture is not None or decision.method_fqn is None:
            raise ValueError("candidate_n5_content_selection_not_unique")
        from polisyos.runtime.quality.joint_simulation_horizon import (
            PreparedJointSimulationConfiguration,
            read_joint_simulation_configuration,
        )

        configuration = PreparedJointSimulationConfiguration.model_validate_json(
            read_joint_simulation_configuration(self.controller).model_dump_json()
        )
        self.configuration = configuration
        self.profile = _native_profile(configuration, numerical_callable=self.selected_callable)
        image = capture_n5_production_image(
            root=_product_root(), admitted_profile=_prepared_image_descriptor(configuration)
        )
        self.production_image = image
        # Operational admission and copied occurrence labels are separate from
        # these request values. The wider source-basis owner enforces its field
        # role census; this producer binds the concrete plan it actually uses.
        numerical = _numerical_intent(self.request, plan, decision, configuration)
        self.capture = N5ControlledCallCaptureV3(effective_inputs=numerical, production_image=image)
        self.method_fqn = decision.method_fqn
        self.planned_units = _planned_units(self.request, plan, decision)
        if self._replay_preflight is not None:
            from polisyos.runtime.quality.n5_replay_execution import (
                N5OriginalPreflight,
                N5ReplayPreflight,
            )

            if type(self._replay_preflight) is N5ReplayPreflight:
                N5ReplayPreflight.check(self._replay_preflight, self)
            else:
                N5OriginalPreflight.check(self._replay_preflight, self)
            self._preflight_passed = True

    def invoke(
        self, function: Callable[..., _ResultT], /, *args: object, **kwargs: object
    ) -> _ResultT:
        """Invoke the retained selected callable through the actual seam."""
        if self.capture is None:
            raise ValueError("candidate_n5_content_plan_missing")
        if not self._preflight_passed:
            raise ValueError("candidate_n5_content_preflight_not_passed")
        if function is not self.selected_callable:
            raise ValueError("candidate_n5_content_retained_callable_mismatch")
        return self.capture.observe_numerical_call(function, *args, **kwargs)

    def require_replay_engine(self, decision: EngineDecision) -> None:
        """Stop unsupported replay dispatch before reservation or numerical work."""
        if self._replay_preflight is not None and (
            decision.decision != "selected" or decision.engine_kind != "ncm_parallel_worlds"
        ):
            raise ValueError("candidate_n5_replay_engine_capture_unsupported")

    def diagnostic_replay_preflight_passed(self, budget: object) -> bool:
        """Bind invocation-only admission to this preflighted controller."""
        return (
            self._replay_preflight is not None
            and self._preflight_passed
            and self.controller._producer_budget_observer is budget
        )


@dataclass
class _GenericGraphStep:
    physical_spec_ref: str
    replication_seed: int
    step: int
    effective_seed: int
    base_state_ref: ArtifactRef | None
    planned_nodes: tuple[tuple[str, str, str | None], ...]
    completed_nodes: list[tuple[int, str, str]] = field(default_factory=list)
    calls: list[dict[str, object]] = field(default_factory=list)
    method_calls: list[dict[str, object]] = field(default_factory=list)
    pending: dict[int, tuple[object, bytes | None]] = field(default_factory=dict, repr=False)
    pending_methods: dict[int, tuple[object, bytes | None]] = field(
        default_factory=dict, repr=False
    )
    graph_finished: bool = False
    reason_codes: list[str] = field(default_factory=list)


class GenericProgramGraphN5ContentRun(CandidateN5ContentRun):
    """Record one generic ProgramGraph's actual calls, not a prospective trace."""

    def __init__(
        self,
        *,
        controller: JointSimulationHorizonController,
        request: JointSimulationRequest,
        input_ref: ArtifactRef,
        semantic_successor_ref: ArtifactRef,
        store: CoreJSONArtifactStore,
    ) -> None:
        super().__init__(controller=controller, request=request, input_ref=input_ref)
        self.semantic_successor_ref = semantic_successor_ref
        self.store = store
        self.source_image: N5ProductionImage | None = None
        self.steps: list[_GenericGraphStep] = []
        self.remaining_trace_bytes = 131072
        self.remaining_state_bytes = 8 * 1024 * 1024
        self.remaining_calls = 256
        self.numerical_intent: bytes | None = None
        self.preflight: ProgramGraphInputPreflight | None = None
        self.numerical_intent_profile = "generic_program_graph_declared_numerical_v2"
        self.prepared_method_calls: tuple[tuple[int, int, str, int, bytes], ...] = ()
        self.prepared_calls: tuple[tuple[int, str, int, bytes], ...] = ()

    def prepare_program_graph(
        self, plan: EnginePlan, decision: EngineDecision, semantic_input: object
    ) -> None:
        """Observe the selected controller and its profile before physical work."""
        from polisyos.core.contracts import load_model_input_obligation_set
        from polisyos.runtime.quality.acquisition_evaluation import (
            _prepare_generic_model_input_numerical_quantity,
        )
        from polisyos.runtime.quality.joint_simulation_horizon import (
            _SelectedSemanticProgramGraphInput,
        )
        from polisyos.runtime.quality.model_input_requirements import ProgramGraphInputPreflight

        if (
            self.configuration is not None
            or decision.engine_kind != "program_graph"
            or type(semantic_input) is not _SelectedSemanticProgramGraphInput
            or len(self.request.engine_plan) != 1
            or self.request.engine_plan[0] is not plan
            or self.controller._select_engine(self.request).decision != decision
        ):
            raise ValueError("generic_program_graph_content_selection_invalid")
        selected, _ = load_model_input_obligation_set(self.store, semantic_input.obligation_set_ref)
        if selected.invocation != semantic_input.invocation:
            raise ValueError("generic_program_graph_content_preflight_mismatch")
        preflight = ProgramGraphInputPreflight(
            obligation_refs=selected.obligation_refs,
            supplied_initial_slots=selected.supplied_initial_slots,
            parameter_override_bundle_ref=semantic_input.invocation.parameter_override_bundle_ref,
            obligation_set_ref=semantic_input.obligation_set_ref,
            invocation=semantic_input.invocation,
        )
        quantity = _prepare_generic_model_input_numerical_quantity(
            store=self.store, request=self.request, preflight=preflight, controller=self.controller
        )
        from polisyos.foundry.execute import execute_semantic_horizon_step
        from polisyos.runtime.quality.joint_simulation_horizon import (
            read_joint_simulation_configuration,
        )

        self.configuration = read_joint_simulation_configuration(self.controller)
        self.selected_callable = execute_semantic_horizon_step
        self.profile = quantity.execution_profile
        self.source_image = quantity.source_image
        self.numerical_intent = quantity.numerical_intent
        self.numerical_intent_profile = quantity.numerical_intent_profile
        self.prepared_method_calls = quantity.prepared_method_calls
        self.prepared_calls = quantity.prepared_calls
        self.preflight = preflight
        self.method_fqn = decision.method_fqn
        self.planned_units = _planned_units(self.request, plan, decision)

    def observer_for_unit(self, physical_spec_ref: str, seed: int) -> _GenericGraphUnitObserver:
        """Return an explicit Foundry observer for one actual physical unit."""
        return _GenericGraphUnitObserver(self, physical_spec_ref=physical_spec_ref, seed=seed)

    def _bounded_hex(self, value: bytes) -> str:
        self.remaining_trace_bytes -= len(value)
        if self.remaining_trace_bytes < 0:
            raise ValueError("generic_program_graph_trace_limit_exceeded")
        return value.hex()

    def step_observations(self) -> tuple[GenericProgramGraphStepObservation, ...]:
        """Seal only the observed per-step node and call facts."""
        observations = []
        record_type = (
            GenericProgramGraphMethodStepObservation
            if self.numerical_intent_profile == "generic_program_graph_mapped_numpy_methods_v3"
            else GenericProgramGraphStepObservation
        )
        for step in self.steps:
            reasons = list(step.reason_codes)
            payload = {
                "physical_spec_ref": step.physical_spec_ref,
                "replication_seed": step.replication_seed,
                "step": step.step,
                "effective_seed": step.effective_seed,
                "base_state_ref": step.base_state_ref,
                "planned_nodes": step.planned_nodes,
                "completed_nodes": tuple(step.completed_nodes),
                "calls": tuple(step.calls),
                "graph_finished": step.graph_finished,
            }
            if record_type is GenericProgramGraphMethodStepObservation:
                payload["calls"] = tuple(step.method_calls)
                payload["mechanism_calls"] = tuple(step.calls)
            if not reasons:
                try:
                    observations.append(record_type(**payload, predicate_provenance="recomputed"))
                    continue
                except (TypeError, ValueError):
                    reasons.append("generic_program_graph_step_not_complete")
            observations.append(
                record_type(
                    **payload,
                    predicate_provenance="not_established",
                    reason_codes=tuple(dict.fromkeys(reasons)),
                )
            )
        return tuple(observations)


class _GenericGraphUnitObserver:
    """Passively observe the Foundry-owned calls for one physical unit."""

    def __init__(
        self, scope: GenericProgramGraphN5ContentRun, *, physical_spec_ref: str, seed: int
    ) -> None:
        self.scope = scope
        self.physical_spec_ref = physical_spec_ref
        self.seed = seed
        self.current: _GenericGraphStep | None = None

    def graph_started(
        self,
        *,
        step: int,
        seed: int,
        base_state_ref: ArtifactRef | None,
        nodes: tuple[tuple[str, str, str | None], ...],
    ) -> None:
        current = _GenericGraphStep(
            physical_spec_ref=self.physical_spec_ref,
            replication_seed=self.seed,
            step=step,
            effective_seed=seed,
            base_state_ref=base_state_ref,
            planned_nodes=nodes,
        )
        if self.current is not None and not self.current.graph_finished:
            current.reason_codes.append("generic_program_graph_prior_step_unfinished")
        if seed != self.seed + step:
            current.reason_codes.append("generic_program_graph_step_seed_mismatch")
        self.scope.steps.append(current)
        self.current = current

    def mechanism_started(
        self,
        *,
        step: int,
        plan_index: int,
        node_id: str,
        selected_call: Callable[..., object],
        state: object,
        key: object,
        target_mask: object,
    ) -> None:
        current = self.current
        if current is None:
            return
        call: dict[str, object] = {
            "plan_index": plan_index,
            "node_id": node_id,
            "callable_receiver_hex": None,
            "key_hex": None,
            "target_mask_hex": None,
            "state_ref": None,
            "receiver_stable": False,
            "state_matches_base": False,
            "status": "not_established",
            "reason_codes": (),
        }
        receiver: bytes | None = None
        try:
            if current.step != step or plan_index in current.pending:
                raise ValueError("generic_program_graph_call_scope_mismatch")
            self.scope.remaining_calls -= 1
            if self.scope.remaining_calls < 0:
                raise ValueError("generic_program_graph_call_limit_exceeded")
            receiver = snapshot_foundry_mechanism_call(selected_call)
            if (
                self.scope.numerical_intent_profile
                == "generic_program_graph_mapped_numpy_methods_v3"
            ):
                expected = tuple(
                    content
                    for index, name, at_step, content in self.scope.prepared_calls
                    if (index, name, at_step) == (plan_index, node_id, step)
                )
                if expected != (receiver,):
                    raise ValueError("generic_mechanism_actual_call_differs_from_preparation")
            call["callable_receiver_hex"] = self.scope._bounded_hex(receiver)
            call["key_hex"] = self.scope._bounded_hex(snapshot_foundry_call_value(key))
            call["target_mask_hex"] = self.scope._bounded_hex(
                snapshot_foundry_call_value(target_mask)
            )
            from polisyos.core.artifacts import input_ref_from_artifact_ref
            from polisyos.foundry.execute import (
                load_state_snapshot,
                put_state_snapshot,
                state_snapshot_value_projection,
            )

            if current.base_state_ref is None:
                raise ValueError("generic_program_graph_base_state_missing")
            projection = state_snapshot_value_projection(state)
            self.scope.remaining_state_bytes -= sum(
                len(leaf.path.encode()) + len(leaf.dtype) + len(leaf.value_bytes)
                for leaf in projection
            )
            if self.scope.remaining_state_bytes < 0:
                raise ValueError("generic_program_graph_state_limit_exceeded")
            persisted = load_state_snapshot(self.scope.store, snapshot_ref=current.base_state_ref)
            call["state_matches_base"] = projection == state_snapshot_value_projection(persisted)
            if call["state_matches_base"]:
                call["state_ref"] = current.base_state_ref
            else:
                # This is the real before-call state, not a reconstruction of
                # the preceding patches or a prediction for a later run.
                state_ref = put_state_snapshot(
                    self.scope.store,
                    state=state,
                    step=step,
                    inputs=[
                        input_ref_from_artifact_ref(
                            current.base_state_ref, role="observation.step_predecessor"
                        )
                    ],
                    return_selected_profile=True,
                )
                reopened = load_state_snapshot(self.scope.store, snapshot_ref=state_ref)
                if projection != state_snapshot_value_projection(reopened):
                    raise ValueError("generic_program_graph_call_state_readback_mismatch")
                call["state_ref"] = state_ref
        except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
            call["reason_codes"] = ("generic_program_graph_call_identity_not_established",)
        current.pending[plan_index] = (selected_call, receiver)
        current.calls.append(call)

    def mechanism_finished(
        self, *, step: int, plan_index: int, node_id: str, status: Literal["returned", "raised"]
    ) -> None:
        current = self.current
        if current is None or not current.calls:
            return
        call = current.calls[-1]
        pending = current.pending.pop(plan_index, None)
        if (
            current.step != step
            or call["plan_index"] != plan_index
            or call["node_id"] != node_id
            or pending is None
        ):
            current.reason_codes.append("generic_program_graph_call_scope_mismatch")
            return
        selected_call, before = pending
        call["status"] = status
        try:
            call["receiver_stable"] = (
                before is not None and snapshot_foundry_mechanism_call(selected_call) == before
            )
        except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
            call["receiver_stable"] = False
        if call["receiver_stable"] is not True:
            call["reason_codes"] = ("generic_program_graph_receiver_not_stable",)

    def method_started(
        self, *, step: int, plan_index: int, node_id: str, prepared_call: object
    ) -> None:
        from polisyos.runtime.quality.acquisition_evaluation import _generic_method_call_content

        current = self.current
        if current is None:
            return
        call = {
            "plan_index": plan_index,
            "node_id": node_id,
            "call_content_hex": None,
            "stable": False,
            "status": "not_established",
            "reason_codes": (),
        }
        content = None
        try:
            if current.step != step or plan_index in current.pending_methods:
                raise ValueError("generic_method_call_scope_mismatch")
            self.scope.remaining_calls -= 1
            if self.scope.remaining_calls < 0:
                raise ValueError("generic_program_graph_call_limit_exceeded")
            content = _generic_method_call_content(prepared_call)
            call["call_content_hex"] = self.scope._bounded_hex(content)
            expected = tuple(
                value
                for seed, index, name, at_step, value in self.scope.prepared_method_calls
                if (seed, index, name, at_step) == (self.seed, plan_index, node_id, step)
            )
            if expected != (content,):
                raise ValueError("generic_method_actual_call_differs_from_preparation")
        except (OSError, RuntimeError, TypeError, ValueError, AttributeError) as exc:
            call["reason_codes"] = (str(getattr(exc, "code", None) or exc),)
        current.method_calls.append(call)
        current.pending_methods[plan_index] = (prepared_call, content)

    def method_finished(
        self,
        *,
        step: int,
        plan_index: int,
        node_id: str,
        status: Literal["returned", "raised"],
    ) -> None:
        from polisyos.runtime.quality.acquisition_evaluation import _generic_method_call_content

        current = self.current
        if current is None:
            return
        pending = current.pending_methods.pop(plan_index, None)
        if current.step != step or pending is None or not current.method_calls:
            current.reason_codes.append("generic_method_call_scope_mismatch")
            return
        call = current.method_calls[-1]
        if (call["plan_index"], call["node_id"]) != (plan_index, node_id):
            current.reason_codes.append("generic_method_call_scope_mismatch")
            return
        row, before = pending
        call["status"] = status
        try:
            call["stable"] = before is not None and _generic_method_call_content(row) == before
        except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
            call["stable"] = False
        if not call["stable"]:
            call["reason_codes"] = (*call["reason_codes"], "generic_method_call_not_stable")

    def node_finished(
        self,
        *,
        step: int,
        plan_index: int,
        node_id: str,
        status: Literal["succeeded", "skipped", "failed"],
    ) -> None:
        current = self.current
        if current is None:
            return
        if current.step != step:
            current.reason_codes.append("generic_program_graph_node_scope_mismatch")
        current.completed_nodes.append((plan_index, node_id, status))

    def graph_finished(self, *, step: int, seed: int) -> None:
        current = self.current
        if current is None:
            return
        if (
            current.step != step
            or current.effective_seed != seed
            or current.pending
            or current.pending_methods
        ):
            current.reason_codes.append("generic_program_graph_graph_scope_mismatch")
        current.graph_finished = True


@contextmanager
def observe_generic_program_graph_n5_input(
    *,
    port: object,
    request: JointSimulationRequest,
    input_ref: ArtifactRef,
    semantic_successor_ref: ArtifactRef,
) -> Iterator[GenericProgramGraphN5ContentRun]:
    """Observe a request already reopened by the canonical semantic successor owner."""
    from polisyos.runtime.quality.generation_cycle import JointSimulationPort

    if (
        type(port) is not JointSimulationPort
        or port._artifact_store is None
        or _ACTIVE.get() is not None
        or input_ref.kind != "runtime.quality.generic_cycle_simulation_n5_input"
        or input_ref.manifest_profile_sha256 is None
        or semantic_successor_ref.kind != "runtime.quality.model_input_successor_selection"
        or semantic_successor_ref.manifest_profile_sha256 is None
    ):
        raise ValueError("generic_program_graph_content_scope_not_established")
    scope = GenericProgramGraphN5ContentRun(
        controller=port._controller,
        request=request,
        input_ref=input_ref,
        semantic_successor_ref=semantic_successor_ref,
        store=port._artifact_store,
    )
    token = _ACTIVE.set(scope)
    try:
        yield scope
    finally:
        _ACTIVE.reset(token)


def bind_generic_program_graph_n5_content_observation(
    result: JointSimulationResult, *, scope: GenericProgramGraphN5ContentRun
) -> JointSimulationResult:
    """Bind actual ProgramGraph observations to the producer's ordinary result."""
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationResult,
        build_content_bound_simulation_receipt,
        read_joint_simulation_configuration,
        verify_simulation_receipt,
    )

    if (
        type(scope) is not GenericProgramGraphN5ContentRun
        or scope.configuration is None
        or scope.profile is None
        or scope.source_image is None
        or scope.numerical_intent is None
        or scope.preflight is None
    ):
        return result
    payload = deepcopy(_candidate_result_payload(result))
    verify_simulation_receipt(result.receipt, payload)
    if CONTENT_OBSERVATION_KEY in payload["diagnostics"]:
        raise ValueError("generic_program_graph_content_already_bound")
    current = read_joint_simulation_configuration(scope.controller)
    observed_profile = _native_profile(current, numerical_callable=scope.selected_callable)
    current_image = capture_n5_production_image(
        root=_product_root(), admitted_profile=_prepared_image_descriptor(scope.configuration)
    )
    profile_stable = (
        exact_n5_content_bytes(current) == exact_n5_content_bytes(scope.configuration)
        and reconcile_recorded_n5_profile_content(scope.profile, observed_profile).status
        == "recomputed"
    )
    image_stable = current_image.content_hash == scope.source_image.content_hash
    completion = _completion(result, scope.planned_units)
    steps = scope.step_observations()
    expected_steps = {
        (physical, seed, step)
        for physical, seed in scope.planned_units
        for step in scope.request.horizon.steps()
    }
    actual_steps = tuple(
        (item.physical_spec_ref, item.replication_seed, item.step) for item in steps
    )
    reasons = []
    if completion.status != "recomputed":
        reasons.append("generic_program_graph_physical_completion_not_established")
    if len(actual_steps) != len(expected_steps) or set(actual_steps) != expected_steps:
        reasons.append("generic_program_graph_step_census_not_established")
    if any(item.predicate_provenance != "recomputed" for item in steps):
        reasons.append("generic_program_graph_call_identity_not_established")
    if not profile_stable or observed_profile.profile_identity_predicate != "recomputed":
        reasons.append("generic_program_graph_execution_profile_not_established")
    if not image_stable or scope.source_image.provenance != "recomputed":
        reasons.append("generic_program_graph_source_image_not_established")
    from polisyos.runtime.quality.acquisition_evaluation import (
        _prepare_generic_model_input_numerical_quantity,
    )

    try:
        final_quantity = _prepare_generic_model_input_numerical_quantity(
            store=scope.store,
            request=scope.request,
            preflight=scope.preflight,
            controller=scope.controller,
        )
        if final_quantity.numerical_intent != scope.numerical_intent:
            reasons.append("generic_program_graph_numerical_intent_changed")
    except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
        reasons.append("generic_program_graph_numerical_intent_not_established")
    values = {
        "schema_version": (
            "GenericProgramGraphContentObservation@3.0"
            if scope.numerical_intent_profile == "generic_program_graph_mapped_numpy_methods_v3"
            else "GenericProgramGraphContentObservation@2.0"
        ),
        "authority_purpose": "candidate_declared_numerical_basis_only",
        "call_normalization_profile": GENERIC_FOUNDRY_CALL_NORMALIZATION,
        "numerical_intent_profile": scope.numerical_intent_profile,
        "numerical_intent_sha256": "sha256:" + hashlib.sha256(scope.numerical_intent).hexdigest(),
        "input_ref_identity": artifact_ref_identity_key(scope.input_ref),
        "semantic_successor_ref": scope.semantic_successor_ref.model_dump(mode="json"),
        "source_image": scope.source_image.model_dump(mode="json"),
        "execution_profile": observed_profile.model_dump(mode="json"),
        "profile_stability": "recomputed" if profile_stable else "not_established",
        "source_image_stability": "recomputed" if image_stable else "not_established",
        "consumed_configuration": scope.configuration.model_dump(mode="json"),
        "completion": completion.model_dump(mode="json"),
        "steps": [item.model_dump(mode="json") for item in steps],
        "predicate_provenance": "not_established" if reasons else "recomputed",
        "reason_codes": reasons,
        "result_without_observation_hash": exact_n5_content_hash(payload),
        "closure_residuals": list(CANDIDATE_CONTENT_RESIDUALS),
        "independent_verification": "not_established",
        "protected_use_allowed": False,
    }
    values = json.loads(json.dumps(values, allow_nan=False))
    observation_type = (
        GenericProgramGraphContentObservationV3
        if scope.numerical_intent_profile == "generic_program_graph_mapped_numpy_methods_v3"
        else GenericProgramGraphContentObservationV2
    )
    observation = observation_type.model_validate_json(
        json.dumps({**values, "content_hash": exact_n5_content_hash(values)}, allow_nan=False)
    )
    payload["diagnostics"][CONTENT_OBSERVATION_KEY] = observation.model_dump(mode="json")
    receipt = build_content_bound_simulation_receipt(
        engine_kind=result.receipt.engine_kind, payload=payload, diagnostics=payload["diagnostics"]
    )
    bound = JointSimulationResult.model_validate(
        {**payload, "receipt": receipt.model_dump(mode="json")}
    )
    bound._content_payload = payload
    verify_simulation_receipt(bound.receipt, bound.content_bound_payload())
    return bound


def active_candidate_n5_content_run(
    controller: JointSimulationHorizonController,
) -> CandidateN5ContentRun | None:
    """Return only this actual controller's scoped native producer operation."""
    active = _ACTIVE.get()
    return active if active is not None and active.controller is controller else None


@contextmanager
def observe_source_rebuilt_candidate_n5_input(
    *,
    store: CoreJSONArtifactStore,
    controller: JointSimulationHorizonController,
    spec: N5BlindReplayLaunchSpecV2,
    budget: ProducerBudgetObserver,
) -> Iterator[tuple[JointSimulationRequest, CandidateN5ContentRun]]:
    """Rebuild a historical candidate input for a limited diagnostic execution.

    The canonical preflight runs after actual controller selection and before
    its first numerical call, and admits the complete physical plan.
    This context itself grants no authority or quota permission.
    """
    from polisyos.runtime.quality.acquisition_evaluation import (
        rebuild_selected_candidate_n5_request,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )
    from polisyos.runtime.quality.n5_replay_execution import N5ReplayPreflight

    if type(controller) is not JointSimulationHorizonController:
        raise ValueError("candidate_n5_content_controller_not_canonical")
    if _ACTIVE.get() is not None:
        raise ValueError("candidate_n5_content_scope_already_active")
    binding = N5ReplayPreflight(spec=spec, store=store, budget=budget)
    if controller._producer_budget_observer is not budget:
        raise ValueError("candidate_n5_replay_budget_binding_mismatch")
    request = rebuild_selected_candidate_n5_request(
        store=store,
        input_ref=spec.selected_candidate_simulation_n5_input_ref,
        run_id=spec.source_run_id,
        job_id=spec.source_job_id,
        tenant_id=spec.tenant_id,
        cell_id=spec.cell_id,
    )
    selection = controller._select_engine(request)
    if (
        selection.decision.decision != "selected"
        or selection.decision.engine_kind != "ncm_parallel_worlds"
    ):
        raise ValueError("candidate_n5_replay_engine_capture_unsupported")
    scope = CandidateN5ContentRun(
        controller=controller,
        request=request,
        input_ref=spec.selected_candidate_simulation_n5_input_ref,
        replay_preflight=binding,
    )
    token = _ACTIVE.set(scope)
    try:
        yield request, scope
    finally:
        _ACTIVE.reset(token)


@contextmanager
def observe_source_rebuilt_original_n5_input(
    *,
    store: CoreJSONArtifactStore,
    controller: JointSimulationHorizonController,
    action: N5OriginalProducerAction,
    budget: ProducerBudgetObserver,
) -> Iterator[tuple[JointSimulationRequest, CandidateN5ContentRun]]:
    """Reopen a retained V5 input for a distinct candidate original producer."""
    from polisyos.runtime.quality.acquisition_evaluation import (
        rebuild_selected_candidate_n5_request,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
    from polisyos.runtime.quality.n5_replay_execution import N5OriginalPreflight

    if type(controller) is not JointSimulationHorizonController or _ACTIVE.get() is not None:
        raise ValueError("candidate_n5_original_scope_not_established")
    binding = N5OriginalPreflight(action=action, budget=budget)
    if controller._producer_budget_observer is not budget:
        raise ValueError("candidate_n5_original_budget_binding_mismatch")
    request = rebuild_selected_candidate_n5_request(
        store=store,
        input_ref=action.source_input_ref,
        run_id=action.source_run_id,
        job_id=action.source_job_id,
        tenant_id=action.tenant_id,
        cell_id=action.cell_id,
    )
    selection = controller._select_engine(request)
    if (
        selection.decision.decision != "selected"
        or selection.decision.engine_kind != "ncm_parallel_worlds"
    ):
        raise ValueError("candidate_n5_original_engine_capture_unsupported")
    scope = CandidateN5ContentRun(
        controller=controller,
        request=request,
        input_ref=action.source_input_ref,
        replay_preflight=binding,
    )
    token = _ACTIVE.set(scope)
    try:
        yield request, scope
    finally:
        _ACTIVE.reset(token)


@contextmanager
def observe_candidate_n5_content_input(
    *,
    port: object,
    candidate: object,
    problem: object,
    request: JointSimulationRequest,
    input_ref: ArtifactRef,
) -> Iterator[tuple[JointSimulationRequest, CandidateN5ContentRun]]:
    """Reopen the selected V5 source through its owner before native execution."""
    from polisyos.runtime.quality.generation_cycle import JointSimulationPort
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    if type(port) is not JointSimulationPort:
        raise ValueError("candidate_n5_content_port_not_canonical")
    handoff = port._candidate_simulation_handoff
    if handoff is None or port._artifact_store is None:
        raise ValueError("candidate_n5_content_input_owner_missing")
    record = GenerationSourceRepository(port._artifact_store).resolve_candidate_simulation_v5(
        ref=input_ref,
        expected_job_id=handoff.job_id,
        expected_run_id=handoff.run_id,
        expected_tenant_id=handoff.tenant_id,
        expected_cell_id=handoff.cell_id,
    )
    expected = port._build_candidate_simulation_request(
        candidate=candidate, problem=problem, input_record=record
    )
    expected = expected.model_copy(
        update={"world_model_record": expected.world_model_record.model_copy(deep=True)}
    )
    if exact_n5_content_bytes(expected) != exact_n5_content_bytes(request):
        raise ValueError("candidate_n5_content_input_request_mismatch")
    scope = CandidateN5ContentRun(
        controller=port._controller, request=expected, input_ref=input_ref
    )
    token = _ACTIVE.set(scope)
    try:
        yield expected, scope
    finally:
        _ACTIVE.reset(token)


def bind_candidate_n5_content_observation(
    result: JointSimulationResult, *, scope: CandidateN5ContentRun
) -> JointSimulationResult:
    """Seal the real observation into the result before its ordinary CAS writer."""
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationResult,
        build_content_bound_simulation_receipt,
        read_joint_simulation_configuration,
        verify_simulation_receipt,
    )

    if (
        scope.capture is None
        or scope.profile is None
        or scope.method_fqn is None
        or scope.configuration is None
    ):
        return result
    payload = deepcopy(_candidate_result_payload(result))
    verify_simulation_receipt(result.receipt, payload)
    if CONTENT_OBSERVATION_KEY in payload["diagnostics"]:
        raise ValueError("candidate_n5_content_already_bound")
    current_configuration = read_joint_simulation_configuration(scope.controller)
    configuration_stable = exact_n5_content_bytes(current_configuration) == (
        exact_n5_content_bytes(scope.configuration)
    )
    observed_profile = _native_profile(
        current_configuration, numerical_callable=scope.selected_callable
    )
    current_image = capture_n5_production_image(
        root=_product_root(), admitted_profile=_prepared_image_descriptor(scope.configuration)
    )
    values = {
        "schema_version": "CandidateN5ContentObservation@1.0",
        "authority_purpose": "candidate_declared_numerical_basis_only",
        "input_ref_identity": artifact_ref_identity_key(scope.input_ref),
        "method_fqn": scope.method_fqn,
        "witness": scope.capture.seal().model_dump(mode="json"),
        "execution_profile": observed_profile.model_dump(mode="json"),
        "profile_stability": (
            "recomputed"
            if configuration_stable
            and reconcile_recorded_n5_profile_content(scope.profile, observed_profile).status
            == "recomputed"
            else "not_established"
        ),
        "source_image_stability": (
            "recomputed"
            if current_image.content_hash == scope.capture.seal().production_image.content_hash
            else "not_established"
        ),
        "consumed_configuration": scope.configuration.model_dump(mode="json"),
        "completion": _completion(result, scope.planned_units).model_dump(mode="json"),
        "result_without_observation_hash": exact_n5_content_hash(payload),
        "closure_residual_profile": "candidate-n5-declared-basis-residuals/1",
        "closure_residuals": CANDIDATE_CONTENT_RESIDUALS,
        "independent_verification": "not_established",
        "protected_use_allowed": False,
    }
    # Hash the wire representation, not Python tuple-versus-list incidence.
    values = json.loads(json.dumps(values, allow_nan=False))
    observation = CandidateN5ContentObservation.model_validate_json(
        json.dumps({**values, "content_hash": exact_n5_content_hash(values)}, allow_nan=False)
    )
    payload["diagnostics"][CONTENT_OBSERVATION_KEY] = observation.model_dump(mode="json")
    receipt = build_content_bound_simulation_receipt(
        engine_kind=result.receipt.engine_kind, payload=payload, diagnostics=payload["diagnostics"]
    )
    bound = JointSimulationResult.model_validate(
        {**payload, "receipt": receipt.model_dump(mode="json")}
    )
    bound._content_payload = payload
    verify_simulation_receipt(bound.receipt, bound.content_bound_payload())
    return bound


def _candidate_result_payload(result: JointSimulationResult) -> dict[str, object]:
    """Reopen complete new-format wire bytes without requiring producer memory.

    Historical reader owners retain their original signed projections. This
    content-observation writer emits the full typed result, so a fresh model
    can reconstruct it; an existing private cache cannot hide changed fields.
    """
    from polisyos.pdc import gy_content_hash, gy_content_hash_operation_rule_identity
    from polisyos.runtime.quality.joint_simulation_horizon import (
        _NATIVE_GY_HASH,
        _NATIVE_GY_RULE_IDENTITY,
        JointSimulationResult,
        _freeze_receipt_json,
        _same_exact_json,
    )

    if type(result) is not JointSimulationResult:
        raise ValueError("candidate_n5_content_result_untyped")
    actual = result.model_dump(mode="json", exclude={"receipt"})
    cached = result.content_bound_payload()
    if cached:
        try:
            exactly_equal = (
                _NATIVE_GY_RULE_IDENTITY is not None
                and gy_content_hash is _NATIVE_GY_HASH
                and gy_content_hash_operation_rule_identity() == _NATIVE_GY_RULE_IDENTITY
                and _same_exact_json(_freeze_receipt_json(cached), actual)
            )
        except (TypeError, ValueError, RecursionError):
            exactly_equal = False
        if not exactly_equal and gy_content_hash(cached) != gy_content_hash(actual):
            raise ValueError("candidate_n5_content_result_payload_mismatch")
    return cached or actual


def read_candidate_n5_content_observation(
    result: JointSimulationResult,
    *,
    input_ref: ArtifactRef,
    expected_request: JointSimulationRequest | None = None,
) -> CandidateN5ContentObservation:
    """Read historical content and selected-result joins without current permission."""
    from polisyos.runtime.quality.joint_simulation_horizon import verify_simulation_receipt

    complete_payload = _candidate_result_payload(result)
    verify_simulation_receipt(result.receipt, complete_payload)
    observation = _read_candidate_n5_observation_wire(
        result.diagnostics.get(CONTENT_OBSERVATION_KEY)
    )
    if observation.input_ref_identity != artifact_ref_identity_key(input_ref):
        raise ValueError("candidate_n5_content_input_mismatch")
    payload = deepcopy(complete_payload)
    del payload["diagnostics"][CONTENT_OBSERVATION_KEY]
    if exact_n5_content_hash(payload) != observation.result_without_observation_hash:
        raise ValueError("candidate_n5_content_result_mismatch")
    if _completion(result, observation.completion.planned_units) != observation.completion:
        raise ValueError("candidate_n5_content_completion_mismatch")
    selected = [item.method_fqn for item in result.engine_decisions if item.decision == "selected"]
    if selected != [observation.method_fqn]:
        raise ValueError("candidate_n5_content_method_mismatch")
    if expected_request is not None:
        _require_resolved_request_binding(observation, result, expected_request)
    return observation


def _read_recorded_generic_method_call(
    call: GenericProgramGraphMethodCallObservation,
) -> dict[str, object]:
    """Read bounded canonical call facts without loading a current method ABI."""
    import numpy as np

    from polisyos.foundry.data_plane import selected_tensor_value_sha256
    from polisyos.runtime.quality.n5_execution_basis import _require_v2_wire

    encoded = call.call_content_hex
    if encoded is None:
        raise ValueError("generic_method_recorded_call_not_established")
    try:
        raw = bytes.fromhex(encoded)
        payload = json.loads(raw)
        _require_n5_json_wire_domain(payload)
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("generic_method_recorded_call_not_established") from exc
    names = {
        "profile",
        "plan_index",
        "node_id",
        "step",
        "method_fqn",
        "method_version",
        "method_abi_digest",
        "arguments",
        "resolved_parameters",
        "root_seed",
        "seed",
        "key_words",
        "rng_state",
        "providers",
    }
    if (
        type(payload) is not dict
        or set(payload) != names
        or raw.hex() != encoded
        or canonical != raw
        or payload["profile"] != "foundry-mapped-numpy-method-call/1"
        or (payload["plan_index"], payload["node_id"]) != (call.plan_index, call.node_id)
        or type(payload["arguments"]) is not list
        or not payload["arguments"]
        or type(payload["providers"]) is not dict
    ):
        raise ValueError("generic_method_recorded_call_scope_mismatch")
    allowed_providers = {
        "runner_execute",
        "pure_step",
        "postprocessor",
        "default_rng",
        "representation_call",
        "restricted_selector",
        "output_dematerializer",
        "custom_output_projection",
    }
    if (
        not {"runner_execute", "pure_step", "default_rng", "output_dematerializer"}.issubset(
            payload["providers"]
        )
        or set(payload["providers"]) - allowed_providers
        or any(
            payload["providers"][name] is None
            for name in ("runner_execute", "pure_step", "default_rng", "output_dematerializer")
        )
        or any(
            type(payload[name]) is not int for name in ("plan_index", "step", "root_seed", "seed")
        )
        or type(payload["key_words"]) is not list
        or any(type(word) is not int for word in payload["key_words"])
    ):
        raise ValueError("generic_method_recorded_provider_census_mismatch")
    _require_v2_wire(payload["resolved_parameters"])
    _require_v2_wire(payload["rng_state"])
    for content in payload["providers"].values():
        _require_v2_wire(content)
    names_seen = set()
    for argument in payload["arguments"]:
        if type(argument) is not dict or set(argument) != {
            "name",
            "source_slot",
            "dtype",
            "shape",
            "value_hex",
            "value_sha256",
        }:
            raise ValueError("generic_method_recorded_argument_not_established")
        name = argument["name"]
        if (
            type(argument["source_slot"]) is not str
            or not argument["source_slot"]
            or type(argument["dtype"]) is not str
            or type(argument["shape"]) is not list
            or type(argument["value_hex"]) is not str
        ):
            raise ValueError("generic_method_recorded_argument_not_established")
        if type(name) is not str or not name or name in names_seen:
            raise ValueError("generic_method_recorded_argument_census_mismatch")
        names_seen.add(name)
        dtype = np.dtype(argument["dtype"])
        shape = tuple(argument["shape"])
        value = bytes.fromhex(argument["value_hex"])
        if (
            dtype.kind != "f"
            or dtype.metadata is not None
            or any(type(size) is not int or size <= 0 for size in shape)
            or len(value) > 1024 * 1024
            or value.hex() != argument["value_hex"]
            or (len(value) // dtype.itemsize) != int(np.prod(shape, dtype=np.int64))
            or len(value) % dtype.itemsize
            or not np.isfinite(np.frombuffer(value, dtype=dtype)).all()
            or selected_tensor_value_sha256(dtype, shape, value) != argument["value_sha256"]
        ):
            raise ValueError("generic_method_recorded_argument_not_established")
    return payload


def _reconcile_recorded_generic_method_step(
    store: CoreJSONArtifactStore,
    *,
    step_ref: ArtifactRef,
    bindings_ref: ArtifactRef,
    program_ref: ArtifactRef,
    observed: GenericProgramGraphMethodStepObservation,
) -> None:
    """Join producer-observed call content to the exact stored Foundry dispatch."""
    import numpy as np

    from polisyos.foundry.execute import (
        load_stored_selected_method_input_occurrences,
        read_program_graph_method_input_sources,
    )
    from polisyos.runtime.quality.n5_execution_basis import _v2_native_wire

    occurrences = load_stored_selected_method_input_occurrences(
        store, historical_execution_ref=step_ref, input_bindings_ref=bindings_ref
    )
    selected = {
        (item.plan_index, item.node_id): item for item in occurrences if item.node_kind == "method"
    }
    if set(selected) != {(call.plan_index, call.node_id) for call in observed.calls}:
        raise ValueError("generic_method_recorded_dispatch_census_mismatch")
    for call in observed.calls:
        payload = _read_recorded_generic_method_call(call)
        occurrence = selected[(call.plan_index, call.node_id)]
        dispatch = occurrence.dispatch
        if (
            dispatch is None
            or dispatch.outcome != "succeeded"
            or dispatch.parameter_resolution_status != "captured"
            or dispatch.backend_identity_status != "reconciled"
            or dispatch.actual_backend != "numpy"
            or dispatch.fallback_status != "not_fell_back"
            or payload["method_fqn"] != occurrence.method_fqn
            or payload["method_version"] != occurrence.method_version
            or payload["method_abi_digest"] != occurrence.method_abi_digest
            or payload["step"] != observed.step
            or dispatch.step != observed.step
            or payload["root_seed"] != dispatch.root_seed
            or payload["seed"] != dispatch.method_seed
            or tuple(payload["key_words"]) != dispatch.method_key_words
            or payload["resolved_parameters"]
            != _v2_native_wire({item.name: item.value for item in dispatch.parameter_values})
        ):
            raise ValueError("generic_method_recorded_dispatch_binding_mismatch")
        arguments = {item["name"]: item for item in payload["arguments"]}
        sources = read_program_graph_method_input_sources(
            store,
            program_ref=program_ref,
            node_id=occurrence.node_id,
            signature_input_slot_ids=dispatch.signature_input_slot_ids,
        )
        if {name: item["source_slot"] for name, item in arguments.items()} != dict(sources):
            raise ValueError("generic_method_recorded_argument_source_mismatch")
        if set(arguments) != {item.slot_id for item in dispatch.input_slot_values}:
            raise ValueError("generic_method_recorded_argument_census_mismatch")
        for actual in dispatch.input_slot_values:
            expected = arguments[actual.slot_id]
            if (
                actual.status != "captured"
                or actual.value_sha256 != expected["value_sha256"]
                or actual.runtime_shape != tuple(expected["shape"])
                or actual.runtime_dtype is None
                or np.dtype(actual.runtime_dtype).str != expected["dtype"]
            ):
                raise ValueError("generic_method_recorded_argument_binding_mismatch")


def read_generic_program_graph_n5_content_observation(
    result: JointSimulationResult,
    *,
    input_ref: ArtifactRef,
    semantic_successor_ref: ArtifactRef,
    expected_request: JointSimulationRequest,
    store: CoreJSONArtifactStore,
) -> GenericProgramGraphContentObservationV2 | GenericProgramGraphContentObservationV3:
    """Reopen original graph calls and their actual selected Foundry step chains.

    This historical producer observation is not a current permission, a
    prospective future trace, or proof of an independent numerical execution.
    """
    from polisyos.core.artifacts import input_ref_from_artifact_ref
    from polisyos.core.contracts import ExecPlan, ProgramGraph
    from polisyos.foundry.execute import (
        admit_semantic_horizon_step_chain,
        load_model,
        load_state_snapshot,
        state_snapshot_value_projection,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
        PreparedJointSimulationConfiguration,
        _physical_spec_digest,
        verify_semantic_program_graph_result_sources,
        verify_simulation_receipt,
    )

    complete = _candidate_result_payload(result)
    verify_simulation_receipt(result.receipt, complete)
    raw = result.diagnostics.get(CONTENT_OBSERVATION_KEY)
    if type(raw) is not dict:
        raise ValueError("generic_program_graph_content_observation_missing")
    observation = _read_generic_program_graph_observation_wire(raw)
    if (
        type(observation)
        not in {GenericProgramGraphContentObservationV2, GenericProgramGraphContentObservationV3}
        or observation.numerical_intent_profile
        != (
            "generic_program_graph_mapped_numpy_methods_v3"
            if type(observation) is GenericProgramGraphContentObservationV3
            else "generic_program_graph_declared_numerical_v2"
        )
        or input_ref.kind != "runtime.quality.generic_cycle_simulation_n5_input"
        or input_ref.media_type != "application/json"
        or input_ref.manifest_profile_sha256 is None
        or semantic_successor_ref.kind != "runtime.quality.model_input_successor_selection"
        or semantic_successor_ref.media_type != "application/json"
        or semantic_successor_ref.manifest_profile_sha256 is None
        or not store.verify(input_ref).ok
        or not store.verify(semantic_successor_ref).ok
        or observation.input_ref_identity != artifact_ref_identity_key(input_ref)
        or artifact_ref_identity_key(observation.semantic_successor_ref)
        != artifact_ref_identity_key(semantic_successor_ref)
        or observation.call_normalization_profile != GENERIC_FOUNDRY_CALL_NORMALIZATION
        or observation.predicate_provenance != "recomputed"
    ):
        raise ValueError("generic_program_graph_content_not_established")
    payload = deepcopy(complete)
    del payload["diagnostics"][CONTENT_OBSERVATION_KEY]
    if exact_n5_content_hash(payload) != observation.result_without_observation_hash:
        raise ValueError("generic_program_graph_content_result_mismatch")
    config = PreparedJointSimulationConfiguration.model_validate(observation.consumed_configuration)
    controller = JointSimulationHorizonController(_prepared_configuration=config)
    selected = controller._select_engine(expected_request)
    if selected.decision.decision != "selected" or selected.decision.engine_kind != "program_graph":
        raise ValueError("generic_program_graph_content_engine_mismatch")
    planned = _planned_units(expected_request, selected.plan, selected.decision)
    if (
        observation.completion.planned_units != planned
        or _completion(result, planned) != observation.completion
        or verify_semantic_program_graph_result_sources(
            store, result, expected_request=expected_request
        )
        is None
    ):
        raise ValueError("generic_program_graph_content_completion_mismatch")
    plan = load_model(store, selected.plan.exec_plan_ref, ExecPlan)
    graph = load_model(store, selected.plan.program_graph_ref, ProgramGraph)
    node_map = {node.node_id: node for node in graph.nodes}
    if len(node_map) != len(graph.nodes):
        raise ValueError("generic_program_graph_content_node_census_mismatch")
    order = plan.order or [node.node_id for node in graph.nodes]
    if any(node_id not in node_map for node_id in order):
        raise ValueError("generic_program_graph_content_node_census_mismatch")
    nodes = tuple(
        (
            node_id,
            str(node_map[node_id].node_kind),
            str(node_map[node_id].op.op_kind) if node_map[node_id].op is not None else None,
        )
        for node_id in order
    )
    step_rows = {
        (item.physical_spec_ref, item.replication_seed, item.step): item
        for item in observation.steps
    }
    expected_keys = {
        (physical, seed, step)
        for physical, seed in planned
        for step in expected_request.horizon.steps()
    }
    if (
        len(step_rows) != len(observation.steps)
        or set(step_rows) != expected_keys
        or any(item.planned_nodes != nodes for item in observation.steps)
    ):
        raise ValueError("generic_program_graph_content_step_census_mismatch")
    checked: set[tuple[str, int]] = set()
    for trajectory in result.trajectories:
        physical = _physical_spec_digest(trajectory.diagnostics.get("physical_run_ref"))
        for replication in trajectory.semantic_program_graph_replications:
            unit = (physical, replication.replication_seed)
            if unit in checked:
                continue
            checked.add(unit)
            chain = admit_semantic_horizon_step_chain(store, replication.step_result_refs)
            for index, admission in enumerate(chain):
                step = expected_request.horizon.steps()[index]
                observed = step_rows[(physical, replication.replication_seed, step)]
                basis = admission.basis
                if (
                    basis is None
                    or observed.base_state_ref is None
                    or artifact_ref_identity_key(observed.base_state_ref)
                    != artifact_ref_identity_key(basis.base_state_snapshot_ref)
                    or artifact_ref_identity_key(basis.program_graph_ref)
                    != artifact_ref_identity_key(selected.plan.program_graph_ref)
                    or basis.effective_step != step
                    or basis.effective_seed != observed.effective_seed
                ):
                    raise ValueError("generic_program_graph_content_step_source_mismatch")
                if type(observation) is GenericProgramGraphContentObservationV3:
                    _reconcile_recorded_generic_method_step(
                        store,
                        step_ref=replication.step_result_refs[index],
                        bindings_ref=basis.input_bindings_ref,
                        program_ref=basis.program_graph_ref,
                        observed=observed,
                    )
                mechanism_calls = (
                    observed.mechanism_calls
                    if type(observation) is GenericProgramGraphContentObservationV3
                    else observed.calls
                )
                for call in mechanism_calls:
                    if call.state_ref is None or not store.verify(call.state_ref).ok:
                        raise ValueError("generic_program_graph_call_state_unavailable")
                    if call.state_matches_base:
                        if artifact_ref_identity_key(call.state_ref) != artifact_ref_identity_key(
                            observed.base_state_ref
                        ):
                            raise ValueError("generic_program_graph_call_state_source_mismatch")
                    else:
                        manifest = store.get_manifest(call.state_ref)
                        edge = input_ref_from_artifact_ref(
                            observed.base_state_ref, role="observation.step_predecessor"
                        )
                        if not manifest.inputs or manifest.inputs[0] != edge:
                            raise ValueError("generic_program_graph_call_state_source_mismatch")
                    # The snapshot owner verifies its selected wrapper and blob.
                    # These bytes are a producer observation, not an independent
                    # derivation of the intermediate state from prior patches.
                    state_snapshot_value_projection(
                        load_state_snapshot(store, snapshot_ref=call.state_ref)
                    )
    if checked != set(planned):
        raise ValueError("generic_program_graph_content_physical_units_mismatch")
    return observation


def _read_generic_program_graph_observation_wire(
    raw: object,
) -> (
    GenericProgramGraphContentObservationV1
    | GenericProgramGraphContentObservationV2
    | GenericProgramGraphContentObservationV3
):
    """Decode each recorded version without upgrading a historical trace."""
    if type(raw) is not dict:
        raise ValueError("generic_program_graph_content_observation_missing")
    _require_n5_json_wire_domain(raw)
    version = raw.get("schema_version")
    if version == "GenericProgramGraphContentObservation@1.0":
        return GenericProgramGraphContentObservationV1.model_validate_json(json.dumps(raw))
    if version == "GenericProgramGraphContentObservation@2.0":
        return GenericProgramGraphContentObservationV2.model_validate_json(json.dumps(raw))
    if version == "GenericProgramGraphContentObservation@3.0":
        return GenericProgramGraphContentObservationV3.model_validate_json(json.dumps(raw))
    raise ValueError("generic_program_graph_content_schema_unsupported")


def _read_candidate_n5_observation_wire(raw: object) -> CandidateN5ContentObservation:
    """Admit inert native JSON and validate the complete nested witness once."""
    if type(raw) is not dict:
        raise ValueError("candidate_n5_content_observation_missing")
    witness_wire = raw.get("witness")
    if type(witness_wire) is not dict:
        raise ValueError("n5_content_witness_wire_required")
    _require_n5_json_wire_domain(witness_wire)
    return CandidateN5ContentObservation.model_validate_json(json.dumps(raw, allow_nan=False))


def _require_resolved_request_binding(
    observation: CandidateN5ContentObservation,
    result: JointSimulationResult,
    request: JointSimulationRequest,
) -> None:
    from polisyos.runtime.quality.joint_simulation_horizon import (
        PreparedJointSimulationConfiguration,
    )

    decisions = [item for item in result.engine_decisions if item.decision == "selected"]
    if len(decisions) != 1:
        raise ValueError("candidate_n5_content_request_selection_ambiguous")
    decision = decisions[0]
    plans = [
        plan
        for plan in request.engine_plan
        if plan.engine_kind == decision.engine_kind and plan.objective_ref == decision.objective_ref
    ]
    if len(plans) != 1:
        raise ValueError("candidate_n5_content_request_plan_mismatch")
    plan = plans[0]
    planned = _planned_units(request, plan, decision)
    if planned != observation.completion.planned_units:
        raise ValueError("candidate_n5_content_source_plan_mismatch")
    configuration = PreparedJointSimulationConfiguration.model_validate_json(
        json.dumps(observation.consumed_configuration, allow_nan=False)
    )
    # The producer's own denominator/intent never supplies the source assertion.
    # Its selected source is reopened by the calling owner and reconstructed by
    # the same pure request constructor used by the real producer.
    prospective = N5ControlledCallCaptureV3(
        effective_inputs=_numerical_intent(request, plan, decision, configuration),
        production_image=observation.witness.production_image,
    )
    if (
        prospective.numerical_intent_content_hash is None
        or observation.witness.numerical_intent_content_hash is None
    ):
        raise ValueError("candidate_n5_content_source_intent_not_established")
    if (
        prospective.numerical_intent_content_hash
        != observation.witness.numerical_intent_content_hash
    ):
        raise ValueError("candidate_n5_content_source_intent_mismatch")


def read_candidate_n5_declared_implementation(
    result: JointSimulationResult,
    *,
    input_ref: ArtifactRef,
    prepared_configuration: PreparedJointSimulationConfiguration,
    expected_request: JointSimulationRequest | None = None,
) -> dict[str, object]:
    """Reconstruct the recorded numerical identity, never a historical permit."""
    _, declared = _read_candidate_n5_declared_implementation(
        result,
        input_ref=input_ref,
        prepared_configuration=prepared_configuration,
        expected_request=expected_request,
    )
    return declared


def _read_candidate_n5_declared_implementation(
    result: JointSimulationResult,
    *,
    input_ref: ArtifactRef,
    prepared_configuration: PreparedJointSimulationConfiguration,
    expected_request: JointSimulationRequest | None = None,
) -> tuple[CandidateN5ContentObservation, dict[str, object]]:
    """Reconstruct the recorded numerical identity, never a historical permit."""
    if expected_request is None:
        raise ValueError("candidate_n5_content_source_request_not_established")
    observation = read_candidate_n5_content_observation(
        result, input_ref=input_ref, expected_request=expected_request
    )
    if exact_n5_content_bytes(observation.consumed_configuration) != exact_n5_content_bytes(
        prepared_configuration.model_dump(mode="json")
    ):
        raise ValueError("candidate_n5_content_configuration_mismatch")
    witness = observation.witness
    calls = witness.observed_calls
    if (
        observation.completion.status != "recomputed"
        or observation.profile_stability != "recomputed"
        or observation.source_image_stability != "recomputed"
        or observation.execution_profile.profile_identity_predicate != "recomputed"
        or witness.production_image.provenance != "recomputed"
        or witness.numerical_intent_content is None
        or len(calls) != len(observation.completion.completed_units)
        or any(
            call.status != "returned"
            or call.callable_content is None
            or call.arguments_content is None
            or call.numerical_content_hash is None
            for call in calls
        )
    ):
        raise ValueError("candidate_n5_declared_identity_not_established")
    callables = tuple(dict.fromkeys(call.callable_content for call in calls))
    if len(callables) != 1:
        raise ValueError("candidate_n5_declared_callable_changed_during_run")
    return observation, {
        "content_image": witness.production_image.model_dump(mode="json"),
        "execution_profile": {
            "schema_version": observation.execution_profile.schema_version,
            "numerical_profile_content_hash": (
                observation.execution_profile.numerical_profile_content_hash
            ),
            "scope": "recorded_file_backed_provider_bytes_and_native_settings",
        },
        "callable_identity": callables[0],
    }


def reconcile_candidate_n5_declared_implementation(
    result: JointSimulationResult,
    *,
    input_ref: ArtifactRef,
    prepared_configuration: PreparedJointSimulationConfiguration,
    expected_request: JointSimulationRequest | None = None,
    current_n5_controller: JointSimulationHorizonController | None = None,
) -> dict[str, object]:
    """Compare current declared content without another numerical kernel call."""
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
        read_joint_simulation_configuration,
    )

    if expected_request is None:
        raise ValueError("candidate_n5_content_source_request_not_established")
    observation, recorded = _read_candidate_n5_declared_implementation(
        result,
        input_ref=input_ref,
        prepared_configuration=prepared_configuration,
        expected_request=expected_request,
    )
    if (
        type(current_n5_controller) is not JointSimulationHorizonController
        or read_joint_simulation_configuration(current_n5_controller) != prepared_configuration
    ):
        raise ValueError("candidate_n5_intended_controller_not_established")
    selected = current_n5_controller._select_engine(expected_request)
    if (
        selected.decision.decision != "selected"
        or selected.decision.method_fqn != observation.method_fqn
    ):
        raise ValueError("candidate_n5_intended_selection_changed")
    method = current_n5_controller._registry.get(observation.method_fqn)
    profile = _native_profile(prepared_configuration, numerical_callable=method.pure_step)
    image = capture_n5_production_image(
        root=_product_root(), admitted_profile=_prepared_image_descriptor(prepared_configuration)
    )
    callable_content = snapshot_n5_callable_content_v3(method.pure_step)
    if (
        profile.profile_identity_predicate != "recomputed"
        or image.provenance != "recomputed"
        or reconcile_recorded_n5_profile_current_bytes(
            observation.execution_profile,
            profile,
            recorded_source_image=observation.witness.production_image,
            current_source_image=image,
        ).status
        != "recomputed"
        or image.content_hash != observation.witness.production_image.content_hash
        or callable_content is None
        or callable_content != recorded["callable_identity"]
    ):
        raise ValueError("candidate_n5_current_declared_identity_changed")
    return recorded
