"""Fail-closed perimeter guard for deployments without the full security chain."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from polisyos.runtime.http.errors import problem_response

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


class FailClosedAccessScopeMiddleware(_BaseHTTPMiddleware):
    """Reject non-public requests unless an authenticated access scope is present."""

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
        scope = getattr(request.state, "access_scope", None)
        if scope is None:
            request_id = getattr(getattr(request, "state", object()), "request_id", None)
            return problem_response(
                status_code=401,
                code="missing_access_scope",
                detail="Authenticated access scope is required for this endpoint",
                request_id=request_id,
                instance=path,
                error="missing_access_scope",
            )
        return await call_next(request)


__all__ = ["FailClosedAccessScopeMiddleware"]
