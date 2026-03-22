"""Unit tests for the condition expression evaluator."""

from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.scientist.engine.condition import (
    ConditionSyntaxError,
    NodeCondition,
    evaluate_condition,
)
from polisyos.scientist.engine.state import ExperimentState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state(**params: object) -> ExperimentState:
    return ExperimentState(run_id="test-run", params=params)


def _state_with_profile(profile: str | None) -> ExperimentState:
    return ExperimentState(run_id="test-run", execution_profile=profile)


# ---------------------------------------------------------------------------
# NodeCondition model
# ---------------------------------------------------------------------------

class TestNodeConditionModel:
    def test_defaults(self) -> None:
        cond = NodeCondition(expr="params.x == true")
        assert cond.on_false == "skip"

    def test_on_false_fail(self) -> None:
        cond = NodeCondition(expr="params.x == true", on_false="fail")
        assert cond.on_false == "fail"

    def test_extra_forbidden(self) -> None:
        with pytest.raises(Exception):
            NodeCondition(expr="x == 1", extra_field="bad")  # type: ignore[call-arg]

    def test_empty_expr_rejected(self) -> None:
        with pytest.raises(Exception):
            NodeCondition(expr="")

    def test_serialization_roundtrip(self) -> None:
        cond = NodeCondition(expr="params.x == 42", on_false="fail")
        dumped = cond.model_dump()
        restored = NodeCondition.model_validate(dumped)
        assert restored.expr == cond.expr
        assert restored.on_false == "fail"


# ---------------------------------------------------------------------------
# Equality / inequality
# ---------------------------------------------------------------------------

class TestEqualityOperators:
    def test_eq_true_literal(self) -> None:
        assert evaluate_condition("params.enabled == true", _state(enabled=True)) is True

    def test_eq_false_literal(self) -> None:
        assert evaluate_condition("params.enabled == false", _state(enabled=False)) is True

    def test_eq_true_mismatch(self) -> None:
        assert evaluate_condition("params.enabled == true", _state(enabled=False)) is False

    def test_eq_string(self) -> None:
        assert evaluate_condition('params.mode == "fast"', _state(mode="fast")) is True

    def test_eq_string_mismatch(self) -> None:
        assert evaluate_condition('params.mode == "slow"', _state(mode="fast")) is False

    def test_eq_integer(self) -> None:
        assert evaluate_condition("params.count == 5", _state(count=5)) is True

    def test_eq_integer_mismatch(self) -> None:
        assert evaluate_condition("params.count == 5", _state(count=3)) is False

    def test_eq_null(self) -> None:
        assert evaluate_condition("params.x == null", _state(x=None)) is True

    def test_eq_null_mismatch(self) -> None:
        assert evaluate_condition("params.x == null", _state(x="hello")) is False

    def test_neq(self) -> None:
        assert evaluate_condition("params.x != 0", _state(x=5)) is True

    def test_neq_false(self) -> None:
        assert evaluate_condition("params.x != 0", _state(x=0)) is False


# ---------------------------------------------------------------------------
# Ordering operators
# ---------------------------------------------------------------------------

class TestOrderingOperators:
    def test_gt(self) -> None:
        assert evaluate_condition("params.x > 3", _state(x=5)) is True

    def test_gt_false(self) -> None:
        assert evaluate_condition("params.x > 3", _state(x=2)) is False

    def test_lt(self) -> None:
        assert evaluate_condition("params.x < 10", _state(x=5)) is True

    def test_gte(self) -> None:
        assert evaluate_condition("params.x >= 5", _state(x=5)) is True

    def test_lte(self) -> None:
        assert evaluate_condition("params.x <= 5", _state(x=5)) is True

    def test_ordering_with_none_lhs(self) -> None:
        assert evaluate_condition("params.missing > 0", _state()) is False

    def test_ordering_with_none_rhs(self) -> None:
        assert evaluate_condition("params.x > null", _state(x=5)) is False


# ---------------------------------------------------------------------------
# Unary operators
# ---------------------------------------------------------------------------

