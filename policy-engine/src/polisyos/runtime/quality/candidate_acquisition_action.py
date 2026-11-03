"""Bind a modeled candidate source to one real, currently leased acquisition action.

This receipt identifies input custody for candidate simulation.  It is not an
observed-data passport, semantic epoch admission, or a claim-evidence grant.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts
from polisyos.data_requirement import DataRequirementCompilationReport
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionCandidateSourceRoute
from polisyos.runtime.quality.candidate_acquisition_source import (
    CandidateAcquisitionSource,
    persist_candidate_acquisition_source,
    read_candidate_acquisition_source,
)

if TYPE_CHECKING:
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIRouteExecutionBinding,
    )
    from polisyos.runtime.http.services.control_plane_store import ControlJobExecutionAdmission
    from polisyos.runtime.quality.acquisition_executor import LiveSourceExecutionEvidence
    from polisyos.runtime.quality.acquisition_planner import AcquisitionRequirementBasisBinding
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionRoutePhaseReceipt,
        VerifiedAcquisitionRouteClosure,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
    )

CANDIDATE_ACTION_KIND = "runtime_quality.acquisition_candidate_action_receipt"
CANDIDATE_ACTION_SCHEMA = "polisyos.runtime.CandidateAcquisitionActionReceipt"


class CandidateAcquisitionActionReceipt(BaseModel):
    """Selected input and source identity bound to one protected acquisition action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["CandidateAcquisitionActionReceipt@1.1"] = (
        "CandidateAcquisitionActionReceipt@1.1"
    )
    status: Literal["candidate_input_prepared"] = "candidate_input_prepared"
    purpose: Literal["candidate_simulation"] = "candidate_simulation"
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    action_job_id: str = Field(min_length=1)
    action_generation: int = Field(ge=1)
    action_attempt: int = Field(ge=1)
    selection: AcquisitionCandidateSourceRoute
    candidate_budget_window_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_budget_window_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    route_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    action_phase_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    selected_action_phase_ref: artifacts.ArtifactRef
    decision_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    route_binding_id: str = Field(min_length=1)
    route_binding: dict[str, object]
    attempt_id: str = Field(min_length=1)
    compiled_requirement_ref: str = Field(min_length=1)
    requirement_id: str = Field(min_length=1)
    candidate_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    profile_selection_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    canonical_variable_id: str = Field(min_length=1)
    target_slot_id: str = Field(min_length=1)
    candidate_source_ref: artifacts.ArtifactRef
    compiler_report_ref: artifacts.ArtifactRef
    limitations: tuple[str, ...] = Field(min_length=1)
    admitted_observation_delta: Literal[0] = 0
    observed_admission: Literal[False] = False
    publication_authority: Literal[False] = False


def receipt_inputs(receipt: CandidateAcquisitionActionReceipt) -> tuple[artifacts.InputRef, ...]:
    """Return the complete selected-profile parents of a candidate action."""
    return tuple(
        artifacts.input_ref_from_artifact_ref(ref, role=role)
        for role, ref in (
            ("candidate_source", receipt.candidate_source_ref),
            ("compiler_report", receipt.compiler_report_ref),
            ("executing_action_phase", receipt.selected_action_phase_ref),
        )
    )


