"""Public routes runs module API."""
from __future__ import annotations

import asyncio
import hashlib
import json
from collections import Counter
from datetime import datetime
from time import monotonic
from typing import Any, Callable

from polisyos.core.contracts.runtime import (
    AgentPipelineResponse,
    RunDetailsResponse,
    RunEvidenceContextResponse,
    RunLineageResponse,
    RunNodesResponse,
    RunsListResponse,
    RunTimelineResponse,
    RunWorkflowResponse,
)
from polisyos.runtime.http.dependencies import (
    RuntimeApiContext,
    build_meta,
    enforce_run_tenant_access,
    get_access_scope,
    get_runtime_api_context,
    set_authz_resource,
)
from polisyos.runtime.http.errors import bad_request

try:  # pragma: no cover - optional runtime dependency
    from fastapi import APIRouter, Depends, Query, Request
    from fastapi.responses import StreamingResponse
except ModuleNotFoundError:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment]
    Depends = None  # type: ignore[assignment]
    Query = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]
    StreamingResponse = None  # type: ignore[assignment]


router = APIRouter(prefix="/api/v1/runs", tags=["runtime-runs"]) if APIRouter else None

_LIVE_STREAM_INTERVAL_SECONDS = 1.0
_LIVE_STREAM_KEEPALIVE_SECONDS = 15.0


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


def _payload_signature(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, default=_json_default, sort_keys=True)
    return hashlib.sha1(encoded.encode("utf-8")).hexdigest()


def _is_terminal_status(status: str | None) -> bool:
    normalized = (status or "").strip().lower()
    return bool(normalized) and not (
        "running" in normalized
        or "pending" in normalized
        or "plan" in normalized
        or "execut" in normalized
        or "evaluat" in normalized
    )


def _build_runs_live_payload(request: Request, ctx: RuntimeApiContext) -> dict[str, Any]:
    scope = get_access_scope(request)
    runs, page = ctx.run_index.list_runs(
        limit=50,
        cursor=None,
        status=None,
        from_ts=None,
        to_ts=None,
        tenant_id=scope.tenant_id if scope else None,
    )
    status_counts = Counter((run.status or "unknown") for run in runs)
    return {
        "cursor": datetime.utcnow().isoformat(),
        "generated_at": datetime.utcnow().isoformat(),
        "page": {
            "count": page.count,
            "total": page.total,
            "next_cursor": page.next_cursor,
        },
        "status_counts": dict(sorted(status_counts.items())),
        "runs": [
            {
                "run_id": run.run_id,
                "status": run.status,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "duration_ms": run.duration_ms,
                "root_artifact_count": run.root_artifact_count,
                "decision_validity_status": (
                    run.decision_validity_status.value
                    if run.decision_validity_status is not None
                    else None
                ),
                "decision_review_required": run.decision_review_required,
            }
            for run in runs
        ],
    }


def _build_run_live_payload(run_id: str, ctx: RuntimeApiContext) -> dict[str, Any]:
    run = ctx.run_index.get_run(run_id)
    timeline = ctx.timeline.build_for_run(run).timeline
    agents = ctx.debug.get_run_agents(run)
    governance = ctx.debug.get_governance_debug(run)
    step_count = sum(len(attempt.steps or []) for attempt in agents.attempts or [])
    return {
        "run_id": run_id,
        "cursor": datetime.utcnow().isoformat(),
        "status": run.details.status,
        "started_at": run.details.started_at,
        "finished_at": run.details.finished_at,
        "duration_ms": run.details.duration_ms,
        "timeline_events": timeline.summary.total_events,
        "timeline_duration_ms": timeline.summary.duration_ms,
        "agent_attempts": len(agents.attempts or []),
        "agent_steps": step_count,
        "governance_issues": len(governance.issues or []),
        "transport_status": (
            governance.transport_summary.get("status")
            if isinstance(governance.transport_summary, dict)
            else None
        ),
        "decision_validity_status": (
            run.details.decision_validity_status.value
            if run.details.decision_validity_status is not None
            else None
        ),
        "decision_review_required": run.details.decision_review_required,
        "decision_superseded_by_ref": (
            run.details.decision_superseded_by_ref.model_dump(mode="json")
            if run.details.decision_superseded_by_ref is not None
            else None
        ),
        "terminal": _is_terminal_status(run.details.status),
        "generated_at": datetime.utcnow().isoformat(),
    }


