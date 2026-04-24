"""IR models for optimal experimental design (Phase 9).

Henckel, Perković & Maathuis (2022): Graphical criteria for efficient adjustment.
Bareinboim, Brito & Pearl (2012): Instrumental sets and the identification of causal effects.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ExperimentPlan",
    "OptimalAdjustmentResult",
    "OptimalIVResult",
]


class OptimalAdjustmentResult(BaseModel):
    """Result of O-set computation (Henckel, Perković & Maathuis 2022).

    The O-set minimises the asymptotic variance of the backdoor adjustment
    estimator among all valid adjustment sets.

    Theorem (Henckel et al. 2022):
        O(X, Y, G) = Pa_G(An(Y)_{G_{V\\De(X)}}) \\ (De(X) ∪ {X})
    """

    model_config = ConfigDict(extra="forbid")

    o_set: frozenset[str]
    """Optimal adjustment set (O-set); minimises asymptotic variance."""

    all_valid_adjustment_sets: list[frozenset[str]] = Field(default_factory=list)
    """Enumerated valid adjustment sets found (may be partial for large graphs)."""

    graphical_criterion_used: str = "henckel-2022-o-set"
    """Name of the graphical criterion applied."""

    treatment: str
    """Treatment variable X."""

    outcome: str
    """Outcome variable Y."""

    o_set_is_valid_backdoor: bool = True
    """True iff the O-set satisfies the backdoor criterion in this graph."""


class OptimalIVResult(BaseModel):
    """Result of optimal instrument set selection.

    Selects the IV set that minimises asymptotic variance for IV/LATE
    estimation among all valid instrument sets in the causal graph.
    """

    model_config = ConfigDict(extra="forbid")

    optimal_iv_set: frozenset[str]
    """Optimal instrumental variable set (may be empty if none exists)."""

    all_valid_iv_sets: list[frozenset[str]] = Field(default_factory=list)
    """All valid IV sets found via graphical criterion."""

    treatment: str
    """Endogenous treatment variable X."""

    outcome: str
    """Outcome variable Y."""

    exclusion_restriction_verified: bool = True
    """True iff the graphical exclusion restriction holds for optimal_iv_set."""


class ExperimentPlan(BaseModel):
    """Minimum-cost experimental design plan.

    Records the minimum-cost set of interventions needed to identify the
    target causal query, along with graphical provenance.

    Based on Bareinboim, Brito & Pearl (2012): minimum-cost identification
    via greedy selection over Z-transport identification trials.
    """

    model_config = ConfigDict(extra="forbid")

    query: str
    """Target causal query, e.g. ``"P(Y|do(X))"``. """

    recommended_interventions: tuple[str, ...] = ()
    """Variable names recommended for experimental intervention (do-calculus).
    Empty when the query is already observationally identified."""

    cost_estimate: float | None = None
    """Total cost of the recommended intervention set (sum of individual costs).
    None if cost information was not provided."""

    adjustment_set: frozenset[str] | None = None
    """Recommended adjustment set for the resulting identified estimand."""

    already_identified_observationally: bool = False
    """True iff the query is identifiable without any experiments."""

    rationale: str = ""
    """Human-readable explanation of why these interventions were chosen."""

    n_stages: int = 1
    """Number of experimental stages (1 for non-adaptive designs)."""
