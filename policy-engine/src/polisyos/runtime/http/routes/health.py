from __future__ import annotations

from datetime import datetime, timezone

try:  # pragma: no cover - optional runtime dependency
    from fastapi import APIRouter
except ModuleNotFoundError:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment]


router = APIRouter(tags=["runtime-health"]) if APIRouter else None


if router is not None:

    @router.get("/health", operation_id="health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/ready", operation_id="ready")
    def ready() -> dict[str, str]:
        return {"status": "ready"}

    @router.get("/api/v1/health", operation_id="runtime_api_health")
    def api_health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "runtime_api_v1",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
