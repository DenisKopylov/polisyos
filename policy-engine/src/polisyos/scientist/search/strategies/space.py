"""Search-space definition and parameter normalization helpers."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from polisyos.scientist.search.strategies._deps import require_torch, torch
from polisyos.scientist.search.strategies.types import (
    NormalizedVector,
    ParameterBounds,
    ParameterType,
)


@dataclass(slots=True)
class SearchSpace:
    """
    Multi-dimensional search space with normalization support.

    Categorical parameters are expanded to one-hot dimensions for surrogate compatibility.
    """

    bounds: list[ParameterBounds] = field(default_factory=list)
    _expanded: list[tuple[ParameterBounds, int | None]] = field(
        init=False,
        repr=False,
        default_factory=list,
    )

    def __post_init__(self) -> None:
        if not self.bounds:
            raise ValueError("SearchSpace must contain at least one parameter")
        self._expanded.clear()
        for bound in self.bounds:
            if bound.dtype == ParameterType.CATEGORICAL:
                assert bound.categories is not None
                for idx in range(len(bound.categories)):
                    self._expanded.append((bound, idx))
            else:
                self._expanded.append((bound, None))

    @property
    def dim(self) -> int:
        return len(self._expanded)

    @property
    def names(self) -> list[str]:
        output: list[str] = []
        for bound, cat_idx in self._expanded:
            if cat_idx is None:
                output.append(bound.name)
            else:
                output.append(f"{bound.name}__{cat_idx}")
        return output

    def normalize(self, params: dict[str, Any]) -> NormalizedVector:
        values: list[float] = []
        for bound in self.bounds:
            if bound.dtype == ParameterType.CATEGORICAL:
                assert bound.categories is not None
                raw = params.get(bound.name)
                if raw not in bound.categories:
                    raise ValueError(
                        f"Unknown category '{raw}' for parameter '{bound.name}'. "
                        f"Allowed: {bound.categories}"
                    )
                values.extend(
                    1.0 if raw == candidate else 0.0 for candidate in bound.categories
                )
                continue
            raw = float(params.get(bound.name, bound.lower))
            if bound.log_scale or bound.dtype == ParameterType.LOG_CONTINUOUS:
                log_lower = math.log(bound.lower)
                log_upper = math.log(bound.upper)
                raw = min(max(raw, bound.lower), bound.upper)
                raw_norm = (math.log(raw) - log_lower) / (log_upper - log_lower)
            else:
                raw_clipped = min(max(raw, bound.lower), bound.upper)
                raw_norm = (raw_clipped - bound.lower) / (bound.upper - bound.lower)
            values.append(float(min(max(raw_norm, 0.0), 1.0)))
        return tuple(values)

    def denormalize(self, vector: NormalizedVector) -> dict[str, Any]:
        if len(vector) != self.dim:
            raise ValueError(f"Expected vector length {self.dim}, got {len(vector)}")

        params: dict[str, Any] = {}
        cursor = 0
        for bound in self.bounds:
            if bound.dtype == ParameterType.CATEGORICAL:
                assert bound.categories is not None
                chunk = vector[cursor : cursor + len(bound.categories)]
                if not chunk:
                    raise ValueError(f"Empty categorical chunk for '{bound.name}'")
                idx = max(range(len(chunk)), key=lambda i: chunk[i])
                params[bound.name] = bound.categories[idx]
                cursor += len(bound.categories)
                continue

            normalized = float(min(max(vector[cursor], 0.0), 1.0))
            if bound.log_scale or bound.dtype == ParameterType.LOG_CONTINUOUS:
                log_lower = math.log(bound.lower)
                log_upper = math.log(bound.upper)
                value = math.exp(log_lower + normalized * (log_upper - log_lower))
            else:
                value = bound.lower + normalized * (bound.upper - bound.lower)
            if bound.dtype == ParameterType.INTEGER:
                params[bound.name] = int(round(value))
            else:
                params[bound.name] = float(value)
            cursor += 1
        return params

    def sample_sobol(self, n_samples: int, seed: int = 42) -> list[NormalizedVector]:
        if n_samples <= 0:
            return []

        if torch is not None:  # pragma: no branch
            local_torch = require_torch()
            sobol_engine = local_torch.quasirandom.SobolEngine(
                self.dim, scramble=True, seed=seed
            )
            tensor = sobol_engine.draw(n_samples).tolist()
            return [tuple(float(v) for v in row) for row in tensor]

        try:
            from scipy.stats.qmc import Sobol  # type: ignore[import-not-found]

            qmc = Sobol(d=self.dim, scramble=True, seed=seed)
            samples = qmc.random(n=n_samples).tolist()
            return [tuple(float(v) for v in row) for row in samples]
        except Exception:
            rng = random.Random(seed)
            return [
                tuple(rng.random() for _ in range(self.dim))
                for _ in range(n_samples)
            ]

    def to_botorch_bounds(self) -> Any:
        local_torch = require_torch()
        return local_torch.stack(
            [
                local_torch.zeros(self.dim, dtype=local_torch.float64),
                local_torch.ones(self.dim, dtype=local_torch.float64),
            ],
            dim=0,
        )
