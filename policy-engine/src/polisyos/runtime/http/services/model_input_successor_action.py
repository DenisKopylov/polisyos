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
    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedModelInputRoutingOrigin
    from polisyos.runtime.quality.generic_simulation_admission import GenericN5ResolvedResult
    from polisyos.runtime.quality.substrate_registry import CatalogServingSourcePaths
    from polisyos.scientist.orchestration.engine import BudgetLedgerReentryBudgetWindow

    from .control import ControlPlaneService
    from .control_plane_store import ControlJobExecutionAdmission


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
    """Lease-fenced pointer to a selected input and optional persisted N5 result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    phase_ref: ArtifactRef
    semantic_successor_ref: ArtifactRef
    execution_ref: ArtifactRef | None = None
    result_ref: ArtifactRef | None = None

    @model_validator(mode="after")
    def _selected_artifact_profiles(self) -> ModelInputUseActionCheckpoint:
        refs = (
            (self.phase_ref, MODEL_INPUT_USE_ACTION_PHASE_KIND),
            (self.semantic_successor_ref, MODEL_INPUT_SUCCESSOR_SELECTION_KIND),
        )
        if self.execution_ref is not None:
            refs += ((self.execution_ref, "runtime.quality.generic_cycle_simulation_n5_execution"),)
        if (
            (self.execution_ref is None) != (self.result_ref is None)
            or any(
                ref.kind != kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
                for ref, kind in refs
            )
            or (self.result_ref is not None and self.result_ref.manifest_profile_sha256 is None)
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
    from polisyos.runtime.quality.model_input_routing import verify_model_input_routing_report
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
    report = verify_model_input_routing_report(
        store,
        request.routing_report_ref,
        expected_obligation_set_ref=origin.routing_report.obligation_set_ref,
        selected_basis=origin.selected_basis,
        catalog_authority=authority,
    )
    if len(report.routes) != 1 or (descriptor := report.routes[0].source_descriptor) is None:
        raise ModelInputSuccessorActionError("model_input_use_single_resolved_route_required")
    admission = _read_model_input_activation_boundary(store, request.activation_receipt_ref)
    passport = AdmissionPassport.model_validate(
        epoch_contract.load_verified_epoch_statement(
            store=store,
            ref=admission.passport_ref,
            expected_kind="epoch.acquisition_passport_snapshot",
        )
    )
    if (
        descriptor.authority_entry_id != passport.authority_entry_id
        or descriptor.authority_registry_content_sha256
        != passport.authority_registry_content_sha256
    ):
        raise ModelInputSuccessorActionError("model_input_use_activated_source_mismatch")
    overlay = CatalogAcquisitionOverlay(authority.baseline_path, source.overlay_path)
    try:
        active = overlay.read_activated_semantic_epoch_observations(
            receipt_ref=request.activation_receipt_ref,
            artifact_store=store,
            passport=passport,
            authority=authority,
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
    """Return a completion payload only for a checkpoint with an actual execution."""
    if checkpoint.execution_ref is None or checkpoint.result_ref is None:
        raise ModelInputSuccessorActionError("model_input_use_result_not_established")
    return {
        "receipt_phase": "terminal",
        "terminal_receipt_ref": str(checkpoint.execution_ref.artifact_id),
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
        materialize_routed_model_input_observation,
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


def _run_model_input_use_n5(
    control: ControlPlaneService,
    store: CoreJSONArtifactStore,
    *,
    selection: SelectedModelInputSuccessorAction,
    checkpoint: ModelInputUseActionCheckpoint,
    window: BudgetLedgerReentryBudgetWindow,
    currentness_resolver: Callable[[], bool],
) -> ModelInputUseActionCheckpoint:
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

    def require_current_action() -> bool:
        return (
            currentness_resolver() is True
            and settlement_store.resolve_reentry_budget_window_safe(window.scope) == window
        )

    observation = JointSimulationPort(
        repo_root=selection.catalog_source.repo_root,
        artifact_store=store,
        producer_budget_observer=observer,
        generic_cycle_simulation_admission_owner=GenericCycleSimulationAdmissionOwner(
            profiles=(), store=store
        ),
    ).run_semantic_successor(
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
    )


def run_model_input_use_action(
    control: ControlPlaneService,
    *,
    selection: SelectedModelInputSuccessorAction,
    admission: ControlJobExecutionAdmission,
    decision_ref: str,
    currentness_resolver: Callable[[], bool],
) -> ModelInputUseActionCheckpoint:
    """Execute the leased PA2 effect or reopen its already-selected V5 result.

    A checkpoint without V5 records possible physical work. Only a recoverable
    selected result can complete the action; a blind retry could repeat work.
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
        window = _resolve_action_budget_window(
            control, selection=selection, phase_ref=checkpoint.phase_ref, open_if_missing=False
        )
        if (
            previous.reentry_budget_window_id != window.window_id
            or previous.reentry_budget_window_digest != window.record_digest
        ):
            raise ModelInputSuccessorActionError("model_input_use_checkpoint_budget_mismatch")
        if checkpoint.execution_ref is None:
            raise ModelInputSuccessorActionError("model_input_use_recovery_required")
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

    phase_ref = persist_model_input_use_action_phase(store, phase)
    window = _resolve_action_budget_window(
        control, selection=selection, phase_ref=phase_ref, open_if_missing=True
    )
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
    )
    job_store.update_progress_state(
        job_id=selection.job_id,
        state="running",
        progress={
            **current.job.progress,
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
    verify_model_input_use_result(
        store,
        selection=selection,
        checkpoint=completed,
        action_payload_ref=payload_ref,
        authority_decision_ref=decision_ref,
    )
    if currentness_resolver() is not True:
        raise ModelInputSuccessorActionError("model_input_use_action_scope_not_current")
    return completed
