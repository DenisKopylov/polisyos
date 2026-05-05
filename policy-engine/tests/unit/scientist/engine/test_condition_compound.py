"""Tests for compound conditions (AND/OR) and aggregate operators (WS5.5)."""

from __future__ import annotations

import pytest
from polisyos.scientist.engine.condition import (
    ConditionSyntaxError,
    evaluate_condition,
)
from polisyos.scientist.engine.state import ExperimentState


def _state(**params: object) -> ExperimentState:
    return ExperimentState(run_id="test-run", params=params)


# ── Compound AND ─────────────────────────────────────────────────────


class TestCompoundAND:
    def test_all_true(self) -> None:
        s = _state(x=5, y=10)
        assert evaluate_condition("params.x > 3 AND params.y > 5", s) is True

    def test_one_false(self) -> None:
        s = _state(x=5, y=2)
        assert evaluate_condition("params.x > 3 AND params.y > 5", s) is False

    def test_all_false(self) -> None:
        s = _state(x=1, y=2)
        assert evaluate_condition("params.x > 3 AND params.y > 5", s) is False

    def test_three_clauses(self) -> None:
        s = _state(a=True, b=True, c=True)
        result = evaluate_condition(
            "params.a == true AND params.b == true AND params.c == true",
            s,
        )
        assert result is True

    def test_three_clauses_one_false(self) -> None:
        s = _state(a=True, b=False, c=True)
        result = evaluate_condition(
            "params.a == true AND params.b == true AND params.c == true",
            s,
        )
        assert result is False

    def test_and_with_unary(self) -> None:
        s = _state(x="hello", y=42)
        assert evaluate_condition("params.x is_set AND params.y > 10", s) is True

    def test_and_missing_lhs(self) -> None:
        s = _state(y=42)
        assert evaluate_condition("params.x is_set AND params.y > 10", s) is False


# ── Compound OR ──────────────────────────────────────────────────────


class TestCompoundOR:
    def test_one_true(self) -> None:
        s = _state(x=5, y=2)
        assert evaluate_condition("params.x > 3 OR params.y > 5", s) is True

    def test_all_true(self) -> None:
        s = _state(x=5, y=10)
        assert evaluate_condition("params.x > 3 OR params.y > 5", s) is True

    def test_all_false(self) -> None:
        s = _state(x=1, y=2)
        assert evaluate_condition("params.x > 3 OR params.y > 5", s) is False

    def test_three_clauses(self) -> None:
        s = _state(a=False, b=False, c=True)
        result = evaluate_condition(
            "params.a == true OR params.b == true OR params.c == true",
            s,
        )
        assert result is True

    def test_or_with_unary(self) -> None:
        s = _state(y=42)
        assert evaluate_condition("params.x is_set OR params.y > 10", s) is True


# ── Mixed AND/OR ─────────────────────────────────────────────────────


class TestMixedANDOR:
    def test_mixed_raises(self) -> None:
        s = _state(x=1, y=2, z=3)
        with pytest.raises(ConditionSyntaxError, match="Mixed AND/OR"):
            evaluate_condition("params.x > 0 AND params.y > 0 OR params.z > 0", s)


# ── Aggregate operators ──────────────────────────────────────────────


class TestHasLengthOperator:
    def test_exact_length_list(self) -> None:
        s = _state(items=[1, 2, 3])
        assert evaluate_condition("params.items has_length 3", s) is True

    def test_exact_length_mismatch(self) -> None:
        s = _state(items=[1, 2])
        assert evaluate_condition("params.items has_length 3", s) is False

    def test_exact_length_string(self) -> None:
        s = _state(name="hello")
        assert evaluate_condition("params.name has_length 5", s) is True

    def test_exact_length_dict(self) -> None:
        s = _state(data={"a": 1, "b": 2})
        assert evaluate_condition("params.data has_length 2", s) is True

    def test_on_non_collection(self) -> None:
        s = _state(x=42)
        assert evaluate_condition("params.x has_length 2", s) is False

    def test_on_none(self) -> None:
        s = _state()
        assert evaluate_condition("params.missing has_length 0", s) is False


class TestHasMinLengthOperator:
    def test_min_length_pass(self) -> None:
        s = _state(items=[1, 2, 3])
        assert evaluate_condition("params.items has_min_length 2", s) is True

    def test_min_length_exact(self) -> None:
        s = _state(items=[1, 2])
        assert evaluate_condition("params.items has_min_length 2", s) is True

    def test_min_length_fail(self) -> None:
        s = _state(items=[1])
        assert evaluate_condition("params.items has_min_length 2", s) is False

    def test_on_non_collection(self) -> None:
        s = _state(x=42)
        assert evaluate_condition("params.x has_min_length 1", s) is False


class TestHasMaxLengthOperator:
    def test_max_length_pass(self) -> None:
        s = _state(items=[1, 2])
        assert evaluate_condition("params.items has_max_length 3", s) is True

    def test_max_length_exact(self) -> None:
        s = _state(items=[1, 2, 3])
        assert evaluate_condition("params.items has_max_length 3", s) is True

    def test_max_length_fail(self) -> None:
        s = _state(items=[1, 2, 3, 4])
        assert evaluate_condition("params.items has_max_length 3", s) is False

    def test_on_non_collection(self) -> None:
        s = _state(x=42)
        assert evaluate_condition("params.x has_max_length 5", s) is False


# ── Aggregate + compound ─────────────────────────────────────────────


class TestAggregateCompound:
    def test_length_and_value(self) -> None:
        s = _state(items=[1, 2, 3], mode="batch")
        result = evaluate_condition(
            'params.items has_min_length 2 AND params.mode == "batch"',
            s,
        )
        assert result is True

    def test_length_or_value(self) -> None:
        s = _state(items=[], mode="batch")
        result = evaluate_condition(
            'params.items has_min_length 2 OR params.mode == "batch"',
            s,
        )
        assert result is True
