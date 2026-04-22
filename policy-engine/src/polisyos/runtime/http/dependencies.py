"""Provide FastAPI dependencies and tenant guards for the Runtime API boundary."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.artifacts.backends.config import (
    ArtifactStoreConfig,
    build_artifact_store,
    build_async_artifact_store,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.contracts.runtime import ApiMeta, SourceKind
from polisyos.core.security.access_scope import AccessScope

from .errors import forbidden, unauthorized
from .resilience import guard_runtime_cas
from .services.artifact_inspector import ArtifactInspectorService
from .services.debug import DebugService
from .services.feedback import FeedbackService
from .services.lineage import LineageService
from .services.mobility import MobilityService
from .services.run_index import IndexedRunRecord, RunIndexService
from .services.timeline import TimelineService

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi import Request

    from polisyos.core.artifacts.protocol import ArtifactStore, AsyncArtifactStore
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer
else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi import Request
    except ModuleNotFoundError:  # pragma: no cover
        Request = Any


@dataclass(frozen=True)
class RuntimeApiContext:
    """Bundle stateful services and policy knobs shared by runtime route handlers."""
    cas_root: Path
    core_runs_root: Path
    store: ArtifactStore
    async_store: AsyncArtifactStore
    run_index: RunIndexService
    timeline: TimelineService
    debug: DebugService
    feedback: FeedbackService
    lineage: LineageService
    artifacts: ArtifactInspectorService
    mobility: MobilityService
    max_preview_bytes: int
    lineage_max_depth: int
    lineage_max_nodes: int
    allow_unscoped_artifacts: bool = False


def build_runtime_api_context(
    *,
    cas_root: Path,
    core_runs_root: Path,
    max_preview_bytes: int = 64 * 1024,
    lineage_max_depth: int = 64,
    lineage_max_nodes: int = 2000,
    allow_unscoped_artifacts: bool = False,
    artifact_redaction_hooks: dict[str, Any] | None = None,
    metrics: MetricsRegistry | None = None,
    tracer: PolicyOSTracer | None = None,
) -> RuntimeApiContext:
    """Create the service graph used by read-only runtime routes and artifact inspection."""
    store_config = ArtifactStoreConfig.from_env().model_copy(update={"root": str(cas_root)})
    store = cast(
        "ArtifactStore",
        guard_runtime_cas(build_artifact_store(store_config, metrics=metrics, tracer=tracer)),
    )
    async_store = build_async_artifact_store(
        store_config,
        metrics=metrics,
        tracer=tracer,
        sync_store=store,
    )
    timeline = TimelineService(metrics=metrics)
    lineage = LineageService(
        store=store,
        default_max_depth=lineage_max_depth,
        default_max_nodes=lineage_max_nodes,
    )
    run_index = RunIndexService(
        store=store,
        core_runs_root=core_runs_root,
        metrics=metrics,
    )
    debug = DebugService(store=store, timeline_service=timeline)
    feedback = FeedbackService(store=store, run_index=run_index)
    artifacts = ArtifactInspectorService(
        store=store,
        lineage_service=lineage,
        default_max_preview_bytes=max_preview_bytes,
        redaction_hooks=artifact_redaction_hooks,
    )
    mobility = MobilityService(store=store)
    return RuntimeApiContext(
        cas_root=cas_root,
        core_runs_root=core_runs_root,
        store=store,
        async_store=async_store,
        run_index=run_index,
        timeline=timeline,
        debug=debug,
        feedback=feedback,
        lineage=lineage,
        artifacts=artifacts,
        mobility=mobility,
        max_preview_bytes=max_preview_bytes,
        lineage_max_depth=lineage_max_depth,
        lineage_max_nodes=lineage_max_nodes,
        allow_unscoped_artifacts=allow_unscoped_artifacts,
    )


def get_runtime_api_context(request: Request) -> RuntimeApiContext:  # pragma: no cover
    """Return the application-scoped runtime context created during API bootstrap."""
    from .container import resolve_runtime_api_context

    context = resolve_runtime_api_context(request)
    if context is None:
        raise RuntimeError("RuntimeApiContext was not initialized during application startup")
    return context


def ensure_request_id(request: Request) -> str:  # pragma: no cover
    """Resolve `X-Request-ID` or generate a correlation ID and cache it on `request.state`."""
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id
    header_id = request.headers.get("X-Request-ID")
    if isinstance(header_id, str) and header_id:
        request.state.request_id = header_id
        return header_id
    generated = uuid.uuid4().hex
    request.state.request_id = generated
    return generated


def build_meta(
    request: Request,
    *,
    source_kinds: list[SourceKind] | None = None,
) -> ApiMeta:  # pragma: no cover
    """Build the common response envelope metadata for one request."""
    request_id = ensure_request_id(request)
    dedup = sorted(set(source_kinds or []))
    return ApiMeta(request_id=request_id, source_kinds=dedup)


def set_authz_resource(
    request: Request,
    *,
    tenant_id: str | None,
    kind: str,
    artifact_id: str | None = None,
) -> None:  # pragma: no cover
    """Attach resource metadata consumed by authz middleware and audit logging."""
    request.state.authz_resource = {
        "tenant_id": tenant_id or "",
        "kind": kind,
        "artifact_id": artifact_id or "",
    }


def record_data_access_audit(
    request: Request,
    *,
    resource_id: str | None = None,
    tenant_id: str | None = None,
    outcome: str = "success",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append a read-path audit entry and emit matching telemetry if configured."""
    from .container import resolve_runtime_access_audit, resolve_runtime_metrics

    authz_resource = getattr(request.state, "authz_resource", None)
    resource_kind = (
        str(authz_resource.get("kind", "runtime.unknown"))
        if isinstance(authz_resource, dict)
        else "runtime.unknown"
    )
    resolved_resource_id = resource_id
    if not resolved_resource_id and isinstance(authz_resource, dict):
        candidate = authz_resource.get("artifact_id")
        if isinstance(candidate, str) and candidate:
            resolved_resource_id = candidate

    scope = get_access_scope(request)
    resolved_tenant = tenant_id or (
        scope.tenant_id if scope is not None else getattr(request.state, "tenant_id", None)
    )
    claims = getattr(request.state, "user_claims", None)
    actor = (
        getattr(claims, "sub", None)
        or getattr(request.state, "authenticated_tenant_id", None)
        or "anonymous"
    )
    entry = {
        "timestamp": time.time(),
        "request_id": ensure_request_id(request),
        "tenant_id": resolved_tenant or "",
        "actor": actor,
        "method": request.method.upper(),
        "endpoint": str(getattr(request.url, "path", "")),
        "operation": f"READ {resource_kind}",
        "resource_kind": resource_kind,
        "resource_id": resolved_resource_id or "",
        "outcome": outcome,
        "metadata": metadata or {},
    }
    audit_trail = resolve_runtime_access_audit(request)
    append = getattr(audit_trail, "append", None)
    if callable(append):
        append(entry)

    metrics = resolve_runtime_metrics(request)
    record_access_metric = getattr(metrics, "record_runtime_data_access", None)
    if callable(record_access_metric):
        record_access_metric(
            resource_kind=resource_kind,
            endpoint=entry["endpoint"],
            outcome=outcome,
            tenant_scoped=bool(resolved_tenant),
        )
    record_audit_metric = getattr(metrics, "record_audit_entry", None)
    if callable(record_audit_metric):
        record_audit_metric(chain_id="runtime.data_access", event_type="read")


