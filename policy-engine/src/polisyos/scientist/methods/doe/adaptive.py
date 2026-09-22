"""Adaptive sensitivity sampling with convergence checking."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from .designs import SensitivityMethod, SensitivityPlan, SensitivityResult


@dataclass(frozen=True)
class ConvergenceConfig:
    """Configuration for adaptive sampling convergence."""

    max_rounds: int = 5
    ranking_stability_threshold: float = 0.9
    index_rtol: float = 0.05
    trajectory_step: int = 5

    def __post_init__(self) -> None:
        if self.max_rounds < 1:
            raise ValueError("max_rounds must be at least 1")
        if self.trajectory_step < 1:
            raise ValueError("trajectory_step must be at least 1")


@dataclass
class AdaptiveRound:
    """Record of a single adaptive sampling round."""

    round_number: int
    n_trajectories: int
    ranking: list[str]
    stability_score: float = 0.0


@dataclass
class AdaptiveResult:
    """Result of adaptive sensitivity sampling."""

    final_result: SensitivityResult
    rounds: list[AdaptiveRound] = field(default_factory=list)
    converged: bool = False
    total_evaluations: int = 0
    stop_reason: str | None = None


class AdaptiveSampler:
    """Iteratively increases n_trajectories until ranking stabilizes.

    At each round the sampler runs sensitivity analysis with increasing
    ``n_trajectories``.  Convergence is declared when the parameter ranking
    is stable across consecutive rounds (Kendall tau-b >= threshold)
    or when the sensitivity indices change by less than ``index_rtol``.
    """

    def __init__(
        self,
        plan: SensitivityPlan,
        convergence: ConvergenceConfig | None = None,
    ) -> None:
        self._plan = plan
        self._conv = convergence or ConvergenceConfig()

    def run(
        self,
        evaluator: Callable[[np.ndarray], np.ndarray],
    ) -> AdaptiveResult:
        """Run adaptive sampling with *evaluator* as the black-box function.

        *evaluator* takes a 2-D sample array ``(n_samples, n_params)`` and
        returns a 1-D output array ``(n_samples,)``.
        """
        from .analysis import analyze_sensitivity
        from .sampling import generate_sensitivity_samples

        rounds: list[AdaptiveRound] = []
        prev_ranking: list[str] | None = None
        prev_indices: dict[str, float] | None = None
        total_evals = 0
        last_result: SensitivityResult | None = None
        stop_reason: str | None = None

        current_n = self._plan.n_trajectories

        for round_num in range(1, self._conv.max_rounds + 1):
            # Create a plan copy with updated n_trajectories
            plan_dict = self._plan.model_dump()
            plan_dict["n_trajectories"] = current_n
            # Preserve the caller's explicit permission.  Constructing the
            # round plan keeps the existing SensitivityPlan guardrail as the
            # single source of truth for estimated-run admission.
            plan_dict["allow_large_run"] = self._plan.allow_large_run
            if (
                not self._plan.allow_large_run
                and self._plan.estimated_runs_for(current_n) > self._plan.max_estimated_runs
            ):
                if last_result is None:
                    raise ValueError(
                        "SensitivityPlan estimated_runs exceeds max_estimated_runs. "
                        "Increase max_estimated_runs or set allow_large_run=true to override."
                    )
                stop_reason = "max_estimated_runs_exceeded"
                break
            round_plan = SensitivityPlan(**plan_dict)

            try:
                samples = generate_sensitivity_samples(round_plan)
                outputs = evaluator(samples)
                total_evals += len(outputs)
                result = analyze_sensitivity(round_plan, samples, outputs)
            except Exception as exc:
                if last_result is None:
                    raise
                stop_reason = f"adaptive_round_failed:{type(exc).__name__}"
                break
            last_result = result

            current_indices = self._extract_primary_indices(result)
            stability = self._compute_stability(
                prev_ranking,
                result.ranking,
                prev_indices,
                current_indices,
            )

            rnd = AdaptiveRound(
                round_number=round_num,
                n_trajectories=current_n,
                ranking=list(result.ranking),
                stability_score=stability,
            )
            rounds.append(rnd)

            if stability >= self._conv.ranking_stability_threshold and round_num > 1:
                return AdaptiveResult(
                    final_result=result,
                    rounds=rounds,
                    converged=True,
                    total_evaluations=total_evals,
                )

            prev_ranking = result.ranking
            prev_indices = current_indices
            current_n += self._conv.trajectory_step

        if last_result is None:
            raise RuntimeError("AdaptiveSampler completed without a result")
        if stop_reason is None:
            stop_reason = "max_rounds_reached"

        return AdaptiveResult(
            final_result=last_result,
            rounds=rounds,
            converged=False,
            total_evaluations=total_evals,
            stop_reason=stop_reason,
        )

    def _extract_primary_indices(self, result: SensitivityResult) -> dict[str, float]:
        if result.method == SensitivityMethod.MORRIS:
            return dict(result.mu_star)
        return dict(result.st) if result.st else dict(result.s1)

    def _compute_stability(
        self,
        prev_ranking: list[str] | None,
        curr_ranking: list[str],
        prev_indices: dict[str, float] | None,
        curr_indices: dict[str, float],
    ) -> float:
        if prev_ranking is None or prev_indices is None:
            return 0.0

        # Ranking stability via Kendall-like overlap metric
        n = len(curr_ranking)
        if n == 0:
            return 1.0

        concordant = 0
        total = 0
        for i in range(n):
            for j in range(i + 1, n):
                total += 1
                # Check if relative order is preserved
                prev_pos_i = (
                    prev_ranking.index(curr_ranking[i]) if curr_ranking[i] in prev_ranking else n
                )
                prev_pos_j = (
                    prev_ranking.index(curr_ranking[j]) if curr_ranking[j] in prev_ranking else n
                )
                if prev_pos_i < prev_pos_j:
                    concordant += 1

        rank_stability = concordant / total if total > 0 else 1.0

        # Index stability via relative tolerance
        index_stable_count = 0
        for name in curr_indices:
            if name in prev_indices and prev_indices[name] != 0:
                rel_change = abs(curr_indices[name] - prev_indices[name]) / abs(prev_indices[name])
                if rel_change < self._conv.index_rtol:
                    index_stable_count += 1
            elif name in prev_indices and prev_indices[name] == 0 and curr_indices[name] == 0:
                index_stable_count += 1

        index_stability = index_stable_count / len(curr_indices) if curr_indices else 1.0

        return 0.6 * rank_stability + 0.4 * index_stability


__all__ = [
    "AdaptiveResult",
    "AdaptiveRound",
    "AdaptiveSampler",
    "ConvergenceConfig",
]
