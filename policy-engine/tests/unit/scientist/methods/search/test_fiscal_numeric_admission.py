"""Float64 fiscal intake preserves unavailable versus genuine numeric zero."""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any

import pytest

from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    CompositeObjective,
)
from polisyos.scientist.methods.search.stopping import (
    ImprovementPlateau,
    TargetAchieved,
)
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient

ALIASES = ("gov_balance", "government_balance", "budget_deficit", "deficit")


@pytest.mark.parametrize("alias", ALIASES)
@pytest.mark.parametrize("token", ["1e-1000", "-1e-1000"])
@pytest.mark.parametrize("representation", [str, Decimal], ids=["text", "decimal"])
def test_fiscal_nonzero_underflow_cannot_be_zero_or_fallback(
    alias, token, representation
):
    raw = representation(token)
    assert Decimal(raw) != 0 and float(raw) == 0.0
    # A valid fallback must not conceal malformed-present primary evidence.
    results = {alias: raw}
    if alias in {"gov_balance", "government_balance"}:
        results["budget_deficit"] = 7.0
    evaluated = BudgetDeficitObjective(threshold=0.0).evaluate(results)
    assert math.isnan(evaluated.raw_value)
    assert evaluated.is_satisfied is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (Decimal("0"), 0.0),
        (Decimal("-0.0"), 0.0),
        (Decimal("0E-1000"), 0.0),
        ("0", 0.0),
        (" -0.0 ", 0.0),
        (0, 0.0),
        (0.0, 0.0),
        (Decimal("-12.5"), 12.5),
        (" -12.5 ", 12.5),
        (Decimal("12.5"), 0.0),
        (Decimal("5e-324"), 0.0),
        ("5e-324", 0.0),
        (Decimal("-5e-324"), 5e-324),
        ("-5e-324", 5e-324),
    ],
    ids=[
        "decimal-zero",
        "negative-zero",
        "zero-exponent",
        "text-zero",
        "text-negative-zero",
        "int-zero",
        "float-zero",
        "paid-decimal",
        "legacy-text",
        "surplus",
        "positive-decimal-subnormal",
        "positive-text-subnormal",
        "decimal-subnormal",
        "text-subnormal",
    ],
)
def test_fiscal_supported_zero_sign_and_subnormal_values(raw, expected):
    evaluated = BudgetDeficitObjective().evaluate({"gov_balance": raw})
    assert evaluated.raw_value == expected
    assert evaluated.is_satisfied is True


@pytest.mark.parametrize(
    "raw",
    [
        True,
        "bad",
        Decimal("NaN"),
        Decimal("Infinity"),
        10**400,
        "1e1000",
        "1e-999999999999999999999",
    ],
)
def test_fiscal_invalid_scalar_refuses_without_fallback(raw):
    evaluated = BudgetDeficitObjective().evaluate(
        {"gov_balance": raw, "budget_deficit": 7}
    )
    assert math.isnan(evaluated.raw_value)
    assert evaluated.is_satisfied is False


@pytest.mark.parametrize(
    "aliases", [("gov_balance", "government_balance"), ("budget_deficit", "deficit")]
)
def test_fiscal_tiny_alias_and_zero_conflict_remains_unavailable(aliases):
    evaluated = BudgetDeficitObjective().evaluate(
        {aliases[0]: Decimal("1e-1000"), aliases[1]: 0}
    )
    assert math.isnan(evaluated.raw_value)
    assert evaluated.is_satisfied is False


class _HTTPResponse:
    status = 200
    headers = {"x-request-id": "fiscal-float64-intake"}

    def __init__(self, text: str):
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def text(self):
        return self._text


class _HTTPSession:
    def __init__(self, text: str):
        self._text = text
        self.calls = 0

    def post(self, *args: Any, **kwargs: Any):
        self.calls += 1
        return _HTTPResponse(self._text)

    async def close(self):
        pass


class _TextGateway(GatewayLLMClient):
    """Only physical HTTP transport is controlled; native B decoding is unchanged."""

    def __init__(self, text: str):
        super().__init__(
            base_url="https://fixture.invalid",
            api_key="",
            model="test-model",
            max_retries=0,
        )
        self.transport = _HTTPSession(text)

    async def _ensure_session(self, timeout_s):
        return self.transport


@pytest.mark.parametrize("alias", ALIASES)
@pytest.mark.parametrize("token", ["1e-1000", "-1e-1000"])
@pytest.mark.asyncio
async def test_actual_response_text_nonzero_decimal_is_unavailable_to_fiscal_consumer(
    alias, token
):
    gateway = _TextGateway('{"' + alias + '":' + token + "}")
    payload = await gateway._post_json(endpoint="/fixture", payload={}, timeout_s=1.0)
    assert gateway.transport.calls == 1
    assert isinstance(payload[alias], Decimal)
    assert payload[alias] == Decimal(token) and payload[alias] != 0
    objective = BudgetDeficitObjective(threshold=0.0)
    evaluated = objective.evaluate(payload)
    combined = CompositeObjective([objective]).evaluate(payload)
    history = [{"objective_value": 0.0}, {"objective_value": combined.normalized_value}]
    plateau = ImprovementPlateau(
        patience=1, objective_unit="declared_fixture_float64_units"
    ).check(history, {})
    assert plateau.should_stop is False
    assert plateau.reason == "objective_observation_missing_or_invalid"
    assert plateau.details["adequacy_status"] == "not_established"
    assert TargetAchieved(0.0).check(history, {}).should_stop is False
    assert math.isnan(evaluated.raw_value) and evaluated.is_satisfied is False
    assert math.isnan(combined.raw_value) and combined.is_satisfied is False


@pytest.mark.parametrize("alias", ALIASES)
@pytest.mark.parametrize(
    ("token", "balance_expected", "deficit_expected"),
    [
        ("0.0", 0.0, 0.0),
        ("-7.5", 7.5, 7.5),
        ("-5e-324", 5e-324, 5e-324),
        ("5e-324", 0.0, 5e-324),
    ],
    ids=[
        "genuine-zero",
        "ordinary-negative",
        "negative-subnormal",
        "positive-subnormal",
    ],
)
@pytest.mark.asyncio
async def test_actual_response_text_fiscal_consumer_preserves_supported_scalar(
    alias, token, balance_expected, deficit_expected
):
    gateway = _TextGateway('{"' + alias + '":' + token + "}")
    payload = await gateway._post_json(endpoint="/fixture", payload={}, timeout_s=1.0)
    assert gateway.transport.calls == 1
    assert isinstance(payload[alias], Decimal) and payload[alias] == Decimal(token)
    evaluated = BudgetDeficitObjective().evaluate(payload)
    expected = (
        balance_expected
        if alias in {"gov_balance", "government_balance"}
        else deficit_expected
    )
    assert evaluated.raw_value == expected and evaluated.is_satisfied is True
    if token == "0.0":
        history = [
            {"objective_value": 0.0},
            {"objective_value": evaluated.normalized_value},
        ]
        assert (
            ImprovementPlateau(
                patience=1, objective_unit="declared_fixture_float64_units"
            )
            .check(history, {})
            .should_stop
            is True
        )
        assert TargetAchieved(0.0).check(history, {}).should_stop is True
