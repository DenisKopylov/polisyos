"""Native reported responses, scoped recorded accounting, and actual search cutoff.

The existing HTTP fixture supplies provider-reported amounts, not invoice
authority. The controller consumes the same public budget owner as the native
workers; physical funnel amounts and per-key accounting remain distinct.
"""

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from runpy import run_path

import pytest

from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.objective import CompositeObjective, GDPGrowthObjective
from polisyos.scientist.methods.search.stopping import CostBudgetStopping
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerSpendReceipt,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

_workflow = run_path(str(Path(__file__).with_name("test_orchestrator.py")))


class _OneProposal:
    """Expose an unexpected proposal after the expected recorded-cost cutoff."""

    def __init__(self):
        self.calls = 0

    def generate(self, history, current_best, context):
        del history, current_best, context
        self.calls += 1
        assert self.calls == 1, "proposal generated after expected cost cutoff"
        return {"candidate_id": "candidate-1", "semantic": {"interventions": []}}


def _controller(funnel, owner, generator, *, budget_key, cutoff, split, stage_b):
    return SearchController(
        config=SearchConfig(
            stopping=CostBudgetStopping(max_cost_usd=cutoff),
            objective=CompositeObjective([GDPGrowthObjective()]),
            enable_stage_a=split,
            budget_middleware=owner,
            budget_key=budget_key,
        ),
        candidate_generator=generator,
        stage_a_evaluator=funnel.as_stage_a_callable(),
        stage_b_evaluator=stage_b,
    )


@pytest.mark.parametrize("split", [False, True])
@pytest.mark.parametrize("default_worker_scopes", [False, True])
def test_native_paid_funnel_receipts_drive_scoped_controller_cost_cutoff(
    tmp_path, monkeypatch, split, default_worker_scopes
):
    path, owner, funnel, calls, _, context = _workflow["configured_workflow"](
        tmp_path, monkeypatch, default_worker_scopes=default_worker_scopes
    )
    # SearchConfig explicitly chooses its run's accounting key. The default
    # translator records the same physical response against two separate keys.
    primary_key = "policy_translator" if default_worker_scopes else "run"
    scoped_cost = Decimal(1 if default_worker_scopes else 2)
    provider_aggregate = Decimal(3 if default_worker_scopes else 2)
    stage_b = funnel.as_stage_b_callable()
    evaluated = []

    def observe_native_stage_b(candidate, native_context):
        result = stage_b(candidate, native_context)
        evaluated.append((result, FileBudgetLedger(path).snapshot()))
        return result

    generator = _OneProposal()
    controller = _controller(
        funnel,
        owner,
        generator,
        budget_key=primary_key,
        cutoff=float(scoped_cost),
        split=split,
        stage_b=observe_native_stage_b,
    )
    # A contradictory legacy scalar cannot override the configured owner.
    result = controller.run({**context, "cumulative_cost_usd": 999.0})

    assert generator.calls == 1
    assert calls == ["adversary", "translator"]
    assert result.iterations_completed == result.stage_b_evaluations == 1
    assert result.stage_a_evaluations == int(split)
    assert "Cost budget" in result.stopping_reason and "exhausted" in result.stopping_reason
    native_result, immediate = evaluated[0]
    outcome = native_result["_funnel_outcome"]
    assert outcome.compute_actual_usd == outcome.provider_spend_usd == Decimal(2)
    assert outcome.compute_cost_source == "provider_reported_only"
    assert len(outcome.resource_event_ids) == 2
    assert [step.provider_spend_usd for step in outcome.trace] == [Decimal(1), Decimal(1)]

    reopened = FileBudgetLedger(path).snapshot()
    assert reopened == immediate
    assert reopened.state.spent[primary_key] == scoped_cost
    assert reopened.state.provider_spent == {"provider-a": provider_aggregate}
    assert len(reopened.spend_receipts) == int(provider_aggregate)
    assert all(amount == 0 for amount in reopened.state.reserved.values())
    for receipt in reopened.spend_receipts.values():
        assert receipt.amount == 1 and receipt.provider == "provider-a"
        assert receipt.payload_digest and owner.resolve_spend_safe(receipt.event_id) == receipt
        assert receipt.event_id.split(":budget:", 1)[0] in outcome.resource_event_ids

    telemetry = result.telemetry
    assert telemetry["budget_snapshot"] == {"cumulative_cost_usd": float(scoped_cost)}
    assert telemetry["budget_spent"] == float(scoped_cost)
    assert telemetry["budget_available"] is True
    assert telemetry["budget_snapshot_source"] == "configured_owner_recorded_state"
    assert telemetry["budget_ledger_id"] == owner.settlement_owner_identity[0]
    assert telemetry["budget_ledger_revision"] is None
    evidence = telemetry["budget_evidence"]
    assert evidence["recorded_by_provider"] == {"provider-a": float(provider_aggregate)}
    assert evidence["provider_cost_origin_available"] is False
    assert evidence["receipt_revision_available"] is False

    # Fresh public owner and fresh controller stop before another proposal or
    # evaluation. This is a fresh ledger consumer, not a service-resume claim.
    fresh_owner = BudgetMiddleware(
        owner.budget_state.model_copy(deep=True), ledger=FileBudgetLedger(path)
    )
    fresh_generator = _OneProposal()
    fresh = _controller(
        funnel,
        fresh_owner,
        fresh_generator,
        budget_key=primary_key,
        cutoff=float(scoped_cost),
        split=split,
        stage_b=observe_native_stage_b,
    ).run(context)
    assert fresh_generator.calls == fresh.iterations_completed == 0
    assert fresh.stage_a_evaluations == fresh.stage_b_evaluations == 0
    assert fresh.telemetry["budget_snapshot"] == telemetry["budget_snapshot"]
    assert calls == ["adversary", "translator"] and len(evaluated) == 1
    assert FileBudgetLedger(path).snapshot() == reopened


