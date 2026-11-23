"""Native action context adapter for the existing Generic generation route.

The original configured profile remains configuration evidence. An acquired
candidate world, the current action lease, and a freshly generated N4 source
have separate identities. This module never manufactures an NL worker scope,
changes the configured profile map, fetches data, or invokes a numerical kernel.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from polisyos.core import artifacts, canon
from polisyos.pdc import gy_content_hash

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.registry import RegistryBundleContent
    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionActionService,
        VerifiedModelInputUseWorker,
    )
    from polisyos.runtime.http.services.control_plane_store import ControlJobRecord
    from polisyos.runtime.http.services.model_input_successor_action import (
        NativeModelInputSuccessorActionRequest,
        SelectedNativeModelInputSuccessorAction,
    )
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedAcquisitionRouteClosure
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
        NativeDerivationInputReplay,
        NativeDerivedWorldSelection,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContext,
        CycleSubstrateContextArtifactOwner,
    )
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleNativeWorldContextHandoffV1,
        GenericCycleSimulationAdmissionOwner,
        GenericCycleSimulationN5InputV1,
        GenericCycleSimulationProfileV1,
        NativeModelInputUseWorldCheckpointV1,
        NativeModelInputUseWorldSourceRowV1,
    )
    from polisyos.runtime.quality.model_input_successor_selection import (
        ModelInputSuccessorSelection,
        ModelInputUseActionPhase,
    )


@dataclass(frozen=True, slots=True)
class NativeModelInputUseSourceSelection:
    """Candidate-only exact Native source rows and one current selected B row."""

    predecessor_terminal_ref: artifacts.ArtifactRef
    historical_native_world_selection: NativeDerivedWorldSelection
    input_collection_ref: artifacts.ArtifactRef
    input_collection_replay: NativeDerivationInputReplay
    source_rows: tuple[NativeModelInputUseWorldSourceRowV1, ...]
    selected_b_source_node_id: str
    currentness_status: Literal["not_established"] = "not_established"
    authority_purpose: Literal["cycle_input_candidate_only"] = "cycle_input_candidate_only"

    @property
    def historical_selection(self) -> NativeDerivedWorldSelection:
        """Return the complete historical Native owner replay."""
        return self.historical_native_world_selection


@dataclass(frozen=True, slots=True)
class NativeModelInputUseWorldSelection:
    """Historical replay of the new action's Native world-use checkpoint."""

    checkpoint_ref: artifacts.ArtifactRef
    checkpoint: NativeModelInputUseWorldCheckpointV1
    source_selection: NativeModelInputUseSourceSelection
    phase: ModelInputUseActionPhase
    successor_selection: ModelInputSuccessorSelection
    context: CycleSubstrateContext
    currentness_status: Literal["not_established"] = "not_established"


@dataclass(frozen=True)
class NativeSelectedProgramGraphLinkage:
    """Expose original configuration and separately replayed Native graph inputs."""

    handoff: GenericCycleNativeWorldContextHandoffV1
    compile_report_ref: artifacts.ArtifactRef
    registry_bundle_ref: artifacts.ArtifactRef
    registry_bundle_content: RegistryBundleContent
    compiled_singleton: bool

    @property
    def profile(self) -> GenericCycleSimulationProfileV1:
        """Return unchanged original configuration, never a projected artifact."""
        return self.handoff.profile

    @property
    def profile_ref(self) -> artifacts.ArtifactRef:
        """Return the exact original selected configuration view."""
        return self.handoff.profile_ref

    @property
    def context(self) -> CycleSubstrateContext:
        """Return the action-owned context, including its candidate limitations."""
        return self.handoff.context

    @property
    def context_job_ref(self) -> artifacts.ArtifactRef:
        """Return the actual acquisition-job context selector."""
        return self.handoff.context_job_ref

    @property
    def native_world_checkpoint_ref(self) -> artifacts.ArtifactRef:
        """Return the selected checkpoint independently replayed by this owner."""
        return self.handoff.native_world_checkpoint_ref

    @property
    def original_generic_input_ref(self) -> artifacts.ArtifactRef:
        """Return the genuine blocked Generic input from the original cycle."""
        return self.handoff.original_generic_input_ref

    @property
    def current_profile_selection_ref(self) -> str:
        """Return the current problem key independently of original configuration."""
        return self.handoff.current_profile_selection_ref


def _error(code: str) -> Exception:
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextOwnerError

    return CycleSubstrateContextOwnerError(code)


def _same_ref(left: artifacts.ArtifactRef, right: artifacts.ArtifactRef) -> bool:
    return artifacts.artifact_ref_identity_key(left) == artifacts.artifact_ref_identity_key(right)


def bind_native_world_history(
    owner: GenericCycleSimulationAdmissionOwner, *, control_store: object, event_log: object
) -> None:
    """Bind the existing immutable action-history backend, without current rights."""
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog

    if (
        type(event_log) is not RuntimeDiagnosticEventLog
        or event_log.artifact_store is not owner.store
        or event_log._store is not control_store
        or not callable(getattr(control_store, "get_acquisition_action_head_by_receipt", None))
    ):
        raise _error("generic_native_world_history_owner_mismatch")
    if owner._native_action_control_store is not None and (
        owner._native_action_control_store is not control_store
        or owner._native_action_event_log is not event_log
    ):
        raise _error("generic_native_world_history_owner_already_bound")
    owner._native_action_control_store = control_store
    owner._native_action_event_log = event_log


