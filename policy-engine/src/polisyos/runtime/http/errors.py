"""Serialize runtime exceptions into RFC 7807-style `application/problem+json` payloads."""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from polisyos.core.contracts.runtime import RuntimeApiProblem
from polisyos.core.errors import ErrorCategory, PolicyOSError
from polisyos.core.security.exceptions import (
    AuthorizationDeniedError,
    AuthorizationError,
    CrossTenantAccessError,
    IdentityNotAvailableError,
    IdentityVerificationError,
    TenantIsolationError,
    TokenValidationError,
)
from polisyos.runtime.http.execution_policy import ExecutionProfileError, PolicyFlagForbiddenError

try:  # pragma: no cover - optional runtime dependency
    from fastapi import HTTPException as _ImportedHTTPException
    from fastapi.exceptions import RequestValidationError as _ImportedRequestValidationError
    from fastapi.responses import JSONResponse as _ImportedJSONResponse
except ModuleNotFoundError:  # pragma: no cover
    _HTTPException: Any | None = None
    _RequestValidationError: Any | None = None
    _JSONResponse: Any | None = None
else:  # pragma: no cover - import wiring only
    _HTTPException = _ImportedHTTPException
    _RequestValidationError = _ImportedRequestValidationError
    _JSONResponse = _ImportedJSONResponse


_DEFAULT_TYPE_BY_STATUS: dict[int, str] = {
    400: "https://polisyos.dev/problems/bad-request",
    401: "https://polisyos.dev/problems/unauthorized",
    403: "https://polisyos.dev/problems/forbidden",
    404: "https://polisyos.dev/problems/not-found",
    406: "https://polisyos.dev/problems/not-acceptable",
    429: "https://polisyos.dev/problems/rate-limited",
    422: "https://polisyos.dev/problems/validation-error",
    503: "https://polisyos.dev/problems/service-unavailable",
    504: "https://polisyos.dev/problems/gateway-timeout",
    500: "https://polisyos.dev/problems/internal-error",
}

_INFRA_DETAIL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"s3://[^\s'\"<>]+", re.IGNORECASE), "s3://[redacted]"),
    (
        re.compile(
            r"\b(bucket|region|endpoint|host|access[_-]?key|secret[_-]?key|"
            r"credential|credentials|token|password|signature)\s*=\s*[^\s,;]+",
            re.IGNORECASE,
        ),
        r"\1=[redacted]",
    ),
    (re.compile(r"arn:aws:[^\s'\"<>]+", re.IGNORECASE), "arn:aws:[redacted]"),
    (
        re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE),
        "[redacted-access-key]",
    ),
    (
        re.compile(r"(X-Amz-(Credential|Signature|Security-Token)=)[^&\s]+", re.IGNORECASE),
        r"\1[redacted]",
    ),
)


@dataclass(frozen=True)
class ErrorReportContext:
    """Structured, sanitized error context propagated across runtime boundaries."""

    request_id: str | None = None
    tenant: str | None = None
    run_id: str | None = None
    artifact_id: str | None = None
    dependency: str | None = None
    retry_state: str | None = None
    stage: str | None = None
    category: str | None = None

    def to_public_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "request_id": self.request_id,
                "tenant": self.tenant,
                "run_id": self.run_id,
                "artifact_id": self.artifact_id,
                "dependency": self.dependency,
                "retry_state": self.retry_state,
                "stage": self.stage,
                "category": self.category,
            }.items()
            if value
        }


def sanitize_error_detail(detail: object, *, fallback: str = "runtime request failed") -> str:
    """Return a client-safe diagnostic string without infra or credential details."""
    rendered = str(detail or fallback)
    for pattern, replacement in _INFRA_DETAIL_PATTERNS:
        rendered = pattern.sub(replacement, rendered)
    return rendered[:2000] or fallback


def _sanitize_context_value(value: object) -> str | None:
    if value is None:
        return None
    rendered = sanitize_error_detail(value, fallback="")
    return rendered[:256] if rendered else None


def _request_id_from_request(request: Any) -> str | None:
    return _sanitize_context_value(getattr(getattr(request, "state", object()), "request_id", None))


def _path_param(request: Any, name: str) -> str | None:
    params = getattr(request, "path_params", None)
    if isinstance(params, Mapping):
        return _sanitize_context_value(params.get(name))
    return None


def _query_param(request: Any, name: str) -> str | None:
    query_params = getattr(request, "query_params", None)
    getter = getattr(query_params, "get", None)
    if callable(getter):
        return _sanitize_context_value(getter(name))
    return None


