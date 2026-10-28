"""Assemble redacted debug, governance, workflow, and evidence views for runs.

The service merges data from run manifests, CAS artifacts, trace timelines, and
decision-validity state. Sensitive keys are sanitized before DTOs cross the HTTP
boundary.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast

from pydantic import ValidationError

from polisyos.common.canonical_profile import (
    CanonicalProfileRefusalError,
    require_declared_profile,
)
from polisyos.common.logger import get_logger
from polisyos.core.artifacts import (
    artifact_manifest_profile_sha256,
    read_core_json_artifact,
    read_core_manifest_profile,
    resolve_manifest_by_profile,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.artifacts.protocol import RawManifestBytesReader
from polisyos.core.contracts import ControlJobResponse, SimulationResult
from polisyos.core.contracts.runtime import (
    AgentPipelineAttempt,
    AgentPipelineCostEvent,
    AgentPipelineStep,
    AgentPipelineView,
    EvaluatorReportView,
    EvaluatorScoresView,
    GovernanceDebugView,
    IterationLifecycleView,
    NodeDebugView,
    NodeStatus,
    PreflightDiagnosticView,
    PreflightReportView,
    ReproducibilityView,
    RetrievalPhaseTelemetry,
    RetrievalTelemetryView,
    RunErrorView,
    RunEvidenceContextView,
    RunEvidenceNeedView,
    RunEvidencePlanView,
    RunEvidencePromotionView,
    RunNodeRecord,
    RunWorkflowEdgeView,
    RunWorkflowNodeView,
    RunWorkflowSummary,
    RunWorkflowView,
    SimulationResultCandidateView,
)
from polisyos.core.trace import TraceRecord
from polisyos.ir import CanonViolation
from polisyos.ir import get_json_artifact as get_ir_json_artifact
from polisyos.ir.analytics import (
    DataViewRequest as AnalyticsDataViewRequest,
)
from polisyos.ir.model_layer.queries import DataViewRequest as QueryDataViewRequest
from polisyos.scientist.orchestration.engine import (
    BudgetLedgerProducerRunBinding,
    BudgetMiddleware,
)
from polisyos.scientist.validation.decision_validity import DecisionValidityService

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.core.contracts.execution_plan import (
        EvaluatorVerdict,
        IterationLifecycleState,
        StopReason,
    )
    from polisyos.scientist.orchestration.engine import BudgetLedgerProducerRecord

    from .run_index import IndexedRunRecord
    from .timeline import TimelineService


def _producer_record_cost_event(record: BudgetLedgerProducerRecord) -> AgentPipelineCostEvent:
    """Project one canonical producer ledger row without inferring absent money."""
    return AgentPipelineCostEvent(
        event_id=record.event_id,
        origin_event_id=record.origin_event_id,
        cost_origin=record.cost_origin,
        amount=record.amount,
        settlement_status=record.status,
        durability="ledger",
        receipts=(record.event_id,) if record.status == "committed" else (),
        payload_digest=record.payload_digest,
        model=record.model,
        provider=record.provider,
        control_job_attempt=record.control_job_attempt,
        pre_admission_attempt_id=record.pre_admission_attempt_id,
    )


def _reconcile_producer_cost_event(
    event: AgentPipelineCostEvent,
    canonical_event: AgentPipelineCostEvent | None,
    *,
    owner_attempt: int | None,
    owner_not_established: bool = False,
) -> tuple[AgentPipelineCostEvent | None, bool]:
    """Join an observed event to the exact durable payload and owning attempt."""
    if event.durability != "ledger" and canonical_event is None:
        return event, False
    if canonical_event is None:
        if event.durability == "ledger" and owner_not_established:
            return None, False
        raise ValueError("agent_pipeline_cost_event_ledger_reconciliation_failed")
    if (
        event.control_job_attempt is not None
        and event.control_job_attempt != canonical_event.control_job_attempt
    ) or (
        event.pre_admission_attempt_id is not None
        and event.pre_admission_attempt_id != canonical_event.pre_admission_attempt_id
    ):
        raise ValueError("agent_pipeline_cost_event_attempt_attribution_conflict")
    normalized_event = event.model_copy(
        update={
            "control_job_attempt": canonical_event.control_job_attempt,
            "pre_admission_attempt_id": canonical_event.pre_admission_attempt_id,
        }
    )
    if normalized_event != canonical_event:
        raise ValueError("agent_pipeline_cost_event_ledger_reconciliation_failed")
    if canonical_event.control_job_attempt is None:
        return None, False
    if owner_attempt is None or canonical_event.control_job_attempt != owner_attempt:
        return None, True
    return canonical_event, False


class _ReadOnlyControlJobStore(Protocol):
    """Read-only owner inputs needed to bind one indexed run to its ControlJob."""

    def get_job(self, job_id: str) -> Any | None: ...

    def get_job_created_event_payload(self, job_id: str) -> dict[str, Any]: ...

    def get_job_created_outbox_event(self, job_id: str) -> Any | None: ...

    def get_job_terminal_source_event_record(self, job_id: str) -> Any: ...

    def get_job_completed_outbox_event(self, job_id: str) -> Any | None: ...


class _ScorecardOwnerSourceReaderUnavailableError(RuntimeError):
    """Signal a missing persisted reader needed for terminal owner reconciliation."""

    def __init__(self, reader_name: str) -> None:
        self.reader_name = reader_name
        super().__init__(f"control_job_source_reader_unavailable:{reader_name}")


@dataclass(frozen=True)
class _ScorecardControlJobOwnerSource:
    """Carry the exact owner fields reconciled from one terminal ControlJob source."""

    job_id: str
    run_id: str
    tenant_id: str
    cell_id: str
    requested_execution_profile: str | None
    effective_execution_profile: str
    attempt: int
    lease_owner: str
    completion_event_id: int
    completion_event_payload_sha256: str
    completion_outbox_event_id: str
    core_run_id: str

    def as_owner_binding(self) -> dict[str, str | int | None]:
        """Return the canonical transport field set after source resolution."""
        return {
            "job_id": self.job_id,
            "run_id": self.run_id,
            "tenant_id": self.tenant_id,
            "cell_id": self.cell_id,
            "requested_execution_profile": self.requested_execution_profile,
            "effective_execution_profile": self.effective_execution_profile,
            "attempt": self.attempt,
            "lease_owner": self.lease_owner,
        }


_GOVERNANCE_REPORT_KEY = "governance_report_ref"
_NORMATIVE_ARBITRATION_RESULT_KEY = "normative_arbitration_result_ref"
_REFLEXION_TERMINAL_KIND = "scientist.reflexion_terminal"
_WORKFLOW_SPEC_KIND = "scientist.workflow_spec"
_DEFAULT_SENSITIVE_KEYS = (
    "authorization",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "cookie",
)
_AGENT_ALIASES: dict[str, str] = {
    "pi": "pi_agent",
    "pi_agent": "pi_agent",
    "pi_decompose": "pi_agent",
    "problem_frame": "pi_agent",
    "data_need_extractor": "data_need_extractor",
    "source_resolver": "source_resolver",
    "executor": "executor",
    "promotion_lane": "promotion_lane",
    "drafter": "drafter",
    "draft": "drafter",
    "formalize": "formalizer",
    "formalizer": "formalizer",
    "critic": "critic",
    "critic_review": "critic",
    "reflexion": "reflexion",
}
_MATERIALIZATION_REF_KINDS = {
    "data_snapshot_ref": "fabric.data_snapshot",
    "input_bindings_ref": "foundry.input_bindings",
    "registry_bundle_ref": "core.registry_bundle",
    "input_binding_report_ref": "foundry.input_binding_report",
    "evidence_bundle_ref": "fabric.evidence_bundle",
    "fabric_retrieval_trace_ref": "fabric.retrieval_trace",
}


logger = get_logger(__name__)

AgentStepStatus = Literal["ok", "warn", "fail", "info"]

_SIMULATION_RESULT_KIND = "foundry.simulation_result"
_SIMULATION_RESULT_MEDIA_TYPE = "application/json"
_SIMULATION_RESULT_SCHEMA_NAME = "polisyos.core.SimulationResult"
_SIMULATION_RESULT_SCHEMA_VERSIONS = frozenset({"1.1", "1.2", "1.3", "1.4"})
_SIMULATION_RESULT_STATE_KEY = "simulation_result_ref"
_EXPERIMENT_STATE_SCHEMA_NAME = "polisyos.scientist.orchestration.engine.ExperimentState"
_EXPERIMENT_STATE_SCHEMA_VERSIONS = frozenset({"1.3"})
_WORKFLOW_REPORT_SCHEMA_NAME = "polisyos.scientist.orchestration.engine.WorkflowReport"
_WORKFLOW_REPORT_SCHEMA_VERSIONS = frozenset({"1.0"})


class SimulationResultProjectionError(RuntimeError):
    """Fail-closed error raised when a candidate result cannot be reconciled."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class DebugService:
    """Expose read-only runtime debug projections for one indexed run."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        timeline_service: TimelineService,
        producer_settlement_store: BudgetMiddleware | None = None,
        sensitive_keys: tuple[str, ...] = _DEFAULT_SENSITIVE_KEYS,
    ) -> None:
        self._store = store
        self._timeline_service = timeline_service
        self._decision_validity_service: DecisionValidityService | None = None
        self._source_use_control_service: Any | None = None
        self._sensitive_keys = tuple(key.lower() for key in sensitive_keys)
        self._producer_settlement_store: BudgetMiddleware | None = None
        self._producer_control_job_store: _ReadOnlyControlJobStore | None = None
        if producer_settlement_store is not None:
            self.bind_producer_settlement_store(producer_settlement_store)

    @property
    def bound_decision_validity_owner(self) -> DecisionValidityService | None:
        """Return the already-bound owner without manufacturing one."""
        return self._decision_validity_service

    def bind_decision_validity_owner(self, owner: DecisionValidityService) -> None:
        """Bind the installed Runtime's existing validity owner, once."""
        if not isinstance(owner, DecisionValidityService) or owner._store is not self._store:
            raise ValueError("debug_decision_validity_owner_mismatch")
        if (
            self._decision_validity_service is not None
            and self._decision_validity_service is not owner
        ):
            raise ValueError("debug_decision_validity_owner_already_bound")
        self._decision_validity_service = owner

    def bind_source_use_control_service(self, control: Any) -> None:
        """Bind the Runtime's actual completed-job owner for fresh source reads."""
        from polisyos.runtime.http.services.control import ControlPlaneService

        if (
            type(control) is not ControlPlaneService
            or control._artifact_store is not self._store
            or control._decision_validity_service is not self._decision_validity_service
            or (
                self._source_use_control_service is not None
                and self._source_use_control_service is not control
            )
        ):
            raise ValueError("debug_source_use_control_owner_mismatch")
        self._source_use_control_service = control

    def bind_producer_settlement_store(self, store: BudgetMiddleware) -> None:
        """Bind the durable ledger used to reconcile one run owner's events."""
        if type(store) is not BudgetMiddleware:
            raise TypeError("producer_settlement_store_must_be_budget_middleware")
        try:
            owner_identity = store.settlement_owner_identity
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValueError("producer_settlement_store_must_be_durable") from exc
        current = self._producer_settlement_store
        if current is not None:
            try:
                if current.settlement_owner_identity != owner_identity:
                    raise ValueError("producer_settlement_store_owner_mismatch")
            except (OSError, RuntimeError, ValueError) as exc:
                if isinstance(exc, ValueError) and str(exc) == (
                    "producer_settlement_store_owner_mismatch"
                ):
                    raise
                raise ValueError("producer_settlement_store_must_be_durable") from exc
        self._producer_settlement_store = store

    def bind_producer_control_job_store(self, store: _ReadOnlyControlJobStore) -> None:
        """Bind the durable ControlJob owner used to resolve indexed run backlinks."""
        required = (
            "get_job",
            "get_job_created_event_payload",
            "get_job_created_outbox_event",
        )
        if any(not callable(getattr(store, name, None)) for name in required):
            raise TypeError("producer_control_job_store_contract_invalid")
        current = self._producer_control_job_store
        if current is not None and current is not store:
            raise ValueError("producer_control_job_store_owner_mismatch")
        self._producer_control_job_store = store

    def list_run_nodes(self, run: IndexedRunRecord) -> list[RunNodeRecord]:
        """List workflow nodes by merging workflow-report rows with trace events."""
        return self.list_run_nodes_with_notes(run)[0]

    def list_run_nodes_with_notes(
        self, run: IndexedRunRecord
    ) -> tuple[list[RunNodeRecord], list[str]]:
        """Return workflow nodes and an explicit limitation for absence-only fallback."""
        notes: list[str] = []
        timeline_events = self._timeline_service.build_for_run(run).timeline.events
        workflow_nodes = self._load_workflow_nodes(
            run.workflow_report_ref,
            on_missing=lambda: notes.append("workflow_report_missing_or_unavailable"),
        )
        if notes:
            return _nodes_from_timeline(timeline_events), notes
        if not workflow_nodes:
            return [], notes
        return _merge_workflow_nodes_with_timeline(workflow_nodes, timeline_events), notes

    def get_node_debug(self, run: IndexedRunRecord, *, alias: str) -> NodeDebugView:
        """Return per-node timeline, cache, and artifact details.

        Raises:
            KeyError: If `alias` does not match any node in the run.
        """
        nodes, notes = self.list_run_nodes_with_notes(run)
        by_alias = {node.alias: node for node in nodes}
        record = by_alias.get(alias)
        if record is None:
            raise KeyError(alias)

        node_phase = f"scientist.node.{alias}"
        timeline = self._timeline_service.build_for_run(run).timeline.events
        node_events = [event for event in timeline if event.phase == node_phase]

        cache_hits = sum(int(event.metrics.get("cache_hit", 0)) for event in node_events)
        cache_stores = sum(int(event.metrics.get("cache_store", 0)) for event in node_events)
        cache_bypasses = sum(int(event.metrics.get("cache_bypass", 0)) for event in node_events)

        input_ids = sorted({aid for event in node_events for aid in event.input_artifact_ids})
        output_ids = sorted({aid for event in node_events for aid in event.output_artifact_ids})

        enriched_record = record.model_copy(
            update={
                "input_artifact_ids": (
                    record.input_artifact_ids if record.input_artifact_ids else input_ids
                ),
                "output_artifact_ids": (
                    record.output_artifact_ids if record.output_artifact_ids else output_ids
                ),
                "input_artifact_refs": _merge_artifact_refs(
                    record.input_artifact_refs,
                    *(event.input_artifact_refs for event in node_events),
                ),
                "output_artifact_refs": _merge_artifact_refs(
                    record.output_artifact_refs,
                    *(event.output_artifact_refs for event in node_events),
                ),
            }
        )

        return NodeDebugView(
            run_id=run.run_id,
            source_kind=run.source_kind,
            alias=alias,
            record=enriched_record,
            timeline_events=node_events,
            cache_hits=cache_hits,
            cache_stores=cache_stores,
            cache_bypasses=cache_bypasses,
            notes=notes,
        )

    def get_simulation_result_candidate(
        self,
        run: IndexedRunRecord,
        *,
        alias: str,
        artifact_id: str | None = None,
    ) -> SimulationResultCandidateView:
        """Read a verified, candidate-only simulation result bound to one node.

        The route deliberately resolves the result through the persisted final
        state and the named workflow node.  It does not use the generic
        artifact inspector because this debug projection is reference-only and
        must preserve the authority-surface ``409`` behavior for generic
        artifact routes.

        Raises:
            KeyError: If ``alias`` is not present in the persisted workflow.
            SimulationResultProjectionError: If the state/node/ref, manifest,
                payload, tenant binding, or CAS integrity cannot be reconciled.
        """
        state_payload = self._load_verified_binding_json(
            run.experiment_state_ref,
            expected_kind="scientist.experiment_state",
            expected_media_type=_SIMULATION_RESULT_MEDIA_TYPE,
            expected_schema_name=_EXPERIMENT_STATE_SCHEMA_NAME,
            expected_schema_versions=_EXPERIMENT_STATE_SCHEMA_VERSIONS,
            expected_run_id=run.run_id,
            expected_tenant_id=run.details.tenant_id,
            expected_cell_id=run.details.cell_id,
        )
        report_payload = self._load_verified_binding_json(
            run.workflow_report_ref,
            expected_kind="scientist.workflow_report",
            expected_media_type=_SIMULATION_RESULT_MEDIA_TYPE,
            expected_schema_name=_WORKFLOW_REPORT_SCHEMA_NAME,
            expected_schema_versions=_WORKFLOW_REPORT_SCHEMA_VERSIONS,
            expected_run_id=run.run_id,
            expected_tenant_id=run.details.tenant_id,
            expected_cell_id=run.details.cell_id,
        )
        report_node = _unique_workflow_report_node(report_payload, alias=alias)
        if report_node is None:
            raise KeyError(alias)
        record = self._workflow_node_record(report_node)

        state_ref = _simulation_result_ref_from_state_payload(state_payload)
        requested_id = _artifact_id_from_string(artifact_id)
        if artifact_id is not None and requested_id is None:
            raise SimulationResultProjectionError(
                "simulation_result_ref_invalid",
                "The requested simulation result reference is malformed",
            )

        if state_ref is None:
            raise SimulationResultProjectionError(
                "simulation_result_ref_missing",
                "The run state has no persisted simulation result reference",
            )
        selected_id = requested_id or state_ref.artifact_id
        node_bound_refs = _artifact_refs_from_report_node(
            report_node,
            relevant_artifact_id=selected_id,
        )

        if requested_id is None:
            node_refs_with_state_id = tuple(
                ref for ref in node_bound_refs if ref.artifact_id == state_ref.artifact_id
            )
            if not node_refs_with_state_id:
                raise SimulationResultProjectionError(
                    "simulation_result_node_binding_missing",
                    "The named workflow node is not bound to the exact run simulation result ref",
                )
            _require_exact_artifact_ref_binding(state_ref, node_refs_with_state_id)
            requested_id = state_ref.artifact_id
        elif not any(ref.artifact_id == requested_id for ref in node_bound_refs):
            raise SimulationResultProjectionError(
                "simulation_result_node_binding_mismatch",
                "The requested reference is not bound to the named workflow node",
            )

        if state_ref is None or requested_id != state_ref.artifact_id:
            raise SimulationResultProjectionError(
                "simulation_result_run_binding_mismatch",
                "The requested reference is not bound to the persisted run state",
            )
        _require_exact_artifact_ref_binding(
            state_ref,
            tuple(ref for ref in node_bound_refs if ref.artifact_id == state_ref.artifact_id),
        )
        if (
            state_ref.kind != _SIMULATION_RESULT_KIND
            or state_ref.media_type != _SIMULATION_RESULT_MEDIA_TYPE
        ):
            raise SimulationResultProjectionError(
                "simulation_result_ref_manifest_mismatch",
                "The persisted run state does not describe a SimulationResult artifact",
            )

        try:
            verification = self._store.verify(state_ref)
            if not verification.ok:
                raise SimulationResultProjectionError(
                    "simulation_result_integrity_failed",
                    "The persisted simulation result failed CAS integrity verification",
                )
            manifest = read_core_manifest_profile(self._store, state_ref)[0]
            payload_bytes = self._store.get_bytes(state_ref)
        except SimulationResultProjectionError:
            raise
        except (
            FileNotFoundError,
            OSError,
            PermissionError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
        ) as exc:
            raise SimulationResultProjectionError(
                "simulation_result_unavailable",
                "The persisted simulation result is unavailable or not owned by this run",
            ) from exc

        if manifest.kind != _SIMULATION_RESULT_KIND:
            raise SimulationResultProjectionError(
                "simulation_result_kind_mismatch",
                "The bound artifact is not a Foundry SimulationResult",
            )
        if manifest.media_type != _SIMULATION_RESULT_MEDIA_TYPE:
            raise SimulationResultProjectionError(
                "simulation_result_media_type_mismatch",
                "The bound simulation result is not JSON",
            )
        schema = manifest.artifact_schema
        if (
            schema is None
            or schema.name != _SIMULATION_RESULT_SCHEMA_NAME
            or schema.version not in _SIMULATION_RESULT_SCHEMA_VERSIONS
        ):
            raise SimulationResultProjectionError(
                "simulation_result_schema_mismatch",
                "The bound artifact does not carry a supported SimulationResult schema",
            )
        tenant_context = manifest.tenant_context
        if tenant_context is None:
            raise SimulationResultProjectionError(
                "simulation_result_tenant_unscoped",
                "The bound simulation result has no persisted tenant ownership context",
            )
        if (
            tenant_context.tenant_id != run.details.tenant_id
            or tenant_context.cell_id != run.details.cell_id
        ):
            raise SimulationResultProjectionError(
                "simulation_result_tenant_binding_mismatch",
                "The simulation result belongs to a different tenant",
            )

        try:
            profiled = read_core_json_artifact(
                self._store, state_ref, raw_payload_bytes=payload_bytes
            )
            simulation_result = SimulationResult.model_validate(profiled.value)
        except (TypeError, ValueError, ValidationError, UnicodeDecodeError) as exc:
            raise SimulationResultProjectionError(
                "simulation_result_payload_invalid",
                "The bound artifact is not a valid persisted SimulationResult",
            ) from exc
        if schema.version != simulation_result.schema_version:
            raise SimulationResultProjectionError(
                "simulation_result_schema_binding_mismatch",
                "The manifest schema version is not bound to the SimulationResult payload",
            )

        from polisyos.core.contracts.runtime import ExAnteSourceUseDebugView
        from polisyos.runtime.http.services.debug_registered_sql import (
            read_registered_sql_source_use,
        )

        source_use = (
            read_registered_sql_source_use(
                store=self._store,
                control=self._source_use_control_service,
                run=run,
                simulation_ref=state_ref,
            )
            if self._source_use_control_service is not None
            else ExAnteSourceUseDebugView(
                status="unknown",
                method_replay_status="verification_missing",
                limitations=("registered_sql_runtime_owner_not_established",),
            )
        )
        return SimulationResultCandidateView(
            exante_source_use=source_use,
            run_id=run.run_id,
            node_alias=alias,
            node_id=record.node_id,
            artifact_ref=state_ref,
            simulation_result=simulation_result,
            notes=[
                "candidate_reference_only",
                "not_an_authority_envelope",
                "generic_artifact_authority_routes_remain_blocked",
                *(
                    warning
                    for warning in run.details.warnings
                    if warning
                    in {
                        "core_run_workflow_finalization_not_established",
                        "core_run_finalization_manifest_tenant_not_established",
                    }
                ),
            ],
        )

    def get_governance_debug(self, run: IndexedRunRecord) -> GovernanceDebugView:
        """Return governance verdict, issue summaries, and decision-validity state.

        When a governance report artifact is missing, the service falls back to
        the governance block embedded in the decision packet payload and marks
        that fallback in the response.
        """
        report_ref = None
        validation_trace = None
        fallback = False

        state_payload = self._load_experiment_state_payload(run.experiment_state_ref)
        if state_payload:
            validation_trace = _extract_validation_trace(state_payload)
            report_ref = _extract_report_ref(state_payload, _GOVERNANCE_REPORT_KEY)

        report_missing: list[bool] = []
        report_payload: dict[str, Any] = {}
        if report_ref is not None:
            report_payload = self._load_json_artifact(
                report_ref,
                on_missing=lambda: report_missing.append(True),
            )
            if report_missing:
                report_ref = None
        if report_ref is not None:
            verdict = _as_str(report_payload.get("verdict"))
            issues = _as_list_of_dicts(report_payload.get("issues"))
            notes = _as_list_of_strings(report_payload.get("notes"))
            links = _governance_links_from_payload(report_payload)
            report_manifest = self._load_manifest(report_ref)
            issue_summary = _summarize_issue_counts(issues)
            legal_executed = _legal_executed_from_governance(report_payload)
            packet_payload = self._load_json_artifact(run.decision_packet_ref)
            decision_validity = self._decision_validity_summary(
                run.decision_packet_ref,
                packet_payload,
            )
            return GovernanceDebugView(
                run_id=run.run_id,
                source_kind=run.source_kind,
                verdict=verdict,
                issues=issues,
                issue_summary=issue_summary,
                notes=notes,
                report_ref=report_ref,
                report_kind=report_manifest.kind if report_manifest is not None else None,
                report_schema_version=(
                    report_manifest.artifact_schema.version
                    if report_manifest is not None and report_manifest.artifact_schema is not None
                    else None
                ),
                links=links,
                legal_executed=legal_executed,
                transport_summary=_transport_summary_from_packet(packet_payload),
                validation_trace=validation_trace,
                contract_warnings=_contract_warnings_from_packet(packet_payload),
                decision_validity=decision_validity,
                normative_summary=_normative_summary_from_packet(packet_payload),
                normative_arbitration_result_ref=_artifact_ref_from_packet(
                    packet_payload,
                    _NORMATIVE_ARBITRATION_RESULT_KEY,
                ),
                fallback_from_decision_packet=False,
            )

        packet_payload = self._load_json_artifact(run.decision_packet_ref)
        decision_validity = self._decision_validity_summary(
            run.decision_packet_ref,
            packet_payload,
        )
        governance_block = packet_payload.get("governance")
        notes = ["governance_report_missing_or_unavailable"] if report_ref is None else []
        if isinstance(governance_block, dict):
            fallback = True
            verdict = _as_str(governance_block.get("verdict"))
            issues = _as_list_of_dicts(governance_block.get("issues"))
            notes.extend(_as_list_of_strings(governance_block.get("notes")))
            links = _governance_links_from_payload(governance_block)
        else:
            verdict = None
            issues = []
            links = None

        return GovernanceDebugView(
            run_id=run.run_id,
            source_kind=run.source_kind,
            verdict=verdict,
            issues=issues,
            issue_summary=_summarize_issue_counts(issues),
            notes=notes,
            report_ref=None,
            report_kind=None,
            report_schema_version=None,
            links=links,
            legal_executed=_legal_executed_from_packet(packet_payload),
            transport_summary=_transport_summary_from_packet(packet_payload),
            validation_trace=validation_trace,
            contract_warnings=_contract_warnings_from_packet(packet_payload),
            decision_validity=decision_validity,
            normative_summary=_normative_summary_from_packet(packet_payload),
            normative_arbitration_result_ref=_artifact_ref_from_packet(
                packet_payload,
                _NORMATIVE_ARBITRATION_RESULT_KEY,
            ),
            fallback_from_decision_packet=fallback,
        )

    def _decision_validity_summary(
        self,
        ref: ArtifactRef | None,
        packet_payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        if ref is None:
            return None
        owner = self._decision_validity_service
        if owner is None:
            # Standalone DebugService keeps its historical lazy local owner;
            # the installed Runtime binds its canonical owner before serving.
            owner = DecisionValidityService(self._store)
            self._decision_validity_service = owner
        return cast(
            "dict[str, Any] | None",
            owner.get_summary(
                str(ref.artifact_id),
                packet_payload=packet_payload,
            ),
        )

    def get_run_errors(self, run: IndexedRunRecord) -> list[RunErrorView]:
        """Collect sanitized manifest, workflow, and trace errors for one run."""
        return self.get_run_errors_with_notes(run)[0]

    def get_run_errors_with_notes(
        self, run: IndexedRunRecord
    ) -> tuple[list[RunErrorView], list[str]]:
        """Return run errors and limitations on any absence-only workflow fallback."""
        errors: list[RunErrorView] = []

        for item in run.manifest_errors:
            errors.append(
                RunErrorView(
                    source="manifest",
                    code=_as_str(item.get("code")) or "manifest.error",
                    message=(
                        _sanitize_string(_as_str(item.get("message")) or "Run manifest error")
                        or "Run manifest error"
                    ),
                    details=_sanitize_payload(dict(item), sensitive_keys=self._sensitive_keys),
                )
            )

        workflow_nodes, notes = self.list_run_nodes_with_notes(run)
        node_error_source = "trace" if notes else "workflow_report"
        for node in workflow_nodes:
            if node.status != "fail":
                continue
            errors.append(
                RunErrorView(
                    source=node_error_source,
                    code=node.error_code or "node.failure",
                    message=(
                        _sanitize_string(node.error_message or "Node execution failed")
                        or "Node execution failed"
                    ),
                    node_alias=node.alias,
                    details=_sanitize_payload(
                        dict(node.error_details),
                        sensitive_keys=self._sensitive_keys,
                    ),
                )
            )

        if run.trace_path is not None and run.trace_path.exists():
            for record in _iter_trace_records(run.trace_path):
                for payload in record.errors:
                    errors.append(
                        RunErrorView(
                            source="trace",
                            code=_as_str(payload.get("code")) or "trace.error",
                            message=(
                                _sanitize_string(_as_str(payload.get("msg")) or "Trace error")
                                or "Trace error"
                            ),
                            timestamp=record.ts,
                            details=_sanitize_payload(
                                dict(payload),
                                sensitive_keys=self._sensitive_keys,
                            ),
                        )
                    )

        errors.sort(key=_error_sort_key)
        return errors, notes

    def get_run_agents(self, run: IndexedRunRecord) -> AgentPipelineView:
        """Build the agent-pipeline view from decision packet, state, and trace data.

        The method prefers `decision_packet.audit_trail`, then timeline events,
        then reflexion-terminal payloads, and appends iteration/preflight/
        evaluator/reproducibility metadata when those artifacts are available.
        """
        notes: list[str] = []
        source: str | None = None

        state_payload = self._load_experiment_state_payload(run.experiment_state_ref)
        decision_packet_payload = self._load_json_artifact(run.decision_packet_ref)
        audit_trail_rows = _as_list_of_dicts(decision_packet_payload.get("audit_trail"))
        steps = _agent_steps_from_nl_preflight(
            state_payload,
            sensitive_keys=self._sensitive_keys,
        )
        compiled_steps, compiled_preflight_note = self._agent_steps_from_compiled_cycle(
            run,
            sensitive_keys=self._sensitive_keys,
        )
        if compiled_steps:
            steps.extend(compiled_steps)
            source = "compiled_recursive_generation_cycle"
        if compiled_preflight_note is not None:
            notes.append(compiled_preflight_note)
        proposal_steps, proposal_note = self._agent_steps_from_n4_candidate_proposal(
            run,
            sensitive_keys=self._sensitive_keys,
        )
        if proposal_steps:
            steps.extend(proposal_steps)
            source = source or "n4_candidate_proposal"
        if proposal_note is not None:
            notes.append(proposal_note)
        if steps:
            source = source or "experiment_state.params"
        if audit_trail_rows:
            steps.extend(
                _agent_steps_from_audit_trail(
                    audit_trail_rows,
                    sensitive_keys=self._sensitive_keys,
                )
            )
            source = "decision_packet.audit_trail"

        if not steps:
            timeline_rows = self._timeline_service.build_for_run(run).timeline.events
            timeline_steps = _agent_steps_from_timeline(
                timeline_rows,
                sensitive_keys=self._sensitive_keys,
            )
            if timeline_steps:
                steps.extend(timeline_steps)
                source = "trace.timeline"

        reflexion_ref = self._find_first_ref_by_kind(run, _REFLEXION_TERMINAL_KIND)
        reflexion_payload = self._load_json_artifact(reflexion_ref)
        reflexion_step = _agent_step_from_reflexion_payload(
            reflexion_payload,
            sensitive_keys=self._sensitive_keys,
        )
        if reflexion_step is not None:
            if not steps or not _contains_agent_step(steps, reflexion_step):
                steps.append(reflexion_step)
            if source is None:
                source = "reflexion_terminal"

        variant_steps, variant_notes = _agent_steps_from_model_variants(
            state_payload,
            sensitive_keys=self._sensitive_keys,
        )
        notes.extend(variant_notes)
        if variant_steps:
            for step in variant_steps:
                existing_index = _agent_step_index(steps, step)
                if existing_index is None:
                    steps.append(step)
                elif step.cost_events or step.unattributed_cost_scalars:
                    existing_step = steps[existing_index]
                    events_by_id = {event.event_id: event for event in existing_step.cost_events}
                    for event in step.cost_events:
                        prior_event = events_by_id.get(event.event_id)
                        if prior_event is not None and prior_event != event:
                            raise ValueError("agent_pipeline_cost_event_identity_conflict")
                        events_by_id[event.event_id] = event
                    merged_events = list(events_by_id.values())
                    merged_scalars = list(existing_step.unattributed_cost_scalars)
                    for scalar in step.unattributed_cost_scalars:
                        if scalar not in merged_scalars:
                            merged_scalars.append(scalar)
                    if len(merged_events) != len(existing_step.cost_events) or len(
                        merged_scalars
                    ) != len(existing_step.unattributed_cost_scalars):
                        merged_values = existing_step.model_dump()
                        merged_values.update(
                            {
                                "cost_events": merged_events,
                                "unattributed_cost_scalars": merged_scalars,
                            }
                        )
                        steps[existing_index] = AgentPipelineStep.model_validate(merged_values)
            source = source or "experiment_state.params"
            if source != "experiment_state.params":
                source = f"{source}+experiment_state.params"

        (
            producer_steps,
            unattributed_cost_events,
            ledger_events_by_id,
            owner_attempt,
            producer_notes,
        ) = self._producer_ledger_projection_for_indexed_run(run)
        if producer_steps:
            steps.extend(producer_steps)
            source = source or "llm_producer_settlement_ledger"
            if source != "llm_producer_settlement_ledger":
                source = f"{source}+llm_producer_settlement_ledger"
        notes.extend(producer_notes)
        producer_owner_not_established = (
            "llm_producer_control_job_owner_not_established" in producer_notes
        )

        other_attempt_events_excluded = False
        reconciled_steps: list[AgentPipelineStep] = []
        for step in steps:
            reconciled_events: list[AgentPipelineCostEvent] = []
            for event in step.cost_events:
                reconciled, excluded_attempt = _reconcile_producer_cost_event(
                    event,
                    ledger_events_by_id.get(event.event_id),
                    owner_attempt=owner_attempt,
                    owner_not_established=producer_owner_not_established,
                )
                other_attempt_events_excluded |= excluded_attempt
                if reconciled is not None:
                    reconciled_events.append(reconciled)
            step_values = step.model_dump()
            step_values.update(
                {
                    "cost_events": reconciled_events,
                    "cost_usd": None,
                    "reported_cost_usd": None,
                    "estimated_cost_usd": None,
                    "cost_origin": None,
                    "cost_origin_counts": {},
                    "settlement_status_counts": {},
                    "settlement_event_ids": (),
                }
            )
            step = AgentPipelineStep.model_validate(step_values)
            reconciled_steps.append(step)
        steps = _deduplicate_agent_cost_events(reconciled_steps)
        if (
            other_attempt_events_excluded
            and "llm_producer_events_from_other_control_job_attempts_excluded_from_core_run"
            not in notes
        ):
            notes.append(
                "llm_producer_events_from_other_control_job_attempts_excluded_from_core_run"
            )

        attempts = _group_agent_steps_by_attempt(steps)
        if not attempts:
            notes.append("agent_pipeline_data_not_available")

        latest_verdict = (
            _latest_attempt_verdict(attempts)
            or _as_str(decision_packet_payload.get("verdict"))
            or _as_str(reflexion_payload.get("decision"))
        )
        retrieval = _retrieval_from_state_payload(state_payload)
        execution_plan_ref = _state_ref_from_param(
            state_payload,
            "execution_plan_ref",
            kind="scientist.execution_plan",
        )
        method_catalog_snapshot_ref = _state_ref_from_param(
            state_payload,
            "method_catalog_snapshot_ref",
            kind="foundry.method_catalog_snapshot",
        )
        preflight_report_ref = _state_ref_from_param(
            state_payload,
            "preflight_report_ref",
            kind="scientist.preflight_report",
        )
        evaluator_report_ref = _state_ref_from_param(
            state_payload,
            "evaluator_report_ref",
            kind="scientist.evaluator_report",
        )
        iteration_state_ref = _state_ref_from_param(
            state_payload,
            "iteration_state_ref",
            kind="scientist.iteration_state",
        )
        reproducibility_manifest_ref = _state_ref_from_param(
            state_payload,
            "reproducibility_manifest_ref",
            kind="scientist.reproducibility_manifest",
        )

        preflight_payload = self._load_json_artifact(preflight_report_ref)
        evaluator_payload = self._load_json_artifact(evaluator_report_ref)
        iteration_payload = self._load_json_artifact(iteration_state_ref)
        reproducibility_payload = self._load_json_artifact(reproducibility_manifest_ref)
        performance_summary = _performance_summary_from_state_payload(
            state_payload,
            sensitive_keys=self._sensitive_keys,
        )

        preflight_view = (
            PreflightReportView(
                ready_to_run=bool(preflight_payload.get("ready_to_run")),
                diagnostics=[
                    PreflightDiagnosticView.model_validate(item)
                    for item in _as_list_of_dicts(preflight_payload.get("diagnostics"))
                ],
                notes=_as_list_of_strings(preflight_payload.get("notes")),
                report_ref=preflight_report_ref,
            )
            if preflight_report_ref is not None
            else None
        )

        evaluator_scores_raw = evaluator_payload.get("scores")
        evaluator_scores = (
            EvaluatorScoresView.model_validate(evaluator_scores_raw)
            if isinstance(evaluator_scores_raw, dict)
            else EvaluatorScoresView()
        )
        evaluator_view = (
            EvaluatorReportView(
                verdict=_as_evaluator_verdict(evaluator_payload.get("verdict")),
                scores=evaluator_scores,
                reasons=_as_list_of_strings(evaluator_payload.get("reasons")),
                replanning_hints=_as_list_of_strings(evaluator_payload.get("replanning_hints")),
                diagnostics=[
                    PreflightDiagnosticView.model_validate(item)
                    for item in _as_list_of_dicts(evaluator_payload.get("diagnostics"))
                ],
                notes=_as_list_of_strings(evaluator_payload.get("notes")),
                report_ref=evaluator_report_ref,
            )
            if evaluator_report_ref is not None
            else None
        )

        iteration_view = (
            IterationLifecycleView(
                iteration=max(1, _as_int(iteration_payload.get("iteration") or 1)),
                state=_as_iteration_lifecycle_state(iteration_payload.get("lifecycle_state")),
                stop_reason=_as_stop_reason(iteration_payload.get("stop_reason")),
                last_verdict=_as_evaluator_verdict(iteration_payload.get("last_verdict")),
                state_ref=iteration_state_ref,
                notes=_as_list_of_strings(iteration_payload.get("notes")),
            )
            if iteration_state_ref is not None
            else None
        )

        reproducibility_view = (
            ReproducibilityView(
                seed=_as_int(reproducibility_payload.get("seed")),
                seed_source=_replay_value(decision_packet_payload, "seed_source"),
                determinism_tier=_replay_value(decision_packet_payload, "determinism_tier"),
                plan_hash=_as_str(reproducibility_payload.get("plan_hash")),
                registry_hash=_as_str(reproducibility_payload.get("registry_hash")),
                method_catalog_hash=_as_str(reproducibility_payload.get("method_catalog_hash")),
                data_snapshot_hash=_as_str(reproducibility_payload.get("data_snapshot_hash")),
                input_bindings_hash=_as_str(reproducibility_payload.get("input_bindings_hash")),
                readiness=_replay_value(decision_packet_payload, "readiness"),
                why_partial=_replay_list(decision_packet_payload, "why_partial"),
                missing_refs=_replay_list(decision_packet_payload, "missing_refs"),
                suggested_next_step=_replay_value(decision_packet_payload, "suggested_next_step"),
                manifest_ref=reproducibility_manifest_ref,
                notes=_as_list_of_strings(reproducibility_payload.get("notes")),
            )
            if (
                reproducibility_manifest_ref is not None
                or _has_replay_payload(decision_packet_payload)
            )
            else None
        )

        return AgentPipelineView._from_verified_owner_context(
            owner_control_job_attempt=owner_attempt,
            run_id=run.run_id,
            source_kind=run.source_kind,
            total_attempts=len(attempts),
            latest_verdict=latest_verdict,
            attempts=attempts,
            unattributed_cost_events=unattributed_cost_events,
            decision_packet_ref=run.decision_packet_ref,
            reflexion_terminal_ref=reflexion_ref,
            retrieval=retrieval,
            execution_plan_ref=execution_plan_ref,
            method_catalog_snapshot_ref=method_catalog_snapshot_ref,
            preflight=preflight_view,
            evaluator=evaluator_view,
            iteration_lifecycle=iteration_view,
            reproducibility=reproducibility_view,
            performance_summary=performance_summary,
            unattributed_cost_scalars=_unattributed_nested_model_variant_scalars(state_payload),
            source=source,
            notes=notes,
        )

    def _agent_steps_from_producer_ledger(
        self,
        run: IndexedRunRecord,
    ) -> tuple[list[AgentPipelineStep], list[str]]:
        """Return only events attributed to this run's validated lease attempt."""
        steps, _, _, _, notes = self._producer_ledger_projection_for_indexed_run(run)
        return steps, notes

    def _producer_ledger_projection_for_indexed_run(
        self,
        run: IndexedRunRecord,
    ) -> tuple[
        list[AgentPipelineStep],
        list[AgentPipelineCostEvent],
        dict[str, AgentPipelineCostEvent],
        int | None,
        list[str],
    ]:
        """Partition exact-owner ledger rows using the persisted lease attempt."""
        settlement_store = self._producer_settlement_store
        if settlement_store is None:
            return [], [], {}, None, []
        binding, attempt, binding_note = self._producer_run_binding_and_attempt_for_indexed_run(run)
        if binding is None or attempt is None:
            return [], [], {}, None, [binding_note] if binding_note is not None else []
        records = settlement_store.list_producer_events_for_run_safe(binding)
        events_by_id = {record.event_id: _producer_record_cost_event(record) for record in records}
        current_events = [
            event
            for event in events_by_id.values()
            if event.control_job_attempt == attempt and event.pre_admission_attempt_id is None
        ]
        unattributed_events = [
            event for event in events_by_id.values() if event.control_job_attempt is None
        ]
        other_attempt_events = [
            event
            for event in events_by_id.values()
            if event.control_job_attempt is not None and event.control_job_attempt != attempt
        ]
        steps = (
            [
                AgentPipelineStep(
                    attempt=1,
                    agent="llm_producer_settlement",
                    action="durable_ledger",
                    status=(
                        "warn"
                        if any(
                            e.settlement_status in {"pending", "unknown"} for e in current_events
                        )
                        else "info"
                    ),
                    summary=(
                        "Provider cost events reconciled to the exact ControlJob lease attempt."
                    ),
                    details={
                        "source": "app_scoped_producer_settlement_ledger",
                        "control_job_attempt": attempt,
                    },
                    model=current_events[0].model,
                    provider=current_events[0].provider,
                    cost_events=current_events,
                )
            ]
            if current_events
            else []
        )
        notes: list[str] = []
        if other_attempt_events:
            notes.append(
                "llm_producer_events_from_other_control_job_attempts_excluded_from_core_run"
            )
        if unattributed_events:
            notes.append("llm_producer_events_with_unknown_or_pre_admission_attempt_unassigned")
        return steps, unattributed_events, events_by_id, attempt, notes

    def _producer_run_binding_for_indexed_run(
        self,
        run: IndexedRunRecord,
    ) -> tuple[BudgetLedgerProducerRunBinding | None, str | None]:
        """Resolve the internal NL ledger key from the persisted ControlJob owner."""
        binding, _, note = self._producer_run_binding_and_attempt_for_indexed_run(run)
        return binding, note

    def _producer_run_binding_and_attempt_for_indexed_run(
        self,
        run: IndexedRunRecord,
    ) -> tuple[BudgetLedgerProducerRunBinding | None, int | None, str | None]:
        """Resolve binding and positive lease attempt from the same persisted owner read."""
        from polisyos.runtime.http.services.adapters.core_run import (
            derive_control_job_core_run_id,
        )
        from polisyos.runtime.http.services.control_plane_store import (
            ControlJobExecutionAdmissionError,
            _control_job_execution_scope_from_event,
            _json_values_equal_strict,
        )

        store = self._producer_control_job_store
        details = run.details
        control_job_id = details.control_job_id
        if not isinstance(control_job_id, str) or not control_job_id.strip():
            return None, None, None
        if store is None:
            return None, None, "llm_producer_control_job_owner_not_established"
        try:
            job = store.get_job(control_job_id)
            if job is None:
                return None, None, "llm_producer_control_job_owner_not_established"
            event_payload = store.get_job_created_event_payload(control_job_id)
            outbox_event = store.get_job_created_outbox_event(control_job_id)
        except (
            ControlJobExecutionAdmissionError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ):
            return None, None, "llm_producer_control_job_owner_not_established"

        outbox_payload = getattr(outbox_event, "payload", None)
        if (
            getattr(outbox_event, "topic", None) != "control.job.created"
            or getattr(outbox_event, "job_id", None) != job.job_id
            or getattr(outbox_event, "run_id", None) != job.run_id
            or not isinstance(outbox_payload, dict)
            or not _json_values_equal_strict(outbox_payload, event_payload)
        ):
            return None, None, "llm_producer_control_job_owner_not_established"

        expected_job_fields = {
            "job_id": job.job_id,
            "run_id": job.run_id,
            "job_kind": job.kind,
            "pipeline_id": job.pipeline_id,
            "payload_ref": job.payload_ref,
            "submitted_by": job.submitted_by,
            "requested_execution_profile": job.requested_execution_profile,
            "effective_execution_profile": job.effective_execution_profile,
            "policy_flags": job.policy_flags,
        }
        if any(
            field not in event_payload
            or not _json_values_equal_strict(event_payload[field], expected)
            for field, expected in expected_job_fields.items()
        ):
            return None, None, "llm_producer_control_job_owner_not_established"
        try:
            scope = _control_job_execution_scope_from_event(event_payload)
        except ControlJobExecutionAdmissionError:
            return None, None, "llm_producer_control_job_owner_not_established"

        progress = job.progress if isinstance(job.progress, dict) else {}
        core_run_id = progress.get("core_run_id")
        core_run_attempt = progress.get("core_run_attempt")
        if (
            job.state not in {"completed", "failed"}
            or job.kind != "natural_language_run"
            or not isinstance(job.run_id, str)
            or not job.run_id.strip()
            or scope.status != "established"
            or scope.tenant_id != details.tenant_id
            or scope.cell_id != details.cell_id
            or scope.actor_subject != job.submitted_by
            or job.effective_execution_profile != details.execution_profile
            or job.job_id != control_job_id
            or type(job.attempt) is not int
            or job.attempt < 1
            or not isinstance(core_run_id, str)
            or core_run_id != details.run_id
            or isinstance(core_run_attempt, bool)
            or not isinstance(core_run_attempt, int)
            or core_run_attempt < 1
            or core_run_attempt != job.attempt
        ):
            return None, None, "llm_producer_control_job_owner_not_established"
        try:
            expected_core_run_id = derive_control_job_core_run_id(
                job_id=job.job_id,
                control_run_id=job.run_id,
                attempt=core_run_attempt,
            )
            if expected_core_run_id != run.run_id or run.run_id != details.run_id:
                return None, None, "llm_producer_control_job_owner_not_established"
            binding = BudgetLedgerProducerRunBinding(
                run_id=job.run_id,
                tenant_id=scope.tenant_id,
                cell_id=scope.cell_id,
                profile_id=job.effective_execution_profile,
                control_job_id=job.job_id,
            )
        except TypeError, ValueError:
            return None, None, "llm_producer_control_job_owner_not_established"
        return binding, core_run_attempt, None

    def _scorecard_owner_source_for_indexed_run(
        self,
        run: IndexedRunRecord,
        *,
        fresh_job_payload: object,
    ) -> _ScorecardControlJobOwnerSource | None:
        """Recompute terminal owner binding across ControlJob, Core index, and fresh GET."""
        from polisyos.runtime.http.services.control_plane_store import (
            ControlJobExecutionAdmissionError,
            _control_job_execution_scope_from_event,
            _control_job_outbox_identity_envelope,
            _json_values_equal_strict,
        )
        from polisyos.runtime.quality.phase_barriers import (
            _validated_execution_owner_binding,
        )

        store = self._producer_control_job_store
        control_job_id = run.details.control_job_id
        if store is None or not isinstance(control_job_id, str) or not control_job_id.strip():
            return None
        for reader_name in (
            "get_job_terminal_source_event_record",
            "get_job_completed_outbox_event",
        ):
            if not callable(getattr(store, reader_name, None)):
                raise _ScorecardOwnerSourceReaderUnavailableError(reader_name)
        binding, binding_note = self._producer_run_binding_for_indexed_run(run)
        if binding is None or binding_note is not None:
            return None
        try:
            job = store.get_job(control_job_id)
            if job is None:
                return None
            creation_payload = store.get_job_created_event_payload(control_job_id)
            creation_outbox = store.get_job_created_outbox_event(control_job_id)
            terminal_event = store.get_job_terminal_source_event_record(control_job_id)
            completion_outbox = store.get_job_completed_outbox_event(control_job_id)
            if terminal_event is None or completion_outbox is None:
                return None
            scope = _control_job_execution_scope_from_event(creation_payload)
            fresh_job = ControlJobResponse.model_validate(fresh_job_payload)
        except (
            ControlJobExecutionAdmissionError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
            ValidationError,
        ):
            return None

        creation_outbox_payload = getattr(creation_outbox, "payload", None)
        if (
            getattr(creation_outbox, "topic", None) != "control.job.created"
            or getattr(creation_outbox, "job_id", None) != job.job_id
            or getattr(creation_outbox, "run_id", None) != job.run_id
            or not isinstance(creation_outbox_payload, dict)
            or not _json_values_equal_strict(creation_outbox_payload, creation_payload)
        ):
            return None

        event_payload = terminal_event.payload
        progress = job.progress if isinstance(job.progress, dict) else None
        if (
            terminal_event.job_id != job.job_id
            or terminal_event.event_type != "job_completed"
            or not isinstance(event_payload, dict)
            or event_payload.get("state") != "completed"
            or job.state != "completed"
            or job.lease_owner is not None
            or job.lease_expires_at is not None
            or job.finished_at is None
            or scope.status != "established"
            or not isinstance(scope.tenant_id, str)
            or not scope.tenant_id.strip()
            or not isinstance(scope.cell_id, str)
            or not scope.cell_id.strip()
            or scope.actor_subject != job.submitted_by
            or job.kind != "natural_language_run"
            or not isinstance(job.run_id, str)
            or not job.run_id.strip()
            or progress is None
            or binding.control_job_id != job.job_id
            or binding.run_id != job.run_id
            or binding.tenant_id != scope.tenant_id
            or binding.cell_id != scope.cell_id
            or binding.profile_id != job.effective_execution_profile
            or terminal_event.payload.get("attempt") != job.attempt
            or type(terminal_event.payload.get("attempt")) is not int
        ):
            return None

        lease_owner = event_payload.get("lease_owner")
        requested_profile = job.requested_execution_profile
        if (
            not isinstance(lease_owner, str)
            or not lease_owner.strip()
            or (
                requested_profile is not None
                and (
                    not isinstance(requested_profile, str)
                    or not requested_profile.strip()
                    or requested_profile != requested_profile.strip()
                )
            )
            or not isinstance(job.effective_execution_profile, str)
            or not job.effective_execution_profile.strip()
        ):
            return None
        expected_owner: dict[str, str | int | None] = {
            "job_id": job.job_id,
            "run_id": job.run_id,
            "tenant_id": scope.tenant_id,
            "cell_id": scope.cell_id,
            "requested_execution_profile": job.requested_execution_profile,
            "effective_execution_profile": job.effective_execution_profile,
            "attempt": job.attempt,
            "lease_owner": lease_owner,
        }
        owner_binding = _validated_execution_owner_binding(
            progress.get("execution_owner_binding"),
            expected=expected_owner,
        )
        core_run_id = progress.get("core_run_id")
        core_run_attempt = progress.get("core_run_attempt")
        if (
            owner_binding is None
            or not isinstance(core_run_id, str)
            or core_run_id != run.run_id
            or isinstance(core_run_attempt, bool)
            or type(core_run_attempt) is not int
            or core_run_attempt != job.attempt
            or fresh_job.job_id != job.job_id
            or fresh_job.kind != job.kind
            or fresh_job.state != "completed"
            or fresh_job.run_id != job.run_id
            or fresh_job.requested_execution_profile != job.requested_execution_profile
            or fresh_job.effective_execution_profile != job.effective_execution_profile
            or fresh_job.projection_source.authority_level != "projection_only"
            or fresh_job.projection_source.projection_policy != "projection_only"
        ):
            return None

        fresh_progress = fresh_job.progress
        fresh_owner_binding = _validated_execution_owner_binding(
            fresh_progress.get("execution_owner_binding"),
            expected=expected_owner,
        )
        fresh_core_run_id = fresh_progress.get("core_run_id")
        fresh_core_run_attempt = fresh_progress.get("core_run_attempt")
        if (
            fresh_owner_binding is None
            or fresh_core_run_id != core_run_id
            or type(fresh_core_run_attempt) is not int
            or fresh_core_run_attempt != core_run_attempt
        ):
            return None

        completion_outbox_payload = getattr(completion_outbox, "payload", None)
        expected_completion_payload = dict(event_payload)
        if "progress" in event_payload and not _json_values_equal_strict(
            event_payload["progress"], progress
        ):
            return None
        expected_completion_payload["progress"] = progress
        expected_outbox_envelope = _control_job_outbox_identity_envelope(job)
        if any(
            field in expected_completion_payload
            and not _json_values_equal_strict(expected_completion_payload[field], value)
            for field, value in expected_outbox_envelope.items()
        ):
            return None
        expected_completion_payload.update(expected_outbox_envelope)
        if (
            getattr(completion_outbox, "topic", None) != "control.job.completed"
            or getattr(completion_outbox, "event_key", None) != f"{job.job_id}:job_completed"
            or getattr(completion_outbox, "job_id", None) != job.job_id
            or getattr(completion_outbox, "run_id", None) != job.run_id
            or not isinstance(completion_outbox_payload, dict)
            or not _json_values_equal_strict(completion_outbox_payload, expected_completion_payload)
        ):
            return None

        return _ScorecardControlJobOwnerSource(
            job_id=job.job_id,
            run_id=job.run_id,
            tenant_id=scope.tenant_id,
            cell_id=scope.cell_id,
            requested_execution_profile=job.requested_execution_profile,
            effective_execution_profile=job.effective_execution_profile,
            attempt=job.attempt,
            lease_owner=lease_owner,
            completion_event_id=terminal_event.event_id,
            completion_event_payload_sha256=terminal_event.payload_sha256,
            completion_outbox_event_id=completion_outbox.event_id,
            core_run_id=run.run_id,
        )

    def get_run_evidence_context(self, run: IndexedRunRecord) -> RunEvidenceContextView:
        """Return data-needs, fetch-plan, promotion, and related-artifact context."""
        warnings: list[str] = []
        state_payload = self._load_experiment_state_payload(run.experiment_state_ref)
        request_profile_origin, request_profile_origin_issue = (
            _workflow_data_view_request_profile_origin(
                store=self._store,
                control_job_store=self._producer_control_job_store,
                control_job_id=run.details.control_job_id,
                state_payload=state_payload,
            )
        )
        if request_profile_origin_issue is not None:
            warnings.append(request_profile_origin_issue)
        decision_packet_payload = self._load_json_artifact(run.decision_packet_ref)
        params = state_payload.get("params")
        params_dict = params if isinstance(params, dict) else {}
        retrieval_context = params_dict.get("retrieval_context")
        retrieval_context_dict = retrieval_context if isinstance(retrieval_context, dict) else {}

        execution_plan_ref = (
            _state_ref_from_param(
                state_payload, "execution_plan_ref", kind="scientist.execution_plan"
            )
            or _artifact_ref_from_string(
                _path_get_as_str(decision_packet_payload, ("artifacts", "execution_plan_ref")),
                kind="scientist.execution_plan",
            )
            or self._find_first_ref_by_kind(run, "scientist.execution_plan")
        )
        execution_plan_payload = self._load_json_artifact(execution_plan_ref)

        plan_needs_raw = execution_plan_payload.get("data_needs")
        context_needs_raw = retrieval_context_dict.get("data_needs")
        data_needs_rows = (
            _as_list_of_dicts(context_needs_raw)
            if isinstance(context_needs_raw, list)
            else _as_list_of_dicts(plan_needs_raw)
        )
        if execution_plan_ref is None:
            warnings.append("execution_plan_ref_missing")
        if not data_needs_rows:
            warnings.append("run_data_needs_missing")

        fetch_plans_rows = _as_list_of_dicts(retrieval_context_dict.get("fetch_plans"))
        if not fetch_plans_rows:
            warnings.append("run_fetch_plans_missing")

        promotion_rows = _as_list_of_dicts(retrieval_context_dict.get("promotion_candidates"))

        needs: list[RunEvidenceNeedView] = []
        needs_by_metric: dict[str, list[str]] = defaultdict(list)
        for row in data_needs_rows:
            need_id = _stable_id(
                "need",
                _as_str(row.get("metric")) or "",
                _as_str(row.get("geography")) or "",
                _as_str(row.get("time_start")) or "",
                _as_str(row.get("time_end")) or "",
                _as_str(row.get("granularity")) or "",
                _as_str(row.get("purpose")) or "",
            )
            metric = _as_str(row.get("metric")) or "unknown.metric"
            needs.append(
                RunEvidenceNeedView(
                    need_id=need_id,
                    metric=metric,
                    geography=_as_str(row.get("geography")),
                    time_start=_as_str(row.get("time_start")),
                    time_end=_as_str(row.get("time_end")),
                    granularity=_as_str(row.get("granularity")) or "annual",
                    quality_min=_as_float(row.get("quality_min"), default=0.6),
                    purpose=_as_str(row.get("purpose")) or "policy_drafting",
                    matched_plan_ids=[],
                    notes=_as_list_of_strings(row.get("notes")),
                )
            )
            needs_by_metric[metric].append(need_id)

        plans: list[RunEvidencePlanView] = []
        plan_ids: set[str] = set()
        plan_ids_by_metric: dict[str, list[str]] = defaultdict(list)
        for row in fetch_plans_rows:
            plan_id = _as_str(row.get("plan_id")) or _stable_id(
                "plan",
                _as_str(row.get("metric_id")) or "",
                _as_str(row.get("connector_id")) or "",
                _as_str(row.get("dataset_id")) or "",
            )
            metric_id = _as_str(row.get("metric_id")) or "unknown.metric"
            matched_need_ids = list(needs_by_metric.get(metric_id, []))
            plans.append(
                RunEvidencePlanView(
                    plan_id=plan_id,
                    metric_id=metric_id,
                    connector_id=_as_str(row.get("connector_id")) or "unknown.connector",
                    dataset_id=_as_str(row.get("dataset_id")) or "unknown.dataset",
                    profile_id=_as_str(row.get("profile_id")),
                    source_lane=_as_str(row.get("source_lane")) or "fastlane",
                    quality_min=_as_float(row.get("quality_min"), default=0.6),
                    filters=_string_list_dict(row.get("filters")),
                    date_start=_as_str(row.get("date_start")),
                    date_end=_as_str(row.get("date_end")),
                    granularity=_as_str(row.get("granularity")),
                    fallback_count=len(_as_list_of_dicts(row.get("fallbacks"))),
                    matched_need_ids=matched_need_ids,
                    notes=_as_list_of_strings(row.get("notes")),
                )
            )
            plan_ids.add(plan_id)
            plan_ids_by_metric[metric_id].append(plan_id)

        if plans:
            needs = [
                item.model_copy(
                    update={"matched_plan_ids": plan_ids_by_metric.get(item.metric, [])}
                )
                for item in needs
            ]

        promotions: list[RunEvidencePromotionView] = []
        for row in promotion_rows:
            metric_id = _as_str(row.get("metric_id")) or "unknown.metric"
            matched_plan_id = None
            candidate_plan_ids = plan_ids_by_metric.get(metric_id, [])
            if len(candidate_plan_ids) == 1:
                matched_plan_id = candidate_plan_ids[0]
            elif candidate_plan_ids:
                connector_id = _as_str(row.get("connector_id"))
                dataset_id = _as_str(row.get("dataset_id"))
                matched_plan_id = next(
                    (
                        plan.plan_id
                        for plan in plans
                        if plan.metric_id == metric_id
                        and plan.connector_id == connector_id
                        and plan.dataset_id == dataset_id
                    ),
                    None,
                )

            promotions.append(
                RunEvidencePromotionView(
                    promotion_id=_as_str(row.get("promotion_id"))
                    or _stable_id(
                        "promotion",
                        metric_id,
                        _as_str(row.get("connector_id")) or "",
                        _as_str(row.get("dataset_id")) or "",
                    ),
                    metric_id=metric_id,
                    connector_id=_as_str(row.get("connector_id")) or "unknown.connector",
                    dataset_id=_as_str(row.get("dataset_id")) or "unknown.dataset",
                    profile_id=_as_str(row.get("profile_id")),
                    source_lane=_as_str(row.get("source_lane")) or "explorelane",
                    confidence=_as_float(row.get("confidence"), default=0.0),
                    status=_as_str(row.get("status")) or "pending",
                    created_at=_as_datetime(row.get("created_at")),
                    signals=_as_list_of_strings(row.get("signals")),
                    matched_plan_id=matched_plan_id,
                    metadata=_as_dict(row.get("metadata")),
                )
            )

        auto_refs = _as_dict(retrieval_context_dict.get("auto_data_source_refs"))
        production_data_context = _as_dict(
            retrieval_context_dict.get("production_data_evidence_context")
        )
        artifact_ownership = _artifact_ownership_evidence_from_store(
            self._store,
            tenant_id=run.details.tenant_id,
            cell_id=run.details.cell_id,
        )
        if artifact_ownership:
            production_data_context.setdefault("artifact_ownership", artifact_ownership)
        materialization_refs = _materialization_refs_from_payload(auto_refs)
        if not materialization_refs:
            materialization_refs = _materialization_refs_from_payload(
                _as_dict(production_data_context.get("materialization_refs"))
            )
        fabric_retrieval_trace_ref = materialization_refs.get(
            "fabric_retrieval_trace_ref"
        ) or _artifact_ref_from_string(
            _as_str(production_data_context.get("fabric_retrieval_trace_ref")),
            kind="fabric.retrieval_trace",
        )
        if fabric_retrieval_trace_ref is not None:
            materialization_refs["fabric_retrieval_trace_ref"] = fabric_retrieval_trace_ref
            production_data_context.setdefault(
                "fabric_retrieval_trace_ref",
                str(fabric_retrieval_trace_ref.artifact_id),
            )
        if materialization_refs:
            production_data_context.setdefault(
                "materialization_refs",
                {key: str(ref.artifact_id) for key, ref in materialization_refs.items()},
            )
        packet_inputs = _as_dict(decision_packet_payload.get("inputs"))
        state_snapshot_ref, state_snapshot_issue = _state_input_ref(
            state_payload,
            "data_snapshot_ref",
            expected_kind="fabric.data_snapshot",
        )
        if state_snapshot_issue is not None:
            warnings.append(state_snapshot_issue)
        data_snapshot_ref = state_snapshot_ref
        if data_snapshot_ref is None and state_snapshot_issue is None:
            data_snapshot_ref = (
                self._find_run_artifact_ref_by_kind(run, "fabric.data_snapshot")
                or materialization_refs.get("data_snapshot_ref")
                or _artifact_ref_from_string(
                    _as_str(packet_inputs.get("data_snapshot_ref")),
                    kind="fabric.data_snapshot",
                )
            )
        if data_snapshot_ref is not None:
            data_snapshot_ref, selection_issue = self._resolve_selected_run_artifact_ref(
                run,
                data_snapshot_ref,
            )
            if selection_issue is not None:
                warnings.append(selection_issue)
        if data_snapshot_ref is not None:
            from polisyos.core.contracts import DataSnapshot

            try:
                selected_snapshot = validate_core_model_json_artifact(
                    DataSnapshot,
                    self._store,
                    data_snapshot_ref,
                )
                from polisyos.runtime.quality.data_snapshot_lineage import (
                    validate_data_snapshot_owner_lineage,
                )

                validate_data_snapshot_owner_lineage(
                    self._store,
                    data_snapshot_ref,
                    selected_snapshot,
                )
            except (
                AttributeError,
                CanonicalProfileRefusalError,
                FileNotFoundError,
                OSError,
                RuntimeError,
                TypeError,
                ValidationError,
                ValueError,
            ):
                warnings.append("data_snapshot_selected_view_not_established")
                data_snapshot_ref = None
            else:
                quality_report_ref = selected_snapshot.quality_report_ref
                supplied_quality_id = _as_str(auto_refs.get("quality_report_ref"))
                if supplied_quality_id is None:
                    supplied_quality_id = _as_str(
                        _as_dict(production_data_context.get("materialization_refs")).get(
                            "quality_report_ref"
                        )
                    )
                if quality_report_ref is not None:
                    if supplied_quality_id is not None and supplied_quality_id != str(
                        quality_report_ref.artifact_id
                    ):
                        warnings.append("quality_report_ref_differs_from_selected_data_snapshot")
                    else:
                        try:
                            quality_manifest, _ = read_core_manifest_profile(
                                self._store,
                                quality_report_ref,
                            )
                            quality_report_ref = ArtifactRef(
                                artifact_id=quality_report_ref.artifact_id,
                                kind=quality_manifest.kind,
                                media_type=quality_manifest.media_type,
                                manifest_profile_sha256=artifact_manifest_profile_sha256(
                                    quality_manifest
                                ),
                            )
                        except (
                            AttributeError,
                            CanonicalProfileRefusalError,
                            FileNotFoundError,
                            OSError,
                            RuntimeError,
                            TypeError,
                            ValueError,
                        ):
                            warnings.append("quality_report_selected_view_not_established")
                        else:
                            materialization_refs["quality_report_ref"] = quality_report_ref
                elif supplied_quality_id is not None:
                    warnings.append("quality_report_ref_missing_from_selected_data_snapshot")
        state_bindings_ref, state_bindings_issue = _state_input_ref(
            state_payload,
            "input_bindings_ref",
            expected_kind="foundry.input_bindings",
        )
        if state_bindings_issue is not None:
            warnings.append(state_bindings_issue)
        input_bindings_ref = state_bindings_ref
        if input_bindings_ref is None and state_bindings_issue is None:
            input_bindings_ref = (
                self._find_run_input_ref_by_kind(run, "foundry.input_bindings")
                or materialization_refs.get("input_bindings_ref")
                or _artifact_ref_from_string(
                    _as_str(packet_inputs.get("input_bindings_ref")),
                    kind="foundry.input_bindings",
                )
            )
        evidence_bundle_ref = (
            self._find_run_input_ref_by_kind(run, "fabric.evidence_bundle")
            or materialization_refs.get("evidence_bundle_ref")
            or _artifact_ref_from_string(
                _as_str(packet_inputs.get("evidence_bundle_ref")),
                kind="fabric.evidence_bundle",
            )
        )
        data_view_request_ref = None
        state_request_ref: ArtifactRef | None = None
        state_request_issue: str | None = None
        if data_snapshot_ref is not None:
            state_request_ref, state_request_issue = _state_input_ref(
                state_payload,
                "data_view_request_ref",
                expected_kind="ir.data_view_request",
            )
            if state_request_issue is not None:
                warnings.append(state_request_issue)
            else:
                data_view_request_ref, source_warning = _data_view_request_ref_from_snapshot(
                    self._store,
                    data_snapshot_ref,
                    expected_request_ref=state_request_ref,
                )
                if source_warning is not None:
                    warnings.append(source_warning)
        if request_profile_origin == "not_requested":
            data_view_request_profile_status = "not_requested"
        elif data_view_request_ref is not None and request_profile_origin == "caller_selected":
            data_view_request_profile_status = "caller_selected_profile"
        elif data_view_request_ref is not None and request_profile_origin == "worker_default":
            data_view_request_profile_status = "worker_default_limited"
            warnings.append("data_view_request_profile_selection_limited_to_worker_default")
        else:
            data_view_request_profile_status = "not_established"
            warnings.append("data_view_request_profile_origin_or_lineage_not_established")
        if data_snapshot_ref is not None:
            materialization_refs["data_snapshot_ref"] = data_snapshot_ref
        if input_bindings_ref is not None:
            materialization_refs["input_bindings_ref"] = input_bindings_ref

        related_artifacts = _dedupe_artifact_refs(
            [
                execution_plan_ref,
                fabric_retrieval_trace_ref,
                data_snapshot_ref,
                data_view_request_ref,
                input_bindings_ref,
                evidence_bundle_ref,
                materialization_refs.get("registry_bundle_ref"),
                materialization_refs.get("quality_report_ref"),
                materialization_refs.get("input_binding_report_ref"),
                _artifact_ref_from_string(
                    _path_get_as_str(decision_packet_payload, ("artifacts", "decision_card_ref")),
                    kind="scientist.decision_card",
                ),
                _artifact_ref_from_string(
                    _path_get_as_str(
                        decision_packet_payload,
                        ("artifacts", "input_binding_report_ref"),
                    ),
                    kind="foundry.input_binding_report",
                ),
                *run.details.root_artifacts,
            ]
        )

        for plan in plans:
            if plan.matched_need_ids:
                continue
            warnings.append(f"unmatched_fetch_plan:{plan.plan_id}")
        for promotion in promotions:
            if promotion.matched_plan_id is None and plan_ids:
                warnings.append(f"unmatched_promotion_candidate:{promotion.promotion_id}")

        return RunEvidenceContextView(
            run_id=run.run_id,
            source_kind=run.source_kind,
            execution_plan_ref=execution_plan_ref,
            evidence_bundle_ref=evidence_bundle_ref,
            fabric_retrieval_trace_ref=fabric_retrieval_trace_ref,
            data_snapshot_ref=data_snapshot_ref,
            data_view_request_ref=data_view_request_ref,
            data_view_request_profile_status=data_view_request_profile_status,
            input_bindings_ref=input_bindings_ref,
            materialization_refs=materialization_refs,
            production_data_evidence_context=production_data_context,
            related_artifacts=related_artifacts,
            data_needs=needs,
            fetch_plans=plans,
            promotion_candidates=promotions,
            warnings=_dedupe_strings(warnings),
        )

    def get_run_workflow(self, run: IndexedRunRecord) -> RunWorkflowView:
        """Return a DAG-like workflow projection with node depths, edges, and heat."""
        notes: list[str] = []
        timeline_events = self._timeline_service.build_for_run(run).timeline.events
        timeline_by_alias = {
            item.alias: item for item in _nodes_from_timeline(timeline_events) if item.alias
        }

        report_payload = self._load_json_artifact(
            run.workflow_report_ref,
            on_missing=lambda: notes.append("workflow_report_missing_or_unavailable"),
        )
        report_rows = _as_list_of_dicts(report_payload.get("nodes"))
        report_by_alias = _workflow_report_nodes_by_alias(report_rows)

        workflow_spec_ref = self._find_run_input_ref_by_kind(run, _WORKFLOW_SPEC_KIND)
        workflow_spec_payload = self._load_json_artifact(
            workflow_spec_ref,
            on_missing=lambda: notes.append("workflow_spec_missing_or_unavailable"),
        )
        spec_rows = _as_list_of_dicts(workflow_spec_payload.get("nodes"))
        spec_by_alias, spec_order = _workflow_spec_nodes(spec_rows)
        if not spec_by_alias and "workflow_spec_missing_or_unavailable" not in notes:
            notes.append("workflow_spec_missing_or_unavailable")

        aliases: list[str] = []
        aliases.extend(spec_order)
        for alias in report_by_alias:
            if alias not in aliases:
                aliases.append(alias)
        for alias in timeline_by_alias:
            if alias not in aliases:
                aliases.append(alias)

        nodes: list[RunWorkflowNodeView] = []
        for alias in aliases:
            spec_node = spec_by_alias.get(alias, {})
            report_node = report_by_alias.get(alias)
            timeline_node = timeline_by_alias.get(alias)

            depends_on = _as_list_of_strings(spec_node.get("depends_on"))
            node_id = _as_str(spec_node.get("node_id"))
            if report_node:
                node_id = node_id or _as_str(report_node.get("node_id"))

            status = _normalize_status(_as_str(report_node.get("status")) if report_node else None)
            if status == "unknown" and timeline_node is not None:
                status = timeline_node.status

            duration_ms = _as_int(report_node.get("duration_ms")) if report_node else 0
            if duration_ms <= 0 and timeline_node is not None:
                duration_ms = timeline_node.duration_ms

            report_artifacts = _artifact_ids_from_report_node(report_node)
            artifact_ids = sorted(
                set(report_artifacts).union(
                    timeline_node.output_artifact_ids if timeline_node else []
                )
            )
            input_artifact_ids = timeline_node.input_artifact_ids if timeline_node else []
            output_artifact_ids = timeline_node.output_artifact_ids if timeline_node else []

            raw_error = report_node.get("error") if report_node else None
            error_payload = raw_error if isinstance(raw_error, dict) else {}

            nodes.append(
                RunWorkflowNodeView(
                    alias=alias,
                    node_id=node_id,
                    depends_on=depends_on,
                    depth=0,
                    status=status,
                    duration_ms=duration_ms,
                    skip_reason=_as_str(report_node.get("skip_reason")) if report_node else None,
                    error_code=_as_str(error_payload.get("code")),
                    error_message=_sanitize_string(_as_str(error_payload.get("message"))),
                    artifact_ids=artifact_ids,
                    input_artifact_ids=input_artifact_ids,
                    output_artifact_ids=output_artifact_ids,
                    input_artifact_refs=timeline_node.input_artifact_refs if timeline_node else [],
                    output_artifact_refs=(
                        timeline_node.output_artifact_refs if timeline_node else []
                    ),
                    heat=0.0,
                )
            )

        edges = _workflow_edges_from_nodes(nodes)
        depth_by_alias, cycle_detected = _workflow_depths(nodes)
        if cycle_detected:
            notes.append("workflow_cycle_detected")

        max_duration = max((node.duration_ms for node in nodes), default=0)
        enriched_nodes: list[RunWorkflowNodeView] = []
        for node in nodes:
            depth = depth_by_alias.get(node.alias, 0)
            heat = float(node.duration_ms) / float(max_duration) if max_duration > 0 else 0.0
            enriched_nodes.append(
                node.model_copy(
                    update={
                        "depth": depth,
                        "heat": round(heat, 3),
                    }
                )
            )
        enriched_nodes.sort(key=lambda item: (item.depth, item.alias))

        status_counts: defaultdict[str, int] = defaultdict(int)
        for node in enriched_nodes:
            status_counts[node.status] += 1
        critical_path = _critical_path_duration_ms(enriched_nodes)

        summary = RunWorkflowSummary(
            workflow_id=(
                _as_str(workflow_spec_payload.get("workflow_id"))
                or _as_str(report_payload.get("workflow_id"))
            ),
            error_policy=(
                _as_str(workflow_spec_payload.get("error_policy"))
                or _as_str(report_payload.get("error_policy"))
            ),
            status=_as_str(report_payload.get("status")),
            node_count=len(enriched_nodes),
            edge_count=len(edges),
            ok_count=status_counts.get("ok", 0),
            skip_count=status_counts.get("skip", 0),
            fail_count=status_counts.get("fail", 0),
            max_depth=max((node.depth for node in enriched_nodes), default=0),
            critical_path_duration_ms=critical_path,
        )

        return RunWorkflowView(
            run_id=run.run_id,
            source_kind=run.source_kind,
            summary=summary,
            nodes=enriched_nodes,
            edges=edges,
            workflow_spec_ref=workflow_spec_ref,
            workflow_report_ref=run.workflow_report_ref,
            notes=notes,
        )

    def _load_workflow_nodes(
        self,
        workflow_report_ref: ArtifactRef | None,
        *,
        payload: dict[str, Any] | None = None,
        on_missing: Callable[[], None] | None = None,
    ) -> list[RunNodeRecord]:
        payload = (
            payload
            if payload is not None
            else self._load_json_artifact(workflow_report_ref, on_missing=on_missing)
        )
        rows = payload.get("nodes")
        if not isinstance(rows, list):
            return []

        result: list[RunNodeRecord] = []
        for row in rows:
            if not isinstance(row, dict):
                continue

            record = self._workflow_node_record(row)
            if record.alias:
                result.append(record)
        result.sort(key=lambda item: item.alias)
        return result

    def _workflow_node_record(self, row: dict[str, Any]) -> RunNodeRecord:
        """Project metadata from the same selected raw node used for ref admission."""
        artifacts = row.get("artifacts")
        artifact_ids: list[str] = []
        if isinstance(artifacts, list):
            for artifact in artifacts:
                if not isinstance(artifact, dict):
                    continue
                artifact_id = _as_str(artifact.get("artifact_id"))
                if artifact_id:
                    artifact_ids.append(artifact_id)

        raw_error = row.get("error")
        error_payload = raw_error if isinstance(raw_error, dict) else {}
        return RunNodeRecord(
            alias=_as_str(row.get("alias")) or "",
            node_id=_as_str(row.get("node_id")),
            status=_normalize_status(_as_str(row.get("status"))),
            duration_ms=_as_int(row.get("duration_ms")),
            error_code=_as_str(error_payload.get("code")),
            error_message=_sanitize_string(_as_str(error_payload.get("message"))),
            error_details=_sanitize_payload(
                error_payload.get("details")
                if isinstance(error_payload.get("details"), dict)
                else {},
                sensitive_keys=self._sensitive_keys,
            ),
            skip_reason=_as_str(row.get("skip_reason")),
            artifact_ids=sorted(set(artifact_ids)),
        )

    def _load_experiment_state_payload(self, ref: ArtifactRef | None) -> dict[str, Any]:
        return self._load_json_artifact(ref)

    def _load_verified_binding_json(
        self,
        ref: ArtifactRef | None,
        *,
        expected_kind: str,
        expected_media_type: str,
        expected_schema_name: str,
        expected_schema_versions: frozenset[str],
        expected_run_id: str,
        expected_tenant_id: str | None,
        expected_cell_id: str | None,
    ) -> dict[str, Any]:
        """Load a verified workflow binding artifact before authorizing a result."""
        if ref is None:
            raise SimulationResultProjectionError(
                "simulation_result_binding_missing",
                "The run has no persisted workflow binding artifact",
            )
        if ref.kind != expected_kind or ref.media_type != expected_media_type:
            raise SimulationResultProjectionError(
                "simulation_result_binding_ref_mismatch",
                "A workflow binding reference has an unexpected kind or media type",
            )
        try:
            verification = self._store.verify(ref)
            if not verification.ok:
                raise SimulationResultProjectionError(
                    "simulation_result_binding_integrity_failed",
                    "A persisted workflow binding artifact failed CAS integrity verification",
                )
            manifest = read_core_manifest_profile(self._store, ref)[0]
            schema = manifest.artifact_schema
            if (
                manifest.kind != expected_kind
                or manifest.media_type != expected_media_type
                or schema is None
                or schema.name != expected_schema_name
                or schema.version not in expected_schema_versions
            ):
                raise SimulationResultProjectionError(
                    "simulation_result_binding_schema_mismatch",
                    "A persisted workflow binding artifact has an unexpected manifest",
                )
            tenant_context = manifest.tenant_context
            if (
                expected_tenant_id is None
                or expected_cell_id is None
                or tenant_context is None
                or tenant_context.tenant_id != expected_tenant_id
                or tenant_context.cell_id != expected_cell_id
            ):
                raise SimulationResultProjectionError(
                    "simulation_result_binding_tenant_mismatch",
                    "A persisted workflow binding artifact has an unexpected tenant or cell",
                )
            manifest_schema_version = schema.version
            payload = read_core_json_artifact(self._store, ref).value
        except SimulationResultProjectionError:
            raise
        except (
            FileNotFoundError,
            OSError,
            PermissionError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
        ) as exc:
            raise SimulationResultProjectionError(
                "simulation_result_binding_unavailable",
                "A persisted workflow binding artifact is unavailable",
            ) from exc
        if not isinstance(payload, dict):
            raise SimulationResultProjectionError(
                "simulation_result_binding_invalid",
                "A persisted workflow binding artifact is not a JSON object",
            )
        if payload.get("run_id") != expected_run_id:
            raise SimulationResultProjectionError(
                "simulation_result_binding_run_mismatch",
                "A persisted workflow binding artifact belongs to another run",
            )
        if payload.get("schema_version") != manifest_schema_version:
            raise SimulationResultProjectionError(
                "simulation_result_binding_schema_mismatch",
                "A persisted workflow binding payload disagrees with its manifest schema version",
            )
        return payload

    def _load_json_artifact(
        self,
        ref: ArtifactRef | None,
        *,
        on_missing: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        if ref is None:
            if on_missing is not None:
                on_missing()
            return {}
        try:
            profiled = read_core_json_artifact(self._store, ref)
            payload = require_declared_profile(profiled)
        except CanonicalProfileRefusalError:
            raise
        except FileNotFoundError as exc:
            if not isinstance(self._store, RawManifestBytesReader):
                raise CanonicalProfileRefusalError(
                    "canon_profile_raw_manifest_reader_unavailable"
                ) from exc
            try:
                self._store.get_raw_manifest_bytes(ref)
            except FileNotFoundError as selected_manifest_missing:
                try:
                    self._store.get_raw_manifest_bytes(ref.artifact_id)
                except FileNotFoundError as default_manifest_missing:
                    try:
                        self._store.get_bytes(ref.artifact_id)
                    except FileNotFoundError:
                        logger.debug(
                            "Optional JSON artifact %s is unavailable: %s",
                            ref.artifact_id,
                            exc,
                        )
                        if on_missing is not None:
                            on_missing()
                        return {}
                    except CanonicalProfileRefusalError:
                        raise
                    except (TypeError, ValueError, UnicodeDecodeError) as payload_exc:
                        raise CanonicalProfileRefusalError(
                            "canon_profile_payload_unavailable"
                        ) from payload_exc
                    raise CanonicalProfileRefusalError(
                        "canon_profile_raw_manifest_unavailable"
                    ) from default_manifest_missing
                except CanonicalProfileRefusalError:
                    raise
                except (TypeError, ValueError, UnicodeDecodeError) as manifest_exc:
                    raise CanonicalProfileRefusalError(
                        "canon_profile_raw_manifest_unavailable"
                    ) from manifest_exc
                raise CanonicalProfileRefusalError(
                    "canon_profile_selection_unverified"
                ) from selected_manifest_missing
            except CanonicalProfileRefusalError:
                raise
            except (TypeError, ValueError, UnicodeDecodeError) as manifest_exc:
                raise CanonicalProfileRefusalError(
                    "canon_profile_raw_manifest_unavailable"
                ) from manifest_exc
            raise CanonicalProfileRefusalError("canon_profile_payload_unavailable") from exc
        except (TypeError, ValueError, UnicodeDecodeError) as exc:
            raise CanonicalProfileRefusalError("canon_profile_payload_nonconformant") from exc
        if not isinstance(payload, dict):
            raise CanonicalProfileRefusalError("canon_profile_payload_nonconformant")
        return payload

    def _agent_steps_from_compiled_cycle(
        self,
        run: IndexedRunRecord,
        *,
        sensitive_keys: tuple[str, ...],
    ) -> tuple[list[AgentPipelineStep], str | None]:
        """Project persisted producer events from the verified compiled-cycle artifact."""
        refs = [
            ref
            for ref in run.details.root_artifacts
            if ref.kind == "runtime.compiled_recursive_generation_cycle"
        ]
        if not refs:
            return [], None
        if len(refs) != 1:
            return [], "compiled_cycle_preflight_cost_events_not_established"

        ref = refs[0]
        try:
            verification = self._store.verify(ref)
            if not verification.ok:
                raise ValueError("compiled_cycle_integrity_not_established")
            manifest = read_core_manifest_profile(self._store, ref)[0]
            tenant_context = manifest.tenant_context
            if (
                manifest.kind != ref.kind
                or manifest.media_type != "application/json"
                or tenant_context is None
                or tenant_context.tenant_id != run.details.tenant_id
                or tenant_context.cell_id != run.details.cell_id
            ):
                raise ValueError("compiled_cycle_run_scope_binding_mismatch")
            payload_bytes = self._store.get_bytes(ref)
            expected_id = f"sha256:{hashlib.sha256(payload_bytes).hexdigest()}"
            if (
                str(ref.artifact_id) != expected_id
                or str(manifest.artifact_id) != expected_id
                or manifest.integrity.sha256 != expected_id.removeprefix("sha256:")
                or manifest.byte_size != len(payload_bytes)
                or manifest.artifact_schema is None
                or manifest.artifact_schema.name
                != "polisyos.runtime.CompiledRecursiveGenerationCycleRun"
            ):
                raise ValueError("compiled_cycle_content_binding_mismatch")

            from polisyos.runtime.http.services.control.generation_cycle import (
                CompiledRecursiveGenerationCycleRun,
            )

            profiled = read_core_json_artifact(self._store, ref, raw_payload_bytes=payload_bytes)
            compiled = CompiledRecursiveGenerationCycleRun.model_validate(profiled.value)
        except CanonicalProfileRefusalError:
            raise
        except Exception:
            return [], "compiled_cycle_preflight_cost_events_not_established"

        compiler_events = list(compiled.nl_preflight_cost_events)
        n4_events = list(compiled.n4_generation_cost_events)
        if not compiler_events and not n4_events:
            return [], None
        steps: list[AgentPipelineStep] = []
        cost_event_source = "compiled_recursive_generation_cycle"
        if compiler_events:
            steps.append(
                AgentPipelineStep(
                    attempt=1,
                    agent="design_problem_compiler",
                    action="nl_preflight",
                    status="info",
                    summary=(
                        "Traced calls made while compiling the DesignProblem "
                        "before recursive execution."
                    ),
                    details=_sanitize_payload(
                        {
                            "cost_event_source": f"{cost_event_source}.nl_preflight_cost_events",
                            "compiled_cycle_ref": str(ref.artifact_id),
                        },
                        sensitive_keys=sensitive_keys,
                    ),
                    model=compiler_events[0].model,
                    provider=compiler_events[0].provider,
                    cost_events=compiler_events,
                )
            )
        if n4_events:
            steps.append(
                AgentPipelineStep(
                    attempt=1,
                    agent="design_generation",
                    action="recursive_n4_generation",
                    status="info",
                    summary="Traced calls made by the persisted N4 candidate producer path.",
                    details=_sanitize_payload(
                        {
                            "cost_event_source": f"{cost_event_source}.n4_generation_cost_events",
                            "compiled_cycle_ref": str(ref.artifact_id),
                        },
                        sensitive_keys=sensitive_keys,
                    ),
                    model=n4_events[0].model,
                    provider=n4_events[0].provider,
                    cost_events=n4_events,
                )
            )
        return (
            steps,
            None,
        )

    def _agent_steps_from_n4_candidate_proposal(
        self,
        run: IndexedRunRecord,
        *,
        sensitive_keys: tuple[str, ...],
    ) -> tuple[list[AgentPipelineStep], str | None]:
        """Project cost events only from the exact run-owned N4 V3 proposal."""
        refs = [
            ref
            for ref in run.details.root_artifacts
            if ref.kind == "runtime.quality.n4_candidate_proposal"
        ]
        if not refs:
            return [], None
        if len(refs) != 1:
            return [], "n4_candidate_proposal_cost_events_not_established"

        ref = refs[0]
        try:
            verification = self._store.verify(ref)
            if not verification.ok:
                raise ValueError("n4_candidate_proposal_integrity_not_established")
            manifest = read_core_manifest_profile(self._store, ref)[0]
            if (
                manifest.kind != ref.kind
                or manifest.media_type != "application/json"
                or manifest.tenant_context is None
                or manifest.tenant_context.tenant_id != run.details.tenant_id
                or manifest.tenant_context.cell_id != run.details.cell_id
            ):
                raise ValueError("n4_candidate_proposal_run_scope_binding_mismatch")
            payload_bytes = self._store.get_bytes(ref)
            expected_id = f"sha256:{hashlib.sha256(payload_bytes).hexdigest()}"
            if (
                str(ref.artifact_id) != expected_id
                or str(manifest.artifact_id) != expected_id
                or manifest.integrity.sha256 != expected_id.removeprefix("sha256:")
                or manifest.byte_size != len(payload_bytes)
                or manifest.artifact_schema is None
                or manifest.artifact_schema.name
                != "policyos.runtime.quality.n4_candidate_proposal_record.v3"
            ):
                raise ValueError("n4_candidate_proposal_content_binding_mismatch")

            from polisyos.runtime.quality.generation_source import (
                N4CandidateProposalRecordV3,
                _has_n4_candidate_proposal_v3_owner_profile,
            )

            profiled = read_core_json_artifact(self._store, ref, raw_payload_bytes=payload_bytes)
            proposal = N4CandidateProposalRecordV3.model_validate(profiled.value)
            if (
                proposal.core_run_id != run.run_id
                or proposal.job_id != run.details.control_job_id
                or proposal.tenant_id != run.details.tenant_id
                or proposal.cell_id != run.details.cell_id
                or proposal.control_job_attempt is None
                or not _has_n4_candidate_proposal_v3_owner_profile(manifest, proposal)
            ):
                raise ValueError("n4_candidate_proposal_core_run_binding_mismatch")
        except CanonicalProfileRefusalError:
            raise
        except Exception:
            return [], "n4_candidate_proposal_cost_events_not_established"

        steps: list[AgentPipelineStep] = []
        if proposal.nl_preflight_cost_events:
            events = list(proposal.nl_preflight_cost_events)
            steps.append(
                AgentPipelineStep(
                    attempt=proposal.control_job_attempt,
                    agent="design_problem_compiler",
                    action="nl_preflight",
                    status="info",
                    summary=(
                        "Traced calls made while compiling the DesignProblem "
                        "before candidate generation."
                    ),
                    details=_sanitize_payload(
                        {
                            "cost_event_source": "n4_candidate_proposal.nl_preflight_cost_events",
                            "candidate_proposal_ref": str(ref.artifact_id),
                        },
                        sensitive_keys=sensitive_keys,
                    ),
                    model=events[0].model,
                    provider=events[0].provider,
                    cost_events=events,
                )
            )
        if proposal.n4_generation_cost_events:
            events = list(proposal.n4_generation_cost_events)
            steps.append(
                AgentPipelineStep(
                    attempt=proposal.control_job_attempt,
                    agent="design_generation",
                    action="n4_candidate_proposal",
                    status="info",
                    summary="Traced calls made by the persisted N4 candidate producer.",
                    details=_sanitize_payload(
                        {
                            "cost_event_source": "n4_candidate_proposal.n4_generation_cost_events",
                            "candidate_proposal_ref": str(ref.artifact_id),
                        },
                        sensitive_keys=sensitive_keys,
                    ),
                    model=events[0].model,
                    provider=events[0].provider,
                    cost_events=events,
                )
            )
        return steps, None

    def _load_manifest(self, ref: ArtifactRef | None) -> Any:
        if ref is None:
            return None
        try:
            return self._store.get_manifest(ref)
        except (
            FileNotFoundError,
            OSError,
            ValidationError,
            TypeError,
            ValueError,
        ) as exc:
            logger.debug("Failed to load manifest %s: %s", ref.artifact_id, exc)
            return None

    def _load_run_manifest_payload(self, run: IndexedRunRecord) -> dict[str, Any]:
        return self._load_json_artifact(run.details.manifest_ref)

    def _find_first_ref_by_kind(self, run: IndexedRunRecord, kind: str) -> ArtifactRef | None:
        for ref in run.details.root_artifacts:
            if ref.kind == kind:
                return ref
        manifest_payload = self._load_run_manifest_payload(run)
        for raw in _as_list_of_dicts(manifest_payload.get("outputs")):
            parsed_ref = _artifact_ref_from_payload(raw)
            if parsed_ref is not None and parsed_ref.kind == kind:
                return parsed_ref
        return None

    def _find_run_input_ref_by_kind(self, run: IndexedRunRecord, kind: str) -> ArtifactRef | None:
        manifest_payload = self._load_run_manifest_payload(run)
        for raw in _as_list_of_dicts(manifest_payload.get("inputs")):
            ref = _artifact_ref_from_payload(raw)
            if ref is not None and ref.kind == kind:
                return ref
        return None

    def _find_run_artifact_ref_by_kind(
        self,
        run: IndexedRunRecord,
        kind: str,
    ) -> ArtifactRef | None:
        """Return one unique selected run artifact view with the requested owner kind."""
        candidates = [
            ref
            for ref in (
                *getattr(run.details, "root_artifacts", ()),
                *getattr(run.details, "root_input_artifacts", ()),
            )
            if ref.kind == kind
        ]
        manifest_payload = self._load_run_manifest_payload(run)
        for field_name in ("outputs", "inputs"):
            for raw in _as_list_of_dicts(manifest_payload.get(field_name)):
                ref = _artifact_ref_from_payload(raw)
                if ref is not None and ref.kind == kind:
                    candidates.append(ref)
        selected = _merge_artifact_refs(candidates)
        return selected[0] if len(selected) == 1 else None

    def _resolve_selected_run_artifact_ref(
        self,
        run: IndexedRunRecord,
        ref: ArtifactRef,
    ) -> tuple[ArtifactRef | None, str | None]:
        """Bind a profileless run reference only when the run records one exact view."""
        if ref.manifest_profile_sha256 is not None:
            return ref, None
        recorded_refs = [
            *getattr(run.details, "root_artifacts", ()),
            *getattr(run.details, "root_input_artifacts", ()),
        ]
        manifest_payload = self._load_run_manifest_payload(run)
        for field_name in ("outputs", "inputs"):
            recorded_refs.extend(
                parsed
                for raw in _as_list_of_dicts(manifest_payload.get(field_name))
                if (parsed := _artifact_ref_from_payload(raw)) is not None
            )
        candidates = _merge_artifact_refs(
            [
                candidate
                for candidate in recorded_refs
                if candidate.artifact_id == ref.artifact_id
                and candidate.kind == ref.kind
                and candidate.media_type == ref.media_type
            ]
        )
        if len(candidates) == 1:
            return candidates[0], None
        if len(candidates) > 1:
            return None, "data_snapshot_selected_view_ambiguous"
        return None, "data_snapshot_selected_view_not_established"


def _merge_artifact_refs(*groups: list[ArtifactRef]) -> list[ArtifactRef]:
    """Deduplicate refs by complete CAS view identity."""
    refs: dict[tuple[str, str, str, str | None], ArtifactRef] = {}
    for group in groups:
        for ref in group:
            refs[artifact_ref_identity_key(ref)] = ref
    return [
        refs[key]
        for key in sorted(
            refs,
            key=lambda item: (item[0], item[1], item[2], item[3] or ""),
        )
    ]


def _nodes_from_timeline(events: list[Any]) -> list[RunNodeRecord]:
    grouped: dict[str, RunNodeRecord] = {}
    for event in events:
        if not event.phase.startswith("scientist.node."):
            continue
        alias = event.phase[len("scientist.node.") :]
        if not alias:
            continue
        existing = grouped.get(alias)
        if existing is None:
            existing = RunNodeRecord(alias=alias)
        status = existing.status
        if event.event == "NODE_OK":
            status = "ok"
        elif event.event == "NODE_SKIP":
            status = "skip"
        elif event.event == "NODE_FAIL":
            status = "fail"

        duration_ms = max(existing.duration_ms, _as_int(event.metrics.get("duration_ms")))
        grouped[alias] = existing.model_copy(
            update={
                "status": status,
                "duration_ms": duration_ms,
                "output_artifact_ids": sorted(
                    set(existing.output_artifact_ids).union(event.output_artifact_ids)
                ),
                "input_artifact_refs": _merge_artifact_refs(
                    existing.input_artifact_refs, event.input_artifact_refs
                ),
                "output_artifact_refs": _merge_artifact_refs(
                    existing.output_artifact_refs, event.output_artifact_refs
                ),
                "input_artifact_ids": sorted(
                    set(existing.input_artifact_ids).union(event.input_artifact_ids)
                ),
            }
        )
    return [grouped[key] for key in sorted(grouped)]


def _state_ref_from_param(
    state_payload: dict[str, Any],
    key: str,
    *,
    kind: str,
    media_type: str = "application/json",
) -> ArtifactRef | None:
    params = state_payload.get("params")
    value = params.get(key) if isinstance(params, dict) else None
    if value is None:
        value = state_payload.get(key)
    if isinstance(value, dict):
        return _artifact_ref_from_payload(value)
    return _artifact_ref_from_string(
        value if isinstance(value, str) else None, kind=kind, media_type=media_type
    )


def _workflow_report_nodes_by_alias(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        alias = _as_str(row.get("alias"))
        if alias:
            result[alias] = row
    return result


def _workflow_spec_nodes(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    by_alias: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in rows:
        alias = _as_str(row.get("alias"))
        if not alias:
            continue
        by_alias[alias] = row
        order.append(alias)
    return by_alias, order


def _artifact_ids_from_report_node(row: dict[str, Any] | None) -> list[str]:
    if row is None:
        return []
    ids: list[str] = []
    for raw_ref in _as_list_of_dicts(row.get("artifacts")):
        artifact_id = _as_str(raw_ref.get("artifact_id"))
        if artifact_id:
            ids.append(artifact_id)
    return sorted(set(ids))


def _simulation_result_ref_from_state_payload(
    payload: dict[str, Any],
) -> ArtifactRef | None:
    """Resolve the persisted simulation ref from a verified state payload."""
    artifacts_index = payload.get("artifacts_index")
    if not isinstance(artifacts_index, dict):
        return None
    return _artifact_ref_from_payload(artifacts_index.get(_SIMULATION_RESULT_STATE_KEY))


def _unique_workflow_report_node(
    payload: dict[str, Any],
    *,
    alias: str,
) -> dict[str, Any] | None:
    """Select one raw named node, refusing ambiguity before any node projection."""
    rows = payload.get("nodes")
    if not isinstance(rows, list):
        raise SimulationResultProjectionError(
            "simulation_result_node_binding_mismatch",
            "The workflow report has no valid node binding collection",
        )
    selected: dict[str, Any] | None = None
    for row in rows:
        row_alias = _as_str(row.get("alias")) if isinstance(row, dict) else None
        if not row_alias:
            raise SimulationResultProjectionError(
                "simulation_result_node_binding_mismatch",
                "The workflow report carries a node whose relevance cannot be established",
            )
        if row_alias != alias:
            continue
        if selected is not None:
            raise SimulationResultProjectionError(
                "simulation_result_node_binding_mismatch",
                "The named workflow node binding is ambiguous",
            )
        selected = row
    return selected


def _artifact_refs_from_report_node(
    row: dict[str, Any],
    *,
    relevant_artifact_id: ArtifactID,
) -> tuple[ArtifactRef, ...]:
    """Resolve selected-row refs without discarding a relevant malformed ref."""
    raw_artifacts = row.get("artifacts")
    if not isinstance(raw_artifacts, list):
        raise SimulationResultProjectionError(
            "simulation_result_node_binding_mismatch",
            "The named workflow node has no valid artifact binding collection",
        )
    refs: list[ArtifactRef] = []
    for raw_ref in raw_artifacts:
        ref = _artifact_ref_from_payload(raw_ref)
        if ref is not None:
            refs.append(ref)
            continue
        raw_id = _as_str(raw_ref.get("artifact_id")) if isinstance(raw_ref, dict) else None
        parsed_id = _artifact_id_from_string(raw_id)
        if parsed_id is None or parsed_id == relevant_artifact_id:
            raise SimulationResultProjectionError(
                "simulation_result_node_binding_mismatch",
                "The named workflow node carries a malformed relevant artifact ref",
            )
    return tuple(refs)


def _require_exact_artifact_ref_binding(
    expected: ArtifactRef,
    candidates: tuple[ArtifactRef, ...],
) -> None:
    """Require every same-ID node ref to carry the complete selected identity."""
    expected_identity = artifact_ref_identity_key(expected)
    if not candidates or any(
        artifact_ref_identity_key(candidate) != expected_identity for candidate in candidates
    ):
        raise SimulationResultProjectionError(
            "simulation_result_node_binding_mismatch",
            "The named workflow node carries a conflicting simulation result ref",
        )


def _workflow_edges_from_nodes(
    nodes: list[RunWorkflowNodeView],
) -> list[RunWorkflowEdgeView]:
    seen: set[tuple[str, str]] = set()
    edges: list[RunWorkflowEdgeView] = []
    aliases = {node.alias for node in nodes}
    for node in nodes:
        for parent in node.depends_on:
            if parent not in aliases:
                continue
            pair = (parent, node.alias)
            if pair in seen:
                continue
            seen.add(pair)
            edges.append(RunWorkflowEdgeView(from_alias=parent, to_alias=node.alias))
    edges.sort(key=lambda item: (item.from_alias, item.to_alias))
    return edges


def _workflow_depths(nodes: list[RunWorkflowNodeView]) -> tuple[dict[str, int], bool]:
    deps = {node.alias: list(node.depends_on) for node in nodes}
    cache: dict[str, int] = {}
    visiting: set[str] = set()
    cycle_detected = False

    def _depth(alias: str) -> int:
        nonlocal cycle_detected
        if alias in cache:
            return cache[alias]
        if alias in visiting:
            cycle_detected = True
            return 0
        visiting.add(alias)
        parents = deps.get(alias) or []
        value = 0 if not parents else 1 + max((_depth(parent) for parent in parents), default=0)
        visiting.discard(alias)
        cache[alias] = max(value, 0)
        return cache[alias]

    for alias in deps:
        _depth(alias)
    return cache, cycle_detected


def _critical_path_duration_ms(nodes: list[RunWorkflowNodeView]) -> int | None:
    if not nodes:
        return None
    node_by_alias = {node.alias: node for node in nodes}
    deps = {node.alias: list(node.depends_on) for node in nodes}
    cache: dict[str, int] = {}
    visiting: set[str] = set()

    def _duration(alias: str) -> int:
        if alias in cache:
            return cache[alias]
        if alias in visiting:
            return 0
        visiting.add(alias)
        node = node_by_alias.get(alias)
        own = node.duration_ms if node is not None else 0
        parents = deps.get(alias) or []
        if not parents:
            total = own
        else:
            total = own + max((_duration(parent) for parent in parents), default=0)
        visiting.discard(alias)
        cache[alias] = max(total, 0)
        return cache[alias]

    durations = [_duration(alias) for alias in deps]
    return max(durations, default=0)


def _retrieval_from_state_payload(
    payload: dict[str, Any],
) -> RetrievalTelemetryView | None:
    params = payload.get("params")
    if not isinstance(params, dict):
        return None

    telemetry_raw = params.get("retrieval_telemetry")
    telemetry = telemetry_raw if isinstance(telemetry_raw, dict) else {}

    mode = _as_str(telemetry.get("mode")) or _as_str(params.get("retrieval_mode"))
    lane_used = _as_str(telemetry.get("lane_used")) or _as_str(params.get("retrieval_lane_used"))
    if mode is None and lane_used is None and not telemetry:
        return None

    phases: list[RetrievalPhaseTelemetry] = []
    raw_phases = telemetry.get("phases")
    if isinstance(raw_phases, list):
        for row in raw_phases:
            if not isinstance(row, dict):
                continue
            phases.append(
                RetrievalPhaseTelemetry(
                    phase=_as_str(row.get("phase")) or "unknown",
                    lane=_as_str(row.get("lane")),
                    duration_ms=max(0, _as_int(row.get("duration_ms"))),
                    candidates_total=max(0, _as_int(row.get("candidates_total"))),
                    candidates_selected=max(0, _as_int(row.get("candidates_selected"))),
                    docs_fetched=max(0, _as_int(row.get("docs_fetched"))),
                )
            )
    if not phases:
        durations = params.get("retrieval_phase_durations")
        if isinstance(durations, dict):
            for phase_name, duration in durations.items():
                phases.append(
                    RetrievalPhaseTelemetry(
                        phase=str(phase_name),
                        lane=None,
                        duration_ms=max(0, _as_int(duration)),
                        candidates_total=0,
                        candidates_selected=0,
                        docs_fetched=0,
                    )
                )

    notes = _as_list_of_strings(telemetry.get("warnings"))
    return RetrievalTelemetryView(
        mode=mode or "hybrid",
        lane_used=lane_used or "none",
        metadata_docs_fetched=max(
            0,
            _as_int(
                telemetry.get("metadata_docs_fetched")
                if telemetry
                else params.get("retrieval_metadata_docs_fetched")
            ),
        ),
        local_index_size_bytes=max(
            0,
            _as_int(
                telemetry.get("local_index_size_bytes")
                if telemetry
                else params.get("retrieval_local_index_size_bytes")
            ),
        ),
        local_index_docs_total=max(
            0,
            _as_int(
                telemetry.get("local_index_docs_total")
                if telemetry
                else params.get("retrieval_local_index_docs_total")
            ),
        ),
        candidates_filtered=max(
            0,
            _as_int(
                telemetry.get("candidates_filtered")
                if telemetry
                else params.get("retrieval_candidates_filtered")
            ),
        ),
        candidates_promoted=max(
            0,
            _as_int(
                telemetry.get("candidates_promoted")
                if telemetry
                else params.get("retrieval_candidates_promoted")
            ),
        ),
        phases=phases,
        notes=notes,
    )


def _performance_summary_from_state_payload(
    payload: dict[str, Any],
    *,
    sensitive_keys: tuple[str, ...],
) -> dict[str, Any] | None:
    params = payload.get("params")
    if not isinstance(params, dict):
        return None
    summary = params.get("run_performance_summary")
    if not isinstance(summary, dict):
        return None
    return _sanitize_payload(summary, sensitive_keys=sensitive_keys)


def _normalize_agent(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return _AGENT_ALIASES.get(normalized, normalized)


def _status_from_agent_action(
    *,
    action: str | None,
    details: dict[str, Any],
    fallback: AgentStepStatus = "info",
) -> AgentStepStatus:
    lowered_action = (action or "").lower()
    verdict = (_as_str(details.get("verdict")) or "").lower()
    if any(token in lowered_action for token in ("fail", "error", "reject", "abort")):
        return "fail"
    if any(token in lowered_action for token in ("warn", "retry", "revise")):
        return "warn"
    if any(token in lowered_action for token in ("ok", "approve", "success", "done")):
        return "ok"
    if verdict in {"reject", "needs_revision", "abort_with_report"}:
        return "fail"
    if verdict in {"approve", "approved", "pass"}:
        return "ok"
    return fallback


def _extract_attempt(value: Any, *, fallback: int) -> int:
    parsed = _as_int(value)
    if parsed <= 0:
        return fallback
    return parsed


def _agent_steps_from_audit_trail(
    rows: list[dict[str, Any]],
    *,
    sensitive_keys: tuple[str, ...],
) -> list[AgentPipelineStep]:
    steps: list[AgentPipelineStep] = []
    current_attempt = 1
    for row in rows:
        node = _normalize_agent(_as_str(row.get("node")))
        action = _as_str(row.get("action"))
        if node is None or action is None or node == "runtime":
            continue
        details = row.get("details")
        detail_payload = details if isinstance(details, dict) else {}
        attempt = _extract_attempt(detail_payload.get("attempt"), fallback=current_attempt)

        if node == "reflexion":
            can_retry = bool(detail_payload.get("can_retry"))
            current_attempt = attempt + 1 if can_retry else max(current_attempt, attempt)
        else:
            current_attempt = max(current_attempt, attempt)

        steps.append(
            AgentPipelineStep(
                attempt=attempt,
                agent=node,
                action=action,
                status=_status_from_agent_action(action=action, details=detail_payload),
                timestamp=_as_datetime(row.get("timestamp")),
                summary=(
                    _as_str(detail_payload.get("summary"))
                    or _as_str(detail_payload.get("message"))
                    or _as_str(detail_payload.get("verdict"))
                ),
                details=_sanitize_payload(detail_payload, sensitive_keys=sensitive_keys),
                prompt=_as_str(detail_payload.get("system_prompt"))
                or _as_str(detail_payload.get("prompt")),
                response=_as_str(detail_payload.get("response"))
                or _as_str(detail_payload.get("raw_response")),
                model=_as_str(detail_payload.get("model")),
                provider=_as_str(detail_payload.get("provider")),
                model_variant_id=_as_str(detail_payload.get("model_variant_id")),
                latency_ms=_as_int_or_none(detail_payload.get("latency_ms")),
                cost_usd=detail_payload.get("cost_usd"),
                reported_cost_usd=detail_payload.get("reported_cost_usd"),
                estimated_cost_usd=detail_payload.get("estimated_cost_usd"),
                cost_events=_agent_cost_events(
                    detail_payload.get("cost_events", row.get("cost_events"))
                ),
                token_usage=_token_usage(detail_payload.get("token_usage")),
            )
        )
    return steps


def _agent_steps_from_timeline(
    events: list[Any],
    *,
    sensitive_keys: tuple[str, ...],
) -> list[AgentPipelineStep]:
    steps: list[AgentPipelineStep] = []
    for event in events:
        phase = _as_str(getattr(event, "phase", None))
        if phase is None:
            continue
        agent = _normalize_agent(_agent_from_phase(phase))
        if agent is None:
            continue
        action = _as_str(getattr(event, "event", None))
        if action is None:
            continue
        metrics = event.metrics if isinstance(event.metrics, dict) else {}
        attempt = _extract_attempt(metrics.get("attempt"), fallback=1)
        details = _sanitize_payload(metrics, sensitive_keys=sensitive_keys)
        steps.append(
            AgentPipelineStep(
                attempt=attempt,
                agent=agent,
                action=action,
                status=_status_from_agent_action(action=action, details=metrics),
                timestamp=getattr(event, "timestamp", None),
                summary=_as_str(metrics.get("summary")) or _as_str(metrics.get("verdict")),
                details=details if isinstance(details, dict) else {},
                model=_as_str(metrics.get("model")),
                provider=_as_str(metrics.get("provider")),
                model_variant_id=_as_str(metrics.get("model_variant_id")),
                latency_ms=_as_int_or_none(metrics.get("latency_ms"))
                or _as_int_or_none(metrics.get("duration_ms")),
                cost_usd=metrics.get("cost_usd"),
                reported_cost_usd=metrics.get("reported_cost_usd"),
                estimated_cost_usd=metrics.get("estimated_cost_usd"),
                cost_events=_agent_cost_events(metrics.get("cost_events")),
                token_usage=_token_usage(metrics.get("token_usage")),
            )
        )
    return steps


def _unattributed_nested_model_variant_scalars(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Keep parent cost claims visible when a variant has nested step rows."""
    params = payload.get("params")
    if not isinstance(params, dict):
        return []
    raw_variants = params.get("llm_model_variants")
    if not isinstance(raw_variants, list):
        return []

    rows: list[dict[str, Any]] = []
    for index, raw_variant in enumerate(raw_variants):
        if not isinstance(raw_variant, dict):
            continue
        nested_steps = raw_variant.get("steps")
        if not isinstance(nested_steps, list) or not nested_steps:
            continue
        for source_field in ("cost_usd", "reported_cost_usd", "estimated_cost_usd"):
            claimed_value = raw_variant.get(source_field)
            if claimed_value is None:
                continue
            rows.append(
                {
                    "source_kind": "performance_summary_variant_row",
                    "source_field": source_field,
                    "claimed_value_usd": claimed_value,
                    "scope": "not_established",
                    "attempt": max(index + 1, 1),
                    "model": _as_str(raw_variant.get("model")),
                    "model_variant_id": _as_str(raw_variant.get("model_variant_id")),
                    "source_index": index,
                }
            )
    return rows


def _model_variant_step_details(
    nested: dict[str, Any],
    *,
    sensitive_keys: tuple[str, ...],
) -> tuple[dict[str, Any], str | None]:
    """Classify one supplied model-variant details field without inventing defaults."""
    if "details" not in nested:
        return {}, None
    raw_details = nested["details"]
    if raw_details is None:
        return {}, None
    if not isinstance(raw_details, dict):
        return {}, "llm_model_variant_step_details_invalid_type_not_projected"
    sanitized = _sanitize_payload(raw_details, sensitive_keys=sensitive_keys)
    if not isinstance(sanitized, dict):
        return {}, "llm_model_variant_step_details_invalid_type_not_projected"
    return sanitized, None


def _agent_steps_from_model_variants(
    payload: dict[str, Any],
    *,
    sensitive_keys: tuple[str, ...],
) -> tuple[list[AgentPipelineStep], list[str]]:
    params = payload.get("params")
    if not isinstance(params, dict):
        return [], []
    raw_variants = params.get("llm_model_variants")
    if not isinstance(raw_variants, list):
        return [], []

    steps: list[AgentPipelineStep] = []
    notes: list[str] = []
    for index, raw_variant in enumerate(raw_variants):
        if not isinstance(raw_variant, dict):
            continue
        attempt = max(index + 1, 1)
        variant_model = _as_str(raw_variant.get("model"))
        variant_provider = _as_str(raw_variant.get("provider"))
        variant_id = _as_str(raw_variant.get("model_variant_id"))
        variant_status = _as_str(raw_variant.get("status")) or "unknown"
        variant_verdict = _as_str(raw_variant.get("verdict"))
        variant_cost = raw_variant.get("cost_usd")
        token_usage = _token_usage(
            {
                "prompt_tokens": raw_variant.get("prompt_tokens"),
                "completion_tokens": raw_variant.get("completion_tokens"),
                "total_tokens": raw_variant.get("total_tokens"),
            }
        )
        timestamp = _as_datetime(raw_variant.get("finished_at"))
        if timestamp is None:
            timestamp = _as_datetime(raw_variant.get("started_at"))

        nested_steps = raw_variant.get("steps")
        if isinstance(nested_steps, list) and nested_steps:
            for nested in nested_steps:
                if not isinstance(nested, dict):
                    continue
                nested_usage = _token_usage(nested.get("token_usage"))
                nested_prompt = _as_str(nested.get("prompt"))
                nested_response = _as_str(nested.get("response"))
                nested_details, details_note = _model_variant_step_details(
                    nested,
                    sensitive_keys=sensitive_keys,
                )
                if details_note is not None and details_note not in notes:
                    notes.append(details_note)
                raw_status = _as_str(nested.get("status"))
                nested_status = _agent_step_status(
                    raw_status,
                    fallback=_status_from_agent_action(
                        action=_as_str(nested.get("action")),
                        details=nested if isinstance(nested, dict) else {},
                    ),
                )
                steps.append(
                    AgentPipelineStep(
                        attempt=attempt,
                        agent=_normalize_agent(_as_str(nested.get("agent")) or "model_variant")
                        or "model_variant",
                        action=_as_str(nested.get("action")) or "step",
                        status=nested_status,
                        timestamp=_as_datetime(nested.get("timestamp")) or timestamp,
                        summary=_as_str(nested.get("summary")),
                        details=nested_details,
                        prompt=nested_prompt,
                        response=nested_response,
                        model=_as_str(nested.get("model")) or variant_model,
                        provider=_as_str(nested.get("provider")) or variant_provider,
                        model_variant_id=_as_str(nested.get("model_variant_id")) or variant_id,
                        latency_ms=_as_int_or_none(nested.get("latency_ms")),
                        cost_usd=nested.get("cost_usd"),
                        reported_cost_usd=nested.get("reported_cost_usd"),
                        estimated_cost_usd=nested.get("estimated_cost_usd"),
                        cost_events=_agent_cost_events(
                            nested.get("cost_events", nested_details.get("cost_events"))
                        ),
                        token_usage=nested_usage,
                    )
                )
            continue

        _, variant_details_note = _model_variant_step_details(
            raw_variant,
            sensitive_keys=sensitive_keys,
        )
        if variant_details_note is not None and variant_details_note not in notes:
            notes.append(variant_details_note)
        details = _sanitize_payload(raw_variant, sensitive_keys=sensitive_keys)
        summary_status_map: dict[str, AgentStepStatus] = {
            "completed": "ok",
            "fallback_mock": "warn",
            "budget_exceeded": "warn",
            "failed": "fail",
            "skipped_budget_guard": "warn",
        }
        summary_status = summary_status_map.get(variant_status, "info")
        steps.append(
            AgentPipelineStep(
                attempt=attempt,
                agent="model_variant",
                action=variant_status,
                status=summary_status,
                timestamp=timestamp,
                summary=variant_verdict or variant_status,
                details=details if isinstance(details, dict) else {},
                model=variant_model,
                provider=variant_provider,
                model_variant_id=variant_id,
                latency_ms=_as_int_or_none(raw_variant.get("latency_ms")),
                cost_usd=variant_cost,
                reported_cost_usd=raw_variant.get("reported_cost_usd"),
                estimated_cost_usd=raw_variant.get("estimated_cost_usd"),
                cost_events=_agent_cost_events(raw_variant.get("cost_events")),
                token_usage=token_usage,
            )
        )
    return steps, notes


def _agent_steps_from_nl_preflight(
    payload: dict[str, Any],
    *,
    sensitive_keys: tuple[str, ...],
) -> list[AgentPipelineStep]:
    """Project preflight compiler events as their own ordinary producer step."""
    params = payload.get("params")
    if not isinstance(params, dict):
        return []
    events = _agent_cost_events(params.get("nl_preflight_cost_events"))
    if not events:
        return []
    return [
        AgentPipelineStep(
            attempt=1,
            agent="design_problem_compiler",
            action="nl_preflight",
            status="info",
            summary="Traced calls made while compiling the DesignProblem before variant execution.",
            details=_sanitize_payload(
                {"cost_event_source": "params.nl_preflight_cost_events"},
                sensitive_keys=sensitive_keys,
            ),
            model=events[0].model,
            provider=events[0].provider,
            cost_events=events,
        )
    ]


def _deduplicate_agent_cost_events(
    steps: list[AgentPipelineStep],
) -> list[AgentPipelineStep]:
    """Count each producer event once across audit and experiment-state views."""
    seen: dict[str, AgentPipelineCostEvent] = {}
    deduplicated: list[AgentPipelineStep] = []
    for step in steps:
        retained: list[AgentPipelineCostEvent] = []
        for event in step.cost_events:
            prior = seen.get(event.event_id)
            if prior is not None:
                if prior != event:
                    raise ValueError("agent_pipeline_cost_event_identity_conflict")
                continue
            seen[event.event_id] = event
            retained.append(event)
        if len(retained) == len(step.cost_events):
            deduplicated.append(step)
            continue
        values = step.model_dump()
        values.update(
            {
                "cost_events": retained,
                "cost_usd": None,
                "reported_cost_usd": None,
                "estimated_cost_usd": None,
                "cost_origin": None,
                "cost_origin_counts": {},
                "settlement_status_counts": {},
                "settlement_event_ids": (),
            }
        )
        deduplicated.append(AgentPipelineStep.model_validate(values))
    return deduplicated


def _agent_from_phase(phase: str) -> str | None:
    normalized = phase.strip().lower()
    if normalized.startswith("scientist.node."):
        return None
    if normalized.startswith("scientist.agent."):
        return normalized.split(".", 2)[-1]
    for marker in _AGENT_ALIASES:
        if marker in normalized:
            return marker
    return None


def _agent_step_from_reflexion_payload(
    payload: dict[str, Any],
    *,
    sensitive_keys: tuple[str, ...],
) -> AgentPipelineStep | None:
    if not payload:
        return None
    decision = _as_str(payload.get("decision"))
    card = payload.get("card")
    card_payload = card if isinstance(card, dict) else {}
    attempt = _extract_attempt(card_payload.get("attempt_number"), fallback=1)
    details: dict[str, Any] = {}
    if card_payload:
        details["card"] = card_payload
    if payload.get("failure_history") is not None:
        details["failure_history"] = payload.get("failure_history")
    if not decision and not details:
        return None
    sanitized = _sanitize_payload(details, sensitive_keys=sensitive_keys)
    detail_payload = sanitized if isinstance(sanitized, dict) else {}
    return AgentPipelineStep(
        attempt=attempt,
        agent="reflexion",
        action=decision or "decision",
        status=_status_from_agent_action(action=decision, details=card_payload),
        timestamp=_as_datetime(card_payload.get("created_at")),
        summary=_as_str(card_payload.get("violation_summary")) or decision,
        details=detail_payload,
        model=_as_str(card_payload.get("model")),
        provider=_as_str(card_payload.get("provider")),
        model_variant_id=_as_str(card_payload.get("model_variant_id")),
        latency_ms=_as_int_or_none(card_payload.get("duration_ms")),
        cost_usd=card_payload.get("cost_usd"),
        reported_cost_usd=card_payload.get("reported_cost_usd"),
        estimated_cost_usd=card_payload.get("estimated_cost_usd"),
        token_usage=_token_usage(card_payload.get("token_usage")),
    )


def _contains_agent_step(existing: list[AgentPipelineStep], target: AgentPipelineStep) -> bool:
    return _agent_step_index(existing, target) is not None


def _agent_step_index(existing: list[AgentPipelineStep], target: AgentPipelineStep) -> int | None:
    for index, step in enumerate(existing):
        if (
            step.attempt == target.attempt
            and step.agent == target.agent
            and step.action == target.action
            and step.timestamp == target.timestamp
        ):
            return index
    return None


def _group_agent_steps_by_attempt(
    steps: list[AgentPipelineStep],
) -> list[AgentPipelineAttempt]:
    grouped: dict[int, list[AgentPipelineStep]] = defaultdict(list)
    for step in steps:
        grouped[max(step.attempt, 1)].append(step)

    attempts: list[AgentPipelineAttempt] = []
    for attempt in sorted(grouped):
        items = sorted(
            grouped[attempt],
            key=lambda item: _agent_step_sort_key(item.timestamp),
        )
        started = next(
            (item.timestamp for item in items if isinstance(item.timestamp, datetime)),
            None,
        )
        finished = next(
            (item.timestamp for item in reversed(items) if isinstance(item.timestamp, datetime)),
            None,
        )
        duration_ms = None
        if isinstance(started, datetime) and isinstance(finished, datetime):
            duration_ms = max(int((finished - started).total_seconds() * 1000), 0)

        verdict = None
        for item in reversed(items):
            if item.agent == "critic":
                verdict = item.summary or item.action
                if verdict:
                    break
            if item.agent == "reflexion":
                verdict = item.action
                if verdict:
                    break

        status = "running"
        if any(item.status == "fail" for item in items):
            status = "failed"
        elif any(item.agent == "reflexion" and "retry" in item.action.lower() for item in items):
            status = "retry"
        elif any(item.status == "ok" for item in items):
            status = "completed"

        attempts.append(
            AgentPipelineAttempt(
                attempt=attempt,
                status=status,
                verdict=verdict,
                started_at=started,
                finished_at=finished,
                duration_ms=duration_ms,
                steps=items,
                notes=[],
            )
        )
    return attempts


def _latest_attempt_verdict(attempts: list[AgentPipelineAttempt]) -> str | None:
    if not attempts:
        return None
    for attempt in reversed(attempts):
        if attempt.verdict:
            return attempt.verdict
    return None


def _agent_step_sort_key(value: datetime | None) -> datetime:
    """Normalize mixed or absent timestamps before ordering persisted steps."""
    if value is None:
        return datetime.max.replace(tzinfo=UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _agent_cost_events(value: object) -> list[AgentPipelineCostEvent]:
    """Parse lossless producer events from a persisted pipeline step."""
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError("agent_pipeline_cost_events_invalid")
    events: list[AgentPipelineCostEvent] = []
    for raw_event in value:
        if not isinstance(raw_event, dict):
            raise ValueError("agent_pipeline_cost_event_invalid")
        event = dict(raw_event)
        if "payload_digest" not in event:
            event["payload_digest"] = event.get("producer_payload_digest")
        if "durability" not in event:
            event["durability"] = event.get("settlement_durability", "none")
        if "receipts" not in event:
            event["receipts"] = event.get("settlement_receipts", ())
        events.append(AgentPipelineCostEvent.model_validate(event))
    return events


def _as_int_or_none(value: Any) -> int | None:
    parsed = _as_int(value)
    return parsed if parsed > 0 else None


def _as_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except TypeError, ValueError:
        return None
    return max(parsed, 0.0)


def _token_usage(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        prompt = _as_int(value.get("prompt_tokens"))
        completion = _as_int(value.get("completion_tokens"))
        total = _as_int(value.get("total_tokens"))
        out: dict[str, int] = {}
        if prompt > 0:
            out["prompt_tokens"] = prompt
        if completion > 0:
            out["completion_tokens"] = completion
        if total > 0:
            out["total_tokens"] = total
        return out

    if isinstance(value, (int, float)):
        total = _as_int(value)
        return {"total_tokens": total} if total > 0 else {}
    return {}


def _merge_workflow_nodes_with_timeline(
    nodes: list[RunNodeRecord], timeline_events: list[Any]
) -> list[RunNodeRecord]:
    from_timeline = {node.alias: node for node in _nodes_from_timeline(timeline_events)}
    merged: list[RunNodeRecord] = []
    for node in nodes:
        timeline_node = from_timeline.get(node.alias)
        if timeline_node is None:
            merged.append(node)
            continue
        merged.append(
            node.model_copy(
                update={
                    "input_artifact_ids": (
                        node.input_artifact_ids
                        if node.input_artifact_ids
                        else timeline_node.input_artifact_ids
                    ),
                    "output_artifact_ids": (
                        node.output_artifact_ids
                        if node.output_artifact_ids
                        else timeline_node.output_artifact_ids
                    ),
                    "input_artifact_refs": _merge_artifact_refs(
                        node.input_artifact_refs, timeline_node.input_artifact_refs
                    ),
                    "output_artifact_refs": _merge_artifact_refs(
                        node.output_artifact_refs, timeline_node.output_artifact_refs
                    ),
                    "artifact_ids": sorted(
                        set(node.artifact_ids).union(timeline_node.output_artifact_ids)
                    ),
                }
            )
        )
    merged.sort(key=lambda item: item.alias)
    return merged


def _extract_validation_trace(payload: dict[str, Any]) -> dict[str, Any] | None:
    params = payload.get("params")
    if not isinstance(params, dict):
        return None
    trace = params.get("validation_trace")
    return trace if isinstance(trace, dict) else None


def _extract_report_ref(payload: dict[str, Any], key: str) -> ArtifactRef | None:
    reports_index = payload.get("reports_index")
    if not isinstance(reports_index, dict):
        return None
    raw_ref = reports_index.get(key)
    if not isinstance(raw_ref, dict):
        return None
    try:
        parsed_ref: ArtifactRef = ArtifactRef.model_validate(raw_ref)
        return parsed_ref
    except (TypeError, ValueError) as exc:
        logger.debug("Failed to parse report ref for key %s: %s", key, exc)
        return None


def _iter_trace_records(path: Path) -> Iterator[TraceRecord]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield TraceRecord.model_validate_json(stripped)
            except (ValueError, TypeError) as exc:
                logger.debug("Failed to parse trace record in %s: %s", path, exc)
                continue


def _error_sort_key(error: RunErrorView) -> tuple[float, str, str]:
    if isinstance(error.timestamp, datetime):
        return (error.timestamp.timestamp(), error.source, error.code)
    return (float("inf"), error.source, error.code)


def _normalize_status(raw: str | None) -> NodeStatus:
    if raw in {"ok", "skip", "fail", "unknown"}:
        return cast("NodeStatus", raw)
    return "unknown"


def _as_int(value: Any) -> int:
    try:
        parsed = int(value)
    except TypeError, ValueError:
        return 0
    return max(parsed, 0)


def _as_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_float(value: Any, *, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except TypeError, ValueError:
        return default
    return max(parsed, 0.0)


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _artifact_ref_from_string(
    value: str | None,
    *,
    kind: str,
    media_type: str = "application/json",
) -> ArtifactRef | None:
    artifact_id = _artifact_id_from_string(value)
    if artifact_id is None:
        return None
    return ArtifactRef(artifact_id=artifact_id, kind=kind, media_type=media_type)


def _materialization_refs_from_payload(value: dict[str, Any]) -> dict[str, ArtifactRef]:
    refs: dict[str, ArtifactRef] = {}
    for key, kind in _MATERIALIZATION_REF_KINDS.items():
        ref = _artifact_ref_from_string(_as_str(value.get(key)), kind=kind)
        if ref is not None:
            refs[key] = ref
    return refs


def _artifact_ownership_evidence_from_store(
    store: object,
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
    return dict(payload) if isinstance(payload, dict) else None


def _path_get_as_str(payload: dict[str, Any], path: tuple[str, ...]) -> str | None:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _as_str(current)


def _string_list_dict(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, raw in value.items():
        items = _as_list_of_strings(raw)
        if items:
            result[str(key)] = items
    return result


def _dedupe_artifact_refs(refs: list[ArtifactRef | None]) -> list[ArtifactRef]:
    result: list[ArtifactRef] = []
    seen: set[tuple[str, str, str, str | None]] = set()
    for ref in refs:
        if ref is None:
            continue
        identity = (
            str(ref.artifact_id),
            ref.kind,
            ref.media_type,
            ref.manifest_profile_sha256,
        )
        if identity in seen:
            continue
        seen.add(identity)
        result.append(ref)
    return result


def _state_input_ref(
    state_payload: dict[str, Any],
    key: str,
    *,
    expected_kind: str,
) -> tuple[ArtifactRef | None, str | None]:
    """Read a persisted full ref from ExperimentState.inputs without ID fallback."""
    if "inputs" not in state_payload:
        return None, None
    inputs = state_payload.get("inputs")
    if not isinstance(inputs, dict):
        return None, f"state_inputs_not_established:{key}"
    if key not in inputs:
        return None, None
    raw_ref = inputs[key]
    if not isinstance(raw_ref, dict):
        return None, f"state_input_ref_malformed:{key}"
    try:
        ref = ArtifactRef.model_validate(raw_ref)
    except TypeError, ValueError, ValidationError:
        return None, f"state_input_ref_malformed:{key}"
    if ref.kind != expected_kind or ref.media_type != "application/json":
        return None, f"state_input_ref_kind_mismatch:{key}"
    return ref, None


def _workflow_data_view_request_profile_origin(
    *,
    store: ArtifactStore,
    control_job_store: _ReadOnlyControlJobStore | None,
    control_job_id: str | None,
    state_payload: dict[str, Any],
) -> tuple[
    Literal["caller_selected", "worker_default", "not_requested", "not_established"],
    str | None,
]:
    """Bind profile-origin status to immutable workflow-job input and actual lineage."""
    from polisyos.runtime.http.services._control_contracts import (
        _WORKFLOW_DATA_VIEW_REQUEST_INTENT_KEY,
        WorkflowDataViewRequestIntent,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        ControlJobExecutionAdmissionError,
        _json_values_equal_strict,
    )

    not_established = (
        "not_established",
        "data_view_request_profile_origin_not_established",
    )
    if (
        not isinstance(control_job_id, str)
        or not control_job_id.strip()
        or control_job_store is None
    ):
        return not_established
    try:
        job = control_job_store.get_job(control_job_id)
        if job is None:
            return not_established
        event_payload = control_job_store.get_job_created_event_payload(control_job_id)
        outbox_event = control_job_store.get_job_created_outbox_event(control_job_id)
    except (
        ControlJobExecutionAdmissionError,
        OSError,
        PermissionError,
        RuntimeError,
        TypeError,
        ValueError,
    ):
        return not_established

    outbox_payload = getattr(outbox_event, "payload", None)
    expected_job_fields = {
        "job_id": job.job_id,
        "run_id": job.run_id,
        "job_kind": job.kind,
        "pipeline_id": job.pipeline_id,
        "payload_ref": job.payload_ref,
        "submitted_by": job.submitted_by,
        "requested_execution_profile": job.requested_execution_profile,
        "effective_execution_profile": job.effective_execution_profile,
        "policy_flags": job.policy_flags,
    }
    if (
        job.job_id != control_job_id
        or job.kind != "workflow_run"
        or not isinstance(job.run_id, str)
        or job.run_id != state_payload.get("run_id")
        or getattr(outbox_event, "topic", None) != "control.job.created"
        or getattr(outbox_event, "job_id", None) != job.job_id
        or getattr(outbox_event, "run_id", None) != job.run_id
        or not isinstance(outbox_payload, dict)
        or not _json_values_equal_strict(outbox_payload, event_payload)
        or any(
            field not in event_payload
            or not _json_values_equal_strict(event_payload[field], expected)
            for field, expected in expected_job_fields.items()
        )
        or not isinstance(job.payload_ref, str)
        or not job.payload_ref
    ):
        return not_established

    try:
        payload_ref = ArtifactRef(
            artifact_id=ArtifactID.model_validate(job.payload_ref),
            kind="runtime.control_job_payload.workflow_run",
            media_type="application/json",
        )
        verification = store.verify(payload_ref)
        manifest = read_core_manifest_profile(store, payload_ref)[0]
        schema = manifest.artifact_schema
        payload = read_core_json_artifact(store, payload_ref).value
    except (
        FileNotFoundError,
        OSError,
        PermissionError,
        RuntimeError,
        TypeError,
        ValueError,
    ):
        return not_established
    if (
        not verification.ok
        or manifest.artifact_id != payload_ref.artifact_id
        or manifest.kind != payload_ref.kind
        or manifest.media_type != payload_ref.media_type
        or schema is None
        or schema.name != "polisyos.runtime.ControlJobPayload"
        or schema.version != "1.0"
        or not isinstance(payload, dict)
        or payload.get("run_id") != job.run_id
    ):
        return not_established

    original_state = payload.get("state_payload")
    if not isinstance(original_state, dict) or original_state.get("run_id") != job.run_id:
        return not_established
    original_inputs = original_state.get("inputs")
    current_inputs = state_payload.get("inputs")
    if not isinstance(original_inputs, dict) or not isinstance(current_inputs, dict):
        return not_established
    has_original_request = "data_view_request_ref" in original_inputs
    has_current_request = "data_view_request_ref" in current_inputs
    has_intent = _WORKFLOW_DATA_VIEW_REQUEST_INTENT_KEY in payload
    if not has_original_request:
        if has_current_request or has_intent:
            return not_established
        return "not_requested", None
    if not has_current_request or not has_intent:
        return not_established
    try:
        original_ref = ArtifactRef.model_validate(original_inputs["data_view_request_ref"])
        current_ref = ArtifactRef.model_validate(current_inputs["data_view_request_ref"])
        intent = WorkflowDataViewRequestIntent.model_validate(
            payload[_WORKFLOW_DATA_VIEW_REQUEST_INTENT_KEY]
        )
    except TypeError, ValueError, ValidationError:
        return not_established
    if (
        original_ref.kind != "ir.data_view_request"
        or original_ref.media_type != "application/json"
        or current_ref.kind != "ir.data_view_request"
        or current_ref.media_type != "application/json"
        or original_ref.artifact_id != current_ref.artifact_id
        or current_ref.manifest_profile_sha256 is None
    ):
        return not_established
    if intent.profile_origin == "caller_selected":
        if (
            original_ref.manifest_profile_sha256 is None
            or original_ref.manifest_profile_sha256 != current_ref.manifest_profile_sha256
        ):
            return not_established
        return "caller_selected", None
    if intent.profile_origin == "worker_default" and original_ref.manifest_profile_sha256 is None:
        return "worker_default", None
    return not_established


def _data_view_request_ref_from_snapshot(
    store: ArtifactStore,
    snapshot_ref: ArtifactRef,
    *,
    expected_request_ref: ArtifactRef | None = None,
) -> tuple[ArtifactRef | None, str | None]:
    """Resolve and validate one request through the selected snapshot profile."""
    if snapshot_ref.kind != "fabric.data_snapshot" or snapshot_ref.media_type != "application/json":
        return None, "data_snapshot_ref_kind_mismatch"
    if snapshot_ref.manifest_profile_sha256 is None:
        return None, "data_snapshot_profile_not_established"
    try:
        if not store.verify(snapshot_ref).ok:
            return None, "data_snapshot_integrity_failed"
        snapshot_manifest = resolve_manifest_by_profile(
            store,
            snapshot_ref.artifact_id,
            snapshot_ref.manifest_profile_sha256,
        )
    except Exception:
        return None, "data_snapshot_profile_resolution_failed"
    if (
        str(snapshot_manifest.artifact_id) != str(snapshot_ref.artifact_id)
        or snapshot_manifest.kind != "fabric.data_snapshot"
        or snapshot_manifest.media_type != "application/json"
    ):
        return None, "data_snapshot_manifest_identity_mismatch"
    request_edges = [
        edge for edge in snapshot_manifest.inputs if edge.role == "data_view_request_ref"
    ]
    if len(request_edges) != 1:
        reason = "missing" if not request_edges else "ambiguous"
        return None, f"data_view_request_edge_{reason}"
    edge = request_edges[0]
    if edge.manifest_profile_sha256 is None:
        return None, "data_view_request_profile_not_established"
    try:
        request_manifest = resolve_manifest_by_profile(
            store,
            edge.artifact_id,
            edge.manifest_profile_sha256,
        )
    except Exception:
        return None, "data_view_request_profile_resolution_failed"
    if (
        str(request_manifest.artifact_id) != str(edge.artifact_id)
        or request_manifest.kind != "ir.data_view_request"
        or request_manifest.media_type != "application/json"
    ):
        return None, "data_view_request_manifest_kind_mismatch"
    selected_request_ref = ArtifactRef(
        artifact_id=edge.artifact_id,
        kind=request_manifest.kind,
        media_type=request_manifest.media_type,
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )
    try:
        if not store.verify(selected_request_ref).ok:
            return None, "data_view_request_integrity_failed"
    except FileNotFoundError, OSError, PermissionError, TypeError, ValueError:
        return None, "data_view_request_integrity_failed"
    if expected_request_ref is not None and _artifact_ref_identity_key(
        expected_request_ref
    ) != _artifact_ref_identity_key(selected_request_ref):
        return None, "data_view_request_ref_does_not_match_snapshot_lineage"

    schema = request_manifest.artifact_schema
    if schema is None or schema.name != "polisyos.ir.DataViewRequest" or schema.version != "1.0":
        return None, "data_view_request_schema_not_supported"
    try:
        request_payload = get_ir_json_artifact(store, selected_request_ref)
    except CanonViolation:
        return None, "data_view_request_profile_not_established"
    except FileNotFoundError, TypeError, ValueError:
        return None, "data_view_request_payload_unavailable"
    if not isinstance(request_payload, dict):
        return None, "data_view_request_payload_invalid"
    valid_models = 0
    try:
        QueryDataViewRequest.model_validate(request_payload)
    except TypeError, ValueError, ValidationError:
        pass
    else:
        valid_models += 1
    try:
        AnalyticsDataViewRequest.model_validate(request_payload)
    except TypeError, ValueError, ValidationError:
        pass
    else:
        valid_models += 1
    if valid_models != 1:
        reason = "ambiguous" if valid_models > 1 else "invalid"
        return None, f"data_view_request_payload_{reason}"
    return selected_request_ref, None


def _artifact_ref_identity_key(ref: ArtifactRef) -> tuple[str, str, str, str | None]:
    return (
        str(ref.artifact_id),
        ref.kind,
        ref.media_type,
        ref.manifest_profile_sha256,
    )


def _dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _summarize_issue_counts(issues: list[dict[str, Any]]) -> dict[str, int]:
    blocker_count = 0
    warning_count = 0
    info_count = 0
    for issue in issues:
        severity = (_as_str(issue.get("severity")) or "").lower()
        if severity == "blocker":
            blocker_count += 1
        elif severity == "warning":
            warning_count += 1
        elif severity == "info":
            info_count += 1
    return {
        "blocker_count": blocker_count,
        "warning_count": warning_count,
        "info_count": info_count,
    }


def _legal_executed_from_governance(payload: dict[str, Any]) -> bool | None:
    links = payload.get("links")
    if not isinstance(links, dict):
        return None
    legal_ref = links.get("legal_report_ref")
    if isinstance(legal_ref, dict):
        return _as_str(legal_ref.get("artifact_id")) is not None
    return isinstance(legal_ref, str)


def _legal_executed_from_packet(payload: dict[str, Any]) -> bool | None:
    diagnostics = payload.get("diagnostics_summary")
    if isinstance(diagnostics, dict) and isinstance(diagnostics.get("legal_executed"), bool):
        return bool(diagnostics.get("legal_executed"))
    return None


def _contract_warnings_from_packet(payload: dict[str, Any]) -> list[str]:
    diagnostics = payload.get("diagnostics_summary")
    if not isinstance(diagnostics, dict):
        return []
    return _as_list_of_strings(diagnostics.get("contract_warnings"))


def _normative_summary_from_packet(payload: dict[str, Any]) -> dict[str, Any] | None:
    diagnostics = payload.get("diagnostics_summary")
    tradeoff = payload.get("tradeoff_certificate")
    if not isinstance(diagnostics, dict) and not isinstance(tradeoff, dict):
        return None
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    tradeoff = tradeoff if isinstance(tradeoff, dict) else {}
    return {
        "selected_policy": diagnostics.get("normative_selected_policy")
        or tradeoff.get("selected_policy"),
        "selected_option": diagnostics.get("normative_selected_option")
        or tradeoff.get("selected_option"),
        "model_completeness": diagnostics.get("normative_model_completeness"),
        "residual_dissent_count": diagnostics.get("normative_residual_dissent_count"),
        "rights_violation_count": diagnostics.get("normative_rights_violation_count"),
        "winners": _as_list_of_strings(tradeoff.get("winners")),
        "losers": _as_list_of_strings(tradeoff.get("losers")),
    }


def _artifact_ref_from_packet(payload: dict[str, Any], key: str) -> ArtifactRef | None:
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    return _artifact_ref_from_payload(artifacts.get(key))


def _transport_summary_from_packet(payload: dict[str, Any]) -> dict[str, Any] | None:
    causal = payload.get("causal")
    if not isinstance(causal, dict):
        return None
    transport = causal.get("transportability_summary")
    return dict(transport) if isinstance(transport, dict) else None


def _governance_links_from_payload(
    payload: dict[str, Any],
) -> dict[str, ArtifactRef | None] | None:
    links = payload.get("links")
    if not isinstance(links, dict):
        return None
    result: dict[str, ArtifactRef | None] = {}
    for key, value in links.items():
        result[str(key)] = _artifact_ref_from_payload(value)
    return result or None


def _artifact_ref_from_payload(value: Any) -> ArtifactRef | None:
    if isinstance(value, dict):
        try:
            parsed_ref: ArtifactRef = ArtifactRef.model_validate(value)
            return parsed_ref
        except (TypeError, ValueError) as exc:
            logger.debug("Failed to parse generic artifact ref payload %s: %s", value, exc)
            return None
    if isinstance(value, str):
        return _artifact_ref_from_string(
            value,
            kind="artifact.unknown",
            media_type="application/json",
        )
    return None


def _agent_step_status(
    value: str | None,
    *,
    fallback: AgentStepStatus = "info",
) -> AgentStepStatus:
    if value in {"ok", "warn", "fail", "info"}:
        return cast("AgentStepStatus", value)
    return fallback


def _as_evaluator_verdict(value: Any) -> EvaluatorVerdict | None:
    if value in {
        "APPROVE",
        "REPLAN_DATA",
        "REPLAN_METHOD",
        "REPLAN_PARAMS",
        "STOP_BUDGET",
    }:
        return cast("EvaluatorVerdict", value)
    return None


def _as_iteration_lifecycle_state(value: Any) -> IterationLifecycleState:
    if value in {
        "plan_created",
        "preflight_running",
        "preflight_failed",
        "ready_to_run",
        "executing",
        "evaluating",
        "replanning",
        "approved",
        "stopped_budget",
        "stopped_no_delta",
        "stopped_guardrail",
    }:
        return cast("IterationLifecycleState", value)
    return "plan_created"


def _as_stop_reason(value: Any) -> StopReason | None:
    if value in {"approved", "budget_exhausted", "no_delta", "guardrail_violation"}:
        return cast("StopReason", value)
    return None


def _artifact_id_from_string(value: str | None) -> ArtifactID | None:
    if not value:
        return None
    try:
        parsed_id: ArtifactID = ArtifactID.model_validate(value)
        return parsed_id
    except (TypeError, ValueError, ValidationError) as exc:
        logger.debug("Failed to parse artifact id %s: %s", value, exc)
        return None


def _has_replay_payload(payload: dict[str, Any]) -> bool:
    replay = payload.get("replay")
    return isinstance(replay, dict)


def _replay_value(payload: dict[str, Any], key: str) -> str | None:
    replay = payload.get("replay")
    if not isinstance(replay, dict):
        return None
    return _as_str(replay.get(key))


def _replay_list(payload: dict[str, Any], key: str) -> list[str]:
    replay = payload.get("replay")
    if not isinstance(replay, dict):
        return []
    return _as_list_of_strings(replay.get(key))


def _as_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            result.append(item)
    return result


def _as_list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if item is None:
            continue
        result.append(str(item))
    return result


def _sanitize_payload(value: Any, *, sensitive_keys: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            lowered_key = str(key).lower()
            if any(marker in lowered_key for marker in sensitive_keys):
                sanitized[str(key)] = "[REDACTED]"
            else:
                sanitized[str(key)] = _sanitize_payload(item, sensitive_keys=sensitive_keys)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_payload(item, sensitive_keys=sensitive_keys) for item in value]
    if isinstance(value, str):
        return _sanitize_string(value)
    return value


def _sanitize_string(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.lower()
    if "bearer " in lowered:
        return "[REDACTED]"
    if lowered.startswith("eyj") and len(value) >= 32:
        return "[REDACTED]"
    return value
