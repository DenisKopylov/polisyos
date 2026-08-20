from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from polisyos.core.trace.record import RunTerminality
from tests.unit.runtime.http.test_cycle_board_projection_service import (
    OBSERVED_AT,
    _component_packets,
    _depth_payload,
    _row,
    _service,
    _summary,
)


@pytest.mark.parametrize(
    ("status", "started_at", "finished_at", "duration_ms"),
    [
        ("finished", OBSERVED_AT, OBSERVED_AT, 1),
        ("terminal-success", None, None, 86_400_000),
        ("completed-finalized", OBSERVED_AT.replace(year=1999), None, 0),
        (
            "new-opaque-terminal-looking-label",
            OBSERVED_AT.replace(year=2099),
            OBSERVED_AT,
            -1,
        ),
    ],
)
def test_lifecycle_absence_ignores_every_status_and_time_proxy(
    status: str,
    started_at: datetime | None,
    finished_at: datetime | None,
    duration_ms: int,
) -> None:
    run_id = "cycle-first_vertical"
    legacy_summary_without_signed_fact = SimpleNamespace(
        run_id=run_id,
        source_kind="core_run",
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
    )
    service, _, _ = _service(summaries={run_id: legacy_summary_without_signed_fact})

    fact = _row(service.get(), "first_vertical").lifecycle_terminality

    assert fact.availability == "not_established"
    assert "value" not in fact.model_dump()


def test_unbound_lifecycle_ignores_every_depth_search_and_acquisition_proxy() -> None:
    run_id = "cycle-first_vertical"
    unsigned = SimpleNamespace(
        run_id=run_id,
        source_kind="core_run",
        status="finished",
        finished_at=OBSERVED_AT,
    )
    depth = _depth_payload()
    original = depth.domain_runs["first_vertical"]
    variants = (
        original.model_copy(update={"search_terminal_kind": "terminal"}),
        original.model_copy(
            update={
                "terminal_distribution": {
                    "terminal_kind": "completed",
                    "finished_at": OBSERVED_AT.isoformat(),
                }
            }
        ),
        original.model_copy(update={"weakest_links": ("run_finished",)}),
        original.model_copy(
            update={
                "acquisition_route": original.acquisition_route.model_copy(
                    update={
                        "planner_status": "complete",
                        "next_action": "none_finished",
                    }
                )
            }
        ),
    )

    for variant in variants:
        runs = dict(depth.domain_runs)
        runs["first_vertical"] = variant
        varied_depth = depth.model_copy(update={"domain_runs": runs})
        service, _, _ = _service(
            packets=_component_packets(depth=varied_depth),
            summaries={run_id: unsigned},
        )
        fact = _row(service.get(), "first_vertical").lifecycle_terminality
        assert fact.availability == "not_established"
        assert "value" not in fact.model_dump()


def test_signed_lifecycle_fact_is_distinct_from_search_terminal_and_absence() -> None:
    run_id = "cycle-first_vertical"
    terminal, _, _ = _service(
        summaries={
            run_id: _summary(
                run_id,
                RunTerminality.TERMINAL,
                status="definitely-not-a-terminal-status",
            )
        }
    )
    producer_unknown, _, _ = _service(
        summaries={run_id: _summary(run_id, RunTerminality.NOT_ESTABLISHED, status="finished")}
    )
    absent, _, _ = _service()
    mismatched, _, _ = _service(
        summaries={run_id: _summary("different-cycle-run", RunTerminality.TERMINAL)}
    )

    terminal_packet = terminal.get()
    producer_unknown_packet = producer_unknown.get()
    absent_packet = absent.get()
    mismatched_packet = mismatched.get()
    terminal_row = _row(terminal_packet, "first_vertical")
    producer_unknown_row = _row(producer_unknown_packet, "first_vertical")
    absent_row = _row(absent_packet, "first_vertical")
    mismatched_row = _row(mismatched_packet, "first_vertical")

    assert terminal_row.lifecycle_terminality.value is RunTerminality.TERMINAL
    assert terminal_row.search_terminal_kind.value == "search-terminal-first_vertical"
    assert producer_unknown_row.lifecycle_terminality.value is RunTerminality.NOT_ESTABLISHED
    assert producer_unknown_row.lifecycle_terminality.availability == "available"
    assert producer_unknown_row.search_terminal_kind == terminal_row.search_terminal_kind
    assert absent_row.lifecycle_terminality.availability == "not_established"
    assert "value" not in absent_row.lifecycle_terminality.model_dump()
    assert mismatched_row.lifecycle_terminality.availability == "not_established"
    assert "value" not in mismatched_row.lifecycle_terminality.model_dump()
    lifecycle_source_id = f"run-summary:{run_id}"
    terminal_source = next(
        entry
        for entry in terminal_packet.composition_manifest
        if entry.source_id == lifecycle_source_id
    )
    producer_unknown_source = next(
        entry
        for entry in producer_unknown_packet.composition_manifest
        if entry.source_id == lifecycle_source_id
    )
    assert terminal_source.availability == "available"
    assert producer_unknown_source.availability == "available"
    assert terminal_source.artifact_content_hash != producer_unknown_source.artifact_content_hash
    assert terminal_source.as_of is None
    assert terminal_source.freshness is None

    changed_depth = _depth_payload()
    changed_runs = dict(changed_depth.domain_runs)
    changed_runs["first_vertical"] = changed_runs["first_vertical"].model_copy(
        update={"search_terminal_kind": "owner-novel-search-terminal"}
    )
    changed_depth = changed_depth.model_copy(update={"domain_runs": changed_runs})
    changed, _, _ = _service(
        packets=_component_packets(depth=changed_depth),
        summaries={run_id: _summary(run_id, RunTerminality.TERMINAL)},
    )
    changed_row = _row(changed.get(), "first_vertical")
    assert changed_row.search_terminal_kind.value == "owner-novel-search-terminal"
    assert changed_row.lifecycle_terminality == terminal_row.lifecycle_terminality
