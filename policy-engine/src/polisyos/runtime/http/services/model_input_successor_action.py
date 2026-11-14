"""Select a protected use of one already-activated model input."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactRef,
    CoreJSONArtifactStore,
    artifact_manifest_profile_sha256,
    matches_artifact_store_protocol,
    read_core_manifest_profile,
)
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.pdc import OperationClass, OperationContract, OperationInvocationRecord
from polisyos.runtime.http.permissions import (
    MODEL_INPUT_USE_PERMISSION as MODEL_INPUT_USE_PERMISSION,
)
from polisyos.runtime.http.permissions import (
    MODEL_INPUT_USE_RESOURCE_KIND as MODEL_INPUT_USE_RESOURCE_KIND,
)
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoop
from polisyos.runtime.quality.agent_action_authority import (
    MODEL_INPUT_USE_ACTION_KIND,
    AgentActionIntent,
    agent_action_content_hash,
)
from polisyos.runtime.quality.model_input_successor_selection import (
    MODEL_INPUT_SUCCESSOR_SELECTION_KIND,
    MODEL_INPUT_USE_ACTION_PHASE_KIND,
    ModelInputSuccessorSelection,
    ModelInputUseActionPhase,
    persist_model_input_successor_selection,
    persist_model_input_use_action_phase,
    read_model_input_successor_selection,
    read_model_input_use_action_phase,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.data_forge.read_api.catalog import CanonicalAcquisitionAuthority
    from polisyos.runtime.quality.acquisition_evaluation import (
        GenericModelInputEvaluationBasisV1,
        GenericModelInputEvaluationDecisionV1,
        GenericModelInputSelectedEvaluation,
    )
    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedModelInputRoutingOrigin
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from polisyos.runtime.quality.generation_cycle import JointSimulationPort
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationN5ExecutionV5,
        GenericN5ResolvedResult,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )
    from polisyos.runtime.quality.substrate_registry import CatalogServingSourcePaths
    from polisyos.scientist.orchestration.engine import BudgetLedgerReentryBudgetWindow

    from .control import ControlPlaneService
    from .control_plane_store import (
        ControlJobExecutionAdmission,
        GenericModelInputEvaluationFrontierCAS,
        GenericModelInputEvaluationFrontierKey,
        GenericModelInputEvaluationFrontierRecord,
        GenericModelInputEvaluationUseRecord,
    )


MODEL_INPUT_USE_IMPLEMENTATION_REF = "polisyos.runtime.model_input_successor.owner_port.v1"
_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_CHECKPOINT_KEY = "model_input_use"
_PAYLOAD_KIND = "runtime.control_job_payload.acquisition"
_DECISION_KIND = "runtime_quality.agent_action_authority_decision"


class ModelInputSuccessorActionError(ValueError):
    """Typed refusal of the selected source for a model-input use action."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ModelInputSuccessorActionRequest(BaseModel):
    """Exact blocked N5, routing report, and activated input selected for a new action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    compiled_ref: ArtifactRef
    blocked_execution_ref: ArtifactRef
    routing_report_ref: ArtifactRef
    activation_receipt_ref: ArtifactRef
    observation_id: str = Field(min_length=1, max_length=300, strict=True)
    idempotency_key: str = Field(min_length=1, max_length=200, strict=True)
    human_decision_record_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _require_exact_selectors(self) -> ModelInputSuccessorActionRequest:
        refs = (
            (self.compiled_ref, "runtime.compiled_recursive_generation_cycle", "application/json"),
            (
                self.blocked_execution_ref,
                "runtime.quality.generic_cycle_simulation_n5_execution",
                "application/json",
            ),
            (
                self.routing_report_ref,
                "runtime.quality.model_input_routing_report",
                "application/json",
            ),
            (
                self.activation_receipt_ref,
                "epoch.activated_overlay_admission_receipt",
                "application/vnd.polisyos.epoch+json",
            ),
        )
        if any(
            ref.kind != kind or ref.media_type != media_type or ref.manifest_profile_sha256 is None
            for ref, kind, media_type in refs
        ) or any(value != value.strip() for value in (self.observation_id, self.idempotency_key)):
            raise ValueError("model_input_use_exact_selected_refs_required")
        return self


class ModelInputSuccessorDecisionResponse(BaseModel):
    """Persisted decision for one candidate-use job identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    route_id: str = Field(pattern=_SHA256_PATTERN)
    job_id: str
    authority_decision_ref: str = Field(pattern=_SHA256_PATTERN)
    outcome: Literal["decision_required", "decision_available"]
    human_decision_request: dict[str, object] | None = None


class ModelInputSuccessorExecutionRequest(BaseModel):
    """Request one deferred action using its exact signed approval."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: ModelInputSuccessorActionRequest
    decision_ref: str = Field(pattern=_SHA256_PATTERN)


class ModelInputUseActionCheckpoint(BaseModel):
    """Lease-fenced current input and its optional current or retained evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    phase_ref: ArtifactRef
    semantic_successor_ref: ArtifactRef
    execution_ref: ArtifactRef | None = None
    result_ref: ArtifactRef | None = None
    schema_version: Literal["polisyos.runtime.ModelInputUseActionCheckpoint@2.0"] | None = None
    evaluation_expected_frontier_revision: int | None = Field(default=None, ge=0)
    evaluation_expected_frontier_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    evaluation_decision_ref: ArtifactRef | None = None
    evaluation_current_basis_ref: ArtifactRef | None = None
    evaluation_replacement_basis_ref: ArtifactRef | None = None

    @model_validator(mode="after")
    def _selected_artifact_profiles(self) -> ModelInputUseActionCheckpoint:
        refs = (
            (self.phase_ref, MODEL_INPUT_USE_ACTION_PHASE_KIND),
            (self.semantic_successor_ref, MODEL_INPUT_SUCCESSOR_SELECTION_KIND),
        )
        if self.execution_ref is not None:
            refs += ((self.execution_ref, "runtime.quality.generic_cycle_simulation_n5_execution"),)
        evaluation_refs = (
            (self.evaluation_decision_ref, "runtime_quality.acquisition_evaluation_decision"),
            (self.evaluation_current_basis_ref, "runtime_quality.acquisition_evaluation_basis"),
            (self.evaluation_replacement_basis_ref, "runtime_quality.acquisition_evaluation_basis"),
        )
        selected_evaluation_refs = tuple(
            (ref, kind) for ref, kind in evaluation_refs if ref is not None
        )
        if (
            (self.execution_ref is None) != (self.result_ref is None)
            or any(
                ref.kind != kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
                for ref, kind in refs
            )
            or (self.result_ref is not None and self.result_ref.manifest_profile_sha256 is None)
            or any(
                ref.kind != kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
                for ref, kind in selected_evaluation_refs
            )
            or (
                self.schema_version is None
                and (
                    selected_evaluation_refs
                    or self.evaluation_expected_frontier_revision is not None
                    or self.evaluation_expected_frontier_ref is not None
                )
            )
            or (
                self.schema_version is not None
                and (
                    (self.evaluation_decision_ref is None)
                    != (self.evaluation_current_basis_ref is None)
                    or (
                        self.evaluation_decision_ref is None
                        and (
                            self.evaluation_expected_frontier_revision is None
                            or self.evaluation_replacement_basis_ref is not None
                        )
                    )
                    or (
                        self.evaluation_decision_ref is not None
                        and (
                            self.evaluation_expected_frontier_revision is not None
                            or self.evaluation_expected_frontier_ref is not None
                        )
                    )
                    or (
                        self.evaluation_expected_frontier_revision is not None
                        and (self.evaluation_expected_frontier_revision == 0)
                        != (self.evaluation_expected_frontier_ref is None)
                    )
                )
            )
        ):
            raise ValueError("model_input_use_checkpoint_selected_refs_invalid")
        return self


@dataclass(frozen=True, slots=True)
class ModelInputSuccessorIdentity:
    """Exact action inputs shared by current admission and historical replay."""

    origin: VerifiedModelInputRoutingOrigin
    request: ModelInputSuccessorActionRequest
    passport_ref: ArtifactRef
    observation_content_sha256: str
    route_id: str
    job_id: str

    @property
    def tenant_id(self) -> str:
        """Return the source owner's tenant."""
        return self.origin.tenant_id

    @property
    def cell_id(self) -> str:
        """Return the source owner's cell."""
        return self.origin.cell_id

    @property
    def run_id(self) -> str:
        """Return the stable served control run identity."""
        return self.origin.run_id


@dataclass(frozen=True, slots=True)
class SelectedModelInputSuccessorAction(ModelInputSuccessorIdentity):
    """Owner-replayed current inputs before a separate PA2 decision is applied."""

    catalog_source: CatalogServingSourcePaths
    catalog_authority: CanonicalAcquisitionAuthority
    passport: AdmissionPassport


@dataclass(frozen=True, slots=True)
class GenericModelInputUseHistory:
    """Immutable use history, with issuance-time predicates and no present permit.

    A retained use has no separate past provider profile. Its recorded decision
    is preserved; the view does not reconstruct its past loaded environment.
    """

    key: GenericModelInputEvaluationFrontierKey
    use: GenericModelInputEvaluationUseRecord
    decision: GenericModelInputEvaluationDecisionV1
    current_basis: GenericModelInputEvaluationBasisV1
    prior_evaluation: GenericModelInputSelectedEvaluation | None
    prior_frontier: GenericModelInputEvaluationFrontierRecord | None
    selected_frontier: GenericModelInputEvaluationFrontierRecord | None
    selected_basis: GenericModelInputEvaluationBasisV1 | None
    frontier_relation: Literal["selected", "superseded", "not_established"]
    selected_frontier_execution: GenericCycleSimulationN5ExecutionV5 | None
    selected_frontier_result: GenericN5ResolvedResult | None
    prior_execution: GenericCycleSimulationN5ExecutionV5 | None
    prior_result: GenericN5ResolvedResult | None
    current_action_result: GenericN5ResolvedResult | None
    history_limitation_codes: tuple[str, ...] = ()


