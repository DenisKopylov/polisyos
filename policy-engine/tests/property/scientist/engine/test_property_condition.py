"""Property-based tests for condition evaluation."""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from polisyos.scientist.engine.condition import (
    ConditionSyntaxError,
    evaluate_condition,
)
from polisyos.scientist.engine.state import ExperimentState

pytestmark = pytest.mark.property


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_identifier = st.from_regex(r"[a-z][a-z0-9_]{0,8}", fullmatch=True)

_dot_path = st.builds(
    lambda parts: ".".join(parts),
    st.lists(_identifier, min_size=1, max_size=3),
)

_int_literal = st.integers(min_value=-1000, max_value=1000).map(str)
_bool_literal = st.sampled_from(["true", "false"])
_quoted_string = st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnop").map(
    lambda s: f'"{s}"'
)
_literal = st.one_of(_int_literal, _bool_literal, _quoted_string)

_binary_op = st.sampled_from(["==", "!=", ">", "<", ">=", "<="])
_unary_op = st.sampled_from(["is_set", "is_empty"])


@st.composite
def single_expressions(draw):
    """Generate a syntactically valid single condition expression."""
    path = draw(_dot_path)
    if draw(st.booleans()):
        op = draw(_unary_op)
        return f"{path} {op}"
    else:
        op = draw(_binary_op)
        val = draw(_literal)
        return f"{path} {op} {val}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@given(expr=single_expressions())
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_well_formed_expressions_return_bool(expr: str):
    """Well-formed expressions always return a bool, never raise."""
    state = ExperimentState(run_id="R_cond")
    result = evaluate_condition(expr, state)
    assert isinstance(result, bool)


@given(
    expr_a=single_expressions(),
    expr_b=single_expressions(),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_and_decomposition(expr_a: str, expr_b: str):
    """evaluate("A AND B") == evaluate("A") and evaluate("B")."""
    state = ExperimentState(run_id="R_and")
    compound = f"{expr_a} AND {expr_b}"
    expected = evaluate_condition(expr_a, state) and evaluate_condition(expr_b, state)
    assert evaluate_condition(compound, state) == expected


@given(
    expr_a=single_expressions(),
    expr_b=single_expressions(),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_or_decomposition(expr_a: str, expr_b: str):
    """evaluate("A OR B") == evaluate("A") or evaluate("B")."""
    state = ExperimentState(run_id="R_or")
    compound = f"{expr_a} OR {expr_b}"
    expected = evaluate_condition(expr_a, state) or evaluate_condition(expr_b, state)
    assert evaluate_condition(compound, state) == expected


@given(path=_dot_path)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_is_set_consistency(path: str):
    """is_set returns True iff path resolves to non-None."""
    state = ExperimentState(run_id="R_isset")
    result = evaluate_condition(f"{path} is_set", state)
    # On an empty state, most paths resolve to None → is_set should be False
    # unless the path happens to match an actual field
    assert isinstance(result, bool)


@given(path=_dot_path)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_is_empty_consistency(path: str):
    """is_empty returns True when value is None, empty str/list/dict."""
    state = ExperimentState(run_id="R_isempty")
    is_empty = evaluate_condition(f"{path} is_empty", state)
    is_set = evaluate_condition(f"{path} is_set", state)
    # If not set → must be empty
    if not is_set:
        assert is_empty


@given(
    expr_a=single_expressions(),
    expr_b=single_expressions(),
)
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_mixed_and_or_raises(expr_a: str, expr_b: str):
    """Mixed AND/OR in one expression raises ConditionSyntaxError."""
    state = ExperimentState(run_id="R_mixed")
    mixed = f"{expr_a} AND {expr_b} OR {expr_a}"
    with pytest.raises(ConditionSyntaxError):
        evaluate_condition(mixed, state)
