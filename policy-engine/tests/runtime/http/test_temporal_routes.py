from __future__ import annotations


def test_fabric_decision_data_route_wraps_decision_values_and_echoes_temporal_scope(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]
    capabilities = client.get(
        "/api/v1/temporal/capabilities",
        params={"run_id": run_id},
    ).json()["capabilities"]
    params = {
        "valid_at": capabilities["valid_range"]["latest"],
        "tx_at": capabilities["tx_range"]["latest"],
        "branch": "main",
    }

    response = client.get(f"/api/v1/runs/{run_id}/fabric-decision-data", params=params)

    assert response.status_code == 200
    assert response.headers["x-temporal-scope"] != "current"
    payload = response.json()
    assert payload["temporal_scope"]["branch"] == "main"
    assert payload["coverage"]["naked_decision_values"] == 0
    assert payload["coverage"]["decision"] >= 1
    assert payload["decision_data"]
    for item in payload["decision_data"]:
        assert item["kind"] == "quantity"
        assert set(item) >= {
            "value",
            "source_contract",
            "quality",
            "lineage",
            "access",
            "time",
            "replay",
            "gaps",
        }
        assert item["time"]["branch"] == "main"
        assert item["quality"]["status"] in {"passed", "warning", "failed", "unknown_quality"}
        assert item["lineage"]["compact_summary_ref"].startswith("/api/v1/lineage/")


def test_temporal_capabilities_include_fabric_decision_data_surface(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]

    response = client.get("/api/v1/temporal/capabilities", params={"run_id": run_id})

    assert response.status_code == 200
    surfaces = {item["surface"]: item for item in response.json()["capabilities"]["surfaces"]}
    assert surfaces["run_fabric_decision_data"]["supported"] is True