def _resolve_model_input_successor_origin(
    control_service: ControlPlaneService,
    *,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    request: ModelInputSuccessorActionRequest,
) -> VerifiedModelInputRoutingOrigin:
    origin = AcquisitionRouteLoop(
        control_store=control_service._control_store,
        artifact_store=control_service._artifact_store,
        event_log=control_service._diagnostic_event_log,
        core_source_resolver=control_service.resolve_completed_control_job_core_run_source,
        tenant_id=tenant_id,
        cell_id=cell_id,
    ).resolve_model_input_routing_origin(
        run_id=run_id, routing_report_ref=request.routing_report_ref
    )
    if (
        origin.compiled_ref != request.compiled_ref
        or origin.n5_execution_ref != request.blocked_execution_ref
    ):
        raise ModelInputSuccessorActionError("model_input_use_blocked_source_mismatch")
    return origin


def _model_input_successor_ids(
    origin: VerifiedModelInputRoutingOrigin,
    request: ModelInputSuccessorActionRequest,
    observation_content_sha256: str,
) -> tuple[str, str]:
    route_id = agent_action_content_hash(
        {
            "action_kind": MODEL_INPUT_USE_ACTION_KIND,
            "tenant_id": origin.tenant_id,
            "cell_id": origin.cell_id,
            "run_id": origin.run_id,
            "source_job_id": origin.source_job_id,
            "selected_inputs": request.model_dump(
                mode="json", exclude={"idempotency_key", "human_decision_record_ref"}
            ),
            "observation_content_sha256": observation_content_sha256,
        }
    )
    job_digest = agent_action_content_hash(
        {"route_id": route_id, "idempotency_key": request.idempotency_key}
    )
    return route_id, "model-input-use." + job_digest.removeprefix("sha256:")


def _read_model_input_activation_boundary(
    store: CoreJSONArtifactStore, activation_ref: ArtifactRef
) -> epoch_contract.AdmittedAcquisitionBoundaryEvidence:
    activation = epoch_contract.ActivatedOverlayAdmissionStatement.model_validate(
        epoch_contract.load_verified_epoch_statement(
            store=store,
            ref=activation_ref,
            expected_kind="epoch.activated_overlay_admission_receipt",
        )
    )
    return epoch_contract.AdmittedAcquisitionBoundaryEvidence.model_validate(
        epoch_contract.load_verified_epoch_statement(
            store=store,
            ref=activation.admitted_boundary_evidence_ref,
            expected_kind="epoch.admitted_acquisition_boundary_evidence",
        )
    )


def resolve_model_input_successor_action(
    control_service: ControlPlaneService,
    *,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    request: ModelInputSuccessorActionRequest,
) -> SelectedModelInputSuccessorAction:
    """Reopen the exact blocked input and one current owner-activated source row.

    This resolution supplies content bindings for a candidate-use decision.
    Action authority, numerical budget, and semantic intake are separate gates.
    """
    from polisyos.data_forge.read_api.catalog import (
        CanonicalAcquisitionAuthority,
        CatalogAcquisitionOverlay,
    )
    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
    from polisyos.runtime.quality.model_input_routing import (
        ModelInputRoutingActivationError,
        resolve_model_input_routing_activation,
    )
    from polisyos.runtime.quality.substrate_registry import require_catalog_serving_source_unchanged

    if type(request) is not ModelInputSuccessorActionRequest:
        raise ModelInputSuccessorActionError("model_input_use_request_untyped")
    store = control_service._artifact_store
    if not matches_artifact_store_protocol(store, CoreJSONArtifactStore):
        raise ModelInputSuccessorActionError("model_input_use_profile_store_unavailable")
    origin = _resolve_model_input_successor_origin(
        control_service,
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        request=request,
    )

    source = control_service.catalog_serving_source
    require_catalog_serving_source_unchanged(source)
    authority = CanonicalAcquisitionAuthority.from_provision(
        repo_root=source.repo_root,
        baseline_path=source.substrate_paths.l1_dcat_path,
        l5_measurement_registry_path=source.substrate_paths.measurement_registry_path,
    )
    admission = _read_model_input_activation_boundary(store, request.activation_receipt_ref)
    passport = AdmissionPassport.model_validate(
        epoch_contract.load_verified_epoch_statement(
            store=store,
            ref=admission.passport_ref,
            expected_kind="epoch.acquisition_passport_snapshot",
        )
    )
    try:
        _, active_authority = resolve_model_input_routing_activation(
            store,
            request.routing_report_ref,
            expected_obligation_set_ref=origin.routing_report.obligation_set_ref,
            selected_basis=origin.selected_basis,
            catalog_authority=authority,
            receipt_ref=request.activation_receipt_ref,
            passport=passport,
        )
    except ModelInputRoutingActivationError as exc:
        code = {
            "single_obligation_required": "model_input_use_single_resolved_route_required",
            "resolved_route_required": "model_input_use_single_resolved_route_required",
            "activated_source_mismatch": "model_input_use_activated_source_mismatch",
            "live_authority_drift": "acquisition_authority_drift",
        }[exc.reason]
        raise ModelInputSuccessorActionError(code) from exc
    overlay = CatalogAcquisitionOverlay(authority.baseline_path, source.overlay_path)
    try:
        active = overlay.read_activated_semantic_epoch_observations(
            receipt_ref=request.activation_receipt_ref,
            artifact_store=store,
            passport=passport,
            authority=active_authority,
        )
    finally:
        overlay.close()
    rows = tuple(
        row
        for row in active.observations
        if row.observation.observation_id == request.observation_id
    )
    if len(rows) != 1 or active.passport_ref != admission.passport_ref:
        raise ModelInputSuccessorActionError("model_input_use_activated_observation_not_selected")
    require_catalog_serving_source_unchanged(source)
    (row,) = rows
    route_id, job_id = _model_input_successor_ids(origin, request, row.row_content_sha256)
    return SelectedModelInputSuccessorAction(
        origin=origin,
        request=request,
        catalog_source=source,
        catalog_authority=authority,
        passport_ref=admission.passport_ref,
        passport=passport,
        observation_content_sha256=row.row_content_sha256,
        route_id=route_id,
        job_id=job_id,
    )


def model_input_successor_action_tuple(
    selection: ModelInputSuccessorIdentity,
) -> tuple[OperationContract, OperationInvocationRecord, AgentActionIntent]:
    """Bind the distinct candidate-use tuple to the exact source and action job."""
    operation = OperationContract(
        operation_id=MODEL_INPUT_USE_ACTION_KIND,
        operation_version="v1",
        operation_class=OperationClass.BIND,
        consumes=[],
        produces=[],
        formal_preconditions=[],
        allowed_internal_execution=["foundry_method"],
        implementation_refs=[{"module": __name__, "symbol": "model_input_successor_action_tuple"}],
        cost_model={"source_fetch": "none", "physical_invocations": "bounded_by_owner"},
        authority_transform={"kind": "preserves"},
        failure_modes=["authority_refused", "selected_input_changed", "successor_not_established"],
        repair_options=[OperationClass.ESCALATE],
    )
    parameters = {
        "route_id": selection.route_id,
        "action_job_id": selection.job_id,
        "source_job_id": selection.origin.source_job_id,
        "selection": selection.request.model_dump(mode="json"),
        "passport_ref": selection.passport_ref.model_dump(mode="json"),
        "observation_content_sha256": selection.observation_content_sha256,
    }
    invocation = OperationInvocationRecord(
        invocation_id="model-input-use."
        + agent_action_content_hash(parameters).removeprefix("sha256:"),
        operation_id=operation.operation_id,
        operation_version=operation.operation_version,
        workspace_id=selection.run_id,
        cycle_index=selection.origin.source_cycle.cycle_index,
        selected_by={"producer": "runtime.model_input_successor"},
        selection_rationale_ref=selection.route_id,
        input_artifacts=[],
        parameters=parameters,
        internal_trace={"phase": "model_input_use_decision"},
        tool_calls=[],
        human_requests=[],
        output_artifacts=[],
        applicability_result="applicable",
        budget_delta={"candidate_model_input_actions": 1},
        status="started",
    )
    return operation, invocation, AgentActionIntent(action_kind=MODEL_INPUT_USE_ACTION_KIND)


def _selected_json_ref(store: CoreJSONArtifactStore, raw_ref: str, *, kind: str) -> ArtifactRef:
    selector = ArtifactID.model_validate(raw_ref)
    manifest, _ = read_core_manifest_profile(store, selector)
    if manifest.kind != kind or manifest.media_type != "application/json":
        raise ModelInputSuccessorActionError("model_input_use_action_manifest_mismatch")
    return ArtifactRef(
        artifact_id=selector,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=artifact_manifest_profile_sha256(manifest),
    )


def _expected_phase(
    store: CoreJSONArtifactStore,
    selection: ModelInputSuccessorIdentity,
    *,
    action_payload_ref: str,
    authority_decision_ref: str,
) -> ModelInputUseActionPhase:
    return ModelInputUseActionPhase(
        tenant_id=selection.tenant_id,
        cell_id=selection.cell_id,
        run_id=selection.run_id,
        source_job_id=selection.origin.source_job_id,
        action_job_id=selection.job_id,
        route_id=selection.route_id,
        action_payload_ref=_selected_json_ref(store, action_payload_ref, kind=_PAYLOAD_KIND),
        authority_decision_ref=_selected_json_ref(
            store, authority_decision_ref, kind=_DECISION_KIND
        ),
    )


def _read_checkpoint_selection(
    store: CoreJSONArtifactStore,
    *,
    selection: ModelInputSuccessorIdentity,
    checkpoint: ModelInputUseActionCheckpoint,
    phase: ModelInputUseActionPhase,
) -> ModelInputSuccessorSelection:
    if read_model_input_use_action_phase(store, checkpoint.phase_ref) != phase:
        raise ModelInputSuccessorActionError("model_input_use_checkpoint_phase_mismatch")
    selected = read_model_input_successor_selection(store, checkpoint.semantic_successor_ref)
    if (
        (selected.tenant_id, selected.cell_id, selected.run_id, selected.source_job_id)
        != (phase.tenant_id, phase.cell_id, phase.run_id, phase.source_job_id)
        or selected.action_job_id != phase.action_job_id
        or selected.route_id != phase.route_id
        or selected.action_phase_ref != checkpoint.phase_ref
        or selected.authority_decision_ref != phase.authority_decision_ref
        or selected.compiled_ref != selection.request.compiled_ref
        or selected.blocked_execution_ref != selection.request.blocked_execution_ref
        or selected.routing_report_ref != selection.request.routing_report_ref
        or selected.activation_receipt_ref != selection.request.activation_receipt_ref
        or selected.observation_id != selection.request.observation_id
        or selected.observation_content_sha256 != selection.observation_content_sha256
    ):
        raise ModelInputSuccessorActionError("model_input_use_checkpoint_selection_mismatch")
    return selected


