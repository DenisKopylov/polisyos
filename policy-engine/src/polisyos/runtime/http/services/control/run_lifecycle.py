"""Control Plane service — bridges HTTP layer to scientist/fabric."""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.common.logger import get_logger
from polisyos.core import artifacts, run
from polisyos.core.artifacts import (
    artifact_ref_for_manifest,
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
    ProducerInfo,
    SchemaInfo,
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
from polisyos.core.observability import get_metrics, get_tracer
from polisyos.core.security import AccessScope, clear_tenant_context
from polisyos.runtime.http.errors import conflict, forbidden, unprocessable_entity
from polisyos.runtime.http.execution_policy import (
    ExecutionProfileError,
    PolicyFlagForbiddenError,
    ResolvedExecutionPolicy,
    RuntimeExecutionPolicyResolver,
    RuntimePrincipal,
)
from polisyos.runtime.http.resilience import (
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
    _make_artifact_ref,
    _resolve_curated_dir,
    write_runtime_authority_artifact,
)
from polisyos.runtime.http.services.control.capabilities import CapabilityManifestMixin
from polisyos.runtime.http.services.control.evaluation_safety import (
    EvaluationSafetyAdmissionVerifier,
    EvaluationSafetyDecisionEvidence,
    EvaluationSafetyPersistenceService,
    EvaluationSafetyPromotionSourceContext,
    EvaluationSafetyPromotionSourceSlot,
    EvaluationSafetyReplayMaterial,
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
    EvaluationExecutionContext,
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
    PublishedSignatureCustodyWatcher,
    resolve_governance_monitor_event,
)
from polisyos.scientist.orchestration.engine import BudgetMiddleware
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
    AcquisitionActionHeadRecord,
    ControlJobExecutionAdmission,
    ControlJobExecutionAdmissionError,
    ControlJobExecutionScope,
    ControlJobLeaseLostError,
    ControlJobRecord,
    ControlPlaneStore,
    ControlPreAdmissionIdempotencyConflictError,
    HumanDecisionRecoveryFence,
    HumanDecisionReservationRecord,
    HumanDecisionReservationResult,
    HumanDecisionWriteFence,
)
from ..control_worker import ControlWorker

