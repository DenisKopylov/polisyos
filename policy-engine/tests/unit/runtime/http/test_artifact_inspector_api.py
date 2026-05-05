from __future__ import annotations


def test_artifact_manifest_endpoint_returns_canonical_metadata(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["workflow_report_artifact_id"]
    response = client.get(f"/api/v1/artifacts/{artifact_id}")
    assert response.status_code == 200

    artifact = response.json()["artifact"]
    assert artifact["artifact_id"] == artifact_id
    assert artifact["kind"] == "scientist.workflow_report"
    assert artifact["schema_name"] == "scientist.workflow_report"


def test_artifact_content_preview_enforces_max_bytes(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["binary_artifact_id"]
    response = client.get(f"/api/v1/artifacts/{artifact_id}/content?max_bytes=1024")
    assert response.status_code == 200

    preview = response.json()["artifact"]
    assert preview["artifact_id"] == artifact_id
    assert preview["truncated"] is True
    assert preview["max_bytes"] == 1024

    secret = client.get(f"/api/v1/artifacts/{runtime_api_env['secret_artifact_id']}/content")
    assert secret.status_code == 200
    secret_preview = secret.json()["artifact"]
    assert secret_preview["preview"] == "[REDACTED]"


def test_artifact_lineage_and_schema_endpoints(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["workflow_report_artifact_id"]

    lineage = client.get(f"/api/v1/artifacts/{artifact_id}/lineage")
    assert lineage.status_code == 200
    lineage_payload = lineage.json()["lineage"]
    assert lineage_payload["total_nodes"] >= 1
    assert artifact_id in lineage_payload["root_artifact_ids"]

    schema = client.get(f"/api/v1/artifacts/{artifact_id}/schema")
    assert schema.status_code == 200
    schema_payload = schema.json()["schema"]
    assert schema_payload["schema_name"] == "scientist.workflow_report"
