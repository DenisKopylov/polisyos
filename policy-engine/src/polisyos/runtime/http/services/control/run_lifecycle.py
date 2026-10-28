"""Control Plane service — bridges HTTP layer to scientist/fabric."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import math
import uuid
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, TypeVar, cast, overload

from pydantic import BaseModel, JsonValue, TypeAdapter

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.common.logger import get_logger
from polisyos.core import artifacts, run
from polisyos.core.artifacts import (
    artifact_ref_for_manifest,
    input_ref_from_artifact_ref,
    read_core_json_artifact,
    read_core_manifest_profile,
)
from polisyos.core.artifacts.async_store import ensure_async_artifact_store
from polisyos.core.artifacts.backends.config import (
    ArtifactStoreConfig,
    build_artifact_store,
)
from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactManifest,
    ArtifactRef,
    ArtifactTenantContextInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    artifact_ref_identity_key,
)
from polisyos.core.artifacts.protocol import (
    ArtifactStore,
    CoreJSONArtifactBoundedInputManifestReceiptReader,
    CoreJSONArtifactBoundedMemberReader,
    CoreJSONArtifactProfileReader,
    CoreJSONArtifactStore,
    SignatureVerifyingArtifactStore,
)
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import (
    CanonSpec,
)
from polisyos.core.contracts import (
    CONTROL_PRE_ADMISSION_SETTLEMENT_REQUIRED_PROFILES,
    CapabilityDiscoveryRequest,
    CapabilityDiscoveryResponse,
    ControlPreAdmissionAttemptEventInfo,
    ControlPreAdmissionAttemptResponse,
    ControlPreAdmissionOwnerBinding,
    DataSnapshot,
    SearchRequest,
)
from polisyos.core.contracts.control import (
    BindingProfileInfo,
    BindingProfilesListResponse,
    CacheStatusResponse,
    ConnectorInfo,
    ConnectorsListResponse,
    ControlJobCancellationRequest,
    ControlJobResponse,
    ControlOutboxEventInfo,
    ControlOutboxEventsResponse,
    ControlWorkerLeaseInfo,
    ControlWorkersResponse,
    DataDiscoverRequest,
    DataDiscoverResponse,
    DataPreviewRequest,
    DataPreviewResponse,
    DataResolveRequest,
    DataResolveResponse,
    DataSourceBinding,
    DecisionValidityEventRequest,
    DecisionValidityEventResponse,
    DecisionValidityLifecycleSummary,
    DecisionValidityPendingReview,
    DecisionValiditySummaryResponse,
    EpochValidityBatchRequest,
    EpochValidityBatchResponse,
    ExecutionProfile,
    IndexStatsResponse,
    IngestRequest,
    IngestResponse,
    ModelProfileInfo,
    ModelProfilesListResponse,
    NaturalLanguageRunRequest,
    PolicyFlags,
    PromotionCandidatesResponse,
    PromotionDecisionRequest,
    PromotionDecisionResponse,
    RunLaunchResponse,
    SourceProfileInfo,
    SourceProfilesListResponse,
    WorkflowRunRequest,
)
from polisyos.core.contracts.decision_validity import (
    DecisionDependencyEvent,
    DecisionTriggerRecord,
    DecisionTriggerType,
    DecisionValidityStatus,
)
from polisyos.core.contracts.fabric import DataSnapshotRef
from polisyos.core.contracts.runtime import CompletedMethodHTESource
from polisyos.core.observability import get_metrics, get_tracer
from polisyos.core.security import AccessScope, clear_tenant_context
from polisyos.runtime.http.errors import RuntimeHTTPError, conflict, forbidden, unprocessable_entity
from polisyos.runtime.http.execution_policy import (
    ExecutionProfileError,
    PolicyFlagForbiddenError,
    ResolvedExecutionPolicy,
    RuntimeExecutionPolicyResolver,
    RuntimePrincipal,
)
from polisyos.runtime.http.resilience import (
    _GuardedStoreSignatureVerifier,
    build_guarded_signature_verifier,
    guard_runtime_cas,
    guard_runtime_control_store,
    run_guarded_dependency_operation,
)
from polisyos.runtime.http.services.adapters.core_run import (
    load_completed_control_job_core_run_source,
)
from polisyos.runtime.http.services.control.artifacts import (
    DIAGNOSTIC_EVENT_ARTIFACT_KIND,
    AuthorityArtifactWriteResult,
    _artifact_ref_from_summary_payload,
    _AuthorityArtifactWriteFields,
    _make_artifact_ref,
    _resolve_curated_dir,
    write_runtime_authority_artifact,
)
from polisyos.runtime.http.services.control.bounded_wait import (
    ControlProducerExecutionError,
    ControlProducerWaitTimeoutError,
    require_shared_execution_value,
    wait_for_shared_execution,
    wrap_shared_execution_exception,
)
from polisyos.runtime.http.services.control.capabilities import CapabilityManifestMixin
from polisyos.runtime.http.services.control.evaluation_safety import (
    EvaluationSafetyAdmissionVerifier,
    EvaluationSafetyAuthoritiesSource,
    EvaluationSafetyDecisionEvidence,
    EvaluationSafetyPersistenceService,
    EvaluationSafetyPromotionSourceContext,
    EvaluationSafetyPromotionSourceSlot,
    EvaluationSafetyReplayMaterial,
    _bind_evaluation_safety_authorities_source_result,
)
from polisyos.runtime.http.services.control.job_attempt_publication import (
    _EVALUATION_SAFETY_EXECUTION_CONTEXT_KEY,
    ControlJobAttemptPublicationMixin,
    _build_nl_authorization_receipt,
    _nl_request_snapshot_request_values,
    _nl_request_snapshot_schema,
    _validate_nl_request_json_values,
)
from polisyos.runtime.http.services.control.job_attempt_publication import (
    _nl_request_body_bytes as _nl_request_body_bytes,
)
from polisyos.runtime.http.services.control.job_attempt_publication import (
    _nl_request_snapshot_content_hash as _nl_request_snapshot_content_hash,
)
from polisyos.runtime.http.services.control.job_diagnostics import (
    _OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY,
    ControlJobDiagnosticsMixin,
)
from polisyos.runtime.http.services.control.job_nl_admission import (
    ControlNLJobAdmissionMixin,
)
from polisyos.runtime.http.services.control.job_nl_execution import (
    ControlNLJobExecutionMixin,
)
from polisyos.runtime.http.services.control.job_nl_publication import (
    ControlNLJobPublicationMixin,
)
from polisyos.runtime.http.services.control.job_nl_publication import (
    _n4_proposal_progress_with_budget as _n4_proposal_progress_with_budget,
)
from polisyos.runtime.http.services.control.job_scope_admission import (
    ControlJobScopeAdmissionMixin,
)
from polisyos.runtime.http.services.control.job_scope_admission import (
    _ControlJobExecutionScopeLimitation as _ControlJobExecutionScopeLimitation,
)
from polisyos.runtime.http.services.control.lex_pipeline import LexPipelineMixin
from polisyos.runtime.http.services.control.nl_pipeline import NaturalLanguageRunMixin
from polisyos.runtime.http.services.control.workspace_loop_transition import (
    ControlPlaneWorkspaceLoopTransitionMixin,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRouteLoopReceipt,
    AcquisitionRoutePhaseReceipt,
)
from polisyos.runtime.quality.authority import GovernanceMetadata
from polisyos.runtime.quality.authority_reconciliation import (
    AuthorityReconciliationError,
    AuthorityReconciliationReport,
    reconcile_authority_ref,
    resolve_authority_diagnostic_event_ref,
)
from polisyos.runtime.quality.design_axes.value_choice_provenance import (
    NormativeAuthorityTrust,
    P20NormativeChoiceError,
)
from polisyos.runtime.quality.diagnostic_events import (
    DIAGNOSTIC_EVENT_SCHEMA_NAME,
    DIAGNOSTIC_EVENT_SCHEMA_VERSION,
    DiagnosticEvent,
)
from polisyos.runtime.quality.epoch_validity_cascade import (
    persist_advisory_perturbation_event,
)
from polisyos.runtime.quality.evaluation_safety import (
    EvalSafetyAppointmentResolution,
    EvalSafetyAuthorityResolution,
    EvalSafetyAuthorityResolver,
    EvalSafetyCertificate,
    EvalSafetyVerifierAppointmentResolver,
    EvalSafetyVerifierRegistry,
    EvaluationAttemptIntake,
    EvaluationAttemptRequest,
    EvaluationExecutionContext,
    EvaluationSafetyDecisionEvent,
    evaluation_execution_context_hash,
)
from polisyos.runtime.quality.event_log import (
    DiagnosticEventPayloadPolicy,
    RuntimeDiagnosticEventLog,
)
from polisyos.runtime.quality.open_world_risk import PromotionRuntime
from polisyos.runtime.quality.source_truth import (
    SourceTruthContractError,
    detect_source_truth_conflict,
)
from polisyos.scientist import (
    ClaimLifecycleBridgeAdvanced,
    EpochClaimLifecycleBridgeService,
    build_default_claim_ledger_owner,
    build_epoch_claim_lifecycle_bridge,
)
from polisyos.scientist.governance.continuous import (
    PublicSignaturePopulationProvider,
    PublishedSignatureCustodyResult,
)
from polisyos.scientist.orchestration.engine import BudgetMiddleware
from polisyos.scientist.orchestration.engine.producer_budget import ProducerBudgetObserver
from polisyos.scientist.orchestration.llm.provider_verification import (
    ProviderPreflightReport,
    run_provider_preflight,
)
from polisyos.scientist.validation.decision_validity import DecisionValidityService

from .._control_contracts import (
    _OPTIONAL_INPUT_KEYS,
    _WORKFLOW_DATA_VIEW_REQUEST_INTENT_KEY,
    _build_api_meta,
    _coerce_optional_execution_profile,
    _coerce_retrieval_mode,
    _dedupe_models,
    _is_multimodel_enabled,
    _resolve_workflow_data_source,
)
from ..control_plane_store import (
    _COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
    AcquisitionActionHeadRecord,
    ControlJobExecutionAdmission,
    ControlJobExecutionAdmissionError,
    ControlJobExecutionScope,
    ControlJobLeaseLostError,
    ControlJobRecord,
    ControlOutboxRecord,
    ControlPlaneStore,
    ControlPreAdmissionIdempotencyConflictError,
    HumanDecisionRecoveryFence,
    HumanDecisionReservationRecord,
    HumanDecisionReservationResult,
    HumanDecisionWriteFence,
)
from ..control_plane_store import (
    _completed_hte_source_invalidation_dedupe_key as _control_hte_invalidation_dedupe_key,
)
from ..control_worker import ControlWorker

logger = get_logger(__name__)


def _same_selected_artifact_ref(left: object, right: object) -> bool:
    """Compare full selected ArtifactRef identity across typed subclasses."""
    if not isinstance(left, ArtifactRef) or not isinstance(right, ArtifactRef):
        return False
    if left.manifest_profile_sha256 is None or right.manifest_profile_sha256 is None:
        return False
    return artifact_ref_identity_key(left) == artifact_ref_identity_key(right)


def _search_binding_admission_input_edges(
    snapshot: SearchUncertaintyTaskAdmissionSnapshot | None,
) -> tuple[tuple[ArtifactRef, str], ...]:
    """Return the selected CAS closure retained by a POST Search admission."""
    if snapshot is None:
        return ()
    return (
        (snapshot.binding_ref, "search_uncertainty_task_binding"),
        (snapshot.projection_ref, "search_uncertainty_task_projection"),
        (snapshot.task_admission_ref, "search_uncertainty_task_admission"),
        (snapshot.task_epoch_ref, "search_uncertainty_task_epoch"),
        (snapshot.owner_context_ref, "search_uncertainty_owner_context"),
        (snapshot.basis_ref, "search_uncertainty_task_basis"),
        (snapshot.dependency_inventory_ref, "search_uncertainty_dependency_inventory"),
        (snapshot.source_projection_ref, "search_uncertainty_source_projection"),
    )


def _observational_run_intent_input_edges(
    intent: _ObservationalRunIntent,
) -> tuple[tuple[ArtifactRef, str], ...]:
    """Return the complete producer lineage recipe for a requested intent."""
    policy_ref = intent.resource_policy_ref
    if policy_ref is None:
        raise ValueError("observational_method_resource_policy_ref_missing")
    return (
        (intent.requested_source_ref, "requested_source"),
        (policy_ref, "resource_policy"),
        *_search_binding_admission_input_edges(intent.search_binding_admission),
    )


def _content_admitted_intent_input_edges(
    intent: _ContentAdmittedObservationalRunIntent,
) -> tuple[tuple[ArtifactRef, str], ...]:
    """Return the complete producer lineage recipe for an admitted intent."""
    edges = (
        (intent.requested_intent_ref, "observational_run_intent"),
        (intent.requested_source_ref, "requested_source"),
        (intent.resource_policy_ref, "resource_policy"),
        (intent.submitted_input_ref, "submitted_input"),
        (intent.effective_input_ref, "effective_input"),
    )
    return (*edges, *_search_binding_admission_input_edges(intent.search_binding_admission))


def _has_exact_selected_input_edges(
    inputs: tuple[InputRef, ...] | list[InputRef],
    expected_edges: tuple[tuple[ArtifactRef, str], ...],
) -> bool:
    """Match the selected ref, profile and semantic role as an exact multiset."""
    if len(inputs) != len(expected_edges):
        return False
    unmatched: list[tuple[object, str, str]] = []
    for ref, role in expected_edges:
        profile = ref.manifest_profile_sha256
        if profile is None:
            return False
        unmatched.append((ref.artifact_id, profile, role))
    for edge in inputs:
        profile = edge.manifest_profile_sha256
        if profile is None:
            return False
        edge_key = (edge.artifact_id, profile, edge.role)
        try:
            unmatched.remove(edge_key)
        except ValueError:
            return False
    return not unmatched


def _same_selected_reference_or_value(left: object, right: object) -> bool:
    """Compare Search snapshot scalars normally and CAS refs by full selected identity."""
    if isinstance(left, ArtifactRef) or isinstance(right, ArtifactRef):
        return (
            isinstance(left, ArtifactRef)
            and isinstance(right, ArtifactRef)
            and _same_selected_artifact_ref(left, right)
        )
    return left == right


def _same_optional_selected_artifact_ref(left: object, right: object) -> bool:
    """Compare optional selected refs without weakening non-null identity checks."""
    if left is None or right is None:
        return left is None and right is None
    return _same_selected_artifact_ref(left, right)


def _same_optional_selected_artifact_ref_for_kind(
    left: object,
    right: object,
    *,
    absence_is_valid_for_selected_kind: bool,
) -> bool:
    """Allow matching absence only when the typed HTE outcome permits it."""
    if left is None or right is None:
        return absence_is_valid_for_selected_kind and left is None and right is None
    return _same_selected_artifact_ref(left, right)


def _same_optional_artifact_ref_payload(
    left: ArtifactRef | None,
    right: ArtifactRef | None,
) -> bool:
    """Compare the complete persisted representation of two optional artifact refs."""
    if left is None or right is None:
        return left is None and right is None
    return left.model_dump(mode="json") == right.model_dump(mode="json")


def _typed_execution_profile(value: str) -> ExecutionProfile:
    """Narrow a runtime-resolved profile to the public response contract."""
    return TypeAdapter(ExecutionProfile).validate_python(value, strict=True)


def _pre_admission_producer_event_refs(
    settlement_store: BudgetMiddleware | None,
    producer_run_binding: BudgetLedgerProducerRunBinding | None,
) -> tuple[tuple[str, ...], Literal["not_applicable", "complete", "unavailable"]]:
    """Read exact durable event IDs for one typed run binding without copying cost claims."""
    if settlement_store is None or producer_run_binding is None:
        return (), "not_applicable"
    try:
        records = settlement_store.list_producer_events_for_run_safe(producer_run_binding)
    except Exception:
        logger.exception("Pre-admission provider event references could not be read")
        return (), "unavailable"
    event_ids = tuple(sorted({str(record.event_id) for record in records}))
    return event_ids, "complete" if event_ids else "unavailable"


def _build_control_nl_producer_budget_reconciler(
    *,
    settlement_store: BudgetMiddleware,
    producer_run_binding: BudgetLedgerProducerRunBinding,
    budget_state: BudgetState,
) -> ProducerBudgetObserver:
    """Bind the canonical current producer-budget owner for N5 and N6 consumers."""
    return ProducerBudgetObserver(
        settlement_store=settlement_store,
        producer_run_binding=producer_run_binding,
        budget_state=budget_state,
    )


# These request keys can assert owner scope; the worker supplies them from its
# replay-validated actor/job binding or omits them when that binding is unknown.


_SCIENTIST_RUNTIME_ONLY_STATE_KEYS = frozenset({"job_id", "tenant_id", "cell_id"})
_EXECUTION_INTENT_BINDING_SCHEMA = "polisyos.runtime.control_execution_intent.v2"
_NL_AUTHORIZATION_RECEIPT_KEY = "nl_authorization_receipt"
_NL_REQUEST_SNAPSHOT_KEY = "nl_request_snapshot"
_NL_REQUEST_SNAPSHOT_DIGEST_PROFILE = (
    "polisyos.runtime.authorization.nl_request_snapshot.canonical_json.v1"
)
_OBSERVATIONAL_METHOD_BASE_FQNS = frozenset(
    {
        "causal.hte.causal_forest",
        "causal.hte.double_ml",
        "causal.hte.meta_learner",
        "causal.hte.forest_dr",
    }
)
_OBSERVATIONAL_METHOD_FQN_V1_0 = "causal.hte.forest_dr@1.0.0"
_OBSERVATIONAL_METHOD_FQN_V1_1 = "causal.hte.forest_dr@1.1.0"
_OBSERVATIONAL_METHOD_FQN_V2 = frozenset(
    {
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.double_ml@2.0.0",
        "causal.hte.meta_learner@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    }
)
_OBSERVATIONAL_METHOD_V2_RESOURCE_PROFILE = {
    "causal.hte.causal_forest@2.0.0": (
        "econml.causal_forest_dml.native_mean@2.0",
        "producer_scoped_joblib_parallelism_one",
        1,
    ),
    "causal.hte.double_ml@2.0.0": (
        "econml.dml.point_only@2.0",
        "producer_scoped_joblib_parallelism_one",
        None,
    ),
    "causal.hte.meta_learner@2.0.0": (
        "econml.meta_learner.point_only@2.0",
        "producer_scoped_joblib_parallelism_one",
        None,
    ),
    "causal.hte.forest_dr@2.0.0": (
        "econml.forest_dr.native_mean@2.0",
        "producer_scoped_joblib_parallelism_one",
        1,
    ),
}
_OBSERVATIONAL_METHOD_CONTRACT_TARGET_ID = "foundry.causal.hte_observational_data.v1"
_OBSERVATIONAL_METHOD_CONTRACT_TARGET = (
    "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
)
_OBSERVATIONAL_SOURCE_ACCESS_STATUS = "not_established"
_OBSERVATIONAL_METHOD_N_JOBS_PARAMETER = "n_jobs"
_GRAPH_METHOD_EXECUTION_BUNDLE_ROLE = "method_execution_bundle"
_GRAPH_METHOD_BINDING_SET_ROLE = "method_metric_binding_set"
_MAX_GRAPH_PRODUCER_EMISSIONS = 16
_MAX_GRAPH_ROLE_REFS_PER_EMISSION = 8
_MAX_GRAPH_DERIVED_REF_SCAN = 256
_GRAPH_PRODUCER_RECEIPT_SEAL = object()
_RUN_LIFECYCLE_OWNER_SCOPE_UNSET = object()
_BoundedArtifactModelT = TypeVar("_BoundedArtifactModelT", bound=BaseModel)


def _read_observational_resource_policy_artifact(
    *,
    store: CoreJSONArtifactBoundedMemberReader,
    policy_ref: ArtifactRef,
    source_ref: ArtifactRef,
    source_governance: ArtifactGovernanceInfo,
    source_tenant_context: ArtifactTenantContextInfo | None,
    limits: CoreJsonReadLimits,
) -> _ObservationalInputResourcePolicy:
    """Resolve the exact Runtime policy artifact and its selected source lineage."""
    from polisyos.core.artifacts import (
        read_core_json_artifact_bounded,
        validate_core_model_bounded_read,
    )
    from polisyos.core.contracts.runtime import ObservationalInputResourcePolicy
    from polisyos.runtime.http.services.control.owned_attempt_anchor import (
        _require_full_profile_ref,
    )

    policy_ref = _require_full_profile_ref(
        policy_ref,
        code="observational_resource_policy_manifest_binding_mismatch",
    )
    source_ref = _require_full_profile_ref(
        source_ref,
        code="observational_resource_policy_manifest_binding_mismatch",
    )
    bounded = read_core_json_artifact_bounded(store, policy_ref, limits=limits)
    manifest = bounded.manifest
    policy_governance, policy_tenant_context, _ = _explicit_source_manifest_metadata(
        raw_manifest_bytes=bounded.raw_manifest_bytes,
        typed_governance=manifest.governance,
        tenant_context=manifest.tenant_context,
    )
    if (
        not _same_selected_artifact_ref(bounded.effective_ref, policy_ref)
        or policy_ref.kind != "runtime.observational_input_resource_policy"
        or policy_ref.media_type != "application/json"
        or policy_ref.manifest_profile_sha256 is None
        or manifest.kind != "runtime.observational_input_resource_policy"
        or manifest.media_type != "application/json"
        or manifest.artifact_schema
        != SchemaInfo(name="polisyos.runtime.ObservationalInputResourcePolicy", version="1.0")
        or policy_governance != source_governance
        or policy_tenant_context != source_tenant_context
        or len(manifest.inputs) != 1
        or manifest.inputs[0].artifact_id != source_ref.artifact_id
        or manifest.inputs[0].manifest_profile_sha256 != source_ref.manifest_profile_sha256
    ):
        raise ValueError("observational_resource_policy_manifest_binding_mismatch")
    policy = validate_core_model_bounded_read(ObservationalInputResourcePolicy, bounded)
    if type(policy) is not ObservationalInputResourcePolicy:
        raise ValueError("observational_resource_policy_payload_invalid")
    return policy


def _validate_direct_method_execution_selection_artifacts(
    *,
    store: CoreJSONArtifactBoundedMemberReader,
    selection: _DirectMethodExecutionSelection,
    limits: CoreJsonReadLimits,
) -> None:
    """Bind persisted direct-method refs to exact producer manifests and lineage edges."""
    from polisyos.core.artifacts import (
        read_core_json_artifact_bounded,
        read_core_manifest_profile_bounded,
        validate_core_model_bounded_read,
    )
    from polisyos.core.contracts.runtime import (
        ContentAdmittedObservationalRunIntent,
        MethodExecutionCandidateOutcome,
        ObservationalRunIntent,
        _expected_content_admitted_limitations,
        _observational_intent_manifest_identity,
    )
    from polisyos.runtime.http.services.control.owned_attempt_anchor import (
        _require_full_profile_ref,
    )

    def read_manifest(
        ref: ArtifactRef,
        *,
        kind: str,
        schema: SchemaInfo | None,
    ) -> CoreJsonManifestBoundedRead:
        ref = _require_full_profile_ref(
            ref,
            code="direct_method_execution_manifest_profile_required",
        )
        bounded = read_core_manifest_profile_bounded(
            store,
            ref,
            max_manifest_bytes=limits.max_manifest_bytes,
        )
        manifest = bounded.manifest
        if (
            not _same_selected_artifact_ref(bounded.effective_ref, ref)
            or manifest.kind != kind
            or manifest.media_type != "application/json"
            or manifest.artifact_schema != schema
        ):
            raise ValueError("direct_method_execution_manifest_contract_mismatch")
        return bounded

    def read_intent(
        ref: ArtifactRef,
        *,
        model: type[_BoundedArtifactModelT],
        kind: str,
        schema_name: str,
    ) -> _BoundedArtifactModelT:
        ref = _require_full_profile_ref(
            ref,
            code="direct_method_execution_intent_profile_required",
        )
        bounded = read_core_json_artifact_bounded(store, ref, limits=limits)
        manifest = bounded.manifest
        payload = bounded.value
        if not isinstance(payload, Mapping):
            raise ValueError("direct_method_execution_intent_payload_invalid")
        payload_version = payload.get("schema_version")
        if type(payload_version) is not str:
            raise ValueError("direct_method_execution_intent_schema_version_invalid")
        try:
            expected_kind, expected_name, expected_version = (
                _observational_intent_manifest_identity(payload_version)
            )
        except ValueError:
            expected_kind = expected_name = expected_version = None
        if (
            not _same_selected_artifact_ref(bounded.effective_ref, ref)
            or manifest.kind != kind
            or manifest.kind != expected_kind
            or manifest.media_type != "application/json"
            or expected_name != schema_name
            or expected_version is None
            or manifest.artifact_schema != SchemaInfo(name=schema_name, version=expected_version)
        ):
            raise ValueError("direct_method_execution_intent_manifest_mismatch")
        return validate_core_model_bounded_read(model, bounded)

    requested_intent = cast(
        "ObservationalRunIntent",
        read_intent(
            selection.observational_run_intent_ref,
            model=ObservationalRunIntent,
            kind="runtime.observational_run_intent",
            schema_name="polisyos.runtime.ObservationalRunIntent",
        ),
    )
    admitted_intent = cast(
        "ContentAdmittedObservationalRunIntent",
        read_intent(
            selection.content_admitted_intent_ref,
            model=ContentAdmittedObservationalRunIntent,
            kind="runtime.content_admitted_observational_run_intent",
            schema_name="polisyos.runtime.ContentAdmittedObservationalRunIntent",
        ),
    )
    if (
        requested_intent.job_id != selection.job_id
        or requested_intent.run_id != selection.run_id
        or requested_intent.requested_source_ref != selection.requested_source_ref
        or requested_intent.protocol != selection.source_protocol
        or requested_intent.method_fqn != selection.method_fqn
        or requested_intent.method_version != selection.method_version
        or requested_intent.method_abi_digest != selection.method_abi_digest
        or requested_intent.method_build_digest != selection.method_build_digest
        or requested_intent.method_build_digest_scope != selection.method_build_digest_scope
        or requested_intent.resource_policy_ref != selection.resource_policy_ref
        or admitted_intent.resource_policy_ref != selection.resource_policy_ref
        or requested_intent.resource_policy_digest != selection.resource_policy_digest
        or selection.selection_digest is None
        or requested_intent.selection_digest() != selection.selection_digest
        or admitted_intent.selection_digest != selection.selection_digest
        or requested_intent.source_access_revalidation_status
        != selection.source_access_revalidation_status
        or admitted_intent.source_access_revalidation_status
        != selection.source_access_revalidation_status
        or selection.source_access_revalidation_status != _OBSERVATIONAL_SOURCE_ACCESS_STATUS
        or admitted_intent.job_id != selection.job_id
        or admitted_intent.run_id != selection.run_id
        or admitted_intent.attempt != selection.attempt
        or admitted_intent.requested_intent_ref != selection.observational_run_intent_ref
        or admitted_intent.requested_source_ref != selection.requested_source_ref
        or admitted_intent.submitted_input_ref != selection.submitted_input_ref
        or admitted_intent.effective_input_ref != selection.effective_input_ref
        or admitted_intent.contract_target_id != selection.contract_target_id
        or admitted_intent.contract_target_id != _OBSERVATIONAL_METHOD_CONTRACT_TARGET_ID
        or admitted_intent.contract_target != selection.contract_target
        or admitted_intent.method_fqn != selection.method_fqn
        or requested_intent.owned_hte_request_context != selection.owned_hte_request_context
        or admitted_intent.owned_hte_request_context != selection.owned_hte_request_context
        or (
            requested_intent.schema_version == "polisyos.runtime.observational_run_intent.v3"
            and (
                admitted_intent.schema_version
                != "polisyos.runtime.content_admitted_observational_run_intent.v3"
                or admitted_intent.search_binding_admission
                != requested_intent.search_binding_admission
            )
        )
        or admitted_intent.source_protocol != selection.source_protocol
        or admitted_intent.normalization != selection.normalization
        or admitted_intent.limitations != selection.limitations
        or admitted_intent.resource_policy_digest != selection.resource_policy_digest
        or requested_intent.contract_target_id != selection.contract_target_id
        or requested_intent.contract_target_fqn != selection.contract_target
        or admitted_intent.source_manifest_sha256 != requested_intent.source_manifest_sha256
        or admitted_intent.limitations
        != _expected_content_admitted_limitations(
            selection.source_protocol,
            source_access_revalidation_status=selection.source_access_revalidation_status,
        )
        or admitted_intent.observed_manifest_bytes
        != admitted_intent.observed_manifest_selection_bytes
        or admitted_intent.observed_manifest_selection_bytes
        > requested_intent.resource_policy.max_manifest_bytes
        or admitted_intent.observed_manifest_verification_bytes
        > requested_intent.resource_policy.max_manifest_bytes
        or admitted_intent.observed_payload_bytes > requested_intent.resource_policy.max_bytes
        or admitted_intent.observed_depth > requested_intent.resource_policy.max_depth
        or admitted_intent.observed_elements > requested_intent.resource_policy.max_elements
        or admitted_intent.observed_source_bytes
        > (
            2 * requested_intent.resource_policy.max_manifest_bytes
            + requested_intent.resource_policy.max_bytes
        )
    ):
        raise ValueError("direct_method_execution_intent_lineage_mismatch")

    input_policy = requested_intent.resource_policy
    if (
        admitted_intent.observed_manifest_selection_bytes > input_policy.max_manifest_bytes
        or admitted_intent.observed_manifest_verification_bytes > input_policy.max_manifest_bytes
        or admitted_intent.observed_payload_bytes > input_policy.max_bytes
        or admitted_intent.observed_depth > input_policy.max_depth
        or admitted_intent.observed_elements > input_policy.max_elements
        or admitted_intent.observed_source_bytes
        > (2 * input_policy.max_manifest_bytes + input_policy.max_bytes)
    ):
        raise ValueError("direct_method_execution_read_usage_exceeds_requested_policy")

    expected_source_schema = (
        SchemaInfo(name="polisyos.ir.ObservationMethodInputEnvelope", version="1.0")
        if selection.source_protocol == "method_input_envelope_v1"
        else None
    )
    source_read = read_manifest(
        selection.requested_source_ref,
        kind=selection.requested_source_ref.kind,
        schema=expected_source_schema,
    )
    source_manifest = source_read.manifest
    source_governance, source_tenant_context, source_manifest_sha256 = (
        _explicit_source_manifest_metadata(
            raw_manifest_bytes=source_read.raw_manifest_bytes,
            typed_governance=source_manifest.governance,
            tenant_context=source_manifest.tenant_context,
            expected_sha256=requested_intent.source_manifest_sha256,
        )
    )
    expected_source_kind = (
        "ir.observation_method_input"
        if selection.source_protocol == "method_input_envelope_v1"
        else "ir.observational_data"
    )
    _require_public_candidate_source(source_governance, source_tenant_context)
    requested_intent_manifest = read_manifest(
        selection.observational_run_intent_ref,
        kind="runtime.observational_run_intent",
        schema=SchemaInfo(
            name="polisyos.runtime.ObservationalRunIntent",
            version=_observational_intent_manifest_identity(requested_intent.schema_version)[2],
        ),
    ).manifest
    admitted_intent_manifest = read_manifest(
        selection.content_admitted_intent_ref,
        kind="runtime.content_admitted_observational_run_intent",
        schema=SchemaInfo(
            name="polisyos.runtime.ContentAdmittedObservationalRunIntent",
            version=_observational_intent_manifest_identity(admitted_intent.schema_version)[2],
        ),
    ).manifest

    if (
        source_manifest.kind != expected_source_kind
        or requested_intent.source_manifest_sha256 != source_manifest_sha256
        or requested_intent.source_governance != source_governance
        or requested_intent.source_tenant_context != source_tenant_context
        or admitted_intent.source_governance != source_governance
        or admitted_intent.source_tenant_context != source_tenant_context
        or requested_intent.source_access_revalidation_status != _OBSERVATIONAL_SOURCE_ACCESS_STATUS
        or not _has_exact_selected_input_edges(
            tuple(requested_intent_manifest.inputs),
            _observational_run_intent_input_edges(requested_intent),
        )
        or not _has_exact_selected_input_edges(
            tuple(admitted_intent_manifest.inputs),
            _content_admitted_intent_input_edges(admitted_intent),
        )
    ):
        raise ValueError("direct_method_execution_source_manifest_lineage_mismatch")

    selected_policy = _read_observational_resource_policy_artifact(
        store=store,
        policy_ref=selection.resource_policy_ref,
        source_ref=selection.requested_source_ref,
        source_governance=source_governance,
        source_tenant_context=source_tenant_context,
        limits=limits,
    )
    if (
        selected_policy != requested_intent.resource_policy
        or selected_policy.digest() != selection.resource_policy_digest
        or admitted_intent.resource_policy_digest != selection.resource_policy_digest
    ):
        raise ValueError("direct_method_execution_resource_policy_lineage_mismatch")

    effective_read = read_manifest(
        selection.effective_input_ref,
        kind="ir.observation_method_input",
        schema=SchemaInfo(name="polisyos.ir.ObservationMethodInputEnvelope", version="1.0"),
    )
    effective_governance, effective_tenant_context, _ = _explicit_source_manifest_metadata(
        raw_manifest_bytes=effective_read.raw_manifest_bytes,
        typed_governance=effective_read.manifest.governance,
        tenant_context=effective_read.manifest.tenant_context,
    )
    if (
        effective_governance != source_governance
        or effective_tenant_context != source_tenant_context
    ):
        raise ValueError("direct_method_execution_effective_input_metadata_mismatch")
    if selection.source_protocol == "method_input_envelope_v1":
        if selection.effective_input_ref != selection.submitted_input_ref:
            raise ValueError("direct_method_execution_effective_input_passthrough_mismatch")
    else:
        effective_source_edges = [
            edge
            for edge in effective_read.manifest.inputs
            if edge.role == "legacy_hte_json_v1_source"
        ]
        if (
            len(effective_read.manifest.inputs) != 1
            or len(effective_source_edges) != 1
            or effective_source_edges[0].artifact_id != selection.submitted_input_ref.artifact_id
            or effective_source_edges[0].manifest_profile_sha256
            != selection.submitted_input_ref.manifest_profile_sha256
        ):
            raise ValueError("direct_method_execution_effective_input_lineage_mismatch")
    result_read = read_manifest(
        selection.method_result_ref,
        kind="scientist.method_result.causal.hte",
        schema=SchemaInfo(name="polisyos.scientist.MethodResult", version="0.1.0"),
    )
    evidence_manifest_read = read_manifest(
        selection.method_evidence_ref,
        kind="scientist.method_evidence",
        schema=SchemaInfo(
            name="polisyos.scientist.MethodExecutionEvidence",
            version="0.1.0",
        ),
    )
    for output_read in (result_read, evidence_manifest_read):
        output_governance, output_tenant_context, _ = _explicit_source_manifest_metadata(
            raw_manifest_bytes=output_read.raw_manifest_bytes,
            typed_governance=output_read.manifest.governance,
            tenant_context=output_read.manifest.tenant_context,
        )
        if output_governance != source_governance or output_tenant_context != source_tenant_context:
            raise ValueError("direct_method_execution_output_metadata_mismatch")

    if selection.hte is not None:
        hte_manifest_specs = [
            (selection.hte_outcome_ref, "ir.hte_outcome", "polisyos.ir.HTEOutcome", "1.0")
        ]
        if selection.hte.kind == "point_estimate":
            hte_manifest_specs.append(
                (
                    selection.point_result_ref,
                    "ir.hte_point_result",
                    "polisyos.ir.HTEPointResult",
                    "1.0",
                )
            )
        if selection.hte.kind == "interval_estimate":
            hte_manifest_specs.extend(
                (
                    (
                        selection.hte_result_ref,
                        "ir.hte_result",
                        "ir.hte_result",
                        "1.0",
                    ),
                    (
                        selection.inference_basis_ref,
                        "ir.ate_inference_basis",
                        "polisyos.ir.ATEInferenceBasis",
                        "1.0",
                    ),
                )
            )
        if selection.inference_basis_ref is not None and selection.hte.kind == "point_estimate":
            hte_manifest_specs.append(
                (
                    selection.inference_basis_ref,
                    "ir.ate_inference_basis",
                    "polisyos.ir.ATEInferenceBasis",
                    "1.0",
                )
            )
        if selection.hte.kind == "refusal":
            hte_manifest_specs.append(
                (
                    selection.refusal_diagnostic_ref,
                    "ir.hte_refusal_diagnostic",
                    "polisyos.ir.HTERefusalDiagnostic",
                    "1.0",
                )
            )
        for ref, kind, schema_name, schema_version in hte_manifest_specs:
            if ref is None:
                raise ValueError("direct_method_execution_hte_manifest_ref_missing")
            read_manifest(
                ref,
                kind=kind,
                schema=SchemaInfo(name=schema_name, version=schema_version),
            )
    result_manifest = result_read.manifest
    evidence_manifest = evidence_manifest_read.manifest

    evidence_ref = _require_full_profile_ref(
        selection.method_evidence_ref,
        code="direct_method_execution_evidence_profile_required",
    )
    evidence_read = read_core_json_artifact_bounded(
        store,
        evidence_ref,
        limits=limits,
    )
    evidence_payload = evidence_read.value
    if not isinstance(evidence_payload, Mapping):
        raise ValueError("direct_method_execution_evidence_content_invalid")
    evidence_candidate_outcome = evidence_payload.get("candidate_outcome")
    if selection.candidate_outcome is None:
        if evidence_candidate_outcome is not None:
            raise ValueError("direct_method_execution_candidate_outcome_unbound")
    else:
        try:
            checked_candidate_outcome = MethodExecutionCandidateOutcome.model_validate(
                evidence_candidate_outcome
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("direct_method_execution_candidate_outcome_invalid") from exc
        if checked_candidate_outcome != selection.candidate_outcome:
            raise ValueError("direct_method_execution_candidate_outcome_mismatch")
    try:
        evidence_result_ref = ArtifactRef.model_validate(evidence_payload.get("method_result_ref"))
    except (TypeError, ValueError) as exc:
        raise ValueError("direct_method_execution_evidence_content_invalid") from exc
    owned_attempt_anchor_ref = selection.owned_attempt_anchor_ref
    if selection.method_fqn in _OBSERVATIONAL_METHOD_FQN_V2:
        if owned_attempt_anchor_ref is None:
            raise ValueError("direct_method_execution_owned_anchor_missing")
        selected_owned_attempt_anchor_ref = owned_attempt_anchor_ref
    else:
        selected_owned_attempt_anchor_ref = None
    effective_input_ref = selection.effective_input_ref
    if effective_input_ref is None:
        raise ValueError("direct_method_execution_effective_input_missing")
    expected_producer_limitations = _expected_content_admitted_limitations(
        selection.source_protocol,
        source_access_revalidation_status=None,
    )

    if (
        evidence_payload.get("authority_purpose") != "method_execution"
        or evidence_payload.get("method_fqn") != selection.method_fqn
        or evidence_payload.get("method_version") != selection.method_version
        or evidence_payload.get("method_abi_digest") != selection.method_abi_digest
        or evidence_payload.get("method_build_digest") != selection.method_build_digest
        or evidence_payload.get("resource_policy_digest") != selection.resource_policy_digest
        or evidence_payload.get("resource_policy_ref")
        != selection.resource_policy_ref.model_dump(mode="json")
        or evidence_payload.get("source_protocol") != selection.source_protocol
        or evidence_payload.get("normalization") != selection.normalization
        or evidence_payload.get("limitations") != list(expected_producer_limitations)
        or evidence_payload.get("requested_source_ref")
        != selection.requested_source_ref.model_dump(mode="json")
        or evidence_payload.get("observational_run_intent_ref")
        != selection.observational_run_intent_ref.model_dump(mode="json")
        or evidence_payload.get("content_admitted_intent_ref")
        != selection.content_admitted_intent_ref.model_dump(mode="json")
        or evidence_payload.get("submitted_input_ref")
        != selection.submitted_input_ref.model_dump(mode="json")
        or evidence_payload.get("effective_input_ref")
        != effective_input_ref.model_dump(mode="json")
        or evidence_payload.get("method_result_ref")
        != selection.method_result_ref.model_dump(mode="json")
        or evidence_result_ref != selection.method_result_ref
        or (
            selected_owned_attempt_anchor_ref is not None
            and evidence_payload.get("owned_attempt_anchor_ref")
            != selected_owned_attempt_anchor_ref.model_dump(mode="json")
        )
        or (
            selection.method_fqn in _OBSERVATIONAL_METHOD_FQN_V2
            and selection.hte is not None
            and evidence_payload.get("materialization_binding_ref")
            != (
                selection.hte.materialization_binding_ref.model_dump(mode="json")
                if selection.hte.materialization_binding_ref is not None
                else None
            )
        )
        or (
            selection.method_fqn not in _OBSERVATIONAL_METHOD_FQN_V2
            and (
                "owned_attempt_anchor_ref" in evidence_payload
                or "materialization_binding_ref" in evidence_payload
            )
        )
    ):
        raise ValueError("direct_method_execution_evidence_content_mismatch")

    expected_lineage = (
        ("requested_source", selection.requested_source_ref),
        ("observational_run_intent", selection.observational_run_intent_ref),
        ("content_admitted_intent", selection.content_admitted_intent_ref),
        ("submitted_method_input", selection.submitted_input_ref),
        ("effective_method_input", selection.effective_input_ref),
        ("method_resource_policy", selection.resource_policy_ref),
    )
    if selection.method_fqn in _OBSERVATIONAL_METHOD_FQN_V2:
        if selection.owned_attempt_anchor_ref is None or selection.hte is None:
            raise ValueError("direct_method_execution_owned_anchor_missing")
        if selection.hte.materialization_binding_ref is not None:
            expected_lineage += (
                (
                    "physical_source_materialization_binding",
                    selection.hte.materialization_binding_ref,
                ),
            )
        expected_lineage += (("owned_attempt_anchor", selection.owned_attempt_anchor_ref),)

    def has_exact_inputs(
        inputs: tuple[object, ...] | list[object],
        expected: tuple[tuple[str, ArtifactRef], ...],
    ) -> bool:
        if len(inputs) != len(expected):
            return False
        remaining = list(expected)
        for edge in inputs:
            edge_role = getattr(edge, "role", None)
            edge_id = getattr(edge, "artifact_id", None)
            edge_profile = getattr(edge, "manifest_profile_sha256", None)
            match = next(
                (
                    index
                    for index, (role, ref) in enumerate(remaining)
                    if edge_role == role
                    and edge_id == ref.artifact_id
                    and edge_profile == ref.manifest_profile_sha256
                ),
                None,
            )
            if match is None:
                return False
            remaining.pop(match)
        return not remaining

    evidence_lineage = (("method_result", selection.method_result_ref), *expected_lineage)
    if not has_exact_inputs(
        tuple(result_manifest.inputs), expected_lineage
    ) or not has_exact_inputs(tuple(evidence_manifest.inputs), evidence_lineage):
        raise ValueError("direct_method_execution_output_lineage_mismatch")


def _reject_duplicate_json_object_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Decode one raw metadata object without ambiguous duplicate keys."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("observational_manifest_duplicate_member")
        result[key] = value
    return result


def _require_public_candidate_source(
    governance: ArtifactGovernanceInfo,
    tenant_context: ArtifactTenantContextInfo | None,
) -> None:
    """Allow candidate execution only for an unscoped public source.

    Runtime currently has no owner-issued source-read authorization receipt for
    asynchronous method work. This bounded case carries that absence explicitly;
    tenant or non-public inputs fail closed instead of treating CAS ownership as
    authorization.
    """
    if governance.classification != "public" or tenant_context is not None:
        raise ValueError("observational_source_current_access_not_established")


def _explicit_source_manifest_metadata(
    *,
    raw_manifest_bytes: bytes,
    typed_governance: ArtifactGovernanceInfo | None,
    tenant_context: ArtifactTenantContextInfo | None,
    expected_sha256: str | None = None,
) -> tuple[ArtifactGovernanceInfo, ArtifactTenantContextInfo | None, str]:
    """Bind raw explicit classification, selected typed metadata, and its digest."""
    if type(raw_manifest_bytes) is not bytes:
        raise ValueError("observational_source_manifest_raw_invalid")
    try:
        raw_manifest = json.loads(
            raw_manifest_bytes.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_object_members,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError("observational_source_manifest_raw_invalid") from exc
    raw_governance = raw_manifest.get("governance") if isinstance(raw_manifest, Mapping) else None
    raw_classification = (
        raw_governance.get("classification") if isinstance(raw_governance, Mapping) else None
    )
    if (
        not isinstance(typed_governance, ArtifactGovernanceInfo)
        or type(raw_classification) is not str
        or not raw_classification.strip()
        or raw_classification != typed_governance.classification
    ):
        raise ValueError("observational_source_governance_not_explicit")
    if tenant_context is not None and not isinstance(tenant_context, ArtifactTenantContextInfo):
        raise ValueError("observational_source_tenant_context_invalid")
    manifest_sha256 = hashlib.sha256(raw_manifest_bytes).hexdigest()
    if expected_sha256 is not None and manifest_sha256 != expected_sha256:
        raise ValueError("observational_source_manifest_pin_drift")
    return typed_governance, tenant_context, manifest_sha256


@dataclass(frozen=True, slots=True)
class _RuntimeGraphProducerEmission:
    """Bounded refs-only facts from one actual Foundry ExecuteResult."""

    emission_index: int
    execute_result_status: Literal["ok", "failed", "not_established"]
    output_ref_status: Literal["complete", "partial", "none"]
    simulation_result_ref: ArtifactRef | None
    method_execution_bundle_refs: tuple[ArtifactRef, ...]
    method_metric_binding_set_refs: tuple[ArtifactRef, ...]


@dataclass(frozen=True, slots=True)
class _RuntimeGraphProducerReceipt:
    """Private ref-only evidence captured at the actual Foundry execute boundary."""

    job_id: str
    run_id: str
    attempt: int
    lease_owner: str
    emissions: tuple[tuple[ArtifactRef, ArtifactRef, ArtifactRef], ...]
    diagnostics: tuple[_RuntimeGraphProducerEmission, ...]
    inventory_truncated: bool
    seal: object

    def is_runtime_minted(self) -> bool:
        """Return whether this receipt was minted by the scoped server wrapper."""
        return self.seal is _GRAPH_PRODUCER_RECEIPT_SEAL

    def diagnostic_model(self) -> MethodExecutionProducerDiagnostic:
        """Build a strict candidate-only projection of the bounded output inventory."""
        from polisyos.core.contracts.runtime import (
            MethodExecutionProducerDiagnostic,
            MethodExecutionProducerEmissionDiagnostic,
        )

        return MethodExecutionProducerDiagnostic(
            job_id=self.job_id,
            run_id=self.run_id,
            attempt=self.attempt,
            emissions=tuple(
                MethodExecutionProducerEmissionDiagnostic(
                    emission_index=item.emission_index,
                    execute_result_status=item.execute_result_status,
                    output_ref_status=item.output_ref_status,
                    simulation_result_ref=item.simulation_result_ref,
                    method_execution_bundle_refs=item.method_execution_bundle_refs,
                    method_metric_binding_set_refs=item.method_metric_binding_set_refs,
                )
                for item in self.diagnostics
            ),
            inventory_truncated=self.inventory_truncated,
        )


@dataclass(frozen=True, slots=True)
class _ScientistGraphOutputRefs:
    """Retain only selected graph refs after the Scientist state is released."""

    simulation_result_ref: ArtifactRef | None
    method_execution_bundle_ref: ArtifactRef | None
    method_metric_binding_set_ref: ArtifactRef | None


@dataclass(frozen=True, slots=True)
class _LegacyScientistWorkflowRun:
    """Internal output from one selected Scientist invocation and Foundry capture."""

    graph_output_refs: _ScientistGraphOutputRefs
    source_experiment_state_ref: ArtifactRef | None
    graph_producer_receipt: _RuntimeGraphProducerReceipt | None


@dataclass(frozen=True, slots=True)
class CompletedMethodMetricSource:
    """Owner-resolved graph source for a later candidate evaluation request.

    The request candidate is compared against the source candidate captured by the
    sealed AD01 admission. The Core state ref is retained as run provenance; it is
    not interpreted as scientific evidence.
    """

    source_run_id: str
    source_candidate_ref: ArtifactRef
    source_experiment_state_ref: ArtifactRef
    selection: _GraphMethodExecutionSelection


class _CurrentMethodMetricProjectionReadResult(Protocol):
    """Small read-only result from the bounded current AD01 projection reader."""

    @property
    def status(self) -> Literal["selected", "verification_missing", "invalid"]: ...

    @property
    def vector_ref(self) -> object | None: ...

    @property
    def observations(self) -> tuple[object, ...]: ...

    @property
    def limitations(self) -> tuple[str, ...]: ...


class _MethodParameterSpecProtocol(Protocol):
    """One already-registered method parameter contract."""

    name: str
    default: object
    bounds: tuple[int | float | None, int | float | None]


class _MethodSignatureProtocol(Protocol):
    """The small exact registration view needed by Runtime admission."""

    fqn: str
    version: str
    parameters: tuple[_MethodParameterSpecProtocol, ...]

    def abi_digest(self) -> str: ...


@dataclass(frozen=True, slots=True)
class _RuntimeObservationalMethodRegistration:
    """One startup-pinned registration and its bounded input-family profile."""

    method_class: type[Any]
    signature: _MethodSignatureProtocol
    build_digest: str
    contract_target: str
    n_jobs_parameter: str | None
    method_profile_id: str | None = None
    execution_scope: str | None = None


class _MethodMetricSourceTupleProtocol(Protocol):
    """The fixed selected graph refs admitted by the AD01 worker."""

    job_id: str
    run_id: str
    attempt: int
    method_result_ref: ArtifactRef | None
    simulation_result_ref: ArtifactRef
    method_execution_bundle_ref: ArtifactRef
    method_metric_binding_set_ref: ArtifactRef


class _RuntimeMethodMetricProjectionArtifactStore(
    CoreJSONArtifactStore,
    CoreJSONArtifactBoundedInputManifestReceiptReader,
    CoreJSONArtifactBoundedMemberReader,
    Protocol,
):
    """Runtime-checkable composite surface required for AD01 metric projection."""


class _VerifiedMethodMetricProjectionAdmissionProtocol(Protocol):
    """The sealed AD01 receipt fields that Runtime must reconcile before commit."""

    source_tuple: _MethodMetricSourceTupleProtocol
    source_candidate_ref: ArtifactRef
    vector_ref: ArtifactRef
    verifier_revision: str
    verifier_implementation_sha256: str


class _RuntimeOriginCapturingFoundryPort:
    """Delegate Foundry calls while retaining a bounded receipt of actual graph outputs."""

    def __init__(
        self,
        *,
        delegate: _FoundryPortProtocol,
        job_id: str,
        run_id: str,
        attempt: int,
        lease_owner: str,
    ) -> None:
        if not job_id or not run_id or type(attempt) is not int or attempt < 1 or not lease_owner:
            raise ValueError("runtime_graph_producer_scope_not_established")
        self._delegate = delegate
        self._job_id = job_id
        self._run_id = run_id
        self._attempt = attempt
        self._lease_owner = lease_owner
        self._emissions: list[tuple[ArtifactRef, ArtifactRef, ArtifactRef]] = []
        self._diagnostics: list[_RuntimeGraphProducerEmission] = []
        self._inventory_truncated = False

    def compile(self, store: ArtifactStore, request: CompileRequest) -> CompileResult:
        """Forward compilation to the server-selected Foundry port."""
        return self._delegate.compile(store, request)

    def execute(self, store: ArtifactStore, request: ExecuteRequest) -> ExecuteResult:
        """Capture actual ExecuteResult refs without retaining payloads or arrays."""
        result = self._delegate.execute(store, request)
        self._capture_execute_result(result)
        return result

    def producer_receipt(self) -> _RuntimeGraphProducerReceipt | None:
        """Freeze the bounded collector after the scoped Scientist invocation."""
        return _RuntimeGraphProducerReceipt(
            job_id=self._job_id,
            run_id=self._run_id,
            attempt=self._attempt,
            lease_owner=self._lease_owner,
            emissions=tuple(self._emissions),
            diagnostics=tuple(self._diagnostics),
            inventory_truncated=self._inventory_truncated,
            seal=_GRAPH_PRODUCER_RECEIPT_SEAL,
        )

    def _capture_execute_result(self, result: object) -> None:
        simulation_observed = getattr(result, "simulation_result_ref", None)
        derived_refs = getattr(result, "derived_refs", None)
        if not isinstance(derived_refs, (list, tuple)):
            derived_refs = ()
        bundle_refs: list[ArtifactRef] = []
        binding_refs: list[ArtifactRef] = []
        bundle_observed = False
        binding_observed = False
        invalid_output_ref = False
        derived_scan_truncated = False
        for index, item in enumerate(derived_refs):
            if index >= _MAX_GRAPH_DERIVED_REF_SCAN:
                derived_scan_truncated = True
                break
            role = getattr(item, "role", None)
            if role not in {
                _GRAPH_METHOD_EXECUTION_BUNDLE_ROLE,
                _GRAPH_METHOD_BINDING_SET_ROLE,
            }:
                continue
            target = bundle_refs if role == _GRAPH_METHOD_EXECUTION_BUNDLE_ROLE else binding_refs
            if role == _GRAPH_METHOD_EXECUTION_BUNDLE_ROLE:
                bundle_observed = True
                expected_kind = "foundry.method_execution_bundle"
            else:
                binding_observed = True
                expected_kind = "foundry.method_metric_binding_set"
            ref = getattr(item, "ref", None)
            if (
                not isinstance(ref, ArtifactRef)
                or ref.kind != expected_kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
            ):
                invalid_output_ref = True
                continue
            if len(target) >= _MAX_GRAPH_ROLE_REFS_PER_EMISSION:
                derived_scan_truncated = True
                continue
            target.append(ref)

        simulation_ref: ArtifactRef | None = None
        if simulation_observed is not None:
            if (
                isinstance(simulation_observed, ArtifactRef)
                and simulation_observed.kind == "foundry.simulation_result"
                and simulation_observed.media_type == "application/json"
                and simulation_observed.manifest_profile_sha256 is not None
            ):
                simulation_ref = simulation_observed
            else:
                invalid_output_ref = True

        if not (simulation_observed is not None or bundle_observed or binding_observed):
            if derived_scan_truncated:
                self._inventory_truncated = True
            return

        if len(self._diagnostics) >= _MAX_GRAPH_PRODUCER_EMISSIONS:
            self._inventory_truncated = True
            return

        direct_bundle_ref = getattr(result, "method_execution_bundle_ref", None)
        direct_bundle_mismatch = direct_bundle_ref is not None and (
            not isinstance(direct_bundle_ref, ArtifactRef)
            or len(bundle_refs) != 1
            or artifact_ref_identity_key(direct_bundle_ref)
            != artifact_ref_identity_key(bundle_refs[0])
        )
        complete_ref_set = (
            simulation_ref is not None and len(bundle_refs) == 1 and len(binding_refs) == 1
        )
        complete_inventory = (
            complete_ref_set
            and not invalid_output_ref
            and not direct_bundle_mismatch
            and not derived_scan_truncated
        )
        complete = getattr(result, "ok", None) is True and complete_inventory
        output_ref_count = int(simulation_ref is not None) + len(bundle_refs) + len(binding_refs)
        output_status: Literal["complete", "partial", "none"] = (
            "complete" if complete_inventory else "partial" if output_ref_count else "none"
        )
        result_ok = getattr(result, "ok", None)
        result_status: Literal["ok", "failed", "not_established"] = (
            "ok" if result_ok is True else "failed" if result_ok is False else "not_established"
        )
        self._diagnostics.append(
            _RuntimeGraphProducerEmission(
                emission_index=len(self._diagnostics),
                execute_result_status=result_status,
                output_ref_status=output_status,
                simulation_result_ref=simulation_ref,
                method_execution_bundle_refs=tuple(bundle_refs),
                method_metric_binding_set_refs=tuple(binding_refs),
            )
        )
        if derived_scan_truncated:
            self._inventory_truncated = True
        if complete and simulation_ref is not None and bundle_refs and binding_refs:
            selected_refs = (simulation_ref, bundle_refs[0], binding_refs[0])
            selected_identity = _graph_source_ref_tuple_identity(selected_refs)
            if not any(
                _graph_source_ref_tuple_identity(emitted_refs) == selected_identity
                for emitted_refs in self._emissions
            ):
                self._emissions.append(selected_refs)


def _graph_source_ref_tuple_identity(
    refs: tuple[ArtifactRef, ArtifactRef, ArtifactRef],
) -> tuple[tuple[str, str, str, str | None], ...]:
    """Return full artifact identities for one simulation/bundle/binding tuple."""
    return tuple(artifact_ref_identity_key(ref) for ref in refs)


def _selected_graph_source_refs_from_receipt(
    *,
    graph_output_refs: _ScientistGraphOutputRefs,
    receipt: _RuntimeGraphProducerReceipt | None,
    job_id: str,
    run_id: str,
    attempt: int,
    lease_owner: str | None,
) -> tuple[ArtifactRef, ArtifactRef, ArtifactRef] | None:
    """Accept only final-state refs that equal a scoped actual ExecuteResult emission."""
    if (
        type(receipt) is not _RuntimeGraphProducerReceipt
        or not receipt.is_runtime_minted()
        or receipt.job_id != job_id
        or receipt.run_id != run_id
        or receipt.attempt != attempt
        or receipt.inventory_truncated
        or not lease_owner
        or receipt.lease_owner != lease_owner
    ):
        return None
    if type(graph_output_refs) is not _ScientistGraphOutputRefs:
        return None
    refs = (
        graph_output_refs.simulation_result_ref,
        graph_output_refs.method_execution_bundle_ref,
        graph_output_refs.method_metric_binding_set_ref,
    )
    if any(not isinstance(ref, ArtifactRef) for ref in refs):
        return None
    selected_refs = cast(
        "tuple[ArtifactRef, ArtifactRef, ArtifactRef]",
        refs,
    )
    expected_kinds = (
        "foundry.simulation_result",
        "foundry.method_execution_bundle",
        "foundry.method_metric_binding_set",
    )
    if any(
        ref.kind != kind
        or ref.media_type != "application/json"
        or ref.manifest_profile_sha256 is None
        for ref, kind in zip(selected_refs, expected_kinds, strict=True)
    ):
        return None
    selected_identity = _graph_source_ref_tuple_identity(selected_refs)
    if not any(
        _graph_source_ref_tuple_identity(emitted_refs) == selected_identity
        for emitted_refs in receipt.emissions
    ):
        return None
    return selected_refs


def _scientist_graph_output_refs(state: Mapping[str, Any]) -> _ScientistGraphOutputRefs:
    """Keep only three full-profile producer refs from the mutable workflow result."""
    artifacts_index = state.get("artifacts_index")
    if not isinstance(artifacts_index, Mapping):
        return _ScientistGraphOutputRefs(None, None, None)
    selected: list[ArtifactRef | None] = []
    for key, expected_kind in (
        ("simulation_result_ref", "foundry.simulation_result"),
        ("method_execution_bundle_ref", "foundry.method_execution_bundle"),
        ("method_metric_binding_set_ref", "foundry.method_metric_binding_set"),
    ):
        try:
            ref = ArtifactRef.model_validate(artifacts_index[key])
        except KeyError, TypeError, ValueError:
            selected.append(None)
            continue
        if (
            ref.kind != expected_kind
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
        ):
            selected.append(None)
            continue
        selected.append(ref)
    return _ScientistGraphOutputRefs(
        simulation_result_ref=selected[0],
        method_execution_bundle_ref=selected[1],
        method_metric_binding_set_ref=selected[2],
    )


def _configured_core_read_owner(store: object) -> object:
    """Resolve only the known Core-to-IR writer adapter to its configured CAS owner.

    The exact repository adapter forwards bounded Core reads to ``store``. Its
    configured owner can be a ``GuardedDependencyProxy``; retain that owner so its
    existing guarded-operation policy remains active. Arbitrary wrappers and
    subclasses must implement their own bounded-reader surface.
    """
    from polisyos.core.artifacts.ir_adapter import CoreToIRArtifactStoreAdapter

    if type(store) is CoreToIRArtifactStoreAdapter:
        return store.store
    return store


def _require_bounded_store_protocol[BoundedStoreProtocolT](
    store: object,
    protocol: type[BoundedStoreProtocolT],
    *,
    limits: CoreJsonReadLimits,
    refusal_code: str,
    failure_stage: str,
) -> BoundedStoreProtocolT:
    """Narrow the configured CAS owner only at a bounded-read use boundary."""
    from polisyos.core.artifacts.canonical_profile import CoreJsonReadBoundsRefusalError
    from polisyos.core.artifacts.protocol import matches_runtime_protocol

    protocol_owner = _configured_core_read_owner(store)
    if matches_runtime_protocol(protocol_owner, protocol):
        return protocol_owner
    raise CoreJsonReadBoundsRefusalError(
        refusal_code,
        limits=limits,
        max_manifest_bytes=limits.max_manifest_bytes,
        observed_manifest_bytes=0,
        observed_manifest_selection_bytes=0,
        observed_manifest_verification_bytes=0,
        observed_bytes=0,
        observed_depth=0,
        observed_elements=0,
        source_usage_complete=True,
        failure_stage=failure_stage,
    )


@dataclass(frozen=True, slots=True)
class _RuntimeMethodExecutionAdmission:
    """Server-resolved request pins supplied to the selected worker slot."""

    store: _MethodExecutionArtifactStore
    requested_source_ref: ArtifactRef
    observational_run_intent_ref: ArtifactRef
    source_manifest_sha256: str
    lease_owner: str
    protocol: Literal["method_input_envelope_v1", "legacy_hte_json_v1"]
    method_fqn: str
    method_version: str
    method_abi_digest: str
    method_build_digest: str
    resource_policy: _ObservationalInputResourcePolicy
    owned_hte_request_context: _OwnedHTERequestContextV1 | None
    search_binding_tenant_id: str | None
    search_binding_cell_id: str | None
    search_binding_admission: SearchUncertaintyTaskAdmissionSnapshot | None
    effective_params: dict[str, Any]
    submitted_params: dict[str, Any]
    submitted_params_present: bool
    seed: int
    resource_policy_ref: ArtifactRef
    resource_policy_digest: str
    selection_digest: str
    source_access_revalidation_status: Literal["not_established"]
    requested_limitations: tuple[str, ...]
    source_governance: ArtifactGovernanceInfo
    source_tenant_context: ArtifactTenantContextInfo | None
    limits: CoreJsonReadLimits


@dataclass(frozen=True, slots=True)
class _RuntimeGraphMetricSource:
    """Bind a fixed metric task to producer refs returned by the current workflow call."""

    job_id: str
    run_id: str
    attempt: int
    lease_owner: str
    simulation_result_ref: ArtifactRef
    method_execution_bundle_ref: ArtifactRef
    method_metric_binding_set_ref: ArtifactRef


_RUNTIME_GRAPH_METRIC_SOURCE: ContextVar[_RuntimeGraphMetricSource | None] = ContextVar(
    "runtime_graph_metric_source", default=None
)


_EPOCH_VALIDITY_INTAKE_FAILURE_CODES = frozenset(
    {
        "verifier_not_configured",
        "ref_unresolved",
        "content_hash_mismatch",
        "signature_unverified",
        "authority_purpose_mismatch",
        "query_context_mismatch",
        "dependency_denominator_unresolved",
        "target_denominator_mismatch",
        "verifier_provenance_untrusted",
        "epoch_pending_verification_binding_mismatch",
        "epoch_completed_verification_binding_mismatch",
        "decision_validity_epoch_receipt_unresolved",
        "epoch_transition_signer_not_established",
        "epoch_transition_exact_evidence_unavailable",
        "epoch_transition_disposition_unresolved",
        "epoch_denominator_reconciliation_unavailable",
        "epoch_denominator_reconciliation_unresolved",
        "epoch_denominator_reconciliation_ambiguous",
        "epoch_denominator_reconciliation_admission_conflict",
        "epoch_denominator_membership_mismatch",
    }
)
_MONITOR_TRIGGER_BY_SOURCE_CLASS: dict[str, DecisionTriggerType] = {
    "incident": DecisionTriggerType.POST_DEPLOYMENT_REFUTATION,
    "appeal": DecisionTriggerType.EXPERT_REVIEW,
    "correction": DecisionTriggerType.DATA_INVALIDATION,
    "retraction": DecisionTriggerType.SOURCE_INVALIDATION,
    "legal_change": DecisionTriggerType.LAW_CHANGE,
    "discovered_bias": DecisionTriggerType.CONTEXT_PROFILE_DRIFT,
}


def _default_runtime_metrics() -> MetricsRegistry:
    return get_metrics()


def _default_runtime_tracer() -> PolicyOSTracer:
    return get_tracer()


def _clean_runtime_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class _ControlEvaluationSafetyAuthorityResolver:
    """Fail-closed authority resolver; it appoints and verifies nothing."""

    def resolve(self, artifact_ref: EvalSafetyArtifactRef) -> EvalSafetyAuthorityResolution:
        return EvalSafetyAuthorityResolution(
            status="blocked",
            artifact_ref=artifact_ref,
            blocker_codes=("polisyos.eval_safety.authority_unresolved@1.0.0",),
            predicate_provenance=("not_established",),
            resolved_at=datetime.now(UTC),
        )


class _ControlEvaluationSafetyAppointmentResolver:
    """Fail-closed appointment resolver; institutional absence stays explicit."""

    def resolve(self, appointment_ref: EvalSafetyArtifactRef) -> EvalSafetyAppointmentResolution:
        return EvalSafetyAppointmentResolution(
            status="blocked",
            appointment_ref=appointment_ref,
            appointment=None,
            blocker_codes=("polisyos.eval_safety.verifier_unappointed@1.0.0",),
            predicate_provenance=("not_established",),
            verified_at=datetime.now(UTC),
        )


class _ControlEvaluationSafetyVerifierRegistry:
    """Empty open registry; unknown contract IDs fail closed without branching."""

    def resolve(self, evidence_contract_id: str) -> None:
        del evidence_contract_id
        return None


@dataclass(frozen=True, slots=True)
class _ControlEvaluationSafetyReplayPointers:
    """Only durable C01 refs retained between attempt and immediate replay."""

    intake_ref: ArtifactRef
    request_ref: ArtifactRef
    decision_ref: ArtifactRef
    certificate_ref: ArtifactRef
    revision_head_ref: ArtifactRef | None


class _ControlEvaluationSafetyCurrentStateResolver:
    """Reload C01 CAS and selected source material for the exact immediate context."""

    def __init__(
        self,
        *,
        persistence_service: EvaluationSafetyPersistenceService,
        authorities_source: EvaluationSafetyAuthoritiesSource | None,
        authority_resolver: EvalSafetyAuthorityResolver,
        appointment_resolver: EvalSafetyVerifierAppointmentResolver,
        verifier_registry: EvalSafetyVerifierRegistry,
    ) -> None:
        self._persistence_service = persistence_service
        self._authorities_source = authorities_source
        self._authority_resolver = authority_resolver
        self._appointment_resolver = appointment_resolver
        self._verifier_registry = verifier_registry
        self._material_by_context: dict[
            tuple[str, str, str | None],
            EvaluationSafetyReplayMaterial | _ControlEvaluationSafetyReplayPointers,
        ] = {}

    @staticmethod
    def _key(context: EvaluationExecutionContext) -> tuple[str, str, str | None]:
        certificate_id = (
            context.eval_safety_certificate_ref.artifact_id
            if context.eval_safety_certificate_ref is not None
            else None
        )
        return (
            str(evaluation_execution_context_hash(context)),
            context.intake_ref.artifact_id,
            certificate_id,
        )

    def register(
        self,
        *,
        context: EvaluationExecutionContext,
        material: EvaluationSafetyReplayMaterial,
    ) -> None:
        if (
            material.intake_ref != context.intake_ref
            or material.certificate_ref != context.eval_safety_certificate_ref
        ):
            raise ValueError("evaluation_safety_current_state_binding_mismatch")
        if (
            self._authorities_source is not None
            and material.request_ref is not None
            and material.certificate_ref is not None
        ):
            revision_head = (
                material.revision_nodes[-1].revision_ref if material.revision_nodes else None
            )
            entry: EvaluationSafetyReplayMaterial | _ControlEvaluationSafetyReplayPointers = (
                _ControlEvaluationSafetyReplayPointers(
                    intake_ref=material.intake_ref,
                    request_ref=material.request_ref,
                    decision_ref=material.decision_ref,
                    certificate_ref=material.certificate_ref,
                    revision_head_ref=revision_head,
                )
            )
        else:
            entry = material
        self._material_by_context[self._key(context)] = entry

    def resolve(self, context: EvaluationExecutionContext) -> EvaluationSafetyReplayMaterial | None:
        entry = self._material_by_context.get(self._key(context))
        if isinstance(entry, EvaluationSafetyReplayMaterial):
            expected_head = entry.revision_nodes[-1].revision_ref if entry.revision_nodes else None
            if expected_head != context.eval_safety_revision_head_ref:
                return None
            return entry
        source = self._authorities_source
        if source is None or entry is None:
            return None
        if (
            entry.intake_ref != context.intake_ref
            or entry.certificate_ref != context.eval_safety_certificate_ref
            or entry.revision_head_ref != context.eval_safety_revision_head_ref
        ):
            return None
        persistence = self._persistence_service
        try:
            certificate = persistence._read_model(
                entry.certificate_ref,
                key="certificate",
                model_type=EvalSafetyCertificate,
            )
            intake = persistence._read_model(
                entry.intake_ref,
                key="intake",
                model_type=EvaluationAttemptIntake,
            )
            request = persistence._read_model(
                entry.request_ref,
                key="request",
                model_type=EvaluationAttemptRequest,
            )
            decision = persistence._read_model(
                entry.decision_ref,
                key="decision",
                model_type=EvaluationSafetyDecisionEvent,
            )
            if (
                certificate.request_ref != entry.request_ref
                or certificate.decision_ref != entry.decision_ref
                or certificate.domain_pack_ref != request.domain_pack_ref
                or request.intake_ref != entry.intake_ref
                or request.domain_pack_ref != intake.domain_pack_ref
            ):
                raise ValueError("evaluation_safety_current_state_binding_mismatch")
            revision_nodes = persistence._complete_revision_nodes(certificate)
            current_head = revision_nodes[-1].revision_ref if revision_nodes else None
            if current_head != context.eval_safety_revision_head_ref:
                return None
            authorities = source.resolve_for_replay(
                artifact_store=persistence._artifact_store,
                intake_ref=entry.intake_ref,
                intake=intake,
                request_ref=entry.request_ref,
                request=request,
            )
            authorities = _bind_evaluation_safety_authorities_source_result(
                authorities=authorities,
                intake=intake,
                authority_resolver=self._authority_resolver,
                appointment_resolver=self._appointment_resolver,
                verifier_registry=self._verifier_registry,
            )
            return EvaluationSafetyReplayMaterial(
                intake_ref=entry.intake_ref,
                request_ref=entry.request_ref,
                mode_basis_ref=authorities.mode_basis_ref,
                mode_basis=authorities.mode_basis,
                pack_ref=authorities.pack_ref,
                pack=authorities.pack,
                facet_registry=authorities.facet_registry,
                facet_denominator=authorities.facet_denominator,
                authority_resolver=self._authority_resolver,
                appointment_resolver=self._appointment_resolver,
                verifier_registry=self._verifier_registry,
                evidence=authorities.evidence,
                classification=authorities.classification,
                decision_ref=entry.decision_ref,
                certificate_ref=entry.certificate_ref,
                revision_nodes=revision_nodes,
                decision_evaluated_at=decision.safety.evaluated_at,
                revalidated_at=datetime.now(UTC),
            )
        except AuthorityReconciliationError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise AuthorityReconciliationError(
                "evaluation_safety_authority_source_replay_not_established",
                "The selected C01 source could not be freshly reloaded for replay.",
            ) from exc


@dataclass(frozen=True, slots=True)
class PublishedSignatureCustodyLifecyclePublication:
    """Narrow internal publication result for advisory signature-custody maintenance.

    This deliberately does not reuse the HTTP monitor response because custody
    staleness is not an epoch perturbation and therefore has no epoch-advisory
    receipt to expose.
    """

    event_id: str
    dedupe_key: str
    affected_packets: list[str]
    affected_statuses: dict[str, int]
    monitor_event_ref: ArtifactRef
    lifecycle_bridge_result_ref: ArtifactRef


if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from polisyos.core import contracts as core_contracts
    from polisyos.core.artifacts.canonical_profile import (
        CoreJsonArtifactBoundedRead,
        CoreJsonManifestBoundedRead,
        CoreJsonReadLimits,
    )
    from polisyos.core.artifacts.protocol import (
        AsyncArtifactStore,
        CoreJSONArtifactBoundedManifestReceiptReader,
        RootedArtifactStore,
    )
    from polisyos.core.contracts.foundry import (
        CompileRequest,
        CompileResult,
        ExecuteRequest,
        ExecuteResult,
    )
    from polisyos.core.contracts.owned_attempt_anchor import (
        OwnedAttemptAnchorAssociation,
        OwnedAttemptAnchorDispatchContext,
        OwnedAttemptAnchorRef,
        OwnedAttemptAnchorRefusalAssociation,
    )
    from polisyos.core.contracts.owned_attempt_anchor import (
        OwnedAttemptAnchorProjectionAssociation as _OwnedAttemptAnchorProjectionAssociation,
    )
    from polisyos.core.contracts.owned_attempt_anchor import (
        OwnedHTERequestContextV1 as _OwnedHTERequestContextV1,
    )
    from polisyos.core.contracts.runtime import (
        CompletedExAnteCandidateRanking,
        MethodExecutionProducerDiagnostic,
        MethodExecutionSelection,
        MethodMetricCandidateScore,
        SearchUncertaintyTaskAdmissionSnapshot,
    )
    from polisyos.core.contracts.runtime import (
        ContentAdmittedObservationalRunIntent as _ContentAdmittedObservationalRunIntent,
    )
    from polisyos.core.contracts.runtime import (
        DirectMethodExecutionRunProjection as _DirectMethodExecutionRunProjection,
    )
    from polisyos.core.contracts.runtime import (
        DirectMethodExecutionSelection as _DirectMethodExecutionSelection,
    )
    from polisyos.core.contracts.runtime import (
        GraphMethodExecutionSelection as _GraphMethodExecutionSelection,
    )
    from polisyos.core.contracts.runtime import (
        ObservationalInputResourcePolicy as _ObservationalInputResourcePolicy,
    )
    from polisyos.core.contracts.runtime import (
        ObservationalRunIntent as _ObservationalRunIntent,
    )
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.fabric.retrieval import RetrievalProviders, RetrievalService
    from polisyos.foundry.data_plane import (
        HTEInputPreparationRefusal,
        PreparedHTEObservationalInput,
    )
    from polisyos.foundry.methods import MethodSignature
    from polisyos.ir.observation import (
        ContractCompatibilityTarget as _ContractCompatibilityTarget,
    )
    from polisyos.pdc import ArtifactRef as EvalSafetyArtifactRef
    from polisyos.runtime.http.services.adapters.core_run import TerminalCoreRunSource
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
        N4CandidateProposalExecution,
        N4CandidateScenarioProposalOnlyExecution,
        NormativeEvidenceSubmissionRequest,
        NormativeEvidenceSubmissionResponse,
        NormativeRunDisposition,
        NormativeRunEvidenceRefs,
        RecursiveBudgetResolution,
    )
    from polisyos.runtime.http.services.control.nl_pipeline import (
        _DesignProblemGatewayClient,
    )
    from polisyos.runtime.http.services.control.owned_attempt_anchor import (
        _OwnedAttemptAnchorArtifactStore,
    )
    from polisyos.runtime.quality.cycle_substrate import VerifiedNLJobScope
    from polisyos.runtime.quality.data_forge_binding import (
        MeasurementRootExecutionBinding,
    )
    from polisyos.runtime.quality.design_generation import GenerationUnderAResult
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.epoch_certificate_issuance import (
        DecisionPacketEpochIssuanceOwner,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
        GenericCycleSimulationContextHandoffV1,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
        ExecutionIntent,
        RecursiveCycleBudget,
        RecursiveLeafContextOwner,
    )
    from polisyos.runtime.quality.substrate_registry import CatalogServingSourcePaths
    from polisyos.scientist import BudgetState
    from polisyos.scientist.compute.runner import (
        MethodExecutionAdmission,
        MethodExecutionWork,
        _MethodExecutionArtifactStore,
    )
    from polisyos.scientist.governance.continuous import (
        PublicSignaturePopulationProvider,
        PublishedSignatureCustodyResult,
    )
    from polisyos.scientist.methods.search.uncertainty import (
        SearchOwnedAttemptAssociation,
        SearchUncertaintyStore,
        SearchUncertaintyTaskBindingResolution,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        MethodMetricProjectionWorkLike,
        _MethodMetricProjectionArtifactStore,
    )
    from polisyos.scientist.orchestration.engine import BudgetLedgerProducerRunBinding
    from polisyos.scientist.orchestration.engine.context import (
        FoundryPort as _FoundryPortProtocol,
    )
    from polisyos.scientist.orchestration.llm.prompt_cache import (
        CacheReuseAuthorizer,
        PromptCacheProtocol,
    )

    from ...step_up import StepUpReplayStore
    from ..control_registry_providers import ControlRegistryProviders
    from ..scenario_heads import ScenarioHeadStore
    from .capability_discovery import CapabilityDiscoveryService

    class _HumanDecisionSignedArtifactStore(Protocol):
        def get_manifest_bytes(self, artifact_id: artifacts.ArtifactID | str) -> bytes: ...

        def get_signature(
            self, artifact_id: artifacts.ArtifactID | str
        ) -> artifacts.DetachedSignature | None: ...

        def sign_artifact(
            self,
            artifact_id: artifacts.ArtifactID,
            signer: artifacts.Ed25519Signer,
            *,
            signer_identity: str | None = None,
        ) -> artifacts.DetachedSignature: ...

        def verify_signature(
            self,
            artifact_id: artifacts.ArtifactID,
            verifier: artifacts.Ed25519Verifier,
            *,
            strict_identity: bool | None = None,
        ) -> artifacts.SignatureVerificationResult: ...

    class _CycleSubstrateContextAdmissionOwner(Protocol):
        def admit_context(
            self,
            *,
            problem: DesignProblem,
            job_id: str,
            run_id: str,
            tenant_id: str,
            cell_id: str,
            target_world_scope_profile_id: str | None = None,
        ) -> object | None: ...


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerifiedAcquisitionActionPhase:
    """One CAS-bound receipt and its exact durable producer event."""

    receipt_ref: str
    receipt: AcquisitionRoutePhaseReceipt | AcquisitionRouteLoopReceipt
    durable_event_id: str
    event: DiagnosticEvent


@dataclass(frozen=True)
class VerifiedAcquisitionActionOutcome:
    """Snapshot a latest action head and its complete verified phase chain."""

    head: AcquisitionActionHeadRecord
    latest_receipt: AcquisitionRoutePhaseReceipt | AcquisitionRouteLoopReceipt
    executing_phase_ref: str | None
    executing_phase: AcquisitionRoutePhaseReceipt | None
    selection_phase_ref: str | None
    selection_phase: AcquisitionRoutePhaseReceipt | None
    phase_chain: tuple[VerifiedAcquisitionActionPhase, ...]


def _require_action_phase_receipt(
    receipt: AcquisitionRoutePhaseReceipt | AcquisitionRouteLoopReceipt,
) -> AcquisitionRoutePhaseReceipt:
    """Refuse any durable replay whose receipt is not a phase record."""
    if not isinstance(receipt, AcquisitionRoutePhaseReceipt):
        raise ValueError("acquisition_action_phase_replay_conflict")
    return receipt


def _require_action_selection_phase_receipt(
    receipt: AcquisitionRoutePhaseReceipt | AcquisitionRouteLoopReceipt,
) -> AcquisitionRoutePhaseReceipt:
    """Refuse a durable replay unless it resolved to the expected phase type."""
    if not isinstance(receipt, AcquisitionRoutePhaseReceipt):
        raise ValueError("acquisition_action_selection_replay_conflict")
    return receipt


class _AcquisitionRouteLoopArtifactStore(ArtifactStore, CoreJSONArtifactProfileReader, Protocol):
    """Exact configured CAS capabilities used by the acquisition receipt owner."""

    def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef: ...


class AcquisitionRouteLoopAuthoritySink:
    """Persist and advance verified acquisition route phase heads."""

    __slots__ = ("_artifact_store", "_control_store", "_event_log")
    _artifact_store: _AcquisitionRouteLoopArtifactStore

    def __init__(
        self,
        *,
        artifact_store: object,
        event_log: RuntimeDiagnosticEventLog,
        control_store: ControlPlaneStore,
    ) -> None:
        from polisyos.core.artifacts.protocol import matches_runtime_protocol

        if not matches_runtime_protocol(artifact_store, _AcquisitionRouteLoopArtifactStore):
            raise TypeError("acquisition sink requires guarded CAS capabilities")
        self._artifact_store = artifact_store
        self._event_log = event_log
        self._control_store = control_store

    def get_head(
        self,
        receipt: AcquisitionRoutePhaseReceipt | AcquisitionRouteLoopReceipt,
    ) -> AcquisitionActionHeadRecord | None:
        """Read the latest exact durable action head for a phase identity."""

        return self._control_store.get_acquisition_action_head(
            tenant_id=receipt.tenant_id,
            cell_id=receipt.cell_id,
            run_id=receipt.run_id,
            source_job_id=receipt.source_job_id,
            route_id=receipt.route_id,
            action_generation=receipt.action_generation,
        )

    def resolve_action_generation(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        source_job_id: str,
        route_id: str,
        job_id: str,
    ) -> int:
        """Reuse one job's generation or select a successor to a verified terminal."""

        outcomes = self.action_outcomes(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            source_job_id=source_job_id,
            route_id=route_id,
        )
        same_job = tuple(outcome for outcome in outcomes if outcome.head.job_id == job_id)
        if len(same_job) > 1:
            raise ValueError("acquisition_action_job_generation_ambiguous")
        if same_job:
            return same_job[0].head.action_generation
        if not outcomes:
            return 1
        latest = outcomes[-1]
        receipt = latest.latest_receipt
        if not isinstance(receipt, AcquisitionRouteLoopReceipt) or receipt.terminal_outcome not in {
            "quarantined_no_growth",
            "reentry_completed",
        }:
            raise ValueError("acquisition_action_generation_not_reopenable")
        return latest.head.action_generation + 1

    def action_outcomes(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        source_job_id: str,
        route_id: str,
    ) -> tuple[VerifiedAcquisitionActionOutcome, ...]:
        """Resolve the contiguous, current owner-verified action history for one route."""

        scope = {
            "tenant_id": tenant_id,
            "cell_id": cell_id,
            "run_id": run_id,
            "source_job_id": source_job_id,
            "route_id": route_id,
        }
        heads = tuple(
            sorted(
                self._control_store.list_acquisition_action_heads(**scope),
                key=lambda head: head.action_generation,
            )
        )
        if not heads:
            return ()
        generations = tuple(head.action_generation for head in heads)
        if generations != tuple(range(1, len(heads) + 1)):
            raise ValueError("acquisition_action_generation_history_not_contiguous")
        if any(
            (
                head.tenant_id,
                head.cell_id,
                head.run_id,
                head.source_job_id,
                head.route_id,
            )
            != (tenant_id, cell_id, run_id, source_job_id, route_id)
            for head in heads
        ):
            raise ValueError("acquisition_action_scope_mismatch")
        outcomes = tuple(self.verify_action_head(head) for head in heads)
        for outcome in outcomes[:-1]:
            if not isinstance(outcome.latest_receipt, AcquisitionRouteLoopReceipt):
                raise ValueError("acquisition_action_generation_predecessor_not_terminal")
        current_heads = tuple(
            sorted(
                self._control_store.list_acquisition_action_heads(**scope),
                key=lambda head: head.action_generation,
            )
        )
        if current_heads != heads:
            raise ValueError("acquisition_action_current_history_changed")
        return outcomes

    def current_action_outcome(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        source_job_id: str,
        route_id: str,
    ) -> VerifiedAcquisitionActionOutcome | None:
        """Read the newest action only while its complete durable history remains current."""

        outcomes = self.action_outcomes(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            source_job_id=source_job_id,
            route_id=route_id,
        )
        return outcomes[-1] if outcomes else None

    @staticmethod
    def _allowed_predecessor_phases(
        receipt: AcquisitionRoutePhaseReceipt | AcquisitionRouteLoopReceipt,
    ) -> frozenset[str] | None:
        """Return the finite ActionHead predecessor relation for one receipt."""
        if isinstance(receipt, AcquisitionRouteLoopReceipt):
            if receipt.terminal_outcome == "reentry_completed":
                return frozenset({"world_committed_reentry_pending"})
            return frozenset({"executing", "outcome_selected"})
        return {
            "requested": frozenset(),
            "executing": frozenset({"requested"}),
            "outcome_selected": frozenset({"executing"}),
            "world_committed_reentry_pending": frozenset({"executing", "outcome_selected"}),
        }.get(receipt.receipt_phase)

    def _verified_action_phase_chain(
        self, head: AcquisitionActionHeadRecord
    ) -> tuple[VerifiedAcquisitionActionPhase, ...]:
        """Resolve every CAS/event predecessor to the unique requested root."""
        newest_first: list[VerifiedAcquisitionActionPhase] = []
        seen_refs: set[str] = set()
        current_ref: str | None = head.receipt_ref
        while current_ref is not None:
            if current_ref in seen_refs:
                raise ValueError("acquisition_action_phase_chain_cycle")
            seen_refs.add(current_ref)
            current = self._read_verified_action_phase(current_ref)
            newest_first.append(current)
            current_ref = current.receipt.predecessor_receipt_ref
        chain = tuple(reversed(newest_first))
        if not chain or len(chain) != head.head_generation:
            raise ValueError("acquisition_action_phase_chain_generation_mismatch")

        identity = chain[0].receipt
        seen_phases: set[str] = set()
        previous: VerifiedAcquisitionActionPhase | None = None
        for current in chain:
            receipt = current.receipt
            phase_name = (
                "terminal"
                if isinstance(receipt, AcquisitionRouteLoopReceipt)
                else receipt.receipt_phase
            )
            if phase_name in seen_phases:
                raise ValueError("acquisition_action_phase_chain_duplicate_phase")
            seen_phases.add(phase_name)
            if not self._same_action_identity(identity, receipt):
                raise ValueError("acquisition_action_phase_chain_identity_mismatch")
            if previous is None:
                if (
                    not isinstance(receipt, AcquisitionRoutePhaseReceipt)
                    or receipt.receipt_phase != "requested"
                    or receipt.predecessor_receipt_ref is not None
                    or current.event.state_before is not None
                ):
                    raise ValueError("acquisition_action_phase_chain_requested_root_invalid")
            else:
                previous_receipt = previous.receipt
                previous_name = (
                    "terminal"
                    if isinstance(previous_receipt, AcquisitionRouteLoopReceipt)
                    else previous_receipt.receipt_phase
                )
                allowed = self._allowed_predecessor_phases(receipt)
                if (
                    allowed is None
                    or previous_name not in allowed
                    or receipt.predecessor_receipt_ref != previous.receipt_ref
                    or current.event.state_before != previous_name
                    or receipt.generated_at < previous_receipt.generated_at
                ):
                    raise ValueError("acquisition_action_phase_chain_transition_invalid")
                if (
                    isinstance(receipt, AcquisitionRoutePhaseReceipt)
                    and receipt.receipt_phase == "outcome_selected"
                    and (
                        not isinstance(previous_receipt, AcquisitionRoutePhaseReceipt)
                        or previous_receipt.receipt_phase != "executing"
                    )
                ):
                    raise ValueError("acquisition_action_selection_predecessor_invalid")
            if current.event.state_after != phase_name:
                raise ValueError("acquisition_action_phase_chain_event_state_mismatch")
            previous = current

        latest = chain[-1]
        latest_receipt = latest.receipt
        if (
            head.receipt_ref != head.receipt_sha256
            or latest.receipt_ref != head.receipt_ref
            or latest.durable_event_id != head.durable_event_id
            or any(
                getattr(latest_receipt, field) != getattr(head, field)
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
            )
        ):
            raise ValueError("acquisition_action_head_binding_mismatch")

        executing = next(
            (
                item
                for item in chain
                if isinstance(item.receipt, AcquisitionRoutePhaseReceipt)
                and item.receipt.receipt_phase == "executing"
            ),
            None,
        )
        selection = next(
            (
                item
                for item in chain
                if isinstance(item.receipt, AcquisitionRoutePhaseReceipt)
                and item.receipt.receipt_phase == "outcome_selected"
            ),
            None,
        )
        if selection is not None:
            later_phases = chain[chain.index(selection) + 1 :]
            if executing is None or any(
                not set(selection.receipt.owner_receipt_refs).issubset(
                    set(item.receipt.owner_receipt_refs)
                )
                for item in later_phases
            ):
                raise ValueError("acquisition_action_selection_owner_chain_mismatch")
            executing_phase = _require_action_phase_receipt(executing.receipt)
            self._verified_current_action_outcome_ref(
                executing_phase,
                executing.receipt_ref,
                selection.receipt.owner_receipt_refs,
            )
        if isinstance(latest_receipt, AcquisitionRouteLoopReceipt):
            if latest_receipt.terminal_outcome == "reentry_completed":
                if (
                    len(chain) < 2
                    or not isinstance(chain[-2].receipt, AcquisitionRoutePhaseReceipt)
                    or chain[-2].receipt.receipt_phase != "world_committed_reentry_pending"
                    or chain[-2].receipt.owner_receipt_refs != latest_receipt.owner_receipt_refs
                ):
                    raise ValueError("acquisition_action_terminal_owner_chain_mismatch")
            elif selection is not None and not set(selection.receipt.owner_receipt_refs).issubset(
                set(latest_receipt.owner_receipt_refs)
            ):
                raise ValueError("acquisition_action_terminal_owner_chain_mismatch")
        return chain

    @staticmethod
    def _same_action_identity(
        left: AcquisitionRoutePhaseReceipt | AcquisitionRouteLoopReceipt,
        right: AcquisitionRoutePhaseReceipt | AcquisitionRouteLoopReceipt,
    ) -> bool:
        return all(
            getattr(left, field) == getattr(right, field)
            for field in (
                "tenant_id",
                "cell_id",
                "run_id",
                "source_job_id",
                "route_id",
                "action_generation",
                "job_id",
                "compiled_ref",
                "planner_report_hash",
                "cost_basis_hash",
                "decision_ref",
            )
        )

    def _read_verified_action_phase(self, receipt_ref: str) -> VerifiedAcquisitionActionPhase:
        """Resolve exact receipt bytes and verify its complete producer-event binding."""
        if (
            not receipt_ref.startswith("sha256:")
            or len(receipt_ref) != 71
            or any(character not in "0123456789abcdef" for character in receipt_ref[7:])
        ):
            raise ValueError("acquisition_action_head_receipt_ref_invalid")
        artifact_id = artifacts.ArtifactID.model_validate(receipt_ref)
        payload = self._artifact_store.get_bytes(artifact_id)
        if "sha256:" + hashlib.sha256(payload).hexdigest() != receipt_ref:
            raise ValueError("acquisition_action_head_receipt_hash_mismatch")
        manifest = read_core_manifest_profile(self._artifact_store, artifact_id)[0]
        if manifest.kind == "runtime_quality.acquisition_route_loop_receipt":
            receipt_type = AcquisitionRouteLoopReceipt
            schema_name = "polisyos.runtime.AcquisitionRouteLoopReceipt"
        elif manifest.kind == "runtime_quality.acquisition_route_phase_receipt":
            receipt_type = AcquisitionRoutePhaseReceipt
            schema_name = "polisyos.runtime.AcquisitionRoutePhaseReceipt"
        else:
            raise ValueError("acquisition_action_head_receipt_kind_invalid")
        receipt = receipt_type.model_validate(
            read_core_json_artifact(
                self._artifact_store,
                artifact_ref_for_manifest(manifest),
                raw_payload_bytes=payload,
            ).value
        )
        schema = manifest.artifact_schema
        tenant = manifest.tenant_context
        closure = manifest.same_input_closure
        producer = manifest.producer
        if (
            schema is None
            or schema.name != schema_name
            or schema.version != receipt.schema_version.rsplit("@", 1)[-1]
            or manifest.media_type != "application/json"
            or producer is None
            or producer.component != "polisyos.runtime.acquisition_route_loop"
            or producer.version != "2026.08.28+ds15-c02"
            or tenant is None
            or tenant.tenant_id != receipt.tenant_id
            or tenant.cell_id != receipt.cell_id
            or closure is None
            or closure.closure_id != f"acquisition-route:{receipt.receipt_id}"
            or closure.status != "closed"
            or closure.run_id != receipt.run_id
            or closure.job_id != receipt.job_id
            or closure.tenant_id != receipt.tenant_id
            or closure.cell_id != receipt.cell_id
            or closure.closure_sha256 != receipt.route_id
        ):
            raise ValueError("acquisition_action_head_receipt_schema_or_scope_invalid")
        report = reconcile_authority_ref(
            artifact_store=self._artifact_store,
            event_log=self._event_log,
            cas_ref=receipt_ref,
            expected_tenant_id=receipt.tenant_id,
            expected_cell_id=receipt.cell_id,
            expected_run_id=receipt.run_id,
            expected_job_id=receipt.job_id,
        )
        if report.durable_event_id is None or manifest.authority is None:
            raise ValueError("acquisition_action_head_receipt_event_missing")
        event_ref = resolve_authority_diagnostic_event_ref(self._artifact_store, manifest.authority)
        event_manifest = read_core_manifest_profile(self._artifact_store, event_ref)[0]
        selected_event_ref = artifact_ref_for_manifest(event_manifest)
        event_schema = event_manifest.artifact_schema
        if (
            event_manifest.kind != DIAGNOSTIC_EVENT_ARTIFACT_KIND
            or event_schema is None
            or event_schema.name != DIAGNOSTIC_EVENT_SCHEMA_NAME
            or event_schema.version != DIAGNOSTIC_EVENT_SCHEMA_VERSION
        ):
            raise ValueError("acquisition_action_phase_event_schema_invalid")
        event_payload = self._artifact_store.get_bytes(selected_event_ref)
        event_ref_text = str(event_ref.artifact_id)
        if "sha256:" + hashlib.sha256(event_payload).hexdigest() != event_ref_text:
            raise ValueError("acquisition_action_phase_event_hash_mismatch")
        event = DiagnosticEvent.model_validate(
            read_core_json_artifact(
                self._artifact_store,
                selected_event_ref,
                raw_payload_bytes=event_payload,
            ).value
        )
        expected_inputs = tuple(
            sorted(
                {
                    *(
                        ()
                        if receipt.predecessor_receipt_ref is None
                        else (receipt.predecessor_receipt_ref,)
                    ),
                    *receipt.owner_receipt_refs,
                }
            )
        )
        expected_event_type = (
            "polisyos.runtime.acquisition.route_loop.v1"
            if isinstance(receipt, AcquisitionRouteLoopReceipt)
            else "polisyos.runtime.acquisition.route_phase.v1"
        )
        expected_blocking = (
            "blocking" if receipt.recovery_state == "reentry_recovery_required" else "non_blocking"
        )
        records = self._event_log.list_events(
            event_id=event.event_id,
            run_id=receipt.run_id,
            job_id=receipt.job_id,
            limit=100,
        )
        if (
            report.durable_event_id != event.event_id
            or len(records) != 1
            or records[0].event != event
            or event.event_source != "polisyos.runtime.quality.acquisition_route_loop"
            or event.event_type != expected_event_type
            or event.event_subject
            != f"run/{receipt.run_id}/job/{receipt.job_id}/acquisition/{receipt.receipt_phase}"
            or event.event_time != receipt.generated_at
            or event.trace_id != f"trace-{receipt.job_id}"
            or event.span_id != f"span-{receipt.receipt_phase}"
            or event.parent_span_id is not None
            or event.run_id != receipt.run_id
            or event.job_id != receipt.job_id
            or event.tenant_id != receipt.tenant_id
            or event.cell_id != receipt.cell_id
            or event.producer_component != "polisyos.runtime.acquisition_route_loop"
            or event.producer_version != "2026.08.28+ds15-c02"
            or event.execution_profile != "governed"
            or event.phase != "acquisition_route_loop"
            or event.state_after != receipt.receipt_phase
            or event.payload_ref != receipt_ref
            or event.artifact_refs != (receipt_ref,)
            or event.input_refs != expected_inputs
            or closure.evidence_input_refs != expected_inputs
            or event.blocking_status != expected_blocking
        ):
            raise ValueError("acquisition_action_phase_event_binding_mismatch")
        return VerifiedAcquisitionActionPhase(
            receipt_ref=receipt_ref,
            receipt=receipt,
            durable_event_id=event.event_id,
            event=event,
        )

    def _verified_receipt_ref(
        self, receipt_ref: str
    ) -> tuple[AcquisitionRoutePhaseReceipt | AcquisitionRouteLoopReceipt, str]:
        """Retain the receipt reader API while enforcing the full event binding."""
        verified = self._read_verified_action_phase(receipt_ref)
        return verified.receipt, verified.durable_event_id

    def _verified_generation_head(
        self,
        head: AcquisitionActionHeadRecord,
    ) -> AcquisitionRoutePhaseReceipt | AcquisitionRouteLoopReceipt:
        """Verify the whole generation before using its terminal or current receipt."""
        return self.verify_action_head(head).latest_receipt

    def _verified_current_action_outcome_ref(
        self,
        executing: AcquisitionRoutePhaseReceipt,
        executing_ref: str,
        owner_receipt_refs: tuple[str, ...],
    ) -> str:
        """Resolve exactly one current action outcome CAS from the full owner receipt set."""
        from polisyos.runtime.quality.acquisition_world_growth import (
            AcquisitionWorldGrowthNoGrowthReceipt,
            AcquisitionWorldGrowthReceipt,
        )

        kinds = {
            "runtime_quality.acquisition_world_growth_receipt": (
                AcquisitionWorldGrowthReceipt,
                AcquisitionWorldGrowthReceipt.ARTIFACT_SCHEMA_NAME,
            ),
            "runtime_quality.acquisition_world_growth_no_growth_receipt": (
                AcquisitionWorldGrowthNoGrowthReceipt,
                "polisyos.runtime.AcquisitionWorldGrowthNoGrowthReceipt",
            ),
        }
        matches: list[str] = []
        for ref in owner_receipt_refs:
            if (
                not ref.startswith("sha256:")
                or len(ref) != 71
                or any(character not in "0123456789abcdef" for character in ref[7:])
            ):
                raise ValueError("acquisition_action_owner_receipt_ref_invalid")
            artifact_id = artifacts.ArtifactID.model_validate(ref)
            manifest = read_core_manifest_profile(self._artifact_store, artifact_id)[0]
            expected = kinds.get(manifest.kind)
            if expected is None:
                continue
            receipt_type, schema_name = expected
            payload = self._artifact_store.get_bytes(artifact_id)
            if "sha256:" + hashlib.sha256(payload).hexdigest() != ref:
                raise ValueError("acquisition_action_owner_receipt_hash_mismatch")
            receipt = receipt_type.model_validate(
                read_core_json_artifact(
                    self._artifact_store,
                    artifact_ref_for_manifest(manifest),
                    raw_payload_bytes=payload,
                ).value
            )
            if receipt.action_phase_ref != executing_ref:
                continue
            schema = manifest.artifact_schema
            if (
                schema is None
                or schema.name != schema_name
                or schema.version != "1.1"
                or receipt.schema_version != f"{schema_name.rsplit('.', 1)[-1]}@1.1"
                or manifest.producer is None
                or manifest.producer.component != "polisyos.runtime.acquisition_world_growth"
                or manifest.media_type != "application/json"
                or manifest.tenant_context is None
                or manifest.tenant_context.tenant_id != executing.tenant_id
                or manifest.tenant_context.cell_id != executing.cell_id
                or receipt.selection.tenant_id != executing.tenant_id
                or receipt.selection.cell_id != executing.cell_id
                or receipt.selection.run_id != executing.run_id
                or receipt.selection.route_id != executing.route_id
            ):
                raise ValueError("acquisition_action_owner_receipt_binding_mismatch")
            report = reconcile_authority_ref(
                artifact_store=self._artifact_store,
                event_log=self._event_log,
                cas_ref=ref,
                expected_tenant_id=executing.tenant_id,
                expected_cell_id=executing.cell_id,
                expected_run_id=executing.run_id,
                expected_job_id=executing.source_job_id,
            )
            if report.durable_event_id is None:
                raise ValueError("acquisition_action_owner_receipt_event_missing")
            matches.append(ref)
        if len(matches) != 1:
            raise ValueError("acquisition_action_owner_outcome_missing_or_ambiguous")
        return matches[0]

    def _existing_action_selection_event(
        self, expected: AcquisitionRoutePhaseReceipt, event_id: str
    ) -> tuple[str, str] | None:
        records = self._event_log.list_events(
            event_id=event_id,
            run_id=expected.run_id,
            job_id=expected.job_id,
            limit=100,
        )
        if not records:
            return None
        if len(records) != 1 or records[0].event.event_id != event_id:
            raise ValueError("acquisition_action_selection_event_ambiguous")
        ref = records[0].event.payload_ref
        if not ref:
            raise ValueError("acquisition_action_selection_event_ambiguous")
        receipt, durable_id = self._verified_receipt_ref(ref)
        expected_receipt = expected.model_copy(update={"generated_at": receipt.generated_at})
        if (
            not isinstance(receipt, AcquisitionRoutePhaseReceipt)
            or receipt != expected_receipt
            or durable_id != event_id
        ):
            raise ValueError("acquisition_action_selection_replay_conflict")
        return ref, durable_id

    def _advance_existing_action_selection(
        self,
        receipt: AcquisitionRoutePhaseReceipt,
        receipt_ref: str,
        durable_event_id: str,
    ) -> AcquisitionActionHeadRecord:
        current = self.get_head(receipt)
        if current is not None and current.receipt_ref == receipt_ref:
            if self._verified_generation_head(current) != receipt:
                raise ValueError("acquisition_action_selection_head_binding_mismatch")
            return current
        if (
            current is None
            or current.receipt_ref != receipt.predecessor_receipt_ref
            or current.receipt_phase != "executing"
        ):
            raise ValueError("acquisition_action_selection_predecessor_conflict")
        head = self._control_store.advance_acquisition_action_head(
            tenant_id=receipt.tenant_id,
            cell_id=receipt.cell_id,
            run_id=receipt.run_id,
            source_job_id=receipt.source_job_id,
            route_id=receipt.route_id,
            action_generation=receipt.action_generation,
            expected_head_generation=current.head_generation,
            receipt_ref=receipt_ref,
            receipt_sha256=receipt_ref,
            durable_event_id=durable_event_id,
            coarse_phase=receipt.coarse_phase,
            receipt_phase=receipt.receipt_phase,
            recovery_state=receipt.recovery_state,
            job_id=receipt.job_id,
            predecessor_receipt_ref=receipt.predecessor_receipt_ref,
        )
        if self.get_head(receipt) != head:
            raise RuntimeError("acquisition_action_selection_head_readback_failed")
        verified = self.verify_action_head(head)
        if (
            verified.selection_phase_ref != head.receipt_ref
            or verified.selection_phase is None
            or verified.selection_phase.predecessor_receipt_ref != receipt.predecessor_receipt_ref
        ):
            raise RuntimeError("acquisition_action_selection_chain_readback_failed")
        return head

    def persist_action_outcome_selection(
        self,
        action_phase_ref: str,
        owner_receipt_refs: tuple[str, ...],
    ) -> AcquisitionActionHeadRecord:
        """Persist selection of one verified owner CAS as a durable action-head transition."""
        executing, _ = self._verified_receipt_ref(action_phase_ref)
        if (
            not isinstance(executing, AcquisitionRoutePhaseReceipt)
            or executing.receipt_phase != "executing"
        ):
            raise ValueError("acquisition_action_selection_executing_phase_invalid")
        scope = {
            "tenant_id": executing.tenant_id,
            "cell_id": executing.cell_id,
            "run_id": executing.run_id,
            "source_job_id": executing.source_job_id,
            "route_id": executing.route_id,
        }
        snapshot = self.current_action_outcome(**scope)
        if (
            snapshot is None
            or snapshot.executing_phase_ref != action_phase_ref
            or snapshot.executing_phase != executing
        ):
            raise ValueError("acquisition_action_selection_executing_head_changed")
        outcome_ref = self._verified_current_action_outcome_ref(
            executing, action_phase_ref, owner_receipt_refs
        )
        if snapshot.selection_phase is not None:
            selection = snapshot.selection_phase
            if (
                selection.predecessor_receipt_ref != action_phase_ref
                or selection.owner_receipt_refs != (outcome_ref,)
                or snapshot.selection_phase_ref is None
            ):
                raise ValueError("acquisition_action_selection_replay_conflict")
            return snapshot.head
        if (
            snapshot.head.receipt_ref != action_phase_ref
            or snapshot.head.receipt_phase != "executing"
        ):
            raise ValueError("acquisition_action_selection_executing_head_changed")
        identity = "\0".join(
            (
                executing.tenant_id,
                executing.cell_id,
                executing.run_id,
                executing.source_job_id,
                executing.route_id,
                str(executing.action_generation),
                executing.job_id,
                action_phase_ref,
                outcome_ref,
            )
        )
        digest = hashlib.sha256(identity.encode()).hexdigest()
        suffix = f"outcome_selected_{digest[:24]}"
        selection = AcquisitionRoutePhaseReceipt(
            schema_version="AcquisitionRoutePhaseReceipt@1.1",
            receipt_id=f"{executing.job_id}.outcome-selected.{digest[:24]}",
            tenant_id=executing.tenant_id,
            cell_id=executing.cell_id,
            run_id=executing.run_id,
            source_job_id=executing.source_job_id,
            route_id=executing.route_id,
            action_generation=executing.action_generation,
            job_id=executing.job_id,
            compiled_ref=executing.compiled_ref,
            planner_report_hash=executing.planner_report_hash,
            cost_basis_hash=executing.cost_basis_hash,
            decision_ref=executing.decision_ref,
            coarse_phase="executing",
            receipt_phase="outcome_selected",
            recovery_state="none",
            predecessor_receipt_ref=action_phase_ref,
            owner_receipt_refs=(outcome_ref,),
            generated_at=datetime.now(UTC),
        )
        event_id = f"evt_acquisition_{executing.action_generation}_{suffix}"
        existing = self._existing_action_selection_event(selection, event_id)
        if existing is None:
            try:
                head = self._persist_receipt(
                    selection,
                    artifact_kind="runtime_quality.acquisition_route_phase_receipt",
                    schema_name="polisyos.runtime.AcquisitionRoutePhaseReceipt",
                    event_type="polisyos.runtime.acquisition.route_phase.v1",
                    event_suffix=suffix,
                    receipt_type=AcquisitionRoutePhaseReceipt,
                    receipt_label="phase",
                )
            except Exception:
                existing = self._existing_action_selection_event(selection, event_id)
                if existing is None:
                    raise
                existing_receipt, _ = self._verified_receipt_ref(existing[0])
                phase_receipt = _require_action_selection_phase_receipt(existing_receipt)
                head = self._advance_existing_action_selection(phase_receipt, *existing)
        else:
            existing_receipt, _ = self._verified_receipt_ref(existing[0])
            phase_receipt = _require_action_selection_phase_receipt(existing_receipt)
            head = self._advance_existing_action_selection(phase_receipt, *existing)
        after = self.current_action_outcome(**scope)
        if (
            after is None
            or after.selection_phase is None
            or after.selection_phase_ref != head.receipt_ref
            or after.selection_phase.predecessor_receipt_ref != action_phase_ref
            or after.selection_phase.owner_receipt_refs != (outcome_ref,)
        ):
            raise RuntimeError("acquisition_action_selection_readback_failed")
        return head

    def verify_action_head(
        self, head: AcquisitionActionHeadRecord
    ) -> VerifiedAcquisitionActionOutcome:
        """Verify the exact head, every receipt/event ancestor, and a fresh head read."""
        current = self._control_store.get_acquisition_action_head(
            tenant_id=head.tenant_id,
            cell_id=head.cell_id,
            run_id=head.run_id,
            source_job_id=head.source_job_id,
            route_id=head.route_id,
            action_generation=head.action_generation,
        )
        if current != head:
            raise ValueError("acquisition_action_generation_head_changed")
        phase_chain = self._verified_action_phase_chain(head)
        latest = phase_chain[-1]
        executing = next(
            (
                item
                for item in phase_chain
                if isinstance(item.receipt, AcquisitionRoutePhaseReceipt)
                and item.receipt.receipt_phase == "executing"
            ),
            None,
        )
        selection = next(
            (
                item
                for item in phase_chain
                if isinstance(item.receipt, AcquisitionRoutePhaseReceipt)
                and item.receipt.receipt_phase == "outcome_selected"
            ),
            None,
        )
        current = self._control_store.get_acquisition_action_head(
            tenant_id=head.tenant_id,
            cell_id=head.cell_id,
            run_id=head.run_id,
            source_job_id=head.source_job_id,
            route_id=head.route_id,
            action_generation=head.action_generation,
        )
        if current != head:
            raise ValueError("acquisition_action_generation_head_changed")
        executing_phase = (
            None if executing is None else _require_action_phase_receipt(executing.receipt)
        )
        selection_phase = (
            None
            if selection is None
            else _require_action_selection_phase_receipt(selection.receipt)
        )
        return VerifiedAcquisitionActionOutcome(
            head=head,
            latest_receipt=latest.receipt,
            executing_phase_ref=None if executing is None else executing.receipt_ref,
            executing_phase=executing_phase,
            selection_phase_ref=None if selection is None else selection.receipt_ref,
            selection_phase=selection_phase,
            phase_chain=phase_chain,
        )

    def persist_phase(
        self,
        receipt: AcquisitionRoutePhaseReceipt,
    ) -> AcquisitionActionHeadRecord:
        """Write, reconcile, read back, and then advance one exact phase head."""

        typed = AcquisitionRoutePhaseReceipt.model_validate(receipt)
        return self._persist_receipt(
            typed,
            artifact_kind="runtime_quality.acquisition_route_phase_receipt",
            schema_name="polisyos.runtime.AcquisitionRoutePhaseReceipt",
            event_type="polisyos.runtime.acquisition.route_phase.v1",
            event_suffix=typed.receipt_phase,
            receipt_type=AcquisitionRoutePhaseReceipt,
            receipt_label="phase",
        )

    def persist_terminal(
        self,
        receipt: AcquisitionRouteLoopReceipt,
    ) -> AcquisitionActionHeadRecord:
        """Write and expose a terminal head only after exact loop-receipt readback."""

        typed = AcquisitionRouteLoopReceipt.model_validate(receipt)
        return self._persist_receipt(
            typed,
            artifact_kind="runtime_quality.acquisition_route_loop_receipt",
            schema_name="polisyos.runtime.AcquisitionRouteLoopReceipt",
            event_type="polisyos.runtime.acquisition.route_loop.v1",
            event_suffix="loop_terminal",
            receipt_type=AcquisitionRouteLoopReceipt,
            receipt_label="loop",
        )

    def _persist_receipt(
        self,
        typed: AcquisitionRoutePhaseReceipt | AcquisitionRouteLoopReceipt,
        *,
        artifact_kind: str,
        schema_name: str,
        event_type: str,
        event_suffix: str,
        receipt_type: type[AcquisitionRoutePhaseReceipt] | type[AcquisitionRouteLoopReceipt],
        receipt_label: str,
    ) -> AcquisitionActionHeadRecord:
        """Persist one strict receipt family before advancing its shared action head."""

        current = self.get_head(typed)
        if (current is None and typed.predecessor_receipt_ref is not None) or (
            current is not None and typed.predecessor_receipt_ref != current.receipt_ref
        ):
            raise ValueError("acquisition_action_predecessor_conflict")
        if current is not None:
            previous = self.verify_action_head(current)
            if not self._same_action_identity(typed, previous.latest_receipt):
                raise ValueError("acquisition_action_predecessor_identity_mismatch")
        payload = typed.model_dump(mode="json")
        canon_spec = CanonSpec(forbid_floats=False)
        generated_at = typed.generated_at.isoformat()
        input_ref_set = set()
        if typed.predecessor_receipt_ref is not None:
            input_ref_set.add(typed.predecessor_receipt_ref)
        input_ref_set.update(typed.owner_receipt_refs)
        input_refs = tuple(sorted(input_ref_set))
        result = write_runtime_authority_artifact(
            self._artifact_store,
            self._event_log,
            payload,
            ArtifactWriteOptions(
                kind=artifact_kind,
                media_type="application/json",
                schema=SchemaInfo(
                    name=schema_name,
                    version=typed.schema_version.rsplit("@", 1)[-1],
                ),
                producer=ProducerInfo(
                    component="polisyos.runtime.acquisition_route_loop",
                    version="2026.08.28+ds15-c02",
                ),
                governance=ArtifactGovernanceInfo(classification="internal"),
                inputs=[],
            ),
            evidence_id=typed.receipt_id,
            evidence_class="authority_bearing",
            authority_role="producer_authority",
            provenance_kind="runtime_emitted",
            owner="team-runtime-quality",
            reader_contract="runtime.acquisition_route_loop.reader",
            reader_contract_version="1.0",
            tenant_id=typed.tenant_id,
            cell_id=typed.cell_id,
            run_id=typed.run_id,
            job_id=typed.job_id,
            trace_id=f"trace-{typed.job_id}",
            span_id=f"span-{typed.receipt_phase}",
            parent_span_id=None,
            requested_execution_profile="governed",
            effective_execution_profile="governed",
            phase="acquisition_route_loop",
            generated_at=generated_at,
            as_of_time=generated_at,
            same_input_closure={
                "closure_id": f"acquisition-route:{typed.receipt_id}",
                "status": "closed",
                "run_id": typed.run_id,
                "job_id": typed.job_id,
                "tenant_id": typed.tenant_id,
                "cell_id": typed.cell_id,
                "evidence_input_refs": input_refs,
                "closure_sha256": typed.route_id,
            },
            input_refs=input_refs,
            effective_mode_ref=typed.route_id,
            degradation_ledger_ref=None,
            semantic_binding_ref=typed.cost_basis_hash,
            validation_status="pass",
            blocking_status=(
                "blocking"
                if typed.recovery_state == "reentry_recovery_required"
                else "non_blocking"
            ),
            governance=GovernanceMetadata(
                classification="internal",
                authority_boundary="runtime.acquisition_route_loop",
                pii="none",
                retention_policy="runtime-quality-90d",
                review_status="runtime_verified",
                override_policy="no_override",
                approval_policy="pa2_ds9_decision_required",
            ),
            event_id=f"evt_acquisition_{typed.action_generation}_{event_suffix}",
            event_source="polisyos.runtime.quality.acquisition_route_loop",
            event_type=event_type,
            event_subject=(
                f"run/{typed.run_id}/job/{typed.job_id}/acquisition/{typed.receipt_phase}"
            ),
            state_before=(current.receipt_phase if current is not None else None),
            state_after=typed.receipt_phase,
            canon_spec=canon_spec,
        )
        receipt_ref = str(result.cas_ref.artifact_id)
        if result.payload_sha256 != receipt_ref.removeprefix("sha256:"):
            raise RuntimeError(f"acquisition_{receipt_label}_payload_hash_mismatch")
        report = reconcile_authority_ref(
            artifact_store=self._artifact_store,
            event_log=self._event_log,
            cas_ref=receipt_ref,
            expected_tenant_id=typed.tenant_id,
            expected_cell_id=typed.cell_id,
            expected_run_id=typed.run_id,
            expected_job_id=typed.job_id,
        )
        loaded = receipt_type.model_validate(
            read_core_json_artifact(self._artifact_store, receipt_ref).value
        )
        manifest = read_core_manifest_profile(self._artifact_store, receipt_ref)[0]
        schema = manifest.artifact_schema
        if (
            loaded != typed
            or report.durable_event_id is None
            or manifest.kind != artifact_kind
            or schema is None
            or schema.name != schema_name
            or schema.version != typed.schema_version.rsplit("@", 1)[-1]
        ):
            raise RuntimeError(f"acquisition_{receipt_label}_readback_failed")
        head = self._control_store.advance_acquisition_action_head(
            tenant_id=typed.tenant_id,
            cell_id=typed.cell_id,
            run_id=typed.run_id,
            source_job_id=typed.source_job_id,
            route_id=typed.route_id,
            action_generation=typed.action_generation,
            expected_head_generation=(current.head_generation if current is not None else 0),
            receipt_ref=receipt_ref,
            receipt_sha256=receipt_ref,
            durable_event_id=report.durable_event_id,
            coarse_phase=typed.coarse_phase,
            receipt_phase=typed.receipt_phase,
            recovery_state=typed.recovery_state,
            job_id=typed.job_id,
            predecessor_receipt_ref=typed.predecessor_receipt_ref,
        )
        if self.get_head(typed) != head:
            raise RuntimeError("acquisition_action_head_readback_failed")
        verified = self.verify_action_head(head)
        if verified.latest_receipt != typed:
            raise RuntimeError("acquisition_action_chain_readback_failed")
        return head


_CustodyResult = TypeVar("_CustodyResult")


class HumanDecisionAuthoritySink:
    """Narrow persistence boundary for custodied human-decision records."""

    __slots__ = ("_artifact_store", "_event_log", "_reservation_store")

    def __init__(
        self,
        *,
        artifact_store: ArtifactStore,
        event_log: RuntimeDiagnosticEventLog,
        reservation_store: ControlPlaneStore,
    ) -> None:
        self._artifact_store = artifact_store
        self._event_log = event_log
        self._reservation_store = reservation_store

    def run_custody_operation(self, operation: Callable[[], _CustodyResult]) -> _CustodyResult:
        """Keep a whole fenced operation on the guarded transaction owner."""

        return run_guarded_dependency_operation(self._reservation_store, operation)

    def reserve_action(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        binding_sha256: str,
        now: datetime,
        lease_seconds: int,
        record_valid_until: datetime,
    ) -> HumanDecisionReservationResult:
        """Reserve the sole live generation for an exact governed action."""

        return self._reservation_store.reserve_human_decision_action(
            tenant_id=tenant_id,
            governed_action_key=governed_action_key,
            reservation_id=reservation_id,
            binding_sha256=binding_sha256,
            now=now,
            lease_seconds=lease_seconds,
            record_valid_until=record_valid_until,
        )

    def get_reservation(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
    ) -> HumanDecisionReservationRecord | None:
        """Derive the newest immutable reservation generation."""

        return self._reservation_store.get_human_decision_reservation(
            tenant_id=tenant_id,
            governed_action_key=governed_action_key,
        )

    def get_reservation_generation(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_version: int,
    ) -> HumanDecisionReservationRecord | None:
        """Read one exact reservation generation."""

        return self._reservation_store.get_human_decision_reservation_generation(
            tenant_id=tenant_id,
            governed_action_key=governed_action_key,
            reservation_version=reservation_version,
        )

    def hold_write_fence(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        reservation_version: int,
        binding_sha256: str,
        acquired_at: datetime,
        expected_record_valid_until: datetime,
    ) -> AbstractContextManager[HumanDecisionWriteFence]:
        """Hold the exact reservation through record/event finalization."""

        return self._reservation_store.hold_human_decision_write_fence(
            tenant_id=tenant_id,
            governed_action_key=governed_action_key,
            reservation_id=reservation_id,
            reservation_version=reservation_version,
            binding_sha256=binding_sha256,
            acquired_at=acquired_at,
            expected_record_valid_until=expected_record_valid_until,
        )

    def hold_recovery_fence(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        reservation_version: int,
    ) -> AbstractContextManager[HumanDecisionRecoveryFence]:
        """Hold one exact null-ref generation through CAS/event restoration."""

        return self._reservation_store.hold_human_decision_recovery_fence(
            tenant_id=tenant_id,
            governed_action_key=governed_action_key,
            reservation_id=reservation_id,
            reservation_version=reservation_version,
        )

    def mark_recovery_required(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        reservation_version: int,
        record_ref: str | None = None,
        record_sha256: str | None = None,
        durable_event_id: str | None = None,
    ) -> HumanDecisionReservationRecord:
        """Freeze a partial generation pending independent reconciliation."""

        return self._reservation_store.mark_human_decision_recovery_required(
            tenant_id=tenant_id,
            governed_action_key=governed_action_key,
            reservation_id=reservation_id,
            reservation_version=reservation_version,
            record_ref=record_ref,
            record_sha256=record_sha256,
            durable_event_id=durable_event_id,
        )

    def reconcile_orphan_reservation(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        reservation_version: int,
        verifier: artifacts.Ed25519Verifier,
        expected_signer_identity: str,
        expected_key_id: str,
        expected_cell_id: str | None,
        expected_run_id: str,
        expected_job_id: str,
        reconciled_at: datetime,
    ) -> HumanDecisionReservationRecord:
        """Make a signed/event-reconciled orphan historical without deleting it."""

        from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
            HUMAN_DECISION_RECORD_V2,
            HumanDecisionRecord,
        )

        reservation = self.get_reservation_generation(
            tenant_id=tenant_id,
            governed_action_key=governed_action_key,
            reservation_version=reservation_version,
        )
        if (
            reservation is None
            or reservation.reservation_id != reservation_id
            or reservation.state != "recovery_required"
            or reservation.record_ref is None
            or reservation.record_ref != reservation.record_sha256
            or reservation.durable_event_id is None
        ):
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        manifest = self.get_artifact_manifest(reservation.record_ref)
        schema = manifest.artifact_schema
        if (
            manifest.kind != "runtime_quality.agent_action_human_decision"
            or schema is None
            or schema.name != "polisyos.runtime.HumanDecisionRecord"
            or schema.version != "2.0"
        ):
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        signature = self.verify_artifact_signature(
            reservation.record_ref,
            verifier,
            strict_identity=True,
        )
        if (
            not signature.ok
            or signature.signer_identity != expected_signer_identity
            or signature.key_id != expected_key_id
        ):
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        report = self.reconcile_authority_artifact(
            reservation.record_ref,
            expected_tenant_id=tenant_id,
            expected_cell_id=expected_cell_id,
            expected_run_id=expected_run_id,
            expected_job_id=expected_job_id,
        )
        if report.durable_event_id != reservation.durable_event_id:
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        record = HumanDecisionRecord.model_validate(
            read_core_json_artifact(self._artifact_store, reservation.record_ref).value
        )
        if (
            record.schema_version != HUMAN_DECISION_RECORD_V2
            or record.tenant_id != tenant_id
            or record.run_id != expected_run_id
            or record.governed_action_key != governed_action_key
            or record.reservation_id != reservation_id
            or record.reservation_version != reservation_version
            or record.binding_sha256 != reservation.binding_sha256
            or record.custody_signer_identity != expected_signer_identity
            or record.custody_key_id != expected_key_id
            or record.valid_until != reservation.record_valid_until
        ):
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        return self._reservation_store._reconcile_orphan_human_decision_reservation(
            tenant_id=tenant_id,
            governed_action_key=governed_action_key,
            reservation_id=reservation_id,
            reservation_version=reservation_version,
            reconciled_at=reconciled_at,
        )

    def reconcile_null_ref_reservation(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        reservation_version: int,
        verifier: artifacts.Ed25519Verifier,
        expected_signer_identity: str,
        expected_key_id: str,
        expected_cell_id: str | None,
        expected_run_id: str,
        expected_job_id: str,
        reconciled_at: datetime,
    ) -> HumanDecisionReservationRecord:
        """Discover and reconcile one signed orphan whose SQL refs rolled back."""

        def _restore() -> HumanDecisionReservationRecord:
            from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
                HUMAN_DECISION_RECORD_V2,
                HumanDecisionRecord,
            )

            if getattr(self._event_log, "_store", None) is not self._reservation_store:
                raise RuntimeError("human-decision recovery requires the shared control store")
            with self.hold_recovery_fence(
                tenant_id=tenant_id,
                governed_action_key=governed_action_key,
                reservation_id=reservation_id,
                reservation_version=reservation_version,
            ) as fence:
                matches: list[tuple[str, ArtifactManifest, Mapping[str, Any]]] = []
                for artifact_id in self._artifact_store.iter_artifact_ids():
                    try:
                        manifest = read_core_manifest_profile(self._artifact_store, artifact_id)[0]
                    except CanonicalProfileRefusalError:
                        raise
                    except Exception as exc:
                        raise RuntimeError(
                            "human-decision recovery CAS manifest scan failed"
                        ) from exc
                    if manifest.kind != "runtime_quality.agent_action_human_decision":
                        continue
                    try:
                        payload = read_core_json_artifact(self._artifact_store, artifact_id).value
                    except CanonicalProfileRefusalError:
                        raise
                    except Exception as exc:
                        raise RuntimeError("human-decision recovery CAS readback failed") from exc
                    if not isinstance(payload, Mapping):
                        raise RuntimeError("human-decision record payload is not an object")
                    if (
                        payload.get("reservation_id") == reservation_id
                        and payload.get("reservation_version") == reservation_version
                    ):
                        matches.append((str(artifact_id), manifest, payload))
                if len(matches) != 1:
                    raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
                record_ref, manifest, payload = matches[0]
                schema = manifest.artifact_schema
                if (
                    schema is None
                    or schema.name != "polisyos.runtime.HumanDecisionRecord"
                    or schema.version != "2.0"
                ):
                    raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
                try:
                    record = HumanDecisionRecord.model_validate(payload)
                except (TypeError, ValueError) as exc:
                    raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED") from exc
                reservation = fence.reservation
                if (
                    record.schema_version != HUMAN_DECISION_RECORD_V2
                    or record.tenant_id != tenant_id
                    or record.run_id != expected_run_id
                    or record.governed_action_key != governed_action_key
                    or record.reservation_id != reservation_id
                    or record.reservation_version != reservation_version
                    or record.binding_sha256 != reservation.binding_sha256
                    or record.valid_until != reservation.record_valid_until
                    or record.custody_signer_identity != expected_signer_identity
                    or record.custody_key_id != expected_key_id
                ):
                    raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
                signature = self.verify_artifact_signature(
                    record_ref,
                    verifier,
                    strict_identity=True,
                )
                if (
                    not signature.ok
                    or signature.signer_identity != expected_signer_identity
                    or signature.key_id != expected_key_id
                ):
                    raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
                authority = manifest.authority
                if authority is None:
                    raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
                event_ref = resolve_authority_diagnostic_event_ref(
                    self._artifact_store,
                    authority,
                )
                event_manifest = read_core_manifest_profile(self._artifact_store, event_ref)[0]
                event_schema = event_manifest.artifact_schema
                if (
                    event_manifest.kind != DIAGNOSTIC_EVENT_ARTIFACT_KIND
                    or event_schema is None
                    or event_schema.name != DIAGNOSTIC_EVENT_SCHEMA_NAME
                    or event_schema.version != DIAGNOSTIC_EVENT_SCHEMA_VERSION
                ):
                    raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
                try:
                    event = DiagnosticEvent.model_validate(
                        read_core_json_artifact(self._artifact_store, event_ref).value
                    )
                except (TypeError, ValueError) as exc:
                    raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED") from exc
                if (
                    event.payload_ref != record_ref
                    or event.tenant_id != tenant_id
                    or event.run_id != expected_run_id
                    or event.job_id != expected_job_id
                    or (expected_cell_id is not None and event.cell_id != expected_cell_id)
                ):
                    raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
                self._event_log.append(
                    event,
                    payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=True),
                )
                report = self.reconcile_authority_artifact(
                    record_ref,
                    expected_tenant_id=tenant_id,
                    expected_cell_id=expected_cell_id,
                    expected_run_id=expected_run_id,
                    expected_job_id=expected_job_id,
                )
                if report.durable_event_id != event.event_id:
                    raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
                return fence.reconcile_orphan(
                    record_ref=record_ref,
                    record_sha256=record_ref,
                    durable_event_id=event.event_id,
                    reconciled_at=reconciled_at,
                )

        return self.run_custody_operation(_restore)

    def reconcile_empty_reservation(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        reservation_version: int,
        reconciled_at: datetime,
    ) -> HumanDecisionReservationRecord:
        """Reconcile only after independently proving no record artifact exists."""

        reservation = self.get_reservation_generation(
            tenant_id=tenant_id,
            governed_action_key=governed_action_key,
            reservation_version=reservation_version,
        )
        if (
            reservation is None
            or reservation.reservation_id != reservation_id
            or reservation.state != "recovery_required"
            or reservation.record_ref is not None
            or reservation.record_sha256 is not None
            or reservation.durable_event_id is not None
        ):
            raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        for artifact_id in self._artifact_store.iter_artifact_ids():
            try:
                manifest = read_core_manifest_profile(self._artifact_store, artifact_id)[0]
            except CanonicalProfileRefusalError:
                raise
            except Exception as exc:
                raise RuntimeError("human-decision reconciliation CAS scan failed") from exc
            if manifest.kind != "runtime_quality.agent_action_human_decision":
                continue
            try:
                payload = read_core_json_artifact(self._artifact_store, artifact_id).value
            except CanonicalProfileRefusalError:
                raise
            except Exception as exc:
                raise RuntimeError("human-decision reconciliation readback failed") from exc
            if not isinstance(payload, Mapping):
                raise RuntimeError("human-decision record payload is not an object")
            if (
                payload.get("reservation_id") == reservation_id
                and payload.get("reservation_version") == reservation_version
            ):
                raise ValueError("DS9-RESERVATION-RECOVERY-REQUIRED")
        return self._reservation_store._reconcile_empty_human_decision_reservation(
            tenant_id=tenant_id,
            governed_action_key=governed_action_key,
            reservation_id=reservation_id,
            reservation_version=reservation_version,
            reconciled_at=reconciled_at,
        )

    def ownership_evidence(
        self,
        *,
        tenant_id: str | None,
        cell_id: str | None,
    ) -> Mapping[str, object]:
        """Read active ownership-format evidence from the supplied runtime store."""

        read_evidence = getattr(self._artifact_store, "ownership_evidence", None)
        if not callable(read_evidence):
            raise RuntimeError("artifact_ownership_evidence_unavailable")
        evidence = read_evidence(tenant_id=tenant_id, cell_id=cell_id)
        if not isinstance(evidence, Mapping):
            raise RuntimeError("artifact_ownership_evidence_invalid")
        return dict(evidence)

    def write_authority_artifact(
        self,
        payload: object,
        options: ArtifactWriteOptions,
        *,
        authority_fields: _AuthorityArtifactWriteFields,
    ) -> AuthorityArtifactWriteResult:
        """Persist through the existing CAS plus durable diagnostic event chain."""

        typed_authority_fields = TypeAdapter(_AuthorityArtifactWriteFields).validate_python(
            authority_fields,
            strict=True,
        )
        return write_runtime_authority_artifact(
            self._artifact_store,
            self._event_log,
            payload,
            options,
            **typed_authority_fields,
        )

    def reconcile_authority_artifact(
        self,
        artifact_ref: str,
        *,
        expected_tenant_id: str | None,
        expected_cell_id: str | None,
        expected_run_id: str | None,
        expected_job_id: str | None,
    ) -> AuthorityReconciliationReport:
        """Prove one CAS authority record has its durable diagnostic event."""

        report = reconcile_authority_ref(
            artifact_store=self._artifact_store,
            event_log=self._event_log,
            cas_ref=artifact_ref,
            expected_tenant_id=expected_tenant_id,
            expected_cell_id=expected_cell_id,
            expected_run_id=expected_run_id,
            expected_job_id=expected_job_id,
        )
        artifact_id = artifacts.ArtifactID.model_validate(artifact_ref)
        manifest = read_core_manifest_profile(self._artifact_store, artifact_id)[0]
        authority = manifest.authority
        if authority is None:
            raise ValueError("human-decision authority manifest linkage is absent")
        event_id = resolve_authority_diagnostic_event_ref(self._artifact_store, authority)
        event_manifest = read_core_manifest_profile(self._artifact_store, event_id)[0]
        event_schema = event_manifest.artifact_schema
        if (
            event_manifest.kind != DIAGNOSTIC_EVENT_ARTIFACT_KIND
            or event_schema is None
            or event_schema.name != DIAGNOSTIC_EVENT_SCHEMA_NAME
            or event_schema.version != DIAGNOSTIC_EVENT_SCHEMA_VERSION
        ):
            raise ValueError("human-decision diagnostic event artifact changed")
        event = DiagnosticEvent.model_validate(
            read_core_json_artifact(self._artifact_store, event_id).value
        )
        durable_records = self._event_log.list_events(
            event_id=event.event_id,
            run_id=expected_run_id,
            job_id=expected_job_id,
            limit=100,
        )
        if (
            report.durable_event_id != event.event_id
            or event.payload_ref != artifact_ref
            or not any(getattr(record, "event", None) == event for record in durable_records)
        ):
            raise ValueError("human-decision diagnostic event binding changed")
        return report

    def has_artifact(self, artifact_ref: str) -> bool:
        """Return whether an exact content ref is present."""

        return bool(self._artifact_store.has(artifacts.ArtifactID.model_validate(artifact_ref)))

    def get_artifact_bytes(self, artifact_ref: str) -> bytes:
        """Return exact CAS bytes for verification and model readback."""

        return self._artifact_store.get_bytes(artifacts.ArtifactID.model_validate(artifact_ref))

    def get_artifact_json(self, artifact_ref: str) -> Any:  # noqa: ANN401
        """Decode one exact Core JSON view through the shared profile guard."""
        artifact_id = artifacts.ArtifactID.model_validate(artifact_ref)
        return read_core_json_artifact(self._artifact_store, artifact_id).value

    def get_artifact_manifest(self, artifact_ref: str) -> ArtifactManifest:
        """Return the exact CAS manifest for schema admission."""

        return self._artifact_store.get_manifest(artifacts.ArtifactID.model_validate(artifact_ref))

    def get_artifact_manifest_bytes(self, artifact_ref: str) -> bytes:
        """Return manifest bytes bound by detached signatures."""

        return self._signed_artifact_store().get_manifest_bytes(
            artifacts.ArtifactID.model_validate(artifact_ref)
        )

    def get_artifact_signature(self, artifact_ref: str) -> artifacts.DetachedSignature | None:
        """Return an existing detached signature without synthesizing one."""

        return self._signed_artifact_store().get_signature(
            artifacts.ArtifactID.model_validate(artifact_ref)
        )

    def sign_artifact(
        self,
        artifact_ref: str,
        signer: artifacts.Ed25519Signer,
        *,
        signer_identity: str,
    ) -> artifacts.DetachedSignature:
        """Sign one exact artifact only when no sidecar exists."""

        store = self._signed_artifact_store()
        artifact_id = artifacts.ArtifactID.model_validate(artifact_ref)
        if store.get_signature(artifact_id) is not None:
            raise ValueError("human-decision artifact already has a signature")
        return store.sign_artifact(
            artifact_id,
            signer,
            signer_identity=signer_identity,
        )

    def verify_artifact_signature(
        self,
        artifact_ref: str,
        verifier: artifacts.Ed25519Verifier,
        *,
        strict_identity: bool = True,
    ) -> artifacts.SignatureVerificationResult:
        """Verify exact bytes, manifest, key trust, and signer identity."""

        return self._signed_artifact_store().verify_signature(
            artifacts.ArtifactID.model_validate(artifact_ref),
            verifier,
            strict_identity=strict_identity,
        )

    def _signed_artifact_store(self) -> _HumanDecisionSignedArtifactStore:
        required_methods = (
            "get_manifest_bytes",
            "get_signature",
            "sign_artifact",
            "verify_signature",
        )
        if any(
            not callable(getattr(self._artifact_store, method_name, None))
            for method_name in required_methods
        ):
            raise RuntimeError("human-decision signed artifact store is unavailable")
        return cast(
            "_HumanDecisionSignedArtifactStore",
            cast("object", self._artifact_store),
        )


def _injected_artifact_store_backend(
    *,
    artifact_store: ArtifactStore,
    signature_verifier: SignatureVerifyingArtifactStore | None,
) -> tuple[str | None, SignatureVerifyingArtifactStore | None]:
    """Select a filesystem backend only from a concrete store or bound verifier."""
    from polisyos.core.artifacts.store import FileSystemCAS

    if signature_verifier is not None and (
        not callable(getattr(signature_verifier, "verify_signature", None))
        or getattr(signature_verifier, "guarded_store", None) is not artifact_store
    ):
        raise ValueError("control_signature_verifier_store_mismatch")
    if type(artifact_store) is FileSystemCAS:
        selected_verifier = signature_verifier or build_guarded_signature_verifier(
            backend="filesystem",
            guarded_store=artifact_store,
        )
        return "filesystem", selected_verifier
    if type(signature_verifier) is _GuardedStoreSignatureVerifier:
        return "filesystem", signature_verifier
    return None, signature_verifier


class ControlPlaneService(
    ControlJobAttemptPublicationMixin,
    ControlJobScopeAdmissionMixin,
    ControlJobDiagnosticsMixin,
    ControlNLJobAdmissionMixin,
    ControlNLJobExecutionMixin,
    ControlNLJobPublicationMixin,
    ControlPlaneWorkspaceLoopTransitionMixin,
    CapabilityManifestMixin,
    LexPipelineMixin,
    NaturalLanguageRunMixin,
):
    """Bridge HTTP control requests to durable jobs and domain pipelines."""

    @staticmethod
    def build_decision_validity_owner(store: ArtifactStore) -> DecisionValidityService:
        """Build the canonical Decision Validity owner over ``store``."""
        from polisyos.runtime.quality.epoch_transition_verification import (
            build_epoch_decision_validity_owner,
        )

        return build_epoch_decision_validity_owner(store=store)

    @staticmethod
    def is_decision_validity_owner(candidate: object) -> bool:
        """Return whether ``candidate`` is the canonical owner service type."""
        return isinstance(candidate, DecisionValidityService)

    def __init__(
        self,
        *,
        cas_root: Path,
        core_runs_root: Path,
        repo_root: Path | None = None,
        metrics: MetricsRegistry | None = None,
        tracer: PolicyOSTracer | None = None,
        artifact_store: ArtifactStore | None = None,
        signature_verifier: SignatureVerifyingArtifactStore | None = None,
        async_artifact_store: AsyncArtifactStore | None = None,
        control_store: ControlPlaneStore | None = None,
        retrieval_service: RetrievalService | None = None,
        policy_resolver: RuntimeExecutionPolicyResolver | None = None,
        registry_providers: ControlRegistryProviders | None = None,
        decision_validity_service: DecisionValidityService | None = None,
        epoch_certificate_issuance_owner: DecisionPacketEpochIssuanceOwner | None = None,
        promotion_runtime: PromotionRuntime | None = None,
        epoch_claim_lifecycle_bridge: EpochClaimLifecycleBridgeService | None = None,
        evaluation_safety_persistence_service: EvaluationSafetyPersistenceService | None = None,
        evaluation_safety_authorities_source: EvaluationSafetyAuthoritiesSource | None = None,
        evaluation_safety_promotion_source_slot: EvaluationSafetyPromotionSourceSlot | None = None,
        published_signature_population_provider: PublicSignaturePopulationProvider | None = None,
        normative_authority_trust: NormativeAuthorityTrust | None = None,
        llm_producer_settlement_store: BudgetMiddleware | None = None,
        llm_cache_reuse_authorizer: CacheReuseAuthorizer | None = None,
        llm_prompt_cache: PromptCacheProtocol | None = None,
        cycle_substrate_context_admission_owner: _CycleSubstrateContextAdmissionOwner | None = None,
        generic_cycle_simulation_admission_owner: GenericCycleSimulationAdmissionOwner
        | None = None,
        generic_cycle_simulation_root_profile_id: str | None = None,
        enable_contract_testing_credal_source_attempts: bool = False,
    ) -> None:
        from polisyos.fabric.retrieval import RetrievalService

        self._cas_root = cas_root
        self._core_runs_root = core_runs_root
        if (
            llm_producer_settlement_store is not None
            and type(llm_producer_settlement_store) is not BudgetMiddleware
        ):
            raise TypeError("llm_producer_settlement_store_must_be_budget_middleware")
        self._llm_producer_settlement_store = llm_producer_settlement_store
        self._llm_cache_reuse_authorizer: CacheReuseAuthorizer | None = None
        self._llm_prompt_cache: PromptCacheProtocol | None = None
        self.bind_llm_cache_reuse(
            authorizer=llm_cache_reuse_authorizer,
            prompt_cache=llm_prompt_cache,
        )
        # The source-data root is a separate input from CAS/output roots and package
        # resources. The default preserves module-derived behavior; an explicit root
        # is accepted only when it is an existing absolute directory.
        if repo_root is None:
            self._repo_root = Path(__file__).resolve().parents[6]
        else:
            if not isinstance(repo_root, Path):
                raise TypeError("runtime_source_repo_root_must_be_path")
            if not repo_root.is_absolute():
                raise ValueError("runtime_source_repo_root_must_be_absolute")
            try:
                resolved_source_root = repo_root.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise ValueError("runtime_source_repo_root_invalid") from exc
            if not resolved_source_root.is_dir():
                raise ValueError("runtime_source_repo_root_invalid")
            self._repo_root = resolved_source_root
        self._normative_authority_trust = normative_authority_trust or NormativeAuthorityTrust()
        if type(self._normative_authority_trust) is not NormativeAuthorityTrust:
            raise TypeError("normative_deployment_trust_must_be_typed")
        if cycle_substrate_context_admission_owner is not None and not callable(
            getattr(cycle_substrate_context_admission_owner, "admit_context", None)
        ):
            raise ValueError("cycle_substrate_context_admission_owner_invalid")
        self._cycle_substrate_context_admission_owner = cycle_substrate_context_admission_owner
        from polisyos.runtime.quality.generic_simulation_admission import (
            GenericCycleSimulationAdmissionOwner as _GenericCycleSimulationAdmissionOwner,
        )

        if (
            generic_cycle_simulation_admission_owner is not None
            and type(generic_cycle_simulation_admission_owner)
            is not _GenericCycleSimulationAdmissionOwner
        ):
            raise ValueError("generic_cycle_simulation_context_owner_invalid")
        if (generic_cycle_simulation_admission_owner is None) != (
            generic_cycle_simulation_root_profile_id is None
        ):
            raise ValueError("generic_cycle_simulation_root_profile_configuration_incomplete")
        if generic_cycle_simulation_root_profile_id is not None and (
            not isinstance(generic_cycle_simulation_root_profile_id, str)
            or not generic_cycle_simulation_root_profile_id.strip()
        ):
            raise ValueError("generic_cycle_simulation_root_profile_id_invalid")
        if type(enable_contract_testing_credal_source_attempts) is not bool:
            raise TypeError("contract_testing_credal_source_attempts_flag_must_be_bool")
        resolved_policy_resolver = policy_resolver or RuntimeExecutionPolicyResolver.from_env()
        if (
            enable_contract_testing_credal_source_attempts
            and resolved_policy_resolver.default_profile != "dev"
        ):
            raise ValueError("contract_testing_credal_source_attempts_dev_profile_required")
        if enable_contract_testing_credal_source_attempts and (
            generic_cycle_simulation_admission_owner is None
        ):
            raise ValueError("contract_testing_credal_source_attempts_require_generic_owner")
        self._generic_cycle_simulation_admission_owner = generic_cycle_simulation_admission_owner
        self._generic_cycle_simulation_root_profile_id = generic_cycle_simulation_root_profile_id
        self._enable_contract_testing_credal_source_attempts = (
            enable_contract_testing_credal_source_attempts
        )
        self._metrics = metrics if metrics is not None else _default_runtime_metrics()
        self._tracer = tracer if tracer is not None else _default_runtime_tracer()
        self._policy_resolver = resolved_policy_resolver
        self._capability_discovery_service: CapabilityDiscoveryService | None = None
        if registry_providers is None:
            raise ValueError(
                "ControlPlaneService requires typed registry_providers from the "
                "runtime composition root"
            )
        self._registry_providers = registry_providers
        self._catalog_run_profile = registry_providers.catalog_run_profile
        self._catalog_source_selection = registry_providers.catalog_source_selection
        from polisyos.runtime.quality.substrate_registry import (
            resolve_catalog_serving_source,
        )

        self._catalog_serving_source = resolve_catalog_serving_source(
            self._repo_root,
            selection=self._catalog_source_selection,
            requested_profile=self._catalog_run_profile,
        )
        self._catalog_run_profile = self._catalog_serving_source.catalog_run_profile
        self._owns_artifact_store = artifact_store is None
        supplied_signature_verifier = signature_verifier
        signature_verifier = None
        if artifact_store is None:
            if supplied_signature_verifier is not None:
                raise ValueError("control_signature_verifier_requires_injected_store")
            store_config = ArtifactStoreConfig.from_env().model_copy(update={"root": str(cas_root)})
            self._artifact_store_backend: str | None = store_config.backend
            self._artifact_store = cast(
                "ArtifactStore",
                guard_runtime_cas(
                    build_artifact_store(
                        store_config,
                        metrics=self._metrics,
                        tracer=self._tracer,
                    )
                ),
            )
            signature_verifier = build_guarded_signature_verifier(
                backend=store_config.backend, guarded_store=self._artifact_store
            )
        else:
            self._artifact_store = artifact_store
            (
                self._artifact_store_backend,
                signature_verifier,
            ) = _injected_artifact_store_backend(
                artifact_store=artifact_store,
                signature_verifier=supplied_signature_verifier,
            )
        if generic_cycle_simulation_admission_owner is not None:
            if generic_cycle_simulation_admission_owner.store is not self._artifact_store:
                raise ValueError("generic_cycle_simulation_context_owner_store_mismatch")
            root_profiles = tuple(
                profile
                for profile in generic_cycle_simulation_admission_owner.profiles
                if profile.profile_id == generic_cycle_simulation_root_profile_id
            )
            if len(root_profiles) != 1 or root_profiles[0].profile_selection_kind != "problem":
                raise ValueError("generic_cycle_simulation_root_profile_not_configured")
        self._async_artifact_store = async_artifact_store or ensure_async_artifact_store(
            self._artifact_store
        )

        self._owns_control_store = control_store is None
        if control_store is None:
            self._control_store = cast(
                "ControlPlaneStore",
                guard_runtime_control_store(
                    ControlPlaneStore(
                        backend=self._policy_resolver.state_store_backend,
                        sqlite_path=self._resolve_control_sqlite_path(),
                        postgres_dsn=self._policy_resolver.postgres_dsn,
                    )
                ),
            )
        else:
            self._control_store = control_store
        (
            self._method_registry,
            self._observational_method_registrations,
        ) = self._bootstrap_observational_method_registration()
        from polisyos.core.contracts.bounded_liveness import BoundedLivenessConfig
        from polisyos.core.contracts.runtime import ObservationalInputResourcePolicy
        from polisyos.scientist.compute.runner import MethodBackend

        self._bounded_liveness_config = BoundedLivenessConfig()
        method_wait_policy = self._bounded_liveness_config.resolve(
            "runtime.observational_method_execution",
            requested_retries=0,
        )
        self._method_metric_projection_wait_policy = self._bounded_liveness_config.resolve(
            "runtime.method_metric_projection",
            requested_retries=0,
        )
        self._observational_resource_policy = ObservationalInputResourcePolicy(
            schema_version="polisyos.runtime.observational_input_resource_policy.v3",
            revision="r3",
            method_contract_target=_OBSERVATIONAL_METHOD_CONTRACT_TARGET,
            required_estimator_n_jobs=1,
            method_execution_wait_policy=method_wait_policy,
        )
        self._method_backend = MethodBackend(
            admission_service=self,
            registry_provider=lambda: self._method_registry,
            metric_projection_service=self,
        )
        if evaluation_safety_persistence_service is not None and not isinstance(
            evaluation_safety_persistence_service,
            EvaluationSafetyPersistenceService,
        ):
            raise ValueError("evaluation_safety_persistence_owner_invalid")
        if evaluation_safety_persistence_service is None:
            self._diagnostic_event_log = RuntimeDiagnosticEventLog(
                store=self._control_store,
                artifact_store=self._artifact_store,
            )
            self._evaluation_safety_persistence_service = EvaluationSafetyPersistenceService(
                artifact_store=self._artifact_store,
                event_log=self._diagnostic_event_log,
            )
        else:
            supplied_event_log = evaluation_safety_persistence_service._event_log
            if (
                evaluation_safety_persistence_service._artifact_store is not self._artifact_store
                or supplied_event_log._store is not self._control_store
                or supplied_event_log._artifact_store is not self._artifact_store
            ):
                raise ValueError("evaluation_safety_persistence_owner_mismatch")
            self._diagnostic_event_log = supplied_event_log
            self._evaluation_safety_persistence_service = evaluation_safety_persistence_service
        if evaluation_safety_authorities_source is not None and not isinstance(
            evaluation_safety_authorities_source,
            EvaluationSafetyAuthoritiesSource,
        ):
            raise ValueError("evaluation_safety_authorities_source_invalid")
        self._evaluation_safety_authorities_source = evaluation_safety_authorities_source
        if evaluation_safety_authorities_source is None:
            self._evaluation_safety_authority_resolver = _ControlEvaluationSafetyAuthorityResolver()
            self._evaluation_safety_appointment_resolver = (
                _ControlEvaluationSafetyAppointmentResolver()
            )
            self._evaluation_safety_verifier_registry = _ControlEvaluationSafetyVerifierRegistry()
        else:
            self._evaluation_safety_authority_resolver = (
                evaluation_safety_authorities_source.authority_resolver
            )
            self._evaluation_safety_appointment_resolver = (
                evaluation_safety_authorities_source.appointment_resolver
            )
            self._evaluation_safety_verifier_registry = (
                evaluation_safety_authorities_source.verifier_registry
            )
        self._evaluation_safety_state_resolver = _ControlEvaluationSafetyCurrentStateResolver(
            persistence_service=self._evaluation_safety_persistence_service,
            authorities_source=evaluation_safety_authorities_source,
            authority_resolver=self._evaluation_safety_authority_resolver,
            appointment_resolver=self._evaluation_safety_appointment_resolver,
            verifier_registry=self._evaluation_safety_verifier_registry,
        )
        self._evaluation_safety_admission_verifier = EvaluationSafetyAdmissionVerifier(
            persistence_service=self._evaluation_safety_persistence_service,
            current_state_resolver=self._evaluation_safety_state_resolver,
            authority_resolver=self._evaluation_safety_authority_resolver,
            appointment_resolver=self._evaluation_safety_appointment_resolver,
            verifier_registry=self._evaluation_safety_verifier_registry,
        )
        self._evaluation_safety_decision_evidence: dict[
            tuple[str, str], EvaluationSafetyDecisionEvidence
        ] = {}
        self._human_decision_sink = HumanDecisionAuthoritySink(
            artifact_store=self._artifact_store,
            event_log=self._diagnostic_event_log,
            reservation_store=self._control_store,
        )
        self._acquisition_route_sink = AcquisitionRouteLoopAuthoritySink(
            artifact_store=self._artifact_store,
            event_log=self._diagnostic_event_log,
            control_store=self._control_store,
        )
        self._acquisition_job_handler: (
            Callable[
                [ControlJobRecord, dict[str, Any], ControlJobExecutionScope],
                dict[str, Any],
            ]
            | None
        ) = None
        if decision_validity_service is not None and not isinstance(
            decision_validity_service, DecisionValidityService
        ):
            raise ValueError("decision_validity_owner_invalid")
        self._decision_validity_service = (
            decision_validity_service or self.build_decision_validity_owner(self._artifact_store)
        )
        if epoch_certificate_issuance_owner is not None:
            from polisyos.runtime.quality.epoch_certificate_issuance import (
                DecisionPacketEpochIssuanceOwner,
            )

            if (
                type(epoch_certificate_issuance_owner) is not DecisionPacketEpochIssuanceOwner
                or epoch_certificate_issuance_owner.store is not self._artifact_store
            ):
                raise ValueError("epoch_certificate_issuance_owner_mismatch")
        self._epoch_certificate_issuance_owner = epoch_certificate_issuance_owner
        if promotion_runtime is not None and not isinstance(promotion_runtime, PromotionRuntime):
            raise ValueError("promotion_runtime_owner_invalid")
        self._promotion_runtime = promotion_runtime or PromotionRuntime(
            store=self._artifact_store,
            completed_epoch_batches=self._decision_validity_service,
            signature_verifier=signature_verifier,
        )
        if (
            self._promotion_runtime.store is not self._artifact_store
            or self._promotion_runtime.epoch_n9_evidence_resolver._completed_batches
            is not self._decision_validity_service
        ):
            raise ValueError("promotion_runtime_decision_validity_owner_mismatch")
        source_slot = (
            evaluation_safety_promotion_source_slot or EvaluationSafetyPromotionSourceSlot()
        )
        if type(source_slot) is not EvaluationSafetyPromotionSourceSlot:
            raise TypeError("evaluation_safety_promotion_source_slot_must_be_typed")
        if epoch_claim_lifecycle_bridge is None:
            claim_owner = build_default_claim_ledger_owner(store=self._artifact_store)
            self._epoch_claim_lifecycle_bridge = build_epoch_claim_lifecycle_bridge(
                completed_batches=self._decision_validity_service,
                claim_owner=claim_owner,
                artifacts=self._artifact_store,
            )
        else:
            if not isinstance(epoch_claim_lifecycle_bridge, EpochClaimLifecycleBridgeService):
                raise ValueError("epoch_claim_lifecycle_bridge_owner_invalid")
            if (
                epoch_claim_lifecycle_bridge.artifacts is not self._artifact_store
                or epoch_claim_lifecycle_bridge.completed_batches
                is not self._decision_validity_service
                or getattr(epoch_claim_lifecycle_bridge.claim_owner, "store", None)
                is not self._artifact_store
            ):
                raise ValueError("epoch_claim_lifecycle_bridge_owner_store_mismatch")
            self._epoch_claim_lifecycle_bridge = epoch_claim_lifecycle_bridge

        from polisyos.scientist.governance.continuous import (
            PublishedSignatureCustodyWatcher,
        )

        self._published_signature_custody_watcher = PublishedSignatureCustodyWatcher(
            store=self._artifact_store,
            population_provider=published_signature_population_provider,
            lifecycle_publisher=self.publish_published_signature_custody_event,
        )

        self._retrieval_catalog = None
        if retrieval_service is None:
            from polisyos.data_forge.read_api import catalog as catalog_read_api

            curated_dir = _resolve_curated_dir()
            source = self._catalog_serving_source
            self._retrieval_catalog = catalog_read_api.DatasetCatalogGraph(
                source.database_path,
                source.index_dir,
                overlay_path=source.overlay_path,
            )
            self._retrieval = RetrievalService(
                curated_dir=curated_dir,
                artifact_store=self._artifact_store,
                dataset_catalog=self._retrieval_catalog,
                providers=self._build_retrieval_providers(),
            )
        else:
            if self._catalog_source_selection is not None:
                from polisyos.runtime.quality.substrate_registry import (
                    require_catalog_serving_graph_binding,
                )

                graph = getattr(retrieval_service, "_dataset_catalog", None)
                require_catalog_serving_graph_binding(graph, self._catalog_serving_source)
            self._retrieval = retrieval_service
        from polisyos.runtime.quality.promotion_sequence import (
            N9PromotionEvidenceBridgeRepository,
        )

        self._evaluation_safety_promotion_sources = EvaluationSafetyPromotionSourceContext(
            slot=source_slot,
            control_store=self._control_store,
            core_runs_root=self._core_runs_root,
            promotion_runtime=self._promotion_runtime,
            promotion_evidence_resolver=N9PromotionEvidenceBridgeRepository(
                store=self._artifact_store,
                measurement_catalog=self._promotion_runtime.promotion_evidence_source.measurement_catalog,
                measurement_providers=(
                    self._promotion_runtime.promotion_evidence_source.measurement_providers
                ),
                promotion_safety_source_trust=self._promotion_runtime.promotion_safety_source_trust,
                signature_verifier=self._promotion_runtime.signature_verifier,
            ),
        )
        self._worker: ControlWorker | None = None
        self._search_hte_outbox_cursor: int | None = None
        self._search_hte_outbox_watermark: int | None = None
        self._completed_hte_validity_outbox_cursor: int | None = None
        self._completed_hte_validity_outbox_watermark: int | None = None
        if self._policy_resolver.worker_backend == "embedded":
            self._worker = ControlWorker(
                store=self._control_store,
                handler=self._process_control_job,
                maintenance_callback=self._run_control_worker_maintenance,
            )
            self._worker.start()

    @property
    def scenario_head_store(self) -> ScenarioHeadStore:
        """Expose the narrow durable scenario-head authority to the runtime container."""
        return cast("ScenarioHeadStore", self._control_store)

    @property
    def catalog_serving_source(self) -> CatalogServingSourcePaths:
        """Return the immutable catalog source selected by this app's composition root.

        The selected paths are candidate source inputs only. Exposing the exact
        object lets HTTP consumers bind their readback to the same source used by
        the running control service; it does not confer provenance or currentness.
        """
        return self._catalog_serving_source

    @property
    def llm_producer_settlement_store(self) -> BudgetMiddleware | None:
        """Expose the app-scoped producer settlement owner to pipeline composition."""
        return self._llm_producer_settlement_store

    def bind_llm_producer_settlement_store(self, store: BudgetMiddleware) -> None:
        """Bind one durable app-scoped producer settlement owner exactly once.

        The binding supports an injected control service supplied through the
        runtime container. Its identity is local accounting provenance only; it
        does not establish external billing authority or admission policy.
        """
        if type(store) is not BudgetMiddleware:
            raise TypeError("llm_producer_settlement_store_must_be_budget_middleware")
        try:
            identity = store.settlement_owner_identity
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
            raise ValueError("llm_producer_settlement_store_must_be_durable") from exc
        if (
            not isinstance(identity, tuple)
            or len(identity) != 3
            or any(not isinstance(value, str) or not value.strip() for value in identity)
        ):
            raise ValueError("llm_producer_settlement_store_identity_invalid")
        current = self._llm_producer_settlement_store
        if current is not None and current is not store:
            raise ValueError("llm_producer_settlement_store_already_bound")
        self._llm_producer_settlement_store = store

    def bind_llm_cache_reuse(
        self,
        *,
        authorizer: CacheReuseAuthorizer | None,
        prompt_cache: PromptCacheProtocol | None,
    ) -> None:
        """Bind the optional app-scoped cache owner without creating authority."""
        if authorizer is None and prompt_cache is None:
            return
        if authorizer is not None and not callable(getattr(authorizer, "authorize_reuse", None)):
            raise TypeError("llm_cache_reuse_authorizer_invalid")
        if prompt_cache is not None and not all(
            callable(getattr(prompt_cache, name, None)) for name in ("get", "put")
        ):
            raise TypeError("llm_prompt_cache_invalid")
        current_authorizer = self._llm_cache_reuse_authorizer
        current_cache = self._llm_prompt_cache
        if current_authorizer is not None and authorizer is not current_authorizer:
            raise ValueError("llm_cache_reuse_authorizer_already_bound")
        if current_cache is not None and prompt_cache is not current_cache:
            raise ValueError("llm_prompt_cache_already_bound")
        if authorizer is not None:
            self._llm_cache_reuse_authorizer = authorizer
        if prompt_cache is not None:
            self._llm_prompt_cache = prompt_cache

    def reconcile_epoch_validity_for_subject(
        self,
        *,
        subject_ref: core_contracts.ArtifactRef,
    ) -> (
        core_contracts.PersistedEpochValidityGateEvidence
        | core_contracts.EpochValidityGateNonReceipt
    ):
        """Delegate one pre-N9 gate to the exact container-owned runtime."""

        return self._promotion_runtime.epoch_validity_gate.reconcile_before_n9(
            subject_ref=subject_ref
        )

    def run_published_signature_custody_maintenance(
        self,
    ) -> PublishedSignatureCustodyResult:
        """Run the container-composed published-signature watcher without an HTTP request."""

        return self._published_signature_custody_watcher.scan_once()

    def _run_control_worker_maintenance(self) -> PublishedSignatureCustodyResult:
        """Run custody maintenance and retry durable HTE validity deliveries."""
        result = self.run_published_signature_custody_maintenance()
        self.reconcile_pending_completed_hte_source_validity_events()
        self.reconcile_pending_search_hte_completion_events()
        return result

    def _dispatch_search_hte_completion_for_job(self, *, job_id: str) -> None:
        """Best-effort delivery after a durable HTE completion has committed."""
        try:
            event = self._control_store.get_job_terminal_source_event_record(job_id)
            if event.event_type != "job_completed":
                return
            delivery = self._control_store.get_search_hte_completion_outbox_event(
                job_id=job_id,
                completed_event_id=event.event_id,
            )
            if delivery is not None and delivery.state == "pending":
                self._deliver_search_hte_completion_outbox(delivery)
        except Exception:
            logger.exception("Search HTE completion dispatch read failed for %s", job_id)

    def reconcile_pending_search_hte_completion_events(self) -> int:
        """Retry one page bounded by a frozen delivery watermark.

        A retry cycle never chases arrivals created while it is running. Failed
        rows remain pending and are revisited when the next cycle starts at the
        beginning of the durable Search-only sequence.
        """
        page_size = 25
        cursor = self._search_hte_outbox_cursor
        watermark = self._search_hte_outbox_watermark
        try:
            if watermark is None:
                watermark = self._control_store.get_search_hte_completion_delivery_watermark()
                cursor = 0
            page = self._control_store.list_pending_search_hte_completion_delivery_page(
                limit=page_size,
                after_sequence_id=cursor if cursor is not None else 0,
                through_sequence_id=watermark,
            )
        except Exception:
            logger.exception("Search HTE completion outbox page read failed")
            self._search_hte_outbox_cursor = None
            self._search_hte_outbox_watermark = None
            return 0
        if not page:
            self._search_hte_outbox_cursor = None
            self._search_hte_outbox_watermark = None
            return 0
        acknowledged = 0
        for _, delivery in page:
            if self._deliver_search_hte_completion_outbox(delivery):
                acknowledged += 1
        if len(page) == page_size:
            self._search_hte_outbox_cursor = page[-1][0]
            self._search_hte_outbox_watermark = watermark
        else:
            self._search_hte_outbox_cursor = None
            self._search_hte_outbox_watermark = None
        return acknowledged

    def _deliver_search_hte_completion_outbox(self, delivery_record: ControlOutboxRecord) -> bool:
        """Content-reconcile and acknowledge only the Search-specific outbox row."""
        from pydantic import TypeAdapter

        from polisyos.core.contracts.runtime import (
            RuntimeSearchHTECompletionDeliveryV1,
            _validate_strict_json_wire_payload,
        )

        def leave_pending(reason_code: str) -> bool:
            try:
                self._control_store.record_outbox_delivery_failure(
                    event_id=delivery_record.event_id,
                    reason_code=reason_code,
                )
            except Exception:
                logger.exception(
                    "Search HTE outbox failure receipt could not be retained for %s",
                    delivery_record.event_id,
                )
            return False

        if (
            delivery_record.topic != "control.search.hte_completed"
            or delivery_record.state != "pending"
            or not delivery_record.job_id
        ):
            return leave_pending("search_hte_outbox_identity_not_established")
        try:
            payload = _validate_strict_json_wire_payload(
                delivery_record.payload,
                TypeAdapter(RuntimeSearchHTECompletionDeliveryV1),
                invalid_code="search_hte_outbox_payload_invalid",
            )
        except Exception:
            return leave_pending("search_hte_outbox_payload_invalid")
        if (
            payload.job_id != delivery_record.job_id
            or payload.run_id != delivery_record.run_id
            or delivery_record.event_key
            != f"{payload.job_id}:job_completed:{payload.completed_event_id}"
        ):
            return leave_pending("search_hte_outbox_payload_owner_mismatch")
        if self._artifact_store_backend != "filesystem":
            return leave_pending("search_hte_backend_not_established")

        try:
            scope = self._control_store.historical_completed_job_execution_scope(
                job_id=payload.job_id,
                expected_run_id=payload.run_id,
            )
            if scope.status != "established" or not scope.tenant_id:
                return leave_pending("search_hte_execution_scope_not_established")
            from polisyos.core.artifacts.manifest import artifact_ref_identity_key
            from polisyos.core.contracts.owned_attempt_anchor import (
                OwnedAttemptAnchorAssociation,
            )
            from polisyos.core.security import tenant_scope
            from polisyos.runtime.quality.hte_source_projection import (
                verify_hte_source_projection_join,
            )
            from polisyos.scientist.methods.search.uncertainty import (
                SearchUncertaintyCompletionReceipt,
                consume_owned_hte_completion,
            )

            owner_failure_reason: str | None = None
            receipt: SearchUncertaintyCompletionReceipt | None = None
            with tenant_scope(
                None,
                tenant_id=scope.tenant_id,
                cell_id=scope.cell_id,
            ):
                owner_association = self.resolve_historical_completed_method_execution(
                    job_id=payload.job_id,
                    completed_event_id=payload.completed_event_id,
                    tenant_id=scope.tenant_id,
                    cell_id=scope.cell_id,
                )
                if (
                    type(owner_association) is not OwnedAttemptAnchorAssociation
                    or owner_association.status != "owner_selection_reconciled"
                    or owner_association.job_id != payload.job_id
                    or owner_association.run_id != payload.run_id
                    or owner_association.attempt != payload.attempt
                    or owner_association.job_completed_event.event_id != payload.completed_event_id
                    or owner_association.job_completed_event.event_type != "job_completed"
                    or owner_association.job_completed_event.payload_sha256
                    != payload.completed_event_payload_sha256
                ):
                    owner_failure_reason = "search_hte_owner_completion_not_established"
                else:
                    binding_ref = owner_association.search_uncertainty_task_binding_ref
                    if binding_ref is None or artifact_ref_identity_key(
                        binding_ref
                    ) != artifact_ref_identity_key(payload.search_uncertainty_task_binding_ref):
                        owner_failure_reason = "search_hte_owner_binding_not_established"
                    else:
                        receipt = consume_owned_hte_completion(
                            store=self._require_search_uncertainty_store(),
                            owner=self,
                            binding_ref=binding_ref,
                            owner_association=owner_association,
                            source_projection_verifier=verify_hte_source_projection_join,
                        )
            if owner_failure_reason is not None:
                return leave_pending(owner_failure_reason)
        except Exception:
            logger.exception(
                "Search HTE completion receiver failed for job %s event %s",
                payload.job_id,
                payload.completed_event_id,
            )
            return leave_pending("search_hte_receiver_not_established")
        if (
            type(receipt) is not SearchUncertaintyCompletionReceipt
            or receipt.schema_version != "1.0"
            or receipt.job_id != payload.job_id
            or receipt.completed_event_id != payload.completed_event_id
        ):
            return leave_pending("search_hte_receiver_receipt_invalid")
        if receipt.status not in {"admitted", "already_admitted"}:
            reason_code = receipt.reason_code or "search_hte_receiver_not_established"
            return leave_pending(reason_code)
        try:
            self._control_store.mark_outbox_published(event_id=delivery_record.event_id)
            published = self._control_store.get_outbox_event(delivery_record.event_id)
        except Exception:
            logger.exception(
                "Search HTE delivery acknowledgement failed for %s",
                delivery_record.event_id,
            )
            return False
        return published is not None and published.state == "published"

    async def compile_and_run_recursive_generation_cycle(
        self,
        *,
        raw_request: str,
        context: Mapping[str, object],
        model_name: str,
        trusted_source_context: Mapping[str, object | None] | None = None,
        execution_intent: ExecutionIntent | None = None,
        joint_interaction_candidate_intent: Literal["n4_unique_parent_source_members.v1"]
        | None = None,
        n4_proposal_only: bool = False,
        n4_proposal_only_origin: Literal["explicit", "derived_legacy_default"] = "explicit",
        producer_run_id: str | None = None,
        producer_run_binding: BudgetLedgerProducerRunBinding | None = None,
        compiler_gateway: _DesignProblemGatewayClient | None,
        budget_state: BudgetState,
        recursive_budget: RecursiveCycleBudget,
        recursive_budget_resolution: RecursiveBudgetResolution | None = None,
        target_world_scope_profile_id: str | None = None,
        cycle_substrate_context_resolver: Callable[[DesignProblem], object | None] | None = None,
        candidate_simulation_currentness_resolver: Callable[[], bool] | None = None,
        generic_cycle_simulation_handoff_resolver: (
            Callable[[DesignProblem], GenericCycleSimulationContextHandoffV1 | None] | None
        ) = None,
        generic_cycle_simulation_currentness_resolver: Callable[[], bool] | None = None,
        verified_nl_job_scope: VerifiedNLJobScope | None = None,
        n4_recursive_source: GenerationUnderAResult | None = None,
        recursive_leaf_context_owner: RecursiveLeafContextOwner | None = None,
        root_evaluation_context: EvaluationExecutionContext | None = None,
        measurement_root_execution_binding: MeasurementRootExecutionBinding | None = None,
    ) -> (
        CompiledRecursiveGenerationCycleRun
        | N4CandidateProposalExecution
        | N4CandidateScenarioProposalOnlyExecution
    ):
        """Run the HTTP composition through its container-owned epoch strangle."""

        from polisyos.runtime.http.services.control.generation_cycle import (
            compile_and_run_recursive_generation_cycle,
        )
        from polisyos.runtime.quality.generation_source import (
            GenerationSourceRepository,
        )
        from polisyos.runtime.quality.substrate_registry import (
            run_catalog_source_awaitable,
        )

        producer_budget_reconciler = None
        if producer_run_binding is not None:
            if producer_run_id != producer_run_binding.run_id:
                from polisyos.runtime.quality.generation_cycle import (
                    GenerationCycleError,
                )

                raise GenerationCycleError("control_nl_budget_run_id_binding_mismatch")
            settlement_store = self._llm_producer_settlement_store
            if settlement_store is None:
                from polisyos.runtime.quality.generation_cycle import (
                    GenerationCycleError,
                )

                raise GenerationCycleError("control_nl_budget_settlement_store_not_established")
            producer_budget_reconciler = _build_control_nl_producer_budget_reconciler(
                settlement_store=settlement_store,
                producer_run_binding=producer_run_binding,
                budget_state=budget_state,
            )

        return await run_catalog_source_awaitable(
            self._catalog_serving_source,
            compile_and_run_recursive_generation_cycle(
                raw_request=raw_request,
                context=context,
                trusted_source_context=trusted_source_context,
                model_name=model_name,
                execution_intent=execution_intent,
                joint_interaction_candidate_intent=joint_interaction_candidate_intent,
                n4_proposal_only=n4_proposal_only,
                n4_proposal_only_origin=n4_proposal_only_origin,
                producer_run_id=producer_run_id,
                producer_settlement_store=self._llm_producer_settlement_store,
                _producer_budget_reconciler=producer_budget_reconciler,
                compiler_gateway=compiler_gateway,
                budget_state=budget_state,
                recursive_budget=recursive_budget,
                recursive_budget_resolution=recursive_budget_resolution,
                target_world_scope_profile_id=target_world_scope_profile_id,
                catalog_run_profile=self._catalog_run_profile,
                catalog_serving_source=self._catalog_serving_source,
                cycle_substrate_context_resolver=cycle_substrate_context_resolver,
                candidate_simulation_currentness_resolver=(
                    candidate_simulation_currentness_resolver
                ),
                generic_cycle_simulation_admission_owner=(
                    self._generic_cycle_simulation_admission_owner
                    if generic_cycle_simulation_handoff_resolver is not None
                    else None
                ),
                generic_cycle_simulation_handoff_resolver=(
                    generic_cycle_simulation_handoff_resolver
                ),
                enable_contract_testing_credal_source_attempts=(
                    self._enable_contract_testing_credal_source_attempts
                ),
                generic_cycle_simulation_currentness_resolver=(
                    generic_cycle_simulation_currentness_resolver
                ),
                verified_nl_job_scope=verified_nl_job_scope,
                n4_recursive_source=n4_recursive_source,
                generation_source_repository=GenerationSourceRepository(self._artifact_store),
                recursive_leaf_context_owner=recursive_leaf_context_owner,
                root_evaluation_context=root_evaluation_context,
                measurement_root_execution_binding=measurement_root_execution_binding,
                eval_safety_verifier=self._evaluation_safety_admission_verifier,
                promotion_runtime=self._promotion_runtime,
                repo_root=self._repo_root,
            ),
        )

    @property
    def step_up_replay_store(self) -> StepUpReplayStore:
        """Expose the narrow durable one-use assertion store."""
        return cast("StepUpReplayStore", self._control_store)

    def resolve_generation_value_choices(
        self,
        *,
        compiled_run_ref: str,
        evidence: NormativeRunEvidenceRefs | None = None,
        evaluated_at: datetime,
        compiled_artifact_ref: ArtifactRef | None = None,
    ) -> NormativeRunDisposition:
        """Persist and replay current source-bound S8 choices through the deployment owner."""
        from polisyos.runtime.http.services.control.generation_cycle import (
            normative_owner_for_runtime_store,
            produce_normative_run_disposition,
        )

        owner = normative_owner_for_runtime_store(
            self._artifact_store,
            self._normative_authority_trust,
            signature_verifier=self._promotion_runtime.signature_verifier,
            repo_root=self._repo_root,
        )
        return produce_normative_run_disposition(
            store=self._artifact_store,
            owner=owner,
            compiled_run_ref=compiled_run_ref,
            evidence=evidence,
            evaluated_at=evaluated_at,
            compiled_artifact_ref=compiled_artifact_ref,
        )

    def _normative_owned_job_source(
        self, record: ControlJobRecord
    ) -> tuple[ArtifactRef, ArtifactRef]:
        """Bind outputs to the completed job's exact lease-attempt Core trace."""
        from polisyos.core.artifacts.manifest import artifact_ref_identity_key

        if record.run_id is None or record.payload_ref is None:
            raise ValueError("normative_evidence_job_run_missing")
        payload = self._load_payload_ref(
            record.payload_ref,
            kind=f"runtime.control_job_payload.{record.kind}",
        )
        tenant_id = payload.get("tenant_id") if isinstance(payload, Mapping) else None
        cell_id = payload.get("cell_id") if isinstance(payload, Mapping) else None
        if (
            not isinstance(tenant_id, str)
            or not tenant_id.strip()
            or not isinstance(cell_id, str)
            or not cell_id.strip()
            or payload.get("run_id") != record.run_id
        ):
            raise ValueError("normative_evidence_job_scope_not_established")
        terminal = load_completed_control_job_core_run_source(
            store=self._artifact_store,
            core_runs_root=self._core_runs_root,
            job=record,
            expected_control_run_id=record.run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        outputs = terminal.manifest.outputs
        compiled = [
            ref for ref in outputs if ref.kind == "runtime.compiled_recursive_generation_cycle"
        ]
        normative = [
            ref for ref in outputs if ref.kind == "runtime.normative_generation_composition"
        ]
        if (
            terminal.manifest.status != "ok"
            or len(outputs) != 2
            or len(compiled) != 1
            or len(normative) != 1
        ):
            raise ValueError("normative_evidence_owned_run_source_mismatch")
        progress = record.progress
        try:
            selected_compiled = ArtifactRef.model_validate(
                progress.get("compiled_recursive_generation_cycle_artifact_ref")
            )
            selected_normative = ArtifactRef.model_validate(
                progress.get("normative_disposition_artifact_ref")
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("normative_evidence_owned_output_ref_not_established") from exc
        if (
            artifact_ref_identity_key(selected_compiled) != artifact_ref_identity_key(compiled[0])
            or artifact_ref_identity_key(selected_normative)
            != artifact_ref_identity_key(normative[0])
            or progress.get("compiled_recursive_generation_cycle_ref")
            != str(compiled[0].artifact_id)
            or progress.get("normative_disposition_ref") != str(normative[0].artifact_id)
        ):
            raise ValueError("normative_evidence_owned_output_selection_mismatch")
        return selected_compiled, selected_normative

    def resolve_completed_control_job_core_run_source(
        self,
        job: ControlJobRecord,
        *,
        expected_control_run_id: str,
        tenant_id: str,
        cell_id: str,
    ) -> TerminalCoreRunSource:
        """Resolve a completed job through its exact lease-attempt Core owner."""
        return load_completed_control_job_core_run_source(
            store=self._artifact_store,
            core_runs_root=self._core_runs_root,
            job=job,
            expected_control_run_id=expected_control_run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )

    def submit_normative_evidence(
        self,
        *,
        run_id: str,
        submission: NormativeEvidenceSubmissionRequest,
        request_id: str | None = None,
    ) -> NormativeEvidenceSubmissionResponse:
        """Admit post-source evidence for the exact owned job and atomically attach its head."""
        from polisyos.runtime.http.services.control.generation_cycle import (
            NORMATIVE_GENERATION_HEAD_KIND,
            NORMATIVE_GENERATION_HEAD_SCHEMA,
            NormativeEvidenceHeadStrangleReceipt,
            NormativeEvidenceSubmissionResponse,
            NormativeGenerationHead,
            NormativeRunEvidenceRefs,
        )

        record = self._control_store.get_job(submission.job_id)
        if record is None or record.run_id != run_id:
            raise ValueError("normative_evidence_job_run_mismatch")
        if record.kind != "natural_language_run" or record.state != "completed":
            raise ValueError("normative_evidence_job_not_completed")
        compiled_artifact_ref, original_artifact_ref = self._normative_owned_job_source(record)
        compiled_ref = str(compiled_artifact_ref.artifact_id)
        original_ref = str(original_artifact_ref.artifact_id)
        now = datetime.now(UTC)
        evidence = submission.evidence
        if compiled_ref != record.progress.get("compiled_recursive_generation_cycle_ref"):
            evidence = NormativeRunEvidenceRefs(
                input_limitation="p20_normative_sidecar_replay_failed"
            )
        disposition = self.resolve_generation_value_choices(
            compiled_run_ref=compiled_ref,
            evidence=evidence,
            evaluated_at=now,
            compiled_artifact_ref=compiled_artifact_ref,
        )
        if disposition.disposition_ref is None:
            raise RuntimeError("normative_evidence_disposition_not_persisted")
        status: Literal["admitted", "refused", "conflict"] = "refused"
        if disposition.authorization_status == "authorized":
            head = NormativeGenerationHead(
                job_id=record.job_id,
                run_id=run_id,
                compiled_run_ref=compiled_ref,
                previous_head_ref=submission.expected_prior_head_ref,
                disposition_ref=disposition.disposition_ref,
                evidence=submission.evidence,
                evaluated_at=now,
                strangle_receipt=NormativeEvidenceHeadStrangleReceipt(
                    original_disposition_ref=original_ref,
                    current_disposition_ref=disposition.disposition_ref,
                ),
            )
            persisted_head = self._artifact_store.put_json(
                head.model_dump(mode="json"),
                ArtifactWriteOptions(
                    kind=NORMATIVE_GENERATION_HEAD_KIND,
                    media_type="application/json",
                    schema=SchemaInfo(
                        name=NORMATIVE_GENERATION_HEAD_KIND,
                        version=NORMATIVE_GENERATION_HEAD_SCHEMA,
                    ),
                ),
            )
            head_ref = str(persisted_head.artifact_id)
            status = (
                "admitted"
                if self._control_store.append_normative_evidence_head(
                    job_id=record.job_id,
                    run_id=run_id,
                    compiled_run_ref=compiled_ref,
                    expected_prior_head_ref=submission.expected_prior_head_ref,
                    head_ref=head_ref,
                )
                else "conflict"
            )
        if status != "admitted":
            self._control_store.append_event(
                job_id=record.job_id,
                event_type="normative_evidence_" + status,
                payload={
                    "job_id": record.job_id,
                    "run_id": run_id,
                    "compiled_run_ref": compiled_ref,
                    "expected_prior_head_ref": submission.expected_prior_head_ref,
                    "attempted_disposition_ref": disposition.disposition_ref,
                    "evidence": submission.evidence.model_dump(mode="json"),
                    "evaluated_at": now.isoformat(),
                },
            )
        current = self._current_normative_job_record(record)
        return NormativeEvidenceSubmissionResponse(
            status=status,
            head_ref=current.progress.get("normative_head_ref"),
            attempted_disposition_ref=disposition.disposition_ref,
            job=current.to_response(request_id=request_id),
        )

    def _current_normative_generation_projection(
        self,
        *,
        disposition_ref: str | None,
        compiled_run_ref: str | None,
        disposition_artifact_ref: ArtifactRef | None = None,
        compiled_artifact_ref: ArtifactRef | None = None,
        evaluated_at: datetime,
        refusal_reason: str | None = None,
    ) -> dict[str, object]:
        from polisyos.runtime.http.services.control.generation_cycle import (
            NormativeRunEvidenceRefs,
            normative_owner_for_runtime_store,
            project_normative_run_disposition,
        )

        try:
            if refusal_reason is not None:
                raise P20NormativeChoiceError(refusal_reason)
            if disposition_ref is None or compiled_run_ref is None:
                raise P20NormativeChoiceError("p20_normative_generation_disposition_missing")
            owner = normative_owner_for_runtime_store(
                self._artifact_store,
                self._normative_authority_trust,
                signature_verifier=self._promotion_runtime.signature_verifier,
                repo_root=self._repo_root,
            )
            return project_normative_run_disposition(
                store=self._artifact_store,
                owner=owner,
                disposition_ref=disposition_ref,
                compiled_run_ref=compiled_run_ref,
                evaluated_at=evaluated_at,
                disposition_artifact_ref=disposition_artifact_ref,
                compiled_artifact_ref=compiled_artifact_ref,
            ).model_dump(mode="json")
        except (ValueError, TypeError, OSError, KeyError) as exc:
            reason = (
                str(exc)
                if isinstance(exc, P20NormativeChoiceError)
                else "p20_normative_current_replay_unavailable"
            )
            if compiled_run_ref is not None:
                try:
                    refusal = self.resolve_generation_value_choices(
                        compiled_run_ref=compiled_run_ref,
                        evidence=NormativeRunEvidenceRefs(
                            input_limitation=(
                                "p20_normative_generation_disposition_missing"
                                if disposition_ref is None and refusal_reason is None
                                else "p20_normative_sidecar_replay_failed"
                            )
                        ),
                        evaluated_at=evaluated_at,
                        compiled_artifact_ref=compiled_artifact_ref,
                    )
                    return {
                        **refusal.model_dump(mode="json"),
                        "refusal_disposition_ref": refusal.disposition_ref,
                        "reason_codes": [reason],
                    }
                except ValueError, TypeError, OSError, KeyError:
                    pass
            return {
                "authorization_status": "blocked",
                "ranked_recommendations": [],
                "reason_codes": [reason],
                "source_status": "not_established",
                "candidate_fronts": None,
            }

    @property
    def human_decision_sink(self) -> HumanDecisionAuthoritySink:
        """Expose only the custodied human-decision persistence boundary."""

        return self._human_decision_sink

    @property
    def acquisition_route_sink(self) -> AcquisitionRouteLoopAuthoritySink:
        """Expose the sole durable acquisition action-head authority."""

        return self._acquisition_route_sink

    def bind_acquisition_job_handler(
        self,
        handler: Callable[
            [ControlJobRecord, dict[str, Any], ControlJobExecutionScope],
            dict[str, Any],
        ],
    ) -> None:
        """Bind one container-composed acquisition worker bridge."""

        if not callable(handler):
            raise TypeError("acquisition job handler must be callable")
        if self._acquisition_job_handler is not None:
            raise RuntimeError("acquisition job handler is already bound")
        self._acquisition_job_handler = handler

    def enqueue_acquisition_job(
        self,
        *,
        job_id: str,
        run_id: str,
        payload: dict[str, Any],
        request_id: str | None = None,
        principal: RuntimePrincipal | None = None,
    ) -> ControlJobRecord:
        """Persist one deterministic acquisition payload and queue it for the generic worker."""

        existing = self._control_store.get_job(job_id)
        if existing is not None:
            if existing.kind != "acquisition" or existing.run_id != run_id:
                raise RuntimeError("acquisition_job_identity_conflict")
            return existing
        policy = self._resolve_execution_policy(
            requested_profile=None,
            policy_flags=PolicyFlags(),
            principal=principal,
        )
        return self._enqueue_job(
            job_id=job_id,
            job_kind="acquisition",
            run_id=run_id,
            pipeline_id=None,
            payload=payload,
            policy=policy,
            request_id=request_id,
        )

    @property
    def execution_policy_resolver(self) -> RuntimeExecutionPolicyResolver:
        """Expose the policy owner needed by container-only capability composition."""
        return self._policy_resolver

    def bind_capability_discovery_service(self, service: CapabilityDiscoveryService) -> None:
        """Bind the sole container-composed discovery owner once."""
        if self._capability_discovery_service is not None:
            raise RuntimeError("capability discovery service is already bound")
        for provider in self._registry_providers.capability_discovery_providers:
            bind_artifact_store = getattr(provider, "bind_artifact_store", None)
            if callable(bind_artifact_store):
                bind_artifact_store(self._artifact_store)
        self._capability_discovery_service = service

    def close(self) -> None:
        """Stop embedded workers and release durable control-plane resources."""
        if self._worker is not None:
            self._worker.stop()
        retrieval_catalog_close = cast(
            "Callable[[], None] | None", getattr(self._retrieval_catalog, "close", None)
        )
        if callable(retrieval_catalog_close):
            retrieval_catalog_close()
        control_store_close = cast(
            "Callable[[], None] | None", getattr(self._control_store, "close", None)
        )
        artifact_store_close = cast(
            "Callable[[], None] | None", getattr(self._artifact_store, "close", None)
        )
        if self._owns_control_store and callable(control_store_close):
            control_store_close()
        if self._owns_artifact_store and callable(artifact_store_close):
            artifact_store_close()

    def _resolve_control_sqlite_path(self) -> Path:
        path = Path(self._policy_resolver.sqlite_path)
        if path.is_absolute():
            return path
        return self._cas_root.parent / path

    def _build_retrieval_providers(self) -> RetrievalProviders:
        from polisyos.fabric.retrieval import RetrievalProviders

        return RetrievalProviders(
            registry=cast("ConnectorRegistry", self._registry_providers.connectors),
            profiles=cast("SourceProfileRegistry", self._registry_providers.source_profiles),
            tracer=self._tracer,
            metrics=self._metrics,
        )

    def _resolve_execution_policy(
        self,
        *,
        requested_profile: ExecutionProfile | None,
        policy_flags: PolicyFlags,
        principal: RuntimePrincipal | None,
    ) -> ResolvedExecutionPolicy:
        try:
            policy = self._policy_resolver.resolve(
                requested_profile=requested_profile,
                policy_flags=policy_flags,
                principal=principal,
            )
            self._validate_policy_runtime_compatibility(policy)
            return policy
        except ExecutionProfileError as exc:
            raise unprocessable_entity(str(exc), code=exc.code) from exc
        except PolicyFlagForbiddenError as exc:
            raise forbidden(str(exc), code=exc.code) from exc

    def _validate_policy_runtime_compatibility(
        self,
        policy: ResolvedExecutionPolicy,
    ) -> None:
        if policy.external_worker_required and self._policy_resolver.worker_backend != "external":
            raise ExecutionProfileError(
                "durable_worker_required",
                (
                    f"Execution profile {policy.effective_profile!r} requires "
                    "POLISYOS_CONTROL_WORKER_BACKEND=external."
                ),
            )
        if policy.postgres_required and self._policy_resolver.state_store_backend != "postgres":
            raise ExecutionProfileError(
                "durable_state_store_required",
                (
                    f"Execution profile {policy.effective_profile!r} requires a "
                    "PostgreSQL-backed control-plane state store."
                ),
            )
        if policy.postgres_required and not self._policy_resolver.postgres_dsn:
            raise ExecutionProfileError(
                "durable_state_store_required",
                (
                    f"Execution profile {policy.effective_profile!r} requires "
                    "POLISYOS_CONTROL_POSTGRES_DSN."
                ),
            )

    def _put_json_artifact(
        self,
        payload: object,
        *,
        kind: str,
        schema_name: str,
        schema_version: str = "1.0",
    ) -> str:
        return str(
            self._put_json_artifact_ref(
                payload,
                kind=kind,
                schema_name=schema_name,
                schema_version=schema_version,
            ).artifact_id
        )

    def _put_json_artifact_ref(
        self,
        payload: object,
        *,
        kind: str,
        schema_name: str,
        schema_version: str = "1.0",
        tenant_context: ArtifactTenantContextInfo | None = None,
        governance: ArtifactGovernanceInfo | None = None,
        inputs: list[ArtifactRef] | None = None,
        input_roles: tuple[str, ...] | None = None,
    ) -> ArtifactRef:
        """Persist JSON and retain the exact store-selected manifest view."""
        if inputs:
            if input_roles is None or len(input_roles) != len(inputs):
                raise ValueError("runtime_artifact_input_roles_mismatch")
            manifest_inputs = [
                input_ref_from_artifact_ref(reference, role=role)
                for reference, role in zip(inputs, input_roles, strict=True)
            ]
        else:
            if input_roles not in (None, ()):
                raise ValueError("runtime_artifact_input_roles_mismatch")
            manifest_inputs = None
        artifact_ref = self._artifact_store.put_json(
            payload,
            ArtifactWriteOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(name=schema_name, version=schema_version),
                inputs=manifest_inputs,
                governance=governance,
                tenant_context=tenant_context,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        if tenant_context is not None:
            record_owner = getattr(self._artifact_store, "record_artifact_owner", None)
            if not callable(record_owner):
                raise RuntimeError("tenant_scoped_artifact_owner_record_unavailable")
            record_owner(
                artifact_ref.artifact_id,
                tenant_id=tenant_context.tenant_id,
                cell_id=tenant_context.cell_id,
                writer="runtime.control.run_lifecycle",
            )
        return artifact_ref

    def _persist_job_payload(
        self,
        *,
        job_kind: str,
        payload: dict[str, Any],
    ) -> str:
        schema_version = (
            "1.1"
            if job_kind == "natural_language_run" and "target_world_scope_profile_id" in payload
            else "1.0"
        )
        return self._put_json_artifact(
            payload,
            kind=f"runtime.control_job_payload.{job_kind}",
            schema_name="polisyos.runtime.ControlJobPayload",
            schema_version=schema_version,
        )

    def _build_job_telemetry(self, *, request_id: str | None) -> dict[str, Any] | None:
        telemetry: dict[str, Any] = {}
        if request_id:
            telemetry["request_id"] = request_id
        telemetry["runtime_trace"] = {
            "trace_id": f"trace_{uuid.uuid4().hex}",
            "span_id": f"span_{uuid.uuid4().hex[:16]}",
            "parent_span_id": None,
        }
        carrier: dict[str, str] = {}
        inject_context = getattr(self._tracer, "inject_context", None)
        if callable(inject_context):
            inject_context(carrier)
        if carrier:
            telemetry["trace_context"] = carrier
        return telemetry or None

    def _enrich_job_payload(
        self,
        payload: dict[str, Any],
        *,
        request_id: str | None,
    ) -> dict[str, Any]:
        enriched_payload = dict(payload)
        telemetry = self._build_job_telemetry(request_id=request_id)
        if telemetry is not None:
            enriched_payload["_telemetry"] = telemetry
        return enriched_payload

    def _job_trace_context(
        self,
        *,
        job_id: str,
        payload: Mapping[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> dict[str, str | None]:
        telemetry = payload.get("_telemetry") if isinstance(payload, Mapping) else None
        runtime_trace = telemetry.get("runtime_trace") if isinstance(telemetry, Mapping) else None
        trace_id = None
        span_id = None
        stored_parent_span_id = None
        if isinstance(runtime_trace, Mapping):
            trace_id = runtime_trace.get("trace_id")
            span_id = runtime_trace.get("span_id")
            stored_parent_span_id = runtime_trace.get("parent_span_id")
        return {
            "trace_id": str(trace_id or f"trace_{job_id}"),
            "span_id": f"span_{uuid.uuid4().hex[:16]}",
            "parent_span_id": str(parent_span_id or span_id or stored_parent_span_id or "") or None,
        }

    @staticmethod
    def _execution_scope_payload(scope: ControlJobExecutionScope) -> dict[str, Any]:
        """Serialize the typed route identity for the existing job-created owner event."""
        return {
            "schema_version": "polisyos.runtime.control_execution_scope.v1",
            "status": scope.status,
            "tenant_id": scope.tenant_id,
            "cell_id": scope.cell_id,
            "actor_subject": scope.actor_subject,
            "actor_authenticated": scope.actor_authenticated,
            "actor_roles": list(scope.actor_roles),
        }

    @staticmethod
    def _job_created_event_payload(
        *,
        job_id: str,
        job_kind: str,
        run_id: str | None,
        pipeline_id: str | None,
        payload_ref: str | None,
        submitted_by: str | None,
        requested_execution_profile: str | None,
        effective_execution_profile: str,
        policy_flags: Mapping[str, Any],
        capability_manifest_ref: str | None,
        execution_scope: ControlJobExecutionScope,
    ) -> dict[str, Any]:
        """Build the complete immutable stable envelope stored with the creation event."""
        return {
            "job_id": job_id,
            "run_id": run_id,
            "job_kind": job_kind,
            "pipeline_id": pipeline_id,
            "payload_ref": payload_ref,
            "submitted_by": submitted_by,
            "requested_execution_profile": requested_execution_profile,
            "effective_execution_profile": effective_execution_profile,
            "policy_flags": dict(policy_flags),
            "capability_manifest_ref": capability_manifest_ref,
            "execution_scope": ControlPlaneService._execution_scope_payload(execution_scope),
        }

    def _bootstrap_observational_method_registration(
        self,
    ) -> tuple[Any, dict[str, _RuntimeObservationalMethodRegistration]]:
        """Register and pin only the supported versions of one HTE method family.

        Registry metadata is resolved during Runtime composition. This does not
        scan entry points or import estimator dependencies; each worker later
        resolves the exact FQN/version frozen into the durable intent.
        """
        from polisyos.foundry.methods.catalog.causal.forest_dr import (
            ForestDRLearnerEstimator,
            ForestDRLearnerEstimatorV11,
        )
        from polisyos.foundry.methods.catalog.causal.hte_v2 import (
            CausalForestEstimatorV2,
            DoubleMachineLearningV2,
            ForestDRLearnerEstimatorV2,
            MetaLearnerEstimatorV2,
        )
        from polisyos.foundry.methods.selection.registry import MethodRegistry

        registry = MethodRegistry.get_instance()
        registrations: dict[str, _RuntimeObservationalMethodRegistration] = {}
        method_classes = (
            ForestDRLearnerEstimator,
            ForestDRLearnerEstimatorV11,
            CausalForestEstimatorV2,
            DoubleMachineLearningV2,
            MetaLearnerEstimatorV2,
            ForestDRLearnerEstimatorV2,
        )
        for method_class in method_classes:
            signature = method_class.signature
            if (
                signature.fqn.rpartition("@")[0] not in _OBSERVATIONAL_METHOD_BASE_FQNS
                or signature.fqn != f"{signature.fqn.rpartition('@')[0]}@{signature.version}"
            ):
                raise RuntimeError("observational_method_startup_fqn_mismatch")
            successor_profile = _OBSERVATIONAL_METHOD_V2_RESOURCE_PROFILE.get(signature.fqn)
            if successor_profile is not None and (
                getattr(method_class, "owned_hte_method_fqn", None) != signature.fqn
                or getattr(method_class, "owned_hte_method_abi", None) != signature.version
                or getattr(method_class, "owned_hte_profile_id", None) != successor_profile[0]
                or not callable(getattr(method_class, "pure_step_with_runtime_context", None))
            ):
                raise RuntimeError("observational_method_startup_hte_runtime_context_invalid")
            existing_signature = registry.get_signature(signature.fqn)
            if existing_signature is None:
                registry.register(method_class)
            elif (
                existing_signature.fqn != signature.fqn
                or existing_signature.version != signature.version
                or existing_signature.abi_digest() != signature.abi_digest()
            ):
                raise RuntimeError("observational_method_startup_registry_conflict")
            try:
                registered_class = registry.get(signature.fqn, version=signature.version)
            except Exception as exc:
                raise RuntimeError("observational_method_startup_registration_unavailable") from exc
            if registered_class is not method_class:
                raise RuntimeError("observational_method_startup_class_conflict")
            try:
                source = inspect.getsource(registered_class).encode("utf-8")
            except (OSError, TypeError) as exc:
                raise RuntimeError("observational_method_startup_build_not_established") from exc
            registrations[signature.fqn] = _RuntimeObservationalMethodRegistration(
                method_class=registered_class,
                signature=signature,
                build_digest=hashlib.sha256(source).hexdigest(),
                contract_target=_OBSERVATIONAL_METHOD_CONTRACT_TARGET,
                n_jobs_parameter=(
                    _OBSERVATIONAL_METHOD_N_JOBS_PARAMETER
                    if successor_profile is None or successor_profile[2] == 1
                    else None
                ),
                method_profile_id=successor_profile[0] if successor_profile else None,
                execution_scope=successor_profile[1] if successor_profile else None,
            )
        if set(registrations) != {
            _OBSERVATIONAL_METHOD_FQN_V1_0,
            _OBSERVATIONAL_METHOD_FQN_V1_1,
            *_OBSERVATIONAL_METHOD_FQN_V2,
        }:
            raise RuntimeError("observational_method_supported_registration_set_invalid")
        return registry, registrations

    def _resolve_observational_method_registration(
        self,
        *,
        fqn: str,
        version: str | None,
    ) -> _RuntimeObservationalMethodRegistration:
        """Resolve exact or latest registry metadata once, before durable acceptance."""
        from polisyos.foundry.methods.selection.resolution import (
            ResolutionError,
            ResolutionPolicy,
            resolve_version,
        )

        if "@" in fqn:
            requested_base, separator, embedded_version = fqn.rpartition("@")
            if not separator or not embedded_version:
                raise ValueError("observational_method_fqn_invalid")
            if version is not None and version != embedded_version:
                raise ValueError("observational_method_version_conflict")
            requested_version = embedded_version
        else:
            requested_base = fqn
            requested_version = version
        if requested_base not in _OBSERVATIONAL_METHOD_BASE_FQNS:
            raise ValueError("observational_method_registration_not_supported")
        available_versions = self._method_registry.list_versions(requested_base)
        policy = (
            ResolutionPolicy.EXACT if requested_version is not None else ResolutionPolicy.LATEST
        )
        try:
            resolved_version = resolve_version(
                available_versions,
                requested_version,
                policy,
            )
        except (ResolutionError, TypeError, ValueError) as exc:
            raise ValueError("observational_method_registration_not_available") from exc
        resolved_fqn = f"{requested_base}@{resolved_version}"
        registration = self._observational_method_registrations.get(resolved_fqn)
        live_signature = self._method_registry.get_signature(resolved_fqn)
        if (
            registration is None
            or live_signature is None
            or live_signature.fqn != registration.signature.fqn
            or live_signature.version != registration.signature.version
            or live_signature.abi_digest() != registration.signature.abi_digest()
        ):
            raise ValueError("observational_method_registration_not_supported")
        return registration

    def _require_observational_method_resource_profile(
        self,
        registration: _RuntimeObservationalMethodRegistration,
        resolved_params: Mapping[str, object],
        *,
        resource_policy: _ObservationalInputResourcePolicy | None = None,
    ) -> None:
        """Require the exact method identity to meet its selected Runtime profile."""
        policy = resource_policy or self._resource_policy_for_registration(registration)
        if registration.signature.fqn in _OBSERVATIONAL_METHOD_FQN_V2:
            profile = _OBSERVATIONAL_METHOD_V2_RESOURCE_PROFILE.get(registration.signature.fqn)
            if (
                policy.revision != "r5"
                or policy.schema_version
                != "polisyos.runtime.observational_input_resource_policy.v5"
                or policy.method_contract_target != registration.contract_target
                or policy.method_fqn != registration.signature.fqn
                or profile is None
                or registration.method_profile_id != profile[0]
                or registration.execution_scope != profile[1]
                or policy.method_profile_id != profile[0]
                or policy.execution_scope != profile[1]
                or policy.required_estimator_n_jobs != profile[2]
                or policy.max_jobs != 1
                or registration.n_jobs_parameter != ("n_jobs" if profile[2] == 1 else None)
            ):
                raise ValueError("observational_method_resource_profile_not_supported")
            parameters = {item.name: item for item in registration.signature.parameters}
            if profile[2] == 1:
                parameter = parameters.get("n_jobs")
                if (
                    parameter is None
                    or type(parameter.default) is not int
                    or parameter.default != 1
                    or parameter.bounds != (1, 1)
                    or type(resolved_params.get("n_jobs")) is not int
                    or resolved_params.get("n_jobs") != 1
                ):
                    raise ValueError("observational_method_resource_profile_not_supported")
            return
        if (
            policy.revision not in {"r2", "r3"}
            or policy.method_contract_target != registration.contract_target
            or policy.required_estimator_n_jobs != 1
            or registration.n_jobs_parameter != _OBSERVATIONAL_METHOD_N_JOBS_PARAMETER
        ):
            raise ValueError("observational_method_resource_profile_not_supported")
        parameter_specs = [
            parameter
            for parameter in registration.signature.parameters
            if parameter.name == registration.n_jobs_parameter
        ]
        if len(parameter_specs) != 1:
            raise ValueError("observational_method_resource_profile_not_supported")
        parameter = parameter_specs[0]
        lower, upper = parameter.bounds
        selected_value = resolved_params.get(registration.n_jobs_parameter)
        if (
            type(parameter.default) is not int
            or parameter.default != policy.required_estimator_n_jobs
            or type(lower) is not int
            or lower != policy.required_estimator_n_jobs
            or type(upper) is not int
            or upper != policy.required_estimator_n_jobs
            or type(selected_value) is not int
            or selected_value != policy.required_estimator_n_jobs
        ):
            raise ValueError("observational_method_resource_profile_not_supported")

    def _resource_policy_for_registration(
        self,
        registration: _RuntimeObservationalMethodRegistration,
    ) -> _ObservationalInputResourcePolicy:
        """Build the selected versioned resource policy for one registered method."""
        from polisyos.core.contracts.runtime import ObservationalInputResourcePolicy

        profile = _OBSERVATIONAL_METHOD_V2_RESOURCE_PROFILE.get(registration.signature.fqn)
        if profile is None:
            return self._observational_resource_policy
        wait_policy = self._observational_resource_policy.method_execution_wait_policy
        if wait_policy is None:
            raise ValueError("observational_method_wait_policy_not_established")
        return ObservationalInputResourcePolicy.model_validate(
            {
                "schema_version": "polisyos.runtime.observational_input_resource_policy.v5",
                "revision": "r5",
                "method_contract_target": registration.contract_target,
                "required_estimator_n_jobs": profile[2],
                "method_execution_wait_policy": wait_policy,
                "method_fqn": registration.signature.fqn,
                "method_profile_id": profile[0],
                "execution_scope": profile[1],
                "max_jobs": 1,
            },
            strict=True,
        )

    def _observational_read_limits(self) -> CoreJsonReadLimits:
        """Build the exact Core reader limits from the immutable Runtime policy."""
        from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits

        policy = self._observational_resource_policy
        return CoreJsonReadLimits(
            max_bytes=policy.max_bytes,
            max_depth=policy.max_depth,
            max_elements=policy.max_elements,
            max_manifest_bytes=policy.max_manifest_bytes,
        )

    def _require_core_bounded_member_reader(
        self, *, limits: CoreJsonReadLimits
    ) -> CoreJSONArtifactBoundedMemberReader:
        """Require the configured handle's exact bounded selected-member read port."""
        from polisyos.core.artifacts.protocol import CoreJSONArtifactBoundedMemberReader

        return _require_bounded_store_protocol(
            self._artifact_store,
            CoreJSONArtifactBoundedMemberReader,
            limits=limits,
            refusal_code="canon_profile_bounded_stream_unavailable",
            failure_stage="bounded_member_open_preflight",
        )

    def _require_core_bounded_manifest_reader(
        self, *, limits: CoreJsonReadLimits
    ) -> CoreJSONArtifactBoundedManifestReceiptReader:
        """Require the configured handle's exact bounded manifest-receipt port."""
        from polisyos.core.artifacts.protocol import (
            CoreJSONArtifactBoundedManifestReceiptReader,
        )

        return _require_bounded_store_protocol(
            self._artifact_store,
            CoreJSONArtifactBoundedManifestReceiptReader,
            limits=limits,
            refusal_code="canon_profile_bounded_manifest_unavailable",
            failure_stage="selected_manifest_reader_preflight",
        )

    def _require_search_uncertainty_store(self) -> SearchUncertaintyStore:
        """Narrow the actual configured CAS owner for Search's live ticket reads."""
        from polisyos.core.artifacts.protocol import matches_runtime_protocol
        from polisyos.scientist.methods.search.uncertainty import SearchUncertaintyStore

        store = _configured_core_read_owner(self._artifact_store)
        if matches_runtime_protocol(store, SearchUncertaintyStore):
            return store
        raise TypeError("search_uncertainty_store_contract_unavailable")

    def _require_owned_attempt_anchor_bounded_store(
        self, *, limits: CoreJsonReadLimits
    ) -> _OwnedAttemptAnchorArtifactStore:
        """Require the configured owner implementing the bounded Core read ports.

        The constructor remains open to the supported ArtifactStore family. This
        accessor narrows only the owned-attempt Core read path after the caller has
        validated its selected reference. Only the exact known Core-to-IR forwarding
        adapter is resolved to its configured owner; a guarded owner inside it stays
        intact, and arbitrary facades or subclasses must provide the read ports.
        """
        from polisyos.core.artifacts.canonical_profile import (
            CoreJsonReadBoundsRefusalError,
        )
        from polisyos.core.artifacts.protocol import (
            CoreJSONArtifactBoundedManifestReader,
            CoreJSONArtifactBoundedManifestReceiptReader,
            CoreJSONArtifactBoundedMemberReader,
            CoreJSONArtifactStreamingReader,
            matches_runtime_protocol,
            runtime_protocol_requirements,
        )
        from polisyos.runtime.http.services.control.owned_attempt_anchor import (
            _OwnedAttemptAnchorArtifactStore,
        )

        def refuse(code: str, *, stage: str) -> CoreJsonReadBoundsRefusalError:
            return CoreJsonReadBoundsRefusalError(
                code,
                limits=limits,
                max_manifest_bytes=limits.max_manifest_bytes,
                observed_manifest_bytes=0,
                observed_manifest_selection_bytes=0,
                observed_manifest_verification_bytes=0,
                observed_bytes=0,
                observed_depth=0,
                observed_elements=0,
                source_usage_complete=True,
                failure_stage=stage,
            )

        protocol_owner = _configured_core_read_owner(self._artifact_store)
        if matches_runtime_protocol(protocol_owner, _OwnedAttemptAnchorArtifactStore):
            return protocol_owner

        def missing_protocol_members(protocol: type[Any]) -> list[str]:
            missing: list[str] = []
            for name, callable_required in runtime_protocol_requirements(protocol).items():
                try:
                    member = getattr(protocol_owner, name)
                except AttributeError:
                    missing.append(name)
                    continue
                if callable_required and not callable(member):
                    missing.append(name)
            return sorted(missing)

        missing_manifest_members = sorted(
            set(missing_protocol_members(CoreJSONArtifactBoundedManifestReceiptReader))
            | set(missing_protocol_members(CoreJSONArtifactBoundedManifestReader))
        )
        if missing_manifest_members:
            raise refuse(
                "canon_profile_bounded_manifest_unavailable",
                stage="selected_manifest_reader_preflight",
            )

        bounded_member_protocol = CoreJSONArtifactBoundedMemberReader
        bounded_member_members = set(runtime_protocol_requirements(bounded_member_protocol))
        streaming_members = set(runtime_protocol_requirements(CoreJSONArtifactStreamingReader))
        receipt_members = set(
            runtime_protocol_requirements(CoreJSONArtifactBoundedManifestReceiptReader)
        )
        bounded_member_open_members = bounded_member_members - streaming_members - receipt_members
        missing_member_members = set(missing_protocol_members(bounded_member_protocol))
        if bounded_member_open_members & missing_member_members:
            raise refuse(
                "canon_profile_bounded_stream_unavailable",
                stage="bounded_member_open_preflight",
            )

        missing_members = missing_protocol_members(_OwnedAttemptAnchorArtifactStore)
        mismatch_detail = ",".join(missing_members) or "composite_protocol_unmatched"
        mismatch = TypeError("owned_attempt_store_protocol_missing_members:" + mismatch_detail)
        raise refuse(
            "owned_attempt_store_contract_unavailable",
            stage="bounded_store_protocol_preflight",
        ) from mismatch

    def _read_observational_source_manifest(
        self,
        source_ref: ArtifactRef,
        *,
        expected_sha256: str | None = None,
    ) -> tuple[
        CoreJsonManifestBoundedRead, ArtifactGovernanceInfo, ArtifactTenantContextInfo | None, str
    ]:
        """Bound-read one selected source manifest and require raw explicit governance."""
        from polisyos.core.artifacts import read_core_manifest_profile_bounded
        from polisyos.runtime.http.services.control.owned_attempt_anchor import (
            _require_full_profile_ref,
        )

        source_ref = _require_full_profile_ref(
            source_ref,
            code="observational_source_selected_profile_required",
        )
        limits = self._observational_read_limits()
        bounded = read_core_manifest_profile_bounded(
            self._require_core_bounded_manifest_reader(limits=limits),
            source_ref,
            max_manifest_bytes=limits.max_manifest_bytes,
        )
        if not _same_selected_artifact_ref(bounded.effective_ref, source_ref):
            raise ValueError("observational_source_selected_profile_drift")
        manifest = bounded.manifest
        if (
            manifest.kind != source_ref.kind
            or manifest.media_type != "application/json"
            or artifact_ref_for_manifest(manifest).manifest_profile_sha256
            != source_ref.manifest_profile_sha256
        ):
            raise ValueError("observational_source_manifest_identity_mismatch")
        typed_governance, tenant_context, manifest_sha256 = _explicit_source_manifest_metadata(
            raw_manifest_bytes=bounded.raw_manifest_bytes,
            typed_governance=manifest.governance,
            tenant_context=manifest.tenant_context,
            expected_sha256=expected_sha256,
        )
        return bounded, typed_governance, tenant_context, manifest_sha256

    def _resolve_search_uncertainty_binding(
        self,
        *,
        binding_ref: ArtifactRef,
        tenant_id: str,
        cell_id: str | None,
        request_context: _OwnedHTERequestContextV1,
        method_fqn: str,
        method_version: str,
        method_abi_digest: str,
        resolved_params: Mapping[str, object],
        seed: int,
        inference_profile_id: str,
        selected_method_input_ref: ArtifactRef,
        selected_method_input_content_sha256: str,
        admitted_snapshot: SearchUncertaintyTaskAdmissionSnapshot | None = None,
    ) -> SearchUncertaintyTaskAdmissionSnapshot:
        """Reconcile the POST snapshot with Runtime request and worker pins."""
        from polisyos.core.contracts.runtime import SearchUncertaintyTaskAdmissionSnapshot
        from polisyos.runtime.http.services.control.owned_attempt_anchor import (
            _require_full_profile_ref,
        )
        from polisyos.scientist.methods.search.uncertainty import (
            SearchUncertaintyHTERequestProjection,
            SearchUncertaintyTaskBindingResolution,
            resolve_admitted_search_uncertainty_task_binding,
            resolve_current_search_uncertainty_task_binding,
        )

        binding_ref = _require_full_profile_ref(
            binding_ref,
            code="search_task_binding_runtime_selection_invalid",
        )
        selected_method_input_ref = _require_full_profile_ref(
            selected_method_input_ref,
            code="search_task_binding_runtime_selection_invalid",
        )
        request_binding_ref = request_context.search_uncertainty_task_binding_ref
        if (
            binding_ref.kind != "scientist.search.uncertainty_task_binding"
            or binding_ref.media_type != "application/json"
            or binding_ref.manifest_profile_sha256 is None
            or request_binding_ref is None
            or not _same_selected_artifact_ref(binding_ref, request_binding_ref)
            or not tenant_id
            or type(method_fqn) is not str
            or not method_fqn.endswith("@" + method_version)
            or type(method_abi_digest) is not str
            or len(method_abi_digest) != 64
            or any(character not in "0123456789abcdef" for character in method_abi_digest)
            or type(seed) is not int
            or seed < 0
            or selected_method_input_ref.manifest_profile_sha256 is None
            or selected_method_input_ref.artifact_id.hex != selected_method_input_content_sha256
        ):
            raise ValueError("search_task_binding_runtime_selection_invalid")
        if (
            request_context.request_estimand_status != "declared"
            or request_context.request_target_scope_status != "declared"
            or request_context.outcome_variable_status != "declared"
            or request_context.treatment_variable_status != "declared"
            or request_context.contrast_status != "declared"
            or request_context.request_alpha_status != "declared"
        ):
            raise ValueError("search_task_binding_request_context_not_established")
        request_payload: dict[str, object] = {
            "estimand": request_context.request_estimand,
            "target_scope": request_context.request_target_scope,
            "outcome_variable_id": request_context.outcome_variable_id,
            "treatment_variable_id": request_context.treatment_variable_id,
            "control_value": request_context.control_value,
            "treated_value": request_context.treated_value,
            "alpha": request_context.requested_alpha,
        }
        if request_context.requested_guarantee_status == "declared":
            request_payload["requested_guarantee"] = request_context.requested_guarantee
        request_projection = SearchUncertaintyHTERequestProjection.model_validate(request_payload)
        params_bytes = json.dumps(
            dict(resolved_params),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        params_sha256 = hashlib.sha256(params_bytes).hexdigest()
        selected_method_fqn = TypeAdapter(
            Literal[
                "causal.hte.causal_forest@2.0.0",
                "causal.hte.double_ml@2.0.0",
                "causal.hte.meta_learner@2.0.0",
                "causal.hte.forest_dr@2.0.0",
            ]
        ).validate_python(method_fqn, strict=True)
        selected_method_abi_version = TypeAdapter(Literal["2.0.0"]).validate_python(
            method_version,
            strict=True,
        )
        selected_inference_profile_id = TypeAdapter(
            Literal[
                "econml.causal_forest_dml.native_mean@2.0",
                "econml.dml.point_only@2.0",
                "econml.meta_learner.point_only@2.0",
                "econml.forest_dr.native_mean@2.0",
            ]
        ).validate_python(inference_profile_id, strict=True)
        selected_method_params = TypeAdapter(dict[str, JsonValue]).validate_python(
            dict(resolved_params),
            strict=True,
        )
        search_store = self._require_search_uncertainty_store()
        if admitted_snapshot is None:
            resolution = resolve_current_search_uncertainty_task_binding(
                store=search_store,
                binding_ref=binding_ref,
                tenant_id=tenant_id,
                cell_id=cell_id,
                request_projection=request_projection,
                selected_method_fqn=selected_method_fqn,
                selected_method_abi_version=selected_method_abi_version,
                selected_method_abi_digest=method_abi_digest,
                selected_method_params=selected_method_params,
                selected_method_params_sha256=params_sha256,
                selected_method_seed=seed,
                selected_inference_profile_id=selected_inference_profile_id,
                selected_input_ref=selected_method_input_ref,
                selected_input_sha256=selected_method_input_content_sha256,
            )
        else:
            if type(
                admitted_snapshot
            ) is not SearchUncertaintyTaskAdmissionSnapshot or not _same_selected_artifact_ref(
                admitted_snapshot.binding_ref, binding_ref
            ):
                raise ValueError("search_task_binding_admitted_snapshot_ref_mismatch")
            resolution = resolve_admitted_search_uncertainty_task_binding(
                store=search_store,
                binding_ref=binding_ref,
                expected_ticket_id=admitted_snapshot.ticket_id,
                expected_ticket_generation=admitted_snapshot.ticket_generation,
                expected_owner_revision=admitted_snapshot.owner_revision,
                expected_projection_revision=admitted_snapshot.projection_revision,
                expected_projection_ref=admitted_snapshot.source_projection_ref,
                expected_task_admission_ref=admitted_snapshot.task_admission_ref,
                expected_task_epoch_ref=admitted_snapshot.task_epoch_ref,
                expected_owner_context_ref=admitted_snapshot.owner_context_ref,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
                owned_historical_attempt_association_resolver=(
                    self.resolve_owned_attempt_anchor_association
                ),
            )
        if type(resolution) is not SearchUncertaintyTaskBindingResolution:
            raise TypeError("search_task_binding_resolution_type_invalid")
        binding = resolution.binding
        allowed_resolution_statuses = (
            {"current"} if admitted_snapshot is None else {"current", "historical"}
        )
        if (
            resolution.schema_version != "1.0"
            or resolution.resolution_status not in allowed_resolution_statuses
            or resolution.closure_status != "recomputed"
            or not _same_selected_artifact_ref(resolution.binding_ref, binding_ref)
            or resolution.tenant_id != tenant_id
            or resolution.cell_id != cell_id
            or binding.request_projection != request_projection
            or binding.selected_method_fqn != method_fqn
            or binding.selected_method_abi_version != method_version
            or binding.selected_method_abi_digest != method_abi_digest
            or binding.selected_method_params != dict(resolved_params)
            or binding.selected_method_params_sha256 != params_sha256
            or binding.selected_method_seed != seed
            or binding.selected_inference_profile_id != inference_profile_id
            or not _same_selected_artifact_ref(
                binding.selected_method_input_ref,
                selected_method_input_ref,
            )
            or binding.selected_method_input_content_sha256 != selected_method_input_content_sha256
        ):
            raise ValueError("search_task_binding_runtime_reconciliation_mismatch")
        resolved_snapshot = SearchUncertaintyTaskAdmissionSnapshot(
            binding_ref=ArtifactRef.model_validate(binding_ref.model_dump(mode="json")),
            binding_content_sha256=resolution.binding_content_sha256,
            ticket_id=resolution.ticket_id,
            ticket_generation=resolution.ticket_generation,
            owner_revision=resolution.owner_revision,
            projection_revision=resolution.projection_revision,
            projection_ref=ArtifactRef.model_validate(
                resolution.projection_ref.model_dump(mode="json")
            ),
            task_admission_ref=ArtifactRef.model_validate(
                resolution.task_admission_ref.model_dump(mode="json")
            ),
            task_epoch_ref=ArtifactRef.model_validate(
                resolution.task_epoch_ref.model_dump(mode="json")
            ),
            owner_context_ref=ArtifactRef.model_validate(
                resolution.owner_context_ref.model_dump(mode="json")
            ),
            basis_ref=ArtifactRef.model_validate(resolution.basis_ref.model_dump(mode="json")),
            dependency_inventory_ref=ArtifactRef.model_validate(
                resolution.dependency_inventory_ref.model_dump(mode="json")
            ),
            dependency_inventory_sha256=resolution.dependency_inventory_sha256,
            source_projection_ref=ArtifactRef.model_validate(
                resolution.source_projection_ref.model_dump(mode="json")
            ),
            selected_method_fqn=selected_method_fqn,
            selected_method_abi_version=selected_method_abi_version,
            selected_method_abi_digest=method_abi_digest,
            selected_method_params=selected_method_params,
            selected_method_params_sha256=params_sha256,
            selected_method_seed=seed,
            selected_inference_profile_id=selected_inference_profile_id,
            selected_method_input_ref=ArtifactRef.model_validate(
                selected_method_input_ref.model_dump(mode="json")
            ),
            selected_method_input_content_sha256=selected_method_input_content_sha256,
            tenant_id=tenant_id,
            cell_id=cell_id,
            resolved_at=resolution.resolved_at,
            resolution_status="current",
            closure_status="recomputed",
        )
        if admitted_snapshot is None:
            return resolved_snapshot
        if resolved_snapshot.model_dump(mode="python", exclude={"resolved_at"}) != (
            admitted_snapshot.model_dump(mode="python", exclude={"resolved_at"})
        ):
            raise ValueError("search_task_binding_admitted_snapshot_drift")
        return admitted_snapshot

    @staticmethod
    def _resolve_observational_method_params(
        signature: _MethodSignatureProtocol,
        submitted: Mapping[str, object],
    ) -> dict[str, JsonValue]:
        """Resolve only declared parameter names and defaults from the pinned signature."""
        specs = {spec.name: spec for spec in signature.parameters}
        if len(specs) != len(signature.parameters) or any(
            type(name) is not str or not name for name in specs
        ):
            raise ValueError("observational_method_parameter_contract_invalid")
        if any(type(name) is not str or name not in specs for name in submitted):
            raise ValueError("observational_method_parameter_unknown")
        resolved = {name: spec.default for name, spec in specs.items()}
        for name, value in submitted.items():
            spec = specs[name]
            default = spec.default
            if value is None:
                if default is not None:
                    raise ValueError(f"observational_method_parameter_type_invalid:{name}")
            elif type(default) is bool:
                if type(value) is not bool:
                    raise ValueError(f"observational_method_parameter_type_invalid:{name}")
            elif type(default) is int:
                if type(value) is not int:
                    raise ValueError(f"observational_method_parameter_type_invalid:{name}")
            elif type(default) is float:
                if type(value) is int:
                    numeric_value: int | float = value
                elif type(value) is float:
                    numeric_value = value
                else:
                    raise ValueError(f"observational_method_parameter_type_invalid:{name}")
                if not math.isfinite(float(numeric_value)):
                    raise ValueError(f"observational_method_parameter_type_invalid:{name}")
            elif type(default) is str:
                if type(value) is not str:
                    raise ValueError(f"observational_method_parameter_type_invalid:{name}")
            elif default is None:
                raise ValueError(f"observational_method_parameter_type_not_established:{name}")
            else:
                raise ValueError(f"observational_method_parameter_type_not_established:{name}")
            lower, upper = spec.bounds
            if lower is not None or upper is not None:
                if type(value) is int:
                    bounded_value: int | float = value
                elif type(value) is float:
                    bounded_value = value
                else:
                    raise ValueError(f"observational_method_parameter_bounds_invalid:{name}")
                if not math.isfinite(float(bounded_value)):
                    raise ValueError(f"observational_method_parameter_bounds_invalid:{name}")
                if (lower is not None and bounded_value < lower) or (
                    upper is not None and bounded_value > upper
                ):
                    raise ValueError(f"observational_method_parameter_bounds_invalid:{name}")
            resolved[name] = value
        try:
            resolved_json = json.dumps(
                resolved, ensure_ascii=False, allow_nan=False, sort_keys=True
            )
            normalized = json.loads(resolved_json)
        except (TypeError, ValueError) as exc:
            raise ValueError("observational_method_parameters_not_json") from exc
        if not isinstance(normalized, dict):
            raise ValueError("observational_method_parameters_not_json")
        return TypeAdapter(dict[str, JsonValue]).validate_python(normalized, strict=True)

    def _launch_observational_workflow_run(
        self,
        request: WorkflowRunRequest,
        *,
        run_id: str,
        job_id: str,
        policy: ResolvedExecutionPolicy,
        request_id: str | None,
        principal: RuntimePrincipal | None,
    ) -> RunLaunchResponse:
        """Persist selected source/method pins, then enqueue a refs-only direct job."""
        from polisyos.core.contracts.runtime import (
            ObservationalRunIntent,
            _observational_intent_manifest_identity,
        )
        from polisyos.ir.observation import ContractCompatibilityTarget

        selection = request.observational_input
        if selection is None or request.mode != "workflow":
            raise unprocessable_entity(
                "observational_input_requires_workflow_mode",
                code="observational_input_mode_invalid",
            )
        if request.params:
            raise unprocessable_entity(
                "Top-level workflow parameters cannot accompany observational_input.",
                code="observational_input_top_level_params_conflict",
            )
        from polisyos.core.artifacts.canonical_profile import (
            CoreJsonReadBoundsRefusalError,
        )

        try:
            (
                bounded_manifest,
                source_governance,
                source_tenant,
                source_manifest_sha256,
            ) = self._read_observational_source_manifest(selection.source_ref)
        except CoreJsonReadBoundsRefusalError as exc:
            # Core wraps an exact owner-access denial in its bounded-read refusal. Preserve
            # that typed access boundary; other bounded, integrity, and profile refusals
            # keep the established 422 admission response.
            bounded_read_error = exc.__cause__
            owner_error = (
                bounded_read_error.original_exception
                if isinstance(bounded_read_error, artifacts.ArtifactBoundedManifestReadError)
                else bounded_read_error
            )
            if type(owner_error) is artifacts.ArtifactOwnershipError:
                raise forbidden(
                    "Current tenant access to the selected observation manifest "
                    "is not established.",
                    code="observational_source_current_access_not_established",
                ) from exc
            raise unprocessable_entity(
                "Selected observation manifest is not admissible for bounded method input.",
                code="observational_source_manifest_not_admitted",
            ) from exc
        except Exception as exc:
            raise unprocessable_entity(
                "Selected observation manifest is not admissible for bounded method input.",
                code="observational_source_manifest_not_admitted",
            ) from exc
        manifest = bounded_manifest.manifest
        expected_kind = (
            "ir.observation_method_input"
            if selection.protocol == "method_input_envelope_v1"
            else "ir.observational_data"
        )
        if manifest.kind != expected_kind:
            raise unprocessable_entity(
                "Selected observation kind does not match the declared protocol.",
                code="observational_source_kind_mismatch",
            )
        if selection.protocol == "method_input_envelope_v1":
            if manifest.artifact_schema != SchemaInfo(
                name="polisyos.ir.ObservationMethodInputEnvelope",
                version="1.0",
            ):
                raise unprocessable_entity(
                    "Selected method-input envelope schema does not match the declared protocol.",
                    code="observational_source_schema_mismatch",
                )
        elif manifest.artifact_schema is not None:
            raise unprocessable_entity(
                "Legacy observational JSON must not assert an artifact schema.",
                code="observational_source_schema_mismatch",
            )

        try:
            registration = self._resolve_observational_method_registration(
                fqn=selection.method.fqn,
                version=selection.method.version,
            )
        except (TypeError, ValueError) as exc:
            code = str(exc) or "observational_method_registration_not_available"
            raise unprocessable_entity(
                "The requested method does not resolve to a supported exact registration.",
                code=code,
            ) from exc
        signature = registration.signature
        submitted_present = "params" in selection.method.model_fields_set
        submitted_params = dict(selection.method.params or {})
        try:
            resolved_params = self._resolve_observational_method_params(
                signature,
                submitted_params,
            )
        except (TypeError, ValueError) as exc:
            raise unprocessable_entity(
                "Submitted method parameters do not resolve against the selected method contract.",
                code="observational_method_parameters_invalid",
            ) from exc
        is_successor = registration.signature.fqn in _OBSERVATIONAL_METHOD_FQN_V2
        if is_successor:
            from polisyos.core.contracts.control import ObservationalHTERequestV2

            hte_request = selection.hte_request
            if type(hte_request) is not ObservationalHTERequestV2:
                raise unprocessable_entity(
                    "Version-two HTE methods require an immutable version-two estimand request.",
                    code="observational_hte_request_v2_required",
                )
            if "alpha" in submitted_params:
                if resolved_params.get("alpha") != hte_request.alpha:
                    raise unprocessable_entity(
                        "Submitted method alpha conflicts with immutable HTE request alpha.",
                        code="observational_hte_method_alpha_conflict",
                    )
            else:
                try:
                    request_params = self._resolve_observational_method_params(
                        signature,
                        {"alpha": hte_request.alpha},
                    )
                except (TypeError, ValueError) as exc:
                    raise unprocessable_entity(
                        "The selected HTE method does not admit the immutable request alpha.",
                        code="observational_hte_request_alpha_not_admitted",
                    ) from exc
                resolved_params["alpha"] = request_params["alpha"]
        resource_policy = self._resource_policy_for_registration(registration)
        try:
            self._require_observational_method_resource_profile(
                registration,
                resolved_params,
                resource_policy=resource_policy,
            )
        except ValueError as exc:
            raise unprocessable_entity(
                "The exact selected method does not meet Runtime's declared resource profile.",
                code="observational_method_resource_profile_not_supported",
            ) from exc

        try:
            _require_public_candidate_source(source_governance, source_tenant)
        except ValueError as exc:
            raise forbidden(
                "Asynchronous candidate execution requires an unscoped public observation.",
                code="observational_source_current_access_not_established",
            ) from exc
        resource_policy_digest = resource_policy.digest()
        resource_policy_ref = self._put_json_artifact_ref(
            resource_policy.model_dump(mode="json"),
            kind="runtime.observational_input_resource_policy",
            schema_name="polisyos.runtime.ObservationalInputResourcePolicy",
            schema_version="1.0",
            governance=source_governance,
            tenant_context=source_tenant,
            inputs=[selection.source_ref],
            input_roles=("requested_source",),
        )
        if resource_policy_ref.manifest_profile_sha256 is None:
            raise RuntimeError("observational_resource_policy_profile_not_established")
        selected_resource_policy = _read_observational_resource_policy_artifact(
            store=self._require_core_bounded_member_reader(
                limits=self._observational_read_limits()
            ),
            policy_ref=resource_policy_ref,
            source_ref=selection.source_ref,
            source_governance=source_governance,
            source_tenant_context=source_tenant,
            limits=self._observational_read_limits(),
        )
        if (
            selected_resource_policy != resource_policy
            or selected_resource_policy.digest() != resource_policy_digest
        ):
            raise RuntimeError("observational_resource_policy_readback_mismatch")
        contract_target = ContractCompatibilityTarget(
            contract_id=_OBSERVATIONAL_METHOD_CONTRACT_TARGET_ID,
            contract_fqn=_OBSERVATIONAL_METHOD_CONTRACT_TARGET,
        )
        contract_target_id = TypeAdapter(
            Literal["foundry.causal.hte_observational_data.v1"]
        ).validate_python(contract_target.contract_id, strict=True)
        contract_target_fqn = TypeAdapter(
            Literal["polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"]
        ).validate_python(contract_target.contract_fqn, strict=True)
        owned_hte_request_context = None
        search_binding_tenant_id = None
        search_binding_cell_id = None
        search_binding_admission = None
        if is_successor:
            from polisyos.core.contracts.control import ObservationalHTERequestV2
            from polisyos.core.contracts.owned_attempt_anchor import OwnedHTERequestContextV1

            hte_request = selection.hte_request
            if type(hte_request) is not ObservationalHTERequestV2:
                raise unprocessable_entity(
                    "Version-two HTE methods require an immutable version-two estimand request.",
                    code="observational_hte_request_v2_required",
                )
            binding_ref = hte_request.search_uncertainty_task_binding_ref
            selected_binding_ref = None
            if binding_ref is not None:
                from polisyos.core.contracts.owned_attempt_anchor import SelectedArtifactRef

                if binding_ref.manifest_profile_sha256 is None:
                    raise unprocessable_entity(
                        "The Search-owned HTE binding must select its manifest profile.",
                        code="search_task_binding_profile_not_established",
                    )
                selected_binding_ref = SelectedArtifactRef.model_validate(
                    binding_ref.model_dump(mode="json"),
                    strict=True,
                )
            owned_hte_request_context = OwnedHTERequestContextV1(
                request_estimand_status="declared",
                request_estimand=hte_request.estimand,
                request_target_scope_status="declared",
                request_target_scope=hte_request.target_scope,
                outcome_variable_status="declared",
                outcome_variable_id=hte_request.outcome_variable_id,
                treatment_variable_status="declared",
                treatment_variable_id=hte_request.treatment_variable_id,
                contrast_status="declared",
                control_value=float(hte_request.control_value),
                treated_value=float(hte_request.treated_value),
                request_alpha_status="declared",
                requested_alpha=hte_request.alpha,
                requested_guarantee_status=(
                    "declared" if hte_request.requested_guarantee is not None else "not_established"
                ),
                requested_guarantee=hte_request.requested_guarantee,
                search_uncertainty_task_binding_ref=selected_binding_ref,
            )
            if hte_request.search_uncertainty_task_binding_ref is not None:
                if (
                    principal is None
                    or principal.authenticated is not True
                    or principal.fixture_identity is True
                    or type(principal.tenant_id) is not str
                    or not principal.tenant_id
                    or type(principal.cell_id) is not str
                    or not principal.cell_id
                ):
                    raise forbidden(
                        "Search-bound method execution requires an authenticated tenant and cell.",
                        code="search_task_binding_runtime_scope_not_established",
                    )
                search_binding_tenant_id = principal.tenant_id
                search_binding_cell_id = principal.cell_id
                inference_profile_id = resource_policy.method_profile_id
                if inference_profile_id is None:
                    raise unprocessable_entity(
                        "The exact selected method has no admitted inference profile.",
                        code="search_task_binding_inference_profile_not_established",
                    )
                try:
                    search_binding_admission = self._resolve_search_uncertainty_binding(
                        binding_ref=hte_request.search_uncertainty_task_binding_ref,
                        tenant_id=search_binding_tenant_id,
                        cell_id=search_binding_cell_id,
                        request_context=owned_hte_request_context,
                        method_fqn=registration.signature.fqn,
                        method_version=registration.signature.version,
                        method_abi_digest=registration.signature.abi_digest(),
                        resolved_params=resolved_params,
                        seed=0,
                        inference_profile_id=inference_profile_id,
                        selected_method_input_ref=selection.source_ref,
                        selected_method_input_content_sha256=selection.source_ref.artifact_id.hex,
                    )
                except (TypeError, ValueError) as exc:
                    raise unprocessable_entity(
                        "The Search-owned HTE binding is not current for this exact request "
                        "and input.",
                        code="search_task_binding_request_not_current",
                    ) from exc
        intent = ObservationalRunIntent(
            schema_version=(
                "polisyos.runtime.observational_run_intent.v3"
                if search_binding_admission is not None
                else (
                    "polisyos.runtime.observational_run_intent.v2"
                    if is_successor
                    else "polisyos.runtime.observational_run_intent.v1"
                )
            ),
            job_id=job_id,
            run_id=run_id,
            requested_source_ref=selection.source_ref,
            source_manifest_sha256=source_manifest_sha256,
            protocol=selection.protocol,
            method_fqn=registration.signature.fqn,
            method_version=registration.signature.version,
            owned_hte_request_context=owned_hte_request_context,
            search_binding_admission=search_binding_admission,
            search_binding_tenant_id=search_binding_tenant_id,
            search_binding_cell_id=search_binding_cell_id,
            method_abi_digest=registration.signature.abi_digest(),
            method_build_digest=registration.build_digest,
            method_build_digest_scope="class_source_only",
            submitted_params_present=submitted_present,
            submitted_params=submitted_params,
            resolved_params=resolved_params,
            seed=0,
            seed_policy_revision="server_seed_zero_v1",
            resource_policy=resource_policy,
            resource_policy_ref=resource_policy_ref,
            contract_target_id=contract_target_id,
            contract_target_fqn=contract_target_fqn,
            resource_policy_digest=resource_policy_digest,
            source_governance=source_governance,
            source_tenant_context=source_tenant,
            source_access_revalidation_status=_OBSERVATIONAL_SOURCE_ACCESS_STATUS,
            limitations=(
                "candidate_input_not_external_truth",
                "scientific_validity_not_established",
                "units_and_context_not_established",
                "source_access_revalidation_not_established",
            ),
        )
        intent_input_edges = _observational_run_intent_input_edges(intent)
        intent_ref = self._put_json_artifact_ref(
            intent.artifact_payload(),
            kind="runtime.observational_run_intent",
            schema_name="polisyos.runtime.ObservationalRunIntent",
            schema_version=_observational_intent_manifest_identity(intent.schema_version)[2],
            governance=source_governance,
            tenant_context=source_tenant,
            inputs=[ref for ref, _role in intent_input_edges],
            input_roles=tuple(role for _ref, role in intent_input_edges),
        )
        if intent_ref.manifest_profile_sha256 is None:
            raise RuntimeError("observational_run_intent_profile_not_established")
        selection_digest = intent.selection_digest()
        state_payload: dict[str, Any] = {
            "run_id": run_id,
            "inputs": {},
            "params": {},
        }
        payload = {
            "run_id": run_id,
            "state_payload": state_payload,
            _OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY: {
                "requested_source_ref": selection.source_ref.model_dump(mode="json"),
                "observational_run_intent_ref": intent_ref.model_dump(mode="json"),
                "observational_selection_digest": selection_digest,
            },
        }
        self._enqueue_job(
            job_id=job_id,
            job_kind="workflow_run",
            run_id=run_id,
            pipeline_id=None,
            payload=payload,
            policy=policy,
            request_id=request_id,
        )
        return RunLaunchResponse(
            meta=_build_api_meta(request_id),
            status="accepted",
            run_id=run_id,
            job_id=job_id,
            effective_execution_profile=_typed_execution_profile(policy.effective_profile),
            message=f"Workflow run {run_id} accepted and queued for durable execution.",
            observational_run_intent_ref=intent_ref,
            observational_selection_digest=selection_digest,
            observational_method_fqn=TypeAdapter(
                Literal[
                    "causal.hte.forest_dr@1.0.0",
                    "causal.hte.forest_dr@1.1.0",
                    "causal.hte.causal_forest@2.0.0",
                    "causal.hte.double_ml@2.0.0",
                    "causal.hte.meta_learner@2.0.0",
                    "causal.hte.forest_dr@2.0.0",
                ]
            ).validate_python(registration.signature.fqn, strict=True),
            observational_contract_target_id=contract_target_id,
            observational_contract_target_fqn=contract_target_fqn,
        )

    def _read_bounded_intent_artifact_read(
        self, intent_ref: ArtifactRef
    ) -> CoreJsonArtifactBoundedRead:
        """Resolve and retain one full-profile bounded Core intent read."""
        from polisyos.core.artifacts import read_core_json_artifact_bounded
        from polisyos.core.contracts.runtime import _observational_intent_manifest_identity
        from polisyos.runtime.http.services.control.owned_attempt_anchor import (
            _require_full_profile_ref,
        )

        intent_ref = _require_full_profile_ref(
            intent_ref,
            code="observational_run_intent_selected_profile_required",
        )
        limits = self._observational_read_limits()
        result = read_core_json_artifact_bounded(
            self._require_core_bounded_member_reader(limits=limits),
            intent_ref,
            limits=limits,
        )
        if not _same_selected_artifact_ref(result.effective_ref, intent_ref):
            raise ValueError("observational_run_intent_selected_profile_drift")
        value = result.value
        if not isinstance(value, Mapping):
            raise ValueError("observational_run_intent_payload_not_object")
        try:
            payload = TypeAdapter(dict[str, JsonValue]).validate_python(value, strict=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("observational_run_intent_payload_not_json_object") from exc
        manifest = result.manifest
        payload_schema_version = payload.get("schema_version")
        if type(payload_schema_version) is not str:
            raise ValueError("observational_run_intent_schema_version_invalid")
        try:
            expected_kind, expected_name, expected_version = (
                _observational_intent_manifest_identity(payload_schema_version)
            )
        except ValueError:
            expected_kind = expected_name = expected_version = None
        if (
            expected_kind != intent_ref.kind
            or manifest.kind != intent_ref.kind
            or manifest.media_type != "application/json"
            or expected_name is None
            or expected_version is None
            or manifest.artifact_schema != SchemaInfo(name=expected_name, version=expected_version)
        ):
            raise ValueError("observational_intent_payload_manifest_version_mismatch")
        return result

    def _read_bounded_intent_artifact(self, intent_ref: ArtifactRef) -> dict[str, JsonValue]:
        """Return the JSON mapping view for callers that inspect generic intent fields."""
        bounded = self._read_bounded_intent_artifact_read(intent_ref)
        try:
            return TypeAdapter(dict[str, JsonValue]).validate_python(bounded.value, strict=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("observational_run_intent_payload_not_json_object") from exc

    def _read_bounded_intent_model(
        self,
        intent_ref: ArtifactRef,
        *,
        model: type[_BoundedArtifactModelT],
    ) -> _BoundedArtifactModelT:
        """Hydrate one persisted intent through Core's typed bounded JSON reader."""
        from polisyos.core.artifacts import validate_core_model_bounded_read

        return validate_core_model_bounded_read(
            model,
            self._read_bounded_intent_artifact_read(intent_ref),
        )

    def resolve_method_execution_admission(
        self, *, work: MethodExecutionWork
    ) -> MethodExecutionAdmission:
        """Resolve immutable intent and lease identity before input materialization."""
        from polisyos.core.contracts.runtime import (
            ObservationalInputResourcePolicy,
            ObservationalRunIntent,
            SearchUncertaintyTaskAdmissionSnapshot,
        )

        current = self._control_store.current_execution_job_admission()
        job = current.job
        if (
            job.kind != "workflow_run"
            or job.state != "running"
            or job.job_id != work.job_id
            or job.run_id != work.run_id
            or job.attempt != work.attempt
            or not job.lease_owner
        ):
            raise ControlJobLeaseLostError("observational_method_live_lease_mismatch")
        payload = self._load_payload_ref(
            self._require_control_job_payload_ref(job),
            kind="runtime.control_job_payload.workflow_run",
        )
        marker = payload.get(_OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY)
        if not isinstance(marker, Mapping):
            raise ValueError("observational_method_job_intent_missing")
        try:
            persisted_source_ref = ArtifactRef.model_validate(marker["requested_source_ref"])
            persisted_intent_ref = ArtifactRef.model_validate(
                marker["observational_run_intent_ref"]
            )
            persisted_selection_digest = marker["observational_selection_digest"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("observational_method_job_intent_malformed") from exc
        if not _same_selected_artifact_ref(
            persisted_source_ref,
            work.requested_source_ref,
        ) or not _same_selected_artifact_ref(
            persisted_intent_ref,
            work.observational_run_intent_ref,
        ):
            raise ValueError("observational_method_work_refs_not_job_bound")
        intent = self._read_bounded_intent_model(
            persisted_intent_ref,
            model=ObservationalRunIntent,
        )
        if (
            type(persisted_selection_digest) is not str
            or persisted_selection_digest != intent.selection_digest()
        ):
            raise ValueError("observational_method_job_selection_digest_mismatch")
        bounded_source, source_governance, source_tenant_context, source_manifest_sha256 = (
            self._read_observational_source_manifest(
                persisted_source_ref,
                expected_sha256=intent.source_manifest_sha256,
            )
        )
        if intent.resource_policy_ref is None:
            raise ValueError("observational_method_resource_policy_ref_missing")
        registration = self._observational_method_registrations.get(intent.method_fqn)
        if registration is None:
            raise ValueError("observational_method_registration_not_supported")
        expected_resource_policy = self._resource_policy_for_registration(registration)
        selected_resource_policy = _read_observational_resource_policy_artifact(
            store=self._require_core_bounded_member_reader(
                limits=self._observational_read_limits()
            ),
            policy_ref=intent.resource_policy_ref,
            source_ref=persisted_source_ref,
            source_governance=source_governance,
            source_tenant_context=source_tenant_context,
            limits=self._observational_read_limits(),
        )
        if (
            type(selected_resource_policy) is not ObservationalInputResourcePolicy
            or selected_resource_policy != intent.resource_policy
            or selected_resource_policy != expected_resource_policy
            or selected_resource_policy.digest() != intent.resource_policy_digest
        ):
            raise ValueError("observational_method_resource_policy_pin_drift")
        expected_kind = (
            "ir.observation_method_input"
            if intent.protocol == "method_input_envelope_v1"
            else "ir.observational_data"
        )
        try:
            _require_public_candidate_source(source_governance, source_tenant_context)
        except ValueError as exc:
            raise ValueError("observational_method_source_current_access_not_established") from exc
        if bounded_source.manifest.kind != expected_kind:
            raise ValueError("observational_method_source_kind_pin_drift")
        if intent.protocol == "method_input_envelope_v1":
            if bounded_source.manifest.artifact_schema != SchemaInfo(
                name="polisyos.ir.ObservationMethodInputEnvelope",
                version="1.0",
            ):
                raise ValueError("observational_method_source_schema_pin_drift")
        elif bounded_source.manifest.artifact_schema is not None:
            raise ValueError("observational_method_source_schema_pin_drift")
        if (
            registration is None
            or source_governance != intent.source_governance
            or source_tenant_context != intent.source_tenant_context
            or source_manifest_sha256 != intent.source_manifest_sha256
            or intent.job_id != job.job_id
            or intent.run_id != str(job.run_id or "")
            or not _same_selected_artifact_ref(
                intent.requested_source_ref,
                persisted_source_ref,
            )
            or intent.resource_policy_ref is None
            or intent.resource_policy_digest != expected_resource_policy.digest()
            or intent.resource_policy != expected_resource_policy
            or intent.contract_target_id != _OBSERVATIONAL_METHOD_CONTRACT_TARGET_ID
            or intent.contract_target_fqn != _OBSERVATIONAL_METHOD_CONTRACT_TARGET
            or intent.selection_digest() != persisted_selection_digest
            or intent.source_access_revalidation_status != _OBSERVATIONAL_SOURCE_ACCESS_STATUS
            or (
                intent.search_binding_tenant_id is not None
                and intent.search_binding_tenant_id != current.scope.tenant_id
            )
            or (
                intent.search_binding_cell_id is not None
                and intent.search_binding_cell_id != current.scope.cell_id
            )
            or intent.method_fqn != registration.signature.fqn
            or intent.method_version != registration.signature.version
            or intent.method_abi_digest != registration.signature.abi_digest()
            or intent.method_build_digest != registration.build_digest
            or intent.resource_policy.method_contract_target != registration.contract_target
        ):
            raise ValueError("observational_method_intent_pin_drift")
        try:
            self._require_observational_method_resource_profile(
                registration,
                intent.resolved_params,
                resource_policy=expected_resource_policy,
            )
        except ValueError as exc:
            raise ValueError("observational_method_intent_resource_profile_drift") from exc
        search_binding_admission = None
        if intent.schema_version == "polisyos.runtime.observational_run_intent.v3":
            snapshot = intent.search_binding_admission
            request_context = intent.owned_hte_request_context
            if (
                type(snapshot) is not SearchUncertaintyTaskAdmissionSnapshot
                or request_context is None
                or request_context.search_uncertainty_task_binding_ref is None
                or intent.search_binding_tenant_id is None
                or intent.search_binding_cell_id is None
                or current.scope.status != "established"
                or current.scope.actor_authenticated is not True
                or current.scope.tenant_id != intent.search_binding_tenant_id
                or current.scope.cell_id != intent.search_binding_cell_id
                or type(expected_resource_policy.method_profile_id) is not str
                or expected_resource_policy.method_profile_id
                != snapshot.selected_inference_profile_id
            ):
                raise ValueError("observational_method_search_admission_scope_not_established")
            try:
                search_binding_admission = self._resolve_search_uncertainty_binding(
                    binding_ref=request_context.search_uncertainty_task_binding_ref,
                    tenant_id=intent.search_binding_tenant_id,
                    cell_id=intent.search_binding_cell_id,
                    request_context=request_context,
                    method_fqn=intent.method_fqn,
                    method_version=intent.method_version,
                    method_abi_digest=intent.method_abi_digest,
                    resolved_params=intent.resolved_params,
                    seed=intent.seed,
                    inference_profile_id=expected_resource_policy.method_profile_id,
                    selected_method_input_ref=persisted_source_ref,
                    selected_method_input_content_sha256=persisted_source_ref.artifact_id.hex,
                    admitted_snapshot=snapshot,
                )
            except (TypeError, ValueError) as exc:
                raise ValueError("observational_method_search_admission_not_reconciled") from exc
        return _RuntimeMethodExecutionAdmission(
            store=cast("_MethodExecutionArtifactStore", self._artifact_store),
            requested_source_ref=persisted_source_ref,
            observational_run_intent_ref=persisted_intent_ref,
            source_manifest_sha256=source_manifest_sha256,
            lease_owner=str(job.lease_owner),
            protocol=intent.protocol,
            method_fqn=intent.method_fqn,
            method_version=intent.method_version,
            method_abi_digest=intent.method_abi_digest,
            method_build_digest=intent.method_build_digest,
            resource_policy=expected_resource_policy,
            owned_hte_request_context=intent.owned_hte_request_context,
            search_binding_tenant_id=intent.search_binding_tenant_id,
            search_binding_cell_id=intent.search_binding_cell_id,
            search_binding_admission=search_binding_admission,
            effective_params=dict(intent.resolved_params),
            submitted_params=dict(intent.submitted_params),
            submitted_params_present=intent.submitted_params_present,
            seed=intent.seed,
            resource_policy_ref=intent.resource_policy_ref,
            resource_policy_digest=intent.resource_policy_digest,
            selection_digest=intent.selection_digest(),
            source_access_revalidation_status=_OBSERVATIONAL_SOURCE_ACCESS_STATUS,
            requested_limitations=intent.limitations,
            source_governance=intent.source_governance,
            source_tenant_context=intent.source_tenant_context,
            limits=self._observational_read_limits(),
        )

    def verify_method_registration(
        self,
        admission: MethodExecutionAdmission,
        signature: MethodSignature,
        method_class: type,
    ) -> None:
        """Refuse exact method ABI or class-source drift before input decoding."""
        registration = self._observational_method_registrations.get(admission.method_fqn)
        if (
            type(admission) is not _RuntimeMethodExecutionAdmission
            or registration is None
            or signature.fqn != admission.method_fqn
            or signature.version != admission.method_version
            or signature.abi_digest() != admission.method_abi_digest
            or method_class is not registration.method_class
        ):
            raise ValueError("observational_method_registration_pin_mismatch")
        try:
            self._require_observational_method_resource_profile(
                registration,
                admission.effective_params,
                resource_policy=admission.resource_policy,
            )
        except ValueError as exc:
            raise ValueError("observational_method_resource_profile_pin_mismatch") from exc
        try:
            build_digest = hashlib.sha256(
                inspect.getsource(method_class).encode("utf-8")
            ).hexdigest()
        except (OSError, TypeError) as exc:
            raise ValueError("observational_method_build_not_established") from exc
        if (
            build_digest != admission.method_build_digest
            or build_digest != registration.build_digest
        ):
            raise ValueError("observational_method_build_pin_mismatch")

    def persist_content_admitted_intent(
        self,
        *,
        work: MethodExecutionWork,
        admission: MethodExecutionAdmission,
        submitted_ref: ArtifactRef,
        effective_ref: ArtifactRef,
        contract_target: _ContractCompatibilityTarget,
        method_fqn: str,
        source_protocol: str,
        normalization: str,
        limitations: tuple[str, ...],
        source_governance: ArtifactGovernanceInfo | None,
        source_tenant_context: ArtifactTenantContextInfo | None,
        observed_bytes: int,
        observed_depth: int,
        observed_elements: int,
        observed_manifest_bytes: int,
        observed_manifest_selection_bytes: int,
        observed_manifest_verification_bytes: int,
        observed_payload_bytes: int,
        observed_source_bytes: int,
        payload_integrity_verified: Literal[True],
    ) -> ArtifactRef:
        """Persist only worker-admitted refs and counters before the method dispatches."""
        from polisyos.core.contracts.runtime import (
            ContentAdmittedObservationalRunIntent,
            ObservationalRunIntent,
            _expected_content_admitted_limitations,
            _expected_observational_limitations,
            _expected_observational_normalization,
            _observational_intent_manifest_identity,
        )
        from polisyos.ir.observation import ContractCompatibilityTarget

        if (
            type(admission) is not _RuntimeMethodExecutionAdmission
            or type(contract_target) is not ContractCompatibilityTarget
        ):
            raise ValueError("content_admitted_intent_admission_owner_invalid")
        admission = cast("_RuntimeMethodExecutionAdmission", admission)
        contract_target_id = contract_target.contract_id
        contract_target_fqn = contract_target.contract_fqn
        current = self._control_store.current_execution_job_admission()
        job = current.job
        if (
            job.job_id != work.job_id
            or job.run_id != work.run_id
            or job.attempt != work.attempt
            or job.state != "running"
            or job.lease_owner != admission.lease_owner
            or not _same_selected_artifact_ref(
                admission.requested_source_ref,
                work.requested_source_ref,
            )
            or not _same_selected_artifact_ref(
                admission.observational_run_intent_ref,
                work.observational_run_intent_ref,
            )
        ):
            raise ControlJobLeaseLostError("content_admitted_intent_live_lease_mismatch")
        _, current_governance, current_tenant_context, current_manifest_sha256 = (
            self._read_observational_source_manifest(
                admission.requested_source_ref,
                expected_sha256=admission.source_manifest_sha256,
            )
        )
        if (
            current_governance != admission.source_governance
            or current_tenant_context != admission.source_tenant_context
            or current_manifest_sha256 != admission.source_manifest_sha256
        ):
            raise ValueError("content_admitted_intent_source_manifest_pin_drift")
        _require_public_candidate_source(current_governance, current_tenant_context)
        requested_intent = self._read_bounded_intent_model(
            admission.observational_run_intent_ref,
            model=ObservationalRunIntent,
        )
        expected_normalization = _expected_observational_normalization(source_protocol)
        expected_request_limitations = _expected_observational_limitations(
            source_protocol,
            source_access_revalidation_status=admission.source_access_revalidation_status,
        )
        required_producer_limitations = _expected_content_admitted_limitations(
            source_protocol,
            source_access_revalidation_status=None,
        )
        producer_limitations = tuple(limitations)
        expected_admitted_limitations = _expected_content_admitted_limitations(
            source_protocol,
            source_access_revalidation_status=admission.source_access_revalidation_status,
        )
        if (
            requested_intent.job_id != work.job_id
            or requested_intent.run_id != work.run_id
            or not _same_selected_artifact_ref(
                requested_intent.requested_source_ref,
                admission.requested_source_ref,
            )
            or requested_intent.protocol != admission.protocol
            or requested_intent.source_manifest_sha256 != admission.source_manifest_sha256
            or requested_intent.method_fqn != admission.method_fqn
            or requested_intent.method_version != admission.method_version
            or requested_intent.method_abi_digest != admission.method_abi_digest
            or requested_intent.method_build_digest != admission.method_build_digest
            or not _same_selected_artifact_ref(
                requested_intent.resource_policy_ref,
                admission.resource_policy_ref,
            )
            or requested_intent.resource_policy_digest != admission.resource_policy_digest
            or requested_intent.resource_policy != admission.resource_policy
            or requested_intent.owned_hte_request_context != admission.owned_hte_request_context
            or requested_intent.search_binding_admission != admission.search_binding_admission
            or requested_intent.search_binding_tenant_id != admission.search_binding_tenant_id
            or requested_intent.search_binding_cell_id != admission.search_binding_cell_id
            or requested_intent.contract_target_id != contract_target_id
            or requested_intent.contract_target_fqn != contract_target_fqn
            or requested_intent.selection_digest() != admission.selection_digest
            or requested_intent.limitations != admission.requested_limitations
            or requested_intent.limitations != expected_request_limitations
            or requested_intent.source_access_revalidation_status
            != admission.source_access_revalidation_status
            or admission.source_access_revalidation_status != _OBSERVATIONAL_SOURCE_ACCESS_STATUS
            or not _same_selected_artifact_ref(
                submitted_ref,
                admission.requested_source_ref,
            )
            or method_fqn != admission.method_fqn
            or source_protocol != admission.protocol
            or normalization != expected_normalization
            or len(set(producer_limitations)) != len(producer_limitations)
            or set(producer_limitations) != set(required_producer_limitations)
            or source_governance != admission.source_governance
            or source_tenant_context != admission.source_tenant_context
            or contract_target_id != _OBSERVATIONAL_METHOD_CONTRACT_TARGET_ID
            or contract_target_fqn != _OBSERVATIONAL_METHOD_CONTRACT_TARGET
            or type(observed_manifest_bytes) is not int
            or observed_manifest_bytes < 1
            or observed_manifest_bytes > admission.limits.max_manifest_bytes
            or type(observed_manifest_selection_bytes) is not int
            or observed_manifest_selection_bytes < 0
            or observed_manifest_selection_bytes > admission.limits.max_manifest_bytes
            or observed_manifest_bytes != observed_manifest_selection_bytes
            or type(observed_manifest_verification_bytes) is not int
            or observed_manifest_verification_bytes < 0
            or observed_manifest_verification_bytes > admission.limits.max_manifest_bytes
            or type(observed_payload_bytes) is not int
            or observed_payload_bytes < 0
            or observed_payload_bytes > admission.limits.max_bytes
            or type(observed_source_bytes) is not int
            or observed_source_bytes
            != (
                observed_manifest_selection_bytes
                + observed_manifest_verification_bytes
                + observed_payload_bytes
            )
            or observed_source_bytes
            > (2 * admission.limits.max_manifest_bytes + admission.limits.max_bytes)
            or payload_integrity_verified is not True
            or type(observed_bytes) is not int
            or observed_bytes != observed_payload_bytes
            or observed_bytes > admission.limits.max_bytes
            or type(observed_depth) is not int
            or observed_depth < 0
            or observed_depth > admission.limits.max_depth
            or type(observed_elements) is not int
            or observed_elements < 0
            or observed_elements > admission.limits.max_elements
        ):
            raise ValueError("content_admitted_intent_source_binding_mismatch")
        search_binding_admission = None
        request_context = admission.owned_hte_request_context
        search_binding_ref = (
            request_context.search_uncertainty_task_binding_ref
            if request_context is not None
            else None
        )
        if search_binding_ref is not None:
            execution_scope = current.scope
            if (
                admission.method_fqn not in _OBSERVATIONAL_METHOD_FQN_V2
                or request_context is None
                or admission.search_binding_tenant_id is None
                or admission.search_binding_cell_id is None
                or execution_scope.status != "established"
                or execution_scope.actor_authenticated is not True
                or execution_scope.tenant_id != admission.search_binding_tenant_id
                or execution_scope.cell_id != admission.search_binding_cell_id
                or payload_integrity_verified is not True
                or effective_ref.manifest_profile_sha256 is None
            ):
                raise ValueError("content_admitted_search_scope_or_input_not_established")
            selected_profile_id = admission.resource_policy.method_profile_id
            if type(selected_profile_id) is not str:
                raise ValueError("content_admitted_search_method_profile_not_established")
            search_binding_admission = self._resolve_search_uncertainty_binding(
                binding_ref=search_binding_ref,
                tenant_id=admission.search_binding_tenant_id,
                cell_id=admission.search_binding_cell_id,
                request_context=request_context,
                method_fqn=admission.method_fqn,
                method_version=admission.method_version,
                method_abi_digest=admission.method_abi_digest,
                resolved_params=admission.effective_params,
                seed=admission.seed,
                inference_profile_id=selected_profile_id,
                selected_method_input_ref=effective_ref,
                selected_method_input_content_sha256=effective_ref.artifact_id.hex,
                admitted_snapshot=admission.search_binding_admission,
            )
        intent = ContentAdmittedObservationalRunIntent(
            schema_version=(
                "polisyos.runtime.content_admitted_observational_run_intent.v3"
                if admission.search_binding_admission is not None
                else (
                    "polisyos.runtime.content_admitted_observational_run_intent.v2"
                    if admission.method_fqn in _OBSERVATIONAL_METHOD_FQN_V2
                    else "polisyos.runtime.content_admitted_observational_run_intent.v1"
                )
            ),
            job_id=job.job_id,
            run_id=str(job.run_id or ""),
            attempt=job.attempt,
            requested_intent_ref=admission.observational_run_intent_ref,
            requested_source_ref=admission.requested_source_ref,
            source_manifest_sha256=admission.source_manifest_sha256,
            resource_policy_ref=admission.resource_policy_ref,
            submitted_input_ref=submitted_ref,
            effective_input_ref=effective_ref,
            contract_target_id=contract_target_id,
            contract_target=contract_target_fqn,
            selection_digest=admission.selection_digest,
            source_access_revalidation_status=admission.source_access_revalidation_status,
            method_fqn=method_fqn,
            owned_hte_request_context=admission.owned_hte_request_context,
            search_binding_admission=search_binding_admission,
            search_binding_tenant_id=admission.search_binding_tenant_id,
            search_binding_cell_id=admission.search_binding_cell_id,
            source_protocol=source_protocol,
            normalization=expected_normalization,
            limitations=expected_admitted_limitations,
            source_governance=source_governance,
            source_tenant_context=source_tenant_context,
            observed_manifest_bytes=observed_manifest_bytes,
            observed_manifest_selection_bytes=observed_manifest_selection_bytes,
            observed_manifest_verification_bytes=observed_manifest_verification_bytes,
            observed_payload_bytes=observed_payload_bytes,
            observed_source_bytes=observed_source_bytes,
            payload_integrity_verified=payload_integrity_verified,
            observed_bytes=observed_bytes,
            observed_depth=observed_depth,
            observed_elements=observed_elements,
            resource_policy_digest=admission.resource_policy_digest,
        )
        intent_input_edges = _content_admitted_intent_input_edges(intent)
        ref = self._put_json_artifact_ref(
            intent.artifact_payload(),
            kind="runtime.content_admitted_observational_run_intent",
            schema_name="polisyos.runtime.ContentAdmittedObservationalRunIntent",
            schema_version=_observational_intent_manifest_identity(intent.schema_version)[2],
            governance=source_governance,
            tenant_context=source_tenant_context,
            inputs=[ref for ref, _role in intent_input_edges],
            input_roles=tuple(role for _ref, role in intent_input_edges),
        )
        if ref.manifest_profile_sha256 is None:
            raise RuntimeError("content_admitted_intent_profile_not_established")
        return ref

    def resolve_method_metric_projection_store(
        self, *, work: MethodMetricProjectionWorkLike
    ) -> _MethodMetricProjectionArtifactStore | None:
        """Resolve AD01 CAS only for the exact raw graph refs returned by this workflow."""
        source = _RUNTIME_GRAPH_METRIC_SOURCE.get()
        if source is None or (
            source.job_id != work.job_id
            or source.run_id != work.run_id
            or source.attempt != work.attempt
            or not source.lease_owner
            or source.simulation_result_ref != work.simulation_result_ref
            or source.method_execution_bundle_ref != work.method_execution_bundle_ref
            or source.method_metric_binding_set_ref != work.method_metric_binding_set_ref
            or work.method_result_ref is not None
        ):
            raise ValueError("method_metric_projection_source_not_workflow_bound")
        current = self._control_store.current_execution_job_admission()
        job = current.job
        if (
            job.job_id != source.job_id
            or job.run_id != source.run_id
            or job.attempt != source.attempt
            or job.lease_owner != source.lease_owner
            or job.state != "running"
        ):
            raise ControlJobLeaseLostError("method_metric_projection_live_lease_mismatch")
        from polisyos.core.artifacts.protocol import matches_runtime_protocol

        protocol_owner = _configured_core_read_owner(self._artifact_store)
        if not matches_runtime_protocol(
            protocol_owner, _RuntimeMethodMetricProjectionArtifactStore
        ):
            return None
        return protocol_owner

    def persist_pre_output_owned_attempt_anchor(
        self,
        *,
        work: MethodExecutionWork,
        admission: MethodExecutionAdmission,
        prepared: PreparedHTEObservationalInput,
        content_admitted_intent_ref: ArtifactRef,
        method_class: type,
    ) -> OwnedAttemptAnchorDispatchContext:
        """Persist the current fenced worker's pre-output anchor through Core ownership."""
        from polisyos.runtime.http.services.control.owned_attempt_anchor import (
            persist_pre_output_owned_attempt_anchor,
        )

        return persist_pre_output_owned_attempt_anchor(
            service=self,
            work=work,
            admission=admission,
            prepared=prepared,
            content_admitted_intent_ref=content_admitted_intent_ref,
            method_class=method_class,
        )

    def persist_pre_output_hte_input_refusal_anchor(
        self,
        *,
        work: MethodExecutionWork,
        admission: MethodExecutionAdmission,
        refusal: HTEInputPreparationRefusal,
        method_class: type,
    ) -> OwnedAttemptAnchorRef:
        """Persist typed selected-input refusal without inventing admitted inputs."""
        from polisyos.foundry.data_plane import HTEInputPreparationRefusal
        from polisyos.runtime.http.services.control.owned_attempt_anchor import (
            persist_pre_output_hte_input_refusal_anchor,
        )

        if type(refusal) is not HTEInputPreparationRefusal:
            raise TypeError("method_execution_input_refusal_must_be_typed")
        return persist_pre_output_hte_input_refusal_anchor(
            service=self,
            work=work,
            admission=admission,
            refusal=refusal,
            method_class=method_class,
        )

    def resolve_owned_attempt_anchor_association(
        self,
        *,
        anchor_ref: ArtifactRef,
        expected_completed_event_id: int | None = None,
        expected_job_id: str | None = None,
        expected_tenant_id: str | None = None,
        expected_cell_id: str | None | object = _RUN_LIFECYCLE_OWNER_SCOPE_UNSET,
    ) -> OwnedAttemptAnchorAssociation:
        """Resolve an anchor to a current or exact historical completed selection."""
        from polisyos.core.contracts.owned_attempt_anchor import OwnedAttemptAnchorRef
        from polisyos.runtime.http.services.control.owned_attempt_anchor import (
            resolve_owned_attempt_anchor_association,
        )

        if type(anchor_ref) is OwnedAttemptAnchorRef:
            typed_anchor_ref = anchor_ref
        elif type(anchor_ref) is ArtifactRef:
            try:
                typed_anchor_ref = OwnedAttemptAnchorRef.model_validate(
                    anchor_ref.model_dump(mode="python"), strict=True
                )
            except (TypeError, ValueError) as exc:
                raise TypeError("method_execution_owned_anchor_ref_invalid") from exc
        else:
            raise TypeError("method_execution_owned_anchor_ref_invalid")
        if (
            expected_cell_id is not _RUN_LIFECYCLE_OWNER_SCOPE_UNSET
            and expected_cell_id is not None
            and type(expected_cell_id) is not str
        ):
            raise TypeError("method_execution_expected_cell_id_invalid")
        if (
            expected_completed_event_id is None
            and expected_job_id is None
            and expected_tenant_id is None
            and expected_cell_id is _RUN_LIFECYCLE_OWNER_SCOPE_UNSET
        ):
            return resolve_owned_attempt_anchor_association(
                service=self,
                anchor_ref=typed_anchor_ref,
            )
        if expected_cell_id is _RUN_LIFECYCLE_OWNER_SCOPE_UNSET:
            return resolve_owned_attempt_anchor_association(
                service=self,
                anchor_ref=typed_anchor_ref,
                expected_completed_event_id=expected_completed_event_id,
                expected_job_id=expected_job_id,
                expected_tenant_id=expected_tenant_id,
            )
        return resolve_owned_attempt_anchor_association(
            service=self,
            anchor_ref=typed_anchor_ref,
            expected_completed_event_id=expected_completed_event_id,
            expected_job_id=expected_job_id,
            expected_tenant_id=expected_tenant_id,
            expected_cell_id=expected_cell_id,
        )

    def resolve_historical_search_uncertainty_task_binding(
        self,
        *,
        binding_ref: ArtifactRef,
        owner_association: SearchOwnedAttemptAssociation,
    ) -> SearchUncertaintyTaskBindingResolution:
        """Reconcile an admitted Search binding to its immutable Runtime attempt.

        The Search owner proves the binding's own ticket history and dependency
        closure. Runtime independently binds that historical result to the
        selected anchor, content-admitted intent, exact method/source request,
        and the Search admission snapshot written before dispatch.
        """
        from polisyos.core.artifacts import (
            read_core_json_artifact_bounded,
            validate_core_model_bounded_read,
        )
        from polisyos.core.contracts.owned_attempt_anchor import (
            OwnedAttemptAnchor,
            OwnedAttemptAnchorAssociation,
        )
        from polisyos.core.contracts.runtime import (
            ContentAdmittedObservationalRunIntent,
            ObservationalRunIntent,
            SearchUncertaintyTaskAdmissionSnapshot,
        )
        from polisyos.runtime.http.services.control.owned_attempt_anchor import (
            _require_full_profile_ref,
            _same_request_context,
        )
        from polisyos.scientist.methods.search.uncertainty import (
            SearchUncertaintyHTERequestProjection,
            SearchUncertaintyTaskBinding,
            SearchUncertaintyTaskBindingResolution,
            resolve_historical_search_uncertainty_task_binding,
        )

        binding_ref = _require_full_profile_ref(
            binding_ref,
            code="runtime_historical_search_binding_owner_selection_invalid",
        )
        if (
            binding_ref.kind != "scientist.search.uncertainty_task_binding"
            or binding_ref.media_type != "application/json"
            or binding_ref.manifest_profile_sha256 is None
            or type(owner_association) is not OwnedAttemptAnchorAssociation
            or not _same_selected_artifact_ref(
                owner_association.search_uncertainty_task_binding_ref,
                binding_ref,
            )
            or owner_association.anchor_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("runtime_historical_search_binding_owner_selection_invalid")

        resolution = resolve_historical_search_uncertainty_task_binding(
            store=self._require_search_uncertainty_store(),
            binding_ref=binding_ref,
            owner_association=owner_association,
        )
        if (
            type(resolution) is not SearchUncertaintyTaskBindingResolution
            or resolution.schema_version != "1.0"
            or resolution.resolution_status != "historical"
            or resolution.closure_status != "recomputed"
            or not _same_selected_artifact_ref(resolution.binding_ref, binding_ref)
            or type(resolution.binding) is not SearchUncertaintyTaskBinding
            or resolution.binding_content_sha256 != binding_ref.artifact_id.hex
            or not resolution.tenant_id
            or not resolution.cell_id
        ):
            raise ValueError("runtime_historical_search_binding_resolution_invalid")

        limits = self._observational_read_limits()
        selected_anchor_ref = _require_full_profile_ref(
            owner_association.anchor_ref,
            code="runtime_historical_search_anchor_profile_invalid",
        )
        bounded_anchor = read_core_json_artifact_bounded(
            self._require_core_bounded_member_reader(limits=limits),
            selected_anchor_ref,
            limits=limits,
        )
        if (
            not _same_selected_artifact_ref(
                bounded_anchor.effective_ref,
                selected_anchor_ref,
            )
            or bounded_anchor.manifest.kind != "runtime.owned_attempt_anchor"
            or bounded_anchor.manifest.media_type != "application/json"
            or bounded_anchor.manifest.artifact_schema
            != SchemaInfo(name="polisyos.runtime.OwnedAttemptAnchor", version="1.0")
        ):
            raise ValueError("runtime_historical_search_anchor_profile_invalid")
        try:
            anchor = validate_core_model_bounded_read(
                OwnedAttemptAnchor,
                bounded_anchor,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("runtime_historical_search_anchor_payload_invalid") from exc
        if (
            not _same_selected_artifact_ref(
                anchor.request_context.search_uncertainty_task_binding_ref,
                binding_ref,
            )
            or anchor.job_id != owner_association.job_id
            or anchor.run_id != owner_association.run_id
            or anchor.attempt != owner_association.attempt
            or not anchor.cell_id
            or anchor.tenant_id != resolution.tenant_id
            or anchor.cell_id != resolution.cell_id
            or anchor.input_admission.admission_status != "input_admitted"
            or not _same_selected_artifact_ref(
                anchor.effective_input_ref,
                owner_association.source_data_ref,
            )
        ):
            raise ValueError("runtime_historical_search_anchor_binding_mismatch")

        content_intent_ref = anchor.content_admitted_intent_ref
        try:
            content_intent = self._read_bounded_intent_model(
                content_intent_ref,
                model=ContentAdmittedObservationalRunIntent,
            )
            requested_intent = self._read_bounded_intent_model(
                content_intent.requested_intent_ref,
                model=ObservationalRunIntent,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("runtime_historical_search_intents_invalid") from exc
        snapshot = content_intent.search_binding_admission
        binding = resolution.binding
        if type(snapshot) is not SearchUncertaintyTaskAdmissionSnapshot:
            raise ValueError("runtime_historical_search_admission_snapshot_missing")

        request_context = anchor.request_context
        request_projection_payload: dict[str, object] = {
            "estimand": request_context.request_estimand,
            "target_scope": request_context.request_target_scope,
            "outcome_variable_id": request_context.outcome_variable_id,
            "treatment_variable_id": request_context.treatment_variable_id,
            "control_value": request_context.control_value,
            "treated_value": request_context.treated_value,
            "alpha": request_context.requested_alpha,
        }
        if request_context.requested_guarantee_status == "declared":
            request_projection_payload["requested_guarantee"] = request_context.requested_guarantee
        request_projection = SearchUncertaintyHTERequestProjection.model_validate(
            request_projection_payload
        )
        params_bytes = json.dumps(
            dict(requested_intent.resolved_params),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        params_sha256 = hashlib.sha256(params_bytes).hexdigest()
        if (
            resolution.owner_revision != binding.owner_revision
            or resolution.projection_revision != binding.projection_revision
            or not _same_selected_artifact_ref(
                resolution.projection_ref,
                binding.source_projection_ref,
            )
        ):
            raise ValueError("runtime_historical_search_binding_revision_mismatch")
        expected_snapshot_values = (
            (snapshot.binding_ref, binding_ref),
            (snapshot.binding_content_sha256, resolution.binding_content_sha256),
            (snapshot.ticket_id, resolution.ticket_id),
            (snapshot.ticket_generation, resolution.ticket_generation),
            (snapshot.owner_revision, resolution.owner_revision),
            (snapshot.projection_revision, resolution.projection_revision),
            (snapshot.projection_ref, resolution.projection_ref),
            (snapshot.task_admission_ref, resolution.task_admission_ref),
            (snapshot.task_epoch_ref, resolution.task_epoch_ref),
            (snapshot.owner_context_ref, resolution.owner_context_ref),
            (snapshot.basis_ref, resolution.basis_ref),
            (snapshot.dependency_inventory_ref, resolution.dependency_inventory_ref),
            (snapshot.dependency_inventory_sha256, resolution.dependency_inventory_sha256),
            (snapshot.source_projection_ref, resolution.source_projection_ref),
            (snapshot.tenant_id, resolution.tenant_id),
            (snapshot.cell_id, resolution.cell_id),
            (snapshot.selected_method_fqn, anchor.method_fqn),
            (snapshot.selected_method_abi_version, anchor.method_version),
            (snapshot.selected_method_abi_digest, anchor.method_abi_digest),
            (snapshot.selected_method_params, requested_intent.resolved_params),
            (snapshot.selected_method_params_sha256, params_sha256),
            (snapshot.selected_method_seed, requested_intent.seed),
            (snapshot.selected_inference_profile_id, anchor.resource_policy_method_profile_id),
            (snapshot.selected_method_input_ref, anchor.effective_input_ref),
            (
                snapshot.selected_method_input_content_sha256,
                anchor.effective_input_ref.artifact_id.hex,
            ),
        )
        if (
            content_intent.job_id != anchor.job_id
            or content_intent.run_id != anchor.run_id
            or content_intent.attempt != anchor.attempt
            or content_intent.method_fqn != anchor.method_fqn
            or not _same_selected_artifact_ref(
                content_intent.resource_policy_ref,
                anchor.resource_policy_ref,
            )
            or not _same_request_context(
                content_intent.owned_hte_request_context,
                requested_intent.owned_hte_request_context,
            )
            or not _same_selected_artifact_ref(
                content_intent.requested_intent_ref,
                anchor.observational_run_intent_ref,
            )
            or not _same_selected_artifact_ref(
                content_intent.effective_input_ref,
                anchor.effective_input_ref,
            )
            or content_intent.search_binding_tenant_id != anchor.tenant_id
            or content_intent.search_binding_cell_id != anchor.cell_id
            or not _same_request_context(
                requested_intent.owned_hte_request_context,
                request_context,
            )
            or binding.request_projection != request_projection
            or binding.selected_method_fqn != anchor.method_fqn
            or binding.selected_method_abi_version != anchor.method_version
            or binding.selected_method_abi_digest != anchor.method_abi_digest
            or binding.selected_method_params != requested_intent.resolved_params
            or binding.selected_method_params_sha256 != params_sha256
            or binding.selected_method_seed != requested_intent.seed
            or binding.selected_inference_profile_id != anchor.resource_policy_method_profile_id
            or not _same_selected_artifact_ref(
                binding.selected_method_input_ref,
                anchor.effective_input_ref,
            )
            or binding.selected_method_input_content_sha256
            != anchor.effective_input_ref.artifact_id.hex
            or resolution.selected_method_fqn != anchor.method_fqn
            or resolution.selected_method_abi_version != anchor.method_version
            or resolution.selected_method_abi_digest != anchor.method_abi_digest
            or resolution.selected_method_params != requested_intent.resolved_params
            or resolution.selected_method_params_sha256 != params_sha256
            or resolution.selected_method_seed != requested_intent.seed
            or resolution.selected_inference_profile_id != anchor.resource_policy_method_profile_id
            or not _same_selected_artifact_ref(
                resolution.selected_method_input_ref,
                anchor.effective_input_ref,
            )
            or resolution.selected_method_input_content_sha256
            != anchor.effective_input_ref.artifact_id.hex
            or any(
                not _same_selected_reference_or_value(left, right)
                for left, right in expected_snapshot_values
            )
        ):
            raise ValueError("runtime_historical_search_snapshot_binding_mismatch")
        return resolution

    def resolve_historical_completed_method_execution(
        self,
        *,
        job_id: str,
        completed_event_id: int,
        tenant_id: str,
        cell_id: str | None,
    ) -> OwnedAttemptAnchorAssociation | None:
        """Resolve one exact owner-selected @2 HTE completion for Search receipt.

        This history reader is keyed by the immutable event and matching Search
        outbox row. It deliberately does not require that the attempt still be
        the current run winner, so a delayed durable delivery remains provable
        after a newer attempt supersedes it.
        """
        from pydantic import TypeAdapter

        from polisyos.core.contracts.owned_attempt_anchor import (
            OwnedAttemptAnchorAssociation,
            OwnedAttemptAnchorRef,
        )
        from polisyos.core.contracts.runtime import (
            DirectMethodExecutionSelection,
            RuntimeSearchHTECompletionDeliveryV1,
            _validate_method_execution_selection_wire_payload,
            _validate_strict_json_wire_payload,
        )
        from polisyos.runtime.http.services.control.owned_attempt_anchor import (
            resolve_owned_attempt_anchor_association,
        )
        from polisyos.runtime.http.services.control_plane_store import (
            _control_job_execution_scope_from_event,
        )

        if (
            not isinstance(job_id, str)
            or not job_id
            or type(completed_event_id) is not int
            or completed_event_id < 1
            or not isinstance(tenant_id, str)
            or not tenant_id
        ):
            return None
        try:
            event = self._control_store.get_job_lifecycle_event_record(
                job_id=job_id,
                event_id=completed_event_id,
                expected_event_type="job_completed",
            )
            record = self._control_store.get_job(job_id)
            created_event = self._control_store._get_job_created_source_event_record(job_id)
            delivery_record = self._control_store.get_search_hte_completion_outbox_event(
                job_id=job_id,
                completed_event_id=completed_event_id,
            )
        except OSError, RuntimeError, TypeError, ValueError:
            return None
        if (
            record is None
            or record.job_id != job_id
            or record.kind != "workflow_run"
            or record.run_id is None
            or delivery_record is None
            or delivery_record.topic != "control.search.hte_completed"
            or delivery_record.job_id != job_id
            or delivery_record.run_id != record.run_id
            or created_event.job_id != job_id
            or created_event.event_type != "job_created"
            or event.job_id != job_id
            or event.event_type != "job_completed"
            or event.payload.get("state") != "completed"
        ):
            return None
        try:
            delivery = _validate_strict_json_wire_payload(
                delivery_record.payload,
                TypeAdapter(RuntimeSearchHTECompletionDeliveryV1),
                invalid_code="search_hte_outbox_payload_invalid",
            )
            selection_payload = event.payload.get("method_execution_selection")
            selection = _validate_method_execution_selection_wire_payload(selection_payload)
        except TypeError, ValueError:
            return None

        def same_selected_ref(left: object, right: object) -> bool:
            """Compare complete selected ArtifactRef identity across DTO subclasses."""
            return _same_selected_artifact_ref(left, right)

        def same_optional_selected_ref(
            left: object,
            right: object,
            *,
            absence_is_valid_for_selected_kind: bool,
        ) -> bool:
            """Compare a typed optional ref, permitting only valid selected-kind absence."""
            return _same_optional_selected_artifact_ref_for_kind(
                left,
                right,
                absence_is_valid_for_selected_kind=absence_is_valid_for_selected_kind,
            )

        if (
            type(selection) is not DirectMethodExecutionSelection
            or selection.method_version != "2.0.0"
            or selection.hte is None
            or selection.owned_attempt_anchor_ref is None
            or not same_selected_ref(
                selection.hte.search_uncertainty_task_binding_ref,
                delivery.search_uncertainty_task_binding_ref,
            )
            or delivery.job_id != job_id
            or delivery.run_id != selection.run_id
            or delivery.attempt != selection.attempt
            or delivery.completed_event_id != event.event_id
            or delivery.completed_event_payload_sha256 != event.payload_sha256
            or event.payload.get("attempt") != selection.attempt
            or type(event.payload.get("attempt")) is not int
            or record.run_id != selection.run_id
            or type(record.attempt) is not int
            or record.attempt < selection.attempt
        ):
            return None
        expected_event_key = f"{job_id}:job_completed:{event.event_id}"
        if delivery_record.event_key != expected_event_key:
            return None
        scope = _control_job_execution_scope_from_event(created_event.payload)
        if (
            scope.status != "established"
            or scope.tenant_id != tenant_id
            or scope.cell_id != cell_id
            or created_event.payload.get("run_id") != selection.run_id
            or created_event.payload.get("job_kind") != "workflow_run"
        ):
            return None
        try:
            anchor_ref = OwnedAttemptAnchorRef.model_validate(
                selection.owned_attempt_anchor_ref,
                strict=True,
            )
            association = resolve_owned_attempt_anchor_association(
                service=self,
                anchor_ref=anchor_ref,
                expected_completed_event_id=event.event_id,
                expected_job_id=job_id,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
            )
        except OSError, RuntimeError, TypeError, ValueError:
            return None
        if (
            type(association) is not OwnedAttemptAnchorAssociation
            or association.job_id != selection.job_id
            or association.run_id != selection.run_id
            or association.attempt != selection.attempt
            or association.job_completed_event.event_id != event.event_id
            or association.job_completed_event.payload_sha256 != event.payload_sha256
            or not same_selected_ref(association.anchor_ref, anchor_ref)
            or association.outcome_kind != selection.hte.kind
            or not same_selected_ref(association.outcome_ref, selection.hte.hte_outcome_ref)
            or not same_selected_ref(association.source_data_ref, selection.hte.source_data_ref)
            or not same_selected_ref(association.method_result_ref, selection.method_result_ref)
            or not same_selected_ref(association.method_evidence_ref, selection.method_evidence_ref)
            or not same_optional_selected_ref(
                association.point_result_ref,
                selection.hte.point_result_ref,
                absence_is_valid_for_selected_kind=selection.hte.kind != "point_estimate",
            )
            or not same_optional_selected_ref(
                association.hte_result_ref,
                selection.hte.hte_result_ref,
                absence_is_valid_for_selected_kind=selection.hte.kind != "interval_estimate",
            )
            or not same_optional_selected_ref(
                association.inference_basis_ref,
                selection.hte.inference_basis_ref,
                absence_is_valid_for_selected_kind=selection.hte.kind != "interval_estimate",
            )
            or not same_optional_selected_ref(
                association.refusal_diagnostic_ref,
                selection.hte.refusal_diagnostic_ref,
                absence_is_valid_for_selected_kind=selection.hte.kind != "refusal",
            )
            or not same_optional_selected_ref(
                association.invocation_basis_ref,
                selection.invocation_basis_ref,
                absence_is_valid_for_selected_kind=selection.invocation_basis_ref is None,
            )
            or not same_selected_ref(
                association.search_uncertainty_task_binding_ref,
                selection.hte.search_uncertainty_task_binding_ref,
            )
            or not same_optional_selected_ref(
                association.materialization_binding_ref,
                selection.hte.materialization_binding_ref,
                absence_is_valid_for_selected_kind=(
                    selection.hte.resource_evidence.owner_policy_revision != "r5"
                ),
            )
        ):
            return None
        return association

    def resolve_owned_attempt_anchor_refusal_association(
        self,
        *,
        anchor_ref: OwnedAttemptAnchorRef,
    ) -> OwnedAttemptAnchorRefusalAssociation:
        """Resolve only a typed refusal anchor selected by the current failed owner event."""
        from polisyos.core.contracts.owned_attempt_anchor import OwnedAttemptAnchorRef
        from polisyos.runtime.http.services.control.owned_attempt_anchor import (
            resolve_owned_attempt_anchor_refusal_association,
        )

        if type(anchor_ref) is not OwnedAttemptAnchorRef:
            raise TypeError("method_execution_owned_anchor_ref_invalid")
        return resolve_owned_attempt_anchor_refusal_association(
            service=self,
            anchor_ref=anchor_ref,
        )

    def resolve_owned_attempt_anchor_projection_association(
        self,
        *,
        run_id: str,
        expected_job_id: str,
        tenant_id: str,
        cell_id: str | None,
    ) -> _OwnedAttemptAnchorProjectionAssociation:
        """Reconcile the bounded, worker-admitted summary to the current owner row.

        Unlike the assessment-command association, this path does not load method
        outputs or numerical arrays. The helper re-reads the selected owner row,
        completion event, intent lineage, and profiled manifests only.
        """
        from polisyos.runtime.http.services.control.owned_attempt_anchor import (
            resolve_owned_attempt_anchor_projection_association,
        )

        return resolve_owned_attempt_anchor_projection_association(
            service=self,
            run_id=run_id,
            expected_job_id=expected_job_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )

    def _validate_direct_method_execution_selection_artifacts(
        self, selection: _DirectMethodExecutionSelection
    ) -> None:
        """Bind the selected refs to their exact bounded producer manifests."""
        _validate_direct_method_execution_selection_artifacts(
            store=self._require_core_bounded_member_reader(
                limits=self._observational_read_limits()
            ),
            selection=selection,
            limits=self._observational_read_limits(),
        )

    def _is_observational_method_job(self, payload: Mapping[str, Any]) -> bool:
        """Return whether this persisted job payload selected the direct method path."""
        return _OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY in payload

    def _has_observational_method_job_selection(
        self,
        *,
        job: ControlJobRecord,
        payload: Mapping[str, Any],
    ) -> bool:
        """Check both immutable creation selection and the current payload marker."""
        if job.kind != "workflow_run":
            return False
        created_event = self._control_store.get_job_created_event_payload(job.job_id)
        return (
            isinstance(created_event, Mapping)
            and _OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY in created_event
        ) or self._is_observational_method_job(payload)

    def _read_validated_observational_method_job_intent(
        self,
        *,
        job: ControlJobRecord,
        payload: Mapping[str, Any],
    ) -> tuple[ArtifactRef, ArtifactRef, str, _ObservationalRunIntent]:
        """Resolve the immutable creation-time selection before selecting work refs."""
        from polisyos.core.contracts.runtime import ObservationalRunIntent

        marker = payload.get(_OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY)
        if not isinstance(marker, Mapping):
            raise ValueError("observational_method_job_marker_invalid")
        try:
            created_event = self._control_store.get_job_created_event_payload(job.job_id)
        except (RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("observational_method_job_creation_event_unavailable") from exc
        if (
            created_event.get("job_id") != job.job_id
            or created_event.get("run_id") != job.run_id
            or created_event.get("job_kind") != "workflow_run"
            or created_event.get("payload_ref") != job.payload_ref
        ):
            raise ValueError("observational_method_job_creation_event_binding_mismatch")
        created_marker = created_event.get(_OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY)
        if not isinstance(created_marker, Mapping):
            raise ValueError("observational_method_job_creation_marker_missing")
        try:
            payload_projection = json.dumps(
                dict(marker),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            created_projection = json.dumps(
                dict(created_marker),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("observational_method_job_marker_malformed") from exc
        if payload_projection != created_projection:
            raise ValueError("observational_method_job_payload_selection_not_creation_bound")
        try:
            requested_source_ref = ArtifactRef.model_validate(
                created_marker["requested_source_ref"], strict=True
            )
            intent_ref = ArtifactRef.model_validate(
                created_marker["observational_run_intent_ref"], strict=True
            )
            selection_digest = created_marker["observational_selection_digest"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("observational_method_job_marker_invalid") from exc
        if (
            requested_source_ref.manifest_profile_sha256 is None
            or intent_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("observational_method_job_marker_profile_missing")

        requested_intent = self._read_bounded_intent_model(
            intent_ref,
            model=ObservationalRunIntent,
        )
        if (
            requested_intent.job_id != job.job_id
            or requested_intent.run_id != str(job.run_id or "")
            or not _same_selected_artifact_ref(
                requested_source_ref,
                requested_intent.requested_source_ref,
            )
            or type(selection_digest) is not str
            or selection_digest != requested_intent.selection_digest()
        ):
            raise ValueError("observational_method_job_selection_or_intent_binding_mismatch")
        return (
            requested_intent.requested_source_ref,
            intent_ref,
            selection_digest,
            requested_intent,
        )

    def _complete_observational_method_control_job(
        self,
        *,
        job: ControlJobRecord,
        payload: Mapping[str, Any],
        capability_manifest_ref: str,
        execution_scope: ControlJobExecutionScope,
        core_run_id: str,
        core_run_context: run.RunContext,
    ) -> None:
        """Dispatch one refs-only method work item and atomically publish its selection."""
        from polisyos.core.contracts.runtime import (
            ContentAdmittedObservationalRunIntent,
            DirectMethodExecutionSelection,
            MethodExecutionCandidateOutcome,
            MethodExecutionPosteriorSummaryRef,
            _expected_content_admitted_limitations,
        )
        from polisyos.scientist.compute.runner import (
            MethodExecutionInputRefusalOutcome,
            MethodExecutionWork,
        )

        (
            requested_source_ref,
            intent_ref,
            selection_digest,
            requested_intent,
        ) = self._read_validated_observational_method_job_intent(job=job, payload=payload)
        wait_policy = requested_intent.resource_policy.method_execution_wait_policy
        if (
            wait_policy is None
            or wait_policy.producer_key != "runtime.observational_method_execution"
            or wait_policy.retry_ceiling != 0
        ):
            raise ValueError("observational_method_job_selection_or_wait_policy_invalid")
        work = MethodExecutionWork(
            job_id=job.job_id,
            run_id=str(job.run_id or ""),
            attempt=job.attempt,
            requested_source_ref=requested_source_ref,
            observational_run_intent_ref=intent_ref,
        )
        try:
            handle = self._method_backend.submit_method_execution_work(work)
        except Exception as exc:
            raise wrap_shared_execution_exception(exc, wait_policy) from None
        completion = cast("Any", wait_for_shared_execution(handle, wait_policy))
        outcome = cast("Any", require_shared_execution_value(completion, wait_policy))
        if type(outcome) is MethodExecutionInputRefusalOutcome:
            raise ControlProducerExecutionError(
                resolution=wait_policy,
                exception_type=("polisyos.foundry.data_plane.bindings.HTEInputPreparationRefusal"),
                code="observational_input_refused",
                retryable=False,
                input_refusal_anchor_ref=outcome.anchor_ref,
            ) from None
        admitted_intent = self._read_bounded_intent_model(
            outcome.content_admitted_intent_ref,
            model=ContentAdmittedObservationalRunIntent,
        )
        producer_limitations = _expected_content_admitted_limitations(
            outcome.source_protocol,
            source_access_revalidation_status=None,
        )
        registration = self._observational_method_registrations.get(outcome.method_fqn)
        if (
            registration is None
            or outcome.job_id != job.job_id
            or outcome.run_id != str(job.run_id or "")
            or outcome.attempt != job.attempt
            or not _same_selected_artifact_ref(
                outcome.requested_source_ref,
                requested_source_ref,
            )
            or not _same_selected_artifact_ref(
                outcome.observational_run_intent_ref,
                intent_ref,
            )
            or outcome.method_fqn != registration.signature.fqn
            or outcome.method_version != registration.signature.version
            or outcome.method_abi_digest != registration.signature.abi_digest()
            or outcome.method_build_digest != registration.build_digest
            or not _same_selected_artifact_ref(
                outcome.resource_policy_ref,
                requested_intent.resource_policy_ref,
            )
            or not _same_selected_artifact_ref(
                outcome.resource_policy_ref,
                admitted_intent.resource_policy_ref,
            )
            or outcome.resource_policy_digest != admitted_intent.resource_policy_digest
            or (
                outcome.method_version == "2.0.0"
                and (
                    outcome.candidate_outcome is not None
                    or outcome.owned_attempt_anchor_ref is None
                    or outcome.hte_outcome_ref is None
                    or outcome.hte_summary is None
                )
            )
            or (
                outcome.method_version != "2.0.0"
                and type(outcome.candidate_outcome) is not MethodExecutionCandidateOutcome
            )
            or admitted_intent.job_id != outcome.job_id
            or admitted_intent.run_id != outcome.run_id
            or admitted_intent.attempt != outcome.attempt
            or not _same_selected_artifact_ref(
                admitted_intent.requested_intent_ref,
                outcome.observational_run_intent_ref,
            )
            or not _same_selected_artifact_ref(
                admitted_intent.requested_source_ref,
                outcome.requested_source_ref,
            )
            or not _same_optional_selected_artifact_ref(
                admitted_intent.submitted_input_ref,
                outcome.submitted_input_ref,
            )
            or not _same_optional_selected_artifact_ref(
                admitted_intent.effective_input_ref,
                outcome.effective_input_ref,
            )
            or admitted_intent.selection_digest != selection_digest
            or admitted_intent.contract_target_id != _OBSERVATIONAL_METHOD_CONTRACT_TARGET_ID
            or admitted_intent.contract_target != _OBSERVATIONAL_METHOD_CONTRACT_TARGET
            or admitted_intent.method_fqn != outcome.method_fqn
            or admitted_intent.owned_hte_request_context
            != requested_intent.owned_hte_request_context
            or admitted_intent.source_protocol != outcome.source_protocol
            or admitted_intent.normalization != outcome.normalization
            or outcome.limitations != producer_limitations
            or admitted_intent.limitations
            != _expected_content_admitted_limitations(
                outcome.source_protocol,
                source_access_revalidation_status=_OBSERVATIONAL_SOURCE_ACCESS_STATUS,
            )
            or admitted_intent.source_access_revalidation_status
            != _OBSERVATIONAL_SOURCE_ACCESS_STATUS
        ):
            raise ValueError("observational_method_execution_outcome_binding_mismatch")
        posterior_refs = tuple(
            MethodExecutionPosteriorSummaryRef(
                point_role=summary.point_role,
                ref=summary.ref,
            )
            for summary in outcome.posterior_summary_refs
        )
        selection = DirectMethodExecutionSelection(
            job_id=job.job_id,
            run_id=str(job.run_id or ""),
            attempt=job.attempt,
            requested_source_ref=outcome.requested_source_ref,
            observational_run_intent_ref=outcome.observational_run_intent_ref,
            content_admitted_intent_ref=outcome.content_admitted_intent_ref,
            resource_policy_ref=outcome.resource_policy_ref,
            submitted_input_ref=outcome.submitted_input_ref,
            effective_input_ref=outcome.effective_input_ref,
            method_result_ref=outcome.method_result_ref,
            method_evidence_ref=outcome.method_evidence_ref,
            contract_target_id=admitted_intent.contract_target_id,
            contract_target=admitted_intent.contract_target,
            selection_digest=admitted_intent.selection_digest,
            source_access_revalidation_status=admitted_intent.source_access_revalidation_status,
            method_fqn=outcome.method_fqn,
            method_version=outcome.method_version,
            method_abi_digest=outcome.method_abi_digest,
            method_build_digest=outcome.method_build_digest,
            method_build_digest_scope=outcome.method_build_digest_scope,
            resource_policy_digest=outcome.resource_policy_digest,
            source_protocol=outcome.source_protocol,
            normalization=admitted_intent.normalization,
            limitations=admitted_intent.limitations,
            method_dispatch_binding_status=(
                outcome.method_dispatch_binding_status
                if outcome.method_dispatch_binding_status in {"recomputed", "not_established"}
                else "not_established"
            ),
            candidate_outcome=outcome.candidate_outcome,
            posterior_summary_refs=posterior_refs,
            owned_attempt_anchor_ref=outcome.owned_attempt_anchor_ref,
            hte_outcome_ref=outcome.hte_outcome_ref,
            point_result_ref=outcome.point_result_ref,
            hte_result_ref=outcome.hte_result_ref,
            inference_basis_ref=outcome.inference_basis_ref,
            refusal_diagnostic_ref=outcome.refusal_diagnostic_ref,
            invocation_basis_ref=outcome.invocation_basis_ref,
            owned_hte_request_context=admitted_intent.owned_hte_request_context,
            hte=outcome.hte_summary,
        )
        self._validate_direct_method_execution_selection_artifacts(selection)
        core_output_candidates = [
            selection.method_result_ref,
            selection.method_evidence_ref,
            selection.hte_outcome_ref,
            selection.point_result_ref,
            selection.hte_result_ref,
            selection.inference_basis_ref,
            selection.refusal_diagnostic_ref,
            selection.invocation_basis_ref,
            *(summary.ref for summary in selection.posterior_summary_refs),
        ]
        core_outputs: list[ArtifactRef] = []
        seen_output_keys: set[tuple[str, str, str, str | None]] = set()
        for reference in core_output_candidates:
            if reference is None:
                continue
            if not isinstance(reference, ArtifactRef):
                raise ValueError("observational_method_core_output_ref_invalid")
            identity_key = artifact_ref_identity_key(reference)
            if identity_key not in seen_output_keys:
                seen_output_keys.add(identity_key)
                core_outputs.append(reference)
        if not core_outputs:
            raise ValueError("observational_method_core_outputs_not_established")
        core_manifest_ref = self._finish_generation_run_context(
            job=job,
            execution_scope=execution_scope,
            core_run_id=core_run_id,
            context=core_run_context,
            outputs=core_outputs,
            status="ok",
        )
        progress = {
            "state": "completed",
            "phase": "direct_method_execution",
            "runtime_state": "candidate_only",
            "authority_path": "direct_method_candidate",
            "authority_result": "candidate_only",
            "run_id": job.run_id,
            "job_id": job.job_id,
            "attempt": job.attempt,
            "method_fqn": outcome.method_fqn,
            "method_version": outcome.method_version,
            "observational_selection_digest": selection.selection_digest,
            "method_execution_wait_policy": wait_policy.model_dump(mode="json"),
            "limitations": list(selection.limitations),
            "core_terminal_status": "ok",
            **self._core_run_progress_fields(
                job=job,
                core_run_id=core_run_id,
                manifest_ref=core_manifest_ref,
            ),
        }
        self._control_store.complete_job(
            job_id=job.job_id,
            run_id=job.run_id,
            capability_manifest_ref=capability_manifest_ref,
            progress=progress,
            method_execution_selection=selection,
            expected_lease_owner=job.lease_owner,
            expected_attempt=job.attempt,
        )
        terminal_record = self._control_store.get_job(job.job_id)
        terminal_state = terminal_record.state if terminal_record is not None else "completed"
        self._emit_runtime_diagnostic_event(
            execution_scope=execution_scope,
            job_id=job.job_id,
            run_id=job.run_id,
            execution_profile=job.effective_execution_profile,
            phase="job_execution",
            event_type="polisyos.runtime.diagnostic.phase_transition.v1",
            state_before="running",
            state_after=terminal_state,
            payload=dict(payload),
            event_payload={
                "job_kind": job.kind,
                "method_execution": "direct_candidate",
            },
            blocking_status="blocking" if terminal_state == "failed" else None,
        )

    @staticmethod
    def _selected_graph_source_refs(
        graph_output_refs: _ScientistGraphOutputRefs,
        *,
        job: ControlJobRecord,
        producer_receipt: _RuntimeGraphProducerReceipt | None,
    ) -> tuple[ArtifactRef, ArtifactRef, ArtifactRef] | None:
        """Require the final state tuple to equal an actual scoped ExecuteResult."""
        return _selected_graph_source_refs_from_receipt(
            graph_output_refs=graph_output_refs,
            receipt=producer_receipt,
            job_id=job.job_id,
            run_id=str(job.run_id or ""),
            attempt=job.attempt,
            lease_owner=job.lease_owner,
        )

    def _submit_graph_metric_projection(
        self,
        *,
        job: ControlJobRecord,
        source_refs: tuple[ArtifactRef, ArtifactRef, ArtifactRef],
    ) -> tuple[_VerifiedMethodMetricProjectionAdmissionProtocol | None, dict[str, object] | None]:
        """Run the AD01 fixed refs-only task bound to the exact final-state tuple."""
        from polisyos.scientist.compute.runner import (
            MethodMetricProjectionWork,
        )

        simulation_ref, bundle_ref, binding_ref = source_refs
        source = _RuntimeGraphMetricSource(
            job_id=job.job_id,
            run_id=str(job.run_id or ""),
            attempt=job.attempt,
            lease_owner=str(job.lease_owner or ""),
            simulation_result_ref=simulation_ref,
            method_execution_bundle_ref=bundle_ref,
            method_metric_binding_set_ref=binding_ref,
        )
        token = _RUNTIME_GRAPH_METRIC_SOURCE.set(source)
        try:
            work = MethodMetricProjectionWork(
                job_id=source.job_id,
                run_id=source.run_id,
                attempt=source.attempt,
                simulation_result_ref=simulation_ref,
                method_execution_bundle_ref=bundle_ref,
                method_metric_binding_set_ref=binding_ref,
                method_result_ref=None,
            )
            handle = self._method_backend.submit_method_metric_projection_work(work)
            completion = cast(
                "Any",
                wait_for_shared_execution(handle, self._method_metric_projection_wait_policy),
            )
        except ControlProducerWaitTimeoutError as exc:
            return None, exc.diagnostic()
        except Exception as exc:
            failure = wrap_shared_execution_exception(
                exc,
                self._method_metric_projection_wait_policy,
            )
            logger.warning(
                "Method metric projection unavailable for candidate run %s (%s: %s)",
                source.run_id,
                failure.exception_type,
                failure.code,
            )
            return None, {**failure.diagnostic(), "status": "failed"}
        finally:
            _RUNTIME_GRAPH_METRIC_SOURCE.reset(token)
        if completion.status != "completed" or completion.value is None:
            failure = getattr(completion, "failure", None)
            exception_type = getattr(failure, "exception_type", "not_established")
            code = getattr(failure, "code", "method_metric_projection_not_established")
            retryable = getattr(failure, "retryable", False)
            failure_diagnostic = ControlProducerExecutionError(
                resolution=self._method_metric_projection_wait_policy,
                exception_type=(
                    exception_type if isinstance(exception_type, str) else "not_established"
                ),
                code=code if isinstance(code, str) else "method_metric_projection_not_established",
                retryable=retryable if type(retryable) is bool else False,
            ).diagnostic()
            return None, {**failure_diagnostic, "status": "failed"}
        admission = completion.value.admission
        try:
            from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
                is_verified_method_metric_projection_admission,
            )

            if not is_verified_method_metric_projection_admission(admission):
                return None, {"code": "method_metric_projection_receipt_invalid"}
        except ImportError, AttributeError:
            return None, {"code": "method_metric_projection_verifier_unavailable"}
        source_tuple = admission.source_tuple
        source_candidate_ref = getattr(admission, "source_candidate_ref", None)
        if (
            source_tuple.job_id != source.job_id
            or source_tuple.run_id != source.run_id
            or source_tuple.attempt != source.attempt
            or source_tuple.method_result_ref is not None
            or source_tuple.simulation_result_ref != simulation_ref
            or source_tuple.method_execution_bundle_ref != bundle_ref
            or source_tuple.method_metric_binding_set_ref != binding_ref
            or not isinstance(source_candidate_ref, ArtifactRef)
            or source_candidate_ref.kind != "scientist.policy_design.candidate"
            or source_candidate_ref.media_type != "application/json"
            or source_candidate_ref.manifest_profile_sha256 is None
        ):
            return None, {"code": "method_metric_projection_source_tuple_mismatch"}
        return admission, None

    def _graph_method_execution_selection(
        self,
        *,
        job: ControlJobRecord,
        graph_output_refs: _ScientistGraphOutputRefs,
        source_experiment_state_ref: ArtifactRef | None,
        producer_receipt: _RuntimeGraphProducerReceipt | None,
    ) -> tuple[Any, Any | None, dict[str, object] | None] | None:
        """Prepare an exact graph source selection and optional verified vector receipt."""
        from polisyos.core.contracts.runtime import GraphMethodExecutionSelection

        source_refs = self._selected_graph_source_refs(
            graph_output_refs,
            job=job,
            producer_receipt=producer_receipt,
        )
        if (
            source_refs is None
            or not isinstance(source_experiment_state_ref, ArtifactRef)
            or source_experiment_state_ref.kind != "scientist.experiment_state"
            or source_experiment_state_ref.media_type != "application/json"
            or source_experiment_state_ref.manifest_profile_sha256 is None
        ):
            return None
        admission, wait_diagnostic = self._submit_graph_metric_projection(
            job=job,
            source_refs=source_refs,
        )
        projection = None
        source_candidate_ref = None
        status: Literal["verified", "verification_missing"] = "verification_missing"
        if admission is not None:
            from polisyos.core.contracts.runtime import MethodMetricProjectionSelection

            projection = MethodMetricProjectionSelection(
                vector_ref=admission.vector_ref,
                verifier_revision=admission.verifier_revision,
                verifier_implementation_sha256=admission.verifier_implementation_sha256,
            )
            source_candidate_ref = admission.source_candidate_ref
            status = "verified"
        selection = GraphMethodExecutionSelection(
            job_id=job.job_id,
            run_id=str(job.run_id or ""),
            attempt=job.attempt,
            method_result_ref=None,
            source_experiment_state_ref=source_experiment_state_ref,
            simulation_result_ref=source_refs[0],
            method_execution_bundle_ref=source_refs[1],
            method_metric_binding_set_ref=source_refs[2],
            source_candidate_ref=source_candidate_ref,
            metric_verification_status=status,
            method_metric_projection=projection,
            metric_projection_wait_policy=self._method_metric_projection_wait_policy,
        )
        return selection, admission, wait_diagnostic

    def get_job_status(
        self,
        job_id: str,
        *,
        request_id: str | None = None,
    ) -> ControlJobResponse:
        """Return durable job state or raise `KeyError` so the route renders a 404 problem."""
        record = self._control_store.get_job(job_id)
        if record is None:
            raise KeyError(job_id)
        if record.state == "cancelled":
            record = self._control_store.get_cancelled_job_verified_record(job_id)
        return self._current_normative_job_record(record).to_response(request_id=request_id)

    def cancel_job(
        self,
        *,
        job_id: str,
        request: ControlJobCancellationRequest,
        authorization_proof: object,
        request_id: str | None = None,
    ) -> ControlJobResponse:
        """Consume one current sealed job-owned permission and fence its exact attempt."""
        from polisyos.runtime.http.authorization import BoundActionPermissionVerification
        from polisyos.runtime.http.permissions import RuntimePermission
        from polisyos.runtime.http.resource_binding import (
            BindingAuthority,
            BoundAuthorizationResource,
        )

        if type(authorization_proof) is not BoundActionPermissionVerification:
            raise forbidden("Cancellation authorization proof is invalid")
        verification = authorization_proof.verification
        bound = authorization_proof.bound_resource
        if (
            verification.requirement.permission is not RuntimePermission.JOBS_CANCEL
            or type(bound) is not BoundAuthorizationResource
            or bound.authority is not BindingAuthority.OWNERSHIP_VERIFIED
            or bound.requirement is not verification.requirement
            or bound.tenant_id != verification.tenant_id
            or dict(bound.canonical_selectors).get("job_id") != json.dumps(job_id)
            or not isinstance(dict(bound.canonical_selectors).get("cell_id"), str)
        ):
            raise forbidden("Cancellation proof is not bound to this exact job")
        record = self._control_store.cancel_job(
            job_id=job_id,
            authorization_proof=authorization_proof,
            operation_id=request.operation_id,
            expected_lease_owner=request.expected_lease_owner,
            expected_attempt=request.expected_attempt,
        )
        verified_record = self._control_store.get_cancelled_job_verified_record(record.job_id)
        return verified_record.to_response(request_id=request_id)

    def get_method_execution_selection(
        self,
        *,
        run_id: str,
        tenant_id: str,
        cell_id: str | None,
    ) -> MethodExecutionSelection | None:
        """Read the sole completed workflow selection after the route has authorized scope.

        The route supplies its already-verified run tenant and cell. This lookup reads
        only the fenced control-job row and immutable creation event; it never reads
        method payloads, vectors, simulation arrays, or compute state.
        """
        from polisyos.core.contracts.runtime import (
            DirectMethodExecutionSelection,
            GraphMethodExecutionSelection,
            _validate_method_execution_selection_wire_payload,
        )

        if not run_id or not tenant_id:
            return None
        try:
            record = self._control_store.get_unique_completed_job_by_run_and_kind(
                run_id=run_id,
                kind="workflow_run",
            )
            if record is None or record.method_execution_selection is None:
                return None
            created = self._control_store.get_job_created_event_payload(record.job_id)
        except RuntimeError, ValueError:
            return None
        if (
            created.get("job_id") != record.job_id
            or created.get("run_id") != run_id
            or created.get("job_kind") != "workflow_run"
        ):
            return None
        execution_scope = created.get("execution_scope")
        if not isinstance(execution_scope, Mapping):
            return None
        if (
            execution_scope.get("tenant_id") != tenant_id
            or execution_scope.get("cell_id") != cell_id
        ):
            return None
        try:
            selection = _validate_method_execution_selection_wire_payload(
                record.method_execution_selection
            )
        except TypeError, ValueError:
            return None
        if (
            selection.job_id != record.job_id
            or selection.run_id != run_id
            or selection.attempt != record.attempt
        ):
            return None
        if isinstance(selection, DirectMethodExecutionSelection):
            try:
                self._validate_direct_method_execution_selection_artifacts(selection)
            except OSError, RuntimeError, TypeError, ValueError:
                return None
        if isinstance(selection, GraphMethodExecutionSelection):
            terminal_state_ref = self._terminal_experiment_state_ref_for_control_job(
                job_id=record.job_id,
                run_id=run_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            if terminal_state_ref != selection.source_experiment_state_ref:
                return None
        return selection

    def _resolve_observational_method_core_run_binding(
        self,
        *,
        control_run_id: str,
        tenant_id: str,
        cell_id: str,
    ) -> tuple[str, str] | None:
        """Resolve only a current scoped direct-method job to its actual Core attempt.

        Pending requests stay on the control-jobs surface. Active attempts bind the
        current lease row to the running event's owner and attempt; the event expiry
        is the initial lease and may differ after a renewal. Terminal attempts require
        the released owner row, exact terminal event, selected Core manifest, and
        persisted attempt pointer to agree. The returned identity is the Core run ID,
        never a relabelled stable control-run ID.
        """
        from polisyos.runtime.http.services.adapters.core_run import (
            derive_control_job_core_run_id,
            load_terminal_core_run_source,
        )
        from polisyos.runtime.http.services.control_plane_store import (
            _control_job_execution_scope_from_event,
            _iso,
            _parse_dt,
        )

        if (
            type(control_run_id) is not str
            or not control_run_id.strip()
            or type(tenant_id) is not str
            or not tenant_id.strip()
            or type(cell_id) is not str
            or not cell_id.strip()
        ):
            return None
        control_store = self._control_store
        try:
            record = control_store.get_latest_job_by_run(control_run_id)
        except (RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("observational_method_core_owner_read_failed") from exc
        if record is None or record.run_id != control_run_id or record.kind != "workflow_run":
            return None
        if record.state not in {"running", "completed", "failed"}:
            return None
        try:
            created_event = control_store._get_job_created_source_event_record(record.job_id)
            scope = _control_job_execution_scope_from_event(created_event.payload)
        except (RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("observational_method_core_creation_owner_invalid") from exc
        creation = created_event.payload
        if (
            created_event.event_type != "job_created"
            or created_event.job_id != record.job_id
            or creation.get("job_id") != record.job_id
            or creation.get("run_id") != control_run_id
            or creation.get("job_kind") != "workflow_run"
        ):
            raise ValueError("observational_method_core_creation_identity_mismatch")
        marker = creation.get(_OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY)
        if not isinstance(marker, Mapping):
            return None
        try:
            requested_source_ref = ArtifactRef.model_validate(
                marker["requested_source_ref"], strict=True
            )
            intent_ref = ArtifactRef.model_validate(
                marker["observational_run_intent_ref"], strict=True
            )
            selection_digest = marker["observational_selection_digest"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("observational_method_core_creation_marker_invalid") from exc
        if (
            requested_source_ref.manifest_profile_sha256 is None
            or intent_ref.manifest_profile_sha256 is None
            or type(selection_digest) is not str
            or len(selection_digest) != 64
            or any(character not in "0123456789abcdef" for character in selection_digest)
            or scope.status != "established"
            or scope.tenant_id != tenant_id
            or scope.cell_id != cell_id
        ):
            raise ValueError("observational_method_core_creation_scope_or_marker_invalid")
        if type(record.attempt) is not int or record.attempt < 1:
            raise ValueError("observational_method_core_attempt_invalid")
        core_run_id = derive_control_job_core_run_id(
            job_id=record.job_id,
            control_run_id=control_run_id,
            attempt=record.attempt,
        )
        try:
            running_event = control_store._latest_control_job_lifecycle_event_record(
                job_id=record.job_id,
                event_type="job_running",
            )
        except (RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("observational_method_core_running_event_unavailable") from exc
        running_payload = running_event.payload
        running_owner = running_payload.get("lease_owner")
        running_lease_expires_at_raw = running_payload.get("lease_expires_at")
        try:
            running_lease_expires_at = _parse_dt(running_lease_expires_at_raw)
        except (OverflowError, TypeError, ValueError) as exc:
            raise ValueError("observational_method_core_running_fence_mismatch") from exc
        if (
            running_event.event_type != "job_running"
            or running_event.job_id != record.job_id
            or running_payload.get("state") != "running"
            or type(running_payload.get("attempt")) is not int
            or running_payload.get("attempt") != record.attempt
            or type(running_lease_expires_at_raw) is not str
            or running_lease_expires_at is None
            or running_lease_expires_at.tzinfo is None
            or running_lease_expires_at_raw != _iso(running_lease_expires_at)
            or running_event.created_at >= running_lease_expires_at
            or type(running_owner) is not str
            or not running_owner.strip()
            or record.started_at is None
            or running_event.event_id <= created_event.event_id
            or running_event.created_at < created_event.created_at
            or running_event.created_at < record.started_at
        ):
            raise ValueError("observational_method_core_running_fence_mismatch")

        terminal_event = None
        if record.state == "running":
            if (
                record.lease_owner != running_owner
                or record.lease_expires_at is None
                or record.lease_expires_at.tzinfo is None
                or record.lease_expires_at <= datetime.now(UTC)
                or record.finished_at is not None
            ):
                raise ValueError("observational_method_core_live_lease_unavailable")
        else:
            expected_event_type = "job_completed" if record.state == "completed" else "job_failed"
            try:
                terminal_event = control_store.get_job_terminal_source_event_record(record.job_id)
            except (RuntimeError, TypeError, ValueError) as exc:
                raise ValueError("observational_method_core_terminal_event_unavailable") from exc
            terminal_payload = terminal_event.payload
            if (
                record.lease_owner is not None
                or record.lease_expires_at is not None
                or record.finished_at is None
                or terminal_event.event_type != expected_event_type
                or terminal_event.job_id != record.job_id
                or terminal_payload.get("state") != record.state
                or terminal_payload.get("lease_owner") != running_owner
                or type(terminal_payload.get("attempt")) is not int
                or terminal_payload.get("attempt") != record.attempt
                or terminal_event.event_id <= running_event.event_id
                or terminal_event.created_at < running_event.created_at
                or terminal_event.created_at < record.finished_at
            ):
                raise ValueError("observational_method_core_terminal_fence_mismatch")
            progress = record.progress
            if (
                not isinstance(progress, Mapping)
                or progress.get("state") != record.state
                or progress.get("job_id") != record.job_id
                or progress.get("run_id") != control_run_id
                or type(progress.get("attempt")) is not int
                or progress.get("attempt") != record.attempt
                or progress.get("phase") != "direct_method_execution"
                or progress.get("core_run_id") != core_run_id
                or type(progress.get("core_run_attempt")) is not int
                or progress.get("core_run_attempt") != record.attempt
                or progress.get("core_terminal_status")
                != ("ok" if record.state == "completed" else "error")
            ):
                raise ValueError("observational_method_core_terminal_pointer_mismatch")
            try:
                manifest_ref = ArtifactRef.model_validate(
                    progress.get("core_manifest_artifact_ref"), strict=True
                )
                terminal = load_terminal_core_run_source(
                    store=self._artifact_store,
                    core_runs_root=self._core_runs_root,
                    run_id=core_run_id,
                )
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                raise ValueError("observational_method_core_terminal_source_unavailable") from exc
            expected_status = "ok" if record.state == "completed" else "error"
            if (
                manifest_ref.manifest_profile_sha256 is None
                or not _same_selected_artifact_ref(terminal.manifest_ref, manifest_ref)
                or progress.get("manifest_ref") != str(manifest_ref.artifact_id)
                or terminal.run_id != core_run_id
                or terminal.manifest.run_id != core_run_id
                or terminal.manifest.control_job_id != record.job_id
                or terminal.manifest.status != expected_status
                or terminal.manifest.tenant_id != tenant_id
                or terminal.manifest.cell_id != cell_id
                or terminal.manifest.execution_profile != record.effective_execution_profile
            ):
                raise ValueError("observational_method_core_terminal_source_mismatch")

        # Re-read the owner row and the decisive event after any Core read. A retry,
        # lease turnover, or new terminal event invalidates this alias.
        try:
            latest = control_store.get_latest_job_by_run(control_run_id)
            latest_created = control_store._get_job_created_source_event_record(record.job_id)
            latest_running = control_store._latest_control_job_lifecycle_event_record(
                job_id=record.job_id,
                event_type="job_running",
            )
            latest_terminal = (
                control_store.get_job_terminal_source_event_record(record.job_id)
                if terminal_event is not None
                else None
            )
        except (RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("observational_method_core_owner_readback_failed") from exc
        if (
            latest is None
            or latest.job_id != record.job_id
            or latest.run_id != control_run_id
            or latest.kind != "workflow_run"
            or latest.state != record.state
            or latest.attempt != record.attempt
            or latest.lease_owner != record.lease_owner
            or latest.lease_expires_at != record.lease_expires_at
            or latest.started_at != record.started_at
            or latest.finished_at != record.finished_at
            or latest.progress != record.progress
            or latest.effective_execution_profile != record.effective_execution_profile
            or latest.capability_manifest_ref != record.capability_manifest_ref
            or latest_created.event_type != "job_created"
            or latest_created.job_id != created_event.job_id
            or latest_created.event_id != created_event.event_id
            or latest_created.created_at != created_event.created_at
            or latest_created.payload_sha256 != created_event.payload_sha256
            or latest_running.event_id != running_event.event_id
            or latest_running.event_type != running_event.event_type
            or latest_running.job_id != running_event.job_id
            or latest_running.created_at != running_event.created_at
            or latest_running.payload_sha256 != running_event.payload_sha256
            or (
                record.state == "running"
                and (
                    latest.lease_expires_at is None
                    or latest.lease_expires_at.tzinfo is None
                    or latest.lease_expires_at <= datetime.now(UTC)
                )
            )
            or (
                terminal_event is not None
                and (
                    latest_terminal is None
                    or latest_terminal.event_id != terminal_event.event_id
                    or latest_terminal.event_type != terminal_event.event_type
                    or latest_terminal.job_id != terminal_event.job_id
                    or latest_terminal.created_at != terminal_event.created_at
                    or latest_terminal.payload_sha256 != terminal_event.payload_sha256
                )
            )
        ):
            raise ValueError("observational_method_core_owner_changed_during_resolution")
        return core_run_id, record.job_id

    def get_observational_method_run_projection(
        self,
        *,
        run_id: str,
        expected_job_id: str | None,
        tenant_id: str,
        cell_id: str | None,
    ) -> _DirectMethodExecutionRunProjection:
        """Read a current direct-method request and selection from fenced owner state.

        The route authorizes the selected review view before this lookup. It reads the
        durable job row, the small direct-run payload marker, and bounded intent and
        evidence artifacts. It never materializes method result arrays.
        """

        from polisyos.core.contracts.owned_attempt_anchor import OwnedAttemptAnchorRef
        from polisyos.core.contracts.runtime import (
            ContentAdmittedObservationalRunIntent,
            DirectMethodExecutionRequestSummary,
            DirectMethodExecutionRunProjection,
            DirectMethodExecutionSelection,
            DirectMethodExecutionTimeRoles,
            MethodExecutionCandidateOutcome,
            ObservationalRunIntent,
            _validate_method_execution_selection_wire_payload,
        )

        reader_at = datetime.now(UTC)

        def unavailable(
            limitation: Literal[
                "execution_outcome_not_established",
                "selection_persistence_not_established",
            ],
            *,
            request: DirectMethodExecutionRequestSummary | None = None,
            record: ControlJobRecord | None = None,
        ) -> DirectMethodExecutionRunProjection:
            roles = None
            if request is not None:
                roles = DirectMethodExecutionTimeRoles(
                    execution_started_at=record.started_at if record is not None else None,
                    execution_finished_at=record.finished_at if record is not None else None,
                    owner_verified_at=datetime.now(UTC),
                    reader_at=reader_at,
                )
            return DirectMethodExecutionRunProjection(
                status="unavailable",
                request=request,
                time_roles=roles,
                limitations=(limitation,),
            )

        if not run_id or not tenant_id:
            return unavailable("execution_outcome_not_established")
        if not expected_job_id:
            return DirectMethodExecutionRunProjection(
                status="absent",
                limitations=("no_direct_method_request",),
            )
        try:
            record = self._control_store.get_job(expected_job_id)
            if record is None:
                return unavailable("execution_outcome_not_established")
            created = self._control_store.get_job_created_event_payload(record.job_id)
        except OSError, RuntimeError, TypeError, ValueError:
            return unavailable("execution_outcome_not_established")
        if (
            record.job_id != expected_job_id
            or record.run_id != run_id
            or created.get("job_id") != record.job_id
            or created.get("run_id") != run_id
            or created.get("job_kind") != record.kind
        ):
            return unavailable("execution_outcome_not_established", record=record)
        if record.kind != "workflow_run":
            return DirectMethodExecutionRunProjection(
                status="absent",
                limitations=("no_direct_method_request",),
            )
        execution_scope = created.get("execution_scope")
        if not isinstance(execution_scope, Mapping) or (
            execution_scope.get("tenant_id") != tenant_id
            or execution_scope.get("cell_id") != cell_id
        ):
            return unavailable("execution_outcome_not_established", record=record)
        marker = created.get(_OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY)
        if not isinstance(marker, Mapping):
            raw_selection = record.method_execution_selection
            if isinstance(raw_selection, Mapping) and raw_selection.get("selection_kind") == (
                "direct_method"
            ):
                return DirectMethodExecutionRunProjection(
                    status="legacy_unbound",
                    limitations=("legacy_selection_unbound",),
                )
            return DirectMethodExecutionRunProjection(
                status="absent",
                limitations=("no_direct_method_request",),
            )
        try:
            requested_source_ref = ArtifactRef.model_validate(marker["requested_source_ref"])
            intent_ref = ArtifactRef.model_validate(marker["observational_run_intent_ref"])
            selection_digest = marker["observational_selection_digest"]
            if (
                requested_source_ref.manifest_profile_sha256 is None
                or intent_ref.manifest_profile_sha256 is None
                or type(selection_digest) is not str
            ):
                return unavailable("execution_outcome_not_established", record=record)
            intent = self._read_bounded_intent_model(
                intent_ref,
                model=ObservationalRunIntent,
            )
            if (
                intent.job_id != record.job_id
                or intent.run_id != run_id
                or intent.requested_source_ref != requested_source_ref
                or intent.resource_policy_ref is None
                or intent.resource_policy_ref.manifest_profile_sha256 is None
                or intent.selection_digest() != selection_digest
                or (
                    intent.method_version == "2.0.0"
                    and intent.method_fqn not in _OBSERVATIONAL_METHOD_FQN_V2
                )
                or (
                    intent.method_version != "2.0.0"
                    and intent.method_fqn != f"causal.hte.forest_dr@{intent.method_version}"
                )
            ):
                return unavailable("execution_outcome_not_established", record=record)
            resolved_params_bytes = json.dumps(
                intent.resolved_params,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            request_summary = DirectMethodExecutionRequestSummary(
                requested_source_ref=requested_source_ref,
                requested_intent_ref=intent_ref,
                resource_policy_ref=intent.resource_policy_ref,
                source_protocol=intent.protocol,
                method_fqn=intent.method_fqn,
                method_version=intent.method_version,
                owned_hte_request_context=intent.owned_hte_request_context,
                method_abi_digest=intent.method_abi_digest,
                method_build_digest=intent.method_build_digest,
                method_build_digest_scope=intent.method_build_digest_scope,
                resource_policy_digest=intent.resource_policy_digest,
                resolved_params_sha256=hashlib.sha256(resolved_params_bytes).hexdigest(),
                seed=intent.seed,
                seed_policy_revision=intent.seed_policy_revision,
                required_estimator_n_jobs=intent.resource_policy.required_estimator_n_jobs,
                max_manifest_bytes=intent.resource_policy.max_manifest_bytes,
                max_bytes=intent.resource_policy.max_bytes,
                max_depth=intent.resource_policy.max_depth,
                max_elements=intent.resource_policy.max_elements,
                requested_at=intent.created_at,
            )
        except OSError, RuntimeError, TypeError, ValueError:
            return unavailable("execution_outcome_not_established", record=record)

        def time_roles(
            *,
            admitted_at: datetime | None = None,
            owner_verified_at: datetime | None = None,
        ) -> DirectMethodExecutionTimeRoles:
            return DirectMethodExecutionTimeRoles(
                admitted_at=admitted_at,
                execution_started_at=record.started_at,
                execution_finished_at=record.finished_at,
                owner_verified_at=owner_verified_at or datetime.now(UTC),
                reader_at=reader_at,
            )

        if record.state in {"pending", "queued", "running"}:
            return DirectMethodExecutionRunProjection(
                status="accepted_pending",
                request=request_summary,
                time_roles=time_roles(),
                limitations=("candidate_execution_pending",),
            )
        if record.state == "failed":
            try:
                terminal_event = self._control_store.get_job_terminal_source_event_record(
                    record.job_id
                )
                terminal_payload = getattr(terminal_event, "payload", None)
                if (
                    getattr(terminal_event, "event_type", None) == "job_failed"
                    and isinstance(terminal_payload, Mapping)
                    and terminal_payload.get("owned_attempt_failure_disposition") == "input_refused"
                ):
                    anchor_ref = OwnedAttemptAnchorRef.model_validate(
                        terminal_payload.get("owned_attempt_anchor_ref"), strict=True
                    )
                    refusal_association = self.resolve_owned_attempt_anchor_refusal_association(
                        anchor_ref=anchor_ref
                    )
                    if (
                        refusal_association.job_id != record.job_id
                        or refusal_association.run_id != run_id
                        or refusal_association.attempt != record.attempt
                        or not _same_selected_artifact_ref(
                            refusal_association.requested_source_ref,
                            requested_source_ref,
                        )
                        or not _same_selected_artifact_ref(
                            refusal_association.observational_run_intent_ref,
                            intent_ref,
                        )
                        or not _same_selected_artifact_ref(
                            refusal_association.resource_policy_ref,
                            intent.resource_policy_ref,
                        )
                        or refusal_association.job_failed_event.event_id != terminal_event.event_id
                        or refusal_association.job_failed_event.payload_sha256
                        != terminal_event.payload_sha256
                    ):
                        return unavailable(
                            "execution_outcome_not_established",
                            request=request_summary,
                            record=record,
                        )
                    return DirectMethodExecutionRunProjection(
                        status="input_refused",
                        request=request_summary,
                        input_refusal=refusal_association,
                        time_roles=time_roles(owner_verified_at=refusal_association.verified_at),
                        refusal_code="observational_input_refused",
                        limitations=("input_refused_before_dispatch",),
                    )
            except OSError, RuntimeError, TypeError, ValueError:
                return unavailable(
                    "execution_outcome_not_established",
                    request=request_summary,
                    record=record,
                )
            return DirectMethodExecutionRunProjection(
                status="execution_failed",
                request=request_summary,
                time_roles=time_roles(),
                limitations=("execution_outcome_not_established",),
            )
        if record.state != "completed" or record.method_execution_selection is None:
            return unavailable(
                "selection_persistence_not_established",
                request=request_summary,
                record=record,
            )
        try:
            selection = _validate_method_execution_selection_wire_payload(
                record.method_execution_selection
            )
            if type(selection) is not DirectMethodExecutionSelection:
                return unavailable(
                    "selection_persistence_not_established",
                    request=request_summary,
                    record=record,
                )
            if (
                selection.job_id != record.job_id
                or selection.run_id != run_id
                or selection.attempt != record.attempt
                or selection.observational_run_intent_ref != intent_ref
                or selection.requested_source_ref != requested_source_ref
                or selection.selection_digest != selection_digest
                or selection.method_fqn != request_summary.method_fqn
                or selection.method_version != request_summary.method_version
            ):
                return unavailable(
                    "selection_persistence_not_established",
                    request=request_summary,
                    record=record,
                )
            self._validate_direct_method_execution_selection_artifacts(selection)
            is_successor_selection = selection.method_fqn in _OBSERVATIONAL_METHOD_FQN_V2
            if is_successor_selection:
                if (
                    selection.candidate_outcome is not None
                    or selection.owned_attempt_anchor_ref is None
                    or selection.hte is None
                ):
                    return unavailable(
                        "selection_persistence_not_established",
                        request=request_summary,
                        record=record,
                    )
            elif type(selection.candidate_outcome) is not MethodExecutionCandidateOutcome:
                return unavailable(
                    "selection_persistence_not_established",
                    request=request_summary,
                    record=record,
                )
            admitted_intent = self._read_bounded_intent_model(
                selection.content_admitted_intent_ref,
                model=ContentAdmittedObservationalRunIntent,
            )
            if (
                admitted_intent.job_id != record.job_id
                or admitted_intent.run_id != run_id
                or admitted_intent.attempt != record.attempt
                or admitted_intent.requested_intent_ref != intent_ref
                or admitted_intent.selection_digest != selection_digest
            ):
                return unavailable(
                    "selection_persistence_not_established",
                    request=request_summary,
                    record=record,
                )
            if is_successor_selection:
                if selection.hte is None:
                    return unavailable(
                        "selection_persistence_not_established",
                        request=request_summary,
                        record=record,
                    )
                projection_association = self.resolve_owned_attempt_anchor_projection_association(
                    run_id=run_id,
                    expected_job_id=record.job_id,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                )
                summary_bytes = json.dumps(
                    selection.hte.model_dump(mode="json"),
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                expected_summary_sha256 = hashlib.sha256(summary_bytes).hexdigest()
                summary_ref_pairs = (
                    (
                        projection_association.anchor_ref,
                        selection.hte.owned_attempt_anchor_ref,
                    ),
                    (projection_association.outcome_ref, selection.hte.hte_outcome_ref),
                    (projection_association.source_data_ref, selection.hte.source_data_ref),
                    (
                        projection_association.resource_policy_ref,
                        selection.hte.resource_evidence.owner_policy_ref,
                    ),
                    (projection_association.method_result_ref, selection.hte.method_result_ref),
                    (
                        projection_association.method_evidence_ref,
                        selection.hte.method_evidence_ref,
                    ),
                    (projection_association.point_result_ref, selection.hte.point_result_ref),
                    (
                        projection_association.hte_result_ref,
                        selection.hte.hte_result_ref,
                    ),
                    (
                        projection_association.inference_basis_ref,
                        selection.hte.inference_basis_ref,
                    ),
                    (
                        projection_association.refusal_diagnostic_ref,
                        selection.hte.refusal_diagnostic_ref,
                    ),
                )
                if (
                    projection_association.status != "owner_projection_reconciled"
                    or projection_association.content_validation_status
                    != "worker_admitted_not_recomputed"
                    or projection_association.manifest_identity_status != "independently_reconciled"
                    or projection_association.job_id != record.job_id
                    or projection_association.run_id != run_id
                    or projection_association.attempt != record.attempt
                    or projection_association.tenant_id != tenant_id
                    or projection_association.cell_id != cell_id
                    or projection_association.outcome_kind != selection.hte.kind
                    or projection_association.selected_summary_sha256 != expected_summary_sha256
                    or projection_association.job_completed_event.event_type != "job_completed"
                    or projection_association.job_completed_event.job_id != record.job_id
                    or projection_association.invocation_basis_ref is not None
                    or any(
                        not _same_optional_artifact_ref_payload(proof_ref, summary_ref)
                        for proof_ref, summary_ref in summary_ref_pairs
                    )
                ):
                    return unavailable(
                        "selection_persistence_not_established",
                        request=request_summary,
                        record=record,
                    )
        except OSError, RuntimeError, TypeError, ValueError:
            return unavailable(
                "selection_persistence_not_established",
                request=request_summary,
                record=record,
            )
        return DirectMethodExecutionRunProjection(
            status="selected",
            request=request_summary,
            selection=selection,
            time_roles=time_roles(admitted_at=admitted_intent.admitted_at),
            limitations=selection.limitations,
        )

    def read_current_admitted_method_metric_projection(
        self,
        *,
        run_id: str,
        tenant_id: str,
        cell_id: str,
    ) -> _CurrentMethodMetricProjectionReadResult:
        """Read the current owner-selected AD01 projection with bounded CAS reads."""
        from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
            _MethodMetricProjectionArtifactReader,
            read_current_admitted_method_metric_projection,
        )

        store = _require_bounded_store_protocol(
            self._artifact_store,
            _MethodMetricProjectionArtifactReader,
            limits=self._observational_read_limits(),
            refusal_code="canon_profile_bounded_stream_unavailable",
            failure_stage="method_metric_projection_reader_preflight",
        )
        return read_current_admitted_method_metric_projection(
            store,
            owner=self,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )

    def read_current_completed_ex_ante_candidate_score(
        self,
        *,
        run_id: str,
        tenant_id: str,
        cell_id: str,
    ) -> MethodMetricCandidateScore:
        """Reopen one authorized completed source and recompute a candidate score."""
        from polisyos.core.contracts.runtime import MethodMetricCandidateScore
        from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
            _MethodMetricProjectionArtifactStore,
            read_completed_admitted_method_metric_projection,
            recompute_completed_ex_ante_rank_projection,
        )

        def limited(reason: str) -> MethodMetricCandidateScore:
            return MethodMetricCandidateScore(status="verification_missing", limitations=(reason,))

        try:
            selection = self.get_method_execution_selection(
                run_id=run_id, tenant_id=tenant_id, cell_id=cell_id
            )
            candidate_ref = getattr(selection, "source_candidate_ref", None)
            if not isinstance(candidate_ref, ArtifactRef):
                return limited("completed_candidate_selection_not_established")
            store = _require_bounded_store_protocol(
                self._artifact_store,
                _MethodMetricProjectionArtifactStore,
                limits=self._observational_read_limits(),
                refusal_code="canon_profile_bounded_stream_unavailable",
                failure_stage="completed_ex_ante_rank_reader_preflight",
            )
            read = read_completed_admitted_method_metric_projection(
                store,
                owner=self,
                source_run_id=run_id,
                candidate_ref=candidate_ref,
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            if read.status != "selected" or read.basis is None:
                return limited("completed_candidate_selection_not_established")
            basis = read.basis
            identity = (
                basis.cache_source_identity(),
                basis.candidate_ref,
                basis.source_state_ref,
                basis.vector_ref,
                basis.verifier_revision,
                basis.verifier_implementation_sha256,
            )
            score = recompute_completed_ex_ante_rank_projection(
                store, basis=basis, candidate_ref=candidate_ref
            )
            if score.status != "selected":
                return limited("completed_ex_ante_profile_not_established")
            # The source may have been revoked or replaced while the bounded
            # replay was running. Reselect through Runtime before emission.
            current = read_completed_admitted_method_metric_projection(
                store,
                owner=self,
                source_run_id=run_id,
                candidate_ref=candidate_ref,
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            if current.status != "selected" or current.basis is None:
                return limited("completed_candidate_selection_no_longer_current")
            basis = current.basis
            if (
                basis.cache_source_identity(),
                basis.candidate_ref,
                basis.source_state_ref,
                basis.vector_ref,
                basis.verifier_revision,
                basis.verifier_implementation_sha256,
            ) != identity:
                return limited("completed_candidate_selection_changed_during_replay")
            return MethodMetricCandidateScore(
                status="selected",
                candidate_ref=candidate_ref,
                source_vector_ref=basis.vector_ref,
                minimized_score=score.minimized_score,
                maximizing_coordinate=score.maximizing_coordinate,
                comparison_contract_sha256=score.comparison_contract_sha256,
            )
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            return limited("completed_candidate_source_replay_unavailable")

    def read_current_completed_ex_ante_comparison(
        self,
        *,
        run_id: str,
        tenant_id: str,
        cell_id: str,
    ) -> CompletedExAnteCandidateRanking | None:
        """Replay a completed run's bounded candidate comparison under live scope."""
        from types import SimpleNamespace

        from polisyos.core.artifacts import read_core_json_artifact_bounded
        from polisyos.core.artifacts.canonical_profile import validate_core_model_bounded_read
        from polisyos.core.contracts.runtime import (
            CompletedExAnteCandidateRanking,
            CompletedExAnteComparisonRequest,
        )
        from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry
        from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
            _MethodMetricProjectionArtifactStore,
        )
        from polisyos.scientist.orchestration.engine.state import ExperimentState

        def limited(reason: str) -> CompletedExAnteCandidateRanking:
            return CompletedExAnteCandidateRanking(
                status="verification_missing", limitations=(reason,)
            )

        try:
            record = self._control_store.get_unique_completed_job_by_run_and_kind(
                run_id=run_id, kind="workflow_run"
            )
            if record is None:
                return limited("completed_comparison_run_not_established")
            created = self._control_store.get_job_created_event_payload(record.job_id)
            scope = created.get("execution_scope")
            if (
                created.get("job_id") != record.job_id
                or created.get("run_id") != run_id
                or created.get("job_kind") != "workflow_run"
                or not isinstance(scope, Mapping)
                or scope.get("tenant_id") != tenant_id
                or scope.get("cell_id") != cell_id
            ):
                return limited("completed_comparison_run_scope_not_established")
            state_ref = self._terminal_experiment_state_ref_for_control_job(
                job_id=record.job_id, run_id=run_id, tenant_id=tenant_id, cell_id=cell_id
            )
            if state_ref is None:
                return limited("completed_comparison_run_state_not_established")
            store = _require_bounded_store_protocol(
                self._artifact_store,
                _MethodMetricProjectionArtifactStore,
                limits=self._observational_read_limits(),
                refusal_code="canon_profile_bounded_stream_unavailable",
                failure_stage="completed_ex_ante_comparison_reader_preflight",
            )
            read = read_core_json_artifact_bounded(
                store, state_ref, limits=self._observational_read_limits()
            )
            schema = read.manifest.artifact_schema
            if (
                read.manifest.kind != "scientist.experiment_state"
                or read.manifest.media_type != "application/json"
                or schema is None
                or schema.name != "polisyos.scientist.orchestration.engine.ExperimentState"
            ):
                return limited("completed_comparison_run_state_contract_invalid")
            state = validate_core_model_bounded_read(ExperimentState, read)
            if state.run_id != run_id or state.schema_version != schema.version:
                return limited("completed_comparison_run_state_binding_invalid")
            if "policy_search_completed_ex_ante_comparison" not in state.params:
                return None
            try:
                request = CompletedExAnteComparisonRequest.model_validate(
                    state.params["policy_search_completed_ex_ante_comparison"]
                )
            except (TypeError, ValueError):
                return CompletedExAnteCandidateRanking(
                    status="invalid",
                    limitations=("completed_comparison_run_comparison_request_invalid",),
                )
            # This context is constructed by the actual Runtime service only
            # after the completed job and scoped terminal receipt have been read.
            # The service itself is the existing Runtime selection owner.
            context = SimpleNamespace(
                store=store,
                method_metric_selection_owner=self,
                run=SimpleNamespace(tenant_id=tenant_id, cell_id=cell_id),
            )
            result = ParetoRegistry.rank_completed_ex_ante_candidates(
                ctx=context, sources=request.sources
            )
            current = self._control_store.get_unique_completed_job_by_run_and_kind(
                run_id=run_id, kind="workflow_run"
            )
            if (
                current is None
                or current.job_id != record.job_id
                or current.attempt != record.attempt
                or self._terminal_experiment_state_ref_for_control_job(
                    job_id=current.job_id, run_id=run_id, tenant_id=tenant_id, cell_id=cell_id
                )
                != state_ref
            ):
                return limited("completed_comparison_run_changed_during_comparison")
            return result
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            return limited("completed_comparison_run_comparison_read_unavailable")

    def resolve_completed_method_metric_selection(
        self,
        *,
        source_run_id: str,
        candidate_ref: ArtifactRef,
        tenant_id: str,
        cell_id: str | None,
    ) -> CompletedMethodMetricSource | None:
        """Resolve an exact completed graph source for an authorized follow-up.

        ``source_run_id`` and ``candidate_ref`` are lookup keys only. The method
        returns a selection only after the completed Runtime owner, creation scope,
        terminal Core source-state output, verified AD01 association, and full
        candidate reference all agree.
        """
        from polisyos.core.contracts.runtime import GraphMethodExecutionSelection

        if (
            not source_run_id
            or not tenant_id
            or not isinstance(candidate_ref, ArtifactRef)
            or candidate_ref.kind != "scientist.policy_design.candidate"
            or candidate_ref.media_type != "application/json"
            or candidate_ref.manifest_profile_sha256 is None
        ):
            return None
        selection = self.get_method_execution_selection(
            run_id=source_run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        if (
            not isinstance(selection, GraphMethodExecutionSelection)
            or selection.metric_verification_status != "verified"
            or selection.method_metric_projection is None
            or selection.source_candidate_ref is None
            or selection.source_experiment_state_ref is None
            or selection.source_candidate_ref != candidate_ref
        ):
            return None
        return CompletedMethodMetricSource(
            source_run_id=source_run_id,
            source_candidate_ref=selection.source_candidate_ref,
            source_experiment_state_ref=selection.source_experiment_state_ref,
            selection=selection,
        )

    @staticmethod
    def _completed_hte_source_invalidation_dedupe_key(
        *,
        source_run_id: str,
        source_job_id: str,
        source_attempt: int,
        completed_event_id: int,
        completed_event_payload_sha256: str,
    ) -> str:
        """Bind idempotency to the exact owner-selected completion event."""
        return _control_hte_invalidation_dedupe_key(
            source_run_id=source_run_id,
            source_job_id=source_job_id,
            source_attempt=source_attempt,
            completed_event_id=completed_event_id,
            completed_event_payload_sha256=completed_event_payload_sha256,
        )

    def _completed_hte_source_validity_request(
        self,
        *,
        job_id: str,
    ) -> DecisionValidityEventRequest | None:
        """Recompute the sole admitted invalidation from persisted owner state."""
        from polisyos.core.contracts.runtime import (
            DirectMethodExecutionHTESummary,
            DirectMethodExecutionSelection,
            _validate_method_execution_selection_wire_payload,
        )

        record = self._control_store.get_job(job_id)
        if (
            record is None
            or record.kind != "workflow_run"
            or record.state != "completed"
            or type(record.job_id) is not str
            or record.job_id != job_id
            or type(record.run_id) is not str
            or not record.run_id
            or type(record.attempt) is not int
            or record.attempt < 1
            or not isinstance(record.method_execution_selection, Mapping)
        ):
            return None
        event = self._control_store.get_job_terminal_source_event_record(job_id)
        if (
            event is None
            or event.job_id != record.job_id
            or event.event_type != "job_completed"
            or type(event.event_id) is not int
            or event.event_id < 1
            or event.payload.get("state") != "completed"
            or type(event.payload.get("attempt")) is not int
            or event.payload.get("attempt") != record.attempt
            or event.payload.get("method_execution_selection") != record.method_execution_selection
        ):
            return None
        try:
            selected = _validate_method_execution_selection_wire_payload(
                record.method_execution_selection
            )
        except TypeError, ValueError:
            return None
        if (
            type(selected) is not DirectMethodExecutionSelection
            or selected.method_version != "2.0.0"
            or type(selected.hte) is not DirectMethodExecutionHTESummary
            or selected.job_id != record.job_id
            or selected.run_id != record.run_id
            or selected.attempt != record.attempt
        ):
            return None

        dependency_key = f"hte_completed_source_run:{record.run_id}"
        try:
            dedupe_key = self._completed_hte_source_invalidation_dedupe_key(
                source_run_id=record.run_id,
                source_job_id=record.job_id,
                source_attempt=record.attempt,
                completed_event_id=event.event_id,
                completed_event_payload_sha256=event.payload_sha256,
            )
        except ValueError:
            return None
        return DecisionValidityEventRequest(
            trigger_type=DecisionTriggerType.METRIC_INVALIDATION,
            status=DecisionValidityStatus.STALE,
            reason="completed_hte_source_owner_selection_updated",
            dependency_keys=[dependency_key],
            source_ref=(
                f"control-job-event:{record.job_id}:{event.event_id}:{event.payload_sha256}"
            ),
            dedupe_key=dedupe_key,
            occurred_at=event.created_at,
            payload={
                "source_run_id": record.run_id,
                "source_job_id": record.job_id,
                "source_attempt": record.attempt,
                "completed_event_id": event.event_id,
                "completed_event_payload_sha256": event.payload_sha256,
            },
        )

    @staticmethod
    def _completed_hte_source_validity_event_id(*, dedupe_key: str) -> str:
        """Derive one stable event ID so a retry can finish its notification row."""
        if type(dedupe_key) is not str or not dedupe_key:
            raise ValueError("completed_hte_source_dedupe_key_invalid")
        digest = hashlib.sha256(dedupe_key.encode("utf-8")).hexdigest()
        return f"decision_evt_{digest}"

    def _dispatch_completed_hte_source_validity_for_job(self, *, job_id: str) -> None:
        """Try the exact durable completion intent once after its transaction commits."""
        try:
            event = self._control_store.get_job_terminal_source_event_record(job_id)
            if event is None or event.event_type != "job_completed":
                return
            delivery = self._control_store.get_outbox_topic_event(
                topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
                event_key=f"{job_id}:job_completed:{event.event_id}",
                job_id=job_id,
            )
            if delivery is not None and delivery.state == "pending":
                self._deliver_completed_hte_source_validity_outbox(delivery)
        except Exception:
            logger.exception("Completed HTE DecisionValidity dispatch read failed for %s", job_id)

    def reconcile_pending_completed_hte_source_validity_events(self) -> int:
        """Retry a bounded page of durable completion intents from one frozen watermark."""
        page_size = 25
        cursor = self._completed_hte_validity_outbox_cursor
        watermark = self._completed_hte_validity_outbox_watermark
        try:
            if watermark is None:
                watermark = self._control_store.get_outbox_topic_delivery_watermark(
                    topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC
                )
                cursor = 0
            if watermark == 0:
                self._completed_hte_validity_outbox_cursor = None
                self._completed_hte_validity_outbox_watermark = None
                return 0
            page = self._control_store.list_pending_outbox_topic_delivery_page(
                topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
                limit=page_size,
                after_sequence_id=cursor if cursor is not None else 0,
                through_sequence_id=watermark,
            )
        except Exception:
            logger.exception("Completed HTE DecisionValidity outbox page read failed")
            self._completed_hte_validity_outbox_cursor = None
            self._completed_hte_validity_outbox_watermark = None
            return 0
        if not page:
            self._completed_hte_validity_outbox_cursor = None
            self._completed_hte_validity_outbox_watermark = None
            return 0
        acknowledged = 0
        for _, delivery in page:
            if self._deliver_completed_hte_source_validity_outbox(delivery):
                acknowledged += 1
        if len(page) == page_size:
            self._completed_hte_validity_outbox_cursor = page[-1][0]
            self._completed_hte_validity_outbox_watermark = watermark
        else:
            self._completed_hte_validity_outbox_cursor = None
            self._completed_hte_validity_outbox_watermark = None
        return acknowledged

    def _deliver_completed_hte_source_validity_outbox(
        self,
        delivery: ControlOutboxRecord,
    ) -> bool:
        """Publish only a request that exactly matches current persisted source custody."""

        from pydantic import TypeAdapter

        from polisyos.core.contracts.runtime import _validate_strict_json_wire_payload

        def leave_pending(reason_code: str) -> bool:
            try:
                self._control_store.record_outbox_delivery_failure(
                    event_id=delivery.event_id,
                    reason_code=reason_code,
                )
            except Exception:
                logger.exception(
                    "Completed HTE DecisionValidity failure receipt was not retained for %s",
                    delivery.event_id,
                )
            return False

        if (
            delivery.topic != _COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC
            or delivery.state != "pending"
            or not delivery.job_id
            or not delivery.run_id
        ):
            return leave_pending("completed_hte_validity_outbox_identity_not_established")
        expected = self._completed_hte_source_validity_request(job_id=delivery.job_id)
        if expected is None or expected.payload.get("source_run_id") != delivery.run_id:
            return leave_pending("completed_hte_validity_source_not_established")
        try:
            queued = _validate_strict_json_wire_payload(
                delivery.payload,
                TypeAdapter(DecisionValidityEventRequest),
                invalid_code="completed_hte_validity_outbox_payload_invalid",
            )
        except Exception:
            return leave_pending("completed_hte_validity_outbox_payload_invalid")
        if (
            queued != expected
            or delivery.event_key
            != f"{delivery.job_id}:job_completed:{expected.payload.get('completed_event_id')}"
        ):
            return leave_pending("completed_hte_validity_outbox_payload_owner_mismatch")
        try:
            self.publish_decision_validity_event(
                expected,
                event_id=self._completed_hte_source_validity_event_id(
                    dedupe_key=expected.dedupe_key or ""
                ),
            )
            self._control_store.mark_outbox_published(event_id=delivery.event_id)
        except Exception:
            logger.exception(
                "Completed HTE DecisionValidity delivery failed for %s", delivery.event_id
            )
            return leave_pending("completed_hte_validity_delivery_failed")
        return True

    def resolve_completed_method_hte_selection(
        self,
        *,
        source_run_id: str,
        tenant_id: str,
        cell_id: str | None,
    ) -> CompletedMethodHTESource | None:
        """Resolve the exact completed owner-selected HTE summary for a follow-up.

        The run ID is only a lookup key. Runtime admits the source only when a
        unique completed workflow row, its immutable completion event, the
        direct-method selection, the bounded owner projection, and every
        selected HTE ref agree under the requested tenant/cell scope. This
        route reads no HTE result vectors and does not refit a method.

        Args:
            source_run_id: Completed source run requested by the caller.
            tenant_id: Already authorized tenant scope for the current workflow.
            cell_id: Already authorized cell scope for the current workflow.

        Returns:
            A frozen scalar HTE summary with exact owner-event provenance, or
            ``None`` when the requested source cannot be established.
        """

        from polisyos.core.contracts.owned_attempt_anchor import (
            OwnedAttemptAnchorProjectionAssociation,
        )
        from polisyos.core.contracts.runtime import (
            DirectMethodExecutionHTESummary,
            DirectMethodExecutionSelection,
            _validate_method_execution_selection_wire_payload,
        )

        if (
            not isinstance(source_run_id, str)
            or not source_run_id
            or not isinstance(tenant_id, str)
            or not tenant_id
            or (cell_id is not None and (not isinstance(cell_id, str) or not cell_id))
        ):
            return None
        try:
            record = self._control_store.get_unique_completed_job_by_run_and_kind(
                run_id=source_run_id,
                kind="workflow_run",
            )
            if (
                record is None
                or record.state != "completed"
                or record.kind != "workflow_run"
                or record.run_id != source_run_id
                or record.method_execution_selection is None
            ):
                return None
            projection = self.get_observational_method_run_projection(
                run_id=source_run_id,
                expected_job_id=record.job_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            selection = projection.selection
            if (
                projection.status != "selected"
                or type(selection) is not DirectMethodExecutionSelection
                or selection.method_version != "2.0.0"
                or selection.hte is None
                or type(selection.hte) is not DirectMethodExecutionHTESummary
                or selection.job_id != record.job_id
                or selection.run_id != source_run_id
                or selection.attempt != record.attempt
                or selection.owned_attempt_anchor_ref is None
            ):
                return None
            association = self.resolve_owned_attempt_anchor_projection_association(
                run_id=source_run_id,
                expected_job_id=record.job_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            if (
                type(association) is not OwnedAttemptAnchorProjectionAssociation
                or association.job_id != record.job_id
                or association.run_id != source_run_id
                or association.attempt != record.attempt
                or association.tenant_id != tenant_id
                or association.cell_id != cell_id
                or association.job_completed_event.event_type != "job_completed"
                or association.job_completed_event.job_id != record.job_id
                or association.outcome_kind != selection.hte.kind
                or not _same_selected_artifact_ref(
                    association.anchor_ref,
                    selection.owned_attempt_anchor_ref,
                )
                or not _same_selected_artifact_ref(
                    association.outcome_ref,
                    selection.hte.hte_outcome_ref,
                )
                or not _same_selected_artifact_ref(
                    association.source_data_ref,
                    selection.hte.source_data_ref,
                )
                or not _same_selected_artifact_ref(
                    association.method_result_ref,
                    selection.method_result_ref,
                )
                or not _same_selected_artifact_ref(
                    association.method_evidence_ref,
                    selection.method_evidence_ref,
                )
                or not _same_optional_selected_artifact_ref(
                    association.point_result_ref,
                    selection.hte.point_result_ref,
                )
                or not _same_optional_selected_artifact_ref(
                    association.hte_result_ref,
                    selection.hte.hte_result_ref,
                )
                or not _same_optional_selected_artifact_ref(
                    association.inference_basis_ref,
                    selection.hte.inference_basis_ref,
                )
                or not _same_optional_selected_artifact_ref(
                    association.refusal_diagnostic_ref,
                    selection.hte.refusal_diagnostic_ref,
                )
                or not _same_optional_selected_artifact_ref(
                    association.materialization_binding_ref,
                    selection.hte.materialization_binding_ref,
                )
                or not _same_optional_selected_artifact_ref(
                    association.search_uncertainty_task_binding_ref,
                    selection.hte.search_uncertainty_task_binding_ref,
                )
            ):
                return None

            # Re-read the exact immutable completion event and its selection.
            # A run lookup or current-pointer equality alone is not historical
            # completion proof, and event IDs are never inferred from the ref.
            event_ref = association.job_completed_event
            event = self._control_store.get_job_lifecycle_event_record(
                job_id=record.job_id,
                event_id=event_ref.event_id,
                expected_event_type="job_completed",
            )
            event_selection = _validate_method_execution_selection_wire_payload(
                event.payload.get("method_execution_selection")
            )
            if (
                event.event_id != event_ref.event_id
                or event.job_id != record.job_id
                or event.payload_sha256 != event_ref.payload_sha256
                or event.payload.get("state") != "completed"
                or event.payload.get("attempt") != record.attempt
                or type(event.payload.get("attempt")) is not int
                or type(event_selection) is not DirectMethodExecutionSelection
                or event_selection.job_id != record.job_id
                or event_selection.run_id != source_run_id
                or event_selection.attempt != record.attempt
                or event_selection.hte is None
                or event_selection.hte.model_dump(mode="json")
                != selection.hte.model_dump(mode="json")
            ):
                return None

            # Close the read window against a newer/replaced completed row.
            current = self._control_store.get_unique_completed_job_by_run_and_kind(
                run_id=source_run_id,
                kind="workflow_run",
            )
            if (
                current is None
                or current.job_id != record.job_id
                or current.attempt != record.attempt
                or current.method_execution_selection != record.method_execution_selection
            ):
                return None
            return CompletedMethodHTESource(
                source_run_id=source_run_id,
                source_job_id=record.job_id,
                source_attempt=record.attempt,
                completed_event_id=event.event_id,
                completed_event_payload_sha256=event.payload_sha256,
                summary=selection.hte,
                association=association,
            )
        except OSError, RuntimeError, TypeError, ValueError:
            return None

    def _terminal_experiment_state_ref_for_control_job(
        self,
        *,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str | None,
    ) -> ArtifactRef | None:
        """Resolve the exact final state named by the terminal workflow receipt."""
        from polisyos.core.artifacts import read_core_json_artifact_bounded
        from polisyos.core.artifacts.canonical_profile import (
            CoreJsonReadLimits,
            validate_core_model_bounded_read,
        )
        from polisyos.core.contracts.runtime import ObservationalInputResourcePolicy
        from polisyos.runtime.http.services.adapters.core_run import (
            load_terminal_core_run_source,
        )
        from polisyos.scientist.orchestration.engine.finalization import (
            FINALIZATION_KIND,
            FINALIZATION_SCHEMA_NAME,
            FINALIZATION_SCHEMA_VERSION,
            WorkflowStateFinalization,
        )

        if not job_id or not run_id or not tenant_id:
            return None
        try:
            terminal = load_terminal_core_run_source(
                store=self._artifact_store,
                core_runs_root=self._core_runs_root,
                run_id=run_id,
            )
            manifest = terminal.manifest
            finalization_ref = terminal.workflow_finalization_ref
        except OSError, RuntimeError, TypeError, ValueError:
            return None
        if (
            terminal.run_id != run_id
            or manifest.run_id != run_id
            or manifest.control_job_id != job_id
            or manifest.tenant_id != tenant_id
            or manifest.cell_id != cell_id
            or terminal.tenant_id != tenant_id
            or terminal.cell_id != cell_id
            or not isinstance(finalization_ref, ArtifactRef)
            or finalization_ref not in manifest.outputs
            or sum(ref == finalization_ref for ref in manifest.outputs) != 1
        ):
            return None
        policy = ObservationalInputResourcePolicy()
        limits = CoreJsonReadLimits(
            max_bytes=policy.max_bytes,
            max_depth=policy.max_depth,
            max_elements=policy.max_elements,
            max_manifest_bytes=policy.max_manifest_bytes,
        )
        try:
            bounded = read_core_json_artifact_bounded(
                self._require_core_bounded_member_reader(limits=limits),
                finalization_ref,
                limits=limits,
            )
            if (
                not _same_selected_artifact_ref(bounded.effective_ref, finalization_ref)
                or bounded.manifest.kind != FINALIZATION_KIND
                or bounded.manifest.media_type != "application/json"
                or bounded.manifest.artifact_schema
                != SchemaInfo(
                    name=FINALIZATION_SCHEMA_NAME,
                    version=FINALIZATION_SCHEMA_VERSION,
                )
            ):
                return None
            finalization = validate_core_model_bounded_read(
                WorkflowStateFinalization,
                bounded,
            )
        except OSError, RuntimeError, TypeError, ValueError:
            return None
        selected_state = finalization.final_state_ref
        if (
            finalization.run_id != run_id
            or selected_state.kind != "scientist.experiment_state"
            or selected_state.media_type != "application/json"
            or selected_state.manifest_profile_sha256 is None
            or selected_state not in manifest.outputs
            or sum(ref == selected_state for ref in manifest.outputs) != 1
        ):
            return None
        return selected_state

    def get_method_execution_producer_diagnostic(
        self,
        *,
        run_id: str,
        tenant_id: str,
        cell_id: str | None,
    ) -> MethodExecutionProducerDiagnostic | None:
        """Read bounded candidate producer refs after the route authorizes this run."""
        from polisyos.core.contracts.runtime import MethodExecutionProducerDiagnostic

        if not run_id or not tenant_id:
            return None
        try:
            record = self.get_latest_job_for_run(run_id)
            if (
                record is None
                or record.kind != "workflow_run"
                or record.run_id != run_id
                or record.state not in {"completed", "failed"}
                or record.progress.get("authority_path") != "legacy_shadow"
            ):
                return None
            created = self._control_store.get_job_created_event_payload(record.job_id)
        except RuntimeError, ValueError:
            return None
        if (
            created.get("job_id") != record.job_id
            or created.get("run_id") != run_id
            or created.get("job_kind") != "workflow_run"
        ):
            return None
        execution_scope = created.get("execution_scope")
        if not isinstance(execution_scope, Mapping) or (
            execution_scope.get("tenant_id") != tenant_id
            or execution_scope.get("cell_id") != cell_id
        ):
            return None
        raw_diagnostic = record.progress.get("method_execution_producer_diagnostic")
        if not isinstance(raw_diagnostic, Mapping):
            return None
        try:
            diagnostic = MethodExecutionProducerDiagnostic.model_validate(raw_diagnostic)
        except TypeError, ValueError:
            return None
        if (
            diagnostic.job_id != record.job_id
            or diagnostic.run_id != run_id
            or diagnostic.attempt != record.attempt
            or diagnostic.authority_status != "candidate_only"
        ):
            return None
        return diagnostic

    def get_pre_admission_attempt_status_by_idempotency_key(
        self,
        idempotency_key: str,
        *,
        request_id: str | None,
        principal: RuntimePrincipal,
    ) -> ControlPreAdmissionAttemptResponse:
        """Resolve recovery using the authenticated principal and header key only."""
        if (
            not isinstance(idempotency_key, str)
            or not idempotency_key
            or idempotency_key != idempotency_key.strip()
            or len(idempotency_key) > 128
            or any(ord(character) < 33 or ord(character) > 126 for character in idempotency_key)
        ):
            raise unprocessable_entity(
                (
                    "Idempotency-Key must be a non-empty printable ASCII value of at most "
                    "128 characters."
                ),
                code="control_pre_admission_idempotency_key_invalid",
            )
        scope_values = (
            (principal.subject, principal.tenant_id, principal.cell_id) if principal else ()
        )
        scope_sentinels = {
            "unknown",
            "tenant-unknown",
            "cell-unknown",
            "anonymous",
            "none",
            "null",
        }
        if (
            principal is None
            or not principal.authenticated
            or any(
                not isinstance(value, str)
                or not value
                or value != value.strip()
                or value.casefold() in scope_sentinels
                for value in scope_values
            )
        ):
            raise forbidden(
                "Pre-admission recovery requires an authenticated actor, tenant, and cell scope.",
                code="control_pre_admission_scope_not_established",
            )
        tenant_id = principal.tenant_id
        cell_id = principal.cell_id
        if (
            not isinstance(tenant_id, str)
            or not tenant_id
            or not isinstance(cell_id, str)
            or not cell_id
        ):
            raise forbidden(
                "Pre-admission recovery requires an authenticated actor, tenant, and cell scope.",
                code="control_pre_admission_scope_not_established",
            )
        digest = hashlib.sha256(idempotency_key.encode("ascii")).hexdigest()
        record = self._control_store.get_pre_admission_attempt_by_idempotency_key(
            tenant_id=tenant_id,
            cell_id=cell_id,
            actor_subject=principal.subject,
            idempotency_key_sha256=digest,
        )
        if record is None:
            raise KeyError("control_pre_admission_attempt_not_found")
        return self.get_pre_admission_attempt_status(
            record.attempt_id,
            request_id=request_id,
            principal=principal,
        )

    def get_pre_admission_attempt_status(
        self,
        attempt_id: str,
        *,
        request_id: str | None,
        principal: RuntimePrincipal,
    ) -> ControlPreAdmissionAttemptResponse:
        """Return one attempt history only to its authenticated initiating actor."""
        record = self._control_store.get_pre_admission_attempt(attempt_id)
        if record is None:
            raise KeyError(attempt_id)
        if (
            principal is None
            or not principal.authenticated
            or record.actor_subject is None
            or record.tenant_id is None
            or record.cell_id is None
            or principal.subject != record.actor_subject
            or principal.tenant_id != record.tenant_id
            or principal.cell_id != record.cell_id
        ):
            raise forbidden(
                "Pre-admission attempt is outside the caller's verified scope.",
                code="control_pre_admission_attempt_scope_mismatch",
            )
        intent_content_sha256 = record.intent_binding.get("request_content_sha256")
        if not isinstance(intent_content_sha256, str):
            raise RuntimeError("pre-admission request content binding is not established")
        owner = record.shared_owner
        purpose = TypeAdapter(Literal["control.nl_pre_admission.v1"]).validate_python(
            owner.purpose,
            strict=True,
        )
        scope_kind = TypeAdapter(Literal["route"]).validate_python(owner.scope_kind, strict=True)
        scope_id = TypeAdapter(Literal["control.runs.nl"]).validate_python(
            owner.scope_id,
            strict=True,
        )
        effective_execution_profile = TypeAdapter(ExecutionProfile).validate_python(
            record.effective_execution_profile,
            strict=True,
        )
        owner_binding = ControlPreAdmissionOwnerBinding(
            purpose=purpose,
            scope_kind=scope_kind,
            scope_id=scope_id,
            tenant_id=owner.tenant_id,
            cell_id=owner.cell_id,
            actor_subject_sha256=owner.actor_subject_sha256,
            run_id=owner.run_id,
            intent_id=owner.intent_id,
            body_sha256=owner.body_sha256,
            request_content_sha256=intent_content_sha256,
            effective_execution_profile=effective_execution_profile,
        )
        return ControlPreAdmissionAttemptResponse(
            meta=_build_api_meta(request_id),
            owner_binding=owner_binding,
            attempt_id=record.attempt_id,
            intent_sha256=record.intent_sha256,
            status=record.status,
            run_id=record.run_id,
            job_id=record.job_id,
            effective_execution_profile=effective_execution_profile,
            producer_event_ids=list(record.producer_event_ids),
            producer_event_observation=record.producer_event_observation,
            producer_no_call_reason=record.producer_no_call_reason,
            failure_code=record.failure_code,
            created_at=record.created_at,
            updated_at=record.updated_at,
            history=[
                ControlPreAdmissionAttemptEventInfo(
                    event_id=event.event_id,
                    sequence=event.sequence,
                    event_type=event.event_type,
                    observed_at=event.observed_at,
                    producer_event_ids=list(event.producer_event_ids),
                    producer_event_observation=event.producer_event_observation,
                    producer_no_call_reason=event.producer_no_call_reason,
                    failure_code=event.failure_code,
                    job_id=event.job_id,
                )
                for event in record.history
            ],
        )

    def _current_normative_job_record(self, record: ControlJobRecord) -> ControlJobRecord:
        """Replay normative authority once for every outward job-record reader."""
        if record.kind == "natural_language_run" and record.state == "completed":
            progress = dict(record.progress)
            stored_disposition_ref = progress.get("normative_disposition_ref")
            stored_compiled_ref = progress.get("compiled_recursive_generation_cycle_ref")
            copied_head_ref = progress.pop("normative_head_ref", None)
            progress.pop("normative_head_strangle_receipt", None)
            progress.pop("normative_head_limitation", None)
            disposition_ref: str | None = None
            compiled_ref: str | None = None
            disposition_artifact_ref: ArtifactRef | None = None
            compiled_artifact_ref: ArtifactRef | None = None
            refusal_reason: str | None = None
            from polisyos.runtime.http.services.control.generation_cycle import (
                NormativeEvidenceHeadStrangleReceipt,
                load_normative_generation_head,
                normative_owner_for_runtime_store,
                replay_normative_run_disposition,
            )

            try:
                compiled_artifact_ref, original_disposition_artifact_ref = (
                    self._normative_owned_job_source(record)
                )
                compiled_ref = str(compiled_artifact_ref.artifact_id)
                original_disposition_ref = str(original_disposition_artifact_ref.artifact_id)
                progress["compiled_recursive_generation_cycle_ref"] = compiled_ref
                if stored_compiled_ref != compiled_ref:
                    raise ValueError("normative_head_owned_source_mismatch")
                event = self._control_store.get_normative_evidence_head(record.job_id)
                if event is None:
                    if (
                        copied_head_ref is not None
                        or stored_disposition_ref != original_disposition_ref
                    ):
                        raise ValueError("normative_admitted_head_missing")
                    disposition_ref = original_disposition_ref
                    disposition_artifact_ref = original_disposition_artifact_ref
                else:
                    head = load_normative_generation_head(self._artifact_store, event["head_ref"])
                    expected = {
                        "head_ref": event["head_ref"],
                        "previous_head_ref": head.previous_head_ref,
                        "job_id": record.job_id,
                        "run_id": record.run_id,
                        "compiled_run_ref": compiled_ref,
                    }
                    if event != expected or (
                        head.job_id,
                        head.run_id,
                        head.compiled_run_ref,
                    ) != (
                        record.job_id,
                        record.run_id,
                        compiled_ref,
                    ):
                        raise ValueError("normative_head_source_binding_mismatch")
                    owner = normative_owner_for_runtime_store(
                        self._artifact_store,
                        self._normative_authority_trust,
                        signature_verifier=self._promotion_runtime.signature_verifier,
                        repo_root=self._repo_root,
                    )
                    historical_replay = replay_normative_run_disposition(
                        store=self._artifact_store,
                        owner=owner,
                        disposition_ref=head.disposition_ref,
                        compiled_run_ref=head.compiled_run_ref,
                        compiled_artifact_ref=compiled_artifact_ref,
                    )
                    historical = historical_replay.disposition
                    actual_evidence = {
                        node: leaf.evidence
                        for node, leaf in historical.leaf_dispositions.items()
                        if leaf.evidence is not None
                    }
                    if (
                        not historical_replay.admission_authority_established
                        or historical.authorization_status != "authorized"
                        or head.evidence.input_limitation is not None
                        or head.evidence.by_node != actual_evidence
                        or any(
                            leaf.admitted_at != head.evaluated_at
                            for leaf in historical.leaf_dispositions.values()
                        )
                        or head.strangle_receipt
                        != NormativeEvidenceHeadStrangleReceipt(
                            original_disposition_ref=original_disposition_ref,
                            current_disposition_ref=head.disposition_ref,
                        )
                    ):
                        raise ValueError("normative_head_evidence_binding_mismatch")
                    disposition_ref = head.disposition_ref
                    progress["normative_head_ref"] = event["head_ref"]
                    progress["normative_disposition_ref"] = disposition_ref
                    progress["normative_head_strangle_receipt"] = head.strangle_receipt.model_dump(
                        mode="json"
                    )
            except (ValueError, TypeError, OSError, KeyError) as exc:
                # The canonical source survives projection/head failure. Mutable progress
                # never supplies authority when the immutable owner cannot resolve it.
                refusal_reason = str(exc)
                progress["normative_head_limitation"] = refusal_reason
            projection = self._current_normative_generation_projection(
                disposition_ref=disposition_ref,
                compiled_run_ref=compiled_ref,
                disposition_artifact_ref=disposition_artifact_ref,
                compiled_artifact_ref=compiled_artifact_ref,
                evaluated_at=datetime.now(UTC),
                refusal_reason=refusal_reason,
            )
            progress["normative_disposition"] = projection
            progress["normative_disposition_ref"] = projection.get(
                "refusal_disposition_ref", disposition_ref
            )
            return replace(record, progress=progress)
        return record

    def get_latest_job_for_run(self, run_id: str) -> ControlJobRecord | None:
        """Return the newest durable control job attached to one runtime run."""
        record = self._control_store.get_latest_job_by_run(run_id)
        return self._current_normative_job_record(record) if record is not None else None

    def record_production_approval_packet(
        self,
        *,
        run_id: str,
        approval_packet_ref: str,
        decision: str,
        request_access_scope: AccessScope,
        scorecard: Mapping[str, Any] | None = None,
        approval_packet: Mapping[str, Any] | None = None,
    ) -> None:
        """Attach a persisted approval packet ref to the latest run control progress."""
        record = self.get_latest_job_for_run(run_id)
        if record is None:
            return

        progress = dict(record.progress)
        existing_scorecard = progress.get("quality_scorecard")
        if scorecard is not None:
            progress_scorecard: dict[str, Any] = dict(scorecard)
        elif isinstance(existing_scorecard, Mapping):
            progress_scorecard = dict(existing_scorecard)
        else:
            progress_scorecard = {}
        if isinstance(existing_scorecard, Mapping):
            progress_scorecard.update(dict(existing_scorecard))

        evidence_refs = progress_scorecard.get("evidence_refs")
        if not isinstance(evidence_refs, Mapping):
            evidence_refs = {}
        evidence_refs = dict(evidence_refs)
        evidence_refs["approval_packet_ref"] = approval_packet_ref
        evidence_refs.setdefault("approval_packet", approval_packet_ref)

        existing_projection = dict(progress_scorecard)
        existing_decision = existing_projection.get("approval_decision") or existing_projection.get(
            "decision"
        )
        conflict = None
        if (
            existing_projection.get("approval_packet_ref") is not None
            or existing_decision is not None
        ):
            try:
                conflict = detect_source_truth_conflict(
                    field_family="approval_readiness_public_status",
                    authoritative_source="runtime.approval_packet",
                    authoritative_surface="runtime.approval",
                    authoritative_values={
                        "approval_packet_ref": approval_packet_ref,
                        "decision": decision,
                    },
                    conflicting_source="runtime.dashboard",
                    conflicting_surface="runtime.dashboard",
                    conflicting_values={
                        "approval_packet_ref": existing_projection.get("approval_packet_ref"),
                        "decision": existing_decision,
                    },
                    fields=("approval_packet_ref", "decision"),
                    downstream_impact=(
                        "Dashboard progress projection would disagree with the persisted packet."
                    ),
                )
            except SourceTruthContractError:
                conflict = None
        if conflict is not None:
            existing_conflicts = progress_scorecard.get("source_truth_conflicts")
            progress_scorecard["source_truth_conflicts"] = [
                *(existing_conflicts if isinstance(existing_conflicts, list) else []),
                conflict,
            ]

        progress_scorecard["approval_packet_ref"] = approval_packet_ref
        progress_scorecard["approval_decision"] = decision
        # A stored packet is a historical projection. Every operational consumer
        # must re-run the concrete resolver against the signed packet and inputs.
        progress_scorecard["approval_ready"] = False
        progress_scorecard["approval_state"] = (
            "approval_projection_only"
            if decision in {"approved", "approved_with_override"}
            else "approval_blocked"
        )
        progress_scorecard["approval_currentness"] = "resolver_required"
        progress_scorecard["approval_projection_only"] = True
        progress_scorecard["evidence_refs"] = evidence_refs
        if approval_packet is not None:
            packet_payload = dict(approval_packet)
            progress_scorecard["approval_packet"] = packet_payload
            eligibility = packet_payload.get("eligibility")
            if isinstance(eligibility, Mapping):
                progress_scorecard["approval_eligibility"] = dict(eligibility)
                reasons = eligibility.get("reasons")
                if isinstance(reasons, list):
                    progress_scorecard["approval_reasons"] = list(reasons)

        progress["quality_scorecard"] = progress_scorecard
        progress["approval_packet_ref"] = approval_packet_ref
        progress["approval_decision"] = decision
        progress_evidence_refs = progress.get("evidence_refs")
        progress_evidence_refs = (
            dict(progress_evidence_refs) if isinstance(progress_evidence_refs, Mapping) else {}
        )
        progress_evidence_refs["approval_packet_ref"] = approval_packet_ref
        progress["evidence_refs"] = {
            **progress_evidence_refs,
        }
        approval_event = self._emit_runtime_diagnostic_event(
            job_id=record.job_id,
            run_id=run_id,
            execution_profile=record.effective_execution_profile,
            phase="approval_packet",
            event_type="polisyos.runtime.diagnostic.approval_decision.v1",
            state_after=decision,
            payload=record.progress,
            event_payload={
                "approval_packet_ref": approval_packet_ref,
                "decision": decision,
                "projection_authority": "progress_reference_only",
            },
            artifact_refs=[approval_packet_ref],
            authority_bearing_payload=True,
            execution_scope=request_access_scope,
        )
        if approval_event.event_id is not None:
            progress.setdefault("diagnostic_event_ids", [])
            if isinstance(progress["diagnostic_event_ids"], list):
                progress["diagnostic_event_ids"].append(approval_event.event_id)
            progress["diagnostic_event_authority"] = (
                "progress_reference_only"
                if approval_event.status == "persisted"
                else (
                    "scope_limited"
                    if approval_event.status == "authority_withheld"
                    else "candidate_diagnostic"
                )
            )
            progress["diagnostic_event_scope_status"] = approval_event.scope_status
            if approval_event.limitation_code is not None:
                progress["diagnostic_event_limitation_code"] = approval_event.limitation_code
        self._control_store.upsert_progress(job_id=record.job_id, progress=progress)

    def list_control_workers(
        self,
        *,
        active_only: bool = True,
        request_id: str | None = None,
    ) -> ControlWorkersResponse:
        """Return active/all worker leases from the control-plane store."""
        workers = self._control_store.list_worker_leases(active_only=active_only)
        return ControlWorkersResponse(
            meta=_build_api_meta(request_id),
            active_only=active_only,
            workers=[
                ControlWorkerLeaseInfo(
                    worker_id=item.worker_id,
                    state=item.state,
                    backend=item.backend,
                    active_job_id=item.active_job_id,
                    metadata=dict(item.metadata),
                    heartbeat_at=item.heartbeat_at,
                    lease_expires_at=item.lease_expires_at,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
                for item in workers
            ],
        )

    def list_control_outbox(
        self,
        *,
        state: str | None = "pending",
        limit: int = 100,
        request_id: str | None = None,
    ) -> ControlOutboxEventsResponse:
        """Return durable outbox events filtered by state and capped to 500 rows."""
        events = self._control_store.list_outbox_events(state=state, limit=limit)
        return ControlOutboxEventsResponse(
            meta=_build_api_meta(request_id),
            state=state,
            limit=max(1, min(int(limit), 500)),
            events=[
                ControlOutboxEventInfo(
                    event_id=item.event_id,
                    topic=item.topic,
                    event_key=item.event_key,
                    state=item.state,
                    job_id=item.job_id,
                    run_id=item.run_id,
                    payload=dict(item.payload),
                    created_at=item.created_at,
                    published_at=item.published_at,
                    attempt=item.attempt,
                    error_message=item.error_message,
                )
                for item in events
            ],
        )

    def _process_control_job(self, job: ControlJobRecord) -> None:
        """Enter only the persisted, live-lease scope before any job artifact read."""
        del job  # The lease-fenced row, not the dispatch snapshot, owns stable fields.
        with clear_tenant_context():
            try:
                admission = self._control_store.current_execution_job_admission()
            except ControlJobLeaseLostError:
                raise
            except ControlJobExecutionAdmissionError as exc:
                current = self._control_store.current_execution_job_record()
                self._control_store.fail_job(
                    job_id=current.job_id,
                    capability_manifest_ref=current.capability_manifest_ref,
                    error_message=exc.code,
                    progress={
                        "state": "failed",
                        "phase": "job_admission",
                        "status": "not_established",
                        "failure_code": exc.code,
                        "execution_scope": "not_established",
                    },
                )
                return
            with self._install_execution_scope(admission.scope):
                self._process_control_job_admitted(
                    job=admission.job,
                    admission=admission,
                    execution_scope=admission.scope,
                )

    def _process_control_job_admitted(
        self,
        *,
        job: ControlJobRecord,
        admission: ControlJobExecutionAdmission,
        execution_scope: ControlJobExecutionScope,
    ) -> None:
        payload: dict[str, Any] = {}
        capability_manifest_ref: str | None = job.capability_manifest_ref
        capability_manifest: dict[str, Any] | None = None
        execution_intent_binding: dict[str, Any] | None = None
        core_run_id: str | None = None
        core_run_context: run.RunContext | None = None

        def start_core_attempt() -> tuple[str, run.RunContext]:
            """Start the admitted attempt once, before its protected computation."""
            nonlocal core_run_id, core_run_context
            if core_run_id is not None and core_run_context is not None:
                return core_run_id, core_run_context
            if core_run_id is not None or core_run_context is not None:
                raise RuntimeError("control_job_core_run_attempt_identity_incomplete")
            profile_ref: ArtifactRef | None = None
            snapshot_ref: DataSnapshotRef | None = None
            predictive_refs: list[ArtifactRef] = []
            observational_refs: list[ArtifactRef] = []
            if job.kind == "workflow_run" and (_OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY in payload):
                marker = payload.get(_OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY)
                if not isinstance(marker, Mapping):
                    raise ValueError("observational_method_job_marker_invalid")
                try:
                    source_ref = ArtifactRef.model_validate(
                        marker["requested_source_ref"], strict=True
                    )
                    intent_ref = ArtifactRef.model_validate(
                        marker["observational_run_intent_ref"], strict=True
                    )
                    selection_digest = marker["observational_selection_digest"]
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError("observational_method_job_marker_invalid") from exc
                if (
                    source_ref.manifest_profile_sha256 is None
                    or intent_ref.manifest_profile_sha256 is None
                    or type(selection_digest) is not str
                    or len(selection_digest) != 64
                    or any(character not in "0123456789abcdef" for character in selection_digest)
                ):
                    raise ValueError("observational_method_job_marker_invalid")
                observational_refs.extend((source_ref, intent_ref))
            if job.kind == "natural_language_run" and "data_source" in payload:
                raw_data_source = payload["data_source"]
                if isinstance(raw_data_source, Mapping):
                    source_binding = DataSourceBinding.model_validate(dict(raw_data_source))
                    selected_snapshot = source_binding.data_snapshot_ref
                    if isinstance(selected_snapshot, DataSnapshotRef):
                        self._validate_control_nl_data_snapshot(selected_snapshot)
                        snapshot_ref = selected_snapshot
            if job.kind == "natural_language_run" and "value_data_profile_ref" in payload:
                raw_profile_ref = payload["value_data_profile_ref"]
                if not isinstance(raw_profile_ref, Mapping):
                    raise ValueError("control_nl_value_data_profile_payload_invalid")
                try:
                    profile_ref = ArtifactRef.model_validate(dict(raw_profile_ref))
                    resolved_profile = self._validate_control_nl_value_data_profile(profile_ref)
                    profile = getattr(resolved_profile, "profile", None)
                    unit_id = payload.get("value_data_unit_id")
                    if not any(
                        getattr(row, "unit_id", None) == unit_id
                        for row in getattr(profile, "rows", ())
                    ):
                        raise ValueError("selected_value_data_unit_not_in_profile")
                    if snapshot_ref is None:
                        raise ValueError("selected_predictive_snapshot_missing")
                    self._validate_control_nl_predictive_basis(
                        snapshot_ref,
                        profile_ref,
                        unit_id=str(unit_id),
                        resolved_profile=resolved_profile,
                    )
                except Exception as exc:
                    raise ValueError("control_nl_value_data_profile_not_admitted") from exc
                for field_name, expected_kind in (
                    ("model_spec_ref", "ir.model_spec"),
                    ("policy_spec_ref", "ir.policy_spec"),
                    ("calibration_rule_ref", "ir.forecast_calibration_rule"),
                ):
                    raw_reference = payload.get(field_name)
                    if not isinstance(raw_reference, Mapping):
                        raise ValueError("control_nl_predictive_input_payload_invalid")
                    reference = ArtifactRef.model_validate(dict(raw_reference))
                    self._validate_control_nl_exact_ref(reference, expected_kind=expected_kind)
                    predictive_refs.append(reference)
            core_run_id, core_run_context = self._start_generation_run_context(
                job=job,
                execution_scope=execution_scope,
            )
            if snapshot_ref is not None:
                core_run_context.add_input(snapshot_ref)
            if profile_ref is not None:
                core_run_context.add_input(profile_ref)
            for reference in predictive_refs:
                core_run_context.add_input(reference)
            for reference in observational_refs:
                core_run_context.add_input(reference)
            return core_run_id, core_run_context

        try:
            payload_ref = self._require_control_job_payload_ref(job)
            payload = (
                self._load_control_nl_job_payload(job)
                if job.kind == "natural_language_run"
                else self._load_payload_ref(
                    payload_ref,
                    kind=f"runtime.control_job_payload.{job.kind}",
                )
            )
            if self._has_observational_method_job_selection(job=job, payload=payload):
                self._read_validated_observational_method_job_intent(
                    job=job,
                    payload=payload,
                )
            payload = self._payload_for_execution_scope(
                payload,
                job=job,
                execution_scope=execution_scope,
            )
            if self._has_observational_method_job_selection(job=job, payload=payload):
                self._read_validated_observational_method_job_intent(job=job, payload=payload)
            capability_manifest_ref, capability_manifest = (
                self._resolve_capability_manifest_for_execution(
                    job=job,
                    admission=admission,
                    execution_scope=execution_scope,
                )
            )
            if capability_manifest_ref is None:
                raise RuntimeError("control_job_capability_manifest_not_established")
            execution_intent_binding = self._bind_control_job_execution_intent(
                job=job,
                admission=admission,
                execution_scope=execution_scope,
                payload=payload,
                capability_manifest_ref=capability_manifest_ref,
                capability_manifest=capability_manifest,
            )
            with self._control_job_span(job=job, payload=payload):
                self._emit_control_job_start_event(
                    job=job,
                    payload=payload,
                    execution_scope=execution_scope,
                    execution_intent_binding=execution_intent_binding,
                )
                if job.kind == "workflow_run":
                    self._process_workflow_control_job(
                        job=job,
                        payload=payload,
                        execution_scope=execution_scope,
                        capability_manifest_ref=capability_manifest_ref,
                        admission=admission,
                        start_core_attempt_callback=start_core_attempt,
                    )
                    return
                if job.kind == "natural_language_run":
                    nl_context = self._prepare_control_nl_job_context(
                        job=job,
                        admission=admission,
                        execution_scope=execution_scope,
                        payload=payload,
                        capability_manifest_ref=capability_manifest_ref,
                        execution_intent_binding=cast("dict[str, Any]", execution_intent_binding),
                        core_run_id=core_run_id,
                        core_run_context=core_run_context,
                        start_core_attempt_callback=start_core_attempt,
                    )
                    if nl_context is None:
                        return
                    compiled = self._execute_control_nl_job(nl_context)
                    if compiled is not None:
                        self._publish_control_nl_job(nl_context, compiled)
                    return
                if job.kind == "lex_pipeline":
                    self._run_lex_pipeline_job(
                        job=job,
                        payload=payload,
                        capability_manifest_ref=capability_manifest_ref,
                        execution_scope=execution_scope,
                    )
                    return
                if job.kind == "acquisition":
                    self._complete_acquisition_control_job(
                        job=job,
                        payload=payload,
                        execution_scope=execution_scope,
                        capability_manifest_ref=capability_manifest_ref,
                    )
                    return
                raise RuntimeError(f"Unsupported control job kind: {job.kind}")
        except Exception as exc:
            self._fail_control_job_attempt(
                job=job,
                execution_scope=execution_scope,
                payload=payload,
                capability_manifest_ref=capability_manifest_ref,
                core_run_id=core_run_id,
                core_run_context=core_run_context,
                exc=exc,
                logger=logger,
            )

    def _collect_lex_progress(
        self,
        *,
        output_dir: Path | None,
        state: str,
        existing: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        progress = dict(existing or {})
        if output_dir is not None:
            progress["output_dir"] = str(output_dir)
        progress["state"] = state
        progress_summary: dict[str, int] = dict(progress.get("progress_summary") or {})
        if output_dir is not None and str(output_dir):
            try:
                from polisyos.data_forge.read_api.legal import ProgressTracker

                progress_path = output_dir / "progress.jsonl"
                if progress_path.exists():
                    tracker = ProgressTracker(progress_path)
                    progress_summary = tracker.summary()
            except (AttributeError, OSError, TypeError, ValueError) as exc:
                logger.debug("Failed to read lex pipeline progress from %s: %s", output_dir, exc)
        progress["progress_summary"] = progress_summary
        return progress

    # ---- Workflow launch ---------------------------------------------------

    def launch_workflow_run(
        self,
        request: WorkflowRunRequest,
        *,
        request_id: str | None = None,
        principal: RuntimePrincipal | None = None,
    ) -> RunLaunchResponse:
        """Persist a workflow payload/capability manifest and queue a durable `workflow_run` job.

        Raises:
            RuntimeHTTPError: If profile resolution fails or no data source ref is
                present in `request.data_source`.
        """
        from polisyos.core.run.context import new_run_id

        run_id = new_run_id()
        job_id = uuid.uuid4().hex
        policy = self._resolve_execution_policy(
            requested_profile=request.execution_profile,
            policy_flags=request.policy_flags,
            principal=principal,
        )
        if request.observational_input is not None:
            return self._launch_observational_workflow_run(
                request,
                run_id=run_id,
                job_id=job_id,
                policy=policy,
                request_id=request_id,
                principal=principal,
            )

        # Build inputs dict
        inputs: dict[str, Any] = {}

        # Data source (required)
        workflow_data_source = request.data_source
        if workflow_data_source is None:
            raise ValueError("workflow_data_source_required_without_observational_input")
        ds_key, ds_ref, data_view_request_intent = _resolve_workflow_data_source(
            workflow_data_source
        )
        inputs[ds_key] = ds_ref

        # Optional refs
        for field_name, kind in _OPTIONAL_INPUT_KEYS.items():
            value = getattr(request, field_name, None)
            if value:
                if isinstance(value, ArtifactRef):
                    if value.kind != kind or value.media_type != "application/json":
                        raise ValueError(
                            f"workflow_input_ref_kind_or_media_type_invalid:{field_name}"
                        )
                    inputs[field_name] = value
                else:
                    inputs[field_name] = _make_artifact_ref(value, kind=kind)

        state_payload: dict[str, Any] = {
            "run_id": run_id,
            "inputs": inputs,
            "params": dict(request.params),
        }
        payload = {
            "run_id": run_id,
            "state_payload": state_payload,
            "checkpoint_policy": request.checkpoint_policy,
        }
        if data_view_request_intent is not None:
            payload[_WORKFLOW_DATA_VIEW_REQUEST_INTENT_KEY] = data_view_request_intent.model_dump(
                mode="json"
            )
        self._enqueue_job(
            job_id=job_id,
            job_kind="workflow_run",
            run_id=run_id,
            pipeline_id=None,
            payload=payload,
            policy=policy,
            request_id=request_id,
        )

        return RunLaunchResponse(
            meta=_build_api_meta(request_id),
            status="accepted",
            run_id=run_id,
            job_id=job_id,
            effective_execution_profile=_typed_execution_profile(policy.effective_profile),
            message=f"Workflow run {run_id} accepted and queued for durable execution.",
        )

    def publish_decision_validity_event(
        self,
        request: DecisionValidityEventRequest,
        *,
        request_id: str | None = None,
        event_id: str | None = None,
    ) -> DecisionValidityEventResponse:
        """Record a decision-dependency event and enqueue one deduplicated outbox notification."""
        if request.monitor_event_ref is not None:
            if event_id is not None:
                raise ValueError("monitor_event_decision_validity_event_id_not_supported")
            return self._publish_monitor_decision_validity_event(
                request.monitor_event_ref,
                request_id=request_id,
            )
        dependency_keys = [item.strip() for item in request.dependency_keys if str(item).strip()]
        dedupe_key = request.dedupe_key or self._derive_decision_validity_dedupe_key(
            request,
            dependency_keys=dependency_keys,
        )
        trigger_type = request.trigger_type
        status = request.status
        reason = request.reason
        if trigger_type is None or status is None or reason is None:
            raise ValueError("decision_validity_legacy_event_fields_not_established")
        event = DecisionDependencyEvent(
            event_id=event_id or f"decision_evt_{uuid.uuid4().hex[:16]}",
            dedupe_key=dedupe_key,
            occurred_at=request.occurred_at or datetime.now(UTC).replace(microsecond=0),
            trigger_type=trigger_type,
            status=status,
            reason=reason,
            dependency_keys=dependency_keys,
            source_ref=request.source_ref,
            payload=dict(request.payload),
        )
        try:
            evaluations = self._decision_validity_service.record_dependency_event(event=event)
        except ValueError as exc:
            if str(exc) != "semantic_epoch_dependency_requires_owner_batch":
                raise
            raise unprocessable_entity(
                "Semantic-epoch dependencies require the owner-verified batch intake.",
                code="semantic_epoch_dependency_requires_owner_batch",
            ) from exc
        affected_statuses: dict[str, int] = {}
        affected_packets: list[str] = []
        for evaluation in evaluations:
            status = evaluation.status.value
            affected_statuses[status] = affected_statuses.get(status, 0) + 1
            if (
                evaluation.decision_packet_ref
                and evaluation.decision_packet_ref not in affected_packets
            ):
                affected_packets.append(evaluation.decision_packet_ref)
        self._control_store.enqueue_outbox_event(
            topic="control.decision_validity.event_published",
            event_key=dedupe_key,
            payload={
                "event_id": event.event_id,
                "dedupe_key": dedupe_key,
                "trigger_type": event.trigger_type.value,
                "status": event.status.value,
                "reason": event.reason,
                "dependency_keys": list(event.dependency_keys),
                "source_ref": event.source_ref,
                "affected_packets": affected_packets,
                "affected_statuses": affected_statuses,
            },
        )
        return DecisionValidityEventResponse(
            meta=_build_api_meta(request_id),
            event_id=event.event_id,
            dedupe_key=dedupe_key,
            affected_packets=affected_packets,
            affected_statuses=affected_statuses,
            message=(
                f"Decision validity event {event.event_id} accepted for "
                f"{len(affected_packets)} packet(s)."
            ),
        )

    @overload
    def _publish_monitor_decision_validity_event(
        self,
        monitor_event_ref: ArtifactRef,
        *,
        request_id: str | None,
        published_signature_custody: Literal[False] = False,
    ) -> DecisionValidityEventResponse: ...

    @overload
    def _publish_monitor_decision_validity_event(
        self,
        monitor_event_ref: ArtifactRef,
        *,
        request_id: str | None,
        published_signature_custody: Literal[True],
    ) -> PublishedSignatureCustodyLifecyclePublication: ...

    def _publish_monitor_decision_validity_event(
        self,
        monitor_event_ref: ArtifactRef,
        *,
        request_id: str | None,
        published_signature_custody: bool = False,
    ) -> DecisionValidityEventResponse | PublishedSignatureCustodyLifecyclePublication:
        """Content-bind the monitor arm before deriving any lifecycle consequence."""

        try:
            from polisyos.scientist.governance.continuous import (
                resolve_governance_monitor_event,
            )

            persisted = resolve_governance_monitor_event(
                self._artifact_store,
                monitor_event_ref,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise unprocessable_entity(
                "The governance monitor event could not be resolved exactly.",
                code="monitor_event_unresolvable",
            ) from exc
        event = persisted.event
        perturbation = event.perturbation
        if perturbation is None and not published_signature_custody:
            raise unprocessable_entity(
                "The monitor event does not carry a typed epoch perturbation.",
                code="monitor_event_perturbation_missing",
            )
        if event.observed_epoch_ref is None and not published_signature_custody:
            raise unprocessable_entity(
                "The monitor event does not bind the epoch in which it was observed.",
                code="monitor_event_epoch_binding_missing",
            )
        if published_signature_custody and (
            perturbation is not None
            or event.scope.get("custody_subject") != "published_signature"
            or event.metadata.get("published_signature_custody") != "advisory"
        ):
            raise unprocessable_entity(
                "The custody watcher event is not an advisory published-signature signal.",
                code="published_signature_custody_event_invalid",
            )

        try:
            bridge = self._epoch_claim_lifecycle_bridge.bridge_monitor_event(
                monitor_event_ref=monitor_event_ref,
                actor_id="runtime.control.decision_validity.monitor_event",
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise unprocessable_entity(
                "The monitor event could not be bound to the packet claim lifecycle.",
                code="monitor_event_lifecycle_bridge_rejected",
            ) from exc
        if bridge.monitor_event != persisted:
            raise unprocessable_entity(
                "The lifecycle bridge resolved different monitor bytes.",
                code="monitor_event_lifecycle_bridge_rejected",
            )
        advisory_event_ref: ArtifactRef | None = None
        if not published_signature_custody:
            try:
                advisory_event_ref = persist_advisory_perturbation_event(
                    store=self._artifact_store,
                    persisted_monitor_event=persisted,
                )
            except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
                raise unprocessable_entity(
                    "The monitor event could not be bound to the epoch advisory stream.",
                    code="monitor_event_epoch_advisory_rejected",
                ) from exc

        if published_signature_custody:
            source_class = "published_signature_custody"
        else:
            if perturbation is None:
                raise unprocessable_entity(
                    "The monitor event does not carry a typed epoch perturbation.",
                    code="monitor_event_perturbation_missing",
                )
            source_class = perturbation.source_class
        trigger = DecisionTriggerRecord(
            trigger_type=(
                DecisionTriggerType.POST_DEPLOYMENT_REFUTATION
                if published_signature_custody
                else _MONITOR_TRIGGER_BY_SOURCE_CLASS[source_class]
            ),
            status=(
                DecisionValidityStatus.WARNING
                if event.advisory_posture == "annotation_only"
                else DecisionValidityStatus.REVIEW_REQUIRED
            ),
            reason=event.reason,
            source_ref=str(monitor_event_ref.artifact_id),
            details={
                "monitor_event_ref": monitor_event_ref.model_dump(mode="json"),
                "source_class": source_class,
                "observed_epoch_ref": event.observed_epoch_ref,
                "advisory_event_ref": (
                    advisory_event_ref.model_dump(mode="json")
                    if advisory_event_ref is not None
                    else None
                ),
            },
        )
        evaluation = self._decision_validity_service.mark_packet_trigger(
            packet_ref=str(event.decision_packet_ref.artifact_id),
            trigger=trigger,
        )
        dedupe_key = f"monitor:{monitor_event_ref.artifact_id}"
        affected_packets = [str(event.decision_packet_ref.artifact_id)]
        affected_statuses = {evaluation.status.value: 1}
        self._control_store.enqueue_outbox_event(
            topic=(
                "control.decision_validity.published_signature_custody"
                if published_signature_custody
                else "control.decision_validity.monitor_event_published"
            ),
            event_key=dedupe_key,
            payload={
                "event_id": event.event_id,
                "dedupe_key": dedupe_key,
                "monitor_event_ref": monitor_event_ref.model_dump(mode="json"),
                "lifecycle_bridge_result_ref": bridge.result_ref.model_dump(mode="json"),
                "advisory_event_ref": (
                    advisory_event_ref.model_dump(mode="json")
                    if advisory_event_ref is not None
                    else None
                ),
                "source_class": source_class,
                "affected_packets": affected_packets,
                "affected_statuses": affected_statuses,
            },
        )
        if published_signature_custody:
            return PublishedSignatureCustodyLifecyclePublication(
                event_id=event.event_id,
                dedupe_key=dedupe_key,
                affected_packets=affected_packets,
                affected_statuses=affected_statuses,
                monitor_event_ref=monitor_event_ref,
                lifecycle_bridge_result_ref=bridge.result_ref,
            )
        return DecisionValidityEventResponse(
            meta=_build_api_meta(request_id),
            event_id=event.event_id,
            dedupe_key=dedupe_key,
            affected_packets=affected_packets,
            affected_statuses=affected_statuses,
            monitor_event_ref=monitor_event_ref,
            lifecycle_bridge_result_ref=bridge.result_ref,
            advisory_event_ref=advisory_event_ref,
            message=(
                f"Governance monitor event {event.event_id} was content-bound to "
                "the claim lifecycle and epoch advisory stream."
            ),
        )

    def publish_published_signature_custody_event(
        self,
        monitor_event_ref: ArtifactRef,
    ) -> PublishedSignatureCustodyLifecyclePublication:
        """Bridge one persisted advisory signature-custody event into lifecycle and outbox state."""

        result = self._publish_monitor_decision_validity_event(
            monitor_event_ref,
            request_id=None,
            published_signature_custody=True,
        )
        if not isinstance(result, PublishedSignatureCustodyLifecyclePublication):
            raise RuntimeError("published_signature_custody_publication_type_mismatch")
        return result

    def admit_epoch_validity_batch(
        self,
        request: EpochValidityBatchRequest,
        *,
        request_id: str | None = None,
    ) -> EpochValidityBatchResponse:
        """Delegate the two-field request to the container-owned owner intake."""

        try:
            receipt = self._decision_validity_service.admit_epoch_validity_batch(
                transition_artifact_ref=request.transition_artifact_ref,
                requested_query_context_ref=request.requested_query_context_ref,
            )
        except ValueError as exc:
            code = str(exc)
            if code == "batch_pending":
                raise conflict("An epoch validity batch is already pending.", code=code) from exc
            if code not in _EPOCH_VALIDITY_INTAKE_FAILURE_CODES:
                raise
            raise unprocessable_entity(
                "The epoch validity batch failed owner verification.",
                code=code,
            ) from exc
        except RuntimeError as exc:
            if str(exc) not in {
                "decision_validity_owner_state_corrupt",
                "decision_validity_epoch_receipt_unresolved",
            }:
                raise
            raise unprocessable_entity(
                "The Decision Validity owner state could not be verified.",
                code="decision_validity_owner_state_corrupt",
            ) from exc
        completed_evidence = (
            self._decision_validity_service.resolve_completed_epoch_batch_evidence_by_id(
                batch_id=receipt.batch_id
            )
        )
        claim_bridge_result_refs: list[ArtifactRef] = []
        for packet_id in receipt.affected_packet_refs:
            packet_artifact_id = artifacts.ArtifactID.model_validate(packet_id)
            packet_manifest = self._artifact_store.get_manifest(packet_artifact_id)
            bridge_result = self._epoch_claim_lifecycle_bridge.bridge_completed_batch(
                batch_receipt_ref=completed_evidence.batch_receipt_ref,
                decision_packet_ref=ArtifactRef(
                    artifact_id=packet_manifest.artifact_id,
                    kind=packet_manifest.kind,
                    media_type=packet_manifest.media_type,
                ),
                requested_query_context_ref=receipt.requested_query_context_ref,
            )
            if isinstance(bridge_result, ClaimLifecycleBridgeAdvanced):
                claim_bridge_result_refs.append(bridge_result.bridge_result.bridge_result_ref)
        return EpochValidityBatchResponse(
            meta=_build_api_meta(request_id),
            batch_id=receipt.batch_id,
            state=receipt.state,
            transition=receipt.transition_artifact_ref,
            completion_receipt=receipt,
            affected_packet_refs=receipt.affected_packet_refs,
            claim_bridge_result_refs=tuple(claim_bridge_result_refs),
        )

    def get_decision_validity_summary(
        self,
        packet_ref: str,
        *,
        run_id: str | None = None,
        request_id: str | None = None,
    ) -> DecisionValiditySummaryResponse:
        """Read the latest decision-validity lifecycle summary for a decision packet ref."""
        summary = self._decision_validity_service.get_summary(packet_ref)
        lifecycle_payload = dict(summary.get("lifecycle") or {})
        return DecisionValiditySummaryResponse(
            meta=_build_api_meta(request_id),
            run_id=run_id,
            decision_packet_ref=_make_artifact_ref(
                packet_ref,
                kind="scientist.decision_packet",
            ),
            status=summary["status"],
            lifecycle_status=summary["status"],
            checked_at=summary["checked_at"],
            reasons=list(summary.get("reasons") or []),
            triggers=list(summary.get("triggers") or []),
            review_required=bool(summary.get("review_required")),
            supersedes_decision_ref=_artifact_ref_from_summary_payload(
                summary.get("supersedes_decision_ref"),
                kind="scientist.decision_packet",
            ),
            superseded_by_ref=_artifact_ref_from_summary_payload(
                summary.get("superseded_by_ref"),
                kind="scientist.decision_packet",
            ),
            evaluation_ref=_artifact_ref_from_summary_payload(
                summary.get("evaluation_ref"),
                kind="scientist.decision_validity_evaluation",
            ),
            decision_lineage_key=str(summary.get("decision_lineage_key") or packet_ref),
            recommended_action=str(summary.get("recommended_action") or "none"),
            lifecycle=DecisionValidityLifecycleSummary(
                status=summary["status"],
                events=list(lifecycle_payload.get("events") or []),
                transitions=list(lifecycle_payload.get("transitions") or []),
                pending_reviews=[
                    DecisionValidityPendingReview.model_validate(item)
                    for item in (lifecycle_payload.get("pending_reviews") or [])
                ],
                scheduled_jobs=list(lifecycle_payload.get("scheduled_jobs") or []),
                reissue_candidates=[
                    _make_artifact_ref(
                        candidate["artifact_id"],
                        kind="scientist.decision_reissue_plan",
                    )
                    for candidate in (lifecycle_payload.get("reissue_candidates") or [])
                    if isinstance(candidate, dict) and isinstance(candidate.get("artifact_id"), str)
                ],
                latest_transition_at=lifecycle_payload.get("latest_transition_at"),
            ),
        )

    def reissue_run(
        self,
        run_id: str,
        *,
        request_id: str | None = None,
        principal: RuntimePrincipal | None = None,
    ) -> dict[str, str | None]:
        """Prepare a human-gated reissue payload and enqueue the replacement workflow run."""
        from ..feedback import FeedbackService
        from ..run_index import RunIndexService

        run_index = RunIndexService(
            store=self._artifact_store,
            core_runs_root=self._core_runs_root,
        )
        run = run_index.get_run(run_id)
        policy = self._resolve_execution_policy(
            requested_profile=_coerce_optional_execution_profile(run.details.execution_profile),
            policy_flags=PolicyFlags(),
            principal=principal,
        )
        feedback = FeedbackService(store=self._artifact_store, run_index=run_index)
        prepared = feedback.prepare_reissue(run)
        job_id = uuid.uuid4().hex
        payload = {
            "run_id": prepared.reissued_run_id,
            "state_payload": prepared.state_payload,
            "checkpoint_policy": "strict",
        }
        self._enqueue_job(
            job_id=job_id,
            job_kind="workflow_run",
            run_id=prepared.reissued_run_id,
            pipeline_id=None,
            payload=payload,
            policy=policy,
            request_id=request_id,
        )
        return {
            "job_id": job_id,
            "run_id": prepared.reissued_run_id,
            "effective_execution_profile": policy.effective_profile,
            "monitoring_report_ref": prepared.monitoring_report_ref,
            "compare_report_ref": prepared.compare_report_ref,
            "reissue_plan_ref": prepared.reissue_plan_ref,
            "message": (
                f"Reissue for run {run_id} accepted as {prepared.reissued_run_id} "
                "and queued for durable execution."
            ),
        }

    def _run_legacy_scientist_workflow(
        self,
        state_payload: dict[str, Any],
        *,
        job: ControlJobRecord | None = None,
    ) -> _LegacyScientistWorkflowRun:
        from polisyos.scientist.api import run_experiment

        execution_payload = dict(state_payload)
        # These values are already bound to the admitted job and installed
        # execution context. They are runtime custody, not Scientist inputs.
        # The strict ExperimentState boundary accepts the canonical run/job
        # identifiers and receives tenant/cell scope from the installed context.
        for key in _SCIENTIST_RUNTIME_ONLY_STATE_KEYS:
            execution_payload.pop(key, None)
        raw_context = execution_payload.pop(
            _EVALUATION_SAFETY_EXECUTION_CONTEXT_KEY,
            None,
        )
        execution_context = (
            EvaluationExecutionContext.model_validate(raw_context)
            if raw_context is not None
            else None
        )
        foundry_capture: _RuntimeOriginCapturingFoundryPort | None = None
        source_experiment_state_ref: ArtifactRef | None = None
        if job is not None:
            if job.kind != "workflow_run" or not job.run_id or not job.lease_owner:
                raise ValueError("runtime_graph_producer_scope_not_established")
            from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort

            foundry_capture = _RuntimeOriginCapturingFoundryPort(
                delegate=DefaultFoundryPort(),
                job_id=job.job_id,
                run_id=str(job.run_id),
                attempt=job.attempt,
                lease_owner=job.lease_owner,
            )
        try:
            final_state = run_experiment(
                execution_payload,
                store=self._artifact_store,
                foundry=foundry_capture,
                epoch_certificate_issuance_owner=self._epoch_certificate_issuance_owner,
                eval_safety_execution_context=execution_context,
                eval_safety_verifier=(
                    self._evaluation_safety_admission_verifier
                    if execution_context is not None
                    else None
                ),
                method_metric_selection_owner=self if job is not None else None,
                completed_method_hte_selection_owner=self if job is not None else None,
            )
            if not isinstance(final_state, dict):
                raise TypeError("legacy_scientist_workflow_final_state_not_mapping")
        except Exception as exc:
            if foundry_capture is None:
                raise
            from polisyos.runtime.http.services.control.workspace_loop_transition import (
                _LegacyScientistWorkflowError,
            )

            raise _LegacyScientistWorkflowError(
                str(exc),
                graph_producer_receipt=foundry_capture.producer_receipt(),
            ) from exc
        graph_output_refs = _scientist_graph_output_refs(final_state)
        if job is not None:
            source_experiment_state_ref = self._legacy_scientist_final_state_ref(job=job)
        del final_state
        return _LegacyScientistWorkflowRun(
            graph_output_refs=graph_output_refs,
            source_experiment_state_ref=source_experiment_state_ref,
            graph_producer_receipt=(
                foundry_capture.producer_receipt() if foundry_capture is not None else None
            ),
        )

    def _legacy_scientist_final_state_ref(
        self,
        *,
        job: ControlJobRecord,
    ) -> ArtifactRef | None:
        """Resolve the final-state output from this job's actual terminal Core run."""
        if job.kind != "workflow_run" or not isinstance(job.run_id, str) or not job.run_id:
            return None
        try:
            created = self._control_store.get_job_created_event_payload(job.job_id)
        except RuntimeError, ValueError:
            return None
        if (
            created.get("job_id") != job.job_id
            or created.get("run_id") != job.run_id
            or created.get("job_kind") != "workflow_run"
        ):
            return None
        execution_scope = created.get("execution_scope")
        if not isinstance(execution_scope, Mapping):
            return None
        tenant_id = execution_scope.get("tenant_id")
        cell_id = execution_scope.get("cell_id")
        if not isinstance(tenant_id, str) or not tenant_id:
            return None
        return self._terminal_experiment_state_ref_for_control_job(
            job_id=job.job_id,
            run_id=job.run_id,
            tenant_id=tenant_id,
            cell_id=cell_id if isinstance(cell_id, str) else None,
        )

    # ---- NL launch (agent circuit) ----------------------------------------

    def _validate_control_nl_data_snapshot(self, reference: DataSnapshotRef) -> DataSnapshot:
        """Resolve and type-check one exact DataSnapshot profile view."""
        from polisyos.core.artifacts import validate_core_model_json_artifact
        from polisyos.runtime.http.services.predictive_calibration import _require_selected_ref

        if type(reference) is not DataSnapshotRef:
            raise ValueError("control_nl_data_snapshot_ref_untyped")
        if reference.manifest_profile_sha256 is None:
            raise ValueError("control_nl_data_snapshot_profile_missing")
        _require_selected_ref(
            self._artifact_store,
            reference,
            expected_kind="fabric.data_snapshot",
        )
        manifest = self._artifact_store.get_manifest(reference)
        schema = getattr(manifest, "artifact_schema", None)
        if (
            schema is None
            or schema.name != DataSnapshot.ARTIFACT_SCHEMA_NAME
            or schema.version not in DataSnapshot.ARTIFACT_SCHEMA_VERSIONS
        ):
            raise ValueError("control_nl_data_snapshot_schema_mismatch")
        snapshot = validate_core_model_json_artifact(
            DataSnapshot,
            self._artifact_store,
            reference,
        )
        if snapshot.data_ref.manifest_profile_sha256 is None:
            raise ValueError("control_nl_data_snapshot_data_profile_missing")
        _require_selected_ref(self._artifact_store, snapshot.data_ref, expected_kind=None)
        from polisyos.runtime.quality.data_snapshot_lineage import (
            validate_data_snapshot_owner_lineage,
        )

        validate_data_snapshot_owner_lineage(
            self._artifact_store,
            reference,
            snapshot,
        )
        return snapshot

    def _validate_control_nl_predictive_basis(
        self,
        snapshot_ref: DataSnapshotRef,
        profile_ref: ArtifactRef,
        *,
        unit_id: str,
        resolved_profile: object | None = None,
    ) -> None:
        """Recompute the selected profile-to-snapshot join before N4 execution."""
        from collections.abc import Mapping

        from polisyos.core.artifacts import ensure_ir_artifact_store
        from polisyos.ir import get_json_artifact
        from polisyos.runtime.quality.forecast_profile_binding import (
            join_profile_member_to_observed_series,
        )

        if type(snapshot_ref) is not DataSnapshotRef or type(profile_ref) is not ArtifactRef:
            raise ValueError("control_nl_predictive_basis_ref_untyped")
        snapshot = self._validate_control_nl_data_snapshot(snapshot_ref)
        binding = resolved_profile or self._validate_control_nl_value_data_profile(profile_ref)
        profile = getattr(binding, "profile", None)
        source_projection_ref = getattr(binding, "source_projection_ref", None)
        projection = getattr(binding, "projection", None)
        source_passport = getattr(binding, "source_passport", None)
        if (
            profile is None
            or source_projection_ref is None
            or projection is None
            or getattr(profile, "outcome", None) is None
        ):
            raise ValueError("control_nl_predictive_basis_profile_incomplete")
        observed_data_ref = ArtifactRef.model_validate(snapshot.data_ref.model_dump(mode="python"))
        observed_payload = get_json_artifact(
            ensure_ir_artifact_store(self._artifact_store),
            observed_data_ref,
        )
        if not isinstance(observed_payload, Mapping):
            raise ValueError("control_nl_predictive_basis_observed_data_invalid")
        join_profile_member_to_observed_series(
            profile=profile,
            profile_ref=profile_ref,
            source_projection_ref=source_projection_ref,
            projection=projection,
            observed_source_ref=ArtifactRef.model_validate(snapshot_ref.model_dump(mode="python")),
            observed_data_ref=observed_data_ref,
            target_metric=profile.outcome,
            unit_id=unit_id,
            observed_values=observed_payload.get(profile.outcome),
            source_passport=source_passport,
        )

    def _validate_control_nl_exact_ref(self, reference: ArtifactRef, *, expected_kind: str) -> None:
        """Require an exact, selected JSON CAS view of one declared forecast input."""
        from polisyos.runtime.http.services.predictive_calibration import _require_selected_ref

        if (
            type(reference) is not ArtifactRef
            or reference.kind != expected_kind
            or reference.media_type != "application/json"
            or reference.manifest_profile_sha256 is None
        ):
            raise ValueError("control_nl_predictive_input_ref_invalid")
        _require_selected_ref(self._artifact_store, reference, expected_kind=expected_kind)

    def _validate_control_nl_value_data_profile(self, reference: ArtifactRef) -> object:
        """Resolve an exact selected value profile through this app's bound source."""
        from polisyos.runtime.http.services.predictive_calibration import (
            _validate_selected_value_data_profile,
        )
        from polisyos.runtime.quality.substrate_registry import run_catalog_source_call

        if type(reference) is not ArtifactRef:
            raise ValueError("control_nl_value_data_profile_ref_untyped")
        return run_catalog_source_call(
            self._catalog_serving_source,
            _validate_selected_value_data_profile,
            self._artifact_store,
            reference,
        )

    async def launch_nl_run(
        self,
        request: NaturalLanguageRunRequest,
        *,
        request_id: str | None = None,
        principal: RuntimePrincipal | None = None,
        authorization_proof: object | None = None,
        authorization_request_body: bytes | None = None,
        authorization_query_bytes: bytes = b"",
        idempotency_key: str | None = None,
        on_pre_admission_attempt: Callable[[str], None] | None = None,
    ) -> RunLaunchResponse:
        """Queue a natural-language agent run and apply execution-policy fallback constraints."""
        from polisyos.core.run.context import new_run_id

        if authorization_proof is None:
            raise ValueError("nl_route_authorization_proof_not_established")
        _validate_nl_request_json_values(request)
        if request.data_source is not None and isinstance(
            request.data_source.data_snapshot_ref, DataSnapshotRef
        ):
            try:
                self._validate_control_nl_data_snapshot(request.data_source.data_snapshot_ref)
            except Exception as exc:
                reason = getattr(exc, "code", None)
                raise RuntimeHTTPError(
                    status_code=422,
                    error="request_validation_failed",
                    detail=(
                        "Selected data snapshot is not an exact typed profile in this run scope."
                    ),
                    code="nl_data_snapshot_not_admitted",
                    extensions={"reason": reason or type(exc).__name__},
                ) from exc
        if request.value_data_profile_ref is not None:
            try:
                resolved_profile = self._validate_control_nl_value_data_profile(
                    request.value_data_profile_ref
                )
                profile = getattr(resolved_profile, "profile", None)
                rows = getattr(profile, "rows", ())
                if not any(
                    getattr(row, "unit_id", None) == request.value_data_unit_id for row in rows
                ):
                    raise ValueError("selected_value_data_unit_not_in_profile")
                for reference, expected_kind in (
                    (request.model_spec_ref, "ir.model_spec"),
                    (request.policy_spec_ref, "ir.policy_spec"),
                    (request.calibration_rule_ref, "ir.forecast_calibration_rule"),
                ):
                    if reference is None:
                        raise ValueError("selected_predictive_input_missing")
                    self._validate_control_nl_exact_ref(
                        reference,
                        expected_kind=expected_kind,
                    )
                data_source = request.data_source
                if data_source is None:
                    raise ValueError("nl_predictive_input_data_source_not_established")
                snapshot_ref = data_source.data_snapshot_ref
                if type(snapshot_ref) is not DataSnapshotRef:
                    raise ValueError("selected_predictive_snapshot_not_typed")
                self._validate_control_nl_predictive_basis(
                    snapshot_ref,
                    request.value_data_profile_ref,
                    unit_id=request.value_data_unit_id or "",
                    resolved_profile=resolved_profile,
                )
            except Exception as exc:
                reason = getattr(exc, "code", None)
                raise RuntimeHTTPError(
                    status_code=422,
                    error="request_validation_failed",
                    detail=(
                        "The selected predictive input set does not join to this run's exact "
                        "source."
                    ),
                    code="nl_predictive_input_basis_not_admitted",
                    extensions={"reason": reason or type(exc).__name__},
                ) from exc
        run_id = new_run_id()
        job_id = uuid.uuid4().hex
        request_id = request_id or f"control-job:{job_id}"
        policy = self._resolve_execution_policy(
            requested_profile=request.execution_profile,
            policy_flags=request.policy_flags,
            principal=principal,
        )
        requested_models = _dedupe_models(list(request.llm_models or []))
        if request.llm_model and request.llm_model not in requested_models:
            requested_models.insert(0, request.llm_model)
        if not _is_multimodel_enabled() and len(requested_models) > 1:
            requested_models = requested_models[:1]
        if not requested_models:
            raise unprocessable_entity(
                "Natural-language production runs require a configured LLM model.",
                code="llm_model_unconfigured",
            )
        request_snapshot = {
            "schema_version": _nl_request_snapshot_schema(request),
            "digest_profile": _NL_REQUEST_SNAPSHOT_DIGEST_PROFILE,
            "request": _nl_request_snapshot_request_values(request),
            "normalized_llm_models": list(requested_models),
        }
        request_body_bytes = (
            authorization_request_body
            if authorization_request_body is not None
            else _nl_request_body_bytes(request)
        )
        authorization_receipt = (
            _build_nl_authorization_receipt(
                authorization_proof,
                request_id=request_id,
                request=request,
                request_body_bytes=request_body_bytes,
                request_query_bytes=authorization_query_bytes,
                normalized_llm_models=requested_models,
            )
            if authorization_proof is not None
            else None
        )
        if authorization_receipt is not None:
            permission_snapshot = authorization_receipt.get("permission_snapshot")
            if not isinstance(permission_snapshot, Mapping) or (
                permission_snapshot.get("subject") != policy.actor.get("subject")
                or permission_snapshot.get("tenant_id") != policy.actor.get("tenant_id")
                or tuple(permission_snapshot.get("roles", ()))
                != tuple(sorted(policy.actor.get("roles", ())))
            ):
                raise ValueError("nl_route_authorization_actor_binding_mismatch")
        provider_preflight_payload: dict[str, Any] | None = None
        pre_admission_attempt_id: str | None = None
        pre_admission_preflight_no_call = False
        provider_preflight_required = (
            policy.effective_profile in CONTROL_PRE_ADMISSION_SETTLEMENT_REQUIRED_PROFILES
        )
        if requested_models and (
            on_pre_admission_attempt is not None or provider_preflight_required
        ):
            from polisyos.scientist.orchestration.engine import (
                BudgetLedgerProducerRunBinding,
            )

            preflight_execution_scope = self._execution_scope_for_policy(policy)
            producer_settlement_store = self._llm_producer_settlement_store
            producer_run_binding = None
            if (
                producer_settlement_store is not None
                and preflight_execution_scope.status == "established"
                and preflight_execution_scope.tenant_id is not None
                and preflight_execution_scope.cell_id is not None
            ):
                producer_run_binding = BudgetLedgerProducerRunBinding(
                    run_id=run_id,
                    tenant_id=preflight_execution_scope.tenant_id,
                    cell_id=preflight_execution_scope.cell_id,
                    profile_id=policy.effective_profile,
                    control_job_id=job_id,
                )
            if idempotency_key is not None and (
                not idempotency_key
                or idempotency_key != idempotency_key.strip()
                or len(idempotency_key) > 128
                or any(ord(character) < 33 or ord(character) > 126 for character in idempotency_key)
            ):
                raise unprocessable_entity(
                    (
                        "Idempotency-Key must be a non-empty printable ASCII value of at most "
                        "128 characters."
                    ),
                    code="control_pre_admission_idempotency_key_invalid",
                )
            if principal is None or not principal.authenticated:
                raise forbidden(
                    (
                        "Natural-language launch ownership requires an authenticated actor, "
                        "tenant, and cell scope."
                    ),
                    code="control_pre_admission_scope_not_established",
                )
            if idempotency_key is None:
                raise unprocessable_entity(
                    (
                        "Every HTTP natural-language launch requires an Idempotency-Key for "
                        "safe recovery."
                    ),
                    code="control_pre_admission_idempotency_key_required",
                )
            scope_values = (principal.subject, principal.tenant_id, principal.cell_id)
            scope_sentinels = {
                "unknown",
                "tenant-unknown",
                "cell-unknown",
                "anonymous",
                "none",
                "null",
            }
            if any(
                not isinstance(value, str)
                or not value
                or value != value.strip()
                or value.casefold() in scope_sentinels
                for value in scope_values
            ):
                raise forbidden(
                    (
                        "Natural-language launch ownership requires an authenticated actor, "
                        "tenant, and cell scope."
                    ),
                    code="control_pre_admission_scope_not_established",
                )
            if (
                preflight_execution_scope.status != "established"
                or preflight_execution_scope.actor_subject != principal.subject
                or preflight_execution_scope.tenant_id != principal.tenant_id
                or preflight_execution_scope.cell_id != principal.cell_id
            ):
                raise forbidden(
                    "Natural-language launch scope does not match the authenticated principal.",
                    code="control_pre_admission_scope_mismatch",
                )
            authorization_snapshot = (
                authorization_receipt.get("permission_snapshot")
                if isinstance(authorization_receipt, Mapping)
                else None
            )
            if not isinstance(authorization_snapshot, Mapping):
                raise ValueError("nl_route_authorization_snapshot_not_established")
            intent_binding = {
                "schema_version": "polisyos.runtime.control_pre_admission_intent.v1",
                "request_content_sha256": _nl_request_snapshot_content_hash(request_snapshot),
                "actor_subject": principal.subject,
                "tenant_id": principal.tenant_id,
                "cell_id": principal.cell_id,
                "effective_execution_profile": policy.effective_profile,
                "authorization_permission": authorization_snapshot.get("required_permission"),
                "authorization_resource_sha256": authorization_snapshot.get("resource_digest"),
            }
            idempotency_digest = (
                hashlib.sha256(idempotency_key.encode("ascii")).hexdigest()
                if idempotency_key is not None
                else None
            )
            if idempotency_digest is None:
                raise RuntimeError("billable pre-admission intent key was not established")
            pre_admission_attempt_id = hashlib.sha256(
                f"control.nl_pre_admission.v1\0control.runs.nl\0{principal.tenant_id}\0{principal.cell_id}\0{principal.subject}\0{idempotency_digest}".encode()
            ).hexdigest()[:32]
            try:
                attempt_record, attempt_created = self._control_store.start_pre_admission_attempt(
                    attempt_id=pre_admission_attempt_id,
                    request_id=request_id,
                    run_id=run_id,
                    candidate_job_id=job_id,
                    effective_execution_profile=policy.effective_profile,
                    intent_binding=intent_binding,
                    producer_run_binding=(
                        producer_run_binding.model_dump(mode="json")
                        if producer_run_binding is not None
                        else None
                    ),
                    idempotency_key_sha256=idempotency_digest,
                )
            except ControlPreAdmissionIdempotencyConflictError as exc:
                if on_pre_admission_attempt is not None:
                    on_pre_admission_attempt(exc.attempt_id)
                raise conflict(
                    (
                        "Idempotency-Key is already bound to a different natural-language "
                        "launch intent."
                    ),
                    code="control_pre_admission_idempotency_conflict",
                    extensions={"pre_admission_attempt_id": exc.attempt_id},
                ) from exc
            pre_admission_attempt_id = attempt_record.attempt_id
            if on_pre_admission_attempt is not None:
                on_pre_admission_attempt(pre_admission_attempt_id)
            if not attempt_created:
                if attempt_record.status == "admitted" and attempt_record.job_id is not None:
                    return RunLaunchResponse(
                        meta=_build_api_meta(request_id),
                        status="accepted",
                        run_id=attempt_record.run_id,
                        job_id=attempt_record.job_id,
                        effective_execution_profile=_typed_execution_profile(
                            attempt_record.effective_execution_profile
                        ),
                        message=(
                            "This idempotent launch was already admitted; "
                            "no duplicate job was created."
                        ),
                    )
                if attempt_record.status == "refused" and attempt_record.job_id is not None:
                    return RunLaunchResponse(
                        meta=_build_api_meta(request_id),
                        status="rejected",
                        run_id=attempt_record.run_id,
                        job_id=attempt_record.job_id,
                        effective_execution_profile=_typed_execution_profile(
                            attempt_record.effective_execution_profile
                        ),
                        message=(
                            "This idempotent launch was already refused; "
                            "no duplicate job was created."
                        ),
                    )
                raise conflict(
                    (
                        "This idempotent launch already has an unresolved pre-admission "
                        "attempt; inspect its history before retrying."
                    ),
                    code="control_pre_admission_attempt_unresolved",
                    extensions={
                        "pre_admission_attempt_id": attempt_record.attempt_id,
                        "pre_admission_attempt_status": attempt_record.status,
                    },
                )
            if provider_preflight_required and (
                producer_settlement_store is None or producer_run_binding is None
            ):
                self._control_store.observe_pre_admission_attempt(
                    attempt_id=pre_admission_attempt_id,
                    event_type="refused",
                    failure_code="producer_run_binding_not_established",
                    producer_event_observation="no_call",
                    producer_no_call_reason="producer_run_binding_not_established",
                )
                raise unprocessable_entity(
                    (
                        "Natural-language launch was refused because its durable producer "
                        "binding is unavailable."
                    ),
                    code="producer_run_binding_not_established",
                )
            if provider_preflight_required:
                try:
                    preflight_report = await run_provider_preflight(
                        models=requested_models,
                        producer_settlement_store=producer_settlement_store,
                        producer_run_binding=producer_run_binding,
                        pre_admission_attempt_id=pre_admission_attempt_id,
                        producer_budget_key=f"nl-run:{run_id}",
                        require_producer_settlement=True,
                    )
                    if type(preflight_report) is not ProviderPreflightReport:
                        raise RuntimeError(
                            "control_pre_admission_provider_preflight_report_invalid"
                        )
                    producer_event_ids, producer_event_observation = (
                        _pre_admission_producer_event_refs(
                            producer_settlement_store, producer_run_binding
                        )
                    )
                    provider_preflight_payload = preflight_report.model_dump(mode="json")
                    completion_observation = preflight_report.producer_completion_observation
                    if completion_observation == "not_started":
                        if preflight_report.status not in {"failed", "skipped"}:
                            raise RuntimeError(
                                "control_pre_admission_provider_preflight_no_call_status_invalid"
                            )
                        if producer_event_observation == "complete" or producer_event_ids:
                            raise RuntimeError(
                                "control_pre_admission_provider_preflight_no_call_has_producer_events"
                            )
                        pre_admission_preflight_no_call = True
                    elif (
                        completion_observation == "complete"
                        and preflight_report.status != "unknown"
                        and producer_event_observation == "complete"
                        and producer_event_ids
                    ):
                        self._control_store.observe_pre_admission_attempt(
                            attempt_id=pre_admission_attempt_id,
                            event_type="settled",
                            producer_event_ids=producer_event_ids,
                            producer_event_observation="complete",
                        )
                    else:
                        self._control_store.observe_pre_admission_attempt(
                            attempt_id=pre_admission_attempt_id,
                            event_type="failed",
                            producer_event_ids=producer_event_ids,
                            producer_event_observation="unavailable",
                            failure_code="provider_preflight_settlement_unavailable",
                        )
                        raise conflict(
                            (
                                "Provider preflight completion or producer settlement is "
                                "unresolved; "
                                "inspect the attempt and reconcile its history before retrying."
                            ),
                            code="control_pre_admission_attempt_unresolved",
                            extensions={
                                "pre_admission_attempt_id": pre_admission_attempt_id,
                                "pre_admission_attempt_status": "failed",
                            },
                        )
                except BaseException as exc:
                    current_attempt = self._control_store.get_pre_admission_attempt(
                        pre_admission_attempt_id
                    )
                    if current_attempt is not None and current_attempt.status in {
                        "started",
                        "settled",
                    }:
                        event_refs, event_observation = _pre_admission_producer_event_refs(
                            producer_settlement_store, producer_run_binding
                        )
                        terminal_status = (
                            "cancelled" if isinstance(exc, asyncio.CancelledError) else "failed"
                        )
                        try:
                            if (
                                current_attempt.status == "started"
                                and event_refs
                                and event_observation == "complete"
                            ):
                                current_attempt = self._control_store.observe_pre_admission_attempt(
                                    attempt_id=pre_admission_attempt_id,
                                    event_type="settled",
                                    producer_event_ids=event_refs,
                                    producer_event_observation=event_observation,
                                )
                            self._control_store.observe_pre_admission_attempt(
                                attempt_id=pre_admission_attempt_id,
                                event_type=terminal_status,
                                producer_event_ids=event_refs,
                                producer_event_observation=event_observation,
                                failure_code=(
                                    "provider_preflight_cancelled"
                                    if terminal_status == "cancelled"
                                    else "provider_preflight_exception"
                                ),
                            )
                        except BaseException:
                            logger.exception("Pre-admission attempt terminal observation failed")
                    raise
                if preflight_report.status != "ok":
                    preflight_ref = self._put_json_artifact(
                        provider_preflight_payload,
                        kind="runtime.provider_preflight_report",
                        schema_name="polisyos.runtime.ProviderPreflightReport",
                    )
                    execution_scope = preflight_execution_scope
                    policy = self._policy_with_execution_scope(policy, execution_scope)
                    submitted_by = execution_scope.actor_subject or "anonymous"
                    capability_manifest_ref = self._persist_capability_manifest(
                        policy=policy,
                        job_id=job_id,
                        run_id=run_id,
                        pipeline_id=None,
                        payload_ref=None,
                    )
                    self._control_store.create_job(
                        job_id=job_id,
                        kind="natural_language_run",
                        run_id=run_id,
                        pipeline_id=None,
                        requested_execution_profile=policy.requested_profile,
                        effective_execution_profile=_typed_execution_profile(
                            policy.effective_profile
                        ),
                        policy_flags=policy.policy_flags.model_dump(mode="json"),
                        capability_manifest_ref=capability_manifest_ref,
                        payload_ref=None,
                        submitted_by=submitted_by,
                        creation_event_payload=self._job_created_event_payload(
                            job_id=job_id,
                            job_kind="natural_language_run",
                            run_id=run_id,
                            pipeline_id=None,
                            payload_ref=None,
                            submitted_by=submitted_by,
                            requested_execution_profile=policy.requested_profile,
                            effective_execution_profile=_typed_execution_profile(
                                policy.effective_profile
                            ),
                            policy_flags=policy.policy_flags.model_dump(mode="json"),
                            capability_manifest_ref=capability_manifest_ref,
                            execution_scope=execution_scope,
                        ),
                        initial_state="failed",
                        initial_error_message="provider_preflight_refused",
                        initial_progress={
                            "state": "failed",
                            "phase": "provider_preflight",
                            "run_id": run_id,
                            "provider_preflight_ref": preflight_ref,
                            "provider_preflight": provider_preflight_payload,
                        },
                        pre_admission_attempt_id=pre_admission_attempt_id,
                        pre_admission_outcome="refused",
                        pre_admission_producer_event_observation=(
                            "no_call" if pre_admission_preflight_no_call else None
                        ),
                        pre_admission_no_call_reason=(
                            "provider_preflight_not_started"
                            if pre_admission_preflight_no_call
                            else None
                        ),
                        pre_admission_failure_code=(
                            "provider_preflight_not_started"
                            if pre_admission_preflight_no_call
                            else None
                        ),
                    )
                    failure = dict(preflight_report.failure or {})
                    failure.setdefault("code", "llm_provider_preflight_failed")
                    failure.setdefault("layer", "llm_gateway")
                    failure.setdefault("phase", "provider_preflight")
                    failure.setdefault("message", "LLM provider preflight failed.")
                    failure.setdefault("retryable", bool(preflight_report.retryable))
                    failure.setdefault("run_id", run_id)
                    failure.setdefault("job_id", job_id)
                    artifact_refs = failure.get("artifact_refs")
                    if not isinstance(artifact_refs, dict):
                        artifact_refs = {}
                    artifact_refs["provider_preflight_ref"] = preflight_ref
                    failure["artifact_refs"] = artifact_refs
                    self._control_store.fail_job(
                        job_id=job_id,
                        error_message=str(
                            failure.get("message") or "LLM provider preflight failed."
                        ),
                        capability_manifest_ref=capability_manifest_ref,
                        progress={
                            "state": "failed",
                            "phase": "provider_preflight",
                            "run_id": run_id,
                            "provider_preflight_ref": preflight_ref,
                            "provider_preflight": provider_preflight_payload,
                            "failure": failure,
                        },
                    )
                    return RunLaunchResponse(
                        meta=_build_api_meta(request_id),
                        status="rejected",
                        run_id=run_id,
                        job_id=job_id,
                        effective_execution_profile=_typed_execution_profile(
                            policy.effective_profile
                        ),
                        message=(
                            f"Natural-language run {run_id} was rejected by LLM provider "
                            "preflight. Inspect the control job failure envelope."
                        ),
                    )
        nl_payload = {
            "run_id": run_id,
            "request": request.request,
            "joint_interaction_candidate_intent": request.joint_interaction_candidate_intent,
            "context": dict(request.context),
            "domain_hint": request.domain_hint,
            "data_source": request.data_source.model_dump(mode="json")
            if request.data_source
            else None,
            **(
                {"target_world_scope_profile_id": request.target_world_scope_profile_id}
                if request.target_world_scope_profile_id is not None
                else {}
            ),
            "max_iterations": request.max_iterations,
            "llm_models": requested_models,
            "max_parallel_models": request.max_parallel_models,
            "run_budget_usd": request.run_budget_usd,
            "per_model_budget_usd": request.per_model_budget_usd,
            "checkpoint_policy": request.checkpoint_policy,
            "execution_plan_ref": request.execution_plan_ref,
            "execution_plan": request.execution_plan,
            "stop_criteria": request.stop_criteria,
            "governance_constraints": request.governance_constraints,
            "expected_outputs": request.expected_outputs,
            "provider_preflight": provider_preflight_payload,
        }
        if request.temporal_scope is not None:
            nl_payload["temporal_scope"] = request.model_dump(mode="json")["temporal_scope"]
        if request.value_data_profile_ref is not None:
            for field_name in (
                "value_data_profile_ref",
                "value_data_unit_id",
                "model_spec_ref",
                "policy_spec_ref",
                "calibration_rule_ref",
            ):
                selected = getattr(request, field_name)
                nl_payload[field_name] = (
                    selected.model_dump(mode="json")
                    if isinstance(selected, ArtifactRef)
                    else selected
                )
        nl_payload[_NL_REQUEST_SNAPSHOT_KEY] = request_snapshot
        if authorization_receipt is not None:
            nl_payload[_NL_AUTHORIZATION_RECEIPT_KEY] = authorization_receipt
        try:
            queued_job = self._enqueue_job(
                job_id=job_id,
                job_kind="natural_language_run",
                run_id=run_id,
                pipeline_id=None,
                payload=nl_payload,
                policy=policy,
                request_id=request_id,
                pre_admission_attempt_id=pre_admission_attempt_id,
            )
        except BaseException as exc:
            current_attempt = (
                self._control_store.get_pre_admission_attempt(pre_admission_attempt_id)
                if pre_admission_attempt_id is not None
                else None
            )
            if current_attempt is not None and current_attempt.status in {
                "started",
                "settled",
            }:
                refs: tuple[str, ...] = ()
                observation: Literal["not_applicable", "complete", "unavailable"] = "unavailable"
                if current_attempt.producer_run_binding is not None:
                    from polisyos.scientist.orchestration.engine import (
                        BudgetLedgerProducerRunBinding,
                    )

                    try:
                        bound = BudgetLedgerProducerRunBinding.model_validate(
                            current_attempt.producer_run_binding
                        )
                    except TypeError, ValueError:
                        observation = "unavailable"
                    else:
                        refs, observation = _pre_admission_producer_event_refs(
                            self._llm_producer_settlement_store, bound
                        )
                existing_job = self._control_store.get_job(job_id)
                linked = existing_job is not None and (
                    existing_job.state != "failed"
                    or existing_job.progress.get("phase") != "job_admission"
                )
                try:
                    self._control_store.observe_pre_admission_attempt(
                        attempt_id=current_attempt.attempt_id,
                        event_type=(
                            "admitted"
                            if linked
                            else "cancelled"
                            if isinstance(exc, asyncio.CancelledError)
                            else "failed"
                        ),
                        producer_event_ids=refs,
                        producer_event_observation=observation,
                        failure_code=(
                            None
                            if linked
                            else "provider_preflight_cancelled"
                            if isinstance(exc, asyncio.CancelledError)
                            else "launch_admission_exception"
                        ),
                        job_id=existing_job.job_id if linked and existing_job is not None else None,
                    )
                except BaseException:
                    logger.exception("Pre-admission attempt admission observation failed")
            raise
        if queued_job.state == "failed":
            return RunLaunchResponse(
                meta=_build_api_meta(request_id),
                status="rejected",
                run_id=run_id,
                job_id=job_id,
                effective_execution_profile=_typed_execution_profile(policy.effective_profile),
                message=(
                    "Natural-language run was refused because its execution intent "
                    "or route authorization could not be established."
                ),
            )

        models_label = ", ".join(requested_models)
        if len(requested_models) > 1:
            mode_label = (
                f"{len(requested_models)} model variants "
                f"(parallel={max(1, min(request.max_parallel_models, len(requested_models)))})"
            )
        elif requested_models:
            mode_label = "single model"
        else:  # pragma: no cover - guarded by llm_model_unconfigured above.
            raise AssertionError("llm_model_unconfigured")

        return RunLaunchResponse(
            meta=_build_api_meta(request_id),
            status="accepted",
            run_id=run_id,
            job_id=job_id,
            effective_execution_profile=_typed_execution_profile(policy.effective_profile),
            message=(
                f"Natural-language run {run_id} accepted. "
                f"Agent circuit was queued in {mode_label}: {models_label}."
            ),
        )

    # ---- Data ingestion ---------------------------------------------------

    def run_data_ingestion(
        self,
        request: IngestRequest,
        *,
        request_id: str | None = None,
    ) -> IngestResponse:
        """Execute connector ingestion and return refs/status for produced artifacts."""
        from polisyos.core.artifacts import ArtifactOwnershipError
        from polisyos.fabric.ingestion import (
            ConnectorManifestSpec,
            DatasetFetchSpec,
            IngestionDependencies,
        )
        from polisyos.fabric.ingestion.ingestion_providers import IngestionStoreBindingError
        from polisyos.fabric.storage.tenant_cas import TenantSidecarScope
        from polisyos.runtime.http.errors import forbidden

        datasets = [
            DatasetFetchSpec(
                connector_id=ds.connector_id,
                dataset_id=ds.dataset_id,
                filters=ds.filters,
                date_start=ds.date_start,
                date_end=ds.date_end,
            )
            for ds in request.datasets
        ]
        if request.fetch_plans:
            datasets.extend(
                DatasetFetchSpec(
                    connector_id=plan.connector_id,
                    dataset_id=plan.dataset_id,
                    filters=plan.filters,
                    date_start=plan.date_start,
                    date_end=plan.date_end,
                )
                for plan in request.fetch_plans
            )

        manifest = ConnectorManifestSpec(
            datasets=datasets,
            cache_policy=request.cache_policy if request.cache_policy != "default" else None,
        )

        # Resolve connection profile → ConnectionConfig
        connection_config = None
        connection_profile_id = request.connection_profile
        if not connection_profile_id:
            profile_ids = {plan.profile_id for plan in request.fetch_plans if plan.profile_id}
            if len(profile_ids) == 1:
                connection_profile_id = next(iter(profile_ids))
            elif len(profile_ids) > 1:
                logger.warning(
                    "Multiple profile_ids in fetch_plans; using connector defaults. "
                    "Provide connection_profile for deterministic credentials."
                )

        if connection_profile_id:
            from polisyos.fabric.connectors.profiles.resolver import (
                resolve_connection_config,
            )

            profile_reg = self._registry_providers.source_profiles
            profile = profile_reg.get(connection_profile_id)
            if profile:
                connection_config = resolve_connection_config(profile)

        def _served_ingestion_store(root: Path) -> RootedArtifactStore:
            requested_root = Path(root).resolve()
            service_root = Path(self._cas_root).resolve()
            store_root = getattr(self._artifact_store, "root", None)
            if (
                requested_root != service_root
                or not isinstance(store_root, (str, Path))
                or Path(store_root).resolve() != service_root
            ):
                raise IngestionStoreBindingError("served_ingestion_store_root_mismatch")
            return cast("RootedArtifactStore", self._artifact_store)

        sidecar_scope = TenantSidecarScope.from_current_context(self._cas_root)
        ingestion_dependencies = IngestionDependencies(
            registry=cast("Any", self._registry_providers.connectors),
            tracer=self._tracer,
            metrics=self._metrics,
            store_factory=_served_ingestion_store,
            source_progress_readers=self._registry_providers.source_progress_readers,
        )

        mode = request.execution_mode
        if request.replay_ref is not None:
            mode = "replay"
        record_ref: str | None = None
        try:
            # Record/replay takes priority over execution mode dispatch
            if request.replay_ref is not None:
                from polisyos.fabric.data_plane.modes import run_replay_mode

                result = run_replay_mode(
                    connector_manifest=manifest,
                    source=request.source,
                    license_name=request.license_name,
                    cas_root=self._cas_root,
                    replay_ref=request.replay_ref,
                    connection_config=connection_config,
                    produce_snapshot=request.produce_data_snapshot,
                    ingestion_dependencies=ingestion_dependencies,
                    sidecar_scope=sidecar_scope,
                )
            elif request.record_mode:
                from polisyos.fabric.data_plane.modes import run_record_mode

                result, record_ref = run_record_mode(
                    connector_manifest=manifest,
                    source=request.source,
                    license_name=request.license_name,
                    cas_root=self._cas_root,
                    connection_config=connection_config,
                    produce_snapshot=request.produce_data_snapshot,
                    ingestion_dependencies=ingestion_dependencies,
                    sidecar_scope=sidecar_scope,
                )
            elif mode == "streaming_windowed":
                from polisyos.fabric.data_plane.modes import run_streaming_windowed

                result = run_streaming_windowed(
                    connector_manifest=manifest,
                    source=request.source,
                    license_name=request.license_name,
                    cas_root=self._cas_root,
                    connection_config=connection_config,
                    produce_snapshot=request.produce_data_snapshot,
                    ingestion_dependencies=ingestion_dependencies,
                    sidecar_scope=sidecar_scope,
                )
            elif mode == "batch_incremental":
                from polisyos.fabric.data_plane.modes import run_batch_incremental

                result = run_batch_incremental(
                    connector_manifest=manifest,
                    source=request.source,
                    license_name=request.license_name,
                    cas_root=self._cas_root,
                    connection_config=connection_config,
                    produce_snapshot=request.produce_data_snapshot,
                    ingestion_dependencies=ingestion_dependencies,
                    sidecar_scope=sidecar_scope,
                )
            else:
                from polisyos.fabric.data_plane.orchestrator import (
                    run_orchestrated_ingestion,
                )

                result = run_orchestrated_ingestion(
                    connector_manifest=manifest,
                    source=request.source,
                    license_name=request.license_name,
                    cas_root=self._cas_root,
                    connection_config=connection_config,
                    produce_snapshot=request.produce_data_snapshot,
                    ingestion_dependencies=ingestion_dependencies,
                    sidecar_scope=sidecar_scope,
                )

            from polisyos.fabric.data_plane import ingestion_is_complete

            # Post-ingestion: produce input bindings if requested
            input_bindings_ref: str | None = None
            if (
                ingestion_is_complete(result)
                and request.produce_input_bindings
                and request.binding_profile_id
            ):
                input_bindings_ref = self._produce_input_bindings(
                    binding_profile_id=request.binding_profile_id,
                    data_snapshot_ref=(
                        str(result.data_snapshot_ref.artifact_id.hex)
                        if result.data_snapshot_ref
                        else None
                    ),
                )

            return IngestResponse(
                meta=_build_api_meta(request_id),
                status=result.status,
                evidence_bundle_ref=(
                    str(result.evidence_bundle_ref.artifact_id.hex)
                    if result.evidence_bundle_ref
                    else None
                ),
                data_snapshot_ref=(
                    str(result.data_snapshot_ref.artifact_id.hex)
                    if ingestion_is_complete(result) and result.data_snapshot_ref
                    else None
                ),
                datasets_fetched=result.datasets_fetched,
                message=(
                    f"Successfully ingested {result.datasets_fetched} dataset(s)."
                    if ingestion_is_complete(result)
                    else f"Ingestion {result.status}: {result.datasets_fetched} source(s) retained."
                ),
                warnings=result.warnings,
                cursor_ref=result.cursor_ref,
                mode_effective=result.mode_effective or mode,
                record_ref=record_ref,
                input_bindings_ref=input_bindings_ref,
            )
        except ArtifactOwnershipError as exc:
            raise forbidden(
                "Ingestion artifact is not accessible in the current tenant scope",
                code="ingestion_artifact_ownership_denied",
            ) from exc
        except (LookupError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.exception("Data ingestion failed: %s", exc)
            return IngestResponse(
                meta=_build_api_meta(request_id),
                status="failed",
                datasets_fetched=0,
                message=f"Ingestion failed: {exc}",
                mode_effective=mode,
            )

    def data_resolve(
        self,
        request: DataResolveRequest,
        *,
        request_id: str | None = None,
    ) -> DataResolveResponse:
        """Resolve `DataNeed[]` into concrete fetch plans via the retrieval service."""
        from polisyos.data_forge.read_api.catalog import (
            CatalogSelectionError,
            validate_catalog_run_profile,
        )

        configured_profile = self._catalog_run_profile
        requested_profile = request.catalog_run_profile
        try:
            if requested_profile is not None:
                if not isinstance(requested_profile, str):
                    raise CatalogSelectionError("unsupported_run_profile", repr(requested_profile))
                requested_profile = validate_catalog_run_profile(requested_profile)
            if configured_profile is not None:
                configured_profile = validate_catalog_run_profile(configured_profile)
        except CatalogSelectionError as exc:
            raise unprocessable_entity(exc.detail, code=exc.code) from exc
        if (
            configured_profile is not None
            and requested_profile is not None
            and configured_profile != requested_profile
        ):
            raise unprocessable_entity(
                "The requested catalog run profile conflicts with the runtime selection.",
                code="catalog_run_profile_conflict",
            )
        selected_profile = configured_profile or requested_profile
        try:
            result = self._retrieval.resolve(request, run_profile=selected_profile)
        except CatalogSelectionError as exc:
            raise unprocessable_entity(exc.detail, code=exc.code) from exc
        return DataResolveResponse(
            meta=_build_api_meta(request_id),
            mode=_coerce_retrieval_mode(result.mode),
            fetch_plans=result.fetch_plans,
            candidates=result.candidates,
            warnings=result.warnings,
        )

    def data_discover(
        self,
        request: DataDiscoverRequest,
        *,
        request_id: str | None = None,
    ) -> DataDiscoverResponse:
        """Run bounded discovery over connector metadata and return ranked candidates."""
        result = self._retrieval.discover(
            data_needs=request.data_needs,
            max_sources_per_query=request.max_sources_per_query,
            max_discovery_calls_per_source=request.max_discovery_calls_per_source,
            max_candidates_total=request.max_candidates_total,
            time_budget_ms=request.time_budget_ms,
            cost_budget_usd=request.cost_budget_usd,
        )
        return DataDiscoverResponse(
            meta=_build_api_meta(request_id),
            candidates=result.candidates,
            docs_fetched_total=result.docs_fetched_total,
            index_stats=self._retrieval.get_index_stats(),
            warnings=result.warnings,
        )

    def data_preview(
        self,
        request: DataPreviewRequest,
        *,
        request_id: str | None = None,
    ) -> DataPreviewResponse:
        """Preview one fetch plan through quality/retrieval fallback semantics."""
        result = self._retrieval.preview(
            request.fetch_plan,
            allow_fallback=request.allow_fallback,
        )
        return DataPreviewResponse(
            meta=_build_api_meta(request_id),
            preview=result.preview,
        )

    def search_data_catalog(
        self,
        *,
        metric_query: str,
        geography: str | None = None,
        limit: int = 25,
        request_id: str | None = None,
    ) -> CapabilityDiscoveryResponse:
        """Delegate the legacy dataset address to canonical capability discovery."""
        budget: dict[str, object] = {"top_k": limit}
        if geography is not None:
            budget["geography"] = geography
        return self.search_capabilities(
            CapabilityDiscoveryRequest(
                search=SearchRequest(
                    request_id=request_id or f"catalog:{uuid.uuid4().hex}",
                    query_text=metric_query,
                    construct_refs=(metric_query,),
                    intent="capability_discovery",
                    required_layers=("L1",),
                    authority_purpose="review_capability_candidates",
                    allowed_modes=("exact", "alias", "lexical", "semantic"),
                    budget=budget,
                    rule_version="policyos.runtime.http.capability_discovery.v1",
                ),
                resource_kinds=("dataset",),
                audience="REVIEWER",
            ),
            request_id=request_id,
        )

    def search_capabilities(
        self,
        request: CapabilityDiscoveryRequest,
        *,
        request_id: str | None = None,
    ) -> CapabilityDiscoveryResponse:
        """Search through the sole injected owner and persist the exact response packet."""
        service = self._capability_discovery_service
        if service is None:
            raise RuntimeError("capability discovery service is not bound")
        response = service.search(request, meta=_build_api_meta(request_id))
        self._put_json_artifact(
            response.model_dump(mode="json"),
            kind="runtime.capability_discovery_response",
            schema_name="polisyos.core.contracts.CapabilityDiscoveryResponse",
        )
        return response

    def get_data_index_stats(self, *, request_id: str | None = None) -> IndexStatsResponse:
        """Return retrieval index statistics for `/control/data/index/stats`."""
        return IndexStatsResponse(
            meta=_build_api_meta(request_id),
            stats=self._retrieval.get_index_stats(),
        )

    def list_promotion_candidates(
        self,
        *,
        request_id: str | None = None,
    ) -> PromotionCandidatesResponse:
        """Return current PromotionLane candidates from the retrieval service."""
        return PromotionCandidatesResponse(
            meta=_build_api_meta(request_id),
            candidates=self._retrieval.list_promotion_candidates(),
        )

    def approve_promotion_candidate(
        self,
        promotion_id: str,
        request: PromotionDecisionRequest,
        *,
        request_id: str | None = None,
    ) -> PromotionDecisionResponse:
        """Approve one promotion candidate and report whether source bindings changed."""
        updated = self._retrieval.approve_promotion(promotion_id, reason=request.reason)
        status = "approved" if updated else "rejected"
        return PromotionDecisionResponse(
            meta=_build_api_meta(request_id),
            promotion_id=promotion_id,
            status=status,
            message=(
                "Promotion candidate approved and source bindings updated."
                if updated
                else "Promotion candidate not found."
            ),
            binding_updated=updated,
        )

    def reject_promotion_candidate(
        self,
        promotion_id: str,
        request: PromotionDecisionRequest,
        *,
        request_id: str | None = None,
    ) -> PromotionDecisionResponse:
        """Reject one promotion candidate and preserve an audit-friendly response shape."""
        updated = self._retrieval.reject_promotion(promotion_id, reason=request.reason)
        return PromotionDecisionResponse(
            meta=_build_api_meta(request_id),
            promotion_id=promotion_id,
            status="rejected",
            message=(
                "Promotion candidate rejected." if updated else "Promotion candidate not found."
            ),
            binding_updated=False,
        )

    def _produce_input_bindings(
        self,
        *,
        binding_profile_id: str,
        data_snapshot_ref: str | None,
    ) -> str | None:
        """Resolve binding profile and persist rules as a CAS artifact."""
        from polisyos.fabric.connectors.bindings.resolver import (
            persist_binding_rules_artifact,
        )

        registry = self._registry_providers.binding_profiles
        profile = registry.get(binding_profile_id)
        if profile is None:
            logger.warning("Binding profile '%s' not found", binding_profile_id)
            return None

        store = self._artifact_store
        ref = persist_binding_rules_artifact(
            store,
            profile,
            data_snapshot_ref=data_snapshot_ref,
        )
        return str(ref.artifact_id.hex)

    # ---- Connectors listing -----------------------------------------------

    def list_connectors(self, *, request_id: str | None = None) -> ConnectorsListResponse:
        """List discovered Fabric connectors and available source profiles per family."""
        registry = self._registry_providers.connectors
        profile_reg = self._registry_providers.source_profiles
        infos: list[ConnectorInfo] = []

        for entry in registry.query_entries():
            meta = entry.metadata
            family_profiles = profile_reg.list_by_family(meta.namespace)
            infos.append(
                ConnectorInfo(
                    connector_id=meta.fully_qualified_id,
                    namespace=meta.namespace,
                    version=meta.version,
                    known_datasets=sorted(entry.known_datasets),
                    loaded=entry.loaded,
                    last_health_check=entry.last_health_check,
                    available_profiles=[p.profile_id for p in family_profiles],
                )
            )

        return ConnectorsListResponse(
            meta=_build_api_meta(request_id),
            connectors=infos,
        )

    # ---- Source profiles --------------------------------------------------

    def list_source_profiles(self, *, request_id: str | None = None) -> SourceProfilesListResponse:
        """List source profiles and mark whether each connector family is currently available."""
        profile_reg = self._registry_providers.source_profiles
        connector_reg = self._registry_providers.connectors

        # Determine which connector families are registered
        registered_families: set[str] = set()
        for entry in connector_reg.query_entries():
            registered_families.add(entry.metadata.namespace)

        profiles = profile_reg.list_all()
        infos = [
            SourceProfileInfo(
                profile_id=p.profile_id,
                display_name=p.display_name,
                description=p.description,
                connector_family=p.connector_family,
                base_url=p.base_url,
                auth_policy=p.auth_policy,
                tags=p.tags,
                source_organization=p.source_organization,
                estimated_datasets=p.estimated_datasets,
                connector_available=(p.connector_family in registered_families),
            )
            for p in profiles
        ]

        return SourceProfilesListResponse(
            meta=_build_api_meta(request_id),
            profiles=infos,
        )

    # ---- LLM model profiles -----------------------------------------------

    def list_model_profiles(self, *, request_id: str | None = None) -> ModelProfilesListResponse:
        """List registered LLM model profiles and pricing/capability metadata."""
        profile_reg = self._registry_providers.model_profiles
        profiles = profile_reg.list_all()
        infos = [
            ModelProfileInfo(
                profile_id=p.profile_id,
                display_name=p.display_name,
                description=p.description,
                provider=p.provider,
                model_id=p.model_id,
                base_url=p.base_url,
                tags=p.tags,
                capabilities=p.capabilities,
                input_cost_per_mtoken_usd=p.input_cost_per_mtoken_usd,
                output_cost_per_mtoken_usd=p.output_cost_per_mtoken_usd,
                enabled=p.enabled,
            )
            for p in profiles
        ]
        return ModelProfilesListResponse(
            meta=_build_api_meta(request_id),
            profiles=infos,
        )

    # ---- Binding profiles -------------------------------------------------

    def list_binding_profiles(
        self, *, request_id: str | None = None
    ) -> BindingProfilesListResponse:
        """List input-binding profiles exposed to control-plane ingestion requests."""
        registry = self._registry_providers.binding_profiles
        profiles = registry.list_all()
        infos = [
            BindingProfileInfo(
                profile_id=p.profile_id,
                display_name=p.display_name,
                description=p.description,
                schema_family=p.schema_family,
                strategy=p.strategy,
                rule_count=len(p.rules),
                expected_columns=p.expected_columns,
                tags=p.tags,
            )
            for p in profiles
        ]
        return BindingProfilesListResponse(
            meta=_build_api_meta(request_id),
            profiles=infos,
        )

    # ---- Cache status -----------------------------------------------------

    def get_cache_status(self, *, request_id: str | None = None) -> CacheStatusResponse:
        """Return a cache status placeholder until ConnectorCacheStore-backed stats are wired."""
        # CacheStore uses SQLite; for now return a basic response
        # Production version should query ConnectorCacheStore
        return CacheStatusResponse(
            meta=_build_api_meta(request_id),
            total_entries=0,
            total_size_bytes=0,
            entries=[],
        )


__all__ = ["ControlPlaneService"]
