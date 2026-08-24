"""Runtime read-only types for the legal knowledge graph."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import contracts

epoch_contract = contracts.epoch

# Lex owns enumeration of the amendment-window denominator.  Re-export the
# shared wire DTOs from its native read surface so chronology consumes an
# owner API rather than reaching into the Lex store implementation.
LegalAmendmentWindowResolutionQuery = epoch_contract.LegalAmendmentWindowResolutionQuery
LegalAmendmentWindowAssessment = epoch_contract.LegalAmendmentWindowAssessment
LegalAmendmentWindowDenominatorReceipt = epoch_contract.LegalAmendmentWindowDenominatorReceipt

# ---------------------------------------------------------------------------
# Graph entities and search contracts
# ---------------------------------------------------------------------------


FactTrustTier = Literal["search_candidate", "grounded_fact", "normative_fact"]
GroundingStatus = Literal[
    "exact_quote",
    "quote_without_offsets",
    "offsets_without_quote",
    "missing_quote",
]
CanonicalStatus = Literal["canonicalized", "partially_canonicalized", "raw"]
ReferenceResolutionStatus = Literal["resolved", "partial", "unresolved", "not_applicable"]


class LegalEntity(BaseModel):
    """A unique legal concept stored in the knowledge graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: str
    name_en: str
    name_uk: str
    entity_type: str = Field(description="concept | measure | institution | document | threshold")
    mention_count: int = 1
    aliases_en: list[str] = Field(default_factory=list)
    aliases_uk: list[str] = Field(default_factory=list)

    def embedding_text(self) -> str:
        """Bilingual structured template for high-quality embedding."""
        parts = [
            "ENTITY",
            f"en: {self.name_en}",
            f"uk: {self.name_uk}",
        ]
        all_aliases = self.aliases_en + self.aliases_uk
        if all_aliases:
            parts.append(f"aliases: {'; '.join(all_aliases[:10])}")
        parts.append(f"type: {self.entity_type}")
        return "\n".join(parts)


class LegalFact(BaseModel):
    """A legal statement stored in the knowledge graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fact_id: str
    subject_id: str
    predicate: str
    object_id: str
    fact_text: str
    confidence: float
    norm_type: str
    action_canon: str = ""
    norm_type_canon: str = ""
    condition_text_uk: str = ""
    exception_text_uk: str = ""
    procedure_text_uk: str = ""
    temporal_text_uk: str = ""
    sanction_text_uk: str = ""
    source_quote_uk: str = ""
    source_quote_start: int | None = None
    source_quote_end: int | None = None
    thresholds_json: str = "[]"
    trust_tier: FactTrustTier = "search_candidate"
    grounding_status: GroundingStatus = "missing_quote"
    canonical_status: CanonicalStatus = "raw"
    reference_resolution_status: ReferenceResolutionStatus = "not_applicable"
    structure_quality: str = ""
    constraint_type_canon: str = ""
    legal_unit_subtype: str = ""
    legal_unit_micro_subtype: str = ""
    route_class: str = ""
    empty_spo_retry_eligible: bool = False
    audit_miss_prone: bool = False
    reference_bearing: bool = False
    threshold_bearing: bool = False

    # Provenance
    doc_id: str
    doc_reestr_code: str
    doc_name: str = ""
    doc_type: str = ""
    doc_date_acc: str = ""
    doc_status: str = ""
    provision_anchor: str = ""
    provision_citation: str = ""
    jurisdiction: str = "UA"
    top_domain: str = ""
    doc_family_id: str = ""
    version_id: str = ""
    effective_from: str = ""
    effective_to: str = ""
    temporal_state: str = ""
    temporal_resolution_status: str = ""
    temporal_source_scope: str = ""
    temporal_source_kind: str = ""
    temporal_confidence: float | None = None
    temporal_provenance_json: str = ""

    # SPO bilingual labels (for embedding template)
    subject_en: str = ""
    subject_uk: str = ""
    object_en: str = ""
    object_uk: str = ""

    def embedding_text(self) -> str:
        """Bilingual structured template with rule clauses."""
        parts = [
            "FACT",
            f"trust_tier: {self.trust_tier}",
            f"norm_type: {self.norm_type_canon or self.norm_type}",
            f"action: {self.action_canon or self.predicate}",
            f"spo: {self.subject_en} ({self.subject_uk}) {self.predicate} {self.object_en} ({self.object_uk})",
            f"fact_en: {self.fact_text}",
        ]
        if self.condition_text_uk:
            parts.append(f"condition_uk: {self.condition_text_uk}")
        if self.exception_text_uk:
            parts.append(f"exception_uk: {self.exception_text_uk}")
        if self.procedure_text_uk:
            parts.append(f"procedure_uk: {self.procedure_text_uk}")
        if self.source_quote_uk:
            parts.append(f"quote_uk: {self.source_quote_uk[:400]}")
        if self.top_domain:
            parts.append(f"domain: {self.top_domain}")
        return "\n".join(parts)


class LegalProvision(BaseModel):
    """A provision (article/point) stored for fallback embedding search."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provision_id: str
    doc_id: str
    doc_reestr_code: str
    doc_name: str = ""
    doc_type: str = ""
    doc_status: str = ""
    anchor_path: str
    citation_label: str
    kind: str
    provision_text: str
    struct_kind: str = ""
    section_role: str = ""
    lineage_path: str = ""
    appendix_id: str = ""
    table_id: str = ""
    fallback_allowed_for_reasoning: bool = False

    def embedding_text(self) -> str:
        """Raw Ukrainian provision text for embedding."""
        return self.provision_text


