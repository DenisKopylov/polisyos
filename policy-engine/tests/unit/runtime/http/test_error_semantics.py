from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, cast

import pytest

from polisyos.common import logger as logger_module
from polisyos.core.contracts.runtime import RuntimeApiProblem
from polisyos.core.errors import ErrorCategory, PolicyOSError
from polisyos.core.security.exceptions import CrossTenantAccessError
from polisyos.fabric.connectors.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
)
from polisyos.runtime.http.errors import (
    RuntimeDependencyTimeoutError,
    RuntimeDependencyUnavailableError,
    RuntimeHTTPError,
    install_exception_handlers,
)
from polisyos.runtime.http.execution_policy import ExecutionProfileError, PolicyFlagForbiddenError
from polisyos.runtime.http.resilience import (
    BlockingDependencyGuard,
    _BlockingDependencyWaitTimeoutError,
)

try:
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    FastAPI = None
    Request = object
    TestClient = None


pytestmark = pytest.mark.skipif(TestClient is None, reason="fastapi is not installed")


@contextmanager
def _forward_runtime_error():
    yield


def _client_for_operation(operation: Callable[[], None]) -> TestClient:
    assert FastAPI is not None
    app = FastAPI()
    install_exception_handlers(app)

    @app.middleware("http")
    async def _attach_request_context(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID", "req-fixture")
        request.state.tenant_id = request.headers.get("X-Tenant-ID", "tenant-fixture")
        return await call_next(request)

    @app.get("/runs/{run_id}/artifacts/{artifact_id}")
    def _raise() -> None:
        with _forward_runtime_error():
            operation()

    return TestClient(app, raise_server_exceptions=False)


def _client_for(exc: BaseException) -> TestClient:
    def _raise() -> None:
        raise exc

    return _client_for_operation(_raise)


def test_cross_tenant_error_maps_to_forbidden_problem_response() -> None:
    client = _client_for(CrossTenantAccessError("tenant-a", "tenant-b", "run:R1"))

    response = client.get(
        "/runs/R1/artifacts/sha256:abc",
        headers={"X-Request-ID": "req-123", "X-Tenant-ID": "tenant-a"},
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["code"] == "cross_tenant_access_denied"
    assert payload["error"] == "forbidden"
    assert payload["request_id"] == "req-123"
    assert payload["context"]["tenant"] == "tenant-a"
    assert payload["context"]["run_id"] == "R1"
    assert payload["context"]["artifact_id"] == "sha256:abc"


@pytest.mark.parametrize(
    ("exc", "status_code", "code"),
    [
        (
            ExecutionProfileError("invalid_execution_profile", "Unsupported profile"),
            400,
            "invalid_execution_profile",
        ),
        (
            PolicyFlagForbiddenError("policy_flag_forbidden", "Restricted flag"),
            403,
            "policy_flag_forbidden",
        ),
    ],
)
def test_execution_policy_errors_map_to_typed_problem_response(
    exc: BaseException,
    status_code: int,
    code: str,
) -> None:
    client = _client_for(exc)

    response = client.get("/runs/R1/artifacts/A1")

    assert response.status_code == status_code
    assert response.json()["code"] == code


def test_policyos_error_context_is_preserved_and_storage_details_are_sanitized() -> None:
    exc = PolicyOSError(
        "S3 write failed bucket=private-prod region=us-east-1 token=supersecret s3://private-prod/key",
        category=ErrorCategory.TRANSIENT,
        stage="core.artifacts.s3",
        code="storage_backend_failed",
        details={"dependency": "s3", "retry_state": "attempt_2"},
    )
    client = _client_for(exc)

    response = client.get("/runs/R2/artifacts/A2", headers={"X-Request-ID": "req-s3"})

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "storage_backend_failed"
    assert "private-prod" not in payload["detail"]
    assert "us-east-1" not in payload["detail"]
    assert "supersecret" not in payload["detail"]
    assert "s3://[redacted]" in payload["detail"]
    assert payload["context"]["dependency"] == "s3"
    assert payload["context"]["retry_state"] == "attempt_2"
    assert payload["context"]["stage"] == "core.artifacts.s3"


def test_runtime_http_error_uses_one_strict_envelope_and_preserves_diagnostics() -> None:
    client = _client_for(
        RuntimeHTTPError(
            status_code=409,
            error="conflict",
            detail="Selected evidence needs review",
            code="evidence_conflict",
            extensions={"authority_surface_decision": {"status": "blocked"}},
        )
    )

    response = client.get("/runs/R1/artifacts/A1")

    assert response.status_code == 409
    payload = RuntimeApiProblem.model_validate_json(response.content, strict=True)
    assert payload.context is not None
    assert payload.context.run_id == "R1"
    assert payload.extensions == {"authority_surface_decision": {"status": "blocked"}}
    assert "authority_surface_decision" not in response.json()


def test_key_and_value_errors_share_the_typed_problem_emitter() -> None:
    errors = (
        (KeyError("missing artifact"), 404),
        (ValueError("invalid filter"), 400),
    )
    for exc, status_code in errors:
        response = _client_for(exc).get("/runs/R1/artifacts/A1")

        assert response.status_code == status_code
        RuntimeApiProblem.model_validate_json(response.content, strict=True)


_WAIT_LOG_EVENT = "runtime_dependency_wait_timeout"
_WAIT_TEST_PATH = "/runs/R-timeout/artifacts/A-timeout"


@contextmanager
def _rendered_http_error_log(*, broken_sink: bool = False) -> Iterator[list[str]]:
    """Capture the real common logger's rendered message, not a warning mock."""
    rendered: list[str] = []

    def consume(message: object) -> None:
        rendered.append(str(message).strip())
        if broken_sink:
            raise OSError("test-owned log sink is unavailable")

    if logger_module._USE_LOGURU:
        backend = cast("Any", logger_module._loguru_logger)
        sink_id = backend.add(
            consume,
            format="{message}",
            filter=lambda record: record["extra"].get("module") == "polisyos.runtime.http.errors",
            catch=False,
        )
        try:
            yield rendered
        finally:
            backend.remove(sink_id)
        return

    class RenderedHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            consume(self.format(record))

    backend = logging.getLogger("polisyos.runtime.http.errors")
    handler = RenderedHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    previous_level = backend.level
    backend.setLevel(logging.WARNING)
    backend.addHandler(handler)
    try:
        yield rendered
    finally:
        backend.removeHandler(handler)
        backend.setLevel(previous_level)
        handler.close()


def _single_rendered_wait_event(rendered: list[str]) -> dict[str, Any]:
    prefix = _WAIT_LOG_EVENT + " "
    messages = [message.removeprefix(prefix) for message in rendered if message.startswith(prefix)]
    assert len(messages) == 1, "one rendered canonical wait diagnostic is required"
    event = json.loads(messages[0])
    assert type(event) is dict
    return event


def _plain_timeout_problem(request_id: str) -> dict[str, Any]:
    with _client_for(RuntimeDependencyTimeoutError("content_addressed_storage")) as client:
        response = client.get(_WAIT_TEST_PATH, headers={"X-Request-ID": request_id})
    assert response.status_code == 504
    RuntimeApiProblem.model_validate_json(response.content, strict=True)
    return response.json()


def _guard_wait_response(
    request_id: str,
) -> tuple[Any, _BlockingDependencyWaitTimeoutError]:
    """Produce a real guarded wait and consume it through the bare HTTP handler."""
    entered = threading.Event()
    release = threading.Event()
    caught: list[RuntimeDependencyTimeoutError] = []
    guard = BlockingDependencyGuard(
        dependency_name="content_addressed_storage",
        timeout_seconds=0.25,
        breaker=CircuitBreaker(
            circuit_id="http-wait-diagnostic-test",
            config=CircuitBreakerConfig(failure_threshold=1, min_throughput=1),
        ),
        executor_max_workers=1,
    )

    def _backend(private_argument: str) -> None:
        assert private_argument == "token=private-backend-argument"
        entered.set()
        assert release.wait(timeout=5), "test must release its own backend"

    def _operation() -> None:
        try:
            guard.run(_backend, "token=private-backend-argument")
        except RuntimeDependencyTimeoutError as exc:
            caught.append(exc)
            raise

    try:
        with _client_for_operation(_operation) as client:
            response = client.get(_WAIT_TEST_PATH, headers={"X-Request-ID": request_id})
        assert entered.is_set(), "the real backend must have started before its deadline"
        assert len(caught) == 1
        assert type(caught[0]) is _BlockingDependencyWaitTimeoutError
        return response, cast("_BlockingDependencyWaitTimeoutError", caught[0])
    finally:
        release.set()
        guard.close()


def test_blocking_wait_timeout_logs_rendered_canonical_diagnostic_without_public_change() -> None:
    request_id = "req-" + "x" * 300
    expected_public = _plain_timeout_problem(request_id)
    with _rendered_http_error_log() as rendered:
        response, error = _guard_wait_response(request_id)

    assert response.status_code == 504
    assert response.json() == expected_public
    RuntimeApiProblem.model_validate_json(response.content, strict=True)
    event = _single_rendered_wait_event(rendered)
    assert event["request_id"] == expected_public["request_id"] == request_id[:256]
    assert event["dependency"] == "content_addressed_storage"
    assert event["code"] == "content_addressed_storage_timeout"
    diagnostic = event["blocking_wait"]
    assert diagnostic == _BlockingDependencyWaitTimeoutError.diagnostic(error)
    assert diagnostic["timeout_seconds"] == 0.25
    assert diagnostic["wait_disposition"] == "running_at_observation"
    assert diagnostic["operation"]["module"] == __name__
    assert diagnostic["operation"]["qualname"].endswith("._backend")
    assert diagnostic["caller"]["qualname"].endswith("._operation")
    assert diagnostic["queue_wait_seconds"] >= 0
    assert diagnostic["wait_elapsed_seconds"] >= diagnostic["timeout_seconds"]
    assert diagnostic["operation_elapsed_seconds"] >= 0
    assert "blocking_wait" not in response.text
    assert "private-backend-argument" not in "\n".join(rendered)
    assert "private-backend-argument" not in response.text


def test_blocking_wait_log_uses_class_getter_and_omits_unknown_diagnostic_payload() -> None:
    """The existing getter bounds unknown keys and invalid symbolic identities."""
    error = _BlockingDependencyWaitTimeoutError(
        "content_addressed_storage",
        diagnostic={
            "timeout_seconds": True,
            "wait_elapsed_seconds": float("nan"),
            "queue_wait_seconds": -1,
            "operation_elapsed_seconds": 0.5,
            "wait_disposition": "untrusted disposition token=private-diagnostic-payload",
            "operation": {"module": "token=private-diagnostic-payload", "qualname": "owned_call"},
            "caller": {
                "module": "owned.module",
                "qualname": "caller token=private-diagnostic-payload",
            },
            "unknown_payload": "private-diagnostic-payload",
        },
    )

    def instance_getter_trap() -> dict[str, object]:
        pytest.fail("the consumer must use the canonical class getter")

    error.diagnostic = instance_getter_trap  # type: ignore[method-assign]
    with _rendered_http_error_log() as rendered, _client_for(error) as client:
        response = client.get(_WAIT_TEST_PATH)

    assert response.status_code == 504
    event = _single_rendered_wait_event(rendered)
    assert event["blocking_wait"] == {
        "timeout_seconds": None,
        "wait_elapsed_seconds": None,
        "queue_wait_seconds": None,
        "operation_elapsed_seconds": 0.5,
        "wait_disposition": "not_established",
        "operation": {"module": "not_established", "qualname": "owned_call"},
        "caller": {"module": "owned.module", "qualname": "not_established"},
    }
    assert "private-diagnostic-payload" not in "\n".join(rendered)
    assert "private-diagnostic-payload" not in response.text
    assert "blocking_wait" not in response.text
    RuntimeApiProblem.model_validate_json(response.content, strict=True)


@pytest.mark.parametrize("unavailable", [False, True], ids=["timeout", "unavailable"])
def test_ordinary_dependency_error_does_not_invoke_duck_diagnostic(unavailable: bool) -> None:
    error = (
        RuntimeDependencyUnavailableError("content_addressed_storage")
        if unavailable
        else RuntimeDependencyTimeoutError("content_addressed_storage")
    )

    def duck_getter_trap() -> dict[str, object]:
        pytest.fail("an unrelated dependency error cannot supply a blocking-wait diagnostic")

    error.diagnostic = duck_getter_trap  # type: ignore[attr-defined]
    with _rendered_http_error_log() as rendered, _client_for(error) as client:
        response = client.get(_WAIT_TEST_PATH)

    assert response.status_code == (503 if unavailable else 504)
    assert not any(_WAIT_LOG_EVENT in message for message in rendered)
    assert "blocking_wait" not in response.text
    RuntimeApiProblem.model_validate_json(response.content, strict=True)


def test_blocking_wait_log_sink_failure_keeps_public_timeout() -> None:
    expected_public = _plain_timeout_problem("req-broken-sink")
    with _rendered_http_error_log(broken_sink=True) as rendered:
        response, _error = _guard_wait_response("req-broken-sink")

    assert response.status_code == 504
    assert response.json() == expected_public
    assert _single_rendered_wait_event(rendered)["request_id"] == "req-broken-sink"
