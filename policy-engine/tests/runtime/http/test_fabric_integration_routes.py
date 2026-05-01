from __future__ import annotations


def test_fabric_source_scorecards_route_exposes_committed_snapshot(runtime_api_env) -> None:
    client = runtime_api_env["client"]

    response = client.get("/api/v1/fabric/source-scorecards")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "fabric.source_scorecard.v1"
    assert payload["count"] >= 5
    assert "worldbank.wdi.generic" in payload["scorecards"]
    scorecard = payload["scorecards"]["worldbank.wdi.generic"]
    assert scorecard["source_contract_id"] == "worldbank.wdi.generic"
    assert scorecard["metrics"]


def test_fabric_quality_and_trust_batch_routes_share_decision_data_ids(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]
    body = {"run_id": run_id}

    quality_response = client.post(
        "/api/v1/fabric/quality/batch",
        params={"branch": "main"},
        json=body,
    )
    trust_response = client.post(
        "/api/v1/fabric/trust/batch",
        params={"branch": "main"},
        json=body,
    )

    assert quality_response.status_code == 200
    assert trust_response.status_code == 200
    quality_payload = quality_response.json()
    trust_payload = trust_response.json()
    assert quality_payload["temporal_scope"]["branch"] == "main"
    assert trust_payload["temporal_scope"]["branch"] == "main"
    assert quality_payload["quality_refs"]
    assert set(quality_payload["quality_refs"]) == set(trust_payload["trust_refs"])
    assert all(ref["status"] == "passed" for ref in quality_payload["quality_refs"].values())
    assert all(
        {"quality", "access", "lineage", "replay", "time", "gaps"} <= set(row)
        for row in trust_payload["trust_refs"].values()
    )


def test_fabric_replay_route_exposes_run_replay_refs(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]

    response = client.get(f"/api/v1/fabric/runs/{run_id}/replay")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == run_id
    assert payload["replay_refs"]
    assert payload["status_counts"]["replayable"] >= 1
    assert all(ref["manifest_ref"] for ref in payload["replay_refs"].values())


def test_fabric_impact_route_answers_lineage_and_source_contract_impact(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]
    artifact_id = runtime_api_env["decision_packet_artifact_id"]

    response = client.post(
        "/api/v1/fabric/impact",
        json={
            "run_id": run_id,
            "lineage_ids": [f"artifact:{artifact_id}"],
            "source_contract_ids": ["worldbank.wdi.generic"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["run_id"] == run_id
    subjects = {row["subject_id"]: row for row in payload["impacts"]}
    assert f"artifact:{artifact_id}" in subjects
    assert "worldbank.wdi.generic" in subjects
    lineage_row = subjects[f"artifact:{artifact_id}"]
    assert lineage_row["lineage_status"] == "verified"
    assert lineage_row["affected_decision_data_ids"]
    assert lineage_row["source_contract_ids"] == ["worldbank.wdi.generic"]