def bind_native_world_action_owner(
    owner: GenericCycleSimulationAdmissionOwner, service: object
) -> None:
    """Bind the actual Runtime Control owner, never a caller-supplied permission."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService

    if (
        type(service) is not ControlPlaneService
        or service._artifact_store is not owner.store
        or service._generic_cycle_simulation_admission_owner is not owner
    ):
        raise _error("generic_native_world_action_owner_mismatch")
    if (
        owner._native_world_action_owner is not None
        and owner._native_world_action_owner is not service
    ):
        raise _error("generic_native_world_action_owner_already_bound")
    bind_native_world_history(
        owner, control_store=service._control_store, event_log=service._diagnostic_event_log
    )
    owner._native_world_action_owner = service


def _recorded_selection(
    owner: GenericCycleSimulationAdmissionOwner, checkpoint_ref: artifacts.ArtifactRef
) -> NativeDerivedWorldSelection:
    from polisyos.runtime.quality.acquisition_world_growth import (
        replay_native_derived_world_selection,
    )

    if owner._native_action_control_store is None or owner._native_action_event_log is None:
        raise _error("generic_native_world_history_owner_unavailable")
    return replay_native_derived_world_selection(
        owner.store,
        control_store=owner._native_action_control_store,
        event_log=owner._native_action_event_log,
        checkpoint_ref=checkpoint_ref,
    )


def _current_bridge(owner: GenericCycleSimulationAdmissionOwner) -> AcquisitionWorldGrowthBridge:
    from polisyos.runtime.http.services.acquisition_action_service import AcquisitionActionService
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge

    service = owner._native_world_action_owner
    if (
        type(service) is not ControlPlaneService
        or service._generic_cycle_simulation_admission_owner is not owner
        or service._artifact_store is not owner.store
    ):
        raise _error("generic_native_world_action_owner_unavailable")
    action = getattr(service._acquisition_job_handler, "__self__", None)
    if type(action) is not AcquisitionActionService or action.control_service is not service:
        raise _error("generic_native_world_action_handler_not_canonical")
    port = action._production_execution_port
    if type(port) is not WorldBankWDIAcquisitionExecutionPort or action._execution_port is not port:
        raise _error("generic_native_world_execution_port_not_canonical")
    bridge = port._world_growth_bridge
    if (
        type(bridge) is not AcquisitionWorldGrowthBridge
        or bridge._source_control_service is not service
        or bridge.artifact_store is not owner.store
        or bridge.control_store is not service._control_store
        or bridge.event_log is not service._diagnostic_event_log
        or bridge.action_head_sink is not service.acquisition_route_sink
    ):
        raise _error("generic_native_world_bridge_owner_mismatch")
    return bridge


def _current_selection(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    checkpoint_ref: artifacts.ArtifactRef,
    problem: DesignProblem,
    expected_bridge: AcquisitionWorldGrowthBridge | None = None,
    expected_closure: VerifiedAcquisitionRouteClosure | None = None,
) -> NativeDerivedWorldSelection:
    bridge = _current_bridge(owner)
    if expected_bridge is not None and bridge is not expected_bridge:
        raise _error("generic_native_world_bridge_owner_mismatch")
    return bridge.resolve_native_derived_world_selection(
        checkpoint_ref,
        problem=problem,
        expected_closure=expected_closure,
    )


def _context(
    selection: NativeDerivedWorldSelection, problem: DesignProblem
) -> CycleSubstrateContext:
    from polisyos.runtime.quality.cycle_substrate import (
        build_cycle_substrate_context,
        cycle_job_design_problem_ref,
        revalidate_cycle_substrate_context,
    )

    if selection.problem.model_dump(mode="python") != problem.model_dump(mode="python"):
        raise _error("generic_native_world_source_problem_mismatch")
    inputs = selection.original_profile.context_inputs
    if inputs.candidate_levers or inputs.transport_context is not None:
        raise _error("generic_native_world_context_evidence_reissue_required")
    context = build_cycle_substrate_context(
        design_problem_ref=cycle_job_design_problem_ref(problem),
        domain=problem.domain,
        substrate_registry=inputs.substrate_registry,
        selected_registry_entry_hashes=inputs.selected_registry_entry_hashes,
        world_model_record=selection.world_model_record,
        intervention_substrate=inputs.intervention_substrate,
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=inputs.source_pack_content_hash,
        substrate_input_content_hash=inputs.substrate_input_content_hash,
        additional_authority_denials=("native_derived_model_input_candidate_only",),
    )
    return revalidate_cycle_substrate_context(context)


def _fresh_native_model_input_use_worker(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    expected_worker: object | None = None,
) -> tuple[
    AcquisitionActionService, VerifiedModelInputUseWorker, ControlJobRecord, dict[str, object]
]:
    """Reopen the exact current Native worker, payload, and signed lease."""
    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionActionService,
        VerifiedModelInputUseWorker,
    )
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_plane_store import ControlJobRecord
    from polisyos.runtime.http.services.model_input_successor_action import (
        SelectedNativeModelInputSuccessorAction,
    )

    service = owner._native_world_action_owner
    if (
        type(service) is not ControlPlaneService
        or service._generic_cycle_simulation_admission_owner is not owner
        or service._artifact_store is not owner.store
    ):
        raise _error("generic_native_model_input_use_action_owner_unavailable")
    action = getattr(service._acquisition_job_handler, "__self__", None)
    if type(action) is not AcquisitionActionService or action.control_service is not service:
        raise _error("generic_native_model_input_use_action_handler_not_canonical")
    port = action._production_execution_port
    if type(port) is not WorldBankWDIAcquisitionExecutionPort or action._execution_port is not port:
        raise _error("generic_native_model_input_use_execution_port_not_canonical")
    bridge = _current_bridge(owner)
    if port._world_growth_bridge is not bridge:
        raise _error("generic_native_model_input_use_bridge_owner_mismatch")

    control_store = service._control_store
    admission = control_store.current_execution_job_admission()
    job = control_store.current_execution_job_record()
    if (
        type(job) is not ControlJobRecord
        or not admission.matches_job_record(job)
        or job.payload_ref is None
        or job.run_id is None
    ):
        raise _error("generic_native_model_input_use_running_lease_not_established")
    payload = service._load_payload_ref(
        job.payload_ref, kind="runtime.control_job_payload.acquisition"
    )
    if type(payload) is not dict:
        raise _error("generic_native_model_input_use_job_payload_invalid")
    if payload.get("job_id", job.job_id) != job.job_id:
        raise _error("generic_native_model_input_use_job_payload_identity_mismatch")
    payload = {**payload, "job_id": job.job_id}
    try:
        worker = action._require_model_input_use_worker(
            job,
            payload,
            admission.scope,
            effect_handler=action._model_input_use_effect_requires_worker,
            native_use=True,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise _error("generic_native_model_input_use_live_worker_not_established") from exc
    if (
        type(worker) is not VerifiedModelInputUseWorker
        or type(worker.selection) is not SelectedNativeModelInputSuccessorAction
        or not worker.admission.same_execution_identity(admission)
        or not control_store.current_execution_job_admission().same_execution_identity(admission)
    ):
        raise _error("generic_native_model_input_use_live_worker_changed")
    if expected_worker is not None and (
            type(expected_worker) is not VerifiedModelInputUseWorker
            or type(expected_worker.selection) is not SelectedNativeModelInputSuccessorAction
            or not expected_worker.admission.same_execution_identity(worker.admission)
            or expected_worker.selection != worker.selection
            or expected_worker.decision.durable_event_id != worker.decision.durable_event_id
            or expected_worker.decision.decision != worker.decision.decision
    ):
        raise _error("generic_native_model_input_use_worker_binding_mismatch")
    return action, worker, job, payload


def _reopen_native_source_row(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    overlay: object,
    occurrence: object,
    source_node_id: str,
    receipt_ref: artifacts.ArtifactRef,
    passport_ref: artifacts.ArtifactRef,
    occurrence_ref: artifacts.ArtifactRef,
) -> NativeModelInputUseWorldSourceRowV1:
    """Reconcile one retained occurrence with its exact currently active row."""
    from polisyos.core.contracts import epoch as epoch_contract
    from polisyos.core.contracts.variable_binding import ScopedMeasurementOccurrence
    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
    from polisyos.runtime.quality.generic_simulation_admission import (
        NativeModelInputUseWorldSourceRowV1,
    )

    if type(occurrence) is not ScopedMeasurementOccurrence:
        raise _error("generic_native_model_input_use_source_occurrence_untyped")
    passport = AdmissionPassport.model_validate(
        epoch_contract.load_verified_epoch_statement(
            store=bridge.artifact_store,
            ref=passport_ref,
            expected_kind="epoch.acquisition_passport_snapshot",
        )
    )
    if passport.field_binding.canonical_unit != occurrence.canonical_unit:
        raise _error("generic_native_model_input_use_source_unit_mismatch")
    try:
        projection = overlay.read_activated_semantic_epoch_observations(
            receipt_ref=receipt_ref,
            artifact_store=bridge.artifact_store,
            passport=passport,
            authority=bridge.authority,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise _error("generic_native_model_input_use_source_activation_not_current") from exc
    matches = tuple(
        row
        for row in projection.observations
        if row.observation.observation_id == occurrence.observation_id
    )
    if len(matches) != 1:
        raise _error("generic_native_model_input_use_source_row_not_current")
    active = matches[0]
    observation = active.observation
    expected_transform = (
        None
        if occurrence.unit_transform_evidence is None
        else occurrence.unit_transform_evidence.model_dump(mode="json")
    )
    actual_transform = (
        None
        if observation.unit_transform_evidence is None
        else observation.unit_transform_evidence.model_dump(mode="json")
    )
    try:
        same_numeric_value = Decimal(str(observation.value)) == Decimal(occurrence.canonical_value)
    except ArithmeticError as exc:
        raise _error("generic_native_model_input_use_source_value_invalid") from exc
    if (
        not _same_ref(projection.receipt_ref, receipt_ref)
        or not _same_ref(projection.passport_ref, passport_ref)
        or projection.variable_id != passport.variable_id
        or observation.canonical_var != occurrence.canonical_variable
        or observation.dataset_id != occurrence.dataset_id
        or observation.dataset_version != occurrence.dataset_version
        or observation.raw_variable != occurrence.raw_variable
        or observation.country_code != occurrence.country_code
        or observation.year != occurrence.year
        or observation.survey_year != occurrence.survey_year
        or observation.wave != occurrence.wave
        or observation.condition_json != occurrence.condition_json
        or observation.acquisition_method != occurrence.acquisition_method
        or observation.source_watermark != occurrence.source_watermark
        or observation.observation_class != occurrence.observation_class
        or active.row_content_sha256 != occurrence.observation_content_sha256
        or not same_numeric_value
        or actual_transform != expected_transform
    ):
        raise _error("generic_native_model_input_use_source_row_changed")
    return NativeModelInputUseWorldSourceRowV1(
        source_node_id=source_node_id,
        occurrence_ref=artifacts.ArtifactRef.model_validate(
            occurrence_ref.model_dump(mode="python")
        ),
        source_receipt_ref=receipt_ref,
        source_passport_ref=passport_ref,
        observation_id=occurrence.observation_id,
        observation_content_sha256=occurrence.observation_content_sha256,
        canonical_value=occurrence.canonical_value,
        canonical_unit=occurrence.canonical_unit,
    )


def preflight_native_model_input_use_source_selection(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    request: NativeModelInputSuccessorActionRequest,
) -> tuple[SelectedNativeModelInputSuccessorAction, NativeModelInputUseSourceSelection]:
    """Reopen canonical Native B before and after verifying the retained A+B inputs.

    These rows are candidate-only. The read does not authorize protected work.
    """
    from polisyos.runtime.http.services.acquisition_action_service import AcquisitionActionService
    from polisyos.runtime.http.services.model_input_successor_action import (
        NativeModelInputSuccessorActionRequest,
        SelectedNativeModelInputSuccessorAction,
    )

    if type(request) is not NativeModelInputSuccessorActionRequest:
        raise _error("generic_native_model_input_use_source_selection_untyped")
    bridge = _current_bridge(owner)
    service = owner._native_world_action_owner
    action = getattr(service._acquisition_job_handler, "__self__", None)
    if (
        type(action) is not AcquisitionActionService
        or action.control_service is not service
        or action._production_execution_port._world_growth_bridge is not bridge
    ):
        raise _error("generic_native_model_input_use_source_action_owner_mismatch")

    def select_b() -> SelectedNativeModelInputSuccessorAction:
        actual = action._resolve_native_model_input_use(
            tenant_id=tenant_id, cell_id=cell_id, run_id=run_id, request=request
        )
        if type(actual) is not SelectedNativeModelInputSuccessorAction:
            raise _error("generic_native_model_input_use_source_selection_untyped")
        return actual

    selection = select_b()
    source = _read_native_model_input_use_source_selection(
        owner, bridge=bridge, selected_b=selection, problem=selection.origin.design_problem_basis
    )
    try:
        current = select_b()
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise _error("generic_native_model_input_use_current_b_not_reselected") from exc
    if (
        _current_bridge(owner) is not bridge
        or current.catalog_source is not selection.catalog_source
        or current.catalog_authority is not selection.catalog_authority
        or current.request != selection.request
        or current.origin != selection.origin
        or current.job_id != selection.job_id
        or current.route_id != selection.route_id
        or current.passport_ref != selection.passport_ref
        or current.passport != selection.passport
        or current.observation_content_sha256 != selection.observation_content_sha256
        or not _same_ref(current.growth_receipt_ref, selection.growth_receipt_ref)
        or current.fresh_budget_usd != selection.fresh_budget_usd
    ):
        raise _error("generic_native_model_input_use_current_b_changed")
    return selection, source


def _read_native_model_input_use_source_selection(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    bridge: AcquisitionWorldGrowthBridge,
    selected_b: SelectedNativeModelInputSuccessorAction,
    problem: DesignProblem,
) -> NativeModelInputUseSourceSelection:
    """Verify exact input history and active source rows between live owner checks."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.data_forge import read_api as data_forge_read_api
    from polisyos.data_forge.read_api.catalog import CatalogAcquisitionOverlay
    from polisyos.runtime.http.services.model_input_successor_action import (
        NativeModelInputSuccessorActionRequest,
    )
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoopReceipt
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthReceipt,
        replay_native_derivation_input_collection,
    )
    from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref

    request = selected_b.request
    if (
        type(request) is not NativeModelInputSuccessorActionRequest
        or selected_b.origin.design_problem_basis.model_dump(mode="python")
        != problem.model_dump(mode="python")
        or selected_b.fresh_budget_usd != request.native_use.fresh_budget_usd
        or not _same_ref(selected_b.origin.compiled_ref, request.compiled_ref)
        or not _same_ref(selected_b.origin.n5_execution_ref, request.blocked_execution_ref)
        or not _same_ref(selected_b.origin.routing_report_ref, request.routing_report_ref)
    ):
        raise _error("generic_native_model_input_use_source_problem_mismatch")
    history = _recorded_selection(owner, request.native_use.world_checkpoint_ref)
    checkpoint = history.checkpoint
    if (
        history.problem.model_dump(mode="python") != problem.model_dump(mode="python")
        or checkpoint.source_job_id != selected_b.origin.source_job_id
        or history.pending_action_phase.compiled_ref
        != str(selected_b.origin.compiled_ref.artifact_id)
    ):
        raise _error("generic_native_model_input_use_historical_scope_mismatch")

    terminal_ref = request.native_use.predecessor_terminal_ref
    terminal = AcquisitionRouteLoopReceipt.model_validate(
        load_core_json_artifact(owner.store, terminal_ref)
    )
    terminal_report = reconcile_authority_ref(
        artifact_store=owner.store,
        event_log=owner._native_action_event_log,
        cas_ref=terminal_ref,
        expected_tenant_id=terminal.tenant_id,
        expected_cell_id=terminal.cell_id,
        expected_run_id=terminal.run_id,
        expected_job_id=terminal.job_id,
    )
    if (
        terminal_report.durable_event_id is None
        or terminal.schema_version != "AcquisitionRouteLoopReceipt@1.2"
        or terminal.terminal_outcome != "reentry_completed"
        or (terminal.tenant_id, terminal.cell_id, terminal.run_id, terminal.source_job_id)
        != (
            checkpoint.tenant_id,
            checkpoint.cell_id,
            checkpoint.run_id,
            checkpoint.source_job_id,
        )
        or terminal.job_id != checkpoint.action_job_id
        or terminal.route_id != checkpoint.route_id
        or str(selected_b.growth_receipt_ref.artifact_id) not in terminal.owner_receipt_refs
        or terminal.compiled_ref != history.pending_action_phase.compiled_ref
        or not _same_ref(history.original_generic_execution_ref, request.blocked_execution_ref)
    ):
        raise _error("generic_native_model_input_use_predecessor_terminal_mismatch")

    growth = AcquisitionWorldGrowthReceipt.model_validate(
        bridge._read(
            selected_b.growth_receipt_ref, "runtime_quality.acquisition_world_growth_receipt"
        )
    )
    if (
        growth.activation.overlay_admission_receipt_ref != request.activation_receipt_ref
        or growth.activation.passport_ref != selected_b.passport_ref
        or growth.selection.key
        != (
            selected_b.origin.tenant_id,
            selected_b.origin.cell_id,
            selected_b.origin.run_id,
            terminal.route_id,
        )
    ):
        raise _error("generic_native_model_input_use_paid_growth_mismatch")

    collection_refs = checkpoint.collection_refs
    if len(collection_refs) != 1:
        raise _error("generic_native_model_input_use_native_collection_not_unique")
    collection_ref = collection_refs[0]
    replay = replay_native_derivation_input_collection(owner.store, collection_ref)
    collection = replay.collection
    if (
        collection.input_closure_status != "inputs_complete"
        or replay.source_value_replay != "recomputed"
        or replay.replayed_source_node_ids != collection.source_node_ids
        or not collection.source_inputs
    ):
        raise _error("generic_native_model_input_use_source_denominator_incomplete")

    overlay_path, _ = bridge._paths(growth.selection, create=False)
    overlay = CatalogAcquisitionOverlay(bridge.authority.baseline_path, overlay_path)
    source_rows: list[NativeModelInputUseWorldSourceRowV1] = []
    selected_nodes: list[str] = []
    try:
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            for row in collection.source_inputs:
                stored, replayed, _source_selection = (
                    data_forge_read_api.catalog.replay_selected_scoped_measurement_facts(
                        owner.store, row.occurrence_ref
                    )
                )
                if (
                    stored != replayed
                    or not _same_ref(stored.source_receipt_ref, row.source_receipt_ref)
                    or not _same_ref(stored.source_passport_ref, row.source_passport_ref)
                ):
                    raise _error("generic_native_model_input_use_source_replay_mismatch")
                source_row = _reopen_native_source_row(
                    bridge=bridge,
                    overlay=overlay,
                    occurrence=stored,
                    source_node_id=row.source_node_id,
                    receipt_ref=row.source_receipt_ref,
                    passport_ref=row.source_passport_ref,
                    occurrence_ref=row.occurrence_ref,
                )
                source_rows.append(source_row)
                if (
                    _same_ref(row.source_receipt_ref, request.activation_receipt_ref)
                    and _same_ref(row.source_passport_ref, selected_b.passport_ref)
                    and stored.observation_id == request.observation_id
                    and stored.observation_content_sha256
                    == selected_b.observation_content_sha256
                ):
                    selected_nodes.append(row.source_node_id)
    finally:
        overlay.close()
    if len(selected_nodes) != 1 or tuple(
        row.source_node_id for row in source_rows
    ) != tuple(sorted(collection.source_node_ids)):
        raise _error("generic_native_model_input_use_selected_b_not_unique")
    return NativeModelInputUseSourceSelection(
        predecessor_terminal_ref=terminal_ref,
        historical_native_world_selection=history,
        input_collection_ref=collection_ref,
        input_collection_replay=replay,
        source_rows=tuple(source_rows),
        selected_b_source_node_id=selected_nodes[0],
    )


