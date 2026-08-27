"""HTTP middleware for tenant-to-cell routing."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics
from polisyos.core.security import (
    TENANT_HEADER,
    CellRegistry,
    CrossTenantAccessError,
    MissingTenantHeaderError,
    TenantIsolationError,
    TenantNotFoundError,
    TenantRoutingError,
    reset_current_access_scope,
    resolve_routing,
    set_current_access_scope,
    tenant_scope,
)
from polisyos.runtime.http.errors import problem_response
from polisyos.runtime.http.security import clear_request_auth_context

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request as _Request
    from starlette.responses import JSONResponse as _JSONResponse
    from starlette.responses import Response as _Response
    from starlette.types import ASGIApp as _ASGIApp

    from polisyos.core.observability import MetricsRegistry

    class _BaseHTTPMiddleware:
        def __init__(self, app: _ASGIApp) -> None: ...
else:
    try:  # pragma: no cover - optional runtime dependency
        from starlette.middleware.base import BaseHTTPMiddleware as _BaseHTTPMiddleware
        from starlette.requests import Request as _Request
        from starlette.responses import JSONResponse as _JSONResponse
        from starlette.responses import Response as _Response
        from starlette.types import ASGIApp as _ASGIApp
    except ModuleNotFoundError:  # pragma: no cover
        _BaseHTTPMiddleware = object
        _Request = Any
        _Response = Any
        _JSONResponse = None
        _ASGIApp = Any

logger = get_logger("polisyos.security")


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


class CellRouterMiddleware(_BaseHTTPMiddleware):
    """Route requests into tenant contexts and emit routing telemetry."""

    def __init__(
        self,
        app: _ASGIApp,
        *,
        registry: CellRegistry,
        tenant_header: str = TENANT_HEADER,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        if _JSONResponse is None:
            raise RuntimeError("CellRouterMiddleware requires starlette/fastapi dependencies")
        super().__init__(app)
        self._registry = registry
        self._tenant_header = tenant_header
        self._metrics = metrics if metrics is not None else _default_metrics()

    async def dispatch(
        self,
        request: _Request,
        call_next: Callable[[_Request], Awaitable[_Response]],
    ) -> _Response:
        path = str(getattr(request.url, "path", ""))
        if path in {"/health", "/ready", "/metrics"}:
            return await call_next(request)
        request_id = getattr(getattr(request, "state", object()), "request_id", None)

        claims = getattr(request.state, "user_claims", None)
        authenticated_tenant_id = (
            getattr(claims, "tenant_id", None)
            if claims is not None
            else getattr(request.state, "authenticated_tenant_id", None)
        )
        header_tenant_id = request.headers.get(self._tenant_header)
        if (
            authenticated_tenant_id
            and header_tenant_id
            and header_tenant_id != authenticated_tenant_id
        ):
            self._record_failure("tenant_binding_mismatch")
            clear_request_auth_context(request.state)
            return problem_response(
                status_code=403,
                code="tenant_binding_mismatch",
                detail=(
                    f"Authenticated tenant {authenticated_tenant_id!r} "
                    f"does not match header tenant {header_tenant_id!r}"
                ),
                request_id=request_id,
                instance=path,
                error="tenant_binding_mismatch",
            )

        effective_tenant_id = authenticated_tenant_id or header_tenant_id
        routing_headers = dict(request.headers)
        if effective_tenant_id:
            routing_headers[self._tenant_header] = effective_tenant_id
            routing_headers[self._tenant_header.lower()] = effective_tenant_id

        from polisyos.runtime.http.deployment_security_attestation import (
            require_attested_deployment_component,
        )

        registry = cast(
            "CellRegistry",
            require_attested_deployment_component(
                request,
                component_name="cell_registry",
                candidate=self._registry,
            ),
        )
        start = time.perf_counter()
        try:
            routing = resolve_routing(
                headers=routing_headers,
                registry=registry,
                tenant_header=self._tenant_header,
            )
        except MissingTenantHeaderError as exc:
            self._record_failure("missing_tenant_header")
            clear_request_auth_context(request.state)
            return problem_response(
                status_code=401,
                code="missing_tenant_id",
                detail=str(exc),
                request_id=request_id,
                instance=path,
                error="missing_tenant_id",
            )
        except TenantRoutingError as exc:
            self._record_failure("tenant_not_found")
            clear_request_auth_context(request.state)
            return problem_response(
                status_code=403,
                code="tenant_not_found",
                detail=str(exc),
                request_id=request_id,
                instance=path,
                error="tenant_not_found",
            )

        request.state.tenant_id = routing.tenant_id
        request.state.cell_id = routing.cell_id
        request.state.cell_tier = routing.cell_tier

        token_claim_cell = getattr(claims, "cell_id", None) if claims is not None else None
        if token_claim_cell and token_claim_cell != routing.cell_id:
            self._record_failure("cell_binding_mismatch")
            clear_request_auth_context(request.state)
            return problem_response(
                status_code=403,
                code="cell_binding_mismatch",
                detail=(
                    f"Token is bound to cell {token_claim_cell!r}, "
                    f"but routed cell is {routing.cell_id!r}"
                ),
                request_id=request_id,
                instance=path,
                error="cell_binding_mismatch",
            )

        scope_token = None
        try:
            access_scope = getattr(request.state, "access_scope", None)
            if access_scope is not None:
                scope_token = set_current_access_scope(access_scope)
            with tenant_scope(None, tenant_id=routing.tenant_id, cell_id=routing.cell_id):
                response = await call_next(request)
        except CrossTenantAccessError as exc:
            self._record_security_incident(routing.cell_slug, str(exc))
            clear_request_auth_context(request.state)
            return problem_response(
                status_code=403,
                code="cross_tenant_access",
                detail=str(exc),
                request_id=request_id,
                instance=path,
                error="cross_tenant_access",
            )
        except TenantIsolationError as exc:
            logger.exception("Tenant isolation error")
            clear_request_auth_context(request.state)
            return problem_response(
                status_code=500,
                code="tenant_isolation_error",
                detail=str(exc),
                request_id=request_id,
                instance=path,
                error="tenant_isolation_error",
            )
        finally:
            if scope_token is not None:
                reset_current_access_scope(scope_token)

        duration_seconds = time.perf_counter() - start
        self._record_success(
            cell_id=routing.cell_slug,
            tier=routing.cell_tier,
            status_code=getattr(response, "status_code", 500),
            duration_seconds=duration_seconds,
        )

        response.headers["X-Cell-ID"] = routing.cell_slug
        response.headers["X-Cell-Tier"] = routing.cell_tier
        return response

    def _record_success(
        self,
        *,
        cell_id: str,
        tier: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        self._metrics.record_cell_router_request(
            cell_id=cell_id,
            tier=tier,
            status=str(status_code),
        )
        self._metrics.record_cell_router_latency(
            cell_id=cell_id,
            duration_seconds=duration_seconds,
        )

    def _record_failure(self, reason: str) -> None:
        self._metrics.record_cell_router_failure(reason=reason)

    def _record_security_incident(self, cell_id: str, detail: str) -> None:
        logger.critical(
            "SECURITY_INCIDENT cross_tenant_access",
            extra={"cell_id": cell_id, "detail": detail},
        )
        self._metrics.record_security_incident(
            incident_type="cross_tenant_access",
            cell_id=cell_id,
        )


__all__ = [
    "TENANT_HEADER",
    "CellRegistry",
    "CellRouterMiddleware",
    "TenantNotFoundError",
]