def _verify_selected_routing_use_decision_current(
    store: CoreJSONArtifactStore,
    selection: SelectedModelInputSuccessorAction,
    selected: ModelInputSuccessorSelection,
) -> None:
    """Reopen the persisted candidate decision and fence its current route."""

    from polisyos.runtime.quality.model_input_routing import (
        MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2,
        verify_model_input_routing_use_decision_current,
    )

    is_v2 = selected.schema_version == "polisyos.runtime.ModelInputSuccessorSelection@2.0"
    report_is_v2 = (
        selection.origin.routing_report.schema_version
        == MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2
    )
    if is_v2 != report_is_v2 or (is_v2 and selected.routing_use_decision_ref is None):
        raise ModelInputSuccessorActionError("model_input_use_routing_decision_not_selected")
    if not is_v2:
        return
    decision_ref = selected.routing_use_decision_ref
    if decision_ref is None:
        raise ModelInputSuccessorActionError("model_input_use_routing_decision_not_selected")
    verify_model_input_routing_use_decision_current(
        store,
        decision_ref,
        expected_report_ref=selection.origin.routing_report_ref,
        expected_obligation_set_ref=selection.origin.routing_report.obligation_set_ref,
        selected_basis=selection.origin.selected_basis,
        catalog_authority=selection.catalog_authority,
    )


def resolve_model_input_successor_history(
    control_service: ControlPlaneService,
    *,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    request: ModelInputSuccessorActionRequest,
    checkpoint: ModelInputUseActionCheckpoint,
) -> ModelInputSuccessorIdentity:
    """Rebuild identity for subsequent signed decision and result verification."""
    store = control_service._artifact_store
    if not matches_artifact_store_protocol(store, CoreJSONArtifactStore):
        raise ModelInputSuccessorActionError("model_input_use_profile_store_unavailable")
    origin = _resolve_model_input_successor_origin(
        control_service, tenant_id=tenant_id, cell_id=cell_id, run_id=run_id, request=request
    )
    selected = read_model_input_successor_selection(store, checkpoint.semantic_successor_ref)
    admission = _read_model_input_activation_boundary(store, request.activation_receipt_ref)
    route_id, job_id = _model_input_successor_ids(
        origin, request, selected.observation_content_sha256
    )
    return ModelInputSuccessorIdentity(
        origin=origin,
        request=request,
        passport_ref=admission.passport_ref,
        observation_content_sha256=selected.observation_content_sha256,
        route_id=route_id,
        job_id=job_id,
    )


def verify_model_input_use_result(
    store: CoreJSONArtifactStore,
    *,
    selection: ModelInputSuccessorIdentity,
    checkpoint: ModelInputUseActionCheckpoint,
    action_payload_ref: str,
    authority_decision_ref: str,
) -> GenericN5ResolvedResult:
    """Read back the independently selected phase, semantic input, and actual V5."""
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
        GenericCycleSimulationN5ExecutionV5,
        GenericN5ExecutionJoinExpectation,
    )

    if checkpoint.execution_ref is None or checkpoint.result_ref is None:
        raise ModelInputSuccessorActionError("model_input_use_result_not_established")
    phase = _expected_phase(
        store,
        selection,
        action_payload_ref=action_payload_ref,
        authority_decision_ref=authority_decision_ref,
    )
    _read_checkpoint_selection(store, selection=selection, checkpoint=checkpoint, phase=phase)
    expectation = GenericN5ExecutionJoinExpectation.model_validate(
        {
            **selection.origin.n5_expectation.model_dump(mode="python"),
            "status": "joint_simulated",
            "result_ref": checkpoint.result_ref,
            "model_input_obligation_set_ref": None,
            "semantic_successor_ref": checkpoint.semantic_successor_ref,
        }
    )
    outcome, result = GenericCycleSimulationAdmissionOwner(
        profiles=(), store=store
    ).resolve_n5_execution_join_with_result(checkpoint.execution_ref, expected=expectation)
    if (
        outcome.status != "resolved"
        or type(outcome.execution) is not GenericCycleSimulationN5ExecutionV5
        or outcome.execution.action_job_id != selection.job_id
        or result is None
    ):
        raise ModelInputSuccessorActionError(
            outcome.code or "model_input_use_result_not_established"
        )
    return result


def model_input_use_terminal_progress(checkpoint: ModelInputUseActionCheckpoint) -> dict[str, Any]:
    """Return completion progress with a locator owned by this action."""
    terminal_ref = checkpoint.execution_ref or checkpoint.evaluation_decision_ref
    if terminal_ref is None or (checkpoint.execution_ref is None) != (
        checkpoint.result_ref is None
    ):
        raise ModelInputSuccessorActionError("model_input_use_result_not_established")
    return {
        "receipt_phase": "terminal",
        "terminal_receipt_ref": str(terminal_ref.artifact_id),
        _CHECKPOINT_KEY: checkpoint.model_dump(mode="json", exclude_none=True),
    }


def _resolve_action_budget_window(
    control: ControlPlaneService,
    *,
    selection: SelectedModelInputSuccessorAction,
    phase_ref: ArtifactRef,
    open_if_missing: bool,
) -> BudgetLedgerReentryBudgetWindow:
    from polisyos.scientist.orchestration.engine import (
        BudgetLedgerReentryBudgetScope,
        BudgetMiddleware,
    )

    origin = selection.origin
    binding = control.verify_acquisition_source_budget_owner(closure=origin)
    evidence = control.verify_candidate_unpriced_budget_scope(closure=origin)
    cap = evidence.run_budget_usd
    settlement_store = control._llm_producer_settlement_store
    if type(settlement_store) is not BudgetMiddleware or cap is None or cap <= 0:
        raise ModelInputSuccessorActionError("model_input_use_budget_scope_not_established")
    scope = BudgetLedgerReentryBudgetScope(
        run_binding=binding,
        action_job_id=selection.job_id,
        route_id=selection.route_id,
        action_generation=1,
        action_phase_ref=str(phase_ref.artifact_id),
        source_payload_ref=origin.source_payload_ref,
        profile_selection_ref=origin.n5_expectation.profile_selection_ref,
    )
    window = settlement_store.resolve_reentry_budget_window_safe(scope)
    if window is None and open_if_missing:
        window = settlement_store.open_reentry_budget_window_safe(
            scope, fresh_limit_usd=cap, global_limit_usd=cap
        )
    if (
        window is None
        or window.scope != scope
        or window.fresh_limit_usd != cap
        or window.global_limit_usd != cap
    ):
        raise ModelInputSuccessorActionError("model_input_use_budget_window_mismatch")
    return window


def _materialize_semantic_successor(
    control: ControlPlaneService,
    store: CoreJSONArtifactStore,
    *,
    selection: SelectedModelInputSuccessorAction,
    admission: ControlJobExecutionAdmission,
    phase_ref: ArtifactRef,
    phase: ModelInputUseActionPhase,
    window: BudgetLedgerReentryBudgetWindow,
) -> ArtifactRef:
    from polisyos.data_forge.read_api.catalog import CatalogAcquisitionOverlay
    from polisyos.runtime.quality.model_input_routing import (
        MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2,
        materialize_routed_model_input_observation,
        persist_current_model_input_routing_use_decision,
    )

    origin = selection.origin
    overlay = CatalogAcquisitionOverlay(
        selection.catalog_authority.baseline_path, selection.catalog_source.overlay_path
    )
    try:
        result = materialize_routed_model_input_observation(
            store,
            report_ref=origin.routing_report_ref,
            expected_obligation_set_ref=origin.routing_report.obligation_set_ref,
            selected_basis=origin.selected_basis,
            catalog_authority=selection.catalog_authority,
            overlay=overlay,
            receipt_ref=selection.request.activation_receipt_ref,
            passport=selection.passport,
            observation_id=selection.request.observation_id,
            profile_selection_ref=origin.n5_expectation.profile_selection_ref,
            workspace_dir=control._cas_root / "model-input-use" / selection.job_id,
            transaction_time=datetime.now(UTC),
        )
    finally:
        overlay.close()
    foundry_ref = result.semantic_foundry_input_bindings_ref
    worker_id = admission.job.lease_owner
    if foundry_ref is None or not worker_id:
        raise ModelInputSuccessorActionError("model_input_use_semantic_input_not_established")
    routing_use_decision_ref = None
    selection_schema_version = "polisyos.runtime.ModelInputSuccessorSelection@1.0"
    if origin.routing_report.schema_version == MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2:
        if len(origin.routing_report.routes) != 1:
            raise ModelInputSuccessorActionError("model_input_use_single_resolved_route_required")
        (route,) = origin.routing_report.routes
        try:
            routing_use_decision_ref, _decision = persist_current_model_input_routing_use_decision(
                store,
                origin.routing_report_ref,
                expected_obligation_set_ref=origin.routing_report.obligation_set_ref,
                selected_basis=origin.selected_basis,
                catalog_authority=selection.catalog_authority,
                tenant_id=selection.tenant_id,
                cell_id=selection.cell_id,
                route_port_id=route.port_id,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ModelInputSuccessorActionError(
                "model_input_use_routing_decision_not_established"
            ) from exc
        selection_schema_version = "polisyos.runtime.ModelInputSuccessorSelection@2.0"
    return persist_model_input_successor_selection(
        store,
        ModelInputSuccessorSelection(
            tenant_id=selection.tenant_id,
            cell_id=selection.cell_id,
            run_id=selection.run_id,
            source_job_id=origin.source_job_id,
            compiled_ref=origin.compiled_ref,
            blocked_execution_ref=origin.n5_execution_ref,
            routing_report_ref=origin.routing_report_ref,
            schema_version=selection_schema_version,
            routing_use_decision_ref=routing_use_decision_ref,
            activation_receipt_ref=selection.request.activation_receipt_ref,
            observation_id=selection.request.observation_id,
            observation_content_sha256=selection.observation_content_sha256,
            route_id=selection.route_id,
            action_job_id=selection.job_id,
            action_worker_id=worker_id,
            action_attempt=admission.attempt,
            action_phase_ref=phase_ref,
            authority_decision_ref=phase.authority_decision_ref,
            reentry_budget_window_id=window.window_id,
            reentry_budget_window_digest=window.record_digest,
            semantic_foundry_input_bindings_ref=foundry_ref,
        ),
    )


def _build_model_input_use_n5_port(
    control: ControlPlaneService,
    store: CoreJSONArtifactStore,
    *,
    selection: ModelInputSuccessorIdentity,
    window: BudgetLedgerReentryBudgetWindow,
) -> object:
    """Create the current N5 port shared by prospective replay and execution."""
    from polisyos.runtime.quality.generation_cycle import JointSimulationPort
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
    )
    from polisyos.scientist.orchestration.engine import BudgetMiddleware, BudgetState

    from .control.run_lifecycle import _build_control_nl_producer_budget_reconciler

    settlement_store = control._llm_producer_settlement_store
    if type(settlement_store) is not BudgetMiddleware:
        raise ModelInputSuccessorActionError("model_input_use_budget_scope_not_established")
    observer = _build_control_nl_producer_budget_reconciler(
        settlement_store=settlement_store,
        producer_run_binding=window.scope.run_binding,
        budget_state=BudgetState.model_validate(
            {"limits": {"run": {"key": "run", "max_usd": window.effective_limit_usd}}}
        ),
        reentry_budget_scope=window.scope,
    )
    source = getattr(selection, "catalog_source", control.catalog_serving_source)
    from polisyos.runtime.quality.substrate_registry import (
        require_catalog_serving_source_unchanged,
    )

    require_catalog_serving_source_unchanged(source)
    return JointSimulationPort(
        repo_root=source.repo_root,
        artifact_store=store,
        producer_budget_observer=observer,
        generic_cycle_simulation_admission_owner=GenericCycleSimulationAdmissionOwner(
            profiles=(), store=store
        ),
    )


