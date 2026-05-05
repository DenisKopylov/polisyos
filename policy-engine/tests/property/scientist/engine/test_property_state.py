"""Property-based tests for ExperimentState serialization."""

from __future__ import annotations

import copy
from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from polisyos.scientist.engine.state import ExperimentState

pytestmark = pytest.mark.property

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_safe_text = st.text(
    min_size=1,
    max_size=20,
    alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
)

_json_primitive = st.one_of(
    st.text(min_size=0, max_size=30),
    st.integers(min_value=-1_000_000, max_value=1_000_000),
    st.booleans(),
    st.none(),
)

_json_value = st.recursive(
    _json_primitive,
    lambda children: st.one_of(
        st.lists(children, max_size=3),
        st.dictionaries(st.text(min_size=1, max_size=10), children, max_size=3),
    ),
    max_leaves=10,
)


@st.composite
def experiment_states(draw):
    run_id = draw(_safe_text)
    params = draw(
        st.dictionaries(
            st.text(
                min_size=1,
                max_size=15,
                alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
            ),
            _json_value,
            max_size=3,
        )
    )
    budgets = draw(
        st.dictionaries(
            st.text(min_size=1, max_size=10),
            st.decimals(
                min_value=Decimal("0"),
                max_value=Decimal("1000000"),
                allow_nan=False,
                allow_infinity=False,
            ),
            max_size=2,
        )
    )
    return ExperimentState(run_id=run_id, params=params, budgets=budgets)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@given(state=experiment_states())
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_json_roundtrip(state: ExperimentState):
    """model_dump(mode='json') → model_validate() is identity."""
    dumped = state.model_dump(mode="json")
    restored = ExperimentState.model_validate(dumped)
    assert restored.run_id == state.run_id
    assert restored.params == state.params


@given(state=experiment_states())
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_deep_copy_equality(state: ExperimentState):
    """Deep copy preserves equality."""
    copied = copy.deepcopy(state)
    assert copied == state
    assert copied is not state


@given(state=experiment_states())
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_schema_version_pattern(state: ExperimentState):
    """schema_version always matches the expected pattern."""
    import re

    assert re.match(r"^\d+\.\d+$", state.schema_version)


def test_extra_fields_rejected():
    """ExperimentState with extra='forbid' rejects unknown fields."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ExperimentState(run_id="R_extra", unknown_field="value")
