"""Public routes runs module API."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.contracts.runtime import (
    AgentPipelineResponse,
    ArtifactLineageView,
    CompareCandidatesResponse,
    CompareRunResponse,
    RunDetailsResponse,
    RunEvidenceContextResponse,
    RunLineageResponse,
    RunNodesResponse,
    RunQuantitiesResponse,
    RunsBatchRequest,
    RunsBatchResponse,
    RunsListResponse,
    RunTimelineResponse,
    RunWorkflowResponse,
    SourceKind,
    TemporalScope,
    TemporalSurfaceSupport,
)
from polisyos.fabric.decision_data import (
    FabricDecisionDataResponse,
)
from polisyos.fabric.decision_data import (
    TemporalRef as FabricTemporalRef,
)
from polisyos.runtime.http.dependencies import (
    RuntimeApiContext,
    build_meta,
    enforce_run_tenant_access,
    get_runtime_api_context,
    record_data_access_audit,
    require_access_scope,
    set_authz_resource,
)
from polisyos.runtime.http.errors import bad_request
from polisyos.runtime.http.response_policies import add_run_link_relations

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


def _payload_signature(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, default=_json_default, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _as_source_kind(value: str) -> SourceKind:
    return cast("SourceKind", value)


def _is_terminal_status(status: str | None) -> bool:
    normalized = (status or "").strip().lower()
    return bool(normalized) and not (
        "running" in normalized
        or "pending" in normalized
        or "plan" in normalized
        or "execut" in normalized
        or "evaluat" in normalized
    )


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


def _build_runs_live_payload(request: Request, ctx: RuntimeApiContext) -> dict[str, Any]:
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
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    return {
        "cursor": now,
        "generated_at": now,
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
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    return {
        "run_id": run_id,
        "cursor": now,
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
        "generated_at": now,
    }


async def _stream_payloads(
    builder: Callable[[], dict[str, Any]],
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
            now = datetime.now(UTC).replace(microsecond=0).isoformat()
            yield _encode_sse(
                {
                    "cursor": now,
                    "generated_at": now,
                    "reason": "stream_timeout_budget_exhausted",
                },
                event="stream.timeout",
            )
            break
        payload = builder()
        signature = _payload_signature(payload)
        should_emit = signature != previous_signature
        if should_emit:
            previous_signature = signature
            last_emit_at = monotonic()
            sleep_seconds = policy.min_interval_seconds
            event_id = str(payload.get("cursor") or payload.get("generated_at") or "")
            yield _encode_sse(payload, event="snapshot", event_id=event_id or None)
            if payload.get("terminal") is True:
                break
        elif monotonic() - last_emit_at >= policy.keepalive_seconds:
            last_emit_at = monotonic()
            yield ": keep-alive\n\n"
            sleep_seconds = policy.min_interval_seconds
        else:
            sleep_seconds = min(policy.max_interval_seconds, sleep_seconds * 2)
        await asyncio.sleep(sleep_seconds)


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
        return RunDetailsResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            temporal_scope=temporal_scope,
            run=ctx.temporal.project_run_details(run.details, temporal_scope),
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

        lineage = (
            ctx.lineage.build_for_artifact_ids(
                root_ids,
                max_depth=max_depth,
                max_nodes=max_nodes,
            )
            if root_ids
            else ArtifactLineageView(root_artifact_ids=[])
        )
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
        quantities, coverage, entries = ctx.lineage.build_quantity_inventory_for_run(run)
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
        quantities, runtime_coverage, entries = ctx.lineage.build_quantity_inventory_for_run(run)
        quantities, runtime_coverage, _entries = ctx.temporal.project_quantities(
            quantities,
            entries,
            temporal_scope,
        )
        decision_data, coverage = ctx.lineage.build_fabric_decision_data_for_quantities(
            quantities,
            runtime_coverage,
            temporal_scope=temporal_scope,
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
        evidence_context = ctx.debug.get_run_evidence_context(run)
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