def collect_error_context(request: Any, exc: BaseException | None = None) -> ErrorReportContext:
    """Collect safe request/exception metadata for RFC 7807 extension payloads."""
    state = getattr(request, "state", object())
    access_scope = getattr(state, "access_scope", None)
    tenant = (
        getattr(access_scope, "tenant_id", None)
        or getattr(state, "tenant_id", None)
        or getattr(exc, "tenant_id", None)
        or getattr(exc, "requesting_tenant", None)
    )
    details = getattr(exc, "details", None)
    detail_map = details if isinstance(details, Mapping) else {}
    retry_value = (
        getattr(exc, "retry_state", None)
        or detail_map.get("retry_state")
        or detail_map.get("retry_attempt")
    )
    category = getattr(getattr(exc, "category", None), "value", None) or getattr(
        exc,
        "category",
        None,
    )
    return ErrorReportContext(
        request_id=_request_id_from_request(request),
        tenant=_sanitize_context_value(tenant),
        run_id=(
            _path_param(request, "run_id")
            or _query_param(request, "run_id")
            or _sanitize_context_value(getattr(exc, "run_id", None) or detail_map.get("run_id"))
        ),
        artifact_id=(
            _path_param(request, "artifact_id")
            or _query_param(request, "artifact_id")
            or _sanitize_context_value(
                getattr(exc, "artifact_id", None) or detail_map.get("artifact_id")
            )
        ),
        dependency=_sanitize_context_value(
            getattr(exc, "dependency", None) or detail_map.get("dependency")
        ),
        retry_state=_sanitize_context_value(retry_value),
        stage=_sanitize_context_value(getattr(exc, "stage", None) or detail_map.get("stage")),
        category=_sanitize_context_value(category),
    )


