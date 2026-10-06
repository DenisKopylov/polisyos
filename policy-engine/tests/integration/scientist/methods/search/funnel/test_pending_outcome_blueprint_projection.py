"""Actual unknown settlement ACK remains pending evidence after JSON/CAS reopen."""

import json
from decimal import Decimal
from pathlib import Path
from runpy import run_path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    _serialize_funnel_outcome,
)
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.state import ExperimentState

_workflow = run_path(str(Path(__file__).with_name("test_orchestrator.py")))


@pytest.mark.parametrize("write_before_ack", [False, True])
def test_actual_native_pending_receipt_survives_blueprint_json_and_fresh_cas(
    tmp_path, monkeypatch, write_before_ack
):
    ledger_path, owner, funnel, calls, observed, context = _workflow["configured_workflow"](
        tmp_path, monkeypatch, levels=(3,)
    )
    settle = owner.settle_spend_safe

    def lose_ack(*args, **kwargs):
        if write_before_ack:
            settle(*args, **kwargs)
        raise OSError("actual settlement acknowledgment unavailable")

    monkeypatch.setattr(owner, "settle_spend_safe", lose_ack)
    outcome = funnel.advance(funnel.submit({"candidate_id": "candidate-1"}, context), policy="full")
    ledger = FileBudgetLedger(ledger_path).snapshot()
    assert calls == ["adversary"] and observed == []
    assert not outcome.final_result.is_promising
    assert ledger.state.spent == ({"run": Decimal(1)} if write_before_ack else {})
    assert outcome.provider_spend_usd == (Decimal(1) if write_before_ack else None)

    payload = _serialize_funnel_outcome(outcome)
    state = ExperimentState(run_id="run-1", params={"_funnel_outcome": payload})
    store_path = tmp_path / "cas"
    ref = FileSystemCAS(store_path).put_bytes(
        state.model_dump_json().encode(),
        PutOptions(kind="scientist.experiment_state", media_type="application/json"),
    )
    reopened = ExperimentState.model_validate_json(FileSystemCAS(store_path).get_bytes(ref))
    projected = reopened.params["_funnel_outcome"]
    assert projected["evaluation_status"] == outcome.evaluation_status
    assert projected["resource_event_ids"] == list(outcome.resource_event_ids)
    assert projected["provider_spend_usd"] == (
        str(outcome.provider_spend_usd) if write_before_ack else None
    )
    feedback = projected["stage_results"]["3"]["feedback"]
    assert feedback == json.loads(json.dumps(outcome.final_result.feedback))
    assert feedback["resource_settlement_status"] == (
        "committed_after_unknown_ack" if write_before_ack else "unknown"
    )
    if not write_before_ack:
        pending = feedback["resource_settlement_pending"][0]
        assert pending["event"]["amount"] == "1.0"
        assert pending["event"]["event_id"] and pending["payload_digest"]
        assert ledger.spend_receipts == {}
