"""Domain types for the academic knowledge graph (works, estimates, claims, priors)."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from polisyos.ir.analytics import (
    ClaimVocabularyAxisStatus,
    DesignFamily,
    EvidenceStrength,
    SourceBasis,
    VersionedClaimVocabularyEnvelope,
    adapt_legacy_claim_occurrence_as_v2_absence,
)

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
CLAIM_VOCABULARY_COLUMN_CONTRACT = {
    CLAIM_VOCABULARY_DISCRIMINATOR_COLUMN: ("VARCHAR", "NO", "'2.0'"),
    "design_family_hint": ("VARCHAR", "YES", None),
    "design_family_hint_status": ("VARCHAR", "NO", "'not_established'"),
    "evidence_strength": ("VARCHAR", "YES", None),
    "evidence_strength_status": ("VARCHAR", "NO", "'not_established'"),
    "claim_extraction_confidence": ("FLOAT", "YES", None),
    "claim_extraction_confidence_status": ("VARCHAR", "NO", "'not_established'"),
    "source_basis": ("VARCHAR", "YES", None),
    "source_basis_status": ("VARCHAR", "NO", "'not_established'"),
    "legacy_strength_label": ("VARCHAR", "YES", None),
    "record_extraction_mode": ("VARCHAR", "YES", None),
}
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

CLAIM_VOCABULARY_PROJECTION_RULE_VERSION = "policyos.academic.claim-vocabulary-projection.v2"
ClaimSourceTable = Literal[
    "ac_causal_claims_raw",
    "ac_causal_claims",
    "ac_skg_edges",
    "ac_skg_family_edges",
    "ac_skg_contested_edges",
]
ClaimSourceSchema = Literal["legacy_v1", "explicit_v2", "explicit_edge_summary"]


class ClaimVocabularyLimitation(str, Enum):
    """Descriptive limitation carried by the compatibility projection."""

    AMBIGUOUS_LEGACY_VOCABULARY = "ambiguous_legacy_vocabulary"


class ClaimTableSchemaError(ValueError):
    """Raised when a claim table is absent, partial, mixed, or future-valued."""


class ClaimLineageCursorError(ValueError):
    """Raised when an audit cursor cannot be safely resumed."""


class ClaimVocabularySourceRowBinding(BaseModel):
    """Content binding for one physical source row (descriptive only)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_table: ClaimSourceTable
    source_schema_version: ClaimSourceSchema
    source_identity: str = Field(min_length=1)
    source_row_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )


class ClaimVocabularyProjectionBinding(BaseModel):
    """Ordered physical inputs and digest for a projected vocabulary result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    projection_rule_version: Literal["policyos.academic.claim-vocabulary-projection.v2"]
    subject_kind: Literal["claim_row", "edge_summary"]
    source_rows: tuple[ClaimVocabularySourceRowBinding, ...] = Field(min_length=1)
    projected_vocabulary_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
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
    """Frozen, lossless transport pairing one occurrence with its vocabulary sidecar."""

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

    This candidate boundary intentionally creates no receipt, authority decision,
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
    """Return the exact persistence layout for a re-admitted candidate sidecar.

    The active writers use this exact layout after re-admission. It never emits
    a generic ``strength`` field.
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


def adapt_legacy_claim_occurrence_transport(
    occurrence: Mapping[str, JsonValue],
    *,
    provenance: Literal["legacy_jsonl", "legacy_snapshot"],
    record_extraction_mode: str | None = None,
) -> ClaimOccurrenceVocabularyTransport:
    """Adapt a persisted legacy occurrence before strict v2 admission.

    This compatibility route is deliberately provenance-bound and is not used
    by live producers or writers. Legacy lookalike fields are removed instead
    of being treated as established vocabulary.
    """

    raw = dict(occurrence)
    if provenance not in {"legacy_jsonl", "legacy_snapshot"}:
        raise ValueError(f"unsupported legacy provenance: {provenance}")
    expected_keys = {"cause", "effect", "direction", "strength", "mechanism"}
    if not set(raw) >= expected_keys:
        raise ValueError(
            "legacy claim occurrence must contain "
            "cause, effect, direction, strength, mechanism"
        )
    if CLAIM_VOCABULARY_DISCRIMINATOR_COLUMN in raw or "schema_version" in raw:
        raise ValueError("legacy claim occurrence must not carry a v2 discriminator")
    legacy = {
        "cause": raw.get("cause"),
        "effect": raw.get("effect"),
        "direction": raw.get("direction"),
        "strength": raw.get("strength"),
        "mechanism": raw.get("mechanism"),
    }
    vocabulary = adapt_legacy_claim_occurrence_as_v2_absence(
        legacy,
        record_extraction_mode=record_extraction_mode,
    )
    for key in {"strength", *_ROOT_VOCABULARY_KEYS}:
        raw.pop(key, None)
    return admit_candidate_claim_vocabulary(
        ClaimOccurrenceVocabularyTransport(occurrence=raw, vocabulary=vocabulary)
    )


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


