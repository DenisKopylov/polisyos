"""Bounded numeric L6 state-edit values preserve their source decimal meaning."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from polisyos.runtime.quality.candidate_simulation import CandidateScenarioDecimalSetToRuleV2
from polisyos.runtime.quality.intervention_substrate import (
    InterventionSubstrateError,
    candidate_scenario_decimal_set_to_value,
)


def _rule() -> CandidateScenarioDecimalSetToRuleV2:
    return CandidateScenarioDecimalSetToRuleV2(
        operator_kind="tax_relief_rate",
        parameter_id="rate",
        target_world_slot="global.tax_rate",
        unit_id="ratio",
        minimum=Decimal("0"),
        maximum=Decimal("1"),
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, Decimal("0")),
        (0.2, Decimal("0.2")),
        (Decimal("0.123456789012345678901"), Decimal("0.123456789012345678901")),
        ("0.3", Decimal("0.3")),
    ],
)
def test_declared_decimal_parameter_retains_exact_source_value(raw: Any, expected: Decimal) -> None:
    actual = candidate_scenario_decimal_set_to_value(
        _rule(),
        operator_kind="tax_relief_rate",
        parameters={"rate": raw},
        linked_write_slots=("global.tax_rate",),
    )
    assert actual == expected
    assert type(actual) is Decimal


@pytest.mark.parametrize(
    "raw",
    [
        True,
        float("nan"),
        float("inf"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("1e-999"),
        Decimal("1e999"),
        "rate * 0.5",
        -0.1,
        1.1,
    ],
)
def test_numeric_projection_refuses_invalid_unrepresentable_or_out_of_domain(raw: Any) -> None:
    with pytest.raises(InterventionSubstrateError):
        candidate_scenario_decimal_set_to_value(
            _rule(),
            operator_kind="tax_relief_rate",
            parameters={"rate": raw},
            linked_write_slots=("global.tax_rate",),
        )


@pytest.mark.parametrize(
    ("operator", "parameters", "writes"),
    [
        ("other", {"rate": 0.2}, ("global.tax_rate",)),
        ("tax_relief_rate", {"rate": 0.2, "extra": 1}, ("global.tax_rate",)),
        ("tax_relief_rate", {"rate": 0.2}, ("government.balance",)),
    ],
)
def test_numeric_rule_uses_exact_operator_parameter_and_linked_write_set(
    operator: str, parameters: dict[str, Any], writes: tuple[str, ...]
) -> None:
    with pytest.raises(InterventionSubstrateError):
        candidate_scenario_decimal_set_to_value(
            _rule(), operator_kind=operator, parameters=parameters, linked_write_slots=writes
        )


def test_decimal_rule_preserves_declared_supporting_parameter_context() -> None:
    """A real PolicySpec's semantic parameters cannot be silently discarded."""
    rule = _rule().model_copy(
        update={
            "parameter_context": {
                "target_world_slot": "global.tax_rate",
                "outcome_slots": ["government.balance"],
                "estimand": "average_treatment_effect",
            }
        }
    )
    values = {"rate": "0.2", **rule.parameter_context}
    assert candidate_scenario_decimal_set_to_value(
        rule,
        operator_kind="tax_relief_rate",
        parameters=values,
        linked_write_slots=("global.tax_rate",),
    ) == Decimal("0.2")
    with pytest.raises(InterventionSubstrateError, match="parameter_context_mismatch"):
        candidate_scenario_decimal_set_to_value(
            rule,
            operator_kind="tax_relief_rate",
            parameters={**values, "outcome_slots": ["agents.income"]},
            linked_write_slots=("global.tax_rate",),
        )
