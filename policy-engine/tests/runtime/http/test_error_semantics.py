from __future__ import annotations

import pytest

from polisyos.core.errors import ErrorCategory, PolicyOSError
from polisyos.core.security.exceptions import CrossTenantAccessError
from polisyos.runtime.http.errors import install_exception_handlers
from polisyos.runtime.http.execution_policy import ExecutionProfileError, PolicyFlagForbiddenError

try:
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    FastAPI = None
    Request = object
    TestClient = None


pytestmark = pytest.mark.skipif(TestClient is None, reason="fastapi is not installed")


def _client_for(exc: BaseException) -> TestClient:
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
        raise exc

    return TestClient(app, raise_server_exceptions=False)


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
