"""IR models for data fusion (Phase 9).

Bareinboim & Pearl (2016): Causal inference and the data-fusion problem.
Provides lightweight Pydantic contracts for fusion results and combination plans.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


__all__ = [
    "FusionDataset",
    "FusionResult",
    "DataCombinationPlan",
    "ValidityReport",
]


class FusionDataset(BaseModel):
    """Description of a single data source for multi-study fusion.

    Corresponds to one domain in the multi-source selection diagram
    (Bareinboim & Pearl 2016).  ``selection_bias_vars`` maps to S-nodes;
    ``available_interventions`` maps to Z-interventional distributions.
    """

    model_config = ConfigDict(extra="forbid")

    dataset_ref: str
    """Unique reference identifier for this dataset (e.g. "study_rct_2020")."""

    domain_id: str
    """Domain identifier used to distinguish sources in mZ-ID algorithm."""

    n_obs: int
    """Number of observations in this dataset."""

    available_interventions: tuple[str, ...] = ()
    """Variables for which this dataset provides experimental (do-calculus)
    distributions — i.e. P(V|do(Z)) distributions are available."""

    selection_bias_vars: tuple[str, ...] = ()
    """Variables that differ mechanistically from the target population;
    correspond to S-node targets in the selection diagram."""

    quality_score: float = 1.0
    """Data quality weight in [0, 1]; used for variance-weighted combination."""


class FusionResult(BaseModel):
    """Result of a data fusion identification step.

    Records whether the target causal query is identifiable from the
    combined source datasets, plus the identification formula and provenance.
    """

    model_config = ConfigDict(extra="forbid")

    query: str
    """Human-readable target query, e.g. ``"P*(Y|do(X))"``. """

    is_identified: bool
    """True iff the target query is identifiable from the fused sources."""

    fusion_formula_latex: str | None = None
    """LaTeX representation of the identification formula, if identified."""

    required_datasets: tuple[str, ...] = ()
    """dataset_ref values that are required to compute the estimand."""

    required_interventions: tuple[str, ...] = ()
    """Variable names for which experimental distributions are needed."""

    identification_algorithm: str = "mz-id"
    """Algorithm used: ``"mz-id"`` | ``"z-id"`` | ``"tr"``."""

    proof_steps: tuple[str, ...] = ()
    """Sequence of rule names from the ID algorithm trace."""

    warnings: tuple[str, ...] = ()
    """Non-fatal warnings generated during identification."""


class DataCombinationPlan(BaseModel):
    """Variance-optimal weights for combining estimates across datasets.

    Implements inverse-variance weighting (the semiparametrically efficient
    combination when EIF variances are known):
    ``w_k ∝ 1/V_k``, ``V_combined = 1 / Σ_k (1/V_k)``.
    """

    model_config = ConfigDict(extra="forbid")

    query: str
    """Target causal query this combination plan addresses."""

    source_weights: dict[str, float]
    """Mapping domain_id → optimal weight in [0, 1]; weights sum to 1."""

    combination_method: str = "inverse_variance_weighted"
    """Combination method used (currently always inverse-variance weighting)."""

    expected_variance: float | None = None
    """Combined asymptotic variance after optimal weighting."""

    required_datasets: tuple[str, ...] = ()
    """dataset_ref values that contribute to the combination."""


class ValidityReport(BaseModel):
    """External validity assessment via transportability analysis.

    Records whether the source-population causal effect transports to the
    target population, and identifies the blocking S-nodes if not.
    """

    model_config = ConfigDict(extra="forbid")

    source_population: str
    """Identifier of the source study population."""

    target_population: str
    """Identifier of the target policy population."""

    transportable_variables: tuple[str, ...] = ()
    """S-node target variables that do NOT block transportability."""

    non_transportable_variables: tuple[str, ...] = ()
    """S-node target variables that block full transportability."""

    recommended_adjustments: tuple[str, ...] = ()
    """Variables recommended for stratified transport adjustment."""

    transport_formula_latex: str | None = None
    """LaTeX transport formula if identified; None otherwise."""

    overall_transportability: bool
    """True iff P*(Y|do(X)) is identifiable via the TR algorithm."""
