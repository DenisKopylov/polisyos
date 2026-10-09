"""Provider usage parsing preserves unknown and malformed monetary values."""

from __future__ import annotations

from polisyos.core.llm.response import extract_llm_response_data


def test_missing_cost_and_usage_are_not_imputed_as_zero() -> None:
    parsed = extract_llm_response_data({"content": "answer", "usage": {}})

    assert parsed.usage_status == "missing"
    assert parsed.cost_status == "missing"
    assert parsed.cost_usd is None


def test_negative_reported_cost_is_invalid_not_a_reported_zero() -> None:
    parsed = extract_llm_response_data(
        {
            "content": "answer",
            "usage": {"prompt_tokens": 2, "completion_tokens": 1, "cost_usd": -0.02},
        }
    )

    assert parsed.usage_status == "known"
    assert parsed.cost_status == "invalid"
    assert parsed.cost_usd is None


def test_explicit_null_cost_is_invalid_and_does_not_fall_through_to_alias() -> None:
    parsed = extract_llm_response_data(
        {
            "content": "answer",
            "usage": {
                "prompt_tokens": 2,
                "completion_tokens": 1,
                "total_cost_usd": None,
                "cost_usd": 0.25,
            },
        }
    )

    assert parsed.usage_status == "known"
    assert parsed.cost_status == "invalid"
    assert parsed.cost_usd is None


def test_only_explicit_null_cost_is_not_estimate_eligible() -> None:
    parsed = extract_llm_response_data(
        {
            "content": "answer",
            "usage": {
                "prompt_tokens": 2,
                "completion_tokens": 1,
                "total_cost_usd": None,
            },
        }
    )

    assert parsed.usage_status == "known"
    assert parsed.cost_status == "invalid"
    assert parsed.cost_usd is None


def test_nested_usage_alias_precedes_top_level_and_component_costs_require_both_parts() -> None:
    nested_alias = extract_llm_response_data(
        {
            "content": "answer",
            "cost_usd": 0.5,
            "usage": {
                "prompt_tokens": 2,
                "completion_tokens": 1,
                "cost": 0.25,
                "base_cost_usd": 0.1,
                "platform_fee_usd": 0.1,
            },
        }
    )
    component_sum = extract_llm_response_data(
        {
            "content": "answer",
            "usage": {
                "prompt_tokens": 2,
                "completion_tokens": 1,
                "base_cost_usd": 0.2,
                "platform_fee_usd": 0.02,
            },
        }
    )
    incomplete_components = extract_llm_response_data(
        {
            "content": "answer",
            "usage": {
                "prompt_tokens": 2,
                "completion_tokens": 1,
                "base_cost_usd": 0.2,
            },
        }
    )

    assert nested_alias.cost_status == "known"
    assert nested_alias.cost_usd == 0.25
    assert component_sum.cost_status == "known"
    assert component_sum.cost_usd == 0.22
    assert incomplete_components.cost_status == "invalid"
    assert incomplete_components.cost_usd is None
