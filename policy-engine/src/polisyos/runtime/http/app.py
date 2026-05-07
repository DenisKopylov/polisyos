"""Assembles the FastAPI runtime surface, middleware chain, and OpenAPI contract."""

from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from polisyos.runtime.http.authz_middleware import AuthzMiddleware
from polisyos.runtime.http.cell_router_middleware import CellRouterMiddleware
from polisyos.runtime.http.container import (
    RuntimeContainerConfig,
    RuntimeContainerOverrides,
    RuntimeServiceContainer,
    resolve_runtime_metrics,
    resolve_runtime_tracer,
)
from polisyos.runtime.http.csrf import CSRFMiddleware
from polisyos.runtime.http.dev_identity_middleware import DevelopmentFixtureIdentityMiddleware
from polisyos.runtime.http.errors import install_exception_handlers
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
from polisyos.runtime.http.fail_closed_middleware import FailClosedAccessScopeMiddleware
from polisyos.runtime.http.jwt_auth_middleware import JWTAuthMiddleware
from polisyos.runtime.http.mutation_policy import MutationProtectionMiddleware
from polisyos.runtime.http.openapi_contract import install_runtime_openapi_contract
from polisyos.runtime.http.response_policies import set_versioning_headers
from polisyos.runtime.http.routes.analysis import router as analysis_router
from polisyos.runtime.http.routes.artifacts import router as artifacts_router
from polisyos.runtime.http.routes.auth import router as auth_router
from polisyos.runtime.http.routes.control import router as control_router
from polisyos.runtime.http.routes.debug import router as debug_router
from polisyos.runtime.http.routes.fabric import router as fabric_router
from polisyos.runtime.http.routes.health import router as health_router
from polisyos.runtime.http.routes.lineage import router as lineage_router
from polisyos.runtime.http.routes.mobility import router as mobility_router
from polisyos.runtime.http.routes.review import router as review_router
from polisyos.runtime.http.routes.runs import router as runs_router
from polisyos.runtime.http.routes.scenarios import router as scenarios_router
from polisyos.runtime.http.routes.temporal import router as temporal_router
from polisyos.runtime.http.security import RuntimeSecurityConfig, is_fixture_identity_enabled

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

FastAPI: Any | None
Request: Any
GZipMiddleware: Any | None
try:  # pragma: no cover - optional runtime dependency
    from fastapi import FastAPI as _FastAPI
    from fastapi import Request as _Request
    from starlette.middleware.gzip import GZipMiddleware as _GZipMiddleware
except ModuleNotFoundError:  # pragma: no cover
    FastAPI = None
    Request = Any
    GZipMiddleware = None
else:  # pragma: no cover - import aliasing for type-checkers
    FastAPI = _FastAPI
    Request = _Request
    GZipMiddleware = _GZipMiddleware


