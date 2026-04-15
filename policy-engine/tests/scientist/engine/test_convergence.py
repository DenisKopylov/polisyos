"""Unit tests for convergence detection."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from polisyos.scientist.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.engine.convergence import (
    ConvergenceConfig,
    ConvergenceDetector,
    ConvergenceState,
    ConvergenceStrategy,
    ConvergenceValidationError,
)

# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------

class TestConvergenceConfigModel:
    def test_defaults(self) -> None:
        cfg = ConvergenceConfig()
        assert cfg.strategy == ConvergenceStrategy.ABSOLUTE_DELTA
        assert cfg.threshold == 0.01
        assert cfg.min_iterations == 2
        assert cfg.max_iterations == 10
        assert cfg.window_size == 2
        assert cfg.budget_key is None

    def test_extra_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            ConvergenceConfig(extra_field="bad")  # type: ignore[call-arg]

    def test_roundtrip(self) -> None:
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.RELATIVE_DELTA,
            threshold=0.05,
            min_iterations=3,
            max_iterations=20,
        )
        dumped = cfg.model_dump()
        restored = ConvergenceConfig.model_validate(dumped)
        assert restored.strategy == ConvergenceStrategy.RELATIVE_DELTA
        assert restored.threshold == 0.05


class TestConvergenceStateModel:
    def test_defaults(self) -> None:
        s = ConvergenceState()
        assert s.iteration == 0
        assert s.converged is False
        assert s.reason == ""


# ---------------------------------------------------------------------------
# Absolute delta strategy
# ---------------------------------------------------------------------------

class TestAbsoluteDelta:
    def test_converges_when_stable(self) -> None:
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.ABSOLUTE_DELTA,
            threshold=0.05,
            min_iterations=2,
            window_size=2,
        )
        d = ConvergenceDetector(cfg)
        s1 = d.check(0.80)
        assert not s1.converged  # iteration 1 < min_iterations=2
        s2 = d.check(0.82)  # delta=0.02 < 0.05, iteration 2 >= min=2 → converged
        assert s2.converged
        assert "absolute_delta" in s2.reason

    def test_not_converged_when_delta_large(self) -> None:
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.ABSOLUTE_DELTA,
            threshold=0.01,
            min_iterations=2,
            window_size=2,
        )
        d = ConvergenceDetector(cfg)
        d.check(0.50)
        s = d.check(0.60)  # delta=0.10 > 0.01
        assert not s.converged

    def test_min_iterations_respected(self) -> None:
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.ABSOLUTE_DELTA,
            threshold=0.5,  # very loose
            min_iterations=5,
            window_size=2,
        )
        d = ConvergenceDetector(cfg)
        for _i in range(4):
            s = d.check(0.80)
            assert not s.converged  # below min_iterations
        s = d.check(0.80)
        assert s.converged  # iteration 5 >= min=5

    def test_max_iterations_hard_stop(self) -> None:
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.ABSOLUTE_DELTA,
            threshold=0.001,  # very tight — won't converge naturally
            min_iterations=1,
            max_iterations=3,
            window_size=2,
        )
        d = ConvergenceDetector(cfg)
        d.check(0.10)
        d.check(0.30)
        s = d.check(0.50)  # iteration 3 = max
        assert s.converged
        assert s.reason == "max_iterations"

    def test_window_size_3(self) -> None:
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.ABSOLUTE_DELTA,
            threshold=0.02,
            min_iterations=3,
            window_size=3,
        )
        d = ConvergenceDetector(cfg)
        d.check(0.80)
        d.check(0.81)
        s = d.check(0.815)  # window=[0.80, 0.81, 0.815], deltas=[0.01, 0.005] < 0.02
        assert s.converged


# ---------------------------------------------------------------------------
# Relative delta strategy
# ---------------------------------------------------------------------------

class TestRelativeDelta:
    def test_converges_when_relative_change_small(self) -> None:
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.RELATIVE_DELTA,
            threshold=0.05,
            min_iterations=2,
            window_size=2,
        )
        d = ConvergenceDetector(cfg)
        d.check(10.0)
        s = d.check(10.1)  # relative delta = 0.1/10.0 = 0.01 < 0.05
        assert s.converged

    def test_not_converged_when_relative_change_large(self) -> None:
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.RELATIVE_DELTA,
            threshold=0.05,
            min_iterations=2,
            window_size=2,
        )
        d = ConvergenceDetector(cfg)
        d.check(1.0)
        s = d.check(1.5)  # relative delta = 0.5/1.0 = 0.50 > 0.05
        assert not s.converged

    def test_near_zero_base_fallback(self) -> None:
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.RELATIVE_DELTA,
            threshold=0.1,
            min_iterations=2,
            window_size=2,
        )
        d = ConvergenceDetector(cfg)
        d.check(0.0)
        s = d.check(0.05)  # base ≈ 0, absolute fallback: 0.05 < 0.1
        assert s.converged


# ---------------------------------------------------------------------------
# Semantic similarity strategy
# ---------------------------------------------------------------------------

class TestSemanticSimilarity:
    def test_converges_above_threshold(self) -> None:
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.SEMANTIC_SIMILARITY,
            threshold=0.95,
            min_iterations=2,
            window_size=2,
        )
        d = ConvergenceDetector(cfg)
        d.check(0.80)
        s = d.check(0.96)
        assert s.converged

    def test_not_converged_below_threshold(self) -> None:
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.SEMANTIC_SIMILARITY,
            threshold=0.95,
            min_iterations=2,
            window_size=2,
        )
        d = ConvergenceDetector(cfg)
        d.check(0.80)
        s = d.check(0.90)
        assert not s.converged


# ---------------------------------------------------------------------------
# Composite strategy
# ---------------------------------------------------------------------------

class TestComposite:
    def test_converges_when_both_pass(self) -> None:
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.COMPOSITE,
            threshold=0.05,
            min_iterations=2,
            window_size=2,
        )
        d = ConvergenceDetector(cfg)
        d.check(10.0)
        s = d.check(10.01)  # abs delta=0.01 < 0.05, rel delta=0.001 < 0.05
        assert s.converged

    def test_not_converged_when_only_abs_passes(self) -> None:
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.COMPOSITE,
            threshold=0.02,
            min_iterations=2,
            window_size=2,
        )
        d = ConvergenceDetector(cfg)
        d.check(0.5)
        s = d.check(0.51)  # abs=0.01 < 0.02, rel=0.01/0.5=0.02 → NOT < 0.02
        assert not s.converged


# ---------------------------------------------------------------------------
# Budget integration
# ---------------------------------------------------------------------------

class TestBudgetPressure:
    def test_early_stop_on_budget_pressure(self) -> None:
        budget = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("1.00"))},
            spent={"run": Decimal("0.95")},
        )
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.ABSOLUTE_DELTA,
            threshold=0.001,
            min_iterations=1,
            max_iterations=10,
            budget_key="run",
            budget_headroom_ratio=0.1,  # stop when < 0.10 remaining
        )
        d = ConvergenceDetector(cfg, budget_state=budget)
        s = d.check(0.50)  # remaining=0.05 < 0.10 headroom
        assert s.converged
        assert s.reason == "budget_pressure"

    def test_no_early_stop_when_budget_ok(self) -> None:
        budget = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("1.00"))},
            spent={"run": Decimal("0.50")},
        )
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.ABSOLUTE_DELTA,
            threshold=0.001,
            min_iterations=1,
            max_iterations=10,
            budget_key="run",
            budget_headroom_ratio=0.1,
        )
        d = ConvergenceDetector(cfg, budget_state=budget)
        s = d.check(0.50)  # remaining=0.50, headroom=0.10 → ok
        assert not s.converged

    def test_no_budget_key_ignores_budget(self) -> None:
        budget = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("1.00"))},
            spent={"run": Decimal("0.99")},
        )
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.ABSOLUTE_DELTA,
            threshold=0.5,
            min_iterations=2,
            budget_key=None,  # no budget check
        )
        d = ConvergenceDetector(cfg, budget_state=budget)
        d.check(0.50)
        s = d.check(0.51)
        assert s.converged
        assert "absolute_delta" in s.reason

    def test_budget_key_requires_positive_limit(self) -> None:
        budget = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("0.00"))},
        )
        cfg = ConvergenceConfig(budget_key="run")

        with pytest.raises(ConvergenceValidationError, match="positive limit"):
            ConvergenceDetector(cfg, budget_state=budget)


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_clears_state(self) -> None:
        cfg = ConvergenceConfig(min_iterations=1, max_iterations=5)
        d = ConvergenceDetector(cfg)
        d.check(0.50)
        d.check(0.50)
        d.reset()
        s = d.check(0.50)
        assert not s.converged  # iteration 1, min=2 required
        assert s.iteration == 1


# ---------------------------------------------------------------------------
# History tracking
# ---------------------------------------------------------------------------

class TestHistoryTracking:
    def test_history_recorded(self) -> None:
        cfg = ConvergenceConfig(min_iterations=1, max_iterations=10)
        d = ConvergenceDetector(cfg)
        d.check(0.1)
        d.check(0.2)
        s = d.check(0.3)
        assert s.history == [0.1, 0.2, 0.3]
        assert s.iteration == 3


def test_non_finite_metric_is_rejected() -> None:
    detector = ConvergenceDetector(ConvergenceConfig())
    with pytest.raises(ConvergenceValidationError, match="finite"):
        detector.check(float("nan"))
