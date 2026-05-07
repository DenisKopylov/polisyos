"""Tests for WS6.5 — Cost-Aware Stopping & AND-Logic Composite."""

from __future__ import annotations

import pytest
from polisyos.scientist.methods.search.stopping import (
    AllStoppingCriteria,
    CompositeStoppingCriterion,
    CostBudgetStopping,
    MaxIterations,
    StoppingPresets,
)

# ---------------------------------------------------------------------------
# CostBudgetStopping
# ---------------------------------------------------------------------------


class TestCostBudgetStopping:
    def test_stops_at_budget(self):
        s = CostBudgetStopping(max_cost_usd=10.0)
        result = s.check([], {"cumulative_cost_usd": 10.0})
        assert result.should_stop
        assert "10.0 USD" in result.reason

    def test_does_not_stop_below_budget(self):
        s = CostBudgetStopping(max_cost_usd=10.0)
        result = s.check([], {"cumulative_cost_usd": 9.9})
        assert not result.should_stop

    def test_stops_when_over_budget(self):
        s = CostBudgetStopping(max_cost_usd=5.0)
        result = s.check([], {"cumulative_cost_usd": 7.0})
        assert result.should_stop

    def test_missing_cost_key_does_not_stop(self):
        s = CostBudgetStopping(max_cost_usd=10.0)
        result = s.check([], {})
        assert not result.should_stop

    def test_custom_cost_key(self):
        s = CostBudgetStopping(max_cost_usd=5.0, cost_key="my_cost")
        result = s.check([], {"my_cost": 5.0})
        assert result.should_stop

    def test_invalid_budget_raises(self):
        with pytest.raises(ValueError):
            CostBudgetStopping(max_cost_usd=0.0)

    def test_name(self):
        assert CostBudgetStopping(1.0).name == "cost_budget"


# ---------------------------------------------------------------------------
# AllStoppingCriteria (AND logic)
# ---------------------------------------------------------------------------


class TestAllStoppingCriteria:
    def test_stops_when_all_trigger(self):
        s = AllStoppingCriteria(
            [
                MaxIterations(3),
                CostBudgetStopping(max_cost_usd=5.0),
            ]
        )
        history = [{"iteration": i} for i in range(3)]
        result = s.check(history, {"cumulative_cost_usd": 5.0})
        assert result.should_stop

    def test_does_not_stop_when_only_one_triggers(self):
        s = AllStoppingCriteria(
            [
                MaxIterations(3),
                CostBudgetStopping(max_cost_usd=5.0),
            ]
        )
        history = [{"iteration": i} for i in range(3)]
        result = s.check(history, {"cumulative_cost_usd": 2.0})
        assert not result.should_stop

    def test_does_not_stop_when_none_trigger(self):
        s = AllStoppingCriteria(
            [
                MaxIterations(10),
                CostBudgetStopping(max_cost_usd=100.0),
            ]
        )
        result = s.check([{"iteration": 0}], {"cumulative_cost_usd": 1.0})
        assert not result.should_stop

    def test_reason_includes_all(self):
        s = AllStoppingCriteria(
            [
                MaxIterations(1),
                CostBudgetStopping(max_cost_usd=0.01),
            ]
        )
        result = s.check([{"iteration": 0}], {"cumulative_cost_usd": 1.0})
        assert result.should_stop
        assert "AND" in result.reason

    def test_reset_propagates(self):
        s = AllStoppingCriteria([MaxIterations(3)])
        s.reset()  # Should not raise

    def test_empty_criteria_raises(self):
        with pytest.raises(ValueError):
            AllStoppingCriteria([])

    def test_name(self):
        assert AllStoppingCriteria([MaxIterations(1)]).name == "all_composite"


# ---------------------------------------------------------------------------
# StoppingPresets.cost_bounded
# ---------------------------------------------------------------------------


class TestStoppingPresetsCostBounded:
    def test_cost_bounded_preset(self):
        s = StoppingPresets.cost_bounded(max_cost_usd=10.0, max_iter=50)
        assert isinstance(s, CompositeStoppingCriterion)

    def test_stops_on_cost(self):
        s = StoppingPresets.cost_bounded(max_cost_usd=5.0, max_iter=100)
        result = s.check([], {"cumulative_cost_usd": 5.0})
        assert result.should_stop

    def test_stops_on_iterations(self):
        s = StoppingPresets.cost_bounded(max_cost_usd=1000.0, max_iter=3)
        history = [{"iteration": i} for i in range(3)]
        result = s.check(history, {"cumulative_cost_usd": 0.0})
        assert result.should_stop
