"""Ranking stability analysis for sensitivity indices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from .designs import SensitivityMethod, SensitivityPlan, _admit_sensitivity_plan
from .morris_geometry import _validate_morris_plan_samples


@dataclass
class StabilityReport:
    """Report on parameter ranking stability."""

    rank_stability_score: float = 0.0
    unstable_parameters: list[str] = field(default_factory=list)
    n_bootstrap: int = 0
    rank_variance: dict[str, float] = field(default_factory=dict)
    status: Literal["ok", "limited", "not_evaluated", "unsupported"] = "not_evaluated"
    reason: str | None = None
    requested_bootstrap: int = 0
    attempted_bootstrap: int = 0
    failed_bootstrap: int = 0
    input_run_count: int = 0
    replicate_outcomes: list[str] = field(default_factory=list)


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
        plan = _admit_sensitivity_plan(plan)
        from .analysis import _prepare_analysis_inputs, analyze_sensitivity

        if plan.method != SensitivityMethod.MORRIS:
            return StabilityReport(
                status="unsupported",
                reason="estimator_specific_structured_bootstrap_not_implemented",
                requested_bootstrap=self._n_bootstrap,
                input_run_count=int(samples.shape[0]),
            )

        if samples.shape[0] < 10:
            return StabilityReport(
                rank_stability_score=0.0,
                n_bootstrap=0,
                reason="insufficient_input_runs",
                requested_bootstrap=self._n_bootstrap,
                input_run_count=int(samples.shape[0]),
            )

        rng = np.random.default_rng(self._seed)
        if plan.method == SensitivityMethod.MORRIS:
            _validate_morris_plan_samples(plan, samples)
            prepared = _prepare_analysis_inputs(plan, samples, outputs)
            if prepared.failed_runs:
                raise ValueError(
                    "Morris stability requires complete successful trajectories; "
                    "failed-run selection or imputation is not established for ranking stability"
                )
        # Morris rows are connected points, not independent observations.
        # Preserve every original trajectory's order inside each replicate.
        block_size = plan.num_parameters + 1 if plan.method == SensitivityMethod.MORRIS else 1
        if samples.shape[0] % block_size:
            raise ValueError("Morris stability requires complete trajectory blocks")
        n_blocks = samples.shape[0] // block_size
        names = [p.name for p in plan.parameter_specs]

        # Collect rankings from bootstrap samples
        rank_positions: dict[str, list[int]] = {name: [] for name in names}
        outcomes: list[str] = []

        for _ in range(self._n_bootstrap):
            block_ids = rng.choice(n_blocks, size=n_blocks, replace=True)
            idx = (block_ids[:, None] * block_size + np.arange(block_size)).reshape(-1)
            boot_samples = samples[idx]
            boot_outputs = outputs[idx]

            try:
                result = analyze_sensitivity(plan, boot_samples, boot_outputs)
                for pos, name in enumerate(result.ranking):
                    rank_positions[name].append(pos)
                outcomes.append("success")
            except Exception as exc:
                outcomes.append(f"failed:{type(exc).__name__}:{exc}")
                continue

        successful_replicates = outcomes.count("success")
        accounting = {
            "requested_bootstrap": self._n_bootstrap,
            "attempted_bootstrap": len(outcomes),
            "failed_bootstrap": len(outcomes) - successful_replicates,
            "input_run_count": int(samples.shape[0]),
            "replicate_outcomes": outcomes,
        }

        if not rank_positions[names[0]]:
            return StabilityReport(
                rank_stability_score=0.0,
                n_bootstrap=0,
                reason="no_successful_bootstrap_replicates",
                **accounting,
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
            n_bootstrap=successful_replicates,
            rank_variance=rank_variance,
            status="ok" if successful_replicates == self._n_bootstrap else "limited",
            reason=(
                None
                if successful_replicates == self._n_bootstrap
                else "ranking_conditional_on_successful_bootstrap_replicates"
            ),
            **accounting,
        )


__all__ = [
    "RankingStabilityChecker",
    "StabilityReport",
]
