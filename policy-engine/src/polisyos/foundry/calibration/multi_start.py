"""Multi-start optimization: run from N perturbed initial points, select best."""

from __future__ import annotations

from dataclasses import dataclass, field

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
    runs: list[SingleRunResult]
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
    if not any(_finite_loss(r) is not None for r in runs):
        raise ValueError("No run has a finite loss")
    if len(runs) == 1:
        return 0, "single_run"

    if config.selection == "best_identifiability":
        return _select_best_identifiability(runs)
    return _select_best_loss(runs, config.condition_threshold)


def _finite_loss(run: SingleRunResult) -> float | None:
    """Return a finite scalar loss, or ``None`` for malformed results."""
    try:
        loss = float(run.loss)
    except (TypeError, ValueError, OverflowError):
        return None
    return loss if np.isfinite(loss) else None


def _condition_status(run: SingleRunResult, condition_threshold: float) -> str:
    """Classify Hessian evidence without collapsing missing and known failures."""
    if run.hessian_result is None:
        return "missing"
    try:
        condition = float(run.hessian_result.condition_number)
    except (TypeError, ValueError, OverflowError):
        return "nonfinite"
    if condition == float("inf"):
        return "inf"
    if not np.isfinite(condition):
        return "nonfinite"
    if condition < 0.0:
        return "invalid"
    if condition < condition_threshold:
        return "acceptable"
    return "finite_large"


def _select_best_loss(
    runs: list[SingleRunResult],
    condition_threshold: float,
) -> tuple[int, str]:
    """Select run with min loss among those with acceptable Hessian condition."""
    finite_runs = [
        (i, loss)
        for i, run in enumerate(runs)
        if (loss := _finite_loss(run)) is not None
    ]
    if not finite_runs:
        raise ValueError("No run has a finite loss")

    # A missing Hessian is an explicitly limited loss-only mode.  A present
    # non-finite or over-threshold Hessian is known bad evidence and must not
    # be silently reclassified as missing.
    acceptable: list[tuple[int, float]] = []
    for index, loss in finite_runs:
        status = _condition_status(runs[index], condition_threshold)
        if status in {"acceptable", "missing"}:
            acceptable.append((index, loss))

    if acceptable:
        best_idx, best_loss = min(acceptable, key=lambda t: t[1])
        statuses = {_condition_status(runs[index], condition_threshold) for index, _ in acceptable}
        if statuses == {"missing"}:
            reason = "missing_hessian"
        elif statuses == {"acceptable"}:
            reason = f"condition<{condition_threshold:.1g}"
        else:
            reason = f"condition<{condition_threshold:.1g} or hessian_missing"
        return best_idx, f"best_loss={best_loss:.6g} ({reason})"

    # Every finite-loss candidate is diagnostic-limited.  Preserve the
    # computed result, but say exactly which limitation forced the fallback.
    best_idx, best_loss = min(finite_runs, key=lambda t: t[1])
    statuses = sorted(
        {_condition_status(runs[index], condition_threshold) for index, _ in finite_runs}
    )
    return (
        best_idx,
        f"best_loss={best_loss:.6g} (fallback: condition_status={','.join(statuses)})",
    )


def _select_best_identifiability(
    runs: list[SingleRunResult],
) -> tuple[int, str]:
    """Select run with most identified parameters; break ties by condition then loss."""

    finite_runs = [
        (index, loss)
        for index, run in enumerate(runs)
        if (loss := _finite_loss(run)) is not None
    ]
    if not finite_runs:
        raise ValueError("No run has a finite loss")

    def _score(item: tuple[int, float]) -> tuple[int, float, float, int]:
        index, loss = item
        r = runs[index]
        n_id = r.identifiability.n_identified if r.identifiability else 0
        condition = (
            float(r.hessian_result.condition_number)
            if r.hessian_result is not None
            and _finite_condition(r.hessian_result.condition_number)
            else float("inf")
        )
        return (-n_id, condition, loss, index)  # maximize identified, then minimize condition/loss

    best_idx = min(finite_runs, key=_score)[0]
    r = runs[best_idx]
    n_id = r.identifiability.n_identified if r.identifiability else 0
    condition = (
        float(r.hessian_result.condition_number)
        if r.hessian_result is not None
        and _finite_condition(r.hessian_result.condition_number)
        else float("inf")
    )
    condition_status = _condition_status(r, float("inf"))
    loss = _finite_loss(r)
    assert loss is not None  # selected from finite_runs above
    return best_idx, (
        f"best_identifiability: {n_id} identified, condition={condition:.6g}, "
        f"loss={loss:.6g}, condition_status={condition_status}"
    )


def _finite_condition(value: object) -> bool:
    """Return whether a condition number is a finite scalar."""
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError, OverflowError):
        return False
