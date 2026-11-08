"""Bind a modeled candidate source to one real, currently leased acquisition action.

This receipt identifies input custody for candidate simulation.  It is not an
observed-data passport, semantic epoch admission, or a claim-evidence grant.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts
from polisyos.data_requirement import DataRequirementCompilationReport
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionCandidateSourceRoute
from polisyos.runtime.quality.candidate_acquisition_source import (
    CANDIDATE_ACQUISITION_SOURCE_KIND,
    CandidateAcquisitionSource,
    persist_candidate_acquisition_source,
    read_candidate_acquisition_source,
)

if TYPE_CHECKING:
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIRouteExecutionBinding,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import (
        ControlPlaneService,
        VerifiedAcquisitionActionOutcome,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionActionHeadRecord,
        ControlJobExecutionAdmission,
    )
    from polisyos.runtime.quality.acquisition_executor import LiveSourceExecutionEvidence
    from polisyos.runtime.quality.acquisition_planner import AcquisitionRequirementBasisBinding
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
        AcquisitionRoutePhaseReceipt,
        VerifiedAcquisitionRouteClosure,
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
    )
    from polisyos.scientist.orchestration.engine import BudgetLedgerReentryBudgetWindow

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


@dataclass(frozen=True)
class _VerifiedCurrentCandidateExperimentReentryAction:
    """Keep one current reentry proof and its verified budget window together."""

    selection: AcquisitionCandidateSourceRoute
    phase: AcquisitionCandidateExperimentPhaseReceipt
    admission: ControlJobExecutionAdmission
    action: CandidateAcquisitionActionReceipt
    head: AcquisitionActionHeadRecord
    outcome: VerifiedAcquisitionActionOutcome
    budget_window: BudgetLedgerReentryBudgetWindow


@dataclass(frozen=True)
class _CurrentCandidateExperimentActionContext:
    """Carry one owner-replayed action snapshot into its reentry consumer."""

    selection: AcquisitionCandidateSourceRoute
    phase: AcquisitionCandidateExperimentPhaseReceipt
    admission: ControlJobExecutionAdmission
    outcome: VerifiedAcquisitionActionOutcome
    action: CandidateAcquisitionActionReceipt | None


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
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoop

    service = _require_canonical_action_bridge(bridge)
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


def _require_canonical_action_bridge(
    bridge: AcquisitionWorldGrowthBridge,
) -> ControlPlaneService:
    """Require the bridge's exact composed Control and artifact owners."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge

    service = getattr(bridge, "_source_control_service", None)
    if (
        type(bridge) is not AcquisitionWorldGrowthBridge
        or type(service) is not ControlPlaneService
        or service._control_store is not bridge.control_store
        or service._artifact_store is not bridge.artifact_store
        or service._diagnostic_event_log is not bridge.event_log
        or service.acquisition_route_sink is not bridge.action_head_sink
    ):
        raise TypeError("candidate_action_canonical_bridge_required")
    return service


def _select_current_candidate_experiment_outcome(
    outcomes: tuple[VerifiedAcquisitionActionOutcome, ...],
    *,
    origin: VerifiedCandidateExperimentOrigin,
    action_job_id: str,
    action_generation: int,
    receipt_ref: str | None = None,
    required_phase: str | None = None,
) -> VerifiedAcquisitionActionOutcome:
    """Select one exact current action from the canonical owner's verified history.

    This pure projection consumes already owner-replayed outcomes and prefix;
    it does not authenticate supplied rows, authorize effects, or replace the
    independent live lease and source checks of its consumers.
    """
    from polisyos.runtime.http.services.control.run_lifecycle import (
        VerifiedAcquisitionActionOutcome,
    )
    from polisyos.runtime.quality.acquisition_evaluation import CandidateExperimentTerminalHistory
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceipt,
        VerifiedCandidateExperimentOrigin,
    )

    if type(origin) is not VerifiedCandidateExperimentOrigin or type(outcomes) is not tuple:
        raise ValueError("candidate_experiment_action_history_not_verified")
    prefix = origin.candidate_terminal_history_chain
    if (
        type(action_generation) is not int
        or action_generation != len(prefix) + 1
        or len(outcomes) != action_generation
        or any(type(item) is not VerifiedAcquisitionActionOutcome for item in outcomes)
        or any(
            (
                item.head.tenant_id,
                item.head.cell_id,
                item.head.run_id,
                item.head.source_job_id,
                item.head.route_id,
            )
            != (
                origin.tenant_id,
                origin.cell_id,
                origin.run_id,
                origin.source_job_id,
                origin.route_id,
            )
            for item in outcomes
        )
        or tuple(item.head.action_generation for item in outcomes)
        != tuple(range(1, action_generation + 1))
    ):
        raise ValueError("candidate_experiment_action_history_not_current")
    for history, outcome in zip(prefix, outcomes[:-1], strict=True):
        if (
            type(history) is not CandidateExperimentTerminalHistory
            or type(outcome.latest_receipt) is not AcquisitionCandidateExperimentTerminalReceipt
            or outcome.head != history.head
            or outcome.latest_receipt != history.terminal
            or outcome.candidate_experiment_terminal_history != history
        ):
            raise ValueError("candidate_experiment_action_prefix_changed")
    outcome = outcomes[-1]
    head = outcome.head
    phase = outcome.latest_receipt
    if (
        (head.tenant_id, head.cell_id, head.run_id, head.source_job_id, head.route_id)
        != (origin.tenant_id, origin.cell_id, origin.run_id, origin.source_job_id, origin.route_id)
        or head.job_id != action_job_id
        or head.action_generation != action_generation
        or phase.job_id != action_job_id
        or phase.action_generation != action_generation
        or head.receipt_ref != head.receipt_sha256
        or (receipt_ref is not None and head.receipt_ref != receipt_ref)
        or (required_phase is not None and head.receipt_phase != required_phase)
        or phase.receipt_phase != head.receipt_phase
        or not outcome.phase_chain
        or outcome.phase_chain[-1].receipt != phase
        or outcome.phase_chain[-1].receipt_ref != head.receipt_ref
    ):
        raise ValueError("candidate_experiment_action_phase_not_current")
    return outcome


