from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.runtime.http.services.control.response_shapes import (
    _build_scientist_v2_shadow_comparison,
    _delta_usage,
    _sum_call_events,
)


def _typed_event(**changes: object) -> dict[str, object]:
    event: dict[str, object] = {
        "prompt_tokens": 3,
        "completion_tokens": 2,
        "latency_ms": 5,
        "cost_usd": 0.0,
        "cost_status": "known",
        "cost_origin": "reported",
        "usage_status": "known",
        "origin_cost_usd": 0.0,
        "estimated_cost_usd": 0.00001,
        "cost_delta_usd": -0.00001,
        "provider": "provider-a",
        "model": "model-a",
        "provider_call": True,
        "cache_hit": False,
        "event_identity": "event-a",
        "producer_event_id": "producer-event-a",
        "payload_digest": "sha256:payload-a",
        "settlement_status": "unmanaged",
    }
    event.update(changes)
    return event


def test_typed_reported_zero_and_estimate_keep_origin_and_event_identity() -> None:
    reported = _sum_call_events([_typed_event()])
    assert reported["cost_usd"] == 0.0
    assert reported["cost_status"] == "known"
    assert reported["cost_origin"] == "reported"
    assert reported["usage_status"] == "known"
    assert reported["prompt_tokens"] == 3.0
    assert reported["completion_tokens"] == 2.0
    assert reported["latency_ms"] == 5.0
    assert reported["cost_events"][0]["event_identity"] == "event-a"
    assert reported["cost_events"][0]["producer_event_id"] == "producer-event-a"
    assert reported["cost_events"][0]["payload_digest"] == "sha256:payload-a"
    assert reported["cost_events"][0]["settlement_status"] == "unmanaged"

    estimated_amount = 0.0000475
    estimated = _sum_call_events(
        [
            _typed_event(
                cost_usd=estimated_amount,
                cost_status="missing",
                cost_origin="estimated",
                estimated_cost_usd=estimated_amount,
                origin_cost_usd=None,
                cost_delta_usd=None,
            )
        ]
    )
    assert estimated["cost_usd"] == estimated_amount
    assert estimated["cost_status"] == "known"
    assert estimated["cost_origin"] == "estimated"
    assert estimated["cost_events"][0]["cost_status"] == "missing"
    assert estimated["cost_events"][0]["cost_origin"] == "estimated"


def test_reuse_cost_remains_zero_with_reuse_and_cache_identity() -> None:
    summary = _sum_call_events(
        [
            _typed_event(
                prompt_tokens=0,
                completion_tokens=0,
                cost_status="missing",
                cost_origin="reuse",
                cost_usd=0.0,
                cache_hit=True,
                provider_call=False,
                usage_origin="reuse",
                reuse_event_id="reused-event",
                origin_cost_usd=None,
                estimated_cost_usd=None,
                cost_delta_usd=None,
            )
        ]
    )
    assert summary["cost_usd"] == 0.0
    assert summary["cost_status"] == "known"
    assert summary["cost_origin"] == "reuse"
    assert summary["cost_events"][0]["usage_origin"] == "reuse"
    assert summary["cost_events"][0]["reuse_event_id"] == "reused-event"


def test_unknown_and_legacy_scalar_costs_do_not_become_zero_or_known() -> None:
    unknown = _sum_call_events(
        [
            _typed_event(
                cost_usd=None,
                cost_status="missing",
                cost_origin="unknown",
                origin_cost_usd=None,
                usage_status="missing",
                estimated_cost_usd=0.002,
                cost_delta_usd=None,
            )
        ]
    )
    assert unknown["cost_usd"] is None
    assert unknown["cost_status"] == "missing"
    assert unknown["cost_origin"] == "unknown"
    assert unknown["estimated_cost_usd"] is None
    assert unknown["usage_status"] == "missing"
    assert unknown["prompt_tokens"] == 0.0

    legacy = _sum_call_events([{"cost_usd": 0.0, "provider": "legacy-provider"}])
    assert legacy["cost_usd"] is None
    assert legacy["cost_status"] == "missing"
    assert legacy["cost_origin"] == "unknown"
    assert legacy["cost_events"][0]["source_classification"] == "legacy_untyped"
    assert legacy["cost_events"][0]["cost_usd"] is None


@pytest.mark.parametrize(
    "event",
    [
        _typed_event(cost_usd="0.01"),
        _typed_event(cost_status=[]),
        _typed_event(cost_origin=[]),
        _typed_event(cost_status="missing", cost_origin="unknown", cost_usd=0.0),
        _typed_event(
            cost_status="missing",
            cost_origin="estimated",
            cost_usd=0.01,
            estimated_cost_usd=0.01,
            usage_status="missing",
        ),
        _typed_event(
            cost_status="missing",
            cost_origin="estimated",
            cost_usd=0.01,
            estimated_cost_usd=0.01,
            origin_cost_usd=0.04,
        ),
        _typed_event(cost_status="known", cost_origin="estimated", cost_usd=0.01),
    ],
)
def test_malformed_or_contradictory_cost_evidence_is_invalid(
    event: dict[str, object],
) -> None:
    summary = _sum_call_events([event])
    assert summary["cost_usd"] is None
    assert summary["cost_status"] == "invalid"
    assert summary["cost_events"][0]["source_classification"] == "invalid"


def test_mixed_known_and_unknown_cost_is_not_a_partial_total() -> None:
    summary = _sum_call_events(
        [
            _typed_event(cost_usd=0.02, origin_cost_usd=0.02, estimated_cost_usd=0.00001),
            _typed_event(
                event_identity="event-unknown",
                cost_usd=None,
                cost_status="missing",
                cost_origin="unknown",
                origin_cost_usd=None,
                estimated_cost_usd=None,
                cost_delta_usd=None,
            ),
        ]
    )
    assert summary["cost_usd"] is None
    assert summary["cost_status"] == "missing"
    assert summary["cost_origin"] == "mixed"
    assert len(summary["cost_events"]) == 2


