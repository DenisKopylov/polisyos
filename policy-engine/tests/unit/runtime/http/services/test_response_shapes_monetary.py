"""Monetary provenance must survive runtime response aggregation."""

from __future__ import annotations

from polisyos.runtime.http.services.control.response_shapes import (
    _project_call_event_cost,
    _sum_call_events,
)


def test_unknown_cost_stays_distinct_from_reported_zero_in_aggregate() -> None:
    summary = _sum_call_events(
        [
            {"cost_status": "reported", "cost_usd": 0.0},
            {"cost_status": "unknown", "cost_usd": None},
        ]
    )

    assert summary["cost_usd"] is None
    assert summary["cost_status_counts"] == {"reported": 1, "unknown": 1}


def test_nonterminal_settlement_never_contributes_to_known_cost_total() -> None:
    for settlement_status in ("pending", "unknown"):
        summary = _sum_call_events(
            [
                {
                    "cost_origin": "reported",
                    "amount": "0.25",
                    "settlement_status": settlement_status,
                }
            ]
        )
        assert summary["cost_usd"] is None
        assert summary["cost_origin_counts"] == {"reported": 1}
        assert summary["settlement_status_counts"] == {settlement_status: 1}


def test_call_event_projection_keeps_origin_settlement_and_unknown_amount() -> None:
    projected = _project_call_event_cost(
        {
            "event_id": "reuse-1",
            "origin_event_id": "provider-1",
            "cost_origin": "reuse",
            "amount": 0,
            "settlement_status": "committed",
            "durability": "ledger",
            "receipts": ["reuse-1"],
            "producer_payload_digest": "a" * 64,
        }
    )

    assert projected == {
        "event_id": "reuse-1",
        "origin_event_id": "provider-1",
        "cost_origin": "reuse",
        "amount": "0",
        "settlement_status": "committed",
        "durability": "ledger",
        "receipts": ["reuse-1"],
        "payload_digest": "a" * 64,
        "model": None,
        "provider": None,
    }
    unknown = _project_call_event_cost(
        {"event_id": "unknown-1", "cost_origin": "reported", "amount": "NaN"}
    )
    assert unknown["cost_origin"] == "unknown"
    assert unknown["amount"] is None


def test_untrusted_money_discriminators_fail_closed_without_hashing_raw_values() -> None:
    raw_values = (None, [], {}, 7, True, "malformed")
    for raw_value in raw_values:
        projected = _project_call_event_cost(
            {
                "event_id": "malformed-discriminator",
                "cost_origin": raw_value,
                "amount": "0.25",
                "settlement_status": raw_value,
                "durability": raw_value,
            }
        )
        assert projected["cost_origin"] == "unknown"
        assert projected["amount"] is None
        assert projected["settlement_status"] == "unknown"
        assert projected["durability"] == "none"

        summary = _sum_call_events(
            [
                {
                    "cost_origin": raw_value,
                    "amount": "0.25",
                    "settlement_status": raw_value,
                    "durability": raw_value,
                }
            ]
        )
        assert summary["cost_usd"] is None
        assert summary["cost_origin_counts"] == {"unknown": 1}
        assert summary["settlement_status_counts"] == {"unknown": 1}
        assert summary["settlement_durability_counts"] == {"none": 1}
