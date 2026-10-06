"""Native paid outcomes survive the real blueprint JSON/CAS projection.

This exercises the available configured translator/adversary producer and the
node's actual serializer. It does not claim the default policy backend creates
an LLM request or has an appointed physical-resource billing producer.
"""

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


@pytest.mark.parametrize("partial", [False, True])
def test_actual_paid_outcome_survives_blueprint_json_and_fresh_cas_reopen(
    tmp_path, monkeypatch, partial
):
    ledger_path, _, funnel, calls, _, context = _workflow["configured_workflow"](
        tmp_path, monkeypatch
    )
    ticket = funnel.submit({"candidate_id": "candidate-1"}, context)
    outcome = funnel.advance(ticket, policy="stage_a" if partial else "full")
    expected_spend = Decimal(1 if partial else 2)
    ledger = FileBudgetLedger(ledger_path).snapshot()
    assert ledger.state.spent["run"] == expected_spend
    assert calls == (["adversary"] if partial else ["adversary", "translator"])
    assert outcome.provider_spend_usd == expected_spend

    payload = _serialize_funnel_outcome(outcome)
    state = ExperimentState(run_id="run-1", params={"_funnel_outcome": payload})
    store_path = tmp_path / "cas"
    ref = FileSystemCAS(store_path).put_json(
        state.model_dump(mode="json"),
        PutOptions(kind="scientist.experiment_state", media_type="application/json"),
    )
    reopened = ExperimentState.model_validate_json(FileSystemCAS(store_path).get_bytes(ref))
    actual = reopened.params["_funnel_outcome"]
    assert actual["evaluation_status"] == ("partial" if partial else "evaluated")
    assert actual["compute_actual_usd"] == float(expected_spend)
    assert actual["compute_cost_source"] == "provider_reported_only"
    assert actual["provider_spend_usd"] == str(expected_spend)
    assert actual["resource_event_ids"] == list(outcome.resource_event_ids)
    assert actual["completed"] is (not partial)
    for level, result in outcome.stage_results.items():
        projected = actual["stage_results"][str(level)]
        assert projected["compute_actual_usd"] == result.compute_actual_usd
        assert projected["compute_cost_source"] == result.compute_cost_source
        assert projected["provider_spend_usd"] == str(result.provider_spend_usd)
        assert projected["resource_event_ids"] == list(result.resource_event_ids)
        assert projected["feedback"] == json.loads(json.dumps(result.feedback))
    for projected, step in zip(actual["trace"], outcome.trace, strict=True):
        assert projected["compute_actual_usd"] == step.compute_actual_usd
        assert projected["compute_cost_source"] == step.compute_cost_source
        assert projected["provider_spend_usd"] == str(step.provider_spend_usd)
        assert projected["resource_event_ids"] == list(step.resource_event_ids)
