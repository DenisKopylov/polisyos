from __future__ import annotations

from decimal import Decimal

from polisyos.runtime.http.services.control.response_shapes import (
    _project_call_event_cost,
)


def test_call_event_projection_preserves_high_precision_decimal_amount_as_text() -> None:
    amount = Decimal("9007199254740993.000000001")

    projected = _project_call_event_cost(
        {
            "event_id": "fixture-call",
            "cost_origin": "reported",
            "amount": amount,
            "settlement_status": "committed",
            "durability": "ledger",
        }
    )

    assert projected["amount"] == str(amount)
    assert isinstance(projected["amount"], str)
    assert Decimal(projected["amount"]) == amount