def test_trace_cost_one_without_settlement_cannot_establish_controller_cutoff(
    tmp_path, monkeypatch
):
    path, owner, funnel, calls, _, context = _workflow["configured_workflow"](
        tmp_path, monkeypatch, levels=(4,)
    )

    def remove_settlement(event_id, key, amount, *, payload_digest, provider=None):
        # A typed-looking ACK retains all markers but writes no real receipt.
        return BudgetLedgerSpendReceipt(
            event_id=event_id,
            key=key,
            amount=amount,
            payload_digest=payload_digest,
            provider=provider,
            revision=1,
            committed_at=datetime.now(UTC),
        )

    monkeypatch.setattr(owner, "settle_spend_safe", remove_settlement)
    stage = funnel._stages_by_level[4]
    native_evaluate = stage.evaluate
    # Keep the old trace-cost marker after the real paid response while the
    # settlement removal stays active. It is deliberately not a receipt.
    monkeypatch.setattr(
        stage,
        "evaluate",
        lambda candidate, ctx: replace(native_evaluate(candidate, ctx), compute_actual_usd=1.0),
    )
    stage_b = funnel.as_stage_b_callable()
    evaluated = []

    def observe_native_stage_b(candidate, native_context):
        result = stage_b(candidate, native_context)
        evaluated.append(result)
        return result

    generator = _OneProposal()
    controller = _controller(
        funnel,
        owner,
        generator,
        budget_key="run",
        cutoff=1.0,
        split=False,
        stage_b=observe_native_stage_b,
    )
    with pytest.raises(AssertionError, match="proposal generated after expected cost cutoff"):
        controller.run(context)

    assert calls == ["translator"] and generator.calls == 2
    assert len(evaluated) == 1
    outcome = evaluated[0]["_funnel_outcome"]
    assert outcome.trace[0].compute_actual_usd == 1.0
    assert outcome.final_result.is_promising is False
    assert outcome.final_action == "reject"
    reopened = FileBudgetLedger(path).snapshot()
    assert reopened.state.spent == {} and reopened.spend_receipts == {}
    assert controller._run_state.budget_snapshot == {"cumulative_cost_usd": 0.0}
    # The positive custody oracle fails with trace=1 and all new markers still
    # present. No paid receipt or cutoff is inferred from that trace scalar.
    with pytest.raises(AssertionError):
        assert reopened.state.spent.get("run", Decimal(0)) == 1
