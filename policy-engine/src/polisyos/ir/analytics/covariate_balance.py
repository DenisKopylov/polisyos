"""CovariateBalanceReport — standardised mean difference diagnostics.

Captures per-variable SMD (standardised mean difference) and aggregate balance
statistics for use in the DiagnosticDashboard.  Populated by the causal engine
after weighting / matching, or computed directly from raw covariate data.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CovariateBalanceReport(BaseModel):
    """Per-variable and aggregate balance statistics after weighting or matching.

    Standard threshold: SMD > 0.1 indicates imbalance (Austin 2011).
    SMD > 0.2 is considered severe (Stuart 2010).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    variable_smd: dict[str, float] = Field(default_factory=dict)
    """Map from covariate name to its standardised mean difference (|treated_mean - control_mean| / pooled_sd)."""

    max_smd: float = 0.0
    """Maximum SMD across all variables."""

    mean_smd: float = 0.0
    """Mean SMD across all variables."""

    n_imbalanced: int = 0
    """Number of variables with SMD above the imbalance threshold."""

    imbalance_threshold: float = Field(default=0.1, ge=0.0)
    """SMD threshold above which a variable is considered imbalanced (default 0.1)."""

    passes_balance_check: bool = True
    """True when max_smd <= imbalance_threshold for all covariates."""

    weighted: bool = False
    """True when the SMDs were computed after IPW weighting or matching."""

    n_vars_total: int = 0
    """Total number of covariates assessed."""

    recommendations: tuple[str, ...] = ()
    """Human-readable recommendations derived from balance statistics."""


def compute_smd(
    X_treated: "Any",  # array-like (n_treated, p)
    X_control: "Any",  # array-like (n_control, p)
    *,
    column_names: list[str] | None = None,
    threshold: float = 0.1,
) -> CovariateBalanceReport:
    """Compute standardised mean differences between treated and control groups.

    Parameters
    ----------
    X_treated:
        Covariate matrix for treated units, shape (n_treated, p).
    X_control:
        Covariate matrix for control units, shape (n_control, p).
    column_names:
        Optional list of variable names.  If None, uses 'x0', 'x1', …
    threshold:
        SMD threshold for imbalance classification (default 0.1).
    """
    import numpy as np

    Xt = np.asarray(X_treated, dtype=float)
    Xc = np.asarray(X_control, dtype=float)

    if Xt.ndim == 1:
        Xt = Xt[:, None]
    if Xc.ndim == 1:
        Xc = Xc[:, None]

    p = Xt.shape[1]
    names = column_names if column_names and len(column_names) == p else [f"x{i}" for i in range(p)]

    smd_dict: dict[str, float] = {}
    for j, name in enumerate(names):
        mean_t = float(np.mean(Xt[:, j]))
        mean_c = float(np.mean(Xc[:, j]))
        var_t = float(np.var(Xt[:, j], ddof=1)) if Xt.shape[0] > 1 else 0.0
        var_c = float(np.var(Xc[:, j], ddof=1)) if Xc.shape[0] > 1 else 0.0
        pooled_sd = float(np.sqrt((var_t + var_c) / 2.0))
        smd = abs(mean_t - mean_c) / max(pooled_sd, 1e-12)
        smd_dict[name] = round(smd, 6)

    max_smd = max(smd_dict.values()) if smd_dict else 0.0
    mean_smd = sum(smd_dict.values()) / len(smd_dict) if smd_dict else 0.0
    n_imbalanced = sum(1 for v in smd_dict.values() if v > threshold)

    recommendations: list[str] = []
    if n_imbalanced > 0:
        worst = sorted(smd_dict.items(), key=lambda kv: -kv[1])[:3]
        worst_str = ", ".join(f"{k}={v:.3f}" for k, v in worst)
        recommendations.append(
            f"{n_imbalanced} variable(s) exceed SMD threshold {threshold}: {worst_str}. "
            "Consider additional matching/weighting variables."
        )
    if max_smd > 0.2:
        recommendations.append(
            f"Severe imbalance detected (max SMD={max_smd:.3f} > 0.2). "
            "Estimation may be sensitive to model misspecification."
        )

    return CovariateBalanceReport(
        variable_smd=smd_dict,
        max_smd=round(max_smd, 6),
        mean_smd=round(mean_smd, 6),
        n_imbalanced=n_imbalanced,
        imbalance_threshold=threshold,
        passes_balance_check=(n_imbalanced == 0),
        weighted=False,
        n_vars_total=p,
        recommendations=tuple(recommendations),
    )


__all__ = ["CovariateBalanceReport", "compute_smd"]