def _context_extension(context: ErrorReportContext) -> dict[str, Any]:
    payload = context.to_public_dict()
    return {"context": payload} if payload else {}


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
    """Build the canonical runtime error model used by FastAPI exception handlers."""
    resolved_title = title or _title_for_code(code, fallback="Runtime API error")
    resolved_type = type_uri or _DEFAULT_TYPE_BY_STATUS.get(status_code, "about:blank")
    resolved_error = error or code
    return RuntimeApiProblem(
        type=resolved_type,
        title=resolved_title,
        status=status_code,
        detail=sanitize_error_detail(detail),
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
    """Render a `RuntimeApiProblem` as `application/problem+json`.

    Raises:
        RuntimeError: If FastAPI/Starlette dependencies are unavailable.
    """
    json_response = _JSONResponse
    if json_response is None:
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
    return json_response(
        status_code=status_code,
        content=content,
        media_type="application/problem+json",
    )


@dataclass(frozen=True)
class RuntimeHTTPError(Exception):
    """Carry a typed HTTP error that is converted to `RuntimeApiProblem`."""
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
    """Create a 400 error for malformed or semantically invalid requests."""
    return RuntimeHTTPError(status_code=400, error="bad_request", detail=detail, code=code)


def forbidden(detail: str, *, code: str = "forbidden") -> RuntimeHTTPError:
    """Create a 403 error for tenant, capability, or authz policy violations."""
    return RuntimeHTTPError(status_code=403, error="forbidden", detail=detail, code=code)


def unauthorized(detail: str, *, code: str = "unauthorized") -> RuntimeHTTPError:
    """Create a 401 error for missing or invalid authentication context."""
    return RuntimeHTTPError(status_code=401, error="unauthorized", detail=detail, code=code)


def rate_limited(detail: str, *, code: str = "rate_limited") -> RuntimeHTTPError:
    """Create a 429 error for runtime write/read throttling."""
    return RuntimeHTTPError(status_code=429, error="rate_limited", detail=detail, code=code)


def unprocessable_entity(
    detail: str,
    *,
    code: str = "unprocessable_entity",
) -> RuntimeHTTPError:
    """Unprocessable entity helper."""
    return RuntimeHTTPError(
        status_code=422,
        error="request_validation_failed",
        detail=detail,
        code=code,
    )


def not_found(detail: str, *, code: str = "not_found") -> RuntimeHTTPError:
    """Create a 404 error for missing runs, artifacts, jobs, or pipelines."""
    return RuntimeHTTPError(status_code=404, error="not_found", detail=detail, code=code)


def not_acceptable(detail: str, *, code: str = "not_acceptable") -> RuntimeHTTPError:
    """Create a 406 error when the client requests an unsupported representation."""
    return RuntimeHTTPError(
        status_code=406,
        error="not_acceptable",
        detail=detail,
        code=code,
    )


def internal_error(detail: str, *, code: str = "internal_error") -> RuntimeHTTPError:
    """Create a 500 error for unexpected runtime failures."""
    return RuntimeHTTPError(status_code=500, error="internal_error", detail=detail, code=code)


def service_unavailable(
    detail: str,
    *,
    code: str = "service_unavailable",
) -> RuntimeHTTPError:
    """Create a 503 error for unavailable runtime dependencies."""
    return RuntimeHTTPError(
        status_code=503,
        error="service_unavailable",
        detail=detail,
        code=code,
    )


def gateway_timeout(detail: str, *, code: str = "gateway_timeout") -> RuntimeHTTPError:
    """Create a 504 error for timed-out runtime dependencies."""
    return RuntimeHTTPError(
        status_code=504,
        error="gateway_timeout",
        detail=detail,
        code=code,
    )


class RuntimeDependencyError(Exception):
    """Represent an unavailable or timed-out runtime dependency."""

    def __init__(
        self,
        *,
        dependency: str,
        status_code: int,
        code: str,
        detail: str,
        retry_state: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.dependency = dependency
        self.status_code = status_code
        self.code = code
        self.detail = sanitize_error_detail(detail)
        self.retry_state = retry_state


class RuntimeDependencyUnavailableError(RuntimeDependencyError):
    """Represent a dependency failure that should surface as `503`."""

    def __init__(
        self,
        dependency: str,
        *,
        detail: str | None = None,
        code: str | None = None,
    ) -> None:
        normalized = dependency.strip().lower().replace(" ", "_")
        super().__init__(
            dependency=dependency,
            status_code=503,
            code=code or f"{normalized}_unavailable",
            detail=detail or f"{dependency} is temporarily unavailable",
            retry_state="retryable",
        )


class RuntimeDependencyTimeoutError(RuntimeDependencyError):
    """Represent a dependency timeout that should surface as `504`."""

    def __init__(
        self,
        dependency: str,
        *,
        detail: str | None = None,
        code: str | None = None,
    ) -> None:
        normalized = dependency.strip().lower().replace(" ", "_")
        super().__init__(
            dependency=dependency,
            status_code=504,
            code=code or f"{normalized}_timeout",
            detail=detail or f"{dependency} timed out",
            retry_state="retryable",
        )


@dataclass(frozen=True)
class _MappedException:
    status_code: int
    code: str
    error: str
    detail: str
    title: str | None = None


def _policyos_status_code(exc: PolicyOSError) -> int:
    if exc.category == ErrorCategory.TRANSIENT:
        return 503
    if exc.category == ErrorCategory.VALIDATION:
        return 400
    return 500


def _map_core_exception(exc: BaseException) -> _MappedException:
    if isinstance(exc, CrossTenantAccessError):
        return _MappedException(
            status_code=403,
            code="cross_tenant_access_denied",
            error="forbidden",
            detail="Cross-tenant access is not allowed",
            title="Cross tenant access denied",
        )
    if isinstance(exc, AuthorizationDeniedError):
        return _MappedException(
            status_code=403,
            code=getattr(exc, "code", None) or "authorization_denied",
            error="forbidden",
            detail=str(exc),
            title="Authorization denied",
        )
    if isinstance(exc, AuthorizationError):
        return _MappedException(
            status_code=403,
            code=getattr(exc, "code", None) or "authorization_error",
            error="forbidden",
            detail=str(exc),
            title="Authorization failed",
        )
    if isinstance(exc, IdentityNotAvailableError):
        return _MappedException(
            status_code=503,
            code=getattr(exc, "code", None) or "identity_unavailable",
            error="service_unavailable",
            detail=str(exc),
            title="Identity service unavailable",
        )
    if isinstance(exc, (IdentityVerificationError, TokenValidationError)):
        return _MappedException(
            status_code=401,
            code=getattr(exc, "code", None) or "identity_verification_failed",
            error="unauthorized",
            detail=str(exc),
            title="Identity verification failed",
        )
    if isinstance(exc, TenantIsolationError):
        return _MappedException(
            status_code=403,
            code=getattr(exc, "code", None) or "tenant_isolation_denied",
            error="forbidden",
            detail=str(exc),
            title="Tenant isolation denied",
        )
    if isinstance(exc, ExecutionProfileError):
        return _MappedException(
            status_code=400,
            code=getattr(exc, "code", None) or "execution_profile_error",
            error="bad_request",
            detail=str(exc),
            title="Execution profile rejected",
        )
    if isinstance(exc, PolicyFlagForbiddenError):
        return _MappedException(
            status_code=403,
            code=getattr(exc, "code", None) or "policy_flag_forbidden",
            error="forbidden",
            detail=str(exc),
            title="Policy flag forbidden",
        )
    if isinstance(exc, PolicyOSError):
        status_code = _policyos_status_code(exc)
        return _MappedException(
            status_code=status_code,
            code=exc.code or f"policyos_{exc.category.value}",
            error=(
                "service_unavailable"
                if status_code == 503
                else "bad_request"
                if status_code == 400
                else "internal_error"
            ),
            detail=str(exc),
            title="PolicyOS core error",
        )
    return _MappedException(
        status_code=500,
        code="internal_error",
        error="internal_error",
        detail="Runtime request failed",
        title="Runtime API error",
    )


def install_exception_handlers(app: Any) -> None:
    """Install FastAPI exception handlers that preserve `request_id` and problem semantics."""
    json_response = _JSONResponse
    request_validation_error = _RequestValidationError
    http_exception = _HTTPException
    if json_response is None or request_validation_error is None or http_exception is None:
        return

    async def _handle_runtime_http_error(request: Any, exc: RuntimeHTTPError) -> Any:
        context = collect_error_context(request, exc)
        request_id = context.request_id
        payload = exc.to_model(request_id=request_id, instance=str(request.url.path))
        content = payload.model_dump(mode="json")
        content.update(_context_extension(context))
        return json_response(
            status_code=exc.status_code,
            content=content,
            media_type="application/problem+json",
        )

    async def _handle_runtime_dependency_error(
        request: Any,
        exc: RuntimeDependencyError,
    ) -> Any:
        context = collect_error_context(request, exc)
        error = "gateway_timeout" if exc.status_code == 504 else "service_unavailable"
        return problem_response(
            status_code=exc.status_code,
            code=exc.code,
            detail=exc.detail,
            request_id=context.request_id,
            instance=str(request.url.path),
            error=error,
            extensions=_context_extension(context),
        )

    async def _handle_core_exception(request: Any, exc: BaseException) -> Any:
        context = collect_error_context(request, exc)
        mapped = _map_core_exception(exc)
        return problem_response(
            status_code=mapped.status_code,
            code=mapped.code,
            detail=mapped.detail,
            request_id=context.request_id,
            instance=str(request.url.path),
            error=mapped.error,
            title=mapped.title,
            extensions=_context_extension(context),
        )

    async def _handle_key_error(request: Any, exc: KeyError) -> Any:
        context = collect_error_context(request, exc)
        payload = build_problem(
            status_code=404,
            code="not_found",
            detail=str(exc.args[0]) if exc.args else "resource not found",
            request_id=context.request_id,
            instance=str(request.url.path),
            error="not_found",
        )
        content = payload.model_dump(mode="json")
        content.update(_context_extension(context))
        return json_response(
            status_code=404,
            content=content,
            media_type="application/problem+json",
        )

    async def _handle_value_error(request: Any, exc: ValueError) -> Any:
        context = collect_error_context(request, exc)
        payload = build_problem(
            status_code=400,
            code="bad_request",
            detail=str(exc),
            request_id=context.request_id,
            instance=str(request.url.path),
            error="bad_request",
        )
        content = payload.model_dump(mode="json")
        content.update(_context_extension(context))
        return json_response(
            status_code=400,
            content=content,
            media_type="application/problem+json",
        )

    async def _handle_validation_error(request: Any, exc: Any) -> Any:
        context = collect_error_context(request, exc)
        return problem_response(
            status_code=422,
            code="request_validation_failed",
            detail=str(exc),
            request_id=context.request_id,
            instance=str(request.url.path),
            error="request_validation_failed",
            title="Request validation failed",
            extensions=_context_extension(context),
        )

    async def _handle_http_exception(request: Any, exc: Any) -> Any:
        context = collect_error_context(request, exc)
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
            request_id=context.request_id,
            instance=str(request.url.path),
            error=code,
            extensions=_context_extension(context),
        )

    app.add_exception_handler(RuntimeHTTPError, _handle_runtime_http_error)
    app.add_exception_handler(RuntimeDependencyError, _handle_runtime_dependency_error)
    app.add_exception_handler(ExecutionProfileError, _handle_core_exception)
    app.add_exception_handler(PolicyFlagForbiddenError, _handle_core_exception)
    app.add_exception_handler(TenantIsolationError, _handle_core_exception)
    app.add_exception_handler(PolicyOSError, _handle_core_exception)
    app.add_exception_handler(KeyError, _handle_key_error)
    app.add_exception_handler(ValueError, _handle_value_error)
    app.add_exception_handler(request_validation_error, _handle_validation_error)
    app.add_exception_handler(http_exception, _handle_http_exception)
