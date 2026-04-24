from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import numpy as np
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from polisyos.core.contracts.foundry import LoweredConstraint
from polisyos.foundry.constraints_engine import check_constraints
from polisyos.ir.kernel.merge_rules import MergeRuleRef
from polisyos.ir.kernel.slots import SlotKind, SlotRegistry, SlotScope, SlotSpec, SlotValueType

_HEALTH_CHECKS = [HealthCheck.function_scoped_fixture, HealthCheck.too_slow]


def _make_state(**kwargs: object) -> SimpleNamespace:
    root = SimpleNamespace()
    for dotted_path, value in kwargs.items():
        parts = dotted_path.split(".")
        current = root
        for part in parts[:-1]:
            if not hasattr(current, part):
                setattr(current, part, SimpleNamespace())
            current = getattr(current, part)
        setattr(current, parts[-1], value)
    return root


def _make_registry(*slot_defs: tuple[str, str]) -> SlotRegistry:
    return SlotRegistry(
        slots={
            slot_id: SlotSpec(
                slot_id=slot_id,
                scope=SlotScope.GLOBAL,
                value_type=SlotValueType.DECIMAL,
                kind=SlotKind.STOCK,
                merge_rule=MergeRuleRef(rule_id="replace"),
                state_path=state_path,
            )
            for slot_id, state_path in slot_defs
        }
    )


_VALUES_ONLY_REGISTRY = _make_registry(("gov.balance", "gov.balance"))
_WEIGHTED_REGISTRY = _make_registry(
    ("gov.balance", "gov.balance"),
    ("weights", "weights"),
)


@st.composite
def _weighted_vectors(draw) -> tuple[list[float], list[float], float]:
    size = draw(st.integers(min_value=1, max_value=8))
    values = draw(
        st.lists(
            st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
            min_size=size,
            max_size=size,
        )
    )
    weights = draw(
        st.lists(
            st.floats(0.01, 1000, allow_nan=False, allow_infinity=False),
            min_size=size,
            max_size=size,
        )
    )
    expected = draw(st.floats(-1000, 1000, allow_nan=False, allow_infinity=False))
    return values, weights, expected


@given(
    values=st.lists(
        st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=8,
    ),
    expected=st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, suppress_health_check=_HEALTH_CHECKS)
def test_mean_aggregation_matches_numpy_and_comparison_semantics(
    values: list[float],
    expected: float,
) -> None:
    constraint = LoweredConstraint(
        constraint_id="mean_constraint",
        severity="hard",
        slot_id="gov.balance",
        operator=">=",
        expected=Decimal(str(expected)),
        aggregation="mean",
    )
    state = _make_state(**{"gov.balance": np.array(values, dtype=np.float64)})

    report = check_constraints(
        constraints=[constraint],
        slot_registry=_VALUES_ONLY_REGISTRY,
        state=state,
    )

    actual_decimal = Decimal(report.violations[0].actual)
    actual = float(actual_decimal)
    expected_decimal = Decimal(str(expected))
    expected_mean = float(np.mean(np.asarray(values, dtype=np.float64)))
    assert np.isclose(actual, expected_mean)
    assert report.violations[0].violated is (actual_decimal < expected_decimal)


@given(data=_weighted_vectors())
@settings(max_examples=80, suppress_health_check=_HEALTH_CHECKS)
def test_weighted_mean_aggregation_matches_numpy_average(
    data: tuple[list[float], list[float], float],
) -> None:
    values, weights, expected = data
    constraint = LoweredConstraint(
        constraint_id="weighted_constraint",
        severity="hard",
        slot_id="gov.balance",
        operator="<=",
        expected=Decimal(str(expected)),
        aggregation="weighted_mean",
        weights_slot_id="weights",
    )
    state = _make_state(
        **{
            "gov.balance": np.array(values, dtype=np.float64),
            "weights": np.array(weights, dtype=np.float64),
        }
    )

    report = check_constraints(
        constraints=[constraint],
        slot_registry=_WEIGHTED_REGISTRY,
        state=state,
    )

    actual_decimal = Decimal(report.violations[0].actual)
    actual = float(actual_decimal)
    expected_decimal = Decimal(str(expected))
    weighted_mean = float(
        np.average(
            np.asarray(values, dtype=np.float64),
            weights=np.asarray(weights, dtype=np.float64),
        )
    )
    assert np.isclose(actual, weighted_mean)
    assert report.violations[0].violated is (actual_decimal > expected_decimal)
