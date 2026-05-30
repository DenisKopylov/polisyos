"""Public search portfolio module API."""

from __future__ import annotations

import itertools
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from polisyos.ir.loading.portfolio import PolicyPortfolio


class PortfolioSearchMode(str, Enum):
    """Portfolio search mode public type."""

    ENUMERATE = "enumerate"
    SAMPLE = "sample"
    GREEDY = "greedy"


@dataclass(frozen=True)
class PortfolioCombination:
    """Portfolio combination public type."""

    active_policy_ids: frozenset[str]
    parameter_overrides: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    @property
    def combination_key(self) -> str:
        return "|".join(sorted(self.active_policy_ids))


@dataclass(frozen=True)
class PortfolioEvaluationResult:
    """Portfolio evaluation result data model."""

    combination: PortfolioCombination
    objective_value: float
    metrics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PortfolioSweepConfig:
    """Portfolio sweep config data model."""

    portfolio: PolicyPortfolio
    combination_mode: PortfolioSearchMode = PortfolioSearchMode.ENUMERATE
    max_combinations: int = 100
    parameter_grid: Mapping[str, list[Any]] | None = None


@dataclass(frozen=True)
class PortfolioSweepReport:
    """Portfolio sweep report data model."""

    total_evaluations: int
    best_result: PortfolioEvaluationResult | None
    all_results: tuple[PortfolioEvaluationResult, ...]


class PortfolioSearchSpace:
    """Combinatorial search space over policy activation choices."""

    def __init__(
        self,
        portfolio: PolicyPortfolio,
        *,
        enumeration_limit: int = 10_000,
    ) -> None:
        self.portfolio = portfolio
        self.enumeration_limit = max(1, int(enumeration_limit))
        self._all_ids = list(portfolio.policy_ids)
        self._required = set(portfolio.required_policies)
        self._excluded = {frozenset(pair) for pair in portfolio.excluded_pairs}
        self._optional = [
            policy_id for policy_id in self._all_ids if policy_id not in self._required
        ]

    def enumerate_combinations(self) -> list[PortfolioCombination]:
        max_optional = len(self._optional)
        if self.portfolio.max_active_policies is not None:
            max_optional = min(
                max_optional,
                self.portfolio.max_active_policies - len(self._required),
            )

        combinations: list[PortfolioCombination] = []
        for cardinality in range(max_optional + 1):
            for subset in itertools.combinations(self._optional, cardinality):
                active = self._required | set(subset)
                if not self._is_valid(active):
                    continue
                combinations.append(PortfolioCombination(active_policy_ids=frozenset(active)))
                if len(combinations) > self.enumeration_limit:
                    raise ValueError(
                        "portfolio combination count exceeded enumeration limit; "
                        "switch to sample mode or increase limit"
                    )
        return combinations

    def sample_combinations(
        self,
        n: int,
        *,
        rng_seed: int = 42,
    ) -> list[PortfolioCombination]:
        n = max(1, int(n))
        rng = random.Random(rng_seed)

        if len(self._optional) <= 15:
            all_combinations = self.enumerate_combinations()
            if len(all_combinations) <= n:
                return all_combinations
            rng.shuffle(all_combinations)
            return all_combinations[:n]

        sampled: dict[str, PortfolioCombination] = {}
        attempts = 0
        max_attempts = max(n * 50, 100)

        while len(sampled) < n and attempts < max_attempts:
            attempts += 1
            active = set(self._required)
            for policy_id in self._optional:
                if rng.random() < 0.5:
                    active.add(policy_id)
            if not self._is_valid(active):
                continue
            combination = PortfolioCombination(active_policy_ids=frozenset(active))
            sampled[combination.combination_key] = combination

        return list(sampled.values())

    def greedy_combinations(
        self,
        *,
        base_benefits: Mapping[str, float],
        max_combinations: int,
    ) -> list[PortfolioCombination]:
        max_combinations = max(1, int(max_combinations))
        active = set(self._required)
        yielded: list[PortfolioCombination] = [
            PortfolioCombination(active_policy_ids=frozenset(active))
        ]

        remaining = [policy_id for policy_id in self._optional if policy_id not in active]
        while remaining and len(yielded) < max_combinations:
            best_policy: str | None = None
            best_delta = float("-inf")

            for candidate in remaining:
                candidate_active = set(active)
                candidate_active.add(candidate)
                if not self._is_valid(candidate_active):
                    continue
                current = self.portfolio.total_benefit(base_benefits, active_policy_ids=active)
                proposed = self.portfolio.total_benefit(
                    base_benefits,
                    active_policy_ids=candidate_active,
                )
                delta = proposed - current
                if delta > best_delta:
                    best_delta = delta
                    best_policy = candidate

            if best_policy is None:
                break
            active.add(best_policy)
            remaining.remove(best_policy)
            yielded.append(PortfolioCombination(active_policy_ids=frozenset(active)))

        return yielded[:max_combinations]

    def _is_valid(self, active: set[str]) -> bool:
        if not self.portfolio.is_valid_combination(active):
            return False
        for pair in self._excluded:
            if pair.issubset(active):
                return False
        return True


class PortfolioSweep:
    """Two-level sweep over portfolio combinations and optional parameter grid."""

    def __init__(self, config: PortfolioSweepConfig) -> None:
        self.config = config

    def run(
        self,
        evaluator: Callable[[PortfolioCombination], PortfolioEvaluationResult],
    ) -> PortfolioSweepReport:
        search_space = PortfolioSearchSpace(self.config.portfolio)

        if self.config.combination_mode is PortfolioSearchMode.ENUMERATE:
            try:
                combinations = search_space.enumerate_combinations()
            except ValueError:
                combinations = search_space.sample_combinations(self.config.max_combinations)
        elif self.config.combination_mode is PortfolioSearchMode.SAMPLE:
            combinations = search_space.sample_combinations(self.config.max_combinations)
        else:
            combinations = search_space.greedy_combinations(
                base_benefits={},
                max_combinations=self.config.max_combinations,
            )

        combinations = combinations[: self.config.max_combinations]

        results: list[PortfolioEvaluationResult] = []
        if self.config.parameter_grid:
            expanded = self._expand_grid(self.config.parameter_grid)
            for combination in combinations:
                for overrides in expanded:
                    combo = PortfolioCombination(
                        active_policy_ids=combination.active_policy_ids,
                        parameter_overrides=overrides,
                    )
                    results.append(evaluator(combo))
        else:
            for combination in combinations:
                results.append(evaluator(combination))

        results.sort(key=lambda item: item.objective_value, reverse=True)
        best = results[0] if results else None
        return PortfolioSweepReport(
            total_evaluations=len(results),
            best_result=best,
            all_results=tuple(results),
        )

    def _expand_grid(
        self,
        grid: Mapping[str, list[Any]],
    ) -> list[dict[str, dict[str, Any]]]:
        if not grid:
            return [{}]

        keys = sorted(grid.keys())
        values = [list(grid[key]) for key in keys]
        variants: list[dict[str, dict[str, Any]]] = []

        for tuple_values in itertools.product(*values):
            payload: dict[str, dict[str, Any]] = {}
            for key, value in zip(keys, tuple_values):
                policy_id, _, param_id = key.partition(".")
                if not policy_id or not param_id:
                    continue
                payload.setdefault(policy_id, {})[param_id] = value
            variants.append(payload)
        return variants


__all__ = [
    "PortfolioCombination",
    "PortfolioEvaluationResult",
    "PortfolioSearchMode",
    "PortfolioSearchSpace",
    "PortfolioSweep",
    "PortfolioSweepConfig",
    "PortfolioSweepReport",
]
