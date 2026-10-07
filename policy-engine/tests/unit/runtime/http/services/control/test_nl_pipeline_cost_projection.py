from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from polisyos.runtime.http.services.control.nl_pipeline import (
    _advance_run_budget,
    _aggregate_variant_costs,
    _budget_cost_amount,
    _build_run_performance_summary,
    _cost_projection_from_usage,
    _invalidate_cost_after_usage_failure,
    _no_provider_call_cost,
    _step_usage_projection,
)
from polisyos.runtime.http.services.control.response_shapes import _delta_usage


def _variant_cost(
    *,
    amount: float | None,
    status: str,
    origin: str,
    estimated: float | None = None,
    cost_basis: str = "call_event_summary",
) -> dict[str, Any]:
    return {
        "cost_usd": amount,
        "cost_status": status,
        "cost_origin": origin,
        "estimated_cost_usd": estimated,
        "cost_delta_usd": None,
        "cost_basis": cost_basis,
    }


def test_unknown_cost_stays_unknown_and_stops_the_next_budgeted_variant() -> None:
    reported = _variant_cost(amount=0.02, status="known", origin="reported")
    unknown = _variant_cost(amount=None, status="missing", origin="unknown")

    spent, stop = _advance_run_budget(spent=0.0, budget=0.10, variant=reported)
    assert spent == 0.02
    assert not stop

    # The unknown completion neither disappears as zero nor releases the known
    # remainder for a subsequent queued model variant.
    spent, stop = _advance_run_budget(spent=spent, budget=0.10, variant=unknown)
    assert spent == 0.02
    assert stop
    assert _budget_cost_amount(unknown) is None

    totals = _aggregate_variant_costs([reported, unknown])
    assert totals["cost_usd"] is None
    assert totals["cost_status"] == "missing"
    assert totals["cost_origin"] == "mixed"

    summary = _build_run_performance_summary(
        [
            {"model_variant_id": "reported", **reported},
            {"model_variant_id": "unknown", **unknown},
        ]
    )
    assert summary["llm"]["usage_status"] == "missing"
    assert summary["llm"]["cost_usd"] is None
    assert summary["variant_rows"][1]["cost_usd"] is None
    assert summary["variant_rows"][1]["cost_origin"] == "unknown"


def test_estimated_amount_remains_labeled_and_participates_in_budget_guard() -> None:
    estimated = _variant_cost(
        amount=0.03,
        status="known",
        origin="estimated",
        estimated=0.03,
    )
    reported_zero = _variant_cost(amount=0.0, status="known", origin="reported")

    assert _budget_cost_amount(estimated) == 0.03
    spent, stop = _advance_run_budget(spent=0.0, budget=0.10, variant=estimated)
    assert spent == 0.03
    assert not stop

    # A reported zero remains a real known amount and does not fabricate spend.
    spent, stop = _advance_run_budget(spent=0.0, budget=0.10, variant=reported_zero)
    assert spent == 0.0
    assert not stop

    totals = _aggregate_variant_costs([estimated, reported_zero])
    assert totals["cost_usd"] == 0.03
    assert totals["cost_origin"] == "mixed"
    assert totals["estimated_cost_usd"] == 0.03

    # A legacy scalar zero has no typed origin and is not interchangeable with
    # the producer-reported zero above.
    untyped_zero = _cost_projection_from_usage({"cost_usd": 0.0})
    assert untyped_zero["cost_usd"] is None
    assert untyped_zero["cost_status"] == "missing"
    assert untyped_zero["cost_origin"] == "unknown"


def test_tiny_positive_cost_is_not_rounded_to_reported_zero_before_budget_guard() -> None:
    tiny_positive = _variant_cost(amount=1e-10, status="known", origin="reported")
    projection = _cost_projection_from_usage(tiny_positive)

    assert projection["cost_usd"] == 1e-10
    spent, stop = _advance_run_budget(
        spent=0.0,
        budget=0.5e-10,
        variant=projection,
    )
    assert spent == 1e-10
    assert stop

    reported_zero = _variant_cost(amount=0.0, status="known", origin="reported")
    spent, stop = _advance_run_budget(
        spent=0.0,
        budget=0.5e-10,
        variant=reported_zero,
    )
    assert spent == 0.0
    assert not stop