logger = get_logger(__name__)


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
) -> Callable[[BudgetState], None]:
    """Recompute run spend from the exact committed producer-event set before N6 spend."""
    from polisyos.runtime.quality.generation_cycle import GenerationCycleError
    from polisyos.scientist import BudgetState as CanonicalBudgetState
    from polisyos.scientist.orchestration.engine import (
        BudgetLedgerProducerRecord,
        BudgetLimit,
    )
    from polisyos.scientist.orchestration.engine import (
        BudgetLedgerProducerRunBinding as CanonicalProducerRunBinding,
    )

    if type(settlement_store) is not BudgetMiddleware:
        raise TypeError("control_nl_budget_settlement_store_invalid")
    if type(producer_run_binding) is not CanonicalProducerRunBinding:
        raise TypeError("control_nl_budget_run_binding_invalid")
    if type(budget_state) is not CanonicalBudgetState:
        raise TypeError("control_nl_budget_state_invalid")

    last_reconciled_total = Decimal(0)

    def reconcile(current_state: BudgetState) -> None:
        nonlocal last_reconciled_total
        if current_state is not budget_state or type(current_state) is not CanonicalBudgetState:
            raise GenerationCycleError("control_nl_budget_state_binding_mismatch")
        if type(current_state.limits) is not dict:
            raise GenerationCycleError("control_nl_budget_limits_not_established")
        run_limit = current_state.limits.get("run")
        if type(run_limit) is not BudgetLimit or type(run_limit.max_usd) is not Decimal:
            raise GenerationCycleError("control_nl_budget_run_limit_not_established")
        if not run_limit.max_usd.is_finite():
            raise GenerationCycleError("control_nl_budget_run_limit_invalid")
        # A non-positive cap cannot admit the configured positive N6 stage
        # cost. Its terminal does not depend on treating missing spend as zero.
        if run_limit.max_usd <= Decimal(0):
            return
        try:
            records = settlement_store.list_producer_events_for_run_safe(producer_run_binding)
        except Exception as exc:
            raise GenerationCycleError("control_nl_budget_producer_events_unavailable") from exc
        if type(records) is not tuple or not records:
            raise GenerationCycleError("control_nl_budget_producer_events_not_established")

        total = Decimal(0)
        event_ids: set[str] = set()
        for record in records:
            if type(record) is not BudgetLedgerProducerRecord:
                raise GenerationCycleError("control_nl_budget_producer_event_untyped")
            if record.run_binding != producer_run_binding or (
                record.key != f"nl-run:{producer_run_binding.run_id}"
            ):
                raise GenerationCycleError("control_nl_budget_producer_event_binding_mismatch")
            if record.event_id in event_ids:
                raise GenerationCycleError("control_nl_budget_producer_event_duplicate")
            event_ids.add(record.event_id)
            if record.status != "committed":
                raise GenerationCycleError("control_nl_budget_producer_event_not_settled")
            amount = record.amount
            if type(amount) is not Decimal or not amount.is_finite() or amount < Decimal(0):
                raise GenerationCycleError("control_nl_budget_producer_amount_not_established")
            if record.cost_origin not in {"reported", "estimated", "reuse"}:
                raise GenerationCycleError("control_nl_budget_producer_cost_origin_not_established")
            if record.cost_origin == "reuse":
                if amount != Decimal(0) or not isinstance(record.origin_event_id, str):
                    raise GenerationCycleError("control_nl_budget_producer_reuse_basis_invalid")
                try:
                    origin = settlement_store.resolve_producer_event_safe(record.origin_event_id)
                except Exception as exc:
                    raise GenerationCycleError(
                        "control_nl_budget_producer_reuse_origin_unavailable"
                    ) from exc
                if (
                    type(origin) is not BudgetLedgerProducerRecord
                    or origin.status != "committed"
                    or type(origin.amount) is not Decimal
                    or not origin.amount.is_finite()
                    or origin.amount < Decimal(0)
                    or origin.cost_origin not in {"reported", "estimated"}
                    or origin.origin_event_id is not None
                    or origin.run_binding != producer_run_binding
                    or origin.key != record.key
                    or origin.model != record.model
                    or origin.provider != record.provider
                    or origin.request_digest != record.request_digest
                    or not isinstance(origin.payload_digest, str)
                    or len(origin.payload_digest) != 64
                ):
                    raise GenerationCycleError(
                        "control_nl_budget_producer_reuse_origin_not_established"
                    )
            total += amount
            if not total.is_finite():
                raise GenerationCycleError("control_nl_budget_producer_total_invalid")

        if type(current_state.spent) is not dict:
            raise GenerationCycleError("control_nl_budget_state_spend_not_established")
        current_spend = current_state.spent.get("run", Decimal(0))
        if (
            type(current_spend) is not Decimal
            or not current_spend.is_finite()
            or current_spend < Decimal(0)
        ):
            raise GenerationCycleError("control_nl_budget_state_spend_not_established")
        non_producer_spend = current_spend - last_reconciled_total
        if not non_producer_spend.is_finite() or non_producer_spend < Decimal(0):
            raise GenerationCycleError("control_nl_budget_state_spend_basis_invalid")
        current_state.spent["run"] = non_producer_spend + total
        last_reconciled_total = total

    return reconcile


# These request keys can assert owner scope; the worker supplies them from its
# replay-validated actor/job binding or omits them when that binding is unknown.