def _generic_model_input_frontier_key(
    selection: ModelInputSuccessorIdentity,
) -> GenericModelInputEvaluationFrontierKey:
    from .control_plane_store import GenericModelInputEvaluationFrontierKey

    origin = selection.origin
    return GenericModelInputEvaluationFrontierKey(
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        source_job_id=origin.source_job_id,
        design_problem_ref=origin.source_cycle.design_problem_ref,
        candidate_id=origin.source_cycle.selected_candidate_ref,
    )


def _read_generic_model_input_basis(
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    ref: ArtifactRef,
) -> GenericModelInputEvaluationBasisV1:
    from polisyos.runtime.quality.acquisition_evaluation import (
        GenericModelInputEvaluationBasisV1,
        read_acquisition_evaluation_artifact,
    )

    basis = read_acquisition_evaluation_artifact(
        store=store,
        event_log=event_log,
        ref=ref,
        record_type=GenericModelInputEvaluationBasisV1,
    )
    if type(basis) is not GenericModelInputEvaluationBasisV1:
        raise ModelInputSuccessorActionError("model_input_use_basis_not_established")
    return basis


def _persist_generic_model_input_record(
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    record: GenericModelInputEvaluationBasisV1 | GenericModelInputEvaluationDecisionV1,
) -> ArtifactRef:
    from polisyos.runtime.quality.acquisition_evaluation import (
        persist_acquisition_evaluation_artifact,
    )

    return persist_acquisition_evaluation_artifact(store=store, event_log=event_log, record=record)


def _generic_selected_evaluation(
    selection: ModelInputSuccessorIdentity,
    checkpoint: ModelInputUseActionCheckpoint,
) -> GenericModelInputSelectedEvaluation:
    from polisyos.runtime.quality.acquisition_evaluation import (
        GenericModelInputSelectedEvaluation,
    )

    if checkpoint.execution_ref is None or checkpoint.result_ref is None:
        raise ModelInputSuccessorActionError("model_input_use_result_not_established")
    return GenericModelInputSelectedEvaluation(
        input_ref=selection.origin.n5_expectation.input_ref,
        execution_ref=checkpoint.execution_ref,
        result_ref=checkpoint.result_ref,
        semantic_successor_ref=checkpoint.semantic_successor_ref,
        action_job_id=selection.job_id,
    )


def _issue_model_input_basis(
    control: ControlPlaneService,
    selection: SelectedModelInputSuccessorAction,
    checkpoint: ModelInputUseActionCheckpoint,
    *,
    port: JointSimulationPort,
    role: Literal["prospective", "evaluated"],
    evaluation: GenericModelInputSelectedEvaluation | None = None,
    prospective_basis_ref: ArtifactRef | None = None,
    comparison_decision_ref: ArtifactRef | None = None,
) -> GenericModelInputEvaluationBasisV1:
    from polisyos.runtime.quality.acquisition_evaluation import (
        issue_generic_model_input_evaluation_basis,
    )

    return issue_generic_model_input_evaluation_basis(
        store=control._artifact_store,
        origin=selection.origin,
        input_ref=selection.origin.n5_expectation.input_ref,
        semantic_successor_ref=checkpoint.semantic_successor_ref,
        controller=port._controller,
        basis_role=role,
        evaluation=evaluation,
        event_log=control._diagnostic_event_log,
        prospective_basis_ref=prospective_basis_ref,
        comparison_decision_ref=comparison_decision_ref,
        prior_origin=selection.origin if prospective_basis_ref is not None else None,
    )


def _checkpoint_with_evaluation(
    checkpoint: ModelInputUseActionCheckpoint,
    *,
    decision_ref: ArtifactRef,
    current_basis_ref: ArtifactRef,
    replacement_basis_ref: ArtifactRef | None,
    execution_ref: ArtifactRef | None = None,
    result_ref: ArtifactRef | None = None,
) -> ModelInputUseActionCheckpoint:
    return ModelInputUseActionCheckpoint(
        phase_ref=checkpoint.phase_ref,
        semantic_successor_ref=checkpoint.semantic_successor_ref,
        execution_ref=execution_ref if execution_ref is not None else checkpoint.execution_ref,
        result_ref=result_ref if result_ref is not None else checkpoint.result_ref,
        schema_version="polisyos.runtime.ModelInputUseActionCheckpoint@2.0",
        evaluation_decision_ref=decision_ref,
        evaluation_current_basis_ref=current_basis_ref,
        evaluation_replacement_basis_ref=replacement_basis_ref,
        evaluation_expected_frontier_revision=None,
        evaluation_expected_frontier_ref=None,
    )


def _run_model_input_use_n5(
    control: ControlPlaneService,
    store: CoreJSONArtifactStore,
    *,
    selection: SelectedModelInputSuccessorAction,
    checkpoint: ModelInputUseActionCheckpoint,
    window: BudgetLedgerReentryBudgetWindow,
    currentness_resolver: Callable[[], bool],
    port: object | None = None,
) -> ModelInputUseActionCheckpoint:
    from polisyos.runtime.quality.generation_cycle import JointSimulationPort
    from polisyos.scientist.orchestration.engine import BudgetMiddleware

    settlement_store = control._llm_producer_settlement_store
    if type(settlement_store) is not BudgetMiddleware:
        raise ModelInputSuccessorActionError("model_input_use_budget_scope_not_established")
    selected_port = port or _build_model_input_use_n5_port(
        control, store, selection=selection, window=window
    )
    if type(selected_port) is not JointSimulationPort:
        raise ModelInputSuccessorActionError("model_input_use_simulation_port_not_established")
    observer = selected_port._controller._producer_budget_observer
    if getattr(observer, "reentry_budget_window", None) != window:
        raise ModelInputSuccessorActionError("model_input_use_budget_window_mismatch")

    def require_current_action() -> bool:
        if currentness_resolver() is not True:
            return False
        try:
            selected_input = read_model_input_successor_selection(
                store, checkpoint.semantic_successor_ref
            )
            _verify_selected_routing_use_decision_current(store, selection, selected_input)
        except (OSError, RuntimeError, TypeError, ValueError):
            return False
        return settlement_store.resolve_reentry_budget_window_safe(window.scope) == window

    observation = selected_port.run_semantic_successor(
        semantic_successor_ref=checkpoint.semantic_successor_ref,
        expected_blocked_execution_ref=selection.origin.n5_execution_ref,
        expected_input_ref=selection.origin.n5_expectation.input_ref,
        currentness_resolver=require_current_action,
    )
    if (
        observation.status != "joint_simulated"
        or observation.generic_n5_execution_ref is None
        or observation.simulation_result_ref is None
    ):
        raise ModelInputSuccessorActionError("model_input_use_result_not_established")
    return ModelInputUseActionCheckpoint(
        phase_ref=checkpoint.phase_ref,
        semantic_successor_ref=checkpoint.semantic_successor_ref,
        execution_ref=observation.generic_n5_execution_ref,
        result_ref=observation.simulation_result_ref,
        schema_version=checkpoint.schema_version,
        evaluation_expected_frontier_revision=checkpoint.evaluation_expected_frontier_revision,
        evaluation_expected_frontier_ref=checkpoint.evaluation_expected_frontier_ref,
        evaluation_decision_ref=checkpoint.evaluation_decision_ref,
        evaluation_current_basis_ref=checkpoint.evaluation_current_basis_ref,
        evaluation_replacement_basis_ref=checkpoint.evaluation_replacement_basis_ref,
    )