# ---------------------------------------------------------------------------
# Search results
# ---------------------------------------------------------------------------


class LegalSearchResult(BaseModel):
    """Entity found by vector search."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: str
    name_en: str
    name_uk: str
    entity_type: str
    similarity: float


class LegalFactResult(BaseModel):
    """Fact found by vector/text search."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fact_id: str
    subject_name: str
    predicate: str
    object_name: str
    fact_text: str
    confidence: float
    norm_type: str
    action_canon: str = ""
    norm_type_canon: str = ""
    condition_text_uk: str = ""
    exception_text_uk: str = ""
    procedure_text_uk: str = ""
    thresholds_json: str = ""
    source_quote_uk: str = ""
    trust_tier: FactTrustTier = "search_candidate"
    grounding_status: GroundingStatus = "missing_quote"
    canonical_status: CanonicalStatus = "raw"
    reference_resolution_status: ReferenceResolutionStatus = "not_applicable"
    structure_quality: str = ""
    constraint_type_canon: str = ""
    legal_unit_subtype: str = ""
    route_class: str = ""
    empty_spo_retry_eligible: bool = False
    audit_miss_prone: bool = False
    reference_bearing: bool = False
    threshold_bearing: bool = False
    fused_confidence: float | None = None
    confidence_breakdown_json: str = ""
    consistency_score: float | None = None
    hallucination_flags_json: str = ""
    quality_band: str = ""
    doc_id: str = ""
    doc_family_id: str = ""
    version_id: str = ""
    jurisdiction: str = "UA"
    top_domain: str = ""
    effective_from: str = ""
    effective_to: str = ""
    temporal_state: str = ""
    temporal_resolution_status: str = ""
    temporal_source_scope: str = ""
    temporal_source_kind: str = ""
    temporal_confidence: float | None = None
    temporal_provenance_json: str = ""
    doc_name: str
    doc_reestr_code: str
    provision_anchor: str = ""
    provision_citation: str
    similarity: float


class LegalProvisionResult(BaseModel):
    """Provision found by vector search (fallback when SPO is empty)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provision_id: str
    doc_id: str = ""
    version_id: str = ""
    doc_name: str
    doc_reestr_code: str
    anchor_path: str = ""
    citation_label: str
    kind: str
    provision_text_preview: str
    struct_kind: str = ""
    section_role: str = ""
    legal_unit_subtype: str = ""
    route_class: str = ""
    empty_spo_retry_eligible: bool = False
    audit_miss_prone: bool = False
    reference_bearing: bool = False
    threshold_bearing: bool = False
    fallback_allowed_for_reasoning: bool = False
    similarity: float


class LegalReferenceEdgeResult(BaseModel):
    """Resolved or unresolved reference edge around a provision cluster."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_doc_id: str
    source_anchor: str
    target_doc_id: str = ""
    target_anchor: str = ""
    relation_type: str = ""
    resolution_status: str = ""
    resolution_confidence: float = 0.0
    ref_text_uk: str = ""


