"""Domain types for the academic knowledge graph (works, estimates, claims, priors)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from polisyos.ir.analytics.literature import VersionedClaimVocabularyEnvelope

_OCCURRENCE_IDENTITY_FIELDS = ("cause", "effect", "direction", "mechanism")
CLAIM_VOCABULARY_DISCRIMINATOR_COLUMN = "claim_vocabulary_schema_version"
CLAIM_VOCABULARY_DISCRIMINATOR_VALUE = "2.0"
CLAIM_VOCABULARY_STORE_COLUMNS = (
    "design_family_hint",
    "design_family_hint_status",
    "evidence_strength",
    "evidence_strength_status",
    "claim_extraction_confidence",
    "claim_extraction_confidence_status",
    "source_basis",
    "source_basis_status",
    "legacy_strength_label",
    "record_extraction_mode",
)
_ROOT_VOCABULARY_KEYS = frozenset(
    {
        "design_family_hint",
        "evidence_strength",
        "claim_extraction_confidence",
        "source_basis",
        "design_family_hint_status",
        "evidence_strength_status",
        "claim_extraction_confidence_status",
        "source_basis_status",
        "legacy_strength_label",
        "record_extraction_mode",
    }
)


def _forbidden_vocabulary_key_path(value: JsonValue, *, path: str = "occurrence") -> str | None:
    """Return the first forbidden vocabulary key path in a JSON occurrence."""

    if isinstance(value, dict):
        for key, nested_value in value.items():
            key_path = f"{path}.{key}"
            if key == "strength" or (path == "occurrence" and key in _ROOT_VOCABULARY_KEYS):
                return key_path
            found = _forbidden_vocabulary_key_path(nested_value, path=key_path)
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, nested_value in enumerate(value):
            found = _forbidden_vocabulary_key_path(nested_value, path=f"{path}[{index}]")
            if found is not None:
                return found
    return None


def _complete_model_state(model: BaseModel) -> dict[str, object]:
    """Return all model state, including post-init forged keys."""

    state = dict(vars(model))
    extra = getattr(model, "__pydantic_extra__", None)
    if isinstance(extra, dict):
        state.update(extra)
    return state


class ClaimOccurrenceVocabularyTransport(BaseModel):
    """Frozen, lossless inactive transport pairing one occurrence with its vocabulary sidecar."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    occurrence: dict[str, JsonValue]
    vocabulary: VersionedClaimVocabularyEnvelope

    @model_validator(mode="after")
    def _validate_occurrence_binding(self) -> ClaimOccurrenceVocabularyTransport:
        """Require exact identity binding and reserve vocabulary keys at their owner."""

        forbidden_path = _forbidden_vocabulary_key_path(self.occurrence)
        if forbidden_path is not None:
            raise ValueError(f"vocabulary key is not allowed in v2 occurrence: {forbidden_path}")
        for field_name in _OCCURRENCE_IDENTITY_FIELDS:
            occurrence_value = self.occurrence.get(field_name)
            if not isinstance(occurrence_value, str):
                raise ValueError(f"occurrence.{field_name} must be a present string")
            if occurrence_value != getattr(self.vocabulary, field_name):
                raise ValueError(f"occurrence.{field_name} must match vocabulary.{field_name}")
        return self


def admit_candidate_claim_vocabulary(
    transport: ClaimOccurrenceVocabularyTransport,
) -> ClaimOccurrenceVocabularyTransport:
    """Mechanically revalidate a candidate vocabulary sidecar and occurrence binding.

    This inactive boundary intentionally creates no receipt, authority decision,
    publication conclusion, or ranking result.
    """

    transport_state = _complete_model_state(transport)
    vocabulary = transport_state.get("vocabulary")
    if isinstance(vocabulary, VersionedClaimVocabularyEnvelope):
        transport_state["vocabulary"] = _complete_model_state(vocabulary)
    return ClaimOccurrenceVocabularyTransport.model_validate(transport_state)


def candidate_claim_vocabulary_store_values(
    transport: ClaimOccurrenceVocabularyTransport,
) -> dict[str, JsonValue]:
    """Return the inactive exact persistence layout for a re-admitted sidecar.

    This pure projector prepares the Task-3 storage switch only.  It is not
    connected to DDL or writers and never emits a generic ``strength`` field.
    """

    vocabulary = admit_candidate_claim_vocabulary(transport).vocabulary
    return {
        CLAIM_VOCABULARY_DISCRIMINATOR_COLUMN: vocabulary.schema_version,
        "design_family_hint": (
            vocabulary.design_family_hint.value
            if vocabulary.design_family_hint is not None
            else None
        ),
        "design_family_hint_status": vocabulary.design_family_hint_status.value,
        "evidence_strength": (
            vocabulary.evidence_strength.value if vocabulary.evidence_strength is not None else None
        ),
        "evidence_strength_status": vocabulary.evidence_strength_status.value,
        "claim_extraction_confidence": vocabulary.claim_extraction_confidence,
        "claim_extraction_confidence_status": vocabulary.claim_extraction_confidence_status.value,
        "source_basis": (
            vocabulary.source_basis.value if vocabulary.source_basis is not None else None
        ),
        "source_basis_status": vocabulary.source_basis_status.value,
        "legacy_strength_label": vocabulary.legacy_strength_label,
        "record_extraction_mode": vocabulary.record_extraction_mode,
    }


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
