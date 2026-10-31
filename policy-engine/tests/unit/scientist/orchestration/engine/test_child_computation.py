"""Lossless state copying and complete parent-input identity."""

from decimal import Decimal

from polisyos.scientist.orchestration.engine.child_computation import (
    _state_copy,
    _state_from_snapshot,
    _state_snapshot,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState


def test_child_copy_preserves_decimal_and_literal_string_values() -> None:
    """Distinct supported scalar types survive copying through the real codec."""
    state = ExperimentState(
        run_id="parent",
        params={"number": Decimal("1.25"), "text": "1.25", "nested": {"n": Decimal("2")}},
        budgets={"run_max_usd": Decimal("3.50")},
    )
    copied = _state_copy(state, run_id="child")
    assert copied.run_id == "child" and state.run_id == "parent"
    assert type(copied.params["number"]) is Decimal
    assert copied.params["number"] == Decimal("1.25")
    assert type(copied.params["text"]) is str
    assert copied.params["nested"] == {"n": Decimal("2")}
    assert copied.budgets == state.budgets
    assert _state_from_snapshot(_state_snapshot(state)).params == state.params


def test_parent_state_identity_distinguishes_decimal_from_same_text() -> None:
    """The identical ordinary JSON image cannot replace the actual typed input."""
    number = ExperimentState(run_id="parent", params={"value": Decimal("1")})
    text = ExperimentState(run_id="parent", params={"value": "1"})
    assert number.model_dump(mode="json") == text.model_dump(mode="json")
    assert _state_snapshot(number) != _state_snapshot(text)
