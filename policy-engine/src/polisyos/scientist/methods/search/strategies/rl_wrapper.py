"""RL-inspired exploration wrapper for search strategies."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Protocol

from polisyos.scientist.methods.search.strategies.base import SearchStrategy
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    PolicyCandidate,
    StrategyState,
)


class ExplorationSchedule(Protocol):
    """Exploration schedule protocol."""

    def __call__(self, iteration: int) -> float:
        """Return exploration probability at given iteration."""


@dataclass(slots=True)
class LinearDecay:
    """Linear epsilon decay."""

    start: float = 1.0
    end: float = 0.1
    n_steps: int = 100

    def __call__(self, iteration: int) -> float:
        if iteration >= self.n_steps:
            return self.end
        return self.start - (self.start - self.end) * (iteration / self.n_steps)


@dataclass(slots=True)
class RLConfig:
    """Config for RL exploration wrapper."""

    exploration_schedule: ExplorationSchedule | None = None
    seed: int = 42

    def __post_init__(self) -> None:
        if self.exploration_schedule is None:
            self.exploration_schedule = LinearDecay()


class RLStrategyWrapper:
    """Adds epsilon-greedy exploration on top of another strategy."""

    def __init__(
        self,
        base_strategy: SearchStrategy,
        space: SearchSpace,
        config: RLConfig | None = None,
    ):
        self._base = base_strategy
        self._space = space
        self._config = config or RLConfig()
        self._rng = random.Random(self._config.seed)
        self._iteration = 0

    def suggest(
        self,
        evaluations: list[Evaluation],
        pending: list[PolicyCandidate] | None = None,
    ) -> PolicyCandidate:
        self._iteration = len(evaluations)
        epsilon = self._config.exploration_schedule(self._iteration)
        if self._rng.random() < epsilon:
            return self._explore_random()
        return self._base.suggest(evaluations, pending=pending)

    def suggest_batch(
        self, evaluations: list[Evaluation], batch_size: int
    ) -> list[PolicyCandidate]:
        return [self.suggest(evaluations) for _ in range(batch_size)]

    def update(self, evaluation: Evaluation) -> None:
        self._base.update(evaluation)

    def get_state(self) -> StrategyState:
        base_state = self._base.get_state()
        return StrategyState(
            strategy_name="RLStrategyWrapper",
            iteration=self._iteration,
            rng_state={"python": self._rng.getstate()},
            model_state=base_state.model_state,
            metadata={
                "base_strategy": base_state.strategy_name,
                "base_state": base_state.to_artifact().decode("utf-8"),
            },
        )

    def set_state(self, state: StrategyState) -> None:
        self._iteration = state.iteration
        rng_state = state.rng_state.get("python")
        if rng_state is not None:
            self._rng.setstate(rng_state)

    def _explore_random(self) -> PolicyCandidate:
        vector = tuple(self._rng.random() for _ in range(self._space.dim))
        return PolicyCandidate(
            params=self._space.denormalize(vector),
            params_normalized=vector,
            source_strategy="rl_exploration",
        )
