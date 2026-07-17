from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polisyos.fabric.provenance.lineage import FabricLineageTracker, trace_value_origin


def test_runtime_lineage_endpoint_returns_compact_and_full_graph(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["decision_packet_artifact_id"]

    response = client.get(
        f"/api/v1/lineage/artifact:{artifact_id}",
        params={"valid_at": "2026-04-15T12:00:00Z", "branch": "main"},
    )
    assert response.status_code == 200

    lineage = response.json()["lineage"]
    temporal_scope = response.json()["temporal_scope"]
    assert lineage["id"] == f"artifact:{artifact_id}"
    assert lineage["status"] in {"verified", "disputed"}
    assert lineage["compact_summary"]
    assert lineage["nodes"]
    assert lineage["exports"]["openlineage"].endswith("/export/openlineage")
    assert lineage["exports"]["prov"].endswith("/export/prov")
    assert lineage["trust_metadata"]["verification_status"] == lineage["status"]
    assert lineage["trust_metadata"]["verification_method"] == "lineage_hash_match"
    assert lineage["trust_metadata"]["temporal_scope"]["valid_at"] == "2026-04-15T12:00:00Z"
    assert temporal_scope["valid_at"] == "2026-04-15T12:00:00Z"
    assert temporal_scope["branch"] == "main"
    assert response.headers["x-temporal-scope"] != "current"


def test_runtime_lineage_batch_preserves_order(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["decision_packet_artifact_id"]

    response = client.post(
        "/api/v1/lineage/batch",
        params={"t": "2026-04-15T12:00:00Z"},
        json={"lineage_ids": [f"artifact:{artifact_id}", "lin_unknown"]},
    )
    assert response.status_code == 200

    lineages = response.json()["lineages"]
    assert [item["id"] for item in lineages] == [f"artifact:{artifact_id}", "lin_unknown"]
    assert response.json()["temporal_scope"]["valid_at"] == "2026-04-15T12:00:00Z"
    assert lineages[1]["status"] == "untraced"
    assert lineages[1]["metadata"]["reason_code"] == "lineage_id_not_resolved"
    assert lineages[1]["trust_metadata"]["verification_status"] == "untraced"
    assert lineages[1]["trust_metadata"]["temporal_scope"]["valid_at"] == "2026-04-15T12:00:00Z"


def test_runtime_lineage_exports(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["decision_packet_artifact_id"]

    openlineage = client.get(
        f"/api/v1/lineage/artifact:{artifact_id}/export/openlineage",
        params={"valid_at": "2026-04-15T12:00:00Z"},
    )
    assert openlineage.status_code == 200
    assert openlineage.json()["format"] == "openlineage"
    assert openlineage.json()["payload"]["producer"] == "polisyos-runtime-api"
    assert openlineage.json()["temporal_scope"]["valid_at"] == "2026-04-15T12:00:00Z"

    prov = client.get(f"/api/v1/lineage/artifact:{artifact_id}/export/prov")
    assert prov.status_code == 200
    assert prov.json()["format"] == "prov"
    assert "entity" in prov.json()["payload"]


def test_runtime_lineage_exports_bind_shared_replay_contract(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["decision_packet_artifact_id"]
    path = f"/api/v1/lineage/artifact:{artifact_id}/export/openlineage"
    params = {"valid_at": "2026-04-15T12:00:00Z"}

    first = client.get(path, params=params)

    assert first.status_code == 200
    projection_hash = first.headers["x-policyos-export-projection-hash"]
    assert projection_hash.startswith("sha256:")
    assert first.headers["x-policyos-export-stable-address"].startswith(path)
    assert first.headers["x-policyos-export-replay-address"].startswith(path)
    assert first.headers["x-policyos-export-as-of"] == "2026-04-15T12:00:00+00:00"

    replay = client.get(
        path,
        params={**params, "export_projection_hash": projection_hash},
    )
    mismatch = client.get(
        path,
        params={**params, "export_projection_hash": "sha256:" + "0" * 64},
    )

    assert replay.status_code == 200
    assert replay.headers["x-policyos-export-projection-hash"] == projection_hash
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "export_replay_pin_mismatch"


def test_run_quantities_inventory_reports_traced_and_untraced(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]

    response = client.get(f"/api/v1/runs/{run_id}/quantities")
    assert response.status_code == 200

    payload = response.json()
    assert payload["run_id"] == run_id
    assert payload["coverage"]["decision"] >= 1
    assert payload["coverage"]["telemetry"] >= 1
    assert payload["coverage"]["traced"] >= 1
    assert payload["coverage"]["untraced"] >= 1
    assert any(
        entry["path"] == "decision_packet.simulation_results.policy_cost"
        for entry in payload["entries"]
    )
    assert any(
        quantity["lineage"]["status"] == "untraced"
        and quantity["lineage"]["reason_code"] == "runtime_telemetry_not_decision_bearing"
        for quantity in payload["quantities"]
    )


def test_lineage_service_projects_fabric_trace_to_runtime_view(runtime_api_env) -> None:
    tracker = FabricLineageTracker("graph.runtime.fabric")
    started_at = datetime(2026, 4, 24, tzinfo=UTC)
    completed_at = started_at + timedelta(seconds=1)
    tracker.register_source_dataset(
        connector_id="worldbank.wdi",
        dataset_id="NY.GDP.MKTP.CD",
        fields=["gdp_local"],
        schema_id="schema.gdp",
    )
    _activity_id, outputs = tracker.record_transform_stage(
        stage_name="normalize",
        started_at=started_at,
        completed_at=completed_at,
        input_columns=["gdp_local"],
        output_columns=["gdp_usd"],
        parameters={"field_mappings": {"gdp_local": "gdp_usd"}},
    )
    trace = trace_value_origin(tracker.graph, outputs["gdp_usd"])
    container = runtime_api_env["app"].state.runtime_container

    lineage = container.runtime_api_context.lineage.build_from_fabric_trace(trace)

    assert lineage.id == f"fabric:{outputs['gdp_usd']}"
    assert lineage.status == "verified"
    assert lineage.freshness == "current"
    assert lineage.nodes
    assert lineage.edges
    assert any(item.kind == "source" for item in lineage.compact_summary)
    assert any(item.kind == "transform" for item in lineage.compact_summary)
