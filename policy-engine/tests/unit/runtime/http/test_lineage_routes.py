from __future__ import annotations


def test_lineage_batch_lookup_uses_compact_batch_adapter(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["decision_packet_artifact_id"]
    lineage_ids = [f"artifact:{artifact_id}", "lin_unknown", f"artifact:{artifact_id}"]

    response = client.post(
        "/api/v1/lineage/batch",
        params={"valid_at": "2026-04-15T12:00:00Z", "branch": "main"},
        json={"lineage_ids": lineage_ids},
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload["lineages"]] == lineage_ids
    assert payload["temporal_scope"]["branch"] == "main"
    assert all(
        item["trust_metadata"]["temporal_scope"]["branch"] == "main" for item in payload["lineages"]
    )
    assert payload["lineages"][1]["status"] == "untraced"


def test_compact_lineage_batch_local_benchmark_meets_phase6_budget(runtime_api_env) -> None:
    container = runtime_api_env["app"].state.runtime_container
    service = container.runtime_api_context.lineage

    report = service.benchmark_compact_lineage_batch(
        [f"lin_unknown_{index}" for index in range(50)]
    )

    assert report["count"] == 50
    assert report["unique_count"] == 50
    assert report["p95_ms"] <= 150.0
    assert report["status_counts"]["untraced"] == 50


def test_full_lineage_graph_local_benchmark_meets_phase6_budget(runtime_api_env) -> None:
    container = runtime_api_env["app"].state.runtime_container
    service = container.runtime_api_context.lineage
    artifact_id = runtime_api_env["decision_packet_artifact_id"]

    report = service.benchmark_full_lineage_graph([artifact_id])

    assert report["root_count"] == 1
    assert report["node_count"] >= 1
    assert report["p95_ms"] <= 500.0
    assert report["is_complete"] is True
