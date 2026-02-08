"""JWT authentication middleware for PolicyOS runtime HTTP services."""
from __future__ import annotations

import contextvars
import logging
import os
from typing import Any, Callable

from polisyos.core.observability import get_metrics
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.exceptions import MFARequiredError, TokenValidationError
from polisyos.core.security.identity import SPIFFEIdentityProvider, UserIdentityClaims
from polisyos.core.security.tenant_context import (
    reset_current_access_scope,
    set_current_access_scope,
)

logger = logging.getLogger("polisyos.security.jwt")


try:  # pragma: no cover - optional runtime dependency
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
except ModuleNotFoundError:  # pragma: no cover
    BaseHTTPMiddleware = object  # type: ignore[assignment]
    Request = Any  # type: ignore[assignment]
    Response = Any  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]


_current_user: contextvars.ContextVar[UserIdentityClaims | None] = contextvars.ContextVar(
    "current_user",
    default=None,
)

_PUBLIC_PATHS = frozenset({"/health", "/ready", "/metrics", "/auth/callback"})


def get_current_user() -> UserIdentityClaims | None:
    return _current_user.get()


class JWTAuthMiddleware(BaseHTTPMiddleware):  # type: ignore[misc]
    """Validate Bearer JWT and project claims into request/context."""

    def __init__(
        self,
        app: Any,
        *,
        identity_provider: SPIFFEIdentityProvider,
        tenant_header: str = "X-Tenant-ID",
        public_paths: frozenset[str] = _PUBLIC_PATHS,
        expected_cell_id: str | None = None,
    ) -> None:
        if JSONResponse is None:
            raise RuntimeError("JWTAuthMiddleware requires starlette/fastapi dependencies")
        super().__init__(app)
        self._identity_provider = identity_provider
        self._tenant_header = tenant_header
        self._public_paths = public_paths
        configured_cell_id = os.getenv("POLISYOS_CELL_ID", "").strip()
        self._expected_cell_id = expected_cell_id or configured_cell_id or None

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        path = str(getattr(request.url, "path", ""))
        if path in self._public_paths:
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"error": "missing_bearer_token"})

        token = auth_header[7:].strip()
        if not token:
            return JSONResponse(status_code=401, content={"error": "missing_bearer_token"})

        try:
            claims = self._identity_provider.extract_user_claims(
                token,
                expected_cell_id=self._expected_cell_id,
            )
        except MFARequiredError as exc:
            get_metrics().record_identity_failure(reason="mfa_required", provider="keycloak")
            logger.warning("JWT rejected due to missing MFA: %s", exc)
            return JSONResponse(
                status_code=403,
                content={"error": "mfa_required", "detail": str(exc)},
            )
        except TokenValidationError as exc:
            get_metrics().record_identity_failure(reason="invalid_token", provider="keycloak")
            logger.warning("JWT authentication failed: %s", exc)
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_token", "detail": str(exc)},
            )
        except Exception as exc:
            get_metrics().record_identity_failure(reason="identity_error", provider="keycloak")
            logger.exception("Unexpected JWT authentication error")
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_token", "detail": str(exc)},
            )

        header_tenant = request.headers.get(self._tenant_header)
        if header_tenant and header_tenant != claims.tenant_id:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "tenant_binding_mismatch",
                    "detail": (
                        f"Header {self._tenant_header}={header_tenant!r} "
                        "does not match token tenant"
                    ),
                },
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
