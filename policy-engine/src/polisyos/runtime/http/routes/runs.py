"""Public routes runs module API."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from time import monotonic
from typing import TYPE_CHECKING, Annotated, Any, Literal, Protocol, cast

from pydantic import ValidationError

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactOwnershipError,
    ArtifactRef,
    SelectedProfileVerificationReader,
    artifact_ref_for_manifest,
    artifact_ref_identity_key,
    raise_artifact_read_access_error,
    read_core_json_artifact,
    read_core_json_artifact_bounded,
    read_core_manifest_profile,
)
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
    CompletedExAnteCandidateComparisonResponse,
    CompletedExAnteCandidateRanking,
    DirectMethodExecutionRunProjection,
    MethodExecutionProducerDiagnostic,
    MethodMetricCandidateScore,
    MethodMetricProjectionResponse,
    RunCandidateSimulationAcquisitionHistoryEntry,
    RunCandidateSimulationAcquisitionHistoryEntryV3,
    RunCandidateSimulationChildProfileBinding,
    RunCandidateSimulationN5Observation,
    RunCandidateSimulationN8ChildSourceBinding,
    RunCandidateSimulationProjection,
    RunConditionalTransportCandidateProjection,
    RunDetailsResponse,
    RunEvidenceContextResponse,
    RunEvidenceContextView,
    RunGenericCycleSimulationChildProfileBinding,
    RunGenericCycleSimulationN5Observation,
    RunGenericCycleSimulationN5ResultBody,
    RunGenericCycleSimulationN6CycleHistoryEntry,
    RunGenericCycleSimulationProjection,
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
    OptionalActionPermissionResult,
    ResourceBindingSource,
    ResourceBindingSpec,
    principal_from_access_scope,
    require_action_permission,
    require_optional_action_permission,
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
    CANONICAL_PROFILE_REFUSAL_RESPONSES,
    RuntimeDependencyError,
    bad_request,
    conflict,
    forbidden,
    not_found,
    service_unavailable,
    unprocessable_entity,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.resource_binding import (
    _resolve_method_execution_indexed_run,
    production_approval_inputs_from_bound_request,
)
from polisyos.runtime.http.response_policies import add_run_link_relations
from polisyos.runtime.http.services.authority_values import (
    RunAuthorityProjection,
    build_run_authority_projection,
)
from polisyos.runtime.http.services.candidate_hte_packet_projection import (
    DECISION_PACKET_CANDIDATE_READ_LIMITS,
    CandidateDecisionPacketHTEProjection,
    CandidatePacketProjectionRefusalError,
    candidate_packet_source_selector,
    project_candidate_hte_packet,
    require_candidate_projection_scope,
    require_exact_candidate_packet_ref,
    require_same_candidate_source_run,
    validate_bounded_candidate_packet,
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
from polisyos.runtime.http.services.human_decision_contracts import (
    HumanDecisionWriteContext,
)
from polisyos.runtime.http.services.human_decisions import HumanDecisionPersistenceError
from polisyos.runtime.http.services.lineage import LineageSurfaceAdmissionError
from polisyos.runtime.http.services.predictive_calibration import (
    PredictiveCalibrationError,
    PredictiveCalibrationRequest,
    PredictiveCalibrationResponse,
    load_run_predictive_calibration,
    produce_run_predictive_calibration,
)
from polisyos.runtime.http.services.run_paper_contracts import (
    RunPaperPacket,
    RunPaperReplayConflictError,
    RunPaperReplayQuery,
    RunPaperReplaySyntaxError,
    RunPaperSourceError,
)
from polisyos.runtime.http.services.run_paper_projection import (
    RunPaperProjectionService,
)
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

    from polisyos.core.artifacts import ArtifactStore
    from polisyos.core.artifacts.manifest import ArtifactManifest
    from polisyos.core.artifacts.manifest import InputRef as CoreInputRef
    from polisyos.ir import InputRef as IRInputRef
    from polisyos.runtime.http.services.run_index import IndexedRunRecord
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationN5InputV5,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveGenerationCyclePartialRunV2,
        RecursiveGenerationCyclePartialRunV3,
        RecursiveGenerationCycleRun,
    )
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
_CREATE_RUN_PREDICTIVE_CALIBRATION_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_FEEDBACK_EVALUATE,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_PATH,
        resource_kind="runtime.run.predictive_calibration",
        path_parameter="run_id",
    ),
)
_GET_RUN_PREDICTIVE_CALIBRATION_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_REVIEW,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_PATH,
        resource_kind="runtime.run.predictive_calibration",
        path_parameter="run_id",
        allow_empty_body=True,
    ),
)
_GET_RUN_METHOD_METRICS_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_REVIEW,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_PATH,
        resource_kind="runtime.run.method_metrics",
        path_parameter="run_id",
        allow_empty_body=True,
    ),
)
_GET_RUN_CANDIDATE_PACKET_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_REVIEW,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_PATH,
        resource_kind="runtime.run.method_execution_selection",
        path_parameter="run_id",
        path_selector_parameters=("packet_id",),
        query_selector_parameters=("manifest_profile_sha256",),
        allow_empty_body=True,
    ),
)
_GET_RUN_METHOD_SELECTION_AUTHZ = require_optional_action_permission(
    RuntimePermission.RUNS_REVIEW,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_PATH,
        resource_kind="runtime.run.method_execution_selection",
        path_parameter="run_id",
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


def _selected_target_baseline_hashes(
    before: CandidateSimulationN5InputV5, after: CandidateSimulationN5InputV5
) -> tuple[str, str] | None:
    """Hash the exact selected target baseline before and after N5 re-entry."""

    if before.materialization.target_world_slot != after.materialization.target_world_slot:
        return None
    target_slot = before.materialization.target_world_slot
    before_value = before.profile.n5.baseline_state.get(target_slot)
    after_value = after.profile.n5.baseline_state.get(target_slot)
    if before_value is None or after_value is None:
        return None
    from polisyos.core.canon import CanonSpec, to_canonical_bytes

    def digest(value: float) -> str:
        payload = {"target_world_slot": target_slot, "baseline_value": value}
        return (
            "sha256:"
            + hashlib.sha256(
                to_canonical_bytes(payload, CanonSpec(forbid_floats=False))
            ).hexdigest()
        )

    hashes = digest(before_value), digest(after_value)
    return None if hashes[0] == hashes[1] else hashes


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
) -> tuple[
    tuple[
        RunCandidateSimulationAcquisitionHistoryEntry
        | RunCandidateSimulationAcquisitionHistoryEntryV3,
        ...,
    ],
    str | None,
]:
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

    from polisyos.core.artifacts import artifact_ref_identity_key

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
    except CanonicalProfileRefusalError:
        raise
    except Exception:
        return (), "acquisition_action_history_integrity_not_established"
    if not heads:
        return (), "acquisition_action_history_not_observed"

    from polisyos.core.artifacts import (
        ArtifactID,
        ArtifactRef,
        artifact_ref_identity_key,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionRouteLoopReceipt,
        AcquisitionRoutePhaseReceipt,
    )
    from polisyos.runtime.quality.authority_reconciliation import (
        reconcile_authority_ref,
    )
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationN5InputV5,
    )
    from polisyos.runtime.quality.generation_cycle import (
        AcquisitionOverlayReentryReceipt,
        _current_candidate_summaries,
        validate_acquisition_overlay_continuation,
    )
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
        expected_version: str | tuple[str, ...],
        expected_job_id: str,
    ) -> tuple[Any, bytes, Any, ArtifactRef]:
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
        manifest = read_core_manifest_profile(store, ref)[0]
        ref = artifact_ref_for_manifest(manifest)
        if not store.verify(ref).ok:
            raise ValueError("acquisition_history_artifact_integrity_not_established")
        schema = manifest.artifact_schema
        if (
            manifest.kind != expected_kind
            or manifest.media_type != "application/json"
            or schema is None
            or schema.name != expected_schema
            or schema.version
            not in (
                expected_version if isinstance(expected_version, tuple) else (expected_version,)
            )
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
        # Preserve the exact manifest view selected for this GET. The action head
        # remains ID-only; this reader-materialized profile is not producer attestation
        # and does not promote currentness, status, or authority.
        return (
            read_core_json_artifact(store, ref, raw_payload_bytes=payload_bytes).value,
            payload_bytes,
            report,
            ref,
        )

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
        ):
            raise ValueError("acquisition_reentry_n5_input_ref_invalid")
        manifest = read_core_manifest_profile(store, input_ref)[0]
        if not store.verify(input_ref).ok:
            raise ValueError("acquisition_reentry_n5_input_ref_invalid")
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
        history_entries: list[
            RunCandidateSimulationAcquisitionHistoryEntry
            | RunCandidateSimulationAcquisitionHistoryEntryV3
        ] = []
        matching_receipts: list[
            tuple[
                Any,
                ArtifactRef,
                AcquisitionRouteLoopReceipt | RunCandidateSimulationAcquisitionHistoryEntryV3,
                Any,
            ]
        ] = []
        matching_incomplete = False
        for head in heads:
            verified_source = None
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
                route_payload, _route_bytes, route_report, route_receipt_ref = (
                    _read_authority_payload(
                        route_receipt_ref,
                        expected_kind="runtime_quality.acquisition_route_loop_receipt",
                        expected_schema="polisyos.runtime.AcquisitionRouteLoopReceipt",
                        expected_version=("1.0", "2.0"),
                        expected_job_id=head.job_id,
                    )
                )
                route_manifest = read_core_manifest_profile(store, route_receipt_ref)[0]
                route_schema = route_manifest.artifact_schema
                if route_schema is None:
                    raise ValueError("acquisition_history_terminal_schema_missing")
                if route_schema.version == "2.0":
                    # Dispatch by the selected manifest epoch before legacy parsing.
                    # The Runtime owner reopens the actual closure; payload flags
                    # and a readable decision blob cannot establish this join.
                    if not isinstance(route_payload, dict):
                        raise ValueError("acquisition_history_terminal_payload_invalid")
                    if route_payload.get("compiled_ref") != str(compiled_ref.artifact_id):
                        continue
                    from polisyos.runtime.quality.acquisition_evaluation_history import (
                        verify_acquisition_retention_history,
                    )

                    verified = verify_acquisition_retention_history(
                        artifact_store=store,
                        event_log=event_log,
                        control_store=control_store,
                        control_service=control_service,
                        head=head,
                        route_receipt_ref=route_receipt_ref,
                        compiled_ref=compiled_ref,
                        source_run_id=source_run_id,
                        source_job_id=source_job_id,
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                    )
                    verified_source = verified
                    if verified.history_entry is not None:
                        if verified.legacy_receipt is not None:
                            raise ValueError("acquisition_history_v3_projection_ambiguous")
                        matching_receipts.append(
                            (
                                head,
                                route_receipt_ref,
                                RunCandidateSimulationAcquisitionHistoryEntryV3.model_validate(
                                    verified.history_entry
                                ),
                                verified_source,
                            )
                        )
                        continue
                    if verified.legacy_receipt is None:
                        raise ValueError("acquisition_history_v3_projection_missing")
                    route_receipt = verified.legacy_receipt
                else:
                    route_receipt = AcquisitionRouteLoopReceipt.model_validate(route_payload)
                receipt = route_receipt
            else:
                route_receipt_ref = _selected_ref(
                    head.receipt_ref,
                    kind="runtime_quality.acquisition_route_phase_receipt",
                )
                route_payload, _route_bytes, route_report, route_receipt_ref = (
                    _read_authority_payload(
                        route_receipt_ref,
                        expected_kind="runtime_quality.acquisition_route_phase_receipt",
                        expected_schema="polisyos.runtime.AcquisitionRoutePhaseReceipt",
                        expected_version=("1.0", "1.1"),
                        expected_job_id=head.job_id,
                    )
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
            matching_receipts.append((head, route_receipt_ref, route_receipt, verified_source))

        if not matching_receipts and not history_entries:
            if matching_incomplete:
                return (), "acquisition_action_history_incomplete"
            return (), "acquisition_action_history_not_observed"

        for _head, route_receipt_ref, route_receipt, verified_source in matching_receipts:
            if isinstance(route_receipt, RunCandidateSimulationAcquisitionHistoryEntryV3):
                history_entries.append(route_receipt)
                continue
            if route_receipt.terminal_outcome == "quarantined_no_growth":
                observed_origin_source_ref = None
                if compiled.n4_recursive_source_ref is not None:
                    observed_origin_source_ref = ArtifactRef.model_validate(
                        compiled.n4_recursive_source_ref.model_dump(mode="json")
                    )
                history_entries.append(
                    RunCandidateSimulationAcquisitionHistoryEntry(
                        route_receipt_ref=route_receipt_ref,
                        route_id=route_receipt.route_id,
                        action_generation=route_receipt.action_generation,
                        terminal_outcome="quarantined_no_growth",
                        origin_source_ref=observed_origin_source_ref,
                        schema_version=(
                            "policyos.runtime.run_candidate_simulation_acquisition_history.v2"
                        ),
                        reentry_receipt_schema_version=None,
                        continuation_join_status="not_applicable",
                        origin_source_binding_status=(
                            "observed_only"
                            if observed_origin_source_ref is not None
                            else "not_supplied"
                        ),
                    )
                )
                continue
            if route_receipt.reentry_receipt_ref is None:
                raise ValueError("acquisition_reentry_ref_missing")
            reentry_receipt_ref = _selected_ref(
                route_receipt.reentry_receipt_ref,
                kind="runtime_quality.acquisition_overlay_reentry_receipt",
            )
            reentry_payload, _reentry_bytes, _reentry_report, reentry_receipt_ref = (
                _read_authority_payload(
                    reentry_receipt_ref,
                    expected_kind="runtime_quality.acquisition_overlay_reentry_receipt",
                    expected_schema="polisyos.runtime.AcquisitionOverlayReentryReceipt",
                    expected_version=("1.0", "2.0"),
                    expected_job_id=route_receipt.source_job_id,
                )
            )
            reentry_receipt = AcquisitionOverlayReentryReceipt.model_validate(reentry_payload)
            if (
                reentry_receipt.design_problem_ref != compiled.design_problem_ref
                or reentry_receipt.new_cycle.design_problem_ref
                != reentry_receipt.design_problem_ref
                or reentry_receipt.new_cycle.cycle_index != reentry_receipt.source_cycle_index + 1
            ):
                raise ValueError("acquisition_reentry_route_binding_mismatch")

            if verified_source is not None:
                source_run = verified_source.source_generation_run
                selected_source_cycle = verified_source.source_cycle
                if source_run is None or selected_source_cycle is None:
                    raise ValueError("acquisition_reentry_verified_source_missing")
                source_runs = (source_run,)
            else:
                selected_source_cycle = None
                source_runs = tuple(
                    node.cycle_run
                    for node in recursive_run.nodes
                    if isinstance(node, RecursiveCycleNode)
                    and node.cycle_run is not None
                    and node.design_problem_ref == reentry_receipt.design_problem_ref
                    and any(
                        cycle.cycle_index == reentry_receipt.source_cycle_index
                        for cycle in node.cycle_run.cycles
                    )
                )
            source_cycles = tuple(
                cycle
                for run in source_runs
                for cycle in run.cycles
                if cycle.cycle_index == reentry_receipt.source_cycle_index
            )
            if (
                len(source_cycles) != 1
                or source_cycles[0].selected_candidate_ref != reentry_receipt.source_candidate_ref
                or source_cycles[0].simulation.candidate_id != reentry_receipt.source_candidate_ref
            ):
                raise ValueError("acquisition_reentry_source_candidate_binding_mismatch")
            source_cycle = source_cycles[0]
            if selected_source_cycle is not None and source_cycle != selected_source_cycle:
                raise ValueError("acquisition_reentry_verified_source_cycle_mismatch")
            if len(source_runs) != 1:
                raise ValueError("acquisition_reentry_source_run_ambiguous")
            source_run = source_runs[0]
            if reentry_receipt.schema_version.endswith(".v3"):
                validate_acquisition_overlay_continuation(source_run, reentry_receipt)
            old_source_ref = source_cycle.simulation.candidate_simulation_n4_source_ref
            old_input_ref = source_cycle.simulation.candidate_simulation_n5_input_ref
            old_source = None
            if (old_source_ref is None) != (old_input_ref is None):
                raise ValueError("acquisition_reentry_old_candidate_source_incomplete")
            if old_source_ref is not None and old_input_ref is not None:
                old_evaluation_job_id = (
                    verified_source.source_evaluation_job_id
                    if verified_source is not None
                    else source_job_id
                )
                if not old_evaluation_job_id:
                    raise ValueError("acquisition_reentry_old_evaluation_job_missing")
                old_input, old_source = _resolve_n5_v5_source(
                    ArtifactRef.model_validate(old_input_ref.model_dump(mode="json")),
                    expected_run_id=source_run_id,
                    expected_job_id=old_evaluation_job_id,
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
            expected_origin_source_ref = None
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
                expected_origin_source_ref = ArtifactRef.model_validate(
                    expected_origin_ref.model_dump(mode="json")
                )
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
                selected_target_hashes = _selected_target_baseline_hashes(old_input, new_input)
                if (
                    old_input is None
                    or old_input.profile.profile_selection_ref
                    != new_input.profile.profile_selection_ref
                    or old_source.profile_selection_ref != old_input.profile.profile_selection_ref
                    or new_source.profile_selection_ref != new_input.profile.profile_selection_ref
                ):
                    raise ValueError(
                        "acquisition_reentry_same_candidate_profile_selection_mismatch"
                    )
                if (
                    selected_target_hashes is None
                    or selected_target_hashes[0] == selected_target_hashes[1]
                ):
                    raise ValueError("acquisition_reentry_selected_target_input_not_changed")

            continuation_projection = None
            if reentry_receipt.schema_version.endswith(".v3"):
                continued = reentry_receipt.continued_generation_run
                if continued is None:
                    raise ValueError("acquisition_reentry_continuation_missing")
                if old_input is None:
                    target_hashes = None
                    previous_n4_ref = None
                    previous_n5_ref = None
                    previous_profile_selection_ref = None
                    previous_profile_content_hash = None
                else:
                    target_hashes = _selected_target_baseline_hashes(old_input, new_input)
                    previous_n4_ref = ArtifactRef.model_validate(
                        old_input.n4_source_ref.model_dump(mode="json")
                    )
                    previous_n5_ref = ArtifactRef.model_validate(
                        source_cycle.simulation.candidate_simulation_n5_input_ref.model_dump(
                            mode="json"
                        )
                    )
                    previous_profile_selection_ref = old_input.profile.profile_selection_ref
                    previous_profile_content_hash = old_input.profile.content_hash
                if same_candidate and (
                    target_hashes is None or target_hashes[0] == target_hashes[1]
                ):
                    raise ValueError("acquisition_reentry_selected_target_input_not_changed")
                from polisyos.core.contracts.runtime import (
                    RunCandidateSimulationAcquisitionContinuationProjection,
                    RunCandidateSimulationContinuationFronts,
                    RunCandidateSimulationCurrentOccurrence,
                )

                current_occurrences = _current_candidate_summaries(continued.candidate_summaries)
                source_currentness = reentry_receipt.source_run_currentness
                continuation_currentness = reentry_receipt.continuation_currentness
                continuation_projection = RunCandidateSimulationAcquisitionContinuationProjection(
                    source_generation_run_content_hash=(
                        reentry_receipt.source_generation_run_content_hash
                    ),
                    continued_generation_run_content_hash=(
                        reentry_receipt.continued_generation_run_content_hash
                    ),
                    source_cycle_index=reentry_receipt.source_cycle_index,
                    continued_cycle_index=reentry_receipt.new_cycle.cycle_index,
                    previous_n4_source_ref=previous_n4_ref,
                    previous_n5_input_ref=previous_n5_ref,
                    selected_n4_source_ref=new_source_ref,
                    selected_n5_input_ref=new_input_ref,
                    previous_profile_selection_ref=previous_profile_selection_ref,
                    previous_profile_content_hash=previous_profile_content_hash,
                    selected_profile_selection_ref=new_input.profile.profile_selection_ref,
                    selected_profile_content_hash=new_input.profile.content_hash,
                    selected_target_world_slot=new_input.materialization.target_world_slot,
                    previous_selected_target_baseline_hash=(
                        target_hashes[0] if target_hashes is not None else None
                    ),
                    selected_target_baseline_hash=(
                        target_hashes[1] if target_hashes is not None else None
                    ),
                    source_currentness_status=(
                        source_currentness.status
                        if source_currentness is not None
                        else "not_established"
                    ),
                    source_currentness_reason=(
                        source_currentness.reason_code
                        if source_currentness is not None
                        else "currentness_observation_unavailable"
                    ),
                    continuation_currentness_status=(
                        continuation_currentness.status
                        if continuation_currentness is not None
                        else "not_established"
                    ),
                    continuation_currentness_reason=(
                        continuation_currentness.reason_code
                        if continuation_currentness is not None
                        else "currentness_observation_unavailable"
                    ),
                    n9_status=continued.promotion_port.status,
                    n9_reason=continued.promotion_port.reason,
                    n9_certified_candidate_ids=continued.promotion_port.certified_candidate_ids,
                    current_candidate_occurrences=tuple(
                        RunCandidateSimulationCurrentOccurrence(
                            candidate_id=row.candidate_id,
                            cycle_index=row.cycle_index,
                            content_hash=row.content_hash,
                            source_content_hash=row.source_content_hash,
                            front=row.front,
                            certified_by_n9=row.certified_by_n9,
                        )
                        for row in current_occurrences
                    ),
                    current_fronts=RunCandidateSimulationContinuationFronts(
                        decision_candidate_ids=continued.fronts.decision.candidate_ids,
                        research_candidate_ids=continued.fronts.research.candidate_ids,
                        quarantine_candidate_ids=continued.fronts.quarantine.candidate_ids,
                        portfolio_candidate_ids=continued.fronts.portfolio.candidate_ids,
                    ),
                )
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
                    expected_origin_source_ref=expected_origin_source_ref,
                    schema_version=(
                        "policyos.runtime.run_candidate_simulation_acquisition_history.v2"
                    ),
                    reentry_receipt_schema_version=reentry_receipt.schema_version,
                    continuation_join_status=(
                        "v3_occurrence_joined"
                        if reentry_receipt.schema_version
                        == "policyos.runtime.acquisition_overlay_reentry.v3"
                        else "legacy_occurrence_unbound"
                    ),
                    origin_source_binding_status=(
                        "verified_same_candidate_root"
                        if same_candidate
                        else (
                            "observed_only"
                            if new_source.origin_source_ref is not None
                            else "not_supplied"
                        )
                    ),
                    continuation=continuation_projection,
                )
            )
        return tuple(history_entries), None
    except CanonicalProfileRefusalError:
        raise
    except Exception:
        return (), "acquisition_action_history_integrity_not_established"


def _n5_interaction_evidence_projection(result: object | None) -> dict[str, Any] | None:
    """Project exact validated paired-scope samples into the run readback DTO."""

    if result is None:
        return None
    from polisyos.core.contracts.runtime import (
        RunN5InteractionEvidence,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JOINT_SIMULATION_HORIZON_PAIRED_INTERACTION_UNCERTAINTY_SCHEMA_VERSION,
    )

    schema_version = str(result.schema_version)
    current = (
        schema_version == JOINT_SIMULATION_HORIZON_PAIRED_INTERACTION_UNCERTAINTY_SCHEMA_VERSION
    )
    terms: list[dict[str, Any]] = []
    for term in result.interaction_terms:
        summaries: dict[int, dict[str, Any]] = {}
        if current:
            for step, summary in term.replication_sampling_by_step.items():
                values = tuple(
                    {
                        "seed": sample.seed,
                        "value": sample.effects["derived_effect"],
                    }
                    for sample in summary.samples
                )
                summaries[int(step)] = {
                    "status": summary.status,
                    "replicate_count": summary.replicate_count,
                    "seeds": summary.seeds,
                    "samples": values,
                    "mean": term.by_step[step],
                    "standard_error": summary.effects_standard_error["derived_effect"],
                }
        terms.append(
            {
                "atom_ids": term.atom_ids,
                "outcome": term.outcome,
                "by_step": term.by_step,
                "replication_sampling_by_step": summaries,
            }
        )
    residual_sampling: dict[str, dict[int, dict[str, Any]]] = {}
    if current:
        for outcome, by_step in result.higher_order_residual_sampling.items():
            projected_steps: dict[int, dict[str, Any]] = {}
            for step, summary in by_step.items():
                projected_steps[int(step)] = {
                    "status": summary.status,
                    "replicate_count": summary.replicate_count,
                    "seeds": summary.seeds,
                    "samples": tuple(
                        {
                            "seed": sample.seed,
                            "value": sample.effects["derived_effect"],
                        }
                        for sample in summary.samples
                    ),
                    "mean": result.higher_order_residuals[outcome][step],
                    "standard_error": summary.effects_standard_error["derived_effect"],
                }
            residual_sampling[outcome] = projected_steps
    if current:
        feedback = result.feedback_classification
        numeric = feedback.numeric_interaction
        basis = feedback.numeric_interaction_basis
        sampling_status = feedback.interaction_sampling_status
    else:
        # A v1-v3 numeric label was not bound to complete paired interaction
        # summaries. Preserve its means for history, but never its old authority.
        numeric = "unsupported"
        basis = "not_established"
        sampling_status = "not_established"
    projection = RunN5InteractionEvidence(
        schema_version=schema_version,
        numeric_interaction=numeric,
        numeric_interaction_basis=basis,
        interaction_sampling_status=sampling_status,
        interaction_terms=tuple(terms),
        higher_order_residuals=result.higher_order_residuals,
        higher_order_residual_sampling=residual_sampling,
        checked_interaction_orders=result.feedback_classification.checked_interaction_orders,
    )
    return projection.model_dump(mode="json")


def _n5_interaction_scope_fields(result: object | None) -> dict[str, tuple[int, ...]]:
    """Project the selected result's horizon and replicate axes into its parent DTO."""

    if result is None:
        return {}
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JOINT_SIMULATION_HORIZON_PAIRED_INTERACTION_UNCERTAINTY_SCHEMA_VERSION,
    )

    if (
        str(result.schema_version)
        != JOINT_SIMULATION_HORIZON_PAIRED_INTERACTION_UNCERTAINTY_SCHEMA_VERSION
    ):
        return {}
    return {
        "executed_steps": tuple(result.horizon.steps()),
        "replication_seeds": tuple(result.diagnostics.get("replication_seeds", ())),
    }


