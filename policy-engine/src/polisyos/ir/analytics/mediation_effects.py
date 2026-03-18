"""Mediation effects IR types.

Covers:
1. **Natural Direct Effect (NDE)** and **Natural Indirect Effect (NIE)**
   via semiparametric cross-fitting (Tchetgen Tchetgen & Shpitser 2012).

2. **Path-Specific Effects (PSE)**
   via the Avin-Shpitser-Pearl recanting witness criterion (2005).

3. **MediationDecomposition** — unified result container for NDE/NIE/CDE.

All models: ``ConfigDict(extra="forbid", frozen=True)``, ``schema_version="1.0"``.

References
----------
Tchetgen Tchetgen, E.J. & Shpitser, I. (2012). Semiparametric Theory for
    Causal Mediation Analysis. Ann. Stat.
Avin, C., Shpitser, I. & Pearl, J. (2005). Identifiability of Path-Specific
    Effects. IJCAI.
Pearl, J. (2001). Direct and Indirect Effects. UAI.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PathSpecificQuery(BaseModel):
    """Query specification for path-specific effects.

    Identifies which causal paths from ``treatment`` to ``outcome`` are
    "active" (allowed to vary) vs. "fixed" (blocked to their natural values
    under a reference treatment level).

    For NDE (Natural Direct Effect):
        - active_paths: [("treatment", "outcome")]  ← direct path only
        - fixed_paths: any mediator paths

    For NIE (Natural Indirect Effect):
        - active_paths: all paths through mediators
        - fixed_paths: ["treatment", "outcome"] ← direct path
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"

    treatment: str
    """Treatment variable name."""

    outcome: str
    """Outcome variable name."""

    mediators: tuple[str, ...] = ()
    """Mediator variable(s) on the causal path."""

    active_paths: tuple[tuple[str, ...], ...] = ()
    """Paths that are allowed to vary with treatment.

    Each path is a tuple of variable names from treatment to outcome.
    Empty tuple means all paths are active (= ATE estimand).
    """

    fixed_paths: tuple[tuple[str, ...], ...] = ()
    """Paths that are blocked (frozen to reference-treatment levels)."""

    reference_treatment: float = 0.0
    """Reference (control) value of treatment."""

    active_treatment: float = 1.0
    """Active (treated) value of treatment."""

    metadata: dict[str, Any] = Field(default_factory=dict)


class MediationDecomposition(BaseModel):
    """Full mediation decomposition: NDE, NIE, total effect.

    Estimates are obtained via cross-fitted EIF (Tchetgen Tchetgen &
    Shpitser 2012, Eq. 3) which is doubly-robust and locally efficient.

    Decomposition identity:
        ATE = NDE + NIE

    In practice: nde + nie ≈ total_effect (small discrepancy from
    finite-sample cross-fitting noise is normal).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"

    # Core estimates
    nde: float
    """Natural Direct Effect: E[Y(1, M(0))] - E[Y(0, M(0))]."""

    nie: float
    """Natural Indirect Effect: E[Y(1, M(1))] - E[Y(1, M(0))]."""

    total_effect: float
    """ATE = NDE + NIE."""

    cde: float | None = None
    """Controlled Direct Effect at mediator_reference_level (optional)."""

    # Standard errors
    nde_se: float | None = None
    """Standard error of NDE estimate."""

    nie_se: float | None = None
    """Standard error of NIE estimate."""

    # Confidence intervals (95%)
    nde_ci: tuple[float, float] | None = None
    """95% Wald CI for NDE."""

    nie_ci: tuple[float, float] | None = None
    """95% Wald CI for NIE."""

    # Estimation metadata
    n_folds: int = 2
    """Number of cross-fitting folds used."""

    n_obs: int = 0
    """Number of observations."""

    estimation_method: str = "eif_cross_fit"
    """Estimation approach used: ``'eif_cross_fit'`` | ``'ols_baron_kenny'``."""

    # Sensitivity
    sensitivity_rho_range: tuple[float, ...] | None = None
    """ρ values used in sensitivity analysis, if any."""

    sensitivity_nde: tuple[float, ...] | None = None
    """Sensitivity-corrected NDE for each ρ in ``sensitivity_rho_range``."""

    sensitivity_nie: tuple[float, ...] | None = None
    """Sensitivity-corrected NIE for each ρ in ``sensitivity_rho_range``."""

    # Interpretation helpers
    proportion_mediated: float | None = None
    """NIE / ATE — fraction of total effect via mediator (None if ATE ≈ 0)."""

    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "PathSpecificQuery",
    "MediationDecomposition",
]