def resolve_native_model_input_use_source_selection(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    worker: object,
    problem: DesignProblem,
) -> NativeModelInputUseSourceSelection:
    """Reuse the read-only source preflight under a freshly verified lease."""
    source, _, _, _ = _read_current_native_model_input_use_sources(
        owner, expected_worker=worker, problem=problem
    )
    return source


def _read_current_native_model_input_use_sources(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    problem: DesignProblem,
    expected_worker: object | None = None,
) -> tuple[
    NativeModelInputUseSourceSelection,
    VerifiedModelInputUseWorker,
    ControlJobRecord,
    dict[str, object],
]:
    """Read current source and worker together for the caller's immediate stage verification."""
    action, current_worker, _, _ = _fresh_native_model_input_use_worker(
        owner, expected_worker=expected_worker
    )
    bridge = _current_bridge(owner)
    source = _read_native_model_input_use_source_selection(
        owner, bridge=bridge, selected_b=current_worker.selection, problem=problem
    )
    action_after, worker_after, _, payload = _fresh_native_model_input_use_worker(
        owner, expected_worker=current_worker
    )
    if action_after is not action or _current_bridge(owner) is not bridge:
        raise _error("generic_native_model_input_use_source_action_owner_mismatch")
    # The expensive owner reopen starts from a lease record and may outlast a
    # progress update. Read current progress from the final admitted lease.
    admission = action.control_service._control_store.current_execution_job_admission()
    if not admission.same_execution_identity(worker_after.admission):
        raise _error("generic_native_model_input_use_live_worker_changed")
    return source, worker_after, admission.job, payload


def _read_model_input_use_stage(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    worker: object,
    job: object,
    payload: dict[str, object],
    history: NativeDerivedWorldSelection,
    expected_world_checkpoint: NativeModelInputUseWorldCheckpointV1 | None = None,
) -> tuple[ModelInputUseActionPhase, ModelInputSuccessorSelection]:
    """Reopen the current phase and B selector, preserving any sealed selection."""
    from polisyos.core.artifacts import artifact_ref_for_manifest
    from polisyos.runtime.http.services.acquisition_action_service import (
        VerifiedModelInputUseWorker,
    )
    from polisyos.runtime.http.services.control_plane_store import ControlJobRecord
    from polisyos.runtime.http.services.model_input_successor_action import (
        ModelInputSuccessorActionError,
        ModelInputUseActionCheckpoint,
        _resolve_action_budget_window,
        unwrap_native_model_input_use_request,
    )
    from polisyos.runtime.quality.model_input_successor_selection import (
        read_model_input_successor_selection,
        read_model_input_use_action_phase,
    )

    if (
        type(worker) is not VerifiedModelInputUseWorker
        or type(job) is not ControlJobRecord
        or type(job.progress) is not dict
        or job.payload_ref is None
    ):
        raise _error("generic_native_model_input_use_stage_owner_invalid")
    raw_checkpoint = job.progress.get("model_input_use")
    if type(raw_checkpoint) is not dict:
        raise _error("generic_native_model_input_use_stage_not_selected")
    try:
        stage = ModelInputUseActionCheckpoint.model_validate(raw_checkpoint)
        if expected_world_checkpoint is not None and (
            not _same_ref(stage.phase_ref, expected_world_checkpoint.model_input_use_phase_ref)
            or not _same_ref(
                stage.semantic_successor_ref,
                expected_world_checkpoint.model_input_successor_selection_ref,
            )
        ):
            raise ValueError("generic_native_model_input_use_stage_selected_view_changed")
        phase = read_model_input_use_action_phase(owner.store, stage.phase_ref)
        selection = read_model_input_successor_selection(owner.store, stage.semantic_successor_ref)
        request = unwrap_native_model_input_use_request(payload, phase=phase)
        service = owner._native_world_action_owner
        budget_window = _resolve_action_budget_window(
            service,
            selection=worker.selection,
            phase_ref=stage.phase_ref,
            open_if_missing=False,
        )
    except (ModelInputSuccessorActionError, TypeError, ValueError) as exc:
        raise _error("generic_native_model_input_use_stage_not_replayed") from exc
    selection_manifest = owner.store.get_manifest(stage.semantic_successor_ref)
    payload_selector = artifact_ref_for_manifest(owner.store.get_manifest(job.payload_ref))
    if (
        stage.schema_version is not None
        or any(
            value is not None
            for value in (
                stage.execution_ref,
                stage.result_ref,
                stage.evaluation_decision_ref,
                stage.evaluation_current_basis_ref,
                stage.evaluation_replacement_basis_ref,
                stage.evaluation_expected_frontier_revision,
                stage.evaluation_expected_frontier_ref,
            )
        )
        or payload_selector != phase.action_payload_ref
        or phase.authority_decision_ref != selection.authority_decision_ref
        or (phase.action_job_id, phase.run_id, phase.tenant_id, phase.cell_id)
        != (
            job.job_id,
            job.run_id,
            worker.selection.tenant_id,
            worker.selection.cell_id,
        )
        or phase.action_job_id == phase.source_job_id
        or phase.route_id != worker.selection.route_id
        or selection.schema_version != "polisyos.runtime.ModelInputSuccessorSelection@1.0"
        or selection.routing_use_decision_ref is not None
        or selection.action_phase_ref != stage.phase_ref
        or selection.authority_decision_ref != phase.authority_decision_ref
        or selection.action_job_id != job.job_id
        or selection.action_worker_id != job.lease_owner
        or selection.action_attempt != job.attempt
        or selection.reentry_budget_window_id != budget_window.window_id
        or selection.reentry_budget_window_digest != budget_window.record_digest
        or (
            selection.tenant_id,
            selection.cell_id,
            selection.run_id,
            selection.source_job_id,
        )
        != (phase.tenant_id, phase.cell_id, phase.run_id, phase.source_job_id)
        or selection.route_id != phase.route_id
        or selection.compiled_ref != worker.selection.origin.compiled_ref
        or selection.blocked_execution_ref != worker.selection.request.blocked_execution_ref
        or selection.routing_report_ref != worker.selection.request.routing_report_ref
        or selection.activation_receipt_ref != worker.selection.request.activation_receipt_ref
        or selection.observation_id != worker.selection.request.observation_id
        or selection.observation_content_sha256 != worker.selection.observation_content_sha256
        or not _same_ref(
            selection.semantic_foundry_input_bindings_ref, history.checkpoint.input_bindings_ref
        )
        or request != worker.selection.request
        or selection_manifest.artifact_schema is None
        or selection_manifest.artifact_schema.version != "1.0"
    ):
        raise _error("generic_native_model_input_use_stage_binding_mismatch")
    return phase, selection