def _recover_model_input_use_n5(
    control: ControlPlaneService,
    store: CoreJSONArtifactStore,
    *,
    selection: SelectedModelInputSuccessorAction,
    checkpoint: ModelInputUseActionCheckpoint,
    window: BudgetLedgerReentryBudgetWindow,
    action_payload_ref: str,
    authority_decision_ref: str,
    currentness_resolver: Callable[[], bool],
) -> ModelInputUseActionCheckpoint:
    """Select an already durable V5 without repeating possible physical work."""
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
    )
    from polisyos.scientist.orchestration.engine import BudgetMiddleware, ProducerBudgetObservation

    if currentness_resolver() is not True:
        raise ModelInputSuccessorActionError("model_input_use_action_scope_not_current")
    try:
        execution_ref, execution = GenericCycleSimulationAdmissionOwner(
            profiles=(), store=store
        ).recover_semantic_successor_execution(
            expected=selection.origin.n5_expectation,
            semantic_successor_ref=checkpoint.semantic_successor_ref,
            action_job_id=selection.job_id,
        )
        recovered = ModelInputUseActionCheckpoint.model_validate(
            {
                **checkpoint.model_dump(mode="python"),
                "execution_ref": execution_ref,
                "result_ref": execution.result_ref,
            }
        )
        resolved = verify_model_input_use_result(
            store,
            selection=selection,
            checkpoint=recovered,
            action_payload_ref=action_payload_ref,
            authority_decision_ref=authority_decision_ref,
        )
        settlement_store = control._llm_producer_settlement_store
        if type(settlement_store) is not BudgetMiddleware:
            raise ValueError("model_input_use_recovery_ledger_unavailable")
        snapshot = settlement_store.snapshot_safe()
        if snapshot.reentry_budget_windows.get(window.window_id) != window:
            raise ValueError("model_input_use_recovery_budget_window_mismatch")
        binding = window.scope.run_binding
        profile = snapshot.invocation_profiles.get(binding.run_id)
        if (profile is not None and profile.run_binding != binding) or (
            profile is None and snapshot.invocation_unconfigured_runs.get(binding.run_id) != binding
        ):
            raise ValueError("model_input_use_recovery_invocation_profile_mismatch")
        work = resolved.result.physical_work_observations
        if not work:
            raise ValueError("model_input_use_recovery_physical_work_not_established")
        bases = {
            key: ProducerBudgetObservation.model_validate(value)
            for key, value in resolved.result.diagnostics["producer_budget_observations"].items()
        }
        for item in work:
            basis = (
                bases.get(item.budget_source_basis_digest)
                if item.budget_source_basis_digest is not None
                else None
            )
            if basis is None or basis.run_binding != binding:
                raise ValueError("model_input_use_recovery_physical_owner_mismatch")
            if profile is None:
                if item.invocation_quota_operation_id is not None:
                    raise ValueError("model_input_use_recovery_invocation_profile_mismatch")
                continue
            reservation = (
                snapshot.invocation_reservations.get(item.invocation_quota_operation_id)
                if item.invocation_quota_operation_id is not None
                else None
            )
            if (
                reservation is None
                or reservation.run_id != binding.run_id
                or reservation.profile_digest != profile.profile_digest
                or reservation.profile_digest != item.invocation_quota_profile_digest
                or reservation.request_digest != item.invocation_quota_request_digest
                or reservation.purpose != item.invocation_quota_purpose
                or reservation.status != item.invocation_quota_status
                or reservation.status != item.status
                or reservation.units != item.work_units
            ):
                raise ValueError("model_input_use_recovery_physical_ledger_mismatch")
    except (OSError, RuntimeError, TypeError, ValueError, KeyError, AttributeError) as exc:
        raise ModelInputSuccessorActionError("model_input_use_recovery_required") from exc
    if currentness_resolver() is not True:
        raise ModelInputSuccessorActionError("model_input_use_action_scope_not_current")
    job_store = control._control_store
    job_store.update_progress_state(
        job_id=selection.job_id,
        state="running",
        progress={
            **job_store.current_execution_job_record().progress,
            _CHECKPOINT_KEY: recovered.model_dump(mode="json", exclude_none=True),
        },
    )
    return recovered


