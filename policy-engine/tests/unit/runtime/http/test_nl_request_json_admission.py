"""Typed request wire admission keeps raw candidate JSON rejection semantics."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from polisyos.core.contracts.control import NaturalLanguageRunRequest
from polisyos.runtime.http.errors import RuntimeHTTPError
from polisyos.runtime.http.resource_binding import _digest_payload
from polisyos.runtime.http.services.control.job_attempt_publication import (
    _validate_nl_request_json_values,
)


def _request(**values: object) -> NaturalLanguageRunRequest:
    return NaturalLanguageRunRequest.model_validate(
        {
            "request": "Validate selected intent, not raw native candidate values.",
            "llm_model": "simulated-qwen",
            "temporal_scope": {"valid_at": datetime(2026, 1, 1, tzinfo=UTC), "tx_at": None},
            **values,
        }
    )


def test_declared_typed_cursor_instants_pass_public_request_json_admission() -> None:
    request = _request(context={"as_of": "caller-role-only", "measurement": 0.25})
    _validate_nl_request_json_values(request)
    assert request.model_dump(mode="json")["temporal_scope"] == {
        "valid_at": "2026-01-01T00:00:00Z",
        "tx_at": None,
    }
    assert request.context == {"as_of": "caller-role-only", "measurement": 0.25}


@pytest.mark.parametrize(
    "field_name",
    [
        "context",
        "execution_plan",
        "stop_criteria",
        "governance_constraints",
        "expected_outputs",
    ],
)
@pytest.mark.parametrize(
    "raw_value",
    [
        datetime(2026, 1, 1, tzinfo=UTC),
        date(2026, 1, 1),
        Decimal("1.125"),
        b"candidate-bytes",
        {1, 2},
        object(),
    ],
    ids=["datetime", "date", "decimal", "bytes", "set", "unknown-object"],
)
def test_raw_candidate_native_values_are_not_laundered_by_typed_request_serialization(
    field_name: str, raw_value: object
) -> None:
    value = {"nested": {"value": raw_value}}
    selected = [value] if field_name in {"governance_constraints", "expected_outputs"} else value
    request = _request(**{field_name: selected})
    with pytest.raises(RuntimeHTTPError) as raised:
        _validate_nl_request_json_values(request)
    assert raised.value.status_code == 400
    assert raised.value.code == "authorization_binding_selector_invalid"


@pytest.mark.parametrize("raw_value", [float("nan"), float("inf"), float("-inf")])
def test_raw_candidate_nonfinite_numbers_keep_existing_refusal(raw_value: float) -> None:
    request = _request(context={"nested": [raw_value]})
    with pytest.raises(RuntimeHTTPError) as raised:
        _validate_nl_request_json_values(request)
    assert raised.value.code == "authorization_binding_selector_invalid"


@pytest.mark.parametrize("field_name", ["run_budget_usd", "per_model_budget_usd"])
@pytest.mark.parametrize("raw_value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_typed_scalar_cannot_hide_behind_a_wire_projection(
    field_name: str, raw_value: float
) -> None:
    # model_copy adversarially bypasses the scalar DTO validator. Admission must
    # retain the previous raw finite-number check before any queue or serializer.
    request = _request().model_copy(update={field_name: raw_value})
    with pytest.raises(RuntimeHTTPError) as raised:
        _validate_nl_request_json_values(request)
    assert raised.value.code == "authorization_binding_selector_invalid"


def test_whole_model_json_conversion_control_would_launder_raw_candidate_datetime() -> None:
    raw = datetime(2026, 1, 2, tzinfo=UTC)
    request = _request(context={"raw_candidate": raw})
    blind_projection = request.model_dump(mode="json")
    assert blind_projection["context"]["raw_candidate"] == "2026-01-02T00:00:00Z"
    _digest_payload(blind_projection)
    with pytest.raises(RuntimeHTTPError) as raised:
        _validate_nl_request_json_values(request)
    assert raised.value.code == "authorization_binding_selector_invalid"


def test_finite_raw_candidate_json_remains_accepted_with_and_without_cursor() -> None:
    candidate = {
        "_type": "caller-owned",
        "measurement": 0.25,
        "unknown": None,
        "nested": [True, "text", {"count": 2}],
    }
    selected = _request(context=candidate, expected_outputs=[{"value": candidate}])
    legacy = NaturalLanguageRunRequest(request="Legacy raw JSON.", context=candidate)
    for request in (selected, legacy):
        _validate_nl_request_json_values(request)
        assert request.context == candidate
