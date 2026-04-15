"""Explicit development-only fixture identity middleware."""
from __future__ import annotations

from typing import Any, Callable

from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.tenant_context import (
    reset_current_access_scope,
    set_current_access_scope,
)
from polisyos.runtime.http.security import build_fixture_identity_claims

try:  # pragma: no cover - optional runtime dependency
    BaseHTTPMiddleware: Any
    Request: Any
    Response: Any
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response
except ModuleNotFoundError:  # pragma: no cover
    BaseHTTPMiddleware = object
    Request = Any
    Response = Any


_PUBLIC_PATHS = frozenset({"/health", "/ready", "/metrics", "/auth/callback"})


class DevelopmentFixtureIdentityMiddleware(BaseHTTPMiddleware):
    """Project a fixed identity only when explicitly enabled for dev/test workflows."""

    def __init__(
        self,
        app: Any,
        *,
        public_paths: frozenset[str] = _PUBLIC_PATHS,
    ) -> None:
        super().__init__(app)
        self._public_paths = public_paths

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        path = str(getattr(request.url, "path", ""))
        if path in self._public_paths:
            return await call_next(request)

        claims = build_fixture_identity_claims()
        request.state.user_claims = claims
        request.state.authenticated_tenant_id = claims.tenant_id
        request.state.access_scope = AccessScope.from_user_claims(claims)

        scope_token = set_current_access_scope(request.state.access_scope)
        try:
            return await call_next(request)
        finally:
            reset_current_access_scope(scope_token)


__all__ = ["DevelopmentFixtureIdentityMiddleware"]
