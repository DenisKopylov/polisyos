"""Conflicting declared USD costs cannot be admitted as a cheaper receipt."""

import json
from decimal import Decimal
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger

_text = run_path(str(Path(__file__).with_name("test_gateway_response_text_cost.py")))
TextGateway = _text["TextGateway"]
build_owned_enforcer = _text["build_owned_enforcer"]
invoke = _text["invoke"]


def response_text(usage, payload=None):
    return json.dumps(
        {
            "choices": [{"message": {"content": "observed response"}}],
            "provider": "provider-a",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, **usage},
            **(payload or {}),
        }
    )


@pytest.mark.parametrize("source", ["usage", "payload"])
@pytest.mark.parametrize("alias", ["cost_usd", "cost"])
@pytest.mark.parametrize("first", [0, 1])
@pytest.mark.asyncio
async def test_actual_http_conflicting_finite_totals_refuse_with_normalized_marker(
    tmp_path, source, alias, first
):
    declared = {"total_cost_usd": first, alias: 1 - first}
    gateway = TextGateway(
        response_text(
            declared if source == "usage" else {}, declared if source == "payload" else None
        )
    )
    path, enforcer = build_owned_enforcer(tmp_path, gateway)
    with pytest.raises(ValueError, match="conflicting provider cost"):
        await invoke(enforcer)
    assert gateway.transport.calls == 1
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.spent == {} and snapshot.spend_receipts == {}


@pytest.mark.parametrize(
    ("usage", "payload"),
    [
        ({"cost_usd": 1}, {"cost_usd": 2}),
        ({"total_cost_usd": 0, "base_cost_usd": 1, "platform_fee_usd": 0}, {}),
        ({"total_cost_usd": 1, "base_cost_usd": 0.2, "platform_fee_usd": 0.3}, {}),
    ],
)
@pytest.mark.asyncio
async def test_actual_http_components_and_root_usage_share_one_declared_usd_total(
    tmp_path, usage, payload
):
    gateway = TextGateway(response_text(usage, payload))
    path, enforcer = build_owned_enforcer(tmp_path, gateway)
    with pytest.raises(ValueError, match="conflicting provider cost"):
        await invoke(enforcer)
    assert FileBudgetLedger(path).snapshot().spend_receipts == {}


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        ({"total_cost_usd": 0, "cost_usd": 0, "cost": 0}, Decimal(0)),
        (
            {"total_cost_usd": 0.3, "cost_usd": 0.3, "base_cost_usd": 0.1, "platform_fee_usd": 0.2},
            Decimal("0.3"),
        ),
    ],
)
@pytest.mark.asyncio
async def test_actual_http_consistent_zero_and_decimal_components_reopen_exactly(
    tmp_path, usage, expected
):
    gateway = TextGateway(response_text(usage))
    path, enforcer = build_owned_enforcer(tmp_path, gateway)
    await invoke(enforcer)
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.spent["run"] == expected
    assert next(iter(snapshot.spend_receipts.values())).amount == expected


@pytest.mark.asyncio
async def test_sdk_declared_magicmock_cost_is_invalid_present_not_absent(tmp_path):
    class SDK:
        async def generate(self, **kwargs):
            return SimpleNamespace(
                content="observed response",
                model="test-model",
                provider="provider-a",
                request_id="request-1",
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, cost_usd=MagicMock()),
                raw=None,
            )

    path, enforcer = build_owned_enforcer(tmp_path, SDK())
    with pytest.raises(ValueError, match="provider cost must be numeric"):
        await invoke(enforcer)
    assert FileBudgetLedger(path).snapshot().spend_receipts == {}


@pytest.mark.parametrize("reported", [0, 1])
@pytest.mark.asyncio
async def test_actual_gateway_altered_normalized_cost_refuses_matching_original_marker(
    tmp_path, monkeypatch, reported
):
    gateway = TextGateway(response_text({"cost_usd": reported}))
    native = gateway.generate

    async def alter(**kwargs):
        response = await native(**kwargs)
        response.usage.cost_usd = reported + 1
        return response

    monkeypatch.setattr(gateway, "generate", alter)
    path, enforcer = build_owned_enforcer(tmp_path, gateway)
    with pytest.raises(ValueError, match="conflicting provider cost"):
        await invoke(enforcer)
    assert gateway.transport.calls == 1
    assert FileBudgetLedger(path).snapshot().spend_receipts == {}


@pytest.mark.asyncio
async def test_sdk_raw_and_envelope_conflict_is_not_resolved_by_first_present(tmp_path):
    class SDK:
        async def generate(self, **kwargs):
            return SimpleNamespace(
                content="observed response",
                model="test-model",
                provider="provider-a",
                request_id="request-1",
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, cost_usd=2),
                raw={"cost_usd": 1},
            )

    path, enforcer = build_owned_enforcer(tmp_path, SDK())
    with pytest.raises(ValueError, match="conflicting provider cost"):
        await invoke(enforcer)
    assert FileBudgetLedger(path).snapshot().spend_receipts == {}
