from __future__ import annotations

from datetime import datetime

from polisyos.core.contracts.runtime import (
    LineageRef,
    QuantityCoverageEntry,
    QuantityCoverageSummary,
    QuantityUncertainty,
    QuantityValue,
    TemporalRef,
    UnitRef,
)


def test_compare_runs_returns_comparison_frame_and_quantity_deltas(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_a = runtime_api_env["core_run_id"]
    run_b = runtime_api_env["core_run_id_secondary"]
    run_a_details = client.get(f"/api/v1/runs/{run_a}").json()["run"]

    response = client.get(
        "/api/v1/runs/compare",
        params={
            "a": run_a,
            "b": run_b,
            "valid_at": run_a_details["started_at"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert response.headers["X-Temporal-Scope"] != "current"
    assert response.headers["ETag"].startswith('W/"temporal-')
    assert payload["comparison_frame"]["run_a"] == run_a
    assert payload["comparison_frame"]["run_b"] == run_b
    assert payload["comparison_frame"]["temporal_scope"]["valid_at"] is not None
    assert payload["comparability"]["status"] in {"compatible", "warning"}
    assert payload["deltas"]

    by_metric = {item["metric_id"]: item for item in payload["deltas"]}
    assert "policy_cost" in by_metric
    policy_cost = by_metric["policy_cost"]
    assert policy_cost["a"]["quantity_class"] == "decision"
    assert policy_cost["b"]["quantity_class"] == "decision"
    assert policy_cost["delta_absolute"]["quantity_class"] == "decision"
    assert policy_cost["delta_absolute"]["lineage"]["summary"]["method"] == "QuantityValue delta"
    assert policy_cost["lineage_delta"]["source_changed"] is True


def test_compare_runs_blocks_same_run_without_misleading_deltas(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]

    response = client.get("/api/v1/runs/compare", params={"a": run_id, "b": run_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["comparability"]["status"] == "blocked"
    assert "same_run" in payload["comparability"]["blocked_reasons"]
    assert payload["deltas"] == []


def test_compare_candidates_respects_tenant_and_reports_comparability(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]

    response = client.get(f"/api/v1/runs/{run_id}/compare-candidates")

    assert response.status_code == 200
    payload = response.json()
    candidate_ids = {item["run_id"] for item in payload["candidates"]}
    assert runtime_api_env["core_run_id_secondary"] in candidate_ids
    assert runtime_api_env["cross_tenant_run_id"] not in candidate_ids
    assert all("comparability" in item for item in payload["candidates"])
    assert all(
        item["relation"] in {"baseline", "previous", "recommended"}
        for item in payload["candidates"]
    )


def test_compare_runs_respects_tx_at_for_late_arriving_quantity(
    monkeypatch,
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    run_a_id = runtime_api_env["core_run_id"]
    run_b_id = runtime_api_env["core_run_id_secondary"]
    ctx = runtime_api_env["app"].state.runtime_api_ctx

    capabilities_a = client.get(
        "/api/v1/temporal/capabilities",
        params={"run_id": run_a_id},
    ).json()["capabilities"]
    capabilities_b = client.get(
        "/api/v1/temporal/capabilities",
        params={"run_id": run_b_id},
    ).json()["capabilities"]
    valid_at = min(
        _parse_dt(capabilities_a["valid_range"]["latest"]),
        _parse_dt(capabilities_b["valid_range"]["latest"]),
    )
    early_tx_at = max(
        _parse_dt(capabilities_a["tx_range"]["earliest"]),
        _parse_dt(capabilities_b["tx_range"]["earliest"]),
    )
    late_tx_at = min(
        _parse_dt(capabilities_a["tx_range"]["latest"]),
        _parse_dt(capabilities_b["tx_range"]["latest"]),
    )
    assert early_tx_at < late_tx_at

    def fake_inventory(run):
        point = 10.0 if run.run_id == run_a_id else 12.0
        quantity = QuantityValue(
            point=point,
            unit=UnitRef(code="[USD]", system="ucum", display="USD"),
            metric_id="late_policy_cost",
            label="Late policy cost",
            lineage=LineageRef(
                id=f"lin_{run.run_id}_late_policy_cost",
                status="verified",
                freshness="current",
                summary={"source": run.run_id, "method": "late-evidence-fixture"},
            ),
            uncertainty=QuantityUncertainty(
                ci_95=(point - 1.0, point + 1.0),
                method="bootstrap",
                identifiability="estimated",
            ),
            time=TemporalRef(valid_at=valid_at, tx_at=late_tx_at),
            quantity_class="decision",
        )
        entry = QuantityCoverageEntry(
            path="fixture.late_policy_cost",
            quantity_class="decision",
            status="verified",
            lineage_id=quantity.lineage.id,
            metric_id=quantity.metric_id,
        )
        coverage = QuantityCoverageSummary(
            total=1,
            decision=1,
            traced=1,
        )
        return [quantity], coverage, [entry]

    monkeypatch.setattr(
        ctx.compare._lineage,
        "build_quantity_inventory_for_run",
        fake_inventory,
    )

    early_response = client.get(
        "/api/v1/runs/compare",
        params={
            "a": run_a_id,
            "b": run_b_id,
            "valid_at": valid_at.isoformat(),
            "tx_at": early_tx_at.isoformat(),
        },
    )
    late_response = client.get(
        "/api/v1/runs/compare",
        params={
            "a": run_a_id,
            "b": run_b_id,
            "valid_at": valid_at.isoformat(),
            "tx_at": late_tx_at.isoformat(),
        },
    )

    assert early_response.status_code == 200
    assert late_response.status_code == 200
    assert early_response.json()["deltas"] == []
    by_metric = {item["metric_id"]: item for item in late_response.json()["deltas"]}
    assert by_metric["late_policy_cost"]["delta_absolute"]["point"] == 2.0


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
