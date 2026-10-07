"""Ordinary native response → typed input origin → real funnel → JSON/CAS projection."""

import json
from dataclasses import replace
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
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient

_workflow = run_path(str(Path(__file__).with_name("test_orchestrator.py")))


def _native_inputs(tmp_path, monkeypatch, profiles, *, write_before_ack=False):
    mixed = len(profiles) == 2
    path, _, funnel, calls, observed, context = _workflow["configured_workflow"](
        tmp_path,
        monkeypatch,
        levels=(3, 4) if mixed else (3,),
        default_worker_scopes=mixed,
    )
    physical_texts = []
    native_session = GatewayLLMClient._ensure_session
    for key in ("POLISYOS_LLM_DEFAULT_INPUT_USD", "POLISYOS_LLM_DEFAULT_OUTPUT_USD"):
        monkeypatch.delenv(key, raising=False)

    class Session:
        def __init__(self, inner):
            self.inner = inner

        def post(self, *args, **kwargs):
            response = self.inner.post(*args, **kwargs)
            index = 0 if kwargs["json"]["model"] == "gpt-3.5-turbo" else 1
            profile = profiles[index]
            payload = json.loads(response.body)
            payload["usage"] = {
                "prompt_tokens": 0 if profile == "estimated_zero" else 50000,
                "completion_tokens": 0,
            }
            if profile == "reported_zero":
                payload["usage"]["cost_usd"] = 0.0
            elif profile == "reported_quarter":
                payload["usage"]["cost_usd"] = 0.25
            elif profile == "unknown":
                payload["usage"]["cost_usd"] = None
            response.body = json.dumps(payload)
            if profile == "unknown":
                response.body = response.body.replace('"cost_usd": null', '"cost_usd": 1e-1000')
            physical_texts.append(response.body)
            return response

        async def close(self):
            return await self.inner.close()

    async def transport(client, timeout_s):
        return Session(await native_session(client, timeout_s))

    monkeypatch.setattr(GatewayLLMClient, "_ensure_session", transport)
    settle = FileBudgetLedger.settle_spend

    def lose_ack(ledger, *args, **kwargs):
        if write_before_ack:
            settle(ledger, *args, **kwargs)
        raise OSError("actual settlement acknowledgement unavailable")

    monkeypatch.setattr(FileBudgetLedger, "settle_spend", lose_ack)
    if mixed:
        # Native workers already use distinct owner budget keys. Both independent
        # physical operations belong to this bounded stage's actual observer;
        # an unresolved first key must not invent admission for that same key.
        medium = funnel._stages_by_level[3].evaluate
        full = funnel._stages_by_level[4].evaluate

        def execute_both(candidate, stage_context):
            first = medium(candidate, stage_context)
            second = full(candidate, stage_context)
            return replace(
                first,
                failure_cards=[*first.failure_cards, *second.failure_cards],
            )

        monkeypatch.setattr(funnel._stages_by_level[3], "evaluate", execute_both)
    outcome = funnel.advance(funnel.submit({"candidate_id": "candidate-1"}, context), policy="full")
    assert calls == (["adversary", "translator"] if mixed else ["adversary"])
    assert len(physical_texts) == len(profiles) and observed == []
    assert outcome.final_action == "reject" and not outcome.final_result.is_promising
    ledger = FileBudgetLedger(path).snapshot()
    events = [record.event_payload for record in ledger.completion_obligations.values()]
    assert len(events) == len(profiles)
    return path, outcome, ledger, events


def _fresh_projection(tmp_path, outcome):
    state = ExperimentState(
        run_id="run-1", params={"_funnel_outcome": _serialize_funnel_outcome(outcome)}
    )
    path = tmp_path / "cas"
    ref = FileSystemCAS(path).put_bytes(
        state.model_dump_json().encode(),
        PutOptions(kind="scientist.experiment_state", media_type="application/json"),
    )
    projected = ExperimentState.model_validate_json(FileSystemCAS(path).get_bytes(ref)).params[
        "_funnel_outcome"
    ]
    assert projected["stage_results"]["3"]["feedback"] == json.loads(
        json.dumps(outcome.stage_results[3].feedback)
    )
    return projected["stage_results"]["3"]["feedback"]


