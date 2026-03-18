"""Actual Causality IR types.

Covers three related concepts:

1. **Probability of Necessity and Sufficiency (PN/PS/PNS)**
   Pearl (2000), Chapter 9; Tian & Pearl (2000).

2. **HP Actual Causality** (AC1/AC2/AC3 conditions)
   Halpern & Pearl (2005), updated in Halpern (2016).

3. **Degree of Responsibility / Blame**
   Chockler & Halpern (2004).

All models use ``ConfigDict(extra="forbid", frozen=True)`` per project standard.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── PN / PS / PNS ─────────────────────────────────────────────────────────────


class PNResult(BaseModel):
    """Probability of Necessity result.

    PN = P(Y_{x'} = 0 | X = x, Y = 1)

    Asks: "Would Y *not* have occurred if X had been absent?"
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"

    treatment: str
    """Name of the treatment variable X."""

    outcome: str
    """Name of the outcome variable Y."""

    treatment_value: float
    """Factual treatment value x (X = x was observed)."""

    counterfactual_value: float
    """Counterfactual treatment value x' (the absent scenario)."""

    pn: float = Field(ge=0.0, le=1.0)
    """Estimated PN — probability of necessity."""

    pn_ci: tuple[float, float] | None = None
    """95% confidence interval for PN (lower, upper)."""

    bounds_lower: float | None = None
    """Tian & Pearl (2000) observational lower bound for PN."""

    bounds_upper: float | None = None
    """Tian & Pearl (2000) observational upper bound for PN."""

    n_samples: int = 0
    """Number of Monte Carlo samples used (0 if analytical)."""

    computation_method: str = "simulation"
    """How PN was computed: ``"simulation"`` | ``"tian_pearl_bounds"``."""

    metadata: dict[str, Any] = Field(default_factory=dict)


class PSResult(BaseModel):
    """Probability of Sufficiency result.

    PS = P(Y_x = 1 | X = x', Y = 0)

    Asks: "Would Y have occurred if X had been present?"
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"

    treatment: str
    outcome: str
    treatment_value: float
    counterfactual_value: float

    ps: float = Field(ge=0.0, le=1.0)
    """Estimated PS — probability of sufficiency."""

    ps_ci: tuple[float, float] | None = None
    bounds_lower: float | None = None
    bounds_upper: float | None = None
    n_samples: int = 0
    computation_method: str = "simulation"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PNSResult(BaseModel):
    """Probability of Necessity and Sufficiency result.

    PNS = P(Y_x = 1, Y_{x'} = 0)

    Asks: "Was X both necessary and sufficient for Y?"
    This is the tightest single-number summary of actual causation probability.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"

    treatment: str
    outcome: str
    treatment_value: float
    counterfactual_value: float

    pns: float = Field(ge=0.0, le=1.0)
    """Estimated PNS."""

    pn: float | None = Field(default=None, ge=0.0, le=1.0)
    """Marginal PN (derived from same simulation)."""

    ps: float | None = Field(default=None, ge=0.0, le=1.0)
    """Marginal PS (derived from same simulation)."""

    pns_ci: tuple[float, float] | None = None
    n_samples: int = 0
    computation_method: str = "simulation"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PNPSBounds(BaseModel):
    """Tian & Pearl (2000) PN/PS/PNS bounds from observational data.

    These sharp bounds do **not** require a full SCM — only the observational
    probabilities P(Y=1|X=1) and P(Y=1|X=0) are needed.

    Under the monotonicity assumption (Y_1 >= Y_0 for all units), the bounds
    collapse to a point and PNS = P(Y=1|X=1) - P(Y=1|X=0).

    Reference: Tian & Pearl (2000), "Probabilities of Causation: Bounds and
    Identification", Annals of Mathematics and Artificial Intelligence.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"

    # Input probabilities
    p_y1_x1: float = Field(ge=0.0, le=1.0)
    """P(Y=1 | X=1) — outcome probability under treatment."""

    p_y1_x0: float = Field(ge=0.0, le=1.0)
    """P(Y=1 | X=0) — outcome probability under control."""

    p_x1: float | None = Field(default=None, ge=0.0, le=1.0)
    """P(X=1) — marginal treatment probability (for weighted estimates)."""

    # PN bounds: max(0, (p11-p10)/p11) ≤ PN ≤ min(1, (1-p10)/p11)
    pn_lower: float = Field(ge=0.0, le=1.0)
    pn_upper: float = Field(ge=0.0, le=1.0)

    # PS bounds: max(0, (p11-p10)/(1-p10)) ≤ PS ≤ min(1, p11/(1-p10))
    ps_lower: float = Field(ge=0.0, le=1.0)
    ps_upper: float = Field(ge=0.0, le=1.0)

    # PNS bounds: max(0, p11-p10) ≤ PNS ≤ min(p11, 1-p10)
    pns_lower: float = Field(ge=0.0, le=1.0)
    pns_upper: float = Field(ge=0.0, le=1.0)

    monotone_pns: float | None = None
    """Point estimate of PNS under monotonicity assumption: p11 - p10."""

    is_monotone_compatible: bool | None = None
    """Whether data are compatible with monotone treatment response."""

    metadata: dict[str, Any] = Field(default_factory=dict)


# ── HP Actual Causality ────────────────────────────────────────────────────────


class ContingencySet(BaseModel):
    """Contingency set W used in HP AC2 condition.

    AC2 requires: ∃W, ∃x' such that the counterfactual intervention
    do(X=x', W=w) in the actual context produces Y ≠ y.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    variables: list[str] = Field(default_factory=list)
    """Variables in the contingency set W."""

    values: dict[str, float] = Field(default_factory=dict)
    """Values w for each contingency variable: W ← w."""

    size: int = 0
    """Number of contingency variables (|W|)."""


class HPResult(BaseModel):
    """Result of an HP actual cause check (Halpern & Pearl 2005, updated 2016).

    Checks AC1, AC2, AC3 conditions:
    - AC1: X=x and Y=y hold in the actual context (factual condition).
    - AC2: ∃W, ∃x' s.t. the counterfactual (X←x', W←w) produces Y≠y.
    - AC3: Minimality — no proper subset of X's assignment satisfies AC1+AC2.

    References
    ----------
    Halpern, J. (2016). Actual Causality. MIT Press.
    Halpern, J. & Pearl, J. (2005). Causes and Explanations: A Structural-Model
        Approach. BJPS.
    Chockler, H. & Halpern, J. (2004). Responsibility and Blame: A Structural-Model
        Approach. JAIR.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"

    cause_variable: str
    """The candidate cause variable X."""

    cause_value: float
    """The factual value x of the cause (X = x was observed)."""

    counterfactual_cause_value: float
    """The counterfactual value x' tested in AC2."""

    effect_variable: str
    """The effect variable Y."""

    effect_value: float
    """The factual value y of the effect (Y = y was observed)."""

    # AC conditions
    ac1_satisfied: bool
    """True iff X=x, Y=y holds in the actual context."""

    ac2_satisfied: bool
    """True iff a valid contingency set W was found."""

    ac3_satisfied: bool
    """True iff minimality holds (no proper subset satisfies AC1+AC2)."""

    is_actual_cause: bool
    """True iff ac1 ∧ ac2 ∧ ac3 — X=x is an actual cause of Y=y."""

    contingency: ContingencySet | None = None
    """The contingency set W that witnesses AC2 (None if AC2 not satisfied)."""

    degree_of_responsibility: float = Field(default=0.0, ge=0.0, le=1.0)
    """DR(X=x → Y=y) = 1 / (|W_min| + 1) where W_min is the smallest AC2 witness.

    DR = 1.0 for direct causes (no contingency needed).
    DR = 0.5 when |W_min| = 1.
    DR = 0.0 when X=x is not an actual cause.
    """

    degree_of_blame: float | None = Field(default=None, ge=0.0, le=1.0)
    """Expected degree of responsibility over an epistemic state (Chockler & Halpern 2004)."""

    explanation: str = ""
    """Human-readable explanation of the result."""

    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "PNResult",
    "PSResult",
    "PNSResult",
    "PNPSBounds",
    "ContingencySet",
    "HPResult",
]