def _candidate_experiment_source_selection(
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
) -> AcquisitionCandidateSourceRoute:
    """Derive the typed source selection from its current experiment owners."""
    from polisyos.data_requirement import DataRequirementCompilationReport
    from polisyos.fabric import data_plane
    from polisyos.runtime.http.services.acquisition_action_service import AcquisitionActionService
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
        _resolve_world_bank_wdi_source_attempts,
        build_production_world_bank_wdi_execution_port,
    )
    from polisyos.runtime.quality.acquisition_executor import (
        LiveCatalogExecutionConstraints,
        _prepare_live_catalog_authorization,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        VerifiedCandidateExperimentOrigin,
        _CandidateExperimentSourceIdentity,
    )
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        resolve_current_candidate_unpriced_policy,
        verify_candidate_unpriced_experiment_policy_intent,
    )
    from polisyos.runtime.quality.candidate_acquisition_source import (
        validate_candidate_acquisition_selection,
    )
    from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref

    if type(origin) is not VerifiedCandidateExperimentOrigin:
        raise TypeError("candidate_experiment_origin_untyped")
    service = _require_canonical_action_bridge(bridge)
    scope = origin.policy_scope
    problem = origin.design_problem_basis
    try:
        selected_ref, policy = resolve_current_candidate_unpriced_policy(
            control_service=service, scope=scope
        )
        experiment_evidence = verify_candidate_unpriced_experiment_policy_intent(
            control_service=service,
            closure=_CandidateExperimentSourceIdentity(
                tenant_id=origin.tenant_id,
                cell_id=origin.cell_id,
                run_id=origin.run_id,
                source_job_id=origin.source_job_id,
                source_payload_ref=origin.source_payload_ref,
                capability_manifest_ref=origin.capability_manifest_ref,
            ),
            scope=scope,
            policy_ref=origin.policy_ref,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("candidate_experiment_source_policy_not_current") from exc
    if (
        selected_ref != origin.policy_ref
        or policy.purpose != "bounded_candidate_experiment_voi_unknown"
        or policy.configured_template is None
        or policy.scope != scope
        or policy.source_payload_ref != origin.source_payload_ref
        or policy.request_content_hash != origin.request_content_hash
        or policy.original_metered_budget_usd != experiment_evidence.run_budget_usd
        or experiment_evidence.request_content_hash != origin.request_content_hash
        or experiment_evidence.run_budget_usd is None
        or experiment_evidence.run_budget_usd <= 0
    ):
        raise ValueError("candidate_experiment_source_policy_changed")

    handler = getattr(service, "_acquisition_job_handler", None)
    action_service = getattr(handler, "__self__", None)
    live_port = getattr(action_service, "_production_execution_port", None)
    if (
        type(action_service) is not AcquisitionActionService
        or action_service.control_service is not service
        or type(live_port) is not WorldBankWDIAcquisitionExecutionPort
        or action_service._execution_port is not live_port
        or live_port._world_growth_bridge is not bridge
        or live_port._artifact_store is not bridge.artifact_store
    ):
        raise ValueError("candidate_experiment_source_execution_owner_not_current")
    current_port = build_production_world_bank_wdi_execution_port(control_service=service)
    if (
        type(current_port) is not WorldBankWDIAcquisitionExecutionPort
        or current_port._artifact_store is not bridge.artifact_store
        or current_port._registry != live_port._registry
        or current_port._provision != live_port._provision
        or current_port._provision_content_sha256 != live_port._provision_content_sha256
    ):
        raise ValueError("candidate_experiment_source_authority_changed")
    template = policy.configured_template
    if (
        template.authority_registry_sha256 != current_port._registry.content_sha256
        or template.authority_provision_sha256 != current_port._provision_content_sha256
    ):
        raise ValueError("candidate_experiment_source_template_authority_changed")

    try:
        variable_id, entry_id, constraints, attempts = _resolve_world_bank_wdi_source_attempts(
            source=origin,
            authority=current_port._authority,
            registry=current_port._registry,
            provision=current_port._provision,
            provision_content_sha256=current_port._provision_content_sha256,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("candidate_experiment_source_attempt_not_current") from exc
    selected_authorization = policy.select_source_authorization(origin.source_attempt_prefix)
    selected_attempts = tuple(
        attempt
        for attempt, _receipt in attempts
        if attempt.attempt_id == selected_authorization.attempt_id
    )
    if entry_id != template.authority_entry_id or len(selected_attempts) != 1:
        raise ValueError("candidate_experiment_source_attempt_changed")
    bounded = LiveCatalogExecutionConstraints.model_validate(
        {
            **constraints.model_dump(),
            "max_response_bytes": min(
                constraints.max_response_bytes, template.max_http_response_bytes
            ),
            "max_decompressed_bytes": min(
                constraints.max_decompressed_bytes, template.max_http_decompressed_bytes
            ),
            "timeout_cap_seconds": min(
                constraints.timeout_cap_seconds, template.max_http_timeout_seconds
            ),
        }
    )
    try:
        prepared = _prepare_live_catalog_authorization(
            authority=current_port._authority,
            entry_id=entry_id,
            attempt_id=selected_authorization.attempt_id,
            constraints=bounded,
            registry_providers=service._registry_providers,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("candidate_experiment_source_authorization_not_current") from exc
    if type(selected_authorization) is not data_plane.LiveExecutionAuthorization or (
        prepared.authorization != selected_authorization
    ):
        raise ValueError("candidate_experiment_source_authorization_changed")

    compilation = DataRequirementCompilationReport.model_validate(
        artifacts.load_core_json_artifact(bridge.artifact_store, scope.compiler_report_ref)
    )
    specs = tuple(
        spec for spec in compilation.specs if spec.requirement_id == scope.compiled_requirement_ref
    )
    if len(specs) != 1:
        raise ValueError("candidate_experiment_source_requirement_not_unique")
    spec = specs[0]
    if (
        scope.compiled_requirement_ref != origin.planner_record.compiled_requirement_ref
        or not spec.scope.population
    ):
        raise ValueError("candidate_experiment_source_requirement_scope_mismatch")
    try:
        candidate, resolved_source = validate_candidate_acquisition_selection(
            bridge.artifact_store,
            requirement_basis_binding=origin.planner_report.requirement_basis_binding,
            compiled_requirement_ref=scope.compiled_requirement_ref,
            requirement_id=scope.requirement_id,
            candidate_digest=scope.candidate_digest,
            authority=current_port._authority,
            entry_id=entry_id,
            target_slot_id=variable_id,
            country_code=bounded.country_code,
            year=bounded.start_year,
            population=spec.scope.population,
        )
        live_resolved_source = live_port._authority.resolve(entry_id)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("candidate_experiment_source_selection_not_current") from exc
    if (
        candidate.content_digest != scope.candidate_digest
        or resolved_source != live_resolved_source
    ):
        raise ValueError("candidate_experiment_source_entry_changed")
    return AcquisitionCandidateSourceRoute(
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        run_id=origin.run_id,
        route_id=origin.route_id,
        design_problem_ref=scope.design_problem_ref,
        compiled_requirement_ref=scope.compiled_requirement_ref,
        requirement_id=scope.requirement_id,
        candidate_digest=scope.candidate_digest,
        profile_selection_ref=cycle_job_profile_selection_ref(problem),
        canonical_variable_id=variable_id,
        target_slot_id=variable_id,
        country_code=constraints.country_code,
        year=constraints.start_year,
        population=spec.scope.population,
        reentry_budget_usd=min(
            policy.configured_template.max_metered_reentry_usd,
            experiment_evidence.run_budget_usd,
        ),
    )


def _same_candidate_experiment_origin_source(
    supplied: VerifiedCandidateExperimentOrigin,
    current: VerifiedCandidateExperimentOrigin,
) -> bool:
    """Compare every immutable source field while resolving the action head separately."""
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedCandidateExperimentOrigin

    return (
        type(supplied) is VerifiedCandidateExperimentOrigin
        and type(current) is VerifiedCandidateExperimentOrigin
        and replace(supplied, current_action_head=None)
        == replace(current, current_action_head=None)
    )


def _selected_candidate_experiment_phase_ref(
    bridge: AcquisitionWorldGrowthBridge,
    phase: AcquisitionCandidateExperimentPhaseReceipt,
    phase_ref: str,
) -> artifacts.ArtifactRef:
    """Resolve the selected full CAS view for one exact typed experiment phase."""
    from polisyos.core.artifacts import artifact_ref_for_manifest

    if not re.fullmatch(r"sha256:[0-9a-f]{64}", phase_ref):
        raise ValueError("candidate_experiment_phase_ref_invalid")
    manifest = bridge.artifact_store.get_manifest(phase_ref)
    selected_ref = artifact_ref_for_manifest(manifest)
    if (
        str(selected_ref.artifact_id) != phase_ref
        or selected_ref.manifest_profile_sha256 is None
        or manifest.kind != "runtime_quality.acquisition_candidate_experiment_phase_receipt"
        or artifacts.load_core_json_artifact(bridge.artifact_store, selected_ref)
        != phase.model_dump(mode="json")
    ):
        raise ValueError("candidate_experiment_phase_profile_unselected")
    return selected_ref


def _current_candidate_experiment_action_context(
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
    action_phase_ref: str,
    *,
    required_phase: Literal["executing", "candidate_input_reentry_pending"] = "executing",
    candidate_action_ref: artifacts.ArtifactRef | None = None,
    defer_historical_reentry: bool = False,
) -> _CurrentCandidateExperimentActionContext:
    """Resolve the exact current phase and preserve its verified action snapshot."""
    from polisyos.core.artifacts import artifact_ref_for_manifest
    from polisyos.runtime.http.services.control_plane_store import ControlJobExecutionAdmission
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
        AcquisitionRouteLoop,
        _ResolvedCurrentCandidateExperiment,
    )

    service = _require_canonical_action_bridge(bridge)
    if (
        not isinstance(action_phase_ref, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", action_phase_ref) is None
    ):
        raise ValueError("candidate_experiment_action_phase_ref_invalid")
    if bridge.control_store is None:
        raise ValueError("candidate_experiment_action_live_job_not_established")
    if defer_historical_reentry and required_phase != "candidate_input_reentry_pending":
        raise ValueError("candidate_experiment_reentry_phase_invalid")

    loop = AcquisitionRouteLoop(
        control_store=bridge.control_store,
        artifact_store=bridge.artifact_store,
        event_log=bridge.event_log,
        core_source_resolver=service.resolve_completed_control_job_core_run_source,
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        action_outcome_reader=service.acquisition_route_sink,
    )
    try:
        resolution = loop._resolve_current_candidate_experiment_resolution(run_id=origin.run_id)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("candidate_experiment_action_source_not_current") from exc
    if type(resolution) is not _ResolvedCurrentCandidateExperiment:
        raise ValueError("candidate_experiment_action_source_not_current")
    current_origin = resolution.origin
    if current_origin.current_action_head is None or not _same_candidate_experiment_origin_source(
        origin, current_origin
    ):
        raise ValueError("candidate_experiment_action_source_changed")
    selected = _candidate_experiment_source_selection(bridge, current_origin)

    outcomes = resolution.outcomes
    head = current_origin.current_action_head
    outcome = _select_current_candidate_experiment_outcome(
        outcomes,
        origin=current_origin,
        action_job_id=head.job_id,
        action_generation=head.action_generation,
        receipt_ref=action_phase_ref,
        required_phase=required_phase,
    )
    if type(outcome.latest_receipt) is not AcquisitionCandidateExperimentPhaseReceipt:
        raise ValueError("candidate_experiment_action_phase_not_current")
    phase_record = outcome.phase_chain[-1]
    phase = outcome.latest_receipt
    if (
        phase_record.receipt_ref != action_phase_ref
        or phase_record.receipt != phase
        or phase.receipt_phase != required_phase
        or (
            required_phase == "executing"
            and (
                outcome.executing_phase_ref != action_phase_ref
                or outcome.executing_phase != phase
                or candidate_action_ref is not None
            )
        )
        or (
            required_phase == "candidate_input_reentry_pending"
            and (
                candidate_action_ref is None
                or phase.candidate_receipt_ref != candidate_action_ref
                or candidate_action_ref.kind != CANDIDATE_ACTION_KIND
                or candidate_action_ref.manifest_profile_sha256 is None
            )
        )
        or phase.tenant_id != origin.tenant_id
        or phase.cell_id != origin.cell_id
        or phase.run_id != origin.run_id
        or phase.source_job_id != origin.source_job_id
        or phase.route_id != origin.route_id
        or phase.source_payload_ref != origin.source_payload_ref
        or phase.capability_manifest_ref != origin.capability_manifest_ref
        or phase.request_content_hash != origin.request_content_hash
        or phase.policy_scope != origin.policy_scope
        or phase.policy_ref != origin.policy_ref
        or phase.action_generation != head.action_generation
        or phase.job_id != head.job_id
    ):
        raise ValueError("candidate_experiment_action_phase_binding_mismatch")

    receipt: CandidateAcquisitionActionReceipt | None = None
    if required_phase == "candidate_input_reentry_pending":
        if candidate_action_ref is None:
            raise ValueError("candidate_experiment_reentry_action_missing")
        payload = artifacts.load_core_json_artifact(bridge.artifact_store, candidate_action_ref)
        receipt = CandidateAcquisitionActionReceipt.model_validate(payload)
        executing_records = tuple(
            record
            for record in outcome.phase_chain
            if getattr(record, "receipt_ref", None) == receipt.action_phase_ref
        )
        if len(executing_records) != 1:
            raise ValueError("candidate_experiment_reentry_executing_phase_missing")
        executing_phase = getattr(executing_records[0], "receipt", None)
        if type(executing_phase) is not AcquisitionCandidateExperimentPhaseReceipt:
            raise ValueError("candidate_experiment_reentry_executing_phase_untyped")
        selected_phase_ref = artifact_ref_for_manifest(
            bridge.artifact_store.get_manifest(receipt.action_phase_ref)
        )
        if str(selected_phase_ref.artifact_id) != receipt.action_phase_ref:
            raise ValueError("candidate_experiment_reentry_phase_profile_missing")
        if not defer_historical_reentry:
            read_candidate_experiment_acquisition_action_historical(
                bridge=bridge,
                origin=current_origin,
                receipt_ref=candidate_action_ref,
                executing_phase=executing_phase,
                executing_phase_ref=receipt.action_phase_ref,
            )

    admission = bridge.control_store.current_execution_job_admission()
    job = admission.job
    if (
        type(admission) is not ControlJobExecutionAdmission
        or job.kind != "acquisition"
        or job.state != "running"
        or job.run_id != origin.run_id
        or job.job_id != phase.job_id
        or admission.scope.status != "established"
        or admission.scope.actor_authenticated is not True
        or not admission.scope.actor_subject
        or admission.scope.tenant_id != origin.tenant_id
        or admission.scope.cell_id != origin.cell_id
    ):
        raise ValueError("candidate_experiment_action_live_job_scope_mismatch")
    current_head = bridge.control_store.get_acquisition_action_head(
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        run_id=origin.run_id,
        source_job_id=origin.source_job_id,
        route_id=origin.route_id,
        action_generation=head.action_generation,
    )
    after = bridge.control_store.current_execution_job_admission()
    if current_head != head or not after.same_execution_identity(admission):
        raise ValueError("candidate_experiment_action_live_owner_changed")
    # Reentry consumes this fresh outcome for its historical receipt read. Fold
    # after the final source selection, at the last boundary before that read.
    if defer_historical_reentry and (
        _candidate_experiment_source_selection(bridge, current_origin) != selected
    ):
        raise ValueError("candidate_experiment_action_live_owner_changed")
    try:
        current_outcomes = service.acquisition_route_sink.experiment_action_outcomes(
            tenant_id=origin.tenant_id,
            cell_id=origin.cell_id,
            run_id=origin.run_id,
            source_job_id=origin.source_job_id,
            route_id=origin.route_id,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("candidate_experiment_action_history_not_verified") from exc
    if current_outcomes != outcomes or (
        not defer_historical_reentry
        and _candidate_experiment_source_selection(bridge, current_origin) != selected
    ):
        raise ValueError("candidate_experiment_action_live_owner_changed")
    return _CurrentCandidateExperimentActionContext(
        selection=selected,
        phase=phase,
        admission=admission,
        outcome=current_outcomes[-1],
        action=receipt,
    )


def _current_candidate_experiment_action(
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
    action_phase_ref: str,
    *,
    required_phase: Literal["executing", "candidate_input_reentry_pending"] = "executing",
    candidate_action_ref: artifacts.ArtifactRef | None = None,
) -> tuple[
    AcquisitionCandidateSourceRoute,
    AcquisitionCandidateExperimentPhaseReceipt,
    ControlJobExecutionAdmission,
]:
    """Resolve the exact current experiment phase and separate live acquisition lease."""
    context = _current_candidate_experiment_action_context(
        bridge,
        origin,
        action_phase_ref,
        required_phase=required_phase,
        candidate_action_ref=candidate_action_ref,
    )
    return context.selection, context.phase, context.admission


def _current_candidate_experiment_reentry_action_context(
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
    pending_phase_ref: str,
    candidate_action_ref: artifacts.ArtifactRef,
) -> _VerifiedCurrentCandidateExperimentReentryAction:
    """Resolve one pending action, live lease, and the window bound to its receipt."""
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
    )

    action_context = _current_candidate_experiment_action_context(
        bridge,
        origin,
        pending_phase_ref,
        required_phase="candidate_input_reentry_pending",
        candidate_action_ref=candidate_action_ref,
        defer_historical_reentry=True,
    )
    selection = action_context.selection
    phase = action_context.phase
    admission = action_context.admission
    if type(phase) is not AcquisitionCandidateExperimentPhaseReceipt:
        raise ValueError("candidate_experiment_reentry_phase_untyped")
    receipt = action_context.action
    if type(receipt) is not CandidateAcquisitionActionReceipt:
        raise ValueError("candidate_experiment_reentry_action_changed")
    executing_refs = tuple(
        record
        for record in action_context.outcome.phase_chain
        if getattr(record, "receipt_ref", None) == receipt.action_phase_ref
    )
    if len(executing_refs) != 1 or getattr(executing_refs[0], "receipt", None) is None:
        raise ValueError("candidate_experiment_reentry_executing_phase_missing")
    executing_phase = getattr(executing_refs[0], "receipt", None)
    if type(executing_phase) is not AcquisitionCandidateExperimentPhaseReceipt:
        raise ValueError("candidate_experiment_reentry_executing_phase_untyped")
    verified_receipt, _source, window = read_candidate_experiment_acquisition_action_historical(
        bridge=bridge,
        origin=origin,
        receipt_ref=candidate_action_ref,
        executing_phase=executing_phase,
        executing_phase_ref=receipt.action_phase_ref,
    )
    if verified_receipt != receipt or receipt.selection != selection:
        raise ValueError("candidate_experiment_reentry_action_changed")
    return _VerifiedCurrentCandidateExperimentReentryAction(
        selection=selection,
        phase=phase,
        admission=admission,
        action=receipt,
        head=action_context.outcome.head,
        outcome=action_context.outcome,
        budget_window=window,
    )


def _current_candidate_experiment_reentry_action(
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
    pending_phase_ref: str,
    candidate_action_ref: artifacts.ArtifactRef,
) -> tuple[
    AcquisitionCandidateSourceRoute,
    AcquisitionCandidateExperimentPhaseReceipt,
    ControlJobExecutionAdmission,
    CandidateAcquisitionActionReceipt,
]:
    """Resolve a pending reentry action while preserving the established tuple API."""
    context = _current_candidate_experiment_reentry_action_context(
        bridge,
        origin,
        pending_phase_ref,
        candidate_action_ref,
    )
    return context.selection, context.phase, context.admission, context.action


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


def persist_candidate_experiment_acquisition_action(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
    binding: WorldBankWDIRouteExecutionBinding,
    evidence: LiveSourceExecutionEvidence,
    action_phase_ref: str,
) -> tuple[artifacts.ArtifactRef, CandidateAcquisitionActionReceipt]:
    """Persist a candidate source under the exact experiment phase and live lease."""
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIRouteExecutionBinding,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
    )
    from polisyos.runtime.quality.agent_action_authority import reconcile_authority_ref
    from polisyos.runtime.quality.candidate_acquisition_source import (
        validate_candidate_acquisition_selection,
    )

    if type(binding) is not WorldBankWDIRouteExecutionBinding:
        raise TypeError("candidate_experiment_route_binding_untyped")
    selection, phase, admission = _current_candidate_experiment_action(
        bridge, origin, action_phase_ref
    )
    if type(phase) is not AcquisitionCandidateExperimentPhaseReceipt:
        raise ValueError("candidate_experiment_phase_untyped")
    _pointer, selector = bridge._load_action_selector(selection, action_phase_ref)
    if (
        selector is None
        or selector.state != "executing"
        or selector.candidate_budget_window_id is None
        or selector.candidate_budget_window_digest is None
    ):
        raise ValueError("candidate_experiment_budget_window_missing")
    if (
        binding.tenant_id != origin.tenant_id
        or binding.cell_id != origin.cell_id
        or binding.run_id != origin.run_id
        or binding.route_id != origin.route_id
        or binding.target_variable != selection.target_slot_id
        or binding.constraints.country_code != selection.country_code
        or binding.constraints.start_year != selection.year
        or binding.constraints.end_year != selection.year
        or evidence.authorization.attempt_id != binding.attempt_id
    ):
        raise ValueError("candidate_experiment_execution_binding_mismatch")
    basis = origin.planner_report.requirement_basis_binding
    if basis is None:
        raise ValueError("candidate_experiment_compiler_basis_missing")
    candidate, resolved_source = validate_candidate_acquisition_selection(
        bridge.artifact_store,
        requirement_basis_binding=basis,
        compiled_requirement_ref=selection.compiled_requirement_ref,
        requirement_id=selection.requirement_id,
        candidate_digest=selection.candidate_digest,
        authority=bridge.authority,
        entry_id=binding.authority_entry_id,
        target_slot_id=selection.target_slot_id,
        country_code=selection.country_code,
        year=selection.year,
        population=selection.population,
    )
    if candidate.content_digest != selection.candidate_digest:
        raise ValueError("candidate_experiment_compiler_candidate_changed")
    if binding.authority_entry_id != resolved_source.entry.entry_id:
        raise ValueError("candidate_experiment_execution_entry_changed")
    source_ref = persist_candidate_acquisition_source(
        bridge.artifact_store,
        authority=bridge.authority,
        entry_id=binding.authority_entry_id,
        live_source_execution=evidence,
        requirement_basis_binding=basis,
        requirement_id=selection.requirement_id,
        candidate_digest=selection.candidate_digest,
        target_slot_id=selection.target_slot_id,
        country_code=selection.country_code,
        year=selection.year,
        population=selection.population,
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        run_id=origin.run_id,
        job_id=phase.job_id,
        route_id=origin.route_id,
    )
    source = read_candidate_acquisition_source(
        bridge.artifact_store, source_ref=source_ref, authority=bridge.authority
    )
    if source.resolved_source != resolved_source:
        raise ValueError("candidate_experiment_source_entry_changed")
    phase_ref = artifacts.artifact_ref_for_manifest(
        bridge.artifact_store.get_manifest(action_phase_ref)
    )
    if (
        str(phase_ref.artifact_id) != action_phase_ref
        or phase_ref.manifest_profile_sha256 is None
        or artifacts.load_core_json_artifact(bridge.artifact_store, phase_ref)
        != phase.model_dump(mode="json")
        or reconcile_authority_ref(
            artifact_store=bridge.artifact_store,
            event_log=bridge.event_log,
            cas_ref=phase_ref,
            expected_tenant_id=origin.tenant_id,
            expected_cell_id=origin.cell_id,
            expected_run_id=origin.run_id,
            expected_job_id=phase.job_id,
        ).durable_event_id
        is None
    ):
        raise ValueError("candidate_experiment_phase_profile_unselected")
    receipt = CandidateAcquisitionActionReceipt(
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        run_id=origin.run_id,
        source_job_id=origin.source_job_id,
        action_job_id=phase.job_id,
        action_generation=phase.action_generation,
        action_attempt=admission.attempt,
        selection=selection,
        candidate_budget_window_id=selector.candidate_budget_window_id,
        candidate_budget_window_digest=selector.candidate_budget_window_digest,
        route_id=origin.route_id,
        action_phase_ref=action_phase_ref,
        selected_action_phase_ref=phase_ref,
        decision_ref=str(phase.authority_decision_ref.artifact_id),
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
    selected_ref = bridge._persist_candidate_experiment_receipt(
        origin=origin,
        payload=receipt.model_dump(mode="json"),
        kind=CANDIDATE_ACTION_KIND,
        schema=CANDIDATE_ACTION_SCHEMA,
        phase="candidate_input_prepared",
        artifact_inputs=receipt_inputs(receipt),
    )
    read_candidate_experiment_acquisition_action(
        bridge=bridge,
        origin=origin,
        receipt_ref=selected_ref,
        require_current_action=True,
    )
    selection_after, phase_after, admission_after = _current_candidate_experiment_action(
        bridge, origin, action_phase_ref
    )
    _pointer_after, selector_after = bridge._load_action_selector(selection_after, action_phase_ref)
    if (
        selection_after != selection
        or phase_after != phase
        or admission_after.job.job_id != admission.job.job_id
        or admission_after.job.lease_owner != admission.job.lease_owner
        or admission_after.attempt != admission.attempt
        or admission_after.scope != admission.scope
        or selector_after != selector
    ):
        raise ValueError("candidate_experiment_execution_lease_changed")
    return selected_ref, receipt


def read_candidate_experiment_acquisition_action(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
    receipt_ref: artifacts.ArtifactRef,
    require_current_action: bool,
) -> CandidateAcquisitionActionReceipt:
    """Reopen the exact experiment action, source and phase parents."""
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.agent_action_authority import reconcile_authority_ref

    if (
        type(origin) is not VerifiedCandidateExperimentOrigin
        or receipt_ref.kind != CANDIDATE_ACTION_KIND
        or receipt_ref.media_type != "application/json"
        or receipt_ref.manifest_profile_sha256 is None
        or artifacts.profile_bound_ref(bridge.artifact_store, receipt_ref) != receipt_ref
    ):
        raise ValueError("candidate_experiment_action_profile_unselected")
    payload = artifacts.load_core_json_artifact(bridge.artifact_store, receipt_ref)
    receipt = CandidateAcquisitionActionReceipt.model_validate(payload)
    expected = receipt_inputs(receipt)
    manifest = bridge.artifact_store.get_manifest(receipt_ref)
    if (
        manifest.inputs != list(expected)
        or bridge._read(receipt_ref, CANDIDATE_ACTION_KIND, expected_inputs=expected) != payload
        or (
            receipt.tenant_id,
            receipt.cell_id,
            receipt.run_id,
            receipt.source_job_id,
            receipt.route_id,
        )
        != (
            origin.tenant_id,
            origin.cell_id,
            origin.run_id,
            origin.source_job_id,
            origin.route_id,
        )
        or str(receipt.selected_action_phase_ref.artifact_id) != receipt.action_phase_ref
    ):
        raise ValueError("candidate_experiment_action_parent_mismatch")
    event = reconcile_authority_ref(
        artifact_store=bridge.artifact_store,
        event_log=bridge.event_log,
        cas_ref=receipt_ref,
        expected_tenant_id=origin.tenant_id,
        expected_cell_id=origin.cell_id,
        expected_run_id=origin.run_id,
        expected_job_id=origin.source_job_id,
    )
    if event.durable_event_id is None:
        raise ValueError("candidate_experiment_action_event_missing")
    outcomes = bridge.action_head_sink.experiment_action_outcomes(
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        run_id=origin.run_id,
        source_job_id=origin.source_job_id,
        route_id=origin.route_id,
    )
    outcome = _select_current_candidate_experiment_outcome(
        outcomes,
        origin=origin,
        action_job_id=receipt.action_job_id,
        action_generation=receipt.action_generation,
    )
    matching = tuple(
        record
        for record in outcome.phase_chain
        if getattr(record, "receipt_ref", None) == receipt.action_phase_ref
    )
    if len(matching) != 1:
        raise ValueError("candidate_experiment_action_phase_missing")
    phase = getattr(matching[0], "receipt", None)
    if (
        type(phase) is not AcquisitionCandidateExperimentPhaseReceipt
        or phase.receipt_phase != "executing"
        or phase.tenant_id != receipt.tenant_id
        or phase.cell_id != receipt.cell_id
        or phase.run_id != receipt.run_id
        or phase.source_job_id != receipt.source_job_id
        or phase.job_id != receipt.action_job_id
        or phase.action_generation != receipt.action_generation
        or str(phase.authority_decision_ref.artifact_id) != receipt.decision_ref
        or phase.policy_ref != origin.policy_ref
        or phase.policy_scope != origin.policy_scope
    ):
        raise ValueError("candidate_experiment_action_phase_binding_mismatch")
    source: CandidateAcquisitionSource = read_candidate_acquisition_source(
        bridge.artifact_store,
        source_ref=receipt.candidate_source_ref,
        authority=bridge.authority if require_current_action else None,
    )
    validate_candidate_action_source_binding(bridge.artifact_store, receipt, source)
    if (
        receipt.selection.compiled_requirement_ref != origin.policy_scope.compiled_requirement_ref
        or receipt.selection.requirement_id != origin.policy_scope.requirement_id
        or receipt.selection.candidate_digest != origin.policy_scope.candidate_digest
        or receipt.selection.design_problem_ref != origin.policy_scope.design_problem_ref
        or receipt.selection.profile_selection_ref != receipt.profile_selection_ref
        or receipt.candidate_source_ref.kind != CANDIDATE_ACQUISITION_SOURCE_KIND
    ):
        raise ValueError("candidate_experiment_action_source_binding_mismatch")
    if require_current_action:
        selection, current_phase, admission = _current_candidate_experiment_action(
            bridge, origin, receipt.action_phase_ref
        )
        _pointer, selector = bridge._load_action_selector(selection, receipt.action_phase_ref)
        if (
            selection != receipt.selection
            or current_phase != phase
            or admission.job.job_id != receipt.action_job_id
            or admission.attempt < receipt.action_attempt
            or selector is None
            or selector.candidate_budget_window_id != receipt.candidate_budget_window_id
            or selector.candidate_budget_window_digest != receipt.candidate_budget_window_digest
        ):
            raise ValueError("candidate_experiment_action_current_owner_mismatch")
    return receipt


def read_candidate_experiment_acquisition_action_historical(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
    receipt_ref: artifacts.ArtifactRef,
    executing_phase: AcquisitionCandidateExperimentPhaseReceipt,
    executing_phase_ref: str,
) -> tuple[
    CandidateAcquisitionActionReceipt,
    CandidateAcquisitionSource,
    BudgetLedgerReentryBudgetWindow,
]:
    """Reopen a historical experiment action and source without a live lease."""
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        resolve_current_candidate_unpriced_policy,
        verify_candidate_unpriced_experiment_policy_intent,
    )
    from polisyos.runtime.quality.agent_action_authority import reconcile_authority_ref
    from polisyos.scientist.orchestration.engine import (
        BudgetLedgerReentryBudgetScope,
        BudgetLedgerReentryBudgetWindow,
        BudgetMiddleware,
    )

    if (
        type(origin) is not VerifiedCandidateExperimentOrigin
        or type(executing_phase) is not AcquisitionCandidateExperimentPhaseReceipt
    ):
        raise ValueError("candidate_experiment_action_historical_profile_invalid")
    phase_ref = _selected_candidate_experiment_phase_ref(
        bridge, executing_phase, executing_phase_ref
    )
    if (
        executing_phase.receipt_phase != "executing"
        or receipt_ref.kind != CANDIDATE_ACTION_KIND
        or receipt_ref.media_type != "application/json"
        or receipt_ref.manifest_profile_sha256 is None
        or artifacts.profile_bound_ref(bridge.artifact_store, receipt_ref) != receipt_ref
    ):
        raise ValueError("candidate_experiment_action_historical_profile_invalid")
    payload = artifacts.load_core_json_artifact(bridge.artifact_store, receipt_ref)
    receipt = CandidateAcquisitionActionReceipt.model_validate(payload)
    manifest = bridge.artifact_store.get_manifest(receipt_ref)
    if (
        manifest.artifact_schema is None
        or manifest.artifact_schema
        != artifacts.SchemaInfo(name=CANDIDATE_ACTION_SCHEMA, version="1.1")
        or manifest.producer is None
        or manifest.producer.component != "polisyos.runtime.acquisition_world_growth"
        or manifest.inputs != list(receipt_inputs(receipt))
        or manifest.tenant_context is None
        or manifest.tenant_context.tenant_id != origin.tenant_id
        or manifest.tenant_context.cell_id != origin.cell_id
        or phase_ref != receipt.selected_action_phase_ref
        or str(phase_ref.artifact_id) != executing_phase_ref
        or artifacts.load_core_json_artifact(bridge.artifact_store, phase_ref)
        != executing_phase.model_dump(mode="json")
        or (
            receipt.tenant_id,
            receipt.cell_id,
            receipt.run_id,
            receipt.source_job_id,
            receipt.action_job_id,
            receipt.action_generation,
            receipt.route_id,
            receipt.action_phase_ref,
            receipt.decision_ref,
        )
        != (
            origin.tenant_id,
            origin.cell_id,
            origin.run_id,
            origin.source_job_id,
            executing_phase.job_id,
            executing_phase.action_generation,
            origin.route_id,
            executing_phase_ref,
            str(executing_phase.authority_decision_ref.artifact_id),
        )
        or executing_phase.policy_ref != origin.policy_ref
        or executing_phase.policy_scope != origin.policy_scope
        or receipt.selection.compiled_requirement_ref
        != origin.policy_scope.compiled_requirement_ref
        or receipt.selection.requirement_id != origin.policy_scope.requirement_id
        or receipt.selection.candidate_digest != origin.policy_scope.candidate_digest
        or receipt.selection.design_problem_ref != origin.policy_scope.design_problem_ref
        or receipt.profile_selection_ref != receipt.selection.profile_selection_ref
    ):
        raise ValueError("candidate_experiment_action_historical_binding_mismatch")
    reconciliation = reconcile_authority_ref(
        artifact_store=bridge.artifact_store,
        event_log=bridge.event_log,
        cas_ref=receipt_ref,
        expected_tenant_id=origin.tenant_id,
        expected_cell_id=origin.cell_id,
        expected_run_id=origin.run_id,
        expected_job_id=origin.source_job_id,
    )
    if reconciliation.durable_event_id is None:
        raise ValueError("candidate_experiment_action_historical_event_missing")
    phase_event = reconcile_authority_ref(
        artifact_store=bridge.artifact_store,
        event_log=bridge.event_log,
        cas_ref=phase_ref,
        expected_tenant_id=origin.tenant_id,
        expected_cell_id=origin.cell_id,
        expected_run_id=origin.run_id,
        expected_job_id=executing_phase.job_id,
    )
    if phase_event.durable_event_id is None:
        raise ValueError("candidate_experiment_phase_historical_event_missing")
    source = read_candidate_acquisition_source(
        bridge.artifact_store,
        source_ref=receipt.candidate_source_ref,
        authority=None,
    )
    validate_candidate_action_source_binding(bridge.artifact_store, receipt, source)
    if (
        source.tenant_id != origin.tenant_id
        or source.cell_id != origin.cell_id
        or source.run_id != origin.run_id
        or source.job_id != executing_phase.job_id
        or source.route_id != origin.route_id
    ):
        raise ValueError("candidate_experiment_source_historical_scope_mismatch")
    service = bridge._source_control_service
    if service is None or type(service._llm_producer_settlement_store) is not BudgetMiddleware:
        raise ValueError("candidate_experiment_budget_historical_owner_missing")
    policy_ref, policy = resolve_current_candidate_unpriced_policy(
        control_service=service, scope=origin.policy_scope
    )
    evidence = verify_candidate_unpriced_experiment_policy_intent(
        control_service=service,
        closure=origin,
        scope=origin.policy_scope,
        policy_ref=origin.policy_ref,
    )
    template = policy.configured_template
    if (
        policy_ref != origin.policy_ref
        or template is None
        or evidence.run_budget_usd is None
        or evidence.run_budget_usd <= 0
        or policy.original_metered_budget_usd != evidence.run_budget_usd
    ):
        raise ValueError("candidate_experiment_budget_historical_policy_changed")
    selected_authorization = policy.select_source_authorization(origin.source_attempt_prefix)
    if source.live_source_execution.authorization != selected_authorization:
        raise ValueError("candidate_experiment_source_historical_authorization_mismatch")
    budget_scope = BudgetLedgerReentryBudgetScope(
        run_binding=service.verify_acquisition_source_budget_owner(closure=origin),
        action_job_id=executing_phase.job_id,
        route_id=origin.route_id,
        action_generation=executing_phase.action_generation,
        action_phase_ref=executing_phase_ref,
        source_payload_ref=origin.source_payload_ref,
        profile_selection_ref=receipt.profile_selection_ref,
    )
    window = service._llm_producer_settlement_store.resolve_reentry_budget_window_safe(budget_scope)
    fresh_limit = min(template.max_metered_reentry_usd, evidence.run_budget_usd)
    if (
        type(window) is not BudgetLedgerReentryBudgetWindow
        or window.scope != budget_scope
        or window.window_id != receipt.candidate_budget_window_id
        or window.record_digest != receipt.candidate_budget_window_digest
        or window.fresh_limit_usd != fresh_limit
        or window.global_limit_usd != evidence.run_budget_usd
        or receipt.selection.reentry_budget_usd != fresh_limit
    ):
        raise ValueError("candidate_experiment_budget_historical_window_mismatch")
    return receipt, source, window


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
    "persist_candidate_experiment_acquisition_action",
    "read_candidate_acquisition_action",
    "read_candidate_experiment_acquisition_action",
    "read_candidate_experiment_acquisition_action_historical",
    "receipt_inputs",
    "validate_candidate_action_source_binding",
]
