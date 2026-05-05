"""Domain types for the academic knowledge graph (works, estimates, claims, priors)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ParameterEstimateResult(BaseModel):
    """A single numerical estimate extracted from a paper."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = ""
    work_id: str = ""
    variable_name: str
    estimate: float
    ci_low: float | None = None
    ci_high: float | None = None
    std_error: float | None = None
    unit: str = ""
    domain: str = ""
    study_design: str = ""
    sample_size: int | None = None
    country: str = ""
    period_start: int | None = None
    period_end: int | None = None
    trust_score: float = 0.0
    raw_context: str = ""
    work_title: str = ""
    work_year: int | None = None


class BoundaryConditionResult(BaseModel):
    """Structured boundary condition found in literature evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = ""
    work_id: str = ""
    variable: str
    operator: str = ""
    threshold_value: str = ""
    scope_text: str = ""
    confidence: float = 0.0


class CausalClaimResult(BaseModel):
    """A causal relationship claim from academic literature."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = ""
    work_id: str = ""
    cause: str
    effect: str
    direction: str = ""  # positive, negative, null, mixed
    strength: str = ""  # strong, moderate, weak
    mechanism: str = ""
    domain: str = ""
    trust_score: float = 0.0
    work_title: str = ""
    work_year: int | None = None


class WorkSearchResult(BaseModel):
    """Academic work found by search."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str
    doi: str = ""
    abstract_snippet: str = ""
    year: int | None = None
    publication_date: str = ""
    language: str = ""
    work_type: str = ""
    is_retracted: bool = False
    cited_by_count: int = 0
    fwci: float | None = None
    citation_percentile: float | None = None
    citation_is_top_1_percent: bool = False
    citation_is_top_10_percent: bool = False
    journal: str = ""
    source_id: str = ""
    trust_score: float = 0.0
    study_design: str = ""
    is_oa: bool = False
    has_fulltext: bool = False
    full_text_url: str = ""
    similarity: float = 0.0
    run_id: str = ""
    pass_name: str = ""
    topic_ids: list[str] = Field(default_factory=list)

    # Pre-extracted estimates (available without reading full text)
    pre_extracted_estimates: list[ParameterEstimateResult] = Field(default_factory=list)


class ParameterPrior(BaseModel):
    """Aggregated prior distribution from literature estimates.

    Directly usable for foundry/calibration/ TrainableHandle.prior_mean/prior_std.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    variable: str
    prior_mean: float
    prior_std: float
    prior_low: float  # 10th percentile
    prior_high: float  # 90th percentile
    n_studies: int
    best_design: str = ""
    as_calibration_prior: dict = Field(default_factory=dict)


class EstimateCandidate(BaseModel):
    """Candidate numerical estimate from regex or LLM extraction (batch stage)."""

    model_config = ConfigDict(extra="forbid")

    value: float
    ci_low: float | None = None
    ci_high: float | None = None
    std_error: float | None = None
    unit: str = ""
    context_snippet: str = ""
    pattern_name: str = ""
    confidence: float = 0.5
    variable_hint: str = ""


class SourceTopicRef(BaseModel):
    """Topic-level selection provenance for one work."""

    model_config = ConfigDict(extra="forbid")

    topic_id: str
    topic_display_name: str = ""
    policy_block: str = ""
    policy_subblock: str = ""
    source_file: str = ""
    rank: int = 0
    selection_score: float = 0.0
    batch_origin: str = ""
    selected_at: str = ""


class WorkRecord(BaseModel):
    """Full work record for batch pipeline (harvest -> graph builder)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    doi: str = ""
    abstract: str = ""
    year: int | None = None
    publication_date: str = ""
    language: str = ""
    work_type: str = ""
    is_retracted: bool = False
    cited_by_count: int = 0
    fwci: float | None = None
    citation_normalized_percentile: float | None = None
    citation_is_top_1_percent: bool = False
    citation_is_top_10_percent: bool = False
    journal: str = ""
    source_id: str = ""
    is_oa: bool = False
    has_fulltext: bool = False
    full_text_url: str = ""
    concepts: list[dict] = Field(default_factory=list)
    source_topics: list[SourceTopicRef] = Field(default_factory=list)
    study_design: str = ""
    trust_score: float = 0.0
    estimates: list[EstimateCandidate] = Field(default_factory=list)
    causal_claims: list[dict] = Field(default_factory=list)
    boundary_conditions: list[dict] = Field(default_factory=list)
    context_profile: dict = Field(default_factory=dict)

    extraction_mode: str = "deterministic"  # deterministic|llm_enriched
    extraction_confidence: float = 0.0
    method_signal_score: float = 0.0

    llm_gate_route: str = ""
    llm_gate_score: float = 0.0
    llm_gate_reasons: list[str] = Field(default_factory=list)

    token_count_prompt: int = 0
    token_count_completion: int = 0
    screening_cost_usd: float = 0.0
    extraction_cost_usd: float = 0.0

    metadata: dict = Field(default_factory=dict)