class TestUnaryOperators:
    def test_is_set_true(self) -> None:
        assert evaluate_condition("params.x is_set", _state(x="val")) is True

    def test_is_set_false(self) -> None:
        assert evaluate_condition("params.x is_set", _state(x=None)) is False

    def test_is_set_missing_path(self) -> None:
        assert evaluate_condition("params.missing is_set", _state()) is False

    def test_is_empty_none(self) -> None:
        assert evaluate_condition("params.x is_empty", _state(x=None)) is True

    def test_is_empty_missing(self) -> None:
        assert evaluate_condition("params.missing is_empty", _state()) is True

    def test_is_empty_empty_string(self) -> None:
        assert evaluate_condition("params.x is_empty", _state(x="")) is True

    def test_is_empty_nonempty_string(self) -> None:
        assert evaluate_condition("params.x is_empty", _state(x="hello")) is False

    def test_is_empty_empty_list(self) -> None:
        assert evaluate_condition("params.items is_empty", _state(items=[])) is True

    def test_is_empty_nonempty_list(self) -> None:
        assert evaluate_condition("params.items is_empty", _state(items=[1, 2])) is False

    def test_is_empty_integer(self) -> None:
        # Integers are not empty
        assert evaluate_condition("params.x is_empty", _state(x=42)) is False


# ---------------------------------------------------------------------------
# Dot-path resolution
# ---------------------------------------------------------------------------

class TestPathResolution:
    def test_top_level_field(self) -> None:
        s = _state_with_profile("research")
        assert evaluate_condition('execution_profile == "research"', s) is True

    def test_nested_params(self) -> None:
        s = ExperimentState(
            run_id="r",
            params={"transport_required": True},
        )
        assert evaluate_condition("params.transport_required == true", s) is True

    def test_deeply_missing_path(self) -> None:
        assert evaluate_condition("params.a.b.c is_set", _state()) is False

    def test_run_id(self) -> None:
        s = ExperimentState(run_id="my-run")
        assert evaluate_condition('run_id == "my-run"', s) is True

    def test_budgets(self) -> None:
        s = ExperimentState(run_id="r", budgets={"run_max_usd": Decimal("10.0")})
        assert evaluate_condition("budgets.run_max_usd > 5", s) is True

    def test_inputs_dict(self) -> None:
        s = ExperimentState(run_id="r", params={"keys": {"a": 1}})
        assert evaluate_condition("params.keys.a == 1", s) is True


# ---------------------------------------------------------------------------
# Edge cases and errors
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_expression_raises(self) -> None:
        with pytest.raises(ConditionSyntaxError, match="Empty"):
            evaluate_condition("", _state())

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ConditionSyntaxError, match="Empty"):
            evaluate_condition("   ", _state())

    def test_invalid_syntax_raises(self) -> None:
        with pytest.raises(ConditionSyntaxError, match="Cannot parse"):
            evaluate_condition("not a valid expression!", _state())

    def test_binary_op_missing_rhs_raises(self) -> None:
        with pytest.raises(ConditionSyntaxError, match="requires a right-hand value"):
            evaluate_condition("params.x ==", _state())

    def test_single_quoted_string(self) -> None:
        assert evaluate_condition("params.x == 'hello'", _state(x="hello")) is True

    def test_decimal_literal(self) -> None:
        assert evaluate_condition("params.x > 0.5", _state(x=Decimal("0.8"))) is True

    def test_negative_integer(self) -> None:
        assert evaluate_condition("params.x == -1", _state(x=-1)) is True

    def test_bare_string_literal(self) -> None:
        # Unquoted strings treated as string literals
        assert evaluate_condition("params.mode == fast", _state(mode="fast")) is True


# ---------------------------------------------------------------------------
# in / not_in operators
# ---------------------------------------------------------------------------

class TestMembershipOperators:
    def test_in_string(self) -> None:
        assert evaluate_condition('params.mode in "fast_mode"', _state(mode="fast")) is True

    def test_not_in_string(self) -> None:
        assert evaluate_condition('params.mode not_in "slow_mode"', _state(mode="fast")) is True
