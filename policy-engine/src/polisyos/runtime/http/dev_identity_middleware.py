"""Explicit development-only fixture identity middleware."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from polisyos.core.security import (
    AccessScope,
    reset_current_access_scope,
    set_current_access_scope,
)
from polisyos.runtime.http.security import build_fixture_identity_claims

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.middleware.base import BaseHTTPMiddleware as _BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response
else:  # pragma: no cover - optional runtime dependency
    try:
        from starlette.middleware.base import BaseHTTPMiddleware as _BaseHTTPMiddleware
        from starlette.requests import Request
        from starlette.responses import Response
    except ModuleNotFoundError:  # pragma: no cover
        _BaseHTTPMiddleware = cast("type[Any]", object)
        Request = cast("Any", None)
        Response = cast("Any", None)


_PUBLIC_PATHS = frozenset({"/health", "/ready", "/metrics", "/auth/callback"})


class DevelopmentFixtureIdentityMiddleware(_BaseHTTPMiddleware):
    """Project a fixed identity only when explicitly enabled for dev/test workflows."""

    def __init__(
        self,
        app: Any,
        *,
        public_paths: frozenset[str] = _PUBLIC_PATHS,
    ) -> None:
        super().__init__(app)
        self._public_paths = public_paths

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
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
