"""Control Plane service — bridges HTTP layer to scientist/fabric."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

from opentelemetry.context import attach, detach

from polisyos.common.async_tools import run_blocking_async
from polisyos.common.logger import get_logger
from polisyos.core.artifacts.async_store import ensure_async_artifact_store
from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.control import (
    BindingProfileInfo,
    BindingProfilesListResponse,
    CacheStatusResponse,
    CapabilityFeatureInfo,
    CapabilityManifestResponse,
    ConnectorInfo,
    ConnectorsListResponse,
    ControlJobKind,
    ControlJobResponse,
    ControlOutboxEventInfo,
    ControlOutboxEventsResponse,
    ControlWorkerLeaseInfo,
    ControlWorkersResponse,
    DataCatalogSearchResponse,
    DataDiscoverRequest,
    DataDiscoverResponse,
    DataNeed,
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
    IndexStatsResponse,
    IngestRequest,
    IngestResponse,
    LexGraphStatsResponse,
    LexPipelineStatusResponse,
    LexSearchRequest,
    LexSearchResponse,
    LexTriggerRequest,
    LexTriggerResponse,
    ModelProfileInfo,
    ModelProfilesListResponse,
    NaturalLanguageRunRequest,
    ExecutionProfile,
    PolicyFlags,
    PromotionCandidatesResponse,
    PromotionDecisionRequest,
    PromotionDecisionResponse,
    RetrievalMode,
    RunLaunchResponse,
    SourceProfileInfo,
    SourceProfilesListResponse,
    WorkflowRunRequest,
)
from polisyos.core.contracts.decision_validity import DecisionDependencyEvent
from polisyos.core.contracts.runtime import ApiMeta
from polisyos.core.observability import get_metrics, get_tracer
from polisyos.foundry.methods.catalog.causal.capabilities import (
    build_causal_capability_contract,
    project_capability_features,
)
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
from polisyos.scientist.decision_validity import DecisionValidityService
from polisyos.scientist.llm.factory import create_traced_gateway_client

from .control_plane_store import ControlJobRecord, ControlPlaneStore
from .control_registry_providers import ControlRegistryProviders
from .control_worker import ControlWorker

logger = get_logger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.core.artifacts.protocol import ArtifactStore, AsyncArtifactStore
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
    from polisyos.fabric.connectors.registry import ConnectorRegistry

_CONTROL_JOB_KINDS = frozenset({"workflow_run", "natural_language_run", "lex_pipeline"})
_RETRIEVAL_MODES = frozenset({"fastlane", "explorelane", "hybrid"})

class _MethodCatalogSnapshotAware(Protocol):
    def set_method_catalog_snapshot(self, payload: dict[str, Any] | None) -> None: ...


def _coerce_control_job_kind(value: str) -> ControlJobKind:
    normalized = value.strip()
    if normalized not in _CONTROL_JOB_KINDS:
        raise ValueError(f"Unsupported control job kind: {normalized!r}")
    return cast("ControlJobKind", normalized)


def _build_api_meta(request_id: str | None = None) -> ApiMeta:
    return ApiMeta(request_id=request_id or uuid.uuid4().hex)


# ---------------------------------------------------------------------------
# Helpers to convert string refs → ArtifactRef
# ---------------------------------------------------------------------------

def _make_artifact_ref(
    ref_str: str,
    *,
    kind: str,
    media_type: str = "application/json",
) -> ArtifactRef:
    """Lazily import ArtifactRef and ArtifactID to avoid heavy startup cost."""
    from polisyos.core.artifacts.ids import ArtifactID

    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(ref_str),
        kind=kind,
        media_type=media_type,
    )


def _typed_artifact_ref(
    ref_str: str,
    *,
    kind: str,
    ref_type: Any,
    media_type: str = "application/json",
) -> Any:
    return cast("Any", ref_type).model_validate(
        _make_artifact_ref(ref_str, kind=kind, media_type=media_type).model_dump(mode="json")
    )


def _artifact_ref_from_summary_payload(
    payload: Any,
    *,
    kind: str,
    media_type: str = "application/json",
) -> ArtifactRef | None:
    if not isinstance(payload, dict):
        return None
    artifact_id = payload.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id:
        return None
    return _make_artifact_ref(artifact_id, kind=kind, media_type=media_type)


_DATA_SOURCE_KEYS = {
    "data_snapshot_ref": "fabric.data_snapshot",
    "input_bindings_ref": "foundry.input_bindings",
    "data_view_request_ref": "fabric.data_view_request",
}

_OPTIONAL_INPUT_KEYS = {
    "trinity_bundle_ref": "ir.trinity_bundle",
    "policy_spec_ref": "ir.policy_spec",
    "model_spec_ref": "ir.model_spec",
    "research_intent_ref": "scholar.research_intent",
    "knowledge_bundle_ref": "scholar.knowledge_bundle",
    "norm_pack_ref": "lex.norm_pack",
    "calibration_report_ref": "foundry.calibration_report",
}


def _resolve_data_source(binding: DataSourceBinding) -> tuple[str, str]:
    """Return (state_key, ref_string) for the provided data source."""
    for field_name, _kind in _DATA_SOURCE_KEYS.items():
        value = getattr(binding, field_name, None)
        if value:
            return field_name, value
    raise ValueError(
        "At least one data source must be provided: "
        "data_snapshot_ref, input_bindings_ref, or data_view_request_ref"
    )


def _as_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _coerce_retrieval_mode(value: str) -> RetrievalMode:
    normalized = value.strip().lower()
    if normalized not in _RETRIEVAL_MODES:
        raise ValueError(f"Unsupported retrieval mode: {value!r}")
    return cast("RetrievalMode", normalized)


def _coerce_optional_execution_profile(value: str | None) -> ExecutionProfile | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    supported_profiles = RuntimeExecutionPolicyResolver.supported_profiles()
    if normalized not in supported_profiles:
        raise ValueError(f"Unsupported execution profile: {value!r}")
    return cast("ExecutionProfile", normalized)


def _is_multimodel_enabled() -> bool:
    return _as_bool(
        os.getenv("POLISYOS_LLM_MULTIMODEL_ENABLED"),
        default=True,
    )


def _is_required_preflight_enabled() -> bool:
    return _as_bool(os.getenv("POLISYOS_REQUIRED_PREFLIGHT_ENABLED"), default=True)


def _is_auto_materialization_enabled() -> bool:
    return _as_bool(os.getenv("POLISYOS_AUTO_MATERIALIZATION_ENABLED"), default=True)


def _is_unified_dag_enabled() -> bool:
    return _as_bool(os.getenv("POLISYOS_UNIFIED_DAG_ENABLED"), default=True)


def _is_scientist_v2_enabled() -> bool:
    return _as_bool(os.getenv("POLISYOS_SCIENTIST_V2_ENABLED"), default=False)


def _is_scientist_shadow_mode() -> bool:
    return _as_bool(os.getenv("POLISYOS_SCIENTIST_SHADOW_MODE"), default=False)


def _is_scientist_web_search_enabled() -> bool:
    return _as_bool(os.getenv("POLISYOS_SCIENTIST_WEB_SEARCH_ENABLED"), default=False)


def _is_scientist_swarm_enabled() -> bool:
    return _as_bool(os.getenv("POLISYOS_SCIENTIST_SWARM_ENABLED"), default=False)


def _is_scientist_reflexion_enabled() -> bool:
    return _as_bool(os.getenv("POLISYOS_SCIENTIST_REFLEXION_ENABLED"), default=False)


def _normalize_model_variant_id(model_name: str, index: int) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", model_name.strip().lower()).strip("_")
    if not base:
        base = "model"
    return f"{base}_{index + 1}"


def _dedupe_models(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _now_ms() -> int:
    return int(time.time() * 1000)


def _record_control_plane_job_admission_metric(
    *,
    metrics: Any,
    job_kind: str,
    effective_profile: str,
    status: str,
    duration_seconds: float,
) -> None:
    recorder = getattr(metrics, "record_control_plane_job_admission", None)
    if callable(recorder):
        recorder(
            job_kind=job_kind,
            effective_profile=effective_profile,
            status=status,
            duration_seconds=duration_seconds,
        )


def _record_control_plane_job_execution_metric(
    *,
    metrics: Any,
    job_kind: str,
    status: str,
    duration_seconds: float,
    queue_lag_seconds: float,
) -> None:
    recorder = getattr(metrics, "record_control_plane_job_execution", None)
    if callable(recorder):
        recorder(
            job_kind=job_kind,
            status=status,
            duration_seconds=duration_seconds,
            queue_lag_seconds=queue_lag_seconds,
        )


def _resolve_curated_dir() -> Path:
    candidates = (
        Path("data/curated"),
        Path("policy-engine/data/curated"),
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _sum_call_events(events: list[dict[str, Any]]) -> dict[str, float]:
    prompt_tokens = 0.0
    completion_tokens = 0.0
    latency_ms = 0.0
    cost_usd = 0.0
    estimated_cost_usd = 0.0
    cost_delta_usd = 0.0
    for event in events:
        prompt_tokens += float(event.get("prompt_tokens") or 0)
        completion_tokens += float(event.get("completion_tokens") or 0)
        latency_ms += float(event.get("latency_ms") or 0)
        cost_usd += float(event.get("cost_usd") or 0.0)
        estimated_cost_usd += float(event.get("estimated_cost_usd") or 0.0)
        cost_delta_usd += float(event.get("cost_delta_usd") or 0.0)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
        "estimated_cost_usd": estimated_cost_usd,
        "cost_delta_usd": cost_delta_usd,
    }


def _delta_usage(
    before: dict[str, float],
    after: dict[str, float],
) -> tuple[int, int, int, float]:
    prompt = max(0, int(after["prompt_tokens"] - before["prompt_tokens"]))
    completion = max(0, int(after["completion_tokens"] - before["completion_tokens"]))
    latency = max(0, int(after["latency_ms"] - before["latency_ms"]))
    cost = max(0.0, float(after["cost_usd"] - before["cost_usd"]))
    return prompt, completion, latency, cost


def _build_scientist_v2_shadow_comparison(
    *,
    legacy_status: str,
    legacy_verdict: str | None,
    legacy_issue_count: int,
    legacy_cost_usd: float,
    legacy_prompt_tokens: int,
    legacy_completion_tokens: int,
    shadow_result: Any | None,
) -> dict[str, Any] | None:
    if shadow_result is None:
        return None
    shadow_metrics = dict(getattr(shadow_result, "metrics", {}) or {})
    shadow_result_payload = dict(getattr(shadow_result, "result", {}) or {})
    shadow_grounding = dict(shadow_result_payload.get("grounding") or {})
    claim_links = shadow_grounding.get("claim_links")
    supported_claims = 0
    total_claims = 0
    if isinstance(claim_links, list):
        total_claims = len(claim_links)
        supported_claims = sum(
            1
            for item in claim_links
            if isinstance(item, dict) and item.get("support_state") == "supported"
        )
    shadow_citation_coverage = float(shadow_metrics.get("citation_coverage") or 0.0)
    return {
        "legacy_status": legacy_status,
        "legacy_verdict": legacy_verdict,
        "shadow_verdict": shadow_result_payload.get("verdict"),
        "verdict_match": legacy_verdict == shadow_result_payload.get("verdict"),
        "legacy_issue_count": int(legacy_issue_count),
        "shadow_issue_count": int(shadow_result_payload.get("issue_count") or 0),
        "issue_count_delta": int(shadow_result_payload.get("issue_count") or 0) - int(legacy_issue_count),
        "legacy_cost_usd": float(legacy_cost_usd),
        "shadow_final_score": float(shadow_metrics.get("final_score") or 0.0),
        "legacy_total_tokens": int(legacy_prompt_tokens) + int(legacy_completion_tokens),
        "shadow_citation_coverage": shadow_citation_coverage,
        "shadow_supported_claims": supported_claims,
        "shadow_total_claims": total_claims,
        "default_on_candidate": bool(
            shadow_result_payload.get("verdict") == "APPROVE"
            and shadow_citation_coverage >= 0.85
        ),
    }


def _canonicalize_numeric_payload(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {
            key: _canonicalize_numeric_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_canonicalize_numeric_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_canonicalize_numeric_payload(item) for item in value]
    return value


def _decision_validity_dedupe_payload(
    request: DecisionValidityEventRequest,
    *,
    dependency_keys: list[str],
) -> str:
    return json.dumps(
        {
            "trigger_type": request.trigger_type.value,
            "status": request.status.value,
            "reason": request.reason,
            "dependency_keys": sorted(dependency_keys),
            "source_ref": request.source_ref,
            "payload": request.payload,
            "occurred_at": (
                request.occurred_at.astimezone(timezone.utc).replace(microsecond=0).isoformat()
                if request.occurred_at is not None
                else None
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ControlPlaneService:
    """Bridge HTTP control requests to durable jobs, Scientist runs, Fabric ingestion, and Lex pipelines."""

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
        self._metrics = metrics or get_metrics()
        self._tracer = tracer or get_tracer()
        self._policy_resolver = policy_resolver or RuntimeExecutionPolicyResolver.from_env()
        if registry_providers is None:
            raise ValueError(
                "ControlPlaneService requires typed registry_providers from the runtime composition root"
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
        self._async_artifact_store = (
            async_artifact_store or ensure_async_artifact_store(self._artifact_store)
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
        control_store_close = cast("Callable[[], None] | None", getattr(self._control_store, "close", None))
        artifact_store_close = cast("Callable[[], None] | None", getattr(self._artifact_store, "close", None))
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
                token = attach(cast("Any", extract_context({str(key): str(value) for key, value in carrier.items()})))
        queue_lag_seconds = max(
            (datetime.now(timezone.utc) - job.created_at).total_seconds(),
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
        policy = self._policy_resolver.resolve(
            requested_profile=job.requested_execution_profile,
            policy_flags=PolicyFlags.model_validate(job.policy_flags),
            principal=RuntimePrincipal(
                subject=job.submitted_by or "control-plane",
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
        try:
            if not job.payload_ref:
                raise RuntimeError("control job payload ref is missing")
            payload = self._load_payload_ref(job.payload_ref)
            with self._control_job_span(job=job, payload=payload):
                if job.kind == "workflow_run":
                    capability_manifest_ref = job.capability_manifest_ref or self._refresh_capability_manifest(job=job)
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
                    return
                if job.kind == "natural_language_run":
                    capability_manifest_ref = job.capability_manifest_ref or self._refresh_capability_manifest(job=job)
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
                        governance_constraints_payload=list(payload.get("governance_constraints") or []),
                        expected_outputs_payload=list(payload.get("expected_outputs") or []),
                        control_job_id=job.job_id,
                        execution_profile=job.effective_execution_profile,
                        capability_manifest_ref=capability_manifest_ref,
                        allow_mock_fallback=bool(job.policy_flags.get("allow_mock_fallback"))
                        or job.effective_execution_profile == "dev",
                        capability_manifest_updater=lambda fallbacks: self._refresh_capability_manifest(
                            job=job,
                            observed_fallbacks=fallbacks,
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
                    return
                if job.kind == "lex_pipeline":
                    capability_manifest_ref = job.capability_manifest_ref or self._refresh_capability_manifest(job=job)
                    self._run_lex_pipeline_job(
                        job=job,
                        payload=payload,
                        capability_manifest_ref=capability_manifest_ref,
                    )
                    return
                raise RuntimeError(f"Unsupported control job kind: {job.kind}")
        except Exception as exc:
            logger.exception("Control job %s failed: %s", job.job_id, exc)
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
                from polisyos.lex.batch.progress import ProgressTracker

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
            occurred_at=request.occurred_at or datetime.now(timezone.utc).replace(microsecond=0),
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
            if evaluation.decision_packet_ref and evaluation.decision_packet_ref not in affected_packets:
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
        from .feedback import FeedbackService
        from .run_index import RunIndexService

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

    @staticmethod
    def _execute_workflow(
        state_payload: dict[str, Any],
        checkpoint_policy: str,
    ) -> None:
        from polisyos.scientist.api import run_experiment

        run_experiment(state_payload)

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
        if not requested_models and policy.effective_profile != "dev" and not policy.mock_fallback_allowed:
            raise unprocessable_entity(
                "Mock-only NL runs require allow_mock_fallback outside the dev profile.",
                code="mock_fallback_disallowed",
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
                "data_source": request.data_source.model_dump(mode="json") if request.data_source else None,
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

    def _execute_nl_pipeline(
        self,
        run_id: str,
        nl_request: str,
        context: dict[str, Any],
        domain_hint: str | None,
        data_source: DataSourceBinding | None,
        max_iterations: int,
        llm_models: list[str],
        max_parallel_models: int,
        run_budget_usd: float | None,
        per_model_budget_usd: float | None,
        checkpoint_policy: str,
        execution_plan_ref: str | None,
        execution_plan_payload: dict[str, Any] | None,
        stop_criteria_payload: dict[str, Any] | None,
        governance_constraints_payload: list[dict[str, Any]] | None,
        expected_outputs_payload: list[dict[str, Any]] | None,
        control_job_id: str | None = None,
        execution_profile: str | None = None,
        capability_manifest_ref: str | None = None,
        allow_mock_fallback: bool = True,
        capability_manifest_updater: Any | None = None,
    ) -> dict[str, Any]:
        """Run agent circuit synchronously for a durable control-plane job."""
        from polisyos.common.async_tools import run_coro_sync

        async def _agent_pipeline() -> dict[str, Any]:
            from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
            from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
            from polisyos.core.canon import CanonSpec
            from polisyos.core.contracts.execution_plan import (
                ExecutionPlan,
                ExecutionPlanRef,
                IterationState,
                MethodCatalogSnapshot,
                MethodCatalogSnapshotRef,
                PreflightReportRef,
            )
            from polisyos.core.contracts.fabric import DataSnapshot
            from polisyos.core.contracts.foundry import (
                FoundryInputBindings,
                StateSnapshot,
                StateSnapshotRef,
            )
            from polisyos.core.registry import build_default_registry_bundle
            from polisyos.fabric.retrieval import RetrievalService
            from polisyos.foundry.methods import (
                build_method_catalog_snapshot,
                persist_method_catalog_snapshot,
            )
            from polisyos.foundry.methods.catalog import (
                ensure_all_methods_registered as ensure_causal_methods_registered,
            )
            from polisyos.scientist.agent.critic import LLMCriticAgent, MockCriticAgent
            from polisyos.scientist.agent.data_need_extractor import (
                LLMDataNeedExtractorAgent,
                MockDataNeedExtractorAgent,
            )
            from polisyos.scientist.agent.drafter_clients import LLMDrafterAgent, MockDrafterAgent
            from polisyos.scientist.agent.formalizer import LLMFormalizerAgent, MockFormalizerAgent
            from polisyos.scientist.agent.pi import LLMPIAgent, MockPIAgent
            from polisyos.scientist.engine.iteration_state_machine import transition
            from polisyos.scientist.llm_cycle import (
                build_default_execution_plan,
                build_reproducibility_manifest,
                evaluate_iteration,
                persist_evaluator_report,
                persist_execution_plan,
                persist_iteration_state,
                persist_preflight_report,
                persist_reproducibility_manifest,
                preflight_execution_plan,
            )

            store = self._artifact_store
            async_store = self._async_artifact_store
            models_to_run = _dedupe_models(list(llm_models))
            current_capability_manifest_ref = capability_manifest_ref
            if not models_to_run and not allow_mock_fallback:
                raise RuntimeError("mock_fallback_disallowed")
            method_catalog_snapshot_cache: dict[str, Any] = {
                "snapshot": None,
                "ref": None,
            }
            registry_bundle_ref_cache: ArtifactRef | None = None
            catalog_lock = asyncio.Lock()

            def _artifact_ref_from_sha(sha: str, *, kind: str) -> ArtifactRef:
                return _make_artifact_ref(sha, kind=kind)

            async def _ensure_registry_bundle_ref() -> ArtifactRef:
                nonlocal registry_bundle_ref_cache
                if registry_bundle_ref_cache is None:
                    bundle = await run_blocking_async(build_default_registry_bundle, store)
                    registry_bundle_ref = bundle.bundle_ref
                    if registry_bundle_ref is None:
                        raise RuntimeError("default registry bundle did not produce an artifact reference")
                    registry_bundle_ref_cache = registry_bundle_ref
                if registry_bundle_ref_cache is None:
                    raise RuntimeError("default registry bundle ref cache was not populated")
                return registry_bundle_ref_cache

            async def _ensure_catalog_snapshot() -> tuple[MethodCatalogSnapshot, str]:
                async with catalog_lock:
                    cached_snapshot = method_catalog_snapshot_cache.get("snapshot")
                    cached_ref = method_catalog_snapshot_cache.get("ref")
                    if isinstance(cached_snapshot, MethodCatalogSnapshot) and isinstance(cached_ref, str):
                        return cached_snapshot, cached_ref
                    ensure_causal_methods_registered()
                    snapshot = build_method_catalog_snapshot(run_id=run_id)
                    snapshot_ref = await run_blocking_async(
                        persist_method_catalog_snapshot,
                        store,
                        snapshot,
                    )
                    snapshot_ref_str = str(snapshot_ref.artifact_id)
                    method_catalog_snapshot_cache["snapshot"] = snapshot
                    method_catalog_snapshot_cache["ref"] = snapshot_ref_str
                    return snapshot, snapshot_ref_str

            async def _materialize_retrieval_artifacts(
                *,
                variant_id: str,
                data_context_payload: dict[str, Any],
                retrieval_telemetry: dict[str, Any],
            ) -> dict[str, str]:
                payload_ref = await async_store.put_json(
                    {
                        "model_variant_id": variant_id,
                        "data_context": data_context_payload,
                        "retrieval_telemetry": retrieval_telemetry,
                    },
                    ArtifactWriteOptions(
                        kind="fabric.retrieval_payload",
                        media_type="application/json",
                        schema=SchemaInfo(name="polisyos.fabric.RetrievalPayload", version="1.0"),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                )
                quality_ref = await async_store.put_json(
                    {
                        "source": "retrieval_service",
                        "mode": str(retrieval_telemetry.get("mode") or "hybrid"),
                        "coverage_ok": True,
                        "warnings": list(retrieval_telemetry.get("warnings") or []),
                    },
                    ArtifactWriteOptions(
                        kind="fabric.quality_report",
                        media_type="application/json",
                        schema=SchemaInfo(name="polisyos.fabric.DataQualityReport", version="1.0"),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                )
                snapshot = DataSnapshot(
                    data_ref=payload_ref,
                    quality_report_ref=quality_ref,
                    stats={
                        "metric_count": len(data_context_payload.get("metrics") or []),
                        "metadata_docs_fetched": int(
                            data_context_payload.get("metadata_docs_fetched") or 0
                        ),
                    },
                    notes=[
                        "source:runtime_nl_retrieval",
                        f"model_variant_id:{variant_id}",
                    ],
                )
                snapshot_ref = await async_store.put_json(
                    snapshot,
                    ArtifactWriteOptions(
                        kind="fabric.data_snapshot",
                        media_type="application/json",
                        schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
                        inputs=[
                            InputRef(artifact_id=payload_ref.artifact_id, role="retrieval_payload"),
                        ],
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                )
                registry_ref = await _ensure_registry_bundle_ref()
                try:
                    from polisyos.foundry.data_plane import build_input_bindings

                    bindings_result = await run_blocking_async(
                        build_input_bindings,
                        store,
                        data_snapshot_ref=_artifact_ref_from_sha(
                            str(snapshot_ref.artifact_id),
                            kind="fabric.data_snapshot",
                        ),
                        registry_bundle_ref=registry_ref,
                        rules=None,
                        notes=["runtime_nl_auto_materialization"],
                    )
                    return {
                        "data_snapshot_ref": str(snapshot_ref.artifact_id),
                        "input_bindings_ref": str(bindings_result.input_bindings_ref.artifact_id),
                        "registry_bundle_ref": str(registry_ref.artifact_id),
                        "input_binding_report_ref": str(
                            bindings_result.input_binding_report_ref.artifact_id
                        ),
                    }
                except ModuleNotFoundError:
                    # Keep pipeline runnable in lightweight environments without JAX.
                    fallback_state_ref = await async_store.put_json(
                        {"source": "runtime_nl_auto_materialization", "jax": "missing"},
                        ArtifactWriteOptions(
                            kind="foundry.state_payload",
                            media_type="application/json",
                            schema=SchemaInfo(name="polisyos.foundry.StatePayload", version="0.1.0"),
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                    )
                    fallback_snapshot = StateSnapshot(
                        schema_version="2.0",
                        state_ref=fallback_state_ref,
                        step=0,
                        notes=["fallback_state_snapshot_without_jax"],
                    )
                    fallback_snapshot_ref = await async_store.put_json(
                        fallback_snapshot,
                        ArtifactWriteOptions(
                            kind="foundry.state_snapshot",
                            media_type="application/json",
                            schema=SchemaInfo(name="polisyos.core.StateSnapshot", version="1.0"),
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                    )
                    fallback_bindings = FoundryInputBindings(
                        schema_version="1.0",
                        data_snapshot_ref=_artifact_ref_from_sha(
                            str(snapshot_ref.artifact_id),
                            kind="fabric.data_snapshot",
                        ),
                        registry_bundle_ref=registry_ref,
                        rules=[],
                        bound_state_snapshot_ref=StateSnapshotRef(
                            artifact_id=fallback_snapshot_ref.artifact_id
                        ),
                        notes=["fallback_bindings_without_jax"],
                    )
                    fallback_bindings_ref = await async_store.put_json(
                        fallback_bindings,
                        ArtifactWriteOptions(
                            kind="foundry.input_bindings",
                            media_type="application/json",
                            schema=SchemaInfo(name="polisyos.core.FoundryInputBindings", version="1.0"),
                            inputs=[
                                InputRef(artifact_id=snapshot_ref.artifact_id, role="data_snapshot"),
                                InputRef(artifact_id=fallback_snapshot_ref.artifact_id, role="bound_state"),
                            ],
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                    )
                    fallback_report_ref = await async_store.put_json(
                        {
                            "ok": False,
                            "warnings": ["jax_not_available"],
                            "applied_rules": [],
                            "errors": [],
                        },
                        ArtifactWriteOptions(
                            kind="foundry.input_binding_report",
                            media_type="application/json",
                            schema=SchemaInfo(
                                name="polisyos.foundry.FoundryInputBindingReport",
                                version="1.0",
                            ),
                            inputs=[
                                InputRef(
                                    artifact_id=fallback_bindings_ref.artifact_id,
                                    role="input_bindings",
                                )
                            ],
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                    )
                    return {
                        "data_snapshot_ref": str(snapshot_ref.artifact_id),
                        "input_bindings_ref": str(fallback_bindings_ref.artifact_id),
                        "registry_bundle_ref": str(registry_ref.artifact_id),
                        "input_binding_report_ref": str(fallback_report_ref.artifact_id),
                    }

            async def _store_bundle(bundle: Any) -> str:
                ref = await async_store.put_json(
                    bundle,
                    ArtifactWriteOptions(
                        kind="ir.trinity_bundle",
                        media_type="application/json",
                        schema=SchemaInfo(
                            name="polisyos.ir.TrinityBundle",
                            version=str(getattr(bundle, "schema_version", "1.0")),
                        ),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                )
                return str(ref.artifact_id)

            async def _run_variant(model_name: str | None, variant_index: int) -> dict[str, Any]:
                nonlocal current_capability_manifest_ref
                variant_started_at = _now_ms()
                variant_started_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
                call_events: list[dict[str, Any]] = []
                variant_label = model_name or "mock"
                variant_id = _normalize_model_variant_id(variant_label, variant_index)
                notes: list[str] = []
                llm_client = None
                provider = "mock"

                if model_name:
                    llm_client = create_traced_gateway_client(
                        model_name=model_name,
                        run_id=run_id,
                        model_variant_id=variant_id,
                        call_observer=call_events.append,
                        tracer=self._tracer,
                        metrics=self._metrics,
                    )
                    if llm_client is None:
                        if not allow_mock_fallback:
                            raise RuntimeError("mock_fallback_disallowed")
                        notes.append("gateway_not_configured_fallback_to_mock")
                        if callable(capability_manifest_updater):
                            current_capability_manifest_ref = capability_manifest_updater(
                                ["gateway_not_configured_fallback_to_mock"]
                            )
                    else:
                        provider = "gateway"
                elif not allow_mock_fallback:
                    raise RuntimeError("mock_fallback_disallowed")

                if llm_client is None:
                    pi = MockPIAgent()
                    data_need_extractor = MockDataNeedExtractorAgent()
                    drafter = MockDrafterAgent()
                    formalizer = MockFormalizerAgent()
                    critic = MockCriticAgent()
                else:
                    pi = LLMPIAgent(llm_client=llm_client, model_name=model_name)
                    data_need_extractor = LLMDataNeedExtractorAgent(
                        llm_client=llm_client,
                        model_name=model_name,
                    )
                    drafter = LLMDrafterAgent(llm_client=llm_client, model_name=model_name)
                    formalizer = LLMFormalizerAgent(llm_client=llm_client, model_name=model_name)
                    critic = LLMCriticAgent(llm_client=llm_client, model_name=model_name)

                retrieval = RetrievalService(
                    curated_dir=_resolve_curated_dir(),
                    cas_root=Path(".polisyos"),
                    providers=self._build_retrieval_providers(),
                )

                steps: list[dict[str, Any]] = []
                retrieval_telemetry: dict[str, Any] = {}
                retrieval_mode = "hybrid"
                retrieval_lane_used = "none"
                retrieval_metadata_docs_fetched = 0
                retrieval_index_size_bytes = 0
                retrieval_index_docs_total = 0
                retrieval_candidates_filtered = 0
                retrieval_candidates_promoted = 0
                retrieval_phase_durations: dict[str, int] = {}
                data_context_payload: dict[str, Any] = {}
                auto_data_source_refs: dict[str, str] = {}
                retrieval_context_payload: dict[str, Any] = {
                    "data_needs": [],
                    "fetch_plans": [],
                    "promotion_candidates": [],
                    "auto_data_source_refs": {},
                }
                execution_plan_ref_str = execution_plan_ref
                method_catalog_snapshot_ref_str: str | None = None
                preflight_report_ref_str: str | None = None
                evaluator_report_ref_str: str | None = None
                iteration_state_ref_str: str | None = None
                reproducibility_manifest_ref_str: str | None = None
                preflight_ready = True
                preflight_diagnostics: list[dict[str, Any]] = []
                evaluator_payload: dict[str, Any] = {}
                fabric_result = None
                fabric_shadow_result = None
                fabric_shadow_task = None
                fabric_shadow_comparison = None

                async def _capture_step(
                    *,
                    agent: str,
                    action: str,
                    coro: Any,
                    summary: str | None = None,
                    status: str = "ok",
                    details: dict[str, Any] | None = None,
                ) -> Any:
                    before = _sum_call_events(call_events)
                    started = _now_ms()
                    result = await coro
                    after = _sum_call_events(call_events)
                    finished = _now_ms()
                    prompt_tokens, completion_tokens, llm_latency_ms, delta_cost = _delta_usage(
                        before,
                        after,
                    )
                    total_tokens = prompt_tokens + completion_tokens
                    step_latency = max(0, finished - started)
                    steps.append(
                        {
                            "attempt": 1,
                            "agent": agent,
                            "action": action,
                            "status": status,
                            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                            "summary": summary,
                            "model": model_name,
                            "provider": provider,
                            "model_variant_id": variant_id,
                            "latency_ms": llm_latency_ms or step_latency,
                            "cost_usd": round(delta_cost, 8),
                            "token_usage": {
                                "prompt_tokens": prompt_tokens,
                                "completion_tokens": completion_tokens,
                                "total_tokens": total_tokens,
                            },
                            "details": details or {},
                        }
                    )
                    return result

                def _append_step(
                    *,
                    agent: str,
                    action: str,
                    summary: str | None = None,
                    status: str = "ok",
                    details: dict[str, Any] | None = None,
                ) -> None:
                    steps.append(
                        {
                            "attempt": 1,
                            "agent": agent,
                            "action": action,
                            "status": status,
                            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                            "summary": summary,
                            "model": model_name,
                            "provider": provider,
                            "model_variant_id": variant_id,
                            "latency_ms": 0,
                            "cost_usd": 0.0,
                            "token_usage": {
                                "prompt_tokens": 0,
                                "completion_tokens": 0,
                                "total_tokens": 0,
                            },
                            "details": details or {},
                        }
                    )

                try:
                    problem_frame = await _capture_step(
                        agent="pi_agent",
                        action="create_problem_frame",
                        coro=pi.create_problem_frame(
                            nl_request,
                            domain_hint=domain_hint or "custom",
                        ),
                        summary="Problem frame created",
                    )
                    await pi.hold_problem_frame(problem_frame)
                    data_need_specs = await _capture_step(
                        agent="data_need_extractor",
                        action="extract_data_need",
                        coro=data_need_extractor.extract_data_needs(problem_frame),
                        summary="Data needs extracted from problem frame",
                    )
                    data_needs = [
                        DataNeed(
                            metric=spec.metric,
                            geography=spec.geography,
                            time_start=spec.time_start,
                            time_end=spec.time_end,
                            granularity=spec.granularity,
                            quality_min=spec.quality_min,
                            purpose=spec.purpose,
                        )
                        for spec in data_need_specs
                        if spec.metric
                    ]
                    if not data_needs:
                        notes.append("no_data_needs_extracted")
                    retrieval_context_payload["data_needs"] = [
                        item.model_dump(mode="json") for item in data_needs
                    ]

                    # 1) Build ExecutionPlan first and persist as the first cycle artifact.
                    if execution_plan_payload:
                        try:
                            execution_plan_data = dict(execution_plan_payload)
                            execution_plan_data["run_id"] = run_id
                            execution_plan_data["iteration"] = 1
                            if isinstance(stop_criteria_payload, dict):
                                execution_plan_data["stop_criteria"] = dict(stop_criteria_payload)
                            if isinstance(governance_constraints_payload, list):
                                execution_plan_data["governance_constraints"] = list(
                                    governance_constraints_payload
                                )
                            if isinstance(expected_outputs_payload, list):
                                execution_plan_data["expected_outputs"] = list(
                                    expected_outputs_payload
                                )
                            execution_plan = ExecutionPlan.model_validate(execution_plan_data)
                        except (TypeError, ValueError) as exc:
                            logger.debug(
                                "Falling back to default execution plan for run %s: %s",
                                run_id,
                                exc,
                            )
                            execution_plan = build_default_execution_plan(
                                run_id=run_id,
                                data_needs=data_needs,
                                method_dag=[],
                                params={"context": context},
                                max_iterations=max_iterations,
                                run_budget_usd=run_budget_usd,
                                per_model_budget_usd=per_model_budget_usd,
                                governance_constraints=governance_constraints_payload,
                                expected_outputs=expected_outputs_payload,
                            )
                    else:
                        execution_plan = build_default_execution_plan(
                            run_id=run_id,
                            data_needs=data_needs,
                            method_dag=[],
                            params={"context": context},
                            max_iterations=max_iterations,
                            run_budget_usd=run_budget_usd,
                            per_model_budget_usd=per_model_budget_usd,
                            governance_constraints=governance_constraints_payload,
                            expected_outputs=expected_outputs_payload,
                        )

                    if not execution_plan_ref_str:
                        execution_plan_ref_obj = await run_blocking_async(
                            persist_execution_plan,
                            store,
                            execution_plan,
                        )
                        execution_plan_ref_str = str(execution_plan_ref_obj.artifact_id)
                    _append_step(
                        agent="planner",
                        action="build_execution_plan",
                        summary="ExecutionPlan persisted",
                        details={
                            "execution_plan_ref": execution_plan_ref_str,
                            "data_needs": len(execution_plan.data_needs),
                            "method_dag_nodes": len(execution_plan.method_dag),
                        },
                    )

                    # 2) Build and cache live method catalog snapshot for this run.
                    catalog_snapshot, method_catalog_snapshot_ref_str = await _ensure_catalog_snapshot()
                    snapshot_injector = cast(
                        "_MethodCatalogSnapshotAware | None",
                        formalizer if hasattr(formalizer, "set_method_catalog_snapshot") else None,
                    )
                    if snapshot_injector is not None:
                        try:
                            snapshot_injector.set_method_catalog_snapshot(
                                catalog_snapshot.model_dump(mode="json")
                            )
                        except (AttributeError, TypeError, ValueError) as exc:
                            logger.debug(
                                "Failed to inject method catalog snapshot for run %s: %s",
                                run_id,
                                exc,
                            )
                            notes.append("formalizer_catalog_injection_failed")

                    # 3) Mandatory preflight before execution.
                    preflight_report = preflight_execution_plan(execution_plan, catalog_snapshot)
                    preflight_report.plan_ref = _typed_artifact_ref(
                        execution_plan_ref_str,
                        kind="scientist.execution_plan",
                        ref_type=ExecutionPlanRef,
                    )
                    preflight_report.catalog_snapshot_ref = _typed_artifact_ref(
                        method_catalog_snapshot_ref_str,
                        kind="foundry.method_catalog_snapshot",
                        ref_type=MethodCatalogSnapshotRef,
                    )
                    preflight_report_ref = await run_blocking_async(
                        persist_preflight_report,
                        store,
                        preflight_report,
                        inputs=[
                            InputRef(
                                artifact_id=_artifact_ref_from_sha(
                                    execution_plan_ref_str,
                                    kind="scientist.execution_plan",
                                ).artifact_id,
                                role="execution_plan",
                            ),
                            InputRef(
                                artifact_id=_artifact_ref_from_sha(
                                    method_catalog_snapshot_ref_str,
                                    kind="foundry.method_catalog_snapshot",
                                ).artifact_id,
                                role="method_catalog_snapshot",
                            ),
                        ],
                    )
                    preflight_report_ref_str = str(preflight_report_ref.artifact_id)
                    preflight_ready = bool(preflight_report.ready_to_run)
                    preflight_diagnostics = [
                        item.model_dump(mode="json") for item in preflight_report.diagnostics
                    ]
                    _append_step(
                        agent="preflight",
                        action="validate_execution_plan",
                        summary="Preflight completed",
                        status="ok" if preflight_ready else "warn",
                        details={
                            "ready_to_run": preflight_ready,
                            "diagnostics_count": len(preflight_diagnostics),
                            "preflight_report_ref": preflight_report_ref_str,
                        },
                    )

                    iteration_state = IterationState(
                        schema_version="1.0",
                        run_id=run_id,
                        iteration=1,
                        lifecycle_state="plan_created",
                        plan_ref=_typed_artifact_ref(
                            execution_plan_ref_str,
                            kind="scientist.execution_plan",
                            ref_type=ExecutionPlanRef,
                        ),
                        preflight_report_ref=_typed_artifact_ref(
                            preflight_report_ref_str,
                            kind="scientist.preflight_report",
                            ref_type=PreflightReportRef,
                        ),
                    )
                    iteration_state = transition(
                        iteration_state,
                        "start_preflight",
                        notes=["preflight_started"],
                    )
                    if preflight_ready:
                        iteration_state = transition(
                            iteration_state,
                            "preflight_ready",
                            notes=["ready_to_run"],
                        )
                    else:
                        iteration_state = transition(
                            iteration_state,
                            "preflight_failed",
                            notes=["replanning_required"],
                        )
                        # Lightweight replanning strategy: keep data_needs, clear method DAG.
                        execution_plan = execution_plan.model_copy(
                            update={
                                "method_dag": [],
                                "method_edges": [],
                                "notes": list(execution_plan.notes)
                                + ["replanned_after_preflight_diagnostics"],
                            }
                        )
                        execution_plan_ref_obj = await run_blocking_async(
                            persist_execution_plan,
                            store,
                            execution_plan,
                        )
                        execution_plan_ref_str = str(execution_plan_ref_obj.artifact_id)
                        preflight_report = preflight_execution_plan(execution_plan, catalog_snapshot)
                        preflight_report.plan_ref = _typed_artifact_ref(
                            execution_plan_ref_str,
                            kind="scientist.execution_plan",
                            ref_type=ExecutionPlanRef,
                        )
                        preflight_report.catalog_snapshot_ref = _typed_artifact_ref(
                            method_catalog_snapshot_ref_str,
                            kind="foundry.method_catalog_snapshot",
                            ref_type=MethodCatalogSnapshotRef,
                        )
                        preflight_report_ref = await run_blocking_async(
                            persist_preflight_report,
                            store,
                            preflight_report,
                        )
                        preflight_report_ref_str = str(preflight_report_ref.artifact_id)
                        preflight_ready = bool(preflight_report.ready_to_run)
                        preflight_diagnostics = [
                            item.model_dump(mode="json") for item in preflight_report.diagnostics
                        ]
                        _append_step(
                            agent="preflight",
                            action="replan_after_diagnostics",
                            summary="ExecutionPlan replanned after preflight diagnostics",
                            status="warn",
                            details={
                                "ready_to_run": preflight_ready,
                                "diagnostics_count": len(preflight_diagnostics),
                            },
                        )
                        if preflight_ready:
                            iteration_state = transition(
                                iteration_state,
                                "replan",
                                notes=["replan_completed"],
                            )
                            iteration_state = transition(
                                iteration_state,
                                "start_preflight",
                                notes=["preflight_rerun"],
                            )
                            iteration_state = transition(
                                iteration_state,
                                "preflight_ready",
                                notes=["ready_after_replan"],
                            )
                        else:
                            notes.append("preflight_failed_after_replan")

                    iteration_state_ref = await run_blocking_async(
                        persist_iteration_state,
                        store,
                        iteration_state,
                    )
                    iteration_state_ref_str = str(iteration_state_ref.artifact_id)

                    resolve_request = DataResolveRequest(
                        data_needs=data_needs or [DataNeed(metric="generic.policy.context")],
                        mode="hybrid",
                        allow_explore_fallback=True,
                    )
                    resolve_outcome = await _capture_step(
                        agent="source_resolver",
                        action="resolve_fast_lane",
                        coro=run_blocking_async(retrieval.resolve, resolve_request),
                        summary="Resolved data needs into fetch plans",
                        details={"data_needs": len(data_needs)},
                    )
                    retrieval_telemetry = dict(resolve_outcome.telemetry)
                    retrieval_mode = str(resolve_outcome.mode)
                    retrieval_lane_used = str(
                        retrieval_telemetry.get("lane_used")
                        or retrieval_telemetry.get("lane")
                        or "none"
                    )
                    retrieval_metadata_docs_fetched = int(
                        retrieval_telemetry.get("metadata_docs_fetched") or 0
                    )
                    retrieval_index_size_bytes = int(
                        retrieval_telemetry.get("local_index_size_bytes") or 0
                    )
                    retrieval_index_docs_total = int(
                        retrieval_telemetry.get("local_index_docs_total") or 0
                    )
                    retrieval_candidates_filtered = int(
                        retrieval_telemetry.get("candidates_filtered") or 0
                    )
                    phase_rows = retrieval_telemetry.get("phases") or []
                    if isinstance(phase_rows, list):
                        for phase in phase_rows:
                            if not isinstance(phase, dict):
                                continue
                            phase_name = str(phase.get("phase") or "unknown")
                            retrieval_phase_durations[phase_name] = int(
                                phase.get("duration_ms") or 0
                            )
                            if phase_name == "discover_explore_lane":
                                _append_step(
                                    agent="source_resolver",
                                    action="discover_explore_lane",
                                    summary="ExploreLane discovery executed",
                                    details={
                                        "docs_fetched": int(phase.get("docs_fetched") or 0),
                                        "candidates_total": int(
                                            phase.get("candidates_total") or 0
                                        ),
                                        "candidates_selected": int(
                                            phase.get("candidates_selected") or 0
                                        ),
                                    },
                                )

                    execute_outcome = None
                    if resolve_outcome.fetch_plans:
                        def _promotion_candidate_payload(item: Any) -> dict[str, Any]:
                            if hasattr(item, "model_dump"):
                                return dict(item.model_dump(mode="json"))
                            if isinstance(item, dict):
                                return dict(item)
                            return {
                                "promotion_id": getattr(item, "promotion_id", None),
                                "candidate": repr(item),
                            }

                        def _promotion_candidate_id(item: Any) -> str | None:
                            if isinstance(item, dict):
                                value = item.get("promotion_id")
                            else:
                                value = getattr(item, "promotion_id", None)
                            return str(value) if value else None

                        list_promotion_candidates = getattr(
                            retrieval,
                            "list_promotion_candidates",
                            None,
                        )
                        promotion_candidates_before = (
                            list(raw_candidates_before)
                            if callable(list_promotion_candidates)
                            and isinstance((raw_candidates_before := list_promotion_candidates()), list | tuple | set)
                            else []
                        )
                        promotion_ids_before = {
                            promotion_id
                            for item in promotion_candidates_before
                            if (promotion_id := _promotion_candidate_id(item)) is not None
                        }
                        execute_outcome = await _capture_step(
                            agent="executor",
                            action="fetch_execute",
                            coro=run_blocking_async(
                                retrieval.execute_fetch_plans,
                                list(resolve_outcome.fetch_plans),
                                persist_payload=False,
                                allow_fallback=True,
                            ),
                            summary="Executed fetch plans",
                            details={"fetch_plans": len(resolve_outcome.fetch_plans)},
                        )
                        preview_rejected = sum(
                            1
                            for item in execute_outcome.previews
                            if not bool(item.preview.coverage_ok)
                        )
                        _append_step(
                            agent="executor",
                            action="preview_gate",
                            summary="Preview gate completed",
                            status="warn" if preview_rejected > 0 else "ok",
                            details={
                                "plans_total": len(execute_outcome.previews),
                                "coverage_rejected": preview_rejected,
                                "fallback_triggered": execute_outcome.fallback_triggered_count,
                            },
                        )
                        retrieval_candidates_promoted = int(execute_outcome.promoted_count)
                        promotion_candidates_after = (
                            list(raw_candidates_after)
                            if callable(list_promotion_candidates)
                            and isinstance((raw_candidates_after := list_promotion_candidates()), list | tuple | set)
                            else []
                        )
                        promotion_candidates = [
                            _promotion_candidate_payload(item)
                            for item in promotion_candidates_after
                            if (promotion_id := _promotion_candidate_id(item)) is not None
                            and promotion_id not in promotion_ids_before
                        ]
                        _append_step(
                            agent="promotion_lane",
                            action="promotion_signal_emit",
                            summary="Promotion signals emitted",
                            details={"candidates_promoted": retrieval_candidates_promoted},
                        )
                        def _json_payload(item: Any) -> dict[str, Any]:
                            if hasattr(item, "model_dump"):
                                return dict(item.model_dump(mode="json"))
                            if isinstance(item, dict):
                                return dict(item)
                            return dict(vars(item))

                        data_context_payload = {
                            "metrics": [
                                metric.model_dump(mode="json")
                                for metric in execute_outcome.data_context.metrics
                            ],
                            "metadata_docs_fetched": execute_outcome.data_context.metadata_docs_fetched,
                            "index_docs_total": execute_outcome.data_context.index_docs_total,
                            "index_size_bytes": execute_outcome.data_context.index_size_bytes,
                        }
                        retrieval_context_payload["fetch_plans"] = [
                            _json_payload(item)
                            for item in resolve_outcome.fetch_plans
                        ]
                        retrieval_context_payload["promotion_candidates"] = promotion_candidates
                    else:
                        _append_step(
                            agent="executor",
                            action="fetch_execute",
                            summary="No fetch plans resolved",
                            status="warn",
                            details={"fetch_plans": 0},
                            )

                    if _is_auto_materialization_enabled():
                        try:
                            auto_data_source_refs = await _materialize_retrieval_artifacts(
                                variant_id=variant_id,
                                data_context_payload=data_context_payload or {"metrics": []},
                                retrieval_telemetry=retrieval_telemetry,
                            )
                            _append_step(
                                agent="executor",
                                action="materialize_data_artifacts",
                                summary="Retrieval materialized into DataSnapshot/InputBindings",
                                details={
                                    "data_snapshot_ref": auto_data_source_refs.get(
                                        "data_snapshot_ref"
                                    ),
                                    "input_bindings_ref": auto_data_source_refs.get(
                                        "input_bindings_ref"
                                    ),
                                },
                            )
                            retrieval_context_payload["auto_data_source_refs"] = dict(
                                auto_data_source_refs
                            )
                        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
                            notes.append(f"auto_materialization_failed:{exc}")
                            _append_step(
                                agent="executor",
                                action="materialize_data_artifacts",
                                summary="Retrieval materialization failed",
                                status="warn",
                                details={"error": str(exc)},
                            )

                    fabric_flags_active = (
                        _is_scientist_v2_enabled() or _is_scientist_shadow_mode()
                    )
                    if fabric_flags_active:
                        from polisyos.scientist.agent.fabric import (
                            ScientistAgentFabric,
                            ScientistAgentFabricConfig,
                            ScientistAgentFabricRequest,
                        )

                        fabric = ScientistAgentFabric(
                            config=ScientistAgentFabricConfig.from_env()
                        )
                        fabric_request = ScientistAgentFabricRequest(
                            run_id=run_id,
                            variant_id=variant_id,
                            model_name=model_name,
                            llm_client=llm_client,
                            problem_frame=problem_frame,
                            data_context=dict(data_context_payload or {}),
                            drafter=drafter,
                            formalizer=formalizer,
                            critic=critic,
                            artifact_store=store,
                            max_iterations=max_iterations,
                        )
                        if fabric.config.shadow_mode:
                            fabric_shadow_task = asyncio.create_task(fabric.run(fabric_request))
                        elif fabric.config.enabled:
                            fabric_result = await _capture_step(
                                agent="scientist_v2",
                                action="fabric_run",
                                coro=fabric.run(fabric_request),
                                summary="Scientist v2 orchestration completed",
                            )

                    verdict = "NEEDS_REVISION"
                    issue_count = 0
                    if fabric_result is not None:
                        draft = fabric_result.draft
                        trinity_bundle = fabric_result.trinity_bundle
                        verdict = fabric_result.critique.verdict
                        issue_count = len(fabric_result.critique.issues)
                        evaluator_payload = dict(fabric_result.metrics or {})
                        _append_step(
                            agent="scientist_v2",
                            action="fabric_summary",
                            summary="Scientist v2 result accepted",
                            details={
                                "result": dict(fabric_result.result or {}),
                                "traces": dict(fabric_result.traces or {}),
                                "metrics": dict(fabric_result.metrics or {}),
                            },
                        )
                    else:
                        draft = await _capture_step(
                            agent="drafter",
                            action="draft_policy",
                            coro=drafter.draft_policy(
                                problem_frame,
                                data_context=data_context_payload or None,
                            ),
                            summary="Draft generated",
                        )
                        trinity_bundle = await _capture_step(
                            agent="formalizer",
                            action="formalize",
                            coro=formalizer.formalize(draft),
                            summary="Trinity bundle formalized",
                        )

                        if preflight_ready:
                            try:
                                iteration_state = transition(
                                    iteration_state,
                                    "start_execute",
                                    notes=["execution_started"],
                                )
                                iteration_state = transition(
                                    iteration_state,
                                    "execute_done",
                                    notes=["execution_phase_complete"],
                                )
                            except ValueError as exc:
                                logger.debug(
                                    "Iteration state execute transition failed for run %s: %s",
                                    run_id,
                                    exc,
                                )
                                notes.append("iteration_state_execute_transition_failed")
                        for iteration in range(max_iterations):
                            critique = await _capture_step(
                                agent="critic",
                                action="critique",
                                coro=critic.critique(trinity_bundle, problem_frame),
                                summary=f"Critique iteration {iteration + 1}",
                                details={"iteration": iteration + 1},
                            )
                            verdict = critique.verdict
                            issue_count = len(critique.issues)

                            usage_snapshot = _sum_call_events(call_events)
                            budget_remaining_ratio = None
                            if per_model_budget_usd is not None and float(per_model_budget_usd) > 0:
                                budget_remaining_ratio = max(
                                    0.0,
                                    (float(per_model_budget_usd) - float(usage_snapshot["cost_usd"]))
                                    / float(per_model_budget_usd),
                                )
                            retrieval_quality = (
                                1.0
                                if retrieval_candidates_filtered == 0
                                else max(
                                    0.0,
                                    1.0
                                    - (
                                        float(retrieval_candidates_filtered)
                                        / float(
                                            max(
                                                1,
                                                retrieval_candidates_filtered + len(data_context_payload.get("metrics", [])),
                                            )
                                        )
                                    ),
                                )
                            )
                            evaluator_report = evaluate_iteration(
                                issue_count=issue_count,
                                verdict=critique.verdict,
                                retrieval_quality=retrieval_quality,
                                budget_remaining_ratio=budget_remaining_ratio,
                            )
                            evaluator_report_ref = await run_blocking_async(
                                persist_evaluator_report,
                                store,
                                evaluator_report,
                            )
                            evaluator_report_ref_str = str(evaluator_report_ref.artifact_id)
                            evaluator_payload = evaluator_report.model_dump(mode="json")
                            _append_step(
                                agent="evaluator",
                                action="score_iteration",
                                summary=f"Evaluator verdict: {evaluator_report.verdict}",
                                status="ok" if evaluator_report.verdict == "APPROVE" else "warn",
                                details={
                                    "iteration": iteration + 1,
                                    "verdict": evaluator_report.verdict,
                                    "scores": evaluator_payload.get("scores"),
                                    "evaluator_report_ref": evaluator_report_ref_str,
                                },
                            )
                            try:
                                if evaluator_report.verdict == "APPROVE":
                                    iteration_state = transition(
                                        iteration_state,
                                        "approve",
                                        verdict=evaluator_report.verdict,
                                        stop_reason="approved",
                                        notes=["approved_by_evaluator"],
                                    )
                                elif evaluator_report.verdict == "STOP_BUDGET":
                                    iteration_state = transition(
                                        iteration_state,
                                        "stop_budget",
                                        verdict=evaluator_report.verdict,
                                        stop_reason="budget_exhausted",
                                        notes=["stopped_by_budget_guard"],
                                    )
                                else:
                                    iteration_state = transition(
                                        iteration_state,
                                        "replan",
                                        verdict=evaluator_report.verdict,
                                        notes=[f"replanning_due_to:{evaluator_report.verdict}"],
                                    )
                            except ValueError as exc:
                                logger.debug(
                                    "Iteration state evaluator transition failed for run %s: %s",
                                    run_id,
                                    exc,
                                )
                                notes.append("iteration_state_evaluator_transition_failed")

                            if evaluator_report.verdict == "APPROVE":
                                verdict = "APPROVE"
                                break
                            if evaluator_report.verdict == "STOP_BUDGET":
                                verdict = "STOP_BUDGET"
                                notes.append("evaluator_stop_budget")
                                break
                            if iteration < max_iterations - 1:
                                draft = await _capture_step(
                                    agent="drafter",
                                    action="refine_draft",
                                    coro=drafter.refine_draft(draft, critique),
                                    summary="Draft refined",
                                    status="warn",
                                    details={"iteration": iteration + 1},
                                )
                                trinity_bundle = await _capture_step(
                                    agent="formalizer",
                                    action="formalize",
                                    coro=formalizer.formalize(draft),
                                    summary="Trinity bundle re-formalized",
                                    status="warn",
                                    details={"iteration": iteration + 1},
                                )
                                if preflight_ready:
                                    try:
                                        iteration_state = transition(
                                            iteration_state,
                                            "start_preflight",
                                            notes=["iteration_replan_preflight_start"],
                                        )
                                        iteration_state = transition(
                                            iteration_state,
                                            "preflight_ready",
                                            notes=["iteration_replan_preflight_ready"],
                                        )
                                        iteration_state = transition(
                                            iteration_state,
                                            "start_execute",
                                            notes=["iteration_reexecution_start"],
                                        )
                                        iteration_state = transition(
                                            iteration_state,
                                            "execute_done",
                                            notes=["iteration_reexecution_done"],
                                        )
                                    except ValueError as exc:
                                        logger.debug(
                                            "Iteration replan transition failed for run %s: %s",
                                            run_id,
                                            exc,
                                        )
                                        notes.append("iteration_state_replan_transition_failed")

                    if fabric_shadow_task is not None:
                        try:
                            fabric_shadow_result = await fabric_shadow_task
                            fabric_shadow_comparison = _build_scientist_v2_shadow_comparison(
                                legacy_status="completed",
                                legacy_verdict=verdict,
                                legacy_issue_count=int(issue_count),
                                legacy_cost_usd=float(_sum_call_events(call_events)["cost_usd"]),
                                legacy_prompt_tokens=int(_sum_call_events(call_events)["prompt_tokens"]),
                                legacy_completion_tokens=int(_sum_call_events(call_events)["completion_tokens"]),
                                shadow_result=fabric_shadow_result,
                            )
                            _append_step(
                                agent="scientist_v2",
                                action="shadow_run",
                                summary="Scientist v2 shadow run completed",
                                details={
                                    "result": dict(fabric_shadow_result.result or {}),
                                    "traces": dict(fabric_shadow_result.traces or {}),
                                    "metrics": dict(fabric_shadow_result.metrics or {}),
                                    "comparison": dict(fabric_shadow_comparison or {}),
                                },
                            )
                        except Exception as exc:  # noqa: BLE001
                            notes.append(f"scientist_v2_shadow_failed:{exc}")
                            _append_step(
                                agent="scientist_v2",
                                action="shadow_run",
                                summary="Scientist v2 shadow run failed",
                                status="warn",
                                details={"error": str(exc)},
                            )
                    iteration_state_ref = await run_blocking_async(
                        persist_iteration_state,
                        store,
                        iteration_state,
                    )
                    iteration_state_ref_str = str(iteration_state_ref.artifact_id)
                except (AttributeError, LookupError, RuntimeError, TypeError, ValueError) as exc:  # pragma: no cover - defensive pipeline hardening
                    logger.exception("NL variant failed for model '%s': %s", model_name, exc)
                    return {
                        "model_variant_id": variant_id,
                        "model": model_name,
                        "provider": provider,
                        "status": "failed",
                        "verdict": "ERROR",
                        "issue_count": 0,
                        "prompt_tokens": int(_sum_call_events(call_events)["prompt_tokens"]),
                        "completion_tokens": int(_sum_call_events(call_events)["completion_tokens"]),
                        "total_tokens": int(
                            _sum_call_events(call_events)["prompt_tokens"]
                            + _sum_call_events(call_events)["completion_tokens"]
                        ),
                        "latency_ms": max(0, _now_ms() - variant_started_at),
                        "cost_usd": round(_sum_call_events(call_events)["cost_usd"], 8),
                        "cost_reconciliation_delta_usd": round(
                            _sum_call_events(call_events)["cost_delta_usd"],
                            8,
                        ),
                        "started_at": variant_started_iso,
                        "finished_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                        "steps": steps,
                        "notes": notes + [f"variant_error:{exc}"],
                        "retrieval_mode": retrieval_mode,
                        "retrieval_lane_used": retrieval_lane_used,
                        "metadata_docs_fetched": retrieval_metadata_docs_fetched,
                        "local_index_size_bytes": retrieval_index_size_bytes,
                        "local_index_docs_total": retrieval_index_docs_total,
                        "candidates_filtered": retrieval_candidates_filtered,
                        "candidates_promoted": retrieval_candidates_promoted,
                        "retrieval_phase_durations": retrieval_phase_durations,
                        "retrieval_telemetry": retrieval_telemetry,
                        "execution_plan_ref": execution_plan_ref_str,
                        "method_catalog_snapshot_ref": method_catalog_snapshot_ref_str,
                        "preflight_report_ref": preflight_report_ref_str,
                        "preflight_ready": preflight_ready,
                        "preflight_diagnostics": preflight_diagnostics,
                        "evaluator_report_ref": evaluator_report_ref_str,
                        "evaluator": evaluator_payload,
                        "iteration_state_ref": iteration_state_ref_str,
                        "auto_data_source_refs": auto_data_source_refs,
                        "reproducibility_manifest_ref": reproducibility_manifest_ref_str,
                        "retrieval_context": retrieval_context_payload,
                        "scientist_v2": (
                            {
                                "result": dict(fabric_result.result or {}),
                                "traces": dict(fabric_result.traces or {}),
                                "metrics": dict(fabric_result.metrics or {}),
                            }
                            if fabric_result is not None
                            else None
                        ),
                        "scientist_v2_shadow": (
                            {
                                "result": dict(fabric_shadow_result.result or {}),
                                "traces": dict(fabric_shadow_result.traces or {}),
                                "metrics": dict(fabric_shadow_result.metrics or {}),
                                "comparison": dict(fabric_shadow_comparison or {}),
                            }
                            if fabric_shadow_result is not None
                            else None
                        ),
                        "_bundle": None,
                    }

                usage = _sum_call_events(call_events)
                variant_cost = round(float(usage["cost_usd"]), 8)
                status = "completed"
                if per_model_budget_usd is not None and variant_cost > float(per_model_budget_usd):
                    status = "budget_exceeded"
                    notes.append("per_model_budget_exceeded")
                if llm_client is None and model_name:
                    status = "fallback_mock"

                trinity_ref_str = await _store_bundle(trinity_bundle)
                try:
                    repro_manifest = build_reproducibility_manifest(
                        run_id=run_id,
                        iteration=1,
                        seed=int(context.get("random_seed", 0) or 0),
                        plan=execution_plan,
                        registry_bundle_ref=auto_data_source_refs.get("registry_bundle_ref"),
                        method_catalog_snapshot_ref=method_catalog_snapshot_ref_str,
                        data_snapshot_ref=auto_data_source_refs.get("data_snapshot_ref"),
                        input_bindings_ref=auto_data_source_refs.get("input_bindings_ref"),
                    )
                    repro_manifest_ref = await run_blocking_async(
                        persist_reproducibility_manifest,
                        store,
                        repro_manifest,
                    )
                    reproducibility_manifest_ref_str = str(repro_manifest_ref.artifact_id)
                except (OSError, RuntimeError, TypeError, ValueError) as exc:
                    notes.append(f"reproducibility_manifest_failed:{exc}")
                    return {
                        "model_variant_id": variant_id,
                        "model": model_name,
                        "provider": provider,
                        "status": status,
                        "verdict": verdict,
                        "issue_count": int(issue_count),
                        "prompt_tokens": int(usage["prompt_tokens"]),
                        "completion_tokens": int(usage["completion_tokens"]),
                        "total_tokens": int(usage["prompt_tokens"] + usage["completion_tokens"]),
                        "latency_ms": max(0, _now_ms() - variant_started_at),
                        "cost_usd": variant_cost,
                        "cost_reconciliation_delta_usd": round(
                            float(usage["cost_delta_usd"]),
                            8,
                        ),
                        "trinity_bundle_ref": trinity_ref_str,
                        "started_at": variant_started_iso,
                        "finished_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                        "steps": steps,
                        "notes": notes,
                        "retrieval_mode": retrieval_mode,
                        "retrieval_lane_used": retrieval_lane_used,
                        "metadata_docs_fetched": retrieval_metadata_docs_fetched,
                        "local_index_size_bytes": retrieval_index_size_bytes,
                        "local_index_docs_total": retrieval_index_docs_total,
                        "candidates_filtered": retrieval_candidates_filtered,
                        "candidates_promoted": retrieval_candidates_promoted,
                        "retrieval_phase_durations": retrieval_phase_durations,
                        "retrieval_telemetry": retrieval_telemetry,
                        "execution_plan_ref": execution_plan_ref_str,
                        "method_catalog_snapshot_ref": method_catalog_snapshot_ref_str,
                        "preflight_report_ref": preflight_report_ref_str,
                        "preflight_ready": preflight_ready,
                        "preflight_diagnostics": preflight_diagnostics,
                        "evaluator_report_ref": evaluator_report_ref_str,
                        "evaluator": evaluator_payload,
                        "iteration_state_ref": iteration_state_ref_str,
                        "auto_data_source_refs": auto_data_source_refs,
                        "reproducibility_manifest_ref": reproducibility_manifest_ref_str,
                        "retrieval_context": retrieval_context_payload,
                        "scientist_v2": (
                            {
                                "result": dict(fabric_result.result or {}),
                                "traces": dict(fabric_result.traces or {}),
                                "metrics": dict(fabric_result.metrics or {}),
                            }
                            if fabric_result is not None
                            else None
                        ),
                        "scientist_v2_shadow": (
                            {
                                "result": dict(fabric_shadow_result.result or {}),
                                "traces": dict(fabric_shadow_result.traces or {}),
                                "metrics": dict(fabric_shadow_result.metrics or {}),
                                "comparison": dict(fabric_shadow_comparison or {}),
                            }
                            if fabric_shadow_result is not None
                            else None
                        ),
                        "_bundle": trinity_bundle,
                    }

                return {
                    "model_variant_id": variant_id,
                    "model": model_name,
                    "provider": provider,
                    "status": status,
                    "verdict": verdict,
                    "issue_count": int(issue_count),
                    "prompt_tokens": int(usage["prompt_tokens"]),
                    "completion_tokens": int(usage["completion_tokens"]),
                    "total_tokens": int(usage["prompt_tokens"] + usage["completion_tokens"]),
                    "latency_ms": max(0, _now_ms() - variant_started_at),
                    "cost_usd": variant_cost,
                    "cost_reconciliation_delta_usd": round(
                        float(usage["cost_delta_usd"]),
                        8,
                    ),
                    "trinity_bundle_ref": trinity_ref_str,
                    "started_at": variant_started_iso,
                    "finished_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    "steps": steps,
                    "notes": notes,
                    "retrieval_mode": retrieval_mode,
                    "retrieval_lane_used": retrieval_lane_used,
                    "metadata_docs_fetched": retrieval_metadata_docs_fetched,
                    "local_index_size_bytes": retrieval_index_size_bytes,
                    "local_index_docs_total": retrieval_index_docs_total,
                    "candidates_filtered": retrieval_candidates_filtered,
                    "candidates_promoted": retrieval_candidates_promoted,
                    "retrieval_phase_durations": retrieval_phase_durations,
                    "retrieval_telemetry": retrieval_telemetry,
                    "execution_plan_ref": execution_plan_ref_str,
                    "method_catalog_snapshot_ref": method_catalog_snapshot_ref_str,
                    "preflight_report_ref": preflight_report_ref_str,
                    "preflight_ready": preflight_ready,
                    "preflight_diagnostics": preflight_diagnostics,
                    "evaluator_report_ref": evaluator_report_ref_str,
                    "evaluator": evaluator_payload,
                    "iteration_state_ref": iteration_state_ref_str,
                    "auto_data_source_refs": auto_data_source_refs,
                    "reproducibility_manifest_ref": reproducibility_manifest_ref_str,
                    "retrieval_context": retrieval_context_payload,
                    "scientist_v2": (
                        {
                            "result": dict(fabric_result.result or {}),
                            "traces": dict(fabric_result.traces or {}),
                            "metrics": dict(fabric_result.metrics or {}),
                        }
                        if fabric_result is not None
                        else None
                    ),
                    "scientist_v2_shadow": (
                        {
                            "result": dict(fabric_shadow_result.result or {}),
                            "traces": dict(fabric_shadow_result.traces or {}),
                            "metrics": dict(fabric_shadow_result.metrics or {}),
                            "comparison": dict(fabric_shadow_comparison or {}),
                        }
                        if fabric_shadow_result is not None
                        else None
                    ),
                    "_bundle": trinity_bundle,
                }

            variants: list[dict[str, Any]] = []
            if not models_to_run:
                variants.append(await _run_variant(None, 0))
            else:
                run_budget_spent = 0.0
                run_budget_stop = False
                sem = asyncio.Semaphore(max(1, min(max_parallel_models, len(models_to_run))))
                budget_lock = asyncio.Lock()

                async def _run_with_limits(idx: int, model_name: str) -> dict[str, Any]:
                    nonlocal run_budget_spent, run_budget_stop
                    async with sem:
                        async with budget_lock:
                            if run_budget_stop:
                                return {
                                    "model_variant_id": _normalize_model_variant_id(model_name, idx),
                                    "model": model_name,
                                    "provider": "gateway",
                                    "status": "skipped_budget_guard",
                                    "verdict": None,
                                    "issue_count": 0,
                                    "prompt_tokens": 0,
                                    "completion_tokens": 0,
                                    "total_tokens": 0,
                                    "latency_ms": 0,
                                    "cost_usd": 0.0,
                                    "started_at": None,
                                    "finished_at": None,
                                    "steps": [],
                                    "notes": ["run_budget_guard_prevented_start"],
                                    "_bundle": None,
                                }
                        variant = await _run_variant(model_name, idx)
                        async with budget_lock:
                            run_budget_spent += float(variant.get("cost_usd") or 0.0)
                            if run_budget_usd is not None and run_budget_spent >= float(run_budget_usd):
                                run_budget_stop = True
                        return variant

                tasks = [
                    asyncio.create_task(_run_with_limits(index, model_name))
                    for index, model_name in enumerate(models_to_run)
                ]
                variants = await asyncio.gather(*tasks)

            selected_variant: dict[str, Any] | None = None
            approved_candidates = [
                item
                for item in variants
                if item.get("_bundle") is not None and str(item.get("verdict", "")).upper() == "APPROVE"
            ]
            if approved_candidates:
                selected_variant = approved_candidates[0]
            if selected_variant is None:
                non_failed = [
                    item
                    for item in variants
                    if item.get("_bundle") is not None and item.get("status") not in {"failed"}
                ]
                if non_failed:
                    selected_variant = non_failed[0]
            if selected_variant is None:
                if not allow_mock_fallback:
                    raise RuntimeError("mock_fallback_disallowed")
                # Last-resort fallback guarantees a runnable workflow payload only when policy allows it.
                selected_variant = await _run_variant(None, len(variants))
                variants.append(selected_variant)
            selected_variant["selected_for_workflow"] = True

            selected_ref = selected_variant.get("trinity_bundle_ref")
            if not isinstance(selected_ref, str):
                selected_bundle = selected_variant.get("_bundle")
                if selected_bundle is None:
                    raise RuntimeError("No valid model variant produced a Trinity bundle")
                selected_ref = await _store_bundle(selected_bundle)
                selected_variant["trinity_bundle_ref"] = selected_ref

            # 8. Build state and run workflow
            inputs: dict[str, Any] = {
                "trinity_bundle_ref": _make_artifact_ref(
                    selected_ref, kind="ir.trinity_bundle"
                ),
            }

            # Add data source if provided
            if data_source:
                ds_key, ds_value = _resolve_data_source(data_source)
                inputs[ds_key] = _make_artifact_ref(
                    ds_value, kind=_DATA_SOURCE_KEYS[ds_key]
                )
            else:
                auto_refs = selected_variant.get("auto_data_source_refs")
                if isinstance(auto_refs, dict):
                    snapshot_ref = auto_refs.get("data_snapshot_ref")
                    bindings_ref = auto_refs.get("input_bindings_ref")
                    registry_ref = auto_refs.get("registry_bundle_ref")
                    if isinstance(snapshot_ref, str) and snapshot_ref:
                        inputs["data_snapshot_ref"] = _make_artifact_ref(
                            snapshot_ref,
                            kind=_DATA_SOURCE_KEYS["data_snapshot_ref"],
                        )
                    if isinstance(bindings_ref, str) and bindings_ref:
                        inputs["input_bindings_ref"] = _make_artifact_ref(
                            bindings_ref,
                            kind=_DATA_SOURCE_KEYS["input_bindings_ref"],
                        )
                    if isinstance(registry_ref, str) and registry_ref:
                        inputs["registry_bundle_ref"] = _make_artifact_ref(
                            registry_ref,
                            kind="core.registry_bundle",
                        )

            state_payload = _canonicalize_numeric_payload(
                {
                    "run_id": run_id,
                    "inputs": inputs,
                    "control_job_id": control_job_id,
                    "execution_profile": execution_profile,
                    "params": {
                        "nl_request": nl_request,
                        "agent_circuit": True,
                        "llm_model": selected_variant.get("model"),
                        "llm_models": [item.get("model") for item in variants if item.get("model")],
                        "llm_selected_variant_id": selected_variant.get("model_variant_id"),
                        "llm_prompt_tokens": int(selected_variant.get("prompt_tokens") or 0),
                        "llm_completion_tokens": int(selected_variant.get("completion_tokens") or 0),
                        "llm_cost_usd": float(selected_variant.get("cost_usd") or 0.0),
                        "llm_cost_reconciliation_delta_usd": float(
                            selected_variant.get("cost_reconciliation_delta_usd") or 0.0
                        ),
                        "run_cost_usd": round(
                            sum(float(item.get("cost_usd") or 0.0) for item in variants),
                            8,
                        ),
                        "llm_model_variants": [
                            {
                                key: value
                                for key, value in item.items()
                                if not key.startswith("_")
                            }
                            for item in variants
                        ],
                        "llm_multimodel_enabled": _is_multimodel_enabled(),
                        "run_budget_usd": run_budget_usd,
                        "per_model_budget_usd": per_model_budget_usd,
                        "max_parallel_models": max_parallel_models,
                        "checkpoint_policy": checkpoint_policy,
                        "unified_dag_enabled": _is_unified_dag_enabled(),
                        "required_preflight_enabled": _is_required_preflight_enabled(),
                        "auto_materialization_enabled": _is_auto_materialization_enabled(),
                        "retrieval_mode": selected_variant.get("retrieval_mode"),
                        "retrieval_lane_used": selected_variant.get("retrieval_lane_used"),
                        "retrieval_metadata_docs_fetched": int(
                            selected_variant.get("metadata_docs_fetched") or 0
                        ),
                        "retrieval_local_index_size_bytes": int(
                            selected_variant.get("local_index_size_bytes") or 0
                        ),
                        "retrieval_local_index_docs_total": int(
                            selected_variant.get("local_index_docs_total") or 0
                        ),
                        "retrieval_candidates_filtered": int(
                            selected_variant.get("candidates_filtered") or 0
                        ),
                        "retrieval_candidates_promoted": int(
                            selected_variant.get("candidates_promoted") or 0
                        ),
                        "retrieval_phase_durations": dict(
                            selected_variant.get("retrieval_phase_durations") or {}
                        ),
                        "retrieval_telemetry": selected_variant.get("retrieval_telemetry") or {},
                        "execution_plan_ref": selected_variant.get("execution_plan_ref"),
                        "method_catalog_snapshot_ref": selected_variant.get(
                            "method_catalog_snapshot_ref"
                        ),
                        "preflight_report_ref": selected_variant.get("preflight_report_ref"),
                        "preflight_ready": bool(selected_variant.get("preflight_ready")),
                        "preflight_diagnostics": list(
                            selected_variant.get("preflight_diagnostics") or []
                        ),
                        "evaluator_report_ref": selected_variant.get("evaluator_report_ref"),
                        "evaluator": dict(selected_variant.get("evaluator") or {}),
                        "iteration_state_ref": selected_variant.get("iteration_state_ref"),
                        "reproducibility_manifest_ref": selected_variant.get(
                            "reproducibility_manifest_ref"
                        ),
                        "stop_criteria": dict(stop_criteria_payload or {}),
                        "governance_constraints": list(governance_constraints_payload or []),
                        "expected_outputs": list(expected_outputs_payload or []),
                        "context": context,
                        "retrieval_context": dict(selected_variant.get("retrieval_context") or {}),
                        "scientist_v2_enabled": _is_scientist_v2_enabled(),
                        "scientist_v2_shadow_mode": _is_scientist_shadow_mode(),
                        "scientist_web_search_enabled": _is_scientist_web_search_enabled(),
                        "scientist_swarm_enabled": _is_scientist_swarm_enabled(),
                        "scientist_reflexion_enabled": _is_scientist_reflexion_enabled(),
                        "scientist_v2": dict(selected_variant.get("scientist_v2") or {}),
                        "scientist_v2_shadow": dict(
                            selected_variant.get("scientist_v2_shadow") or {}
                        ),
                    },
                }
            )
            if isinstance(current_capability_manifest_ref, str) and current_capability_manifest_ref:
                state_payload["capability_manifest_ref"] = _make_artifact_ref(
                    current_capability_manifest_ref,
                    kind="runtime.capability_manifest",
                )
            execution_plan_ref_value = selected_variant.get("execution_plan_ref")
            if isinstance(execution_plan_ref_value, str) and execution_plan_ref_value:
                state_payload["execution_plan_ref"] = _make_artifact_ref(
                    execution_plan_ref_value,
                    kind="scientist.execution_plan",
                )
            method_catalog_ref_value = selected_variant.get("method_catalog_snapshot_ref")
            if isinstance(method_catalog_ref_value, str) and method_catalog_ref_value:
                state_payload["method_catalog_snapshot_ref"] = _make_artifact_ref(
                    method_catalog_ref_value,
                    kind="foundry.method_catalog_snapshot",
                )
            preflight_ref_value = selected_variant.get("preflight_report_ref")
            if isinstance(preflight_ref_value, str) and preflight_ref_value:
                state_payload["preflight_report_ref"] = _make_artifact_ref(
                    preflight_ref_value,
                    kind="scientist.preflight_report",
                )
            evaluator_ref_value = selected_variant.get("evaluator_report_ref")
            if isinstance(evaluator_ref_value, str) and evaluator_ref_value:
                state_payload["evaluator_report_ref"] = _make_artifact_ref(
                    evaluator_ref_value,
                    kind="scientist.evaluator_report",
                )
            iteration_ref_value = selected_variant.get("iteration_state_ref")
            if isinstance(iteration_ref_value, str) and iteration_ref_value:
                state_payload["iteration_state_ref"] = _make_artifact_ref(
                    iteration_ref_value,
                    kind="scientist.iteration_state",
                )
            repro_ref_value = selected_variant.get("reproducibility_manifest_ref")
            if isinstance(repro_ref_value, str) and repro_ref_value:
                state_payload["reproducibility_manifest_ref"] = _make_artifact_ref(
                    repro_ref_value,
                    kind="scientist.reproducibility_manifest",
                )

            from polisyos.scientist.api import run_experiment
            run_experiment(state_payload)
            return {
                "run_id": run_id,
                "capability_manifest_ref": current_capability_manifest_ref,
            }

        return cast("dict[str, Any]", run_coro_sync(_agent_pipeline()))

    # ---- Data ingestion ---------------------------------------------------

    def run_data_ingestion(
        self,
        request: IngestRequest,
        *,
        request_id: str | None = None,
    ) -> IngestResponse:
        """Execute connector ingestion synchronously and return refs/status for produced artifacts."""
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
                "Promotion candidate rejected."
                if updated
                else "Promotion candidate not found."
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
            store, profile, data_snapshot_ref=data_snapshot_ref,
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

    def list_source_profiles(
        self, *, request_id: str | None = None
    ) -> SourceProfilesListResponse:
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

    def list_model_profiles(
        self, *, request_id: str | None = None
    ) -> ModelProfilesListResponse:
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

    # ---- Capabilities -----------------------------------------------------

    def get_capabilities(
        self, *, request_id: str | None = None
    ) -> CapabilityManifestResponse:
        """Return the control-plane capability manifest, execution profiles, and feature gates."""
        causal_contract = build_causal_capability_contract()
        resolved_policy = self._policy_resolver.resolve(
            requested_profile=None,
            policy_flags=PolicyFlags(),
            principal=None,
        )
        features = [
            CapabilityFeatureInfo(
                key="workflow_runs",
                label="Workflow runs",
                description="Launch workflow-backed runs from explicit artifact bindings.",
                category="runs",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="natural_language_runs",
                label="Natural-language runs",
                description="Use the agent circuit to transform NL requests into executable policy runs.",
                category="runs",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="multimodel_nl",
                label="Multi-model NL execution",
                description="Evaluate multiple LLM variants for a single NL request.",
                category="runs",
                enabled=_is_multimodel_enabled(),
            ),
            CapabilityFeatureInfo(
                key="scientist_v2",
                label="Scientist v2 runtime",
                description="Unified v2 facade for web grounding, swarm, and Reflexion orchestration.",
                category="runs",
                enabled=_is_scientist_v2_enabled(),
            ),
            CapabilityFeatureInfo(
                key="scientist_shadow_mode",
                label="Scientist shadow mode",
                description="Run v2 in shadow alongside the legacy Scientist path and keep legacy as return-path.",
                category="runs",
                enabled=_is_scientist_shadow_mode(),
            ),
            CapabilityFeatureInfo(
                key="required_preflight",
                label="Required preflight",
                description="Run execution-plan preflight diagnostics before execution.",
                category="governance",
                enabled=_is_required_preflight_enabled(),
            ),
            CapabilityFeatureInfo(
                key="evaluator_reports",
                label="Evaluator reports",
                description="Persist evaluator verdicts, scores, and replanning hints.",
                category="governance",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="reproducibility_manifests",
                label="Reproducibility manifests",
                description="Expose replay, hash, and determinism metadata for completed runs.",
                category="governance",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="transport_summary",
                label="Transport summary",
                description="Expose transportability summaries on governance and decision surfaces.",
                category="governance",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="promotion_lane",
                label="Promotion lane",
                description="Review and approve ExploreLane candidates into reusable bindings.",
                category="evidence",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="auto_materialization",
                label="Auto materialization",
                description="Materialize retrieval results into snapshots or bindings during NL execution.",
                category="evidence",
                enabled=_is_auto_materialization_enabled(),
            ),
            CapabilityFeatureInfo(
                key="binding_profiles",
                label="Binding profiles",
                description="List reusable binding-profile strategies for structured inputs.",
                category="evidence",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="source_profiles",
                label="Source profiles",
                description="List curated connector/source profiles for ingestion and retrieval.",
                category="evidence",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="scientist_web_search",
                label="Scientist web search",
                description="Enable first-class Scholar web search and citation grounding in the Scientist runtime.",
                category="evidence",
                enabled=_is_scientist_web_search_enabled(),
            ),
            CapabilityFeatureInfo(
                key="scientist_swarm",
                label="Scientist swarm runtime",
                description="Enable supervisor-worker swarm orchestration for research and evaluation facets.",
                category="runtime",
                enabled=_is_scientist_swarm_enabled(),
            ),
            CapabilityFeatureInfo(
                key="scientist_reflexion",
                label="Scientist Reflexion",
                description="Enable evaluator-optimizer retries with persistent memory in the Scientist runtime.",
                category="runtime",
                enabled=_is_scientist_reflexion_enabled(),
            ),
            CapabilityFeatureInfo(
                key="lex_pipeline",
                label="Lex knowledge pipeline",
                description="Trigger, inspect, and search the legal knowledge graph pipeline.",
                category="knowledge",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="unified_dag",
                label="Unified DAG",
                description="Expose unified method DAG execution in NL and workflow paths.",
                category="runtime",
                enabled=_is_unified_dag_enabled(),
            ),
            CapabilityFeatureInfo(
                key="security_admin_layer",
                label="Security / admin layer",
                description="Dedicated tenant/authz/audit admin surfaces.",
                category="platform",
                enabled=False,
                stage="deferred",
            ),
            CapabilityFeatureInfo(
                key="durable_control_plane",
                label="Durable control plane",
                description="Use leased workers, durable state, and outbox-backed control events.",
                category="platform",
                enabled=bool(resolved_policy.fallback_rules.get("durable_control_required")),
            ),
            CapabilityFeatureInfo(
                key="control_plane_local_waiver",
                label="Local control-plane waiver",
                description="Explicit research-only waiver allowing non-durable local control infrastructure.",
                category="platform",
                enabled=bool(resolved_policy.fallback_rules.get("local_control_plane_waiver_active")),
                stage="planned" if not resolved_policy.fallback_rules.get("local_control_plane_waiver_active") else "active",
            ),
        ]
        for feature in project_capability_features(causal_contract):
            features.append(CapabilityFeatureInfo.model_validate(feature))

        return CapabilityManifestResponse(
            meta=_build_api_meta(request_id),
            default_execution_profile=self._policy_resolver.default_profile,
            supported_execution_profiles=list(self._policy_resolver.supported_profiles()),
            worker_backend=self._policy_resolver.worker_backend,
            state_store_backend=self._policy_resolver.state_store_backend,
            security_posture=dict(resolved_policy.security_posture),
            fallback_rules=dict(resolved_policy.fallback_rules),
            workspaces=[
                "command_center",
                "scenario_composer",
                "runs_decisions",
                "evidence_fabric",
                "lex_knowledge",
                "platform_health",
            ],
            features=features,
            constraints={
                "max_parallel_models": 16,
                "max_nl_iterations": 10,
                "artifact_preview_max_bytes": 2_000_000,
                "task_runner": "durable_control_worker",
                "default_locale": "en",
                "supported_locales": ["en", "uk"],
                "durable_control_profiles": ["research", "governed", "production"],
                "local_control_plane_waiver_active": bool(
                    resolved_policy.fallback_rules.get("local_control_plane_waiver_active")
                ),
                "causal_runtime": causal_contract.model_dump(mode="json"),
            },
        )

    # ---- Lex Knowledge Graph -----------------------------------------------

    def trigger_lex_pipeline(
        self,
        request: "LexTriggerRequest",
        *,
        request_id: str | None = None,
        principal: RuntimePrincipal | None = None,
    ) -> "LexTriggerResponse":
        """Queue a Lex batch pipeline job and reject empty stage selections."""
        from polisyos.core.contracts.control import LexTriggerResponse

        pipeline_id = f"lex_{uuid.uuid4().hex[:12]}"
        job_id = uuid.uuid4().hex
        output_dir = Path(request.output_dir)
        policy = self._resolve_execution_policy(
            requested_profile=request.execution_profile,
            policy_flags=request.policy_flags,
            principal=principal,
        )

        # Build stage set from config
        stages: set[str] = set()
        sc = request.stages
        if sc.parse:
            stages.add("parse")
        if sc.structure:
            stages.add("structure")
        if sc.spo:
            stages.add("spo")
        if sc.graph:
            stages.add("graph")
        if sc.embed:
            stages.add("embed")

        if not stages:
            return LexTriggerResponse(
                meta=_build_api_meta(request_id),
                status="rejected",
                pipeline_id=pipeline_id,
                job_id=job_id,
                effective_execution_profile=policy.effective_profile,
                message="No stages selected.",
            )

        self._enqueue_job(
            job_id=job_id,
            job_kind="lex_pipeline",
            run_id=None,
            pipeline_id=pipeline_id,
            payload={
                "pipeline_id": pipeline_id,
                "cards_path": request.cards_path,
                "texts_path": request.texts_path,
                "output_dir": str(output_dir),
                "stages": sorted(stages),
                "status_filter": list(request.status_filter or []),
                "llm_model": request.llm_model,
                "resume": request.resume,
            },
            policy=policy,
            request_id=request_id,
        )

        return LexTriggerResponse(
            meta=_build_api_meta(request_id),
            status="accepted",
            pipeline_id=pipeline_id,
            job_id=job_id,
            effective_execution_profile=policy.effective_profile,
            message=f"Pipeline {pipeline_id} launched with stages: {', '.join(sorted(stages))}",
        )

    def _run_lex_pipeline_job(
        self,
        *,
        job: ControlJobRecord,
        payload: dict[str, Any],
        capability_manifest_ref: str,
    ) -> None:
        import asyncio

        from polisyos.lex.batch.config import BatchConfig
        from polisyos.lex.batch.pipeline import run_batch_pipeline

        output_dir = Path(str(payload["output_dir"]))
        progress = {
            "output_dir": str(output_dir),
            "state": "running",
            "stages": list(payload.get("stages") or []),
        }
        self._control_store.update_progress_state(
            job_id=job.job_id,
            state="running",
            progress=progress,
        )
        config = BatchConfig(
            cards_path=Path(str(payload["cards_path"])),
            texts_path=Path(str(payload["texts_path"])),
            output_dir=output_dir,
            llm_model=str(payload.get("llm_model") or ""),
            stages=frozenset(str(item) for item in (payload.get("stages") or [])),
            resume=bool(payload.get("resume")),
            status_filter=(
                frozenset(str(item) for item in (payload.get("status_filter") or []))
                if payload.get("status_filter")
                else None
            ),
        )
        try:
            asyncio.run(run_batch_pipeline(config))
        except Exception:
            raise
        final_progress = self._collect_lex_progress(
            output_dir=output_dir,
            state="completed",
            existing=progress,
        )
        self._control_store.complete_job(
            job_id=job.job_id,
            pipeline_id=job.pipeline_id,
            capability_manifest_ref=capability_manifest_ref,
            progress=final_progress,
        )

    def get_lex_pipeline_status(
        self,
        pipeline_id: str,
        *,
        request_id: str | None = None,
    ) -> "LexPipelineStatusResponse":
        """Return durable Lex pipeline state merged with file-backed progress summaries."""
        from polisyos.core.contracts.control import LexPipelineStatusResponse

        record = self._control_store.get_job_by_pipeline(pipeline_id)
        if record is None:
            return LexPipelineStatusResponse(
                meta=_build_api_meta(request_id),
                pipeline_id=pipeline_id,
                state="failed",
                error_message="Pipeline not found.",
            )

        info = dict(record.progress)
        output_dir_raw = str(info.get("output_dir") or "").strip()
        output_dir = Path(output_dir_raw) if output_dir_raw else None
        merged_progress = self._collect_lex_progress(
            output_dir=output_dir,
            state=record.state,
            existing=info,
        )
        if merged_progress != info:
            self._control_store.upsert_progress(job_id=record.job_id, progress=merged_progress)
            info = merged_progress
        progress_summary = dict(info.get("progress_summary") or {})

        return LexPipelineStatusResponse(
            meta=_build_api_meta(request_id),
            pipeline_id=pipeline_id,
            state=record.state,
            progress_summary=progress_summary,
            error_message=record.error_message,
        )

    def get_lex_graph_stats(
        self,
        output_dir_str: str,
        *,
        request_id: str | None = None,
    ) -> "LexGraphStatsResponse":
        """Inspect a Lex DuckDB graph database and return aggregate/top-k statistics."""
        import duckdb

        from polisyos.core.contracts.control import LexGraphStatsResponse

        db_path = Path(output_dir_str) / "lex_knowledge_graph.duckdb"

        if not db_path.exists():
            return LexGraphStatsResponse(
                meta=_build_api_meta(request_id),
                db_exists=False,
            )

        try:
            con = duckdb.connect(str(db_path), read_only=True)
            entity_row = con.execute("SELECT COUNT(*) FROM lex_entities").fetchone()
            fact_row = con.execute("SELECT COUNT(*) FROM lex_facts").fetchone()
            provision_row = con.execute("SELECT COUNT(*) FROM lex_provisions").fetchone()
            if entity_row is None or fact_row is None or provision_row is None:
                raise RuntimeError("lex graph count query returned no rows")
            entities = entity_row[0]
            facts = fact_row[0]
            provisions = provision_row[0]

            top_preds = [
                {"predicate": r[0], "count": r[1]}
                for r in con.execute(
                    "SELECT predicate, COUNT(*) AS cnt FROM lex_facts "
                    "GROUP BY predicate ORDER BY cnt DESC LIMIT 10"
                ).fetchall()
            ]

            top_types = [
                {"entity_type": r[0], "count": r[1]}
                for r in con.execute(
                    "SELECT entity_type, COUNT(*) AS cnt FROM lex_entities "
                    "GROUP BY entity_type ORDER BY cnt DESC LIMIT 10"
                ).fetchall()
            ]

            con.close()

            return LexGraphStatsResponse(
                meta=_build_api_meta(request_id),
                total_entities=entities,
                total_facts=facts,
                total_provisions=provisions,
                top_predicates=top_preds,
                top_entity_types=top_types,
                db_exists=True,
            )
        except (duckdb.Error, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Failed to read lex graph stats: %s", exc)
            return LexGraphStatsResponse(
                meta=_build_api_meta(request_id),
                db_exists=False,
            )

    def search_lex_graph(
        self,
        request: "LexSearchRequest",
        *,
        request_id: str | None = None,
    ) -> "LexSearchResponse":
        """Run a Lex text search against the generated knowledge graph and return ranked facts."""
        from polisyos.core.contracts.control import (
            LexSearchResponse,
            LexSearchResultItem,
        )

        db_path = Path(request.output_dir) / "lex_knowledge_graph.duckdb"

        if not db_path.exists():
            return LexSearchResponse(
                meta=_build_api_meta(request_id),
                query=request.query,
                results=[],
                total=0,
            )

        try:
            from polisyos.lex.knowledge.store import LegalKnowledgeStore

            store = LegalKnowledgeStore(
                db_path=db_path,
                index_dir=Path(request.output_dir),
            )
            try:
                raw_results = store.text_search_facts(
                    request.query,
                    top_k=request.top_k,
                )
            finally:
                store.close()

            items = [
                LexSearchResultItem(
                    fact_id=r.fact_id,
                    subject_name=r.subject_name,
                    predicate=r.predicate,
                    object_name=r.object_name,
                    fact_text=r.fact_text,
                    confidence=r.confidence,
                    norm_type=r.norm_type,
                    action_canon=r.action_canon,
                    norm_type_canon=r.norm_type_canon,
                    condition_text_uk=r.condition_text_uk,
                    exception_text_uk=r.exception_text_uk,
                    procedure_text_uk=r.procedure_text_uk,
                    thresholds_json=r.thresholds_json,
                    source_quote_uk=r.source_quote_uk,
                    doc_name=r.doc_name,
                    doc_reestr_code=r.doc_reestr_code,
                    provision_citation=r.provision_citation,
                )
                for r in raw_results
            ]

            return LexSearchResponse(
                meta=_build_api_meta(request_id),
                query=request.query,
                results=items,
                total=len(items),
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Lex graph search failed: %s", exc)
            return LexSearchResponse(
                meta=_build_api_meta(request_id),
                query=request.query,
                results=[],
                total=0,
            )


__all__ = ["ControlPlaneService"]
