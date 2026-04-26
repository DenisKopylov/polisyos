from __future__ import annotations

import json
from importlib.util import find_spec
from pathlib import Path

import pytest

if find_spec("fastapi") is None:  # pragma: no cover - optional dependency guard
    pytest.skip("fastapi is not installed", allow_module_level=True)

from polisyos.runtime.http.app import export_runtime_openapi_schema
from polisyos.runtime.http.openapi_contract import validate_runtime_openapi_contract
from tools.runtime import generate_runtime_client


def test_openapi_contract_includes_examples_and_problem_payloads() -> None:
    schema = export_runtime_openapi_schema()
    violations = validate_runtime_openapi_contract(schema)
    assert violations == []


def test_openapi_contract_includes_client_navigation_links() -> None:
    schema = export_runtime_openapi_schema()
    run_links = schema["paths"]["/api/v1/runs/{run_id}"]["get"]["responses"]["200"]["links"]
    artifact_links = schema["paths"]["/api/v1/artifacts/{artifact_id}"]["get"]["responses"]["200"][
        "links"
    ]
    mobility_links = schema["paths"]["/api/v1/mobility/reports/{artifact_id}"]["get"]["responses"][
        "200"
    ]["links"]

    assert sorted(run_links) == [
        "runAgents",
        "runEvidenceContext",
        "runLineage",
        "runNodes",
        "runQuantities",
        "runTimeline",
        "runWorkflow",
    ]
    assert sorted(artifact_links) == [
        "artifactDownload",
        "artifactLineage",
        "artifactPreview",
        "artifactSchema",
    ]
    assert sorted(mobility_links) == [
        "mobilityBounds",
        "mobilityDiagnostics",
    ]


def test_openapi_contract_includes_batch_read_operations() -> None:
    schema = export_runtime_openapi_schema()

    runs_batch = schema["paths"]["/api/v1/runs/batch"]["post"]
    artifacts_batch = schema["paths"]["/api/v1/artifacts/batch"]["post"]

    assert runs_batch["operationId"] == "get_runs_batch"
    assert artifacts_batch["operationId"] == "get_artifact_batch"
    lineage_batch = schema["paths"]["/api/v1/lineage/batch"]["post"]
    assert lineage_batch["operationId"] == "get_lineage_batch"


def test_generated_runtime_client_includes_batch_read_wrappers() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    spec_path = repo_root / "schemas" / "runtime_api_v1.openapi.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    operations = generate_runtime_client._extract_operations(spec)
    names = {operation.name for operation in operations}

    assert "getRunsBatch" in names
    assert "getArtifactBatch" in names


def test_generated_runtime_client_includes_mobility_wrappers() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    spec_path = repo_root / "schemas" / "runtime_api_v1.openapi.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    operations = generate_runtime_client._extract_operations(spec)
    names = {operation.name for operation in operations}

    assert "estimateMobility" in names
    assert "computeMobilityBounds" in names
    assert "getMobilityReport" in names
    assert "getMobilityReportBounds" in names
    assert "getMobilityReportDiagnostics" in names


def test_generated_runtime_js_client_accepts_params_for_body_operations() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    spec_path = repo_root / "schemas" / "runtime_api_v1.openapi.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    operations = generate_runtime_client._extract_operations(spec)
    rendered_js = generate_runtime_client._render_js(operations)

    body_operations = [
        operation.name for operation in operations if operation.body_schema is not None
    ]

    for operation_name in body_operations:
        assert f"async {operation_name}(params) {{" in rendered_js


def test_committed_runtime_client_matches_generator() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    spec_path = repo_root / "schemas" / "runtime_api_v1.openapi.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    operations = generate_runtime_client._extract_operations(spec)
    expected_ts = generate_runtime_client._render_ts(spec, operations)
    expected_js = generate_runtime_client._render_js(operations)

    client_root = repo_root / "frontend" / "runtime-api-client"
    committed_ts = (client_root / "runtimeApiClient.ts").read_text(encoding="utf-8")
    committed_js = (client_root / "runtimeApiClient.js").read_text(encoding="utf-8")

    assert committed_ts == expected_ts
    assert committed_js == expected_js


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
