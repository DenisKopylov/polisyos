"""JWT authentication middleware for PolicyOS runtime HTTP services."""

from __future__ import annotations

import contextvars
import os
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.exceptions import MFARequiredError, TokenValidationError
from polisyos.core.security.tenant_context import (
    reset_current_access_scope,
    set_current_access_scope,
)
from polisyos.runtime.http.access_audit import (
    RuntimeAuthorizationOutcome,
    emit_runtime_authorization_audit,
)
from polisyos.runtime.http.errors import problem_response
from polisyos.runtime.http.security import (
    clear_request_auth_context,
    is_fixture_identity_claims,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request as _Request
    from starlette.responses import JSONResponse as _JSONResponse
    from starlette.responses import Response as _Response
    from starlette.types import ASGIApp as _ASGIApp

    from polisyos.core.observability import MetricsRegistry
    from polisyos.core.security.identity import SPIFFEIdentityProvider, UserIdentityClaims

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

logger = get_logger("polisyos.security.jwt")


_current_user: contextvars.ContextVar[UserIdentityClaims | None] = contextvars.ContextVar(
    "current_user",
    default=None,
)

_PUBLIC_PATHS = frozenset({"/health", "/ready", "/metrics", "/auth/callback"})
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _audit_identity_denial(request: _Request, *, reason: str) -> None:
    if request.method.upper() not in _UNSAFE_METHODS:
        return
    emit_runtime_authorization_audit(
        request,
        outcome=RuntimeAuthorizationOutcome.DENY,
        denial_reason=reason,
        raise_on_failure=False,
    )


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


def get_current_user() -> UserIdentityClaims | None:
    """Return current user."""
    return _current_user.get()


class JWTAuthMiddleware(_BaseHTTPMiddleware):
    """Validate Bearer JWT and project claims into request/context."""

    def __init__(
        self,
        app: _ASGIApp,
        *,
        identity_provider: SPIFFEIdentityProvider,
        tenant_header: str = "X-Tenant-ID",
        public_paths: frozenset[str] = _PUBLIC_PATHS,
        expected_cell_id: str | None = None,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        if _JSONResponse is None:
            raise RuntimeError("JWTAuthMiddleware requires starlette/fastapi dependencies")
        super().__init__(app)
        self._identity_provider = identity_provider
        self._tenant_header = tenant_header
        self._public_paths = public_paths
        self._metrics = metrics if metrics is not None else _default_metrics()
        configured_cell_id = os.getenv("POLISYOS_CELL_ID", "").strip()
        self._expected_cell_id = expected_cell_id or configured_cell_id or None

    async def dispatch(
        self,
        request: _Request,
        call_next: Callable[[_Request], Awaitable[_Response]],
    ) -> _Response:
        path = str(getattr(request.url, "path", ""))
        if path in self._public_paths:
            return await call_next(request)
        request_id = getattr(getattr(request, "state", object()), "request_id", None)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            _audit_identity_denial(request, reason="missing_bearer_token")
            clear_request_auth_context(request.state)
            return problem_response(
                status_code=401,
                code="missing_bearer_token",
                detail="Authorization header must contain a Bearer token",
                request_id=request_id,
                instance=path,
                error="missing_bearer_token",
            )

        token = auth_header[7:].strip()
        if not token:
            _audit_identity_denial(request, reason="missing_bearer_token")
            clear_request_auth_context(request.state)
            return problem_response(
                status_code=401,
                code="missing_bearer_token",
                detail="Authorization header must contain a non-empty Bearer token",
                request_id=request_id,
                instance=path,
                error="missing_bearer_token",
            )

        try:
            claims = self._identity_provider.extract_user_claims(
                token,
                expected_cell_id=self._expected_cell_id,
            )
        except MFARequiredError as exc:
            self._metrics.record_identity_failure(reason="mfa_required", provider="keycloak")
            logger.warning("JWT rejected due to missing MFA: %s", exc)
            _audit_identity_denial(request, reason="mfa_required")
            clear_request_auth_context(request.state)
            return problem_response(
                status_code=403,
                code="mfa_required",
                detail=str(exc),
                request_id=request_id,
                instance=path,
                error="mfa_required",
            )
        except TokenValidationError as exc:
            self._metrics.record_identity_failure(reason="invalid_token", provider="keycloak")
            logger.warning("JWT authentication failed: %s", exc)
            _audit_identity_denial(request, reason="invalid_token")
            clear_request_auth_context(request.state)
            return problem_response(
                status_code=401,
                code="invalid_token",
                detail=str(exc),
                request_id=request_id,
                instance=path,
                error="invalid_token",
            )
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as exc:
            self._metrics.record_identity_failure(reason="identity_error", provider="keycloak")
            logger.exception("Unexpected JWT authentication error")
            _audit_identity_denial(request, reason="invalid_token")
            clear_request_auth_context(request.state)
            return problem_response(
                status_code=401,
                code="invalid_token",
                detail=str(exc),
                request_id=request_id,
                instance=path,
                error="invalid_token",
            )

        if is_fixture_identity_claims(claims):
            self._metrics.record_identity_failure(
                reason="fixture_identity_forbidden",
                provider="keycloak",
            )
            _audit_identity_denial(request, reason="fixture_identity_forbidden")
            clear_request_auth_context(request.state)
            return problem_response(
                status_code=401,
                code="fixture_identity_forbidden",
                detail="Identity providers may not return development fixture claims",
                request_id=request_id,
                instance=path,
                error="fixture_identity_forbidden",
            )

        header_tenant = request.headers.get(self._tenant_header)
        if header_tenant and header_tenant != claims.tenant_id:
            _audit_identity_denial(request, reason="tenant_binding_mismatch")
            clear_request_auth_context(request.state)
            return problem_response(
                status_code=403,
                code="tenant_binding_mismatch",
                detail=(
                    f"Header {self._tenant_header}={header_tenant!r} does not match token tenant"
                ),
                request_id=request_id,
                instance=path,
                error="tenant_binding_mismatch",
            )

        request.state.user_claims = claims
        request.state.authenticated_tenant_id = claims.tenant_id
        request.state.access_scope = AccessScope.from_user_claims(claims)

        user_token = _current_user.set(claims)
        scope_token = set_current_access_scope(request.state.access_scope)
        try:
            return await call_next(request)
        finally:
            _current_user.reset(user_token)
            reset_current_access_scope(scope_token)


__all__ = ["JWTAuthMiddleware", "get_current_user"]
