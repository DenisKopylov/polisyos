"""Control Plane service — bridges HTTP layer to scientist/fabric."""

from __future__ import annotations

import time
import uuid
from collections.abc import Mapping
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from opentelemetry.context import attach, detach

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.async_store import ensure_async_artifact_store
from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
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
    DataCatalogSearchResponse,
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
from polisyos.core.contracts.decision_validity import DecisionDependencyEvent
from polisyos.core.observability import get_metrics, get_tracer
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.errors import forbidden, unprocessable_entity
from polisyos.runtime.http.execution_policy import (
    ExecutionProfileError,
    PolicyFlagForbiddenError,
    ResolvedExecutionPolicy,
    RuntimeExecutionPolicyResolver,
    RuntimePrincipal,
    build_capability_manifest_payload,
)
from polisyos.runtime.http.resilience import guard_runtime_cas, guard_runtime_control_store
from polisyos.runtime.http.services.control.admission import (
    _record_control_plane_job_admission_metric,
    _record_control_plane_job_execution_metric,
)
from polisyos.runtime.http.services.control.artifacts import (
    _artifact_ref_from_summary_payload,
    _make_artifact_ref,
    _resolve_curated_dir,
)
from polisyos.runtime.http.services.control.capabilities import CapabilityManifestMixin
from polisyos.runtime.http.services.control.lex_pipeline import LexPipelineMixin
from polisyos.runtime.http.services.control.nl_pipeline import NaturalLanguageRunMixin
from polisyos.runtime.http.services.control.response_shapes import (
    _decision_validity_dedupe_payload,
)
from polisyos.runtime.quality.diagnostic_events import (
    DIAGNOSTIC_EVENT_SCHEMA_NAME,
    DIAGNOSTIC_EVENT_SCHEMA_VERSION,
    SERIOUS_EXECUTION_PROFILES,
    DiagnosticEvent,
)
from polisyos.runtime.quality.event_log import (
    DiagnosticEventPayloadPolicy,
    RuntimeDiagnosticEventLog,
)
from polisyos.runtime.quality.source_truth import (
    SourceTruthContractError,
    detect_source_truth_conflict,
)
from polisyos.scientist.orchestration.llm.provider_verification import run_provider_preflight
from polisyos.scientist.validation.decision_validity import DecisionValidityService

from .._control_contracts import (
    _DATA_SOURCE_KEYS,
    _OPTIONAL_INPUT_KEYS,
    _build_api_meta,
    _coerce_control_job_kind,
    _coerce_optional_execution_profile,
    _coerce_retrieval_mode,
    _dedupe_models,
    _is_multimodel_enabled,
    _is_required_preflight_enabled,
    _resolve_data_source,
)
from ..control_plane_store import ControlJobRecord, ControlPlaneStore
from ..control_worker import ControlWorker

logger = get_logger(__name__)
_SERIOUS_EXECUTION_PROFILES = frozenset({"research", "governed", "production"})


def _default_runtime_metrics() -> Any:
    return get_metrics()


def _default_runtime_tracer() -> Any:
    return get_tracer()


