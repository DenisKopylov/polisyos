"""Public routes runs module API."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

from polisyos.core.contracts.control import (
    ProductionApprovalOverrideRequest,
    ProductionApprovalRequest,
    ProductionApprovalResponse,
)
from polisyos.core.contracts.runtime import (
    AgentPipelineResponse,
    ArtifactLineageView,
    CompareCandidatesResponse,
    CompareRunResponse,
    RunCandidateSimulationAcquisitionHistoryEntry,
    RunCandidateSimulationChildProfileBinding,
    RunCandidateSimulationN5Observation,
    RunCandidateSimulationProjection,
    RunDetailsResponse,
    RunEvidenceContextResponse,
    RunEvidenceContextView,
    RunLineageResponse,
    RunNodesResponse,
    RunOperatorDiagnostic,
    RunQuantitiesResponse,
    RunRecursiveCycleBranchFailure,
    RunRecursiveCycleCheckpoint,
    RunsBatchRequest,
    RunsBatchResponse,
    RunsListResponse,
    RunTerminality,
    RunTimelineResponse,
    RunWorkflowResponse,
    SourceKind,
    TemporalScope,
    TemporalSurfaceSupport,
)
from polisyos.fabric.evidence.decision_data import (
    FabricDecisionDataResponse,
)
from polisyos.fabric.evidence.decision_data import (
    TemporalRef as FabricTemporalRef,
)
from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    ResourceBindingSpec,
    require_action_permission,
)
from polisyos.runtime.http.container import resolve_production_approval_resolver
from polisyos.runtime.http.dependencies import (
    RuntimeApiContext,
    build_meta,
    enforce_run_tenant_access,
    ensure_request_id,
    get_runtime_api_context,
    record_data_access_audit,
    require_access_scope,
    set_authz_resource,
)
from polisyos.runtime.http.errors import (
    bad_request,
    conflict,
    forbidden,
    not_found,
    service_unavailable,
    unprocessable_entity,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.resource_binding import (
    production_approval_inputs_from_bound_request,
)
from polisyos.runtime.http.response_policies import add_run_link_relations
from polisyos.runtime.http.services.authority_values import (
    RunAuthorityProjection,
    build_run_authority_projection,
)
from polisyos.runtime.http.services.case_inspection import CaseInspectionService
from polisyos.runtime.http.services.case_inspection_contracts import (
    CaseInspectionResponse,
)
from polisyos.runtime.http.services.channel_contracts import (
    RunDetailSnapshot,
    RunsListSnapshot,
    RunsListSnapshotPage,
    RunsListSnapshotRun,
    RunsLiveSnapshot,
    RunsStreamTimeout,
    validate_runs_channel_data_event,
)
from polisyos.runtime.http.services.human_decision_contracts import HumanDecisionWriteContext
from polisyos.runtime.http.services.human_decisions import HumanDecisionPersistenceError
from polisyos.runtime.http.services.lineage import LineageSurfaceAdmissionError
from polisyos.runtime.http.services.run_paper_contracts import (
    RunPaperPacket,
    RunPaperReplayConflictError,
    RunPaperReplayQuery,
    RunPaperReplaySyntaxError,
    RunPaperSourceError,
)
from polisyos.runtime.http.services.run_paper_projection import RunPaperProjectionService
from polisyos.runtime.http.step_up import (
    StepUpAssertionVerification,
    StepUpClass,
    require_step_up,
)
from polisyos.runtime.quality.approval import (
    ProductionApprovalIssuanceInput,
    ProductionApprovalResolutionError,
    build_resolved_production_approval_packet,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from fastapi import APIRouter, Depends, Query, Request, Response
    from fastapi.responses import StreamingResponse
else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi import APIRouter, Depends, Query, Request, Response
        from fastapi.responses import StreamingResponse
    except ModuleNotFoundError:  # pragma: no cover
        APIRouter = cast("Any", None)
        Depends = cast("Any", None)
        Query = cast("Any", None)
        Request = cast("Any", Any)
        Response = cast("Any", Any)
        StreamingResponse = cast("Any", Any)


def _build_router() -> APIRouter:
    if APIRouter is None:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("runtime HTTP routes require FastAPI to be installed")
    return APIRouter(prefix="/api/v1/runs", tags=["runtime-runs"])


router = _build_router()
_GET_RUN_PAPER_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_REVIEW,
    ResourceBindingSpec(
        source=ResourceBindingSource.TENANT_COLLECTION,
        resource_kind="runtime.run_paper",
        allow_empty_body=True,
    ),
)
_GET_CASE_INSPECTION_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_REVIEW,
    ResourceBindingSpec(
        source=ResourceBindingSource.TENANT_COLLECTION,
        resource_kind="runtime.case_inspection",
        allow_empty_body=True,
    ),
)
_GET_RUNS_BATCH_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_BATCH_READ,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_BATCH,
        resource_kind="runtime.run.batch",
        body_field="run_ids",
    ),
)
_CREATE_PRODUCTION_APPROVAL_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_PRODUCTION_APPROVAL_CREATE,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_PATH,
        resource_kind="runtime.run.production_approval",
        path_parameter="run_id",
    ),
)
_CREATE_PRODUCTION_APPROVAL_STEP_UP = require_step_up(
    StepUpClass.PRODUCTION_APPROVAL,
)


def _validated_production_approval_override(
    request: Request,
    body: ProductionApprovalRequest,
) -> ProductionApprovalOverrideRequest | None:
    """Bind override attribution to the verified step-up subject."""
    override = body.override
    if override is None:
        return None
    verification = getattr(request.state, "step_up_verification", None)
    if (
        type(verification) is not StepUpAssertionVerification
        or verification.context.step_up_class is not StepUpClass.PRODUCTION_APPROVAL
    ):
        raise forbidden(
            "Production approval override lacks a bound step-up proof",
            code="production_approval_override_step_up_unbound",
        )
    if override.reviewer_identity != verification.context.subject:
        raise forbidden(
            "Override reviewer identity must equal the verified step-up subject",
            code="production_approval_override_identity_mismatch",
        )
    if override.signature is not None:
        raise forbidden(
            "Client-asserted approval signatures are not authority",
            code="production_approval_client_signature_forbidden",
        )
    return override


def _candidate_simulation_refusal(
    *,
    run_id: str,
    limitation_code: str,
    source_ref: Any = None,
) -> RunCandidateSimulationProjection:
    """Build a strict refusal while keeping the authorized RunDetails readable."""
    return RunCandidateSimulationProjection(
        run_id=run_id,
        artifact_status="not_established",
        source_ref=source_ref,
        limitation_code=limitation_code,
    )


def _candidate_simulation_checkpoint(
    recursive_run: Any,
) -> RunRecursiveCycleCheckpoint | None:
    """Project only persisted recursive traversal state, preserving stop type."""
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveCycleFailedNode,
        RecursiveCycleNode,
        RecursiveCyclePendingNode,
        RecursiveGenerationCyclePartialRunV2,
        RecursiveGenerationCyclePartialRunV3,
    )

    if isinstance(recursive_run, RecursiveGenerationCyclePartialRunV2):
        completed = tuple(
            node.node_ref for node in recursive_run.nodes if isinstance(node, RecursiveCycleNode)
        )
        terminals = {
            node.node_ref: node.terminal.kind.value
            for node in recursive_run.nodes
            if isinstance(node, RecursiveCycleNode) and not node.child_refs
        }
        return RunRecursiveCycleCheckpoint(
            schema_version="policyos.runtime.recursive_cycle_checkpoint.v1",
            budget_stop_node_ref=recursive_run.budget_stop_node_ref,
            pending_frontier=recursive_run.frontier_node_refs,
            completed_design_refs=completed,
            leaf_terminal_kinds=terminals,
        )
    if isinstance(recursive_run, RecursiveGenerationCyclePartialRunV3):
        failed_nodes = tuple(
            node for node in recursive_run.nodes if isinstance(node, RecursiveCycleFailedNode)
        )
        completed = tuple(
            node.node_ref for node in recursive_run.nodes if isinstance(node, RecursiveCycleNode)
        )
        pending = tuple(
            node.node_ref
            for node in recursive_run.nodes
            if isinstance(node, RecursiveCyclePendingNode)
        )
        failures = tuple(
            RunRecursiveCycleBranchFailure(
                failed_branch_ref=node.node_ref,
                origin_node_ref=node.failure.origin_node_ref,
                stage=node.failure.stage,
                exception_type=node.failure.exception_type,
                error_code=node.failure.error_code,
                error_message=node.failure.error_message,
            )
            for node in failed_nodes
        )
        return RunRecursiveCycleCheckpoint(
            schema_version="policyos.runtime.recursive_cycle_checkpoint.v2",
            pending_frontier=pending,
            completed_design_refs=completed,
            leaf_terminal_kinds={
                node.node_ref: node.terminal.kind.value
                for node in recursive_run.nodes
                if isinstance(node, RecursiveCycleNode) and not node.child_refs
            },
            failed_branches=failures,
        )
    return None


def _candidate_acquisition_history_projection(
    *,
    compiled: Any,
    compiled_ref: Any,
    recursive_run: Any,
    store: Any,
    control_service: Any | None,
    core_run_id: str,
    control_job_id: str | None,
    source_status: str | None,
    tenant_id: str | None,
    cell_id: str | None,
) -> tuple[tuple[RunCandidateSimulationAcquisitionHistoryEntry, ...], str | None]:
    """Resolve persisted acquisition receipts without asserting route currentness."""
    if not tenant_id or not cell_id or not control_job_id:
        return (), "acquisition_n4_source_not_established"
    if control_service is None or getattr(control_service, "_artifact_store", None) is not store:
        return (), "acquisition_action_history_not_observed"

    control_store = getattr(control_service, "_control_store", None)
    event_log = getattr(control_service, "_diagnostic_event_log", None)
    list_heads = getattr(control_store, "list_acquisition_action_heads_for_source", None)
    source_resolver = getattr(
        control_service,
        "resolve_completed_control_job_core_run_source",
        None,
    )
    if not callable(list_heads) or not callable(source_resolver) or event_log is None:
        return (), "acquisition_action_history_not_observed"

    from polisyos.core.artifacts.manifest import artifact_ref_identity_key

    try:
        control_job = control_store.get_job(control_job_id)
        if (
            control_job is None
            or control_job.job_id != control_job_id
            or control_job.kind != "natural_language_run"
            or control_job.state != "completed"
            or not isinstance(control_job.run_id, str)
            or not control_job.run_id.strip()
        ):
            raise ValueError("acquisition_history_source_job_not_completed")
        completed_core_source = source_resolver(
            control_job,
            expected_control_run_id=control_job.run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        if (
            completed_core_source.run_id != core_run_id
            or completed_core_source.manifest.control_job_id != control_job_id
            or not any(
                artifact_ref_identity_key(output_ref) == artifact_ref_identity_key(compiled_ref)
                for output_ref in completed_core_source.manifest.outputs
            )
        ):
            raise ValueError("acquisition_history_compiled_output_not_job_owned")
        source_run_id = control_job.run_id
        source_job_id = control_job.job_id
        if compiled.n4_recursive_source_ref is not None and (
            source_status != "resolved"
            or compiled.n4_recursive_source_job_id != source_job_id
            or compiled.n4_recursive_source_run_id != source_run_id
            or compiled.n4_recursive_source_tenant_id != tenant_id
            or compiled.n4_recursive_source_cell_id != cell_id
        ):
            return (), "acquisition_n4_source_not_established"
        heads = list_heads(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=source_run_id,
            source_job_id=source_job_id,
        )
    except Exception:
        return (), "acquisition_action_history_integrity_not_established"
    if not heads:
        return (), "acquisition_action_history_not_observed"

    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionRouteLoopReceipt,
        AcquisitionRoutePhaseReceipt,
    )
    from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationN5InputV5
    from polisyos.runtime.quality.generation_cycle import AcquisitionOverlayReentryReceipt
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateScenarioSourceRecordV3,
        candidate_scenario_semantic_identity_hash,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import RecursiveCycleNode

    def _selected_ref(ref_id: str, *, kind: str) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=ArtifactID.model_validate(ref_id),
            kind=kind,
            media_type="application/json",
        )

    def _read_authority_payload(
        ref: ArtifactRef,
        *,
        expected_kind: str,
        expected_schema: str,
        expected_version: str,
        expected_job_id: str,
    ) -> tuple[Any, bytes, Any]:
        expected_producer = {
            "runtime_quality.acquisition_route_loop_receipt": (
                "polisyos.runtime.acquisition_route_loop"
            ),
            "runtime_quality.acquisition_overlay_reentry_receipt": (
                "polisyos.runtime.acquisition_world_growth"
            ),
        }.get(expected_kind)
        if expected_producer is None:
            raise ValueError("acquisition_history_artifact_kind_unsupported")
        if not store.verify(ref).ok:
            raise ValueError("acquisition_history_artifact_integrity_not_established")
        manifest = store.get_manifest(ref)
        schema = manifest.artifact_schema
        if (
            manifest.kind != expected_kind
            or manifest.media_type != "application/json"
            or schema is None
            or schema.name != expected_schema
            or schema.version != expected_version
            or manifest.producer.component != expected_producer
            or manifest.tenant_context is None
            or manifest.tenant_context.tenant_id != tenant_id
            or manifest.tenant_context.cell_id != cell_id
        ):
            raise ValueError("acquisition_history_artifact_manifest_mismatch")
        payload_bytes = store.get_bytes(ref)
        expected_id = "sha256:" + hashlib.sha256(payload_bytes).hexdigest()
        if (
            str(ref.artifact_id) != expected_id
            or str(manifest.artifact_id) != expected_id
            or manifest.integrity.sha256 != expected_id.removeprefix("sha256:")
            or manifest.byte_size != len(payload_bytes)
        ):
            raise ValueError("acquisition_history_artifact_content_mismatch")
        report = reconcile_authority_ref(
            artifact_store=store,
            event_log=event_log,
            cas_ref=expected_id,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
            expected_run_id=source_run_id,
            expected_job_id=expected_job_id,
        )
        if report.cas_ref != expected_id or report.durable_event_id is None:
            raise ValueError("acquisition_history_event_binding_mismatch")
        return from_canonical_bytes(payload_bytes), payload_bytes, report

    def _resolve_n5_v5_source(
        input_ref: ArtifactRef,
        *,
        expected_run_id: str,
        expected_job_id: str,
        expected_tenant_id: str,
        expected_cell_id: str,
    ) -> tuple[CandidateSimulationN5InputV5, N4CandidateScenarioSourceRecordV3]:
        if (
            input_ref.kind != "runtime.quality.candidate_simulation_n5_input"
            or input_ref.media_type != "application/json"
            or not store.verify(input_ref).ok
        ):
            raise ValueError("acquisition_reentry_n5_input_ref_invalid")
        manifest = store.get_manifest(input_ref)
        if (
            manifest.artifact_schema is None
            or manifest.artifact_schema.name != "policyos.runtime.candidate_simulation.n5_input.v5"
            or manifest.artifact_schema.version != "5.0"
            or manifest.tenant_context is None
            or manifest.tenant_context.tenant_id != expected_tenant_id
            or manifest.tenant_context.cell_id != expected_cell_id
        ):
            raise ValueError("acquisition_reentry_n5_input_manifest_mismatch")
        repository = GenerationSourceRepository(store)
        input_record = repository.resolve_candidate_simulation_v5(
            ref=input_ref,
            expected_run_id=expected_run_id,
            expected_job_id=expected_job_id,
            expected_tenant_id=expected_tenant_id,
            expected_cell_id=expected_cell_id,
        )
        if type(input_record) is not CandidateSimulationN5InputV5:
            raise ValueError("acquisition_reentry_n5_input_schema_mismatch")
        source = repository.load_candidate_scenario_source_v3(
            input_record.n4_source_ref,
            expected_run_id=expected_run_id,
            expected_job_id=expected_job_id,
            expected_tenant_id=expected_tenant_id,
            expected_cell_id=expected_cell_id,
        )
        if type(source) is not N4CandidateScenarioSourceRecordV3:
            raise ValueError("acquisition_reentry_n4_source_schema_mismatch")
        return input_record, source

    try:
        history_entries: list[RunCandidateSimulationAcquisitionHistoryEntry] = []
        matching_receipts: list[tuple[Any, ArtifactRef, AcquisitionRouteLoopReceipt]] = []
        matching_incomplete = False
        for head in heads:
            if (
                head.tenant_id != tenant_id
                or head.cell_id != cell_id
                or head.run_id != source_run_id
                or head.source_job_id != source_job_id
            ):
                raise ValueError("acquisition_action_head_scope_mismatch")
            if head.receipt_ref != head.receipt_sha256:
                raise ValueError("acquisition_action_head_ref_mismatch")
            if head.receipt_phase == "terminal":
                route_receipt_ref = _selected_ref(
                    head.receipt_ref,
                    kind="runtime_quality.acquisition_route_loop_receipt",
                )
                route_payload, _route_bytes, route_report = _read_authority_payload(
                    route_receipt_ref,
                    expected_kind="runtime_quality.acquisition_route_loop_receipt",
                    expected_schema="polisyos.runtime.AcquisitionRouteLoopReceipt",
                    expected_version="1.0",
                    expected_job_id=head.job_id,
                )
                route_receipt = AcquisitionRouteLoopReceipt.model_validate(route_payload)
                receipt = route_receipt
            else:
                route_receipt_ref = _selected_ref(
                    head.receipt_ref,
                    kind="runtime_quality.acquisition_route_phase_receipt",
                )
                route_payload, _route_bytes, route_report = _read_authority_payload(
                    route_receipt_ref,
                    expected_kind="runtime_quality.acquisition_route_phase_receipt",
                    expected_schema="polisyos.runtime.AcquisitionRoutePhaseReceipt",
                    expected_version="1.0",
                    expected_job_id=head.job_id,
                )
                receipt = AcquisitionRoutePhaseReceipt.model_validate(route_payload)
            if any(
                getattr(receipt, field) != getattr(head, field)
                for field in (
                    "tenant_id",
                    "cell_id",
                    "run_id",
                    "source_job_id",
                    "route_id",
                    "action_generation",
                    "job_id",
                    "coarse_phase",
                    "receipt_phase",
                    "recovery_state",
                    "predecessor_receipt_ref",
                )
            ):
                raise ValueError("acquisition_action_head_binding_mismatch")
            if route_report.durable_event_id != head.durable_event_id:
                raise ValueError("acquisition_action_head_event_binding_mismatch")
            current_head = control_store.get_acquisition_action_head(
                tenant_id=head.tenant_id,
                cell_id=head.cell_id,
                run_id=head.run_id,
                source_job_id=head.source_job_id,
                route_id=head.route_id,
                action_generation=head.action_generation,
            )
            if current_head != head:
                raise ValueError("acquisition_action_head_readback_mismatch")
            if receipt.compiled_ref != str(compiled_ref.artifact_id):
                continue
            if head.receipt_phase != "terminal":
                matching_incomplete = True
                continue
            if not isinstance(receipt, AcquisitionRouteLoopReceipt):
                raise ValueError("acquisition_action_terminal_receipt_type_mismatch")
            if receipt.run_id != source_run_id or receipt.source_job_id != source_job_id:
                raise ValueError("acquisition_action_head_source_binding_mismatch")
            route_receipt = receipt
            matching_receipts.append((head, route_receipt_ref, route_receipt))

        if not matching_receipts:
            if matching_incomplete:
                return (), "acquisition_action_history_incomplete"
            return (), "acquisition_action_history_not_observed"

        for _head, route_receipt_ref, route_receipt in matching_receipts:
            if route_receipt.terminal_outcome == "quarantined_no_growth":
                history_entries.append(
                    RunCandidateSimulationAcquisitionHistoryEntry(
                        route_receipt_ref=route_receipt_ref,
                        route_id=route_receipt.route_id,
                        action_generation=route_receipt.action_generation,
                        terminal_outcome="quarantined_no_growth",
                    )
                )
                continue
            if route_receipt.reentry_receipt_ref is None:
                raise ValueError("acquisition_reentry_ref_missing")
            reentry_receipt_ref = _selected_ref(
                route_receipt.reentry_receipt_ref,
                kind="runtime_quality.acquisition_overlay_reentry_receipt",
            )
            reentry_payload, _reentry_bytes, _reentry_report = _read_authority_payload(
                reentry_receipt_ref,
                expected_kind="runtime_quality.acquisition_overlay_reentry_receipt",
                expected_schema="polisyos.runtime.AcquisitionOverlayReentryReceipt",
                expected_version="1.0",
                expected_job_id=route_receipt.source_job_id,
            )
            reentry_receipt = AcquisitionOverlayReentryReceipt.model_validate(reentry_payload)
            if (
                reentry_receipt.design_problem_ref != compiled.design_problem_ref
                or reentry_receipt.new_cycle.design_problem_ref
                != reentry_receipt.design_problem_ref
                or reentry_receipt.new_cycle.cycle_index != reentry_receipt.source_cycle_index + 1
            ):
                raise ValueError("acquisition_reentry_route_binding_mismatch")

            source_cycles = tuple(
                cycle
                for node in recursive_run.nodes
                if isinstance(node, RecursiveCycleNode)
                and node.cycle_run is not None
                and node.design_problem_ref == reentry_receipt.design_problem_ref
                for cycle in node.cycle_run.cycles
                if cycle.cycle_index == reentry_receipt.source_cycle_index
            )
            if (
                len(source_cycles) != 1
                or source_cycles[0].selected_candidate_ref != reentry_receipt.source_candidate_ref
                or source_cycles[0].simulation.candidate_id != reentry_receipt.source_candidate_ref
            ):
                raise ValueError("acquisition_reentry_source_candidate_binding_mismatch")
            source_cycle = source_cycles[0]
            old_source_ref = source_cycle.simulation.candidate_simulation_n4_source_ref
            old_input_ref = source_cycle.simulation.candidate_simulation_n5_input_ref
            old_source = None
            if (old_source_ref is None) != (old_input_ref is None):
                raise ValueError("acquisition_reentry_old_candidate_source_incomplete")
            if old_source_ref is not None and old_input_ref is not None:
                old_input, old_source = _resolve_n5_v5_source(
                    ArtifactRef.model_validate(old_input_ref.model_dump(mode="json")),
                    expected_run_id=source_run_id,
                    expected_job_id=source_job_id,
                    expected_tenant_id=tenant_id,
                    expected_cell_id=cell_id,
                )
                old_source_ref = ArtifactRef.model_validate(old_source_ref.model_dump(mode="json"))
                if (
                    artifact_ref_identity_key(old_input.n4_source_ref)
                    != artifact_ref_identity_key(old_source_ref)
                    or old_input.original_candidate_id != reentry_receipt.source_candidate_ref
                    or old_source.candidate.candidate_id != reentry_receipt.source_candidate_ref
                ):
                    raise ValueError("acquisition_reentry_old_candidate_source_mismatch")

            new_simulation = reentry_receipt.new_cycle.simulation
            if (
                new_simulation.candidate_simulation_n4_source_ref is None
                or new_simulation.candidate_simulation_n5_input_ref is None
            ):
                return (), "acquisition_reentry_source_not_established"
            new_input_ref = ArtifactRef.model_validate(
                new_simulation.candidate_simulation_n5_input_ref.model_dump(mode="json")
            )
            new_input, new_source = _resolve_n5_v5_source(
                new_input_ref,
                expected_run_id=route_receipt.run_id,
                expected_job_id=route_receipt.job_id,
                expected_tenant_id=route_receipt.tenant_id,
                expected_cell_id=route_receipt.cell_id,
            )
            new_source_ref = ArtifactRef.model_validate(
                new_simulation.candidate_simulation_n4_source_ref.model_dump(mode="json")
            )
            if (
                artifact_ref_identity_key(new_input.n4_source_ref)
                != artifact_ref_identity_key(new_source_ref)
                or new_input.original_candidate_id
                != reentry_receipt.new_cycle.selected_candidate_ref
                or new_source.candidate.candidate_id
                != reentry_receipt.new_cycle.selected_candidate_ref
            ):
                raise ValueError("acquisition_reentry_new_candidate_source_mismatch")

            # Candidate IDs are truncated semantic digests. Reconcile the full
            # identity and immutable occurrence lineage when both IDs match.
            same_candidate = (
                reentry_receipt.source_candidate_ref
                == reentry_receipt.new_cycle.selected_candidate_ref
            )
            if same_candidate:
                if old_source is None or old_source_ref is None:
                    raise ValueError("acquisition_reentry_same_candidate_source_missing")
                old_semantic_identity = candidate_scenario_semantic_identity_hash(
                    stable_subject_ref=old_source.stable_subject_ref,
                    proposal=old_source.proposal,
                    candidate=old_source.candidate,
                    profile=old_source.profile,
                )
                new_semantic_identity = candidate_scenario_semantic_identity_hash(
                    stable_subject_ref=new_source.stable_subject_ref,
                    proposal=new_source.proposal,
                    candidate=new_source.candidate,
                    profile=new_source.profile,
                )
                expected_origin_ref = old_source.origin_source_ref or old_source_ref
                if (
                    old_semantic_identity != old_source.semantic_identity_hash
                    or new_semantic_identity != new_source.semantic_identity_hash
                    or old_source.stable_subject_ref != new_source.stable_subject_ref
                    or old_source.semantic_identity_hash != new_source.semantic_identity_hash
                    or old_source.profile_selection_ref != new_source.profile_selection_ref
                    or old_source.candidate.candidate_id != new_source.candidate.candidate_id
                    or old_source.candidate_occurrence_hash == new_source.candidate_occurrence_hash
                    or old_source.world_model_record_hash == new_source.world_model_record_hash
                    or new_source.origin_source_ref is None
                    or artifact_ref_identity_key(new_source.origin_source_ref)
                    != artifact_ref_identity_key(expected_origin_ref)
                ):
                    raise ValueError("acquisition_reentry_same_candidate_lineage_mismatch")

            history_entries.append(
                RunCandidateSimulationAcquisitionHistoryEntry(
                    route_receipt_ref=route_receipt_ref,
                    reentry_receipt_ref=reentry_receipt_ref,
                    route_id=route_receipt.route_id,
                    action_generation=route_receipt.action_generation,
                    terminal_outcome="reentry_completed",
                    old_candidate_id=reentry_receipt.source_candidate_ref,
                    new_candidate_id=reentry_receipt.new_cycle.selected_candidate_ref,
                    new_candidate_source_ref=new_source_ref,
                    origin_source_ref=new_source.origin_source_ref,
                )
            )
        return tuple(history_entries), None
    except Exception:
        return (), "acquisition_action_history_integrity_not_established"


def _candidate_simulation_projection(
    *,
    run_id: str,
    tenant_id: str | None,
    cell_id: str | None,
    control_job_id: str | None,
    root_artifacts: tuple[Any, ...],
    store: Any,
    control_service: Any | None = None,
) -> RunCandidateSimulationProjection | None:
    """Resolve the exact Core-run output and source-bound N5 child artifacts."""
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.runtime.http.services.control.generation_cycle import (
        COMPILED_RECURSIVE_GENERATION_CYCLE_COST_SCHEMA_VERSION,
        COMPILED_RECURSIVE_GENERATION_CYCLE_FAILED_PARTIAL_SCHEMA_VERSION,
        COMPILED_RECURSIVE_GENERATION_CYCLE_PARTIAL_SCHEMA_VERSION,
        COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality.generation_cycle import (
        _joint_simulation_port_outcome,
        load_joint_simulation_result,
    )
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveCycleNode,
    )

    compiled_refs = tuple(
        ref
        for ref in root_artifacts
        if getattr(ref, "kind", None) == "runtime.compiled_recursive_generation_cycle"
    )
    if not compiled_refs:
        return None
    if len(compiled_refs) != 1:
        return _candidate_simulation_refusal(
            run_id=run_id,
            limitation_code="compiled_cycle_artifact_ambiguous",
        )
    ref = compiled_refs[0]
    if getattr(ref, "media_type", None) != "application/json":
        return _candidate_simulation_refusal(
            run_id=run_id,
            source_ref=ref,
            limitation_code="compiled_cycle_artifact_ref_invalid",
        )
    if not tenant_id or not cell_id:
        return _candidate_simulation_refusal(
            run_id=run_id,
            source_ref=ref,
            limitation_code="compiled_cycle_artifact_integrity_not_established",
        )

    try:
        verification = store.verify(ref)
        if not verification.ok:
            raise ValueError("compiled_cycle_artifact_integrity_not_established")
        manifest = store.get_manifest(ref)
        tenant_context = manifest.tenant_context
        if (
            manifest.kind != "runtime.compiled_recursive_generation_cycle"
            or manifest.media_type != "application/json"
            or tenant_context is None
            or tenant_context.tenant_id != tenant_id
            or tenant_context.cell_id != cell_id
        ):
            raise ValueError("compiled_cycle_artifact_manifest_binding_invalid")
        payload_bytes = store.get_bytes(ref)
        expected_artifact_id = f"sha256:{hashlib.sha256(payload_bytes).hexdigest()}"
        if (
            str(ref.artifact_id) != expected_artifact_id
            or str(manifest.artifact_id) != expected_artifact_id
            or manifest.integrity.sha256 != expected_artifact_id.removeprefix("sha256:")
            or manifest.byte_size != len(payload_bytes)
        ):
            raise ValueError("compiled_cycle_artifact_content_hash_mismatch")
    except Exception:
        return _candidate_simulation_refusal(
            run_id=run_id,
            source_ref=ref,
            limitation_code="compiled_cycle_artifact_integrity_not_established",
        )

    try:
        if (
            manifest.artifact_schema is None
            or manifest.artifact_schema.name
            != "polisyos.runtime.CompiledRecursiveGenerationCycleRun"
        ):
            raise ValueError("compiled_cycle_artifact_schema_binding_invalid")
        compiled = CompiledRecursiveGenerationCycleRun.model_validate(
            from_canonical_bytes(payload_bytes)
        )
        expected_manifest_schema_version = {
            COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION: "1.0",
            COMPILED_RECURSIVE_GENERATION_CYCLE_PARTIAL_SCHEMA_VERSION: "1.0",
            COMPILED_RECURSIVE_GENERATION_CYCLE_FAILED_PARTIAL_SCHEMA_VERSION: "1.0",
            COMPILED_RECURSIVE_GENERATION_CYCLE_COST_SCHEMA_VERSION: "1.0",
        }.get(compiled.schema_version)
        if (
            expected_manifest_schema_version is None
            or manifest.artifact_schema.version != expected_manifest_schema_version
        ):
            raise ValueError("compiled_cycle_artifact_schema_binding_invalid")
    except Exception:
        return _candidate_simulation_refusal(
            run_id=run_id,
            source_ref=ref,
            limitation_code="compiled_cycle_artifact_content_invalid",
        )

    recursive_run = compiled.recursive_run
    checkpoint = _candidate_simulation_checkpoint(recursive_run)
    n4_source_status: Literal["resolved", "not_established"] | None = None
    n4_source_content_hash: str | None = None
    n4_source_limitation_code: str | None = None
    n4_source_result_status: str | None = None
    root_n4_source = None
    if compiled.n4_recursive_source_ref is not None:
        try:
            if (
                compiled.n4_recursive_source_job_id is None
                or compiled.n4_recursive_source_run_id is None
                or compiled.n4_recursive_source_tenant_id != tenant_id
                or compiled.n4_recursive_source_cell_id != cell_id
                or compiled.n4_recursive_source_context_job_ref is None
            ):
                raise ValueError("n4_recursive_source_scope_not_established")
            repository = GenerationSourceRepository(store)
            root_n4_source = repository.load(
                compiled.n4_recursive_source_ref,
                run_id=compiled.n4_recursive_source_run_id,
                expected_job_id=compiled.n4_recursive_source_job_id,
                expected_tenant_id=compiled.n4_recursive_source_tenant_id,
                expected_cell_id=compiled.n4_recursive_source_cell_id,
            )
            if (
                root_n4_source.problem != compiled.design_problem
                or root_n4_source.content_hash is None
                or root_n4_source.generation_result.status
                != compiled.n4_recursive_source_result_status
                or root_n4_source.cycle_substrate_context is None
                or root_n4_source.cycle_substrate_context.content_hash
                != compiled.cycle_substrate_context_ref
            ):
                raise ValueError("n4_recursive_source_compiled_binding_mismatch")
            from polisyos.runtime.quality.cycle_substrate import (
                CycleSubstrateContextArtifactOwner,
                cycle_job_profile_selection_ref,
            )

            context_job = CycleSubstrateContextArtifactOwner(
                store=store
            ).resolve_historical_job_artifact(
                compiled.n4_recursive_source_context_job_ref,
                problem=compiled.design_problem,
                expected_job_id=compiled.n4_recursive_source_job_id,
                expected_run_id=compiled.n4_recursive_source_run_id,
                expected_tenant_id=compiled.n4_recursive_source_tenant_id,
                expected_cell_id=compiled.n4_recursive_source_cell_id,
            )
            if (
                context_job.context.content_hash != compiled.cycle_substrate_context_ref
                or compiled.n4_recursive_source_profile_selection_ref
                != cycle_job_profile_selection_ref(compiled.design_problem)
            ):
                raise ValueError("n4_recursive_source_context_profile_mismatch")
            n4_source_status = "resolved"
            n4_source_content_hash = root_n4_source.content_hash
            n4_source_result_status = root_n4_source.generation_result.status
        except Exception:
            n4_source_status = "not_established"
            n4_source_limitation_code = "n4_recursive_source_reference_not_established"
    elif compiled.n4_child_profile_status == "not_established":
        n4_source_status = "not_established"
        n4_source_limitation_code = (
            compiled.n4_child_profile_limitation_code
            or "n4_recursive_source_reference_not_established"
        )

    child_profile_status = (
        compiled.n4_child_profile_status
        if compiled.n4_child_profile_status != "not_attempted"
        else None
    )
    child_profile_limitation_code = compiled.n4_child_profile_limitation_code
    child_profile_bindings: list[RunCandidateSimulationChildProfileBinding] = []
    if compiled.n4_child_profile_bindings:
        try:
            if n4_source_status != "resolved" or root_n4_source is None:
                raise ValueError("n4_recursive_source_reference_not_established")
            from polisyos.runtime.quality.candidate_simulation import (
                candidate_simulation_profile_ref,
            )
            from polisyos.runtime.quality.cycle_substrate import (
                CycleSubstrateContextArtifactOwner,
                cycle_job_profile_selection_ref,
            )
            from polisyos.runtime.quality.design_generation import (
                derive_n4_candidate_child_problems,
            )

            derived_children = derive_n4_candidate_child_problems(
                compiled.design_problem,
                root_n4_source.generation_result,
                model_id=root_n4_source.generation_result.model_id,
            )
            from polisyos.pdc import gy_content_hash

            child_by_ref = {
                "design-problem://"
                + gy_content_hash(child.problem.model_dump(mode="json")).removeprefix(
                    "sha256:"
                ): child
                for child in derived_children
            }
            root_node_ref = "design-problem://" + compiled.design_problem_ref.removeprefix(
                "sha256:"
            )
            root_node = next(node for node in recursive_run.nodes if node.node_ref == root_node_ref)
            expected_child_nodes = {row.node_ref for row in compiled.n4_child_profile_bindings}
            if (
                set(root_node.child_refs) != expected_child_nodes
                or set(child_by_ref) != expected_child_nodes
            ):
                raise ValueError("compiled_n4_child_graph_source_mismatch")
            context_owner = CycleSubstrateContextArtifactOwner(store=store)
            for binding in compiled.n4_child_profile_bindings:
                child = child_by_ref[binding.node_ref]
                handoff = binding.handoff
                if (
                    binding.design_problem_ref
                    != gy_content_hash(child.problem.model_dump(mode="json"))
                    or handoff.profile.profile_selection_ref
                    != cycle_job_profile_selection_ref(child.problem)
                    or handoff.profile_config_ref
                    != candidate_simulation_profile_ref(handoff.profile)
                    or handoff.job_id != compiled.n4_recursive_source_job_id
                    or handoff.run_id != compiled.n4_recursive_source_run_id
                    or handoff.tenant_id != tenant_id
                    or handoff.cell_id != cell_id
                ):
                    raise ValueError("compiled_n4_child_profile_content_binding_mismatch")
                current_context_job = context_owner.resolve_historical_job_artifact(
                    handoff.context_job_ref,
                    problem=child.problem,
                    expected_job_id=handoff.job_id,
                    expected_run_id=handoff.run_id,
                    expected_tenant_id=handoff.tenant_id,
                    expected_cell_id=handoff.cell_id,
                )
                if current_context_job.context.content_hash != handoff.context.content_hash:
                    raise ValueError("compiled_n4_child_context_job_replay_mismatch")
                child_profile_bindings.append(
                    RunCandidateSimulationChildProfileBinding(
                        node_ref=binding.node_ref,
                        design_problem_ref=binding.design_problem_ref,
                        root_n4_source_ref=compiled.n4_recursive_source_ref,
                        context_job_ref=handoff.context_job_ref,
                        context_hash=handoff.context.content_hash,
                        profile_id=handoff.profile.profile_id,
                        profile_config_ref=handoff.profile_config_ref,
                        profile_selection_ref=handoff.profile.profile_selection_ref,
                        model_declaration_ref=handoff.model_declaration_ref,
                        ncm_ref=handoff.ncm_ref,
                        job_id=handoff.job_id,
                        run_id=handoff.run_id,
                        tenant_id=handoff.tenant_id,
                        cell_id=handoff.cell_id,
                        historical_binding_status="resolved",
                    )
                )
        except Exception:
            child_profile_status = "not_established"
            child_profile_limitation_code = "n4_child_profile_reference_not_established"
            child_profile_bindings = [
                RunCandidateSimulationChildProfileBinding(
                    node_ref=row.node_ref,
                    design_problem_ref=row.design_problem_ref,
                    root_n4_source_ref=compiled.n4_recursive_source_ref,
                    context_job_ref=row.handoff.context_job_ref,
                    context_hash=row.handoff.context.content_hash,
                    profile_id=row.handoff.profile.profile_id,
                    profile_config_ref=row.handoff.profile_config_ref,
                    profile_selection_ref=row.handoff.profile.profile_selection_ref,
                    model_declaration_ref=row.handoff.model_declaration_ref,
                    ncm_ref=row.handoff.ncm_ref,
                    job_id=row.handoff.job_id,
                    run_id=row.handoff.run_id,
                    tenant_id=row.handoff.tenant_id,
                    cell_id=row.handoff.cell_id,
                    historical_binding_status="not_established",
                    limitation_code="n4_child_profile_reference_not_established",
                )
                for row in compiled.n4_child_profile_bindings
            ]

    observations: list[RunCandidateSimulationN5Observation] = []
    n5_ref_unresolved = False
    root_node_ref = "design-problem://" + compiled.design_problem_ref.removeprefix("sha256:")
    compiled_child_handoffs = {
        row.node_ref: row.handoff for row in compiled.n4_child_profile_bindings
    }
    child_projection_by_node = {row.node_ref: row for row in child_profile_bindings}
    n4_projection_fields = {
        "n4_recursive_source_ref": compiled.n4_recursive_source_ref,
        "n4_recursive_source_content_hash": n4_source_content_hash,
        "n4_recursive_source_status": n4_source_status,
        "n4_recursive_source_limitation_code": n4_source_limitation_code,
        "n4_recursive_source_result_status": n4_source_result_status,
        "n4_recursive_source_context_job_ref": compiled.n4_recursive_source_context_job_ref,
        "n4_recursive_source_profile_config_ref": (compiled.n4_recursive_source_profile_config_ref),
        "n4_recursive_source_profile_selection_ref": (
            compiled.n4_recursive_source_profile_selection_ref
        ),
        "n4_child_profile_status": child_profile_status,
        "n4_child_profile_limitation_code": child_profile_limitation_code,
        "n4_child_profile_bindings": tuple(child_profile_bindings),
    }
    acquisition_history, acquisition_history_limitation_code = (
        _candidate_acquisition_history_projection(
            compiled=compiled,
            compiled_ref=ref,
            recursive_run=recursive_run,
            store=store,
            control_service=control_service,
            core_run_id=run_id,
            control_job_id=control_job_id,
            source_status=n4_source_status,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
    )
    acquisition_history_fields = {
        "acquisition_history": acquisition_history,
        "acquisition_history_limitation_code": acquisition_history_limitation_code,
    }

    def _lineage_projection(simulation: Any, *, node_ref: str, problem_ref: str) -> dict[str, Any]:
        selected_refs = (
            simulation.candidate_simulation_n4_source_ref,
            simulation.candidate_simulation_context_job_ref,
            simulation.candidate_simulation_n5_input_ref,
        )
        if not any(selected_refs):
            return {}
        common = {
            "n4_source_ref": simulation.candidate_simulation_n4_source_ref,
            "context_job_ref": simulation.candidate_simulation_context_job_ref,
            "n5_input_ref": simulation.candidate_simulation_n5_input_ref,
            "profile_config_ref": simulation.candidate_simulation_profile_config_ref,
            "profile_selection_ref": simulation.candidate_simulation_profile_selection_ref,
            "lineage_status": "not_established",
            "lineage_limitation_code": "candidate_n5_lineage_reference_not_established",
        }
        if not all(selected_refs) or not all(
            (
                simulation.candidate_simulation_profile_config_ref,
                simulation.candidate_simulation_profile_selection_ref,
            )
        ):
            return common
        try:
            from polisyos.core.canon import from_canonical_bytes
            from polisyos.runtime.quality.candidate_simulation import (
                candidate_simulation_profile_ref,
            )
            from polisyos.runtime.quality.cycle_substrate import (
                cycle_job_profile_selection_ref,
            )
            from polisyos.runtime.quality.generation_source import GenerationSourceRepository

            input_ref = simulation.candidate_simulation_n5_input_ref
            input_manifest = store.get_manifest(input_ref)
            input_payload = from_canonical_bytes(store.get_bytes(input_ref))
            if not isinstance(input_payload, dict):
                raise ValueError("candidate_simulation_input_payload_invalid")
            input_schema = input_payload.get("schema_version")
            repository = GenerationSourceRepository(store)
            resolver_by_schema = {
                "policyos.runtime.candidate_simulation.n5_input.v2": (
                    repository.resolve_candidate_simulation_v2
                ),
                "policyos.runtime.candidate_simulation.n5_input.v3": (
                    repository.resolve_candidate_simulation_v3
                ),
                "policyos.runtime.candidate_simulation.n5_input.v4": (
                    repository.resolve_candidate_simulation_v4
                ),
                "policyos.runtime.candidate_simulation.n5_input.v5": (
                    repository.resolve_candidate_simulation_v5
                ),
            }
            resolver = resolver_by_schema.get(input_schema)
            if resolver is None:
                raise ValueError("candidate_simulation_input_schema_unsupported")
            input_job_id = input_payload.get("job_id")
            input_run_id = input_payload.get("run_id")
            input_tenant_id = input_payload.get("tenant_id")
            input_cell_id = input_payload.get("cell_id")
            if (
                not isinstance(input_job_id, str)
                or not isinstance(input_run_id, str)
                or input_tenant_id != tenant_id
                or input_cell_id != cell_id
                or input_manifest.tenant_context is None
                or input_manifest.tenant_context.tenant_id != tenant_id
                or input_manifest.tenant_context.cell_id != cell_id
            ):
                raise ValueError("candidate_simulation_input_scope_mismatch")
            lineage = resolver(
                ref=input_ref,
                expected_run_id=input_run_id,
                expected_job_id=input_job_id,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
            )
            if (
                lineage.run_id != input_run_id
                or lineage.job_id != input_job_id
                or lineage.tenant_id != tenant_id
                or lineage.cell_id != cell_id
                or lineage.materialization.problem_ref != problem_ref
                or lineage.n4_source_ref != simulation.candidate_simulation_n4_source_ref
                or lineage.context_job_ref != simulation.candidate_simulation_context_job_ref
                or lineage.profile_config_ref != simulation.candidate_simulation_profile_config_ref
                or lineage.profile.profile_selection_ref
                != simulation.candidate_simulation_profile_selection_ref
                or candidate_simulation_profile_ref(lineage.profile) != lineage.profile_config_ref
            ):
                raise ValueError("candidate_simulation_input_compiled_binding_mismatch")
            if node_ref == root_node_ref:
                if (
                    n4_source_status != "resolved"
                    or n4_source_content_hash is None
                    or compiled.n4_recursive_source_context_job_ref != lineage.context_job_ref
                    or compiled.n4_recursive_source_profile_config_ref != lineage.profile_config_ref
                    or compiled.n4_recursive_source_profile_selection_ref
                    != cycle_job_profile_selection_ref(compiled.design_problem)
                ):
                    raise ValueError("candidate_simulation_root_profile_binding_mismatch")
            else:
                child_handoff = compiled_child_handoffs.get(node_ref)
                child_projection = child_projection_by_node.get(node_ref)
                if (
                    compiled.n4_child_profile_status != "resolved"
                    or n4_source_status != "resolved"
                    or child_handoff is None
                    or child_projection is None
                    or child_projection.historical_binding_status != "resolved"
                    or child_handoff.context_job_ref != lineage.context_job_ref
                    or child_handoff.profile_config_ref != lineage.profile_config_ref
                    or child_handoff.profile.content_hash != lineage.profile.content_hash
                    or child_handoff.model_declaration_ref != lineage.model_declaration_ref
                    or child_handoff.ncm_ref != lineage.ncm_ref
                    or (input_run_id, input_job_id)
                    != (
                        compiled.n4_recursive_source_run_id,
                        compiled.n4_recursive_source_job_id,
                    )
                ):
                    raise ValueError("candidate_simulation_child_profile_binding_mismatch")
            return {
                **common,
                "lineage_status": "resolved",
                "lineage_limitation_code": None,
            }
        except Exception:
            return common

    def _resolved_n5_result(
        *,
        result_ref: Any,
        expected_world_hash: str | None,
        expected_status: str | None = None,
        expected_simulation_ref: str | None = None,
        expected_atom_ids: tuple[str, ...] | None = None,
        expected_outcomes: tuple[str, ...] | None = None,
        embedded_result: Any = None,
    ) -> tuple[Any, tuple[str, ...]]:
        n5_manifest = store.get_manifest(result_ref)
        n5_tenant_context = n5_manifest.tenant_context
        if (
            n5_tenant_context is None
            or n5_tenant_context.tenant_id != tenant_id
            or n5_tenant_context.cell_id != cell_id
        ):
            raise ValueError("n5_result_tenant_binding_not_established")
        verification_report = store.verify(result_ref)
        if not verification_report.ok:
            raise ValueError("n5_result_integrity_not_established")
        result = load_joint_simulation_result(
            result_ref,
            store=store,
            expected_world_model_record_content_hash=expected_world_hash,
            expected_atom_ids=expected_atom_ids,
            expected_selected_outcomes=expected_outcomes,
        )
        if embedded_result is not None and (
            result.model_dump(mode="json") != embedded_result.model_dump(mode="json")
        ):
            raise ValueError("n5_result_compiled_binding_mismatch")
        actual_status, actual_blockers = _joint_simulation_port_outcome(result)
        if expected_status is not None and actual_status != expected_status:
            raise ValueError("n5_result_status_binding_mismatch")
        if (
            expected_simulation_ref is not None
            and result.receipt.payload_hash != expected_simulation_ref
        ):
            raise ValueError("n5_result_receipt_binding_mismatch")
        return result, actual_blockers

    try:
        for node in recursive_run.nodes:
            if not isinstance(node, RecursiveCycleNode):
                continue
            if node.cycle_run is not None:
                for cycle in node.cycle_run.cycles:
                    simulation = cycle.simulation
                    result = None
                    blockers = tuple(simulation.authority_blockers)
                    if simulation.simulation_result_ref is not None:
                        result, actual_blockers = _resolved_n5_result(
                            result_ref=simulation.simulation_result_ref,
                            expected_world_hash=simulation.k_world_ref_before,
                            expected_status=simulation.status,
                            expected_simulation_ref=simulation.simulation_ref,
                        )
                        if not set(actual_blockers).issubset(blockers):
                            raise ValueError("n5_result_blockers_binding_mismatch")
                    elif simulation.status == "joint_simulated":
                        raise ValueError("n5_result_reference_not_established")
                    lineage_fields = _lineage_projection(
                        simulation,
                        node_ref=node.node_ref,
                        problem_ref=cycle.design_problem_ref,
                    )
                    observations.append(
                        RunCandidateSimulationN5Observation(
                            node_ref=node.node_ref,
                            design_problem_ref=cycle.design_problem_ref,
                            design_problem_basis_ref=cycle.design_problem_basis_ref,
                            cycle_index=cycle.cycle_index,
                            candidate_id=simulation.candidate_id,
                            atom_ids=tuple(result.atom_ids) if result is not None else (),
                            selected_outcomes=(
                                tuple(result.selected_outcomes) if result is not None else ()
                            ),
                            status=simulation.status,
                            simulation_ref=simulation.simulation_ref,
                            simulation_result_ref=(
                                simulation.simulation_result_ref
                                if simulation.simulation_result_ref is not None
                                else None
                            ),
                            world_model_record_content_hash=(
                                result.world_model_record_content_hash
                                if result is not None
                                else simulation.k_world_ref_before
                            ),
                            k_world_ref_before=simulation.k_world_ref_before,
                            k_world_ref_after=simulation.k_world_ref_after,
                            authority_blockers=blockers,
                            **lineage_fields,
                        )
                    )
            if node.joint_simulation is not None:
                if node.joint_simulation_ref is None:
                    raise ValueError("n5_result_reference_not_established")
                parent_result = node.joint_simulation
                status, blockers = _joint_simulation_port_outcome(parent_result)
                result, resolved_blockers = _resolved_n5_result(
                    result_ref=node.joint_simulation_ref,
                    expected_world_hash=parent_result.world_model_record_content_hash,
                    expected_status=status,
                    expected_simulation_ref=parent_result.receipt.payload_hash,
                    expected_atom_ids=tuple(parent_result.atom_ids),
                    expected_outcomes=tuple(parent_result.selected_outcomes),
                    embedded_result=parent_result,
                )
                if tuple(resolved_blockers) != tuple(blockers):
                    raise ValueError("n5_result_blockers_binding_mismatch")
                observations.append(
                    RunCandidateSimulationN5Observation(
                        node_ref=node.node_ref,
                        design_problem_ref=node.design_problem_ref,
                        atom_ids=tuple(result.atom_ids),
                        selected_outcomes=tuple(result.selected_outcomes),
                        status=status,
                        simulation_ref=parent_result.receipt.payload_hash,
                        simulation_result_ref=node.joint_simulation_ref,
                        world_model_record_content_hash=result.world_model_record_content_hash,
                        k_world_ref_before=result.world_model_record_content_hash,
                        k_world_ref_after=result.world_model_record_content_hash,
                        authority_blockers=blockers,
                    )
                )
    except Exception:
        n5_ref_unresolved = True

    if n5_ref_unresolved:
        return RunCandidateSimulationProjection(
            run_id=run_id,
            artifact_status="resolved",
            source_ref=ref,
            source_content_hash=compiled.content_hash,
            limitation_code="n5_result_reference_not_established",
            recursive_cycle_checkpoint=checkpoint,
            **acquisition_history_fields,
            **n4_projection_fields,
        )
    if not observations:
        return RunCandidateSimulationProjection(
            run_id=run_id,
            artifact_status="resolved",
            source_ref=ref,
            source_content_hash=compiled.content_hash,
            limitation_code="n5_observation_not_emitted",
            recursive_cycle_checkpoint=checkpoint,
            **acquisition_history_fields,
            **n4_projection_fields,
        )
    return RunCandidateSimulationProjection(
        run_id=run_id,
        artifact_status="resolved",
        source_ref=ref,
        source_content_hash=compiled.content_hash,
        n5_observations=tuple(observations),
        recursive_cycle_checkpoint=checkpoint,
        **acquisition_history_fields,
        **n4_projection_fields,
    )


@dataclass(frozen=True)
class LiveStreamPolicy:
    min_interval_seconds: float
    max_interval_seconds: float
    keepalive_seconds: float
    max_duration_seconds: float

    @classmethod
    def from_env(cls) -> LiveStreamPolicy:
        min_interval = max(
            float(os.getenv("POLISYOS_RUNTIME_LIVE_MIN_INTERVAL_SECONDS", "1.0")),
            0.1,
        )
        max_interval = max(
            float(os.getenv("POLISYOS_RUNTIME_LIVE_MAX_INTERVAL_SECONDS", "5.0")),
            min_interval,
        )
        keepalive = max(
            float(os.getenv("POLISYOS_RUNTIME_LIVE_KEEPALIVE_SECONDS", "15.0")),
            min_interval,
        )
        max_duration = max(
            float(os.getenv("POLISYOS_RUNTIME_LIVE_MAX_DURATION_SECONDS", "120")),
            5.0,
        )
        return cls(
            min_interval_seconds=min_interval,
            max_interval_seconds=max_interval,
            keepalive_seconds=keepalive,
            max_duration_seconds=max_duration,
        )


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _encode_sse(
    payload: dict[str, Any], event: str = "message", event_id: str | None = None
) -> str:
    lines = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(payload, default=_json_default, sort_keys=True)}")
    return "\n".join(lines) + "\n\n"


def _encode_validated_runs_sse(
    payload: object,
    *,
    event: str,
    event_id: str | None = None,
) -> str:
    """Validate and encode one data-bearing runs SSE event."""

    validated = validate_runs_channel_data_event(payload, event=event)
    return _encode_sse(
        validated.payload.model_dump(mode="json"),
        event=validated.event,
        event_id=event_id,
    )


def _payload_signature(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, default=_json_default, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _as_source_kind(value: str) -> SourceKind:
    return cast("SourceKind", value)


def _control_service_from_request(request: Request) -> Any | None:
    state = getattr(getattr(request, "app", None), "state", None)
    if state is None:
        return None
    service = getattr(state, "_control_service", None)
    if service is not None:
        return service
    container = getattr(state, "runtime_container", None)
    return getattr(container, "control_service", None)


def _artifact_ownership_evidence(
    store: Any,
    *,
    tenant_id: str | None,
    cell_id: str | None,
) -> dict[str, Any] | None:
    evidence = getattr(store, "ownership_evidence", None)
    if not callable(evidence):
        return None
    try:
        payload = evidence(tenant_id=tenant_id, cell_id=cell_id)
    except Exception:
        return None
    if not isinstance(payload, Mapping):
        return None
    return dict(payload)


def _latest_control_operator_diagnostic(
    control_service: Any | None,
    run_id: str,
) -> RunOperatorDiagnostic | None:
    if control_service is None:
        return None
    get_latest = getattr(control_service, "get_latest_job_for_run", None)
    if not callable(get_latest):
        return None
    try:
        record = get_latest(run_id)
    except Exception:
        return None
    if record is None:
        return None
    try:
        response = record.to_response(request_id="run-details-operator-diagnostic")
    except Exception:
        return None
    diagnostic = getattr(response, "operator_diagnostic", None)
    if diagnostic is None:
        failure = getattr(response, "failure", None)
        diagnostic = getattr(failure, "operator_diagnostic", None)
    if diagnostic is None:
        return None
    try:
        return RunOperatorDiagnostic.model_validate(
            diagnostic.model_dump(mode="json", exclude_none=True)
        )
    except Exception:
        return None


def _latest_control_policy_projection(
    control_service: Any | None,
    run_id: str,
) -> dict[str, Any] | None:
    if control_service is None:
        return None
    get_latest = getattr(control_service, "get_latest_job_for_run", None)
    if not callable(get_latest):
        return None
    try:
        record = get_latest(run_id)
    except Exception:
        return None
    if record is None:
        return None
    try:
        response = record.to_response(request_id="run-details-policy-design-projection")
    except Exception:
        return None
    projection = getattr(response, "policy_design_case_projection", None)
    return dict(projection) if isinstance(projection, Mapping) else None


def _live_promotion_decisions(control_service: Any | None) -> dict[str, dict[str, Any]]:
    if control_service is None:
        return {}
    list_candidates = getattr(control_service, "list_promotion_candidates", None)
    if not callable(list_candidates):
        return {}
    try:
        response = list_candidates()
    except Exception:
        return {}

    candidates = getattr(response, "candidates", None)
    if candidates is None and isinstance(response, dict):
        candidates = response.get("candidates")
    if not isinstance(candidates, list):
        return {}

    decisions: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        promotion_id = getattr(candidate, "promotion_id", None)
        status = getattr(candidate, "status", None)
        if not promotion_id or not status:
            continue
        metadata = getattr(candidate, "metadata", None)
        decisions[str(promotion_id)] = {
            "status": str(status),
            "metadata": metadata if isinstance(metadata, dict) else {},
        }
    return decisions


def _overlay_live_promotion_decisions(
    evidence_context: RunEvidenceContextView,
    control_service: Any | None,
) -> RunEvidenceContextView:
    decisions = _live_promotion_decisions(control_service)
    if not decisions or not evidence_context.promotion_candidates:
        return evidence_context

    changed = False
    promotions = []
    for promotion in evidence_context.promotion_candidates:
        decision = decisions.get(promotion.promotion_id)
        if decision is None:
            promotions.append(promotion)
            continue
        live_status = decision["status"]
        live_metadata = decision["metadata"]
        if promotion.status == live_status and not live_metadata:
            promotions.append(promotion)
            continue
        changed = True
        promotions.append(
            promotion.model_copy(
                update={
                    "status": live_status,
                    "metadata": {**promotion.metadata, **live_metadata},
                }
            )
        )

    if not changed:
        return evidence_context
    return evidence_context.model_copy(update={"promotion_candidates": promotions})


def _resolve_temporal_scope(
    ctx: RuntimeApiContext,
    run: Any,
    response: Response,
    *,
    surface: TemporalSurfaceSupport,
    valid_at: datetime | None,
    tx_at: datetime | None,
    t: datetime | None,
    branch: str | None,
    snapshot_id: str | None,
    scenario_id: str | None,
) -> TemporalScope | None:
    scope = ctx.temporal.resolve_scope(
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    scope = ctx.temporal.materialize_run_scope(run, scope)
    ctx.temporal.validate_run_scope(run, scope, surface=surface)
    response.headers["X-Temporal-Scope"] = ctx.temporal.response_header_value(scope)
    response.headers["ETag"] = ctx.temporal.response_etag(
        run_id=run.run_id,
        surface=surface,
        scope=scope,
    )
    response.headers.setdefault("Vary", "Accept, Authorization")
    return scope


def _resolve_compare_temporal_scope(
    ctx: RuntimeApiContext,
    run_a: Any,
    run_b: Any,
    response: Response,
    *,
    valid_at: datetime | None,
    tx_at: datetime | None,
    t: datetime | None,
    branch: str | None,
    snapshot_id: str | None,
    scenario_id: str | None,
) -> TemporalScope | None:
    scope = ctx.temporal.resolve_scope(
        valid_at=valid_at,
        tx_at=tx_at,
        t=t,
        branch=branch,
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
    )
    scope = ctx.temporal.materialize_run_scope(run_a, scope)
    ctx.temporal.validate_run_scope(run_a, scope, surface="run_compare")
    ctx.temporal.validate_run_scope(run_b, scope, surface="run_compare")
    response.headers["X-Temporal-Scope"] = ctx.temporal.response_header_value(scope)
    response.headers["ETag"] = ctx.temporal.response_etag(
        run_id=f"{run_a.run_id}:{run_b.run_id}",
        surface="run_compare",
        scope=scope,
    )
    response.headers.setdefault("Vary", "Accept, Authorization")
    return scope


def _build_runs_live_payload(request: Request, ctx: RuntimeApiContext) -> RunsListSnapshot:
    scope = require_access_scope(request)
    runs, page = ctx.run_index.list_runs(
        limit=50,
        cursor=None,
        status=None,
        from_ts=None,
        to_ts=None,
        tenant_id=scope.tenant_id if scope else None,
    )
    status_counts = Counter((run.status or "unknown") for run in runs)
    now = datetime.now(UTC).replace(microsecond=0)
    return RunsListSnapshot(
        cursor=now,
        generated_at=now,
        page=RunsListSnapshotPage(
            count=page.count,
            total=page.total,
            next_cursor=page.next_cursor,
        ),
        status_counts=dict(sorted(status_counts.items())),
        runs=[
            RunsListSnapshotRun(
                run_id=run.run_id,
                status=run.status,
                run_terminality=run.run_terminality,
                started_at=run.started_at,
                finished_at=run.finished_at,
                duration_ms=run.duration_ms,
                root_artifact_count=run.root_artifact_count,
                decision_validity_status=run.decision_validity_status,
                decision_review_required=run.decision_review_required,
            )
            for run in runs
        ],
    )


def _build_run_live_payload(run_id: str, ctx: RuntimeApiContext) -> RunDetailSnapshot:
    run = ctx.run_index.get_run(run_id)
    timeline = ctx.timeline.build_for_run(run).timeline
    agents = ctx.debug.get_run_agents(run)
    governance = ctx.debug.get_governance_debug(run)
    step_count = sum(len(attempt.steps or []) for attempt in agents.attempts or [])
    now = datetime.now(UTC).replace(microsecond=0)
    return RunDetailSnapshot(
        run_id=run_id,
        cursor=now,
        status=run.details.status,
        run_terminality=run.summary.run_terminality,
        started_at=run.details.started_at,
        finished_at=run.details.finished_at,
        duration_ms=run.details.duration_ms,
        timeline_events=timeline.summary.total_events,
        timeline_duration_ms=timeline.summary.duration_ms,
        agent_attempts=len(agents.attempts or []),
        agent_steps=step_count,
        governance_issues=len(governance.issues or []),
        transport_status=(
            governance.transport_summary.get("status")
            if isinstance(governance.transport_summary, dict)
            else None
        ),
        decision_validity_status=run.details.decision_validity_status,
        decision_review_required=run.details.decision_review_required,
        decision_superseded_by_ref=run.details.decision_superseded_by_ref,
        generated_at=now,
    )


async def _stream_payloads(
    builder: Callable[[], RunsLiveSnapshot],
    request: Request,
    *,
    policy: LiveStreamPolicy,
) -> AsyncIterator[str]:
    previous_signature = None
    started_at = monotonic()
    last_emit_at = monotonic()
    sleep_seconds = policy.min_interval_seconds
    while True:
        if await request.is_disconnected():
            break
        if monotonic() - started_at >= policy.max_duration_seconds:
            now = datetime.now(UTC).replace(microsecond=0)
            yield _encode_validated_runs_sse(
                RunsStreamTimeout(cursor=now, generated_at=now),
                event="stream.timeout",
            )
            break
        snapshot = builder()
        payload = (
            snapshot.model_dump(mode="json")
            if hasattr(snapshot, "model_dump")
            else cast("dict[str, Any]", snapshot)
        )
        signature = _payload_signature(payload)
        should_emit = signature != previous_signature
        if should_emit:
            previous_signature = signature
            last_emit_at = monotonic()
            sleep_seconds = policy.min_interval_seconds
            event_id = str(payload.get("cursor") or payload.get("generated_at") or "")
            yield _encode_validated_runs_sse(
                snapshot,
                event="snapshot",
                event_id=event_id or None,
            )
            if payload.get("run_terminality") == RunTerminality.TERMINAL:
                break
        elif monotonic() - last_emit_at >= policy.keepalive_seconds:
            last_emit_at = monotonic()
            yield ": keep-alive\n\n"
            sleep_seconds = policy.min_interval_seconds
        else:
            sleep_seconds = min(policy.max_interval_seconds, sleep_seconds * 2)
        await asyncio.sleep(sleep_seconds)


def _resolve_replay_bound_paper_packet(
    request: Request,
    *,
    run_id: str,
    service: RunPaperProjectionService | CaseInspectionService,
    replay_syntax_code: str,
    replay_conflict_code: str,
    source_invalid_code: str,
    missing_run_code: str | None = None,
    missing_run_message: str = "Run was not found",
) -> RunPaperPacket:
    """Apply the one replay verifier to either authorized paper surface."""

    try:
        replay_query = RunPaperReplayQuery.from_query_items(request.query_params.multi_items())
        return service.get(run_id, replay_query=replay_query)
    except KeyError as exc:
        if missing_run_code is None:
            raise
        raise not_found(
            missing_run_message,
            code=missing_run_code,
        ) from exc
    except RunPaperReplaySyntaxError as exc:
        raise unprocessable_entity(
            str(exc),
            code=replay_syntax_code,
        ) from exc
    except RunPaperReplayConflictError as exc:
        raise conflict(
            str(exc),
            code=replay_conflict_code,
        ) from exc
    except RunPaperSourceError as exc:
        raise conflict(
            str(exc),
            code=source_invalid_code,
        ) from exc


if router is not None:

    @router.get("", response_model=RunsListResponse, operation_id="list_runs")
    def list_runs(
        request: Request,
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str | None = Query(default=None),
        q: str | None = Query(default=None),
        status: str | None = Query(default=None),
        from_ts: datetime | None = Query(default=None),
        to_ts: datetime | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> RunsListResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="runtime.run_list",
        )
        scope = require_access_scope(request)
        runs, page = ctx.run_index.list_runs(
            limit=limit,
            cursor=cursor,
            q=q,
            status=status,
            from_ts=from_ts,
            to_ts=to_ts,
            tenant_id=scope.tenant_id if scope else None,
        )
        source_kinds: list[SourceKind] = [_as_source_kind(run.source_kind) for run in runs]
        record_data_access_audit(
            request,
            resource_id=scope.tenant_id,
            tenant_id=scope.tenant_id,
            metadata={"count": len(runs), "cursor": page.cursor, "next_cursor": page.next_cursor},
        )
        return RunsListResponse(
            meta=build_meta(request, source_kinds=source_kinds),
            page=page,
            runs=runs,
        )

    @router.post(
        "/batch",
        response_model=RunsBatchResponse,
        operation_id="get_runs_batch",
        dependencies=[Depends(_GET_RUNS_BATCH_AUTHZ)],
    )
    def get_runs_batch(
        body: RunsBatchRequest,
        request: Request,
        response: Response,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> RunsBatchResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="runtime.run_batch",
        )
        runs = []
        source_kinds: list[SourceKind] = []
        for run_id in body.run_ids:
            run = ctx.run_index.get_run(run_id)
            enforce_run_tenant_access(request, ctx=ctx, run=run)
            runs.append(run.details)
            source_kinds.append(_as_source_kind(run.source_kind))
        record_data_access_audit(
            request,
            resource_id="run.batch",
            tenant_id=getattr(request.state, "tenant_id", None),
            metadata={"count": len(runs)},
        )
        response.headers["Link"] = '</api/v1/runs>; rel="collection"'
        return RunsBatchResponse(
            meta=build_meta(request, source_kinds=source_kinds),
            runs=runs,
        )

    @router.get("/compare", response_model=CompareRunResponse, operation_id="compare_runs")
    def compare_runs(
        request: Request,
        response: Response,
        run_a_id: str = Query(alias="a", min_length=1),
        run_b_id: str = Query(alias="b", min_length=1),
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> CompareRunResponse:
        run_a = ctx.run_index.get_run(run_a_id)
        run_b = ctx.run_index.get_run(run_b_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run_a)
        enforce_run_tenant_access(request, ctx=ctx, run=run_b)
        temporal_scope = _resolve_compare_temporal_scope(
            ctx,
            run_a,
            run_b,
            response,
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
        )
        set_authz_resource(
            request,
            tenant_id=run_a.details.tenant_id,
            kind="runtime.run_compare",
        )
        frame, comparability, deltas = ctx.compare.build_compare(
            run_a=run_a,
            run_b=run_b,
            temporal_scope=temporal_scope,
        )
        record_data_access_audit(
            request,
            resource_id=f"{run_a_id}:{run_b_id}",
            tenant_id=run_a.details.tenant_id,
            metadata={
                "comparability": comparability.status,
                "delta_count": len(deltas),
            },
        )
        response.headers["Link"] = (
            f'</api/v1/runs/{run_a_id}>; rel="run-a", </api/v1/runs/{run_b_id}>; rel="run-b"'
        )
        return CompareRunResponse(
            meta=build_meta(request, source_kinds=[run_a.source_kind, run_b.source_kind]),
            temporal_scope=temporal_scope,
            comparison_frame=frame,
            comparability=comparability,
            deltas=deltas,
        )

    @router.get("/live", include_in_schema=False)
    async def stream_runs_live(
        request: Request,
        cursor: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> StreamingResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="runtime.run_list",
        )
        scope = require_access_scope(request)
        record_data_access_audit(
            request,
            resource_id=scope.tenant_id,
            tenant_id=scope.tenant_id,
            outcome="stream_opened",
        )
        policy = LiveStreamPolicy.from_env()
        return StreamingResponse(
            _stream_payloads(
                lambda: _build_runs_live_payload(request, ctx),
                request,
                policy=policy,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-SSE-Flow-Control": (
                    f"adaptive; min={policy.min_interval_seconds}; "
                    f"max={policy.max_interval_seconds}; "
                    f"heartbeat={policy.keepalive_seconds}; "
                    f"budget={policy.max_duration_seconds}"
                ),
            },
        )

    @router.post(
        "/{run_id}/production-approval",
        response_model=ProductionApprovalResponse,
        operation_id="create_run_production_approval",
        dependencies=[
            Depends(_CREATE_PRODUCTION_APPROVAL_AUTHZ),
            Depends(_CREATE_PRODUCTION_APPROVAL_STEP_UP),
        ],
    )
    def create_run_production_approval(
        run_id: str,
        body: ProductionApprovalRequest,
        request: Request,
        response: Response,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> ProductionApprovalResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        tenant_id = run.details.tenant_id
        if tenant_id is None:
            raise service_unavailable(
                "The production approval run has no tenant authority binding",
                code="DS9-RAW-APPROVAL-NOT-AUTHORITY",
            )
        set_authz_resource(
            request,
            tenant_id=tenant_id,
            kind="runtime.production_approval",
        )

        control_service = _control_service_from_request(request)
        scorecard, scorecard_digest = production_approval_inputs_from_bound_request(
            request,
            run_id=run_id,
        )
        artifact_ownership = _artifact_ownership_evidence(
            ctx.store,
            tenant_id=tenant_id,
            cell_id=run.details.cell_id,
        )
        resolver = resolve_production_approval_resolver(request)
        if resolver is None:
            raise service_unavailable(
                "The production approval resolver is not installed",
                code="DS9-DECISION-PRODUCER-MISSING",
            )
        if (
            body.production_basis_ref is None
            or body.production_basis_digest is None
            or body.human_decision_record_ref is None
            or body.human_decision_record_digest is None
        ):
            raise service_unavailable(
                "Signed production basis and human decision record are required",
                code="DS9-DECISION-PRODUCER-MISSING",
            )
        try:
            authority = resolver.authorize_issuance(
                ProductionApprovalIssuanceInput(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    scorecard_ref=cast("str", scorecard.get("quality_scorecard_ref")),
                    scorecard_digest=scorecard_digest,
                    production_basis_ref=body.production_basis_ref,
                    production_basis_digest=body.production_basis_digest,
                    human_decision_record_ref=body.human_decision_record_ref,
                    human_decision_record_digest=body.human_decision_record_digest,
                    expected_consumer="polisyos.runtime.production_approval",
                    expected_audience="polisyos-runtime",
                )
            )
        except (ProductionApprovalResolutionError, ValueError) as exc:
            raise service_unavailable(
                "The production approval inputs are not independently verified",
                code=getattr(exc, "code", "DS9-RAW-APPROVAL-NOT-AUTHORITY"),
            ) from exc
        packet = build_resolved_production_approval_packet(
            authority,
            override=_validated_production_approval_override(request, body),
            artifact_ownership=artifact_ownership,
        )
        scope = require_access_scope(request)
        request_id = ensure_request_id(request)
        try:
            persisted = resolver.persist_authorized_packet(
                authority,
                packet,
                write_context=HumanDecisionWriteContext(
                    tenant_id=tenant_id,
                    cell_id=run.details.cell_id,
                    run_id=run_id,
                    job_id=f"production-approval-http-{request_id}",
                    trace_id=str(getattr(request.state, "trace_id", None) or f"trace-{request_id}"),
                    span_id=str(getattr(request.state, "span_id", None) or f"span-{request_id}"),
                    parent_span_id=None,
                    owner=scope.user_sub or scope.spiffe_id,
                    requested_execution_profile="governed",
                    effective_execution_profile="governed",
                    effective_mode_ref="runtime://production-approval/http",
                ),
            )
        except HumanDecisionPersistenceError as exc:
            raise service_unavailable(
                "The production approval owner format cannot accept a V2 authority packet",
                code=exc.code,
            ) from exc
        approval_packet_ref = {
            "artifact_id": persisted.packet_ref,
            "kind": "runtime.production_approval_packet",
            "media_type": "application/json",
        }
        record_approval_packet = getattr(
            control_service,
            "record_production_approval_packet",
            None,
        )
        if callable(record_approval_packet):
            record_approval_packet(
                run_id=run_id,
                approval_packet_ref=persisted.packet_ref,
                decision=packet.decision,
                request_access_scope=scope,
                scorecard=scorecard,
                approval_packet=packet.model_dump(mode="json", exclude_none=True),
            )
        record_data_access_audit(
            request,
            resource_id=run_id,
            tenant_id=tenant_id,
            outcome="approval_packet_created",
        )
        add_run_link_relations(response, run_id=run_id)
        return ProductionApprovalResponse.model_validate(
            {
                "meta": build_meta(request, source_kinds=[run.source_kind]),
                "run_id": run_id,
                "decision": packet.decision,
                "packet": packet,
                "approval_packet_ref": approval_packet_ref,
                "evidence_bundle_packet_path": None,
            }
        )

    @router.get(
        "/{run_id}/paper",
        response_model=RunPaperPacket,
        dependencies=[Depends(_GET_RUN_PAPER_AUTHZ)],
        operation_id="get_run_paper",
        summary="Get the replay-bound paper projection for one verified run",
    )
    def get_run_paper(
        run_id: str,
        request: Request,
        response: Response,
        replay_query: Annotated[RunPaperReplayQuery, Depends()],
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> RunPaperPacket:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        scope = require_access_scope(request)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_paper",
            artifact_id=(
                str(run.details.manifest_ref.artifact_id)
                if run.details.manifest_ref is not None
                else None
            ),
        )
        service = RunPaperProjectionService(
            store=ctx.store,
            core_runs_root=ctx.core_runs_root,
            tenant_id=scope.tenant_id,
        )
        packet = _resolve_replay_bound_paper_packet(
            request,
            run_id=run_id,
            service=service,
            replay_syntax_code="run_paper_replay_syntax_invalid",
            replay_conflict_code="run_paper_replay_conflict",
            source_invalid_code="run_paper_source_invalid",
        )
        record_data_access_audit(
            request,
            resource_id=run_id,
            tenant_id=run.details.tenant_id,
            outcome="run_paper_projected",
        )
        add_run_link_relations(response, run_id=run_id)
        return packet

    @router.get(
        "/{run_id}/case-inspection",
        response_model=CaseInspectionResponse,
        dependencies=[Depends(_GET_CASE_INSPECTION_AUTHZ)],
        operation_id="get_case_inspection",
        summary="Inspect the frozen case slot for one verified run",
    )
    def get_case_inspection(
        run_id: str,
        request: Request,
        response: Response,
        replay_query: Annotated[RunPaperReplayQuery, Depends()],
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> CaseInspectionResponse:
        try:
            run = ctx.run_index.get_run(run_id)
        except KeyError as exc:
            raise not_found(
                "Case inspection run was not found",
                code="case_inspection_run_not_found",
            ) from exc
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        scope = require_access_scope(request)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.case_inspection",
            artifact_id=(
                str(run.details.manifest_ref.artifact_id)
                if run.details.manifest_ref is not None
                else None
            ),
        )
        service = CaseInspectionService(
            RunPaperProjectionService(
                store=ctx.store,
                core_runs_root=ctx.core_runs_root,
                tenant_id=scope.tenant_id,
            )
        )
        packet = _resolve_replay_bound_paper_packet(
            request,
            run_id=run_id,
            service=service,
            replay_syntax_code="case_inspection_replay_syntax_invalid",
            replay_conflict_code="case_inspection_replay_pin_mismatch",
            source_invalid_code="case_inspection_source_invalid",
            missing_run_code="case_inspection_run_not_found",
            missing_run_message="Case inspection run was not found",
        )
        record_data_access_audit(
            request,
            resource_id=run_id,
            tenant_id=run.details.tenant_id,
            outcome="case_inspection_projected",
        )
        add_run_link_relations(response, run_id=run_id)
        return packet

    @router.get("/{run_id}", response_model=RunDetailsResponse, operation_id="get_run_details")
    def get_run_details(
        run_id: str,
        request: Request,
        response: Response,
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> RunDetailsResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        temporal_scope = _resolve_temporal_scope(
            ctx,
            run,
            response,
            surface="run_details",
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
        )
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run",
            artifact_id=(
                str(run.details.manifest_ref.artifact_id) if run.details.manifest_ref else None
            ),
        )
        record_data_access_audit(
            request,
            resource_id=run_id,
            tenant_id=run.details.tenant_id,
        )
        add_run_link_relations(response, run_id=run_id)
        run_details = ctx.temporal.project_run_details(run.details, temporal_scope)
        control_service = _control_service_from_request(request)
        operator_diagnostic = _latest_control_operator_diagnostic(control_service, run_id)
        policy_design_case_projection = _latest_control_policy_projection(
            control_service,
            run_id,
        )
        updates: dict[str, Any] = {}
        candidate_simulation = _candidate_simulation_projection(
            run_id=run.details.run_id,
            tenant_id=run.details.tenant_id,
            cell_id=run.details.cell_id,
            control_job_id=run.details.control_job_id,
            root_artifacts=tuple(run.details.root_artifacts),
            store=ctx.store,
            control_service=control_service,
        )
        if candidate_simulation is not None:
            updates["candidate_simulation"] = candidate_simulation
        if operator_diagnostic is not None:
            updates["operator_diagnostic"] = operator_diagnostic
        if policy_design_case_projection is not None:
            updates["policy_design_case_projection"] = policy_design_case_projection
        if updates:
            run_details = run_details.model_copy(update=updates)
        return RunDetailsResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            temporal_scope=temporal_scope,
            run=run_details,
        )

    @router.get("/{run_id}/live", include_in_schema=False)
    async def stream_run_live(
        run_id: str,
        request: Request,
        cursor: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> StreamingResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run",
            artifact_id=(
                str(run.details.manifest_ref.artifact_id) if run.details.manifest_ref else None
            ),
        )
        record_data_access_audit(
            request,
            resource_id=run_id,
            tenant_id=run.details.tenant_id,
            outcome="stream_opened",
        )
        policy = LiveStreamPolicy.from_env()
        return StreamingResponse(
            _stream_payloads(
                lambda: _build_run_live_payload(run_id, ctx),
                request,
                policy=policy,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-SSE-Flow-Control": (
                    f"adaptive; min={policy.min_interval_seconds}; "
                    f"max={policy.max_interval_seconds}; "
                    f"heartbeat={policy.keepalive_seconds}; "
                    f"budget={policy.max_duration_seconds}"
                ),
            },
        )

    @router.get(
        "/{run_id}/timeline",
        response_model=RunTimelineResponse,
        operation_id="get_run_timeline",
    )
    def get_run_timeline(
        run_id: str,
        request: Request,
        response: Response,
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> RunTimelineResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        temporal_scope = _resolve_temporal_scope(
            ctx,
            run,
            response,
            surface="run_timeline",
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
        )
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_timeline",
        )
        timeline = ctx.temporal.project_timeline(
            ctx.timeline.build_for_run(run).timeline,
            temporal_scope,
        )
        record_data_access_audit(
            request,
            resource_id=run_id,
            tenant_id=run.details.tenant_id,
        )
        add_run_link_relations(response, run_id=run_id)
        return RunTimelineResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            temporal_scope=temporal_scope,
            timeline=timeline,
        )

    @router.get(
        "/{run_id}/authority-values",
        response_model=RunAuthorityProjection,
        operation_id="get_run_authority_values",
        summary="Disposition of every retired readiness/scientific-depth value",
    )
    def get_run_authority_values(
        run_id: str,
        request: Request,
        response: Response,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> RunAuthorityProjection:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_authority_values",
        )
        projection = build_run_authority_projection(run_id)
        record_data_access_audit(
            request,
            resource_id=run_id,
            tenant_id=run.details.tenant_id,
            metadata={"value_count": len(projection.values)},
        )
        add_run_link_relations(response, run_id=run_id)
        return projection

    @router.get("/{run_id}/nodes", response_model=RunNodesResponse, operation_id="get_run_nodes")
    def get_run_nodes(
        run_id: str,
        request: Request,
        response: Response,
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> RunNodesResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        _resolve_temporal_scope(
            ctx,
            run,
            response,
            surface="run_nodes",
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
        )
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_nodes",
        )
        nodes = ctx.debug.list_run_nodes(run)
        record_data_access_audit(
            request,
            resource_id=run_id,
            tenant_id=run.details.tenant_id,
            metadata={"node_count": len(nodes)},
        )
        add_run_link_relations(response, run_id=run_id)
        return RunNodesResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            run_id=run_id,
            source_kind=run.source_kind,
            nodes=nodes,
        )

    @router.get(
        "/{run_id}/lineage",
        response_model=RunLineageResponse,
        operation_id="get_run_lineage",
    )
    def get_run_lineage(
        run_id: str,
        request: Request,
        response: Response,
        root_artifact_id: list[str] | None = Query(default=None),
        max_depth: int | None = Query(default=None, ge=1, le=256),
        max_nodes: int | None = Query(default=None, ge=1, le=20000),
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> RunLineageResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        temporal_scope = _resolve_temporal_scope(
            ctx,
            run,
            response,
            surface="run_lineage",
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
        )
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_lineage",
        )

        root_ids = ctx.run_index.resolve_root_artifact_ids(
            run,
            requested_root_ids=root_artifact_id or None,
        )
        if (
            temporal_scope is not None
            and ctx.temporal.project_run_details(run.details, temporal_scope).finished_at is None
        ):
            visible_timeline = ctx.temporal.project_timeline(
                ctx.timeline.build_for_run(run).timeline,
                temporal_scope,
            )
            visible_output_ids = {
                artifact_id
                for event in visible_timeline.events
                for artifact_id in event.output_artifact_ids
            }
            root_ids = [
                artifact_id for artifact_id in root_ids if str(artifact_id) in visible_output_ids
            ]

        if not root_ids and temporal_scope is None:
            raise bad_request(
                "No root artifacts available for lineage resolution",
                code="lineage_roots_missing",
            )

        try:
            lineage = (
                ctx.lineage.build_for_artifact_ids(
                    root_ids,
                    max_depth=max_depth,
                    max_nodes=max_nodes,
                )
                if root_ids
                else ArtifactLineageView(root_artifact_ids=[])
            )
        except LineageSurfaceAdmissionError as exc:
            raise conflict(
                "Run lineage blocked or downgraded by composed authority surface admission",
                code="authority_surface_admission_blocked",
                extensions={
                    "run_id": run_id,
                    "authority_surface_decision": exc.decision.model_dump(mode="json"),
                },
            ) from exc
        record_data_access_audit(
            request,
            resource_id=run_id,
            tenant_id=run.details.tenant_id,
            metadata={"root_artifact_count": len(root_ids)},
        )
        add_run_link_relations(response, run_id=run_id)
        return RunLineageResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            run_id=run_id,
            temporal_scope=temporal_scope,
            lineage=lineage,
        )

    @router.get(
        "/{run_id}/quantities",
        response_model=RunQuantitiesResponse,
        operation_id="get_run_quantities",
    )
    def get_run_quantities(
        run_id: str,
        request: Request,
        response: Response,
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> RunQuantitiesResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        temporal_scope = _resolve_temporal_scope(
            ctx,
            run,
            response,
            surface="run_quantities",
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
        )
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_quantities",
        )
        try:
            ctx.lineage.assert_run_decision_surface_allowed(run, surface="run_quantities")
            quantities, coverage, entries = ctx.lineage.build_quantity_inventory_for_run(run)
        except LineageSurfaceAdmissionError as exc:
            raise conflict(
                "Run quantities blocked or downgraded by composed authority surface admission",
                code="authority_surface_admission_blocked",
                extensions={
                    "run_id": run_id,
                    "authority_surface_decision": exc.decision.model_dump(mode="json"),
                },
            ) from exc
        quantities, coverage, entries = ctx.temporal.project_quantities(
            quantities,
            entries,
            temporal_scope,
        )
        record_data_access_audit(
            request,
            resource_id=run_id,
            tenant_id=run.details.tenant_id,
            metadata={
                "quantity_count": len(quantities),
                "untraced": coverage.untraced,
            },
        )
        add_run_link_relations(response, run_id=run_id)
        return RunQuantitiesResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            run_id=run_id,
            source_kind=run.source_kind,
            temporal_scope=temporal_scope,
            quantities=quantities,
            coverage=coverage,
            entries=entries,
        )

    @router.get(
        "/{run_id}/fabric-decision-data",
        response_model=FabricDecisionDataResponse,
        operation_id="get_run_fabric_decision_data",
    )
    def get_run_fabric_decision_data(
        run_id: str,
        request: Request,
        response: Response,
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> FabricDecisionDataResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        temporal_scope = _resolve_temporal_scope(
            ctx,
            run,
            response,
            surface="run_fabric_decision_data",
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
        )
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_fabric_decision_data",
        )
        try:
            ctx.lineage.assert_run_decision_surface_allowed(run, surface="run_fabric_decision_data")
            quantities, runtime_coverage, entries = ctx.lineage.build_quantity_inventory_for_run(
                run
            )
        except LineageSurfaceAdmissionError as exc:
            raise conflict(
                "Run fabric decision data blocked or downgraded by composed authority "
                "surface admission",
                code="authority_surface_admission_blocked",
                extensions={
                    "run_id": run_id,
                    "authority_surface_decision": exc.decision.model_dump(mode="json"),
                },
            ) from exc
        quantities, runtime_coverage, _entries = ctx.temporal.project_quantities(
            quantities,
            entries,
            temporal_scope,
        )
        decision_data, coverage = ctx.lineage.build_fabric_decision_data_for_quantities(
            quantities,
            runtime_coverage,
            temporal_scope=temporal_scope,
            source_contract=ctx.lineage.source_contract_ref_for_run(run),
        )
        record_data_access_audit(
            request,
            resource_id=run_id,
            tenant_id=run.details.tenant_id,
            metadata={
                "decision_data_count": len(decision_data),
                "untraced": coverage.untraced,
            },
        )
        add_run_link_relations(response, run_id=run_id)
        return FabricDecisionDataResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]).model_dump(mode="json"),
            run_id=run_id,
            source_kind=run.source_kind,
            temporal_scope=FabricTemporalRef.from_runtime_scope(temporal_scope),
            decision_data=decision_data,
            coverage=coverage,
        )

    @router.get(
        "/{run_id}/compare-candidates",
        response_model=CompareCandidatesResponse,
        operation_id="get_run_compare_candidates",
    )
    def get_run_compare_candidates(
        run_id: str,
        request: Request,
        response: Response,
        limit: int = Query(default=20, ge=1, le=100),
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> CompareCandidatesResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        temporal_scope = _resolve_temporal_scope(
            ctx,
            run,
            response,
            surface="run_compare",
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
        )
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_compare_candidates",
        )
        summaries, _page = ctx.run_index.list_runs(
            limit=100,
            tenant_id=run.details.tenant_id,
        )
        candidates = []
        for summary in summaries:
            if summary.run_id == run_id:
                continue
            candidate = ctx.run_index.get_run(summary.run_id)
            candidates.append(
                ctx.compare.candidate_for(
                    run=run,
                    candidate=candidate,
                    temporal_scope=temporal_scope,
                )
            )
        candidates.sort(
            key=lambda item: (
                {"compatible": 0, "warning": 1, "blocked": 2}[item.comparability.status],
                {"baseline": 0, "previous": 1, "recommended": 2, "selected": 3}[item.relation],
                item.run_id,
            )
        )
        candidates = candidates[:limit]
        record_data_access_audit(
            request,
            resource_id=run_id,
            tenant_id=run.details.tenant_id,
            metadata={"candidate_count": len(candidates)},
        )
        add_run_link_relations(response, run_id=run_id)
        return CompareCandidatesResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            run_id=run_id,
            candidates=candidates,
        )

    @router.get(
        "/{run_id}/agents",
        response_model=AgentPipelineResponse,
        operation_id="get_run_agents",
    )
    def get_run_agents(
        run_id: str,
        request: Request,
        response: Response,
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> AgentPipelineResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        _resolve_temporal_scope(
            ctx,
            run,
            response,
            surface="run_agents",
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
        )
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_agents",
        )
        pipeline = ctx.debug.get_run_agents(run)
        record_data_access_audit(
            request,
            resource_id=run_id,
            tenant_id=run.details.tenant_id,
        )
        add_run_link_relations(response, run_id=run_id)
        return AgentPipelineResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            pipeline=pipeline,
        )

    @router.get(
        "/{run_id}/evidence-context",
        response_model=RunEvidenceContextResponse,
        operation_id="get_run_evidence_context",
    )
    def get_run_evidence_context(
        run_id: str,
        request: Request,
        response: Response,
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> RunEvidenceContextResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        _resolve_temporal_scope(
            ctx,
            run,
            response,
            surface="run_evidence_context",
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
        )
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_evidence_context",
        )
        evidence_context = _overlay_live_promotion_decisions(
            ctx.debug.get_run_evidence_context(run),
            _control_service_from_request(request),
        )
        record_data_access_audit(
            request,
            resource_id=run_id,
            tenant_id=run.details.tenant_id,
        )
        add_run_link_relations(response, run_id=run_id)
        return RunEvidenceContextResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            context=evidence_context,
        )

    @router.get(
        "/{run_id}/workflow",
        response_model=RunWorkflowResponse,
        operation_id="get_run_workflow",
    )
    def get_run_workflow(
        run_id: str,
        request: Request,
        response: Response,
        valid_at: datetime | None = Query(default=None),
        tx_at: datetime | None = Query(default=None),
        t: datetime | None = Query(default=None, alias="t"),
        branch: str | None = Query(default=None),
        snapshot_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> RunWorkflowResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        _resolve_temporal_scope(
            ctx,
            run,
            response,
            surface="run_workflow",
            valid_at=valid_at,
            tx_at=tx_at,
            t=t,
            branch=branch,
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
        )
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_workflow",
        )
        workflow = ctx.debug.get_run_workflow(run)
        record_data_access_audit(
            request,
            resource_id=run_id,
            tenant_id=run.details.tenant_id,
        )
        add_run_link_relations(response, run_id=run_id)
        return RunWorkflowResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            workflow=workflow,
        )
