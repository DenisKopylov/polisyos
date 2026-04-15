"""Public routes health module API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from polisyos.runtime.http.container import get_runtime_container, resolve_runtime_metrics

try:  # pragma: no cover - optional runtime dependency
    APIRouter: Any | None
    Request: Any
    from fastapi import APIRouter, Request
except ModuleNotFoundError:  # pragma: no cover
    APIRouter = None
    Request = Any


router = APIRouter(tags=["runtime-health"]) if APIRouter else None


if router is not None:

    @router.get("/health", operation_id="health")
    def health(request: Request) -> dict[str, Any]:
        payload: dict[str, Any] = {"status": "ok"}
        lifecycle = _runtime_lifecycle_payload(request)
        if lifecycle:
            payload["lifecycle"] = lifecycle
        observability = _runtime_observability_payload(request)
        if observability:
            payload["observability"] = observability
        return payload

    @router.get("/ready", operation_id="ready")
    def ready(request: Request) -> dict[str, Any]:
        payload: dict[str, Any] = {"status": "ready"}
        lifecycle = _runtime_lifecycle_payload(request)
        if lifecycle:
            payload["lifecycle"] = lifecycle
            if str(lifecycle.get("status", "")).lower() != "ready":
                payload["status"] = "degraded"
        observability = _runtime_observability_payload(request)
        if observability:
            payload["observability"] = observability
            if _has_observability_degradation(observability):
                payload["status"] = "degraded"
        return payload

    @router.get("/api/v1/health", operation_id="runtime_api_health")
    def api_health(request: Request) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": "ok",
            "service": "runtime_api_v1",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        lifecycle = _runtime_lifecycle_payload(request)
        if lifecycle:
            payload["lifecycle"] = lifecycle
        observability = _runtime_observability_payload(request)
        if observability:
            payload["observability"] = observability
        return payload


def _runtime_lifecycle_payload(request: Request) -> dict[str, Any]:
    container = get_runtime_container(request)
    if container is None:
        return {}
    return container.health_payload()


def _runtime_observability_payload(request: Request) -> dict[str, Any]:
    metrics = resolve_runtime_metrics(request)
    getter = getattr(metrics, "get_exporter_health", None)
    if callable(getter):
        health = getter()
        if isinstance(health, dict):
            return health
    return {}


def _has_observability_degradation(payload: dict[str, Any]) -> bool:
    for value in payload.values():
        if isinstance(value, dict) and str(value.get("status", "")).lower() == "degraded":
            return True
    return False
