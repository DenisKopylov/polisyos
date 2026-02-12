from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from polisyos.core.observability import get_metrics, get_tracer
from polisyos.runtime.http.authz_middleware import AuthzMiddleware
from polisyos.runtime.http.cell_router_middleware import CellRouterMiddleware
from polisyos.runtime.http.dependencies import build_runtime_api_context
from polisyos.runtime.http.errors import install_exception_handlers
from polisyos.runtime.http.jwt_auth_middleware import JWTAuthMiddleware
from polisyos.runtime.http.openapi_contract import install_runtime_openapi_contract
from polisyos.runtime.http.routes.artifacts import router as artifacts_router
from polisyos.runtime.http.routes.control import router as control_router
from polisyos.runtime.http.routes.debug import router as debug_router
from polisyos.runtime.http.routes.health import router as health_router
from polisyos.runtime.http.routes.runs import router as runs_router

try:  # pragma: no cover - optional runtime dependency
    from fastapi import FastAPI, Request
    from starlette.middleware.gzip import GZipMiddleware
except ModuleNotFoundError:  # pragma: no cover
    FastAPI = None  # type: ignore[assignment]
    Request = Any  # type: ignore[assignment]
    GZipMiddleware = None  # type: ignore[assignment]


def create_runtime_api_app(
    *,
    cas_root: Path | str = Path(".polisyos"),
    core_runs_root: Path | str | None = None,
    max_preview_bytes: int = 64 * 1024,
    lineage_max_depth: int = 64,
    lineage_max_nodes: int = 2000,
    allow_unscoped_artifacts: bool = False,
    artifact_redaction_hooks: dict[str, Any] | None = None,
    enable_response_compression: bool = True,
    enable_security_middlewares: bool = False,
    identity_provider: Any | None = None,
    cell_registry: Any | None = None,
    opa_client: Any | None = None,
    authz_enforce: bool = True,
    authz_shadow_mode: bool = False,
    delegation_manager: Any | None = None,
    trusted_delegators: frozenset[str] = frozenset(),
    service_spiffe_id: str | None = None,
) -> Any:
    if FastAPI is None:
        raise RuntimeError("Runtime HTTP API requires fastapi/starlette dependencies")

    normalized_cas_root = Path(cas_root)
    normalized_core_runs_root = (
        Path(core_runs_root) if core_runs_root is not None else (normalized_cas_root / "runs")
    )
    runtime_ctx = build_runtime_api_context(
        cas_root=normalized_cas_root,
        core_runs_root=normalized_core_runs_root,
        max_preview_bytes=max_preview_bytes,
        lineage_max_depth=lineage_max_depth,
        lineage_max_nodes=lineage_max_nodes,
        allow_unscoped_artifacts=allow_unscoped_artifacts,
        artifact_redaction_hooks=artifact_redaction_hooks,
    )

    app = FastAPI(
        title="PolicyOS Runtime API",
        version="1.0.0",
        description=(
            "Runtime API v1: run explorer, debug, and artifact inspector "
            "surfaces for PolicyOS."
        ),
    )
    app.state.runtime_api_ctx = runtime_ctx
    install_exception_handlers(app)

    _install_request_telemetry_middleware(app)
    if enable_response_compression and GZipMiddleware is not None:
        app.add_middleware(GZipMiddleware, minimum_size=1024)

    if enable_security_middlewares:
        if identity_provider is None or cell_registry is None or opa_client is None:
            raise ValueError(
                "identity_provider, cell_registry, and opa_client are required "
                "when enable_security_middlewares=True"
            )
        # Starlette executes middleware in reverse order of registration.
        # Register authz first so JWT/cell routing run before authorization checks.
        app.add_middleware(
            AuthzMiddleware,
            opa_client=opa_client,
            enforce=authz_enforce,
            shadow_mode=authz_shadow_mode,
            delegation_manager=delegation_manager,
            trusted_delegators=trusted_delegators,
            service_spiffe_id=service_spiffe_id,
        )
        app.add_middleware(
            CellRouterMiddleware,
            registry=cell_registry,
        )
        app.add_middleware(
            JWTAuthMiddleware,
            identity_provider=identity_provider,
        )

    if health_router is not None:
        app.include_router(health_router)
    if runs_router is not None:
        app.include_router(runs_router)
    if debug_router is not None:
        app.include_router(debug_router)
    if artifacts_router is not None:
        app.include_router(artifacts_router)
    if control_router is not None:
        app.include_router(control_router)

    install_runtime_openapi_contract(app)
    return app


def _install_request_telemetry_middleware(app: Any) -> None:
    @app.middleware("http")
    async def _runtime_api_request_telemetry(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        metrics = get_metrics()
        tracer = get_tracer()
        started = time.perf_counter()
        status_code = 500
        with tracer.start_as_current_span(
            "runtime.http.request",
            attributes={
                "http.method": request.method,
                "http.route": request.url.path,
                "runtime.request_id": request_id,
            },
        ):
            try:
                response = await call_next(request)
                status_code = int(getattr(response, "status_code", 500))
            except Exception:
                status_code = 500
                _record_runtime_api_metric(
                    metrics=metrics,
                    route=request.url.path,
                    method=request.method,
                    status_code=status_code,
                    duration_seconds=time.perf_counter() - started,
                )
                raise

        duration_seconds = time.perf_counter() - started
        _record_runtime_api_metric(
            metrics=metrics,
            route=request.url.path,
            method=request.method,
            status_code=status_code,
            duration_seconds=duration_seconds,
        )
        response.headers["X-Request-ID"] = request_id
        return response


def _record_runtime_api_metric(
    *,
    metrics: Any,
    route: str,
    method: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    recorder = getattr(metrics, "record_runtime_api_request", None)
    if callable(recorder):
        recorder(
            route=route,
            method=method,
            status=str(status_code),
            duration_seconds=duration_seconds,
        )


def export_runtime_openapi_schema(*, app: Any | None = None) -> dict[str, Any]:
    runtime_app = app or create_runtime_api_app()
    return runtime_app.openapi()


__all__ = ["create_runtime_api_app", "export_runtime_openapi_schema"]