def test_overflowing_aggregate_cost_is_invalid_and_stops_budgeted_queue() -> None:
    large = _variant_cost(amount=1e308, status="known", origin="reported")
    totals = _aggregate_variant_costs([large, large])

    assert totals["cost_usd"] is None
    assert totals["cost_status"] == "invalid"

    spent, stop = _advance_run_budget(
        spent=1e308,
        budget=1.5e308,
        variant=large,
    )
    assert spent == 1e308
    assert stop


def test_missing_step_usage_stays_nullable_without_aborting_the_step() -> None:
    projection = _step_usage_projection(
        {
            "prompt_tokens": None,
            "completion_tokens": None,
            "latency_ms": None,
            "usage_status": "missing",
        }
    )

    assert projection == {
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "latency_ms": None,
        "usage_status": "missing",
    }


def test_empty_step_event_suffix_cannot_masquerade_as_known_zero() -> None:
    empty_summary = {
        "prompt_tokens": 0.0,
        "completion_tokens": 0.0,
        "latency_ms": 0.0,
        "cost_events": (),
    }
    delta = _delta_usage(empty_summary, empty_summary)
    projection = _step_usage_projection(delta)

    assert delta["usage_status"] == "missing"
    assert projection["prompt_tokens"] is None
    assert projection["completion_tokens"] is None
    assert projection["total_tokens"] is None
    assert projection["usage_status"] == "missing"


def test_known_step_usage_keeps_existing_numeric_projection() -> None:
    projection = _step_usage_projection(
        {
            "prompt_tokens": 11,
            "completion_tokens": 4,
            "latency_ms": 7.0,
            "usage_status": "known",
        }
    )

    assert projection == {
        "prompt_tokens": 11,
        "completion_tokens": 4,
        "total_tokens": 15,
        "latency_ms": 7,
        "usage_status": "known",
    }


def test_invalid_event_prefix_is_rejected_before_step_numeric_conversion() -> None:
    before = {
        "prompt_tokens": 3.0,
        "completion_tokens": 4.0,
        "latency_ms": 10.0,
        "cost_events": ({"event_identity": "first"},),
    }
    after = {
        "prompt_tokens": 8.0,
        "completion_tokens": 9.0,
        "latency_ms": 20.0,
        "cost_events": ({"event_identity": "replaced"},),
    }
    delta = _delta_usage(before, after)

    assert delta["usage_status"] == "invalid"
    assert delta["prompt_tokens"] is None
    with pytest.raises(ValueError, match="llm_usage_delta_event_prefix_invalid"):
        _step_usage_projection(delta)


def test_usage_integrity_failure_invalidates_known_cost_and_stops_queue() -> None:
    known_cost = _variant_cost(amount=0.02, status="known", origin="reported")
    invalidated = _invalidate_cost_after_usage_failure(known_cost)

    assert invalidated["cost_usd"] is None
    assert invalidated["cost_status"] == "invalid"
    assert invalidated["usage_status"] == "invalid"
    assert invalidated["cost_basis"] == "invalid_usage_delta"
    spent, stop = _advance_run_budget(spent=0.0, budget=0.10, variant=invalidated)
    assert spent == 0.0
    assert stop


def test_explicit_pipeline_no_call_zero_remains_a_known_zero() -> None:
    no_call: Mapping[str, Any] = _no_provider_call_cost()

    assert no_call["cost_usd"] == 0.0
    assert no_call["cost_status"] == "known"
    assert no_call["cost_basis"] == "no_provider_call"
    assert _budget_cost_amount(no_call) == 0.0
    spent, stop = _advance_run_budget(spent=0.0, budget=0.10, variant=no_call)
    assert spent == 0.0
    assert not stop