def _current_action(
    bridge: AcquisitionWorldGrowthBridge,
    closure: VerifiedAcquisitionRouteClosure,
    action_phase_ref: str,
) -> tuple[
    AcquisitionCandidateSourceRoute, AcquisitionRoutePhaseReceipt, ControlJobExecutionAdmission
]:
    """Resolve the owner route, durable action head and live worker lease again."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoop
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge

    service = bridge._source_control_service
    if (
        type(bridge) is not AcquisitionWorldGrowthBridge
        or type(service) is not ControlPlaneService
        or service._control_store is not bridge.control_store
        or service._artifact_store is not bridge.artifact_store
        or service._diagnostic_event_log is not bridge.event_log
        or service.acquisition_route_sink is not bridge.action_head_sink
    ):
        raise TypeError("candidate_action_canonical_bridge_required")
    selection = bridge.candidate_source_selection(closure)
    if selection is None or bridge.control_store is None:
        raise ValueError("candidate_action_route_not_configured")
    phase = bridge._validate_action_phase(closure, selection, action_phase_ref)
    admission = bridge.control_store.current_execution_job_admission()
    job = admission.job
    if (
        job.kind != "acquisition"
        or job.state != "running"
        or job.run_id != closure.run_id
        or job.job_id != phase.job_id
        or admission.scope.status != "established"
        or not admission.scope.actor_authenticated
        or admission.scope.tenant_id != closure.tenant_id
        or admission.scope.cell_id != closure.cell_id
    ):
        raise ValueError("candidate_action_live_job_scope_mismatch")
    current = AcquisitionRouteLoop(
        control_store=bridge.control_store,
        artifact_store=bridge.artifact_store,
        event_log=bridge.event_log,
        core_source_resolver=service.resolve_completed_control_job_core_run_source,
        tenant_id=closure.tenant_id,
        cell_id=closure.cell_id,
        action_outcome_reader=service.acquisition_route_sink,
    ).resolve_current_route(run_id=closure.run_id, action_job_id=phase.job_id)
    if current != closure:
        raise ValueError("candidate_action_route_no_longer_current")
    return selection, phase, admission


def _compiler_binding(
    bridge: AcquisitionWorldGrowthBridge,
    closure: VerifiedAcquisitionRouteClosure,
    selection: AcquisitionCandidateSourceRoute,
) -> AcquisitionRequirementBasisBinding:
    """Bind the routed compiled spec to the exact compiler-selected discovery query."""
    binding = closure.planner_report.requirement_basis_binding
    if binding is None or binding.compiler_report_ref.manifest_profile_sha256 is None:
        raise ValueError("candidate_action_compiler_basis_unselected")
    _require_compiler_relation(
        bridge.artifact_store,
        binding,
        compiled_requirement_ref=selection.compiled_requirement_ref,
        requirement_id=selection.requirement_id,
        candidate_digest=selection.candidate_digest,
    )
    return binding


def _require_compiler_relation(
    store: artifacts.ArtifactStore,
    binding: object,
    *,
    compiled_requirement_ref: str,
    requirement_id: str,
    candidate_digest: str,
) -> None:
    from polisyos.runtime.quality.acquisition_planner import AcquisitionRequirementBasisBinding

    if type(binding) is not AcquisitionRequirementBasisBinding:
        raise TypeError("candidate_action_compiler_basis_untyped")
    report = DataRequirementCompilationReport.model_validate(
        artifacts.load_core_json_artifact(store, binding.compiler_report_ref)
    )
    specs = tuple(spec for spec in report.specs if spec.requirement_id == compiled_requirement_ref)
    resolutions = tuple(
        row
        for row in (report.capability_requirement_resolutions or ())
        if row.query.requirement_id == requirement_id
    )
    if len(specs) != 1 or len(resolutions) != 1:
        raise ValueError("candidate_action_compiler_selection_missing_or_ambiguous")
    spec, resolution = specs[0], resolutions[0]
    capability = spec.metadata.get("capability_binding")
    discovery = resolution.candidate_discovery
    if (
        not isinstance(capability, Mapping)
        or capability.get("requirement_id") != resolution.query.requirement_id
        or not isinstance(capability.get("construct_ref"), str)
        or capability["construct_ref"].removeprefix("construct:") != resolution.query.construct
        or str(spec.metadata.get("construct_ref", "")).removeprefix("construct:")
        != resolution.query.construct
        or discovery is None
        or discovery.query != resolution.query
        or len(tuple(c for c in discovery.candidates if c.content_digest == candidate_digest)) != 1
    ):
        raise ValueError("candidate_action_compiler_selection_mismatch")
    return binding


def persist_candidate_acquisition_action(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    closure: VerifiedAcquisitionRouteClosure,
    binding: WorldBankWDIRouteExecutionBinding,
    evidence: LiveSourceExecutionEvidence,
    action_phase_ref: str,
) -> tuple[artifacts.ArtifactRef, CandidateAcquisitionActionReceipt]:
    """Persist a source after real route/action/lease verification, without an epoch."""
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIRouteExecutionBinding,
    )

    if type(binding) is not WorldBankWDIRouteExecutionBinding:
        raise TypeError("candidate_action_route_binding_untyped")
    selection, phase, admission = _current_action(bridge, closure, action_phase_ref)
    _pointer, selector = bridge._read_action_selector(closure, selection, action_phase_ref)
    window_id = selector.candidate_budget_window_id
    window_digest = selector.candidate_budget_window_digest
    if window_id is None or window_digest is None:
        raise ValueError("candidate_action_budget_window_missing")
    if (
        binding.tenant_id != closure.tenant_id
        or binding.cell_id != closure.cell_id
        or binding.run_id != closure.run_id
        or binding.route_id != closure.route_id
        or binding.target_variable != selection.target_slot_id
        or binding.constraints.country_code != selection.country_code
        or binding.constraints.start_year != selection.year
        or binding.constraints.end_year != selection.year
        or evidence.authorization.attempt_id != binding.attempt_id
    ):
        raise ValueError("candidate_action_execution_binding_mismatch")
    requirement_basis = _compiler_binding(bridge, closure, selection)
    source_ref = persist_candidate_acquisition_source(
        bridge.artifact_store,
        authority=bridge.authority,
        entry_id=binding.authority_entry_id,
        live_source_execution=evidence,
        requirement_basis_binding=requirement_basis,
        requirement_id=selection.requirement_id,
        candidate_digest=selection.candidate_digest,
        target_slot_id=selection.target_slot_id,
        country_code=selection.country_code,
        year=selection.year,
        population=selection.population,
        tenant_id=closure.tenant_id,
        cell_id=closure.cell_id,
        run_id=closure.run_id,
        job_id=phase.job_id,
        route_id=closure.route_id,
    )
    source = read_candidate_acquisition_source(
        bridge.artifact_store, source_ref=source_ref, authority=bridge.authority
    )
    if (
        source.resolved_source.entry.entry_id != binding.authority_entry_id
        or source.resolved_source.registry_content_sha256
        != binding.authority_registry_content_sha256
        or source.resolved_source.authority_provision_id != binding.authority_provision_id
        or source.resolved_source.authority_provision_content_sha256
        != binding.authority_provision_content_sha256
    ):
        raise ValueError("candidate_action_source_owner_mismatch")
    phase_ref = artifacts.artifact_ref_for_manifest(
        bridge.artifact_store.get_manifest(action_phase_ref)
    )
    from polisyos.runtime.quality.agent_action_authority import reconcile_authority_ref

    if (
        str(phase_ref.artifact_id) != action_phase_ref
        or phase_ref.manifest_profile_sha256 is None
        or artifacts.load_core_json_artifact(bridge.artifact_store, phase_ref)
        != phase.model_dump(mode="json")
        or reconcile_authority_ref(
            artifact_store=bridge.artifact_store,
            event_log=bridge.event_log,
            cas_ref=phase_ref,
            expected_tenant_id=closure.tenant_id,
            expected_cell_id=closure.cell_id,
            expected_run_id=closure.run_id,
            expected_job_id=phase.job_id,
        ).durable_event_id
        is None
    ):
        raise ValueError("candidate_action_phase_profile_unselected")
    receipt = CandidateAcquisitionActionReceipt(
        tenant_id=closure.tenant_id,
        cell_id=closure.cell_id,
        run_id=closure.run_id,
        source_job_id=closure.source_job_id,
        action_job_id=phase.job_id,
        action_generation=phase.action_generation,
        action_attempt=admission.attempt,
        selection=selection,
        candidate_budget_window_id=window_id,
        candidate_budget_window_digest=window_digest,
        route_id=closure.route_id,
        action_phase_ref=action_phase_ref,
        selected_action_phase_ref=phase_ref,
        decision_ref=phase.decision_ref,
        route_binding_id=binding.binding_id,
        route_binding=binding.model_dump(mode="json"),
        attempt_id=binding.attempt_id,
        compiled_requirement_ref=selection.compiled_requirement_ref,
        requirement_id=selection.requirement_id,
        candidate_digest=selection.candidate_digest,
        profile_selection_ref=selection.profile_selection_ref,
        canonical_variable_id=selection.canonical_variable_id,
        target_slot_id=selection.target_slot_id,
        candidate_source_ref=source_ref,
        compiler_report_ref=source.compiler_report_ref,
        limitations=source.limitations,
    )
    # An expired/reassigned job must not publish the prepared action, even if
    # its source and signed phase were valid before the physical fetch.
    _selection_after, _phase_after, after = _current_action(bridge, closure, action_phase_ref)
    _pointer_after, selector_after = bridge._read_action_selector(
        closure, _selection_after, action_phase_ref
    )
    if (
        _selection_after != selection
        or _phase_after != phase
        or after.job.job_id != admission.job.job_id
        or after.job.lease_owner != admission.job.lease_owner
        or after.attempt != admission.attempt
        or after.scope != admission.scope
        or selector_after.candidate_budget_window_id != window_id
        or selector_after.candidate_budget_window_digest != window_digest
    ):
        raise ValueError("candidate_action_execution_lease_changed")
    selected_ref = bridge._persist(
        closure,
        receipt.model_dump(mode="json"),
        CANDIDATE_ACTION_KIND,
        CANDIDATE_ACTION_SCHEMA,
        "candidate_input_prepared",
        artifact_inputs=receipt_inputs(receipt),
        return_selected_profile=True,
    )
    if not isinstance(selected_ref, artifacts.ArtifactRef):
        raise ValueError("candidate_action_writer_profile_missing")
    read_candidate_acquisition_action(
        bridge=bridge, closure=closure, receipt_ref=selected_ref, require_current_action=True
    )
    return selected_ref, receipt


def validate_candidate_action_source_binding(
    store: artifacts.ArtifactStore,
    receipt: CandidateAcquisitionActionReceipt,
    source: CandidateAcquisitionSource,
) -> None:
    """Reconcile the action, selected source and compiler requirement as one owner chain."""
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIRouteExecutionBinding,
    )

    binding = WorldBankWDIRouteExecutionBinding.model_validate(receipt.route_binding)
    if (
        receipt.compiler_report_ref != source.compiler_report_ref
        or receipt.selection.tenant_id != receipt.tenant_id
        or receipt.selection.cell_id != receipt.cell_id
        or receipt.selection.run_id != receipt.run_id
        or receipt.selection.route_id != receipt.route_id
        or receipt.selection.compiled_requirement_ref != receipt.compiled_requirement_ref
        or receipt.selection.requirement_id != receipt.requirement_id
        or receipt.selection.candidate_digest != receipt.candidate_digest
        or receipt.selection.profile_selection_ref != receipt.profile_selection_ref
        or receipt.selection.canonical_variable_id != receipt.canonical_variable_id
        or receipt.selection.target_slot_id != receipt.target_slot_id
        or receipt.selection.country_code != source.country_code
        or receipt.selection.year != source.year
        or receipt.selection.population != source.population
        or receipt.requirement_id != source.requirement_id
        or receipt.candidate_digest != source.candidate_digest
        or receipt.target_slot_id != source.target_slot_id
        or receipt.limitations != source.limitations
        or receipt.tenant_id != source.tenant_id
        or receipt.cell_id != source.cell_id
        or receipt.run_id != source.run_id
        or receipt.action_job_id != source.job_id
        or receipt.route_id != source.route_id
        or receipt.attempt_id != source.live_source_execution.authorization.attempt_id
        or str(receipt.selected_action_phase_ref.artifact_id) != receipt.action_phase_ref
        or binding.binding_id != receipt.route_binding_id
        or binding.tenant_id != receipt.tenant_id
        or binding.cell_id != receipt.cell_id
        or binding.run_id != receipt.run_id
        or binding.route_id != receipt.route_id
        or binding.attempt_id != receipt.attempt_id
        or binding.target_variable != receipt.target_slot_id
        or binding.authority_entry_id != source.resolved_source.entry.entry_id
        or binding.authority_registry_content_sha256
        != source.resolved_source.registry_content_sha256
        or binding.authority_provision_id != source.resolved_source.authority_provision_id
        or binding.authority_provision_content_sha256
        != source.resolved_source.authority_provision_content_sha256
        or binding.constraints.country_code != source.country_code
        or binding.constraints.start_year != source.year
        or binding.constraints.end_year != source.year
        or binding.constraints.page_size != source.request_projection.get("page_size")
    ):
        raise ValueError("candidate_action_receipt_source_binding_mismatch")
    _require_compiler_relation(
        store,
        source.requirement_basis_binding,
        compiled_requirement_ref=receipt.compiled_requirement_ref,
        requirement_id=receipt.requirement_id,
        candidate_digest=receipt.candidate_digest,
    )


def read_candidate_acquisition_action_historical(
    *,
    artifact_store: artifacts.ArtifactStore,
    event_log: object,
    receipt_ref: artifacts.ArtifactRef,
    executing_phase: AcquisitionRoutePhaseReceipt,
    executing_phase_ref: str,
) -> CandidateAcquisitionActionReceipt:
    """Reopen an exact action and its immutable source without a live lease."""
    from polisyos.runtime.quality.agent_action_authority import reconcile_authority_ref

    if (
        receipt_ref.kind != CANDIDATE_ACTION_KIND
        or receipt_ref.media_type != "application/json"
        or receipt_ref.manifest_profile_sha256 is None
        or artifacts.profile_bound_ref(artifact_store, receipt_ref) != receipt_ref
        or executing_phase.receipt_phase != "executing"
    ):
        raise ValueError("candidate_action_historical_profile_invalid")
    receipt = CandidateAcquisitionActionReceipt.model_validate(
        artifacts.load_core_json_artifact(artifact_store, receipt_ref)
    )
    manifest = artifact_store.get_manifest(receipt_ref)
    schema = manifest.artifact_schema
    phase_manifest = artifact_store.get_manifest(receipt.selected_action_phase_ref)
    phase_schema = phase_manifest.artifact_schema
    if (
        schema is None
        or schema.name != CANDIDATE_ACTION_SCHEMA
        or schema.version != "1.1"
        or manifest.producer is None
        or manifest.producer.component != "polisyos.runtime.acquisition_world_growth"
        or manifest.inputs != list(receipt_inputs(receipt))
        or manifest.tenant_context is None
        or manifest.tenant_context.tenant_id != executing_phase.tenant_id
        or manifest.tenant_context.cell_id != executing_phase.cell_id
        or receipt.tenant_id != executing_phase.tenant_id
        or receipt.cell_id != executing_phase.cell_id
        or receipt.run_id != executing_phase.run_id
        or receipt.source_job_id != executing_phase.source_job_id
        or receipt.action_job_id != executing_phase.job_id
        or receipt.action_generation != executing_phase.action_generation
        or receipt.route_id != executing_phase.route_id
        or receipt.action_phase_ref != executing_phase_ref
        or receipt.decision_ref != executing_phase.decision_ref
        or str(receipt.selected_action_phase_ref.artifact_id) != executing_phase_ref
        or phase_manifest.kind != "runtime_quality.acquisition_route_phase_receipt"
        or phase_schema is None
        or phase_schema.name != "polisyos.runtime.AcquisitionRoutePhaseReceipt"
        or phase_schema.version != executing_phase.schema_version.rsplit("@", 1)[-1]
        or phase_manifest.producer is None
        or phase_manifest.producer.component != "polisyos.runtime.acquisition_route_loop"
        or phase_manifest.producer.version != "2026.08.28+ds15-c02"
        or phase_manifest.same_input_closure is None
        or phase_manifest.same_input_closure.closure_id
        != f"acquisition-route:{executing_phase.receipt_id}"
        or phase_manifest.same_input_closure.status != "closed"
        or phase_manifest.same_input_closure.run_id != executing_phase.run_id
        or phase_manifest.same_input_closure.job_id != executing_phase.job_id
        or phase_manifest.same_input_closure.tenant_id != executing_phase.tenant_id
        or phase_manifest.same_input_closure.cell_id != executing_phase.cell_id
        or phase_manifest.same_input_closure.closure_sha256 != executing_phase.route_id
        or artifacts.load_core_json_artifact(artifact_store, receipt.selected_action_phase_ref)
        != executing_phase.model_dump(mode="json")
    ):
        raise ValueError("candidate_action_historical_binding_mismatch")
    for ref, job_id in (
        (receipt_ref, receipt.source_job_id),
        (receipt.selected_action_phase_ref, receipt.action_job_id),
    ):
        report = reconcile_authority_ref(
            artifact_store=artifact_store,
            event_log=event_log,
            cas_ref=ref,
            expected_tenant_id=receipt.tenant_id,
            expected_cell_id=receipt.cell_id,
            expected_run_id=receipt.run_id,
            expected_job_id=job_id,
        )
        if report.durable_event_id is None:
            raise ValueError("candidate_action_historical_event_missing")
    source = read_candidate_acquisition_source(
        artifact_store, source_ref=receipt.candidate_source_ref
    )
    validate_candidate_action_source_binding(artifact_store, receipt, source)
    return receipt


def read_candidate_acquisition_action(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    closure: VerifiedAcquisitionRouteClosure,
    receipt_ref: artifacts.ArtifactRef,
    require_current_action: bool,
) -> CandidateAcquisitionActionReceipt:
    """Reopen exact parents; optionally require the same live action and source owner."""
    if (
        receipt_ref.kind != CANDIDATE_ACTION_KIND
        or receipt_ref.media_type != "application/json"
        or receipt_ref.manifest_profile_sha256 is None
        or artifacts.profile_bound_ref(bridge.artifact_store, receipt_ref) != receipt_ref
    ):
        raise ValueError("candidate_action_receipt_profile_unselected")
    payload = artifacts.load_core_json_artifact(bridge.artifact_store, receipt_ref)
    receipt = CandidateAcquisitionActionReceipt.model_validate(payload)
    expected = receipt_inputs(receipt)
    if bridge.artifact_store.get_manifest(receipt_ref).inputs != list(expected):
        raise ValueError("candidate_action_receipt_parents_mismatch")
    # Reuse the world-growth owner for exact event, schema, and payload verification.
    if bridge._read(receipt_ref, CANDIDATE_ACTION_KIND, expected_inputs=expected) != payload:
        raise ValueError("candidate_action_receipt_owner_readback_mismatch")
    from polisyos.runtime.quality.agent_action_authority import reconcile_authority_ref

    if (
        receipt.tenant_id != closure.tenant_id
        or receipt.cell_id != closure.cell_id
        or receipt.run_id != closure.run_id
        or receipt.source_job_id != closure.source_job_id
        or receipt.route_id != closure.route_id
    ):
        raise ValueError("candidate_action_receipt_route_scope_mismatch")
    reconciliation = reconcile_authority_ref(
        artifact_store=bridge.artifact_store,
        event_log=bridge.event_log,
        cas_ref=receipt_ref,
        expected_tenant_id=closure.tenant_id,
        expected_cell_id=closure.cell_id,
        expected_run_id=closure.run_id,
        expected_job_id=closure.source_job_id,
    )
    if reconciliation.durable_event_id is None:
        raise ValueError("candidate_action_receipt_owner_event_missing")
    source: CandidateAcquisitionSource = read_candidate_acquisition_source(
        bridge.artifact_store,
        source_ref=receipt.candidate_source_ref,
        authority=bridge.authority if require_current_action else None,
    )
    validate_candidate_action_source_binding(bridge.artifact_store, receipt, source)
    if require_current_action:
        selection, phase, admission = _current_action(bridge, closure, receipt.action_phase_ref)
        _compiler_binding(bridge, closure, selection)
        from polisyos.data_forge import read_api
        from polisyos.runtime.http.services.acquisition_surface_execution import (
            WorldBankWDIRouteExecutionBinding,
            resolve_world_bank_wdi_route_execution_bindings,
        )

        registry = read_api.catalog.AcquisitionAuthorityRegistry.model_validate_json(
            bridge.authority.registry_path.read_bytes()
        )
        bound = WorldBankWDIRouteExecutionBinding.model_validate(receipt.route_binding)
        eligible = resolve_world_bank_wdi_route_execution_bindings(
            closure=closure,
            authority=bridge.authority,
            registry=registry,
            provision=bridge.authority.provision,
            provision_content_sha256=bridge.authority.provision_content_sha256,
        )
        if (
            receipt.tenant_id != closure.tenant_id
            or receipt.cell_id != closure.cell_id
            or receipt.run_id != closure.run_id
            or receipt.source_job_id != closure.source_job_id
            or receipt.route_id != closure.route_id
            or receipt.action_job_id != phase.job_id
            or receipt.action_generation != phase.action_generation
            or receipt.decision_ref != phase.decision_ref
            or receipt.compiled_requirement_ref != selection.compiled_requirement_ref
            or receipt.requirement_id != selection.requirement_id
            or receipt.candidate_digest != selection.candidate_digest
            or receipt.profile_selection_ref != selection.profile_selection_ref
            or receipt.canonical_variable_id != selection.canonical_variable_id
            or receipt.target_slot_id != selection.target_slot_id
            or receipt.selection != selection
            or admission.attempt < receipt.action_attempt
            or bound not in eligible
        ):
            raise ValueError("candidate_action_current_owner_binding_mismatch")
        _pointer, selector = bridge._read_action_selector(
            closure, selection, receipt.action_phase_ref
        )
        if (
            selector.candidate_budget_window_id != receipt.candidate_budget_window_id
            or selector.candidate_budget_window_digest != receipt.candidate_budget_window_digest
        ):
            raise ValueError("candidate_action_budget_window_changed")
        # An older attempt is recoverable only after this exact receipt was selected.
        if admission.attempt > receipt.action_attempt and (
            selector.state not in {"prepared", "selected"}
            or selector.receipt_kind != CANDIDATE_ACTION_KIND
            or selector.receipt_ref != str(receipt_ref.artifact_id)
            or selector.candidate_receipt_ref != receipt_ref
        ):
            raise ValueError("candidate_action_prior_attempt_not_selected")
    return receipt


__all__ = [
    "CANDIDATE_ACTION_KIND",
    "CANDIDATE_ACTION_SCHEMA",
    "CandidateAcquisitionActionReceipt",
    "persist_candidate_acquisition_action",
    "read_candidate_acquisition_action",
    "receipt_inputs",
    "validate_candidate_action_source_binding",
]