class LegalDocVersionResult(BaseModel):
    """Version lineage row for a legal document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str
    doc_family_id: str = ""
    version_id: str = ""
    doc_reestr_code: str = ""
    doc_name: str = ""
    doc_type: str = ""
    doc_status: str = ""
    doc_date_acc: str = ""
    version_rank: int = 0
    previous_version_id: str = ""
    next_version_id: str = ""
    is_latest: bool = False


ThresholdEvaluationStatus = Literal["admitted", "blocked", "not_applicable"]
ThresholdEvaluationReason = Literal[
    "threshold_satisfied",
    "threshold_violated",
    "threshold_unresolved",
    "threshold_not_applicable",
    "candidate_bound_missing",
    "threshold_bound_missing",
    "unit_unresolved",
    "unit_incompatible",
    "operator_unresolved",
    "temporal_not_in_force",
]
TemporalCompetenceStatus = Literal["in_force", "not_yet_in_force", "stale", "blocked"]


class LegalRuleThresholdRow(BaseModel):
    """Resolved L3 threshold row bound to its normative fact and provision lineage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    threshold_id: str
    fact_id: str
    metric: str
    operator: str
    value_decimal: float | None = None
    value_text: str = ""
    unit: str = ""
    applies_to: str = ""
    doc_id: str = ""
    doc_family_id: str = ""
    version_id: str = ""
    provision_anchor: str = ""
    provision_citation: str = ""
    provision_ref: str = ""
    jurisdiction: str = "UA"
    top_domain: str = ""
    norm_type: str = ""
    norm_type_canon: str = ""
    effective_from: str = ""
    effective_to: str = ""
    temporal_resolution_status: str = ""
    trust_tier: FactTrustTier = "search_candidate"


class LegalThresholdEvaluation(BaseModel):
    """Semantic evaluation of a candidate value against an L3 threshold."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ThresholdEvaluationStatus
    reason: ThresholdEvaluationReason
    threshold_ref: str
    threshold_id: str = ""
    fact_id: str = ""
    metric: str = ""
    operator: str = ""
    applies_to: str = ""
    normalized_candidate_value: float | None = None
    normalized_threshold_value: float | None = None
    canonical_unit: str = ""
    temporal_status: TemporalCompetenceStatus = "blocked"
    obligation_ref: str = ""
    provision_ref: str = ""


class LegalTemporalCompetence(BaseModel):
    """As-of temporal competence for an amendment or threshold-backed norm."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: TemporalCompetenceStatus
    subject_ref: str
    as_of: str
    effective_from: str = ""
    effective_to: str = ""
    amendment_id: str = ""
    amendment_type: str = ""
    stale_after: str = ""
    reason: str = ""


class LegalSourceAnchor(BaseModel):
    """Source anchor with full text and inherited structural hints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str
    version_id: str = ""
    anchor: str
    citation_label: str = ""
    provision_text: str = ""
    struct_kind: str = ""
    section_role: str = ""
    legal_unit_subtype: str = ""
    route_class: str = ""
    appendix_id: str = ""
    table_id: str = ""
    context_prefix: list[str] = Field(default_factory=list)


class LegalSourceBundle(BaseModel):
    """Grouped source bundle for verification passes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bundle_id: str
    doc_id: str
    version_id: str = ""
    doc_name: str = ""
    doc_reestr_code: str = ""
    source_family: str = ""
    primary_anchors: list[LegalSourceAnchor] = Field(default_factory=list)
    appendix_context: list[str] = Field(default_factory=list)
    reference_neighborhood: list[LegalReferenceEdgeResult] = Field(default_factory=list)
    version_chain: list[LegalDocVersionResult] = Field(default_factory=list)
    candidate_fact_ids: list[str] = Field(default_factory=list)
    candidate_provision_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