class CausalClaimResultV2(BaseModel):
    """Safe default causal claim projection with independent typed axes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["2.0"] = "2.0"
    id: str = ""
    work_id: str = ""
    cause: str
    effect: str
    direction: str = ""
    mechanism: str = ""
    domain: str = ""
    trust_score: float = 0.0
    work_title: str = ""
    work_year: int | None = None
    design_family_hint: DesignFamily | None = None
    design_family_hint_status: ClaimVocabularyAxisStatus = ClaimVocabularyAxisStatus.NOT_ESTABLISHED
    evidence_strength: EvidenceStrength | None = None
    evidence_strength_status: ClaimVocabularyAxisStatus = ClaimVocabularyAxisStatus.NOT_ESTABLISHED
    claim_extraction_confidence: float | None = None
    claim_extraction_confidence_status: ClaimVocabularyAxisStatus = (
        ClaimVocabularyAxisStatus.NOT_ESTABLISHED
    )
    source_basis: SourceBasis | None = None
    source_basis_status: ClaimVocabularyAxisStatus = ClaimVocabularyAxisStatus.NOT_ESTABLISHED
    legacy_strength_label: str | None = None
    record_extraction_mode: str | None = None
    limitations: tuple[ClaimVocabularyLimitation, ...] = ()
    projection_binding: ClaimVocabularyProjectionBinding
    strong_design_evidence: bool = False
    design_quality_tier: int | None = None
    publish_blockers: tuple[str, ...] = ()
    candidate_layer: str = "candidate"

    @model_validator(mode="after")
    def _validate_axis_statuses(self) -> CausalClaimResultV2:
        """Require statuses to be the canonical Task-1 status values."""
        for name, value, status in (
            ("design_family_hint", self.design_family_hint, self.design_family_hint_status),
            ("evidence_strength", self.evidence_strength, self.evidence_strength_status),
            (
                "claim_extraction_confidence",
                self.claim_extraction_confidence,
                self.claim_extraction_confidence_status,
            ),
            ("source_basis", self.source_basis, self.source_basis_status),
        ):
            if not isinstance(status, ClaimVocabularyAxisStatus):
                raise ValueError(f"{name}_status must be a ClaimVocabularyAxisStatus")
            if value is None and status is not ClaimVocabularyAxisStatus.NOT_ESTABLISHED:
                raise ValueError(f"{name} must be absent when its status is not_established")
            if value is not None and status is not ClaimVocabularyAxisStatus.CANDIDATE:
                raise ValueError(f"{name} requires candidate status when present")
        return self


class CausalClaimResultV1(BaseModel):
    """Deprecated lossy audit view; generic legacy strength is never restored."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = ""
    work_id: str = ""
    cause: str
    effect: str
    direction: str = ""
    mechanism: str = ""
    domain: str = ""
    trust_score: float = 0.0
    work_title: str = ""
    work_year: int | None = None
    strength: None = None
    limitation: ClaimVocabularyLimitation = ClaimVocabularyLimitation.AMBIGUOUS_LEGACY_VOCABULARY
    v2_projection_binding: ClaimVocabularyProjectionBinding


# Existing source imports intentionally move to the safe v2 default.
CausalClaimResult = CausalClaimResultV2


class ClaimLineageAuditRecord(BaseModel):
    """Identity-level read-only lineage record for the raw claim audit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    work_id: str
    cause: str
    effect: str
    direction: str = ""
    mechanism: str = ""
    legacy_strength_label: str | None = None
    vocabulary: VersionedClaimVocabularyEnvelope
    projection_binding: ClaimVocabularyProjectionBinding
    limitations: tuple[ClaimVocabularyLimitation, ...] = ()


class ClaimLineageAuditPage(BaseModel):
    """One keyset page of claim identities and its opaque continuation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[ClaimLineageAuditRecord, ...]
    total_identities: int
    next_cursor: str | None = None
    status_filter: Literal["not_established", "candidate", "all"]
    projection_rule_version: Literal["policyos.academic.claim-vocabulary-projection.v2"]


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
    causal_claims: list[ClaimOccurrenceVocabularyTransport] = Field(default_factory=list)
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


def adapt_jsonl_work_record_claims(
    payload: Mapping[str, object],
    *,
    provenance: Literal["legacy_jsonl", "legacy_snapshot"],
) -> WorkRecord:
    """Load one persisted work-record payload across the v1/v2 claim split.

    Persisted claim rows must be either the explicit nested transport payload or
    a historical occurrence containing the exact five legacy vocabulary inputs.
    Non-vocabulary operational metadata is preserved; vocabulary lookalikes are
    stripped before admission as declared absence.
    """

    claims = payload.get("causal_claims")
    if not isinstance(claims, list) or not claims:
        return WorkRecord.model_validate(payload)

    adapted_claims: list[object] = []
    for claim in claims:
        if not isinstance(claim, Mapping):
            raise ValueError("JSONL claim is not a mapping payload")
        if "occurrence" in claim or "vocabulary" in claim:
            if "occurrence" not in claim or "vocabulary" not in claim:
                raise ValueError("JSONL claim transport must contain occurrence and vocabulary")
            adapted_claims.append(dict(claim))
            continue
        if (
            not set(claim) >= {"cause", "effect", "direction", "strength", "mechanism"}
            or CLAIM_VOCABULARY_DISCRIMINATOR_COLUMN in claim
        ):
            raise ValueError(
                "JSONL claim is neither admitted transport nor a legacy occurrence"
            )
        adapted_claims.append(
            adapt_legacy_claim_occurrence_transport(
                claim,
                provenance=provenance,
                record_extraction_mode=str(payload.get("extraction_mode") or "deterministic"),
            )
        )
    return WorkRecord.model_validate({**payload, "causal_claims": adapted_claims})
