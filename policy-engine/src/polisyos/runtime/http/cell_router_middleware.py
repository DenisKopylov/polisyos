"""HTTP middleware for tenant-to-cell routing."""
from __future__ import annotations

import time
from typing import Any, Callable

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics
from polisyos.core.security.exceptions import CrossTenantAccessError, TenantIsolationError
from polisyos.core.security.registry import CellRegistry
from polisyos.core.security.router import (
    TENANT_HEADER,
    MissingTenantHeaderError,
    TenantRoutingError,
    resolve_routing,
)
from polisyos.core.security.tenant_context import (
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)
from polisyos.runtime.http.errors import problem_response

logger = get_logger("polisyos.security")


try:  # pragma: no cover - optional runtime dependency
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
except ModuleNotFoundError:  # pragma: no cover
    BaseHTTPMiddleware = object  # type: ignore[assignment]
    Request = Any  # type: ignore[assignment]
    Response = Any  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]


class CellRouterMiddleware(BaseHTTPMiddleware):  # type: ignore[misc]
    """Route requests into tenant contexts and emit routing telemetry."""

    def __init__(
        self,
        app: Any,
        *,
        registry: CellRegistry,
        tenant_header: str = TENANT_HEADER,
    ) -> None:
        if JSONResponse is None:
            raise RuntimeError("CellRouterMiddleware requires starlette/fastapi dependencies")
        super().__init__(app)
        self._registry = registry
        self._tenant_header = tenant_header

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
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
            _record_failure("tenant_binding_mismatch")
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

        start = time.perf_counter()
        try:
            routing = resolve_routing(
                headers=routing_headers,
                registry=self._registry,
                tenant_header=self._tenant_header,
            )
        except MissingTenantHeaderError as exc:
            _record_failure("missing_tenant_header")
            return problem_response(
                status_code=401,
                code="missing_tenant_id",
                detail=str(exc),
                request_id=request_id,
                instance=path,
                error="missing_tenant_id",
            )
        except TenantRoutingError as exc:
            _record_failure("tenant_not_found")
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
            _record_failure("cell_binding_mismatch")
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
            _record_security_incident(routing.cell_slug, str(exc))
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
        _record_success(
            cell_id=routing.cell_slug,
            tier=routing.cell_tier,
            status_code=getattr(response, "status_code", 500),
            duration_seconds=duration_seconds,
        )

        response.headers["X-Cell-ID"] = routing.cell_slug
        response.headers["X-Cell-Tier"] = routing.cell_tier
        return response


def _record_success(*, cell_id: str, tier: str, status_code: int, duration_seconds: float) -> None:
    metrics = get_metrics()
    metrics.record_cell_router_request(
        cell_id=cell_id,
        tier=tier,
        status=str(status_code),
    )
    metrics.record_cell_router_latency(cell_id=cell_id, duration_seconds=duration_seconds)


def _record_failure(reason: str) -> None:
    metrics = get_metrics()
    metrics.record_cell_router_failure(reason=reason)


def _record_security_incident(cell_id: str, detail: str) -> None:
    logger.critical(
        "SECURITY_INCIDENT cross_tenant_access",
        extra={"cell_id": cell_id, "detail": detail},
    )
    metrics = get_metrics()
    metrics.record_security_incident(incident_type="cross_tenant_access", cell_id=cell_id)


__all__ = ["CellRouterMiddleware", "TENANT_HEADER"]