def get_access_scope(request: Request) -> AccessScope | None:  # pragma: no cover
    """Return the resolved request scope from JWT/SPIFFE middleware, if present."""
    scope = getattr(request.state, "access_scope", None)
    return scope if isinstance(scope, AccessScope) else None


def require_access_scope(request: Request) -> AccessScope:  # pragma: no cover
    """Return the resolved request scope or fail closed."""
    scope = get_access_scope(request)
    if scope is None:
        raise unauthorized(
            "Authenticated access scope is required for this endpoint",
            code="missing_access_scope",
        )
    return scope


def enforce_run_tenant_access(
    request: Request,
    *,
    ctx: RuntimeApiContext,
    run: IndexedRunRecord,
) -> None:  # pragma: no cover
    """Deny cross-tenant run access and fail closed when tenant metadata is missing."""
    scope = require_access_scope(request)

    # Core runs include tenant metadata and must match access scope.
    if run.details.tenant_id:
        if scope.tenant_id != run.details.tenant_id:
            raise forbidden(
                "Run belongs to a different tenant",
                code="run_tenant_mismatch",
            )
        return

    raise forbidden(
        "Tenant metadata is missing for run; access denied by policy",
        code="run_tenant_unscoped",
    )


def enforce_artifact_tenant_access(
    request: Request,
    *,
    ctx: RuntimeApiContext,
    artifact_id: ArtifactID,
) -> str | None:  # pragma: no cover
    """Deny cross-tenant artifact access unless unscoped CAS objects are explicitly allowed."""
    scope = require_access_scope(request)
    tenant_id = ctx.run_index.get_artifact_tenant(str(artifact_id))
    if tenant_id is None:
        if ctx.allow_unscoped_artifacts:
            return None
        raise forbidden(
            "Artifact is not linked to a tenant-scoped run",
            code="artifact_tenant_unscoped",
        )
    if scope.tenant_id != tenant_id:
        raise forbidden(
            "Artifact belongs to a different tenant",
            code="artifact_tenant_mismatch",
        )
    return cast("str | None", tenant_id)


def parse_artifact_ids(values: list[str]) -> list[ArtifactID]:
    """Parse URL/query artifact references into validated `ArtifactID` objects."""
    return [ArtifactID.model_validate(value) for value in values]
