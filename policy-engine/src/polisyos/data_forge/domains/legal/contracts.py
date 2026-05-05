"""Domain types for the legal knowledge graph (SPO entities, facts, provisions)."""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# SPO extraction output (Stage 3 -> Stage 4)
# ---------------------------------------------------------------------------


class ThresholdAtom(BaseModel):
    """Normalized threshold extracted from legal text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str = ""
    operator: str = ""
    value_decimal: str | None = None
    value_text: str | None = None
    unit: str | None = None
    applies_to: str | None = None


class RuleLink(BaseModel):
    """Cross-reference from a statement to another rule/provision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relation_type: str
    target_doc_id: str = ""
    target_anchor: str = ""
    ref_text_uk: str = ""
    resolution_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


FactTrustTier = Literal["search_candidate", "grounded_fact", "normative_fact"]
GroundingStatus = Literal[
    "exact_quote",
    "quote_without_offsets",
    "offsets_without_quote",
    "missing_quote",
]
CanonicalStatus = Literal["canonicalized", "partially_canonicalized", "raw"]
ReferenceResolutionStatus = Literal["resolved", "partial", "unresolved", "not_applicable"]


class SPOCandidate(BaseModel):
    """One extracted legal statement with compatibility + executable fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # --- Legacy/base fields (keep for compatibility) ---
    subject_en: str = Field(description="Canonical English concept (snake_case)")
    subject_uk: str = Field(description="Original Ukrainian text")
    predicate: str = Field(description="Relationship verb (English)")
    object_en: str = Field(description="Canonical English concept (snake_case)")
    object_uk: str = Field(description="Original Ukrainian text")
    fact_text: str = Field(description="Atomic fact in English")
    confidence: float = Field(ge=0.0, le=1.0)
    norm_type: str = Field(description="obligation | prohibition | permission | definition")

    # --- Stable identity / roles ---
    statement_id: str = ""
    actor_en: str = ""
    actor_uk: str = ""
    target_en: str = ""
    target_uk: str = ""
    beneficiary_en: str = ""
    beneficiary_uk: str = ""

    # --- Canonicalized action / modality ---
    action_raw: str = ""
    action_canon: str = ""
    norm_type_raw: str = ""
    norm_type_canon: str = ""

    # --- Rich fields ---
    fact_text_en: str = ""
    fact_text_uk: str = ""
    condition_text_uk: str = ""
    exception_text_uk: str = ""
    procedure_text_uk: str = ""
    temporal_text_uk: str = ""
    sanction_text_uk: str = ""
    source_quote_uk: str = ""
    source_quote_start: int | None = None
    source_quote_end: int | None = None
    grounding_status: GroundingStatus = "missing_quote"
    canonical_status: CanonicalStatus = "raw"
    reference_resolution_status: ReferenceResolutionStatus = "not_applicable"
    trust_tier: FactTrustTier = "search_candidate"
    constraint_type_raw: str = ""
    constraint_type_canon: str = ""
    structure_quality: str = ""
    doc_family_id: str = ""
    version_id: str = ""

    # --- Executable atoms ---
    thresholds: list[ThresholdAtom] = Field(default_factory=list)
    links: list[RuleLink] = Field(default_factory=list)

    # --- Confidence decomposition ---
    confidence_extract: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_verify: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_final: float | None = Field(default=None, ge=0.0, le=1.0)
    fused_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_breakdown_json: str = ""
    consistency_score: float | None = Field(default=None, ge=0.0, le=1.0)
    hallucination_flags_json: str = ""
    quality_band: str = ""

    @model_validator(mode="after")
    def _compat_defaults(self) -> SPOCandidate:
        action_raw = self.action_raw or self.predicate
        action_canon = self.action_canon or action_raw
        norm_type_raw = self.norm_type_raw or self.norm_type
        norm_type_canon = self.norm_type_canon or norm_type_raw
        fact_text_en = self.fact_text_en or self.fact_text
        actor_en = self.actor_en or self.subject_en
        actor_uk = self.actor_uk or self.subject_uk
        target_en = self.target_en or self.object_en
        target_uk = self.target_uk or self.object_uk
        confidence_extract = (
            self.confidence_extract if self.confidence_extract is not None else self.confidence
        )
        confidence_verify = (
            self.confidence_verify if self.confidence_verify is not None else self.confidence
        )
        confidence_final = (
            self.confidence_final if self.confidence_final is not None else self.confidence
        )

        if self.statement_id:
            statement_id = self.statement_id
        else:
            canon = "|".join(
                [
                    actor_en,
                    action_canon,
                    target_en,
                    fact_text_en,
                    self.source_quote_uk[:120],
                ]
            )
            statement_id = hashlib.sha256(canon.encode("utf-8")).hexdigest()[:20]

        # Keep offsets coherent when one side is absent.
        s_start = self.source_quote_start
        s_end = self.source_quote_end
        if (s_start is None) != (s_end is None):
            s_start = None
            s_end = None
        if s_start is not None and s_end is not None and s_end < s_start:
            s_start = None
            s_end = None

        if self.grounding_status != "missing_quote":
            grounding_status = self.grounding_status
        elif self.source_quote_uk.strip() and s_start is not None and s_end is not None:
            grounding_status = "exact_quote"
        elif self.source_quote_uk.strip():
            grounding_status = "quote_without_offsets"
        elif s_start is not None and s_end is not None:
            grounding_status = "offsets_without_quote"
        else:
            grounding_status = "missing_quote"

        if self.canonical_status != "raw":
            canonical_status = self.canonical_status
        elif action_canon and norm_type_canon:
            canonical_status = "canonicalized"
        elif action_canon or norm_type_canon:
            canonical_status = "partially_canonicalized"
        else:
            canonical_status = "raw"

        if self.reference_resolution_status != "not_applicable":
            reference_resolution_status = self.reference_resolution_status
        elif not self.links:
            reference_resolution_status = "not_applicable"
        else:
            resolved_links = sum(
                1 for link in self.links if link.target_doc_id.strip() or link.target_anchor.strip()
            )
            if resolved_links == len(self.links):
                reference_resolution_status = "resolved"
            elif resolved_links > 0:
                reference_resolution_status = "partial"
            else:
                reference_resolution_status = "unresolved"

        if self.structure_quality == "fallback_search_only":
            trust_tier = "search_candidate"
        elif self.trust_tier != "search_candidate":
            trust_tier = self.trust_tier
        else:
            confidence_rank = (
                self.fused_confidence
                if self.fused_confidence is not None
                else (confidence_final if confidence_final is not None else self.confidence)
            )
            if (
                grounding_status == "exact_quote"
                and canonical_status == "canonicalized"
                and (self.norm_type_canon or norm_type_canon)
                in {"obligation", "prohibition", "permission"}
                and confidence_rank >= 0.6
                and self.structure_quality != "fallback_search_only"
            ):
                trust_tier = "normative_fact"
            elif grounding_status == "exact_quote":
                trust_tier = "grounded_fact"
            else:
                trust_tier = "search_candidate"
        # Demote normative_fact only if there are actual blocking hallucination flags
        # (not just an empty JSON array "[]")
        if trust_tier == "normative_fact" and self.hallucination_flags_json.strip():
            try:
                _parsed_flags = __import__("json").loads(self.hallucination_flags_json)
            except Exception:
                _parsed_flags = []
            _blocking_types = {"phantom_article_reference", "phantom_number"}
            if any(
                str(f.get("type") or "") in _blocking_types
                for f in _parsed_flags
                if isinstance(f, dict)
            ):
                trust_tier = (
                    "grounded_fact" if grounding_status == "exact_quote" else "search_candidate"
                )

        object.__setattr__(self, "action_raw", action_raw)
        object.__setattr__(self, "action_canon", action_canon)
        object.__setattr__(self, "norm_type_raw", norm_type_raw)
        object.__setattr__(self, "norm_type_canon", norm_type_canon)
        object.__setattr__(self, "fact_text_en", fact_text_en)
        object.__setattr__(self, "actor_en", actor_en)
        object.__setattr__(self, "actor_uk", actor_uk)
        object.__setattr__(self, "target_en", target_en)
        object.__setattr__(self, "target_uk", target_uk)
        object.__setattr__(self, "confidence_extract", confidence_extract)
        object.__setattr__(self, "confidence_verify", confidence_verify)
        object.__setattr__(self, "confidence_final", confidence_final)
        object.__setattr__(self, "statement_id", statement_id)
        object.__setattr__(self, "source_quote_start", s_start)
        object.__setattr__(self, "source_quote_end", s_end)
        object.__setattr__(self, "grounding_status", grounding_status)
        object.__setattr__(self, "canonical_status", canonical_status)
        object.__setattr__(self, "reference_resolution_status", reference_resolution_status)
        object.__setattr__(self, "trust_tier", trust_tier)
        return self


class SPOExtractionResult(BaseModel):
    """Result of SPO extraction for a single provision (2-pass mode)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str
    provision_anchor: str
    provision_citation: str
    statements: list[SPOCandidate]

    # Raw model outputs
    raw_llm_response: str = ""
    raw_extract_response: str = ""
    raw_verify_response: str = ""

    # Pass metadata
    schema_version: str = "2.0"
    model_id: str = ""
    prompt_version: str = "lex_spo_v2"
    extract_passes: int = 2
    verify_report_json: str = ""
    normalization_report_json: str = ""
    low_confidence: bool = False
    low_confidence_reasons: list[str] = Field(default_factory=list)

    # Routing provenance (deterministic gate -> llm)
    extraction_source: str = "llm"  # rule_auto|llm|llm_gap_fill|audit_llm|deferred
    gate_score: float = 0.0
    gate_reason_codes: list[str] = Field(default_factory=list)
    legal_unit_subtype: str = ""
    legal_unit_micro_subtype: str = ""
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
    context_prefix: str = ""
    baseline_statement_count: int = 0
    llm_gap_fill_llm_statement_count: int = 0
    llm_gap_fill_added_statement_count: int = 0
    llm_error_class: str = ""
    llm_error_retryable: bool = False
    llm_error_http_status: int = 0
    llm_error_provider_key_index: int | None = None
    llm_error_retry_count: int = 0

    # Perf and usage
    latency_ms: int = 0
    pass1_latency_ms: int = 0
    pass2_latency_ms: int = 0
    token_count_prompt: int = 0
    token_count_completion: int = 0
    token_count_prompt_extract: int = 0
    token_count_completion_extract: int = 0
    token_count_prompt_verify: int = 0
    token_count_completion_verify: int = 0

    # Optional costs (available for some providers)
    cost_base_usd: float = 0.0
    cost_platform_usd: float = 0.0
    cost_total_usd: float = 0.0


__all__ = [
    "CanonicalStatus",
    "FactTrustTier",
    "GroundingStatus",
    "ReferenceResolutionStatus",
    "RuleLink",
    "SPOCandidate",
    "SPOExtractionResult",
    "ThresholdAtom",
]
