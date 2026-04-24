"""Grid-search baseline strategy."""

from __future__ import annotations

import itertools

from polisyos.scientist.search.strategies.base import BaseSearchStrategy
from polisyos.scientist.search.strategies.errors import StrategyExhaustedError
from polisyos.scientist.search.strategies.types import (
    Evaluation,
    ParameterType,
    PolicyCandidate,
)


class GridSearchStrategy(BaseSearchStrategy):
    """Finite deterministic grid search."""

    def __init__(
        self,
        space,
        seed: int = 42,
        points_per_dim: int = 5,
        max_candidates: int = 5000,
    ):
        super().__init__(space=space, seed=seed)
        if points_per_dim < 2:
            raise ValueError("points_per_dim must be >= 2")
        self._points_per_dim = points_per_dim
        self._max_candidates = max_candidates
        self._grid_params = self._build_grid_params()
        self._cursor = 0

    def suggest(
        self,
        evaluations: list[Evaluation],
        pending: list[PolicyCandidate] | None = None,
    ) -> PolicyCandidate:
        del evaluations, pending
        if self._cursor >= len(self._grid_params):
            raise StrategyExhaustedError(
                f"Grid exhausted after {len(self._grid_params)} candidates"
            )
        params = self._grid_params[self._cursor]
        self._cursor += 1
        vector = self._space.normalize(params)
        return PolicyCandidate(
            params=params,
            params_normalized=vector,
            source_strategy="grid",
        )

    def get_state(self):
        state = super().get_state()
        state.metadata = {
            **state.metadata,
            "cursor": self._cursor,
            "points_per_dim": self._points_per_dim,
        }
        return state

    def set_state(self, state):
        super().set_state(state)
        self._cursor = int(state.metadata.get("cursor", 0))

    def _build_grid_params(self) -> list[dict[str, object]]:
        per_dim_values: list[list[object]] = []
        names: list[str] = []
        for bound in self._space.bounds:
            names.append(bound.name)
            if bound.dtype == ParameterType.CATEGORICAL:
                assert bound.categories is not None
                per_dim_values.append(list(bound.categories))
                continue
            if bound.dtype == ParameterType.INTEGER:
                values = [
                    int(
                        round(
                            bound.lower
                            + i * (bound.upper - bound.lower) / (self._points_per_dim - 1)
                        )
                    )
                    for i in range(self._points_per_dim)
                ]
                dedup = sorted(set(values))
                per_dim_values.append([int(v) for v in dedup])
                continue
            per_dim_values.append(
                [
                    float(
                        bound.lower + i * (bound.upper - bound.lower) / (self._points_per_dim - 1)
                    )
                    for i in range(self._points_per_dim)
                ]
            )

        product_iter = itertools.product(*per_dim_values)
        output: list[dict[str, object]] = []
        for combo in product_iter:
            output.append({name: value for name, value in zip(names, combo)})
            if len(output) >= self._max_candidates:
                break
        return output
