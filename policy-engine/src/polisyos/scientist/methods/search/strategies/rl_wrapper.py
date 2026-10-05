"""RL-inspired exploration wrapper for search strategies."""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Protocol

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
        """Checkpoint both strategy streams with their replay basis."""
        base_state = self._base.get_state()
        return StrategyState(
            strategy_name="RLStrategyWrapper",
            iteration=self._iteration,
            rng_state={"python": _encode_python_random_state(self._rng.getstate())},
            model_state=base_state.model_state,
            metadata={
                "checkpoint_version": 1,
                "space": self._space.sobol_space_fingerprint(),
                "seed": self._config.seed,
                "schedule": self._schedule_identity(),
                "base_strategy": base_state.strategy_name,
                "base_state": base_state.to_artifact().decode("utf-8"),
            },
        )

    def set_state(self, state: StrategyState) -> None:
        """Restore a compatible wrapper and base without silently restarting."""
        if state.strategy_name != "RLStrategyWrapper":
            raise ValueError("RL checkpoint is incompatible: strategy identity changed")
        if (
            isinstance(state.iteration, bool)
            or not isinstance(state.iteration, int)
            or state.iteration < 0
        ):
            raise ValueError("RL checkpoint iteration must be a non-negative integer")
        if not isinstance(state.metadata, Mapping) or state.metadata.get("checkpoint_version") != 1:
            raise ValueError("RL checkpoint is incompatible: replay basis is missing")
        if state.metadata.get("space") != self._space.sobol_space_fingerprint():
            raise ValueError("RL checkpoint is incompatible: search space changed")
        if state.metadata.get("schedule") != self._schedule_identity():
            raise ValueError("RL checkpoint is incompatible: exploration schedule changed")
        seed = state.metadata.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("RL checkpoint seed must be an integer")
        if not isinstance(state.rng_state, Mapping):
            raise ValueError("RL checkpoint RNG state must be an object")
        decoded_rng = _decode_python_random_state(state.rng_state.get("python"))
        base_payload = state.metadata.get("base_state")
        if not isinstance(base_payload, str):
            raise ValueError("RL checkpoint base state is missing")
        try:
            base_state = StrategyState.from_artifact(base_payload.encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ValueError("RL checkpoint base state is invalid") from exc
        if (
            base_state.strategy_name != state.metadata.get("base_strategy")
            or base_state.model_state != state.model_state
        ):
            raise ValueError("RL checkpoint is incompatible: base identity changed")

        # The canonical base owner validates its own replay basis before the
        # wrapper's stream is changed. Restoring only the outer RNG would make
        # the first exploitation step continue a different experiment.
        self._base.set_state(base_state)
        self._rng.setstate(decoded_rng)
        self._config.seed = seed
        self._iteration = state.iteration

    def _schedule_identity(self) -> dict[str, Any]:
        schedule = self._config.exploration_schedule
        if type(schedule) is not LinearDecay:
            raise ValueError("RL checkpoint requires a replayable LinearDecay schedule")
        return {"type": "linear_decay", **asdict(schedule)}

    def _explore_random(self) -> PolicyCandidate:
        vector = tuple(self._rng.random() for _ in range(self._space.dim))
        return PolicyCandidate(
            params=self._space.denormalize(vector),
            params_normalized=vector,
            source_strategy="rl_exploration",
        )
