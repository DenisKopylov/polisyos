"""Measured accounting survives the actual public compatibility projection."""

from __future__ import annotations

import json
import runpy
from decimal import Decimal
from pathlib import Path

from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger


def test_native_paid_public_evaluate_preserves_measured_fields(tmp_path, monkeypatch):
    fixture = runpy.run_path(
        str(Path("tests/integration/scientist/methods/search/funnel/test_orchestrator.py"))
    )
    path, _, funnel, calls, _, context = fixture["configured_workflow"](
        tmp_path, monkeypatch, levels=(3,)
    )
    candidate = {"candidate_id": "candidate-1"}
    result = funnel.evaluate(candidate, context)
    outcome = funnel.get_outcome(funnel.submit(candidate, context))
    snapshot = FileBudgetLedger(path).snapshot()
    print(
        json.dumps(
            {
                "calls": calls,
                "ledger_spent": str(snapshot.state.spent["run"]),
                "outcome_cost_source": outcome.compute_cost_source,
                "outcome_provider_spend": str(outcome.provider_spend_usd),
                "compatibility_cost_source": result.compute_cost_source,
                "compatibility_provider_spend": str(result.provider_spend_usd),
                "compatibility_event_ids": result.resource_event_ids,
            },
            sort_keys=True,
        )
    )
    assert calls == ["adversary"]
    assert snapshot.state.spent["run"] == Decimal("1")
    assert outcome.provider_spend_usd == Decimal("1")
    assert result.compute_cost_source == "provider_reported_only"
    assert result.provider_spend_usd == Decimal("1")
    assert set(result.resource_event_ids) == set(snapshot.resource_events)
