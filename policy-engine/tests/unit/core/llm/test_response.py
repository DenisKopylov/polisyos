"""Invalid-present provider measurements never become zero or absence."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from polisyos.core.llm.response import extract_llm_response_data


@pytest.mark.parametrize(
    "bad",
    [
        -1,
        float("nan"),
        float("inf"),
        -float("inf"),
        True,
        False,
        "not-a-price",
        {},
        [],
        Decimal("NaN"),
    ],
)
@pytest.mark.parametrize(
    "field", ["total_cost_usd", "cost_usd", "cost", "base_cost_usd", "platform_fee_usd"]
)
@pytest.mark.parametrize(
    "location", ["mapping_usage", "object_usage", "mapping_payload", "object_payload"]
)
def test_present_invalid_cost_refused_even_with_valid_alternate_field(bad, field, location):
    payload = {
        "usage": {},
        "cost_usd": 1.0,
        "provider": "provider-a",
        "request_id": "request-1",
    }
    if location == "mapping_usage":
        payload["usage"][field] = bad
    elif location == "object_usage":
        payload["usage"] = SimpleNamespace(**{field: bad})
        payload = SimpleNamespace(**payload)
    elif location == "mapping_payload":
        payload["usage"] = {"cost_usd": 1}
        payload[field] = bad
    else:
        payload["usage"] = SimpleNamespace(cost_usd=1)
        payload[field] = bad
        payload = SimpleNamespace(**payload)
    with pytest.raises(ValueError, match="provider cost"):
        extract_llm_response_data(payload)


def test_invalid_cost_is_not_swallowed_by_other_metadata_parse_failure():
    payload = {"usage": {"prompt_tokens": "broken", "cost_usd": -1}, "cost_usd": 1}
    with pytest.raises(ValueError, match="provider cost"):
        extract_llm_response_data(payload)


@pytest.mark.parametrize("cost", [0, Decimal("0"), "0", 1.25])
def test_finite_zero_and_positive_costs_remain_provider_measurements(cost):
    result = extract_llm_response_data({"usage": {"cost_usd": cost}})
    assert result.cost_usd == float(cost)


def test_absent_cost_remains_absent_for_legacy_tariff_consumer():
    assert extract_llm_response_data({"usage": {"prompt_tokens": 1}}).cost_usd is None


@pytest.mark.parametrize("form", ["mapping", "sdk"])
def test_admitted_paid_receipt_survives_malformed_ancillary_token_metadata(form):
    usage = {"prompt_tokens": "not-a-token-count", "cost_usd": 1}
    payload = {"usage": usage, "provider": "provider-a", "request_id": "request-1"}
    if form == "sdk":
        payload["usage"] = SimpleNamespace(**usage)
        payload = SimpleNamespace(**payload)
    receipt = extract_llm_response_data(payload)
    assert receipt.cost_usd == 1
    assert receipt.provider == "provider-a" and receipt.request_id == "request-1"
    assert receipt.prompt_tokens == receipt.completion_tokens == 0