def create_runtime_api_app(
    *,
    cas_root: Path | str = Path(".polisyos/cas"),
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
    allow_fixture_identity: bool | None = None,
    metrics_factory: Callable[[], Any] | None = None,
    tracer_factory: Callable[[], Any] | None = None,
    container_overrides: RuntimeContainerOverrides | None = None,
    enable_csrf_protection: bool | None = None,
) -> Any:
    """Create runtime api app."""
    if FastAPI is None:
        raise RuntimeError("Runtime HTTP API requires fastapi/starlette dependencies")

    normalized_cas_root = Path(cas_root)
    normalized_core_runs_root = (
        Path(core_runs_root)
        if core_runs_root is not None
        else _default_core_runs_root(normalized_cas_root)
    )
    policy_resolver = RuntimeExecutionPolicyResolver.from_env()
    security_chain_available = (
        identity_provider is not None and cell_registry is not None and opa_client is not None
    )
    deployment_policy = policy_resolver.validate_bootstrap(
        authz_shadow_mode=authz_shadow_mode,
        security_chain_available=security_chain_available,
    )
    security_middlewares_enabled = (
        enable_security_middlewares or deployment_policy.security_required
    )
    fixture_identity_enabled = is_fixture_identity_enabled(explicit=allow_fixture_identity)
    runtime_container = RuntimeServiceContainer.build(
        config=RuntimeContainerConfig(
            cas_root=normalized_cas_root,
            core_runs_root=normalized_core_runs_root,
            max_preview_bytes=max_preview_bytes,
            lineage_max_depth=lineage_max_depth,
            lineage_max_nodes=lineage_max_nodes,
            allow_unscoped_artifacts=allow_unscoped_artifacts,
            artifact_redaction_hooks=artifact_redaction_hooks,
            metrics_factory=metrics_factory,
            tracer_factory=tracer_factory,
            overrides=container_overrides or RuntimeContainerOverrides(),
        ),
        deployment_policy=deployment_policy,
        runtime_security=RuntimeSecurityConfig(
            identity_provider=identity_provider,
            cell_registry=cell_registry,
            opa_client=opa_client,
            authz_enforce=authz_enforce,
            authz_shadow_mode=authz_shadow_mode,
            allow_fixture_identity=fixture_identity_enabled,
        ),
    )
    runtime_metrics = runtime_container.runtime_metrics
    _ensure_runtime_observability_initialized(runtime_metrics)

    @asynccontextmanager
    async def _runtime_lifespan(app: Any) -> AsyncIterator[None]:
        _assert_runtime_security_middleware_order(
            app,
            security_middlewares_enabled=security_middlewares_enabled,
        )
        await runtime_container.startup(app)
        try:
            yield
        finally:
            await runtime_container.shutdown(app)

    app = FastAPI(
        title="PolicyOS Runtime API",
        version="1.0.0",
        description=(
            "Runtime API v1: run explorer, debug, and artifact inspector surfaces for PolicyOS."
        ),
        lifespan=_runtime_lifespan,
    )
    runtime_container.install(app)
    install_exception_handlers(app)

    _install_request_telemetry_middleware(
        app,
        default_metrics=runtime_container.runtime_metrics,
        default_tracer=runtime_container.runtime_tracer,
    )
    if enable_response_compression and GZipMiddleware is not None:
        app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        MutationProtectionMiddleware,
        rate_limiter=runtime_container.runtime_rate_limiter,
        idempotency_store=runtime_container.runtime_idempotency_store,
        audit_trail=runtime_container.runtime_mutation_audit,
    )
    if _is_csrf_protection_enabled(enable_csrf_protection):
        app.add_middleware(
            CSRFMiddleware,
            session_cookie_name=os.getenv("POLISYOS_SESSION_COOKIE_NAME", "polisyos_session"),
            csrf_cookie_name=os.getenv("POLISYOS_CSRF_COOKIE_NAME", "polisyos_csrf"),
            csrf_header_name=os.getenv("POLISYOS_CSRF_HEADER_NAME", "X-CSRF-Token"),
        )

    if not security_middlewares_enabled:
        app.add_middleware(FailClosedAccessScopeMiddleware)
        if fixture_identity_enabled:
            app.add_middleware(DevelopmentFixtureIdentityMiddleware)

    if security_middlewares_enabled:
        if identity_provider is None or cell_registry is None or opa_client is None:
            raise ValueError(
                "identity_provider, cell_registry, and opa_client are required "
                "when runtime security middlewares are enabled"
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
            metrics=runtime_container.runtime_metrics,
        )
        app.add_middleware(
            JWTAuthMiddleware,
            identity_provider=identity_provider,
            metrics=runtime_container.runtime_metrics,
        )

    if health_router is not None:
        app.include_router(health_router)
    if auth_router is not None:
        app.include_router(auth_router)
    if runs_router is not None:
        app.include_router(runs_router)
    if scenarios_router is not None:
        app.include_router(scenarios_router)
    if temporal_router is not None:
        app.include_router(temporal_router)
    if fabric_router is not None:
        app.include_router(fabric_router)
    if debug_router is not None:
        app.include_router(debug_router)
    if artifacts_router is not None:
        app.include_router(artifacts_router)
    if analysis_router is not None:
        app.include_router(analysis_router)
    if lineage_router is not None:
        app.include_router(lineage_router)
    if mobility_router is not None:
        app.include_router(mobility_router)
    if control_router is not None:
        app.include_router(control_router)
    if review_router is not None:
        app.include_router(review_router)

    install_runtime_openapi_contract(app)
    return app


