"""Bridge native candidate N5 calls to persisted, limited content observations.

This is producer observation, not independent verification or protected-use
permission. Historical receipts remain readable without a process-session token.
Current candidate retention additionally compares the declared numerical image
and actual selected callable; unresolved closure remains an explicit limitation.
"""

from __future__ import annotations

import json
import os
import sys
import types
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import artifact_ref_identity_key
from polisyos.runtime.quality.n5_execution_basis import (
    N5ControlledCallCaptureV3,
    N5ExecutionContentWitnessV3,
    N5ProductionImage,
    _require_n5_json_wire_domain,
    capture_n5_production_image,
    exact_n5_content_bytes,
    exact_n5_content_hash,
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

    from polisyos.core.artifacts import ArtifactRef, CoreJSONArtifactStore
    from polisyos.runtime.quality.joint_simulation_horizon import (
        EngineDecision,
        EnginePlan,
        JointSimulationHorizonController,
        JointSimulationRequest,
        JointSimulationResult,
        PreparedJointSimulationConfiguration,
    )
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