async def _stream_payloads(
    builder: Callable[[], dict[str, Any]],
    request: Request,
) -> Any:
    previous_signature = None
    last_emit_at = monotonic()
    while True:
        if await request.is_disconnected():
            break
        payload = builder()
        signature = _payload_signature(payload)
        should_emit = signature != previous_signature
        if should_emit:
            previous_signature = signature
            last_emit_at = monotonic()
            event_id = str(payload.get("cursor") or payload.get("generated_at") or "")
            yield _encode_sse(payload, event="snapshot", event_id=event_id or None)
            if payload.get("terminal") is True:
                break
        elif monotonic() - last_emit_at >= _LIVE_STREAM_KEEPALIVE_SECONDS:
            last_emit_at = monotonic()
            yield ": keep-alive\n\n"
        await asyncio.sleep(_LIVE_STREAM_INTERVAL_SECONDS)


if router is not None:

    @router.get("", response_model=RunsListResponse, operation_id="list_runs")
    def list_runs(
        request: Request,
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str | None = Query(default=None),
        status: str | None = Query(default=None),
        from_ts: datetime | None = Query(default=None),  # noqa: B008
        to_ts: datetime | None = Query(default=None),  # noqa: B008
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> RunsListResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="runtime.run_list",
        )
        scope = get_access_scope(request)
        runs, page = ctx.run_index.list_runs(
            limit=limit,
            cursor=cursor,
            status=status,
            from_ts=from_ts,
            to_ts=to_ts,
            tenant_id=scope.tenant_id if scope else None,
        )
        source_kinds = [run.source_kind for run in runs]
        return RunsListResponse(
            meta=build_meta(request, source_kinds=source_kinds),
            page=page,
            runs=runs,
        )

    @router.get("/live", include_in_schema=False)
    async def stream_runs_live(
        request: Request,
        cursor: str | None = Query(default=None),  # noqa: B008
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> StreamingResponse:
        set_authz_resource(
            request,
            tenant_id=getattr(request.state, "tenant_id", None),
            kind="runtime.run_list",
        )
        return StreamingResponse(
            _stream_payloads(lambda: _build_runs_live_payload(request, ctx), request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.get("/{run_id}", response_model=RunDetailsResponse, operation_id="get_run_details")
    def get_run_details(
        run_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> RunDetailsResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run",
            artifact_id=(
                str(run.details.manifest_ref.artifact_id)
                if run.details.manifest_ref
                else None
            ),
        )
        return RunDetailsResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            run=run.details,
        )

    @router.get("/{run_id}/live", include_in_schema=False)
    async def stream_run_live(
        run_id: str,
        request: Request,
        cursor: str | None = Query(default=None),  # noqa: B008
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> StreamingResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run",
            artifact_id=(
                str(run.details.manifest_ref.artifact_id)
                if run.details.manifest_ref
                else None
            ),
        )
        return StreamingResponse(
            _stream_payloads(lambda: _build_run_live_payload(run_id, ctx), request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
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
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> RunTimelineResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_timeline",
        )
        timeline = ctx.timeline.build_for_run(run).timeline
        return RunTimelineResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            timeline=timeline,
        )

    @router.get("/{run_id}/nodes", response_model=RunNodesResponse, operation_id="get_run_nodes")
    def get_run_nodes(
        run_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> RunNodesResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_nodes",
        )
        nodes = ctx.debug.list_run_nodes(run)
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
        root_artifact_id: list[str] | None = Query(default=None),  # noqa: B008
        max_depth: int | None = Query(default=None, ge=1, le=256),
        max_nodes: int | None = Query(default=None, ge=1, le=20000),
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> RunLineageResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_lineage",
        )

        root_ids = ctx.run_index.resolve_root_artifact_ids(
            run,
            requested_root_ids=root_artifact_id or None,
        )
        if not root_ids:
            raise bad_request(
                "No root artifacts available for lineage resolution",
                code="lineage_roots_missing",
            )

        lineage = ctx.lineage.build_for_artifact_ids(
            root_ids,
            max_depth=max_depth,
            max_nodes=max_nodes,
        )
        return RunLineageResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            run_id=run_id,
            lineage=lineage,
        )

    @router.get(
        "/{run_id}/agents",
        response_model=AgentPipelineResponse,
        operation_id="get_run_agents",
    )
    def get_run_agents(
        run_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> AgentPipelineResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_agents",
        )
        pipeline = ctx.debug.get_run_agents(run)
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
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> RunEvidenceContextResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_evidence_context",
        )
        evidence_context = ctx.debug.get_run_evidence_context(run)
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
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> RunWorkflowResponse:
        run = ctx.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        set_authz_resource(
            request,
            tenant_id=run.details.tenant_id,
            kind="runtime.run_workflow",
        )
        workflow = ctx.debug.get_run_workflow(run)
        return RunWorkflowResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            workflow=workflow,
        )
