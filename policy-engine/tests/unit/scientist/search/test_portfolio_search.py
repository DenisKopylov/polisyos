from __future__ import annotations

from typing import Any

import pytest
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.portfolio import PolicyPortfolio
from polisyos.scientist.search.controller import SearchConfig, SearchController
from polisyos.scientist.search.objective import (
    CompositeObjective,
    ObjectiveValue,
    OptimizationDirection,
)
from polisyos.scientist.search.portfolio import (
    PortfolioCombination,
    PortfolioSearchMode,
    PortfolioSearchSpace,
)
from polisyos.scientist.search.stopping import MaxIterations


class _NoopObjective:
    @property
    def name(self) -> str:
        return "noop"

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MINIMIZE

    def evaluate(self, results: dict[str, Any]) -> ObjectiveValue:
        return ObjectiveValue(
            name="noop",
            raw_value=float(results.get("v", 0.0)),
            direction=self.direction,
        )


class _NoopGenerator:
    def generate(self, history, current_best, context):
        del history, current_best, context
        return {"semantic": {"interventions": []}}


class _FakePortfolioMetrics:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def record_portfolio_search(
        self,
        *,
        portfolio_id: str,
        combinations_evaluated: int,
        best_objective: float | None,
    ) -> None:
        self.calls.append(
            {
                "portfolio_id": portfolio_id,
                "combinations_evaluated": combinations_evaluated,
                "best_objective": best_objective,
            }
        )


def _portfolio() -> PolicyPortfolio:
    return PolicyPortfolio(
        portfolio_id="portfolio_a",
        policies=[
            PolicySpec(policy_id="a"),
            PolicySpec(policy_id="b"),
            PolicySpec(policy_id="c"),
        ],
        required_policies=["a"],
        excluded_pairs=[("b", "c")],
        max_active_policies=2,
    )


def test_portfolio_search_space_filters_constraints() -> None:
    space = PortfolioSearchSpace(_portfolio(), enumeration_limit=20)
    combos = space.enumerate_combinations()
    keys = {combo.combination_key for combo in combos}
    assert "a" in keys
    assert "a|b" in keys
    assert "a|c" in keys
    assert "a|b|c" not in keys


def test_portfolio_search_space_enumeration_limit() -> None:
    portfolio = PolicyPortfolio(
        portfolio_id="large",
        policies=[PolicySpec(policy_id=f"p{i}") for i in range(5)],
    )
    space = PortfolioSearchSpace(portfolio, enumeration_limit=10)
    with pytest.raises(ValueError, match="exceeded enumeration limit"):
        _ = space.enumerate_combinations()


def test_search_controller_portfolio_mode() -> None:
    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(1),
            objective=CompositeObjective([_NoopObjective()]),
        ),
        candidate_generator=_NoopGenerator(),
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {"v": 0.0},
            "feedback": {"verdict": "APPROVE"},
        },
    )

    portfolio = _portfolio()

    def evaluator(combination: PortfolioCombination, context: dict[str, Any]) -> dict[str, Any]:
        del context
        # Prefer larger valid combinations for this synthetic test.
        return {
            "objective_value": float(len(combination.active_policy_ids)),
            "n_active": len(combination.active_policy_ids),
        }

    results = controller.run_portfolio_search(
        portfolio=portfolio,
        evaluator=evaluator,
        mode=PortfolioSearchMode.ENUMERATE.value,
        max_evaluations=10,
    )

    assert results
    assert results[0].objective_value >= results[-1].objective_value
    assert len(results[0].combination.active_policy_ids) == 2


def test_search_controller_portfolio_falls_back_to_sampling_on_cap() -> None:
    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(1),
            objective=CompositeObjective([_NoopObjective()]),
        ),
        candidate_generator=_NoopGenerator(),
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {"v": 0.0},
            "feedback": {"verdict": "APPROVE"},
        },
    )
    large_portfolio = PolicyPortfolio(
        portfolio_id="large_portfolio",
        policies=[PolicySpec(policy_id=f"p{i}") for i in range(16)],
    )

    results = controller.run_portfolio_search(
        portfolio=large_portfolio,
        evaluator=lambda combo, context: float(len(combo.active_policy_ids)),
        mode=PortfolioSearchMode.ENUMERATE.value,
        max_evaluations=25,
    )

    assert results
    assert len(results) <= 25


def test_search_controller_portfolio_search_accepts_injected_metrics(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "polisyos.scientist.search.controller._default_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global metrics should not be used")),
    )
    metrics = _FakePortfolioMetrics()
    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(1),
            objective=CompositeObjective([_NoopObjective()]),
        ),
        candidate_generator=_NoopGenerator(),
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {"v": 0.0},
            "feedback": {"verdict": "APPROVE"},
        },
        metrics=metrics,
    )

    controller.run_portfolio_search(
        portfolio=_portfolio(),
        evaluator=lambda combo, context: float(len(combo.active_policy_ids)),
        mode=PortfolioSearchMode.ENUMERATE.value,
        max_evaluations=10,
    )

    assert metrics.calls == [
        {
            "portfolio_id": "portfolio_a",
            "combinations_evaluated": 3,
            "best_objective": 2.0,
        }
    ]
