"""Comparator governance protocol for fair head-to-head evaluation.

Ensures all estimators (PolicyOS internal and external baselines) are
compared under identical conditions: same preprocessing, seeds, compute
budget, and numerical sanity guards.

This module addresses the EconML DML LBIDD=167 906 numerical blow-up
scenario where an extreme estimate makes a comparison meaningless.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any


@dataclasses.dataclass(frozen=True)
class ComparatorGovernance:
    """Fair comparison protocol parameters."""

    shared_seed: int = 42
    shared_preprocessing: str = "standardize"  # "standardize" | "none"
    max_absolute_ate: float = 100.0
    max_absolute_rmse: float = 1e4
    shared_crossfit_folds: int = 5
    shared_bootstrap_draws: int = 200


@dataclasses.dataclass
class GovernedResult:
    """A result that has been post-processed under governance rules."""

    method_name: str
    ate_pred: float
    rmse: float
    ci_lower: float = float("nan")
    ci_upper: float = float("nan")
    coverage: float = float("nan")
    governed: bool = False
    fail_reason: str | None = None

    @property
    def failed(self) -> bool:
        return self.fail_reason is not None


def apply_governance(
    method_name: str,
    ate_pred: float,
    rmse: float,
    governance: ComparatorGovernance,
    *,
    ci_lower: float = float("nan"),
    ci_upper: float = float("nan"),
    coverage: float = float("nan"),
) -> GovernedResult:
    """Post-process a single method result under governance rules.

    Flags numerical blow-ups and extreme estimates as governed failures
    rather than treating them as legitimate (but terrible) results.
    This prevents misleading claims like "our method beats external by 100x"
    when the external method simply diverged numerically.
    """
    fail_reason: str | None = None

    if not math.isfinite(ate_pred):
        fail_reason = f"Non-finite ATE estimate: {ate_pred}"
    elif abs(ate_pred) > governance.max_absolute_ate:
        fail_reason = (
            f"Numerical blow-up: |ATE|={abs(ate_pred):.1f} "
            f"> governance threshold {governance.max_absolute_ate}"
        )

    if fail_reason is None and not math.isfinite(rmse):
        fail_reason = f"Non-finite RMSE: {rmse}"
    elif fail_reason is None and rmse > governance.max_absolute_rmse:
        fail_reason = (
            f"RMSE blow-up: {rmse:.1f} > governance threshold {governance.max_absolute_rmse}"
        )

    return GovernedResult(
        method_name=method_name,
        ate_pred=float("nan") if fail_reason else ate_pred,
        rmse=float("nan") if fail_reason else rmse,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        coverage=coverage,
        governed=fail_reason is not None,
        fail_reason=fail_reason,
    )


def governance_summary(results: list[GovernedResult]) -> dict[str, Any]:
    """Produce a summary of governed vs. ungoverned results."""
    total = len(results)
    governed = [r for r in results if r.governed]
    valid = [r for r in results if not r.governed]
    return {
        "total_methods": total,
        "valid_methods": len(valid),
        "governed_out": len(governed),
        "governed_reasons": {r.method_name: r.fail_reason for r in governed},
        "valid_method_names": [r.method_name for r in valid],
    }
