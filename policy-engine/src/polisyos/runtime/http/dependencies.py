"""Provide FastAPI dependencies and tenant guards for the Runtime API boundary."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.runtime import ApiMeta, SourceKind
from polisyos.core.security.access_scope import AccessScope

from .errors import forbidden
from .services.artifact_inspector import ArtifactInspectorService
from .services.debug import DebugService
from .services.feedback import FeedbackService
from .services.lineage import LineageService
from .services.run_index import IndexedRunRecord, RunIndexService
from .services.timeline import TimelineService

try:  # pragma: no cover - optional runtime dependency
    from fastapi import Request
except ModuleNotFoundError:  # pragma: no cover
    Request = Any  # type: ignore[assignment]


@dataclass(frozen=True)
class RuntimeApiContext:
    """Bundle stateful services and policy knobs shared by runtime route handlers."""
    cas_root: Path
    core_runs_root: Path
    store: FileSystemCAS
    run_index: RunIndexService
    timeline: TimelineService
    debug: DebugService
    feedback: FeedbackService
    lineage: LineageService
    artifacts: ArtifactInspectorService
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
) -> RuntimeApiContext:
    """Create the service graph used by read-only runtime routes and artifact inspection."""
    store = FileSystemCAS(cas_root)
    timeline = TimelineService()
    lineage = LineageService(
        store=store,
        default_max_depth=lineage_max_depth,
        default_max_nodes=lineage_max_nodes,
    )
    run_index = RunIndexService(
        store=store,
        core_runs_root=core_runs_root,
    )
    debug = DebugService(store=store, timeline_service=timeline)
    feedback = FeedbackService(store=store, run_index=run_index)
    artifacts = ArtifactInspectorService(
        store=store,
        lineage_service=lineage,
        default_max_preview_bytes=max_preview_bytes,
        redaction_hooks=artifact_redaction_hooks,
    )
    return RuntimeApiContext(
        cas_root=cas_root,
        core_runs_root=core_runs_root,
        store=store,
        run_index=run_index,
        timeline=timeline,
        debug=debug,
        feedback=feedback,
        lineage=lineage,
        artifacts=artifacts,
        max_preview_bytes=max_preview_bytes,
        lineage_max_depth=lineage_max_depth,
        lineage_max_nodes=lineage_max_nodes,
        allow_unscoped_artifacts=allow_unscoped_artifacts,
    )


def get_runtime_api_context(request: Request) -> RuntimeApiContext:  # pragma: no cover
    """Return the application-scoped runtime context created during API bootstrap."""
    return request.app.state.runtime_api_ctx


def ensure_request_id(request: Request) -> str:  # pragma: no cover
    """Resolve `X-Request-ID` or generate a correlation ID and cache it on `request.state`."""
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id
    header_id = request.headers.get("X-Request-ID")
    if header_id:
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


def get_access_scope(request: Request) -> AccessScope | None:  # pragma: no cover
    """Return the resolved request scope from JWT/SPIFFE middleware, if present."""
    scope = getattr(request.state, "access_scope", None)
    return scope if isinstance(scope, AccessScope) else None


def enforce_run_tenant_access(
    request: Request,
    *,
    ctx: RuntimeApiContext,
    run: IndexedRunRecord,
) -> None:  # pragma: no cover
    """Deny cross-tenant run access and fail closed when tenant metadata is missing."""
    scope = get_access_scope(request)
    if scope is None:
        return

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
    scope = get_access_scope(request)
    tenant_id = ctx.run_index.get_artifact_tenant(str(artifact_id))
    if scope is None:
        return tenant_id
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
    return tenant_id


def parse_artifact_ids(values: list[str]) -> list[ArtifactID]:
    """Parse URL/query artifact references into validated `ArtifactID` objects."""
    return [ArtifactID.model_validate(value) for value in values]