def _is_n5_interaction_scope_validation_error(error: ValidationError) -> bool:
    """Recognize a failed current-scope binding without conflating it with absence."""

    return any("run_n5_interaction_scope_" in str(item.get("msg", "")) for item in error.errors())


def _n8_interaction_qualification_fields(
    value_port: object | None,
    *,
    include_status: bool = True,
) -> dict[str, Any]:
    """Expose the interaction qualifier N8 actually consumed."""

    if value_port is None:
        return {}
    projected = {
        "n8_numeric_interaction": getattr(value_port, "numeric_interaction", None),
        "n8_numeric_interaction_basis": getattr(value_port, "numeric_interaction_basis", None),
        "n8_interaction_sampling_status": getattr(value_port, "interaction_sampling_status", None),
    }
    if include_status:
        projected.update(
            {
                "n8_status": getattr(value_port, "status", None),
                "n8_authority_blockers": tuple(getattr(value_port, "authority_blockers", ())),
            }
        )
    return projected


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
    from polisyos.runtime.http.services.control.generation_cycle import (
        COMPILED_RECURSIVE_GENERATION_CYCLE_COST_SCHEMA_VERSION,
        COMPILED_RECURSIVE_GENERATION_CYCLE_FAILED_PARTIAL_SCHEMA_VERSION,
        COMPILED_RECURSIVE_GENERATION_CYCLE_PARTIAL_SCHEMA_VERSION,
        COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
    from polisyos.runtime.quality.generation_cycle import (
        _joint_simulation_port_outcome,
        load_joint_simulation_result,
        resolve_generation_cycle_run_context_history,
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

    owner_store = store
    if type(store) is not SelectedProfileVerificationReader:
        store = SelectedProfileVerificationReader(store)
    try:
        manifest = read_core_manifest_profile(store, ref)[0]
        selected_ref = artifact_ref_for_manifest(manifest)
        tenant_context = manifest.tenant_context
        if tenant_context is not None and (tenant_context.tenant_id, tenant_context.cell_id) != (
            tenant_id,
            cell_id,
        ):
            raise ArtifactOwnershipError("compiled generic run belongs to another tenant or cell")
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
    except CanonicalProfileRefusalError as exc:
        _raise_generic_read_access_refusal(exc)
        raise
    except (OSError, RuntimeDependencyError, RuntimeError, TypeError, ValueError) as exc:
        _raise_generic_read_access_refusal(exc)
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
        compiled_read = read_core_json_artifact(store, ref, raw_payload_bytes=payload_bytes)
        if compiled_read.selected_manifest_profile_sha256 != selected_ref.manifest_profile_sha256:
            raise ValueError("compiled_cycle_artifact_selected_manifest_changed")
        compiled = CompiledRecursiveGenerationCycleRun.model_validate(compiled_read.value)
        if (
            compiled.generic_cycle_simulation_handoff is not None
            or compiled.n4_child_profile_set_ref is not None
            or compiled.generic_n4_child_profile_status != "not_attempted"
        ):
            return None
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
    except CanonicalProfileRefusalError as exc:
        _raise_generic_read_access_refusal(exc)
        raise
    except (OSError, RuntimeDependencyError, RuntimeError, TypeError, ValueError) as exc:
        _raise_generic_read_access_refusal(exc)
        return _candidate_simulation_refusal(
            run_id=run_id,
            source_ref=ref,
            limitation_code="compiled_cycle_artifact_content_invalid",
        )

    # The selected facade is scoped to compiled preflight. Later non-generic
    # consumers compare the actual control-service store by identity.
    store = owner_store
    compiled_view_limitation = (
        "compiled_cycle_selected_view_not_established"
        if ref.manifest_profile_sha256 is None
        else None
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
        except CanonicalProfileRefusalError:
            raise
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
    child_problem_by_node: dict[str, Any] = {}
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
            child_problem_by_node = {
                node_ref: child.problem for node_ref, child in child_by_ref.items()
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
        except CanonicalProfileRefusalError:
            raise
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
    n5_ref_unresolved_limitation_code = "n5_result_reference_not_established"
    root_node_ref = "design-problem://" + compiled.design_problem_ref.removeprefix("sha256:")
    compiled_child_handoffs = {
        row.node_ref: row.handoff for row in compiled.n4_child_profile_bindings
    }
    child_projection_by_node = {row.node_ref: row for row in child_profile_bindings}
    context_history_by_node: dict[str, Any] = {}
    if (
        compiled.n4_recursive_source_job_id is not None
        and compiled.n4_recursive_source_run_id is not None
        and compiled.n4_recursive_source_tenant_id == tenant_id
        and compiled.n4_recursive_source_cell_id == cell_id
    ):
        from polisyos.runtime.quality.cycle_substrate import (
            CycleSubstrateContextArtifactOwner,
        )

        context_owner = CycleSubstrateContextArtifactOwner(store=store)
        for node in recursive_run.nodes:
            if not isinstance(node, RecursiveCycleNode) or node.cycle_run is None:
                continue
            initial_problem = (
                compiled.design_problem
                if node.node_ref == root_node_ref
                else child_problem_by_node.get(node.node_ref)
            )
            if initial_problem is None:
                continue
            context_history_by_node[node.node_ref] = resolve_generation_cycle_run_context_history(
                node.cycle_run,
                context_owner=context_owner,
                initial_problem=initial_problem,
                expected_job_id=compiled.n4_recursive_source_job_id,
                expected_run_id=compiled.n4_recursive_source_run_id,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
            )
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

    resolved_lineage_by_input_ref: dict[str, Any] = {}

    def _lineage_projection(
        simulation: Any,
        *,
        node_ref: str,
        problem_ref: str,
        cycle_index: int,
    ) -> dict[str, Any]:
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
        context_history = context_history_by_node.get(node_ref)
        if context_history is None or context_history.status != "resolved":
            return {
                **common,
                "lineage_limitation_code": "generation_cycle_context_history_not_established",
            }
        context_binding = next(
            (row for row in context_history.bindings if row.cycle_index == cycle_index),
            None,
        )
        if (
            context_binding is None
            or cycle_job_design_problem_ref(context_binding.problem) != problem_ref
            or artifact_ref_identity_key(context_binding.context_job_ref)
            != artifact_ref_identity_key(simulation.candidate_simulation_context_job_ref)
        ):
            return {
                **common,
                "lineage_limitation_code": "generation_cycle_context_history_join_mismatch",
            }
        if cycle_index == 0:
            initial_handoff = compiled_child_handoffs.get(node_ref)
            initial_context_ref = (
                compiled.n4_recursive_source_context_job_ref
                if node_ref == root_node_ref
                else initial_handoff.context_job_ref
                if initial_handoff is not None
                else None
            )
            if initial_context_ref is None or artifact_ref_identity_key(
                context_binding.context_job_ref
            ) != artifact_ref_identity_key(initial_context_ref):
                return {
                    **common,
                    "lineage_limitation_code": (
                        "generation_cycle_context_history_initial_basis_mismatch"
                    ),
                }
        try:
            from polisyos.runtime.quality.candidate_simulation import (
                candidate_simulation_profile_ref,
            )
            from polisyos.runtime.quality.cycle_substrate import (
                cycle_job_profile_selection_ref,
            )
            from polisyos.runtime.quality.generation_source import (
                GenerationSourceRepository,
            )

            input_ref = simulation.candidate_simulation_n5_input_ref
            input_manifest = read_core_manifest_profile(store, input_ref)[0]
            input_payload = read_core_json_artifact(store, input_ref).value
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
            resolved_lineage_by_input_ref[str(input_ref.artifact_id)] = lineage
            return {
                **common,
                "lineage_status": "resolved",
                "lineage_limitation_code": None,
            }
        except CanonicalProfileRefusalError:
            raise
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
        n5_manifest = read_core_manifest_profile(store, result_ref)[0]
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
                        problem_ref=(cycle.design_problem_basis_ref or cycle.design_problem_ref),
                        cycle_index=cycle.cycle_index,
                    )
                    n8_fields = _n8_interaction_qualification_fields(
                        getattr(cycle, "value_port", None)
                    )
                    if compiled_view_limitation is not None:
                        blockers = tuple(dict.fromkeys((*blockers, compiled_view_limitation)))
                        if n8_fields.get("n8_status") is not None:
                            n8_fields["n8_authority_blockers"] = tuple(
                                dict.fromkeys(
                                    (
                                        *n8_fields.get("n8_authority_blockers", ()),
                                        compiled_view_limitation,
                                    )
                                )
                            )
                            if n8_fields["n8_status"] == "value_ready":
                                n8_fields["n8_status"] = "value_pending_n8"
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
                            n5_interaction_evidence=(_n5_interaction_evidence_projection(result)),
                            **_n5_interaction_scope_fields(result),
                            **n8_fields,
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
                if compiled_view_limitation is not None:
                    blockers = tuple(dict.fromkeys((*blockers, compiled_view_limitation)))
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
                        n5_interaction_evidence=(_n5_interaction_evidence_projection(result)),
                        **_n5_interaction_scope_fields(result),
                        n8_status="value_pending_n8",
                        n8_authority_blockers=(
                            (compiled_view_limitation,) if compiled_view_limitation else ()
                        ),
                    )
                )
    except CanonicalProfileRefusalError:
        raise
    except ValidationError as exc:
        n5_ref_unresolved = True
        if _is_n5_interaction_scope_validation_error(exc):
            n5_ref_unresolved_limitation_code = "n5_interaction_scope_not_established"
    except Exception:
        n5_ref_unresolved = True

    if not n5_ref_unresolved:
        from polisyos.pdc import gy_content_hash

        for node in recursive_run.nodes:
            if not isinstance(node, RecursiveCycleNode) or node.joint_simulation is None:
                continue
            parent_index = next(
                (
                    index
                    for index, observation in enumerate(observations)
                    if observation.node_ref == node.node_ref
                    and observation.simulation_result_ref == node.joint_simulation_ref
                ),
                None,
            )
            if parent_index is None:
                continue
            parent_observation = observations[parent_index]
            request = node.joint_simulation_request
            scope_failure = None
            child_bindings: list[RunCandidateSimulationN8ChildSourceBinding] = []
            outcome_units: dict[str, str] = {}
            request_hash = node.joint_simulation_request_content_hash
            candidate_selection_fields: dict[str, Any] = {}
            candidate_selection = node.joint_candidate_selection
            if candidate_selection is not None:
                try:
                    candidate_selection_fields = _parent_joint_candidate_selection_projection(
                        compiled=compiled,
                        node=node,
                        request=request,
                        root_n4_source=root_n4_source,
                    )
                except Exception:
                    candidate_selection_fields = {
                        "n8_candidate_joint_selection_status": "not_established",
                        "n8_candidate_joint_selection_limitation_code": (
                            "parent_joint_candidate_source_selection_not_established"
                        ),
                        "n8_candidate_member_basis": "not_established",
                        "n8_source_candidate_relationship": "not_established",
                        "n8_policy_composition_status": "not_established",
                        "n8_policy_composition_limitation_code": (
                            "parent_joint_candidate_source_selection_not_established"
                        ),
                        "n8_child_to_parent_refinement_status": "not_established",
                        "n8_child_to_parent_refinement_limitation_code": (
                            "parent_joint_candidate_source_selection_not_established"
                        ),
                    }
            if request is None or request_hash is None:
                scope_failure = "parent_joint_request_binding_not_established"
            elif request_hash != gy_content_hash(request.model_dump(mode="json")):
                scope_failure = "parent_joint_request_content_binding_mismatch"
            elif (
                request.world_model_record.content_hash
                != parent_observation.world_model_record_content_hash
                or request.world_model_record_ref != node.joint_simulation.world_model_record_ref
                or tuple(request.selected_outcomes) != parent_observation.selected_outcomes
                or tuple(atom.intervention_id for atom in request.intervention_atoms)
                != parent_observation.atom_ids
                or request.horizon.model_dump(mode="json")
                != node.joint_simulation.horizon.model_dump(mode="json")
            ):
                scope_failure = "parent_joint_request_result_binding_mismatch"
            elif request.coupling_graph is None:
                scope_failure = (
                    "parent_joint_coupling_evidence_not_established"
                    if candidate_selection is not None
                    and candidate_selection_fields.get("n8_candidate_joint_selection_status")
                    == "resolved"
                    else "parent_joint_selected_child_program_not_established"
                )
            elif request.coupling_graph.design_ref != node.node_ref or tuple(
                request.coupling_graph.module_refs
            ) != tuple(node.child_refs):
                scope_failure = "parent_joint_selected_child_program_not_established"
            elif (
                parent_observation.n5_interaction_evidence is None
                or parent_observation.n5_interaction_evidence.schema_version
                != "policyos.runtime.joint_simulation_horizon.v4"
                or parent_observation.n5_interaction_evidence.interaction_sampling_status
                == "not_established"
                or not parent_observation.executed_steps
                or not parent_observation.replication_seeds
            ):
                scope_failure = "parent_joint_interaction_sampling_not_established"
            else:
                child_observations: dict[str, list[RunCandidateSimulationN5Observation]] = {}
                for row in observations:
                    child_observations.setdefault(row.node_ref, []).append(row)
                if (
                    not node.child_refs
                    or len(node.child_refs) != len(set(node.child_refs))
                    or len(node.child_refs) != len(request.intervention_atoms)
                    or set(node.child_refs) != set(request.coupling_graph.module_refs)
                ):
                    scope_failure = "parent_joint_selected_child_denominator_mismatch"
                else:
                    source_atoms_by_node: dict[str, Any] = {}
                    for child_ref in node.child_refs:
                        rows = child_observations.get(child_ref, [])
                        if len(rows) != 1:
                            scope_failure = "parent_joint_child_n5_selection_ambiguous"
                            break
                        child_row = rows[0]
                        if (
                            child_row.status != "joint_simulated"
                            or child_row.lineage_status != "resolved"
                            or child_row.n5_input_ref is None
                            or child_row.n4_source_ref is None
                            or child_row.context_job_ref is None
                            or child_row.simulation_result_ref is None
                            or child_row.profile_config_ref is None
                            or child_row.profile_selection_ref is None
                        ):
                            scope_failure = "parent_joint_child_input_lineage_not_established"
                            break
                        profile_binding = child_projection_by_node.get(child_ref)
                        if (
                            profile_binding is None
                            or profile_binding.historical_binding_status != "resolved"
                            or compiled.n4_child_profile_status != "resolved"
                            or profile_binding.profile_config_ref != child_row.profile_config_ref
                            or (
                                profile_binding.profile_selection_ref
                                != child_row.profile_selection_ref
                            )
                            or profile_binding.context_job_ref != child_row.context_job_ref
                            or profile_binding.root_n4_source_ref != child_row.n4_source_ref
                        ):
                            scope_failure = "parent_joint_child_profile_aggregate_not_established"
                            break
                        lineage = resolved_lineage_by_input_ref.get(
                            str(child_row.n5_input_ref.artifact_id)
                        )
                        source_atom = getattr(
                            getattr(lineage, "materialization", None),
                            "derived_n5_atom",
                            None,
                        )
                        if source_atom is None or len(child_row.atom_ids) != 1:
                            scope_failure = "parent_joint_child_atom_source_not_established"
                            break
                        if source_atom.intervention_id != child_row.atom_ids[0]:
                            scope_failure = "parent_joint_child_atom_result_binding_mismatch"
                            break
                        if source_atom.problem_frame_ref != node.design_problem_ref:
                            scope_failure = "parent_joint_atom_frame_binding_not_established"
                            break
                        source_atoms_by_node[child_ref] = (child_row, source_atom)
                    if scope_failure is None:
                        unmatched_parent_atoms = list(request.intervention_atoms)
                        matched_by_child: dict[str, Any] = {}
                        for child_ref in node.child_refs:
                            child_row, source_atom = source_atoms_by_node[child_ref]
                            matches = []
                            for parent_atom in unmatched_parent_atoms:
                                if _parent_joint_atom_matches_child_source(
                                    parent_atom,
                                    source_atom,
                                ):
                                    matches.append(parent_atom)
                            if len(matches) != 1:
                                scope_failure = (
                                    "parent_joint_atom_child_source_binding_not_established"
                                )
                                break
                            parent_atom = matches[0]
                            unmatched_parent_atoms.remove(parent_atom)
                            if parent_atom.world_model_record_ref != request.world_model_record_ref:
                                scope_failure = "parent_joint_atom_world_model_binding_mismatch"
                                break
                            matched_by_child[child_ref] = (
                                child_row,
                                source_atom,
                                parent_atom,
                            )
                        if scope_failure is None and unmatched_parent_atoms:
                            scope_failure = "parent_joint_atom_child_denominator_mismatch"
                    if scope_failure is None:
                        for outcome in request.selected_outcomes:
                            unit_ids = {
                                source_atom.intended_downstream_estimand.unit_id
                                for _child, source_atom, _parent in matched_by_child.values()
                                if outcome
                                in source_atom.intended_downstream_estimand.outcome_variables
                            }
                            if len(unit_ids) != 1 or None in unit_ids or "" in unit_ids:
                                scope_failure = "parent_joint_outcome_unit_not_established"
                                break
                            outcome_units[outcome] = next(iter(unit_ids))
                    if scope_failure is None:
                        for child_ref in node.child_refs:
                            child_row, source_atom, parent_atom = matched_by_child[child_ref]
                            child_bindings.append(
                                RunCandidateSimulationN8ChildSourceBinding(
                                    child_node_ref=child_ref,
                                    child_design_problem_ref=child_row.design_problem_ref,
                                    n4_source_ref=child_row.n4_source_ref,
                                    context_job_ref=child_row.context_job_ref,
                                    n5_input_ref=child_row.n5_input_ref,
                                    n5_result_ref=child_row.simulation_result_ref,
                                    profile_config_ref=child_row.profile_config_ref,
                                    profile_selection_ref=child_row.profile_selection_ref,
                                    source_intervention_id=source_atom.intervention_id,
                                    source_atom_id=source_atom.atom_id,
                                    source_atom_content_hash=source_atom.content_hash,
                                    source_problem_frame_ref=source_atom.problem_frame_ref,
                                    parent_atom_id=parent_atom.atom_id,
                                    parent_atom_content_hash=parent_atom.content_hash,
                                )
                            )
            blocker = (
                scope_failure
                if scope_failure is not None
                else "joint_interaction_rule_not_established"
            )
            evidence = parent_observation.n5_interaction_evidence
            n8_fields: dict[str, Any] = {
                "n8_joint_request_content_hash": request_hash,
                "n8_joint_world_model_record_ref": (
                    request.world_model_record_ref if request is not None else None
                ),
                "n8_joint_outcome_units": outcome_units if scope_failure is None else {},
                "n8_joint_parent_atom_ids": (
                    tuple(atom.atom_id for atom in request.intervention_atoms)
                    if scope_failure is None and request is not None
                    else ()
                ),
                "n8_joint_parent_atom_content_hashes": (
                    tuple(atom.content_hash for atom in request.intervention_atoms)
                    if scope_failure is None and request is not None
                    else ()
                ),
                "n8_parent_child_refs": (
                    tuple(row.child_node_ref for row in child_bindings)
                    if scope_failure is None
                    else ()
                ),
                "n8_parent_child_source_bindings": (
                    tuple(child_bindings) if scope_failure is None else ()
                ),
                "n8_joint_scope_status": (
                    "resolved" if scope_failure is None else "not_established"
                ),
                "n8_joint_scope_limitation_code": scope_failure,
                "n8_joint_value_limitation_code": (
                    "joint_interaction_rule_not_established" if scope_failure is None else None
                ),
                "n8_status": "value_pending_n8",
                "n8_authority_blockers": tuple(
                    dict.fromkeys((*parent_observation.n8_authority_blockers, blocker))
                ),
                **candidate_selection_fields,
            }
            if scope_failure is None and evidence is not None:
                n8_fields.update(
                    {
                        "n8_numeric_interaction": evidence.numeric_interaction,
                        "n8_numeric_interaction_basis": evidence.numeric_interaction_basis,
                        "n8_interaction_sampling_status": evidence.interaction_sampling_status,
                    }
                )
            observations[parent_index] = parent_observation.model_copy(update=n8_fields)

    if n5_ref_unresolved:
        return RunCandidateSimulationProjection(
            run_id=run_id,
            artifact_status="resolved",
            source_ref=ref,
            source_content_hash=compiled.content_hash,
            limitation_code=n5_ref_unresolved_limitation_code,
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


def _conditional_transport_candidate_for_indexed_run(
    run: IndexedRunRecord,
    *,
    store: ArtifactStore,
) -> RunConditionalTransportCandidateProjection | None:
    """Project only a fresh, verified conditional result on the refused outer branch."""
    from polisyos.core.run.manifest import RunInvocationStarted
    from polisyos.ir.analytics import CausalEffectReport
    from polisyos.ir.analytics.causal_graph import (
        graph_content_sha256,
        load_causal_graph_model,
    )
    from polisyos.ir.analytics.transportability import (
        TransportabilityCandidateRequestV1,
        TransportabilityResult,
        TransportabilityStatus,
        TransportMode,
    )
    from polisyos.scientist.orchestration.engine import ExperimentState, WorkflowSpec

    details = run.details

    def read_selected(
        ref: ArtifactRef,
        *,
        kind: str,
        schema: str,
        version: str | None = None,
    ) -> tuple[dict[str, Any], ArtifactManifest]:
        if (
            ref.kind != kind
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
        ):
            raise ValueError("conditional_transport_selected_ref_invalid")
        manifest, _declaration = read_core_manifest_profile(store, ref)
        raw = store.get_bytes(ref)
        expected_id = f"sha256:{hashlib.sha256(raw).hexdigest()}"
        context = manifest.tenant_context
        if (
            not store.verify(ref).ok
            or manifest.artifact_id != ref.artifact_id
            or manifest.kind != kind
            or manifest.media_type != ref.media_type
            or str(ref.artifact_id) != expected_id
            or str(manifest.artifact_id) != expected_id
            or manifest.integrity.sha256 != expected_id.removeprefix("sha256:")
            or manifest.byte_size != len(raw)
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name != schema
            or (version is not None and manifest.artifact_schema.version != version)
            or (
                context is not None
                and (context.tenant_id != details.tenant_id or context.cell_id != details.cell_id)
            )
        ):
            raise ValueError("conditional_transport_selected_artifact_unverified")
        payload = read_core_json_artifact(
            store,
            ref,
            raw_payload_bytes=raw,
        ).value
        if not isinstance(payload, dict):
            raise ValueError("conditional_transport_selected_payload_not_object")
        return payload, manifest

    def ref_for_edge(edge: CoreInputRef, *, kind: str, role: str) -> ArtifactRef:
        if edge.role != role or edge.manifest_profile_sha256 is None:
            raise ValueError("conditional_transport_input_edge_invalid")
        return ArtifactRef(
            artifact_id=edge.artifact_id,
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256=edge.manifest_profile_sha256,
        )

    def same_reference_identity(
        left_artifact_id: object,
        left_profile: str | None,
        right_artifact_id: object,
        right_profile: str | None,
    ) -> bool:
        return (
            left_profile is not None
            and right_profile is not None
            and str(left_artifact_id) == str(right_artifact_id)
            and left_profile == right_profile
        )

    def same_edge(left: CoreInputRef, right: IRInputRef) -> bool:
        return left.role == right.role and same_reference_identity(
            left.artifact_id,
            left.manifest_profile_sha256,
            right.artifact_id,
            right.manifest_profile_sha256,
        )

    def root_matches_edge(left: ArtifactRef, right: CoreInputRef) -> bool:
        return same_reference_identity(
            left.artifact_id,
            left.manifest_profile_sha256,
            right.artifact_id,
            right.manifest_profile_sha256,
        )

    def one_edge(manifest: ArtifactManifest, role: str) -> CoreInputRef:
        matches = [edge for edge in manifest.inputs if edge.role == role]
        if len(matches) != 1:
            raise ValueError("conditional_transport_manifest_input_not_unique")
        return matches[0]

    try:
        reports = tuple(
            ref
            for ref in details.root_artifacts
            if getattr(ref, "kind", None) == "ir.causal_effect_report"
        )
        if len(reports) != 1:
            return None
        report_ref = reports[0]
        report_payload, report_manifest = read_selected(
            report_ref,
            kind="ir.causal_effect_report",
            schema="ir.causal_effect_report",
            version="1.1",
        )
        report = CausalEffectReport.model_validate(report_payload)
        if report.schema_version != "1.1" or report.transport_result is None:
            return None

        source_report_edge = one_edge(report_manifest, "causal_report_prev")
        if source_report_edge.manifest_profile_sha256 is None:
            return None
        source_report_ref = ref_for_edge(
            source_report_edge,
            kind="ir.causal_effect_report",
            role="causal_report_prev",
        )
        if root_matches_edge(report_ref, source_report_edge):
            return None
        source_report_payload, source_report_manifest = read_selected(
            source_report_ref,
            kind="ir.causal_effect_report",
            schema="ir.causal_effect_report",
        )
        source_report = CausalEffectReport.model_validate(source_report_payload)
        if source_report.schema_version != source_report_manifest.artifact_schema.version:
            return None

        result_edge = one_edge(report_manifest, "transportability_result")
        if result_edge.manifest_profile_sha256 is None:
            return None
        direct_results = tuple(
            ref
            for ref in details.root_artifacts
            if getattr(ref, "kind", None) == "ir.transportability_result"
        )
        if len(direct_results) > 1:
            return None
        if direct_results:
            result_ref = direct_results[0]
            if not root_matches_edge(result_ref, result_edge):
                return None
        else:
            result_ref = ref_for_edge(
                result_edge,
                kind="ir.transportability_result",
                role="transportability_result",
            )
        result_payload, result_manifest = read_selected(
            result_ref,
            kind="ir.transportability_result",
            schema="ir.transportability_result",
            version="2.2",
        )
        result = TransportabilityResult.model_validate(result_payload)
        if (
            result.schema_version != "2.2"
            or report.transport_result.model_dump(mode="json") != result.model_dump(mode="json")
            or result.status is not TransportabilityStatus.UNSUPPORTED
            or result.transport_mode is not TransportMode.NONE
            or result.feasible is not False
        ):
            return None
        diagnostic = result.candidate_diagnostics
        if diagnostic is None:
            return None

        lineage = {edge.role: edge for edge in diagnostic.inputs.lineage_refs}
        if set(lineage) != {
            "transportability_attempt_basis",
            "transportability_workflow_spec",
            "transportability_input_state",
            "selected_causal_graph",
            "causal_effect_report",
        }:
            return None
        expected = {
            "transportability_attempt_basis": (
                diagnostic.attempt.basis_ref,
                "core.run_invocation_attempt",
            ),
            "transportability_workflow_spec": (
                diagnostic.attempt.workflow_spec_ref,
                "scientist.workflow_spec",
            ),
            "transportability_input_state": (
                diagnostic.attempt.input_state_ref,
                "scientist.experiment_state",
            ),
            "selected_causal_graph": (lineage["selected_causal_graph"], "ir.causal_graph_model"),
            "causal_effect_report": (lineage["causal_effect_report"], "ir.causal_effect_report"),
        }
        for role, (expected_edge, kind) in expected.items():
            if expected_edge.role != role or expected_edge.manifest_profile_sha256 is None:
                return None
            actual_edge = one_edge(result_manifest, role)
            if not same_edge(actual_edge, expected_edge):
                return None
            if role == "causal_effect_report":
                if not root_matches_edge(source_report_ref, actual_edge):
                    return None
                continue
            selected_ref = ref_for_edge(actual_edge, kind=kind, role=role)
            if role == "transportability_attempt_basis":
                payload, manifest = read_selected(
                    selected_ref,
                    kind=kind,
                    schema="polisyos.core.RunInvocationAttempt",
                )
                basis = RunInvocationStarted.model_validate(payload)
                if (
                    basis.workflow_spec_ref.kind != "scientist.workflow_spec"
                    or basis.workflow_spec_ref.media_type != "application/json"
                    or basis.input_state_ref.kind != "scientist.experiment_state"
                    or basis.input_state_ref.media_type != "application/json"
                    or basis.schema_version != manifest.artifact_schema.version
                    or basis.run_id != details.run_id
                    or basis.attempt_id != diagnostic.attempt.attempt_id
                    or basis.attempt_number != diagnostic.attempt.attempt_number
                    or basis.node_alias != diagnostic.attempt.node_alias
                    or basis.component_id != diagnostic.attempt.component_id
                    or basis.started_at != diagnostic.attempt.started_at
                    or not same_reference_identity(
                        basis.workflow_spec_ref.artifact_id,
                        basis.workflow_spec_ref.manifest_profile_sha256,
                        diagnostic.attempt.workflow_spec_ref.artifact_id,
                        diagnostic.attempt.workflow_spec_ref.manifest_profile_sha256,
                    )
                    or not same_reference_identity(
                        basis.input_state_ref.artifact_id,
                        basis.input_state_ref.manifest_profile_sha256,
                        diagnostic.attempt.input_state_ref.artifact_id,
                        diagnostic.attempt.input_state_ref.manifest_profile_sha256,
                    )
                ):
                    return None
            elif role == "transportability_workflow_spec":
                payload, manifest = read_selected(
                    selected_ref,
                    kind=kind,
                    schema="polisyos.scientist.orchestration.engine.WorkflowSpec",
                    version="1.0",
                )
                workflow = WorkflowSpec.model_validate(payload)
                nodes = [
                    node for node in workflow.nodes if node.alias == diagnostic.attempt.node_alias
                ]
                if (
                    len(nodes) != 1
                    or str(nodes[0].node_id) != diagnostic.attempt.component_id
                    or workflow.schema_version != manifest.artifact_schema.version
                ):
                    return None
            elif role == "transportability_input_state":
                payload, manifest = read_selected(
                    selected_ref,
                    kind=kind,
                    schema="polisyos.scientist.orchestration.engine.ExperimentState",
                )
                state = ExperimentState.model_validate(payload)
                raw_request = state.params.get("conditional_transport_request")
                if raw_request is None:
                    return None
                request = TransportabilityCandidateRequestV1.model_validate(raw_request)
                if (
                    state.run_id != details.run_id
                    or state.schema_version != manifest.artifact_schema.version
                    or request != diagnostic.candidate_request
                ):
                    return None

        if not same_edge(
            one_edge(result_manifest, "transportability_workflow_spec"),
            lineage["transportability_workflow_spec"],
        ) or not same_edge(
            one_edge(result_manifest, "transportability_input_state"),
            lineage["transportability_input_state"],
        ):
            return None

        evaluations = {row.member_sha256: row for row in diagnostic.evaluations}
        member_prefix = "transportability_candidate_member_graph:"
        member_edges = [
            edge for edge in result_manifest.inputs if edge.role.startswith(member_prefix)
        ]
        expected_roles = {member_prefix + sha256 for sha256 in evaluations}
        if (
            len(member_edges) != len(evaluations)
            or {edge.role for edge in member_edges} != expected_roles
        ):
            return None
        for edge in member_edges:
            member_sha256 = edge.role.removeprefix(member_prefix)
            evaluation = evaluations[member_sha256]
            if not same_reference_identity(
                edge.artifact_id,
                edge.manifest_profile_sha256,
                evaluation.member_graph_ref.artifact_id,
                evaluation.member_graph_ref.manifest_profile_sha256,
            ):
                return None
            graph_ref = evaluation.member_graph_ref
            _member_payload, _member_manifest = read_selected(
                ArtifactRef.model_validate(graph_ref.model_dump(mode="json")),
                kind="ir.causal_graph_model",
                schema="ir.causal_graph_model",
                version="1.0",
            )
            member_graph = load_causal_graph_model(store, graph_ref)
            if graph_content_sha256(member_graph) != member_sha256:
                return None

        selected_source_edge = lineage["selected_causal_graph"]
        if not same_reference_identity(
            selected_source_edge.artifact_id,
            selected_source_edge.manifest_profile_sha256,
            diagnostic.inputs.graph_ref.artifact_id,
            diagnostic.inputs.graph_ref.manifest_profile_sha256,
        ):
            return None
        graph_ref = diagnostic.inputs.graph_ref
        _graph_payload, _graph_manifest = read_selected(
            ArtifactRef.model_validate(graph_ref.model_dump(mode="json")),
            kind="ir.causal_graph_model",
            schema="ir.causal_graph_model",
            version="1.0",
        )
        graph = load_causal_graph_model(store, graph_ref)
        if (
            graph.graph_type != diagnostic.inputs.graph_type
            or graph_content_sha256(graph) != diagnostic.inputs.graph_sha256
        ):
            return None

        completed_valid = tuple(
            row
            for row in diagnostic.evaluations
            if row.disposition == "completed" and row.outcome is not None
        )
        identified = sum(
            row.outcome.status is TransportabilityStatus.IDENTIFIED for row in completed_valid
        )
        denominator = len(completed_valid)
        fraction = identified / denominator if denominator else None
        if diagnostic.identified_member_fraction != fraction:
            return None

        resolution = diagnostic.resource_resolution
        return RunConditionalTransportCandidateProjection(
            candidate_scope="candidate_only",
            candidate_disposition=diagnostic.disposition,
            requested_profile_id=resolution.profile_id,
            requested_profile_revision=resolution.profile_revision,
            selection_identity=resolution.selection_identity,
            reason_code=diagnostic.reason.code if diagnostic.reason is not None else None,
            proposal_count=len(diagnostic.proposals),
            member_evaluation_count=len(diagnostic.evaluations),
            completed_valid_member_count=denominator,
            identified_member_fraction=fraction,
            identified_member_fraction_basis="selected_completed_valid_members",
            source_currentness="unknown",
            interpretation_limit=(
                "selected_family_member_outcomes_do_not_establish_whole_pag_class_probability_calibration_legal_applicability_or_protected_eligibility"
            ),
        )
    except Exception:
        return None


def _candidate_simulation_for_indexed_run(
    run: IndexedRunRecord,
    *,
    store: ArtifactStore,
    control_service: Any | None = None,
) -> RunCandidateSimulationProjection | None:
    """Resolve the current root-bound N5 projection used by run consumers."""
    details = run.details
    return _candidate_simulation_projection(
        run_id=details.run_id,
        tenant_id=details.tenant_id,
        cell_id=details.cell_id,
        control_job_id=details.control_job_id,
        root_artifacts=tuple(details.root_artifacts),
        store=store,
        control_service=control_service,
    )


def _parent_joint_atom_matches_child_source(parent_atom: Any, child_source_atom: Any) -> bool:
    """Require exact producer-owned atom identity across the parent-child seam."""

    if type(parent_atom) is not type(child_source_atom):
        return False
    parent_dump = getattr(parent_atom, "model_dump", None)
    child_dump = getattr(child_source_atom, "model_dump", None)
    if not callable(parent_dump) or not callable(child_dump):
        return False
    return parent_dump(mode="json") == child_dump(mode="json")


def _parent_joint_candidate_selection_projection(
    *,
    compiled: Any,
    node: Any,
    request: Any,
    root_n4_source: Any,
) -> dict[str, Any]:
    """Reconcile the candidate parent basis against the fresh N4 source readback."""

    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
    from polisyos.runtime.quality.design_generation import (
        derive_n4_candidate_child_problems,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
        ParentJointCandidateSelectionV2,
    )

    selection = getattr(node, "joint_candidate_selection", None)
    handoff = getattr(compiled, "generic_cycle_simulation_handoff", None)
    if (
        selection is None
        or request is None
        or root_n4_source is None
        or handoff is None
        or root_n4_source.generation_result.status != "generated"
    ):
        raise ValueError("parent_joint_candidate_source_selection_not_established")
    source_result = root_n4_source.generation_result
    source_result_hash = gy_content_hash(source_result.model_dump(mode="json"))
    if isinstance(selection, ParentJointCandidateSelectionV2) and (
        selection.candidate_intent != "n4_unique_parent_source_members.v1"
        or selection.joint_simulation_request_content_hash
        != gy_content_hash(request.model_dump(mode="json"))
        or selection.member_basis != "hypothetical_all_unique_n4_source_members"
        or selection.source_candidate_relationship != "alternatives"
        or selection.composition_status != "not_established"
        or selection.composition_limitation_code
        != "n4_source_candidates_are_alternatives_not_authored_compound_design"
        or selection.child_to_parent_refinement_status != "not_established"
        or selection.child_to_parent_refinement_limitation_code
        != "child_to_parent_refinement_rule_not_established"
        or request.candidate_intent != selection.candidate_intent
        or request.member_basis != selection.member_basis
        or request.source_candidate_relationship != selection.source_candidate_relationship
        or request.composition_status != selection.composition_status
        or request.composition_limitation_code != selection.composition_limitation_code
        or request.child_to_parent_refinement_status != selection.child_to_parent_refinement_status
        or request.child_to_parent_refinement_limitation_code
        != selection.child_to_parent_refinement_limitation_code
    ):
        raise ValueError("parent_joint_candidate_diagnostic_binding_mismatch")
    world_record = handoff.profile.context_inputs.world_model_record
    if (
        artifact_ref_identity_key(selection.n4_source_ref)
        != artifact_ref_identity_key(compiled.n4_recursive_source_ref)
        or selection.n4_source_result_content_hash != source_result_hash
        or artifact_ref_identity_key(selection.context_job_ref)
        != artifact_ref_identity_key(compiled.n4_recursive_source_context_job_ref)
        or artifact_ref_identity_key(selection.context_job_ref)
        != artifact_ref_identity_key(handoff.context_job_ref)
        or artifact_ref_identity_key(selection.profile_ref)
        != artifact_ref_identity_key(handoff.profile_ref)
        or selection.profile_selection_ref != handoff.profile.profile_selection_ref
        or selection.profile_selection_ref != compiled.n4_recursive_source_profile_selection_ref
        or selection.parent_design_problem_ref != node.design_problem_ref
        or handoff.context.design_problem_ref != node.design_problem_ref
        or selection.world_model_record_ref != world_record.world_model_record_id
        or selection.world_model_record_content_hash != world_record.content_hash
        or request.world_model_record != world_record
        or request.world_model_record_ref != world_record.world_model_record_id
        or selection.outcome_variable not in request.selected_outcomes
        or tuple(request.selected_outcomes) != (selection.outcome_variable,)
        or selection.child_node_refs != node.child_refs
        or tuple(member.child_node_ref for member in selection.members) != node.child_refs
    ):
        raise ValueError("parent_joint_candidate_source_selection_binding_mismatch")

    children = derive_n4_candidate_child_problems(
        compiled.design_problem,
        source_result,
        model_id=source_result.model_id,
    )
    expected_child_refs = tuple(
        "design-problem://" + cycle_job_design_problem_ref(child.problem).removeprefix("sha256:")
        for child in children
    )
    candidates_by_atom_hash: dict[str, list[Any]] = {}
    for candidate in source_result.candidates:
        candidates_by_atom_hash.setdefault(candidate.atom.content_hash, []).append(candidate)
    if (
        expected_child_refs != node.child_refs
        or len(children) != len(selection.members)
        or len(candidates_by_atom_hash) != len(children)
        or any(len(rows) != 1 for rows in candidates_by_atom_hash.values())
        or len(request.intervention_atoms) != len(children)
    ):
        raise ValueError("parent_joint_candidate_source_denominator_mismatch")

    selected_atoms = []
    for child, member, parent_atom in zip(
        children,
        selection.members,
        request.intervention_atoms,
        strict=True,
    ):
        child_ref = "design-problem://" + cycle_job_design_problem_ref(child.problem).removeprefix(
            "sha256:"
        )
        source_candidates = candidates_by_atom_hash.get(child.source_atom_refs[0], ())
        if len(source_candidates) != 1:
            raise ValueError("parent_joint_candidate_source_member_not_established")
        candidate = source_candidates[0]
        source_atom = candidate.atom
        if (
            child.source_result_ref != source_result_hash
            or tuple(child.source_atom_refs) != (source_atom.content_hash,)
            or member.child_node_ref != child_ref
            or member.child_design_problem_ref != cycle_job_design_problem_ref(child.problem)
            or member.semantic_ref != child.semantic_ref
            or member.source_candidate_id != candidate.candidate_id
            or member.source_candidate_content_hash
            != gy_content_hash(candidate.model_dump(mode="json"))
            or member.source_atom_id != source_atom.atom_id
            or member.source_atom_content_hash != source_atom.content_hash
            or member.parent_problem_frame_ref != node.design_problem_ref
            or source_atom.problem_frame_ref != node.design_problem_ref
            or source_atom.world_model_record_ref != request.world_model_record_ref
            or parent_atom != source_atom
        ):
            raise ValueError("parent_joint_candidate_source_member_binding_mismatch")
        selected_atoms.append(parent_atom)
    if {atom.content_hash for atom in selected_atoms} != set(candidates_by_atom_hash):
        raise ValueError("parent_joint_candidate_source_member_denominator_mismatch")
    if tuple(atom.atom_id for atom in selected_atoms) != tuple(
        atom.atom_id for atom in request.intervention_atoms
    ):
        raise ValueError("parent_joint_candidate_request_order_mismatch")

    candidate_selection_fields: dict[str, Any] = {
        "n8_candidate_joint_selection_status": "resolved",
        "n8_candidate_joint_selection_content_hash": selection.content_hash,
        "n8_candidate_parent_atom_ids": tuple(
            member.source_atom_id for member in selection.members
        ),
        "n8_candidate_parent_atom_content_hashes": tuple(
            member.source_atom_content_hash for member in selection.members
        ),
        "n8_candidate_parent_intervention_ids": tuple(
            atom.intervention_id for atom in request.intervention_atoms
        ),
        "n8_candidate_parent_child_refs": tuple(selection.child_node_refs),
    }
    if isinstance(selection, ParentJointCandidateSelectionV2):
        candidate_selection_fields.update(
            {
                "n8_candidate_member_basis": "hypothetical_all_unique_n4_source_members",
                "n8_source_candidate_relationship": "alternatives",
                "n8_policy_composition_status": "not_established",
                "n8_policy_composition_limitation_code": (
                    "n4_source_candidates_are_alternatives_not_authored_compound_design"
                ),
                "n8_child_to_parent_refinement_status": "not_established",
                "n8_child_to_parent_refinement_limitation_code": (
                    "child_to_parent_refinement_rule_not_established"
                ),
            }
        )
    else:
        # Historical v1 binds source identities only; it has no typed statement
        # that the members are a hypothetical diagnostic or an authored design.
        candidate_selection_fields.update(
            {
                "n8_candidate_member_basis": "not_established",
                "n8_source_candidate_relationship": "not_established",
                "n8_policy_composition_status": "not_established",
                "n8_policy_composition_limitation_code": (
                    "legacy_selection_receipt_has_no_composition_basis"
                ),
                "n8_child_to_parent_refinement_status": "not_established",
                "n8_child_to_parent_refinement_limitation_code": (
                    "legacy_selection_receipt_has_no_refinement_basis"
                ),
            }
        )
    return candidate_selection_fields


class _RecursiveCycleTopologyNode(Protocol):
    """Expose graph topology independently from node execution state."""

    node_ref: str
    child_refs: tuple[str, ...]


def _require_generic_recursive_root_child_denominator(
    *,
    nodes: Sequence[_RecursiveCycleTopologyNode],
    root_node_ref: str,
    expected_child_nodes: set[str],
) -> None:
    """Bind the compiled root topology to the source-derived N4 child set."""
    root_node = next(
        (node for node in nodes if node.node_ref == root_node_ref),
        None,
    )
    if root_node is None:
        raise ValueError("generic_recursive_graph_root_not_found")
    if set(root_node.child_refs) != expected_child_nodes:
        raise ValueError("generic_recursive_graph_source_denominator_mismatch")


def _generic_cycle_simulation_refusal(
    *,
    run_id: str,
    limitation_code: str,
    source_ref: Any = None,
) -> RunGenericCycleSimulationProjection:
    """Keep an unverifiable generic chain visible without promoting it."""
    return RunGenericCycleSimulationProjection(
        run_id=run_id,
        artifact_status="not_established",
        source_ref=source_ref,
        child_profile_status="not_established",
        limitation_code=limitation_code,
    )


def _generic_n6_cycle_history_fields(
    recursive_run: (
        RecursiveGenerationCycleRun
        | RecursiveGenerationCyclePartialRunV2
        | RecursiveGenerationCyclePartialRunV3
    ),
) -> dict[str, Any]:
    """Copy persisted N6 cycle outcomes without mapping or promoting their meaning."""
    from polisyos.runtime.quality.recursive_generation_cycle import RecursiveCycleNode

    history = tuple(
        RunGenericCycleSimulationN6CycleHistoryEntry(
            node_ref=node.node_ref,
            cycle_index=cycle.cycle_index,
            design_problem_ref=cycle.design_problem_ref,
            design_problem_basis_ref=cycle.design_problem_basis_ref,
            selected_candidate_ref=cycle.selected_candidate_ref,
            selected_candidate_content_hash=cycle.selected_candidate_content_hash,
            generation_cycle_run_terminal_status=node.cycle_run.terminal_status,
            terminal_kind=cycle.terminal_kind,
            refinement_decision=cycle.refinement_decision.decision,
            search_iteration_status=cycle.search_iteration.status,
            grounding_status=cycle.grounding.status,
            grounding_current_valid=cycle.grounding.current_valid,
            value_status=cycle.value_port.status,
            value_decision_grade=cycle.value_port.decision_grade,
            value_authority_blockers=cycle.value_port.authority_blockers,
            value_ref=cycle.value_port.value_ref,
            voi_next_action=cycle.voi_decision.next_action,
        )
        for node in recursive_run.nodes
        if isinstance(node, RecursiveCycleNode) and node.cycle_run is not None
        for cycle in node.cycle_run.cycles
    )
    return {
        "n6_cycle_history_status": "resolved" if history else "not_established",
        "n6_cycle_history_limitation_code": (None if history else "n6_cycle_history_not_emitted"),
        "n6_cycle_history": history,
    }


class _GenericSelectedScopeNotEstablishedError(ValueError):
    """The selected result has no declared tenant/cell binding."""


class _GenericParentNotEstablishedError(ValueError):
    """A required parent selection or candidate observation is unavailable."""


def _generic_selected_result_manifest(
    store: Any, ref: ArtifactRef, *, tenant_id: str, cell_id: str
) -> Any:
    """Reopen the exact result view and refuse a known foreign tenant or cell."""
    manifest = read_core_manifest_profile(store, ref)[0]
    scope = manifest.tenant_context
    if scope is None:
        raise _GenericSelectedScopeNotEstablishedError("generic_n5_result_scope_not_established")
    if (scope.tenant_id, scope.cell_id) != (tenant_id, cell_id):
        raise ArtifactOwnershipError("selected N5 result belongs to another tenant or cell")
    return manifest


def _raise_generic_read_access_refusal(exc: BaseException) -> None:
    """Do not return sibling data after an owner or filesystem permission refusal."""
    try:
        raise_artifact_read_access_error(exc)
    except ArtifactOwnershipError as denied:
        raise forbidden(
            "The selected artifact is not accessible to this run scope.",
            code="generic_cycle_artifact_scope_refused",
        ) from denied
    except PermissionError as unavailable:
        raise service_unavailable(
            "The selected artifact reader could not access its backing storage.",
            code="generic_cycle_artifact_reader_permission_unavailable",
        ) from unavailable


def _generic_cycle_simulation_projection(
    *,
    run_id: str,
    tenant_id: str | None,
    cell_id: str | None,
    root_artifacts: tuple[Any, ...],
    store: Any,
) -> RunGenericCycleSimulationProjection | None:
    """Replay persisted generic N4-family, N5, and conditional N8 lineage."""
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_design_problem_ref,
    )
    from polisyos.runtime.quality.design_generation import (
        derive_n4_candidate_child_problems,
    )
    from polisyos.runtime.quality.generation_cycle import (
        _consume_parent_joint_candidate_n8,
        _generation_source_run_id,
        _joint_simulation_port_outcome,
        _value_outcome_variable,
        load_joint_simulation_result,
        resolve_generation_cycle_run_context_history,
    )
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
        GenericCycleSimulationN5ExecutionV3,
        GenericCycleSimulationN5RequestBindingV2,
        GenericN5ExecutionJoinExpectation,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveCycleNode,
        RecursiveLeafContextOwner,
    )

    compiled_refs = tuple(
        ref
        for ref in root_artifacts
        if getattr(ref, "kind", None) == "runtime.compiled_recursive_generation_cycle"
    )
    if not compiled_refs:
        return None
    if len(compiled_refs) != 1:
        return _generic_cycle_simulation_refusal(
            run_id=run_id,
            limitation_code="compiled_cycle_artifact_ambiguous",
        )
    ref = compiled_refs[0]
    if getattr(ref, "media_type", None) != "application/json" or not tenant_id or not cell_id:
        return _generic_cycle_simulation_refusal(
            run_id=run_id,
            source_ref=ref,
            limitation_code="compiled_cycle_artifact_binding_not_established",
        )
    if type(store) is not SelectedProfileVerificationReader:
        store = SelectedProfileVerificationReader(store)
    try:
        manifest = read_core_manifest_profile(store, ref)[0]
        selected_ref = artifact_ref_for_manifest(manifest)
        verification = store.verify(selected_ref)
        context = manifest.tenant_context
        if context is not None and (context.tenant_id, context.cell_id) != (tenant_id, cell_id):
            raise ArtifactOwnershipError("compiled generic run belongs to another tenant or cell")
        payload_bytes = store.get_bytes(selected_ref)
        expected_id = f"sha256:{hashlib.sha256(payload_bytes).hexdigest()}"
        if (
            not verification.ok
            or manifest.kind != "runtime.compiled_recursive_generation_cycle"
            or manifest.media_type != "application/json"
            or context is None
            or context.tenant_id != tenant_id
            or context.cell_id != cell_id
            or str(ref.artifact_id) != expected_id
            or str(manifest.artifact_id) != expected_id
            or manifest.integrity.sha256 != expected_id.removeprefix("sha256:")
            or manifest.byte_size != len(payload_bytes)
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name
            != "polisyos.runtime.CompiledRecursiveGenerationCycleRun"
        ):
            raise ValueError("compiled_generic_cycle_manifest_or_content_mismatch")
        compiled = CompiledRecursiveGenerationCycleRun.model_validate(
            read_core_json_artifact(store, selected_ref, raw_payload_bytes=payload_bytes).value
        )
        if manifest.artifact_schema.version != "1.0":
            raise ValueError("compiled_generic_cycle_schema_version_mismatch")
    except CanonicalProfileRefusalError:
        raise
    except (OSError, RuntimeDependencyError, RuntimeError, TypeError, ValueError) as exc:
        _raise_generic_read_access_refusal(exc)
        return _generic_cycle_simulation_refusal(
            run_id=run_id,
            source_ref=ref,
            limitation_code="compiled_cycle_artifact_integrity_not_established",
        )

    has_generic_projection = (
        compiled.generic_cycle_simulation_handoff is not None
        or compiled.n4_child_profile_set_ref is not None
        or compiled.n4_credal_source_attempt_ref is not None
        or compiled.generic_n4_child_profile_status != "not_attempted"
        or compiled.generic_n4_child_profile_limitation_code is not None
    )
    if not has_generic_projection:
        return None
    checkpoint = _candidate_simulation_checkpoint(compiled.recursive_run)
    n6_history_fields = _generic_n6_cycle_history_fields(compiled.recursive_run)
    if compiled.generic_n4_child_profile_status != "resolved":
        if compiled.n4_credal_source_attempt_ref is not None:
            attempt_ref = compiled.n4_credal_source_attempt_ref
            source_ref = compiled.n4_recursive_source_ref
            handoff = compiled.generic_cycle_simulation_handoff
            if (
                source_ref is not None
                and handoff is not None
                and compiled.n4_recursive_source_run_id is not None
                and handoff.tenant_id == tenant_id
                and handoff.cell_id == cell_id
                and handoff.job_id == compiled.n4_recursive_source_job_id
                and handoff.run_id == compiled.n4_recursive_source_run_id
                and handoff.context_job_ref == compiled.n4_recursive_source_context_job_ref
                and handoff.profile.profile_id == compiled.n4_recursive_source_profile_config_ref
                and handoff.profile.profile_selection_ref
                == compiled.n4_recursive_source_profile_selection_ref
                and handoff.profile.profile_selection_kind == "problem"
            ):
                try:
                    from polisyos.runtime.quality.generation_source import (
                        CandidateCredalSourceAttemptV1,
                    )

                    generic_owner = GenericCycleSimulationAdmissionOwner(profiles=(), store=store)
                    source_repository = GenerationSourceRepository(store)
                    if handoff.n4_child_profile_family_ref is not None:
                        generic_owner.resolve_child_profile_family_historical(
                            handoff.n4_child_profile_family_ref,
                            expected_parent_handoff=handoff,
                            expected_parent_problem=compiled.design_problem,
                        )
                    else:
                        context_owner = CycleSubstrateContextArtifactOwner(store=store)
                        parent_context = context_owner.resolve_historical_job_artifact(
                            handoff.context_job_ref,
                            problem=compiled.design_problem,
                            expected_job_id=handoff.job_id,
                            expected_run_id=handoff.run_id,
                            expected_tenant_id=tenant_id or "",
                            expected_cell_id=cell_id or "",
                        )
                        if parent_context.context != handoff.context:
                            raise ValueError("candidate_source_attempt_parent_context_mismatch")
                        generic_owner.resolve_profile_historical(
                            handoff.profile_ref,
                            expected_profile=handoff.profile,
                            job_id=handoff.job_id,
                            run_id=handoff.run_id,
                            tenant_id=tenant_id or "",
                            cell_id=cell_id or "",
                        )
                    attempt = source_repository.load_candidate_credal_source_attempt(
                        attempt_ref,
                        n4_source_ref=source_ref,
                        source_run_id=compiled.n4_recursive_source_run_id or "",
                        job_id=handoff.job_id,
                        run_id=handoff.run_id,
                        tenant_id=tenant_id or "",
                        cell_id=cell_id or "",
                        problem=compiled.design_problem,
                        context=handoff.context,
                        context_job_ref=handoff.context_job_ref,
                        profile_ref=handoff.profile_ref,
                        profile_id=handoff.profile.profile_id,
                        profile_selection_ref=handoff.profile.profile_selection_ref,
                        n4_child_profile_family_ref=(handoff.n4_child_profile_family_ref),
                    )
                    if (
                        type(attempt) is not CandidateCredalSourceAttemptV1
                        or attempt.n4_status != compiled.n4_recursive_source_result_status
                        or attempt.source_run_id != compiled.n4_recursive_source_run_id
                        or attempt.design_problem_ref != compiled.design_problem_ref
                    ):
                        raise ValueError(
                            "candidate_credal_source_attempt_compiled_binding_mismatch"
                        )
                    return RunGenericCycleSimulationProjection(
                        schema_version="policyos.runtime.run_generic_cycle_simulation_projection.v4",
                        run_id=run_id,
                        artifact_status="resolved",
                        source_ref=ref,
                        source_content_hash=compiled.content_hash,
                        n4_source_ref=source_ref,
                        n4_source_status="resolved",
                        parent_context_job_ref=handoff.context_job_ref,
                        parent_profile_ref=handoff.profile_ref,
                        parent_profile_id=handoff.profile.profile_id,
                        child_profile_family_ref=handoff.n4_child_profile_family_ref,
                        credal_source_attempt_ref=attempt_ref,
                        credal_source_status="not_established",
                        credal_source_limitation_code=attempt.limitation_code,
                        child_profile_status="not_established",
                        child_profile_limitation_code=(
                            compiled.generic_n4_child_profile_limitation_code
                            or "generic_n4_source_generation_not_complete"
                        ),
                        n5_limitation_code="generic_n4_source_generation_not_complete",
                        recursive_cycle_checkpoint=checkpoint,
                        limitation_code=attempt.limitation_code,
                        **n6_history_fields,
                    )
                except CanonicalProfileRefusalError:
                    raise
                except (
                    OSError,
                    RuntimeDependencyError,
                    RuntimeError,
                    TypeError,
                    ValueError,
                ) as exc:
                    _raise_generic_read_access_refusal(exc)
                    return RunGenericCycleSimulationProjection(
                        schema_version="policyos.runtime.run_generic_cycle_simulation_projection.v4",
                        run_id=run_id,
                        artifact_status="resolved",
                        source_ref=ref,
                        source_content_hash=compiled.content_hash,
                        n4_source_ref=source_ref,
                        n4_source_status="not_established",
                        n4_source_limitation_code=(
                            "candidate_source_attempt_replay_not_established"
                        ),
                        credal_source_attempt_ref=attempt_ref,
                        credal_source_status="not_established",
                        credal_source_limitation_code=(
                            "candidate_source_attempt_replay_not_established"
                        ),
                        child_profile_status="not_established",
                        child_profile_limitation_code=(
                            "candidate_source_attempt_replay_not_established"
                        ),
                        n5_limitation_code="candidate_source_attempt_replay_not_established",
                        recursive_cycle_checkpoint=checkpoint,
                        limitation_code="candidate_source_attempt_replay_not_established",
                        **n6_history_fields,
                    )
        limitation = (
            compiled.generic_n4_child_profile_limitation_code
            or "generic_n4_child_profile_set_not_established"
        )
        return RunGenericCycleSimulationProjection(
            schema_version="policyos.runtime.run_generic_cycle_simulation_projection.v3",
            run_id=run_id,
            artifact_status="resolved",
            source_ref=ref,
            source_content_hash=compiled.content_hash,
            n4_source_ref=compiled.n4_recursive_source_ref,
            n4_source_status=(
                "resolved" if compiled.n4_recursive_source_ref is not None else "not_established"
            ),
            n4_source_limitation_code=(
                None
                if compiled.n4_recursive_source_ref is not None
                else "n4_recursive_source_reference_not_established"
            ),
            parent_context_job_ref=(
                compiled.generic_cycle_simulation_handoff.context_job_ref
                if compiled.generic_cycle_simulation_handoff is not None
                else None
            ),
            parent_profile_ref=(
                compiled.generic_cycle_simulation_handoff.profile_ref
                if compiled.generic_cycle_simulation_handoff is not None
                else None
            ),
            parent_profile_id=(
                compiled.generic_cycle_simulation_handoff.profile.profile_id
                if compiled.generic_cycle_simulation_handoff is not None
                else None
            ),
            child_profile_family_ref=(
                compiled.generic_cycle_simulation_handoff.n4_child_profile_family_ref
                if compiled.generic_cycle_simulation_handoff is not None
                else None
            ),
            child_profile_set_ref=compiled.n4_child_profile_set_ref,
            child_profile_status="not_established",
            child_profile_limitation_code=limitation,
            n5_limitation_code="generic_n4_child_profile_set_not_established",
            recursive_cycle_checkpoint=checkpoint,
            limitation_code=limitation,
            **n6_history_fields,
        )

    parent_handoff = compiled.generic_cycle_simulation_handoff
    set_ref = compiled.n4_child_profile_set_ref
    source_ref = compiled.n4_recursive_source_ref
    if (
        parent_handoff is None
        or set_ref is None
        or source_ref is None
        or compiled.n4_recursive_source_job_id is None
        or compiled.n4_recursive_source_run_id is None
        or compiled.n4_recursive_source_tenant_id != tenant_id
        or compiled.n4_recursive_source_cell_id != cell_id
        or parent_handoff.context_job_ref != compiled.n4_recursive_source_context_job_ref
        or parent_handoff.profile.profile_selection_kind != "problem"
        or parent_handoff.profile.profile_selection_ref
        != compiled.n4_recursive_source_profile_selection_ref
        or compiled.n4_child_profile_status != "not_attempted"
    ):
        return RunGenericCycleSimulationProjection(
            schema_version="policyos.runtime.run_generic_cycle_simulation_projection.v3",
            run_id=run_id,
            artifact_status="resolved",
            source_ref=ref,
            source_content_hash=compiled.content_hash,
            n4_source_ref=source_ref,
            n4_source_status="not_established",
            n4_source_limitation_code="generic_n4_source_compiled_binding_mismatch",
            parent_context_job_ref=parent_handoff.context_job_ref if parent_handoff else None,
            parent_profile_ref=parent_handoff.profile_ref if parent_handoff else None,
            parent_profile_id=parent_handoff.profile.profile_id if parent_handoff else None,
            child_profile_family_ref=(
                parent_handoff.n4_child_profile_family_ref if parent_handoff else None
            ),
            child_profile_set_ref=set_ref,
            child_profile_status="not_established",
            child_profile_limitation_code="generic_n4_source_compiled_binding_mismatch",
            n5_limitation_code="generic_n4_source_compiled_binding_mismatch",
            recursive_cycle_checkpoint=checkpoint,
            limitation_code="generic_n4_source_compiled_binding_mismatch",
            **n6_history_fields,
        )

    generic_owner = GenericCycleSimulationAdmissionOwner(profiles=(), store=store)
    context_owner = CycleSubstrateContextArtifactOwner(store=store)
    source_repository = GenerationSourceRepository(store)
    history_owner = RecursiveLeafContextOwner(
        store=store,
        context_owner=context_owner,
        admission_owner=None,
        generic_admission_owner=generic_owner,
    )
    try:
        family = history_owner.load_n4_child_profile_set(
            set_ref,
            expected_job_id=parent_handoff.job_id,
            expected_run_id=parent_handoff.run_id,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
            expected_parent_handoff=parent_handoff,
            source_repository=source_repository,
        )
        if (
            family.source_ref != source_ref
            or family.parent_problem != compiled.design_problem
            or family.parent_problem_ref != compiled.design_problem_ref
            or family.n4_child_profile_family_ref != parent_handoff.n4_child_profile_family_ref
            or family.authority_purpose != "cycle_input_candidate_only"
        ):
            raise ValueError("generic_n4_child_profile_set_compiled_binding_mismatch")
        parent_context = context_owner.resolve_historical_job_artifact(
            parent_handoff.context_job_ref,
            problem=compiled.design_problem,
            expected_job_id=parent_handoff.job_id,
            expected_run_id=parent_handoff.run_id,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
        )
        if parent_context.context != parent_handoff.context:
            raise ValueError("generic_parent_context_history_mismatch")
        generic_owner.resolve_profile_historical(
            parent_handoff.profile_ref,
            expected_profile=parent_handoff.profile,
            job_id=parent_handoff.job_id,
            run_id=parent_handoff.run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        child_rows = {row.node_ref: row for row in family.children}
        if len(child_rows) != len(family.children):
            raise ValueError("generic_child_profile_set_duplicate_node")
        source = source_repository.load(
            family.source_ref,
            run_id=family.source_run_id,
            expected_run_id=family.run_id,
            expected_job_id=family.job_id,
            expected_tenant_id=family.tenant_id,
            expected_cell_id=family.cell_id,
            context_job_ref=family.parent_handoff.context_job_ref,
            profile_ref=family.parent_handoff.profile_ref,
            n4_child_profile_family_ref=family.n4_child_profile_family_ref,
        )
        derived = derive_n4_candidate_child_problems(
            family.parent_problem,
            source.generation_result,
            model_id=source.generation_result.model_id,
        )
        # ``load_n4_child_profile_set`` already derives and replays the exact source
        # children. This second set comparison prevents compiled graph rows from
        # becoming the source of their own denominator.
        expected_child_nodes = {
            "design-problem://"
            + cycle_job_design_problem_ref(child.problem).removeprefix("sha256:")
            for child in derived
        }
        root_node_ref = "design-problem://" + cycle_job_design_problem_ref(
            compiled.design_problem
        ).removeprefix("sha256:")
        if set(child_rows) != expected_child_nodes:
            raise ValueError("generic_child_profile_set_source_denominator_mismatch")
        nodes = tuple(compiled.recursive_run.nodes)
        if len({node.node_ref for node in nodes}) != len(nodes):
            raise ValueError("generic_recursive_graph_duplicate_node")
        _require_generic_recursive_root_child_denominator(
            nodes=nodes,
            root_node_ref=root_node_ref,
            expected_child_nodes=expected_child_nodes,
        )
        resolved_child_bindings = tuple(
            RunGenericCycleSimulationChildProfileBinding(
                node_ref=row.node_ref,
                design_problem_ref=cycle_job_design_problem_ref(row.problem),
                source_ref=row.source_ref,
                source_result_ref=row.source_result_ref,
                source_atom_refs=row.source_atom_refs,
                semantic_ref=row.semantic_ref,
                context_job_ref=row.handoff.context_job_ref,
                profile_ref=row.handoff.profile_ref,
                profile_id=row.handoff.profile.profile_id,
                profile_selection_ref=row.handoff.profile.profile_selection_ref,
                historical_binding_status="resolved",
            )
            for row in family.children
        )
    except CanonicalProfileRefusalError:
        raise
    except (OSError, RuntimeDependencyError, RuntimeError, TypeError, ValueError) as exc:
        _raise_generic_read_access_refusal(exc)
        return RunGenericCycleSimulationProjection(
            schema_version="policyos.runtime.run_generic_cycle_simulation_projection.v3",
            run_id=run_id,
            artifact_status="resolved",
            source_ref=ref,
            source_content_hash=compiled.content_hash,
            n4_source_ref=source_ref,
            n4_source_status="not_established",
            n4_source_limitation_code="generic_n4_source_reference_not_established",
            parent_context_job_ref=parent_handoff.context_job_ref,
            parent_profile_ref=parent_handoff.profile_ref,
            parent_profile_id=parent_handoff.profile.profile_id,
            child_profile_family_ref=parent_handoff.n4_child_profile_family_ref,
            child_profile_set_ref=set_ref,
            child_profile_status="not_established",
            child_profile_limitation_code="generic_n4_child_profile_set_reference_not_established",
            n5_limitation_code="generic_n4_child_profile_set_reference_not_established",
            recursive_cycle_checkpoint=checkpoint,
            limitation_code="generic_n4_child_profile_set_reference_not_established",
            **n6_history_fields,
        )

    observations: list[RunGenericCycleSimulationN5Observation] = []
    n5_limitation: str | None = None
    nodes_by_ref = {node.node_ref: node for node in nodes}
    for node_ref in sorted(expected_child_nodes):
        try:
            node = nodes_by_ref.get(node_ref)
            if not isinstance(node, RecursiveCycleNode) or node.cycle_run is None:
                # Keep a typed limitation for failed, pending, or missing
                # siblings while preserving observations already replayed.
                n5_limitation = "generic_n5_sibling_checkpoint_not_established"
                continue
            binding = child_rows[node_ref]
            child_source_run_id = _generation_source_run_id(binding.problem)
            if node.cycle_run.run_id != child_source_run_id:
                raise ValueError("generic_n5_child_source_run_identity_mismatch")
            history_projection = resolve_generation_cycle_run_context_history(
                node.cycle_run,
                context_owner=context_owner,
                initial_problem=binding.problem,
                expected_job_id=family.job_id,
                expected_run_id=family.run_id,
                expected_tenant_id=family.tenant_id,
                expected_cell_id=family.cell_id,
            )
            if history_projection.status != "resolved":
                n5_limitation = "generation_cycle_context_history_not_established"
                continue
            history_by_index = {row.cycle_index: row for row in history_projection.bindings}
            for cycle in node.cycle_run.cycles:
                simulation = cycle.simulation
                generic_refs = (
                    simulation.generic_n4_source_ref,
                    simulation.generic_context_job_ref,
                    simulation.generic_profile_ref,
                    simulation.generic_n4_child_profile_family_ref,
                    simulation.generic_n4_child_profile_set_ref,
                    simulation.generic_n5_input_ref,
                    simulation.generic_n5_execution_ref,
                    simulation.generic_profile_selection_ref,
                )
                if not any(value is not None for value in generic_refs):
                    n5_limitation = "generic_n5_observation_not_emitted"
                    continue
                if any(value is None for index, value in enumerate(generic_refs) if index != 6):
                    raise ValueError("generic_n5_compiled_lineage_incomplete")
                (
                    cycle_source_ref,
                    cycle_context_ref,
                    cycle_profile_ref,
                    cycle_family_ref,
                    cycle_set_ref,
                    input_ref,
                    execution_ref,
                    selection_ref,
                ) = generic_refs
                history_binding = history_by_index.get(cycle.cycle_index)
                if history_binding is None:
                    raise ValueError("generic_n5_cycle_context_history_binding_missing")
                if cycle.cycle_index == 0 and (
                    artifact_ref_identity_key(history_binding.context_job_ref)
                    != artifact_ref_identity_key(binding.handoff.context_job_ref)
                    or history_binding.context.content_hash != binding.handoff.context.content_hash
                ):
                    raise ValueError("generic_n5_cycle_initial_context_binding_mismatch")
                if (
                    cycle.design_problem_ref != cycle_job_design_problem_ref(binding.problem)
                    or cycle_context_ref is None
                    or artifact_ref_identity_key(cycle_context_ref)
                    != artifact_ref_identity_key(history_binding.context_job_ref)
                    or cycle_profile_ref != binding.handoff.profile_ref
                    or cycle_family_ref != family.n4_child_profile_family_ref
                    or cycle_set_ref != set_ref
                    or selection_ref != binding.selection.profile_selection_ref
                ):
                    raise ValueError("generic_n5_compiled_child_binding_mismatch")
                if cycle.design_problem_basis_ref != cycle_job_design_problem_ref(
                    history_binding.problem
                ):
                    raise ValueError("generic_n5_cycle_problem_basis_mismatch")
                expected_child_selection = generic_owner._rebind_child_selection_for_problem(
                    child_selection=binding.selection,
                    problem=history_binding.problem,
                    profile=binding.handoff.profile,
                )
                cycle_source = source_repository.load(
                    cycle_source_ref,
                    run_id=child_source_run_id,
                    expected_run_id=family.run_id,
                    expected_job_id=family.job_id,
                    expected_tenant_id=family.tenant_id,
                    expected_cell_id=family.cell_id,
                    context_job_ref=history_binding.context_job_ref,
                    profile_ref=cycle_profile_ref,
                    n4_child_profile_family_ref=family.n4_child_profile_family_ref,
                )
                if (
                    cycle_source.problem != history_binding.problem
                    or cycle_source.cycle_index != cycle.cycle_index
                    or cycle_source.cycle_substrate_context is None
                    or cycle_source.cycle_substrate_context.content_hash
                    != history_binding.context.content_hash
                    or not generic_owner.context_matches_profile(
                        history_binding.context,
                        binding.handoff.profile,
                        history_binding.problem,
                    )
                ):
                    raise ValueError("generic_n5_cycle_source_context_history_mismatch")
                source_candidates = tuple(
                    candidate
                    for candidate in cycle_source.generation_result.candidates
                    if candidate.candidate_id == simulation.candidate_id
                )
                if len(source_candidates) != 1:
                    raise ValueError("generic_n5_cycle_candidate_source_mismatch")
                outcome_variable = _value_outcome_variable(
                    source_candidates[0], history_binding.problem
                )
                if outcome_variable is None or simulation.status not in {
                    "joint_simulated",
                    "simulation_blocked",
                }:
                    raise ValueError("generic_n5_cycle_candidate_outcome_not_established")
                join = generic_owner.resolve_n5_execution_join(
                    execution_ref,
                    expected=GenericN5ExecutionJoinExpectation(
                        input_ref=input_ref,
                        result_ref=simulation.simulation_result_ref,
                        status=simulation.status,
                        n4_source_ref=cycle_source_ref,
                        context_job_ref=history_binding.context_job_ref,
                        profile_ref=binding.handoff.profile_ref,
                        child_family_ref=family.n4_child_profile_family_ref,
                        child_set_ref=set_ref,
                        profile_selection_ref=selection_ref,
                        profile=binding.handoff.profile,
                        child_selection=expected_child_selection,
                        design_problem_ref=cycle.design_problem_basis_ref,
                        outcome_variable=outcome_variable,
                        cycle_index=cycle.cycle_index,
                        candidate_id=simulation.candidate_id,
                        candidate_atom_hash=source_candidates[0].atom.content_hash,
                        world_model_record_content_hash=(
                            history_binding.context.world_model_record.content_hash
                        ),
                        job_id=family.job_id,
                        run_id=family.run_id,
                        source_run_id=child_source_run_id,
                        tenant_id=family.tenant_id,
                        cell_id=family.cell_id,
                    ),
                )
                if join.code in {
                    "generic_n5_input_scope_refused",
                    "generic_n5_execution_scope_refused",
                }:
                    raise ArtifactOwnershipError("generic selected N5 scope mismatch")
                if join.status != "resolved":
                    # Preserve only the independently checked candidate result;
                    # a known invalid or mismatching join refuses that row alone.
                    conflict = join.status in {"invalid", "mismatch"}
                    result_ref = simulation.simulation_result_ref
                    candidate_result = None
                    candidate_blockers: tuple[str, ...] = ()
                    if not conflict and result_ref is not None:
                        candidate_manifest = _generic_selected_result_manifest(
                            store, result_ref, tenant_id=tenant_id, cell_id=cell_id
                        )
                        candidate_selected_ref = artifact_ref_for_manifest(candidate_manifest)
                        source_candidate = source_candidates[0]
                        atoms = tuple(getattr(source_candidate, "intervention_atoms", ()) or ())
                        if not atoms:
                            atoms = (source_candidate.atom,)
                        candidate_result = load_joint_simulation_result(
                            candidate_selected_ref,
                            store=store,
                            expected_world_model_record_content_hash=(
                                history_binding.context.world_model_record.content_hash
                            ),
                            expected_atom_ids=tuple(atom.intervention_id for atom in atoms),
                            expected_selected_outcomes=(outcome_variable,),
                        )
                        if candidate_result.receipt.payload_hash != simulation.simulation_ref:
                            raise ValueError("generic_n5_candidate_receipt_binding_mismatch")
                        candidate_status, candidate_blockers = _joint_simulation_port_outcome(
                            candidate_result
                        )
                        if candidate_status != simulation.status:
                            raise ValueError("generic_n5_candidate_status_binding_mismatch")
                    if (
                        not conflict
                        and simulation.status == "joint_simulated"
                        and candidate_result is None
                    ):
                        raise ValueError("generic_n5_candidate_result_unavailable")
                    limitation = (
                        "n5_execution_request_provenance_conflict"
                        if conflict
                        else "n5_execution_request_provenance_not_established"
                    )
                    row_status = "simulation_blocked" if conflict else simulation.status
                    value_port = cycle.value_port
                    n8_status = (
                        "value_blocked"
                        if conflict
                        else value_port.status
                        if value_port.status == "value_conditional"
                        else "value_pending_n8"
                    )
                    n8_fields = (
                        _n8_interaction_qualification_fields(value_port, include_status=False)
                        if n8_status == "value_conditional"
                        else {}
                    )
                    result_body_status = (
                        "not_established" if result_ref is not None else "not_applicable"
                    )
                    observations.append(
                        RunGenericCycleSimulationN5Observation(
                            node_ref=node_ref,
                            design_problem_ref=cycle.design_problem_ref,
                            cycle_index=cycle.cycle_index,
                            candidate_id=simulation.candidate_id,
                            status=row_status,
                            simulation_result_ref=result_ref,
                            simulation_result_body_status=result_body_status,
                            simulation_result_body_limitation_code=(
                                "generic_n5_result_body_request_binding_not_established"
                                if result_ref is not None
                                else None
                            ),
                            n4_source_ref=cycle_source_ref,
                            context_job_ref=history_binding.context_job_ref,
                            profile_ref=binding.handoff.profile_ref,
                            child_profile_family_ref=family.n4_child_profile_family_ref,
                            child_profile_set_ref=set_ref,
                            n5_input_ref=input_ref,
                            n5_execution_ref=execution_ref,
                            n5_owner_join_status=join.status,
                            n5_owner_join_limitation_code=join.code,
                            n5_request_binding_status="not_established",
                            profile_selection_ref=selection_ref,
                            atom_ids=tuple(candidate_result.atom_ids) if candidate_result else (),
                            selected_outcomes=(
                                tuple(candidate_result.selected_outcomes)
                                if candidate_result
                                else ()
                            ),
                            world_model_record_content_hash=(
                                history_binding.context.world_model_record.content_hash
                            ),
                            authority_blockers=tuple(
                                dict.fromkeys(
                                    (
                                        *simulation.authority_blockers,
                                        *candidate_blockers,
                                        limitation,
                                    )
                                )
                            ),
                            n8_status=n8_status,
                            n8_lineage_status="not_established",
                            n8_authority_blockers=tuple(
                                dict.fromkeys(
                                    (
                                        *value_port.authority_blockers,
                                        *candidate_blockers,
                                        limitation,
                                    )
                                )
                            ),
                            n8_limitation_code=limitation,
                            n5_interaction_evidence=(
                                _n5_interaction_evidence_projection(candidate_result)
                            ),
                            **_n5_interaction_scope_fields(candidate_result),
                            **n8_fields,
                        )
                    )
                    n5_limitation = limitation
                    continue
                execution = join.execution
                input_record = join.input_record
                if execution is None or input_record is None:
                    raise ValueError("generic_n5_execution_join_resolved_without_record")
                if input_record.child_selection != expected_child_selection:
                    raise ValueError("generic_n5_cycle_child_selection_rebind_mismatch")
                request_binding_status = (
                    "resolved"
                    if type(execution) is GenericCycleSimulationN5ExecutionV3
                    and type(execution.request_binding) is GenericCycleSimulationN5RequestBindingV2
                    else "not_established"
                )
                request_content_hash = (
                    execution.request_binding.request_content_hash
                    if type(execution) is GenericCycleSimulationN5ExecutionV3
                    and type(execution.request_binding) is GenericCycleSimulationN5RequestBindingV2
                    else None
                )
                resolved_result = None
                result_manifest = None
                result_body = None
                result_body_status: Literal["not_applicable", "resolved", "not_established"] = (
                    "not_applicable"
                )
                result_body_limitation_code: (
                    Literal[
                        "generic_n5_result_body_request_binding_not_established",
                        "generic_n5_result_body_selected_manifest_view_not_established",
                        "generic_n5_result_body_execution_not_successful",
                        "generic_n5_result_body_content_refused",
                    ]
                    | None
                ) = None
                blockers = tuple(simulation.authority_blockers)
                if execution.result_ref is not None:
                    result_body_status = "not_established"
                    result_manifest = _generic_selected_result_manifest(
                        store, execution.result_ref, tenant_id=tenant_id, cell_id=cell_id
                    )
                    expected_atom_ids = (
                        tuple(
                            atom.intervention_id
                            for atom in execution.request_binding.request.intervention_atoms
                        )
                        if request_binding_status == "resolved"
                        and type(execution) is GenericCycleSimulationN5ExecutionV3
                        else None
                    )
                    resolved_result = load_joint_simulation_result(
                        artifact_ref_for_manifest(result_manifest),
                        store=store,
                        expected_world_model_record_content_hash=(
                            input_record.profile.context_inputs.world_model_record.content_hash
                        ),
                        expected_atom_ids=expected_atom_ids,
                        expected_selected_outcomes=(input_record.outcome_variable,),
                        expected_request=execution.request_binding.request,
                    )
                    if execution.status != "joint_simulated":
                        result_body_limitation_code = (
                            "generic_n5_result_body_execution_not_successful"
                        )
                    elif request_binding_status != "resolved":
                        result_body_limitation_code = (
                            "generic_n5_result_body_request_binding_not_established"
                        )
                    elif (
                        execution.result_ref.manifest_profile_sha256 is None
                        or result_manifest.artifact_schema is None
                    ):
                        result_body_limitation_code = (
                            "generic_n5_result_body_selected_manifest_view_not_established"
                        )
                    else:
                        try:
                            result_body = RunGenericCycleSimulationN5ResultBody.model_validate(
                                {
                                    "artifact_ref": execution.result_ref,
                                    "artifact_schema_name": result_manifest.artifact_schema.name,
                                    "artifact_schema_version": (
                                        result_manifest.artifact_schema.version
                                    ),
                                    "result_schema_version": resolved_result.schema_version,
                                    "selected_manifest_profile_sha256": (
                                        execution.result_ref.manifest_profile_sha256
                                    ),
                                    "world_model_record_ref": (
                                        resolved_result.world_model_record_ref
                                    ),
                                    "world_model_record_content_hash": (
                                        resolved_result.world_model_record_content_hash
                                    ),
                                    "atom_ids": resolved_result.atom_ids,
                                    "selected_outcomes": resolved_result.selected_outcomes,
                                    "horizon": resolved_result.horizon.model_dump(mode="python"),
                                    "trajectories": tuple(
                                        {
                                            "run_level": trajectory.run_level,
                                            "atom_ids": trajectory.atom_ids,
                                            "points": tuple(
                                                {
                                                    "step": point.step,
                                                    "outcomes": point.outcomes,
                                                    "effects": point.effect,
                                                }
                                                for point in trajectory.points
                                            ),
                                        }
                                        for trajectory in resolved_result.trajectories
                                    ),
                                    "uncertainty_kind": resolved_result.uncertainty_kind,
                                    "authority_purpose": "cycle_input_candidate_only",
                                    "candidate_status": "candidate_unverified",
                                    "currentness_status": "not_established",
                                    "publication_authority": False,
                                }
                            )
                        except ValidationError:
                            # A malformed supplied projection is refused explicitly.
                            result_body_limitation_code = "generic_n5_result_body_content_refused"
                        else:
                            result_body_status = "resolved"
                    result_status, result_blockers = _joint_simulation_port_outcome(
                        resolved_result, request=execution.request_binding.request
                    )
                    if (
                        execution.status == "joint_simulated" and result_status != "joint_simulated"
                    ) or not set(result_blockers).issubset(blockers):
                        raise ValueError("generic_n5_result_execution_status_mismatch")
                elif simulation.status == "joint_simulated":
                    raise ValueError("generic_n5_result_reference_not_established")
                value_port = cycle.value_port
                n8_resolved = False
                n8_value_ref = None
                n8_limitation = "generic_n8_conditional_projection_not_established"
                if value_port.status == "value_conditional":
                    if (
                        resolved_result is None
                        or value_port.candidate_id != simulation.candidate_id
                        or value_port.value_ref != str(execution.result_ref.artifact_id)
                        or value_port.evaluation_mode != "simulate_only"
                        or value_port.decision_grade != "low"
                        or value_port.world_model_record_content_hash
                        != input_record.profile.context_inputs.world_model_record.content_hash
                        or value_port.value_receipt is not None
                        or value_port.method_selection_receipt is not None
                        or "simulation_only_k_sim_not_world_evidence" not in blockers
                    ):
                        raise ValueError("generic_n8_conditional_consumer_binding_mismatch")
                    if request_binding_status == "resolved":
                        n8_resolved = True
                        n8_value_ref = value_port.value_ref
                        n8_limitation = None
                    else:
                        n8_limitation = "generic_n5_request_binding_not_established"
                elif value_port.authority_blockers:
                    n8_limitation = value_port.authority_blockers[0]
                observations.append(
                    RunGenericCycleSimulationN5Observation(
                        node_ref=node_ref,
                        design_problem_ref=cycle.design_problem_ref,
                        cycle_index=cycle.cycle_index,
                        candidate_id=simulation.candidate_id,
                        status=simulation.status,
                        simulation_result_ref=execution.result_ref,
                        simulation_result_body=result_body,
                        simulation_result_body_status=result_body_status,
                        simulation_result_body_limitation_code=result_body_limitation_code,
                        n4_source_ref=cycle_source_ref,
                        context_job_ref=history_binding.context_job_ref,
                        profile_ref=binding.handoff.profile_ref,
                        child_profile_family_ref=family.n4_child_profile_family_ref,
                        child_profile_set_ref=set_ref,
                        n5_input_ref=input_ref,
                        n5_execution_ref=execution_ref,
                        n5_owner_join_status="resolved",
                        n5_request_binding_status=request_binding_status,
                        n5_request_content_hash=request_content_hash,
                        profile_selection_ref=selection_ref,
                        atom_ids=(
                            tuple(resolved_result.atom_ids) if resolved_result is not None else ()
                        ),
                        selected_outcomes=(
                            tuple(resolved_result.selected_outcomes)
                            if resolved_result is not None
                            else ()
                        ),
                        world_model_record_content_hash=(execution.world_model_record_content_hash),
                        authority_blockers=blockers,
                        n8_status=value_port.status,
                        n8_lineage_status="resolved" if n8_resolved else "not_established",
                        n8_value_ref=n8_value_ref,
                        n8_authority_blockers=tuple(value_port.authority_blockers),
                        n8_limitation_code=n8_limitation,
                        n5_interaction_evidence=(
                            _n5_interaction_evidence_projection(resolved_result)
                        ),
                        **_n5_interaction_scope_fields(resolved_result),
                        **_n8_interaction_qualification_fields(
                            value_port,
                            include_status=False,
                        ),
                    )
                )
        except CanonicalProfileRefusalError as exc:
            _raise_generic_read_access_refusal(exc)
            n5_limitation = (
                "generic_n5_persisted_lineage_not_established"
                if exc.code
                in {
                    "canon_profile_raw_manifest_unavailable",
                    "canon_profile_typed_manifest_unavailable",
                    "canon_profile_payload_unavailable",
                }
                else "generic_n5_persisted_lineage_invalid"
            )
            continue
        except ValidationError as exc:
            # Keep a source-resolved but structurally incoherent current scope
            # distinct from an absent/unreadable N5 lineage.
            n5_limitation = (
                "generic_n5_interaction_scope_not_established"
                if _is_n5_interaction_scope_validation_error(exc)
                else "generic_n5_persisted_lineage_not_established"
            )
            continue
        except (OSError, RuntimeDependencyError, RuntimeError, TypeError, ValueError) as exc:
            _raise_generic_read_access_refusal(exc)
            # Preserve each sibling that independently replayed. The recursive
            # checkpoint carries the failed sibling's exact terminal state.
            n5_limitation = "generic_n5_persisted_lineage_not_established"
            continue

    parent_fields: dict[str, Any] = {}
    parent_node = nodes_by_ref.get(root_node_ref)
    if isinstance(parent_node, RecursiveCycleNode) and parent_node.joint_simulation is not None:
        parent_fields = {
            "joint_parent_status": "not_established",
            "joint_parent_limitation_code": "generic_joint_parent_result_not_established",
        }
        try:
            parent_result_ref = parent_node.joint_simulation_ref
            if parent_result_ref is None:
                raise FileNotFoundError("generic_joint_parent_result_missing")
            parent_manifest = _generic_selected_result_manifest(
                store, parent_result_ref, tenant_id=tenant_id, cell_id=cell_id
            )
            parent_selected_ref = artifact_ref_for_manifest(parent_manifest)
            parent_result = load_joint_simulation_result(
                parent_selected_ref,
                store=store,
                expected_world_model_record_content_hash=(
                    parent_handoff.profile.context_inputs.world_model_record.content_hash
                ),
                expected_atom_ids=tuple(parent_node.joint_simulation.atom_ids),
                expected_selected_outcomes=tuple(parent_node.joint_simulation.selected_outcomes),
            )
            if parent_result.model_dump(mode="json") != parent_node.joint_simulation.model_dump(
                mode="json"
            ):
                raise ValueError("generic_joint_parent_compiled_result_mismatch")
            parent_status, parent_blockers = _joint_simulation_port_outcome(parent_result)
            selection_fields = _parent_joint_candidate_selection_projection(
                compiled=compiled,
                node=parent_node,
                request=parent_node.joint_simulation_request,
                root_n4_source=source,
            )
            # This scoped selection is a numerical candidate; the serialized
            # parent request is not independent execution-producer provenance.
            scope_limitation = (
                "parent_joint_coupling_evidence_not_established"
                if parent_node.joint_simulation_request is not None
                and parent_node.joint_simulation_request.coupling_graph is None
                else "parent_joint_request_binding_not_established"
            )
            if parent_node.joint_simulation_request is None:
                raise _GenericParentNotEstablishedError("generic_joint_parent_request_missing")
            candidate_value = _consume_parent_joint_candidate_n8(
                candidate_id="joint-candidate:"
                + parent_node.joint_candidate_selection.content_hash,
                request=parent_node.joint_simulation_request,
                result_ref=parent_selected_ref,
                result=parent_result,
                problem=compiled.design_problem,
                artifact_store=store,
            )
            if candidate_value.status != "value_conditional":
                raise _GenericParentNotEstablishedError(
                    "generic_joint_parent_n8_candidate_not_established"
                )
            parent_row = RunCandidateSimulationN5Observation(
                node_ref=parent_node.node_ref,
                design_problem_ref=parent_node.design_problem_ref,
                candidate_id=candidate_value.candidate_id,
                atom_ids=tuple(parent_result.atom_ids),
                selected_outcomes=tuple(parent_result.selected_outcomes),
                status=parent_status,
                simulation_ref=parent_result.receipt.payload_hash,
                simulation_result_ref=parent_selected_ref,
                world_model_record_content_hash=parent_result.world_model_record_content_hash,
                k_world_ref_before=parent_result.world_model_record_content_hash,
                k_world_ref_after=parent_result.world_model_record_content_hash,
                authority_blockers=parent_blockers,
                n5_interaction_evidence=_n5_interaction_evidence_projection(parent_result),
                n8_status=candidate_value.status,
                n8_candidate_value_ref=candidate_value.value_ref,
                n8_candidate_decision_grade=candidate_value.decision_grade,
                n8_numeric_interaction=candidate_value.numeric_interaction,
                n8_numeric_interaction_basis=candidate_value.numeric_interaction_basis,
                n8_interaction_sampling_status=candidate_value.interaction_sampling_status,
                n8_joint_scope_status="not_established",
                n8_joint_scope_limitation_code=scope_limitation,
                n8_authority_blockers=tuple(
                    dict.fromkeys((*candidate_value.authority_blockers, scope_limitation))
                ),
                **_n5_interaction_scope_fields(parent_result),
                **selection_fields,
            )
        except CanonicalProfileRefusalError as exc:
            _raise_generic_read_access_refusal(exc)
            parent_fields["joint_parent_limitation_code"] = (
                "generic_joint_parent_result_unavailable"
                if exc.code
                in {
                    "canon_profile_raw_manifest_unavailable",
                    "canon_profile_typed_manifest_unavailable",
                    "canon_profile_payload_unavailable",
                }
                else "generic_joint_parent_result_invalid"
            )
        except _GenericSelectedScopeNotEstablishedError:
            parent_fields["joint_parent_limitation_code"] = (
                "generic_joint_parent_scope_not_established"
            )
        except _GenericParentNotEstablishedError:
            pass
        except (OSError, RuntimeDependencyError, RuntimeError, TypeError, ValueError) as exc:
            _raise_generic_read_access_refusal(exc)
            code = getattr(exc, "code", None)
            if isinstance(exc, (OSError, RuntimeDependencyError)) or (
                code == "joint_simulation_result_unavailable"
            ):
                parent_fields["joint_parent_limitation_code"] = (
                    "generic_joint_parent_result_unavailable"
                )
            elif (code is None and isinstance(exc, (TypeError, ValueError))) or code in {
                "joint_simulation_result_integrity_invalid",
                "joint_simulation_result_execution_binding_invalid",
            }:
                parent_fields["joint_parent_limitation_code"] = (
                    "generic_joint_parent_result_invalid"
                )
        else:
            parent_fields = {
                "joint_parent_status": "resolved",
                "joint_parent_observations": (parent_row,),
            }

    return RunGenericCycleSimulationProjection(
        schema_version=(
            "policyos.runtime.run_generic_cycle_simulation_projection.v5"
            if parent_fields or any(row.n5_owner_join_status is not None for row in observations)
            else "policyos.runtime.run_generic_cycle_simulation_projection.v3"
        ),
        run_id=run_id,
        artifact_status="resolved",
        source_ref=ref,
        source_content_hash=compiled.content_hash,
        n4_source_ref=source_ref,
        n4_source_status="resolved",
        parent_context_job_ref=parent_handoff.context_job_ref,
        parent_profile_ref=parent_handoff.profile_ref,
        parent_profile_id=parent_handoff.profile.profile_id,
        child_profile_family_ref=family.n4_child_profile_family_ref,
        child_profile_set_ref=set_ref,
        child_profile_status="resolved",
        child_profile_bindings=resolved_child_bindings,
        n5_observations=tuple(observations),
        **parent_fields,
        n5_limitation_code=(
            n5_limitation or (None if observations else "generic_n5_observation_not_emitted")
        ),
        recursive_cycle_checkpoint=checkpoint,
        limitation_code=n5_limitation,
        **n6_history_fields,
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


def _run_predictive_calibration_with_service_source(
    control_service: Any,
    operation: Callable[..., Any],
    /,
    **kwargs: Any,
) -> Any:
    """Run a calibration producer or reader under its app-selected catalog source."""
    from polisyos.runtime.quality.substrate_registry import (
        CatalogServingSourcePaths,
        run_catalog_source_call,
    )

    source = getattr(control_service, "catalog_serving_source", None)
    if source is not None and type(source) is not CatalogServingSourcePaths:
        raise service_unavailable(
            "The configured catalog serving source is unavailable",
            code="predictive_calibration_catalog_source_invalid",
        )
    return run_catalog_source_call(source, operation, **kwargs)


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
    except CanonicalProfileRefusalError as exc:
        raise conflict(
            "The selected run artifact has a malformed or byte-inconsistent canon profile",
            code=exc.code,
        ) from exc
    except RunPaperSourceError as exc:
        raise conflict(
            str(exc),
            code=source_invalid_code,
        ) from exc


def _filter_temporal_lineage_roots(
    root_refs: list[ArtifactID | ArtifactRef], events: list[Any]
) -> tuple[list[ArtifactID | ArtifactRef], bool]:
    """Keep only root refs present in the scoped trace with full identity."""
    visible: set[tuple[str, str, str, str | None]] = {
        artifact_ref_identity_key(ref) for event in events for ref in event.output_artifact_refs
    }
    selected: list[ArtifactID | ArtifactRef] = []
    limitation = False
    for ref in root_refs:
        if not isinstance(ref, ArtifactRef):
            limitation = True
            continue
        key = artifact_ref_identity_key(ref)
        if key not in visible:
            limitation = True
            continue
        selected.append(ref)
        if ref.manifest_profile_sha256 is None:
            limitation = True
    return selected, limitation


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
            metadata={
                "count": len(runs),
                "cursor": page.cursor,
                "next_cursor": page.next_cursor,
            },
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
        responses=CANONICAL_PROFILE_REFUSAL_RESPONSES,
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
        responses=CANONICAL_PROFILE_REFUSAL_RESPONSES,
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

    @router.get(
        "/{run_id}/decision-packets/{packet_id}/candidate-hte",
        response_model=CandidateDecisionPacketHTEProjection,
        operation_id="get_run_candidate_hte_packet",
    )
    def get_run_candidate_hte_packet(
        run_id: str,
        packet_id: str,
        request: Request,
        manifest_profile_sha256: str = Query(..., min_length=1, max_length=128),
        _authorization: Any = Depends(_GET_RUN_CANDIDATE_PACKET_AUTHZ),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> CandidateDecisionPacketHTEProjection:
        """Expose one exact packet's candidate HTE after required run authorization."""
        del _authorization
        scope = require_access_scope(request)
        try:
            packet_run = ctx.run_index.get_run(run_id)
        except (KeyError, TypeError, ValueError) as exc:
            raise not_found("Run was not found", code="run_not_found") from exc
        if (
            packet_run.run_id != run_id
            or packet_run.details.run_id != run_id
            or packet_run.source_kind != "core_run"
        ):
            raise conflict(
                "The decision-packet owner run is not a resolved Core run",
                code="candidate_packet_run_identity_not_established",
            )
        if (
            not packet_run.details.tenant_id
            or not packet_run.details.cell_id
            or scope.tenant_id != packet_run.details.tenant_id
            or scope.cell_id != packet_run.details.cell_id
        ):
            raise conflict(
                "The decision-packet owner run is outside the verified tenant/cell scope",
                code="candidate_packet_run_scope_not_established",
            )
        try:
            packet_ref = require_exact_candidate_packet_ref(
                indexed_packet_ref=packet_run.decision_packet_ref,
                requested_packet_id=packet_id,
                requested_manifest_profile_sha256=manifest_profile_sha256,
            )
            bounded_read = read_core_json_artifact_bounded(
                ctx.store,
                packet_ref,
                limits=DECISION_PACKET_CANDIDATE_READ_LIMITS,
            )
            packet_payload = validate_bounded_candidate_packet(
                bounded_read=bounded_read,
                selected_ref=packet_ref,
            )
            candidate_status, source_run_id = candidate_packet_source_selector(packet_payload)
            require_same_candidate_source_run(
                packet_run_id=packet_run.run_id,
                source_run_id=source_run_id,
            )
            require_candidate_projection_scope(
                scope_tenant_id=scope.tenant_id,
                scope_cell_id=scope.cell_id,
                packet_tenant_id=packet_run.details.tenant_id,
                packet_cell_id=packet_run.details.cell_id,
                source_tenant_id=packet_run.details.tenant_id,
                source_cell_id=packet_run.details.cell_id,
            )
        except CandidatePacketProjectionRefusalError as exc:
            raise conflict(
                "The packet-bound HTE candidate is not established",
                code=exc.code,
            ) from exc
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise conflict(
                "The exact bounded DecisionPacket profile could not be established",
                code="candidate_packet_bounded_read_refused",
            ) from exc

        record_data_access_audit(
            request,
            resource_id=packet_run.run_id,
            resource_kind="runtime.run.decision_packet_candidate",
            tenant_id=packet_run.details.tenant_id,
            metadata={
                "decision_packet_id": str(packet_ref.artifact_id),
                "manifest_profile_sha256": packet_ref.manifest_profile_sha256,
                "source_run_id": source_run_id,
            },
        )
        record_data_access_audit(
            request,
            resource_id=source_run_id,
            resource_kind="runtime.run.method_execution_selection",
            tenant_id=packet_run.details.tenant_id,
            metadata={
                "decision_packet_id": str(packet_ref.artifact_id),
                "packet_owner_run_id": packet_run.run_id,
            },
        )

        fresh_source = None
        if candidate_status == "selected":
            control_service = _control_service_from_request(request)
            resolve_source = getattr(
                control_service,
                "resolve_completed_method_hte_selection",
                None,
            )
            if not callable(resolve_source):
                raise service_unavailable(
                    "The completed HTE source owner is unavailable",
                    code="completed_hte_source_owner_unavailable",
                )
            fresh_source = resolve_source(
                source_run_id=source_run_id,
                tenant_id=scope.tenant_id,
                cell_id=scope.cell_id,
            )
        try:
            return project_candidate_hte_packet(
                packet_payload=packet_payload,
                packet_run_id=packet_run.run_id,
                packet_ref=packet_ref,
                source_run_id_selector=source_run_id,
                fresh_source=fresh_source,
                reader_at=datetime.now(UTC),
            )
        except CandidatePacketProjectionRefusalError as exc:
            raise conflict(
                "The packet-bound HTE candidate does not reconcile to its owner",
                code=exc.code,
            ) from exc

    @router.get(
        "/{run_id}",
        response_model=RunDetailsResponse,
        operation_id="get_run_details",
        responses=CANONICAL_PROFILE_REFUSAL_RESPONSES,
    )
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
        method_selection_authorization: OptionalActionPermissionResult = Depends(
            _GET_RUN_METHOD_SELECTION_AUTHZ
        ),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> RunDetailsResponse:
        review_scope = require_access_scope(request)
        run = _resolve_method_execution_indexed_run(ctx, request, review_scope, run_id)
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

        # These enrichments are current views with no independently bound record-time.
        # A scoped historical read therefore returns only the temporally projected run.
        if temporal_scope is None:
            if not method_selection_authorization.allowed:
                method_execution_projection = DirectMethodExecutionRunProjection(
                    status="withheld",
                    limitations=("selected_view_permission_required",),
                )
                record_data_access_audit(
                    request,
                    resource_id=run_id,
                    resource_kind="runtime.run.method_execution_selection",
                    tenant_id=run.details.tenant_id,
                    outcome="denied",
                    metadata={"view": "selected_method_execution"},
                )
            elif (
                not run.details.tenant_id
                or review_scope.tenant_id != run.details.tenant_id
                or not run.details.cell_id
                or review_scope.cell_id != run.details.cell_id
            ):
                method_execution_projection = DirectMethodExecutionRunProjection(
                    status="withheld",
                    limitations=("owned_run_cell_scope_required",),
                )
                record_data_access_audit(
                    request,
                    resource_id=run_id,
                    resource_kind="runtime.run.method_execution_selection",
                    tenant_id=run.details.tenant_id,
                    outcome="denied",
                    metadata={"view": "selected_method_execution"},
                )
            else:
                record_data_access_audit(
                    request,
                    resource_id=run_id,
                    resource_kind="runtime.run.method_execution_selection",
                    tenant_id=run.details.tenant_id,
                    metadata={"view": "selected_method_execution"},
                )
                control_service = _control_service_from_request(request)
                read_method_execution_projection = getattr(
                    control_service,
                    "get_observational_method_run_projection",
                    None,
                )
                if callable(read_method_execution_projection):
                    method_execution_projection = read_method_execution_projection(
                        run_id=run_id,
                        expected_job_id=run.details.control_job_id,
                        tenant_id=run.details.tenant_id,
                        cell_id=run.details.cell_id,
                    )
                    if not isinstance(
                        method_execution_projection,
                        DirectMethodExecutionRunProjection,
                    ):
                        raise service_unavailable(
                            "The selected method execution projection is unavailable",
                            code="method_execution_projection_contract_invalid",
                        )
                else:
                    method_execution_projection = DirectMethodExecutionRunProjection(
                        status="unavailable",
                        limitations=("execution_outcome_not_established",),
                    )
            updates: dict[str, Any] = {
                "method_execution_selection": method_execution_projection,
            }

            if (
                not method_selection_authorization.allowed
                or not run.details.tenant_id
                or review_scope.tenant_id != run.details.tenant_id
                or not run.details.cell_id
                or review_scope.cell_id != run.details.cell_id
            ):
                record_data_access_audit(
                    request,
                    resource_id=run_id,
                    resource_kind="runtime.run.conditional_transport_candidate",
                    tenant_id=run.details.tenant_id,
                    outcome="denied",
                    metadata={"view": "conditional_transport_candidate"},
                )
            else:
                conditional_transport_candidate = _conditional_transport_candidate_for_indexed_run(
                    run, store=ctx.store
                )
                if conditional_transport_candidate is not None:
                    updates["conditional_transport_candidate"] = conditional_transport_candidate
                    record_data_access_audit(
                        request,
                        resource_id=run_id,
                        resource_kind="runtime.run.conditional_transport_candidate",
                        tenant_id=run.details.tenant_id,
                        outcome="conditional_transport_candidate_projected",
                        metadata={"view": "conditional_transport_candidate"},
                    )

            control_service = _control_service_from_request(request)
            operator_diagnostic = _latest_control_operator_diagnostic(control_service, run_id)
            policy_design_case_projection = _latest_control_policy_projection(
                control_service,
                run_id,
            )
            get_method_execution_producer_diagnostic = getattr(
                control_service,
                "get_method_execution_producer_diagnostic",
                None,
            )
            if callable(get_method_execution_producer_diagnostic):
                producer_diagnostic = get_method_execution_producer_diagnostic(
                    run_id=run_id,
                    tenant_id=run.details.tenant_id,
                    cell_id=run.details.cell_id,
                )
                if isinstance(producer_diagnostic, MethodExecutionProducerDiagnostic):
                    updates["method_execution_producer_diagnostic"] = producer_diagnostic

            candidate_simulation = _candidate_simulation_for_indexed_run(
                run,
                store=ctx.store,
                control_service=control_service,
            )
            if candidate_simulation is not None:
                updates["candidate_simulation"] = candidate_simulation
            generic_cycle_simulation = _generic_cycle_simulation_projection(
                run_id=run.details.run_id,
                tenant_id=run.details.tenant_id,
                cell_id=run.details.cell_id,
                root_artifacts=tuple(run.details.root_artifacts),
                store=ctx.store,
            )
            if generic_cycle_simulation is not None:
                updates["generic_cycle_simulation"] = generic_cycle_simulation
            if operator_diagnostic is not None:
                updates["operator_diagnostic"] = operator_diagnostic
            if policy_design_case_projection is not None:
                updates["policy_design_case_projection"] = policy_design_case_projection
            run_details = run_details.model_copy(update=updates)

        return RunDetailsResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            temporal_scope=temporal_scope,
            run=run_details,
        )

    @router.get(
        "/{run_id}/method-metrics",
        response_model=MethodMetricProjectionResponse,
        operation_id="get_run_method_metrics",
        dependencies=[Depends(_GET_RUN_METHOD_METRICS_AUTHZ)],
    )
    def get_run_method_metrics(
        run_id: str,
        request: Request,
        ctx: Annotated[RuntimeApiContext, Depends(get_runtime_api_context)],
    ) -> MethodMetricProjectionResponse:
        """Return only the bounded current AD01 metric projection for an owned run."""
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        scope = require_access_scope(request)
        if (
            not run.details.tenant_id
            or scope.tenant_id != run.details.tenant_id
            or not run.details.cell_id
            or scope.cell_id != run.details.cell_id
        ):
            raise forbidden(
                "Method metric projections require the verified run tenant and cell scope",
                code="method_metric_projection_scope_mismatch",
            )
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run.method_metrics",
            artifact_id=(
                str(run.details.manifest_ref.artifact_id)
                if run.details.manifest_ref is not None
                else None
            ),
        )
        control_service = _control_service_from_request(request)
        read_projection = getattr(
            control_service,
            "read_current_admitted_method_metric_projection",
            None,
        )

        def read_selected_projection() -> tuple[
            Literal["selected", "verification_missing", "invalid"],
            ArtifactRef | None,
            tuple[Any, ...],
            tuple[str, ...],
        ]:
            if not callable(read_projection):
                return (
                    "verification_missing",
                    None,
                    (),
                    ("current_method_metric_owner_unavailable",),
                )
            projection = read_projection(
                run_id=run_id,
                tenant_id=run.details.tenant_id,
                cell_id=run.details.cell_id,
            )
            status = getattr(projection, "status", None)
            vector_ref = getattr(projection, "vector_ref", None)
            observations = tuple(getattr(projection, "observations", ()))
            limitations = tuple(getattr(projection, "limitations", ()))
            if status not in {"selected", "verification_missing", "invalid"}:
                raise service_unavailable(
                    "The current method metric projection is unavailable",
                    code="method_metric_projection_read_unavailable",
                )
            if vector_ref is not None and type(vector_ref) is not ArtifactRef:
                dump = getattr(vector_ref, "model_dump", None)
                if not callable(dump):
                    raise service_unavailable(
                        "The current method metric projection has an invalid selected ref",
                        code="method_metric_projection_read_invalid",
                    )
                try:
                    vector_ref = ArtifactRef.model_validate(dump(mode="json"))
                except (TypeError, ValueError) as exc:
                    raise service_unavailable(
                        "The current method metric projection has an invalid selected ref",
                        code="method_metric_projection_read_invalid",
                    ) from exc
            return status, vector_ref, observations, limitations

        (
            projection_status,
            projection_vector_ref,
            projection_observations,
            projection_limitations,
        ) = read_selected_projection()
        candidate_score = None
        read_candidate_score = getattr(
            control_service, "read_current_completed_ex_ante_candidate_score", None
        )
        if projection_status == "selected" and callable(read_candidate_score):
            candidate_score = read_candidate_score(
                run_id=run_id, tenant_id=run.details.tenant_id, cell_id=run.details.cell_id
            )
            if not isinstance(candidate_score, MethodMetricCandidateScore):
                raise service_unavailable(
                    "The current candidate score projection is unavailable",
                    code="method_metric_candidate_score_invalid",
                )
            # Score replay can be long. Re-read the current projection after it,
            # and never join a score to a different selected vector profile.
            (
                projection_status,
                projection_vector_ref,
                projection_observations,
                projection_limitations,
            ) = read_selected_projection()
            if candidate_score.status == "selected" and (
                projection_status != "selected"
                or candidate_score.source_vector_ref != projection_vector_ref
            ):
                candidate_score = MethodMetricCandidateScore(
                    status="verification_missing",
                    limitations=("candidate_score_selection_changed_during_read",),
                )
        record_data_access_audit(
            request,
            resource_id=run_id,
            resource_kind="runtime.run.method_metrics",
            tenant_id=run.details.tenant_id,
            outcome=f"method_metric_projection_{projection_status}",
        )
        observations = tuple(
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in projection_observations
        )
        return MethodMetricProjectionResponse(
            meta=build_meta(request, source_kinds=[_as_source_kind(run.source_kind)]),
            run_id=run_id,
            status=projection_status,
            vector_ref=projection_vector_ref,
            observations=observations,
            limitations=projection_limitations,
            candidate_score=candidate_score,
        )

    @router.get(
        "/{run_id}/method-metric-comparison",
        response_model=CompletedExAnteCandidateComparisonResponse,
        operation_id="get_run_method_metric_comparison",
        dependencies=[Depends(_GET_RUN_METHOD_METRICS_AUTHZ)],
    )
    def get_run_method_metric_comparison(
        run_id: str,
        request: Request,
        ctx: Annotated[RuntimeApiContext, Depends(get_runtime_api_context)],
    ) -> CompletedExAnteCandidateComparisonResponse:
        """Recompute a completed run's candidate-only comparison under current scope."""
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        scope = require_access_scope(request)
        if (
            not run.details.tenant_id
            or scope.tenant_id != run.details.tenant_id
            or not run.details.cell_id
            or scope.cell_id != run.details.cell_id
        ):
            raise forbidden(
                "Method metric comparisons require the verified run tenant and cell scope",
                code="method_metric_projection_scope_mismatch",
            )
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run.method_metrics",
            artifact_id=(
                str(run.details.manifest_ref.artifact_id)
                if run.details.manifest_ref is not None
                else None
            ),
        )
        control_service = _control_service_from_request(request)
        read_comparison = getattr(
            control_service, "read_current_completed_ex_ante_comparison", None
        )
        if callable(read_comparison):
            comparison = read_comparison(
                run_id=run_id, tenant_id=run.details.tenant_id, cell_id=run.details.cell_id
            )
            if comparison is not None and not isinstance(
                comparison, CompletedExAnteCandidateRanking
            ):
                raise service_unavailable(
                    "The current candidate comparison is unavailable",
                    code="method_metric_candidate_comparison_invalid",
                )
        else:
            comparison = CompletedExAnteCandidateRanking(
                status="verification_missing",
                limitations=("current_candidate_comparison_owner_unavailable",),
            )
        record_data_access_audit(
            request,
            resource_id=run_id,
            resource_kind="runtime.run.method_metrics",
            tenant_id=run.details.tenant_id,
            outcome=(
                f"method_metric_comparison_{comparison.status}"
                if comparison
                else "method_metric_comparison_not_requested"
            ),
        )
        return CompletedExAnteCandidateComparisonResponse(
            meta=build_meta(request, source_kinds=[_as_source_kind(run.source_kind)]),
            run_id=run_id,
            candidate_comparison=comparison,
        )

    @router.post(
        "/{run_id}/predictive-calibration",
        response_model=PredictiveCalibrationResponse,
        operation_id="create_run_predictive_calibration",
        status_code=201,
        dependencies=[Depends(_CREATE_RUN_PREDICTIVE_CALIBRATION_AUTHZ)],
    )
    def create_run_predictive_calibration(
        run_id: str,
        body: PredictiveCalibrationRequest,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> PredictiveCalibrationResponse:
        if not ctx.allow_candidate_run_predictive_calibration_surface:
            raise service_unavailable(
                "Candidate predictive diagnostics are not enabled on this runtime",
                code="candidate_predictive_diagnostic_surface_disabled",
            )
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        scope = require_access_scope(request)
        actor_subject, actor_tenant_id, _actor_identity_id, _actor_roles = (
            principal_from_access_scope(scope)
        )
        if (
            actor_tenant_id != run.details.tenant_id
            or not scope.cell_id
            or scope.cell_id != run.details.cell_id
        ):
            raise forbidden(
                "Predictive diagnostics require the verified run tenant and cell scope",
                code="predictive_calibration_scope_mismatch",
            )
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run.predictive_calibration",
            artifact_id=(
                str(run.details.manifest_ref.artifact_id) if run.details.manifest_ref else None
            ),
        )
        control_service = _control_service_from_request(request)
        event_log = getattr(control_service, "_diagnostic_event_log", None)
        if event_log is None:
            raise service_unavailable(
                "Run diagnostic event log is unavailable",
                code="predictive_calibration_event_log_unavailable",
            )
        candidate_simulation = _candidate_simulation_for_indexed_run(
            run,
            store=ctx.store,
            control_service=control_service,
        )
        if candidate_simulation is not None:
            run = replace(
                run,
                details=run.details.model_copy(
                    update={"candidate_simulation": candidate_simulation}
                ),
            )
        try:
            association_ref, association = _run_predictive_calibration_with_service_source(
                control_service,
                produce_run_predictive_calibration,
                store=ctx.store,
                run=run,
                request=body,
                event_log=event_log,
                event_scope={
                    "run_id": run.details.run_id,
                    "job_id": run.details.control_job_id or "",
                    "tenant_id": scope.tenant_id,
                    "cell_id": scope.cell_id or "",
                },
                actor_subject=actor_subject,
            )
        except PredictiveCalibrationError as exc:
            if exc.code in {
                "predictive_calibration_intent_conflict",
                "predictive_calibration_legacy_intent_scope_unverifiable",
                "predictive_calibration_intent_in_progress",
                "predictive_calibration_intent_recovery_required",
                "predictive_calibration_completed_intent_result_unresolved",
            }:
                raise conflict(str(exc), code=exc.code) from exc
            raise unprocessable_entity(str(exc), code=exc.code) from exc
        return PredictiveCalibrationResponse(
            meta=build_meta(request, source_kinds=[_as_source_kind(run.source_kind)]),
            association_ref=association_ref,
            association=association,
        )

    @router.get(
        "/{run_id}/predictive-calibration",
        response_model=PredictiveCalibrationResponse,
        operation_id="get_run_predictive_calibration",
        dependencies=[Depends(_GET_RUN_PREDICTIVE_CALIBRATION_AUTHZ)],
    )
    def get_run_predictive_calibration(
        run_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),
    ) -> PredictiveCalibrationResponse:
        if not ctx.allow_candidate_run_predictive_calibration_surface:
            raise service_unavailable(
                "Candidate predictive diagnostics are not enabled on this runtime",
                code="candidate_predictive_diagnostic_surface_disabled",
            )
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        scope = require_access_scope(request)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run.predictive_calibration",
            artifact_id=(
                str(run.details.manifest_ref.artifact_id) if run.details.manifest_ref else None
            ),
        )
        control_service = _control_service_from_request(request)
        event_log = getattr(control_service, "_diagnostic_event_log", None)
        if event_log is None:
            raise service_unavailable(
                "Run diagnostic event log is unavailable",
                code="predictive_calibration_event_log_unavailable",
            )
        candidate_simulation = _candidate_simulation_for_indexed_run(
            run,
            store=ctx.store,
            control_service=control_service,
        )
        if candidate_simulation is not None:
            run = replace(
                run,
                details=run.details.model_copy(
                    update={"candidate_simulation": candidate_simulation}
                ),
            )
        try:
            association_ref, association = _run_predictive_calibration_with_service_source(
                control_service,
                load_run_predictive_calibration,
                store=ctx.store,
                run=run,
                event_log=event_log,
                event_scope={
                    "run_id": run.details.run_id,
                    "job_id": run.details.control_job_id or "",
                    "tenant_id": scope.tenant_id,
                    "cell_id": scope.cell_id or "",
                },
            )
        except FileNotFoundError as exc:
            raise not_found(
                "Run predictive-calibration diagnostic was not found",
                code="run_predictive_calibration_not_found",
            ) from exc
        except PredictiveCalibrationError as exc:
            raise conflict(str(exc), code=exc.code) from exc
        record_data_access_audit(
            request,
            resource_id=str(association_ref.artifact_id),
            resource_kind="runtime.run.predictive_calibration",
            tenant_id=run.details.tenant_id,
            outcome="predictive_diagnostic_read",
        )
        return PredictiveCalibrationResponse(
            meta=build_meta(request, source_kinds=[_as_source_kind(run.source_kind)]),
            association_ref=association_ref,
            association=association,
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

    @router.get(
        "/{run_id}/nodes",
        response_model=RunNodesResponse,
        operation_id="get_run_nodes",
        responses=CANONICAL_PROFILE_REFUSAL_RESPONSES,
    )
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
        nodes, notes = ctx.debug.list_run_nodes_with_notes(run)
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
            notes=notes,
        )

    @router.get(
        "/{run_id}/lineage",
        response_model=RunLineageResponse,
        operation_id="get_run_lineage",
        responses=CANONICAL_PROFILE_REFUSAL_RESPONSES,
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

        root_refs = ctx.run_index.resolve_root_artifact_refs(
            run,
            requested_root_ids=root_artifact_id or None,
        )
        root_profile_not_established = False
        root_ids = [ref.artifact_id if isinstance(ref, ArtifactRef) else ref for ref in root_refs]
        if (
            temporal_scope is not None
            and ctx.temporal.project_run_details(run.details, temporal_scope).finished_at is None
        ):
            visible_timeline = ctx.temporal.project_timeline(
                ctx.timeline.build_for_run(run).timeline,
                temporal_scope,
            )
            root_refs, root_profile_not_established = _filter_temporal_lineage_roots(
                root_refs, visible_timeline.events
            )
            root_ids = [
                ref.artifact_id if isinstance(ref, ArtifactRef) else ref for ref in root_refs
            ]

        if not root_ids and temporal_scope is None:
            raise bad_request(
                "No root artifacts available for lineage resolution",
                code="lineage_roots_missing",
            )

        try:
            lineage = (
                ctx.lineage.build_for_artifact_ids(
                    root_refs,
                    max_depth=max_depth,
                    max_nodes=max_nodes,
                )
                if root_refs
                else ArtifactLineageView(root_artifact_ids=[])
            )
            if root_profile_not_established:
                lineage = lineage.model_copy(
                    update={
                        "is_complete": False,
                        "notes": sorted(
                            set(lineage.notes).union({"root_manifest_profile_not_established"})
                        ),
                    }
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
            metadata={"root_artifact_count": len(root_refs)},
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
        responses=CANONICAL_PROFILE_REFUSAL_RESPONSES,
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
        except CanonicalProfileRefusalError as exc:
            raise conflict(
                "The run decision packet has a malformed or byte-inconsistent canon profile",
                code=exc.code,
                extensions={"run_id": run_id, "surface": "run_quantities"},
            ) from exc
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
        responses=CANONICAL_PROFILE_REFUSAL_RESPONSES,
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
        except CanonicalProfileRefusalError as exc:
            raise conflict(
                "The run decision packet has a malformed or byte-inconsistent canon profile",
                code=exc.code,
                extensions={"run_id": run_id, "surface": "run_fabric_decision_data"},
            ) from exc
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
        responses=CANONICAL_PROFILE_REFUSAL_RESPONSES,
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
        responses=CANONICAL_PROFILE_REFUSAL_RESPONSES,
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
        responses=CANONICAL_PROFILE_REFUSAL_RESPONSES,
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
        try:
            workflow = ctx.debug.get_run_workflow(run)
        except CanonicalProfileRefusalError as exc:
            raise conflict(
                "The selected workflow JSON has a malformed or byte-inconsistent canon profile",
                code=exc.code,
                extensions={"run_id": run_id, "surface": "run_workflow"},
            ) from exc
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