def test_empty_call_set_is_unknown_until_pipeline_declares_no_call() -> None:
    summary = _sum_call_events([])
    assert summary["cost_usd"] is None
    assert summary["cost_status"] == "missing"
    assert summary["cost_origin"] == "unknown"
    assert summary["usage_status"] == "missing"
    assert summary["prompt_tokens"] == 0.0
    assert summary["completion_tokens"] == 0.0
    assert summary["latency_ms"] == 0.0


def test_explicit_zero_usage_is_distinct_from_missing_usage_axes() -> None:
    explicit_zero = _sum_call_events(
        [_typed_event(prompt_tokens=0, completion_tokens=0, latency_ms=0.0)]
    )
    missing_zero = _sum_call_events(
        [
            _typed_event(
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=0.0,
                usage_status="missing",
            )
        ]
    )
    assert explicit_zero["usage_status"] == "known"
    assert explicit_zero["prompt_tokens"] == explicit_zero["completion_tokens"] == 0.0
    assert explicit_zero["latency_ms"] == 0.0
    assert missing_zero["usage_status"] == "missing"
    assert missing_zero["prompt_tokens"] == missing_zero["completion_tokens"] == 0.0
    assert missing_zero["latency_ms"] == 0.0


@pytest.mark.parametrize(
    "changes",
    [
        {"prompt_tokens": True},
        {"completion_tokens": 2.5},
        {"latency_ms": float("inf")},
    ],
)
def test_malformed_call_usage_is_marked_invalid(changes: dict[str, object]) -> None:
    summary = _sum_call_events([_typed_event(**changes)])
    assert summary["usage_status"] == "invalid"
    assert summary["cost_events"][0]["event_usage_status"] == "invalid"


def test_delta_uses_new_event_suffix_even_when_prefix_cost_is_unknown() -> None:
    unknown_prefix = _typed_event(
        cost_usd=None,
        cost_status="missing",
        cost_origin="unknown",
        origin_cost_usd=None,
        estimated_cost_usd=None,
        cost_delta_usd=None,
    )
    before = _sum_call_events([unknown_prefix])
    after = _sum_call_events([unknown_prefix, _typed_event(event_identity="event-new")])

    delta = _delta_usage(before, after)
    assert delta["prompt_tokens"] == 3
    assert delta["completion_tokens"] == 2
    assert delta["latency_ms"] == 5.0
    assert delta["usage_status"] == "known"
    assert delta["cost_usd"] == 0.0
    assert delta["cost_status"] == "known"
    assert delta["cost_origin"] == "reported"
    assert len(delta["cost_events"]) == 1
    assert delta["cost_events"][0]["event_identity"] == "event-new"


def test_delta_fails_closed_when_prior_event_prefix_changes() -> None:
    before = _sum_call_events([_typed_event()])
    after = _sum_call_events([_typed_event(cost_usd=0.02, origin_cost_usd=0.02)])
    delta = _delta_usage(before, after)
    assert delta["cost_usd"] is None
    assert delta["cost_status"] == "invalid"
    assert delta["usage_status"] == "invalid"
    assert delta["prompt_tokens"] is None
    assert delta["completion_tokens"] is None
    assert delta["latency_ms"] is None


@pytest.mark.parametrize("field", ["prompt_tokens", "completion_tokens", "latency_ms"])
def test_delta_does_not_assign_mutated_prefix_usage_to_current_step(field: str) -> None:
    original = _typed_event()
    before = _sum_call_events([original])
    changed = _typed_event(**{field: 99})
    after = _sum_call_events([changed, _typed_event(event_identity="event-new")])

    delta = _delta_usage(before, after)
    assert delta["usage_status"] == "invalid"
    assert delta["prompt_tokens"] is None
    assert delta["completion_tokens"] is None
    assert delta["latency_ms"] is None
    assert delta["cost_status"] == "invalid"
    assert delta["cost_usd"] is None


def test_delta_usage_with_missing_source_quantities_is_nullable() -> None:
    missing_usage = _typed_event(usage_status="missing")
    before = _sum_call_events([])
    after = _sum_call_events([missing_usage])
    delta = _delta_usage(before, after)
    assert delta["usage_status"] == "missing"
    assert delta["prompt_tokens"] is None
    assert delta["completion_tokens"] is None
    assert delta["latency_ms"] is None


def test_delta_with_valid_prefix_and_no_appended_event_is_missing_not_zero() -> None:
    before = _sum_call_events([_typed_event()])
    after = _sum_call_events([_typed_event()])

    delta = _delta_usage(before, after)
    assert delta["usage_status"] == "missing"
    assert delta["prompt_tokens"] is None
    assert delta["completion_tokens"] is None
    assert delta["latency_ms"] is None
    assert delta["cost_status"] == "missing"
    assert delta["cost_usd"] is None


def test_shadow_comparison_preserves_unknown_legacy_cost_state() -> None:
    result = _build_scientist_v2_shadow_comparison(
        legacy_status="completed",
        legacy_verdict="REVIEW",
        legacy_issue_count=1,
        legacy_cost_usd=None,
        legacy_cost_status="missing",
        legacy_cost_origin="unknown",
        legacy_prompt_tokens=3,
        legacy_completion_tokens=2,
        shadow_result=SimpleNamespace(metrics={}, result={"issue_count": 0}),
    )
    assert result is not None
    assert result["legacy_cost_usd"] is None
    assert result["legacy_cost_status"] == "missing"
    assert result["legacy_cost_origin"] == "unknown"
