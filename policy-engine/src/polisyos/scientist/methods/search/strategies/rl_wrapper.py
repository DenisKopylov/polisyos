"""RL-inspired exploration wrapper for search strategies."""

from __future__ import annotations

import math
import random
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Protocol

from polisyos.scientist.methods.search.strategies.base import (
    SearchStrategy,
    _decode_python_random_state,
    _encode_python_random_state,
)
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

    def __post_init__(self):
        if (
            type(self.n_steps) is not int
            or self.n_steps < 1
            or any(
                type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1
                for value in (self.start, self.end)
            )
        ):
            raise ValueError("Linear exploration schedule is invalid")

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
            occupied = [*(pending or []), *(PolicyCandidate(params=e.params) for e in evaluations)]
            for _ in range(20):
                candidate = self._explore_random()
                if not any(
                    self._space.same_execution(candidate.params, other.params) for other in occupied
                ):
                    return candidate
            return self._explore_random()
        return self._base.suggest(evaluations, pending=pending)

    def suggest_batch(
        self, evaluations: list[Evaluation], batch_size: int
    ) -> list[PolicyCandidate]:
        output = []
        for _ in range(batch_size):
            output.append(self.suggest(evaluations, pending=output))
        return output

    def update(self, evaluation: Evaluation) -> None:
        self._base.update(evaluation)

    def get_state(self) -> StrategyState:
        base_state = self._base.get_state()
        return StrategyState(
            strategy_name="RLStrategyWrapper",
            iteration=self._iteration,
            rng_state={"python": _encode_python_random_state(self._rng.getstate())},
            model_state=base_state.model_state,
            metadata={
                "rl_state_version": 1,
                "seed": self._config.seed,
                "space": self._space.sobol_space_fingerprint(),
                "schedule": self._schedule_basis(),
                "base_strategy": base_state.strategy_name,
                "base_state": base_state.to_artifact().decode("utf-8"),
            },
        )

    def set_state(self, state: StrategyState) -> None:
        meta = state.metadata
        if (
            not isinstance(meta, Mapping)
            or not isinstance(state.rng_state, Mapping)
            or state.strategy_name != "RLStrategyWrapper"
            or type(state.iteration) is not int
            or state.iteration < 0
            or type(meta.get("rl_state_version")) is not int
            or meta["rl_state_version"] != 1
            or type(meta.get("seed")) is not int
            or meta.get("space") != self._space.sobol_space_fingerprint()
            or meta.get("schedule") != self._schedule_basis()
            or not isinstance(meta.get("base_state"), str)
        ):
            raise ValueError("RL checkpoint basis is invalid or incompatible")
        rng = _decode_python_random_state(state.rng_state.get("python"))
        nested = StrategyState.from_artifact(meta["base_state"].encode())
        if (
            nested.strategy_name != meta.get("base_strategy")
            or nested.strategy_name != self._base.get_state().strategy_name
            or nested.model_state != state.model_state
        ):
            raise ValueError("RL nested strategy identity/model changed")
        # Canonical supported base decoders validate completely before mutation.
        # All wrapper-owned fields are validated before invoking that decoder.
        self._base.set_state(nested)
        self._rng.setstate(rng)
        self._iteration = state.iteration
        self._config.seed = meta["seed"]

    def _schedule_basis(self):
        if type(self._config.exploration_schedule) is not LinearDecay:
            raise ValueError("RL checkpoint requires a supported versioned schedule")
        return {"profile": "linear_decay.v1", **asdict(self._config.exploration_schedule)}

    def _explore_random(self) -> PolicyCandidate:
        vector = tuple(self._rng.random() for _ in range(self._space.dim))
        return self._space.candidate_from_vector(vector, source_strategy="rl_exploration")
