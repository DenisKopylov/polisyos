from __future__ import annotations

import pytest

try:  # pragma: no cover - optional dependency guard
    import fastapi  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("fastapi is not installed", allow_module_level=True)

from polisyos.runtime.http.app import export_runtime_openapi_schema
from polisyos.runtime.http.openapi_contract import validate_runtime_openapi_contract


def test_openapi_contract_includes_examples_and_problem_payloads() -> None:
    schema = export_runtime_openapi_schema()
    violations = validate_runtime_openapi_contract(schema)
    assert violations == []


def test_bad_request_uses_problem_json_payload(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get("/api/v1/artifacts/not-a-valid-artifact-id")
    assert response.status_code == 400
    assert response.headers.get("content-type", "").startswith("application/problem+json")

    payload = response.json()
    assert payload["status"] == 400
    assert payload["status_code"] == 400
    assert payload["code"] == "invalid_artifact_id"
    assert payload["error"] == "bad_request"