def _default_core_runs_root(cas_root: Path) -> Path:
    if cas_root.name == "cas" and cas_root.parent.name == ".polisyos":
        return cas_root.parent / "runs"
    return cas_root / "runs"


def _assert_runtime_security_middleware_order(
    app: Any,
    *,
    security_middlewares_enabled: bool,
) -> None:
    if not security_middlewares_enabled:
        return

    names = [middleware.cls.__name__ for middleware in getattr(app, "user_middleware", ())]
    expected = ["JWTAuthMiddleware", "CellRouterMiddleware", "AuthzMiddleware"]
    try:
        start = names.index(expected[0])
    except ValueError as exc:  # pragma: no cover - defensive boot guard
        raise RuntimeError(
            "JWTAuthMiddleware is required when runtime security is enabled"
        ) from exc

    actual = names[start : start + len(expected)]
    if actual != expected:
        raise RuntimeError(
            "Runtime security middleware order must remain "
            "JWTAuthMiddleware -> CellRouterMiddleware -> AuthzMiddleware"
        )


def _is_csrf_protection_enabled(explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    raw = os.getenv("POLISYOS_CSRF_ENABLED")
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    cookie_auth = os.getenv("POLISYOS_COOKIE_AUTH_ENABLED")
    return str(cookie_auth or "").strip().lower() in {"1", "true", "yes", "on"}


def _install_request_telemetry_middleware(
    app: Any,
    *,
    default_metrics: Any | None,
    default_tracer: Any | None,
) -> None:
    async def _runtime_api_request_telemetry(request: Any, call_next: Any) -> Any:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        metrics = resolve_runtime_metrics(request) or default_metrics
        tracer = resolve_runtime_tracer(request) or default_tracer
        if metrics is None or tracer is None:  # pragma: no cover - defensive bootstrap guard
            raise RuntimeError("Runtime observability providers were not initialized")
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
            except (
                AttributeError,
                KeyError,
                OSError,
                RuntimeError,
                TimeoutError,
                TypeError,
                ValueError,
            ):
                status_code = 500
                _record_runtime_api_metric(
                    metrics=metrics,
                    route=_resolve_runtime_route_label(request),
                    method=request.method,
                    status_code=status_code,
                    duration_seconds=time.perf_counter() - started,
                )
                raise

        duration_seconds = time.perf_counter() - started
        _record_runtime_api_metric(
            metrics=metrics,
            route=_resolve_runtime_route_label(request),
            method=request.method,
            status_code=status_code,
            duration_seconds=duration_seconds,
        )
        if str(getattr(request.url, "path", "")).startswith("/api/v1/"):
            set_versioning_headers(response)
        response.headers["X-Request-ID"] = request_id
        return response

    app.middleware("http")(_runtime_api_request_telemetry)


def _ensure_runtime_observability_initialized(metrics: Any) -> None:
    ensure_initialized = getattr(metrics, "ensure_initialized", None)
    if callable(ensure_initialized):
        ensure_initialized()


def _resolve_runtime_route_label(request: Any) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str) and route_path:
        return route_path
    return "unmatched"


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
    """Return the runtime API OpenAPI document from the supplied or freshly built app."""
    runtime_app = app or create_runtime_api_app()
    return cast("dict[str, Any]", runtime_app.openapi())


__all__ = ["create_runtime_api_app", "export_runtime_openapi_schema"]