def _use_checkpoint_event_id(checkpoint: NativeModelInputUseWorldCheckpointV1) -> str:
    """Derive one deterministic event identity from the exact typed checkpoint."""
    import hashlib

    payload = canon.to_canonical_bytes(
        checkpoint.model_dump(mode="json"), canon.CanonSpec(forbid_floats=False)
    )
    return "evt_native_model_input_use_world_" + hashlib.sha256(payload).hexdigest()


def _persist_use_checkpoint(
    owner: GenericCycleSimulationAdmissionOwner,
    checkpoint: NativeModelInputUseWorldCheckpointV1,
) -> artifacts.ArtifactRef:
    """Persist one typed candidate-use selection with its exact authority event."""
    import hashlib
    from datetime import UTC, datetime

    from polisyos.runtime.quality.agent_action_authority import write_runtime_authority_artifact
    from polisyos.runtime.quality.authority import GovernanceMetadata

    if owner._native_action_event_log is None:
        raise _error("generic_native_model_input_use_event_owner_unavailable")
    spec = canon.CanonSpec(forbid_floats=False)
    payload = checkpoint.model_dump(mode="json")
    encoded = canon.to_canonical_bytes(payload, spec)
    identity = hashlib.sha256(encoded).hexdigest()
    input_refs = checkpoint.lineage_inputs()
    evidence_refs = tuple(sorted({str(item.artifact_id) for item in input_refs}))
    generated_at = datetime.now(UTC).isoformat()
    options = artifacts.ArtifactWriteOptions(
        kind=checkpoint.ARTIFACT_KIND,
        media_type=checkpoint.ARTIFACT_MEDIA_TYPE,
        schema=artifacts.SchemaInfo(
            name=checkpoint.ARTIFACT_SCHEMA_NAME,
            version=checkpoint.ARTIFACT_SCHEMA_VERSION,
        ),
        producer=artifacts.ProducerInfo(
            component="polisyos.runtime.quality.native_generic_context", version="1.0"
        ),
        governance=artifacts.ArtifactGovernanceInfo(classification="internal"),
        inputs=list(input_refs),
    )
    try:
        result = write_runtime_authority_artifact(
            owner.store,
            owner._native_action_event_log,
            payload,
            options,
            evidence_id=identity,
            evidence_class="authority_bearing",
            authority_role="producer_authority",
            provenance_kind="runtime_emitted",
            owner="team-runtime-quality",
            reader_contract=checkpoint.ARTIFACT_KIND + ".reader",
            reader_contract_version=checkpoint.ARTIFACT_SCHEMA_VERSION,
            tenant_id=checkpoint.tenant_id,
            cell_id=checkpoint.cell_id,
            run_id=checkpoint.run_id,
            job_id=checkpoint.action_job_id,
            trace_id="trace-" + checkpoint.action_job_id,
            span_id="span-model-input-use-world-selection",
            parent_span_id=None,
            requested_execution_profile="governed",
            effective_execution_profile="governed",
            phase="model_input_use_world_selection",
            generated_at=generated_at,
            as_of_time=generated_at,
            same_input_closure={
                "closure_id": identity,
                "status": "closed",
                "run_id": checkpoint.run_id,
                "job_id": checkpoint.action_job_id,
                "tenant_id": checkpoint.tenant_id,
                "cell_id": checkpoint.cell_id,
                "evidence_input_refs": evidence_refs,
                "closure_sha256": checkpoint.route_id,
            },
            input_refs=evidence_refs,
            effective_mode_ref=checkpoint.route_id,
            semantic_binding_ref=checkpoint.current_profile_selection_ref,
            validation_status="pass",
            blocking_status="non_blocking",
            governance=GovernanceMetadata(
                classification="internal",
                authority_boundary=checkpoint.ARTIFACT_KIND,
                pii="none",
                retention_policy="runtime-quality-90d",
                review_status="runtime_verified",
                override_policy="no_override",
                approval_policy="candidate_only_no_source_or_n5_authority",
            ),
            event_id=_use_checkpoint_event_id(checkpoint),
            event_source="polisyos.runtime.quality.native_generic_context",
            event_type="polisyos.runtime.native.model_input_use_world_checkpoint.v1",
            event_subject=(
                "run/" + checkpoint.run_id + "/model-input-use/" + checkpoint.action_job_id
            ),
            state_before=None,
            state_after="cycle_input_candidate_only",
            canon_spec=spec,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise _error("generic_native_model_input_use_checkpoint_write_failed") from exc
    selected_ref = result.cas_ref
    if (
        type(selected_ref) is not artifacts.ArtifactRef
        or selected_ref.manifest_profile_sha256 is None
        or selected_ref.kind != checkpoint.ARTIFACT_KIND
        or selected_ref.media_type != checkpoint.ARTIFACT_MEDIA_TYPE
    ):
        raise _error("generic_native_model_input_use_checkpoint_profile_missing")
    return selected_ref


def _read_verified_native_model_input_use_checkpoint(
    owner: GenericCycleSimulationAdmissionOwner,
    checkpoint_ref: artifacts.ArtifactRef,
) -> NativeModelInputUseWorldCheckpointV1:
    """Reopen the selected checkpoint profile, lineage, and durable producer event."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
    from polisyos.runtime.quality.generic_simulation_admission import (
        NativeModelInputUseWorldCheckpointV1,
    )

    event_log = owner._native_action_event_log
    if event_log is None:
        raise ValueError("generic_native_model_input_use_checkpoint_unselected")
    checkpoint = NativeModelInputUseWorldCheckpointV1.model_validate(
        load_core_json_artifact(owner.store, checkpoint_ref)
    )
    AcquisitionWorldGrowthBridge.read_verified_artifact(
        owner.store,
        event_log,
        checkpoint_ref,
        checkpoint_ref.kind,
        expected_inputs=checkpoint.lineage_inputs(),
    )
    report = reconcile_authority_ref(
        artifact_store=owner.store,
        event_log=event_log,
        cas_ref=checkpoint_ref,
        expected_tenant_id=checkpoint.tenant_id,
        expected_cell_id=checkpoint.cell_id,
        expected_run_id=checkpoint.run_id,
        expected_job_id=checkpoint.action_job_id,
    )
    if report.durable_event_id != _use_checkpoint_event_id(checkpoint):
        raise ValueError("generic_native_model_input_use_checkpoint_event_mismatch")
    return checkpoint


def replay_native_model_input_use_world_selection(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    checkpoint_ref: artifacts.ArtifactRef,
) -> NativeModelInputUseWorldSelection:
    """Replay the selected current-use artifact and its historical Native basis."""
    from polisyos.core.artifacts import artifact_ref_for_manifest, load_core_json_artifact
    from polisyos.runtime.http.services.model_input_successor_action import (
        ModelInputUseActionCheckpoint,
        unwrap_native_model_input_use_request,
    )
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoopReceipt
    from polisyos.runtime.quality.acquisition_world_growth import (
        replay_native_derivation_input_collection,
    )
    from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner
    from polisyos.runtime.quality.generic_simulation_admission import (
        NativeModelInputUseWorldCheckpointV1,
    )
    from polisyos.runtime.quality.model_input_successor_selection import (
        read_model_input_successor_selection,
        read_model_input_use_action_phase,
    )

    if (
        type(checkpoint_ref) is not artifacts.ArtifactRef
        or checkpoint_ref.kind != NativeModelInputUseWorldCheckpointV1.ARTIFACT_KIND
        or checkpoint_ref.media_type != "application/json"
        or checkpoint_ref.manifest_profile_sha256 is None
        or owner._native_action_control_store is None
        or owner._native_action_event_log is None
    ):
        raise _error("generic_native_model_input_use_checkpoint_unselected")
    try:
        checkpoint = _read_verified_native_model_input_use_checkpoint(owner, checkpoint_ref)
        history = _recorded_selection(owner, checkpoint.historical_native_world_checkpoint_ref)
        terminal = AcquisitionRouteLoopReceipt.model_validate(
            load_core_json_artifact(owner.store, checkpoint.predecessor_terminal_ref)
        )
        terminal_report = reconcile_authority_ref(
            artifact_store=owner.store,
            event_log=owner._native_action_event_log,
            cas_ref=checkpoint.predecessor_terminal_ref,
            expected_tenant_id=checkpoint.tenant_id,
            expected_cell_id=checkpoint.cell_id,
            expected_run_id=checkpoint.run_id,
            expected_job_id=checkpoint.historical_native_action_job_id,
        )
        if (
            terminal_report.durable_event_id is None
            or terminal.schema_version != "AcquisitionRouteLoopReceipt@1.2"
            or terminal.terminal_outcome != "reentry_completed"
            or terminal.job_id != checkpoint.historical_native_action_job_id
            or terminal.route_id != history.checkpoint.route_id
            or terminal.source_job_id != checkpoint.source_job_id
            or terminal.compiled_ref != history.pending_action_phase.compiled_ref
            or checkpoint.source_job_id != history.checkpoint.source_job_id
            or not _same_ref(
                checkpoint.native_input_collection_ref, history.checkpoint.collection_refs[0]
            )
            or not _same_ref(
                checkpoint.native_input_bindings_ref, history.checkpoint.input_bindings_ref
            )
            or not _same_ref(
                checkpoint.original_generic_input_ref, history.original_generic_input_ref
            )
            or not _same_ref(checkpoint.original_profile_ref, history.original_profile_ref)
            or not _same_ref(checkpoint.world_model_ref, history.checkpoint.world_model_ref)
            or checkpoint.historical_native_action_job_id != history.checkpoint.action_job_id
            or (checkpoint.run_id, checkpoint.tenant_id, checkpoint.cell_id)
            != (terminal.run_id, terminal.tenant_id, terminal.cell_id)
            or checkpoint.action_job_id
            in {checkpoint.source_job_id, checkpoint.historical_native_action_job_id}
        ):
            raise ValueError("generic_native_model_input_use_checkpoint_history_mismatch")
        phase = read_model_input_use_action_phase(owner.store, checkpoint.model_input_use_phase_ref)
        selection = read_model_input_successor_selection(
            owner.store, checkpoint.model_input_successor_selection_ref
        )
        action_job = owner._native_action_control_store.get_job(checkpoint.action_job_id)
        if (
            action_job is None
            or action_job.kind != "acquisition"
            or action_job.run_id != checkpoint.run_id
            or action_job.payload_ref is None
        ):
            raise ValueError("generic_native_model_input_use_action_job_missing")
        action_progress = action_job.progress.get("model_input_use")
        if type(action_progress) is not dict:
            raise ValueError("generic_native_model_input_use_action_progress_missing")
        action_checkpoint = ModelInputUseActionCheckpoint.model_validate(action_progress)
        if (
            action_checkpoint.phase_ref != checkpoint.model_input_use_phase_ref
            or action_checkpoint.semantic_successor_ref
            != checkpoint.model_input_successor_selection_ref
        ):
            raise ValueError("generic_native_model_input_use_action_progress_changed")
        payload_selector = artifact_ref_for_manifest(
            owner.store.get_manifest(action_job.payload_ref)
        )
        payload = load_core_json_artifact(owner.store, payload_selector)
        request = unwrap_native_model_input_use_request(payload, phase=phase)
        selected_b_rows = tuple(
            row
            for row in checkpoint.source_rows
            if row.source_node_id == checkpoint.selected_b_source_node_id
        )
        if len(selected_b_rows) != 1:
            raise ValueError("generic_native_model_input_use_selected_b_not_unique")
        (selected_b_row,) = selected_b_rows
        from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref

        expected_profile_selection_ref = cycle_job_profile_selection_ref(history.problem)
        if (
            phase.action_payload_ref != payload_selector
            or phase.authority_decision_ref != selection.authority_decision_ref
            or (
                phase.action_job_id,
                phase.source_job_id,
                phase.run_id,
                phase.tenant_id,
                phase.cell_id,
            )
            != (
                checkpoint.action_job_id,
                checkpoint.source_job_id,
                checkpoint.run_id,
                checkpoint.tenant_id,
                checkpoint.cell_id,
            )
            or phase.route_id != checkpoint.route_id
            or selection.schema_version != "polisyos.runtime.ModelInputSuccessorSelection@1.0"
            or selection.routing_use_decision_ref is not None
            or selection.action_phase_ref != checkpoint.model_input_use_phase_ref
            or selection.action_job_id != checkpoint.action_job_id
            or (
                selection.tenant_id,
                selection.cell_id,
                selection.run_id,
                selection.source_job_id,
            )
            != (
                checkpoint.tenant_id,
                checkpoint.cell_id,
                checkpoint.run_id,
                checkpoint.source_job_id,
            )
            or selection.route_id != checkpoint.route_id
            or str(selection.compiled_ref.artifact_id) != history.pending_action_phase.compiled_ref
            or not _same_ref(
                selection.blocked_execution_ref, history.original_generic_execution_ref
            )
            or not _same_ref(selection.activation_receipt_ref, selected_b_row.source_receipt_ref)
            or selection.observation_id != selected_b_row.observation_id
            or selection.observation_content_sha256 != selected_b_row.observation_content_sha256
            or not _same_ref(
                selection.semantic_foundry_input_bindings_ref,
                checkpoint.native_input_bindings_ref,
            )
            or not _same_ref(
                request.native_use.predecessor_terminal_ref, checkpoint.predecessor_terminal_ref
            )
            or not _same_ref(
                request.native_use.world_checkpoint_ref,
                checkpoint.historical_native_world_checkpoint_ref,
            )
            or not _same_ref(request.activation_receipt_ref, selected_b_row.source_receipt_ref)
            or request.observation_id != selected_b_row.observation_id
            or checkpoint.current_profile_selection_ref != expected_profile_selection_ref
        ):
            raise ValueError("generic_native_model_input_use_checkpoint_selection_mismatch")
        context_record = CycleSubstrateContextArtifactOwner(
            store=owner.store
        ).resolve_historical_job_artifact(
            checkpoint.context_job_ref,
            problem=history.problem,
            expected_job_id=checkpoint.action_job_id,
            expected_run_id=checkpoint.run_id,
            expected_tenant_id=checkpoint.tenant_id,
            expected_cell_id=checkpoint.cell_id,
        )
        context = context_record.context
        if context != _context(history, history.problem):
            raise ValueError("generic_native_model_input_use_checkpoint_context_mismatch")
        replay = replay_native_derivation_input_collection(
            owner.store, checkpoint.native_input_collection_ref
        )
        collection = replay.collection
        if (
            collection.input_closure_status != "inputs_complete"
            or replay.source_value_replay != "recomputed"
            or replay.replayed_source_node_ids != collection.source_node_ids
            or tuple(row.source_node_id for row in checkpoint.source_rows)
            != collection.source_node_ids
            or len(checkpoint.source_rows) != len(collection.source_inputs)
        ):
            raise ValueError(
                "generic_native_model_input_use_checkpoint_source_denominator_mismatch"
            )
        from polisyos.data_forge import read_api as data_forge_read_api

        for selected_row, collected in zip(
            checkpoint.source_rows, collection.source_inputs, strict=True
        ):
            stored, replayed_occurrence, _source_selection = (
                data_forge_read_api.catalog.replay_selected_scoped_measurement_facts(
                    owner.store, collected.occurrence_ref
                )
            )
            if (
                stored != replayed_occurrence
                or selected_row.source_node_id != collected.source_node_id
                or not _same_ref(selected_row.occurrence_ref, collected.occurrence_ref)
                or not _same_ref(selected_row.source_receipt_ref, collected.source_receipt_ref)
                or not _same_ref(selected_row.source_passport_ref, collected.source_passport_ref)
                or stored.observation_id != selected_row.observation_id
                or stored.observation_content_sha256
                != selected_row.observation_content_sha256
                or stored.canonical_value != selected_row.canonical_value
                or stored.canonical_unit != selected_row.canonical_unit
            ):
                raise ValueError("generic_native_model_input_use_checkpoint_source_row_mismatch")
        source_selection = NativeModelInputUseSourceSelection(
            predecessor_terminal_ref=checkpoint.predecessor_terminal_ref,
            historical_native_world_selection=history,
            input_collection_ref=checkpoint.native_input_collection_ref,
            input_collection_replay=replay,
            source_rows=checkpoint.source_rows,
            selected_b_source_node_id=checkpoint.selected_b_source_node_id,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise _error("generic_native_model_input_use_checkpoint_history_not_replayed") from exc
    return NativeModelInputUseWorldSelection(
        checkpoint_ref=checkpoint_ref,
        checkpoint=checkpoint,
        source_selection=source_selection,
        phase=phase,
        successor_selection=selection,
        context=context,
    )


def _native_use_source_selections_match(
    left: NativeModelInputUseSourceSelection,
    right: NativeModelInputUseSourceSelection,
) -> bool:
    return (
        _same_ref(left.predecessor_terminal_ref, right.predecessor_terminal_ref)
        and _same_ref(
            left.historical_selection.checkpoint_ref, right.historical_selection.checkpoint_ref
        )
        and _same_ref(left.input_collection_ref, right.input_collection_ref)
        and left.input_collection_replay == right.input_collection_replay
        and left.source_rows == right.source_rows
        and left.selected_b_source_node_id == right.selected_b_source_node_id
    )


def _profile_selection_ref(problem: DesignProblem) -> str:
    from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref

    return cycle_job_profile_selection_ref(problem)


def _native_use_handoff(
    selection: NativeModelInputUseWorldSelection,
    *,
    context_job_ref: artifacts.ArtifactRef | None = None,
) -> GenericCycleNativeWorldContextHandoffV1:
    return _native_use_handoff_for_checkpoint(
        checkpoint=selection.checkpoint,
        checkpoint_ref=selection.checkpoint_ref,
        profile=selection.source_selection.historical_selection.original_profile,
        context=selection.context,
        context_job_ref=context_job_ref,
    )


def _native_use_handoff_for_checkpoint(
    *,
    checkpoint: NativeModelInputUseWorldCheckpointV1,
    checkpoint_ref: artifacts.ArtifactRef,
    profile: GenericCycleSimulationProfileV1,
    context: CycleSubstrateContext,
    context_job_ref: artifacts.ArtifactRef | None = None,
) -> GenericCycleNativeWorldContextHandoffV1:
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleNativeWorldContextHandoffV1,
    )

    return GenericCycleNativeWorldContextHandoffV1(
        context=context,
        context_job_ref=context_job_ref or checkpoint.context_job_ref,
        profile=profile,
        profile_ref=checkpoint.original_profile_ref,
        native_world_checkpoint_ref=checkpoint_ref,
        original_generic_input_ref=checkpoint.original_generic_input_ref,
        current_profile_selection_ref=checkpoint.current_profile_selection_ref,
        source_job_id=checkpoint.source_job_id,
        job_id=checkpoint.action_job_id,
        run_id=checkpoint.run_id,
        tenant_id=checkpoint.tenant_id,
        cell_id=checkpoint.cell_id,
    )


def admit_native_model_input_use_world_context(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    problem: DesignProblem,
    repo_root: Path | None,
) -> GenericCycleNativeWorldContextHandoffV1:
    """Persist the current candidate-only world selection under its real worker job."""
    from polisyos.runtime.http.services.model_input_successor_action import (
        ModelInputUseActionCheckpoint,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        NativeModelInputUseWorldCheckpointV1,
    )

    source, worker, job, payload = _read_current_native_model_input_use_sources(
        owner, problem=problem
    )
    historical = source.historical_selection
    phase, selector = _read_model_input_use_stage(
        owner, worker=worker, job=job, payload=payload, history=historical
    )
    context = _context(historical, problem)
    service = owner._native_world_action_owner
    context_owner = CycleSubstrateContextArtifactOwner(
        store=owner.store, control_store=service._control_store
    )
    context_ref = context_owner.persist_for_current_job(
        context,
        problem=problem,
        repo_root=repo_root,
        return_selected_profile=True,
    )
    context_owner.resolve_for_current_job(context_ref, problem=problem, repo_root=repo_root)

    source_after, worker_after, job_after, payload_after = (
        _read_current_native_model_input_use_sources(owner, problem=problem, expected_worker=worker)
    )
    phase_after, selector_after = _read_model_input_use_stage(
        owner,
        worker=worker_after,
        job=job_after,
        payload=payload_after,
        history=historical,
    )
    if (
        job_after.job_id != job.job_id
        or phase_after != phase
        or selector_after != selector
        or not _native_use_source_selections_match(source, source_after)
    ):
        raise _error("generic_native_model_input_use_source_changed_before_checkpoint")
    stage_after = ModelInputUseActionCheckpoint.model_validate(
        job_after.progress["model_input_use"]
    )
    checkpoint = NativeModelInputUseWorldCheckpointV1(
        predecessor_terminal_ref=source.predecessor_terminal_ref,
        historical_native_world_checkpoint_ref=historical.checkpoint_ref,
        historical_native_action_job_id=historical.checkpoint.action_job_id,
        native_input_collection_ref=source.input_collection_ref,
        native_input_bindings_ref=historical.checkpoint.input_bindings_ref,
        model_input_use_phase_ref=stage_after.phase_ref,
        model_input_successor_selection_ref=stage_after.semantic_successor_ref,
        context_job_ref=context_ref,
        original_generic_input_ref=historical.original_generic_input_ref,
        original_profile_ref=historical.original_profile_ref,
        world_model_ref=historical.checkpoint.world_model_ref,
        source_job_id=historical.checkpoint.source_job_id,
        action_job_id=job_after.job_id,
        run_id=worker_after.selection.run_id,
        tenant_id=worker_after.selection.tenant_id,
        cell_id=worker_after.selection.cell_id,
        route_id=worker_after.selection.route_id,
        current_profile_selection_ref=cycle_job_profile_selection_ref(problem),
        selected_b_source_node_id=source_after.selected_b_source_node_id,
        source_rows=source_after.source_rows,
    )
    checkpoint_ref = _persist_use_checkpoint(owner, checkpoint)
    expected_handoff = _native_use_handoff_for_checkpoint(
        checkpoint=checkpoint,
        checkpoint_ref=checkpoint_ref,
        profile=historical.original_profile,
        context=context,
    )
    return resolve_native_world_handoff(
        owner,
        handoff=expected_handoff,
        problem=problem,
        context_owner=context_owner,
        repo_root=repo_root,
    )


def _handoff_matches_selection(
    handoff: GenericCycleNativeWorldContextHandoffV1, selection: NativeDerivedWorldSelection
) -> bool:
    checkpoint = selection.checkpoint
    return (
        _same_ref(handoff.native_world_checkpoint_ref, selection.checkpoint_ref)
        and _same_ref(handoff.original_generic_input_ref, selection.original_generic_input_ref)
        and handoff.profile == selection.original_profile
        and _same_ref(handoff.profile_ref, selection.original_profile_ref)
        and (
            handoff.job_id,
            handoff.run_id,
            handoff.tenant_id,
            handoff.cell_id,
            handoff.source_job_id,
        )
        == (
            checkpoint.action_job_id,
            checkpoint.run_id,
            checkpoint.tenant_id,
            checkpoint.cell_id,
            checkpoint.source_job_id,
        )
    )


def _is_native_model_input_use_checkpoint(
    owner: GenericCycleSimulationAdmissionOwner, checkpoint_ref: artifacts.ArtifactRef
) -> bool:
    """Dispatch only the exact versioned use-world checkpoint schema."""
    from polisyos.runtime.quality.generic_simulation_admission import (
        NativeModelInputUseWorldCheckpointV1,
    )

    manifest = owner.store.get_manifest(checkpoint_ref)
    return (
        manifest.kind == NativeModelInputUseWorldCheckpointV1.ARTIFACT_KIND
        and manifest.artifact_schema
        == artifacts.SchemaInfo(
            name=NativeModelInputUseWorldCheckpointV1.ARTIFACT_SCHEMA_NAME,
            version=NativeModelInputUseWorldCheckpointV1.ARTIFACT_SCHEMA_VERSION,
        )
    )


def _use_handoff_matches_selection(
    handoff: GenericCycleNativeWorldContextHandoffV1,
    selection: NativeModelInputUseWorldSelection,
    problem: DesignProblem,
) -> bool:
    checkpoint = selection.checkpoint
    history = selection.source_selection.historical_selection
    return (
        _same_ref(handoff.native_world_checkpoint_ref, selection.checkpoint_ref)
        and _same_ref(handoff.original_generic_input_ref, checkpoint.original_generic_input_ref)
        and handoff.profile == history.original_profile
        and _same_ref(handoff.profile_ref, checkpoint.original_profile_ref)
        and handoff.context == _context(history, problem)
        and handoff.current_profile_selection_ref == _profile_selection_ref(problem)
        and (
            handoff.job_id,
            handoff.run_id,
            handoff.tenant_id,
            handoff.cell_id,
            handoff.source_job_id,
        )
        == (
            checkpoint.action_job_id,
            checkpoint.run_id,
            checkpoint.tenant_id,
            checkpoint.cell_id,
            checkpoint.source_job_id,
        )
    )


def _resolve_current_native_model_input_use_selection(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    handoff: GenericCycleNativeWorldContextHandoffV1,
    problem: DesignProblem,
    context_owner: CycleSubstrateContextArtifactOwner | None,
    repo_root: Path | None,
    expected_bridge: AcquisitionWorldGrowthBridge | None,
) -> NativeModelInputUseWorldSelection:
    selection = replay_native_model_input_use_world_selection(
        owner, checkpoint_ref=handoff.native_world_checkpoint_ref
    )
    return _reconcile_current_native_model_input_use_selection(
        owner,
        selection=selection,
        handoff=handoff,
        problem=problem,
        context_owner=context_owner,
        repo_root=repo_root,
        expected_bridge=expected_bridge,
    )


def _reconcile_current_native_model_input_use_selection(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    selection: NativeModelInputUseWorldSelection,
    handoff: GenericCycleNativeWorldContextHandoffV1,
    problem: DesignProblem,
    context_owner: CycleSubstrateContextArtifactOwner | None,
    repo_root: Path | None,
    expected_bridge: AcquisitionWorldGrowthBridge | None,
) -> NativeModelInputUseWorldSelection:
    """Verify the live action for the exact selection just replayed by the owner."""
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner

    bridge = _current_bridge(owner)
    if expected_bridge is not None and bridge is not expected_bridge:
        raise _error("generic_native_world_bridge_owner_mismatch")
    checkpoint = selection.checkpoint
    current_source, worker, job, payload = _read_current_native_model_input_use_sources(
        owner, problem=problem
    )
    history = selection.source_selection.historical_selection
    phase, successor = _read_model_input_use_stage(
        owner,
        worker=worker,
        job=job,
        payload=payload,
        history=history,
        expected_world_checkpoint=checkpoint,
    )
    if (
        not _use_handoff_matches_selection(handoff, selection, problem)
        or phase != selection.phase
        or successor != selection.successor_selection
        or not _native_use_source_selections_match(
            selection.source_selection, current_source
        )
        or checkpoint.action_job_id != job.job_id
        or checkpoint.route_id != worker.selection.route_id
        or checkpoint.current_profile_selection_ref != _profile_selection_ref(problem)
    ):
        raise _error("generic_native_model_input_use_handoff_current_binding_mismatch")
    service = owner._native_world_action_owner
    if context_owner is None:
        context_owner = CycleSubstrateContextArtifactOwner(
            store=owner.store, control_store=service._control_store
        )
    if (
        type(context_owner) is not CycleSubstrateContextArtifactOwner
        or context_owner._store is not owner.store
        or context_owner._control_store is not service._control_store
    ):
        raise _error("generic_native_model_input_use_context_owner_mismatch")
    resolved = context_owner.resolve_for_current_job(
        handoff.context_job_ref, problem=problem, repo_root=repo_root
    )
    if (
        resolved.context != selection.context
        or (resolved.job_id, resolved.run_id, resolved.tenant_id, resolved.cell_id)
        != (job.job_id, job.run_id, worker.selection.tenant_id, worker.selection.cell_id)
    ):
        raise _error("generic_native_model_input_use_context_current_readback_mismatch")
    source_after, worker_after, job_after, payload_after = (
        _read_current_native_model_input_use_sources(owner, problem=problem, expected_worker=worker)
    )
    phase_after, successor_after = _read_model_input_use_stage(
        owner,
        worker=worker_after,
        job=job_after,
        payload=payload_after,
        history=history,
        expected_world_checkpoint=checkpoint,
    )
    final_admission = owner._native_action_control_store.current_execution_job_admission()
    if (
        phase_after != phase
        or successor_after != successor
        or not _native_use_source_selections_match(current_source, source_after)
        or not final_admission.same_execution_identity(worker.admission)
        or final_admission.job.progress.get("model_input_use")
        != job_after.progress.get("model_input_use")
    ):
        raise _error("generic_native_model_input_use_handoff_changed_during_read")
    return selection


def admit_native_world_context(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    checkpoint_ref: artifacts.ArtifactRef,
    problem: DesignProblem,
    repo_root: Path | None,
) -> GenericCycleNativeWorldContextHandoffV1:
    """Persist an actual acquisition-job context using its existing owner."""
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleNativeWorldContextHandoffV1,
    )

    selection = _current_selection(owner, checkpoint_ref=checkpoint_ref, problem=problem)
    context = _context(selection, problem)
    service = owner._native_world_action_owner
    context_owner = CycleSubstrateContextArtifactOwner(
        store=owner.store, control_store=service._control_store
    )
    context_ref = context_owner.persist_for_current_job(
        context, problem=problem, repo_root=repo_root, return_selected_profile=True
    )
    handoff = GenericCycleNativeWorldContextHandoffV1(
        context=context,
        context_job_ref=context_ref,
        profile=selection.original_profile,
        profile_ref=selection.original_profile_ref,
        native_world_checkpoint_ref=selection.checkpoint_ref,
        original_generic_input_ref=selection.original_generic_input_ref,
        current_profile_selection_ref=cycle_job_profile_selection_ref(problem),
        source_job_id=selection.checkpoint.source_job_id,
        job_id=selection.checkpoint.action_job_id,
        run_id=selection.checkpoint.run_id,
        tenant_id=selection.checkpoint.tenant_id,
        cell_id=selection.checkpoint.cell_id,
    )
    return resolve_native_world_handoff(
        owner, handoff=handoff, problem=problem, context_owner=context_owner, repo_root=repo_root
    )


def resolve_native_world_handoff(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    handoff: GenericCycleNativeWorldContextHandoffV1,
    problem: DesignProblem,
    context_owner: CycleSubstrateContextArtifactOwner | None,
    repo_root: Path | None,
) -> GenericCycleNativeWorldContextHandoffV1:
    """Recheck current ownership separately from the saved original profile."""
    _resolve_native_world_handoff_selection(
        owner,
        handoff=handoff,
        problem=problem,
        context_owner=context_owner,
        repo_root=repo_root,
    )
    return handoff


def _resolve_native_world_handoff_selection(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    handoff: GenericCycleNativeWorldContextHandoffV1,
    problem: DesignProblem,
    context_owner: CycleSubstrateContextArtifactOwner | None = None,
    repo_root: Path | None = None,
    expected_bridge: AcquisitionWorldGrowthBridge | None = None,
    expected_closure: VerifiedAcquisitionRouteClosure | None = None,
) -> NativeDerivedWorldSelection | NativeModelInputUseWorldSelection:
    """Return the verified selection to a caller in the same live read."""
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleNativeWorldContextHandoffV1,
    )

    if type(handoff) is not GenericCycleNativeWorldContextHandoffV1:
        raise _error("generic_native_world_handoff_untyped")
    if _is_native_model_input_use_checkpoint(owner, handoff.native_world_checkpoint_ref):
        return _resolve_current_native_model_input_use_selection(
            owner,
            handoff=handoff,
            problem=problem,
            context_owner=context_owner,
            repo_root=repo_root,
            expected_bridge=expected_bridge,
        )
    selection = _current_selection(
        owner,
        checkpoint_ref=handoff.native_world_checkpoint_ref,
        problem=problem,
        expected_bridge=expected_bridge,
        expected_closure=expected_closure,
    )
    service = owner._native_world_action_owner
    if context_owner is None:
        context_owner = CycleSubstrateContextArtifactOwner(
            store=owner.store, control_store=service._control_store
        )
    if (
        type(context_owner) is not CycleSubstrateContextArtifactOwner
        or context_owner._store is not owner.store
        or context_owner._control_store is not service._control_store
        or not _handoff_matches_selection(handoff, selection)
        or handoff.current_profile_selection_ref != cycle_job_profile_selection_ref(problem)
        or handoff.context != _context(selection, problem)
    ):
        raise _error("generic_native_world_handoff_binding_mismatch")
    resolved = context_owner.resolve_for_current_job(
        handoff.context_job_ref, problem=problem, repo_root=repo_root
    )
    if resolved.context != handoff.context or (
        resolved.job_id,
        resolved.run_id,
        resolved.tenant_id,
        resolved.cell_id,
    ) != (handoff.job_id, handoff.run_id, handoff.tenant_id, handoff.cell_id):
        raise _error("generic_native_world_context_current_readback_mismatch")
    return selection


def _selected_graph_for_handoff(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    handoff: GenericCycleNativeWorldContextHandoffV1,
    selection: NativeDerivedWorldSelection,
    problem: DesignProblem,
) -> NativeSelectedProgramGraphLinkage:
    """Reuse the complete compiler law after separately proving Native context."""
    effective = _effective_profile(selection, handoff.current_profile_selection_ref)
    # The ordinary graph owner checks its own context/profile law. Native's
    # actual context has additional candidate denials; it was independently
    # reproduced above and must not weaken the ordinary equality predicate.
    graph_context = owner.context_for_profile(effective, problem)
    selected = owner._load_selected_program_graph_linkage(
        profile_ref=handoff.profile_ref,
        profile=effective,
        context=graph_context,
        problem=problem,
    )
    return NativeSelectedProgramGraphLinkage(
        handoff=handoff,
        compile_report_ref=selected.compile_report_ref,
        registry_bundle_ref=selected.registry_bundle_ref,
        registry_bundle_content=selected.registry_bundle_content,
        compiled_singleton=selected.compiled_singleton,
    )


def resolve_native_selected_program_graph_linkage(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    handoff: GenericCycleNativeWorldContextHandoffV1,
    problem: DesignProblem,
    context_owner: CycleSubstrateContextArtifactOwner | None = None,
    repo_root: Path | None = None,
) -> NativeSelectedProgramGraphLinkage:
    """Reopen the unchanged graph under the current Native action's own lease."""
    selection = _resolve_native_world_handoff_selection(
        owner,
        handoff=handoff,
        problem=problem,
        context_owner=context_owner,
        repo_root=repo_root,
    )
    historical = (
        selection.source_selection.historical_selection
        if type(selection) is NativeModelInputUseWorldSelection
        else selection
    )
    return _selected_graph_for_handoff(
        owner, handoff=handoff, selection=historical, problem=problem
    )


def resolve_native_selected_program_graph_linkage_historical(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    checkpoint_ref: artifacts.ArtifactRef,
    context_job_ref: artifacts.ArtifactRef,
    profile_ref: artifacts.ArtifactRef,
    expected_context: CycleSubstrateContext,
    problem: DesignProblem,
    job_id: str,
    run_id: str,
    tenant_id: str,
    cell_id: str,
) -> NativeSelectedProgramGraphLinkage:
    """Reproduce recorded Native inputs from actual action history, without rights."""
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleNativeWorldContextHandoffV1,
    )

    if _is_native_model_input_use_checkpoint(owner, checkpoint_ref):
        use_selection = replay_native_model_input_use_world_selection(
            owner, checkpoint_ref=checkpoint_ref
        )
        checkpoint = use_selection.checkpoint
        context = use_selection.context
        handoff = _native_use_handoff(use_selection)
        if (
            not _same_ref(context_job_ref, checkpoint.context_job_ref)
            or not _same_ref(profile_ref, checkpoint.original_profile_ref)
            or context != expected_context
            or (job_id, run_id, tenant_id, cell_id)
            != (
                checkpoint.action_job_id,
                checkpoint.run_id,
                checkpoint.tenant_id,
                checkpoint.cell_id,
            )
        ):
            raise _error("generic_native_model_input_use_historical_handoff_mismatch")
        return _selected_graph_for_handoff(
            owner,
            handoff=handoff,
            selection=use_selection.source_selection.historical_selection,
            problem=problem,
        )
    selection = _recorded_selection(owner, checkpoint_ref)
    context_record = CycleSubstrateContextArtifactOwner(
        store=owner.store
    ).resolve_historical_job_artifact(
        context_job_ref,
        problem=problem,
        expected_job_id=job_id,
        expected_run_id=run_id,
        expected_tenant_id=tenant_id,
        expected_cell_id=cell_id,
    )
    context = context_record.context
    if (
        not _same_ref(profile_ref, selection.original_profile_ref)
        or context != expected_context
        or context != _context(selection, problem)
    ):
        raise _error("generic_native_world_historical_context_mismatch")
    handoff = GenericCycleNativeWorldContextHandoffV1(
        context=context,
        context_job_ref=context_job_ref,
        profile=selection.original_profile,
        profile_ref=profile_ref,
        native_world_checkpoint_ref=checkpoint_ref,
        original_generic_input_ref=selection.original_generic_input_ref,
        current_profile_selection_ref=cycle_job_profile_selection_ref(problem),
        source_job_id=selection.checkpoint.source_job_id,
        job_id=job_id,
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    if not _handoff_matches_selection(handoff, selection):
        raise _error("generic_native_world_historical_scope_mismatch")
    return _selected_graph_for_handoff(owner, handoff=handoff, selection=selection, problem=problem)


def _selection_for_input(
    owner: GenericCycleSimulationAdmissionOwner,
    input_record: GenericCycleSimulationN5InputV1,
    *,
    current: bool = False,
) -> NativeDerivedWorldSelection:
    from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref

    if input_record.native_world_checkpoint_ref is None:
        raise _error("generic_native_world_input_subject_missing")
    if _is_native_model_input_use_checkpoint(owner, input_record.native_world_checkpoint_ref):
        selected_use = replay_native_model_input_use_world_selection(
            owner, checkpoint_ref=input_record.native_world_checkpoint_ref
        )
        use_checkpoint = selected_use.checkpoint
        historical = selected_use.source_selection.historical_selection
        if (
            input_record.schema_version != "policyos.runtime.generic_cycle_simulation_n5_input.v2"
            or input_record.original_generic_input_ref is None
            or not _same_ref(
                input_record.original_generic_input_ref, use_checkpoint.original_generic_input_ref
            )
            or input_record.profile != historical.original_profile
            or not _same_ref(input_record.profile_ref, use_checkpoint.original_profile_ref)
            or not _same_ref(input_record.context_job_ref, use_checkpoint.context_job_ref)
            or input_record.native_current_profile_selection_ref
            != cycle_job_profile_selection_ref(historical.problem)
            or (
                input_record.job_id,
                input_record.run_id,
                input_record.tenant_id,
                input_record.cell_id,
            )
            != (
                use_checkpoint.action_job_id,
                use_checkpoint.run_id,
                use_checkpoint.tenant_id,
                use_checkpoint.cell_id,
            )
        ):
            raise _error("generic_native_model_input_use_n5_input_selection_mismatch")
        if current:
            handoff = _native_use_handoff(selected_use)
            try:
                reopened_checkpoint = _read_verified_native_model_input_use_checkpoint(
                    owner, handoff.native_world_checkpoint_ref
                )
                if reopened_checkpoint != use_checkpoint:
                    raise ValueError("generic_native_model_input_use_checkpoint_changed")
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                raise _error("generic_native_model_input_use_checkpoint_history_not_replayed") from exc
            _reconcile_current_native_model_input_use_selection(
                owner,
                selection=selected_use,
                handoff=handoff,
                problem=historical.problem,
                context_owner=None,
                repo_root=None,
                expected_bridge=None,
            )
        return historical
    selection = _recorded_selection(owner, input_record.native_world_checkpoint_ref)
    if current:
        selection = _current_selection(
            owner,
            checkpoint_ref=input_record.native_world_checkpoint_ref,
            problem=selection.problem,
        )
    checkpoint = selection.checkpoint
    if (
        input_record.schema_version != "policyos.runtime.generic_cycle_simulation_n5_input.v2"
        or input_record.original_generic_input_ref is None
        or not _same_ref(
            input_record.original_generic_input_ref, selection.original_generic_input_ref
        )
        or input_record.profile != selection.original_profile
        or not _same_ref(input_record.profile_ref, selection.original_profile_ref)
        or input_record.native_current_profile_selection_ref
        != cycle_job_profile_selection_ref(selection.problem)
        or (input_record.job_id, input_record.run_id, input_record.tenant_id, input_record.cell_id)
        != (
            checkpoint.action_job_id,
            checkpoint.run_id,
            checkpoint.tenant_id,
            checkpoint.cell_id,
        )
    ):
        raise _error("generic_native_world_input_selection_mismatch")
    return selection


def effective_native_input_profile(
    owner: GenericCycleSimulationAdmissionOwner, input_record: GenericCycleSimulationN5InputV1
) -> GenericCycleSimulationProfileV1:
    """Project only the recorded world/current problem into builder inputs.

    This projection is not adopted configuration. The original profile bytes
    remain in the input, and this projection is reproducible from its separate
    selected checkpoint. No other numerical or operational setting changes.
    """
    selection = _selection_for_input(owner, input_record)
    return _effective_profile(selection, input_record.native_current_profile_selection_ref)


def _effective_profile(
    selection: NativeDerivedWorldSelection, current_profile_selection_ref: str
) -> GenericCycleSimulationProfileV1:
    """Own the one reproducible world/key projection for Native builders."""
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationProfileV1,
    )

    profile = selection.original_profile
    effective = profile.model_copy(
        update={
            "world_model_record_ref": selection.world_model_record_ref,
            "context_inputs": profile.context_inputs.model_copy(
                update={"world_model_record": selection.world_model_record}
            ),
            "profile_selection_ref": current_profile_selection_ref,
        },
        deep=True,
    )
    payload = effective.model_dump(mode="python")
    payload["content_hash"] = gy_content_hash(
        effective.model_dump(mode="json", exclude={"content_hash"})
    )
    return GenericCycleSimulationProfileV1.model_validate(payload)


