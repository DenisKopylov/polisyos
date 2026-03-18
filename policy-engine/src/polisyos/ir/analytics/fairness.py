"""Causal Fairness IR types.

Implements the TV = DE + IE + SE decomposition (Plecko & Bareinboim 2022),
path-specific fairness criteria (Zhang & Bareinboim 2018), and counterfactual
fairness (Kusner et al. 2017).

All models: ``ConfigDict(extra="forbid", frozen=True)``, ``schema_version="1.0"``.

References
----------
Plecko, D. & Bareinboim, E. (2022). Causal Fairness Analysis. ICML.
Zhang, J. & Bareinboim, E. (2018). Fairness in Decision-Making—The Causal
    Explanation Formula. AAAI.
Kusner, M.J., Loftus, J., Russell, C. & Silva, R. (2017). Counterfactual
    Fairness. NeurIPS.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FairnessDecomposition(BaseModel):
    """TV = DE + IE + SE decomposition (Plecko & Bareinboim 2022, Theorem 1).

    The total observational disparity (TV) between protected groups is
    decomposed into three orthogonal causal components:

    - **DE** (Direct Effect): direct causal path A → Y, bypassing mediators
    - **IE** (Indirect Effect): causal path through mediators A → M → Y
    - **SE** (Spurious Effect): non-causal association via common causes U → A, U → Y

    Identity: TV = DE + IE + SE  (approximately; ``decomposition_residual`` measures fit)
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"

    tv: float
    """Total Variation: E[Y|A=a1] - E[Y|A=a0]. Raw observational disparity."""

    direct_effect: float
    """Counterfactual Direct Effect (Ctf-DE): disparity along direct path A → Y."""

    indirect_effect: float
    """Counterfactual Indirect Effect (Ctf-IE): disparity via mediators A → M → Y."""

    spurious_effect: float
    """Spurious (confounded) component: non-causal association via shared causes."""

    decomposition_residual: float
    """Absolute residual |TV - DE - IE - SE|; near zero for well-specified models."""

    # 95% Confidence intervals
    tv_ci: tuple[float, float] | None = None
    """95% CI for Total Variation."""

    de_ci: tuple[float, float] | None = None
    """95% CI for Direct Effect."""

    ie_ci: tuple[float, float] | None = None
    """95% CI for Indirect Effect."""

    se_ci: tuple[float, float] | None = None
    """95% CI for Spurious Effect (propagated from TV - DE - IE)."""

    n_obs: int
    """Number of observations used in estimation."""

    protected_attribute: str
    """Name of the protected (sensitive) attribute."""

    outcome: str
    """Name of the outcome (decision) variable."""

    mediators: tuple[str, ...] = ()
    """Mediator variables used in indirect effect estimation."""

    estimation_method: str
    """Estimation approach: 'tv_decomposition' | 'path_specific' | 'counterfactual'."""

    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_cis(self) -> "FairnessDecomposition":
        for name, ci in [
            ("tv_ci", self.tv_ci),
            ("de_ci", self.de_ci),
            ("ie_ci", self.ie_ci),
            ("se_ci", self.se_ci),
        ]:
            if ci is not None and ci[0] > ci[1] + 1e-12:
                raise ValueError(f"{name}: lower bound {ci[0]:.4f} > upper bound {ci[1]:.4f}")
        return self


class CausalFairnessReport(BaseModel):
    """Full causal fairness audit result.

    Combines the TV = DE + IE + SE decomposition with path-level fairness
    verdicts and a counterfactual fairness assessment.

    References
    ----------
    Plecko & Bareinboim (2022); Zhang & Bareinboim (2018); Kusner et al. (2017).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"

    decomposition: FairnessDecomposition
    """TV = DE + IE + SE causal decomposition of the disparity."""

    counterfactual_fairness_satisfied: bool
    """True if the counterfactual gap |Ŷ(A=a) - Ŷ(A=a')| is below threshold."""

    path_specific_fairness: dict[str, bool]
    """Mapping path_label → True if |PSE(path)| < threshold (Zhang & Bareinboim 2018)."""

    direct_discrimination: float
    """|DE| — magnitude of direct causal discrimination."""

    indirect_discrimination: float
    """|IE| — magnitude of mediated (indirect) discrimination."""

    primary_unfair_pathway: str | None
    """Label of the largest-magnitude unfair pathway; None if none detected."""

    recommendation: str
    """Human-readable finding summarising the fairness status and key drivers."""

    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "FairnessDecomposition",
    "CausalFairnessReport",
]
