from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polisyos.core.contracts.runtime import RuntimeApiProblem

try:  # pragma: no cover - optional runtime dependency
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
except ModuleNotFoundError:  # pragma: no cover
    FastAPI = Any  # type: ignore[assignment]
    HTTPException = Any  # type: ignore[assignment]
    Request = Any  # type: ignore[assignment]
    RequestValidationError = Any  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]


_DEFAULT_TYPE_BY_STATUS: dict[int, str] = {
    400: "https://polisyos.dev/problems/bad-request",
    401: "https://polisyos.dev/problems/unauthorized",
    403: "https://polisyos.dev/problems/forbidden",
    404: "https://polisyos.dev/problems/not-found",
    422: "https://polisyos.dev/problems/validation-error",
    500: "https://polisyos.dev/problems/internal-error",
}


def _title_for_code(code: str, *, fallback: str) -> str:
    tokenized = code.replace(".", " ").replace("_", " ").strip()
    if not tokenized:
        return fallback
    return tokenized[:1].upper() + tokenized[1:]


def build_problem(
    *,
    status_code: int,
    code: str,
    detail: str,
    request_id: str | None,
    instance: str | None = None,
    title: str | None = None,
    type_uri: str | None = None,
    error: str | None = None,
) -> RuntimeApiProblem:
    resolved_title = title or _title_for_code(code, fallback="Runtime API error")
    resolved_type = type_uri or _DEFAULT_TYPE_BY_STATUS.get(status_code, "about:blank")
    resolved_error = error or code
    return RuntimeApiProblem(
        type=resolved_type,
        title=resolved_title,
        status=status_code,
        detail=detail,
        code=code,
        instance=instance,
        request_id=request_id,
        error=resolved_error,
        status_code=status_code,
    )


def problem_response(
    *,
    status_code: int,
    code: str,
    detail: str,
    request_id: str | None,
    instance: str | None = None,
    title: str | None = None,
    type_uri: str | None = None,
    error: str | None = None,
    extensions: dict[str, Any] | None = None,
) -> Any:
    if JSONResponse is None:
        raise RuntimeError("problem_response requires fastapi/starlette dependencies")
    payload = build_problem(
        status_code=status_code,
        code=code,
        detail=detail,
        request_id=request_id,
        instance=instance,
        title=title,
        type_uri=type_uri,
        error=error,
    )
    content = payload.model_dump(mode="json")
    if extensions:
        content.update(extensions)
    return JSONResponse(
        status_code=status_code,
        content=content,
        media_type="application/problem+json",
    )


@dataclass(frozen=True)
class RuntimeHTTPError(Exception):
    status_code: int
    error: str
    detail: str
    code: str

    def to_model(
        self,
        *,
        request_id: str | None = None,
        instance: str | None = None,
    ) -> RuntimeApiProblem:
        return build_problem(
            status_code=self.status_code,
            code=self.code,
            detail=self.detail,
            request_id=request_id,
            instance=instance,
            error=self.error,
        )


def bad_request(detail: str, *, code: str = "bad_request") -> RuntimeHTTPError:
    return RuntimeHTTPError(status_code=400, error="bad_request", detail=detail, code=code)


def forbidden(detail: str, *, code: str = "forbidden") -> RuntimeHTTPError:
    return RuntimeHTTPError(status_code=403, error="forbidden", detail=detail, code=code)


def unprocessable_entity(
    detail: str,
    *,
    code: str = "unprocessable_entity",
) -> RuntimeHTTPError:
    return RuntimeHTTPError(
        status_code=422,
        error="request_validation_failed",
        detail=detail,
        code=code,
    )


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
        payload = exc.to_model(request_id=request_id, instance=str(request.url.path))
        return JSONResponse(
            status_code=exc.status_code,
            content=payload.model_dump(mode="json"),
            media_type="application/problem+json",
        )

    @app.exception_handler(KeyError)
    async def _handle_key_error(request: Request, exc: KeyError):  # type: ignore[no-untyped-def]
        request_id = getattr(getattr(request, "state", object()), "request_id", None)
        payload = build_problem(
            status_code=404,
            code="not_found",
            detail=str(exc.args[0]) if exc.args else "resource not found",
            request_id=request_id,
            instance=str(request.url.path),
            error="not_found",
        )
        return JSONResponse(
            status_code=404,
            content=payload.model_dump(mode="json"),
            media_type="application/problem+json",
        )

    @app.exception_handler(ValueError)
    async def _handle_value_error(request: Request, exc: ValueError):  # type: ignore[no-untyped-def]
        request_id = getattr(getattr(request, "state", object()), "request_id", None)
        payload = build_problem(
            status_code=400,
            code="bad_request",
            detail=str(exc),
            request_id=request_id,
            instance=str(request.url.path),
            error="bad_request",
        )
        return JSONResponse(
            status_code=400,
            content=payload.model_dump(mode="json"),
            media_type="application/problem+json",
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, exc: RequestValidationError):  # type: ignore[no-untyped-def]
        request_id = getattr(getattr(request, "state", object()), "request_id", None)
        return problem_response(
            status_code=422,
            code="request_validation_failed",
            detail=str(exc),
            request_id=request_id,
            instance=str(request.url.path),
            error="request_validation_failed",
            title="Request validation failed",
        )

    @app.exception_handler(HTTPException)
    async def _handle_http_exception(request: Request, exc: HTTPException):  # type: ignore[no-untyped-def]
        request_id = getattr(getattr(request, "state", object()), "request_id", None)
        status_code = int(getattr(exc, "status_code", 500))
        detail = str(getattr(exc, "detail", "Runtime API request failed"))
        code = (
            "unauthorized"
            if status_code == 401
            else "forbidden"
            if status_code == 403
            else "not_found"
            if status_code == 404
            else "http_error"
        )
        return problem_response(
            status_code=status_code,
            code=code,
            detail=detail,
            request_id=request_id,
            instance=str(request.url.path),
            error=code,
        )