def require_current_native_input(
    owner: GenericCycleSimulationAdmissionOwner, input_record: GenericCycleSimulationN5InputV1
) -> None:
    """Require the original current adoption and the current acquisition lease."""
    _selection_for_input(owner, input_record, current=True)


def persist_native_n5_input(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    handoff: GenericCycleNativeWorldContextHandoffV1,
    source_ref: artifacts.ArtifactRef,
    source_run_id: str,
    problem: DesignProblem,
    cycle_index: int,
    candidate_id: str,
    candidate_atom_hash: str,
    outcome_variable: str,
) -> artifacts.ArtifactRef:
    """Bind a fresh actual N4 source to the independently selected action world."""
    from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.generic_simulation_admission import (
        _PROFILE_CANON,
        GenericCycleSimulationN5InputV1,
    )

    handoff = resolve_native_world_handoff(
        owner, handoff=handoff, problem=problem, context_owner=None, repo_root=None
    )
    source = GenerationSourceRepository(owner.store, native_world_owner=owner).load(
        source_ref,
        run_id=source_run_id,
        expected_job_id=handoff.job_id,
        expected_run_id=handoff.run_id,
        expected_tenant_id=handoff.tenant_id,
        expected_cell_id=handoff.cell_id,
        context_job_ref=handoff.context_job_ref,
        profile_ref=handoff.profile_ref,
    )
    if (
        source.problem.model_dump(mode="python") != problem.model_dump(mode="python")
        or source.cycle_substrate_context != handoff.context
        or source.cycle_index != cycle_index
        or len(
            [
                candidate
                for candidate in source.generation_result.candidates
                if getattr(candidate, "candidate_id", None) == candidate_id
                and getattr(getattr(candidate, "atom", None), "content_hash", None)
                == candidate_atom_hash
            ]
        )
        != 1
    ):
        raise _error("generic_native_world_fresh_n4_source_mismatch")
    payload = {
        "schema_version": "policyos.runtime.generic_cycle_simulation_n5_input.v2",
        "authority_purpose": "cycle_input_candidate_only",
        "native_world_checkpoint_ref": handoff.native_world_checkpoint_ref,
        "original_generic_input_ref": handoff.original_generic_input_ref,
        "native_current_profile_selection_ref": handoff.current_profile_selection_ref,
        "job_id": handoff.job_id,
        "run_id": handoff.run_id,
        "source_run_id": source_run_id,
        "tenant_id": handoff.tenant_id,
        "cell_id": handoff.cell_id,
        "design_problem_ref": cycle_job_design_problem_ref(problem),
        "cycle_index": cycle_index,
        "n4_source_ref": source_ref,
        "context_job_ref": handoff.context_job_ref,
        "profile_ref": handoff.profile_ref,
        "profile": handoff.profile,
        "candidate_id": candidate_id,
        "candidate_atom_hash": candidate_atom_hash,
        "outcome_variable": outcome_variable,
        "n5": handoff.profile.n5,
    }
    provisional = GenericCycleSimulationN5InputV1.model_construct(
        **payload, content_hash="sha256:" + "0" * 64
    )
    normalized = provisional.model_dump(mode="json", exclude={"content_hash"})
    record = GenericCycleSimulationN5InputV1.model_validate(
        {**normalized, "content_hash": gy_content_hash(normalized)}
    )
    ref = owner.store.put_json(
        record.model_dump(mode="json"),
        owner._n5_input_write_options(record),
        canon_spec=_PROFILE_CANON,
        return_selected_profile=True,
    )
    owner.resolve_n5_input(ref, expected=record)
    replay_native_n5_input_sources(owner, record)
    return ref


