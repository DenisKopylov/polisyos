"""Base protocols and helpers for search strategies."""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from polisyos.scientist.search.strategies.space import SearchSpace
from polisyos.scientist.search.strategies.types import (
    Evaluation,
    PolicyCandidate,
    StrategyState,
)


@runtime_checkable
class SearchStrategy(Protocol):
    """Protocol for strategy implementations."""

    def suggest(
        self,
        evaluations: list[Evaluation],
        pending: list[PolicyCandidate] | None = None,
    ) -> PolicyCandidate:
        """Suggest one candidate."""

    def suggest_batch(
        self,
        evaluations: list[Evaluation],
        batch_size: int,
    ) -> list[PolicyCandidate]:
        """Suggest a batch of candidates for parallel evaluation."""

    def update(self, evaluation: Evaluation) -> None:
        """Update strategy state after receiving a finished evaluation."""

    def get_state(self) -> StrategyState:
        """Serialize strategy state for checkpointing."""

    def set_state(self, state: StrategyState) -> None:
        """Restore strategy state from checkpoint."""


class BaseSearchStrategy(ABC):
    """Common functionality for concrete strategies."""

    def __init__(self, space: SearchSpace, seed: int = 42):
        self._space = space
        self._seed = seed
        self._rng = random.Random(seed)
        self._iteration = 0
        self._sobol_cache: list[tuple[float, ...]] = []

    @abstractmethod
    def suggest(
        self,
        evaluations: list[Evaluation],
        pending: list[PolicyCandidate] | None = None,
    ) -> PolicyCandidate:
        """Suggest one candidate."""

    def suggest_batch(
        self,
        evaluations: list[Evaluation],
        batch_size: int,
    ) -> list[PolicyCandidate]:
        candidates: list[PolicyCandidate] = []
        for _ in range(batch_size):
            candidates.append(self.suggest(evaluations, pending=candidates))
        return candidates

    def update(self, evaluation: Evaluation) -> None:
        del evaluation

    def get_state(self) -> StrategyState:
        return StrategyState(
            strategy_name=self.__class__.__name__,
            iteration=self._iteration,
            rng_state={"python": self._rng.getstate()},
            metadata={"seed": self._seed},
        )

    def set_state(self, state: StrategyState) -> None:
        self._iteration = state.iteration
        rng_state = state.rng_state.get("python")
        if rng_state is not None:
            self._rng.setstate(rng_state)

    def _random_candidate(self, source: str = "random") -> PolicyCandidate:
        vector = tuple(self._rng.random() for _ in range(self._space.dim))
        return PolicyCandidate(
            params=self._space.denormalize(vector),
            params_normalized=vector,
            source_strategy=source,
        )

    def _sobol_candidate(self, index: int, source: str = "sobol_init") -> PolicyCandidate:
        if index >= len(self._sobol_cache):
            needed = index + 1 - len(self._sobol_cache)
            self._sobol_cache.extend(
                self._space.sample_sobol(n_samples=needed, seed=self._seed + len(self._sobol_cache))
            )
        vector = self._sobol_cache[index]
        return PolicyCandidate(
            params=self._space.denormalize(vector),
            params_normalized=vector,
            source_strategy=source,
        )

