from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polisyos.core.contracts.runtime import (
    LineageRef,
    QuantityCoverageEntry,
    QuantityValue,
    RunDetails,
    RunTimelineEvent,
    RunTimelineSummary,
    RunTimelineView,
    TemporalRef,
    TemporalScope,
    UnitRef,
)
from polisyos.runtime.http.services.temporal import TemporalService


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_temporal_capabilities_expose_supported_surfaces_and_ranges(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]

    response = client.get("/api/v1/temporal/capabilities", params={"run_id": run_id})

    assert response.status_code == 200
    capabilities = response.json()["capabilities"]
    assert capabilities["run_id"] == run_id
    assert capabilities["valid_range"]["earliest"]
    assert capabilities["valid_range"]["latest"]
    assert capabilities["tx_range"]["latest"]
    assert capabilities["event_points"]
    surfaces = {item["surface"]: item for item in capabilities["surfaces"]}
    assert surfaces["run_details"]["supported"] is True
    assert surfaces["run_timeline"]["supported"] is True
    assert surfaces["run_lineage"]["supported"] is True
    assert surfaces["run_quantities"]["supported"] is True
    assert surfaces["run_agents"]["supported"] is False
    assert surfaces["run_agents"]["reason_code"] == "temporal_surface_unsupported"


def test_run_temporal_scope_is_echoed_in_supported_surfaces(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]
    capabilities = client.get(
        "/api/v1/temporal/capabilities",
        params={"run_id": run_id},
    ).json()["capabilities"]
    valid_at = capabilities["valid_range"]["latest"]
    tx_at = capabilities["tx_range"]["latest"]
    params = {"valid_at": valid_at, "tx_at": tx_at, "branch": "main"}

    for suffix in ("", "/timeline", "/lineage", "/quantities"):
        response = client.get(f"/api/v1/runs/{run_id}{suffix}", params=params)

        assert response.status_code == 200
        assert response.headers["x-temporal-scope"] != "current"
        assert response.headers["etag"].startswith('W/"temporal-')
        payload = response.json()
        assert payload["temporal_scope"]["branch"] == "main"
        assert _parse_iso(payload["temporal_scope"]["valid_at"]) == _parse_iso(valid_at)
        assert _parse_iso(payload["temporal_scope"]["tx_at"]) == _parse_iso(tx_at)


def test_run_temporal_shorthand_maps_to_valid_at(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]
    capabilities = client.get(
        "/api/v1/temporal/capabilities",
        params={"run_id": run_id},
    ).json()["capabilities"]
    valid_at = capabilities["valid_range"]["latest"]
    latest_tx_at = capabilities["tx_range"]["latest"]

    response = client.get(f"/api/v1/runs/{run_id}", params={"t": valid_at})

    assert response.status_code == 200
    temporal_scope = response.json()["temporal_scope"]
    assert _parse_iso(temporal_scope["valid_at"]) == _parse_iso(valid_at)
    assert temporal_scope["tx_at"]
    assert _parse_iso(temporal_scope["tx_at"]) >= _parse_iso(latest_tx_at)


def test_temporal_scope_projects_runtime_state_without_naked_echo() -> None:
    service = TemporalService()
    base = datetime(2026, 4, 15, 12, tzinfo=UTC)
    scope = TemporalScope(valid_at=base + timedelta(seconds=1), tx_at=base + timedelta(seconds=1))

    projected_run = service.project_run_details(
        RunDetails(
            run_id="run_temporal",
            source_kind="core_run",
            status="completed",
            started_at=base,
            finished_at=base + timedelta(seconds=10),
            duration_ms=10_000,
        ),
        scope,
    )
    assert projected_run.status == "running"
    assert projected_run.finished_at is None
    assert projected_run.duration_ms == 1_000

    projected_timeline = service.project_timeline(
        RunTimelineView(
            run_id="run_temporal",
            source_kind="core_run",
            summary=RunTimelineSummary(run_id="run_temporal", total_events=2),
            events=[
                RunTimelineEvent(
                    index=0,
                    timestamp=base,
                    phase="core",
                    event="RUN_STARTED",
                ),
                RunTimelineEvent(
                    index=1,
                    timestamp=base + timedelta(seconds=2),
                    phase="core",
                    event="RUN_FINALIZED",
                ),
            ],
        ),
        scope,
    )
    assert projected_timeline.summary.total_events == 1
    assert [event.event for event in projected_timeline.events] == ["RUN_STARTED"]
    assert "temporal_scope_applied" in projected_timeline.notes

    unit = UnitRef(code="1", system="ucum", display="value")
    lineage = LineageRef(id="lin_metric", status="verified")
    quantities, coverage, entries = service.project_quantities(
        [
            QuantityValue(
                point=1.0,
                unit=unit,
                metric_id="known_metric",
                lineage=lineage,
                time=TemporalRef(valid_at=base, tx_at=base),
            ),
            QuantityValue(
                point=2.0,
                unit=unit,
                metric_id="future_metric",
                lineage=lineage,
                time=TemporalRef(
                    valid_at=base + timedelta(seconds=3),
                    tx_at=base + timedelta(seconds=3),
                ),
            ),
        ],
        [
            QuantityCoverageEntry(
                path="known_metric",
                quantity_class="decision",
                status="verified",
                metric_id="known_metric",
            ),
            QuantityCoverageEntry(
                path="future_metric",
                quantity_class="decision",
                status="verified",
                metric_id="future_metric",
            ),
        ],
        scope,
    )
    assert [quantity.metric_id for quantity in quantities] == ["known_metric"]
    assert [entry.metric_id for entry in entries] == ["known_metric"]
    assert coverage.total == 1


def test_temporal_scope_conflict_returns_422(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]

    response = client.get(
        f"/api/v1/runs/{run_id}",
        params={
            "valid_at": "2026-01-01T00:00:00Z",
            "t": "2026-01-02T00:00:00Z",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "temporal_scope_conflict"


def test_temporal_scope_out_of_range_returns_typed_payload(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]

    response = client.get(
        f"/api/v1/runs/{run_id}/timeline",
        params={"valid_at": "1999-01-01T00:00:00Z"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "temporal_scope_out_of_range"
    assert payload["valid_range"]["earliest"]
    assert payload["tx_range"]["latest"]
    assert payload["nearest_event_points"]


def test_unsupported_temporal_surface_fails_closed(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]
    valid_at = client.get(
        "/api/v1/temporal/capabilities",
        params={"run_id": run_id},
    ).json()["capabilities"]["valid_range"]["latest"]

    response = client.get(
        f"/api/v1/runs/{run_id}/agents",
        params={"valid_at": valid_at},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "temporal_surface_unsupported"
