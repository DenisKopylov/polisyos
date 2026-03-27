"""Multi-start optimization: run from N perturbed initial points, select best."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np

from polisyos.foundry.calibration.hessian import HessianResult
from polisyos.foundry.calibration.identifiability import IdentifiabilityReport
from polisyos.ir.analytics.calibration import MultiStartConfig


@dataclass(frozen=True)
class SingleRunResult:
    """Result of a single optimization run."""

    loss: float
    params: list[object]  # optimized theta groups (JAX pytree leaves)
    hessian_result: HessianResult | None = None
    identifiability: IdentifiabilityReport | None = None
    loss_history: list[float] = field(default_factory=list)
    grad_norm_history: list[float] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MultiStartResult:
    """Aggregated result of multi-start optimization."""

    selected_idx: int
    runs: List[SingleRunResult]
    selection_reason: str


def select_best(
    runs: list[SingleRunResult],
    config: MultiStartConfig,
) -> tuple[int, str]:
    """Select the best run according to *config.selection*.

    Returns (selected_index, reason_string).
    """
    if not runs:
        raise ValueError("No runs to select from")
    if len(runs) == 1:
        return 0, "single_run"

    if config.selection == "best_identifiability":
        return _select_best_identifiability(runs)
    return _select_best_loss(runs, config.condition_threshold)


def _select_best_loss(
    runs: list[SingleRunResult],
    condition_threshold: float,
) -> tuple[int, str]:
    """Select run with min loss among those with acceptable Hessian condition."""
    # Filter runs with acceptable condition number
    acceptable: list[tuple[int, float]] = []
    for i, r in enumerate(runs):
        if r.hessian_result is not None and np.isfinite(r.hessian_result.condition_number):
            if r.hessian_result.condition_number < condition_threshold:
                acceptable.append((i, r.loss))
        else:
            # No Hessian info — accept by loss only
            acceptable.append((i, r.loss))

    if acceptable:
        best_idx, best_loss = min(acceptable, key=lambda t: t[1])
        return best_idx, f"best_loss={best_loss:.6g} (condition<{condition_threshold:.1g})"

    # All exceed threshold — fall back to absolute min loss
    best_idx = min(range(len(runs)), key=lambda i: runs[i].loss)
    return best_idx, f"best_loss={runs[best_idx].loss:.6g} (all condition>{condition_threshold:.1g})"


def _select_best_identifiability(
    runs: list[SingleRunResult],
) -> tuple[int, str]:
    """Select run with most identified parameters; break ties by condition then loss."""

    def _score(r: SingleRunResult) -> tuple[int, float, float]:
        n_id = r.identifiability.n_identified if r.identifiability else 0
        condition = (
            r.hessian_result.condition_number
            if r.hessian_result is not None and np.isfinite(r.hessian_result.condition_number)
            else float("inf")
        )
        return (-n_id, condition, r.loss)  # maximize identified, minimize condition, minimize loss

    best_idx = min(range(len(runs)), key=lambda i: _score(runs[i]))
    r = runs[best_idx]
    n_id = r.identifiability.n_identified if r.identifiability else 0
    condition = (
        r.hessian_result.condition_number
        if r.hessian_result is not None and np.isfinite(r.hessian_result.condition_number)
        else float("inf")
    )
    return best_idx, (
        f"best_identifiability: {n_id} identified, "
        f"condition={condition:.6g}, loss={r.loss:.6g}"
    )
