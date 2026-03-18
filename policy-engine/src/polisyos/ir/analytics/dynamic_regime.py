"""IR models for dynamic treatment regimes and longitudinal causal inference.

Covers g-computation results, SNMM (g-estimation), DTR (Q/A-learning, OWL),
off-policy evaluation, and causal bandits.

References:
    Robins (1986). A new approach to causal inference in mortality studies.
    Hernán & Robins (2020). Causal Inference: What If. Chapman & Hall.
    Murphy (2003). Optimal dynamic treatment regimes. JRSS-B.
    Lattimore, Munos & Szepesvári (2016). Causal bandits. NeurIPS.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RegimeRule(str, Enum):
    """How a dynamic treatment regime assigns treatment at each time point."""

    ALWAYS_TREAT = "always_treat"
    NEVER_TREAT = "never_treat"
    THRESHOLD = "threshold"  # treat if covariate_t > threshold_value
    LINEAR_BLIP = "linear_blip"  # treat if blip(H_t) > 0


class DynamicTreatmentRegime(BaseModel):
    """Specification of a dynamic treatment regime d = (d_0, ..., d_{T-1}).

    A regime maps each unit's observed history H_t to an action A_t ∈ {0, 1}:
        A_t = d_t(H_t)  for t = 0, 1, ..., T-1
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    time_points: tuple[int, ...] = Field(
        description="Sorted sequence of time indices (0-based)."
    )
    treatment_variables: tuple[str, ...] = Field(
        description="Names of treatment variables A_0, A_1, ... in temporal order."
    )
    time_varying_covariates: tuple[str, ...] = Field(
        description="Names of time-varying covariate variables L_0, L_1, ..."
    )
    outcome: str = Field(description="Name of the outcome variable Y.")
    rule: RegimeRule = RegimeRule.ALWAYS_TREAT
    threshold_covariate_index: int = Field(
        default=0,
        ge=0,
        description="Index of the covariate used for threshold rule.",
    )
    threshold_value: float = Field(
        default=0.0,
        description="Threshold value for THRESHOLD rule: treat if L[idx] > threshold.",
    )
    regime_coefficients: tuple[float, ...] | None = Field(
        default=None,
        description="Linear blip coefficients ψ for LINEAR_BLIP rule.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class GComputationResult(BaseModel):
    """Result of g-computation E[Y^{ā}] under a dynamic treatment regime.

    Computed by ParametricGFormula, ICEGFormula, or LTMLEEstimator.
    """

    model_config = ConfigDict(extra="forbid")

    counterfactual_mean: float = Field(
        description="Point estimate E[Y^{ā}] under the specified regime."
    )
    confidence_interval: tuple[float, float] = Field(
        description="Bootstrap or asymptotic confidence interval (lo, hi)."
    )
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    standard_error: float = Field(ge=0.0)
    regime: str = Field(description="RegimeRule value used (e.g. 'always_treat').")
    n_units: int = Field(ge=1)
    n_periods: int = Field(ge=1)
    method: Literal["parametric_g", "ice_g", "ltmle"] = "ice_g"
    sequential_ignorability_assumed: bool = True
    convergence_warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


class SNMMResult(BaseModel):
    """Result of Structural Nested Mean Model (SNMM) fitted via g-estimation.

    psi_estimates contains the blip function parameters ψ = (ψ_0, ..., ψ_K)
    for the linear blip γ(a_t, H_t; ψ) = ψ_0·a_t + ψ_1·a_t·L_{t,1} + ...

    References:
        Robins (1994). Correcting for non-compliance in randomized trials.
    """

    model_config = ConfigDict(extra="forbid")

    psi_estimates: tuple[float, ...] = Field(
        description="Blip function parameter estimates ψ̂ per blip feature."
    )
    psi_std_errors: tuple[float, ...] = Field(
        description="Bootstrap standard errors for each ψ̂ estimate."
    )
    blip_model: Literal["linear", "interaction", "quadratic"] = "linear"
    n_units: int = Field(ge=1)
    n_periods: int = Field(ge=1)
    optimal_regime: DynamicTreatmentRegime | None = None
    convergence_iterations: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DTRResult(BaseModel):
    """Result of Dynamic Treatment Regime estimation (Q-learning, A-learning, OWL, DR-DTR).

    Contains the estimated optimal dynamic regime and its value E[Y^{d*}].

    References:
        Murphy (2003). Optimal dynamic treatment regimes. JRSS-B.
        Zhao et al. (2012). Estimating individualized treatment rules using outcome weighted
            learning. JASA.
        Zhang et al. (2013). Robust estimation of optimal dynamic treatment regimes.
    """

    model_config = ConfigDict(extra="forbid")

    method: Literal["q_learning", "a_learning", "owl", "dr_dtr"]
    optimal_regime: DynamicTreatmentRegime = Field(
        description="Estimated optimal regime d*(H_t) at each stage."
    )
    value_estimate: float = Field(
        description="E[Y^{d*}]: expected outcome under optimal regime."
    )
    value_ci: tuple[float, float] = Field(
        description="Bootstrap confidence interval for value_estimate."
    )
    n_units: int = Field(ge=1)
    n_stages: int = Field(ge=1)
    stage_coefficients: tuple[tuple[float, ...], ...] = Field(
        description="Per-stage model coefficients (Q-function or blip function weights)."
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class OPEResult(BaseModel):
    """Result of Off-Policy Evaluation (IS or DR estimator).

    Estimates V^π = E_{π}[Y] from historical data collected under π_b ≠ π.

    References:
        Precup, Sutton & Singh (2000). Eligibility traces for off-policy policy evaluation.
        Dudík, Langford & Li (2011). Doubly robust policy evaluation and learning.
    """

    model_config = ConfigDict(extra="forbid")

    method: Literal["is", "dr"]
    policy_value: float = Field(
        description="Estimated value V̂^π of the target policy."
    )
    confidence_interval: tuple[float, float]
    effective_sample_size: float = Field(
        ge=0.0,
        description="Kish's ESS = (Σ ρ_i)^2 / Σ ρ_i^2 — lower means high variance.",
    )
    n_trajectories: int = Field(ge=1)
    importance_weight_max: float = Field(
        ge=0.0,
        description="Max importance ratio max_i ρ_i — large value signals overlap issues.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class BanditResult(BaseModel):
    """Result of causal bandit simulation.

    Estimates the optimal intervention arm using causal effect estimates + UCB exploration.

    References:
        Lattimore, Munos & Szepesvári (2016). Causal bandits. NeurIPS.
        Bareinboim, Forney & Pearl (2015). Bandits with unobserved confounders. NeurIPS.
    """

    model_config = ConfigDict(extra="forbid")

    optimal_arm: str = Field(description="Name of the arm with highest estimated effect.")
    arm_estimates: dict[str, float] = Field(
        description="Mapping arm_name → estimated causal effect."
    )
    arm_cis: dict[str, tuple[float, float]] = Field(
        description="Mapping arm_name → 95% CI on causal effect estimate."
    )
    n_rounds: int = Field(ge=1)
    arm_pull_counts: dict[str, int] = Field(
        description="Number of times each arm was selected during exploration."
    )
    cumulative_regret: float | None = Field(
        default=None,
        ge=0.0,
        description="Total regret accumulated over n_rounds (if true optimal known).",
    )
    exploration_strategy: str = "ucb1"
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "BanditResult",
    "DTRResult",
    "DynamicTreatmentRegime",
    "GComputationResult",
    "OPEResult",
    "RegimeRule",
    "SNMMResult",
]
