from __future__ import annotations

from datetime import UTC, datetime

from polisyos.core.contracts.runtime import TemporalScope


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
        assert item["source_contract"] == {
            "id": "worldbank.wdi.generic",
            "version": "1.1.0",
        }
        assert item["quality"]["status"] in {"passed", "warning", "failed", "unknown_quality"}
        assert item["lineage"]["compact_summary_ref"].startswith("/api/v1/lineage/")
        assert item["lineage"]["full_graph_ref"].endswith("?view=full")
        assert item["lineage"]["raw_evidence_refs"]
        assert set(item["lineage"]["export_links"]) == {"openlineage", "prov"}


def test_runtime_batches_quality_and_trust_refs_without_n_plus_one(runtime_api_env) -> None:
    container = runtime_api_env["app"].state.runtime_container
    ctx = container.runtime_api_context
    run = ctx.run_index.get_run(runtime_api_env["core_run_id"])

    decision_data, coverage = ctx.lineage.build_fabric_decision_data_for_run(run)
    quality_refs = ctx.lineage.build_quality_refs_batch(decision_data)
    trust_refs = ctx.lineage.build_trust_refs_batch(decision_data)

    assert coverage.decision == len(decision_data)
    assert set(quality_refs) == {item.id for item in decision_data}
    assert set(trust_refs) == {item.id for item in decision_data}
    assert all(ref.status == "passed" for ref in quality_refs.values())
    assert all(
        {"quality", "lineage", "access", "replay", "time"} <= set(row)
        for row in trust_refs.values()
    )


def test_fabric_trust_metadata_is_stable_for_same_valid_time_and_different_tx_time(
    runtime_api_env,
) -> None:
    container = runtime_api_env["app"].state.runtime_container
    ctx = container.runtime_api_context
    run = ctx.run_index.get_run(runtime_api_env["core_run_id"])
    valid_at = datetime(2026, 4, 15, 12, tzinfo=UTC)
    early_scope = TemporalScope(
        valid_at=valid_at,
        tx_at=datetime(2026, 4, 16, 9, 20, tzinfo=UTC),
        branch="main",
    )
    late_scope = TemporalScope(
        valid_at=valid_at,
        tx_at=datetime(2026, 4, 26, 10, tzinfo=UTC),
        branch="main",
    )

    early_data, _early_coverage = ctx.lineage.build_fabric_decision_data_for_run(
        run,
        temporal_scope=early_scope,
    )
    late_data, _late_coverage = ctx.lineage.build_fabric_decision_data_for_run(
        run,
        temporal_scope=late_scope,
    )
    early_trust = ctx.lineage.build_trust_refs_batch(early_data)
    late_trust = ctx.lineage.build_trust_refs_batch(late_data)

    assert early_data and late_data
    assert {item.id for item in early_data} == {item.id for item in late_data}
    for item_id in early_trust:
        assert early_trust[item_id]["time"]["valid_at"] == late_trust[item_id]["time"]["valid_at"]
        assert early_trust[item_id]["time"]["tx_at"] != late_trust[item_id]["time"]["tx_at"]
        assert early_trust[item_id]["quality"]["status"] == late_trust[item_id]["quality"]["status"]
        assert early_trust[item_id]["lineage"]["id"] == late_trust[item_id]["lineage"]["id"]


def test_temporal_capabilities_include_fabric_decision_data_surface(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]

    response = client.get("/api/v1/temporal/capabilities", params={"run_id": run_id})

    assert response.status_code == 200
    capabilities = response.json()["capabilities"]
    surfaces = {item["surface"]: item for item in capabilities["surfaces"]}
    assert surfaces["run_fabric_decision_data"]["supported"] is True
    assert capabilities["branch_support"] is True
    assert capabilities["snapshot_support"] is True
    assert capabilities["graph_temporal_scope"] == "partial"
    assert "world.world_facts" in capabilities["supported_tables"]
