"""The existing fiscal alias contract refuses unmeasured scalar representations."""

import math

import pytest

from polisyos.scientist.methods.search.objective import BudgetDeficitObjective


@pytest.mark.parametrize(
    "alias", ["gov_balance", "government_balance", "budget_deficit", "deficit"]
)
@pytest.mark.parametrize("unmeasured", [False, True, 10**400])
def test_fiscal_alias_boolean_and_unrepresentable_integer_are_unavailable(alias, unmeasured):
    outcome = BudgetDeficitObjective().evaluate({alias: unmeasured})
    assert math.isnan(outcome.raw_value)
    assert outcome.is_satisfied is False


def test_present_boolean_does_not_fall_back_to_a_different_alias():
    outcome = BudgetDeficitObjective().evaluate({"gov_balance": False, "budget_deficit": 99})
    assert math.isnan(outcome.raw_value)
    assert outcome.is_satisfied is False


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ({"gov_balance": 0, "budget_deficit": 99}, 0.0),
        ({"gov_balance": None, "budget_deficit": 99}, 99.0),
        ({"gov_balance": -10}, 10.0),
        ({"gov_balance": "-10"}, 10.0),
    ],
)
def test_existing_zero_null_sign_and_legacy_numeric_text_are_preserved(results, expected):
    outcome = BudgetDeficitObjective().evaluate(results)
    assert outcome.raw_value == expected
    assert outcome.is_satisfied is True
