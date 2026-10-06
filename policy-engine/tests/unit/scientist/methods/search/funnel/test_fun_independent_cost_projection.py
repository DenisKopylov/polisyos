"""Independent measured-cost projection witness through the actual native caller."""

from __future__ import annotations

import json
import runpy
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from polisyos.scientist.methods.search.funnel.types import CheapSignalVector
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger


def test_native_paid_reject_routing_preserves_measured_accounting(tmp_path, monkeypatch):
    fixture = runpy.run_path(
        str(Path("tests/integration/scientist/methods/search/funnel/test_orchestrator.py"))
    )
    path, _, funnel, calls, _, context = fixture["configured_workflow"](
        tmp_path, monkeypatch, levels=(3,)
    )
    native = funnel.stages[0]
    actual_evaluate = native.evaluate

    def actual_stage_with_explicit_reject_signal(candidate, stage_context):
        # Preserve the actual worker, provider response, estimate and measured
        # charge. Supply only the public typed routing vector as the test input.
        actual = actual_evaluate(candidate, stage_context)
        return replace(actual, cheap_signal=CheapSignalVector(structural_validity=0.0))

    monkeypatch.setattr(native, "evaluate", actual_stage_with_explicit_reject_signal)
    outcome = funnel.advance(funnel.submit({"candidate_id": "candidate-1"}, context), policy="full")
    ledger = FileBudgetLedger(path).snapshot()
    stage = outcome.stage_results[3]
    print(
        json.dumps(
            {
                "calls": calls,
                "final_action": outcome.final_action,
                "spent": str(ledger.state.spent["run"]),
                "ledger_event_ids": sorted(ledger.resource_events),
                "trace_cost_source": outcome.trace[0].compute_cost_source,
                "trace_provider_spend": str(outcome.trace[0].provider_spend_usd),
                "stage_cost_source": stage.compute_cost_source,
                "stage_provider_spend": str(stage.provider_spend_usd),
                "stage_event_ids": stage.resource_event_ids,
                "outcome_cost_source": outcome.compute_cost_source,
                "outcome_provider_spend": str(outcome.provider_spend_usd),
                "outcome_event_ids": outcome.resource_event_ids,
            },
            sort_keys=True,
        )
    )
    assert calls == ["adversary"]
    assert outcome.final_action == "reject"
    assert ledger.state.spent["run"] == Decimal("1")
    assert outcome.trace[0].provider_spend_usd == Decimal("1")
    assert stage.compute_cost_source == "provider_reported_only"
    assert stage.provider_spend_usd == Decimal("1")
    assert set(stage.resource_event_ids) == set(ledger.resource_events)
    assert outcome.compute_cost_source == "provider_reported_only"
    assert outcome.provider_spend_usd == Decimal("1")
    assert set(outcome.resource_event_ids) == set(ledger.resource_events)
