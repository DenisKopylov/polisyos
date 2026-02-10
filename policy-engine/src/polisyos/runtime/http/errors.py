from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polisyos.core.contracts.runtime import RuntimeApiError

try:  # pragma: no cover - optional runtime dependency
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
except ModuleNotFoundError:  # pragma: no cover
    FastAPI = Any  # type: ignore[assignment]
    Request = Any  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]


@dataclass(frozen=True)
class RuntimeHTTPError(Exception):
    status_code: int
    error: str
    detail: str
    code: str

    def to_model(self, request_id: str | None = None) -> RuntimeApiError:
        return RuntimeApiError(
            error=self.error,
            detail=self.detail,
            code=self.code,
            request_id=request_id,
            status_code=self.status_code,
        )


def bad_request(detail: str, *, code: str = "bad_request") -> RuntimeHTTPError:
    return RuntimeHTTPError(status_code=400, error="bad_request", detail=detail, code=code)


def forbidden(detail: str, *, code: str = "forbidden") -> RuntimeHTTPError:
    return RuntimeHTTPError(status_code=403, error="forbidden", detail=detail, code=code)


def not_found(detail: str, *, code: str = "not_found") -> RuntimeHTTPError:
    return RuntimeHTTPError(status_code=404, error="not_found", detail=detail, code=code)


def internal_error(detail: str, *, code: str = "internal_error") -> RuntimeHTTPError:
    return RuntimeHTTPError(status_code=500, error="internal_error", detail=detail, code=code)


def install_exception_handlers(app: FastAPI) -> None:
    if JSONResponse is None:
        return

    @app.exception_handler(RuntimeHTTPError)
    async def _handle_runtime_http_error(request: Request, exc: RuntimeHTTPError):  # type: ignore[no-untyped-def]
        request_id = getattr(getattr(request, "state", object()), "request_id", None)
        payload = exc.to_model(request_id=request_id)
        return JSONResponse(
            status_code=exc.status_code,
            content=payload.model_dump(mode="json"),
        )

    @app.exception_handler(KeyError)
    async def _handle_key_error(request: Request, exc: KeyError):  # type: ignore[no-untyped-def]
        request_id = getattr(getattr(request, "state", object()), "request_id", None)
        payload = RuntimeApiError(
            error="not_found",
            detail=str(exc.args[0]) if exc.args else "resource not found",
            code="not_found",
            request_id=request_id,
            status_code=404,
        )
        return JSONResponse(status_code=404, content=payload.model_dump(mode="json"))

    @app.exception_handler(ValueError)
    async def _handle_value_error(request: Request, exc: ValueError):  # type: ignore[no-untyped-def]
        request_id = getattr(getattr(request, "state", object()), "request_id", None)
        payload = RuntimeApiError(
            error="bad_request",
            detail=str(exc),
            code="bad_request",
            request_id=request_id,
            status_code=400,
        )
        return JSONResponse(status_code=400, content=payload.model_dump(mode="json"))