def run_model_input_use_action(
    control: ControlPlaneService,
    *,
    selection: SelectedModelInputSuccessorAction,
    admission: ControlJobExecutionAdmission,
    decision_ref: str,
    currentness_resolver: Callable[[], bool],
) -> ModelInputUseActionCheckpoint:
    """Execute the leased PA2 effect or reopen its already-selected V5 result.

    A checkpoint without a V5 pointer records possible physical work. The owner
    may recover its unique durable output, but absence never permits a blind
    retry. Work lost before durable output remains recovery-required.
    """
    store = control._artifact_store
    job_store = control._control_store
    current = job_store.current_execution_job_admission()
    payload_ref = current.job.payload_ref
    if (
        not matches_artifact_store_protocol(store, CoreJSONArtifactStore)
        or not current.same_execution_identity(admission)
        or current.job.job_id != selection.job_id
        or not payload_ref
        or currentness_resolver() is not True
    ):
        raise ModelInputSuccessorActionError("model_input_use_action_scope_not_current")
    phase = _expected_phase(
        store, selection, action_payload_ref=payload_ref, authority_decision_ref=decision_ref
    )
    raw_checkpoint = current.job.progress.get(_CHECKPOINT_KEY)
    if _CHECKPOINT_KEY in current.job.progress:
        checkpoint = ModelInputUseActionCheckpoint.model_validate(raw_checkpoint)
        previous = _read_checkpoint_selection(
            store, selection=selection, checkpoint=checkpoint, phase=phase
        )
        _verify_selected_routing_use_decision_current(store, selection, previous)
        window = _resolve_action_budget_window(
            control, selection=selection, phase_ref=checkpoint.phase_ref, open_if_missing=False
        )
        if (
            previous.reentry_budget_window_id != window.window_id
            or previous.reentry_budget_window_digest != window.record_digest
        ):
            raise ModelInputSuccessorActionError("model_input_use_checkpoint_budget_mismatch")
        if (
            checkpoint.schema_version is not None
            and checkpoint.execution_ref is None
            and checkpoint.evaluation_decision_ref is None
        ):
            if (
                checkpoint.evaluation_expected_frontier_revision != 0
                or checkpoint.evaluation_expected_frontier_ref is not None
            ):
                raise ModelInputSuccessorActionError("model_input_use_recovery_required")
            checkpoint = _recover_model_input_use_n5(
                control,
                store,
                selection=selection,
                checkpoint=checkpoint,
                window=window,
                action_payload_ref=payload_ref,
                authority_decision_ref=decision_ref,
                currentness_resolver=currentness_resolver,
            )
        if checkpoint.schema_version is not None and checkpoint.evaluation_decision_ref is not None:
            _verify_selected_routing_use_decision_current(store, selection, previous)
            from polisyos.runtime.quality.acquisition_evaluation import (
                GenericModelInputEvaluationDecisionV1,
                read_acquisition_evaluation_artifact,
            )

            decision_record = read_acquisition_evaluation_artifact(
                store=store,
                event_log=control._diagnostic_event_log,
                ref=checkpoint.evaluation_decision_ref,
                record_type=GenericModelInputEvaluationDecisionV1,
            )
            if type(decision_record) is not GenericModelInputEvaluationDecisionV1:
                raise ModelInputSuccessorActionError("model_input_use_decision_not_established")
            if checkpoint.execution_ref is None and (
                decision_record.decision_kind != "comparison"
                or decision_record.comparison_result != "equivalent"
            ):
                checkpoint = _recover_model_input_use_n5(
                    control,
                    store,
                    selection=selection,
                    checkpoint=checkpoint,
                    window=window,
                    action_payload_ref=payload_ref,
                    authority_decision_ref=decision_ref,
                    currentness_resolver=currentness_resolver,
                )
            if checkpoint.execution_ref is not None and (
                decision_record.decision_kind == "comparison"
                and decision_record.comparison_result == "equivalent"
            ):
                raise ModelInputSuccessorActionError("model_input_use_unnecessary_execution")
            if checkpoint.execution_ref is not None:
                verify_model_input_use_result(
                    store,
                    selection=selection,
                    checkpoint=checkpoint,
                    action_payload_ref=payload_ref,
                    authority_decision_ref=decision_ref,
                )
            elif checkpoint.evaluation_current_basis_ref is None:
                raise ModelInputSuccessorActionError("model_input_use_recovery_required")
            if checkpoint.execution_ref is not None and (
                checkpoint.evaluation_replacement_basis_ref is None
            ):
                from polisyos.runtime.quality.acquisition_evaluation import (
                    GenericModelInputEvaluationDecisionV1,
                    issue_generic_model_input_evaluation_basis,
                    read_acquisition_evaluation_artifact,
                    reconcile_generic_model_input_evaluation_completion,
                )

                decision_record = read_acquisition_evaluation_artifact(
                    store=store,
                    event_log=control._diagnostic_event_log,
                    ref=checkpoint.evaluation_decision_ref,
                    record_type=GenericModelInputEvaluationDecisionV1,
                )
                if type(decision_record) is not GenericModelInputEvaluationDecisionV1:
                    raise ModelInputSuccessorActionError("model_input_use_decision_not_established")
                if decision_record.decision_kind == "initial":
                    if checkpoint.evaluation_current_basis_ref is None:
                        raise ModelInputSuccessorActionError(
                            "model_input_use_initial_evaluation_missing"
                        )
                    checkpoint = _checkpoint_with_evaluation(
                        checkpoint,
                        decision_ref=checkpoint.evaluation_decision_ref,
                        current_basis_ref=checkpoint.evaluation_current_basis_ref,
                        replacement_basis_ref=checkpoint.evaluation_current_basis_ref,
                    )
                elif decision_record.comparison_result != "equivalent":
                    port = _build_model_input_use_n5_port(
                        control, store, selection=selection, window=window
                    )
                    evaluation = _generic_selected_evaluation(selection, checkpoint)
                    evaluated = issue_generic_model_input_evaluation_basis(
                        store=store,
                        event_log=control._diagnostic_event_log,
                        origin=selection.origin,
                        prior_origin=selection.origin,
                        input_ref=selection.origin.n5_expectation.input_ref,
                        semantic_successor_ref=checkpoint.semantic_successor_ref,
                        controller=port._controller,
                        basis_role="evaluated",
                        evaluation=evaluation,
                        prospective_basis_ref=checkpoint.evaluation_current_basis_ref,
                        comparison_decision_ref=checkpoint.evaluation_decision_ref,
                    )
                    evaluated_ref = _persist_generic_model_input_record(
                        store, control._diagnostic_event_log, evaluated
                    )
                    reconcile_generic_model_input_evaluation_completion(
                        store=store,
                        event_log=control._diagnostic_event_log,
                        origin=selection.origin,
                        prior_origin=selection.origin,
                        controller=port._controller,
                        comparison_decision_ref=checkpoint.evaluation_decision_ref,
                        evaluated_basis_ref=evaluated_ref,
                    )
                    checkpoint = _checkpoint_with_evaluation(
                        checkpoint,
                        decision_ref=checkpoint.evaluation_decision_ref,
                        current_basis_ref=checkpoint.evaluation_current_basis_ref,
                        replacement_basis_ref=evaluated_ref,
                    )
                job_store.update_progress_state(
                    job_id=selection.job_id,
                    state="running",
                    progress={
                        **job_store.current_execution_job_record().progress,
                        _CHECKPOINT_KEY: checkpoint.model_dump(mode="json", exclude_none=True),
                    },
                )
            if currentness_resolver() is not True:
                raise ModelInputSuccessorActionError("model_input_use_action_scope_not_current")
            return checkpoint
        if checkpoint.schema_version is not None and checkpoint.execution_ref is not None:
            # V2 pending means this action paid N5 before its initial basis and
            # decision were persisted. Finish selection from that exact V5.
            if (
                checkpoint.evaluation_expected_frontier_revision != 0
                or checkpoint.evaluation_expected_frontier_ref is not None
            ):
                raise ModelInputSuccessorActionError("model_input_use_recovery_required")
            verify_model_input_use_result(
                store,
                selection=selection,
                checkpoint=checkpoint,
                action_payload_ref=payload_ref,
                authority_decision_ref=decision_ref,
            )
            from polisyos.runtime.quality.acquisition_evaluation import (
                issue_generic_model_input_evaluation_decision,
            )

            port = _build_model_input_use_n5_port(
                control, store, selection=selection, window=window
            )
            evaluation = _generic_selected_evaluation(selection, checkpoint)
            basis = _issue_model_input_basis(
                control, selection, checkpoint, port=port, role="evaluated", evaluation=evaluation
            )
            basis_ref = _persist_generic_model_input_record(
                store, control._diagnostic_event_log, basis
            )
            decision_record = issue_generic_model_input_evaluation_decision(
                store=store,
                event_log=control._diagnostic_event_log,
                origin=selection.origin,
                prior_origin=None,
                controller=port._controller,
                semantic_successor_ref=checkpoint.semantic_successor_ref,
                current_basis_ref=basis_ref,
                prior_basis_ref=None,
                prior_evaluation=None,
                decision_kind="initial",
                comparison_result=None,
                reason_codes=(),
                expected_frontier_revision=0,
                expected_frontier_ref=None,
                generated_at=datetime.now(UTC).isoformat(),
            )
            decision_artifact_ref = _persist_generic_model_input_record(
                store, control._diagnostic_event_log, decision_record
            )
            checkpoint = _checkpoint_with_evaluation(
                checkpoint,
                decision_ref=decision_artifact_ref,
                current_basis_ref=basis_ref,
                replacement_basis_ref=basis_ref,
            )
            job_store.update_progress_state(
                job_id=selection.job_id,
                state="running",
                progress={
                    **job_store.current_execution_job_record().progress,
                    _CHECKPOINT_KEY: checkpoint.model_dump(mode="json", exclude_none=True),
                },
            )
            return checkpoint
        if checkpoint.execution_ref is not None:
            # A legacy paid result remains readable but is not upgraded into
            # current-use retention without the versioned owner witnesses.
            verify_model_input_use_result(
                store,
                selection=selection,
                checkpoint=checkpoint,
                action_payload_ref=payload_ref,
                authority_decision_ref=decision_ref,
            )
            if currentness_resolver() is not True:
                raise ModelInputSuccessorActionError("model_input_use_action_scope_not_current")
            return checkpoint
        raise ModelInputSuccessorActionError("model_input_use_recovery_required")

    phase_ref = persist_model_input_use_action_phase(store, phase)
    window = _resolve_action_budget_window(
        control, selection=selection, phase_ref=phase_ref, open_if_missing=True
    )
    frontier_key = _generic_model_input_frontier_key(selection)
    frontier = job_store.read_generic_model_input_frontier(frontier_key)
    checkpoint = ModelInputUseActionCheckpoint(
        phase_ref=phase_ref,
        semantic_successor_ref=_materialize_semantic_successor(
            control,
            store,
            selection=selection,
            admission=current,
            phase_ref=phase_ref,
            phase=phase,
            window=window,
        ),
        schema_version="polisyos.runtime.ModelInputUseActionCheckpoint@2.0",
        evaluation_expected_frontier_revision=frontier.revision if frontier is not None else 0,
        evaluation_expected_frontier_ref=frontier.frontier_ref if frontier is not None else None,
    )
    job_store.update_progress_state(
        job_id=selection.job_id,
        state="running",
        progress={
            **current.job.progress,
            _CHECKPOINT_KEY: checkpoint.model_dump(mode="json", exclude_none=True),
        },
    )
    from polisyos.runtime.quality.acquisition_evaluation import (
        compare_generic_model_input_evaluation_bases,
        issue_generic_model_input_evaluation_basis,
        issue_generic_model_input_evaluation_decision,
    )

    port = _build_model_input_use_n5_port(control, store, selection=selection, window=window)
    if currentness_resolver() is not True:
        raise ModelInputSuccessorActionError("model_input_use_action_scope_not_current")
    if _CHECKPOINT_KEY in current.job.progress:
        # The V1 checkpoint predates evaluation selection. If it has no actual
        # V5, physical execution may already have happened; never repeat it.
        raise ModelInputSuccessorActionError("model_input_use_recovery_required")

    prior_evaluation = frontier.selected_evaluation if frontier is not None else None
    if frontier is None:
        completed = _run_model_input_use_n5(
            control,
            store,
            selection=selection,
            checkpoint=checkpoint,
            window=window,
            currentness_resolver=currentness_resolver,
            port=port,
        )
        # Persist the paid producer result before attempting any basis or
        # decision replay, so a crash cannot cause a second N5 execution.
        job_store.update_progress_state(
            job_id=selection.job_id,
            state="running",
            progress={
                **job_store.current_execution_job_record().progress,
                _CHECKPOINT_KEY: completed.model_dump(mode="json", exclude_none=True),
            },
        )
        evaluation = _generic_selected_evaluation(selection, completed)
        basis = _issue_model_input_basis(
            control, selection, completed, port=port, role="evaluated", evaluation=evaluation
        )
        basis_ref = _persist_generic_model_input_record(store, control._diagnostic_event_log, basis)
        decision = issue_generic_model_input_evaluation_decision(
            store=store,
            event_log=control._diagnostic_event_log,
            origin=selection.origin,
            prior_origin=None,
            controller=port._controller,
            semantic_successor_ref=completed.semantic_successor_ref,
            current_basis_ref=basis_ref,
            prior_basis_ref=None,
            prior_evaluation=None,
            decision_kind="initial",
            comparison_result=None,
            reason_codes=(),
            expected_frontier_revision=0,
            expected_frontier_ref=None,
            generated_at=datetime.now(UTC).isoformat(),
        )
        evaluation_decision_ref = _persist_generic_model_input_record(
            store, control._diagnostic_event_log, decision
        )
        completed = _checkpoint_with_evaluation(
            completed,
            decision_ref=evaluation_decision_ref,
            current_basis_ref=basis_ref,
            replacement_basis_ref=basis_ref,
        )
    else:
        from polisyos.runtime.quality.acquisition_evaluation import (
            reconcile_generic_model_input_evaluation_completion,
        )

        try:
            prior_basis = _read_generic_model_input_basis(
                store, control._diagnostic_event_log, frontier.basis_ref
            )
        except (OSError, RuntimeError, TypeError, ValueError, KeyError, AttributeError):
            prior_basis = None
        prospective = issue_generic_model_input_evaluation_basis(
            store=store,
            origin=selection.origin,
            input_ref=selection.origin.n5_expectation.input_ref,
            semantic_successor_ref=checkpoint.semantic_successor_ref,
            controller=port._controller,
            basis_role="prospective",
        )
        prospective_ref = _persist_generic_model_input_record(
            store, control._diagnostic_event_log, prospective
        )
        if prior_basis is None:
            comparison, reasons = (
                "not_established",
                ("generic_model_input_prior_basis_not_established",),
            )
        else:
            comparison, reasons = compare_generic_model_input_evaluation_bases(
                store=store,
                prior=prior_basis,
                current=prospective,
                prior_origin=selection.origin,
                current_origin=selection.origin,
                controller=port._controller,
            )
        decision = issue_generic_model_input_evaluation_decision(
            store=store,
            event_log=control._diagnostic_event_log,
            origin=selection.origin,
            prior_origin=selection.origin,
            controller=port._controller,
            semantic_successor_ref=checkpoint.semantic_successor_ref,
            current_basis_ref=prospective_ref,
            prior_basis_ref=frontier.basis_ref,
            prior_evaluation=prior_evaluation if prior_basis is not None else None,
            decision_kind="comparison",
            comparison_result=comparison,
            reason_codes=reasons,
            expected_frontier_revision=frontier.revision,
            expected_frontier_ref=frontier.frontier_ref,
            generated_at=datetime.now(UTC).isoformat(),
        )
        evaluation_decision_ref = _persist_generic_model_input_record(
            store, control._diagnostic_event_log, decision
        )
        if comparison == "equivalent":
            completed = _checkpoint_with_evaluation(
                checkpoint,
                decision_ref=evaluation_decision_ref,
                current_basis_ref=prospective_ref,
                replacement_basis_ref=None,
            )
        else:
            # Record the decision before potentially paid work. A replacement
            # worker can recover only a unique, fully reopened durable V5.
            checkpoint = _checkpoint_with_evaluation(
                checkpoint,
                decision_ref=evaluation_decision_ref,
                current_basis_ref=prospective_ref,
                replacement_basis_ref=None,
            )
            job_store.update_progress_state(
                job_id=selection.job_id,
                state="running",
                progress={
                    **job_store.current_execution_job_record().progress,
                    _CHECKPOINT_KEY: checkpoint.model_dump(mode="json", exclude_none=True),
                },
            )
            completed = _run_model_input_use_n5(
                control,
                store,
                selection=selection,
                checkpoint=checkpoint,
                window=window,
                currentness_resolver=currentness_resolver,
                port=port,
            )
            job_store.update_progress_state(
                job_id=selection.job_id,
                state="running",
                progress={
                    **job_store.current_execution_job_record().progress,
                    _CHECKPOINT_KEY: completed.model_dump(mode="json", exclude_none=True),
                },
            )
            evaluation = _generic_selected_evaluation(selection, completed)
            try:
                evaluated_basis = issue_generic_model_input_evaluation_basis(
                    store=store,
                    event_log=control._diagnostic_event_log,
                    origin=selection.origin,
                    prior_origin=selection.origin,
                    input_ref=selection.origin.n5_expectation.input_ref,
                    semantic_successor_ref=completed.semantic_successor_ref,
                    controller=port._controller,
                    basis_role="evaluated",
                    evaluation=evaluation,
                    prospective_basis_ref=prospective_ref,
                    comparison_decision_ref=evaluation_decision_ref,
                )
                evaluated_ref = _persist_generic_model_input_record(
                    store, control._diagnostic_event_log, evaluated_basis
                )
                evaluated_basis = reconcile_generic_model_input_evaluation_completion(
                    store=store,
                    event_log=control._diagnostic_event_log,
                    origin=selection.origin,
                    prior_origin=selection.origin,
                    controller=port._controller,
                    comparison_decision_ref=evaluation_decision_ref,
                    evaluated_basis_ref=evaluated_ref,
                )
                completed = _checkpoint_with_evaluation(
                    completed,
                    decision_ref=evaluation_decision_ref,
                    current_basis_ref=prospective_ref,
                    replacement_basis_ref=evaluated_ref,
                )
            except (OSError, RuntimeError, TypeError, ValueError, KeyError, AttributeError):
                # Keep the actual current N5 as an observation. An unverified
                # replacement cannot advance retained selection.
                completed = _checkpoint_with_evaluation(
                    completed,
                    decision_ref=evaluation_decision_ref,
                    current_basis_ref=prospective_ref,
                    replacement_basis_ref=None,
                )
    # Select actual persisted output immediately under the current lease. A
    # replacement worker can verify this exact V5 if verification is cut short.
    job_store.update_progress_state(
        job_id=selection.job_id,
        state="running",
        progress={
            **job_store.current_execution_job_record().progress,
            _CHECKPOINT_KEY: completed.model_dump(mode="json", exclude_none=True),
        },
    )
    if completed.execution_ref is not None:
        verify_model_input_use_result(
            store,
            selection=selection,
            checkpoint=completed,
            action_payload_ref=payload_ref,
            authority_decision_ref=decision_ref,
        )
    if currentness_resolver() is not True:
        raise ModelInputSuccessorActionError("model_input_use_action_scope_not_current")
    persisted_selection = read_model_input_successor_selection(
        store, completed.semantic_successor_ref
    )
    _verify_selected_routing_use_decision_current(store, selection, persisted_selection)
    if currentness_resolver() is not True:
        raise ModelInputSuccessorActionError("model_input_use_action_scope_not_current")
    return completed