@pytest.mark.parametrize(
    ("profile", "reported", "estimated", "reported_status", "estimated_status"),
    [
        ("estimated", None, Decimal("0.5"), "not_reported", "estimated"),
        ("reported_zero", Decimal(0), None, "reported", "not_estimated"),
        ("reported_quarter", Decimal("0.25"), None, "reported", "not_estimated"),
    ],
)
@pytest.mark.parametrize("write_before_ack", [False, True])
def test_native_failed_input_origin_survives_funnel_and_fresh_cas(
    tmp_path, monkeypatch, profile, reported, estimated, reported_status, estimated_status,
    write_before_ack,
):
    path, outcome, ledger, events = _native_inputs(
        tmp_path, monkeypatch, (profile,), write_before_ack=write_before_ack
    )
    expected = reported if reported is not None else estimated
    # Independent fixed decimal pricing oracle: 50000 observed prompt tokens at
    # the declared default input price 1e-5 USD; do not call producer's estimator.
    if profile == "estimated":
        assert Decimal(50000) * Decimal("0.00001") == expected
    assert Decimal(events[0]["amount"]) == expected
    assert events[0]["cost_origin"] == ("estimated" if estimated is not None else "reported")
    feedback = _fresh_projection(tmp_path, outcome)
    if reported is None:
        assert feedback["resource_reported_input_usd"] is None
    else:
        assert Decimal(feedback["resource_reported_input_usd"]) == reported
    if estimated is None:
        assert feedback["resource_estimated_input_usd"] is None
    else:
        assert Decimal(feedback["resource_estimated_input_usd"]) == estimated
    assert feedback["resource_reported_input_status"] == reported_status
    assert feedback["resource_estimated_input_status"] == estimated_status
    assert feedback["resource_settlement_status"] == (
        "committed_after_unknown_ack" if write_before_ack else "unknown"
    )
    assert FileBudgetLedger(path).snapshot() == ledger
    assert ledger.state.spent.get("run", Decimal(0)) == (expected if write_before_ack else 0)
    assert len(ledger.spend_receipts) == int(write_before_ack)
    assert ledger.state.reserved["run"] > 0


def test_native_zero_estimate_is_not_a_provider_reported_zero(tmp_path, monkeypatch):
    _, outcome, ledger, events = _native_inputs(tmp_path, monkeypatch, ("estimated_zero",))
    assert events[0]["cost_origin"] == "estimated" and Decimal(events[0]["amount"]) == 0
    feedback = _fresh_projection(tmp_path, outcome)
    assert feedback["resource_reported_input_usd"] is None
    assert feedback["resource_reported_input_status"] == "not_reported"
    assert Decimal(feedback["resource_estimated_input_usd"]) == 0
    assert feedback["resource_estimated_input_status"] == "estimated"
    assert ledger.spend_receipts == {} and ledger.state.spent == {}


def test_two_native_input_origins_keep_independent_subset_amounts(tmp_path, monkeypatch):
    _, outcome, ledger, events = _native_inputs(
        tmp_path, monkeypatch, ("estimated", "reported_quarter")
    )
    assert sorted((event["cost_origin"], Decimal(event["amount"])) for event in events) == [
        ("estimated", Decimal("0.5")), ("reported", Decimal("0.25"))
    ]
    feedback = _fresh_projection(tmp_path, outcome)
    assert Decimal(feedback["resource_reported_input_usd"]) == Decimal("0.25")
    assert feedback["resource_reported_input_status"] == "reported"
    assert Decimal(feedback["resource_estimated_input_usd"]) == Decimal("0.5")
    assert feedback["resource_estimated_input_status"] == "estimated"
    pending = feedback["resource_settlement_pending"]
    assert len(pending) == 2 and len({row["event"]["event_id"] for row in pending}) == 2
    assert ledger.spend_receipts == {} and ledger.state.spent == {}
    assert outcome.provider_spend_usd is None


@pytest.mark.parametrize("other", [None, "reported_quarter", "estimated"])
def test_native_unknown_amount_preserves_component_absence_and_partial_input(
    tmp_path, monkeypatch, other
):
    profiles = ("unknown",) if other is None else ("unknown", other)
    _, outcome, ledger, events = _native_inputs(tmp_path, monkeypatch, profiles)
    assert any(event["cost_origin"] == "unknown" and event["amount"] is None for event in events)
    feedback = _fresh_projection(tmp_path, outcome)
    reported = Decimal("0.25") if other == "reported_quarter" else None
    estimated = Decimal("0.5") if other == "estimated" else None
    for name, expected in (("reported", reported), ("estimated", estimated)):
        value = feedback[f"resource_{name}_input_usd"]
        if expected is None:
            assert value is None
        else:
            assert Decimal(value) == expected
        assert feedback[f"resource_{name}_input_status"] == (
            "unknown" if expected is None else "partial"
        )
    assert ledger.spend_receipts == {} and ledger.state.spent == {}
    assert outcome.provider_spend_usd is None
