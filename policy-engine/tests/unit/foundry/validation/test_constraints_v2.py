"""Phase 2 — Constraint Engine v2 tests.

Tests vector/tensor aggregation, element-wise reporting, compositional
constraints, backward compatibility, and safe expression evaluation.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import numpy as np
import pytest
from polisyos.core.contracts.foundry import CompositeConstraint, LoweredConstraint
from polisyos.foundry.validation.constraints_engine import (
    _safe_eval_expression,
    check_composite_constraints,
    check_constraints,
)
from polisyos.ir.kernel.merge_rules import MergeRuleRef
from polisyos.ir.kernel.slots import SlotKind, SlotRegistry, SlotScope, SlotSpec, SlotValueType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_slot_registry(*slot_defs: tuple[str, str]) -> SlotRegistry:
    """Create a minimal SlotRegistry from (slot_id, state_path) pairs."""
    slots = {}
    for slot_id, state_path in slot_defs:
        slots[slot_id] = SlotSpec(
            slot_id=slot_id,
            scope=SlotScope.GLOBAL,
            value_type=SlotValueType.DECIMAL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="replace"),
            state_path=state_path,
        )
    return SlotRegistry(slots=slots)


def _make_state(**kwargs: object) -> SimpleNamespace:
    """Build a nested state object from dot-separated keys."""
    root = SimpleNamespace()
    for dotted_path, value in kwargs.items():
        parts = dotted_path.split(".")
        obj = root
        for part in parts[:-1]:
            if not hasattr(obj, part):
                setattr(obj, part, SimpleNamespace())
            obj = getattr(obj, part)
        setattr(obj, parts[-1], value)
    return root


def _scalar_constraint(
    constraint_id: str = "c1",
    slot_id: str = "gov.balance",
    operator: str = ">=",
    expected: object = Decimal("0"),
    severity: str = "hard",
    aggregation: str = "scalar",
    quantile_param: float | None = None,
    penalty: Decimal | None = None,
    weights_slot_id: str | None = None,
) -> LoweredConstraint:
    return LoweredConstraint(
        constraint_id=constraint_id,
        severity=severity,
        slot_id=slot_id,
        operator=operator,
        expected=expected,
        aggregation=aggregation,
        quantile_param=quantile_param,
        penalty=penalty,
        weights_slot_id=weights_slot_id,
    )


SLOT_REG = _make_slot_registry(("gov.balance", "gov.balance"))


# ---------------------------------------------------------------------------
# 1. Scalar backward compatibility
# ---------------------------------------------------------------------------


def test_scalar_constraint_backward_compat():
    """Existing scalar behavior preserved when aggregation is default ('scalar')."""
    state = _make_state(**{"gov.balance": 10.0})
    c = _scalar_constraint(operator=">=", expected=Decimal("5"))
    report = check_constraints(constraints=[c], slot_registry=SLOT_REG, state=state)
    assert report.ok is True
    assert report.hard_fail is False
    assert len(report.violations) == 1
    assert report.violations[0].violated is False


def test_scalar_constraint_violation():
    state = _make_state(**{"gov.balance": 2.0})
    c = _scalar_constraint(operator=">=", expected=Decimal("5"))
    report = check_constraints(constraints=[c], slot_registry=SLOT_REG, state=state)
    assert report.hard_fail is True
    assert report.violations[0].violated is True


# ---------------------------------------------------------------------------
# 2. Vector aggregation — MEAN
# ---------------------------------------------------------------------------


def test_vector_constraint_mean():
    state = _make_state(**{"gov.balance": np.array([10.0, 20.0, 30.0])})
    c = _scalar_constraint(aggregation="mean", operator=">=", expected=Decimal("15"))
    report = check_constraints(constraints=[c], slot_registry=SLOT_REG, state=state)
    assert report.ok is True
    # mean([10, 20, 30]) = 20 >= 15
    assert report.violations[0].violated is False
    assert report.violations[0].actual == str(Decimal(str(float(np.mean([10.0, 20.0, 30.0])))))


def test_vector_constraint_mean_violated():
    state = _make_state(**{"gov.balance": np.array([1.0, 2.0, 3.0])})
    c = _scalar_constraint(aggregation="mean", operator=">=", expected=Decimal("10"))
    report = check_constraints(constraints=[c], slot_registry=SLOT_REG, state=state)
    assert report.hard_fail is True
    assert report.violations[0].violated is True


# ---------------------------------------------------------------------------
# 3. Vector aggregation — ALL (element-wise)
# ---------------------------------------------------------------------------


def test_vector_constraint_all():
    """ALL aggregation: all elements must satisfy the constraint."""
    state = _make_state(**{"gov.balance": np.array([10.0, 3.0, 8.0, 2.0])})
    c = _scalar_constraint(aggregation="all", operator=">=", expected=Decimal("5"))
    report = check_constraints(constraints=[c], slot_registry=SLOT_REG, state=state)

    assert report.violations[0].actual == "0"
    assert report.violations[0].violated is True

    ew_events = [e for e in report.violations[0].events if e.get("event") == "elementwise_check"]
    assert len(ew_events) == 1
    assert ew_events[0]["n_total"] == 4
    assert ew_events[0]["n_satisfying"] == 2
    assert ew_events[0]["n_violating"] == 2
    assert sorted(ew_events[0]["violating_indices"]) == [1, 3]


def test_vector_constraint_all_passes():
    """ALL aggregation when all elements satisfy the constraint."""
    state = _make_state(**{"gov.balance": np.array([10.0, 20.0, 30.0])})
    c = _scalar_constraint(aggregation="all", operator=">=", expected=Decimal("5"))
    report = check_constraints(constraints=[c], slot_registry=SLOT_REG, state=state)

    assert report.violations[0].actual == "1"
    assert report.violations[0].violated is False
    ew = [e for e in report.violations[0].events if e.get("event") == "elementwise_check"]
    assert len(ew) == 1
    assert ew[0]["n_satisfying"] == 3
    assert ew[0]["n_violating"] == 0
    assert ew[0]["n_total"] == 3


# ---------------------------------------------------------------------------
# 4. Vector aggregation — ANY
# ---------------------------------------------------------------------------


def test_vector_constraint_any():
    state = _make_state(**{"gov.balance": np.array([1.0, 2.0, 10.0])})
    c = _scalar_constraint(aggregation="any", operator="==", expected=Decimal("1"))
    report = check_constraints(constraints=[c], slot_registry=SLOT_REG, state=state)
    assert report.violations[0].actual == "1"
    assert report.violations[0].violated is False
    ew = [e for e in report.violations[0].events if e.get("event") == "elementwise_check"]
    assert ew[0]["n_satisfying"] == 1


def test_vector_constraint_any_none_satisfy():
    state = _make_state(**{"gov.balance": np.array([1.0, 2.0, 3.0])})
    c2 = _scalar_constraint(aggregation="any", operator=">=", expected=Decimal("10"))
    report = check_constraints(constraints=[c2], slot_registry=SLOT_REG, state=state)
    assert report.violations[0].actual == "0"
    assert report.violations[0].violated is True
    ew = [e for e in report.violations[0].events if e.get("event") == "elementwise_check"]
    assert ew[0]["n_satisfying"] == 0


# ---------------------------------------------------------------------------
# 5. Vector aggregation — QUANTILE
# ---------------------------------------------------------------------------


def test_vector_constraint_quantile():
    values = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    state = _make_state(**{"gov.balance": values})
    c = _scalar_constraint(
        aggregation="quantile",
        operator="<=",
        expected=Decimal("10"),
        quantile_param=0.9,
    )
    report = check_constraints(constraints=[c], slot_registry=SLOT_REG, state=state)
    q90 = float(np.quantile(values, 0.9))
    assert report.violations[0].violated is False
    assert report.violations[0].actual == str(Decimal(str(q90)))


# ---------------------------------------------------------------------------
# 6. Vector aggregation — COUNT_VIOLATING
# ---------------------------------------------------------------------------


def test_vector_constraint_count_violating():
    state = _make_state(**{"gov.balance": np.array([10.0, 3.0, 8.0, 2.0, 1.0])})
    c = _scalar_constraint(
        aggregation="count_violating",
        operator=">=",
        expected=Decimal("5"),
    )
    report = check_constraints(constraints=[c], slot_registry=SLOT_REG, state=state)
    # Elements violating >= 5: indices 1 (3.0), 3 (2.0), 4 (1.0) → 3 violating
    # actual = Decimal("3"), then _is_violated(">=", current=3, expected=5) → True (3 < 5)
    assert report.violations[0].actual == "3"


# ---------------------------------------------------------------------------
# 7. MIN, MAX, SUM
# ---------------------------------------------------------------------------


def test_vector_constraint_min():
    state = _make_state(**{"gov.balance": np.array([5.0, 10.0, 15.0])})
    c = _scalar_constraint(aggregation="min", operator=">=", expected=Decimal("3"))
    report = check_constraints(constraints=[c], slot_registry=SLOT_REG, state=state)
    assert report.violations[0].violated is False
    assert report.violations[0].actual == str(Decimal(str(5.0)))


def test_vector_constraint_max():
    state = _make_state(**{"gov.balance": np.array([5.0, 10.0, 15.0])})
    c = _scalar_constraint(aggregation="max", operator="<=", expected=Decimal("20"))
    report = check_constraints(constraints=[c], slot_registry=SLOT_REG, state=state)
    assert report.violations[0].violated is False
    assert report.violations[0].actual == str(Decimal(str(15.0)))


def test_vector_constraint_sum():
    state = _make_state(**{"gov.balance": np.array([1.0, 2.0, 3.0])})
    c = _scalar_constraint(aggregation="sum", operator="==", expected=Decimal("6"))
    report = check_constraints(constraints=[c], slot_registry=SLOT_REG, state=state)
    assert report.violations[0].violated is False


def test_vector_constraint_weighted_mean():
    reg = _make_slot_registry(
        ("gov.balance", "gov.balance"),
        ("gov.weights", "gov.weights"),
    )
    state = _make_state(
        **{
            "gov.balance": np.array([10.0, 20.0, 40.0]),
            "gov.weights": np.array([1.0, 1.0, 2.0]),
        }
    )
    c = _scalar_constraint(
        aggregation="weighted_mean",
        operator="==",
        expected=Decimal("27.5"),
        weights_slot_id="gov.weights",
    )
    report = check_constraints(constraints=[c], slot_registry=reg, state=state)
    assert report.violations[0].violated is False
    assert report.violations[0].actual == "27.5"


def test_weighted_mean_shape_mismatch_raises():
    reg = _make_slot_registry(
        ("gov.balance", "gov.balance"),
        ("gov.weights", "gov.weights"),
    )
    state = _make_state(
        **{
            "gov.balance": np.array([10.0, 20.0, 40.0]),
            "gov.weights": np.array([1.0, 2.0]),
        }
    )
    c = _scalar_constraint(
        aggregation="weighted_mean",
        operator="==",
        expected=Decimal("0"),
        weights_slot_id="gov.weights",
    )
    with pytest.raises(ValueError, match="weights shape mismatch"):
        check_constraints(constraints=[c], slot_registry=reg, state=state)


def test_weighted_mean_non_finite_weights_raise():
    reg = _make_slot_registry(
        ("gov.balance", "gov.balance"),
        ("gov.weights", "gov.weights"),
    )
    state = _make_state(
        **{
            "gov.balance": np.array([10.0, 20.0, 40.0]),
            "gov.weights": np.array([1.0, np.nan, 2.0]),
        }
    )
    c = _scalar_constraint(
        aggregation="weighted_mean",
        operator="==",
        expected=Decimal("0"),
        weights_slot_id="gov.weights",
    )
    with pytest.raises(ValueError, match="weights must be finite"):
        check_constraints(constraints=[c], slot_registry=reg, state=state)


def test_vector_constraint_quantile_rejects_invalid_parameter() -> None:
    state = _make_state(**{"gov.balance": np.array([1.0, 2.0, 3.0])})
    c = _scalar_constraint(
        aggregation="quantile",
        operator=">=",
        expected=Decimal("0"),
        quantile_param=1.5,
    )
    with pytest.raises(ValueError, match="quantile_param"):
        check_constraints(constraints=[c], slot_registry=SLOT_REG, state=state)


def test_vector_constraint_rejects_non_finite_state_values() -> None:
    state = _make_state(**{"gov.balance": np.array([1.0, np.nan, 3.0])})
    c = _scalar_constraint(aggregation="mean", operator=">=", expected=Decimal("0"))
    with pytest.raises(ValueError, match="state values must be finite"):
        check_constraints(constraints=[c], slot_registry=SLOT_REG, state=state)


# ---------------------------------------------------------------------------
# 8. Property test: aggregation monotonicity — min <= mean <= max
# ---------------------------------------------------------------------------


def test_aggregation_monotonicity():
    rng = np.random.default_rng(42)
    for _ in range(20):
        arr = rng.uniform(-100, 100, size=rng.integers(2, 50))
        state = _make_state(**{"gov.balance": arr})

        results = {}
        for agg in ("min", "mean", "max"):
            c = _scalar_constraint(aggregation=agg, operator=">=", expected=Decimal("0"))
            report = check_constraints(constraints=[c], slot_registry=SLOT_REG, state=state)
            results[agg] = Decimal(report.violations[0].actual)

        assert results["min"] <= results["mean"], f"min > mean for {arr}"
        assert results["mean"] <= results["max"], f"mean > max for {arr}"


# ---------------------------------------------------------------------------
# 9. Scalar raises on vector when aggregation=scalar
# ---------------------------------------------------------------------------


def test_scalar_aggregation_rejects_vector():
    state = _make_state(**{"gov.balance": np.array([1.0, 2.0])})
    c = _scalar_constraint(aggregation="scalar", operator=">=", expected=Decimal("0"))
    with pytest.raises(ValueError, match="expects scalar slot value"):
        check_constraints(constraints=[c], slot_registry=SLOT_REG, state=state)


# ---------------------------------------------------------------------------
# 10. Composite constraints
# ---------------------------------------------------------------------------


def _composite_slot_registry():
    return _make_slot_registry(
        ("income_mean", "income_mean"),
        ("gdp_per_capita", "gdp_per_capita"),
        ("spending_a", "spending_a"),
        ("spending_b", "spending_b"),
    )


def test_composite_constraint_ratio():
    """slot_a / slot_b >= 0.5"""
    reg = _composite_slot_registry()
    state = _make_state(income_mean=50000.0, gdp_per_capita=80000.0)
    c = CompositeConstraint(
        constraint_id="ratio_check",
        expression="income_mean / gdp_per_capita",
        slot_refs=["income_mean", "gdp_per_capita"],
        operator=">=",
        expected="0.5",
    )
    verdicts = check_composite_constraints(constraints=[c], slot_registry=reg, state=state)
    assert len(verdicts) == 1
    assert verdicts[0].violated is False  # 50000/80000 = 0.625 >= 0.5

    # Check event
    assert verdicts[0].events[0]["event"] == "composite_constraint_evaluated"
    assert verdicts[0].events[0]["ok"] is True


def test_composite_constraint_ratio_violated():
    reg = _composite_slot_registry()
    state = _make_state(income_mean=10000.0, gdp_per_capita=80000.0)
    c = CompositeConstraint(
        constraint_id="ratio_check",
        expression="income_mean / gdp_per_capita",
        slot_refs=["income_mean", "gdp_per_capita"],
        operator=">=",
        expected="0.5",
    )
    verdicts = check_composite_constraints(constraints=[c], slot_registry=reg, state=state)
    assert verdicts[0].violated is True  # 10000/80000 = 0.125 < 0.5


def test_composite_constraint_sum_budget():
    """spending_a + spending_b <= budget"""
    reg = _composite_slot_registry()
    state = _make_state(spending_a=300.0, spending_b=200.0)
    c = CompositeConstraint(
        constraint_id="budget_sum",
        expression="spending_a + spending_b",
        slot_refs=["spending_a", "spending_b"],
        operator="<=",
        expected="600",
    )
    verdicts = check_composite_constraints(constraints=[c], slot_registry=reg, state=state)
    assert verdicts[0].violated is False  # 300 + 200 = 500 <= 600


def test_composite_constraint_sum_budget_violated():
    reg = _composite_slot_registry()
    state = _make_state(spending_a=400.0, spending_b=300.0)
    c = CompositeConstraint(
        constraint_id="budget_sum",
        expression="spending_a + spending_b",
        slot_refs=["spending_a", "spending_b"],
        operator="<=",
        expected="600",
    )
    verdicts = check_composite_constraints(constraints=[c], slot_registry=reg, state=state)
    assert verdicts[0].violated is True  # 700 > 600


# ---------------------------------------------------------------------------
# 11. Safe expression evaluator — rejects unsafe constructs
# ---------------------------------------------------------------------------


def test_safe_eval_rejects_function_call():
    with pytest.raises(ValueError, match="Disallowed AST node"):
        _safe_eval_expression("__import__('os')", {})


def test_safe_eval_rejects_attribute_access():
    with pytest.raises(ValueError, match="Disallowed AST node"):
        _safe_eval_expression("x.__class__", {"x": Decimal("1")})


def test_safe_eval_rejects_list_comprehension():
    with pytest.raises(ValueError, match="Disallowed AST node"):
        _safe_eval_expression("[x for x in range(10)]", {})


def test_safe_eval_unknown_slot():
    with pytest.raises(ValueError, match="Unknown slot reference"):
        _safe_eval_expression("a + b", {"a": Decimal("1")})


def test_safe_eval_basic_arithmetic():
    result = _safe_eval_expression("a + b * 2", {"a": Decimal("10"), "b": Decimal("5")})
    assert float(result) == pytest.approx(20.0)


def test_safe_eval_division():
    result = _safe_eval_expression("a / b", {"a": Decimal("10"), "b": Decimal("4")})
    assert float(result) == pytest.approx(2.5)


def test_safe_eval_negation():
    result = _safe_eval_expression("-a + b", {"a": Decimal("3"), "b": Decimal("10")})
    assert float(result) == pytest.approx(7.0)