def prepare_model_input_use_frontier_completion(
    control: ControlPlaneService,
    *,
    selection: SelectedModelInputSuccessorAction,
    checkpoint: ModelInputUseActionCheckpoint,
    action_payload_ref: str,
    authority_decision_ref: str,
    controller: JointSimulationHorizonController | None = None,
) -> GenericModelInputEvaluationFrontierCAS:
    """Replay a terminal checkpoint and prepare its fenced frontier CAS.

    The store remains the sole writer. This function reopens the selected
    action, decision and basis owners so the worker can pass a typed CAS into
    the same terminal transaction without treating progress as proof.
    The completion owner must revalidate the signed PA2/current action after
    this replay and immediately before its fenced ``complete_job`` call.
    """
    from polisyos.runtime.quality.acquisition_evaluation import (
        GenericModelInputEvaluationDecisionV1,
        issue_generic_model_input_evaluation_decision,
        read_acquisition_evaluation_artifact,
        reconcile_generic_model_input_evaluation_completion,
    )

    from .control_plane_store import GenericModelInputEvaluationFrontierCAS

    if (
        checkpoint.schema_version != "polisyos.runtime.ModelInputUseActionCheckpoint@2.0"
        or checkpoint.evaluation_decision_ref is None
        or checkpoint.evaluation_current_basis_ref is None
    ):
        raise ModelInputSuccessorActionError("model_input_use_evaluation_not_established")
    current = control._control_store.current_execution_job_admission()
    if (
        current.job.job_id != selection.job_id
        or current.job.run_id != selection.run_id
        or current.job.payload_ref != action_payload_ref
        or current.job.state != "running"
        or not current.job.lease_owner
    ):
        raise ModelInputSuccessorActionError("model_input_use_action_scope_not_current")
    phase = _expected_phase(
        control._artifact_store,
        selection,
        action_payload_ref=action_payload_ref,
        authority_decision_ref=authority_decision_ref,
    )
    selected = _read_checkpoint_selection(
        control._artifact_store,
        selection=selection,
        checkpoint=checkpoint,
        phase=phase,
    )
    _verify_selected_routing_use_decision_current(control._artifact_store, selection, selected)
    if controller is None:
        window = _resolve_action_budget_window(
            control,
            selection=selection,
            phase_ref=checkpoint.phase_ref,
            open_if_missing=False,
        )
        controller = _build_model_input_use_n5_port(
            control, control._artifact_store, selection=selection, window=window
        )._controller
    from .control_plane_store import GenericModelInputEvaluationFrontierValue

    event_log = control._diagnostic_event_log
    store = control._artifact_store
    decision = read_acquisition_evaluation_artifact(
        store=store,
        event_log=event_log,
        ref=checkpoint.evaluation_decision_ref,
        record_type=GenericModelInputEvaluationDecisionV1,
    )
    current_basis = _read_generic_model_input_basis(
        store, event_log, checkpoint.evaluation_current_basis_ref
    )
    if type(decision) is not GenericModelInputEvaluationDecisionV1 or (
        decision.action_job_id != selection.job_id
        or decision.action_phase_ref != checkpoint.phase_ref
        or decision.semantic_successor_ref != checkpoint.semantic_successor_ref
        or decision.authority_decision_ref
        != _selected_json_ref(store, authority_decision_ref, kind=_DECISION_KIND)
        or decision.current_basis_ref != checkpoint.evaluation_current_basis_ref
    ):
        raise ModelInputSuccessorActionError("model_input_use_decision_binding_mismatch")
    replayed_decision = issue_generic_model_input_evaluation_decision(
        store=store,
        event_log=event_log,
        origin=selection.origin,
        prior_origin=selection.origin if decision.expected_frontier_revision else None,
        controller=controller,
        semantic_successor_ref=checkpoint.semantic_successor_ref,
        current_basis_ref=checkpoint.evaluation_current_basis_ref,
        prior_basis_ref=decision.prior_basis_ref,
        prior_evaluation=decision.prior_evaluation,
        decision_kind=decision.decision_kind,
        comparison_result=decision.comparison_result,
        reason_codes=decision.reason_codes,
        expected_frontier_revision=decision.expected_frontier_revision,
        expected_frontier_ref=decision.expected_frontier_ref,
        generated_at=decision.generated_at,
    )
    if replayed_decision != decision:
        raise ModelInputSuccessorActionError("model_input_use_decision_replay_mismatch")

    replacement_basis = None
    replacement = None
    if decision.decision_kind == "initial":
        if (
            checkpoint.execution_ref is None
            or checkpoint.result_ref is None
            or current_basis.basis_role != "evaluated"
            or current_basis.evaluation is None
            or checkpoint.evaluation_replacement_basis_ref
            != checkpoint.evaluation_current_basis_ref
        ):
            raise ModelInputSuccessorActionError("model_input_use_initial_evaluation_missing")
        replacement_basis = current_basis
        replacement = GenericModelInputEvaluationFrontierValue(
            basis_ref=checkpoint.evaluation_current_basis_ref,
            basis_content_hash=current_basis.content_hash,
            selected_evaluation=current_basis.evaluation,
            selection_decision_ref=checkpoint.evaluation_decision_ref,
        )
    elif checkpoint.evaluation_replacement_basis_ref is not None:
        if checkpoint.execution_ref is None or checkpoint.result_ref is None:
            raise ModelInputSuccessorActionError("model_input_use_replacement_without_execution")
        replacement_basis = reconcile_generic_model_input_evaluation_completion(
            store=store,
            event_log=event_log,
            origin=selection.origin,
            prior_origin=selection.origin if decision.expected_frontier_revision else None,
            controller=controller,
            comparison_decision_ref=checkpoint.evaluation_decision_ref,
            evaluated_basis_ref=checkpoint.evaluation_replacement_basis_ref,
        )
        evaluation = replacement_basis.evaluation
        if evaluation is None:
            raise ModelInputSuccessorActionError("model_input_use_replacement_not_established")
        replacement = GenericModelInputEvaluationFrontierValue(
            basis_ref=checkpoint.evaluation_replacement_basis_ref,
            basis_content_hash=replacement_basis.content_hash,
            selected_evaluation=evaluation,
            selection_decision_ref=checkpoint.evaluation_decision_ref,
        )

    expected_revision = decision.expected_frontier_revision
    expected_ref = decision.expected_frontier_ref
    comparison_result = (
        "initial" if decision.decision_kind == "initial" else decision.comparison_result
    )
    if comparison_result is None:
        raise ModelInputSuccessorActionError("model_input_use_comparison_not_established")
    return GenericModelInputEvaluationFrontierCAS(
        key=_generic_model_input_frontier_key(selection),
        expected_revision=expected_revision,
        expected_frontier_ref=expected_ref,
        action_job_id=selection.job_id,
        decision_ref=checkpoint.evaluation_decision_ref,
        decision=decision,
        current_basis=current_basis,
        replacement_basis=replacement_basis,
        replacement=replacement,
    )