def replay_native_n5_input_sources(
    owner: GenericCycleSimulationAdmissionOwner, input_record: GenericCycleSimulationN5InputV1
) -> tuple[object, object, CycleSubstrateContext, object]:
    """Replay the fresh N4 source and recorded action world, without new rights."""
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.design_generation import ShadowGeneratedCandidate
    from polisyos.runtime.quality.generation_cycle import JointSimulationPort
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleNativeWorldContextHandoffV1,
    )

    selection = _selection_for_input(owner, input_record)
    source = GenerationSourceRepository(owner.store, native_world_owner=owner).load(
        input_record.n4_source_ref,
        run_id=input_record.source_run_id,
        expected_job_id=input_record.job_id,
        expected_run_id=input_record.run_id,
        expected_tenant_id=input_record.tenant_id,
        expected_cell_id=input_record.cell_id,
        context_job_ref=input_record.context_job_ref,
        profile_ref=input_record.profile_ref,
    )
    problem = source.problem
    if (
        problem.model_dump(mode="python") != selection.problem.model_dump(mode="python")
        or cycle_job_design_problem_ref(problem) != input_record.design_problem_ref
        or input_record.native_current_profile_selection_ref
        != cycle_job_profile_selection_ref(problem)
        or source.cycle_index != input_record.cycle_index
    ):
        raise _error("generic_native_world_recorded_problem_mismatch")
    context_record = CycleSubstrateContextArtifactOwner(
        store=owner.store
    ).resolve_historical_job_artifact(
        input_record.context_job_ref,
        problem=problem,
        expected_job_id=input_record.job_id,
        expected_run_id=input_record.run_id,
        expected_tenant_id=input_record.tenant_id,
        expected_cell_id=input_record.cell_id,
    )
    context = context_record.context
    if context != _context(selection, problem) or source.cycle_substrate_context != context:
        raise _error("generic_native_world_recorded_context_mismatch")
    candidates = tuple(
        candidate
        for candidate in source.generation_result.candidates
        if getattr(candidate, "candidate_id", None) == input_record.candidate_id
        and getattr(getattr(candidate, "atom", None), "content_hash", None)
        == input_record.candidate_atom_hash
    )
    if len(candidates) != 1 or type(candidates[0]) is not ShadowGeneratedCandidate:
        raise _error("generic_native_world_recorded_candidate_mismatch")
    handoff = GenericCycleNativeWorldContextHandoffV1(
        context=context,
        context_job_ref=input_record.context_job_ref,
        profile=input_record.profile,
        profile_ref=input_record.profile_ref,
        native_world_checkpoint_ref=input_record.native_world_checkpoint_ref,
        original_generic_input_ref=input_record.original_generic_input_ref,
        current_profile_selection_ref=input_record.native_current_profile_selection_ref,
        source_job_id=selection.checkpoint.source_job_id,
        job_id=input_record.job_id,
        run_id=input_record.run_id,
        tenant_id=input_record.tenant_id,
        cell_id=input_record.cell_id,
    )
    port = JointSimulationPort(
        cycle_substrate_context=context,
        artifact_store=owner.store,
        generic_cycle_simulation_admission_owner=owner,
        generic_cycle_simulation_handoff=handoff,
    )
    return source, candidates[0], context, port
