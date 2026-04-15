"""CSRF protection for cookie-authenticated runtime deployments."""
from __future__ import annotations

import hmac
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


_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class CSRFMiddleware(BaseHTTPMiddleware):
    """Enforce a double-submit CSRF token for cookie-authenticated mutations.

    Bearer-token requests are intentionally out of scope: the protection is
    only activated for unsafe methods that carry a configured session cookie.
    """

    def __init__(
        self,
        app: Any,
        *,
        session_cookie_name: str = "polisyos_session",
        csrf_cookie_name: str = "polisyos_csrf",
        csrf_header_name: str = "X-CSRF-Token",
        protected_path_prefix: str = "/api/v1/",
    ) -> None:
        super().__init__(app)
        self._session_cookie_name = session_cookie_name
        self._csrf_cookie_name = csrf_cookie_name
        self._csrf_header_name = csrf_header_name
        self._protected_path_prefix = protected_path_prefix

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        method = str(getattr(request, "method", "GET")).upper()
        path = str(getattr(request.url, "path", ""))
        if method not in _UNSAFE_METHODS or not path.startswith(self._protected_path_prefix):
            return await call_next(request)
        if request.headers.get("authorization", "").startswith("Bearer "):
            return await call_next(request)
        if self._session_cookie_name not in request.cookies:
            return await call_next(request)

        csrf_cookie = request.cookies.get(self._csrf_cookie_name, "")
        csrf_header = request.headers.get(self._csrf_header_name, "")
        if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
            request_id = getattr(getattr(request, "state", object()), "request_id", None)
            return problem_response(
                status_code=403,
                code="csrf_token_required",
                detail=(
                    "Cookie-authenticated unsafe requests must include a "
                    "matching CSRF token header"
                ),
                request_id=request_id,
                instance=path,
                error="csrf_token_required",
            )
        return await call_next(request)


__all__ = ["CSRFMiddleware"]
