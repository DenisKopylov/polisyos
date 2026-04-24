"""Ranking stability analysis for sensitivity indices."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .designs import SensitivityPlan


@dataclass
class StabilityReport:
    """Report on parameter ranking stability."""

    rank_stability_score: float = 0.0
    unstable_parameters: list[str] = field(default_factory=list)
    n_bootstrap: int = 0
    rank_variance: dict[str, float] = field(default_factory=dict)


class RankingStabilityChecker:
    """Assess ranking stability via bootstrap resampling.

    For each bootstrap sample, re-computes sensitivity indices and
    checks whether the parameter ranking remains consistent.
    """

    def __init__(self, *, n_bootstrap: int = 50, seed: int = 42) -> None:
        self._n_bootstrap = max(n_bootstrap, 5)
        self._seed = seed

    def check(
        self,
        plan: SensitivityPlan,
        samples: np.ndarray,
        outputs: np.ndarray,
    ) -> StabilityReport:
        """Compute ranking stability via bootstrap.

        Returns a ``StabilityReport`` with a score in [0, 1] where 1
        means perfectly stable rankings across all bootstrap samples.
        """
        from .analysis import analyze_sensitivity

        if samples.shape[0] < 10:
            return StabilityReport(
                rank_stability_score=0.0,
                unstable_parameters=list(plan.parameter_specs[0].name for _ in []),
                n_bootstrap=0,
            )

        rng = np.random.default_rng(self._seed)
        n = samples.shape[0]
        names = [p.name for p in plan.parameter_specs]

        # Collect rankings from bootstrap samples
        rank_positions: dict[str, list[int]] = {name: [] for name in names}

        for _ in range(self._n_bootstrap):
            idx = rng.choice(n, size=n, replace=True)
            boot_samples = samples[idx]
            boot_outputs = outputs[idx]

            try:
                result = analyze_sensitivity(plan, boot_samples, boot_outputs)
                for pos, name in enumerate(result.ranking):
                    rank_positions[name].append(pos)
            except Exception:
                continue

        if not any(rank_positions[names[0]]):
            return StabilityReport(
                rank_stability_score=0.0,
                n_bootstrap=0,
            )

        # Compute rank variance per parameter
        rank_variance: dict[str, float] = {}
        unstable: list[str] = []
        max_possible_var = (len(names) - 1) ** 2 / 4.0  # max variance of uniform over ranks

        for name in names:
            positions = rank_positions[name]
            if len(positions) < 2:
                rank_variance[name] = float("inf")
                unstable.append(name)
                continue
            var = float(np.var(positions))
            rank_variance[name] = var
            # Consider unstable if variance > 25% of max possible
            if max_possible_var > 0 and var > 0.25 * max_possible_var:
                unstable.append(name)

        # Overall stability score: 1 - mean_normalized_variance
        if max_possible_var > 0:
            mean_normalized = np.mean(
                [min(v / max_possible_var, 1.0) for v in rank_variance.values()]
            )
            score = 1.0 - float(mean_normalized)
        else:
            score = 1.0

        return StabilityReport(
            rank_stability_score=max(score, 0.0),
            unstable_parameters=unstable,
            n_bootstrap=self._n_bootstrap,
            rank_variance=rank_variance,
        )


__all__ = [
    "RankingStabilityChecker",
    "StabilityReport",
]
