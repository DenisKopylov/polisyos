"""Actual configured worker defaults share physical events across budget keys."""

from decimal import Decimal
from pathlib import Path
from runpy import run_path

import pytest

from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger

_workflow = run_path(str(Path(__file__).with_name("test_orchestrator.py")))


@pytest.mark.parametrize("split", [False, True])
def test_actual_default_worker_budget_scopes_preserve_one_physical_event_each(
    tmp_path, monkeypatch, split
):
    path, _, funnel, calls, _, context = _workflow["configured_workflow"](
        tmp_path, monkeypatch, default_worker_scopes=True
    )
    ticket = funnel.submit({"candidate_id": "candidate-1"}, context)
    if split:
        stage_a = funnel.advance(ticket, policy="stage_a")
        assert stage_a.provider_spend_usd == 1
    outcome = funnel.advance(ticket, policy="full")
    reopened = FileBudgetLedger(path).snapshot()
    assert calls == ["adversary", "translator"]
    assert len(reopened.spend_receipts) == 3
    assert reopened.state.spent == {
        "policy_adversary": Decimal(1),
        "policy_translator": Decimal(1),
        "policy_briefing": Decimal(1),
    }
    assert all(reopened.state.remaining(key) == 4 for key in reopened.state.limits)
    assert all(amount == 0 for amount in reopened.state.reserved.values())
    assert outcome.provider_spend_usd == 2 and outcome.compute_actual_usd == 2
    assert len(outcome.resource_event_ids) == 2
    physical_ids = {
        receipt.event_id.split(":budget:", 1)[0] for receipt in reopened.spend_receipts.values()
    }
    assert physical_ids == set(outcome.resource_event_ids)
    # Per-key local accounting totals are not a physical-provider bill. The
    # existing B aggregate counts the two translator accounting keys separately.
    assert reopened.state.provider_spent["provider-a"] == 3