def _clean_runtime_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.core.artifacts.protocol import ArtifactStore, AsyncArtifactStore
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
    from polisyos.fabric.connectors.registry import ConnectorRegistry

    from ..control_registry_providers import ControlRegistryProviders


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ControlPlaneService(CapabilityManifestMixin, LexPipelineMixin, NaturalLanguageRunMixin):
    """Bridge HTTP control requests to durable jobs and domain pipelines."""

    def __init__(
        self,
        *,
        cas_root: Path,
        core_runs_root: Path,
        metrics: Any | None = None,
        tracer: Any | None = None,
        artifact_store: ArtifactStore | None = None,
        async_artifact_store: AsyncArtifactStore | None = None,
        control_store: ControlPlaneStore | None = None,
        retrieval_service: Any | None = None,
        policy_resolver: RuntimeExecutionPolicyResolver | None = None,
        registry_providers: ControlRegistryProviders | None = None,
    ) -> None:
        from polisyos.fabric.retrieval import RetrievalService

        self._cas_root = cas_root
        self._core_runs_root = core_runs_root
        self._metrics = metrics if metrics is not None else _default_runtime_metrics()
        self._tracer = tracer if tracer is not None else _default_runtime_tracer()
        self._policy_resolver = policy_resolver or RuntimeExecutionPolicyResolver.from_env()
        if registry_providers is None:
            raise ValueError(
                "ControlPlaneService requires typed registry_providers from the "
                "runtime composition root"
            )
        self._registry_providers = registry_providers
        self._owns_artifact_store = artifact_store is None
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
        else:
            self._artifact_store = artifact_store
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
        self._diagnostic_event_log = RuntimeDiagnosticEventLog(
            store=self._control_store,
            artifact_store=self._artifact_store,
        )

        self._retrieval = retrieval_service or RetrievalService(
            curated_dir=_resolve_curated_dir(),
            cas_root=cas_root,
            providers=self._build_retrieval_providers(),
        )
        self._worker: ControlWorker | None = None
        if self._policy_resolver.worker_backend == "embedded":
            self._worker = ControlWorker(
                store=self._control_store,
                handler=self._process_control_job,
            )
            self._worker.start()

    def close(self) -> None:
        """Stop embedded workers and release durable control-plane resources."""
        if self._worker is not None:
            self._worker.stop()
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

    def _build_retrieval_providers(self) -> Any:
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

    def _put_json_artifact(self, payload: Any, *, kind: str, schema_name: str) -> str:
        ref = self._artifact_store.put_json(
            payload,
            ArtifactWriteOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(name=schema_name, version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        return str(ref.artifact_id)

    def _persist_job_payload(
        self,
        *,
        job_kind: str,
        payload: dict[str, Any],
    ) -> str:
        return self._put_json_artifact(
            payload,
            kind=f"runtime.control_job_payload.{job_kind}",
            schema_name="polisyos.runtime.ControlJobPayload",
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
            "parent_span_id": str(parent_span_id or span_id or stored_parent_span_id or "")
            or None,
        }

    def _emit_runtime_diagnostic_event(
        self,
        *,
        job_id: str,
        run_id: str | None,
        execution_profile: str,
        phase: str,
        event_type: str,
        state_before: str | None = None,
        state_after: str | None = None,
        payload: Mapping[str, Any] | None = None,
        event_payload: Mapping[str, Any] | None = None,
        artifact_refs: list[str] | tuple[str, ...] | None = None,
        input_refs: list[str] | tuple[str, ...] | None = None,
        blocking_status: str | None = None,
        authority_bearing_payload: bool = False,
        producer_component: str = "polisyos.runtime.control",
        parent_span_id: str | None = None,
    ) -> str | None:
        """Emit a durable runtime diagnostic event and return its event id."""

        trace = self._job_trace_context(
            job_id=job_id,
            payload=payload,
            parent_span_id=parent_span_id,
        )
        tenant_id = _clean_runtime_text((payload or {}).get("tenant_id")) or "tenant-unknown"
        cell_id = _clean_runtime_text((payload or {}).get("cell_id")) or "cell-unknown"
        event = DiagnosticEvent(
            event_id=f"evt_{uuid.uuid4().hex[:24]}",
            event_source="polisyos.runtime.control",
            event_type=event_type,
            event_time=datetime.now(UTC).replace(microsecond=0),
            event_subject=f"run/{run_id or 'run-unknown'}/job/{job_id}/phase/{phase}",
            schema_name=DIAGNOSTIC_EVENT_SCHEMA_NAME,
            schema_version=DIAGNOSTIC_EVENT_SCHEMA_VERSION,
            trace_id=str(trace["trace_id"]),
            span_id=str(trace["span_id"]),
            parent_span_id=(
                str(trace["parent_span_id"]) if trace.get("parent_span_id") else None
            ),
            run_id=str(run_id or "run-unknown"),
            job_id=job_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            producer_component=producer_component,
            producer_version="2026.05.15+hds-phase2.2",
            execution_profile=execution_profile,
            phase=phase,
            state_before=state_before,
            state_after=state_after,
            payload_ref=None,
            artifact_refs=tuple(artifact_refs or ()),
            input_refs=tuple(input_refs or ()),
            blocking_status=blocking_status,
            redaction_policy_ref="redaction-policy/runtime-diagnostics-v1",
            duplicate_of=None,
            dedupe_key=None,
            sampling_decision="always_record",
            sampling_rate=1.0,
        )
        try:
            record = self._diagnostic_event_log.append(
                event,
                payload=event_payload,
                payload_policy=DiagnosticEventPayloadPolicy(
                    authority_bearing=authority_bearing_payload
                ),
            )
        except Exception as exc:  # pragma: no cover - diagnostics cannot mask dev jobs
            if execution_profile.strip().casefold() in SERIOUS_EXECUTION_PROFILES:
                raise RuntimeError(
                    f"runtime_diagnostic_event_persistence_failed:{job_id}:{phase}"
                ) from exc
            logger.debug(
                "Failed to persist runtime diagnostic event for job %s phase %s: %s",
                job_id,
                phase,
                exc,
            )
            return None
        return str(record.event.event_id)

    def _attach_job_actor_scope(
        self,
        payload: dict[str, Any],
        *,
        policy: ResolvedExecutionPolicy,
    ) -> dict[str, Any]:
        scoped_payload = dict(payload)
        tenant_id = policy.actor.get("tenant_id")
        cell_id = policy.actor.get("cell_id")
        if isinstance(tenant_id, str) and tenant_id:
            scoped_payload["tenant_id"] = tenant_id
        if isinstance(cell_id, str) and cell_id:
            scoped_payload["cell_id"] = cell_id
        return scoped_payload

    @contextmanager
    def _job_tenant_scope(self, payload: dict[str, Any]) -> Any:
        tenant_id = payload.get("tenant_id")
        cell_id = payload.get("cell_id")
        if not isinstance(tenant_id, str) or not tenant_id:
            with nullcontext():
                yield
            return
        with tenant_scope(
            None,
            tenant_id=tenant_id,
            cell_id=cell_id if isinstance(cell_id, str) and cell_id else None,
        ):
            yield

    @contextmanager
    def _control_job_span(
        self,
        *,
        job: ControlJobRecord,
        payload: dict[str, Any],
    ) -> Any:
        telemetry = payload.get("_telemetry") if isinstance(payload, dict) else None
        request_id = None
        token = None
        if isinstance(telemetry, dict):
            request_id = telemetry.get("request_id")
            carrier = telemetry.get("trace_context")
            extract_context = getattr(self._tracer, "extract_context", None)
            if isinstance(carrier, dict) and carrier and callable(extract_context):
                token = attach(
                    cast(
                        "Any",
                        extract_context({str(key): str(value) for key, value in carrier.items()}),
                    )
                )
        queue_lag_seconds = max(
            (datetime.now(UTC) - job.created_at).total_seconds(),
            0.0,
        )
        started = time.perf_counter()
        status = "success"
        with self._tracer.start_as_current_span(
            "runtime.control.job.execute",
            attributes={
                "runtime.control.job_id": job.job_id,
                "runtime.control.job_kind": job.kind,
                "runtime.control.run_id": job.run_id or "",
                "runtime.control.pipeline_id": job.pipeline_id or "",
                "runtime.control.request_id": str(request_id or ""),
            },
        ):
            try:
                yield
            except Exception:
                status = "error"
                raise
            finally:
                _record_control_plane_job_execution_metric(
                    metrics=self._metrics,
                    job_kind=job.kind,
                    status=status,
                    duration_seconds=time.perf_counter() - started,
                    queue_lag_seconds=queue_lag_seconds,
                )
                if token is not None:
                    detach(token)

    def _persist_capability_manifest(
        self,
        *,
        policy: ResolvedExecutionPolicy,
        job_id: str,
        run_id: str | None,
        pipeline_id: str | None,
        payload_ref: str | None,
        observed_fallbacks: list[str] | None = None,
    ) -> str:
        payload = build_capability_manifest_payload(
            policy=policy,
            job_id=job_id,
            run_id=run_id,
            pipeline_id=pipeline_id,
            payload_ref=payload_ref,
            observed_fallbacks=observed_fallbacks,
        )
        return self._put_json_artifact(
            payload,
            kind="runtime.capability_manifest",
            schema_name="polisyos.runtime.CapabilityManifest",
        )

    def _enqueue_job(
        self,
        *,
        job_id: str,
        job_kind: str,
        run_id: str | None,
        pipeline_id: str | None,
        payload: dict[str, Any],
        policy: ResolvedExecutionPolicy,
        request_id: str | None = None,
    ) -> ControlJobRecord:
        started = time.perf_counter()
        payload = self._attach_job_actor_scope(payload, policy=policy)
        payload = self._enrich_job_payload(payload, request_id=request_id)
        try:
            payload_ref = self._persist_job_payload(job_kind=job_kind, payload=payload)
            capability_manifest_ref = self._persist_capability_manifest(
                policy=policy,
                job_id=job_id,
                run_id=run_id,
                pipeline_id=pipeline_id,
                payload_ref=payload_ref,
            )
            record = self._control_store.create_job(
                job_id=job_id,
                kind=_coerce_control_job_kind(job_kind),
                run_id=run_id,
                pipeline_id=pipeline_id,
                requested_execution_profile=policy.requested_profile,
                effective_execution_profile=policy.effective_profile,
                policy_flags=policy.policy_flags.model_dump(mode="json"),
                capability_manifest_ref=capability_manifest_ref,
                payload_ref=payload_ref,
                submitted_by=str(policy.actor.get("subject") or "anonymous"),
            )
            diagnostic_event_ids = [
                event_id
                for event_id in (
                    self._emit_runtime_diagnostic_event(
                        job_id=job_id,
                        run_id=run_id,
                        execution_profile=policy.effective_profile,
                        phase="job_admission",
                        event_type="polisyos.runtime.diagnostic.cas_write.v1",
                        state_after="payload_persisted",
                        payload=payload,
                        event_payload={
                            "artifact_ref": payload_ref,
                            "artifact_kind": f"runtime.control_job_payload.{job_kind}",
                            "projection_authority": "runtime_event_only",
                        },
                        artifact_refs=[payload_ref],
                        authority_bearing_payload=(
                            policy.effective_profile in _SERIOUS_EXECUTION_PROFILES
                        ),
                    ),
                    self._emit_runtime_diagnostic_event(
                        job_id=job_id,
                        run_id=run_id,
                        execution_profile=policy.effective_profile,
                        phase="job_admission",
                        event_type="polisyos.runtime.diagnostic.cas_write.v1",
                        state_after="capability_manifest_persisted",
                        payload=payload,
                        event_payload={
                            "artifact_ref": capability_manifest_ref,
                            "artifact_kind": "runtime.capability_manifest",
                            "projection_authority": "runtime_event_only",
                        },
                        artifact_refs=[capability_manifest_ref],
                        input_refs=[payload_ref],
                        authority_bearing_payload=(
                            policy.effective_profile in _SERIOUS_EXECUTION_PROFILES
                        ),
                    ),
                    self._emit_runtime_diagnostic_event(
                        job_id=job_id,
                        run_id=run_id,
                        execution_profile=policy.effective_profile,
                        phase="job_admission",
                        event_type="polisyos.runtime.diagnostic.phase_transition.v1",
                        state_after="pending",
                        payload=payload,
                        event_payload={
                            "job_kind": job_kind,
                            "pipeline_id": pipeline_id,
                            "projection_authority": "progress_reference_only",
                        },
                    ),
                )
                if event_id is not None
            ]
            if diagnostic_event_ids:
                self._control_store.update_progress_state(
                    job_id=job_id,
                    state="pending",
                    progress={
                        "state": "pending",
                        "phase": "job_admission",
                        "diagnostic_event_ids": diagnostic_event_ids,
                        "diagnostic_event_authority": "progress_reference_only",
                    },
                )
            if self._worker is not None:
                self._worker.wake()
        except Exception:
            _record_control_plane_job_admission_metric(
                metrics=self._metrics,
                job_kind=job_kind,
                effective_profile=policy.effective_profile,
                status="error",
                duration_seconds=time.perf_counter() - started,
            )
            raise
        _record_control_plane_job_admission_metric(
            metrics=self._metrics,
            job_kind=job_kind,
            effective_profile=policy.effective_profile,
            status="success",
            duration_seconds=time.perf_counter() - started,
        )
        return record

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
        return record.to_response(request_id=request_id)

    def get_latest_job_for_run(self, run_id: str) -> ControlJobRecord | None:
        """Return the newest durable control job attached to one runtime run."""
        return self._control_store.get_latest_job_by_run(run_id)

    def record_production_approval_packet(
        self,
        *,
        run_id: str,
        approval_packet_ref: str,
        decision: str,
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
        progress_scorecard["approval_ready"] = decision in {
            "approved",
            "approved_with_override",
        }
        progress_scorecard["approval_state"] = (
            "approval_ready" if progress_scorecard["approval_ready"] else "approval_blocked"
        )
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
        approval_event_id = self._emit_runtime_diagnostic_event(
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
        )
        if approval_event_id is not None:
            progress.setdefault("diagnostic_event_ids", [])
            if isinstance(progress["diagnostic_event_ids"], list):
                progress["diagnostic_event_ids"].append(approval_event_id)
            progress["diagnostic_event_authority"] = "progress_reference_only"
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

    @staticmethod
    def _derive_decision_validity_dedupe_key(
        request: DecisionValidityEventRequest,
        *,
        dependency_keys: list[str],
    ) -> str:
        return uuid.uuid5(
            uuid.NAMESPACE_URL,
            _decision_validity_dedupe_payload(request, dependency_keys=dependency_keys),
        ).hex

    def _load_payload_ref(self, payload_ref: str) -> dict[str, Any]:
        from polisyos.core.canon import from_canonical_bytes

        payload = from_canonical_bytes(
            self._artifact_store.get_bytes(
                _make_artifact_ref(payload_ref, kind="runtime.payload").artifact_id
            )
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Control job payload must decode to a JSON object")
        return dict(payload)

    def _refresh_capability_manifest(
        self,
        *,
        job: ControlJobRecord,
        observed_fallbacks: list[str] | None = None,
    ) -> str:
        payload: dict[str, Any] = {}
        if job.payload_ref:
            try:
                payload = self._load_payload_ref(job.payload_ref)
            except Exception as exc:
                logger.debug(
                    "Failed to load payload scope while refreshing capability manifest for %s: %s",
                    job.job_id,
                    exc,
                )
        policy = self._policy_resolver.resolve(
            requested_profile=job.requested_execution_profile,
            policy_flags=PolicyFlags.model_validate(job.policy_flags),
            principal=RuntimePrincipal(
                subject=job.submitted_by or "control-plane",
                tenant_id=(
                    payload.get("tenant_id") if isinstance(payload.get("tenant_id"), str) else None
                ),
                cell_id=payload.get("cell_id") if isinstance(payload.get("cell_id"), str) else None,
                roles=frozenset({"system"}),
                authenticated=True,
            ),
        )
        manifest_ref = self._persist_capability_manifest(
            policy=policy,
            job_id=job.job_id,
            run_id=job.run_id,
            pipeline_id=job.pipeline_id,
            payload_ref=job.payload_ref,
            observed_fallbacks=observed_fallbacks,
        )
        self._control_store.update_manifest_ref(
            job_id=job.job_id,
            capability_manifest_ref=manifest_ref,
        )
        return manifest_ref

    def _hydrate_state_payload(
        self,
        payload: dict[str, Any],
        *,
        job: ControlJobRecord,
        capability_manifest_ref: str,
    ) -> dict[str, Any]:
        state_payload = dict(payload)
        state_payload["control_job_id"] = job.job_id
        state_payload["execution_profile"] = job.effective_execution_profile
        state_payload["capability_manifest_ref"] = _make_artifact_ref(
            capability_manifest_ref,
            kind="runtime.capability_manifest",
        )
        return state_payload

    def _process_control_job(self, job: ControlJobRecord) -> None:
        payload: dict[str, Any] = {}
        try:
            if not job.payload_ref:
                raise RuntimeError("control job payload ref is missing")
            payload = self._load_payload_ref(job.payload_ref)
            with self._control_job_span(job=job, payload=payload), self._job_tenant_scope(payload):
                self._emit_runtime_diagnostic_event(
                    job_id=job.job_id,
                    run_id=job.run_id,
                    execution_profile=job.effective_execution_profile,
                    phase="job_execution",
                    event_type="polisyos.runtime.diagnostic.producer_execution.v1",
                    state_before=job.state,
                    state_after="running",
                    payload=payload,
                    event_payload={
                        "job_kind": job.kind,
                        "attempt": job.attempt,
                        "projection_authority": "runtime_event_only",
                    },
                )
                if job.kind == "workflow_run":
                    capability_manifest_ref = (
                        job.capability_manifest_ref or self._refresh_capability_manifest(job=job)
                    )
                    state_payload = self._hydrate_state_payload(
                        payload["state_payload"],
                        job=job,
                        capability_manifest_ref=capability_manifest_ref,
                    )
                    self._execute_workflow(state_payload, payload["checkpoint_policy"])
                    self._control_store.complete_job(
                        job_id=job.job_id,
                        run_id=job.run_id,
                        capability_manifest_ref=capability_manifest_ref,
                    )
                    self._emit_runtime_diagnostic_event(
                        job_id=job.job_id,
                        run_id=job.run_id,
                        execution_profile=job.effective_execution_profile,
                        phase="job_execution",
                        event_type="polisyos.runtime.diagnostic.phase_transition.v1",
                        state_before="running",
                        state_after="completed",
                        payload=payload,
                        event_payload={"job_kind": job.kind},
                    )
                    return
                if job.kind == "natural_language_run":
                    capability_manifest_ref = (
                        job.capability_manifest_ref or self._refresh_capability_manifest(job=job)
                    )
                    result = self._execute_nl_pipeline(
                        run_id=str(payload["run_id"]),
                        nl_request=str(payload["request"]),
                        context=dict(payload.get("context") or {}),
                        domain_hint=payload.get("domain_hint"),
                        data_source=(
                            DataSourceBinding.model_validate(payload["data_source"])
                            if payload.get("data_source") is not None
                            else None
                        ),
                        max_iterations=int(payload.get("max_iterations") or 1),
                        llm_models=list(payload.get("llm_models") or []),
                        max_parallel_models=int(payload.get("max_parallel_models") or 1),
                        run_budget_usd=payload.get("run_budget_usd"),
                        per_model_budget_usd=payload.get("per_model_budget_usd"),
                        checkpoint_policy=str(payload.get("checkpoint_policy") or "strict"),
                        execution_plan_ref=payload.get("execution_plan_ref"),
                        execution_plan_payload=payload.get("execution_plan"),
                        stop_criteria_payload=dict(payload.get("stop_criteria") or {}),
                        governance_constraints_payload=list(
                            payload.get("governance_constraints") or []
                        ),
                        expected_outputs_payload=list(payload.get("expected_outputs") or []),
                        control_job_id=job.job_id,
                        execution_profile=job.effective_execution_profile,
                        capability_manifest_ref=capability_manifest_ref,
                        allow_mock_fallback=bool(job.policy_flags.get("allow_mock_fallback"))
                        or job.effective_execution_profile == "dev",
                        provider_preflight_payload=(
                            dict(payload.get("provider_preflight"))
                            if isinstance(payload.get("provider_preflight"), dict)
                            else None
                        ),
                        capability_manifest_updater=(
                            lambda fallbacks: self._refresh_capability_manifest(
                                job=job,
                                observed_fallbacks=fallbacks,
                            )
                        ),
                    )
                    final_manifest_ref = str(
                        result.get("capability_manifest_ref") or capability_manifest_ref
                    )
                    self._control_store.complete_job(
                        job_id=job.job_id,
                        run_id=str(result.get("run_id") or job.run_id or ""),
                        capability_manifest_ref=final_manifest_ref,
                    )
                    self._emit_runtime_diagnostic_event(
                        job_id=job.job_id,
                        run_id=str(result.get("run_id") or job.run_id or ""),
                        execution_profile=job.effective_execution_profile,
                        phase="job_execution",
                        event_type="polisyos.runtime.diagnostic.phase_transition.v1",
                        state_before="running",
                        state_after="completed",
                        payload=payload,
                        event_payload={
                            "job_kind": job.kind,
                            "capability_manifest_ref": final_manifest_ref,
                        },
                        artifact_refs=[final_manifest_ref],
                    )
                    return
                if job.kind == "lex_pipeline":
                    capability_manifest_ref = (
                        job.capability_manifest_ref or self._refresh_capability_manifest(job=job)
                    )
                    self._run_lex_pipeline_job(
                        job=job,
                        payload=payload,
                        capability_manifest_ref=capability_manifest_ref,
                    )
                    return
                raise RuntimeError(f"Unsupported control job kind: {job.kind}")
        except Exception as exc:
            logger.exception("Control job %s failed: %s", job.job_id, exc)
            self._emit_runtime_diagnostic_event(
                job_id=job.job_id,
                run_id=job.run_id,
                execution_profile=job.effective_execution_profile,
                phase="job_execution",
                event_type="polisyos.runtime.diagnostic.blocker.v1",
                state_before=job.state,
                state_after="failed",
                payload=payload,
                event_payload={
                    "job_kind": job.kind,
                    "error": str(exc)[:500],
                    "projection_authority": "runtime_event_only",
                },
                blocking_status="blocking",
            )
            self._control_store.fail_job(
                job_id=job.job_id,
                capability_manifest_ref=job.capability_manifest_ref,
                error_message=str(exc),
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
        ds_key, ds_value = _resolve_data_source(request.data_source)
        inputs[ds_key] = _make_artifact_ref(ds_value, kind=_DATA_SOURCE_KEYS[ds_key])

        # Optional refs
        for field_name, kind in _OPTIONAL_INPUT_KEYS.items():
            value = getattr(request, field_name, None)
            if value:
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
        service = DecisionValidityService(self._artifact_store)
        evaluations = service.record_dependency_event(event=event)
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

    def get_decision_validity_summary(
        self,
        packet_ref: str,
        *,
        run_id: str | None = None,
        request_id: str | None = None,
    ) -> DecisionValiditySummaryResponse:
        """Read the latest decision-validity lifecycle summary for a decision packet ref."""
        service = DecisionValidityService(self._artifact_store)
        summary = service.get_summary(packet_ref)
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
        feedback = FeedbackService(store=self._artifact_store, run_index=run_index)
        prepared = feedback.prepare_reissue(run)
        job_id = uuid.uuid4().hex
        policy = self._resolve_execution_policy(
            requested_profile=_coerce_optional_execution_profile(run.details.execution_profile),
            policy_flags=PolicyFlags(),
            principal=principal,
        )
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

    def _execute_workflow(
        self,
        state_payload: dict[str, Any],
        checkpoint_policy: str,
    ) -> None:
        from polisyos.scientist.api import run_experiment

        run_experiment(state_payload, store=self._artifact_store)

    # ---- NL launch (agent circuit) ----------------------------------------

    async def launch_nl_run(
        self,
        request: NaturalLanguageRunRequest,
        *,
        request_id: str | None = None,
        principal: RuntimePrincipal | None = None,
    ) -> RunLaunchResponse:
        """Queue a natural-language agent run and apply execution-policy fallback constraints."""
        from polisyos.core.run.context import new_run_id

        run_id = new_run_id()
        job_id = uuid.uuid4().hex
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
        if (
            not requested_models
            and policy.effective_profile != "dev"
            and not policy.mock_fallback_allowed
        ):
            raise unprocessable_entity(
                "Mock-only NL runs require allow_mock_fallback outside the dev profile.",
                code="mock_fallback_disallowed",
            )
        provider_preflight_payload: dict[str, Any] | None = None
        if requested_models and policy.effective_profile in {"research", "governed", "production"}:
            preflight_report = await run_provider_preflight(models=requested_models)
            provider_preflight_payload = preflight_report.model_dump(mode="json")
            if preflight_report.status == "failed":
                preflight_ref = self._put_json_artifact(
                    provider_preflight_payload,
                    kind="runtime.provider_preflight_report",
                    schema_name="polisyos.runtime.ProviderPreflightReport",
                )
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
                    submitted_by=str(policy.actor.get("subject") or "anonymous"),
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
                    error_message=str(failure.get("message") or "LLM provider preflight failed."),
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
        self._enqueue_job(
            job_id=job_id,
            job_kind="natural_language_run",
            run_id=run_id,
            pipeline_id=None,
            payload={
                "run_id": run_id,
                "request": request.request,
                "context": dict(request.context),
                "domain_hint": request.domain_hint,
                "data_source": request.data_source.model_dump(mode="json")
                if request.data_source
                else None,
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
            },
            policy=policy,
            request_id=request_id,
        )

        models_label = ", ".join(requested_models) if requested_models else "mock agents"
        if len(requested_models) > 1:
            mode_label = (
                f"{len(requested_models)} model variants "
                f"(parallel={max(1, min(request.max_parallel_models, len(requested_models)))})"
            )
        elif requested_models:
            mode_label = "single model"
        else:
            mode_label = "mock mode"

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
        from polisyos.fabric.ingestion import (
            ConnectorManifestSpec,
            DatasetFetchSpec,
            IngestionDependencies,
        )

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
            from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config

            profile_reg = self._registry_providers.source_profiles
            profile = profile_reg.get(connection_profile_id)
            if profile:
                connection_config = resolve_connection_config(profile)

        ingestion_dependencies = IngestionDependencies(
            registry=cast("Any", self._registry_providers.connectors),
            tracer=self._tracer,
            metrics=self._metrics,
        )

        mode = request.execution_mode
        record_ref: str | None = None
        try:
            # Record/replay takes priority over execution mode dispatch
            if request.replay_ref:
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
                )
            else:
                from polisyos.fabric.data_plane.orchestrator import run_orchestrated_ingestion

                result = run_orchestrated_ingestion(
                    connector_manifest=manifest,
                    source=request.source,
                    license_name=request.license_name,
                    cas_root=self._cas_root,
                    connection_config=connection_config,
                    produce_snapshot=request.produce_data_snapshot,
                    ingestion_dependencies=ingestion_dependencies,
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
                mode_effective=mode,
                record_ref=record_ref,
                input_bindings_ref=input_bindings_ref,
            )
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
        result = self._retrieval.resolve(request)
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
    ) -> DataCatalogSearchResponse:
        """Search local metric catalog candidates by metric text and optional geography."""
        matches = self._retrieval.search_catalog(
            metric_query=metric_query,
            geography=geography,
            limit=limit,
        )
        return DataCatalogSearchResponse(
            meta=_build_api_meta(request_id),
            query=metric_query,
            matches=matches,
            total_matches=len(matches),
        )

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
        from polisyos.fabric.connectors.bindings.resolver import persist_binding_rules_artifact

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