_SCIENTIST_RUNTIME_ONLY_STATE_KEYS = frozenset({"job_id", "tenant_id", "cell_id"})
_EXECUTION_INTENT_BINDING_SCHEMA = "polisyos.runtime.control_execution_intent.v2"
_NL_AUTHORIZATION_RECEIPT_KEY = "nl_authorization_receipt"
_NL_REQUEST_SNAPSHOT_KEY = "nl_request_snapshot"
_NL_REQUEST_SNAPSHOT_DIGEST_PROFILE = (
    "polisyos.runtime.authorization.nl_request_snapshot.canonical_json.v1"
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


class _ControlEvaluationSafetyCurrentStateResolver:
    """Immediate exact-context replay cache, never an authority producer."""

    def __init__(self) -> None:
        self._material_by_context: dict[
            tuple[str, str, str | None], EvaluationSafetyReplayMaterial
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
        self._material_by_context[self._key(context)] = material

    def resolve(self, context: EvaluationExecutionContext) -> EvaluationSafetyReplayMaterial | None:
        material = self._material_by_context.get(self._key(context))
        if material is None:
            return None
        expected_head = (
            material.revision_nodes[-1].revision_ref if material.revision_nodes else None
        )
        if expected_head != context.eval_safety_revision_head_ref:
            return None
        return material


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
    from typing import Literal, Protocol

    from polisyos.core import contracts as core_contracts
    from polisyos.core.artifacts.protocol import (
        ArtifactStore,
        AsyncArtifactStore,
        RootedArtifactStore,
    )
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.fabric.retrieval import RetrievalProviders, RetrievalService
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
    from polisyos.scientist.orchestration.engine import BudgetLedgerProducerRunBinding

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


def _require_action_selection_phase_receipt(
    receipt: AcquisitionRoutePhaseReceipt | AcquisitionRouteLoopReceipt,
) -> AcquisitionRoutePhaseReceipt:
    """Refuse a durable replay unless it resolved to the expected phase type."""
    if not isinstance(receipt, AcquisitionRoutePhaseReceipt):
        raise ValueError("acquisition_action_selection_replay_conflict")
    return receipt


class AcquisitionRouteLoopAuthoritySink:
    """Persist and advance verified acquisition route phase heads."""

    __slots__ = ("_artifact_store", "_control_store", "_event_log")

    def __init__(
        self,
        *,
        artifact_store: object,
        event_log: RuntimeDiagnosticEventLog,
        control_store: ControlPlaneStore,
    ) -> None:
        for capability in ("has", "get_bytes", "get_manifest", "put_json"):
            if not callable(getattr(artifact_store, capability, None)):
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
            self._verified_current_action_outcome_ref(
                executing.receipt,
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
        payload = self._artifact_store.get_bytes(receipt_ref)
        if "sha256:" + hashlib.sha256(payload).hexdigest() != receipt_ref:
            raise ValueError("acquisition_action_head_receipt_hash_mismatch")
        manifest = read_core_manifest_profile(self._artifact_store, receipt_ref)[0]
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
            manifest = read_core_manifest_profile(self._artifact_store, ref)[0]
            expected = kinds.get(manifest.kind)
            if expected is None:
                continue
            receipt_type, schema_name = expected
            payload = self._artifact_store.get_bytes(ref)
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
        return VerifiedAcquisitionActionOutcome(
            head=head,
            latest_receipt=latest.receipt,
            executing_phase_ref=None if executing is None else executing.receipt_ref,
            executing_phase=None if executing is None else executing.receipt,
            selection_phase_ref=None if selection is None else selection.receipt_ref,
            selection_phase=None if selection is None else selection.receipt,
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
        authority_fields: Mapping[str, object],
    ) -> AuthorityArtifactWriteResult:
        """Persist through the existing CAS plus durable diagnostic event chain."""

        return write_runtime_authority_artifact(
            self._artifact_store,
            self._event_log,
            payload,
            options,
            **dict(authority_fields),
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
        evaluation_safety_promotion_source_slot: EvaluationSafetyPromotionSourceSlot | None = None,
        published_signature_population_provider: PublicSignaturePopulationProvider | None = None,
        normative_authority_trust: NormativeAuthorityTrust | None = None,
        llm_producer_settlement_store: BudgetMiddleware | None = None,
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
        signature_verifier = None
        if artifact_store is None:
            store_config = ArtifactStoreConfig.from_env().model_copy(update={"root": str(cas_root)})
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
        self._evaluation_safety_state_resolver = _ControlEvaluationSafetyCurrentStateResolver()
        self._evaluation_safety_authority_resolver = _ControlEvaluationSafetyAuthorityResolver()
        self._evaluation_safety_appointment_resolver = _ControlEvaluationSafetyAppointmentResolver()
        self._evaluation_safety_verifier_registry = _ControlEvaluationSafetyVerifierRegistry()
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
        if self._policy_resolver.worker_backend == "embedded":
            self._worker = ControlWorker(
                store=self._control_store,
                handler=self._process_control_job,
                maintenance_callback=self.run_published_signature_custody_maintenance,
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
    ) -> ArtifactRef:
        """Persist JSON and retain the exact store-selected manifest view."""
        artifact_ref = self._artifact_store.put_json(
            payload,
            ArtifactWriteOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(name=schema_name, version=schema_version),
                tenant_context=tenant_context,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
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
        return self._current_normative_job_record(record).to_response(request_id=request_id)

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
        digest = hashlib.sha256(idempotency_key.encode("ascii")).hexdigest()
        record = self._control_store.get_pre_admission_attempt_by_idempotency_key(
            tenant_id=principal.tenant_id,
            cell_id=principal.cell_id,
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
        owner_binding = ControlPreAdmissionOwnerBinding(
            purpose=owner.purpose,
            scope_kind=owner.scope_kind,
            scope_id=owner.scope_id,
            tenant_id=owner.tenant_id,
            cell_id=owner.cell_id,
            actor_subject_sha256=owner.actor_subject_sha256,
            run_id=owner.run_id,
            intent_id=owner.intent_id,
            body_sha256=owner.body_sha256,
            request_content_sha256=intent_content_sha256,
            effective_execution_profile=record.effective_execution_profile,
        )
        return ControlPreAdmissionAttemptResponse(
            meta=_build_api_meta(request_id),
            owner_binding=owner_binding,
            attempt_id=record.attempt_id,
            intent_sha256=record.intent_sha256,
            status=record.status,
            run_id=record.run_id,
            job_id=record.job_id,
            effective_execution_profile=record.effective_execution_profile,
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
            return core_run_id, core_run_context

        try:
            payload_ref = self._require_control_job_payload_ref(job)
            payload = self._load_payload_ref(
                payload_ref,
                kind=f"runtime.control_job_payload.{job.kind}",
            )
            payload = self._payload_for_execution_scope(
                payload,
                job=job,
                execution_scope=execution_scope,
            )
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

        # Build inputs dict
        inputs: dict[str, Any] = {}

        # Data source (required)
        ds_key, ds_ref, data_view_request_intent = _resolve_workflow_data_source(
            request.data_source
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
            effective_execution_profile=policy.effective_profile,
            message=f"Workflow run {run_id} accepted and queued for durable execution.",
        )

    def publish_decision_validity_event(
        self,
        request: DecisionValidityEventRequest,
        *,
        request_id: str | None = None,
    ) -> DecisionValidityEventResponse:
        """Record a decision-dependency event and enqueue one deduplicated outbox notification."""
        if request.monitor_event_ref is not None:
            return self._publish_monitor_decision_validity_event(
                request.monitor_event_ref,
                request_id=request_id,
            )
        dependency_keys = [item.strip() for item in request.dependency_keys if str(item).strip()]
        dedupe_key = request.dedupe_key or self._derive_decision_validity_dedupe_key(
            request,
            dependency_keys=dependency_keys,
        )
        event = DecisionDependencyEvent(
            event_id=f"decision_evt_{uuid.uuid4().hex[:16]}",
            dedupe_key=dedupe_key,
            occurred_at=request.occurred_at or datetime.now(UTC).replace(microsecond=0),
            trigger_type=request.trigger_type,
            status=request.status,
            reason=request.reason,
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

    def _publish_monitor_decision_validity_event(
        self,
        monitor_event_ref: ArtifactRef,
        *,
        request_id: str | None,
        published_signature_custody: bool = False,
    ) -> DecisionValidityEventResponse | PublishedSignatureCustodyLifecyclePublication:
        """Content-bind the monitor arm before deriving any lifecycle consequence."""

        try:
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

        source_class = (
            "published_signature_custody"
            if published_signature_custody
            else perturbation.source_class
        )
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
            packet_manifest = self._artifact_store.get_manifest(packet_id)
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

    def _run_legacy_scientist_workflow(self, state_payload: dict[str, Any]) -> None:
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
        run_experiment(
            execution_payload,
            store=self._artifact_store,
            epoch_certificate_issuance_owner=self._epoch_certificate_issuance_owner,
            eval_safety_execution_context=execution_context,
            eval_safety_verifier=(
                self._evaluation_safety_admission_verifier
                if execution_context is not None
                else None
            ),
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
                raise unprocessable_entity(
                    "Selected data snapshot is not an exact typed profile in this run scope.",
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
                snapshot_ref = request.data_source.data_snapshot_ref
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
                raise unprocessable_entity(
                    "The selected predictive input set does not join to this run's exact source.",
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
                        effective_execution_profile=attempt_record.effective_execution_profile,
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
                        effective_execution_profile=attempt_record.effective_execution_profile,
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
                        effective_execution_profile=policy.effective_profile,
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
                            effective_execution_profile=policy.effective_profile,
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
                        effective_execution_profile=policy.effective_profile,
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
                    except (TypeError, ValueError):
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
                        attempt_id=pre_admission_attempt_id,
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
                effective_execution_profile=policy.effective_profile,
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
            effective_execution_profile=policy.effective_profile,
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
        from polisyos.fabric import (
            IngestionStoreBindingError,
            TenantSidecarScope,
        )
        from polisyos.fabric.ingestion import (
            ConnectorManifestSpec,
            DatasetFetchSpec,
            IngestionDependencies,
        )
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

            # Post-ingestion: produce input bindings if requested
            input_bindings_ref: str | None = None
            if request.produce_input_bindings and request.binding_profile_id:
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
                status="completed",
                evidence_bundle_ref=(
                    str(result.evidence_bundle_ref.artifact_id.hex)
                    if result.evidence_bundle_ref
                    else None
                ),
                data_snapshot_ref=(
                    str(result.data_snapshot_ref.artifact_id.hex)
                    if result.data_snapshot_ref
                    else None
                ),
                datasets_fetched=result.datasets_fetched,
                message=f"Successfully ingested {result.datasets_fetched} dataset(s).",
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
