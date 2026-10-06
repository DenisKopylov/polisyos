"""Independent measured-resource caller controls, without billing attestation."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerMutationResult,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer


class ReportedProvider:
    """Local transport reports explicit physical-request IDs and amounts."""

    def __init__(self, receipts):
        self.receipts = iter(receipts)
        self.calls = 0

    def invoke(self, prompt, **kwargs):
        assert not any(key.startswith("_") for key in kwargs)
        self.calls += 1
        identity, amount = next(self.receipts)
        return {
            "content": "observed",
            "provider": "independent-provider-fixture",
            "request_id": identity,
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost_usd": amount},
        }


def _caller(path, receipts, *, metrics=None, audit=None):
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))})
    middleware = BudgetMiddleware(state, ledger=FileBudgetLedger(path))
    transport = ReportedProvider(receipts)
    return LLMBudgetEnforcer(
        client=transport,
        budget_state=state,
        budget_middleware=middleware,
        budget_keys=["run", "unlimited"],
        run_id="independent-run",
        model_name="test-model",
        metrics=metrics,
        audit_log=audit,
    ), transport


def _invoke(caller, candidate="candidate-1"):
    return caller.invoke(
        "paid call", _evaluation_id=candidate, _prompt_tokens_estimate=1, max_tokens=1
    )


def test_actual_full_and_reopened_split_events_match(tmp_path):
    full_path, split_path = tmp_path / "full.json", tmp_path / "split.json"
    full, _ = _caller(full_path, [("physical-1", 1.1), ("physical-2", 2.2)])
    _invoke(full, "candidate-1")
    _invoke(full, "candidate-2")
    first, _ = _caller(split_path, [("physical-1", 1.1)])
    _invoke(first, "candidate-1")
    resumed, _ = _caller(split_path, [("physical-2", 2.2)])
    _invoke(resumed, "candidate-2")
    left, right = FileBudgetLedger(full_path).snapshot(), FileBudgetLedger(split_path).snapshot()
    assert left.state == right.state
    assert left.resource_events == right.resource_events
    assert left.state.spent == {"run": Decimal("3.3"), "unlimited": Decimal("3.3")}
    assert left.state.provider_spent == {"independent-provider-fixture": Decimal("3.3")}
    assert left.state.remaining("run") == Decimal("1.7")
    assert left.state.reserved["run"] == 0
    assert all(row.status == "settled" for row in right.resource_reservations.values())
    assert len(left.resource_events) == len(right.resource_events) == 2


def test_real_duplicate_delivery_with_different_content_is_refused(tmp_path):
    path = tmp_path / "conflict.json"
    caller, transport = _caller(path, [("physical-1", 1), ("physical-1", 2)])
    _invoke(caller)
    with pytest.raises(ValueError, match="identity conflict"):
        _invoke(caller)
    state = FileBudgetLedger(path).snapshot()
    assert transport.calls == 2
    assert state.state.spent["run"] == Decimal("1")
    assert len(state.resource_events) == 1
    assert sorted(row.status for row in state.resource_reservations.values()) == [
        "reconciliation_required",
        "settled",
    ]


def test_paid_response_remains_charged_if_latency_metrics_fail(tmp_path):
    class FailedLatencyMetric:
        def record(self, *args, **kwargs):
            raise RuntimeError("latency metrics unavailable")

    path = tmp_path / "paid-metric-failure.json"
    caller, transport = _caller(
        path,
        [("physical-1", 1)],
        metrics=SimpleNamespace(
            llm_latency_ms=FailedLatencyMetric(),
            llm_cost_usd=None,
            llm_calls_total=None,
            llm_tokens_total=None,
            scientist_llm_budget_utilization=None,
            scientist_llm_cost_anomalies_total=None,
        ),
    )
    with pytest.raises(RuntimeError, match="latency metrics unavailable"):
        _invoke(caller)
    snapshot = FileBudgetLedger(path).snapshot()
    assert transport.calls == 1
    assert snapshot.state.spent["run"] == Decimal("1"), (
        "A known paid provider receipt must settle before observability can fail"
    )
    assert snapshot.state.reserved["run"] == 0


def test_negative_reported_measurement_is_refused_without_false_zero_event(tmp_path):
    path = tmp_path / "malformed-cost.json"
    caller, transport = _caller(path, [("physical-1", -1)])
    with pytest.raises(ValueError):
        _invoke(caller)
    snapshot = FileBudgetLedger(path).snapshot()
    assert transport.calls == 1
    assert not snapshot.resource_events
    assert snapshot.state.spent == {}
    assert next(iter(snapshot.resource_reservations.values())).status == "reconciliation_required"


def test_known_paid_receipt_is_not_erased_by_malformed_token_metadata(tmp_path, monkeypatch):
    path = tmp_path / "paid-token-metadata.json"
    caller, transport = _caller(path, [("physical-1", 1)])
    original_invoke = transport.invoke

    def deliver_report(prompt, **kwargs):
        response = original_invoke(prompt, **kwargs)
        response["usage"]["prompt_tokens"] = "not-a-token-count"
        return response

    monkeypatch.setattr(transport, "invoke", deliver_report)
    try:
        _invoke(caller)
    except ValueError:
        pass
    snapshot = FileBudgetLedger(path).snapshot()
    assert transport.calls == 1
    assert snapshot.state.spent.get("run") == Decimal("1"), (
        "Explicit valid amount/provider/request must not become absent because token metadata fails"
    )
    assert snapshot.state.reserved["run"] == 0


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), True, False, "malformed"])
@pytest.mark.parametrize("location", ["usage", "payload"])
def test_invalid_present_cost_with_valid_alternate_remains_unresolved(
    tmp_path, monkeypatch, bad, location
):
    path = tmp_path / "invalid-alternate.json"
    caller, transport = _caller(path, [("physical-1", 1)])
    original_invoke = transport.invoke

    def deliver_report(prompt, **kwargs):
        response = original_invoke(prompt, **kwargs)
        if location == "usage":
            response["usage"]["cost_usd"] = bad
            response["cost_usd"] = 1
        else:
            response["total_cost_usd"] = bad
        return response

    monkeypatch.setattr(transport, "invoke", deliver_report)
    with pytest.raises(ValueError, match="provider cost"):
        _invoke(caller)
    snapshot = FileBudgetLedger(path).snapshot()
    assert transport.calls == 1
    assert snapshot.state.spent == {}
    assert snapshot.resource_events == {}
    assert snapshot.state.reserved["run"] > 0
    assert next(iter(snapshot.resource_reservations.values())).status == "reconciliation_required"


def test_removed_settlement_cannot_be_hidden_by_trace_cost_one(tmp_path, monkeypatch):
    class Audit:
        def __init__(self):
            self.rows = []

        def append(self, **row):
            self.rows.append(row)

    audit = Audit()
    path = tmp_path / "removed-settlement.json"
    caller, _ = _caller(path, [("physical-1", 1)], audit=audit)

    def no_settlement(ledger, reservation_id, event):
        snapshot = ledger.snapshot()
        # Preserve the truthful transport cost and the displayed new-charge
        # proxy; deliberately remove the actual persisted accounting effect.
        return BudgetLedgerMutationResult(
            snapshot.state, snapshot.revision, applied_amount=Decimal("1")
        )

    monkeypatch.setattr(FileBudgetLedger, "settle_resource", no_settlement)
    response = _invoke(caller)
    assert response["usage"]["cost_usd"] == 1
    committed = [row for row in audit.rows if row["action"] == "BUDGET_COMMITTED"]
    assert committed[0]["metadata"]["reported_cost_usd"] == "1.0"
    assert committed[0]["metadata"]["new_charge_usd"] == "1"
    with pytest.raises(AssertionError):
        assert FileBudgetLedger(path).load().spent.get("run", Decimal(0)) == Decimal("1")