def resolve_model_input_use_evaluation_history(
    control_service: ControlPlaneService,
    *,
    selection: ModelInputSuccessorIdentity,
    checkpoint: ModelInputUseActionCheckpoint,
    action_payload_ref: str,
    authority_decision_ref: str,
) -> GenericModelInputUseHistory | None:
    """Replay immutable V2 use history without issuing a current reuse decision.

    Original predicates describe their issuance time. No past loaded provider
    environment is reconstructed for a retained use, and current provider bytes
    are not a prerequisite to viewing the original numerical observation.
    Legacy checkpoints do not gain retention semantics by being read here.
    """
    if checkpoint.schema_version is None:
        return None
    if (
        checkpoint.evaluation_decision_ref is None
        or checkpoint.evaluation_current_basis_ref is None
    ):
        raise ModelInputSuccessorActionError("model_input_use_evaluation_not_established")
    from polisyos.runtime.quality.acquisition_evaluation import (
        GenericModelInputEvaluationDecisionV1,
        read_acquisition_evaluation_artifact,
        replay_generic_model_input_basis_for_history,
        replay_generic_model_input_decision_for_history,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
        GenericCycleSimulationN5ExecutionV5,
        GenericN5ExecutionJoinExpectation,
    )

    store = control_service._artifact_store
    event_log = control_service._diagnostic_event_log
    phase = _expected_phase(
        store,
        selection,
        action_payload_ref=action_payload_ref,
        authority_decision_ref=authority_decision_ref,
    )
    selected = _read_checkpoint_selection(
        store, selection=selection, checkpoint=checkpoint, phase=phase
    )
    decision = read_acquisition_evaluation_artifact(
        store=store,
        event_log=event_log,
        ref=checkpoint.evaluation_decision_ref,
        record_type=GenericModelInputEvaluationDecisionV1,
    )
    basis = _read_generic_model_input_basis(
        store, event_log, checkpoint.evaluation_current_basis_ref
    )
    if type(decision) is not GenericModelInputEvaluationDecisionV1:
        raise ModelInputSuccessorActionError("model_input_use_decision_not_established")
    window = _resolve_action_budget_window(
        control_service,
        selection=selection,
        phase_ref=checkpoint.phase_ref,
        open_if_missing=False,
    )
    if (
        selected.reentry_budget_window_id != window.window_id
        or selected.reentry_budget_window_digest != window.record_digest
    ):
        raise ModelInputSuccessorActionError("model_input_use_history_budget_window_mismatch")
    if basis.action_job_id != selection.job_id or (
        decision.action_job_id,
        decision.action_phase_ref,
        decision.semantic_successor_ref,
        decision.current_basis_ref,
        decision.authority_decision_ref,
    ) != (
        selection.job_id,
        checkpoint.phase_ref,
        checkpoint.semantic_successor_ref,
        checkpoint.evaluation_current_basis_ref,
        _selected_json_ref(store, authority_decision_ref, kind=_DECISION_KIND),
    ):
        raise ModelInputSuccessorActionError("model_input_use_decision_binding_mismatch")
    key = _generic_model_input_frontier_key(selection)
    use = control_service._control_store.get_generic_model_input_use(
        key=key, action_job_id=selection.job_id
    )
    if use is None or use.decision_ref != checkpoint.evaluation_decision_ref:
        raise ModelInputSuccessorActionError("model_input_use_history_not_established")
    selected_frontier = (
        control_service._control_store.get_generic_model_input_frontier_by_ref(use.frontier_ref)
        if use.frontier_ref is not None
        else None
    )
    prior_frontier = (
        control_service._control_store.get_generic_model_input_frontier_by_ref(
            decision.expected_frontier_ref
        )
        if decision.expected_frontier_ref is not None
        else None
    )
    selected_basis = (
        _read_generic_model_input_basis(store, event_log, selected_frontier.basis_ref)
        if selected_frontier is not None
        else None
    )
    if (
        use.key != key
        or use.action_job_id != selection.job_id
        or use.current_basis_ref != checkpoint.evaluation_current_basis_ref
        or use.decision_content_hash != decision.content_hash
        or use.predicate_provenance != decision.predicate_provenance
        or use.frontier_revision != (selected_frontier.revision if selected_frontier else 0)
        or use.frontier_ref != (selected_frontier.frontier_ref if selected_frontier else None)
        or use.comparison_result
        != ("initial" if decision.decision_kind == "initial" else decision.comparison_result)
    ):
        raise ModelInputSuccessorActionError("model_input_use_history_binding_mismatch")
    should_replace = (
        decision.decision_kind == "initial"
        or checkpoint.evaluation_replacement_basis_ref is not None
    )
    if should_replace:
        if (
            selected_frontier is None
            or selected_basis is None
            or selected_basis.content_hash != selected_frontier.basis_content_hash
            or selected_frontier.selection_decision_ref != checkpoint.evaluation_decision_ref
            or selected_frontier.revision != decision.expected_frontier_revision + 1
        ):
            raise ModelInputSuccessorActionError("model_input_use_selected_frontier_mismatch")
    elif selected_frontier is not prior_frontier and (
        selected_frontier is None
        or prior_frontier is None
        or selected_frontier.frontier_ref != prior_frontier.frontier_ref
    ):
        raise ModelInputSuccessorActionError("model_input_use_prior_frontier_mismatch")
    head = control_service._control_store.read_generic_model_input_frontier(key)
    relation: Literal["selected", "superseded", "not_established"]
    if selected_frontier is None:
        relation = "not_established"
    elif head is not None and head.frontier_ref == selected_frontier.frontier_ref:
        relation = "selected"
    else:
        relation = "superseded"

    def resolve_original(
        evaluation: GenericModelInputSelectedEvaluation,
    ) -> tuple[GenericCycleSimulationN5ExecutionV5, GenericN5ResolvedResult]:
        expected = GenericN5ExecutionJoinExpectation.model_validate(
            {
                **selection.origin.n5_expectation.model_dump(mode="python"),
                "input_ref": evaluation.input_ref,
                "status": "joint_simulated",
                "result_ref": evaluation.result_ref,
                "model_input_obligation_set_ref": None,
                "semantic_successor_ref": evaluation.semantic_successor_ref,
            }
        )
        outcome, result = GenericCycleSimulationAdmissionOwner(
            profiles=(), store=store
        ).resolve_n5_execution_join_with_result(evaluation.execution_ref, expected=expected)
        if (
            outcome.status != "resolved"
            or type(outcome.execution) is not GenericCycleSimulationN5ExecutionV5
            or outcome.execution.action_job_id != evaluation.action_job_id
            or result is None
        ):
            raise ModelInputSuccessorActionError(
                outcome.code or "model_input_use_original_evaluation_not_established"
            )
        return outcome.execution, result

    selected_execution, selected_result = (
        resolve_original(selected_frontier.selected_evaluation)
        if selected_frontier is not None
        else (None, None)
    )
    prior_evaluation = decision.prior_evaluation
    prior_execution, prior_result = (
        resolve_original(prior_evaluation) if prior_evaluation is not None else (None, None)
    )
    current_result = (
        verify_model_input_use_result(
            store,
            selection=selection,
            checkpoint=checkpoint,
            action_payload_ref=action_payload_ref,
            authority_decision_ref=authority_decision_ref,
        )
        if checkpoint.execution_ref is not None
        else None
    )
    evaluation_context = (
        _generic_selected_evaluation(selection, checkpoint)
        if checkpoint.execution_ref is not None
        else selected_frontier.selected_evaluation
        if selected_frontier is not None
        else None
    )
    if evaluation_context is None:
        raise ModelInputSuccessorActionError("model_input_use_history_evaluation_not_established")
    replayed_basis = replay_generic_model_input_basis_for_history(
        store=store,
        event_log=event_log,
        origin=selection.origin,
        basis_ref=checkpoint.evaluation_current_basis_ref,
        evaluation_context=evaluation_context,
    )
    replayed_decision = replay_generic_model_input_decision_for_history(
        store=store,
        event_log=event_log,
        origin=selection.origin,
        decision_ref=checkpoint.evaluation_decision_ref,
        evaluation_context=evaluation_context,
    )
    if replayed_basis != basis or replayed_decision != decision:
        raise ModelInputSuccessorActionError("model_input_use_history_record_replay_mismatch")
    if selected_frontier is not None and selected_basis is not None:
        if selected_basis.evaluation is None:
            raise ModelInputSuccessorActionError(
                "model_input_use_history_selected_evaluation_missing"
            )
        replayed_selected = replay_generic_model_input_basis_for_history(
            store=store,
            event_log=event_log,
            origin=selection.origin,
            basis_ref=selected_frontier.basis_ref,
            evaluation_context=selected_basis.evaluation,
        )
        if replayed_selected != selected_basis:
            raise ModelInputSuccessorActionError("model_input_use_selected_basis_replay_mismatch")
    return GenericModelInputUseHistory(
        key=key,
        use=use,
        decision=decision,
        current_basis=basis,
        selected_basis=selected_basis,
        prior_evaluation=prior_evaluation,
        prior_frontier=prior_frontier,
        selected_frontier=selected_frontier,
        frontier_relation=relation,
        selected_frontier_execution=selected_execution,
        selected_frontier_result=selected_result,
        prior_execution=prior_execution,
        prior_result=prior_result,
        current_action_result=current_result,
        history_limitation_codes=(
            *(
                ("past_provider_profile_not_independently_reconstructed",)
                if checkpoint.execution_ref is None
                else ()
            ),
            *(
                (
                    "past_method_abi_completeness_not_established",
                    "past_method_provider_completeness_not_established",
                )
                if basis.comparison_profile == "generic_program_graph_mapped_numpy_methods_v3"
                else ()
            ),
        ),
    )
