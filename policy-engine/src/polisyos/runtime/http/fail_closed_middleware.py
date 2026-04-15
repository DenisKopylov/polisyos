"""Fail-closed perimeter guard for deployments without the full security chain."""
from __future__ import annotations

from typing import Any, Callable

from polisyos.runtime.http.errors import problem_response

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


class FailClosedAccessScopeMiddleware(BaseHTTPMiddleware):
    """Reject non-public requests unless an authenticated access scope is present."""

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
